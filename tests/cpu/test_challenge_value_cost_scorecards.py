"""Static proposal consistency, not measured value, cost or scientific clearance."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "docs/development/challenge_pipeline"
DOCS = PIPELINE / "value-cost"
SHEET = json.loads((DOCS / "analysis.json").read_text(encoding="utf-8"))
CARDS = SHEET["cards"]
NAMES = {"battery", "motor", "cooling-cell", "f02", "f06", "f08", "f13", "f17"}


def test_owner_framework_is_a_line_ending_normalized_copy_not_reinterpreted():
    content = (DOCS / "README.md").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == (
        "4f0496f14b3d8180e990ebb6d9193e1669d615a78875efbba9c10ab210ad3509"
    )


def test_analysis_cannot_dispatch_or_clear_an_unmeasured_challenge():
    assert SHEET["maturity"] == "SPECIFIED"
    assert SHEET["adoption"] == "HUMAN_INPUT"
    assert SHEET["overall_keep"] == "NOT_DEMONSTRATED"
    assert SHEET["ranking"] == "UNCOMPUTABLE"
    for flag in (
        "runtime_enforced",
        "dispatch_ready",
        "protected_material",
        "historical_rescore",
    ):
        assert SHEET[flag] is False
    assert SHEET["spend_grant"] is SHEET["accepted_value_receipt"] is None
    assert set(CARDS) == NAMES
    assert len(SHEET["source_main"]) == len(SHEET["public_evidence_head"]) == 40


@pytest.mark.parametrize("name", sorted(NAMES))
def test_card_has_all_criteria_sources_and_current_packet(name):
    card = CARDS[name]
    text = (DOCS / card["file"]).read_text(encoding="utf-8")
    assert re.findall(r"^### ([VTC]\d)\b", text, re.MULTILINE) == [
        *[f"V{i}" for i in range(1, 6)],
        *[f"T{i}" for i in range(1, 6)],
        *[f"C{i}" for i in range(1, 5)],
    ]
    assert len(set(card["workflow_authors"])) >= 2
    # A shared publisher can host independent authors (e.g. Dinex on COMSOL).
    # Link count is structural only; it does not certify source independence.
    v1 = text.split("### V1", 1)[1].split("### V2", 1)[0]
    assert len(re.findall(r"\]\(https://", v1)) >= 2
    assert "HUMAN_INPUT" in text and "NOT_DEMONSTRATED" in text
    packet = (PIPELINE / "round1" / card["packet"]).read_text(encoding="utf-8")
    readiness = packet.split("## 10.", 1)[1]
    assert f"../value-cost/{name}.md" in readiness


@pytest.mark.parametrize("name", sorted(NAMES))
def test_low_base_high_is_assumed_gross_not_inflated_or_net(name):
    value = CARDS[name]["buyer_value"]
    assert value["status"] == "ASSUMPTION"
    assert value["net_value"] == "NOT_DEMONSTRATED"
    assert value["currency"] == "USD"
    before = value["before_units"]
    rates = value["unit_rate"]
    assert len(before) == len(rates) == 3
    assert before == sorted(before) and all(x > 0 for x in before + rates)
    assert value["before_gross"] == pytest.approx(
        [units * rate for units, rate in zip(before, rates)]
    )
    if value["after_units"] is not None:
        after = value["after_units"]
        assert value["after_gross"] == pytest.approx(
            [units * rate for units, rate in zip(after, rates)]
        )
        assert all(new <= old for new, old in zip(after, before))
    else:
        assert value["after_gross"] is None


@pytest.mark.parametrize("name", sorted(NAMES))
def test_no_proposal_earns_tiers_power_cost_or_relaxes_safety(name):
    card = CARDS[name]
    assert card["overall_keep"] == card["t3"] == card["t4"] == "NOT_DEMONSTRATED"
    assert card["workflow_evaluation_count"] == "SOURCED_ANALOGUE_WITH_ASSUMED_TRANSFER"
    assert card["credibility"] == {
        "target_tier": 2,
        "earned_tier": None,
        "accepted_witness_receipt": None,
    }
    assert card["safety_before"] == card["safety_after"]
    cost = card["cost"]
    assert cost["bank_size_adopted"] is False
    for field in (
        "complete_case_p50_cpu_h",
        "complete_case_p95_cpu_h",
        "peak_ram_gib",
        "startup_bill",
        "ongoing_cpu_h",
        "validator_measurement",
    ):
        assert cost[field] is None


def test_boundary_coverage_is_not_a_fraction_gate_or_exposure_renewal():
    t2 = SHEET["t2"]
    assert t2["minimum_feasible"] == t2["minimum_near_infeasible"] == 5
    assert t2["near_definition"] == "ONE_REGISTERED_REFINEMENT_BAND"
    assert t2["fraction_role"] == "DIAGNOSTIC_NOT_GATE"
    assert t2["numeric_acceptance"] == "HUMAN_INPUT"
    assert t2["prune_for_fraction"] is False
    assert t2["redraw_none_feasible"] is False
    assert t2["thresholds_reset_exposure"] is False
    bands = SHEET["battery_bands"]
    assert [row["band_c"] for row in bands] == [5, 15, 25, 35, 40]
    assert [row["band_c"] for row in bands if row["feasible"] < 5] == [5, 40]
    assert all(row["near_infeasible"] is None for row in bands)
    assert all(row["t2"] == "NOT_DEMONSTRATED" for row in bands)
    assert [row["feasible"] / row["resolved"] for row in bands] == pytest.approx(
        [3 / 41, 11 / 39, 16 / 131, 15 / 132, 3 / 36]
    )


def test_nine_f02_actions_cannot_supply_ten_distinct_boundary_actions():
    coverage = SHEET["f02_action_coverage"]
    needed = SHEET["t2"]["minimum_feasible"] + SHEET["t2"]["minimum_near_infeasible"]
    assert coverage["original_actions"] == 9 < needed
    assert coverage["necessary_minimum_distinct_actions"] == needed == 10
    assert coverage["illustrative_proposed_actions"] >= needed
    assert coverage["proposal_adopted"] is False
    assert (
        CARDS["f02"]["cost"]["bank_primary_units"]
        == (coverage["illustrative_proposed_actions"] * coverage["contexts"])
        == 384
    )


def test_route_only_changes_do_not_invent_a_buyer_scope_sacrifice():
    for name in ("f08", "f17"):
        card = CARDS[name]
        assert card["reframe"] == "PROPOSED_REFERENCE_ONLY"
        value = card["buyer_value"]
        assert value["before_units"] == value["after_units"]
        assert value["before_gross"] == value["after_gross"]
    f17 = (DOCS / "f17.md").read_text(encoding="utf-8")
    assert "original packet already has fixed repeated grooves" in f17
    assert "Concentration is NOT forced periodic" in f17
    f13 = (DOCS / "f13.md").read_text(encoding="utf-8")
    assert "conditional on an evidenced original-route T/C failure" in f13


def test_budget_node_hours_are_sensitivity_not_measured_cpu_conversion():
    budget = SHEET["budget"]
    assert budget["currency"] == "EUR"
    assert budget["status"] == "ASSUMPTION_NOT_QUOTE_OR_GRANT"
    assert budget["wall_equals_cpu"] == "ILLUSTRATIVE_SERIAL_SCENARIO_NOT_MEASURED"
    available = budget["startup_ceiling"] - budget["overhead_sensitivity_reserve"]
    node_hours = available / budget["working_rate_per_node_hour"]
    assert node_hours == pytest.approx(58.3941605839)
    # Break-even complete-case targets, never facts about wall time or memory.
    expected_minutes = {
        "battery": 7.007299,
        "motor": 1.946472,
        "cooling-cell": 3.503650,
        "f02": 9.124088,
        "f06": 13.686131,
        "f08": 13.686131,
        "f13": 218.978102,
        "f17": 77.858881,
    }
    for name, minutes in expected_minutes.items():
        units = CARDS[name]["cost"]["bank_primary_units"]
        assert node_hours / units * 60 == pytest.approx(minutes, abs=0.00001)
    two_hour_silencer_scenario = 2 * 16 * budget["working_rate_per_node_hour"]
    assert two_hour_silencer_scenario == pytest.approx(43.84)
    assert two_hour_silencer_scenario + 20 < budget["startup_ceiling"]
    assert 8 * budget["ongoing_ax42_fraction_ceiling"] > 1


def test_power_and_witness_custody_do_not_assume_independent_fresh_windows():
    assert SHEET["power"]["cross_batch_evidence"] is None
    assert SHEET["power"]["independent_windows_assumed"] is False
    assert SHEET["power"]["remaining_exposure_required"] is True
    assert SHEET["custody"]["protected_witness_allowed"] is False
    assert SHEET["custody"]["sealed_reference_revised"] is False
    text = (DOCS / "analysis.md").read_text(encoding="utf-8")
    for phrase in (
        "1-(1-p)^windows",
        "remaining E",
        "No EVAL/STRESS/quiz/tuning",
        "not automatic replacement",
        "sealed results",
        "UNCOMPUTABLE",
    ):
        assert phrase in text


def test_historical_packets_and_laws_are_not_silently_rescored():
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
        content = (PIPELINE / relative).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == digest


def test_all_local_links_resolve_and_current_indexes_supersede_fraction_gate():
    for path in DOCS.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if not target.startswith(("http://", "https://", "#")):
                assert (path.parent / target.split("#")[0]).is_file(), (path, target)
    for index in (
        PIPELINE / "question-laws/README.md",
        PIPELINE / "question-laws/value-check-v1.md",
        PIPELINE / "round1/README.md",
    ):
        assert "../value-cost/" in index.read_text(encoding="utf-8")
