"""Nominal protected runner interfaces for registered B-04 executions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .errors import ReferenceInputCode, ReferenceValidationError
from .execution import (
    PrimaryReferenceRequest,
    PrimaryRunGrant,
    ReferenceRunRecord,
    WitnessReferenceRequest,
    WitnessRunGrant,
    _validate_request_grant_pair,
)

_STATIC_MEMBER_ABSENT = object()


def _static_member(value: object, name: str) -> object:
    """Inspect one declared interface member without binding descriptors."""

    value_type = type(value)
    for owner in type.__getattribute__(value_type, "__mro__"):
        namespace = type.__getattribute__(owner, "__dict__")
        if name in namespace:
            return namespace[name]
    return _STATIC_MEMBER_ABSENT


def _static_callable_member(value: object, name: str) -> bool:
    """Return whether one statically declared member is safely known callable."""

    member = _static_member(value, name)
    if type(member) in {classmethod, staticmethod}:
        member = member.__func__
    return member is not _STATIC_MEMBER_ABSENT and callable(member)


def _statically_declares(value: object, name: str) -> bool:
    """Return whether one role member is declared without invoking caller code."""

    return _static_member(value, name) is not _STATIC_MEMBER_ABSENT


@runtime_checkable
class PrimaryReferenceRunner(Protocol):
    """A runner that accepts only the exact registered primary capability."""

    def run_primary(
        self,
        grant: PrimaryRunGrant,
        request: PrimaryReferenceRequest,
    ) -> ReferenceRunRecord: ...


@runtime_checkable
class WitnessReferenceRunner(Protocol):
    """A runner that accepts only the exact registered witness capability."""

    def run_witness(
        self,
        grant: WitnessRunGrant,
        request: WitnessReferenceRequest,
    ) -> ReferenceRunRecord: ...


def require_primary_runner(value: object) -> PrimaryReferenceRunner:
    """Validate one nominal primary interface without invoking caller code."""

    try:
        valid = _static_callable_member(
            value,
            "run_primary",
        ) and not _statically_declares(value, "run_witness")
    except Exception:  # noqa: BLE001 - sanitize hostile structural inspection.
        valid = False
    if not valid:
        raise ReferenceValidationError(
            ReferenceInputCode.AUTHORITY_INTERFACE_INVALID,
            path="/runner",
        )
    return value


def require_witness_runner(value: object) -> WitnessReferenceRunner:
    """Validate one nominal witness interface without invoking caller code."""

    try:
        valid = _static_callable_member(
            value,
            "run_witness",
        ) and not _statically_declares(value, "run_primary")
    except Exception:  # noqa: BLE001 - sanitize hostile structural inspection.
        valid = False
    if not valid:
        raise ReferenceValidationError(
            ReferenceInputCode.AUTHORITY_INTERFACE_INVALID,
            path="/runner",
        )
    return value


def validate_primary_invocation(
    grant: PrimaryRunGrant,
    request: PrimaryReferenceRequest,
) -> None:
    """Fail closed before a primary provider boundary is crossed."""

    _validate_request_grant_pair(request, grant)


def validate_witness_invocation(
    grant: WitnessRunGrant,
    request: WitnessReferenceRequest,
) -> None:
    """Fail closed before a witness provider boundary is crossed."""

    _validate_request_grant_pair(request, grant)


__all__ = [
    "PrimaryReferenceRunner",
    "WitnessReferenceRunner",
    "require_primary_runner",
    "require_witness_runner",
    "validate_primary_invocation",
    "validate_witness_invocation",
]
