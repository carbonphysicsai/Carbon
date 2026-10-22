"""Cooling 1.2's card states its recorded limitation (Validator ruling
VALIDATOR_RULING_COOLING12_PEAK_GATE_20261022, finding G1): catalog recipes
fail the mandatory peak_bounds_profile gate until Cooling 1.3."""

from __future__ import annotations

from scripts.dev.miner_launchpad import capabilities


def test_the_1_2_card_states_the_peak_gate_limitation_and_others_none():
    cooling = {"challenge_id": "chip-cold-plate", "version": "1.2"}
    (line,) = capabilities._known_limitations(cooling)
    assert "peak_bounds_profile" in line and "Cooling 1.3" in line
    assert capabilities._known_limitations({**cooling, "version": "1.1"}) == []
    motor = {"challenge_id": "electric-motor-magnetics", "version": "1.3"}
    assert capabilities._known_limitations(motor) == []
