"""Closed staging and bounded validation for C-05 measurement execution."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    VALIDATION_WALL_SECONDS,
    WorkerCode,
    WorkerFailure,
)
from carbon.reference_runtime.model import BurgersReferenceRole

from .model import (
    MEASUREMENT_IDS,
    MEASUREMENT_OUTPUT_SEMANTICS,
    PHYSICS_IDS,
    SCHEMA,
    SCOPE,
    BurgersMeasurementRequest,
    BurgersMeasurementResult,
    EvidenceDecision,
    FrozenFieldArtifact,
    MeasurementDisposition,
    MeasurementObservation,
    PhysicsObservation,
    execute_measurement,
)

_MAX_FIELD_BYTES = 8 * 1024 * 1024
_REQUEST_FILE = "measurement-request.json"
_CANDIDATE_FILE = "candidate.f64le"
_REFERENCE_FILE = "reference.f64le"
_RESULT_FILE = "result.json"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _unique_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _read_json(path: Path, maximum: int = CONTROL_BYTES) -> dict[str, object]:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise WorkerFailure(WorkerCode.INVALID)
        with path.open("rb") as stream:
            payload = stream.read(maximum + 1)
        if len(payload) > maximum:
            raise WorkerFailure(WorkerCode.INVALID)
        value = json.loads(
            payload,
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except WorkerFailure:
        raise
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise WorkerFailure(WorkerCode.INVALID) from None
    if type(value) is not dict:
        raise WorkerFailure(WorkerCode.INVALID)
    return value


def decode_measurement_request(document: object) -> BurgersMeasurementRequest:
    if type(document) is not dict or set(document) != {
        "schema",
        "scope",
        "challenge",
        "case_digest",
        "candidate",
        "reference",
        "measurement",
        "query",
        "eligibility",
    }:
        raise ValueError("invalid measurement request document")
    challenge = document["challenge"]
    candidate = document["candidate"]
    reference = document["reference"]
    measurement = document["measurement"]
    query = document["query"]
    eligibility = document["eligibility"]
    if (
        document["schema"] != SCHEMA
        or document["scope"] != SCOPE
        or type(challenge) is not dict
        or set(challenge) != {"id", "version"}
        or type(candidate) is not dict
        or set(candidate)
        != {
            "artifact_digest",
            "binding_digest",
            "source_digest",
            "environment_digest",
            "plan_digest",
            "replica_id",
        }
        or type(reference) is not dict
        or set(reference)
        != {
            "artifact_digest",
            "request_digest",
            "policy_digest",
            "environment_digest",
            "role",
            "scientifically_qualified",
        }
        or type(measurement) is not dict
        or set(measurement)
        != {
            "policy_id",
            "policy_version",
            "contract_digest",
            "environment_digest",
            "implementation_digest",
            "precision",
            "operator_ids",
            "physics_ids",
            "scientific_limits",
            "uncertainty_policy",
            "scientifically_qualified",
        }
        or type(query) is not dict
        or set(query)
        != {
            "spatial_points",
            "requested_times",
            "initial_values",
            "domain_length",
            "viscosity",
            "characteristic_time",
            "amplitude",
            "k_rms",
            "output_semantics",
        }
        or eligibility
        != {
            "development_only": True,
            "protected_execution": False,
            "reference_scientifically_qualified": False,
            "measurement_scientifically_qualified": False,
            "score": False,
        }
        or reference["scientifically_qualified"] is not False
        or measurement["scientific_limits"] is not None
        or measurement["uncertainty_policy"] is not None
        or measurement["scientifically_qualified"] is not False
        or measurement["operator_ids"] != list(MEASUREMENT_IDS)
        or measurement["physics_ids"] != list(PHYSICS_IDS)
    ):
        raise ValueError("invalid measurement request document")
    try:
        result = BurgersMeasurementRequest(
            case_digest=document["case_digest"],
            candidate_artifact_digest=candidate["artifact_digest"],
            candidate_binding_digest=candidate["binding_digest"],
            candidate_source_digest=candidate["source_digest"],
            candidate_environment_digest=candidate["environment_digest"],
            candidate_plan_digest=candidate["plan_digest"],
            candidate_replica_id=candidate["replica_id"],
            reference_artifact_digest=reference["artifact_digest"],
            reference_request_digest=reference["request_digest"],
            reference_policy_digest=reference["policy_digest"],
            reference_environment_digest=reference["environment_digest"],
            measurement_contract_digest=measurement["contract_digest"],
            measurement_environment_digest=measurement["environment_digest"],
            spatial_points=tuple(query["spatial_points"]),
            requested_times=tuple(query["requested_times"]),
            initial_values=tuple(query["initial_values"]),
            domain_length=query["domain_length"],
            viscosity=query["viscosity"],
            characteristic_time=query["characteristic_time"],
            amplitude=query["amplitude"],
            k_rms=query["k_rms"],
            challenge_id=challenge["id"],
            challenge_version=challenge["version"],
            policy_id=measurement["policy_id"],
            policy_version=measurement["policy_version"],
            reference_role=BurgersReferenceRole(reference["role"]),
            precision=measurement["precision"],
            output_semantics=query["output_semantics"],
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid measurement request document") from None
    if (
        result.implementation_digest != measurement["implementation_digest"]
        or result.document() != document
    ):
        raise ValueError("measurement request identity mismatch")
    return result


def stage_measurement_request(
    stage_root: Path,
    request: BurgersMeasurementRequest,
    candidate: FrozenFieldArtifact,
    reference: FrozenFieldArtifact,
) -> tuple[Path, str]:
    if (
        not stage_root.is_absolute()
        or stage_root.is_symlink()
        or type(request) is not BurgersMeasurementRequest
        or type(candidate) is not FrozenFieldArtifact
        or type(reference) is not FrozenFieldArtifact
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    # Execute the complete cross-binding check before creating staged authority.
    if (
        candidate.artifact_digest != request.candidate_artifact_digest
        or reference.artifact_digest != request.reference_artifact_digest
        or candidate.binding_digest != request.candidate_binding_digest
        or reference.binding_digest != request.reference_request_digest
        or candidate.shape != request.shape
        or reference.shape != request.shape
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    stage_root.mkdir(parents=True, exist_ok=True)
    os.chmod(stage_root, 0o700)
    stage = Path(tempfile.mkdtemp(prefix=".c05-stage-", dir=stage_root))
    try:
        files = {
            _REQUEST_FILE: _canonical(request.document()) + b"\n",
            _CANDIDATE_FILE: candidate.payload,
            _REFERENCE_FILE: reference.payload,
        }
        if len(files[_REQUEST_FILE]) > CONTROL_BYTES or any(
            len(files[name]) > _MAX_FIELD_BYTES
            for name in (_CANDIDATE_FILE, _REFERENCE_FILE)
        ):
            raise WorkerFailure(WorkerCode.STAGING)
        digest = hashlib.sha256()
        for name, payload in sorted(files.items()):
            destination = stage / name
            with destination.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(destination, 0o444)
            digest.update(name.encode("ascii"))
            digest.update(hashlib.sha256(payload).digest())
        os.chmod(stage, 0o555)
        return stage, "sha256:" + digest.hexdigest()
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def load_staged_measurement(
    input_directory: Path,
) -> tuple[BurgersMeasurementRequest, FrozenFieldArtifact, FrozenFieldArtifact]:
    if input_directory.is_symlink() or not input_directory.is_dir():
        raise WorkerFailure(WorkerCode.INVALID)
    try:
        members = {item.name: item for item in input_directory.iterdir()}
        if set(members) != {_REQUEST_FILE, _CANDIDATE_FILE, _REFERENCE_FILE}:
            raise WorkerFailure(WorkerCode.INVALID)
        request = decode_measurement_request(_read_json(members[_REQUEST_FILE]))
        payloads: dict[str, bytes] = {}
        expected = request.shape[0] * request.shape[1] * 8
        for name in (_CANDIDATE_FILE, _REFERENCE_FILE):
            info = members[name].lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size != expected:
                raise WorkerFailure(WorkerCode.INVALID)
            with members[name].open("rb") as stream:
                payload = stream.read(_MAX_FIELD_BYTES + 1)
            if len(payload) != expected:
                raise WorkerFailure(WorkerCode.INVALID)
            payloads[name] = payload
        candidate = FrozenFieldArtifact(
            request.candidate_binding_digest,
            request.shape,
            payloads[_CANDIDATE_FILE],
            "CANDIDATE_PREDICTION",
        )
        reference = FrozenFieldArtifact(
            request.reference_request_digest,
            request.shape,
            payloads[_REFERENCE_FILE],
            "REFERENCE_PRIMARY",
        )
        if (
            candidate.artifact_digest != request.candidate_artifact_digest
            or reference.artifact_digest != request.reference_artifact_digest
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        return request, candidate, reference
    except WorkerFailure:
        raise
    except (OSError, TypeError, ValueError):
        raise WorkerFailure(WorkerCode.INVALID) from None


def run_staged_measurement_worker(
    input_directory: Path, scratch_directory: Path
) -> int:
    try:
        request, candidate, reference = load_staged_measurement(input_directory)
        result = execute_measurement(request, candidate, reference)
        output = scratch_directory / "output"
        output.mkdir(mode=0o700, exist_ok=False)
        payload = _canonical(result.document()) + b"\n"
        if len(payload) > CONTROL_BYTES:
            raise WorkerFailure(WorkerCode.OUTPUT)
        with (output / _RESULT_FILE).open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(output / _RESULT_FILE, 0o400)
        os.chmod(output, 0o500)
        (scratch_directory / "ready").touch(mode=0o400, exist_ok=False)
        return 0
    except WorkerFailure:
        return 20
    except (OSError, TypeError, ValueError, FloatingPointError):
        return 21
    except Exception:  # noqa: BLE001 - fixed non-echoing worker failure.
        return 22


def _decode_result(
    document: object, request: BurgersMeasurementRequest
) -> BurgersMeasurementResult:
    if type(document) is not dict or set(document) != {
        "schema",
        "scope",
        "request_digest",
        "disposition",
        "measurements",
        "physics",
        "diagnostics",
        "output_semantics",
        "score_input",
        "eligibility",
    }:
        raise ValueError("invalid measurement result")
    if (
        document["schema"] != "carbon.c05.burgers-measurement-result.v1"
        or document["scope"] != SCOPE
        or document["request_digest"] != request.request_digest
        or document["output_semantics"] != MEASUREMENT_OUTPUT_SEMANTICS
        or document["score_input"] is not None
        or document["eligibility"]
        != {
            "scientifically_qualified": False,
            "protected_execution": False,
            "score": False,
        }
        or type(document["measurements"]) is not list
        or type(document["physics"]) is not list
        or type(document["diagnostics"]) is not list
    ):
        raise ValueError("invalid measurement result")
    measurements = []
    for value in document["measurements"]:
        if type(value) is not dict or set(value) != {
            "measurement_id",
            "candidate_value",
            "reference_value",
            "raw_absolute_error",
            "normalization_scale",
            "normalized_error",
            "uncertainty",
            "scientific_limit",
            "decision",
        }:
            raise ValueError("invalid measurement observation")
        measurements.append(
            MeasurementObservation(
                value["measurement_id"],
                value["candidate_value"],
                value["reference_value"],
                value["raw_absolute_error"],
                value["normalization_scale"],
                value["normalized_error"],
                value["uncertainty"],
                value["scientific_limit"],
                EvidenceDecision(value["decision"]),
            )
        )
    physics = []
    for value in document["physics"]:
        if type(value) is not dict or set(value) != {
            "physics_id",
            "raw_defect",
            "normalization_scale",
            "normalized_defect",
            "uncertainty",
            "scientific_limit",
            "decision",
        }:
            raise ValueError("invalid physics observation")
        physics.append(
            PhysicsObservation(
                value["physics_id"],
                value["raw_defect"],
                value["normalization_scale"],
                value["normalized_defect"],
                value["uncertainty"],
                value["scientific_limit"],
                EvidenceDecision(value["decision"]),
            )
        )
    diagnostics = []
    for item in document["diagnostics"]:
        if (
            type(item) is not list
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) not in (float, int, str)
            or (type(item[1]) is float and not math.isfinite(item[1]))
        ):
            raise ValueError("invalid measurement diagnostic")
        diagnostics.append((item[0], item[1]))
    result = BurgersMeasurementResult(
        request.request_digest,
        MeasurementDisposition(document["disposition"]),
        tuple(measurements),
        tuple(physics),
        tuple(diagnostics),
    )
    if result.document() != document:
        raise ValueError("measurement result identity mismatch")
    return result


def validate_measurement_snapshot(
    snapshot: Path, stage: Path
) -> BurgersMeasurementResult:
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise WorkerFailure(WorkerCode.OUTPUT)
    try:
        members = tuple(snapshot.iterdir())
        if len(members) != 1 or members[0].name != _RESULT_FILE:
            raise WorkerFailure(WorkerCode.OUTPUT)
        request, _, _ = load_staged_measurement(stage)
        return _decode_result(_read_json(members[0]), request)
    except WorkerFailure:
        raise
    except (OSError, TypeError, ValueError):
        raise WorkerFailure(WorkerCode.OUTPUT) from None


def validate_measurement_snapshot_bounded(
    snapshot: Path, stage: Path
) -> BurgersMeasurementResult:
    if (
        not snapshot.is_absolute()
        or snapshot.is_symlink()
        or not snapshot.is_dir()
        or not stage.is_absolute()
        or stage.is_symlink()
        or not stage.is_dir()
    ):
        raise WorkerFailure(WorkerCode.OUTPUT)
    from carbon.reconstruction.worker.docker_runtime import _bounded_capture

    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
    }
    root = Path(__file__).resolve().parents[2]
    try:
        process = _bounded_capture(
            [
                sys.executable,
                "-m",
                "carbon.measurement_runtime.validator",
                str(snapshot),
                str(stage),
            ],
            environment=environment,
            timeout=VALIDATION_WALL_SECONDS,
            maximum=CONTROL_BYTES,
            cwd=root,
        )
        if process.returncode != 0:
            raise WorkerFailure(WorkerCode.OUTPUT)
        request, _, _ = load_staged_measurement(stage)
        document = json.loads(
            process.stdout,
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        return _decode_result(document, request)
    except WorkerFailure:
        raise WorkerFailure(WorkerCode.OUTPUT) from None
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        raise WorkerFailure(WorkerCode.OUTPUT) from None


__all__ = [
    "decode_measurement_request",
    "load_staged_measurement",
    "run_staged_measurement_worker",
    "stage_measurement_request",
    "validate_measurement_snapshot",
    "validate_measurement_snapshot_bounded",
]
