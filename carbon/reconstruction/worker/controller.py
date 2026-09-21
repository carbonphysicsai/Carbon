"""Trusted C-03 controller for one exact C-01 attempt/replica."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from carbon.construction import ResolvedConstructionPlan
from carbon.execution import (
    ClaimedExecution,
    DurableExecutionQueue,
    DurableWorkerLaunchStore,
    ExecutionFailure,
    ExecutionStage,
    PartialWorkRef,
    WorkerLaunchBinding,
)
from carbon.reconstruction.model import (
    PublicTrainingArchive,
    ReconstructionReceipt,
    ReconstructionStatus,
)
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import DevelopmentRepeatPlan, DevelopmentReplica
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    create_arguments,
    doctor,
    inspect_effective_controls,
    observe_effective_resources,
    remove_exact_container,
    spawn_watchdog,
)
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    OUTPUT_MEMBERS,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    WorkerLaunchState,
    WorkerTiming,
)
from carbon.reconstruction.worker.protocol import (
    decode_output_stream,
    snapshot_output,
    stage_request,
    validate_snapshot_bounded,
)
from carbon.seeding import DerivedSeed


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _boot_id() -> str:
    try:
        value = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        )
    except OSError:
        value = f"diagnostic-{platform.system().lower()}"
    return value


def _host_id() -> str:
    raw = platform.node() or "development-host"
    safe = "".join(
        character if character.isalnum() or character in "._:-" else "-"
        for character in raw
    )
    return safe[:128] or "development-host"


def _observed_output_bytes(result: object) -> int | None:
    """The output this run actually retained, or None if it was never observed.

    Read from the snapshot observation the export already records, so the batch
    is charged with the same number the run reports rather than a second,
    separately derived one. None - not zero - when the observation is absent:
    an unobserved output keeps the attempt's reserved worst case.
    """
    observation = getattr(result, "resource_observation", None)
    if type(observation) is not dict:
        return None
    snapshot = observation.get("output_snapshot")
    if type(snapshot) is not dict:
        return None
    observed = snapshot.get("observed_bytes")
    if type(observed) is not int or isinstance(observed, bool) or observed < 0:
        return None
    return observed


@dataclass(frozen=True, slots=True)
class WorkerRunResult:
    receipt: ReconstructionReceipt
    launch_digest: str
    effective_controls_digest: str
    output_snapshot_digest: str
    container_id: str
    timings: dict[str, float]
    effective_controls: dict[str, object]
    resource_observation: dict[str, object]
    snapshot_path: Path


class IsolatedReconstructionController:
    """Execute exactly one already-admitted replica in the pinned container."""

    def __init__(
        self,
        *,
        state_root: Path,
        execution_queue: DurableExecutionQueue,
        image: WorkerImageIdentity,
        cli: DockerCLI | None = None,
    ) -> None:
        if not state_root.is_absolute() or state_root.is_symlink():
            raise WorkerFailure(WorkerCode.INVALID)
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.state_root.chmod(0o700)
        (self.state_root / "outputs").mkdir(exist_ok=True)
        (self.state_root / "outputs").chmod(0o700)
        if type(execution_queue) is not DurableExecutionQueue:
            raise WorkerFailure(WorkerCode.INVALID)
        self.image = image
        self.execution_queue = execution_queue
        self.cli = cli or DockerCLI()
        self.store = DurableWorkerLaunchStore(state_root / "launches.sqlite3")

    def execute(
        self,
        *,
        claimed: ClaimedExecution,
        repeat_plan: DevelopmentRepeatPlan,
        replica: DevelopmentReplica,
        plan: ResolvedConstructionPlan,
        training_archive: PublicTrainingArchive,
        derived_seed: DerivedSeed,
        continuation_split_step: int | None = None,
        accelerator_role=None,
        local_diagnostic=None,
        cancelled: Callable[[], bool] | None = None,
    ) -> WorkerRunResult:
        from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
        from carbon.reconstruction.worker.accelerator_runtime import (
            AcceleratorHostAdmission,
            reject_existing_device_containers,
            verify_image_and_toolkit,
        )

        if (
            type(claimed) is not ClaimedExecution
            or type(replica) is not DevelopmentReplica
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        if cancelled is not None and not callable(cancelled):
            raise WorkerFailure(WorkerCode.INVALID)
        self._check_cancelled(cancelled)
        reconstruction = compile_development_profile(plan)
        options = {
            "claimed": claimed,
            "repeat_plan": repeat_plan,
            "replica": replica,
            "plan": plan,
            "training_archive": training_archive,
            "derived_seed": derived_seed,
            "continuation_split_step": continuation_split_step,
        }
        mapping = json.loads(reconstruction.mapping_receipt_json)
        if "execution_profile" not in mapping:
            if accelerator_role is not None:
                raise WorkerFailure(WorkerCode.POLICY)
            return self._execute_bound(**options, cancelled=cancelled)
        if reconstruction.profile_id != GPU_PROFILE.profile_id:
            raise WorkerFailure(WorkerCode.UNSUPPORTED)
        if type(accelerator_role) is not AcceleratorRole:
            raise WorkerFailure(WorkerCode.POLICY)
        if local_diagnostic is not None:
            # Explicit operator-only entry, taken before the strict-only loader
            # and never reached by falling back from a refused strict admission.
            # The caller must present a typed selector, which no public, miner,
            # customer or evaluator route can construct.
            return self._execute_local_diagnostic(
                options=options,
                local_diagnostic=local_diagnostic,
                accelerator_role=accelerator_role,
                claimed=claimed,
                replica=replica,
                cancelled=cancelled,
            )
        # Dispatch on the role, which has carried both values all along. The two
        # roles do different things: a miner searches privately for a better
        # strategy and submits a declarative recipe, so nothing they compute
        # locally enters the scientific record; a validator reconstructs and
        # trains from scratch, and that training is the record.
        #
        # There is no fallback in either direction. A refused strict admission
        # does not become a miner run, and a miner run is not presentable as
        # strict - each role reaches exactly one path, chosen before either
        # admission is attempted.
        if accelerator_role is AcceleratorRole.MINER_RESEARCH:
            return self._execute_miner_lane(
                options=options,
                accelerator_role=accelerator_role,
                replica=replica,
                cancelled=cancelled,
            )
        admission = AcceleratorHostAdmission.load()
        principal = claimed.binding.requester_identity.value
        admission.verify(
            principal=principal,
            state_root=self.state_root,
            image=self.image,
            role=accelerator_role,
            now=float(time.time()),
            dispatch=True,
        )
        identity = replica.binding.replicate_identity
        if (
            admission.document["resource_policy_digest"]
            != identity.policy_ref.content_digest
            or admission.document["resource_class_digest"]
            != identity.resource_class_ref.content_digest
        ):
            raise WorkerFailure(WorkerCode.POLICY)
        # The device this launch is bound to comes from the installed host
        # record, checked against the grant, so the same code runs on any host.
        from carbon.reconstruction.worker.accelerator_runtime import host_device

        worker_profile = DevelopmentWorkerProfile(
            identity.policy_ref.content_digest,
            identity.resource_class_ref.content_digest,
            "carbon.c03.cuda.development.v1",
            "1.0",
            GPU_PROFILE.profile_id,
            admission.digest,
            accelerator_role.value,
            None,
            None,
            host_device().device_uuid,
        )

        def still_owned():
            admission.verify(
                principal=principal,
                state_root=self.state_root,
                image=self.image,
                role=accelerator_role,
                now=float(time.time()),
            )
            if cancelled is None:
                return False
            return cancelled()

        with admission.exclusive_lease():
            still_owned()
            verify_image_and_toolkit(cli=self.cli, image=self.image)
            reject_existing_device_containers(cli=self.cli)
            return self._execute_bound(
                **options, worker_profile=worker_profile, cancelled=still_owned
            )

    def _execute_local_diagnostic(
        self,
        *,
        options,
        local_diagnostic,
        accelerator_role,
        claimed,
        replica,
        cancelled,
    ):
        """Run one approved local diagnostic. Never a relaxed strict execution.

        Reuses the existing image verification, shared host slot, allocation
        ownership and supervised worker path. What differs is the authority: a
        private development approval instead of a strict host grant, an attempt
        reserved durably before anything can attach the device, and an
        observation that claims no exclusivity.
        """
        from carbon.reconstruction.accelerators import GPU_PROFILE
        from carbon.reconstruction.worker.accelerator_runtime import (
            reject_existing_device_containers,
            verify_image_and_toolkit,
        )
        from carbon.reconstruction.worker.development_admission import (
            DevelopmentAttemptJournal,
            DevelopmentHostApproval,
            LocalDiagnosticRequest,
            diagnostic_plan_identity,
            effective_controls,
            require_development_approval,
        )
        from carbon.reconstruction.worker.model import LOCAL_DEVELOPMENT_AUTHORITY

        if type(local_diagnostic) is not LocalDiagnosticRequest:
            raise WorkerFailure(WorkerCode.POLICY)

        from carbon.reconstruction.worker.accelerator_runtime import host_device

        approval = require_development_approval(DevelopmentHostApproval.load())
        principal = claimed.binding.requester_identity.value

        # Derive the diagnostic-plan identity from the work actually about to
        # run, not from the selector's string. A selector that echoes a
        # well-formed digest cannot authorize a different recipe, input archive,
        # image, role, operation or limit set, because the derived body differs.
        plan = options.get("plan")
        archive = options.get("training_archive")
        if plan is None or archive is None:
            raise WorkerFailure(WorkerCode.INVALID)
        derived_digest, _ = diagnostic_plan_identity(
            construction_plan_digest=plan.to_ref().content_digest,
            training_archive_digest=archive.content_digest,
            training_archive_provenance=archive.provenance,
            training_archive_role=archive.role,
            image=self.image,
            profile_digest=GPU_PROFILE.digest,
            role=accelerator_role,
            operation=approval.document["operation"],
            limits=approval.document["limits"],
        )
        # The selector, the approval and the real work must all agree.
        if derived_digest != local_diagnostic.plan_digest:
            raise WorkerFailure(WorkerCode.POLICY)
        approval.verify(
            principal=principal,
            state_root=self.state_root,
            image=self.image,
            role=accelerator_role,
            plan_digest=derived_digest,
            input_digest=archive.content_digest,
            now=float(time.time()),
        )
        if local_diagnostic.input_digest != archive.content_digest:
            raise WorkerFailure(WorkerCode.POLICY)
        # Resolve the controls this run will actually execute under, before any
        # reservation or attachment. An approved limit that never leaves the
        # record is not a limit, and an unrepresentable one is refused here
        # rather than rounded up to something the implementation happens to
        # allow.
        controls = effective_controls(approval.document["limits"])
        identity = replica.binding.replicate_identity

        # Reserve the attempt durably before any container can be created, so a
        # crash, restart or new output directory cannot recover the allowance.
        journal = DevelopmentAttemptJournal()
        journal.reserve(
            nonce=local_diagnostic.nonce,
            plan_digest=derived_digest,
            budget=approval.document["attempt_budget"],
            controls=controls,
            now=float(time.time()),
        )
        # The attempt's clock starts at its reservation, so everything the
        # attempt holds the host for - the shared slot, image verification, the
        # run and its cleanup - is charged to the batch, not just the part
        # spent inside the container.
        attempt_started = time.monotonic()
        attempt_seconds = controls["attempt_seconds"]

        worker_profile = DevelopmentWorkerProfile(
            identity.policy_ref.content_digest,
            identity.resource_class_ref.content_digest,
            "carbon.c03.cuda.development.v1",
            "1.0",
            GPU_PROFILE.profile_id,
            approval.digest,
            accelerator_role.value,
            LOCAL_DEVELOPMENT_AUTHORITY,
            derived_digest,
            host_device().device_uuid,
            controls,
        )

        def still_owned():
            approval.verify(
                principal=principal,
                state_root=self.state_root,
                image=self.image,
                role=accelerator_role,
                plan_digest=derived_digest,
                input_digest=archive.content_digest,
                now=float(time.time()),
            )
            # The whole-attempt deadline, as distinct from the per-process one
            # the watchdog owns. Without it only the productive window was ever
            # bounded, so staging, export and cleanup could carry an attempt
            # past the limit it was admitted under - and past the batch window,
            # which is admitted on the promise that an attempt ends by then.
            #
            # Observed at the boundaries the existing cancellation channel is
            # already consulted at, so it interrupts the same non-destructive
            # way. It raises its own code rather than reporting itself as a
            # cancellation, because an operator stopping a run and a run
            # outliving its deadline are not the same event.
            if time.monotonic() - attempt_started > attempt_seconds:
                raise WorkerFailure(WorkerCode.DEADLINE)
            if cancelled is None:
                return False
            return cancelled()

        # The same shared Carbon device slot as strict work, not a parallel one.
        with approval.exclusive_lease():
            still_owned()
            verify_image_and_toolkit(cli=self.cli, image=self.image)
            reject_existing_device_containers(cli=self.cli)
            # Reconcile the attempt on both exits. An attempt that stays
            # RESERVED after its container is gone consumes one attempt and then
            # blocks every remaining one in the budget, so the terminal side of
            # the journal is not optional bookkeeping.
            try:
                result = self._execute_bound(
                    **options,
                    worker_profile=worker_profile,
                    cancelled=still_owned,
                )
            except BaseException:
                self._reconcile_local_attempt(
                    journal,
                    local_diagnostic.nonce,
                    succeeded=False,
                    elapsed=time.monotonic() - attempt_started,
                    observed_output_bytes=None,
                )
                raise
            self._reconcile_local_attempt(
                journal,
                local_diagnostic.nonce,
                succeeded=True,
                elapsed=time.monotonic() - attempt_started,
                observed_output_bytes=_observed_output_bytes(result),
            )
            return result

    def _execute_miner_lane(
        self,
        *,
        options,
        accelerator_role,
        replica,
        cancelled,
    ):
        """Run one miner-lane accelerator attempt.

        The CPU lane's requirements plus a device, and nothing beyond them. A
        miner receives a public construction plan and public TRAIN material,
        submits a declarative strategy rather than a trained checkpoint, and
        nothing they compute here is submitted, verified or scored. There is
        nothing on this host to protect, so device side-channels defend nothing
        and exclusivity buys nothing.

        What it does require is what makes a local run *faithful* - the same
        pinned image, the same containment, the same content-bound inputs, the
        same bounds - so that exercising a strategy here predicts what a
        validator will get. That is the reason the tooling exists.

        What it deliberately does not do: load a host grant, take the shared
        Carbon slot, enumerate compute processes, claim exclusivity, verify
        whole-device release, or create quarantine.
        """
        from carbon.reconstruction.accelerators import GPU_PROFILE
        from carbon.reconstruction.onboarding import doctor_report, miner_lane_blockers
        from carbon.reconstruction.worker.accelerator_runtime import (
            HOST_ROOT,
            host_device,
            miner_device_lease,
            reject_existing_device_containers,
            verify_image_and_toolkit,
        )
        from carbon.reconstruction.worker.model import (
            MINER_HOST_AUTHORITY,
            registered_run_controls,
        )

        # The device comes from the operator-installed record, which fails
        # closed when it is missing or malformed. Carbon never infers a host's
        # hardware from whatever happens to be visible at dispatch time.
        device = host_device()

        # Readiness is checked, not assumed, and it is the same read-only report
        # the operator runs. Only the findings this lane actually requires can
        # block it - see `MINER_LANE_REQUIRED_CHECKS`, which names what is left
        # out and why. Unknown telemetry stays unknown instead of stopping a
        # miner, which is the point of the lane.
        if miner_lane_blockers(doctor_report(root=HOST_ROOT, cli=self.cli)):
            raise WorkerFailure(WorkerCode.POLICY)

        identity = replica.binding.replicate_identity
        worker_profile = DevelopmentWorkerProfile(
            identity.policy_ref.content_digest,
            identity.resource_class_ref.content_digest,
            "carbon.c03.cuda.development.v1",
            "1.0",
            GPU_PROFILE.profile_id,
            device.digest,
            accelerator_role.value,
            MINER_HOST_AUTHORITY,
            None,
            device.device_uuid,
            registered_run_controls(),
        )

        # This miner's own concurrent runs, not a claim about the device.
        with miner_device_lease(device.device_uuid):
            verify_image_and_toolkit(cli=self.cli, image=self.image)
            # Retained Carbon work on this device still blocks, by Carbon's own
            # label. Other work on the GPU is the miner's business.
            reject_existing_device_containers(cli=self.cli)
            return self._execute_bound(
                **options,
                worker_profile=worker_profile,
                cancelled=cancelled,
            )

    @staticmethod
    def _reconcile_local_attempt(
        journal, nonce, *, succeeded, elapsed, observed_output_bytes
    ):
        """Settle one development attempt from observed host state.

        Deliberately not an unconditional settlement. The attempt is reconciled
        only when this host no longer holds resources this launch owned; if the
        allocation record survives or a strict quarantine exists, the attempt is
        recorded AMBIGUOUS and keeps blocking until an operator reconciles it.
        Unknown cleanup is not a free attempt.

        If this process dies before reaching here the marker stays RESERVED,
        which also blocks. Both defaults fail towards blocking rather than
        towards another launch.

        A settlement failure never replaces the run's own outcome: an unsettled
        marker is the safe direction, and masking the real error with a
        bookkeeping one would lose the reason the run ended.
        """
        from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT
        from carbon.reconstruction.worker.development_admission import (
            ATTEMPT_AMBIGUOUS,
            ATTEMPT_COMPLETED,
            ATTEMPT_RECONCILED,
        )

        try:
            unresolved = (HOST_ROOT / "active-allocation.json").exists() or (
                HOST_ROOT / "device-quarantined"
            ).exists()
            if unresolved:
                state = ATTEMPT_AMBIGUOUS
            elif succeeded:
                state = ATTEMPT_COMPLETED
            else:
                # Cleaned up, but it produced no result. Recording this as
                # COMPLETED would claim science that did not happen.
                state = ATTEMPT_RECONCILED
            # Rounded up, never down: a partial second the batch really spent
            # is charged as a whole one rather than discarded.
            journal.settle(
                nonce=nonce,
                state=state,
                observed_seconds=math.ceil(elapsed),
                observed_output_bytes=observed_output_bytes,
            )
        except (WorkerFailure, OSError):
            return

    @staticmethod
    def _check_cancelled(cancelled):
        if cancelled is not None:
            value = cancelled()
            if type(value) is not bool:
                raise WorkerFailure(WorkerCode.INVALID)
            if value:
                raise WorkerFailure(WorkerCode.CANCELLED)

    def _remove_stage(self, stage):
        if stage.parent != self.state_root / "staging" or stage.is_symlink():
            raise WorkerFailure(WorkerCode.CLEANUP)
        if stage.exists():
            try:
                stage.chmod(0o700)
                shutil.rmtree(stage)
            except OSError:
                raise WorkerFailure(WorkerCode.CLEANUP) from None

    def _execute_bound(
        self,
        *,
        claimed: ClaimedExecution,
        repeat_plan: DevelopmentRepeatPlan,
        replica: DevelopmentReplica,
        plan: ResolvedConstructionPlan,
        training_archive: PublicTrainingArchive,
        derived_seed: DerivedSeed,
        continuation_split_step: int | None = None,
        worker_profile: DevelopmentWorkerProfile | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> WorkerRunResult:
        if (
            type(claimed) is not ClaimedExecution
            or type(repeat_plan) is not DevelopmentRepeatPlan
            or type(replica) is not DevelopmentReplica
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        identity = replica.binding.replicate_identity
        if worker_profile is None:
            worker_profile = DevelopmentWorkerProfile(
                identity.policy_ref.content_digest,
                identity.resource_class_ref.content_digest,
            )
        started_unix = float(time.time())
        started_mono = float(time.monotonic())
        timing = WorkerTiming(
            started_unix,
            started_unix + worker_profile.effective_deadline_seconds,
            started_mono,
            _boot_id(),
            worker_profile.effective_deadline_seconds,
        )
        stage_started = time.monotonic()
        stage, stage_digest = stage_request(
            stage_root=self.state_root / "staging",
            claimed=claimed,
            repeat_plan=repeat_plan,
            replica=replica,
            plan=plan,
            training_archive=training_archive,
            derived_seed=derived_seed,
            worker_profile=worker_profile,
            continuation_split_step=continuation_split_step,
        )
        stage_seconds = time.monotonic() - stage_started
        stable = _canonical(
            {
                "execution_id": f"{claimed.claim.ref.submission_id.value}:{claimed.claim.ref.attempt_number}",
                "replicate_digest": identity.replicate_digest,
                "profile": worker_profile.digest,
                "image": self.image.image_id,
                "stage": stage_digest,
            }
        )
        container_name = "carbon-c03-" + hashlib.sha256(stable).hexdigest()[:32]
        reconstruction_profile = compile_development_profile(plan)
        binding = WorkerLaunchBinding(
            claim=claimed.claim,
            replicate_id=identity.replicate_id,
            replicate_digest=identity.replicate_digest,
            plan_digest=plan.to_ref().content_digest,
            reconstruction_profile_digest=reconstruction_profile.profile_digest,
            training_data_digest=training_archive.content_digest,
            randomness_digest=replica.randomness_digest,
            stage_digest=stage_digest,
            worker_profile=worker_profile,
            image=self.image,
            timing=timing,
            host_id=_host_id(),
            container_name=container_name,
        )
        retained_payload = self.store.binding_payload(binding.execution_id)
        if retained_payload is not None:
            candidate_payload = binding.payload
            replay_fields = set(candidate_payload) - {"timing"}
            if any(
                retained_payload.get(field) != candidate_payload[field]
                for field in replay_fields
            ):
                self._remove_stage(stage)
                raise WorkerFailure(WorkerCode.CONFLICT)
            retained_status = self.store.raw_status(binding.execution_id)
            if (
                retained_status is None
                or retained_status["state"] != WorkerLaunchState.ASSOCIATED.value
                or type(retained_status["launch_digest"]) is not str
                or type(retained_status["effective_controls_digest"]) is not str
                or type(retained_status["output_snapshot_digest"]) is not str
                or type(retained_status["container_id"]) is not str
            ):
                self._remove_stage(stage)
                raise WorkerFailure(WorkerCode.CONFLICT)
            snapshot = (
                self.state_root / "snapshots" / retained_status["launch_digest"][7:]
            )
            # An associated replay revalidates the retained bytes in the same
            # bounded native-parser process. Rebuild the read-only stage only
            # for that validation; it creates no worker execution effect.
            receipt = validate_snapshot_bounded(snapshot, stage)
            self._remove_stage(stage)
            return WorkerRunResult(
                receipt,
                retained_status["launch_digest"],
                retained_status["effective_controls_digest"],
                retained_status["output_snapshot_digest"],
                retained_status["container_id"],
                {"replay": 0.0, "total": float(time.monotonic() - started_mono)},
                {"retained_exact_replay": True},
                retained_status.get("resource_observation")
                or {
                    "schema": "carbon.c03.resource-observation.v1",
                    "status": "UNAVAILABLE_FOR_HISTORICAL_REPLAY",
                },
                snapshot,
            )
        try:
            record = self.store.record_intent(binding)
            if record.state is not WorkerLaunchState.INTENT_RECORDED:
                raise WorkerFailure(WorkerCode.CONFLICT)
            if not self.store.claim_create(binding):
                raise WorkerFailure(WorkerCode.CONFLICT)
        except BaseException:
            self._remove_stage(stage)
            raise
        checked = doctor(
            image_id=self.image.image_id,
            image_identity=self.image,
            cli=self.cli,
        )
        if not checked.eligible or checked.cpuset is None:
            self.store.transition(
                binding,
                WorkerLaunchState.FAILED_INFRA,
                terminal_code=checked.code,
            )
            self._remove_stage(stage)
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        create_started = time.monotonic()
        if worker_profile.accelerator_profile_id is not None:
            from carbon.reconstruction.worker.accelerator_runtime import (
                mark_device_allocation,
            )

            # The authority is recorded with the allocation so cleanup can
            # complete it under the same rules it was created under.
            mark_device_allocation(
                container_name=container_name,
                launch_digest=binding.launch_digest,
                authority=worker_profile.accelerator_authority,
            )
        try:
            created = self.cli.run(
                create_arguments(
                    container_name=container_name,
                    image_id=self.image.image_id,
                    input_directory=stage,
                    cpuset=checked.cpuset,
                    launch_digest=binding.launch_digest,
                    worker_profile=worker_profile,
                ),
                timeout=30,
            )
            container_id = created.stdout.decode("ascii", "strict").strip()
        except (WorkerFailure, UnicodeError):
            # Create may have succeeded even if its response was lost. The
            # deterministic name and exact label are the idempotency key.
            try:
                observed = self.cli.json(
                    ["inspect", container_name, "--format", "{{json .}}"]
                )
                if (
                    type(observed) is not dict
                    or observed.get("Config", {})
                    .get("Labels", {})
                    .get("org.opencontainers.image.carbon.c03.launch")
                    != binding.launch_digest
                ):
                    raise WorkerFailure(WorkerCode.CONFLICT)
                container_id = observed["Id"]
            except (WorkerFailure, KeyError, TypeError):
                self.store.transition(
                    binding, WorkerLaunchState.RECONCILIATION_REQUIRED
                )
                raise WorkerFailure(WorkerCode.RUNTIME) from None
        create_seconds = time.monotonic() - create_started
        self.store.transition(
            binding, WorkerLaunchState.CREATED, container_id=container_id
        )
        execution_running = False
        try:
            # Start the independent deadline owner before dispatching actual work.
            spawn_watchdog(
                container_name=container_name,
                launch_digest=binding.launch_digest,
                deadline_unix=timing.productive_deadline_unix,
            )
            self.cli.run(["start", container_name], timeout=20)
            self._wait_file(container_name, "/scratch/control-ready", timing, cancelled)
            controls_digest, controls = inspect_effective_controls(
                cli=self.cli,
                container_name=container_name,
                image_id=self.image.image_id,
                input_directory=stage,
                cpuset=checked.cpuset,
                launch_digest=binding.launch_digest,
                worker_profile=worker_profile,
            )
            self.store.transition(
                binding,
                WorkerLaunchState.CONTROLS_VERIFIED,
                effective_controls_digest=controls_digest,
            )
            self._check_cancelled(cancelled)
            self.execution_queue.mark_running(claimed.claim)
            execution_running = True
            self.cli.run(
                [
                    "exec",
                    "--user",
                    "65532:65532",
                    container_name,
                    "/usr/bin/touch",
                    "/scratch/authorized",
                ],
                timeout=10,
            )
            self.store.transition(binding, WorkerLaunchState.RUNNING)
            numerical_started = time.monotonic()
            self._wait_file(container_name, "/scratch/ready", timing, cancelled)
            numerical_seconds = time.monotonic() - numerical_started
            export_started = time.monotonic()
            raw_parent = Path(
                tempfile.mkdtemp(prefix=".c03-raw-", dir=self.state_root / "outputs")
            )
            raw = raw_parent / "output"
            framed = raw_parent / "output.stream"
            self.cli.stream_to_file(
                [
                    "exec",
                    "--user",
                    "65532:65532",
                    container_name,
                    "/opt/carbon-worker/bin/python",
                    "-I",
                    "-m",
                    "carbon.reconstruction.worker.exporter",
                ],
                framed,
                maximum=worker_profile.effective_output_bytes + 2 * CONTROL_BYTES,
                timeout=30,
            )
            decode_output_stream(framed, raw)
            framed.unlink()
            snapshot, snapshot_digest = snapshot_output(
                raw,
                self.state_root / "snapshots",
                destination_name=binding.launch_digest[7:],
            )
            shutil.rmtree(raw_parent, ignore_errors=True)
            export_seconds = time.monotonic() - export_started
            resource_observation = observe_effective_resources(
                cli=self.cli, container_name=container_name
            )
            output_members = tuple(
                member for member in snapshot.rglob("*") if member.is_file()
            )
            resource_observation["output_snapshot"] = {
                "observed_bytes": sum(
                    member.stat().st_size for member in output_members
                ),
                "observed_members": len(output_members),
                "bounded_bytes": worker_profile.effective_output_bytes,
                "bounded_members": OUTPUT_MEMBERS,
            }
            self.store.transition(
                binding,
                WorkerLaunchState.OUTPUT_SNAPSHOTTED,
                output_snapshot_digest=snapshot_digest,
                resource_observation=resource_observation,
            )
            cleanup_started = time.monotonic()
            remove_exact_container(
                cli=self.cli,
                container_name=container_name,
                launch_digest=binding.launch_digest,
            )
            cleanup_seconds = time.monotonic() - cleanup_started
            self.store.transition(binding, WorkerLaunchState.TERMINATED)
            validation_started = time.monotonic()
            receipt = validate_snapshot_bounded(snapshot, stage)
            if receipt.status is not ReconstructionStatus.COMPLETE:
                raise WorkerFailure(WorkerCode.OUTPUT)
            validation_seconds = time.monotonic() - validation_started
            self._check_cancelled(cancelled)
            self._remove_stage(stage)
            self.execution_queue.record_partial(
                claimed.claim,
                PartialWorkRef(
                    ExecutionStage.RECONSTRUCTION,
                    "c03-" + binding.launch_digest[7:39],
                    receipt.artifact_digest,
                ),
            )
            self.store.transition(binding, WorkerLaunchState.ASSOCIATED)
            return WorkerRunResult(
                receipt,
                binding.launch_digest,
                controls_digest,
                snapshot_digest,
                container_id,
                {
                    "staging": float(stage_seconds),
                    "create": float(create_seconds),
                    "numerical": float(numerical_seconds),
                    "export": float(export_seconds),
                    "validation": float(validation_seconds),
                    "cleanup": float(cleanup_seconds),
                    "total": float(time.monotonic() - started_mono),
                },
                controls,
                resource_observation,
                snapshot,
            )
        except BaseException as error:
            terminal_code = (
                error.code if type(error) is WorkerFailure else WorkerCode.RUNTIME
            )
            failure_observation: dict[str, object]
            try:
                failure_observation = observe_effective_resources(
                    cli=self.cli, container_name=container_name
                )
            except WorkerFailure:  # retain unavailability, never mask cause
                failure_observation = {
                    "schema": "carbon.c03.resource-observation.v1",
                    "status": "UNAVAILABLE_AT_FAILURE",
                }
            failure_observation["terminal"] = {
                "worker_code": terminal_code.value,
                "elapsed_seconds": float(time.monotonic() - started_mono),
                "admitted_deadline_seconds": worker_profile.effective_deadline_seconds,
                "consumption": "OBSERVED_PARTIAL_OR_UNKNOWN",
                "replacement_authority": "NONE",
            }
            try:
                remove_exact_container(
                    cli=self.cli,
                    container_name=container_name,
                    launch_digest=binding.launch_digest,
                )
            except WorkerFailure:
                try:
                    self.store.transition(
                        binding,
                        WorkerLaunchState.RECONCILIATION_REQUIRED,
                        terminal_code=WorkerCode.CLEANUP.value,
                        resource_observation=failure_observation,
                    )
                    self.store.transition(binding, WorkerLaunchState.QUARANTINED)
                except WorkerFailure:
                    pass
                raise WorkerFailure(WorkerCode.QUARANTINED) from None
            self._remove_stage(stage)
            if execution_running:
                try:
                    # C-01 admits a successor only from RETRYABLE_INFRA. This
                    # source-owned terminal is deliberately FAILED_INFRA so a
                    # deadline, policy/resource exhaustion, malformed output,
                    # or native-parser failure cannot mint a fresh budget.
                    self.execution_queue.fail_infrastructure(claimed.claim)
                except ExecutionFailure:
                    pass
            try:
                current = self.store.raw_status(binding.execution_id)
                if current and current["state"] not in {
                    WorkerLaunchState.ASSOCIATED.value,
                    WorkerLaunchState.CANCELLED.value,
                    WorkerLaunchState.FAILED_INFRA.value,
                }:
                    target = (
                        WorkerLaunchState.CANCELLED
                        if terminal_code in {WorkerCode.CANCELLED, WorkerCode.DEADLINE}
                        else WorkerLaunchState.FAILED_INFRA
                    )
                    self.store.transition(
                        binding,
                        target,
                        terminal_code=terminal_code.value,
                        resource_observation=failure_observation,
                    )
            except WorkerFailure:
                pass
            raise

    def _wait_file(
        self, container_name: str, path: str, timing: WorkerTiming, cancelled=None
    ) -> None:
        while time.monotonic() < timing.productive_deadline_monotonic:
            self._check_cancelled(cancelled)
            result = self.cli.run(
                ["exec", container_name, "/usr/bin/test", "-f", path],
                timeout=5,
                accepted=(0, 1),
            )
            if result.returncode == 0:
                self._check_cancelled(cancelled)
                return
            state = self.cli.json(
                ["inspect", container_name, "--format", "{{json .State}}"]
            )
            if type(state) is not dict or state.get("Running") is not True:
                raise WorkerFailure(WorkerCode.RUNTIME)
            time.sleep(0.1)
        raise WorkerFailure(WorkerCode.DEADLINE)


__all__ = ["IsolatedReconstructionController", "WorkerRunResult"]
