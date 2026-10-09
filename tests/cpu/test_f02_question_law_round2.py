"""Analysis arithmetic and prospective boundaries, not physics or adoption."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/development/challenge_pipeline/question-laws/f02-round2.json"
SHEET = json.loads(PATH.read_text(encoding="utf-8"))


def test_menu_capacity_and_context_counts():
    assert SHEET["context_count"] == 2 * 2 * 2 * 3
    actions = SHEET["action_proposal"]
    assert SHEET["seed_menu_size"] == len(actions["seed_power_w"]) * len(
        actions["seed_duration_s"]
    )
    required = 2 * SHEET["t2a"]["minimum_each_side"]
    assert SHEET["historical_menu_size"] < required <= SHEET["seed_menu_size"]
    assert not SHEET["t2a"]["old_menu_cardinality_can_pass"]
    assert SHEET["historical_grid_question_vectors"] == 24 * 3 * 3


def test_safety_and_adoption_are_not_relaxed():
    assert SHEET["hard_temperature_anchor_c"] == 95
    assert max(SHEET["p_job"]["recommendation"]["thermal_cap_c"]) <= 95
    for name in ("p_job", "q_job", "w_job", "action_proposal", "k"):
        assert SHEET[name]["registered"] is None
    assert not SHEET["runtime_adoption"]
    assert SHEET["solver_runs"] == SHEET["spend"] == 0
    assert not SHEET["bank_recommendation"]["same_truth_resets_exposure"]
    assert SHEET["t2a"]["near_refinement_bands"] == 2
    assert SHEET["expected_distinct_winners_p"] is None
    assert set(SHEET["value_check"].values()) == {"NOT_DEMONSTRATED"}


def test_bank_units_and_cost_arithmetic():
    bank, cost = SHEET["bank_recommendation"], SHEET["cost"]
    assert bank["b_questions"] == bank["multiplier"] * SHEET["k"]["recommendation"]
    assert (
        cost["standard_panel_jobs"] == SHEET["seed_menu_size"] * SHEET["context_count"]
    )
    for minutes, expected in ((2, 17.536), (3, 26.304)):
        bare = 384 * minutes / 60 * cost["node_eur_per_h_assumption"]
        assert bare == pytest.approx(expected)
    cap_h = (100 - 20) / (1.37 * 1.19)
    assert cap_h == pytest.approx(49.0707231798)
    assert cost["refinement_cpu_h_measured"] is None
    assert cost["c2_status"] == "UNMEASURED"


def test_original_menu_has_seven_energy_levels_not_nine():
    energies = {
        (power - 20) * duration for power in (80, 110, 140) for duration in (5, 10, 20)
    }
    assert len(energies) == 7
    assert len({energy / 2 for energy in energies}) == 7
