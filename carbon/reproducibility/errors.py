"""Fixed B-E1 validation and injected-procedure errors."""

from __future__ import annotations

from enum import Enum


class ReproducibilityErrorCode(str, Enum):
    WRONG_TYPE = "reproducibility.input.wrong_type"
    INVALID_VALUE = "reproducibility.input.invalid_value"
    CROSS_CHALLENGE = "reproducibility.input.cross_challenge"
    ROLE_CONFUSION = "reproducibility.input.role_confusion"
    DUPLICATE_IDENTITY = "reproducibility.input.duplicate_identity"
    INCOMPLETE_EVIDENCE = "reproducibility.evidence.incomplete"
    DEPENDENCY_UNDISCLOSED = "reproducibility.evidence.dependency_undisclosed"
    IDENTITY_MISMATCH = "reproducibility.identity.mismatch"
    PROCEDURE_INVALID = "reproducibility.procedure.invalid"


class ReproducibilityError(Exception):
    """Base B-E1 error with a closed message surface."""


class ReproducibilityValidationError(ReproducibilityError, ValueError):
    def __init__(self, code: ReproducibilityErrorCode, *, path: str) -> None:
        if type(code) is not ReproducibilityErrorCode or type(path) is not str:
            raise TypeError("invalid reproducibility validation error")
        self.code = code
        self.path = path
        super().__init__("Reproducibility input is invalid.")
