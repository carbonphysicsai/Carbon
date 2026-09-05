"""Stable fail-closed errors for B-05 measurement authoring."""

from __future__ import annotations

from enum import Enum


class MeasurementInputCode(str, Enum):
    WRONG_TYPE = "measurement.wrong_type"
    INVALID_VALUE = "measurement.invalid_value"
    DUPLICATE_IDENTITY = "measurement.duplicate_identity"
    CROSS_CHALLENGE = "measurement.cross_challenge"
    ROLE_CONFUSION = "measurement.role_confusion"
    CLAIM_MATRIX_VIOLATION = "measurement.claim_matrix_violation"
    FIXTURE_REQUIRED = "measurement.fixture_required"
    DIGEST_MISMATCH = "measurement.digest_mismatch"
    UNKNOWN_OBJECT = "measurement.unknown_object"
    SIZE_LIMIT = "measurement.size_limit"
    PACK_NOT_READY = "measurement.pack_not_ready"
    PACK_COVERAGE_MISMATCH = "measurement.pack_coverage_mismatch"
    FORBIDDEN_SOURCE = "measurement.forbidden_source"
    MATERIAL_UNRESOLVED = "measurement.material_unresolved"


class MeasurementError(Exception):
    """Base B-05 failure with stable code and JSON-pointer-like path."""

    def __init__(self, code: MeasurementInputCode, *, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code.value} at {path}")


class MeasurementValidationError(MeasurementError, ValueError):
    """One in-memory B-05 value violates the closed contract."""


class MeasurementCanonicalError(MeasurementError, ValueError):
    """Canonical bytes are malformed, non-canonical, or mismatched."""


class MeasurementStoreError(MeasurementError):
    """Fixture-store access failed closed."""


__all__ = (
    "MeasurementCanonicalError",
    "MeasurementError",
    "MeasurementInputCode",
    "MeasurementStoreError",
    "MeasurementValidationError",
)
