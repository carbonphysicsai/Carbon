"""Stable fail-closed errors for B-06 structural validation."""

from __future__ import annotations

from enum import Enum


class DossierInputCode(str, Enum):
    WRONG_TYPE = "dossier.wrong_type"
    INVALID_VALUE = "dossier.invalid_value"
    DUPLICATE_IDENTITY = "dossier.duplicate_identity"
    CROSS_CHALLENGE = "dossier.cross_challenge"
    ROLE_CONFUSION = "dossier.role_confusion"
    SLOT_MISMATCH = "dossier.slot_mismatch"
    PLACEHOLDER_EVIDENCE = "dossier.placeholder_evidence"
    MISSING_EVIDENCE = "dossier.missing_evidence"
    VERSION_MISMATCH = "dossier.version_mismatch"
    DIGEST_MISMATCH = "dossier.digest_mismatch"
    SIZE_LIMIT = "dossier.size_limit"


class DossierError(Exception):
    def __init__(self, code: DossierInputCode, *, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code.value} at {path}")


class DossierValidationError(DossierError, ValueError):
    """An in-memory Dossier value violates the closed structural contract."""


class DossierCanonicalError(DossierError, ValueError):
    """Canonical bytes are malformed, non-canonical, or mismatched."""


__all__ = (
    "DossierCanonicalError",
    "DossierError",
    "DossierInputCode",
    "DossierValidationError",
)
