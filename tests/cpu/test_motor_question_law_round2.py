"""Non-runtime proposal consistency and toy bank arithmetic; no solver/data host."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[2] / "docs/development/challenge_pipeline"
LAW = json.loads((DOCS / "question-laws/motor-round2.json").read_text(encoding="utf-8"))
TEXT = (DOCS / "question-laws/motor-round2.md").read_text(encoding="utf-8")
PRIOR = json.loads((DOCS / "question-laws/proposals.json").read_text(encoding="utf-8"))


def test_proposal_cannot_register_or_authorize_a_bank():
    assert LAW["ticket"] == "CHALLENGE-MOTOR-QUESTION-LAW-01"
    assert LAW["maturity"] == "SPECIFIED"
    for field in ("runtime_registration", "bank_draw_authorized", "spend_authorized"):
        assert LAW[field] is False
    assert LAW["bank"]["applied_rule"] is None
    assert LAW["bank"]["pool_n"] is None
    assert LAW["cost"]["quote"] is None
    assert LAW["cost"]["CCX63_throughput"] is None
    for field in (
        "expected_distinct_winners_P",
        "expected_distinct_winners_Q",
        "close_call_rate",
    ):
        assert LAW[field] is None


@pytest.mark.parametrize(
    "field",
    [
        "action_space",
        "P_job",
        "P_case",
        "Q",
        "w",
        "objective",
        "k",
        "NONE_FEASIBLE",
        "reference_uncertainty",
    ],
)
def test_new_law_values_are_only_recommendations(field):
    assert LAW[field]["status"] == "HUMAN_INPUT"
    assert LAW[field]["registered"] is None
    assert LAW[field]["recommendation"]


@pytest.mark.parametrize("axis", LAW["requirements"], ids=lambda row: row["quantity"])
def test_requirements_remain_in_prior_support_without_relaxing_anchor(axis):
    motor = next(row for row in PRIOR["challenges"] if row["challenge"] == "motor")
    old = next(
        row for row in motor["requirement_axes"] if row["quantity"] == axis["quantity"]
    )
    lower, upper = axis["recommendation"]
    prior_lower, prior_upper = old["continuous_interval"]["recommendation"]
    assert prior_lower <= lower < upper <= prior_upper
    assert axis["registered"] is None and axis["status"] == "HUMAN_INPUT"
    assert axis["unit"] == old["unit"] and axis["op"] == old["op"]
    if axis["op"] == ">=":
        assert lower >= axis["anchor"]
    else:
        assert upper <= axis["anchor"]
    assert LAW["peak_absolute_ripple_multiplier"] == 2


def test_geometry_is_continuous_but_skew_topology_and_commands_are_not():
    space = LAW["action_space"]["recommendation"]
    assert space["topology"] == "10p12s-double-layer"
    assert len(space["continuous_geometry"]) == 6
    assert space["discrete_skew_deg"] == [0, 2, 4]
    assert space["holding"] == {"J_A_per_mm2": 10, "gamma_deg": 0}
    assert space["peak"] == {"J_A_per_mm2": 15, "gamma_deg": 0}
    assert space["cogging"] == {"J_A_per_mm2": 0}
    assert space["off_bank_truth"] == "UNRESOLVED_UNTIL_COVERED"
    assert "physical coordinates/topology/skew" in TEXT
    assert "Register before reference outcomes" in TEXT


def test_two_bands_do_not_turn_shortage_or_partial_peak_into_a_pass():
    t2 = LAW["T2a"]
    assert t2["near_refinement_bands"] == 2
    assert t2["minimum_distinct_feasible"] == t2["minimum_distinct_infeasible"] == 5
    assert t2["reference_interval_adopted"] is False
    observed = t2["historical_holding"]
    assert observed["feasible"] + observed["infeasible"] == observed["geometries"]
    assert observed["near_infeasible"] == 4 < t2["minimum_distinct_infeasible"]
    assert observed["next_nearest_bands"] > t2["near_refinement_bands"]
    assert t2["per_boundary_status"] == "NOT_DEMONSTRATED"
    assert t2["full_buyer_status"] == "HOLD"
    assert "missing other designs remain unresolved" in TEXT


def test_public_simulation_is_not_an_adopted_answer_distribution():
    public = LAW["public_export"]
    assert public["states_under_main"] == {"UNRESOLVED": 20}
    assert sum(public["states_simulated_only"].values()) == public["questions"]
    assert sum(public["winners_simulated_only"].values()) == 16
    assert public["states_simulated_only"]["NONE_FEASIBLE"] == 4
    assert LAW["NONE_FEASIBLE"]["recommendation"] == "VALID_FORWARD_QUESTION_NO_REDRAW"
    assert "every eligible bank action proven infeasible" in TEXT
    assert "All-none batches cannot establish" in TEXT


@pytest.mark.parametrize("row", LAW["cost"]["scenarios"], ids=lambda row: row["id"])
def test_startup_arithmetic_counts_all_standard_and_refined_jobs(row):
    cost = LAW["cost"]
    hours = (
        row["unique_bundles"]
        * row["standard_solves_per_bundle"]
        * cost["planning_standard_hours"]
        + row["refined_bundles"]
        * cost["rung2_solves_per_boundary_bundle"]
        * cost["planning_rung2_hours"]
    )
    assert hours == pytest.approx(row["allocated_cpu_hours"])
    assert hours * cost["requested_node_price_eur_per_hour"] == pytest.approx(
        row["bare_serial_eur"]
    )


def test_count_discrepancies_remain_visible_and_cost_is_not_a_machine_quote():
    cost = LAW["cost"]
    assert cost["reported_standard_solves_per_bundle"] == 5
    assert cost["enumerated_standard_solves_per_bundle"] == 1 + 1 + 4 == 6
    assert cost["standard_count_reconciled"] is False
    cogging = cost["cogging_summary_vs_raw"]
    assert cogging["raw_S3_span_rows"] == 8
    assert cogging["maximum_change_nm"] < cogging["change_bound_nm"]
    assert cogging["maximum_absolute_refined_nm"] > cogging["change_bound_nm"]
    assert cogging["status"] == "SUMMARY_TERMINOLOGY_FINDING_NOT_CONVERGENCE_FAILURE"
    assert cost["observed_standard_p95_seconds"] / 3600 == pytest.approx(1.8466667)
    assert cost["observed_rung2_p95_seconds"] / 3600 == pytest.approx(15.6944444)
    node_hours = (cost["startup_target_eur"] - cost["illustrative_non_node_eur"]) / (
        cost["requested_node_price_eur_per_hour"] * (1 + cost["illustrative_tax_rate"])
    )
    assert node_hours == pytest.approx(55.20456357725572)
    assert 604.8 / node_hours == pytest.approx(10.96, abs=0.01)
    p95 = 44 * 6 * 6648 / 3600 + 9 * 4 * 56500 / 3600
    assert p95 == pytest.approx(1052.52)


def test_question_inventory_and_exposure_never_count_as_fresh_geometry():
    bank = LAW["bank"]
    assert bank["B_over_n"] == bank["E"] == 10
    k = LAW["k"]["recommendation"]
    assert bank["Q3_n"]["recommendation"] == k
    b = bank["Q3_B"]["recommendation"]
    assert b == 10 * k
    assert b * bank["E"] / k == 100  # Appearances ceiling, not guaranteed windows.
    assert 44 * b == LAW["cost"]["scenarios"][-1]["unique_bundles"]
    assert bank["underlying_shared_case_exposure_enforced"] == "NOT_DEMONSTRATED"
    assert (
        bank["forward_NONE_FEASIBLE_live_path"] == "REQUIRES_EXPLICIT_MOTOR_INTEGRATION"
    )
    assert "a new threshold/question ID must not renew" in TEXT


def test_toy_without_replacement_winner_occupancy_is_not_iid_or_power():
    # Synthetic arithmetic shaped like the public simulated counts, no panel read.
    counts, total, draws = (12, 4), 20, 12
    expected = sum(
        1 - math.comb(total - count, draws) / math.comb(total, draws)
        for count in counts
    )
    iid = sum(1 - (1 - count / total) ** draws for count in counts)
    assert 1 < expected <= len(counts)
    assert expected > iid
    assert LAW["expected_distinct_winners_P"] is None  # Neither toy is registered P.


def test_scope_keeps_other_laws_and_reference_findings_separate():
    normalized = " ".join(TEXT.split())
    for phrase in (
        "not a global optimum",
        "not calibrated truth confidence intervals",
        "Tool disagreement is a reference finding",
        "Battery EV5/journal14/live",
        "owner adopts law/support/dependence/objective",
        "HOLD its",
        "a separate buyer-valued scope",
    ):
        assert phrase in normalized
