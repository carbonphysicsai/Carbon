"""Opt-in public TRAIN diagnostics through the existing GPU C03 controller.

Scope construction grants nothing. What admits work is the campaign grant plus
the miner lane the role already selects - not a second, owner-signed host grant.
That grant was written to validator requirements and applied to both roles; a
miner receives a public plan and public TRAIN material, so there is nothing here
for exclusivity to protect, and no human can sign a record per run for a network
of miners. The device this launch binds to still comes from the operator's
installed host record, which fails closed when it is missing or withdrawn.

No CPU comparison score is computed here, and nothing on this path becomes
official evidence: the result carries the miner-lane label saying so.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import asdict, replace

from carbon import construction as c
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionScope,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.reconstruction.accelerators import (
    GPU_PROFILE,
    AcceleratorLane,
    AcceleratorRole,
    accelerator_dependency_specs,
    lane_for_role,
    miner_lane_assurance,
)
from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionStatus
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.resource_policy import (
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
)
from carbon.seeding import DerivedSeed

from .contracts import SessionContracts
from .data import write_once
from .profile import canonical, digest
from .research_carrier import (
    ACTIVE_TASK,
    PRECHARGED_TRIAL,
    _cancel_path,
    _numerical_lease,
)
from .research_catalog import compile_recipe, public_catalog, research_contracts
from .research_data import PublicReferenceData
from .research_profile import _context, public_cases

SCHEMA = "carbon.public-gpu-reconstruction.scope.v1"
#: The families the GPU diagnostic lane rebuilds.
GPU_BACKBONES = ("fno", "deeponet")
# The result body gained the miner-lane assurance label, so it is served under a
# new version rather than under the old one. A v1 result recorded no lane and is
# not retrospectively read as though it had; existing records stay readable and
# keep their exact meaning.
RESULT = "carbon.public-gpu-reconstruction.result.v2"
LEGACY_RESULTS = ("carbon.public-gpu-reconstruction.result.v1",)

# What one request is. The strict grant's digest used to be part of this identity;
# on the miner lane there is no grant, and the per-run device binding that
# actually constrains the launch takes its place. That is a different identity,
# so it is versioned rather than quietly reshaped.
#
# A record written under v1 cannot be re-derived, because the grant digest it was
# built from is gone. It is deliberately *not* replayed through this callback:
# the ledger's existing replay check sees a different request for the same task
# and refuses, which is the same answer it gives for a changed recipe and is the
# right one for both - neither is the work this request describes. Those records
# stay readable and recoverable where they always were, through the campaign's
# status, report and export projections, which key on the operation rather than
# on its request identity. Reading one never re-runs it, re-charges it, or moves
# it onto this lane.
REQUEST = "carbon.public-gpu-reconstruction.request.v2"

#: Campaign-owned controller storage. Resolved from the ledger root, never from a
#: browser-supplied path and never from the withdrawn host grant.
CONTROLLER_DIRECTORY = "gpu-controller"


def _storage(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _controller_root(ledger):
    """Resolve this campaign's own controller storage.

    Previously this came out of the strict host grant's `controller_root` field,
    which meant an operator record chose where a campaign's controller state
    lived and the campaign then had to check it belonged to itself. The miner
    lane has no such record, so the location is derived from the campaign root
    that already owns every other artifact this run writes.

    The containment check is kept rather than dropped: it is cheap, and it still
    catches a symlinked or relocated campaign root before anything is staged.
    """
    root = ledger.root.resolve()
    controller = root / CONTROLLER_DIRECTORY
    if controller.is_symlink():
        raise ValueError("campaign GPU controller storage must not be a symlink")
    controller.mkdir(mode=0o700, exist_ok=True)
    controller = controller.resolve()
    if controller == root or not controller.is_relative_to(root):
        raise ValueError("GPU controller root must belong to the exact campaign")
    return controller


def _check_storage_layout(controller_root, directory):
    controller_root, directory = controller_root.resolve(), directory.resolve()
    if controller_root.is_relative_to(directory) or directory.is_relative_to(
        controller_root
    ):
        raise ValueError("GPU controller and operation storage must be disjoint")


def _observations(run):
    def numeric(value):
        return (
            value
            if type(value) in (int, float) and math.isfinite(value) and value >= 0
            else None
        )

    observations = run.resource_observation
    return {
        "host_memory_current_bytes": numeric(
            (observations.get("memory") or {}).get("current_bytes")
        ),
        "host_memory_peak_bytes": numeric(
            (observations.get("memory") or {}).get("peak_bytes")
        ),
        "host_cpu_usage_microseconds": numeric(
            (observations.get("cpu") or {}).get("usage_usec")
        ),
        "device_memory_peak_bytes": None,
        "device_memory_peak_status": "NOT_MEASURED_BY_THIS_PROJECTION",
        "timings": {
            key: numeric(run.timings.get(key))
            for key in (
                "staging",
                "create",
                "numerical",
                "export",
                "validation",
                "cleanup",
                "total",
            )
        },
    }


def gpu_contracts():
    """Change authoring pins before compilation, never a compiled CPU plan."""
    # The GPU lane's own admitted families; widening the CPU research catalog
    # does not widen it.
    old = research_contracts(GPU_BACKBONES)
    env = c.EnvironmentPin(GPU_PROFILE.profile_id, "1.0", GPU_PROFILE.digest)
    deps = old.assembly.dependency_pins + tuple(
        c.DependencyPin(*s) for s in accelerator_dependency_specs(GPU_PROFILE)
    )
    surface = replace(
        old.assembly.backbone_surface,
        options=tuple(
            replace(option, environment_pin=env, dependency_pins=deps)
            for option in old.assembly.backbone_surface.options
        ),
    )
    assembly = replace(
        old.assembly,
        object_id="burgers_gpu_diagnostic_assembly",
        environment_pins=(env,),
        dependency_pins=deps,
        backbone_surface=surface,
    )
    catalog = replace(
        old.catalog,
        object_id="burgers_gpu_diagnostic_parameters",
        candidate_assembly_ref=assembly.to_ref(),
    )
    return SessionContracts(assembly, catalog, old.origin, old.artifacts)


def gpu_catalog():
    value = public_catalog(GPU_BACKBONES)
    value["version"] = "carbon.burgers-gpu-diagnostic-recipes.v1"
    value["constraints"][-1] = (
        "existing C03 host controls, the campaign grant and the installed host device record dominate parameter bounds"
    )
    value["execution"] = {
        "profile": GPU_PROFILE.profile_id,
        "backend": "cuda",
        "lane": AcceleratorLane.MINER_CONTAINED.value,
        "hardware_acceptance": "NOT_EXECUTED",
        "availability": "REQUIRES_CAMPAIGN_GRANT_AND_INSTALLED_HOST_DEVICE_RECORD",
        # Named so a miner reading the catalogue can tell what would actually
        # stop them. None of these is a strict host grant, an exclusivity claim
        # or a whole-device enumeration source.
        "requires": [
            "APPROVED_CAMPAIGN_GRANT_WITH_THIS_GPU_SCOPE",
            "INSTALLED_HOST_DEVICE_RECORD_COMPATIBLE_WITH_THIS_PROFILE",
            "PINNED_GPU_WORKER_IMAGE_AND_CONTAINER_DEVICE_RUNTIME",
        ],
        "assurance": miner_lane_assurance(),
        "score": None,
        "official_eligible": False,
    }
    return value


def gpu_scope(image, role_root):
    if (
        type(image) is not WorkerImageIdentity
        or image.lock_digest != GPU_PROFILE.environment_lock_digest
    ):
        raise ValueError("exact pinned GPU image required")
    contracts = gpu_contracts()
    return {
        "schema": SCHEMA,
        "profile_digest": GPU_PROFILE.digest,
        "image": image.image_id,
        "image_manifest_digest": digest(canonical(asdict(image))),
        "assembly": contracts.assembly.to_ref().content_digest,
        "catalogue": digest(canonical(gpu_catalog())),
        "public_train_digest": digest(
            canonical(public_cases(role_root, "research-train"))
        ),
        "role": AcceleratorRole.MINER_RESEARCH.value,
        "productive_seconds": 600,
        "validation_cleanup_seconds": 120,
        "score": None,
        "official_eligible": False,
    }


#: The operator-installed record naming which GPU worker image this campaign runs.
GPU_IMAGE_RECORD = "gpu-worker-image.json"


def registered_gpu_image(root, runtime, role_root):
    """Read the fixed operator GPU image record; the caller still verifies its grant.

    The same shape as the Julia analysis resolver beside it: an operator writes
    the record, the scope is *recomputed* from the image and the campaign's own
    public TRAIN material rather than trusted as declared, and the record's
    presence grants nothing by itself.

    Recomputing the scope binds the exact public cases, so this can only be
    called once role material exists. That is deliberate - it is the check that
    a declared GPU runtime actually describes this campaign's material, and it
    belongs after generation rather than before it.
    """
    if "gpu_research" not in runtime:
        return None
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    from .research_campaign import private_file

    path = private_file(root / GPU_IMAGE_RECORD)
    if path.resolve() != path or path.stat().st_size > 65536:
        raise ValueError("fixed bounded GPU image record required")
    image = load_image_identity(path)
    if runtime["gpu_research"] != [gpu_scope(image, role_root)]:
        raise ValueError("exact prospective GPU runtime scope required")
    return image


def declared_gpu_runtime(runtime):
    """The GPU scope a grant declares, checked for shape before it is relied on.

    A campaign has to compare the runtime it can compose against the runtime it
    was granted *before* it may charge for generating role material - but the
    scope binds that very material, so its content cannot be recomputed yet.

    What is checked here is therefore shape only, and it is separated under its
    own name so that it cannot be mistaken for the binding check. The binding
    check is `registered_gpu_image`, which recomputes the scope once the roles
    exist, and `PublicGPUPractice._authorize`, which refuses to construct a
    callback whose recomputed scope differs from the frozen manifest. Neither is
    optional, and a grant that reaches this function has not yet been believed.
    """
    scopes = runtime.get("gpu_research")
    if (
        type(scopes) is not list
        or len(scopes) != 1
        or type(scopes[0]) is not dict
        or scopes[0].get("schema") != SCHEMA
        or scopes[0].get("role") != AcceleratorRole.MINER_RESEARCH.value
        or scopes[0].get("official_eligible") is not False
        or scopes[0].get("score") is not None
    ):
        raise ValueError("exact prospective GPU runtime scope required")
    return [dict(scopes[0])]


class PublicGPUPractice:
    """Trusted callback; no request can select the host, role, grant or method."""

    def __init__(self, *, data, image, cleanup_only=False):
        if type(data) is not PublicReferenceData or data.phase != "research":
            raise ValueError("exact public research data required")
        self.data, self.image = data, image
        self.cleanup_only = cleanup_only
        self.scope = gpu_scope(image, data.role_root)
        self.contracts = gpu_contracts()
        self.inspection = None
        self._authorize(cleanup=cleanup_only)

    def compile(self, strategy):
        return compile_recipe(strategy, contracts=self.contracts)

    def projection(self, name, source, workspace):
        if name not in {"objective", "capabilities"}:
            return source
        value = source["document"]
        if name == "capabilities":
            value = dict(value)
            if "installed_pinned_dependencies" in value:
                value["cpu_reference_dependencies"] = value.pop(
                    "installed_pinned_dependencies"
                )
            value["recipes"] = gpu_catalog()
            value["gpu_diagnostic"] = gpu_catalog()["execution"]
            value["public_scaffold_catalogue_digest"] = self.scaffold_digest
            value["unsupported"] = [
                s for s in value.get("unsupported", []) if s != "GPU"
            ]
            value["guidance"] = (
                "Practice tasks construct one GPU TRAIN diagnostic; no score, final comparison or automatic retry. This is the miner lane: no host grant, exclusive device or process enumeration is required, but a compatible installed host device record and the pinned GPU image are."
            )
        elif name == "objective":
            value = {
                "schema": "carbon.public-gpu-reconstruction.objective.v1",
                "physics": value["physics"],
                "input": value["input"],
                "output": value["output"],
                "purpose": "Inspect registered-recipe construction and resource observations on public TRAIN data",
                "score": None,
                "official_eligible": False,
                "hardware_acceptance": "NOT_EXECUTED",
            }
        payload = canonical(value)
        filename = "gpu-diagnostic-" + name + ".json"
        workspace.put(filename, payload)
        return {"document": value, "file": filename, "digest": digest(payload)}

    def _authorize(self, *, cleanup=False):
        with self.data.ledger.db() as db:
            row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
        manifest = json.loads(row[0]) if row else {}
        if (
            not self.data.ledger.controlled(manifest)
            or manifest.get("owner") != self.data.owner
            or manifest.get("runtime", {}).get("gpu_research") != [self.scope]
            or self.scope != gpu_scope(self.image, self.data.role_root)
        ):
            raise ValueError("exact prospective GPU campaign scope required")
        if cleanup:
            self.data.ledger.retained_owner(self.data.owner)
        else:
            self.data.ledger.authority(manifest)
        return manifest

    def _device(self):
        """Bind this launch to the installed host device record.

        Read here, before the reservation, rather than only inside the
        controller: the controller reads it too, but by then the ledger has
        already charged the miner for a launch that cannot dispatch. A withdrawn
        or incompatible record should cost nothing.

        Read on each use rather than cached, for the same reason the worker
        rereads it - a record can be replaced or withdrawn between the check and
        the dispatch, and a cached copy would let a withdrawn one keep supplying
        the device identity this request is bound to.

        This is not the old strict grant and does not stand in for one. It
        establishes which device this host has, which is a compatibility fact.
        It asserts nothing about what else is using that device, and the lane
        makes no claim that would need it to.
        """
        from carbon.reconstruction.worker.accelerator_runtime import host_device

        if self.inspection is None:
            raise ValueError(
                "resolved research resource inspection required before GPU dispatch"
            )
        return host_device()

    def __call__(self, identity, strategy):
        if self.cleanup_only or ACTIVE_TASK.get() != identity:
            raise ValueError("owned active GPU task required")
        self._authorize()
        ledger, owner = self.data.ledger, self.data.owner
        controller_root = _controller_root(ledger)
        device = self._device()
        compiled, profile = self.compile(strategy)
        plan = compiled.construction_plan
        # Reference preparation retains its existing CPU admission and accounting.
        training, _metadata = self.data.prepare("research-train")
        request = {
            "version": REQUEST,
            "scope": self.scope,
            "lane": lane_for_role(AcceleratorRole.MINER_RESEARCH).value,
            "plan": plan.to_ref().content_digest,
            "training": digest(training),
            # What the strict grant digest used to occupy. This binds the request
            # to the exact installed device record, so a replaced or withdrawn
            # record produces a different request rather than silently reusing
            # this one.
            "device": device.digest,
            "task": identity,
        }
        request_digest = digest(canonical(request))
        directory = ledger.root / ("gpu-" + request_digest[7:])
        _check_storage_layout(controller_root, directory)
        resources = {"numerical_milliseconds": 720000, "retained_bytes": 384 * 1024**2}
        if PRECHARGED_TRIAL.get() is None:
            resources["research_trials"] = 1
        with _numerical_lease(ledger):
            self._authorize()
            # Reread rather than reuse: a record withdrawn or replaced between
            # the request being built and the lease being taken must stop this
            # launch instead of dispatching under a stale device identity.
            if self._device().digest != device.digest:
                raise ValueError("installed host device record changed before dispatch")
            reservation = ledger.reserve(
                identity,
                owner=owner,
                phase="research",
                request=request,
                resources=resources,
            )
            if not reservation["dispatch"]:
                if reservation["state"] != "SUCCEEDED":
                    raise ValueError(
                        "GPU attempt uncertain; reconcile without dispatch"
                    )
                return reservation["result"]
            ledger.check_storage(resources["retained_bytes"])
            started = time.monotonic()
            directory.mkdir(mode=0o700, exist_ok=True)
            write_once(directory / "train.npz", training)
            write_once(directory / "randomness.bin", os.urandom(32))
            seed = DerivedSeed((directory / "randomness.bin").read_bytes())
            archive = PublicTrainingArchive.from_file(
                directory / "train.npz", provenance="public_gpu_train_diagnostic"
            )
            execution = ExecutionAttemptRef(SubmissionId(str(uuid.uuid4())), 1)
            write_once(
                directory / "execution.json",
                canonical(
                    {
                        "submission_id": execution.submission_id.value,
                        "attempt": 1,
                        "request_digest": request_digest,
                    }
                ),
            )
            placeholder = BoundReconstructionReplicate(
                ReconstructionReplicateIdentity(
                    plan.challenge_key,
                    plan.to_ref(),
                    self.inspection.policy_ref,
                    self.inspection.resource_class_ref,
                    "gpu-research-1",
                    request_digest,
                )
            )
            randomness = digest(seed.as_backend_bytes())
            replicate_digest = development_replicate_digest(
                binding=placeholder,
                execution_ref=execution,
                randomness_digest=randomness,
                training_data_digest=archive.content_digest,
                request_digest=request_digest,
            )
            replica = DevelopmentReplica(
                BoundReconstructionReplicate(
                    replace(
                        placeholder.replicate_identity,
                        replicate_digest=replicate_digest,
                    )
                ),
                execution,
                randomness,
            )
            repeat = freeze_development_repeat_plan(
                plan_id="gpu-" + request_digest[7:],
                construction_plan_digest=plan.to_ref().content_digest,
                training_data_digest=archive.content_digest,
                request_digest=request_digest,
                replicas=(replica,),
            )
            binding = DurableExecutionBinding(
                ExecutionAttemptHandle(
                    execution.submission_id,
                    1,
                    AdmissionKind.FIXTURE,
                    _context(self.data.role_root, "research-train").pin,
                    ExecutionEnvironmentPin(
                        profile.profile_id, profile.environment_digest
                    ),
                ),
                RequesterIdentity(owner),
                plan.strategy_hash,
                ExecutionScope.FIXTURE_DEVELOPMENT,
                plan.to_ref().content_digest,
                profile.profile_digest,
                self.inspection.policy_ref.content_digest,
                digest(canonical(self.scope)),
            )
            queue = DurableExecutionQueue(
                controller_root / "gpu-research-queue.sqlite3"
            )
            queue.admit(binding)
            claimed = queue.claim(
                execution, "gpu-public-research", claim_id=request_digest[7:]
            )
            controller = IsolatedReconstructionController(
                state_root=controller_root, execution_queue=queue, image=self.image
            )
            host_storage_before = _storage(controller_root)

            def cancelled():
                from .research_control import CampaignControl

                # Campaign authority and the operator's own stop intent. The
                # strict grant recheck that used to sit here belonged to a lane
                # this run is not on; what still governs it is the campaign
                # manifest, its control generation and this task's cancel path.
                self._authorize()
                status = CampaignControl(ledger).status()
                return (
                    status["generation"] != ledger.generation
                    or status["desired"] != "RUN"
                    or _cancel_path(ledger, owner, identity).exists()
                )

            # Any exception preserves the full existing reservation and C03 journal.
            run = controller.execute(
                claimed=claimed,
                repeat_plan=repeat,
                replica=replica,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
                accelerator_role=AcceleratorRole.MINER_RESEARCH,
                cancelled=cancelled,
            )
            self._authorize()
            receipt = run.receipt
            if receipt.status is not ReconstructionStatus.COMPLETE:
                raise ValueError(
                    "C03 complete association required before reconciliation"
                )
            result = {
                "schema": RESULT,
                "backend": "cuda",
                "profile": GPU_PROFILE.profile_id,
                # Stated on the record itself, so a consumer can reject it on
                # its own terms instead of having to know what produced it.
                "lane": lane_for_role(AcceleratorRole.MINER_RESEARCH).value,
                "assurance": miner_lane_assurance(),
                "device_record_digest": device.digest,
                "status": receipt.status.value,
                "completed_steps": receipt.completed_steps,
                "artifact_digest": receipt.artifact_digest,
                "checkpoint_digest": receipt.checkpoint_digest,
                "plan_digest": receipt.plan_digest,
                "training_data_digest": receipt.training_data_digest,
                "compile_seconds": receipt.compile_seconds,
                "training_seconds": receipt.train_execution_seconds,
                "observations": _observations(run),
                "score": None,
                "official_eligible": False,
                "scientifically_qualified": False,
                "accepted_improvement": False,
            }
            result_bytes = canonical(result)
            ledger.check_storage(len(result_bytes))
            write_once(directory / "result.json", result_bytes)
            retained = _storage(directory) + max(
                0, _storage(controller_root) - host_storage_before
            )
            ledger.finish(
                identity,
                owner=owner,
                state="SUCCEEDED",
                actual={
                    **resources,
                    "numerical_milliseconds": math.ceil(
                        (time.monotonic() - started) * 1000
                    ),
                    "retained_bytes": retained,
                },
                result=result,
            )
            return result
