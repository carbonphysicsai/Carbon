"""Immutable values for the bounded A6 card-store disclosure boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from carbon.registry import (
    is_sha256_digest,
    validate_canonical_identifier,
    validate_version,
)

_PUBLIC_CARD_SCHEMA_VERSION = "1.0"
_DISCLOSURE_TIER = "phase0_budgeted"
_MANDATORY_GATE_FAILURE_TAG = "mandatory_gate_failed"
_SCORED = "SCORED"
_MANDATORY_GATE_FAILED = "MANDATORY_GATE_FAILED"
_PACK_NOT_READY = "PACK_NOT_READY"
_PUBLIC_STATUSES = (_SCORED, _MANDATORY_GATE_FAILED, _PACK_NOT_READY)


class CardRequestError(ValueError):
    """Stable, non-echoing failure for an invalid A6 request or value."""

    def __init__(self) -> None:
        self.code = "card.request.invalid"
        super().__init__("Card request is invalid.")


class CardNotFoundError(LookupError):
    """Stable, non-echoing failure for an absent A6 card record."""

    def __init__(self) -> None:
        self.code = "card.record.not_found"
        super().__init__("Card record was not found.")


class CardAuthorizationError(PermissionError):
    """Stable, non-echoing failure for an unauthorized A6 card read."""

    def __init__(self) -> None:
        self.code = "card.authorization.denied"
        super().__init__("Card access is not authorized.")


class CardConflictError(RuntimeError):
    """Stable, non-echoing failure for an insert-only record conflict."""

    def __init__(self) -> None:
        self.code = "card.record.conflict"
        super().__init__("Card record conflicts with existing data.")


class CardStoreError(RuntimeError):
    """Stable, non-echoing failure for recognized private-store corruption."""

    def __init__(self) -> None:
        self.code = "card.store.failure"
        super().__init__("Card store operation failed.")


class CardProjectionError(RuntimeError):
    """Stable, non-echoing failure for a recognized projection invariant."""

    def __init__(self) -> None:
        self.code = "card.projection.failure"
        super().__init__("Card projection failed.")


class CardWriteDisposition(str, Enum):
    """Closed outcomes for an insert-only A6 write."""

    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


def _validated_version_token(value: object) -> str | None:
    if type(value) is not str:
        return None
    try:
        return validate_version(value)
    except ValueError:
        return None


def _validated_canonical_identifier(value: object, field_name: str) -> str | None:
    if type(value) is not str:
        return None
    try:
        return validate_canonical_identifier(value, field_name)
    except ValueError:
        return None


def _is_unit_float(value: object) -> bool:
    return type(value) is float and math.isfinite(value) and 0.0 <= value <= 1.0


def _is_positive_unit_float(value: object) -> bool:
    return _is_unit_float(value) and (value != 0.0 or math.copysign(1.0, value) == 1.0)


def _is_canonical_positive_zero(value: object) -> bool:
    return type(value) is float and value == 0.0 and math.copysign(1.0, value) == 1.0


@dataclass(frozen=True, slots=True)
class CardRecordKey:
    """Opaque pre-A7 lookup/result token for one stored A6 record."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        validated = _validated_version_token(self.value)
        if validated is None:
            raise CardRequestError()
        object.__setattr__(self, "value", validated)


@dataclass(frozen=True, slots=True)
class RequesterAuthorizationKey:
    """Opaque pre-A7 requester binding label, not an authentication proof."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        validated = _validated_version_token(self.value)
        if validated is None:
            raise CardRequestError()
        object.__setattr__(self, "value", validated)


@dataclass(frozen=True, slots=True)
class EvaluationComponentScores:
    """The three approved top-level A5 leg scores."""

    physics: float
    robustness: float
    accuracy: float

    def __post_init__(self) -> None:
        if not all(
            _is_unit_float(value)
            for value in (self.physics, self.robustness, self.accuracy)
        ):
            raise CardRequestError()


@dataclass(frozen=True, slots=True)
class EvaluationGateResult:
    """The public pass/fail projection of one evaluated A5 gate."""

    gate_id: str
    passed: bool

    def __post_init__(self) -> None:
        validated_gate_id = _validated_canonical_identifier(self.gate_id, "gate_id")
        if validated_gate_id is None or type(self.passed) is not bool:
            raise CardRequestError()
        object.__setattr__(self, "gate_id", validated_gate_id)


def _owned_component_scores(
    value: object,
) -> EvaluationComponentScores | None:
    if type(value) is not EvaluationComponentScores:
        return None
    try:
        physics = value.physics
        robustness = value.robustness
        accuracy = value.accuracy
    except AttributeError:
        return None
    try:
        return EvaluationComponentScores(physics, robustness, accuracy)
    except CardRequestError:
        return None


def _owned_gate_result(value: object) -> EvaluationGateResult | None:
    if type(value) is not EvaluationGateResult:
        return None
    try:
        gate_id = value.gate_id
        passed = value.passed
    except AttributeError:
        return None
    try:
        return EvaluationGateResult(gate_id, passed)
    except CardRequestError:
        return None


@dataclass(frozen=True, slots=True)
class EvaluationCard:
    """Exact immutable Phase-0 public projection of an authorized A6 record."""

    schema_version: str
    result_id: str
    status: str
    scoring_pack_hash: str
    overall_score: float | None
    component_scores: EvaluationComponentScores | None
    gate_results: tuple[EvaluationGateResult, ...]
    failure_tags: tuple[str, ...]
    fixture_origin: bool
    eligible_for_emission: bool
    public_diagnostics: tuple[str, ...]
    disclosure_tier: str

    def __post_init__(self) -> None:
        validated_result_id = _validated_version_token(self.result_id)
        if (
            type(self.schema_version) is not str
            or self.schema_version != _PUBLIC_CARD_SCHEMA_VERSION
            or validated_result_id is None
            or type(self.status) is not str
            or self.status not in _PUBLIC_STATUSES
            or not is_sha256_digest(self.scoring_pack_hash)
            or type(self.gate_results) is not tuple
            or type(self.failure_tags) is not tuple
            or any(type(tag) is not str for tag in self.failure_tags)
            or type(self.public_diagnostics) is not tuple
            or bool(self.public_diagnostics)
            or type(self.fixture_origin) is not bool
            or self.fixture_origin is not True
            or type(self.eligible_for_emission) is not bool
            or self.eligible_for_emission is not False
            or type(self.disclosure_tier) is not str
            or self.disclosure_tier != _DISCLOSURE_TIER
        ):
            raise CardRequestError()

        owned_gates: list[EvaluationGateResult] = []
        seen_gate_ids: set[str] = set()
        for gate_result in self.gate_results:
            owned_gate = _owned_gate_result(gate_result)
            if owned_gate is None or owned_gate.gate_id in seen_gate_ids:
                raise CardRequestError()
            seen_gate_ids.add(owned_gate.gate_id)
            owned_gates.append(owned_gate)
        owned_gate_results = tuple(owned_gates)

        owned_components: EvaluationComponentScores | None
        if self.status == _SCORED:
            owned_components = _owned_component_scores(self.component_scores)
            if (
                not _is_positive_unit_float(self.overall_score)
                or owned_components is None
                or not owned_gate_results
                or self.failure_tags != ()
            ):
                raise CardRequestError()
        elif self.status == _MANDATORY_GATE_FAILED:
            owned_components = None
            if (
                not _is_canonical_positive_zero(self.overall_score)
                or self.component_scores is not None
                or not owned_gate_results
                or not any(not gate.passed for gate in owned_gate_results)
                or self.failure_tags != (_MANDATORY_GATE_FAILURE_TAG,)
            ):
                raise CardRequestError()
        else:
            owned_components = None
            if (
                self.overall_score is not None
                or self.component_scores is not None
                or owned_gate_results
                or self.failure_tags != ()
            ):
                raise CardRequestError()

        object.__setattr__(self, "schema_version", _PUBLIC_CARD_SCHEMA_VERSION)
        object.__setattr__(self, "result_id", validated_result_id)
        object.__setattr__(self, "gate_results", owned_gate_results)
        object.__setattr__(
            self, "failure_tags", tuple(tag for tag in self.failure_tags)
        )
        object.__setattr__(self, "component_scores", owned_components)
        object.__setattr__(self, "public_diagnostics", ())
        object.__setattr__(self, "disclosure_tier", _DISCLOSURE_TIER)


__all__ = (
    "CardAuthorizationError",
    "CardConflictError",
    "CardNotFoundError",
    "CardProjectionError",
    "CardRecordKey",
    "CardRequestError",
    "CardStoreError",
    "CardWriteDisposition",
    "EvaluationCard",
    "EvaluationComponentScores",
    "EvaluationGateResult",
    "RequesterAuthorizationKey",
)
