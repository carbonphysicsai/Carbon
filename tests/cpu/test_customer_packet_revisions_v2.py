"""Prospective document consistency; no solver, runtime migration or real truth."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKETS = ROOT / "docs/development/challenge_pipeline/round1"
LAWS = PACKETS.parent / "question-laws"
REQUIREMENTS = json.loads(
    (PACKETS / "first-three-requirements-v2.json").read_text(encoding="utf-8")
)
AMENDMENT = json.loads((LAWS / "proposals-v2.json").read_text(encoding="utf-8"))
BASE_LAW = json.loads((LAWS / "proposals.json").read_text(encoding="utf-8"))
IMPACT = (LAWS / "quiz-impact-v2.md").read_text(encoding="utf-8")
SECTIONS = [
    "Engineering job",
    "Physical system",
    "Population P, Q and w",
    "Case contract",
    "Reference policy",
    "Output and measurement contract",
    "Construction contract",
    "Research kit",
    "Evidence plan",
    "Readiness and claim record",
]


def _lf_hash(path):
    # Git text checkout line endings vary. Pin the UTF-8/LF document content,
    # not Windows CRLF or Linux LF representation of the same historical text.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _row(challenge):
    return next(r for r in AMENDMENT["challenges"] if r["challenge"] == challenge)


def test_amendment_has_no_runtime_scientific_or_execution_authority():
    assert REQUIREMENTS["schema"] == "carbon.mock-customer-planning.first-three.v2"
    assert AMENDMENT["schema"] == "carbon.question-law.amendment.v2"
    assert (
        REQUIREMENTS["authority"]
        == AMENDMENT["authority"]
        == ("OWNER-BATTERY-COOLING-PACKETS-02")
    )
    for key in (
        "dispatch_ready",
        "official_scoring",
        "scientific_qualification",
        "protocol_transition",
        "historical_rescore",
        "protected_material",
    ):
        assert REQUIREMENTS[key] is False
    assert REQUIREMENTS["spend_grant"] is None
    assert AMENDMENT["runtime_registration"] is False
    assert AMENDMENT["historical_rescore"] is False
    assert AMENDMENT["maturity"] == REQUIREMENTS["maturity"] == "SPECIFIED"


def test_six_historical_documents_are_preserved_by_content_identity():
    for item in REQUIREMENTS["unchanged_historical_files"]:
        assert _lf_hash(PACKETS / item["file"]) == item["sha256_lf_utf8"]
    for key in ("base", "historical_quiz"):
        pin = AMENDMENT[key]
        assert _lf_hash(LAWS / pin["file"]) == pin["sha256_lf_utf8"]
    pin = REQUIREMENTS["base"]
    assert _lf_hash(PACKETS / pin["file"]) == pin["sha256_lf_utf8"]


def test_only_battery_and_cooling_law_rows_are_replaced():
    replacements = {r["challenge"]: r for r in AMENDMENT["challenges"]}
    assert len(replacements) == len(AMENDMENT["challenges"]) == 2
    assert set(replacements) == {"battery", "cooling-cell"}
    merged = [replacements.get(r["challenge"], r) for r in BASE_LAW["challenges"]]
    assert len(merged) == 8
    unaffected = set(AMENDMENT["unchanged_challenges"])
    assert len(unaffected) == 6
    for old, new in zip(BASE_LAW["challenges"], merged, strict=True):
        if old["challenge"] in unaffected:
            assert new == old
        else:
            assert new["packet_version"] == "v2"
    assert REQUIREMENTS["packets"]["motor"]["change"] == "NONE"
    # Common P/Q/w and historical measured costs are inherited, not overridden.
    assert "common" not in AMENDMENT
    assert "historical_measured_cost" not in AMENDMENT


@pytest.mark.parametrize("name", ["battery", "cooling-cell"])
def test_v2_packets_keep_ten_sections_valid_links_and_scope(name):
    path = PACKETS / REQUIREMENTS["packets"][name]["file"]
    text = path.read_text(encoding="utf-8")
    assert re.findall(r"^## (\d+)\. (.+)$", text, re.MULTILINE) == [
        (str(i), title) for i, title in enumerate(SECTIONS, 1)
    ]
    for phrase in ("Role-play", "DEVELOPMENT", "HUMAN_INPUT", "UNRESOLVED"):
        assert phrase in text
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if not target.startswith("https://"):
            assert (path.parent / target.split("#", 1)[0]).is_file(), target
    assert "sealed journal" in text or "journal14" in text
    assert REQUIREMENTS["packets"][name]["reference_adequacy"] == (
        "NOT_DEMONSTRATED_FOR_V2_COMPLETE_BUYER_DECISION"
    )


def test_battery_time_is_objective_and_discharge_heat_is_not_a_charge_gate():
    packet = REQUIREMENTS["packets"]["battery"]
    objective, limits = packet["objective"], packet["hard_limits"]
    assert objective["sense"] == "min" and objective["unit"] == "min"
    assert objective["hard_max"] is None
    assert limits["charging_temperature_c_max"] == 45
    assert limits["charging_temperature_scope"] == (
        "ALL_CC_CV_CHARGE_LEGS_IN_DECLARED_PROGRAMME"
    )
    assert limits["every_charge_plating_reaction_overpotential_v_min"] == 0
    assert limits["programme_terminal_voltage_v_max"] == 4.2
    assert limits["q30_over_q1_min"] == 0.99
    assert "test_discharge_temperature_extrema" in packet["diagnostics"]
    assert "whole_programme_temperature_extrema_with_phase_cycle_time" in (
        packet["diagnostics"]
    )
    assert packet["optional_cooling"]["selected_multiplier"] is None
    assert packet["optional_cooling"]["role"] == "OPTIONAL_REPORTED_ACTION"
    timing = packet["timing"]
    assert timing["initial_rest_s_included"] == 120
    assert timing["initial_soc"] == 0.1 and timing["target_soc"] == 0.8
    assert "CHARGE_INTEGRAL" in timing["observer"]
    assert "UNRESOLVED" in timing["missing_crossing"]


def test_reported_battery_best_and_corrected_observation_are_distinct():
    report = REQUIREMENTS["packets"]["battery"]["reported_feasibility"]
    assert report["head"] == "031284d1a6f8c56f1355606908feaa737b5b9a86"
    assert report["solves"] == 435 and report["ambient_c"] == 25
    assert report["old_brief_verdict"] == "NO_VERIFIED_FEASIBLE_PROTOCOL"
    assert report["best_within_limits_min"] == 32.9
    assert report["superseded_voltage_probe_report_min"] == 35.6
    assert report["probe_interval_s"] == 30
    assert report["corrected_charge_integral_observation_min"] == 63.3
    assert report["corrected_observation_is_bank_minimum"] is False
    assert "NOT_REPLAYED_BY_CODEX" in report["source_kind"]


def test_cooling_maps_and_unselected_alternatives_stay_explicitly_missing():
    packet = REQUIREMENTS["packets"]["cooling-cell"]
    assert packet["hard_thermal_limit_c"] == 85
    assert packet["heat_map_plane"] == (
        "COLD_PLATE_INTERFACE_AFTER_DIE_SIDE_SPREADER_OR_LID"
    )
    assert packet["spreader_properties"] is None
    assert packet["post_spreader_heat_map_manifest"] is None
    assert len(packet["required_buyer_inputs"]) == 6
    assert set(packet["selected_alternatives"].values()) == {None}
    assert packet["alternative_policy"] == (
        "REPORT_TIM_RATIO_INLET_ALTERNATIVES_WITHOUT_SELECTING"
    )
    assert packet["assembly_limits_inherited"] is False
    assert "NOT_DIE_JUNCTION" in packet["thermal_claim"]
    assert "NO_FULL_COLD_PLATE" in packet["scope"]


def test_uniform_witness_and_approximate_budget_are_not_a_hotspot_panel_pass():
    report = REQUIREMENTS["packets"]["cooling-cell"]["reported_feasibility"]
    assert report["head"] == "3ab30becb6dcee0a2ec43272883c2800fb32a64a"
    assert report["solves"] == 128
    assert report["uniform_best_c"] == 81.2
    assert report["uniform_stratum_feasible"] is True
    assert report["reported_hotspot_minimum_c"] == 117
    assert report["hotspot_minimum_op"] == ">="
    assert report["complete_panel_feasibility_demonstrated"] is False
    assert report["post_spreader_truth_demonstrated"] is False
    available = 85 - report["inlet_context_c"] - report["approximate_local_tim_jump_k"]
    assert available == report["approximate_available_plate_rise_k"] == 15
    assert available < report["approximate_best_plate_rise_k"] == 28
    # This component budget is not a reconstruction of the reported117C peak.
    assert 45 + 25 + 28 != report["reported_hotspot_minimum_c"]


@pytest.mark.parametrize("challenge", ["battery", "cooling-cell"])
def test_law_grids_continuous_variants_and_costs_remain_proposals(challenge):
    row = _row(challenge)
    for axis in row["requirement_axes"]:
        assert axis["status"] == "HUMAN_INPUT" and axis["registered"] is None
        assert axis["recommendation"] == sorted(set(axis["recommendation"]))
        interval = axis["continuous_interval"]
        assert interval["status"] == "HUMAN_INPUT"
        assert interval["registered"] is None
        assert interval["recommendation"] == [
            min(axis["recommendation"]),
            max(axis["recommendation"]),
        ]
    assert row["raw_question_grid_upper_bound"] == math.prod(
        len(a["recommendation"]) for a in row["requirement_axes"]
    )
    for field in ("service_contexts", "objective", "questions_per_batch"):
        assert row[field]["status"] == "HUMAN_INPUT"
        assert row[field]["registered"] is None
    assert row["revised_bank_cpu_hours"] is None
    assert row["distinct_answer_changing_questions"] is None
    assert row["distinct_best_picks"] is None
    continuous = row["continuous_variant"]
    for field in (
        "expected_distinct_winners_P",
        "expected_distinct_winners_Q",
        "close_call_rate_P",
        "close_call_rate_Q",
        "residual_unresolved_rate",
    ):
        assert continuous[field] is None
    assert continuous["report_status"] == "NOT_DEMONSTRATED"


def test_battery_grid_loses_time_cap_without_promising_eight_distinct_questions():
    row = _row("battery")
    assert {a["quantity"] for a in row["requirement_axes"]} == {
        "charging_temperature_max",
        "capacity_ratio_min",
    }
    assert row["raw_question_grid_upper_bound"] == 4
    assert row["owner_selected_packet_objective"]["hard_max"] is None
    assert "not eight distinct grid" in row["grid_batch_caveat"]
    assert "UNRESOLVED" in row["support_gate"]
    assert _row("cooling-cell")["raw_question_grid_upper_bound"] == 9
    assert _row("cooling-cell")["questions_per_batch"]["recommendation"] == 8


def test_synthetic_decision_example_does_not_reinstate_a_deadline_or_drop_safety():
    # Entirely invented toy numbers, NOT the reported physical protocols.
    bank = [
        {"id": "safe-slower", "minutes": 40, "charge_c": 44, "discharge_c": 54},
        {"id": "unsafe-fast", "minutes": 20, "charge_c": 46, "discharge_c": 40},
        {"id": "safe-faster", "minutes": 34, "charge_c": 43, "discharge_c": 50},
    ]
    eligible = [r for r in bank if r["charge_c"] <= 45]
    assert min(eligible, key=lambda r: r["minutes"])["id"] == "safe-faster"
    assert all(r["minutes"] > 30 for r in eligible)
    assert all(r["discharge_c"] > 45 for r in eligible)


def test_impact_flags_changed_keys_without_modifying_motor_or_historical_quizzes():
    normalized = " ".join(IMPACT.split())
    for phrase in (
        "Content change required",
        "Motor content is unchanged",
        "No time-cap axis",
        "30 minutes is not a feasibility boundary",
        "No redraws",
        "MIGRATION_REQUIRED",
        "Charging",
        "post-spreader",
        "validators never solve references",
        "(a) Optimizer stability",
        "(b) Grid resolution",
        "(c) Power by k",
        "(d) Agreement with decision value",
        "(e) Unresolved rate",
    ):
        assert phrase in normalized
    for filename in ("README.md", "reference-credibility.md"):
        index = (PACKETS / filename).read_text(encoding="utf-8")
        assert "battery-ev-fast-charge-v2.md" in index
        assert "cooling-cell-v2.md" in index
    assert "proposals-v2.json" in (LAWS / "README.md").read_text(encoding="utf-8")
