"""Immutable values for the bounded C-02 development reconstruction seam."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from carbon.registry import is_sha256_digest

_MAX_PUBLIC_ARCHIVE_BYTES = 1 << 30


class ReconstructionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    NONFINITE_REJECTED = "NONFINITE_REJECTED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class ReconstructionFailure(ValueError):
    """Stable, non-echoing failure at the development adapter boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("Development reconstruction request was rejected.")


def _digest(value: object, field: str) -> str:
    if type(value) is not str or not is_sha256_digest(value):
        raise ReconstructionFailure(f"reconstruction.{field}.invalid")
    return value


def _token(value: object, field: str) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise ReconstructionFailure(f"reconstruction.{field}.invalid")
    if not all(character.isalnum() or character in "._:-" for character in value):
        raise ReconstructionFailure(f"reconstruction.{field}.invalid")
    return value


@dataclass(frozen=True, slots=True)
class PublicTrainingArchive:
    """A digest-bound public TRAIN archive; never an evaluation capability."""

    path: Path
    content_digest: str
    provenance: str
    role: str = "TRAIN"
    format: str = "carbon.public-trajectories.v1"

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise ReconstructionFailure("reconstruction.archive.path_invalid")
        object.__setattr__(
            self, "content_digest", _digest(self.content_digest, "archive_digest")
        )
        object.__setattr__(self, "provenance", _token(self.provenance, "provenance"))
        if self.role != "TRAIN" or self.format != "carbon.public-trajectories.v1":
            raise ReconstructionFailure("reconstruction.archive.role_invalid")

    @classmethod
    def from_file(cls, path: Path, *, provenance: str) -> PublicTrainingArchive:
        if not isinstance(path, Path) or path.is_symlink():
            raise ReconstructionFailure("reconstruction.archive.path_invalid")
        resolved = path.resolve(strict=True)
        if (
            not resolved.is_file()
            or resolved.stat().st_size > _MAX_PUBLIC_ARCHIVE_BYTES
        ):
            raise ReconstructionFailure("reconstruction.archive.path_invalid")
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
        digest = "sha256:" + digest.hexdigest()
        return cls(resolved, digest, provenance)


@dataclass(frozen=True, slots=True)
class ReconstructionProfile:
    """Complete seed-free mapping from one verified plan to lab configuration."""

    profile_id: str
    profile_version: str
    profile_digest: str
    plan_digest: str
    backbone_kind: str
    model_config_json: str
    task_config_json: str
    train_config_json: str
    source_digest: str
    environment_digest: str
    input_interface_digest: str
    output_interface_digest: str
    mapping_receipt_json: str

    def __post_init__(self) -> None:
        for field in (
            "profile_digest",
            "plan_digest",
            "source_digest",
            "environment_digest",
            "input_interface_digest",
            "output_interface_digest",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), field))
        _token(self.profile_id, "profile_id")
        _token(self.profile_version, "profile_version")
        _token(self.backbone_kind, "backbone_kind")
        for field in (
            "model_config_json",
            "task_config_json",
            "train_config_json",
            "mapping_receipt_json",
        ):
            value = getattr(self, field)
            if type(value) is not str or not value or len(value) > 1_000_000:
                raise ReconstructionFailure(f"reconstruction.{field}.invalid")


@dataclass(frozen=True, slots=True)
class ReconstructionReceipt:
    artifact_path: Path
    artifact_digest: str
    execution_id: str
    plan_digest: str
    profile_digest: str
    training_data_digest: str
    randomness_digest: str
    checkpoint_digest: str
    status: ReconstructionStatus
    completed_steps: int
    compile_seconds: float
    train_execution_seconds: float

    def __post_init__(self) -> None:
        if (
            not isinstance(self.artifact_path, Path)
            or not self.artifact_path.is_absolute()
        ):
            raise ReconstructionFailure("reconstruction.receipt.path_invalid")
        for field in (
            "artifact_digest",
            "plan_digest",
            "profile_digest",
            "training_data_digest",
            "randomness_digest",
            "checkpoint_digest",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), field))
        _token(self.execution_id, "execution_id")
        if type(self.status) is not ReconstructionStatus:
            raise ReconstructionFailure("reconstruction.receipt.status_invalid")
        if type(self.completed_steps) is not int or self.completed_steps < 0:
            raise ReconstructionFailure("reconstruction.receipt.steps_invalid")
        if any(
            type(v) is not float or v < 0
            for v in (self.compile_seconds, self.train_execution_seconds)
        ):
            raise ReconstructionFailure("reconstruction.receipt.timing_invalid")


@dataclass(frozen=True, slots=True)
class PredictionReceipt:
    artifact_digest: str
    request_digest: str
    output_digest: str
    cases: int
    times: int
    points: int
    execution_seconds: float

    def __post_init__(self) -> None:
        for field in ("artifact_digest", "request_digest", "output_digest"):
            object.__setattr__(self, field, _digest(getattr(self, field), field))
        if any(
            type(v) is not int or v < 1 for v in (self.cases, self.times, self.points)
        ):
            raise ReconstructionFailure("reconstruction.prediction.shape_invalid")
        if type(self.execution_seconds) is not float or self.execution_seconds < 0:
            raise ReconstructionFailure("reconstruction.prediction.timing_invalid")


__all__ = [
    "PredictionReceipt",
    "PublicTrainingArchive",
    "ReconstructionFailure",
    "ReconstructionProfile",
    "ReconstructionReceipt",
    "ReconstructionStatus",
]
