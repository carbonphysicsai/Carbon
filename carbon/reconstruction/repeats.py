"""Frozen, local C-02 development repeats; never an official evaluation path."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from carbon.construction import ResolvedConstructionPlan
from carbon.execution import ExecutionAttemptRef
from carbon.reconstruction.model import (
    PublicTrainingArchive,
    ReconstructionFailure,
    ReconstructionReceipt,
    ReconstructionStatus,
)
from carbon.reconstruction.service import predict, reconstruct
from carbon.resource_policy import BoundReconstructionReplicate
from carbon.seeding import DerivedSeed

_PLAN_SCHEMA = "carbon.c02.development-repeat-plan.v1"
_OUTCOME_SCHEMA = "carbon.c02.development-replica-outcome.v1"
_REPORT_SCHEMA = "carbon.c02.development-repeat-report.v1"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _tagged(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object, code: str) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ReconstructionFailure(code)
    return value


def _execution_id(value: ExecutionAttemptRef) -> str:
    if type(value) is not ExecutionAttemptRef:
        raise ReconstructionFailure("reconstruction.repeat.execution_ref_invalid")
    return f"{value.submission_id.value}:{value.attempt_number}"


def _request_arrays(request: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    if type(request) is not dict or set(request) != {
        "initial",
        "viscosity",
        "requested_times",
        "positions",
    }:
        raise ReconstructionFailure("reconstruction.repeat.request_invalid")
    return (
        ("initial", request["initial"]),
        ("viscosity", request["viscosity"]),
        ("requested_times", request["requested_times"]),
        ("positions", request["positions"]),
    )


def development_request_digest(request: Mapping[str, object]) -> str:
    """Digest one common, target-free prediction request."""
    try:
        import numpy as np

        digest = hashlib.sha256()
        for name, value in _request_arrays(request):
            array = np.ascontiguousarray(value)
            metadata = _canonical(
                {"name": name, "dtype": array.dtype.str, "shape": list(array.shape)}
            )
            digest.update(len(metadata).to_bytes(8, "big"))
            digest.update(metadata)
            digest.update(len(array.tobytes()).to_bytes(8, "big"))
            digest.update(array.tobytes())
        return "sha256:" + digest.hexdigest()
    except ReconstructionFailure:
        raise
    except Exception:  # noqa: BLE001 - arbitrary array providers fail closed.
        raise ReconstructionFailure("reconstruction.repeat.request_invalid") from None


def development_replicate_digest(
    *,
    binding: BoundReconstructionReplicate,
    execution_ref: ExecutionAttemptRef,
    randomness_digest: str,
    training_data_digest: str,
    request_digest: str,
) -> str:
    """Compute the C-02 association promised by a B-02C replicate identity."""
    if type(binding) is not BoundReconstructionReplicate:
        raise ReconstructionFailure("reconstruction.repeat.binding_invalid")
    for value in (randomness_digest, training_data_digest, request_digest):
        _digest(value, "reconstruction.repeat.digest_invalid")
    identity = binding.replicate_identity
    body = {
        "schema": "carbon.c02.development-replicate-binding.v1",
        "challenge": {
            "challenge_id": identity.challenge_key.challenge_id,
            "version": identity.challenge_key.version,
        },
        "construction_plan_digest": identity.construction_plan_ref.content_digest,
        "policy_digest": identity.policy_ref.content_digest,
        "resource_class_digest": identity.resource_class_ref.content_digest,
        "replicate_id": identity.replicate_id,
        "execution_id": _execution_id(execution_ref),
        "randomness_digest": randomness_digest,
        "training_data_digest": training_data_digest,
        "request_digest": request_digest,
    }
    return _tagged(_canonical(body))


@dataclass(frozen=True, slots=True)
class DevelopmentReplica:
    binding: BoundReconstructionReplicate
    execution_ref: ExecutionAttemptRef
    randomness_digest: str
    cancel_before_first_update: bool = False

    def __post_init__(self) -> None:
        if type(self.binding) is not BoundReconstructionReplicate:
            raise ReconstructionFailure("reconstruction.repeat.binding_invalid")
        _execution_id(self.execution_ref)
        _digest(self.randomness_digest, "reconstruction.repeat.randomness_invalid")
        if type(self.cancel_before_first_update) is not bool:
            raise ReconstructionFailure("reconstruction.repeat.cancel_invalid")


@dataclass(frozen=True, slots=True)
class DevelopmentRepeatPlan:
    plan_id: str
    plan_digest: str
    construction_plan_digest: str
    training_data_digest: str
    request_digest: str
    replicas: tuple[DevelopmentReplica, ...]
    concurrency: int = 1

    def __post_init__(self) -> None:
        if type(self.plan_id) is not str or not self.plan_id:
            raise ReconstructionFailure("reconstruction.repeat.plan_id_invalid")
        if type(self.replicas) is not tuple or not self.replicas:
            raise ReconstructionFailure("reconstruction.repeat.replicas_invalid")
        if type(self.concurrency) is not int or self.concurrency != 1:
            raise ReconstructionFailure("reconstruction.repeat.concurrency_invalid")
        for value in (
            self.plan_digest,
            self.construction_plan_digest,
            self.training_data_digest,
            self.request_digest,
        ):
            _digest(value, "reconstruction.repeat.plan_digest_invalid")
        ids = [item.binding.replicate_identity.replicate_id for item in self.replicas]
        if len(ids) != len(set(ids)):
            raise ReconstructionFailure("reconstruction.repeat.replicas_invalid")
        body = _plan_body(self, include_digest=False)
        if self.plan_digest != _tagged(_canonical(body)):
            raise ReconstructionFailure("reconstruction.repeat.plan_digest_invalid")
        first = self.replicas[0].binding.replicate_identity
        for item in self.replicas:
            identity = item.binding.replicate_identity
            if (
                identity.challenge_key != first.challenge_key
                or identity.construction_plan_ref != first.construction_plan_ref
                or identity.policy_ref != first.policy_ref
                or identity.resource_class_ref != first.resource_class_ref
                or identity.construction_plan_ref.content_digest
                != self.construction_plan_digest
                or identity.replicate_digest
                != development_replicate_digest(
                    binding=item.binding,
                    execution_ref=item.execution_ref,
                    randomness_digest=item.randomness_digest,
                    training_data_digest=self.training_data_digest,
                    request_digest=self.request_digest,
                )
            ):
                raise ReconstructionFailure("reconstruction.repeat.binding_mismatch")


def _replica_body(value: DevelopmentReplica) -> dict[str, object]:
    identity = value.binding.replicate_identity
    return {
        "replicate_id": identity.replicate_id,
        "replicate_digest": identity.replicate_digest,
        "execution_id": _execution_id(value.execution_ref),
        "randomness_digest": value.randomness_digest,
        "cancel_before_first_update": value.cancel_before_first_update,
    }


def _plan_body(
    value: DevelopmentRepeatPlan, *, include_digest: bool
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": _PLAN_SCHEMA,
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "plan_id": value.plan_id,
        "construction_plan_digest": value.construction_plan_digest,
        "training_data_digest": value.training_data_digest,
        "request_digest": value.request_digest,
        "concurrency": value.concurrency,
        "replicas": [_replica_body(item) for item in value.replicas],
    }
    if include_digest:
        body["plan_digest"] = value.plan_digest
    return body


def freeze_development_repeat_plan(
    *,
    plan_id: str,
    construction_plan_digest: str,
    training_data_digest: str,
    request_digest: str,
    replicas: tuple[DevelopmentReplica, ...],
) -> DevelopmentRepeatPlan:
    provisional = object.__new__(DevelopmentRepeatPlan)
    object.__setattr__(provisional, "plan_id", plan_id)
    object.__setattr__(provisional, "plan_digest", "")
    object.__setattr__(
        provisional, "construction_plan_digest", construction_plan_digest
    )
    object.__setattr__(provisional, "training_data_digest", training_data_digest)
    object.__setattr__(provisional, "request_digest", request_digest)
    object.__setattr__(provisional, "replicas", replicas)
    object.__setattr__(provisional, "concurrency", 1)
    digest = _tagged(_canonical(_plan_body(provisional, include_digest=False)))
    return DevelopmentRepeatPlan(
        plan_id,
        digest,
        construction_plan_digest,
        training_data_digest,
        request_digest,
        replicas,
    )


def _write_new_json(path: Path, value: object) -> None:
    payload = _canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _receipt_body(receipt: ReconstructionReceipt) -> dict[str, object]:
    return {
        "artifact_digest": receipt.artifact_digest,
        "checkpoint_digest": receipt.checkpoint_digest,
        "completed_steps": receipt.completed_steps,
        "compile_seconds": receipt.compile_seconds,
        "environment_eligibility": receipt.environment_eligibility.value,
        "execution_id": receipt.execution_id,
        "profile_digest": receipt.profile_digest,
        "status": receipt.status.value,
        "train_execution_seconds": receipt.train_execution_seconds,
    }


def run_development_repeats(
    frozen: DevelopmentRepeatPlan,
    *,
    construction_plan: ResolvedConstructionPlan,
    training_archive: PublicTrainingArchive,
    derived_seeds: Mapping[str, DerivedSeed],
    request: Mapping[str, object],
    output_directory: Path,
) -> dict[str, object]:
    """Execute each frozen member once and retain every disposition."""
    if type(frozen) is not DevelopmentRepeatPlan:
        raise ReconstructionFailure("reconstruction.repeat.plan_invalid")
    fully_recorded = (output_directory / "plan.json").is_file() and all(
        (
            output_directory
            / "records"
            / f"{item.binding.replicate_identity.replicate_id}.json"
        ).is_file()
        for item in frozen.replicas
    )
    if not fully_recorded:
        try:
            observed_plan_digest = construction_plan.to_ref().content_digest
        except Exception:  # noqa: BLE001 - compiler identity failures are normalized.
            raise ReconstructionFailure(
                "reconstruction.repeat.construction_plan_mismatch"
            ) from None
        if observed_plan_digest != frozen.construction_plan_digest:
            raise ReconstructionFailure(
                "reconstruction.repeat.construction_plan_mismatch"
            )
    if training_archive.content_digest != frozen.training_data_digest:
        raise ReconstructionFailure("reconstruction.repeat.training_data_mismatch")
    if development_request_digest(request) != frozen.request_digest:
        raise ReconstructionFailure("reconstruction.repeat.request_mismatch")
    expected_ids = {
        item.binding.replicate_identity.replicate_id for item in frozen.replicas
    }
    if type(derived_seeds) is not dict or set(derived_seeds) != expected_ids:
        raise ReconstructionFailure("reconstruction.repeat.seeds_mismatch")
    if not output_directory.is_absolute() or output_directory.is_symlink():
        raise ReconstructionFailure("reconstruction.repeat.path_invalid")
    output_directory.mkdir(parents=True, exist_ok=True)
    plan_path = output_directory / "plan.json"
    plan_body = _plan_body(frozen, include_digest=True)
    if plan_path.exists():
        if plan_path.read_bytes() != _canonical(plan_body) + b"\n":
            raise ReconstructionFailure(
                "reconstruction.repeat.plan_reconciliation_required"
            )
    else:
        _write_new_json(plan_path, plan_body)

    outcomes: list[dict[str, object]] = []
    for item in frozen.replicas:
        replica_id = item.binding.replicate_identity.replicate_id
        seed = derived_seeds[replica_id]
        if (
            type(seed) is not DerivedSeed
            or _tagged(seed.as_backend_bytes()) != item.randomness_digest
        ):
            raise ReconstructionFailure("reconstruction.repeat.seed_binding_mismatch")
        record_path = output_directory / "records" / f"{replica_id}.json"
        artifact_path = output_directory / "artifacts" / replica_id
        prediction_path = output_directory / "predictions" / f"{replica_id}.npz"
        if record_path.exists():
            outcome = json.loads(record_path.read_text(encoding="utf-8"))
            if (
                type(outcome) is not dict
                or outcome.get("schema") != _OUTCOME_SCHEMA
                or outcome.get("plan_digest") != frozen.plan_digest
                or outcome.get("replicate_id") != replica_id
                or outcome.get("replicate_digest")
                != item.binding.replicate_identity.replicate_digest
            ):
                raise ReconstructionFailure(
                    "reconstruction.repeat.outcome_reconciliation_required"
                )
            if outcome.get("disposition") == "COMPLETE" and (
                not artifact_path.is_dir() or not prediction_path.is_file()
            ):
                raise ReconstructionFailure(
                    "reconstruction.repeat.outcome_reconciliation_required"
                )
            outcomes.append(outcome)
            continue
        if artifact_path.exists() or prediction_path.exists():
            outcome = {
                "schema": _OUTCOME_SCHEMA,
                "plan_digest": frozen.plan_digest,
                "replicate_id": replica_id,
                "replicate_digest": item.binding.replicate_identity.replicate_digest,
                "disposition": ReconstructionStatus.RECONCILIATION_REQUIRED.value,
                "reason": "ambiguous_artifact_without_immutable_outcome",
            }
            _write_new_json(record_path, outcome)
            outcomes.append(outcome)
            continue
        wall_started = time.perf_counter()
        cpu_started = time.process_time()
        try:
            receipt = reconstruct(
                execution_ref=item.execution_ref,
                plan=construction_plan,
                training_archive=training_archive,
                derived_seed=seed,
                artifact_path=artifact_path,
                cancel=(lambda: True) if item.cancel_before_first_update else None,
            )
            outcome = {
                "schema": _OUTCOME_SCHEMA,
                "plan_digest": frozen.plan_digest,
                "replicate_id": replica_id,
                "replicate_digest": item.binding.replicate_identity.replicate_digest,
                "disposition": receipt.status.value,
                "receipt": _receipt_body(receipt),
            }
            if receipt.status is ReconstructionStatus.COMPLETE:
                values, prediction_receipt = predict(receipt, **request)
                if prediction_receipt.request_digest != frozen.request_digest:
                    raise ReconstructionFailure(
                        "reconstruction.repeat.prediction_request_mismatch"
                    )
                prediction_path.parent.mkdir(parents=True, exist_ok=True)
                with prediction_path.open("xb") as stream:
                    import numpy as np

                    np.savez_compressed(stream, prediction=values)
                    stream.flush()
                    os.fsync(stream.fileno())
                outcome["prediction"] = {
                    "path": f"predictions/{replica_id}.npz",
                    "request_digest": prediction_receipt.request_digest,
                    "output_digest": prediction_receipt.output_digest,
                    "execution_seconds": prediction_receipt.execution_seconds,
                }
        except ReconstructionFailure as exc:
            outcome = {
                "schema": _OUTCOME_SCHEMA,
                "plan_digest": frozen.plan_digest,
                "replicate_id": replica_id,
                "replicate_digest": item.binding.replicate_identity.replicate_digest,
                "disposition": "FAILED",
                "reason": exc.code,
            }
        outcome["wall_seconds"] = float(time.perf_counter() - wall_started)
        outcome["process_cpu_seconds"] = float(time.process_time() - cpu_started)
        _write_new_json(record_path, outcome)
        outcomes.append(outcome)

    completed = [item for item in outcomes if item["disposition"] == "COMPLETE"]
    failed = [item for item in outcomes if item["disposition"] != "COMPLETE"]
    dispersion: dict[str, object] = {
        "status": "UNRESOLVED_INSUFFICIENT_REPLICAS",
        "completed_subset_size": len(completed),
        "conditional_on_successful_subset": bool(failed),
        "mean_pointwise_sample_standard_deviation": None,
    }
    if len(completed) >= 2:
        import numpy as np

        arrays = [
            np.load(output_directory / item["prediction"]["path"])["prediction"]
            for item in completed
        ]
        dispersion.update(
            {
                "status": "DESCRIPTIVE_ONLY",
                "mean_pointwise_sample_standard_deviation": float(
                    np.mean(np.std(np.stack(arrays), axis=0, ddof=1))
                ),
            }
        )
    report = {
        "schema": _REPORT_SCHEMA,
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "plan_digest": frozen.plan_digest,
        "required": len(outcomes),
        "completed": len(completed),
        "failed_or_incomplete": len(failed),
        "pending": 0,
        "concurrency": 1,
        "total_wall_seconds": float(
            sum(item.get("wall_seconds", 0.0) for item in outcomes)
        ),
        "total_process_cpu_seconds": float(
            sum(item.get("process_cpu_seconds", 0.0) for item in outcomes)
        ),
        "dispersion": dispersion,
        "outcomes": outcomes,
        "authority": "cannot authorize score, accepted result, evaluation pack, or reward",
    }
    return report


__all__ = [
    "DevelopmentRepeatPlan",
    "DevelopmentReplica",
    "development_replicate_digest",
    "development_request_digest",
    "freeze_development_repeat_plan",
    "run_development_repeats",
]
