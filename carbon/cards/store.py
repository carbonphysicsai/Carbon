"""Process-local insert-only storage and bounded A6 card projection."""

from __future__ import annotations

from dataclasses import dataclass, field

from carbon.registry import ChallengeKey
from carbon.scoring.model import (
    GateDecision,
    InternalResult,
    LegScore,
    ScalarScore,
    ScorePackPin,
    ScoreStatus,
)

from .model import (
    _DISCLOSURE_TIER,
    _MANDATORY_GATE_FAILURE_TAG,
    _PUBLIC_CARD_SCHEMA_VERSION,
    CardAuthorizationError,
    CardConflictError,
    CardNotFoundError,
    CardProjectionError,
    CardRecordKey,
    CardRequestError,
    CardStoreError,
    CardWriteDisposition,
    EvaluationCard,
    EvaluationComponentScores,
    EvaluationGateResult,
    RequesterAuthorizationKey,
)

_PRIVATE_RECORD_SCHEMA_VERSION = "1.0"
_MISSING = object()


@dataclass(frozen=True, slots=True, repr=False)
class _StoredCardRecord:
    """Exact private A6 record; no public getter exposes this value."""

    record_schema_version: str = field(
        default=_PRIVATE_RECORD_SCHEMA_VERSION, init=False
    )
    record_key: CardRecordKey
    requester_authorization_key: RequesterAuthorizationKey
    internal_result: InternalResult

    def __post_init__(self) -> None:
        if type(self.record_key) is not CardRecordKey:
            raise TypeError("record_key must be an exact CardRecordKey")
        if type(self.requester_authorization_key) is not RequesterAuthorizationKey:
            raise TypeError(
                "requester_authorization_key must be an exact "
                "RequesterAuthorizationKey"
            )
        if type(self.internal_result) is not InternalResult:
            raise TypeError("internal_result must be an exact InternalResult")


def _canonical_status(value: object) -> ScoreStatus | None:
    if value is ScoreStatus.SCORED:
        return ScoreStatus.SCORED
    if value is ScoreStatus.MANDATORY_GATE_FAILED:
        return ScoreStatus.MANDATORY_GATE_FAILED
    if value is ScoreStatus.PACK_NOT_READY:
        return ScoreStatus.PACK_NOT_READY
    return None


def _try_record_key(value: object) -> CardRecordKey | None:
    """Return a fresh validated key without leaking validation exceptions."""
    try:
        if type(value) is not CardRecordKey:
            return None
        return CardRecordKey(value.value)
    except (AttributeError, TypeError, ValueError):
        return None


def _try_requester_key(value: object) -> RequesterAuthorizationKey | None:
    """Return a fresh validated requester without leaking validation errors."""
    try:
        if type(value) is not RequesterAuthorizationKey:
            return None
        return RequesterAuthorizationKey(value.value)
    except (AttributeError, TypeError, ValueError):
        return None


def _try_internal_result(value: object) -> InternalResult | None:
    """Reconstruct one exact, recursively owned A5 result graph."""
    try:
        if type(value) is not InternalResult:
            return None

        status = _canonical_status(value.status)
        if status is None:
            return None

        source_pin = value.pack_pin
        if type(source_pin) is not ScorePackPin:
            return None
        source_challenge_key = source_pin.challenge_key
        if type(source_challenge_key) is not ChallengeKey:
            return None
        challenge_key = ChallengeKey(
            challenge_id=source_challenge_key.challenge_id,
            version=source_challenge_key.version,
        )
        pack_pin = ScorePackPin(
            challenge_key=challenge_key,
            scoring_version=source_pin.scoring_version,
            scoring_digest=source_pin.scoring_digest,
            generator_version_required=source_pin.generator_version_required,
            generator_digest_required=source_pin.generator_digest_required,
            schema_version=source_pin.schema_version,
            numerical_profile=source_pin.numerical_profile,
            fixture_origin=source_pin.fixture_origin,
        )

        source_gates = value.gate_decisions
        if type(source_gates) is not tuple:
            return None
        gates: list[GateDecision] = []
        for source_gate in source_gates:
            if type(source_gate) is not GateDecision:
                return None
            gates.append(
                GateDecision(
                    gate_id=source_gate.gate_id,
                    passed=source_gate.passed,
                    mandatory=source_gate.mandatory,
                )
            )
        gate_decisions = tuple(gate for gate in gates)

        source_legs = value.leg_scores
        if type(source_legs) is not tuple:
            return None
        legs: list[LegScore] = []
        for source_leg in source_legs:
            if type(source_leg) is not LegScore:
                return None
            source_components = source_leg.components
            if type(source_components) is not tuple:
                return None
            components: list[ScalarScore] = []
            for source_component in source_components:
                if type(source_component) is not ScalarScore:
                    return None
                components.append(
                    ScalarScore(
                        identifier=source_component.identifier,
                        score=source_component.score,
                    )
                )
            legs.append(
                LegScore(
                    leg=source_leg.leg,
                    components=tuple(component for component in components),
                    score=source_leg.score,
                )
            )
        leg_scores = tuple(leg for leg in legs)

        return InternalResult(
            status=status,
            pack_pin=pack_pin,
            gate_decisions=gate_decisions,
            leg_scores=leg_scores,
            combined_score=value.combined_score,
            eligible_for_emission=value.eligible_for_emission,
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _try_outer_record(
    value: object, expected_key: CardRecordKey
) -> tuple[_StoredCardRecord, RequesterAuthorizationKey] | None:
    """Validate only storage metadata needed before authorization."""
    try:
        if type(value) is not _StoredCardRecord:
            return None
        if type(value.record_schema_version) is not str:
            return None
        if value.record_schema_version != _PRIVATE_RECORD_SCHEMA_VERSION:
            return None
        stored_key = _try_record_key(value.record_key)
        if stored_key is None or stored_key != expected_key:
            return None
        requester_key = _try_requester_key(value.requester_authorization_key)
        if requester_key is None:
            return None
        if type(value.internal_result) is not InternalResult:
            return None
        return value, requester_key
    except AttributeError:
        return None


def _try_record_mapping(
    store: CardStore,
) -> dict[CardRecordKey, _StoredCardRecord] | None:
    try:
        records = store._records
    except AttributeError:
        return None
    if type(records) is not dict:
        return None
    return records


def _try_project_budgeted(record: _StoredCardRecord) -> EvaluationCard | None:
    """Build a fresh allow-listed card from one already-authorized record."""
    internal_result = _try_internal_result(record.internal_result)
    if internal_result is None:
        return None

    try:
        status = internal_result.status
        if status is ScoreStatus.SCORED:
            status_literal = "SCORED"
            component_scores = EvaluationComponentScores(
                physics=internal_result.leg_scores[0].score,
                robustness=internal_result.leg_scores[1].score,
                accuracy=internal_result.leg_scores[2].score,
            )
            failure_tags: tuple[str, ...] = ()
        elif status is ScoreStatus.MANDATORY_GATE_FAILED:
            status_literal = "MANDATORY_GATE_FAILED"
            component_scores = None
            failure_tags = (_MANDATORY_GATE_FAILURE_TAG,)
        elif status is ScoreStatus.PACK_NOT_READY:
            status_literal = "PACK_NOT_READY"
            component_scores = None
            failure_tags = ()
        else:  # pragma: no cover - guarded by the owned A5 snapshot
            return None

        gate_results = tuple(
            EvaluationGateResult(gate_id=decision.gate_id, passed=decision.passed)
            for decision in internal_result.gate_decisions
        )
        return EvaluationCard(
            schema_version=_PUBLIC_CARD_SCHEMA_VERSION,
            result_id=record.record_key.value,
            status=status_literal,
            scoring_pack_hash=internal_result.pack_pin.scoring_digest,
            overall_score=internal_result.combined_score,
            component_scores=component_scores,
            gate_results=gate_results,
            failure_tags=failure_tags,
            fixture_origin=internal_result.pack_pin.fixture_origin,
            eligible_for_emission=internal_result.eligible_for_emission,
            public_diagnostics=(),
            disclosure_tier=_DISCLOSURE_TIER,
        )
    except CardRequestError:
        return None


class CardStore:
    """Per-instance, process-local, in-memory, insert-only A6 card store.

    This bounded store is non-durable and is not a production concurrency or
    persistence implementation.
    """

    __slots__ = ("_records",)

    def __init__(self) -> None:
        self._records: dict[CardRecordKey, _StoredCardRecord] = {}

    def write_internal(
        self,
        record_key: CardRecordKey,
        requester_key: RequesterAuthorizationKey,
        internal_result: InternalResult,
    ) -> CardWriteDisposition:
        """Insert one exact private result or recognize an exact duplicate."""
        owned_record_key = _try_record_key(record_key)
        owned_requester_key = _try_requester_key(requester_key)
        owned_internal_result = _try_internal_result(internal_result)
        if (
            owned_record_key is None
            or owned_requester_key is None
            or owned_internal_result is None
        ):
            raise CardRequestError()

        candidate = _StoredCardRecord(
            record_key=owned_record_key,
            requester_authorization_key=owned_requester_key,
            internal_result=owned_internal_result,
        )
        records = _try_record_mapping(self)
        if records is None:
            raise CardStoreError()
        existing = records.get(owned_record_key, _MISSING)
        if existing is _MISSING:
            records[owned_record_key] = candidate
            return CardWriteDisposition.INSERTED

        outer = _try_outer_record(existing, owned_record_key)
        if outer is None:
            raise CardStoreError()
        existing_record, existing_requester = outer
        existing_result = _try_internal_result(existing_record.internal_result)
        if existing_result is None:
            raise CardStoreError()
        if (
            existing_requester == owned_requester_key
            and existing_result == owned_internal_result
        ):
            return CardWriteDisposition.ALREADY_PRESENT
        raise CardConflictError()

    def read_budgeted(
        self,
        record_key: CardRecordKey,
        requester_key: RequesterAuthorizationKey,
    ) -> EvaluationCard:
        """Authorize and return a fresh positive Phase-0 projection."""
        owned_record_key = _try_record_key(record_key)
        owned_requester_key = _try_requester_key(requester_key)
        if owned_record_key is None or owned_requester_key is None:
            raise CardRequestError()

        records = _try_record_mapping(self)
        if records is None:
            raise CardStoreError()
        existing = records.get(owned_record_key, _MISSING)
        if existing is _MISSING:
            raise CardNotFoundError()

        outer = _try_outer_record(existing, owned_record_key)
        if outer is None:
            raise CardStoreError()
        stored_record, stored_requester = outer
        if stored_requester != owned_requester_key:
            raise CardAuthorizationError()

        card = _try_project_budgeted(stored_record)
        if card is None:
            raise CardProjectionError()
        return card


__all__ = ("CardStore",)
