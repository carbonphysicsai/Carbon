"""Contingency document consistency, not buyer, solver or cost qualification."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/development/challenge_pipeline/value-cost/replacements"
SHEET = json.loads((DOCS / "scenarios.json").read_text(encoding="utf-8"))
NAMES = (
    "bolted-joint",
    "seal-gland",
    "snap-fit",
    "solenoid-pole",
    "duct-fitting",
    "air-heat-sink",
)


def test_six_inactive_recommendations_do_not_replace_or_dispatch():
    assert SHEET["ticket"] == "REPLACEMENT-CANDIDATES-01"
    assert SHEET["maturity"] == "SPECIFIED"
    assert SHEET["adoption"] == "HUMAN_INPUT"
    assert SHEET["runtime_ids_activated"] == []
    assert SHEET["solver_runs"] == 0 and SHEET["spend_grant"] is None
    for key in (
        "dispatch_ready",
        "protected_material",
        "historical_rescore",
        "framework_modified",
    ):
        assert not SHEET[key]
    assert set(SHEET["cards"]) == set(NAMES)
    assert SHEET["commercial_floor_eur"] == 0
    assert SHEET["near_frontier_working_bands"] == 2
    assert "Test Lead working value" in SHEET["near_frontier_owner"]
    for slot in ("f08", "cooling-cell"):
        cards = [c for c in SHEET["cards"].values() if c["slot"] == slot]
        assert sorted(c["rank_within_slot"] for c in cards) == [1, 2, 3]


@pytest.mark.parametrize("name", NAMES)
def test_buyer_sources_and_baseline_are_visible_not_earned_passes(name):
    card = SHEET["cards"][name]
    text = (DOCS / f"{name}.md").read_text(encoding="utf-8")
    assert text.index("Strongest cheap baseline first") < text.index("## V1")
    assert card["baseline"]
    assert len({s["author"] for s in card["sources"]}) >= 2
    assert len({s["url"] for s in card["sources"]}) >= 2
    for source in card["sources"]:
        assert source["support"] and source["url"] in text
    assert card["v1"] == "SOURCED_DESK_SCREEN"
    assert card["v2"] == "LABELLED_SCENARIO_NOT_REALIZED"
    assert card["v3"] == "LABELLED_SCENARIO_NOT_OBSERVED"
    assert card["baseline_advantage"] == "NOT_DEMONSTRATED"
    assert card["earned_tier"] == "NOT_DEMONSTRATED"
    assert card["target_tier"] == 2
    assert card["replacement_decision"] == "OWNER_RESERVED"
    assert card["t1_t5"] == "NOT_DEMONSTRATED"
    assert "HUMAN_INPUT" in text and "Reject if" in text


@pytest.mark.parametrize("name", NAMES)
def test_gross_effort_and_conditional_volume_are_auditable_not_traction(name):
    card = SHEET["cards"][name]
    value = SHEET["value_assumptions"]
    assert value["status"] == "ASSUMPTION_CONDITIONAL_COHORT_NOT_MARKET"
    assert value["observed_annual_decisions"] is None
    assert value["realized_benefit_eur"] is None
    assert value["adoption_rate"] is None
    assert card["realized_annual_eur"] is None
    per_revision = [
        hours * rate
        for hours, rate in zip(
            card["engineer_h_per_revision"], value["engineer_eur_per_h"]
        )
    ]
    revisions = [
        teams * cadence
        for teams, cadence in zip(card["teams"], card["revisions_per_team_year"])
    ]
    assert card["gross_eur_per_revision"] == pytest.approx(per_revision)
    assert card["annual_revisions"] == revisions
    assert card["conditional_annual_gross_eur"] == pytest.approx(
        [units * euros for units, euros in zip(revisions, per_revision)]
    )


@pytest.mark.parametrize("name", NAMES)
def test_complete_case_costs_include_refinement_failures_both_witness_tools(name):
    card, cost = SHEET["cards"][name], SHEET["cost_assumptions"]
    assert card["c1_status"] == "HYPOTHESIS_NOT_MEASURED"
    assert card["complete_case_p50_cpu_h"] is None
    assert card["complete_case_p95_cpu_h"] is None
    assert card["startup_measured_eur"] is None
    assert card["solver"] in {"CalculiX", "GetDP", "OpenFOAM"}
    assert card["solver_image_digest"] is None
    assert cost["status"] == "ASSUMPTION_NOT_MEASURED"
    assert not cost["all_in_bill_verified"]
    assert cost["serial_elapsed_to_cpu_ratio"] == 1
    assert card["primary_cases"] == card["designs"] * card["mandatory_strata"]
    units = (
        card["primary_cases"]
        + cost["refinement_cost_multiplier"] * card["refined_cases"]
        + card["charged_failed_attempts"]
        + cost["witness_pairs"] * cost["witness_tools_per_pair"]
    )
    assert card["equivalent_complete_cases"] == units
    cpu = [units * hours for hours in card["complete_case_cpu_h_low_base_high"]]
    assert card["total_cpu_h_scenario"] == pytest.approx(cpu)
    bills = [
        cost["rate_eur_per_node_h"]
        * (hours * cost["serial_elapsed_to_cpu_ratio"] + cost["setup_idle_fit_node_h"])
        * cost["tax_multiplier"]
        + cost["other_charges_reserve_eur"]
        for hours in cpu
    ]
    assert card["startup_eur_scenario"] == pytest.approx(bills, abs=1e-6)
    assert max(bills) <= cost["startup_target_eur"]
    # This is the scenario target, never a measured C pass.
    assert card["c2_pass"] == card["c3_pass"] == card["c4_pass"] == "NOT_DEMONSTRATED"


def test_common_comparison_preserves_independence_and_frontier_rule():
    text = (DOCS / "README.md").read_text(encoding="utf-8")
    for term in (
        "CLOSED_BANK",
        "NEW_SUPPORTED",
        "NONE_FEASIBLE",
        "within two registered refinement bands",
        "never widen bands",
        "EVAL/STRESS/quiz/tuning",
        "not candidate",
        "Tier 3",
        "CPU-hour tariff",
        "no core-count",
        "zero incremental",
    ):
        assert term in text
    assert "Do not quietly" in text and "physics" in text


def test_all_local_document_links_resolve():
    for path in DOCS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            assert (path.parent / target.split("#", 1)[0]).resolve().is_file(), (
                path.name,
                target,
            )
