"""Proposal/static arithmetic checks; no sampler, solver or hidden input."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAW = ROOT / "docs/development/challenge_pipeline/question-laws"
SHEET = json.loads((LAW / "battery-v3-round2.json").read_text(encoding="utf-8"))
TEXT = (LAW / "battery-v3-round2.md").read_text(encoding="utf-8")


def test_proposal_cannot_register_or_execute_science():
    assert SHEET["maturity"] == "SPECIFIED"
    for flag in ("runtime_registration", "historical_rescore", "solver_runs"):
        assert SHEET[flag] is False
    for name in ("registered_P", "registered_Q", "registered_outer_w", "spend_grant"):
        assert SHEET[name] is None
    assert SHEET["other_challenge_laws_changed"] is False


def test_approved_actions_do_not_adopt_missing_bounds_or_round_truth():
    action = SHEET["action_decision"]
    assert action["status"] == "OWNER_APPROVED_DEVELOPMENT"
    assert Decimal(action["c_rate_step_c"]) == Decimal("0.01")
    assert action["cooling_multipliers"] == [1, 2, 4]
    assert action["round_historical_actions"] is False
    assert action["c_rate_bounds"] is None
    assert action["switch_voltage_menu"] is None
    assert action["all_bands_mandatory"] is True
    # Toy lattice illustration, not reference evidence or action validation.
    assert Decimal("1.12") % Decimal(action["c_rate_step_c"]) == 0
    assert Decimal("1.125") % Decimal(action["c_rate_step_c"]) != 0


def test_safety_and_objective_not_relaxed_to_make_an_answer():
    assert SHEET["hard_anchor_limits"] == {
        "charging_temperature_max_c": 45,
        "every_charge_plating_min_v": 0,
        "programme_voltage_max_v": 4.2,
        "q30_over_q1_min": 0.99,
        "hard_session_time_cap": None,
        "discharge_thermal_role": "DIAGNOSTIC",
    }


def test_supported_p_separate_from_expanded_p_and_diagnostic_q():
    p, q, w = SHEET["P_recommendation"], SHEET["Q_recommendation"], SHEET["w"]
    assert p["status"] == q["status"] == "HUMAN_INPUT"
    assert p["covered_pilot_soc"] == [0.1]
    assert p["expanded_soc_support"] == [0.1, 0.2, 0.3]
    assert p["expanded_execution"] == "HOLD_PENDING_COVERAGE"
    assert sum(p["expanded_soc_mass"]) == pytest.approx(1)
    assert (
        sum(
            q[name] for name in ("interior_mass", "safety_edge_mass", "value_edge_mass")
        )
        == 1
    )
    assert q["registered_refinement_bands"] is None
    assert w["Q_is_fleet_mix"] is False
    assert p["arbitrary_initial_soh_supported"] is False


def test_one_map_and_forward_none_rule_do_not_weaken_t1_or_exposure():
    question = SHEET["question"]
    assert question["kind"] == "ONE_COMPLETE_FIVE_BAND_MAP"
    assert question["k"] == {
        "status": "HUMAN_INPUT",
        "registered": None,
        "recommendation": 8,
    }
    assert question["exposure_E"]["registered"] is None
    assert question["new_requirements_renew_exposure"] is False
    policy = question["none_feasible_policy"]
    assert policy["registered"] is None
    assert policy["redraw"] is policy["uncertain_is_none"] is False
    assert policy["T1_seam"] == "GATE_OWNER_DECISION_REQUIRED_NO_WEAKENING"
    assert "HUMAN_INPUT" in TEXT and "do not weaken T1" in TEXT


def test_tier4_and_nominal_audit_are_not_the_same_acceptance_identity():
    tier = SHEET["tier4"]
    assert tier["T40_contains_excluded_cooling"] == [3, 6]
    assert tier["other_bands_in_tier4_summary"] is False
    for band in ("T5", "T40"):
        row = tier[band]
        assert row["feasible"] + row["infeasible"] + row["unresolved"] == row["actions"]
        assert row["infeasible_within_two_bands"] <= row["infeasible_within_five_bands"]
    audit = SHEET["nominal_export_audit"]
    assert sum(row["rows"] for row in audit["bands"]) == 493
    for row in audit["bands"]:
        assert row["rows"] == row["feasible"] + row["infeasible"] + row["unresolved"]
    assert audit["historical_off_lattice_rows"] == 9
    assert audit["unresolved_question_comparisons"] == audit["questions"] == 25
    assert audit["adopted_law_truth"] is False
    assert audit["T2a_by_band"] == ["NOT_DEMONSTRATED"] * 5
    assert audit["bands"][0]["feasible"] != tier["T5"]["feasible"]


def test_diversity_and_cost_arithmetic_do_not_manufacture_power():
    question = SHEET["question"]
    assert question["expected_distinct_winners_by_band"] == [None] * 5
    assert question["mix_only_pick_changes"] == 0
    assert question["search_query_count"] == "SUM_B_N_B"
    # Synthetic two-answer bank: expected occupancy, not measured battery P.
    masses, k = [0.5, 0.5], 8
    occupancy = sum(1 - (1 - mass) ** k for mass in masses)
    assert occupancy == pytest.approx(1.9921875)
    assert occupancy < min(k, len(masses))
    grid = SHEET["audit_grid"]
    assert (
        len(grid["temperature_caps_c"]) * len(grid["retention_floors"])
        == grid["vectors"]
        == 4
    )
    assert grid["role"] == "AUDIT_ONLY"


def test_previous_numeric_sheet_and_cross_links_are_preserved():
    original = json.loads(
        (LAW / "battery-ambient-indexed-v3.json").read_text(encoding="utf-8")
    )
    assert original["schema"] == "carbon.battery-ambient-question-law.proposal.v3"
    assert original["cost"]["total_public_action_contexts"] == 414
    assert original["public_evidence"]["all_band_optima_settled"] is False
    for filename in ("README.md", "battery-ambient-indexed-v3.md"):
        assert "battery-v3-round2.md" in (LAW / filename).read_text(encoding="utf-8")
