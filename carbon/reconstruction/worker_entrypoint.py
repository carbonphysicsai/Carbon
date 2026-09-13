"""Fixed entry point inside the C-03 CPU DEVELOPMENT worker image.

Only root-owned code invokes the canonical C-02 adapter.  The request contains
identities and data, never an import, executable, command, URI, or path.
"""

from __future__ import annotations

import hashlib
import json
import os
import resource
import time
from pathlib import Path

from carbon.construction import decode_resolved_construction_plan
from carbon.construction.refs import ResolvedConstructionPlanRef
from carbon.execution import ExecutionAttemptRef
from carbon.fees import SubmissionId
from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionFailure
from carbon.reconstruction.service import predict, reconstruct
from carbon.registry import ChallengeKey
from carbon.seeding import DerivedSeed

_REQUEST = Path("/input/request.json")
_PLAN = Path("/input/plan.bin")
_TRAIN = Path("/input/training.npz")
_PREDICTION_REQUEST = Path("/input/prediction-request.npz")
_OUTPUT = Path("/output")
_RESULT = _OUTPUT / "result.json"
_REQUEST_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "worker_profile_id",
        "worker_profile_digest",
        "image_id",
        "source_revision",
        "submission_id",
        "attempt_number",
        "challenge_id",
        "challenge_version",
        "plan_digest",
        "archive_digest",
        "archive_provenance",
        "randomness_hex",
        "randomness_digest",
        "prediction_request_digest",
        "replicate_id",
        "replicate_digest",
        "resource_policy_digest",
        "resource_class_digest",
    }
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _read_request() -> dict[str, object]:
    if (
        _REQUEST.is_symlink()
        or not _REQUEST.is_file()
        or _REQUEST.stat().st_size > 65536
    ):
        raise ReconstructionFailure("reconstruction.worker.request_invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        value = json.loads(
            _REQUEST.read_bytes(),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise ReconstructionFailure("reconstruction.worker.request_invalid") from None
    if type(value) is not dict or set(value) != _REQUEST_FIELDS:
        raise ReconstructionFailure("reconstruction.worker.request_invalid")
    if (
        value["schema"] != "carbon.c03.worker-request.v1"
        or value["scope"] != "UNQUALIFIED_PUBLIC_DEVELOPMENT"
        or value["worker_profile_id"] != "carbon_c03_cpu_development_v1"
        or type(value["attempt_number"]) is not int
        or value["attempt_number"] < 1
    ):
        raise ReconstructionFailure("reconstruction.worker.request_invalid")
    for field in (
        "worker_profile_digest",
        "image_id",
        "source_revision",
        "submission_id",
        "challenge_id",
        "challenge_version",
        "plan_digest",
        "archive_digest",
        "archive_provenance",
        "randomness_hex",
        "randomness_digest",
        "prediction_request_digest",
        "replicate_id",
        "replicate_digest",
        "resource_policy_digest",
        "resource_class_digest",
    ):
        if type(value[field]) is not str or not value[field]:
            raise ReconstructionFailure("reconstruction.worker.request_invalid")
    if (
        os.environ.get("CARBON_C03_IMAGE_ID") != value["image_id"]
        or os.environ.get("CARBON_C03_SOURCE_REVISION") != value["source_revision"]
    ):
        raise ReconstructionFailure("reconstruction.worker.image_binding_mismatch")
    try:
        key = bytes.fromhex(value["randomness_hex"])
    except ValueError:
        raise ReconstructionFailure("reconstruction.worker.request_invalid") from None
    if len(key) != 32 or _tagged(key) != value["randomness_digest"]:
        raise ReconstructionFailure("reconstruction.worker.randomness_mismatch")
    return value


def _load_prediction_request(expected_digest: str) -> dict[str, object]:
    if _PREDICTION_REQUEST.is_symlink() or not _PREDICTION_REQUEST.is_file():
        raise ReconstructionFailure("reconstruction.worker.request_invalid")
    try:
        import numpy as np

        with np.load(_PREDICTION_REQUEST, allow_pickle=False) as stored:
            if set(stored.files) != {
                "initial",
                "viscosity",
                "requested_times",
                "positions",
            }:
                raise ValueError
            request = {name: stored[name].copy() for name in stored.files}
        from carbon.reconstruction.repeats import development_request_digest

        if development_request_digest(request) != expected_digest:
            raise ValueError
        return request
    except ReconstructionFailure:
        raise
    except Exception:  # noqa: BLE001 - archive parser detail stays private.
        raise ReconstructionFailure("reconstruction.worker.request_invalid") from None


def _receipt_dict(value) -> dict[str, object]:
    return {
        "artifact_digest": value.artifact_digest,
        "checkpoint_digest": value.checkpoint_digest,
        "completed_steps": value.completed_steps,
        "compile_seconds": value.compile_seconds,
        "environment_digest": value.environment_digest,
        "environment_eligibility": value.environment_eligibility.value,
        "execution_id": value.execution_id,
        "inference_weights": value.inference_weights,
        "input_interface_digest": value.input_interface_digest,
        "normalization_scale": value.normalization_scale,
        "observed_environment_digest": value.observed_environment_digest,
        "output_interface_digest": value.output_interface_digest,
        "physical_scaling_digest": value.physical_scaling_digest,
        "physical_unit_system": value.physical_unit_system,
        "plan_digest": value.plan_digest,
        "profile_digest": value.profile_digest,
        "randomness_digest": value.randomness_digest,
        "source_digest": value.source_digest,
        "status": value.status.value,
        "train_execution_seconds": value.train_execution_seconds,
        "training_data_digest": value.training_data_digest,
    }


def _prediction_dict(value) -> dict[str, object]:
    return {
        "artifact_digest": value.artifact_digest,
        "request_digest": value.request_digest,
        "output_digest": value.output_digest,
        "cases": value.cases,
        "times": value.times,
        "points": value.points,
        "execution_seconds": value.execution_seconds,
    }


def _write_result(value: dict[str, object]) -> None:
    payload = _canonical(value) + b"\n"
    temporary = _OUTPUT / ".result.json.tmp"
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(temporary, _RESULT)


def main() -> int:
    started = time.perf_counter()
    cpu_started = time.process_time()
    request: dict[str, object] | None = None
    validation_seconds = 0.0
    try:
        validation_started = time.perf_counter()
        request = _read_request()
        if (
            _PLAN.is_symlink()
            or not _PLAN.is_file()
            or _PLAN.stat().st_size > (1 << 22)
        ):
            raise ReconstructionFailure("reconstruction.worker.plan_invalid")
        key = ChallengeKey(request["challenge_id"], request["challenge_version"])
        expected_ref = ResolvedConstructionPlanRef(
            key, content_digest=request["plan_digest"]
        )
        plan = decode_resolved_construction_plan(
            _PLAN.read_bytes(), expected_ref=expected_ref
        )
        execution = ExecutionAttemptRef(
            SubmissionId(request["submission_id"]), request["attempt_number"]
        )
        archive = PublicTrainingArchive.from_file(
            _TRAIN, provenance=request["archive_provenance"]
        )
        if archive.content_digest != request["archive_digest"]:
            raise ReconstructionFailure("reconstruction.worker.archive_mismatch")
        seed = DerivedSeed(bytes.fromhex(request["randomness_hex"]))
        prediction_request = _load_prediction_request(
            request["prediction_request_digest"]
        )
        validation_seconds = float(time.perf_counter() - validation_started)

        reconstruction_started = time.perf_counter()
        receipt = reconstruct(
            execution_ref=execution,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=_OUTPUT / "artifact",
        )
        reconstruction_seconds = float(time.perf_counter() - reconstruction_started)
        prediction_started = time.perf_counter()
        prediction, prediction_receipt = predict(receipt, **prediction_request)
        prediction_seconds = float(time.perf_counter() - prediction_started)
        prediction_path = _OUTPUT / "prediction.npz"
        import numpy as np

        with prediction_path.open("xb") as stream:
            np.savez_compressed(stream, prediction=prediction)
            stream.flush()
            os.fsync(stream.fileno())
        usage = resource.getrusage(resource.RUSAGE_SELF)
        _write_result(
            {
                "schema": "carbon.c03.worker-result.v1",
                "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
                "disposition": "COMPLETE",
                "worker_profile_digest": request["worker_profile_digest"],
                "image_id": request["image_id"],
                "source_revision": request["source_revision"],
                "submission_id": request["submission_id"],
                "attempt_number": request["attempt_number"],
                "plan_digest": request["plan_digest"],
                "archive_digest": request["archive_digest"],
                "randomness_digest": request["randomness_digest"],
                "prediction_request_digest": request["prediction_request_digest"],
                "replicate_id": request["replicate_id"],
                "replicate_digest": request["replicate_digest"],
                "resource_policy_digest": request["resource_policy_digest"],
                "resource_class_digest": request["resource_class_digest"],
                "receipt": _receipt_dict(receipt),
                "prediction": _prediction_dict(prediction_receipt),
                "observations": {
                    "request_validation_seconds": validation_seconds,
                    "reconstruction_total_seconds": reconstruction_seconds,
                    "jax_compile_seconds": receipt.compile_seconds,
                    "training_updates_seconds": receipt.train_execution_seconds,
                    "checkpoint_load_seconds": None,
                    "checkpoint_save_seconds": None,
                    "checkpoint_timing_missing_reason": "C02_SOURCE_HAS_NO_NONINTERFERING_STAGE_SEAM",
                    "prediction_seconds": prediction_seconds,
                    "worker_wall_seconds": float(time.perf_counter() - started),
                    "worker_process_cpu_seconds": float(
                        time.process_time() - cpu_started
                    ),
                    "worker_reported_max_rss_bytes": int(usage.ru_maxrss) * 1024,
                    "evidence_class": "WORKER_SELF_REPORTED_DIAGNOSTIC",
                },
            }
        )
        return 0
    except (KeyboardInterrupt, SystemExit):
        return 130
    except Exception as exc:  # noqa: BLE001 - no private detail leaves the worker.
        code = (
            exc.code
            if isinstance(exc, ReconstructionFailure)
            else "reconstruction.worker.failed"
        )
        if request is not None:
            try:
                _write_result(
                    {
                        "schema": "carbon.c03.worker-result.v1",
                        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
                        "disposition": "FAILED",
                        "failure_code": code,
                        "worker_profile_digest": request["worker_profile_digest"],
                        "image_id": request["image_id"],
                        "source_revision": request["source_revision"],
                        "submission_id": request["submission_id"],
                        "attempt_number": request["attempt_number"],
                        "plan_digest": request["plan_digest"],
                        "archive_digest": request["archive_digest"],
                        "randomness_digest": request["randomness_digest"],
                        "prediction_request_digest": request[
                            "prediction_request_digest"
                        ],
                        "replicate_id": request["replicate_id"],
                        "replicate_digest": request["replicate_digest"],
                        "resource_policy_digest": request["resource_policy_digest"],
                        "resource_class_digest": request["resource_class_digest"],
                    }
                )
            except (
                Exception
            ):  # noqa: BLE001, S110 - best-effort private failure record.
                pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
