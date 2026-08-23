"""Narrow, current-constructor adapters for A7's A4/A5 boundary."""

from __future__ import annotations

from carbon.registry import ChallengeKey
from carbon.scoring.model import (
    GateDecision,
    InternalResult,
    LegScore,
    ScalarScore,
    ScorePackPin,
    ScoreStatus,
)
from carbon.seeding import SeedPin


def _canonical_status(value: object) -> ScoreStatus | None:
    if value is ScoreStatus.SCORED:
        return ScoreStatus.SCORED
    if value is ScoreStatus.MANDATORY_GATE_FAILED:
        return ScoreStatus.MANDATORY_GATE_FAILED
    if value is ScoreStatus.PACK_NOT_READY:
        return ScoreStatus.PACK_NOT_READY
    return None


def _owned_internal_result(value: object) -> InternalResult | None:
    """Reconstruct a complete exact A5 graph without generic introspection."""
    try:
        if type(value) is not InternalResult:
            return None
        status = _canonical_status(value.status)
        if status is None:
            return None

        source_pin = value.pack_pin
        if type(source_pin) is not ScorePackPin:
            return None
        source_challenge = source_pin.challenge_key
        if type(source_challenge) is not ChallengeKey:
            return None
        challenge = ChallengeKey(
            source_challenge.challenge_id, source_challenge.version
        )
        pin = ScorePackPin(
            challenge_key=challenge,
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
                    source_gate.gate_id,
                    source_gate.passed,
                    source_gate.mandatory,
                )
            )

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
                    ScalarScore(source_component.identifier, source_component.score)
                )
            legs.append(LegScore(source_leg.leg, tuple(components), source_leg.score))

        return InternalResult(
            status=status,
            pack_pin=pin,
            gate_decisions=tuple(gates),
            leg_scores=tuple(legs),
            combined_score=value.combined_score,
            eligible_for_emission=value.eligible_for_emission,
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _result_matches_seed_pin(result: InternalResult, seed_pin: SeedPin) -> bool:
    """Compare only the exact A5/A4 fields ratified for A7 attribution."""
    pin = result.pack_pin
    return (
        pin.challenge_key == seed_pin.challenge_key
        and pin.scoring_version == seed_pin.scoring_version
        and pin.scoring_digest == seed_pin.scoring_digest
        and pin.generator_version_required == seed_pin.generator_version
        and pin.generator_digest_required == seed_pin.generator_digest
    )


__all__ = ()
