"""Owner-required readiness specifications; no reference or hidden execution."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/development/challenge_pipeline"
LAWS = DOCS / "question-laws"
PACKETS = DOCS / "round1"
SHEET = json.loads((LAWS / "value-check-v1.json").read_text(encoding="utf-8"))
TEXT = (LAWS / "value-check-v1.md").read_text(encoding="utf-8")


def test_owner_prerequisite_does_not_claim_runtime_or_execution_authority():
    assert SHEET["authority"] == "OWNER-DESIGN-VALUE-01"
    assert SHEET["maturity"] == "SPECIFIED"
    assert SHEET["prerequisite"] == "OWNER_REQUIRED_BEFORE_NEW_HIDDEN_BANK_CONSTRUCTION"
    for flag in (
        "runtime_enforced",
        "dispatch_ready",
        "runtime_registration",
        "protected_material",
        "historical_rescore",
    ):
        assert SHEET[flag] is False
    for missing in ("spend_grant", "validator_permit", "accepted_value_receipt"):
        assert SHEET[missing] is None


def test_four_checks_have_per_stratum_and_joint_semantics():
    assert set(SHEET["checks"]) == {"A", "B", "C", "D"}
    assert SHEET["checks"]["A"].endswith("EACH_STRATUM")
    assert SHEET["checks"]["B"].endswith("EACH_STRATUM")
    assert "ALL_MANDATORY_STRATA" in SHEET["checks"]["C"]
    assert "STRATA_OR_QUESTION_DRAWS" in SHEET["checks"]["D"]
    numeric = SHEET["numeric_acceptance"]
    assert numeric["status"] == "HUMAN_INPUT"
    assert numeric["pass_fraction_recommendation"] == [0.2, 0.8]
    assert numeric["cooling_margin_spread_recommendation_k"] == 5
    for field in (
        "registered_pass_fraction_range",
        "registered_minimum_coverage",
        "registered_answer_change_threshold",
        "near_band_policy",
    ):
        assert numeric[field] is None


@pytest.mark.parametrize("row", SHEET["challenges"], ids=lambda row: row["challenge"])
def test_every_current_packet_has_readiness_and_unadopted_buyer_units(row):
    text = (PACKETS / row["packet"]).read_text(encoding="utf-8")
    sections = re.findall(r"^## (\d+)\. (.+)$", text, re.MULTILINE)
    assert [int(number) for number, _ in sections] == list(range(1, 11))
    readiness = text.split("## 10.", 1)[1]
    assert "value-check-v1.md" in readiness
    assert "HUMAN_INPUT" in readiness
    assert "NOT_DEMONSTRATED" in readiness
    assert row["numeric_status"] == "HUMAN_INPUT"
    assert row["registered_spread"] is row["accepted_value_receipt"] is None
    assert row["readiness"] == "NOT_DEMONSTRATED"
    assert row["spread_recommendation"] > 0
    assert row["value_unit"]


def test_eight_challenges_do_not_share_a_temperature_unit_or_earned_clearance():
    rows = SHEET["challenges"]
    assert len(rows) == len({row["challenge"] for row in rows}) == 8
    assert len({row["value_unit"] for row in rows}) == 8
    assert all(row["accepted_value_receipt"] is None for row in rows)
    assert "None of the eight" in TEXT


def test_cooling_owner_plane_and_lid_are_selected_but_final_inputs_are_not():
    selected = SHEET["cooling_owner_selection"]
    assert selected["status"] == "OWNER_SELECTED_DEVELOPMENT_CONDITIONAL_ON_VALUE"
    assert selected["limit_c"] == 85
    assert selected["plane"] == "LID_SIDE_TIM2_INTERFACE"
    assert selected["lid_class"] == "VAPOUR_CHAMBER"
    assert selected["die_tim1_role"] == "DIAGNOSTIC"
    assert selected["final_parameters"] is None
    packet = (PACKETS / "cooling-cell-v3.md").read_text(encoding="utf-8")
    assert "OWNER-DESIGN-VALUE-01" in packet
    assert "vapour-chamber" in packet


def test_cheap_preflight_cannot_release_or_reuse_the_old_copper_recipe():
    preflight = SHEET["cooling_preflight"]
    panel = json.loads((PACKETS / "cooling-spreader-panel-v2.json").read_text())
    budget = json.loads((PACKETS / "cooling-thermal-budget-v2.json").read_text())
    assert preflight["owner"] == "DATA_COLLECTION"
    assert preflight["route"] == "EXISTING_PUBLIC_RESULTS_AND_CHEAP_LID_MODEL_PRE_SOLVE"
    assert preflight["new_large_cfd_allowed"] is False
    assert preflight["candidate_count_recommendation"] == [2, 3]
    assert preflight["final_parameter_owner"] == "HUMAN_OWNER"
    assert preflight["old_panel_logical_jobs"] == 53
    assert panel["recommendation"]["total_logical_jobs"] == 53
    assert panel["recommendation"]["lid"]["material"] == "C11000_COPPER"
    assert "REQUIRES_REVISION" in panel["recipe_status"]
    assert (
        budget["budget_stack_status"]
        == "HISTORICAL_COPPER_SCREEN_NOT_VAPOUR_CHAMBER_TRUTH"
    )
    assert preflight["panel_hold"] == panel["panel_hold"] == budget["panel_status"]
    assert preflight["panel_hold"] == "HOLD_SPREADING_AND_VALUE_CHECK"
    assert preflight["panel_release"] is panel["budget_release"] is None
    assert budget["panel_release"] is None
    assert panel["dispatch_ready"] is False
    for field in ("accepted_spreading_receipt", "accepted_value_receipt"):
        assert panel[field] is preflight[field] is None
    assert "CASE_PLANE_BUYER_LEVERS" in preflight["failure_action"]


def test_inlet_search_does_not_clamp_or_claim_broader_pg25_support():
    preflight = SHEET["cooling_preflight"]
    assert preflight["requested_inlet_range_c"] == [25, 45]
    assert preflight["registered_search_inlet_range_c"] == [30, 45]
    assert preflight["current_pg25_inlet_support_min_c"] == 30
    assert preflight["below_support_outcome"] == "UNSUPPORTED_NOT_CLAMPED"
    assert "property, flow and local response changes need coverage" in TEXT


def test_public_value_audit_reports_partial_checks_not_a_green_map():
    audit = SHEET["audit"]["battery_v3"]
    assert audit["lane"] == "with_cooling"
    bands = audit["bands"]
    assert [row["band_c"] for row in bands] == [5, 15, 25, 35, 40]
    for row in bands:
        assert row["resolved"] == row["actions"] - row["unresolved"]
        assert 0 < row["feasible"] <= row["resolved"]
    within = [
        row["band_c"]
        for row in bands
        if 0.2 <= row["feasible"] / row["resolved"] <= 0.8
    ]
    assert within == [15]
    assert [row["feasible"] / row["resolved"] for row in bands] == pytest.approx(
        [3 / 41, 11 / 39, 16 / 131, 15 / 132, 3 / 36]
    )
    assert audit["whole_gate"] == audit["B"] == "NOT_DEMONSTRATED"
    assert audit["C"].startswith("REPORTED_COMPLETE_FEASIBLE_MAP_AT_STUDY_INPUTS")
    assert "NOT_SETTLED" in audit["D"]
    assert audit["complete_action"] == "FIVE_BAND_MAP_NOT_ONE_SHARED_PROTOCOL"
    assert audit["mix_only_pick_changes"] == 0


def test_motor_registry_is_not_treated_as_final_value_outcomes():
    motor = SHEET["audit"]["motor"]
    assert motor["revised_bank"] == "10P12S_MULTI_SLICE_SKEW"
    assert "NO_PUBLISHED_FINAL_OUTCOME_SUMMARY" in motor["current_evidence"]
    assert set(motor["checks"]) == {"A", "B", "C", "D"}
    assert set(motor["checks"].values()) == {"NOT_DEMONSTRATED"}
    assert motor["whole_gate"] == "NOT_DEMONSTRATED"


def test_custody_exposure_and_forward_none_feasible_are_preserved():
    custody = SHEET["custody"]
    assert (
        custody["witness_source"]
        == "SEPARATE_PUBLIC_NON_HIDDEN_OR_RETIRED_PUBLISHED_BANK"
    )
    assert custody["hidden_tuning_allowed"] is False
    assert custody["redraw_none_feasible"] is False
    assert custody["threshold_variation_resets_exposure"] is False
    for phrase in (
        "P population and Q diagnostic",
        "w cannot make",
        "PASS/(PASS+FAIL)",
        "NEAR rates",
        "tie-break-only ID change",
        "already sealed",
        "Reference failure is missing evidence",
    ):
        # Historical-result preservation is stated with a different phrase.
        if phrase == "already sealed":
            assert "sealed results retain" in TEXT
        else:
            assert phrase in TEXT


def test_pinned_cooling_history_and_battery_law_are_unchanged():
    for relative, digest in (
        (
            "round1/cooling-cell-v2.md",
            "885c88ab5985b320972b51ba41ff4fc10dd8f5de331743b252b1acdb85f2fb84",
        ),
        (
            "question-laws/battery-continuous-v3.json",
            "45e67ea9bd4bcdba7c71d72f51f16ae03817361d3db8d79c2fad76efa2d5b630",
        ),
    ):
        content = (DOCS / relative).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == digest


def test_822_note_keeps_the_original_math_and_appends_owner_resolution():
    note = (
        ROOT / ".agent/decisions/2026-10-08-COOLING-THERMAL-BUDGET-04.md"
    ).read_text(encoding="utf-8")
    before, after = note.split("## Prospective owner resolution, 2026-10-08")
    assert "97.96 C" in before and "115.09-C" in before
    assert "smallest\nowner decision" in before
    assert "OWNER-DESIGN-VALUE-01" in after
    assert "vapour-chamber" in after
    assert "Panel release remains null" in after


def test_indexes_and_local_links_resolve_to_the_current_readiness_versions():
    assert "value-check-v1.md" in (LAWS / "README.md").read_text(encoding="utf-8")
    index = (PACKETS / "README.md").read_text(encoding="utf-8")
    assert "cooling-cell-v3.md" in index
    assert "motor-precision-joint-v2.md" in index
    paths = [LAWS / "value-check-v1.md"] + [
        PACKETS / row["packet"] for row in SHEET["challenges"]
    ]
    for path in paths:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if not target.startswith(("https://", "http://", "#")):
                assert (path.parent / target.split("#")[0]).is_file(), (path, target)
