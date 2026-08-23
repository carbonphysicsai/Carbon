"""Private bounded, process-local storage for A7 submissions.

The store deliberately exposes no persistence, enumeration, mutation, or
serialization API.  :mod:`carbon.fees.service` owns the sole guard and uses
the small ``*_locked`` primitive set below to make lifecycle transactions.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from carbon.cards import (
    CardRecordKey,
    CardStore,
    CardWriteDisposition,
    RequesterAuthorizationKey,
)
from carbon.registry import ChallengeKey
from carbon.scoring.model import InternalResult
from carbon.seeding import SeedPin

from .model import (
    AdmissionKind,
    AttemptEvent,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FeeEvent,
    FeeEventKind,
    FeeOperationKey,
    RequesterIdentity,
    StrategyHash,
    SubmissionConflictError,
    SubmissionId,
    SubmissionResourceError,
    SubmissionResourceLimits,
    SubmissionState,
    SubmissionStoreError,
    _owned_resource_limits,
)

_OpenKey = tuple[str, str, str, str]
_OPEN_STATES = frozenset(
    {
        SubmissionState.RECEIVED,
        SubmissionState.VALIDATED,
        SubmissionState.QUEUED,
        SubmissionState.RUNNING,
        SubmissionState.SCORED,
    }
)


@dataclass(slots=True, repr=False)
class _SubmissionRecord:
    """The ratified minimum private retained record.

    Rejected records intentionally leave every accepted-identity field empty.
    Resource counters live on ``_SubmissionStore`` rather than on records.
    """

    record_schema_version: str = field(default="1.0", init=False)
    submission_id: SubmissionId
    requester_identity: RequesterIdentity
    challenge_key: ChallengeKey
    state: SubmissionState
    strategy: dict[str, object] | None = None
    strategy_hash: StrategyHash | None = None
    admission_kind: AdmissionKind | None = None
    seed_pin: SeedPin | None = None
    environment_pin: ExecutionEnvironmentPin | None = None
    attempt_number: int | None = None
    current_handle: ExecutionAttemptHandle | None = None
    terminal_infra_disposition: FeeEventKind | None = None
    terminal_infra_operation_key: FeeOperationKey | None = None
    attempt_events: list[AttemptEvent] = field(default_factory=list)
    fee_events: list[FeeEvent] = field(default_factory=list)

    def __repr__(self) -> str:
        return "<_SubmissionRecord>"


class _SubmissionStore:
    """Guard, capacity accounting, indexes, and the exclusive A6 store."""

    __slots__ = (
        "build_permits",
        "card_store",
        "guard",
        "limits",
        "open_index",
        "records",
        "retained_strategy_identity_bytes",
        "retained_value_nodes",
        "uuid_factory",
    )

    def __init__(
        self,
        limits: SubmissionResourceLimits,
        *,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        card_store_seed: (
            tuple[CardRecordKey, RequesterAuthorizationKey, InternalResult] | None
        ) = None,
    ) -> None:
        self.limits = _owned_resource_limits(limits)
        if not callable(uuid_factory):
            raise TypeError("UUID factory must be callable.")
        self.guard = threading.Lock()
        self.build_permits = threading.BoundedSemaphore(
            self.limits.max_concurrent_identity_builds
        )
        self.records: dict[str, _SubmissionRecord] = {}
        self.open_index: dict[_OpenKey, str] = {}
        self.retained_value_nodes = 0
        self.retained_strategy_identity_bytes = 0
        self.card_store = CardStore()
        if card_store_seed is not None:
            try:
                if type(card_store_seed) is not tuple or len(card_store_seed) != 3:
                    raise TypeError
                disposition = self.card_store.write_internal(*card_store_seed)
                if disposition is not CardWriteDisposition.INSERTED:
                    raise TypeError
            except Exception:  # noqa: BLE001 - private test seed fails closed
                raise TypeError("Card store seed is invalid.") from None
        self.uuid_factory = uuid_factory

    def __repr__(self) -> str:
        return "<_SubmissionStore>"

    def acquire_build_permit(self) -> None:
        if not self.build_permits.acquire(blocking=False):
            raise SubmissionResourceError._capacity()

    def release_build_permit(self) -> None:
        self.build_permits.release()

    def record_locked(self, submission_id_value: str) -> _SubmissionRecord:
        return self.records[submission_id_value]

    def open_duplicate_locked(self, key: _OpenKey) -> _SubmissionRecord | None:
        submission_value = self.open_index.get(key)
        if submission_value is None:
            return None
        record = self.records.get(submission_value)
        if (
            type(record) is not _SubmissionRecord
            or type(record.submission_id) is not SubmissionId
            or record.submission_id.value != submission_value
            or type(record.requester_identity) is not RequesterIdentity
            or type(record.challenge_key) is not ChallengeKey
            or type(record.strategy_hash) is not StrategyHash
            or type(record.state) is not SubmissionState
            or record.state not in _OPEN_STATES
            or self._open_key_for_record_locked(record) != key
        ):
            raise SubmissionStoreError()
        return record

    def fee_event_locked(
        self, record: _SubmissionRecord, operation_key_value: str
    ) -> FeeEvent | None:
        if type(record.fee_events) is not list:
            raise SubmissionStoreError()
        match = None
        for event in record.fee_events:
            if (
                type(event) is not FeeEvent
                or type(event.operation_key) is not FeeOperationKey
            ):
                raise SubmissionStoreError()
            if event.operation_key.value == operation_key_value:
                if match is not None:
                    raise SubmissionStoreError()
                match = event
        return match

    def ensure_record_capacity_locked(self) -> None:
        if len(self.records) >= self.limits.max_retained_submission_records:
            raise SubmissionResourceError._capacity()

    def ensure_accepted_capacity_locked(
        self, value_nodes: int, identity_bytes: int
    ) -> None:
        if (
            value_nodes
            > self.limits.max_retained_value_nodes - self.retained_value_nodes
        ):
            raise SubmissionResourceError._capacity()
        if identity_bytes > (
            self.limits.max_retained_strategy_identity_bytes
            - self.retained_strategy_identity_bytes
        ):
            raise SubmissionResourceError._capacity()

    def mint_locked(self) -> SubmissionId:
        try:
            candidate = self.uuid_factory()
        except Exception:  # noqa: BLE001 - private injected factories fail closed
            raise SubmissionStoreError() from None
        if type(candidate) is not uuid.UUID:
            raise SubmissionConflictError()
        try:
            submission_id = SubmissionId(str(candidate))
        except (TypeError, ValueError):
            raise SubmissionConflictError() from None
        if submission_id.value in self.records:
            raise SubmissionConflictError()
        return submission_id

    def insert_rejected_locked(self, record: _SubmissionRecord) -> None:
        self.ensure_record_capacity_locked()
        key = record.submission_id.value
        if key in self.records:
            raise SubmissionConflictError()
        try:
            self.records[key] = record
        except BaseException:
            dict.pop(self.records, key, None)
            raise

    def insert_accepted_locked(
        self,
        record: _SubmissionRecord,
        *,
        open_key: _OpenKey,
        value_nodes: int,
        identity_bytes: int,
    ) -> None:
        self.ensure_record_capacity_locked()
        self.ensure_accepted_capacity_locked(value_nodes, identity_bytes)
        if self._open_key_for_record_locked(record) != open_key:
            raise SubmissionStoreError()
        submission_value = record.submission_id.value
        if submission_value in self.records or open_key in self.open_index:
            raise SubmissionConflictError()

        previous_value_nodes = self.retained_value_nodes
        previous_identity_bytes = self.retained_strategy_identity_bytes
        try:
            self.records[submission_value] = record
            self.open_index[open_key] = submission_value
            self.retained_value_nodes += value_nodes
            self.retained_strategy_identity_bytes += identity_bytes
        except BaseException:
            self.retained_value_nodes = previous_value_nodes
            self.retained_strategy_identity_bytes = previous_identity_bytes
            dict.pop(self.open_index, open_key, None)
            dict.pop(self.records, submission_value, None)
            raise

    def validate_open_owner_locked(self, record: _SubmissionRecord) -> _OpenKey:
        key = self._open_key_for_record_locked(record)
        if (
            type(record.submission_id) is not SubmissionId
            or dict.get(self.open_index, key) != record.submission_id.value
        ):
            raise SubmissionStoreError()
        return key

    def close_open_locked(self, open_key: _OpenKey) -> None:
        dict.__delitem__(self.open_index, open_key)

    @staticmethod
    def _open_key_for_record_locked(record: _SubmissionRecord) -> _OpenKey:
        if (
            type(record.requester_identity) is not RequesterIdentity
            or type(record.challenge_key) is not ChallengeKey
            or type(record.strategy_hash) is not StrategyHash
        ):
            raise SubmissionStoreError()
        return (
            record.requester_identity.value,
            record.challenge_key.challenge_id,
            record.challenge_key.version,
            record.strategy_hash.value,
        )


__all__ = ()
