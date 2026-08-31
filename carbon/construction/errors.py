"""Stable failures for the bounded B-02B construction domain."""

from __future__ import annotations


class ConstructionError(Exception):
    """Base class for construction model, reference, and codec failures."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        if type(code) is not str or not code:
            raise TypeError(
                "construction error code must be a nonempty built-in string"
            )
        if type(message) is not str or not message:
            raise TypeError(
                "construction error message must be a nonempty built-in string"
            )
        if type(path) is not str:
            raise TypeError("construction error path must be a built-in string")
        self.code = code
        self.path = path
        super().__init__(message)


class ConstructionValidationError(ConstructionError, ValueError):
    """A construction value is malformed or has a wrong exact nominal type."""


class ConstructionCanonicalEncodingError(ConstructionError, ValueError):
    """A value cannot be represented by the closed construction profile."""


class ConstructionCanonicalDecodingError(ConstructionError, ValueError):
    """Construction bytes are malformed, noncanonical, unknown, or unbounded."""


class ConstructionReferenceMismatchError(ConstructionError, ValueError):
    """Canonical bytes or identity metadata differ from an exact construction ref."""


# Compact public spellings used by callers that do not need the domain prefix.
CanonicalEncodingError = ConstructionCanonicalEncodingError
CanonicalDecodingError = ConstructionCanonicalDecodingError
ReferenceMismatchError = ConstructionReferenceMismatchError


__all__ = [
    "CanonicalDecodingError",
    "CanonicalEncodingError",
    "ConstructionCanonicalDecodingError",
    "ConstructionCanonicalEncodingError",
    "ConstructionError",
    "ConstructionReferenceMismatchError",
    "ConstructionValidationError",
    "ReferenceMismatchError",
]
