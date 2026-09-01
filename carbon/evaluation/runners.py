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

    if not isinstance(value, PrimaryReferenceRunner):
        raise ReferenceValidationError(
            ReferenceInputCode.AUTHORITY_INTERFACE_INVALID,
            path="/runner",
        )
    return value


def require_witness_runner(value: object) -> WitnessReferenceRunner:
    """Validate one nominal witness interface without invoking caller code."""

    if not isinstance(value, WitnessReferenceRunner):
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
