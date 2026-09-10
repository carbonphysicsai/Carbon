"""Closed private values for the C1 durable execution queue."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
)
from carbon.registry import is_sha256_digest, validate_version

_OPAQUE_REF = re.compile(r"[A-Za-z0-9]+(?:[._:-][A-Za-z0-9]+)*\Z", re.ASCII)


class ExecutionCode(str, Enum):
    INVALID = "execution.request.invalid"
    NOT_FOUND = "execution.attempt.not_found"
    DENIED = "execution.authorization.denied"
    CONFLICT = "execution.operation.conflict"
    STATE = "execution.state.invalid"
    CAPACITY = "execution.capacity.exceeded"
    STORE = "execution.store.failure"


class ExecutionFailure(RuntimeError):
    """Stable non-echoing C1 boundary failure."""

    def __init__(self, code: ExecutionCode) -> None:
        if type(code) is not ExecutionCode:
            code = ExecutionCode.INVALID
        self.code = code
        super().__init__("Durable execution operation failed.")


class ExecutionScope(str, Enum):
    FIXTURE_DEVELOPMENT = "FIXTURE_DEVELOPMENT"
    REAL_PATH_NON_LIVE = "REAL_PATH_NON_LIVE"


class ExecutionState(str, Enum):
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    RUNNING = "RUNNING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RETRYABLE_INFRA = "RETRYABLE_INFRA"
    RESULT_RECORDED = "RESULT_RECORDED"
    FAILED_INFRA = "FAILED_INFRA"
    FAILED_STRATEGY = "FAILED_STRATEGY"
    CANCELLED = "CANCELLED"


class ExecutionStage(str, Enum):
    RECONSTRUCTION = "RECONSTRUCTION"
    PREDICTION = "PREDICTION"
    REFERENCE = "REFERENCE"
    MEASUREMENT = "MEASUREMENT"
    SCORE = "SCORE"
    RECEIPT = "RECEIPT"
    ARCHIVE = "ARCHIVE"


class ReconciliationDisposition(str, Enum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    RESUME_EXISTING = "RESUME_EXISTING"


class ArchiveRequirement(str, Enum):
    C_EA2_ACKNOWLEDGEMENT_REQUIRED = "C_EA2_ACKNOWLEDGEMENT_REQUIRED"


class WriteDisposition(str, Enum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


def _tagged_digest(value: object) -> str:
    if type(value) is not str or not is_sha256_digest(value):
        raise ExecutionFailure(ExecutionCode.INVALID)
    return value


def validate_execution_token(value: object, *, maximum: int = 128) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise ExecutionFailure(ExecutionCode.INVALID)
    if _OPAQUE_REF.fullmatch(value) is None:
        raise ExecutionFailure(ExecutionCode.INVALID)
    return value


def _copy_handle(value: object) -> ExecutionAttemptHandle:
    if type(value) is not ExecutionAttemptHandle:
        raise ExecutionFailure(ExecutionCode.INVALID)
    try:
        return ExecutionAttemptHandle(
            submission_id=SubmissionId(value.submission_id.value),
            attempt_number=value.attempt_number,
            admission_kind=value.admission_kind,
            seed_pin=value.seed_pin,
            environment_pin=value.environment_pin,
        )
    except Exception:  # noqa: BLE001 - trusted source value still fails closed.
        raise ExecutionFailure(ExecutionCode.INVALID) from None


def _copy_requester(value: object) -> RequesterIdentity:
    if type(value) is not RequesterIdentity:
        raise ExecutionFailure(ExecutionCode.INVALID)
    try:
        return RequesterIdentity(validate_version(value.value))
    except Exception:  # noqa: BLE001 - stable boundary error.
        raise ExecutionFailure(ExecutionCode.INVALID) from None


def _copy_strategy_hash(value: object) -> StrategyHash:
    if type(value) is not StrategyHash:
        raise ExecutionFailure(ExecutionCode.INVALID)
    try:
        return StrategyHash(value.value)
    except Exception:  # noqa: BLE001 - stable boundary error.
        raise ExecutionFailure(ExecutionCode.INVALID) from None


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionAttemptRef:
    submission_id: SubmissionId
    attempt_number: int

    def __post_init__(self) -> None:
        try:
            submission = SubmissionId(self.submission_id.value)
        except Exception:  # noqa: BLE001
            raise ExecutionFailure(ExecutionCode.INVALID) from None
        if type(self.attempt_number) is not int or not 1 <= self.attempt_number < 2**63:
            raise ExecutionFailure(ExecutionCode.INVALID)
        object.__setattr__(self, "submission_id", submission)


@dataclass(frozen=True, slots=True, repr=False)
class DurableExecutionBinding:
    """Exact C1 inputs; scientific values remain owned by their source contracts."""

    handle: ExecutionAttemptHandle
    requester_identity: RequesterIdentity
    strategy_hash: StrategyHash
    scope: ExecutionScope
    resolved_plan_digest: str
    reconstruction_policy_digest: str
    resource_policy_digest: str
    protected_evaluation_policy_digest: str

    def __post_init__(self) -> None:
        handle = _copy_handle(self.handle)
        requester = _copy_requester(self.requester_identity)
        strategy_hash = _copy_strategy_hash(self.strategy_hash)
        if type(self.scope) is not ExecutionScope:
            raise ExecutionFailure(ExecutionCode.INVALID)
        expected_scope = (
            ExecutionScope.FIXTURE_DEVELOPMENT
            if handle.admission_kind is AdmissionKind.FIXTURE
            else ExecutionScope.REAL_PATH_NON_LIVE
        )
        if self.scope is not expected_scope:
            raise ExecutionFailure(ExecutionCode.INVALID)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "requester_identity", requester)
        object.__setattr__(self, "strategy_hash", strategy_hash)
        for name in (
            "resolved_plan_digest",
            "reconstruction_policy_digest",
            "resource_policy_digest",
            "protected_evaluation_policy_digest",
        ):
            object.__setattr__(self, name, _tagged_digest(getattr(self, name)))

    @property
    def ref(self) -> ExecutionAttemptRef:
        return ExecutionAttemptRef(
            SubmissionId(self.handle.submission_id.value), self.handle.attempt_number
        )


@dataclass(frozen=True, slots=True, repr=False)
class QueueClaim:
    ref: ExecutionAttemptRef
    claim_id: str
    worker_id: str

    def __post_init__(self) -> None:
        if type(self.ref) is not ExecutionAttemptRef:
            raise ExecutionFailure(ExecutionCode.INVALID)
        object.__setattr__(
            self,
            "ref",
            ExecutionAttemptRef(self.ref.submission_id, self.ref.attempt_number),
        )
        object.__setattr__(self, "claim_id", validate_execution_token(self.claim_id))
        object.__setattr__(self, "worker_id", validate_execution_token(self.worker_id))


@dataclass(frozen=True, slots=True, repr=False)
class ClaimedExecution:
    claim: QueueClaim
    binding: DurableExecutionBinding

    def __post_init__(self) -> None:
        if (
            type(self.claim) is not QueueClaim
            or type(self.binding) is not DurableExecutionBinding
        ):
            raise ExecutionFailure(ExecutionCode.INVALID)
        if self.claim.ref != self.binding.ref:
            raise ExecutionFailure(ExecutionCode.INVALID)


@dataclass(frozen=True, slots=True, repr=False)
class PartialWorkRef:
    stage: ExecutionStage
    artifact_ref: str
    artifact_digest: str

    def __post_init__(self) -> None:
        if type(self.stage) is not ExecutionStage:
            raise ExecutionFailure(ExecutionCode.INVALID)
        object.__setattr__(
            self, "artifact_ref", validate_execution_token(self.artifact_ref)
        )
        object.__setattr__(
            self, "artifact_digest", _tagged_digest(self.artifact_digest)
        )


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionResultRefs:
    """Opaque owner references only; C-EA2 still owns finalization."""

    private_result_ref: str
    private_result_digest: str
    card_record_ref: str
    transcript_ref: str
    transcript_digest: str
    archive_requirement: ArchiveRequirement = field(
        default=ArchiveRequirement.C_EA2_ACKNOWLEDGEMENT_REQUIRED
    )
    archive_acknowledgement_ref: None = field(default=None)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "private_result_ref",
            validate_execution_token(self.private_result_ref),
        )
        object.__setattr__(
            self, "private_result_digest", _tagged_digest(self.private_result_digest)
        )
        object.__setattr__(
            self, "card_record_ref", validate_execution_token(self.card_record_ref)
        )
        object.__setattr__(
            self, "transcript_ref", validate_execution_token(self.transcript_ref)
        )
        object.__setattr__(
            self, "transcript_digest", _tagged_digest(self.transcript_digest)
        )
        if (
            self.archive_requirement
            is not ArchiveRequirement.C_EA2_ACKNOWLEDGEMENT_REQUIRED
            or self.archive_acknowledgement_ref is not None
        ):
            raise ExecutionFailure(ExecutionCode.INVALID)


@dataclass(frozen=True, slots=True)
class ExecutionStatusView:
    """Requester-safe view: no pins, strategy, protected data, or result bytes."""

    schema_version: str
    submission_id: SubmissionId = field(repr=False)
    attempt_number: int
    state: ExecutionState
    partial_stage_count: int
    result_recorded: bool
    archive_acknowledged: bool

    def __post_init__(self) -> None:
        if (
            self.schema_version != "c1-execution-status/1"
            or type(self.state) is not ExecutionState
            or type(self.partial_stage_count) is not int
            or not 0 <= self.partial_stage_count <= len(ExecutionStage)
            or type(self.result_recorded) is not bool
            or type(self.archive_acknowledged) is not bool
            or self.archive_acknowledged is not False
        ):
            raise ExecutionFailure(ExecutionCode.INVALID)
        ref = ExecutionAttemptRef(self.submission_id, self.attempt_number)
        object.__setattr__(self, "submission_id", ref.submission_id)
        if self.result_recorded != (self.state is ExecutionState.RESULT_RECORDED):
            raise ExecutionFailure(ExecutionCode.INVALID)
