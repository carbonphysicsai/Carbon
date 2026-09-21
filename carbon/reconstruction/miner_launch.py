"""Start, stop and clean up a miner-lane accelerator run on this host.

A miner rents compute from a provider through the launchpad and approves a
budget. Carbon's worker has to start on hardware nobody chose in advance, and it
has to stop and clean up on the same hardware - a container left behind on a
laptop wastes nothing, but on a rented instance it bills until somebody notices.

So this is an operator entry point, not a scheduler. It wraps
`IsolatedReconstructionController` and the launch store that already exist:
every admission, bound, transition and cleanup decision stays where it was, and
nothing here can start work the controller would not have started, or finish
work the store would not have finished.

Three operations:

``launch``   assemble one execution from a manifest and run it on the miner lane
``request_cancel``  ask a running launch to stop, durably and non-destructively
``recover``  remove containers this host's unfinished launches still own

Cancellation is a file rather than a signal because the process that cancels is
not the process that runs, and because a request must survive both of them. It
is observed at the boundaries the controller already checks, so stopping is as
orderly as any other cancellation and never kills a container out from under
its own cleanup.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from dataclasses import replace as _replace
from pathlib import Path

from carbon.construction import (
    ResolvedConstructionPlanRef,
    decode_resolved_construction_plan,
)
from carbon.development_session.profile import digest as _digest
from carbon.execution import (
    DurableExecutionQueue,
)
from carbon.reconstruction.accelerators import AcceleratorRole
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.worker.model import (
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    exact_digest,
    exact_token,
)
from carbon.resource_policy import (
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
)
from carbon.seeding import DerivedSeed

LAUNCH_SCHEMA = "carbon.accelerator-miner-launch.v1"
CANCEL_SCHEMA = "carbon.accelerator-miner-cancel.v1"
CANCEL_DIRECTORY = "cancel-requests"

# Everything a launch needs and nothing it does not. Closed, like every other
# record on this path: an unexpected key is refused rather than ignored, so a
# manifest cannot smuggle a field the controller would read.
# The manifest supplies *materials*, not identity. Which execution this is, who
# requested it and what seed it is pinned to already exist in the durable queue,
# put there by whoever admitted the work - and the seed pin could not be carried
# in a file even if it were wanted, because `EvaluationBinding` is deliberately
# opaque and exposes no accessor. Reconstructing identity here would mean
# inventing a second, weaker version of it.
REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "replicate_id",
        "paths",
        "plan_ref",
        "policy_ref",
        "resource_class_ref",
        "image",
    }
)
REQUIRED_PATHS = frozenset({"plan", "training_archive", "randomness"})
REQUIRED_PLAN_REF = frozenset(
    {
        "challenge_id",
        "challenge_version",
        "schema_version",
        "canonicalization_profile",
        "digest",
    }
)
REQUIRED_IMAGE = frozenset(
    {
        "image_id",
        "config_digest",
        "source_tree_digest",
        "wheel_digest",
        "lock_digest",
        "base_image_digest",
        "build_recipe_digest",
        "entrypoint_digest",
    }
)
REQUIRED_POLICY_REF = frozenset(
    {
        "challenge_id",
        "challenge_version",
        "object_id",
        "object_version",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    }
)


def _closed(value: object, required: frozenset[str], code=WorkerCode.INVALID) -> dict:
    if type(value) is not dict or set(value) != required:
        raise WorkerFailure(code)
    return value


def _within(root: Path, name: object) -> Path:
    """A manifest names files beside itself, never elsewhere on the host."""
    if type(name) is not str or not name or name != os.path.basename(name):
        raise WorkerFailure(WorkerCode.INVALID)
    resolved = (root / name).resolve()
    if resolved.parent != root.resolve() or not resolved.is_file():
        raise WorkerFailure(WorkerCode.INVALID)
    if resolved.is_symlink():
        raise WorkerFailure(WorkerCode.INVALID)
    return resolved


@dataclass(frozen=True, slots=True)
class MinerLaunchRequest:
    """One assembled launch, read from an operator-supplied manifest."""

    root: Path
    document: dict

    @classmethod
    def load(cls, path: Path) -> MinerLaunchRequest:
        path = Path(path).resolve()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.INVALID) from None
        _closed(document, REQUIRED_FIELDS)
        if document["schema"] != LAUNCH_SCHEMA:
            raise WorkerFailure(WorkerCode.INVALID)
        _closed(document["paths"], REQUIRED_PATHS)
        _closed(document["plan_ref"], REQUIRED_PLAN_REF)
        _closed(document["image"], REQUIRED_IMAGE)
        _closed(document["policy_ref"], REQUIRED_POLICY_REF)
        _closed(document["resource_class_ref"], REQUIRED_POLICY_REF)
        if type(document["replicate_id"]) is not str or not document["replicate_id"]:
            raise WorkerFailure(WorkerCode.INVALID)
        return cls(path.parent, document)

    @property
    def image(self) -> WorkerImageIdentity:
        values = self.document["image"]
        # By keyword, deliberately. These are eight interchangeable-looking
        # digest strings, and a positional list would mis-assign them silently
        # if either order ever changed.
        return WorkerImageIdentity(**{name: values[name] for name in REQUIRED_IMAGE})

    def plan(self):
        from carbon.registry import ChallengeKey

        reference = self.document["plan_ref"]
        expected = ResolvedConstructionPlanRef(
            ChallengeKey(reference["challenge_id"], reference["challenge_version"]),
            reference["schema_version"],
            reference["canonicalization_profile"],
            reference["digest"],
        )
        payload = _within(self.root, self.document["paths"]["plan"]).read_bytes()
        return decode_resolved_construction_plan(payload, expected_ref=expected)

    def training_archive(self) -> PublicTrainingArchive:
        # Type-enforced public at construction: any role but TRAIN is refused
        # there, so a manifest cannot point this at protected material.
        return PublicTrainingArchive.from_file(
            _within(self.root, self.document["paths"]["training_archive"]),
            provenance="miner_lane_launch",
        )

    def derived_seed(self) -> DerivedSeed:
        return DerivedSeed(
            _within(self.root, self.document["paths"]["randomness"]).read_bytes()
        )

    def refs(self):
        """The policy and resource-class identities this launch is bound to.

        Rebuilt from their recorded fields rather than trusted as opaque values,
        so a malformed reference is refused by the same constructor that built
        the original instead of reaching the controller.
        """
        from carbon.registry import ChallengeKey
        from carbon.resource_policy import ResearchResourcePolicyRef, ResourceClassRef

        def build(ref_type, values):
            return ref_type(
                ChallengeKey(values["challenge_id"], values["challenge_version"]),
                values["object_id"],
                values["object_version"],
                values["schema_version"],
                values["canonicalization_profile"],
                values["content_digest"],
            )

        return (
            build(ResearchResourcePolicyRef, self.document["policy_ref"]),
            build(ResourceClassRef, self.document["resource_class_ref"]),
        )


def _cancel_path(state_root: Path, execution_id: str) -> Path:
    return Path(state_root) / CANCEL_DIRECTORY / f"{exact_token(execution_id)}.json"


def request_cancel(
    *, state_root: Path, execution_id: str, schema: str = CANCEL_SCHEMA
) -> Path:
    """Ask a running launch to stop. Durable, and destroys nothing itself.

    Writing a request is all this does. The run observes it at the boundaries
    the controller already checks and then performs its own ordinary cleanup, so
    a cancel never removes a container out from under the code responsible for
    confirming its removal.

    Cancelling is a property of the host and the execution, not of the lane, so
    the validator entry point shares this implementation rather than growing a
    second one that could drift.

    **That lane-independence is deliberate and is part of the contract.** The
    request is keyed by execution id alone, so either entry point can stop a
    launch of either lane on the same host. An execution id already names exactly
    one admitted execution, which ran in exactly one lane, so putting the lane in
    the key would disambiguate nothing and would only create a way for a correct
    cancel to silently miss - the dangerous failure for a stop whose purpose is
    halting spend.

    `schema` only labels the written record with the tool that produced it. It
    does not select a lane or a role, does not convert work between lanes, and
    does not touch any durable execution identity; the request is located and
    observed by execution id either way.
    """
    from carbon.development_session.profile import canonical

    path = _cancel_path(state_root, execution_id)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = canonical({"schema": schema, "execution_id": execution_id})
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
    return path


def cancel_requested(*, state_root: Path, execution_id: str) -> bool:
    return _cancel_path(state_root, execution_id).exists()


def clear_cancel(*, state_root: Path, execution_id: str) -> None:
    """Clear a served request. A stale one must not cancel the next launch."""
    try:
        _cancel_path(state_root, execution_id).unlink(missing_ok=True)
    except OSError:
        raise WorkerFailure(WorkerCode.UNAVAILABLE) from None


def launch(
    *,
    request: MinerLaunchRequest,
    state_root: Path,
    queue_path: Path | None = None,
    cli=None,
    worker_id: str = "miner-lane",
):
    """Claim one admitted execution and run it on the miner lane.

    Assembly only. The execution, its requester and its seed identity are *not*
    built here: they already exist in the durable queue, put there by whoever
    admitted the work, and this claims one rather than inventing a second,
    weaker identity beside it. The manifest supplies materials, and each is
    checked against the digests the binding already committed to - so a manifest
    naming different work than the queue admitted is refused rather than run.

    Every decision that matters - whether this host may run at all, what bounds
    apply, what is cleaned up - belongs to the controller and stays there. The
    role is fixed to MINER_RESEARCH and is not a parameter, because a caller
    that could choose it could choose the lane.
    """
    from carbon.reconstruction.worker.controller import IsolatedReconstructionController
    from carbon.reconstruction.worker.docker_runtime import DockerCLI

    state_root = Path(state_root).resolve()
    queue = DurableExecutionQueue(
        Path(queue_path) if queue_path else state_root / "miner-launch-queue.sqlite3"
    )
    claim_id = exact_token(f"miner-{os.getpid()}")
    claimed = queue.claim_next(worker_id, claim_id=claim_id)
    if claimed is None:
        # Nothing admitted. Not an error in the work, and nothing is invented to
        # give the host something to do.
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    binding = claimed.binding
    plan = request.plan()
    archive = request.training_archive()
    seed = request.derived_seed()
    policy_ref, resource_class_ref = request.refs()
    profile = compile_development_profile(plan)
    plan_ref = plan.to_ref()

    # The manifest and the admitted binding must describe the same work. Checked
    # before anything is staged, because a mismatch here means the host was
    # handed materials for a different execution.
    if (
        plan_ref.content_digest != binding.resolved_plan_digest
        or profile.profile_digest != binding.reconstruction_policy_digest
        or policy_ref.content_digest != binding.resource_policy_digest
    ):
        raise WorkerFailure(WorkerCode.POLICY)

    execution = claimed.claim.ref
    request_digest = exact_digest(plan_ref.content_digest)

    placeholder = BoundReconstructionReplicate(
        ReconstructionReplicateIdentity(
            plan.challenge_key,
            plan_ref,
            policy_ref,
            resource_class_ref,
            request.document["replicate_id"],
            request_digest,
        )
    )
    randomness = _digest(seed.as_backend_bytes())
    replicate_digest = development_replicate_digest(
        binding=placeholder,
        execution_ref=execution,
        randomness_digest=randomness,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
    )
    replica = DevelopmentReplica(
        BoundReconstructionReplicate(
            _replace(placeholder.replicate_identity, replicate_digest=replicate_digest)
        ),
        execution,
        randomness,
    )
    repeat = freeze_development_repeat_plan(
        plan_id="miner-" + request_digest[7:39],
        construction_plan_digest=plan_ref.content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=(replica,),
    )

    controller = IsolatedReconstructionController(
        state_root=state_root,
        execution_queue=queue,
        image=request.image,
        cli=cli or DockerCLI(),
    )
    execution_id = f"{execution.submission_id.value}-{execution.attempt_number}"

    def cancelled() -> bool:
        return cancel_requested(state_root=state_root, execution_id=execution_id)

    try:
        return controller.execute(
            claimed=claimed,
            repeat_plan=repeat,
            replica=replica,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            accelerator_role=AcceleratorRole.MINER_RESEARCH,
            cancelled=cancelled,
        )
    finally:
        # A served request must not cancel whatever runs next on this host.
        clear_cancel(state_root=state_root, execution_id=execution_id)


def recover(
    *,
    state_root: Path,
    cli=None,
    dry_run: bool = False,
    schema: str = "carbon.accelerator-miner-recover.v1",
) -> dict:
    """Remove containers this host's unfinished launches still own.

    Cost control, on a rented instance. A launch that ended without reaching a
    terminal state may still own a running container, and nothing reclaims it on
    its own.

    Reclaiming is a property of the host and its launch store rather than of the
    lane a launch ran in, so the validator entry point shares this
    implementation. `schema` names the tool that produced the report and changes
    nothing about what is reclaimed.

    Scoped to exactly those containers: the store supplies each launch's own
    name and digest, and removal confirms that exact container is gone. Nothing
    else on the host is touched, and a removal that cannot be confirmed leaves
    the launch blocking rather than reporting a release it did not observe.
    """
    from carbon.execution.worker import DurableWorkerLaunchStore
    from carbon.reconstruction.worker.docker_runtime import (
        DockerCLI,
        remove_exact_container,
    )

    state_root = Path(state_root).resolve()
    store = DurableWorkerLaunchStore(state_root / "launches.sqlite3")
    cli = cli or DockerCLI()
    outcomes = []
    for target in store.reconciliation_targets():
        entry = {
            "execution_id": target["execution_id"],
            "container_name": target["container_name"],
            "state": target["state"],
        }
        if dry_run:
            entry["action"] = "WOULD_REMOVE"
            outcomes.append(entry)
            continue
        cleaned = True
        try:
            remove_exact_container(
                cli=cli,
                container_name=target["container_name"],
                launch_digest=target["launch_digest"],
            )
        except WorkerFailure as failure:
            cleaned = False
            entry["detail"] = failure.code.value
        entry["removed"] = cleaned
        entry["resulting_state"] = store.record_operator_cleanup(
            execution_id=target["execution_id"],
            launch_digest=target["launch_digest"],
            cleaned=cleaned,
        ).value
        outcomes.append(entry)
    return {
        "schema": schema,
        "state_root": str(state_root),
        "dry_run": dry_run,
        "outstanding": len(outcomes),
        "launches": outcomes,
        "authority": "TASK_OWNED_CLEANUP_ONLY_NOT_DEVICE_RELEASE",
    }
