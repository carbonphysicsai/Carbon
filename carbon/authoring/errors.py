"""Stable failures for Carbon scientific-authoring contracts."""

from __future__ import annotations


class AuthoringError(Exception):
    """Base class for bounded B-02A failures."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        if type(code) is not str or not code:
            raise TypeError("authoring error code must be a nonempty built-in string")
        if type(message) is not str or not message:
            raise TypeError(
                "authoring error message must be a nonempty built-in string"
            )
        if type(path) is not str:
            raise TypeError("authoring error path must be a built-in string")
        self.code = code
        self.path = path
        super().__init__(message)


class AuthoringValidationError(AuthoringError, ValueError):
    """An exact authored value is malformed or has the wrong nominal type."""


class CanonicalEncodingError(AuthoringError, ValueError):
    """A value cannot be represented by the closed v1 canonical profile."""


class CanonicalDecodingError(AuthoringError, ValueError):
    """Canonical bytes are malformed, non-canonical, unknown, or out of bounds."""


class ReferenceMismatchError(AuthoringError, ValueError):
    """Canonical bytes or identity metadata do not match an expected exact ref."""
