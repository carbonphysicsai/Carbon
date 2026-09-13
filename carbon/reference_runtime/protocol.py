"""Closed staging and bounded artifact protocol for the C-04 worker path."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    VALIDATION_WALL_SECONDS,
    WorkerCode,
    WorkerFailure,
)
from carbon.reference_runtime.model import (
    MAX_POINTS,
    MAX_TIMES,
    OUTPUT_SEMANTICS,
    SCOPE,
    BurgersReferenceArtifact,
    BurgersReferenceRequest,
    BurgersReferenceRole,
    BurgersReferenceRun,
    decode_reference_request,
    execute_reference,
)

_RESULT_SCHEMA = "carbon.c04.burgers-reference-result.v1"
_MAX_ARTIFACT_BYTES = MAX_POINTS * MAX_TIMES * 8
_RESULT_FIELDS = {
    "schema",
    "scope",
    "request_digest",
    "role",
    "outcome",
    "failure_reason",
    "artifact",
    "diagnostics",
    "eligibility",
}
_ARTIFACT_FIELDS = {
    "digest",
    "dtype",
    "output_semantics",
    "path",
    "shape",
    "bytes",
}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _unique_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise WorkerFailure(WorkerCode.INVALID)
        result[key] = value
    return result


def _read_closed_json(path: Path, *, maximum: int) -> dict[str, object]:
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


def stage_reference_request(
    stage_root: Path, request: BurgersReferenceRequest
) -> tuple[Path, str]:
    """Persist one immutable controller-created request without caller paths."""

    if (
        not stage_root.is_absolute()
        or stage_root.is_symlink()
        or type(request) is not BurgersReferenceRequest
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    stage_root.mkdir(parents=True, exist_ok=True)
    os.chmod(stage_root, 0o700)
    stage = Path(tempfile.mkdtemp(prefix=".c04-stage-", dir=stage_root))
    try:
        payload = _canonical(request.document()) + b"\n"
        if len(payload) > CONTROL_BYTES:
            raise WorkerFailure(WorkerCode.STAGING)
        destination = stage / "reference-request.json"
        with destination.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        digest = (
            "sha256:"
            + hashlib.sha256(
                destination.name.encode("ascii") + hashlib.sha256(payload).digest()
            ).hexdigest()
        )
        os.chmod(destination, 0o444)
        os.chmod(stage, 0o555)
        return stage, digest
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def load_staged_reference_request(input_directory: Path) -> BurgersReferenceRequest:
    if input_directory.is_symlink() or not input_directory.is_dir():
        raise WorkerFailure(WorkerCode.INVALID)
    try:
        members = tuple(input_directory.iterdir())
        if len(members) != 1 or members[0].name != "reference-request.json":
            raise WorkerFailure(WorkerCode.INVALID)
        return decode_reference_request(
            _read_closed_json(members[0], maximum=CONTROL_BYTES)
        )
    except WorkerFailure:
        raise
    except (OSError, TypeError, ValueError):
        raise WorkerFailure(WorkerCode.INVALID) from None


def _result_document(run: BurgersReferenceRun) -> dict[str, object]:
    artifact = run.artifact
    return {
        "schema": _RESULT_SCHEMA,
        "scope": SCOPE,
        "request_digest": run.request_digest,
        "role": run.role.value,
        "outcome": run.outcome.value,
        "failure_reason": (
            None if run.failure_reason is None else run.failure_reason.value
        ),
        "artifact": (
            None
            if artifact is None
            else {
                "digest": artifact.artifact_digest,
                "dtype": artifact.dtype,
                "output_semantics": artifact.output_semantics,
                "path": "solution.f64le",
                "shape": list(artifact.shape),
                "bytes": len(artifact.payload),
            }
        ),
        "diagnostics": [[key, value] for key, value in run.diagnostics],
        "eligibility": {
            "scientifically_qualified": False,
            "protected_execution": False,
            "score": False,
        },
    }


def run_staged_reference_worker(input_directory: Path, scratch_directory: Path) -> int:
    """Run the fixed reference request and seal provisional scratch output."""

    try:
        request = load_staged_reference_request(input_directory)
        run = execute_reference(request)
        output = scratch_directory / "output"
        output.mkdir(mode=0o700, exist_ok=False)
        if run.artifact is not None:
            artifact_path = output / "solution.f64le"
            with artifact_path.open("xb") as stream:
                stream.write(run.artifact.payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(artifact_path, 0o400)
        manifest = _canonical(_result_document(run)) + b"\n"
        with (output / "result.json").open("xb") as stream:
            stream.write(manifest)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(output / "result.json", 0o400)
        os.chmod(output, 0o500)
        (scratch_directory / "ready").touch(mode=0o400, exist_ok=False)
        return 0
    except WorkerFailure:
        return 20
    except (OSError, TypeError, ValueError):
        return 21
    except Exception:  # noqa: BLE001 - fixed non-echoing worker failure.
        return 22


@dataclass(frozen=True, slots=True)
class ValidatedReferenceResult:
    request_digest: str
    role: BurgersReferenceRole
    outcome: ReferenceRunOutcome
    failure_reason: ReferenceFailureReason | None
    artifact_digest: str | None
    artifact_bytes: int
    shape: tuple[int, int] | None
    diagnostics: tuple[tuple[str, float | int | str], ...]

    def __post_init__(self) -> None:
        supported = self.outcome is ReferenceRunOutcome.SUPPORTED
        request_digest_valid = (
            type(self.request_digest) is str
            and len(self.request_digest) == 71
            and self.request_digest.startswith("sha256:")
            and all(
                character in "0123456789abcdef" for character in self.request_digest[7:]
            )
        )
        artifact_digest_valid = self.artifact_digest is None or (
            type(self.artifact_digest) is str
            and len(self.artifact_digest) == 71
            and self.artifact_digest.startswith("sha256:")
            and all(
                character in "0123456789abcdef"
                for character in self.artifact_digest[7:]
            )
        )
        if (
            not request_digest_valid
            or not artifact_digest_valid
            or type(self.role) is not BurgersReferenceRole
            or type(self.outcome) is not ReferenceRunOutcome
            or (supported and self.failure_reason is not None)
            or (
                not supported
                and type(self.failure_reason) is not ReferenceFailureReason
            )
            or (supported and type(self.artifact_digest) is not str)
            or (not supported and self.artifact_digest is not None)
            or type(self.artifact_bytes) is not int
            or self.artifact_bytes < 0
            or self.artifact_bytes > _MAX_ARTIFACT_BYTES
            or (supported and self.artifact_bytes == 0)
            or (not supported and self.artifact_bytes != 0)
            or (
                supported
                and (
                    type(self.shape) is not tuple
                    or len(self.shape) != 2
                    or any(type(item) is not int or item < 1 for item in self.shape)
                )
            )
            or (not supported and self.shape is not None)
            or type(self.diagnostics) is not tuple
            or any(
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) not in (float, int, str)
                or (type(item[1]) is float and not math.isfinite(item[1]))
                for item in self.diagnostics
            )
        ):
            raise ValueError("invalid validated reference result")

    @property
    def eligible_for_truth_or_score(self) -> bool:
        return False


def validate_reference_snapshot(
    snapshot: Path, request: BurgersReferenceRequest
) -> ValidatedReferenceResult:
    """Validate exact immutable output bytes; no archive extraction is used."""

    if (
        snapshot.is_symlink()
        or not snapshot.is_dir()
        or type(request) is not BurgersReferenceRequest
    ):
        raise WorkerFailure(WorkerCode.OUTPUT)
    try:
        members = {member.name: member for member in snapshot.iterdir()}
        if set(members) not in ({"result.json"}, {"result.json", "solution.f64le"}):
            raise WorkerFailure(WorkerCode.OUTPUT)
        value = _read_closed_json(members["result.json"], maximum=CONTROL_BYTES)
        if (
            set(value) != _RESULT_FIELDS
            or value["schema"] != _RESULT_SCHEMA
            or value["scope"] != SCOPE
            or value["request_digest"] != request.request_digest
            or value["role"] != request.role.value
            or value["eligibility"]
            != {
                "scientifically_qualified": False,
                "protected_execution": False,
                "score": False,
            }
            or type(value["diagnostics"]) is not list
        ):
            raise WorkerFailure(WorkerCode.OUTPUT)
        outcome = ReferenceRunOutcome(value["outcome"])
        failure = (
            None
            if value["failure_reason"] is None
            else ReferenceFailureReason(value["failure_reason"])
        )
        diagnostic_items: list[tuple[str, float | int | str]] = []
        for item in value["diagnostics"]:
            if (
                type(item) is not list
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) not in (float, int, str)
                or (type(item[1]) is float and not math.isfinite(item[1]))
            ):
                raise WorkerFailure(WorkerCode.OUTPUT)
            diagnostic_items.append((item[0], item[1]))
        if outcome is ReferenceRunOutcome.SUPPORTED:
            artifact_value = value["artifact"]
            if (
                failure is not None
                or type(artifact_value) is not dict
                or set(artifact_value) != _ARTIFACT_FIELDS
                or artifact_value["path"] != "solution.f64le"
                or artifact_value["dtype"] != "<f8"
                or artifact_value["output_semantics"] != OUTPUT_SEMANTICS
                or type(artifact_value["shape"]) is not list
                or artifact_value["shape"]
                != [len(request.requested_times), len(request.spatial_points)]
                or type(artifact_value["bytes"]) is not int
                or not 0 < artifact_value["bytes"] <= _MAX_ARTIFACT_BYTES
                or "solution.f64le" not in members
            ):
                raise WorkerFailure(WorkerCode.OUTPUT)
            payload_path = members["solution.f64le"]
            info = payload_path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_size != artifact_value["bytes"]
            ):
                raise WorkerFailure(WorkerCode.OUTPUT)
            with payload_path.open("rb") as stream:
                payload = stream.read(_MAX_ARTIFACT_BYTES + 1)
            if len(payload) != artifact_value["bytes"]:
                raise WorkerFailure(WorkerCode.OUTPUT)
            artifact = BurgersReferenceArtifact(
                request.request_digest,
                tuple(artifact_value["shape"]),
                payload,
            )
            if artifact.artifact_digest != artifact_value["digest"]:
                raise WorkerFailure(WorkerCode.OUTPUT)
            return ValidatedReferenceResult(
                request.request_digest,
                request.role,
                outcome,
                None,
                artifact.artifact_digest,
                len(payload),
                artifact.shape,
                tuple(diagnostic_items),
            )
        if (
            value["artifact"] is not None
            or "solution.f64le" in members
            or failure is None
        ):
            raise WorkerFailure(WorkerCode.OUTPUT)
        BurgersReferenceRun(
            request.request_digest,
            request.role,
            outcome,
            failure,
            None,
            tuple(diagnostic_items),
        )
        return ValidatedReferenceResult(
            request.request_digest,
            request.role,
            outcome,
            failure,
            None,
            0,
            None,
            tuple(diagnostic_items),
        )
    except WorkerFailure:
        raise
    except (OSError, TypeError, ValueError):
        raise WorkerFailure(WorkerCode.OUTPUT) from None


def validate_reference_snapshot_bounded(
    snapshot: Path, stage: Path
) -> ValidatedReferenceResult:
    """Run native array parsing in the separately limited validator process."""

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
                "carbon.reference_runtime.validator",
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
        value = json.loads(
            process.stdout,
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if (
            type(value) is not dict
            or set(value)
            != {
                "request_digest",
                "role",
                "outcome",
                "failure_reason",
                "artifact_digest",
                "artifact_bytes",
                "shape",
                "diagnostics",
                "eligible_for_truth_or_score",
            }
            or value["eligible_for_truth_or_score"] is not False
        ):
            raise WorkerFailure(WorkerCode.OUTPUT)
        diagnostics = tuple(tuple(item) for item in value["diagnostics"])
        shape = None if value["shape"] is None else tuple(value["shape"])
        return ValidatedReferenceResult(
            value["request_digest"],
            BurgersReferenceRole(value["role"]),
            ReferenceRunOutcome(value["outcome"]),
            (
                None
                if value["failure_reason"] is None
                else ReferenceFailureReason(value["failure_reason"])
            ),
            value["artifact_digest"],
            value["artifact_bytes"],
            shape,
            diagnostics,
        )
    except WorkerFailure:
        raise WorkerFailure(WorkerCode.OUTPUT) from None
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        raise WorkerFailure(WorkerCode.OUTPUT) from None


__all__ = [
    "ValidatedReferenceResult",
    "load_staged_reference_request",
    "run_staged_reference_worker",
    "stage_reference_request",
    "validate_reference_snapshot",
    "validate_reference_snapshot_bounded",
]
