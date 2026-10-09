"""Static proposal boundaries/arithmetic, not V/T/C acceptance evidence."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "docs/development/challenge_pipeline/value-cost/reframes"
SHEET = json.loads((DIRECTORY / "proposals.json").read_text(encoding="utf-8"))
CARDS = SHEET["cards"]


def test_not_an_adoption_or_measurement_grant():
    assert SHEET["maturity"] == "SPECIFIED"
    assert SHEET["adoption"] == "HUMAN_INPUT"
    assert SHEET["spend_grant"] is SHEET["net_savings"] is None
    for name in (
        "runtime_registration",
        "historical_rescore",
        "solver_runs",
        "one_fix_consumed_by_this_sheet",
    ):
        assert SHEET[name] is False
    assert SHEET["check_existing_adopted_fix_ledger"] is True
    assert {card["family"] for card in CARDS} == {"f06", "f08", "cooling-cell"}


@pytest.mark.parametrize("card", CARDS, ids=lambda card: card["family"])
def test_value_is_smaller_assumption_and_not_a_net_saving(card):
    rates = SHEET["hourly_rates_usd_assumption"]
    for scope in ("original", "candidate"):
        assert [
            h * r for h, r in zip(card[f"{scope}_hours_assumption"], rates)
        ] == card[f"{scope}_gross_usd"]
    assert all(
        a < b for a, b in zip(card["candidate_gross_usd"], card["original_gross_usd"])
    )
    assert [
        value * count
        for value, count in zip(
            card["candidate_gross_usd"], card["annual_opportunities_assumption"]
        )
    ] == card["candidate_annual_gross_usd"]
    assert card["volume_status"] == "NOT_DEMONSTRATED"
    assert SHEET["empirical_commercial_floor_usd"] == 0


@pytest.mark.parametrize("card", CARDS, ids=lambda card: card["family"])
def test_sources_lost_scope_and_narrowed_tier_are_explicit(card):
    text = (DIRECTORY / card["file"]).read_text(encoding="utf-8")
    assert len({urlsplit(url).hostname for url in card["sources"]}) >= 2
    assert all(url in text for url in card["sources"])
    assert card["lost_scope"]
    assert card["target_tier"] == 2
    assert card["earned_tier"] == "NOT_DEMONSTRATED"
    assert "HUMAN_INPUT" in text
    # Source existence/independence is not physical credibility or market proof.
    assert "NOT_DEMONSTRATED" in text


def test_safety_scope_and_cooling_hold_are_preserved():
    cards = {card["family"]: card for card in CARDS}
    assert cards["f06"]["final_original_limits"] == {
        "coupling_floor": 0.3,
        "guided_reflection_cap": 0.1,
    }
    assert cards["f06"]["new_second_fix"] is False
    assert cards["f08"]["final_original_limits"] == {
        "mass_kg": 0.45,
        "static_mm_per_n": 0.03,
        "dynamic_mm_per_n": 0.15,
        "frequency_hz": [80, 600],
    }
    cooling = cards["cooling-cell"]
    assert cooling["final_original_limits"]["case_temperature_c"] == 85
    assert cooling["final_original_limits"]["plane"] == "LID_SIDE_TIM2"
    assert cooling["final_original_limits"]["cell_hydraulic_constraints"] is None
    assert cooling["running_T1_T2_required_before_adoption"] is True
    assert (
        cooling["assembly_limits_adopted_as_cell"]
        is cooling["full_cold_plate"]
        is False
    )
    assert (
        cooling["optimizer_regret_for_classification_only"] == "NOT_APPLICABLE_NOT_ZERO"
    )


def test_f06_existing_reframe_is_not_a_second_value_haircut():
    f06 = CARDS[0]
    assert f06["family"] == "f06"
    assert f06["candidate_gross_usd"] == [200, 600, 1200]
    text = (DIRECTORY / "README.md").read_text(encoding="utf-8")
    assert "already" in text and "not a second reduction" in text
    assert "no sample power/decision threshold" in text
