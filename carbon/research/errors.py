"""Closed public-safe failures for the local v2 research protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResearchServiceErrorCode(str, Enum):
    CANONICAL_ENCODING_INVALID = "CANONICAL_ENCODING_INVALID"
    NAMESPACE_MISMATCH = "NAMESPACE_MISMATCH"
    OPERATION_UNSUPPORTED = "OPERATION_UNSUPPORTED"
    REQUEST_TYPE_INVALID = "REQUEST_TYPE_INVALID"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    BOUND_EXCEEDED = "BOUND_EXCEEDED"
    FORBIDDEN_SCIENTIFIC_CONTROL = "FORBIDDEN_SCIENTIFIC_CONTROL"
    CONTEXT_SELECTION_FORBIDDEN = "CONTEXT_SELECTION_FORBIDDEN"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    CHALLENGE_NOT_FOUND = "CHALLENGE_NOT_FOUND"
    REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    PRIOR_INDEX_CHANGED = "PRIOR_INDEX_CHANGED"
    PRIOR_IDENTITY_INVALID = "PRIOR_IDENTITY_INVALID"
    TEST_ONLY_AUTHORITY_INVALID = "TEST_ONLY_AUTHORITY_INVALID"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    INVALID_TASK_TRANSITION = "INVALID_TASK_TRANSITION"
    POLL_SEQUENCE_INVALID = "POLL_SEQUENCE_INVALID"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    DISCLOSURE_REJECTED = "DISCLOSURE_REJECTED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class RetryDisposition(str, Enum):
    NEVER = "NEVER"
    SAME_REQUEST = "SAME_REQUEST"
    NEW_REQUEST = "NEW_REQUEST"


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    key: str
    value: str

    def __post_init__(self) -> None:
        if type(self) is not ErrorDetail:
            raise TypeError("error detail subclasses are rejected")
        for name, value in (("key", self.key), ("value", self.value)):
            if type(value) is not str or not value:
                raise TypeError(f"{name} must be exact nonempty text")
            if len(value.encode("utf-8", errors="strict")) > 16_384:
                raise ValueError(f"{name} exceeds the v2 text bound")


@dataclass(frozen=True, slots=True)
class ResearchServiceError:
    code: ResearchServiceErrorCode
    path: tuple[str, ...]
    message: str
    retry_disposition: RetryDisposition
    details: tuple[ErrorDetail, ...] = ()

    def __post_init__(self) -> None:
        if type(self) is not ResearchServiceError:
            raise TypeError("research service error subclasses are rejected")
        if type(self.code) is not ResearchServiceErrorCode:
            raise TypeError("code must use the exact closed error enum")
        if type(self.retry_disposition) is not RetryDisposition:
            raise TypeError("retry disposition must use its exact enum")
        if type(self.path) is not tuple or len(self.path) > 32:
            raise ValueError("error path exceeds the v2 bound")
        if any(type(part) is not str or not part for part in self.path):
            raise TypeError("error path must contain exact nonempty text")
        if type(self.message) is not str or not self.message:
            raise TypeError("error message must be exact nonempty text")
        if len(self.message.encode("utf-8", errors="strict")) > 1_024:
            raise ValueError("error message exceeds the v2 bound")
        if type(self.details) is not tuple or len(self.details) > 32:
            raise ValueError("error details exceed the v2 bound")
        if any(type(detail) is not ErrorDetail for detail in self.details):
            raise TypeError("error details require exact ErrorDetail values")
        expected = retry_disposition_for(self.code)
        if self.retry_disposition is not expected:
            raise ValueError("retry disposition does not match the error code")


_SAME_REQUEST = frozenset(
    {
        ResearchServiceErrorCode.PROVIDER_UNAVAILABLE,
        ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE,
    }
)


def retry_disposition_for(code: ResearchServiceErrorCode) -> RetryDisposition:
    if type(code) is not ResearchServiceErrorCode:
        raise TypeError("code must use the exact closed error enum")
    if code in _SAME_REQUEST:
        return RetryDisposition.SAME_REQUEST
    if code is ResearchServiceErrorCode.PRIOR_INDEX_CHANGED:
        return RetryDisposition.NEW_REQUEST
    return RetryDisposition.NEVER


_PUBLIC_MESSAGES = {
    code: code.value.lower().replace("_", " ").capitalize() + "."
    for code in ResearchServiceErrorCode
}
_PUBLIC_MESSAGES[ResearchServiceErrorCode.INTERNAL_FAILURE] = (
    "The research service could not complete the request."
)
_PUBLIC_MESSAGES[ResearchServiceErrorCode.DISCLOSURE_REJECTED] = (
    "The result cannot be disclosed."
)


def public_error(
    code: ResearchServiceErrorCode,
    *,
    path: tuple[str, ...] = (),
    details: tuple[ErrorDetail, ...] = (),
) -> ResearchServiceError:
    """Build one constant, non-echoing wire error."""

    return ResearchServiceError(
        code=code,
        path=path,
        message=_PUBLIC_MESSAGES[code],
        retry_disposition=retry_disposition_for(code),
        details=details,
    )


class DiscoveryProviderUnavailable(RuntimeError):
    """Trusted provider signal mapped to a stable public failure."""


__all__ = (
    "DiscoveryProviderUnavailable",
    "ErrorDetail",
    "ResearchServiceError",
    "ResearchServiceErrorCode",
    "RetryDisposition",
    "public_error",
    "retry_disposition_for",
)
