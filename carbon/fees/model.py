"""Immutable values for A7 submission identity, fees, and lifecycle control."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum

from carbon.registry import ChallengeKey, is_sha256_digest, validate_version
from carbon.seeding import SeedPin

_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1
_PROFILE_TOKEN = re.compile(
    r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\Z",
    re.ASCII,
)

_ADMISSION_ERROR_CODES = frozenset(
    {
        "admission.challenge_not_live",
        "admission.challenge_not_fixture_eligible",
        "admission.backbone_not_allowed",
        "submission.admission.unavailable",
    }
)


class SubmissionRequestError(ValueError):
    """Stable, non-echoing failure for a malformed A7 boundary value."""

    def __init__(self) -> None:
        self.code = "submission.request.invalid"
        super().__init__("Submission request is invalid.")


class SubmissionNotFoundError(LookupError):
    """Stable, non-echoing failure for an absent retained submission."""

    def __init__(self) -> None:
        self.code = "submission.record.not_found"
        super().__init__("Submission record was not found.")


class SubmissionAuthorizationError(PermissionError):
    """Stable, non-echoing failure for a requester-binding mismatch."""

    def __init__(self) -> None:
        self.code = "submission.authorization.denied"
        super().__init__("Submission access is not authorized.")


class SubmissionStateError(RuntimeError):
    """Stable, non-echoing failure for an illegal lifecycle operation."""

    def __init__(self) -> None:
        self.code = "submission.state.invalid"
        super().__init__("Submission state does not permit this operation.")


class SubmissionConflictError(RuntimeError):
    """Stable failure for a collision or mismatched operation replay."""

    def __init__(self) -> None:
        self.code = "submission.operation.conflict"
        super().__init__("Submission operation conflicts with retained data.")


class SubmissionStoreError(RuntimeError):
    """Stable, non-echoing failure for private-store invariant corruption."""

    def __init__(self) -> None:
        self.code = "submission.store.failure"
        super().__init__("Submission store operation failed.")


class SubmissionResourcePolicyError(ValueError):
    """Stable failure for absent or invalid mandatory resource policy."""

    def __init__(self) -> None:
        self.code = "submission.resource_policy_unavailable"
        super().__init__("Submission resource policy is unavailable.")


class SubmissionResourceError(RuntimeError):
    """Stable request-resource failure without measurements or categories."""

    def __init__(self) -> None:
        self.code = "submission.resource_limit_exceeded"
        super().__init__("Submission resource limit was exceeded.")

    @classmethod
    def _limit_exceeded(cls) -> SubmissionResourceError:
        return cls()

    @classmethod
    def _capacity_exceeded(cls) -> SubmissionResourceError:
        instance = cls.__new__(cls)
        instance.code = "submission.resource_capacity_exceeded"
        RuntimeError.__init__(instance, "Submission resource capacity was exceeded.")
        return instance

    _limit = _limit_exceeded
    _capacity = _capacity_exceeded


class SubmissionAdmissionError(RuntimeError):
    """Stable closed-code failure for queue admission denial/unavailability."""

    def __init__(self, code: str = "submission.admission.unavailable") -> None:
        if type(code) is not str or code not in _ADMISSION_ERROR_CODES:
            code = "submission.admission.unavailable"
        self.code = code
        super().__init__("Submission admission is unavailable.")

    @classmethod
    def _not_live(cls) -> SubmissionAdmissionError:
        return cls("admission.challenge_not_live")

    @classmethod
    def _not_fixture_eligible(cls) -> SubmissionAdmissionError:
        return cls("admission.challenge_not_fixture_eligible")

    @classmethod
    def _backbone_not_allowed(cls) -> SubmissionAdmissionError:
        return cls("admission.backbone_not_allowed")


class SubmissionIntegrationError(RuntimeError):
    """Stable failure for a trusted A2--A6 integration invariant."""

    def __init__(self) -> None:
        self.code = "submission.integration.failure"
        super().__init__("Submission integration failed.")


class AdmissionKind(str, Enum):
    """Closed execution-admission namespaces."""

    PRODUCTION = "PRODUCTION"
    FIXTURE = "FIXTURE"


class SubmissionState(str, Enum):
    """Closed A7 lifecycle states."""

    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SCORED = "SCORED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    FAILED_INFRA = "FAILED_INFRA"
    FAILED_STRATEGY = "FAILED_STRATEGY"
    CANCELLED = "CANCELLED"


_POST_START_STATES = frozenset(
    {
        SubmissionState.QUEUED,
        SubmissionState.RUNNING,
        SubmissionState.SCORED,
        SubmissionState.PUBLISHED,
        SubmissionState.FAILED_INFRA,
        SubmissionState.FAILED_STRATEGY,
        SubmissionState.CANCELLED,
    }
)


class AttemptEventKind(str, Enum):
    """Closed minimal attempt-history vocabulary."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYABLE_INFRA = "RETRYABLE_INFRA"
    SCORED = "SCORED"
    FAILED_STRATEGY = "FAILED_STRATEGY"
    FAILED_INFRA = "FAILED_INFRA"
    CANCELLED = "CANCELLED"


class FeeEventKind(str, Enum):
    """Closed A7 ledger-event vocabulary."""

    CHARGE = "CHARGE"
    REFUND = "REFUND"
    RETRY_CREDIT = "RETRY_CREDIT"


class FeeOperationContext(str, Enum):
    """Closed lifecycle contexts coupled to fee events."""

    INITIAL_RUN_START = "INITIAL_RUN_START"
    RETRY = "RETRY"
    TERMINAL_INFRA = "TERMINAL_INFRA"
    PUBLICATION_INFRA = "PUBLICATION_INFRA"


class StartDisposition(str, Enum):
    """Closed initial-start application/replay outcomes."""

    STARTED = "STARTED"
    ALREADY_STARTED = "ALREADY_STARTED"


def _validated_version_token(value: object) -> str | None:
    if type(value) is not str:
        return None
    try:
        return validate_version(value)
    except ValueError:
        return None


def _is_positive_u64(value: object) -> bool:
    return type(value) is int and 0 < value <= _UINT64_MAX


def _is_nonnegative_u64(value: object) -> bool:
    return type(value) is int and 0 <= value <= _UINT64_MAX


def _is_tagged_sha256(value: object) -> bool:
    return type(value) is str and len(value) == 71 and is_sha256_digest(value)


def _reject_state(value: object) -> None:
    raise TypeError(f"{type(value).__name__} does not support generic serialization")


def _reject_reduce(value: object, protocol: int) -> object:
    del protocol
    raise TypeError(f"{type(value).__name__} does not support generic serialization")


@dataclass(frozen=True, slots=True)
class SubmissionId:
    """Canonical opaque UUIDv4 identity generated by Carbon."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.value) is not str or len(self.value) != 36:
            raise SubmissionRequestError()
        try:
            parsed = uuid.UUID(self.value)
        except (AttributeError, ValueError):
            raise SubmissionRequestError() from None
        if (
            str(parsed) != self.value
            or parsed.version != 4
            or parsed.variant != uuid.RFC_4122
        ):
            raise SubmissionRequestError()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True)
class StrategyHash:
    """Exact tagged SHA-256 identity of an accepted Strategy."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not _is_tagged_sha256(self.value):
            raise SubmissionRequestError()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True)
class RequesterIdentity:
    """Opaque structural requester label, not authentication proof."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        validated = _validated_version_token(self.value)
        if validated is None:
            raise SubmissionRequestError()
        object.__setattr__(self, "value", validated)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True)
class FeePolicyKey:
    """Opaque denomination/schedule/version policy identity."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        validated = _validated_version_token(self.value)
        if validated is None:
            raise SubmissionRequestError()
        object.__setattr__(self, "value", validated)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True)
class FeeOperationKey:
    """Opaque idempotency identity for one economic operation."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        validated = _validated_version_token(self.value)
        if validated is None:
            raise SubmissionRequestError()
        object.__setattr__(self, "value", validated)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True, repr=False)
class SubmissionResourceLimits:
    """Mandatory finite limits for A7 capture and retained-store accounting."""

    max_total_value_nodes: int
    max_object_members: int
    max_list_items: int
    max_string_utf8_bytes: int
    max_object_key_utf8_bytes: int
    max_strategy_identity_bytes: int
    max_challenge_id_bytes: int
    max_concurrent_identity_builds: int
    max_retained_submission_records: int
    max_retained_value_nodes: int
    max_retained_strategy_identity_bytes: int

    def __post_init__(self) -> None:
        values = (
            self.max_total_value_nodes,
            self.max_object_members,
            self.max_list_items,
            self.max_string_utf8_bytes,
            self.max_object_key_utf8_bytes,
            self.max_strategy_identity_bytes,
            self.max_challenge_id_bytes,
            self.max_concurrent_identity_builds,
            self.max_retained_submission_records,
            self.max_retained_value_nodes,
            self.max_retained_strategy_identity_bytes,
        )
        if not all(_is_positive_u64(value) for value in values):
            raise SubmissionResourcePolicyError()
        if self.max_challenge_id_bytes > _UINT32_MAX:
            raise SubmissionResourcePolicyError()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


def _owned_resource_limits(value: object) -> SubmissionResourceLimits:
    if type(value) is not SubmissionResourceLimits:
        raise SubmissionResourcePolicyError()
    try:
        fields = (
            value.max_total_value_nodes,
            value.max_object_members,
            value.max_list_items,
            value.max_string_utf8_bytes,
            value.max_object_key_utf8_bytes,
            value.max_strategy_identity_bytes,
            value.max_challenge_id_bytes,
            value.max_concurrent_identity_builds,
            value.max_retained_submission_records,
            value.max_retained_value_nodes,
            value.max_retained_strategy_identity_bytes,
        )
    except AttributeError:
        raise SubmissionResourcePolicyError() from None
    return SubmissionResourceLimits(*fields)


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionEnvironmentPin:
    """Safe execution-profile identity reference; not runtime configuration."""

    backend_profile_id: str
    container_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.backend_profile_id) is not str
            or not 1 <= len(self.backend_profile_id) <= 128
            or _PROFILE_TOKEN.fullmatch(self.backend_profile_id) is None
            or not _is_tagged_sha256(self.container_digest)
        ):
            raise SubmissionIntegrationError()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


def _owned_submission_id(value: object) -> SubmissionId:
    if type(value) is not SubmissionId:
        raise SubmissionRequestError()
    try:
        captured = value.value
    except AttributeError:
        raise SubmissionRequestError() from None
    return SubmissionId(captured)


def _owned_strategy_hash(value: object) -> StrategyHash:
    if type(value) is not StrategyHash:
        raise SubmissionRequestError()
    try:
        captured = value.value
    except AttributeError:
        raise SubmissionRequestError() from None
    return StrategyHash(captured)


def _owned_requester_identity(value: object) -> RequesterIdentity:
    if type(value) is not RequesterIdentity:
        raise SubmissionRequestError()
    try:
        captured = value.value
    except AttributeError:
        raise SubmissionRequestError() from None
    return RequesterIdentity(captured)


def _owned_fee_policy_key(value: object) -> FeePolicyKey:
    if type(value) is not FeePolicyKey:
        raise SubmissionRequestError()
    try:
        captured = value.value
    except AttributeError:
        raise SubmissionRequestError() from None
    return FeePolicyKey(captured)


def _owned_fee_operation_key(value: object) -> FeeOperationKey:
    if type(value) is not FeeOperationKey:
        raise SubmissionRequestError()
    try:
        captured = value.value
    except AttributeError:
        raise SubmissionRequestError() from None
    return FeeOperationKey(captured)


def _owned_challenge_key(value: object) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise SubmissionRequestError()
    try:
        challenge_id = value.challenge_id
        version = value.version
    except AttributeError:
        raise SubmissionRequestError() from None
    try:
        return ChallengeKey(challenge_id, version)
    except (TypeError, ValueError):
        raise SubmissionRequestError() from None


def _owned_seed_pin(value: object) -> SeedPin:
    if type(value) is not SeedPin:
        raise SubmissionIntegrationError()
    try:
        return value._copy()
    except Exception:  # noqa: BLE001 - a trusted subsystem boundary fails closed.
        raise SubmissionIntegrationError() from None


def _owned_environment_pin(value: object) -> ExecutionEnvironmentPin:
    if type(value) is not ExecutionEnvironmentPin:
        raise SubmissionIntegrationError()
    try:
        backend_profile_id = value.backend_profile_id
        container_digest = value.container_digest
    except AttributeError:
        raise SubmissionIntegrationError() from None
    return ExecutionEnvironmentPin(backend_profile_id, container_digest)


@dataclass(frozen=True, slots=True, repr=False)
class FixtureSubmissionPolicy:
    """Conspicuous fixture-only fee, retry, scientific, and environment pins."""

    fee_policy_key: FeePolicyKey
    amount_minor: int
    max_attempts: int
    generator_version: str
    generator_digest: str
    scoring_version: str
    scoring_digest: str
    environment_pin: ExecutionEnvironmentPin

    def __post_init__(self) -> None:
        try:
            fee_policy_key = _owned_fee_policy_key(self.fee_policy_key)
            environment_pin = _owned_environment_pin(self.environment_pin)
        except (SubmissionRequestError, SubmissionIntegrationError):
            raise SubmissionAdmissionError() from None
        generator_version = _validated_version_token(self.generator_version)
        scoring_version = _validated_version_token(self.scoring_version)
        if (
            not _is_nonnegative_u64(self.amount_minor)
            or not _is_positive_u64(self.max_attempts)
            or generator_version is None
            or not _is_tagged_sha256(self.generator_digest)
            or scoring_version is None
            or not _is_tagged_sha256(self.scoring_digest)
        ):
            raise SubmissionAdmissionError()
        object.__setattr__(self, "fee_policy_key", fee_policy_key)
        object.__setattr__(self, "generator_version", generator_version)
        object.__setattr__(self, "scoring_version", scoring_version)
        object.__setattr__(self, "environment_pin", environment_pin)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True)
class AttemptEvent:
    """One minimal append-only lifecycle event for an execution attempt."""

    attempt_number: int
    kind: AttemptEventKind

    def __post_init__(self) -> None:
        if (
            not _is_positive_u64(self.attempt_number)
            or type(self.kind) is not AttemptEventKind
        ):
            raise SubmissionIntegrationError()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True)
class FeeEvent:
    """One immutable isolated A7 ledger event."""

    sequence: int
    operation_key: FeeOperationKey = field(repr=False)
    policy_key: FeePolicyKey = field(repr=False)
    kind: FeeEventKind
    operation_context: FeeOperationContext
    admission_kind: AdmissionKind
    source_attempt_number: int
    amount_minor: int
    charge_operation_key: FeeOperationKey | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (
            not _is_positive_u64(self.sequence)
            or type(self.kind) is not FeeEventKind
            or type(self.operation_context) is not FeeOperationContext
            or type(self.admission_kind) is not AdmissionKind
            or not _is_positive_u64(self.source_attempt_number)
            or not _is_nonnegative_u64(self.amount_minor)
        ):
            raise SubmissionIntegrationError()
        try:
            operation_key = _owned_fee_operation_key(self.operation_key)
            policy_key = _owned_fee_policy_key(self.policy_key)
            charge_operation_key = (
                None
                if self.charge_operation_key is None
                else _owned_fee_operation_key(self.charge_operation_key)
            )
        except SubmissionRequestError:
            raise SubmissionIntegrationError() from None

        if self.kind is FeeEventKind.CHARGE:
            valid_coupling = (
                self.operation_context is FeeOperationContext.INITIAL_RUN_START
                and self.source_attempt_number == 1
                and charge_operation_key is None
            )
        elif self.kind is FeeEventKind.REFUND:
            valid_coupling = (
                self.operation_context
                in {
                    FeeOperationContext.TERMINAL_INFRA,
                    FeeOperationContext.PUBLICATION_INFRA,
                }
                and charge_operation_key is not None
            )
        else:
            valid_coupling = (
                self.operation_context is FeeOperationContext.RETRY
                and charge_operation_key is not None
            )
        if not valid_coupling:
            raise SubmissionIntegrationError()

        object.__setattr__(self, "operation_key", operation_key)
        object.__setattr__(self, "policy_key", policy_key)
        object.__setattr__(self, "charge_operation_key", charge_operation_key)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


def _owned_attempt_event(value: object) -> AttemptEvent:
    if type(value) is not AttemptEvent:
        raise SubmissionIntegrationError()
    try:
        attempt_number = value.attempt_number
        kind = value.kind
    except AttributeError:
        raise SubmissionIntegrationError() from None
    return AttemptEvent(attempt_number, kind)


def _owned_fee_event(value: object) -> FeeEvent:
    if type(value) is not FeeEvent:
        raise SubmissionIntegrationError()
    try:
        sequence = value.sequence
        operation_key = value.operation_key
        policy_key = value.policy_key
        kind = value.kind
        operation_context = value.operation_context
        admission_kind = value.admission_kind
        source_attempt_number = value.source_attempt_number
        amount_minor = value.amount_minor
        charge_operation_key = value.charge_operation_key
    except AttributeError:
        raise SubmissionIntegrationError() from None
    return FeeEvent(
        sequence=sequence,
        operation_key=operation_key,
        policy_key=policy_key,
        kind=kind,
        operation_context=operation_context,
        admission_kind=admission_kind,
        source_attempt_number=source_attempt_number,
        amount_minor=amount_minor,
        charge_operation_key=charge_operation_key,
    )


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionAttemptHandle:
    """Private structural handoff identity for one current attempt."""

    submission_id: SubmissionId
    attempt_number: int
    admission_kind: AdmissionKind
    seed_pin: SeedPin
    environment_pin: ExecutionEnvironmentPin

    def __post_init__(self) -> None:
        if (
            not _is_positive_u64(self.attempt_number)
            or type(self.admission_kind) is not AdmissionKind
        ):
            raise SubmissionIntegrationError()
        try:
            submission_id = _owned_submission_id(self.submission_id)
        except SubmissionRequestError:
            raise SubmissionIntegrationError() from None
        seed_pin = _owned_seed_pin(self.seed_pin)
        environment_pin = _owned_environment_pin(self.environment_pin)
        object.__setattr__(self, "submission_id", submission_id)
        object.__setattr__(self, "seed_pin", seed_pin)
        object.__setattr__(self, "environment_pin", environment_pin)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


def _owned_attempt_handle(value: object) -> ExecutionAttemptHandle:
    if type(value) is not ExecutionAttemptHandle:
        raise SubmissionIntegrationError()
    try:
        submission_id = value.submission_id
        attempt_number = value.attempt_number
        admission_kind = value.admission_kind
        seed_pin = value.seed_pin
        environment_pin = value.environment_pin
    except AttributeError:
        raise SubmissionIntegrationError() from None
    return ExecutionAttemptHandle(
        submission_id=submission_id,
        attempt_number=attempt_number,
        admission_kind=admission_kind,
        seed_pin=seed_pin,
        environment_pin=environment_pin,
    )


def _owned_execution_handle(value: object) -> ExecutionAttemptHandle:
    return _owned_attempt_handle(value)


def _owned_fixture_policy(value: object) -> FixtureSubmissionPolicy:
    if type(value) is not FixtureSubmissionPolicy:
        raise SubmissionAdmissionError()
    try:
        fee_policy_key = value.fee_policy_key
        amount_minor = value.amount_minor
        max_attempts = value.max_attempts
        generator_version = value.generator_version
        generator_digest = value.generator_digest
        scoring_version = value.scoring_version
        scoring_digest = value.scoring_digest
        environment_pin = value.environment_pin
    except AttributeError:
        raise SubmissionAdmissionError() from None
    return FixtureSubmissionPolicy(
        fee_policy_key=fee_policy_key,
        amount_minor=amount_minor,
        max_attempts=max_attempts,
        generator_version=generator_version,
        generator_digest=generator_digest,
        scoring_version=scoring_version,
        scoring_digest=scoring_digest,
        environment_pin=environment_pin,
    )


@dataclass(frozen=True, slots=True, repr=False)
class ProductionExecutionEnvelope:
    """Private production-kind execution handoff; production cannot yet queue."""

    handle: ExecutionAttemptHandle
    strategy: dict[str, object]
    strategy_hash: StrategyHash
    challenge_key: ChallengeKey

    def __post_init__(self) -> None:
        handle = _owned_attempt_handle(self.handle)
        if (
            handle.admission_kind is not AdmissionKind.PRODUCTION
            or type(self.strategy) is not dict
        ):
            raise SubmissionIntegrationError()
        try:
            strategy_hash = _owned_strategy_hash(self.strategy_hash)
            challenge_key = _owned_challenge_key(self.challenge_key)
        except SubmissionRequestError:
            raise SubmissionIntegrationError() from None
        if challenge_key != handle.seed_pin.challenge_key:
            raise SubmissionIntegrationError()
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "strategy_hash", strategy_hash)
        object.__setattr__(self, "challenge_key", challenge_key)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True, repr=False)
class FixtureExecutionEnvelope:
    """Private fixture-kind execution handoff with no emission authority."""

    handle: ExecutionAttemptHandle
    strategy: dict[str, object]
    strategy_hash: StrategyHash
    challenge_key: ChallengeKey

    def __post_init__(self) -> None:
        handle = _owned_attempt_handle(self.handle)
        if (
            handle.admission_kind is not AdmissionKind.FIXTURE
            or type(self.strategy) is not dict
        ):
            raise SubmissionIntegrationError()
        try:
            strategy_hash = _owned_strategy_hash(self.strategy_hash)
            challenge_key = _owned_challenge_key(self.challenge_key)
        except SubmissionRequestError:
            raise SubmissionIntegrationError() from None
        if challenge_key != handle.seed_pin.challenge_key:
            raise SubmissionIntegrationError()
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "strategy_hash", strategy_hash)
        object.__setattr__(self, "challenge_key", challenge_key)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


ExecutionEnvelope = ProductionExecutionEnvelope | FixtureExecutionEnvelope


@dataclass(frozen=True, slots=True)
class SubmissionStatusView:
    """Bounded requester-authorized public view of lifecycle state."""

    submission_id: SubmissionId = field(repr=False)
    state: SubmissionState

    def __post_init__(self) -> None:
        if type(self.state) is not SubmissionState:
            raise SubmissionIntegrationError()
        try:
            submission_id = _owned_submission_id(self.submission_id)
        except SubmissionRequestError:
            raise SubmissionIntegrationError() from None
        object.__setattr__(self, "submission_id", submission_id)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


def _owned_status_view(value: object) -> SubmissionStatusView:
    if type(value) is not SubmissionStatusView:
        raise SubmissionIntegrationError()
    try:
        submission_id = value.submission_id
        state = value.state
    except AttributeError:
        raise SubmissionIntegrationError() from None
    return SubmissionStatusView(submission_id, state)


@dataclass(frozen=True, slots=True, repr=False)
class InitialRunStartResult:
    """Closed sum of first-start application and exact replay."""

    disposition: StartDisposition
    fee_event: FeeEvent
    envelope: ExecutionEnvelope | None = None
    state: SubmissionState | None = None

    def __post_init__(self) -> None:
        if type(self.disposition) is not StartDisposition:
            raise SubmissionIntegrationError()
        fee_event = _owned_fee_event(self.fee_event)
        if (
            fee_event.kind is not FeeEventKind.CHARGE
            or fee_event.operation_context is not FeeOperationContext.INITIAL_RUN_START
        ):
            raise SubmissionIntegrationError()

        if self.disposition is StartDisposition.STARTED:
            if (
                type(self.envelope)
                not in {ProductionExecutionEnvelope, FixtureExecutionEnvelope}
                or self.state is not None
            ):
                raise SubmissionIntegrationError()
            envelope = self.envelope
            if envelope is None:
                raise SubmissionIntegrationError()
            if (
                envelope.handle.admission_kind is not fee_event.admission_kind
                or envelope.handle.attempt_number != fee_event.source_attempt_number
            ):
                raise SubmissionIntegrationError()
        elif (
            self.envelope is not None
            or type(self.state) is not SubmissionState
            or self.state not in _POST_START_STATES
        ):
            raise SubmissionIntegrationError()

        object.__setattr__(self, "fee_event", fee_event)

    @classmethod
    def started(
        cls,
        fee_event: FeeEvent,
        envelope: ExecutionEnvelope,
    ) -> InitialRunStartResult:
        return cls(StartDisposition.STARTED, fee_event, envelope=envelope)

    @classmethod
    def already_started(
        cls,
        fee_event: FeeEvent,
        state: SubmissionState,
    ) -> InitialRunStartResult:
        return cls(StartDisposition.ALREADY_STARTED, fee_event, state=state)

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce
