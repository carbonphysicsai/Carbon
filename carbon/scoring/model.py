"""Immutable, fixture-only value objects for canonical A5 scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from carbon.registry import (
    ChallengeKey,
    is_sha256_digest,
    validate_canonical_identifier,
    validate_version,
)

_NUMERICAL_PROFILE = "python_binary64_v1"
_SCHEMA_VERSION = "1.0"
_LEG_ORDER = ("physics", "robustness", "accuracy")


class ScoreStatus(str, Enum):
    """Closed set of scientific scoring dispositions produced by A5."""

    SCORED = "SCORED"
    MANDATORY_GATE_FAILED = "MANDATORY_GATE_FAILED"
    PACK_NOT_READY = "PACK_NOT_READY"


class ScoreInputError(ValueError):
    """Closed ScoreInput construction or lookup failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _validate_identifier(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be an exact string")
    return validate_canonical_identifier(value, field_name)


def _validate_input_key(value: object) -> str:
    if type(value) is not str:
        raise ScoreInputError(
            "score_input.key_type", "ScoreInput key must be an exact string."
        )
    try:
        return validate_canonical_identifier(value, "score input key")
    except ValueError as exc:
        raise ScoreInputError(
            "score_input.key_invalid", "ScoreInput key is not canonical."
        ) from exc


def _validate_unit_score(value: object, field_name: str) -> float:
    if type(value) is not float:
        raise TypeError(f"{field_name} must be an exact float")
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be finite and within [0.0, 1.0]")
    return value


@dataclass(frozen=True, slots=True)
class ScorePackPin:
    """Complete immutable identity of one fixture-only Score Pack."""

    challenge_key: ChallengeKey
    scoring_version: str
    scoring_digest: str
    generator_version_required: str
    generator_digest_required: str
    schema_version: str
    numerical_profile: str
    fixture_origin: bool

    def __post_init__(self) -> None:
        if type(self.challenge_key) is not ChallengeKey:
            raise TypeError("challenge_key must be an exact ChallengeKey")
        validate_version(self.scoring_version)
        if not is_sha256_digest(self.scoring_digest):
            raise ValueError("scoring_digest is not a tagged SHA-256 digest")
        validate_version(self.generator_version_required)
        if not is_sha256_digest(self.generator_digest_required):
            raise ValueError("generator_digest_required is not a tagged SHA-256 digest")
        if type(self.schema_version) is not str:
            raise TypeError("schema_version must be an exact string")
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version is not supported by A5")
        if type(self.numerical_profile) is not str:
            raise TypeError("numerical_profile must be an exact string")
        if self.numerical_profile != _NUMERICAL_PROFILE:
            raise ValueError("numerical_profile is not supported by A5")
        if type(self.fixture_origin) is not bool:
            raise TypeError("fixture_origin must be an exact boolean")
        if self.fixture_origin is not True:
            raise ValueError("A5 accepts only fixture-origin Score Packs")


@dataclass(frozen=True, slots=True)
class NumericInput:
    """One validator-authorized finite non-negative binary64 scalar."""

    key: str
    value: float

    def __post_init__(self) -> None:
        _validate_input_key(self.key)
        if type(self.value) is not float:
            raise ScoreInputError(
                "score_input.numeric_type",
                "Numeric ScoreInput value must be an exact float.",
            )
        if not math.isfinite(self.value) or self.value < 0.0:
            raise ScoreInputError(
                "score_input.numeric_range",
                "Numeric ScoreInput value must be finite and non-negative.",
            )


@dataclass(frozen=True, slots=True)
class BooleanInput:
    """One validator-authorized exact Boolean predicate scalar."""

    key: str
    value: bool

    def __post_init__(self) -> None:
        _validate_input_key(self.key)
        if type(self.value) is not bool:
            raise ScoreInputError(
                "score_input.boolean_type",
                "Boolean ScoreInput value must be an exact boolean.",
            )


@dataclass(frozen=True, slots=True, init=False)
class ScoreInput:
    """Closed validator-owned scalar input; direct construction is forbidden."""

    pack_pin: ScorePackPin
    numeric_inputs: tuple[NumericInput, ...]
    boolean_inputs: tuple[BooleanInput, ...]

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ScoreInputError(
            "score_input.direct_init",
            "ScoreInput must be constructed by the validated fixture boundary.",
        )

    @classmethod
    def _from_validated_fixture(
        cls,
        *,
        pack_pin: ScorePackPin,
        numeric_inputs: tuple[NumericInput, ...],
        boolean_inputs: tuple[BooleanInput, ...],
    ) -> ScoreInput:
        """Construct from the module-private, fully validated fixture boundary."""
        if cls is not ScoreInput:
            raise ScoreInputError(
                "score_input.class_invalid", "ScoreInput cannot be subclassed."
            )
        if type(pack_pin) is not ScorePackPin:
            raise ScoreInputError(
                "score_input.pin_type", "ScoreInput pin must be an exact ScorePackPin."
            )
        if type(numeric_inputs) is not tuple:
            raise ScoreInputError(
                "score_input.numeric_inputs_type",
                "Numeric ScoreInput entries must be an exact tuple.",
            )
        if type(boolean_inputs) is not tuple:
            raise ScoreInputError(
                "score_input.boolean_inputs_type",
                "Boolean ScoreInput entries must be an exact tuple.",
            )

        seen_keys: set[str] = set()
        for entry in numeric_inputs:
            if type(entry) is not NumericInput:
                raise ScoreInputError(
                    "score_input.numeric_entry_type",
                    "Numeric ScoreInput tuple contains an invalid entry.",
                )
            if entry.key in seen_keys:
                raise ScoreInputError(
                    "score_input.duplicate_key", "ScoreInput contains a duplicate key."
                )
            seen_keys.add(entry.key)
        for entry in boolean_inputs:
            if type(entry) is not BooleanInput:
                raise ScoreInputError(
                    "score_input.boolean_entry_type",
                    "Boolean ScoreInput tuple contains an invalid entry.",
                )
            if entry.key in seen_keys:
                raise ScoreInputError(
                    "score_input.duplicate_key", "ScoreInput contains a duplicate key."
                )
            seen_keys.add(entry.key)

        instance = object.__new__(cls)
        object.__setattr__(instance, "pack_pin", pack_pin)
        object.__setattr__(instance, "numeric_inputs", numeric_inputs)
        object.__setattr__(instance, "boolean_inputs", boolean_inputs)
        return instance

    def numeric_value(self, key: str) -> float:
        """Return one numeric value by exact canonical key."""
        validated_key = _validate_input_key(key)
        for entry in self.numeric_inputs:
            if entry.key == validated_key:
                return entry.value
        raise ScoreInputError(
            "score_input.numeric_missing", "Required numeric ScoreInput key is absent."
        )

    def boolean_value(self, key: str) -> bool:
        """Return one Boolean value by exact canonical key."""
        validated_key = _validate_input_key(key)
        for entry in self.boolean_inputs:
            if entry.key == validated_key:
                return entry.value
        raise ScoreInputError(
            "score_input.boolean_missing", "Required Boolean ScoreInput key is absent."
        )


@dataclass(frozen=True, slots=True)
class GateDecision:
    """One evaluated binary hard-gate decision."""

    gate_id: str
    passed: bool
    mandatory: bool

    def __post_init__(self) -> None:
        _validate_identifier(self.gate_id, "gate_id")
        if type(self.passed) is not bool:
            raise TypeError("passed must be an exact boolean")
        if type(self.mandatory) is not bool:
            raise TypeError("mandatory must be an exact boolean")


@dataclass(frozen=True, slots=True)
class ScalarScore:
    """One authorized bounded scalar component score."""

    identifier: str
    score: float

    def __post_init__(self) -> None:
        _validate_identifier(self.identifier, "score identifier")
        _validate_unit_score(self.score, "component score")


@dataclass(frozen=True, slots=True)
class LegScore:
    """One ordered, bounded top-level scoring leg."""

    leg: str
    components: tuple[ScalarScore, ...]
    score: float

    def __post_init__(self) -> None:
        if type(self.leg) is not str:
            raise TypeError("leg must be an exact string")
        if self.leg not in _LEG_ORDER:
            raise ValueError("leg is not supported by A5")
        if type(self.components) is not tuple:
            raise TypeError("components must be an exact tuple")
        if not self.components:
            raise ValueError("components must not be empty")
        identifiers: set[str] = set()
        for component in self.components:
            if type(component) is not ScalarScore:
                raise TypeError("components contains an invalid entry")
            if component.identifier in identifiers:
                raise ValueError("components contains a duplicate identifier")
            identifiers.add(component.identifier)
        _validate_unit_score(self.score, "leg score")


@dataclass(frozen=True, slots=True)
class InternalResult:
    """Private, fixture-only scientific scoring result."""

    status: ScoreStatus
    pack_pin: ScorePackPin
    gate_decisions: tuple[GateDecision, ...]
    leg_scores: tuple[LegScore, ...]
    combined_score: float | None
    eligible_for_emission: bool

    def __post_init__(self) -> None:
        if type(self.status) is not ScoreStatus:
            raise TypeError("status must be an exact ScoreStatus")
        if type(self.pack_pin) is not ScorePackPin:
            raise TypeError("pack_pin must be an exact ScorePackPin")
        if type(self.gate_decisions) is not tuple:
            raise TypeError("gate_decisions must be an exact tuple")
        gate_ids: set[str] = set()
        for decision in self.gate_decisions:
            if type(decision) is not GateDecision:
                raise TypeError("gate_decisions contains an invalid entry")
            if decision.gate_id in gate_ids:
                raise ValueError("gate_decisions contains a duplicate gate_id")
            gate_ids.add(decision.gate_id)
        if type(self.leg_scores) is not tuple:
            raise TypeError("leg_scores must be an exact tuple")
        if any(type(leg_score) is not LegScore for leg_score in self.leg_scores):
            raise TypeError("leg_scores contains an invalid entry")
        if type(self.eligible_for_emission) is not bool:
            raise TypeError("eligible_for_emission must be an exact boolean")
        if self.eligible_for_emission is not False:
            raise ValueError("fixture-origin A5 results are never emission-eligible")

        if self.status is ScoreStatus.PACK_NOT_READY:
            if (
                self.gate_decisions
                or self.leg_scores
                or self.combined_score is not None
            ):
                raise ValueError(
                    "PACK_NOT_READY cannot contain evaluated scientific results"
                )
            return

        if self.status is ScoreStatus.MANDATORY_GATE_FAILED:
            if self.leg_scores:
                raise ValueError(
                    "MANDATORY_GATE_FAILED cannot contain evaluated leg scores"
                )
            if (
                type(self.combined_score) is not float
                or self.combined_score != 0.0
                or math.copysign(1.0, self.combined_score) != 1.0
            ):
                raise ValueError(
                    "MANDATORY_GATE_FAILED requires canonical positive 0.0"
                )
            if not any(
                decision.mandatory and not decision.passed
                for decision in self.gate_decisions
            ):
                raise ValueError(
                    "MANDATORY_GATE_FAILED requires a failed mandatory gate"
                )
            return

        if tuple(leg_score.leg for leg_score in self.leg_scores) != _LEG_ORDER:
            raise ValueError(
                "SCORED requires ordered physics, robustness, and accuracy legs"
            )
        if not any(decision.mandatory for decision in self.gate_decisions):
            raise ValueError("SCORED requires at least one mandatory gate decision")
        if any(
            decision.mandatory and not decision.passed
            for decision in self.gate_decisions
        ):
            raise ValueError("SCORED cannot contain a failed mandatory gate")
        _validate_unit_score(self.combined_score, "combined score")
        if (
            self.combined_score == 0.0
            and math.copysign(1.0, self.combined_score) != 1.0
        ):
            raise ValueError("SCORED requires canonical positive 0.0")

    def _copy(self) -> InternalResult:
        """Return an A5-owned, recursively validated copy of this result."""
        if type(self) is not InternalResult:
            raise TypeError("InternalResult copy requires an exact InternalResult")

        if self.status is ScoreStatus.SCORED:
            status = ScoreStatus.SCORED
        elif self.status is ScoreStatus.MANDATORY_GATE_FAILED:
            status = ScoreStatus.MANDATORY_GATE_FAILED
        elif self.status is ScoreStatus.PACK_NOT_READY:
            status = ScoreStatus.PACK_NOT_READY
        else:
            raise TypeError("status must be a canonical ScoreStatus")

        source_pin = self.pack_pin
        if type(source_pin) is not ScorePackPin:
            raise TypeError("pack_pin must be an exact ScorePackPin")
        source_key = source_pin.challenge_key
        if type(source_key) is not ChallengeKey:
            raise TypeError("challenge_key must be an exact ChallengeKey")
        pack_pin = ScorePackPin(
            challenge_key=ChallengeKey(
                source_key.challenge_id,
                source_key.version,
            ),
            scoring_version=source_pin.scoring_version,
            scoring_digest=source_pin.scoring_digest,
            generator_version_required=source_pin.generator_version_required,
            generator_digest_required=source_pin.generator_digest_required,
            schema_version=source_pin.schema_version,
            numerical_profile=source_pin.numerical_profile,
            fixture_origin=source_pin.fixture_origin,
        )

        if type(self.gate_decisions) is not tuple:
            raise TypeError("gate_decisions must be an exact tuple")
        gates: list[GateDecision] = []
        for source_gate in self.gate_decisions:
            if type(source_gate) is not GateDecision:
                raise TypeError("gate_decisions contains an invalid entry")
            gates.append(
                GateDecision(
                    source_gate.gate_id,
                    source_gate.passed,
                    source_gate.mandatory,
                )
            )

        if type(self.leg_scores) is not tuple:
            raise TypeError("leg_scores must be an exact tuple")
        legs: list[LegScore] = []
        for source_leg in self.leg_scores:
            if type(source_leg) is not LegScore:
                raise TypeError("leg_scores contains an invalid entry")
            if type(source_leg.components) is not tuple:
                raise TypeError("components must be an exact tuple")
            components: list[ScalarScore] = []
            for source_component in source_leg.components:
                if type(source_component) is not ScalarScore:
                    raise TypeError("components contains an invalid entry")
                components.append(
                    ScalarScore(
                        source_component.identifier,
                        source_component.score,
                    )
                )
            legs.append(
                LegScore(
                    source_leg.leg,
                    tuple(components),
                    source_leg.score,
                )
            )

        return InternalResult(
            status=status,
            pack_pin=pack_pin,
            gate_decisions=tuple(gates),
            leg_scores=tuple(legs),
            combined_score=self.combined_score,
            eligible_for_emission=self.eligible_for_emission,
        )


__all__ = (
    "BooleanInput",
    "GateDecision",
    "InternalResult",
    "LegScore",
    "NumericInput",
    "ScalarScore",
    "ScoreInput",
    "ScoreInputError",
    "ScorePackPin",
    "ScoreStatus",
)
