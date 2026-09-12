"""Closed DEVELOPMENT-only values for per-job evaluation packs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from carbon.candidates.model import CandidateRef
from carbon.execution import DurableExecutionBinding, ExecutionScope
from carbon.transport.models import canonical, digest

_HEX = re.compile(r"[0-9a-f]{64}\Z")


class PackCode(str, Enum):
    INVALID = "evaluation_pack.request.invalid"
    NOT_FOUND = "evaluation_pack.not_found"
    CONFLICT = "evaluation_pack.conflict"
    STATE = "evaluation_pack.state.invalid"
    CAPACITY = "evaluation_pack.capacity.exceeded"
    STORE = "evaluation_pack.store.failure"
    INDETERMINATE = "evaluation_pack.reconciliation.required"


class PackFailure(RuntimeError):
    """Stable, non-echoing pack boundary failure."""

    def __init__(self, code: PackCode) -> None:
        self.code = code if type(code) is PackCode else PackCode.INVALID
        super().__init__("Development evaluation-pack operation failed.")


class PackState(str, Enum):
    ASSIGNED = "ASSIGNED"
    ATTEMPT_BOUND = "ATTEMPT_BOUND"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RESULT_RECORDED = "RESULT_RECORDED"
    CLOSED = "CLOSED"
    SUMMARY_DELIVERED = "SUMMARY_DELIVERED"
    INCOMPLETE_CLOSED = "INCOMPLETE_CLOSED"
    CANCELLED = "CANCELLED"


class PackWriteDisposition(str, Enum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


def _hex(value: object) -> str:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise PackFailure(PackCode.INVALID)
    return value


@dataclass(frozen=True, slots=True)
class DevelopmentPackPolicy:
    """Nominal fixture composition; no caller-supplied authority flags."""

    schema_version: str = field(
        default="development-evaluation-pack-policy/1", init=False
    )
    scope: str = field(default="FIXTURE_DEVELOPMENT", init=False)
    variant: str = field(default="A_FRESH_PACK_PER_JOB", init=False)
    summary_release: str = field(default="PACK_CLOSURE", init=False)
    evidence_visibility: str = field(default="PRIVATE", init=False)
    answer_publication: str = field(default="UNAVAILABLE", init=False)
    intentional_wait: str = field(default="NONE", init=False)
    sharing: str = field(default="UNAVAILABLE", init=False)
    required_replicas: int = field(default=1, init=False)
    production_eligible: bool = field(default=False, init=False)
    reward_eligible: bool = field(default=False, init=False)

    @property
    def identity(self) -> str:
        return digest(
            canonical(
                {
                    "domain": "carbon.development-evaluation-pack-policy.v1",
                    "schema_version": self.schema_version,
                    "scope": self.scope,
                    "variant": self.variant,
                    "summary_release": self.summary_release,
                    "evidence_visibility": self.evidence_visibility,
                    "answer_publication": self.answer_publication,
                    "intentional_wait": self.intentional_wait,
                    "sharing": self.sharing,
                    "required_replicas": self.required_replicas,
                    "production_eligible": self.production_eligible,
                    "reward_eligible": self.reward_eligible,
                }
            )
        )


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationPackIdentity:
    identity: str
    parent_context_id: str
    policy_id: str
    case_selection_id: str

    def __post_init__(self) -> None:
        for name in (
            "identity",
            "parent_context_id",
            "policy_id",
            "case_selection_id",
        ):
            object.__setattr__(self, name, _hex(getattr(self, name)))

    def evaluation_binding_bytes(self) -> bytes:
        return bytes.fromhex(self.identity)


@dataclass(frozen=True, slots=True, repr=False)
class PackAssignment:
    candidate: CandidateRef
    pack: EvaluationPackIdentity

    def __post_init__(self) -> None:
        if (
            type(self.candidate) is not CandidateRef
            or type(self.pack) is not EvaluationPackIdentity
        ):
            raise PackFailure(PackCode.INVALID)


@dataclass(frozen=True, slots=True, repr=False)
class PackAttemptBinding:
    assignment: PackAssignment
    execution: DurableExecutionBinding
    artifact_digest: str
    configuration_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.assignment) is not PackAssignment
            or type(self.execution) is not DurableExecutionBinding
            or self.execution.scope is not ExecutionScope.FIXTURE_DEVELOPMENT
        ):
            raise PackFailure(PackCode.INVALID)
        _hex(self.artifact_digest)
        _hex(self.configuration_digest)
        expected = self.assignment.pack.evaluation_binding_bytes()
        if self.execution.handle.seed_pin.evaluation_binding._copy_bytes() != expected:
            raise PackFailure(PackCode.CONFLICT)


@dataclass(frozen=True, slots=True)
class DevelopmentPackStatus:
    schema_version: str
    candidate: CandidateRef = field(repr=False)
    state: PackState
    attempt_number: int | None
    summary_available: bool
    production_eligible: bool = False
    reward_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.schema_version != "development-evaluation-pack-status/1"
            or type(self.candidate) is not CandidateRef
            or type(self.state) is not PackState
            or (
                self.attempt_number is not None
                and (type(self.attempt_number) is not int or self.attempt_number < 1)
            )
            or type(self.summary_available) is not bool
            or self.summary_available != (self.state is PackState.SUMMARY_DELIVERED)
            or self.production_eligible is not False
            or self.reward_eligible is not False
        ):
            raise PackFailure(PackCode.INVALID)


__all__ = (
    "DevelopmentPackPolicy",
    "DevelopmentPackStatus",
    "EvaluationPackIdentity",
    "PackAssignment",
    "PackAttemptBinding",
    "PackCode",
    "PackFailure",
    "PackState",
    "PackWriteDisposition",
)
