"""Opt-in public TRAIN diagnostics through the existing GPU C03 controller.

Scope construction grants nothing. Only the campaign grant and fixed private
host grant together can admit work. No CPU comparison score is computed here.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

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
    AcceleratorRole,
    accelerator_dependency_specs,
)
from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionStatus
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.worker.accelerator_runtime import AcceleratorHostAdmission
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
from .research_admission import MANIFEST, verify_cleanup_owner
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
RESULT = "carbon.public-gpu-reconstruction.result.v1"


def _storage(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


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
    old = research_contracts()
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
    value = public_catalog()
    value["version"] = "carbon.burgers-gpu-diagnostic-recipes.v1"
    value["constraints"][
        -1
    ] = "existing C03 host controls and both explicit grants dominate parameter bounds"
    value["execution"] = {
        "profile": GPU_PROFILE.profile_id,
        "backend": "cuda",
        "hardware_acceptance": "NOT_EXECUTED",
        "availability": "REQUIRES_CAMPAIGN_AND_HOST_GRANTS_AND_VERIFIED_HOST_CONTROLS",
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
                "Practice tasks construct one GPU TRAIN diagnostic; no score, final comparison or automatic retry. Missing authority/host controls prevent admission."
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
            manifest.get("schema") != MANIFEST
            or manifest.get("owner") != self.data.owner
            or manifest.get("runtime", {}).get("gpu_research") != [self.scope]
            or self.scope != gpu_scope(self.image, self.data.role_root)
        ):
            raise ValueError("exact prospective GPU campaign scope required")
        if cleanup:
            verify_cleanup_owner(self.data.ledger, self.data.owner)
        else:
            self.data.ledger._grant(manifest)
        return manifest

    def _host(self):
        admission = AcceleratorHostAdmission.load()
        root = Path(admission.document.get("controller_root", ""))
        admission.verify(
            principal=self.data.owner,
            state_root=root,
            image=self.image,
            role=AcceleratorRole.MINER_RESEARCH,
            now=float(time.time()),
            dispatch=True,
        )
        if root == self.data.ledger.root.resolve() or not root.is_relative_to(
            self.data.ledger.root.resolve()
        ):
            raise ValueError("GPU controller root must belong to the exact campaign")
        if self.inspection is None or (
            admission.document["resource_policy_digest"]
            != self.inspection.policy_ref.content_digest
            or admission.document["resource_class_digest"]
            != self.inspection.resource_class_ref.content_digest
        ):
            raise ValueError("GPU discovery resource binding differs from host grant")
        return admission, root

    def __call__(self, identity, strategy):
        if self.cleanup_only or ACTIVE_TASK.get() != identity:
            raise ValueError("owned active GPU task required")
        self._authorize()
        admission, controller_root = self._host()
        compiled, profile = self.compile(strategy)
        plan = compiled.construction_plan
        # Reference preparation retains its existing CPU admission and accounting.
        training, _metadata = self.data.prepare("research-train")
        ledger, owner = self.data.ledger, self.data.owner
        request = {
            "scope": self.scope,
            "plan": plan.to_ref().content_digest,
            "training": digest(training),
            "host_grant": admission.digest,
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
            self._host()
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

                self._authorize()
                admission.verify(
                    principal=owner,
                    state_root=controller_root,
                    image=self.image,
                    role=AcceleratorRole.MINER_RESEARCH,
                    now=float(time.time()),
                )
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
