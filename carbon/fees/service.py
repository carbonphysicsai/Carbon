"""A7's bounded submission intake, lifecycle, attempt, and fee service."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from carbon.cards import (
    CardRecordKey,
    CardWriteDisposition,
    EvaluationCard,
    RequesterAuthorizationKey,
)
from carbon.registry import ChallengeKey, ChallengeRegistry, LiveEligibility
from carbon.scoring.model import InternalResult, ScoreStatus
from carbon.seeding import EvaluationBinding, SeedPin

from .identity import (
    _copy_strategy_tree,
    _evaluation_binding,
    _validate_and_hash_strategy,
)
from .integration import _owned_internal_result, _result_matches_seed_pin
from .model import (
    AdmissionKind,
    AttemptEvent,
    AttemptEventKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FeeEvent,
    FeeEventKind,
    FeeOperationContext,
    FeeOperationKey,
    FeePolicyKey,
    FixtureExecutionEnvelope,
    FixtureSubmissionPolicy,
    InitialRunStartResult,
    ProductionExecutionEnvelope,
    RequesterIdentity,
    StartDisposition,
    StrategyHash,
    SubmissionAdmissionError,
    SubmissionAuthorizationError,
    SubmissionConflictError,
    SubmissionId,
    SubmissionIntegrationError,
    SubmissionNotFoundError,
    SubmissionRequestError,
    SubmissionResourceError,
    SubmissionResourceLimits,
    SubmissionState,
    SubmissionStateError,
    SubmissionStatusView,
    SubmissionStoreError,
    _owned_execution_handle,
    _owned_fixture_policy,
)
from .store import _SubmissionRecord, _SubmissionStore

_U64_MAX = (1 << 64) - 1


def _requester(value: object) -> RequesterIdentity:
    try:
        if type(value) is not RequesterIdentity:
            raise TypeError
        local = value.value
        if type(local) is not str or len(local) > 64:
            raise TypeError
        return RequesterIdentity(local)
    except (AttributeError, TypeError, ValueError):
        raise SubmissionRequestError() from None


def _submission_id(value: object) -> SubmissionId:
    try:
        if type(value) is not SubmissionId:
            raise TypeError
        local = value.value
        if type(local) is not str or len(local) != 36:
            raise TypeError
        return SubmissionId(local)
    except (AttributeError, TypeError, ValueError):
        raise SubmissionRequestError() from None


def _operation_key(value: object) -> FeeOperationKey:
    try:
        if type(value) is not FeeOperationKey:
            raise TypeError
        local = value.value
        if type(local) is not str or len(local) > 64:
            raise TypeError
        return FeeOperationKey(local)
    except (AttributeError, TypeError, ValueError):
        raise SubmissionRequestError() from None


def _utf8_length_bounded(value: str, maximum: int) -> int:
    total = 0
    for character in value:
        codepoint = ord(character)
        if codepoint <= 0x7F:
            width = 1
        elif codepoint <= 0x7FF:
            width = 2
        elif 0xD800 <= codepoint <= 0xDFFF:
            raise SubmissionRequestError()
        elif codepoint <= 0xFFFF:
            width = 3
        else:
            width = 4
        if width > maximum - total:
            raise SubmissionResourceError._limit()
        total += width
    return total


def _challenge(value: object, limits: SubmissionResourceLimits) -> ChallengeKey:
    try:
        if type(value) is not ChallengeKey:
            raise TypeError
        challenge_id = value.challenge_id
        version = value.version
        if type(challenge_id) is not str or type(version) is not str:
            raise TypeError
        _utf8_length_bounded(challenge_id, limits.max_challenge_id_bytes)
        if len(version) > 64:
            raise TypeError
        return ChallengeKey(challenge_id, version)
    except SubmissionResourceError:
        raise
    except (AttributeError, TypeError, ValueError, SubmissionRequestError):
        raise SubmissionRequestError() from None


def _copy_challenge(value: ChallengeKey) -> ChallengeKey:
    return ChallengeKey(value.challenge_id, value.version)


def _copy_seed_pin(value: SeedPin) -> SeedPin:
    return SeedPin(
        challenge_key=_copy_challenge(value.challenge_key),
        generator_version=value.generator_version,
        generator_digest=value.generator_digest,
        scoring_version=value.scoring_version,
        scoring_digest=value.scoring_digest,
        evaluation_binding=EvaluationBinding(value.evaluation_binding._copy_bytes()),
    )


def _copy_environment(value: ExecutionEnvironmentPin) -> ExecutionEnvironmentPin:
    return ExecutionEnvironmentPin(value.backend_profile_id, value.container_digest)


def _copy_handle(value: ExecutionAttemptHandle) -> ExecutionAttemptHandle:
    return ExecutionAttemptHandle(
        submission_id=SubmissionId(value.submission_id.value),
        attempt_number=value.attempt_number,
        admission_kind=value.admission_kind,
        seed_pin=_copy_seed_pin(value.seed_pin),
        environment_pin=_copy_environment(value.environment_pin),
    )


def _handle(value: object) -> ExecutionAttemptHandle:
    try:
        return _owned_execution_handle(value)
    except (
        AttributeError,
        TypeError,
        ValueError,
        SubmissionIntegrationError,
        SubmissionRequestError,
    ):
        raise SubmissionRequestError() from None


def _copy_fee_event(value: FeeEvent) -> FeeEvent:
    linked = value.charge_operation_key
    return FeeEvent(
        sequence=value.sequence,
        operation_key=FeeOperationKey(value.operation_key.value),
        policy_key=FeePolicyKey(value.policy_key.value),
        kind=value.kind,
        operation_context=value.operation_context,
        admission_kind=value.admission_kind,
        source_attempt_number=value.source_attempt_number,
        amount_minor=value.amount_minor,
        charge_operation_key=(
            None if linked is None else FeeOperationKey(linked.value)
        ),
    )


def _status(
    record: _SubmissionRecord,
    *,
    state: SubmissionState | None = None,
) -> SubmissionStatusView:
    return SubmissionStatusView(
        submission_id=SubmissionId(record.submission_id.value),
        state=record.state if state is None else state,
    )


def _open_key(
    requester: RequesterIdentity,
    challenge: ChallengeKey,
    strategy_hash_value: str,
) -> tuple[str, str, str, str]:
    return (
        requester.value,
        challenge.challenge_id,
        challenge.version,
        strategy_hash_value,
    )


class SubmissionService:
    """Bounded fixture-capable A7 service; production remains fail closed."""

    __slots__ = ("_fixture_policy", "_registry", "_store")

    def __init__(
        self,
        resource_limits: SubmissionResourceLimits,
        registry: ChallengeRegistry,
        fixture_policy: FixtureSubmissionPolicy,
        *,
        _uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        _card_store_seed: (
            tuple[CardRecordKey, RequesterAuthorizationKey, InternalResult] | None
        ) = None,
    ) -> None:
        if type(registry) is not ChallengeRegistry:
            raise SubmissionRequestError()
        self._fixture_policy = _owned_fixture_policy(fixture_policy)
        self._registry = registry
        try:
            self._store = _SubmissionStore(
                resource_limits,
                uuid_factory=_uuid_factory,
                card_store_seed=_card_store_seed,
            )
        except TypeError:
            raise SubmissionRequestError() from None

    def __repr__(self) -> str:
        return "<SubmissionService>"

    def submit(
        self,
        requester_identity: RequesterIdentity,
        challenge_key: ChallengeKey,
        strategy: object,
    ) -> SubmissionId:
        self._store.acquire_build_permit()
        try:
            return self._submit_with_build_permit(
                requester_identity,
                challenge_key,
                strategy,
            )
        finally:
            self._store.release_build_permit()

    def _submit_with_build_permit(
        self,
        requester_identity: RequesterIdentity,
        challenge_key: ChallengeKey,
        strategy: object,
    ) -> SubmissionId:
        requester = _requester(requester_identity)
        challenge = _challenge(challenge_key, self._store.limits)
        identity = _validate_and_hash_strategy(
            strategy,
            self._store.limits,
            challenge_key=challenge,
        )

        accepted = (
            identity.validation is not None
            and identity.validation.ok
            and identity.a7_error_code is None
            and identity.strategy_hash is not None
            and identity.strategy is not None
        )
        if not accepted:
            with self._store.guard:
                self._store.ensure_record_capacity_locked()
                minted = self._store.mint_locked()
                stored_id = SubmissionId(minted.value)
                returned_id = SubmissionId(minted.value)
                record = _SubmissionRecord(
                    submission_id=stored_id,
                    requester_identity=RequesterIdentity(requester.value),
                    challenge_key=_copy_challenge(challenge),
                    state=SubmissionState.REJECTED,
                )
                self._store.insert_rejected_locked(record)
                return returned_id

        strategy_hash = identity.strategy_hash
        owned_strategy = identity.strategy
        key = _open_key(requester, challenge, strategy_hash.value)
        with self._store.guard:
            duplicate = self._store.open_duplicate_locked(key)
            if duplicate is not None:
                return SubmissionId(duplicate.submission_id.value)

            self._store.ensure_record_capacity_locked()
            self._store.ensure_accepted_capacity_locked(
                identity.value_nodes, identity.identity_bytes
            )
            minted = self._store.mint_locked()
            _evaluation_binding(minted, strategy_hash, challenge)
            stored_id = SubmissionId(minted.value)
            returned_id = SubmissionId(minted.value)
            record = _SubmissionRecord(
                submission_id=stored_id,
                requester_identity=RequesterIdentity(requester.value),
                challenge_key=_copy_challenge(challenge),
                state=SubmissionState.RECEIVED,
                strategy=owned_strategy,
                strategy_hash=type(strategy_hash)(strategy_hash.value),
            )
            self._store.insert_accepted_locked(
                record,
                open_key=key,
                value_nodes=identity.value_nodes,
                identity_bytes=identity.identity_bytes,
            )
            return returned_id

    def mark_validated(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> SubmissionStatusView:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            if record.state is not SubmissionState.RECEIVED:
                raise SubmissionStateError()
            if (
                type(record.strategy) is not dict
                or type(record.strategy_hash) is not StrategyHash
            ):
                raise SubmissionStoreError()
            status = _status(record, state=SubmissionState.VALIDATED)
            record.state = SubmissionState.VALIDATED
            return status

    def admit_fixture(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> SubmissionStatusView:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            self._require_validated_identity_locked(record)
            challenge = record.challenge_key
            try:
                eligibility = self._registry.assess_live_eligibility(
                    challenge.challenge_id,
                    challenge.version,
                    fixture_mode=True,
                )
                if type(eligibility) is not LiveEligibility:
                    raise TypeError
                fixture_eligible = eligibility.eligible
            except Exception:  # noqa: BLE001 - the trusted A3 seam fails closed
                raise SubmissionIntegrationError() from None
            if fixture_eligible is not True:
                error = SubmissionAdmissionError._not_fixture_eligible()
                self._reject_admission_locked(record)
                raise error
            backbone = record.strategy["backbone"]  # type: ignore[index]
            try:
                allowed = self._registry.is_backbone_allowed(
                    challenge.challenge_id,
                    challenge.version,
                    backbone,  # type: ignore[arg-type]
                )
            except Exception:  # noqa: BLE001 - the trusted A3 seam fails closed
                raise SubmissionIntegrationError() from None
            if allowed is not True:
                error = SubmissionAdmissionError._backbone_not_allowed()
                self._reject_admission_locked(record)
                raise error

            if record.strategy_hash is None:
                raise SubmissionStoreError()
            policy = self._fixture_policy
            evaluation_binding = _evaluation_binding(
                record.submission_id,
                record.strategy_hash,
                record.challenge_key,
            )
            seed_pin = SeedPin(
                challenge_key=_copy_challenge(challenge),
                generator_version=policy.generator_version,
                generator_digest=policy.generator_digest,
                scoring_version=policy.scoring_version,
                scoring_digest=policy.scoring_digest,
                evaluation_binding=evaluation_binding,
            )
            environment = _copy_environment(policy.environment_pin)
            queued = AttemptEvent(1, AttemptEventKind.QUEUED)
            attempts = [queued]
            status = _status(record, state=SubmissionState.QUEUED)

            record.admission_kind = AdmissionKind.FIXTURE
            record.seed_pin = seed_pin
            record.environment_pin = environment
            record.attempt_number = 1
            record.attempt_events = attempts
            record.terminal_infra_disposition = FeeEventKind.REFUND
            record.state = SubmissionState.QUEUED
            return status

    def admit_production(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> SubmissionStatusView:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            self._require_validated_identity_locked(record)
            challenge = record.challenge_key
            try:
                effectively_live = self._registry.is_effectively_live(
                    challenge.challenge_id, challenge.version
                )
            except Exception:  # noqa: BLE001 - the trusted A3 seam fails closed
                raise SubmissionIntegrationError() from None
            if effectively_live is not True:
                error = SubmissionAdmissionError._not_live()
                self._reject_admission_locked(record)
                raise error
            backbone = record.strategy["backbone"]  # type: ignore[index]
            try:
                backbone_allowed = self._registry.is_backbone_allowed(
                    challenge.challenge_id,
                    challenge.version,
                    backbone,  # type: ignore[arg-type]
                )
            except Exception:  # noqa: BLE001 - the trusted A3 seam fails closed
                raise SubmissionIntegrationError() from None
            if backbone_allowed is not True:
                error = SubmissionAdmissionError._backbone_not_allowed()
                self._reject_admission_locked(record)
                raise error
            raise SubmissionIntegrationError()

    def start_fixture_attempt(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
        charge_operation_key: FeeOperationKey,
        refund_operation_key: FeeOperationKey,
    ) -> InitialRunStartResult:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        charge_key = _operation_key(charge_operation_key)
        refund_key = _operation_key(refund_operation_key)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            existing = self._store.fee_event_locked(record, charge_key.value)
            if existing is not None:
                self._check_initial_start_replay_locked(
                    record,
                    existing,
                    charge_key,
                    refund_key,
                    AdmissionKind.FIXTURE,
                )
                return InitialRunStartResult(
                    disposition=StartDisposition.ALREADY_STARTED,
                    fee_event=_copy_fee_event(existing),
                    state=record.state,
                )

            reserved_refund_key = record.terminal_infra_operation_key
            if (
                reserved_refund_key is not None
                and type(reserved_refund_key) is not FeeOperationKey
            ):
                raise SubmissionStoreError()
            if (
                reserved_refund_key is not None
                and reserved_refund_key.value in (charge_key.value, refund_key.value)
            ) or self._store.fee_event_locked(record, refund_key.value) is not None:
                raise SubmissionConflictError()
            self._require_initial_queue_locked(record, AdmissionKind.FIXTURE)
            if charge_key.value == refund_key.value:
                raise SubmissionConflictError()

            terminal_infra_operation_key = FeeOperationKey(refund_key.value)
            handle = self._new_handle_locked(record)
            envelope = self._fixture_envelope_locked(record, handle)
            fee_event = FeeEvent(
                sequence=1,
                operation_key=FeeOperationKey(charge_key.value),
                policy_key=FeePolicyKey(self._fixture_policy.fee_policy_key.value),
                kind=FeeEventKind.CHARGE,
                operation_context=FeeOperationContext.INITIAL_RUN_START,
                admission_kind=AdmissionKind.FIXTURE,
                source_attempt_number=1,
                amount_minor=self._fixture_policy.amount_minor,
                charge_operation_key=None,
            )
            running = AttemptEvent(1, AttemptEventKind.RUNNING)
            new_attempts = [*record.attempt_events, running]
            new_fees = [fee_event]
            result = InitialRunStartResult(
                disposition=StartDisposition.STARTED,
                fee_event=_copy_fee_event(fee_event),
                envelope=envelope,
            )

            record.current_handle = handle
            record.terminal_infra_operation_key = terminal_infra_operation_key
            record.attempt_events = new_attempts
            record.fee_events = new_fees
            record.state = SubmissionState.RUNNING
            return result

    def start_production_attempt(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
        charge_operation_key: FeeOperationKey,
        refund_operation_key: FeeOperationKey,
    ) -> InitialRunStartResult:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        charge_key = _operation_key(charge_operation_key)
        refund_key = _operation_key(refund_operation_key)
        del charge_key, refund_key
        with self._store.guard:
            self._authorized_record_locked(requested_id, requester)
            raise SubmissionIntegrationError()

    def start_fixture_retry_attempt(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> FixtureExecutionEnvelope:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            self._require_retry_queue_locked(record, AdmissionKind.FIXTURE)
            handle = self._new_handle_locked(record)
            envelope = self._fixture_envelope_locked(record, handle)
            running = AttemptEvent(record.attempt_number, AttemptEventKind.RUNNING)
            record.attempt_events = [*record.attempt_events, running]
            record.current_handle = handle
            record.state = SubmissionState.RUNNING
            return envelope

    def start_production_retry_attempt(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> ProductionExecutionEnvelope:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            self._authorized_record_locked(requested_id, requester)
            raise SubmissionIntegrationError()

    def retry_infrastructure(
        self, execution_handle: ExecutionAttemptHandle
    ) -> SubmissionStatusView | FeeEvent:
        supplied_handle = _handle(execution_handle)
        with self._store.guard:
            record = self._record_for_handle_locked(supplied_handle)
            replay = self._terminal_refund_replay_locked(
                record,
                supplied_handle=supplied_handle,
                expected_context=FeeOperationContext.TERMINAL_INFRA,
            )
            if replay is not None:
                return _copy_fee_event(replay)
            self._require_current_handle_locked(record, supplied_handle)

            attempt = supplied_handle.attempt_number
            if attempt < self._fixture_policy.max_attempts:
                next_attempt = attempt + 1
                retry_event = AttemptEvent(attempt, AttemptEventKind.RETRYABLE_INFRA)
                queued_event = AttemptEvent(next_attempt, AttemptEventKind.QUEUED)
                status = _status(record, state=SubmissionState.QUEUED)
                record.attempt_events = [
                    *record.attempt_events,
                    retry_event,
                    queued_event,
                ]
                record.attempt_number = next_attempt
                record.current_handle = None
                record.state = SubmissionState.QUEUED
                return status

            refund = self._terminal_infra_locked(
                record,
                attempt=attempt,
                context=FeeOperationContext.TERMINAL_INFRA,
                project_refund=True,
                require_refund=True,
            )
            return refund

    def fail_strategy(
        self, execution_handle: ExecutionAttemptHandle
    ) -> SubmissionStatusView:
        supplied_handle = _handle(execution_handle)
        with self._store.guard:
            record = self._record_for_handle_locked(supplied_handle)
            self._require_current_handle_locked(record, supplied_handle)
            open_key = self._store.validate_open_owner_locked(record)
            failed = AttemptEvent(
                supplied_handle.attempt_number, AttemptEventKind.FAILED_STRATEGY
            )
            status = _status(record, state=SubmissionState.FAILED_STRATEGY)
            record.attempt_events = [*record.attempt_events, failed]
            record.current_handle = None
            record.state = SubmissionState.FAILED_STRATEGY
            self._store.close_open_locked(open_key)
            return status

    def fail_infrastructure(
        self,
        subject: SubmissionId | ExecutionAttemptHandle,
        requester_identity: RequesterIdentity | None = None,
    ) -> FeeEvent | None:
        if type(subject) is ExecutionAttemptHandle:
            if requester_identity is not None:
                raise SubmissionRequestError()
            supplied_handle = _handle(subject)
            with self._store.guard:
                record = self._record_for_handle_locked(supplied_handle)
                replay = self._terminal_refund_replay_locked(
                    record,
                    supplied_handle=supplied_handle,
                    expected_context=FeeOperationContext.TERMINAL_INFRA,
                )
                if replay is not None:
                    return _copy_fee_event(replay)
                self._require_current_handle_locked(record, supplied_handle)
                refund = self._terminal_infra_locked(
                    record,
                    attempt=supplied_handle.attempt_number,
                    context=FeeOperationContext.TERMINAL_INFRA,
                    project_refund=True,
                    require_refund=True,
                )
                return refund

        requested_id = _submission_id(subject)
        if requester_identity is None:
            raise SubmissionRequestError()
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            replay = self._terminal_refund_replay_locked(
                record,
                supplied_handle=None,
                expected_context=FeeOperationContext.TERMINAL_INFRA,
            )
            if replay is not None:
                return _copy_fee_event(replay)
            if record.state is not SubmissionState.QUEUED:
                raise SubmissionStateError()
            if type(record.attempt_number) is not int:
                raise SubmissionStoreError()
            refund = self._terminal_infra_locked(
                record,
                attempt=record.attempt_number,
                context=FeeOperationContext.TERMINAL_INFRA,
                project_refund=True,
                require_refund=record.attempt_number > 1,
            )
            return refund

    def complete_and_publish(
        self,
        execution_handle: ExecutionAttemptHandle,
        internal_result: InternalResult,
    ) -> SubmissionStatusView:
        supplied_handle = _handle(execution_handle)
        with self._store.guard:
            record = self._record_for_handle_locked(supplied_handle)
            self._require_current_handle_locked(record, supplied_handle)
            open_key = self._store.validate_open_owner_locked(record)
            integration_error = SubmissionIntegrationError()
            owned_result = _owned_internal_result(internal_result)
            if (
                owned_result is None
                or record.admission_kind is not AdmissionKind.FIXTURE
                or record.seed_pin is None
                or not _result_matches_seed_pin(owned_result, record.seed_pin)
                or owned_result.status is ScoreStatus.PACK_NOT_READY
            ):
                self._integration_failure_locked(record, supplied_handle)
                raise integration_error
            if owned_result.status not in (
                ScoreStatus.SCORED,
                ScoreStatus.MANDATORY_GATE_FAILED,
            ):
                self._integration_failure_locked(record, supplied_handle)
                raise integration_error

            scored_event = AttemptEvent(
                supplied_handle.attempt_number, AttemptEventKind.SCORED
            )
            scored_attempts = [*record.attempt_events, scored_event]
            published_status = _status(record, state=SubmissionState.PUBLISHED)
            publication_failure_plan = self._prepare_terminal_infra_locked(
                record,
                attempt=supplied_handle.attempt_number,
                context=FeeOperationContext.PUBLICATION_INFRA,
                source_state=SubmissionState.SCORED,
                source_attempt_events=scored_attempts,
                require_refund=True,
            )
            publication_store_error = SubmissionStoreError()
            record.attempt_events = scored_attempts
            record.current_handle = None
            record.state = SubmissionState.SCORED
            try:
                record_key = CardRecordKey(record.submission_id.value)
                requester_key = RequesterAuthorizationKey(
                    record.requester_identity.value
                )
                disposition = self._store.card_store.write_internal(
                    record_key, requester_key, owned_result
                )
            except Exception:  # noqa: BLE001 - the trusted A6 seam fails closed
                self._commit_terminal_infra_locked(
                    record,
                    open_key,
                    publication_failure_plan,
                )
                raise integration_error from None

            if (
                disposition is not CardWriteDisposition.INSERTED
                and disposition is not CardWriteDisposition.ALREADY_PRESENT
            ):
                self._commit_terminal_infra_locked(
                    record,
                    open_key,
                    publication_failure_plan,
                )
                raise publication_store_error
            record.state = SubmissionState.PUBLISHED
            self._store.close_open_locked(open_key)
            return published_status

    def cancel(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> SubmissionStatusView:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            if record.state not in (
                SubmissionState.RECEIVED,
                SubmissionState.VALIDATED,
                SubmissionState.QUEUED,
            ):
                raise SubmissionStateError()
            open_key = self._store.validate_open_owner_locked(record)
            attempts = record.attempt_events
            if record.state is SubmissionState.QUEUED:
                if type(record.attempt_number) is not int:
                    raise SubmissionStoreError()
                cancelled = AttemptEvent(
                    record.attempt_number, AttemptEventKind.CANCELLED
                )
                attempts = [*attempts, cancelled]
            status = _status(record, state=SubmissionState.CANCELLED)
            record.attempt_events = attempts
            record.current_handle = None
            record.state = SubmissionState.CANCELLED
            self._store.close_open_locked(open_key)
            return status

    def get_status(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> SubmissionStatusView:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            return _status(record)

    def read_published(
        self,
        submission_id: SubmissionId,
        requester_identity: RequesterIdentity,
    ) -> EvaluationCard:
        requested_id = _submission_id(submission_id)
        requester = _requester(requester_identity)
        with self._store.guard:
            record = self._authorized_record_locked(requested_id, requester)
            if record.state is not SubmissionState.PUBLISHED:
                raise SubmissionStateError()
            return self._store.card_store.read_budgeted(
                CardRecordKey(record.submission_id.value),
                RequesterAuthorizationKey(record.requester_identity.value),
            )

    def _authorized_record_locked(
        self,
        submission_id: SubmissionId,
        requester: RequesterIdentity,
    ) -> _SubmissionRecord:
        record = self._store.records.get(submission_id.value)
        if record is None:
            raise SubmissionNotFoundError()
        if (
            type(record) is not _SubmissionRecord
            or type(record.submission_id) is not SubmissionId
            or record.submission_id != submission_id
            or type(record.requester_identity) is not RequesterIdentity
            or type(record.state) is not SubmissionState
        ):
            raise SubmissionStoreError()
        if record.requester_identity.value != requester.value:
            raise SubmissionAuthorizationError()
        return record

    def _record_for_handle_locked(
        self, handle: ExecutionAttemptHandle
    ) -> _SubmissionRecord:
        record = self._store.records.get(handle.submission_id.value)
        if record is None:
            raise SubmissionNotFoundError()
        if (
            type(record) is not _SubmissionRecord
            or type(record.submission_id) is not SubmissionId
            or record.submission_id != handle.submission_id
            or type(record.requester_identity) is not RequesterIdentity
            or type(record.state) is not SubmissionState
        ):
            raise SubmissionStoreError()
        return record

    def _require_validated_identity_locked(self, record: _SubmissionRecord) -> None:
        if record.state is not SubmissionState.VALIDATED:
            raise SubmissionStateError()
        if (
            type(record.strategy) is not dict
            or type(record.strategy_hash) is not StrategyHash
        ):
            raise SubmissionStoreError()

    def _reject_admission_locked(self, record: _SubmissionRecord) -> None:
        open_key = self._store.validate_open_owner_locked(record)
        record.state = SubmissionState.REJECTED
        self._store.close_open_locked(open_key)

    def _require_initial_queue_locked(
        self, record: _SubmissionRecord, kind: AdmissionKind
    ) -> None:
        if (
            record.state is not SubmissionState.QUEUED
            or record.admission_kind is not kind
            or type(record.attempt_number) is not int
            or record.attempt_number != 1
            or record.current_handle is not None
            or type(record.seed_pin) is not SeedPin
            or type(record.environment_pin) is not ExecutionEnvironmentPin
            or record.terminal_infra_disposition is not FeeEventKind.REFUND
            or record.terminal_infra_operation_key is not None
            or record.fee_events
        ):
            raise SubmissionStateError()

    def _require_retry_queue_locked(
        self, record: _SubmissionRecord, kind: AdmissionKind
    ) -> None:
        if (
            record.state is not SubmissionState.QUEUED
            or record.admission_kind is not kind
            or type(record.attempt_number) is not int
            or record.attempt_number <= 1
            or record.current_handle is not None
            or record.seed_pin is None
            or record.environment_pin is None
            or record.terminal_infra_disposition is not FeeEventKind.REFUND
            or type(record.terminal_infra_operation_key) is not FeeOperationKey
        ):
            raise SubmissionStateError()
        if self._charge_locked(record) is None:
            raise SubmissionStoreError()

    def _new_handle_locked(self, record: _SubmissionRecord) -> ExecutionAttemptHandle:
        if (
            type(record.attempt_number) is not int
            or type(record.admission_kind) is not AdmissionKind
            or type(record.seed_pin) is not SeedPin
            or type(record.environment_pin) is not ExecutionEnvironmentPin
        ):
            raise SubmissionStoreError()
        return ExecutionAttemptHandle(
            submission_id=SubmissionId(record.submission_id.value),
            attempt_number=record.attempt_number,
            admission_kind=record.admission_kind,
            seed_pin=_copy_seed_pin(record.seed_pin),
            environment_pin=_copy_environment(record.environment_pin),
        )

    def _fixture_envelope_locked(
        self,
        record: _SubmissionRecord,
        handle: ExecutionAttemptHandle,
    ) -> FixtureExecutionEnvelope:
        if record.strategy is None or record.strategy_hash is None:
            raise SubmissionStoreError()
        return FixtureExecutionEnvelope(
            handle=_copy_handle(handle),
            strategy=_copy_strategy_tree(record.strategy),
            strategy_hash=type(record.strategy_hash)(record.strategy_hash.value),
            challenge_key=_copy_challenge(record.challenge_key),
        )

    def _check_initial_start_replay_locked(
        self,
        record: _SubmissionRecord,
        event: FeeEvent,
        charge_key: FeeOperationKey,
        refund_key: FeeOperationKey,
        kind: AdmissionKind,
    ) -> None:
        policy = self._fixture_policy
        try:
            event_matches = (
                bool(record.fee_events)
                and record.fee_events[0] is event
                and type(event.sequence) is int
                and event.sequence == 1
                and event.operation_key.value == charge_key.value
                and type(event.policy_key) is FeePolicyKey
                and event.policy_key.value == policy.fee_policy_key.value
                and event.kind is FeeEventKind.CHARGE
                and event.operation_context is FeeOperationContext.INITIAL_RUN_START
                and event.admission_kind is kind
                and type(event.source_attempt_number) is int
                and event.source_attempt_number == 1
                and type(event.amount_minor) is int
                and event.amount_minor == policy.amount_minor
                and event.charge_operation_key is None
            )
        except SubmissionConflictError:
            raise
        except (
            AttributeError,
            TypeError,
            ValueError,
            SubmissionIntegrationError,
            SubmissionRequestError,
        ):
            raise SubmissionConflictError() from None
        if (
            not event_matches
            or not self._fixture_pins_match_policy_locked(record)
            or type(record.terminal_infra_operation_key) is not FeeOperationKey
            or record.terminal_infra_operation_key != refund_key
            or record.admission_kind is not kind
            or record.terminal_infra_disposition is not FeeEventKind.REFUND
        ):
            raise SubmissionConflictError()

    def _require_current_handle_locked(
        self,
        record: _SubmissionRecord,
        supplied_handle: ExecutionAttemptHandle,
    ) -> None:
        if (
            record.state is not SubmissionState.RUNNING
            or record.current_handle is None
            or record.current_handle != supplied_handle
        ):
            raise SubmissionStateError()

    def _charge_locked(self, record: _SubmissionRecord) -> FeeEvent | None:
        if type(record.fee_events) is not list:
            raise SubmissionStoreError()
        if not record.fee_events:
            return None
        charge = record.fee_events[0]
        policy = self._fixture_policy
        if (
            type(charge) is not FeeEvent
            or type(charge.sequence) is not int
            or charge.sequence != 1
            or type(charge.operation_key) is not FeeOperationKey
            or type(charge.policy_key) is not FeePolicyKey
            or charge.policy_key.value != policy.fee_policy_key.value
            or charge.kind is not FeeEventKind.CHARGE
            or charge.operation_context is not FeeOperationContext.INITIAL_RUN_START
            or charge.admission_kind is not record.admission_kind
            or type(charge.source_attempt_number) is not int
            or charge.source_attempt_number != 1
            or type(charge.amount_minor) is not int
            or charge.amount_minor != policy.amount_minor
            or charge.charge_operation_key is not None
            or type(record.terminal_infra_operation_key) is not FeeOperationKey
            or charge.operation_key == record.terminal_infra_operation_key
        ):
            raise SubmissionStoreError()
        return charge

    def _remaining_balance_locked(self, record: _SubmissionRecord) -> int:
        charge = self._charge_locked(record)
        if charge is None:
            return 0
        adjusted = 0
        seen_operation_keys = {charge.operation_key.value}
        for sequence, event in enumerate(record.fee_events[1:], start=2):
            if (
                type(event) is not FeeEvent
                or type(event.sequence) is not int
                or event.sequence != sequence
                or type(event.kind) is not FeeEventKind
                or type(event.operation_context) is not FeeOperationContext
                or event.kind not in (FeeEventKind.REFUND, FeeEventKind.RETRY_CREDIT)
                or (
                    event.kind is FeeEventKind.REFUND
                    and event.operation_context
                    not in (
                        FeeOperationContext.TERMINAL_INFRA,
                        FeeOperationContext.PUBLICATION_INFRA,
                    )
                )
                or (
                    event.kind is FeeEventKind.RETRY_CREDIT
                    and event.operation_context is not FeeOperationContext.RETRY
                )
                or type(event.operation_key) is not FeeOperationKey
                or event.operation_key.value in seen_operation_keys
                or type(event.source_attempt_number) is not int
                or event.source_attempt_number <= 0
                or type(event.amount_minor) is not int
                or event.amount_minor < 0
                or type(event.policy_key) is not FeePolicyKey
                or event.policy_key != charge.policy_key
                or event.admission_kind is not charge.admission_kind
                or type(event.charge_operation_key) is not FeeOperationKey
                or event.charge_operation_key != charge.operation_key
                or event.amount_minor > _U64_MAX - adjusted
            ):
                raise SubmissionStoreError()
            seen_operation_keys.add(event.operation_key.value)
            adjusted += event.amount_minor
        if adjusted > charge.amount_minor:
            raise SubmissionStoreError()
        return charge.amount_minor - adjusted

    def _make_refund_locked(
        self,
        record: _SubmissionRecord,
        *,
        attempt: int,
        context: FeeOperationContext,
    ) -> FeeEvent:
        charge = self._charge_locked(record)
        refund_key = record.terminal_infra_operation_key
        if charge is None or type(refund_key) is not FeeOperationKey:
            raise SubmissionStoreError()
        if record.terminal_infra_disposition is not FeeEventKind.REFUND:
            raise SubmissionStoreError()
        if self._store.fee_event_locked(record, refund_key.value) is not None:
            raise SubmissionConflictError()
        return FeeEvent(
            sequence=len(record.fee_events) + 1,
            operation_key=FeeOperationKey(refund_key.value),
            policy_key=FeePolicyKey(charge.policy_key.value),
            kind=FeeEventKind.REFUND,
            operation_context=context,
            admission_kind=charge.admission_kind,
            source_attempt_number=attempt,
            amount_minor=self._remaining_balance_locked(record),
            charge_operation_key=FeeOperationKey(charge.operation_key.value),
        )

    def _terminal_infra_locked(
        self,
        record: _SubmissionRecord,
        *,
        attempt: int,
        context: FeeOperationContext,
        open_key: tuple[str, str, str, str] | None = None,
        project_refund: bool = False,
        require_refund: bool = False,
    ) -> FeeEvent | None:
        if open_key is None:
            open_key = self._store.validate_open_owner_locked(record)
        plan = self._prepare_terminal_infra_locked(
            record,
            attempt=attempt,
            context=context,
            project_refund=project_refund,
            require_refund=require_refund,
        )
        self._commit_terminal_infra_locked(record, open_key, plan)
        return plan[2]

    def _prepare_terminal_infra_locked(
        self,
        record: _SubmissionRecord,
        *,
        attempt: int,
        context: FeeOperationContext,
        source_state: SubmissionState | None = None,
        source_attempt_events: list[AttemptEvent] | None = None,
        project_refund: bool = False,
        require_refund: bool = False,
    ) -> tuple[list[AttemptEvent], list[FeeEvent], FeeEvent | None]:
        effective_state = record.state if source_state is None else source_state
        if (
            type(record.attempt_number) is not int
            or record.attempt_number != attempt
            or (
                context is FeeOperationContext.TERMINAL_INFRA
                and effective_state
                not in (SubmissionState.QUEUED, SubmissionState.RUNNING)
            )
            or (
                context is FeeOperationContext.PUBLICATION_INFRA
                and effective_state is not SubmissionState.SCORED
            )
        ):
            raise SubmissionStoreError()
        failed = AttemptEvent(attempt, AttemptEventKind.FAILED_INFRA)
        attempts = (
            record.attempt_events
            if source_attempt_events is None
            else source_attempt_events
        )
        attempt_events = [*attempts, failed]
        charge = self._charge_locked(record)
        refund = None
        fee_events = record.fee_events
        if charge is not None:
            refund = self._make_refund_locked(record, attempt=attempt, context=context)
            fee_events = [*record.fee_events, refund]
        if require_refund and refund is None:
            raise SubmissionStoreError()
        returned_refund = (
            _copy_fee_event(refund) if project_refund and refund is not None else refund
        )
        return attempt_events, fee_events, returned_refund

    def _commit_terminal_infra_locked(
        self,
        record: _SubmissionRecord,
        open_key: tuple[str, str, str, str],
        plan: tuple[list[AttemptEvent], list[FeeEvent], FeeEvent | None],
    ) -> None:
        attempt_events, fee_events, _ = plan
        record.attempt_events = attempt_events
        record.fee_events = fee_events
        record.current_handle = None
        record.state = SubmissionState.FAILED_INFRA
        self._store.close_open_locked(open_key)

    def _historical_handle_locked(
        self, record: _SubmissionRecord, attempt: int
    ) -> ExecutionAttemptHandle:
        if (
            record.admission_kind is None
            or record.seed_pin is None
            or record.environment_pin is None
        ):
            raise SubmissionStoreError()
        return ExecutionAttemptHandle(
            submission_id=SubmissionId(record.submission_id.value),
            attempt_number=attempt,
            admission_kind=record.admission_kind,
            seed_pin=_copy_seed_pin(record.seed_pin),
            environment_pin=_copy_environment(record.environment_pin),
        )

    def _terminal_refund_replay_locked(
        self,
        record: _SubmissionRecord,
        *,
        supplied_handle: ExecutionAttemptHandle | None,
        expected_context: FeeOperationContext,
    ) -> FeeEvent | None:
        refund_key = record.terminal_infra_operation_key
        if refund_key is None:
            return None
        if type(refund_key) is not FeeOperationKey:
            raise SubmissionStoreError()
        event = self._store.fee_event_locked(record, refund_key.value)
        if event is None:
            if record.state is SubmissionState.FAILED_INFRA:
                raise SubmissionConflictError()
            return None
        charge = self._charge_locked(record)
        if charge is None:
            raise SubmissionConflictError()
        remaining_balance = self._remaining_balance_locked(record)
        try:
            events = record.attempt_events
            if type(events) is not list:
                raise SubmissionConflictError()
            failed_positions = [
                index
                for index, attempt_event in enumerate(events)
                if (
                    type(attempt_event) is AttemptEvent
                    and attempt_event.attempt_number == event.source_attempt_number
                    and attempt_event.kind is AttemptEventKind.FAILED_INFRA
                )
            ]
            if len(failed_positions) != 1:
                raise SubmissionConflictError()
            failed_position = failed_positions[0]
            if failed_position != len(events) - 1 or failed_position == 0:
                raise SubmissionConflictError()
            predecessor = events[failed_position - 1]
            if predecessor.attempt_number != event.source_attempt_number:
                raise SubmissionConflictError()
            if expected_context is FeeOperationContext.TERMINAL_INFRA:
                if (
                    predecessor.kind is not AttemptEventKind.QUEUED
                    and predecessor.kind is not AttemptEventKind.RUNNING
                ):
                    raise SubmissionConflictError()
                operation_required_handle = predecessor.kind is AttemptEventKind.RUNNING
            else:
                if predecessor.kind is not AttemptEventKind.SCORED:
                    raise SubmissionConflictError()
                operation_required_handle = True
        except SubmissionConflictError:
            raise
        except (AttributeError, TypeError, ValueError):
            raise SubmissionConflictError() from None
        if (
            record.state is not SubmissionState.FAILED_INFRA
            or record.current_handle is not None
            or record.attempt_number != event.source_attempt_number
            or record.terminal_infra_disposition is not FeeEventKind.REFUND
            or record.admission_kind is not AdmissionKind.FIXTURE
            or not self._fixture_pins_match_policy_locked(record)
            or len(record.fee_events) < 2
            or record.fee_events[-1] is not event
            or event.sequence != len(record.fee_events)
            or type(event.operation_key) is not FeeOperationKey
            or event.operation_key != refund_key
            or type(event.policy_key) is not FeePolicyKey
            or event.policy_key != charge.policy_key
            or event.kind is not FeeEventKind.REFUND
            or event.operation_context is not expected_context
            or event.admission_kind is not charge.admission_kind
            or remaining_balance != 0
            or type(event.charge_operation_key) is not FeeOperationKey
            or event.charge_operation_key != charge.operation_key
        ):
            raise SubmissionConflictError()
        if operation_required_handle != (supplied_handle is not None):
            raise SubmissionConflictError()
        if operation_required_handle:
            if supplied_handle is None:
                raise SubmissionConflictError()
            expected = self._historical_handle_locked(
                record, event.source_attempt_number
            )
            if expected != supplied_handle:
                raise SubmissionConflictError()
        return event

    def _fixture_pins_match_policy_locked(self, record: _SubmissionRecord) -> bool:
        try:
            if record.strategy_hash is None or record.seed_pin is None:
                return False
            expected_binding = _evaluation_binding(
                record.submission_id,
                record.strategy_hash,
                record.challenge_key,
            )
            seed = record.seed_pin
            policy = self._fixture_policy
            return (
                seed.challenge_key == record.challenge_key
                and seed.generator_version == policy.generator_version
                and seed.generator_digest == policy.generator_digest
                and seed.scoring_version == policy.scoring_version
                and seed.scoring_digest == policy.scoring_digest
                and seed.evaluation_binding == expected_binding
                and record.environment_pin == policy.environment_pin
            )
        except (
            AttributeError,
            TypeError,
            ValueError,
            SubmissionIntegrationError,
            SubmissionRequestError,
        ):
            return False

    def _integration_failure_locked(
        self,
        record: _SubmissionRecord,
        handle: ExecutionAttemptHandle,
    ) -> None:
        if handle.attempt_number < self._fixture_policy.max_attempts:
            next_attempt = handle.attempt_number + 1
            record.attempt_events = [
                *record.attempt_events,
                AttemptEvent(
                    handle.attempt_number,
                    AttemptEventKind.RETRYABLE_INFRA,
                ),
                AttemptEvent(next_attempt, AttemptEventKind.QUEUED),
            ]
            record.attempt_number = next_attempt
            record.current_handle = None
            record.state = SubmissionState.QUEUED
            return
        self._terminal_infra_locked(
            record,
            attempt=handle.attempt_number,
            context=FeeOperationContext.TERMINAL_INFRA,
            require_refund=True,
        )


__all__ = ("SubmissionService",)
