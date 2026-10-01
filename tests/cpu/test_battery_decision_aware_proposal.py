"""The decision-aware rule is a registered prospective proposal, not a rule.

OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01: the frozen exam rule stays the
deciding one; the proposal is versioned and pinned; both rankings are
reported side by side, with both halves of the evidence.
"""

import json
from pathlib import Path

from carbon.battery import exam
from carbon.battery.value import proposal as p
from carbon.battery.value.contract import load
from carbon.battery.value.report import render, two_rankings

REPOSITORY = Path(__file__).resolve().parents[2]
EV2 = REPOSITORY / "docs/development/evidence/ev2-2026-10-01/results.json"


def ev2():
    return json.loads(EV2.read_text())


def test_the_proposal_cannot_be_selected_by_any_deployment():
    assert p.PROPOSAL["status"] == "PROPOSED_NOT_DECIDING"
    assert p.PROPOSAL["qualification"] is False and p.PROPOSAL["reward"] is False
    # A deployment can only name a rule in exam.RULES; the proposal is not one.
    assert p.PROPOSAL["id"] not in exam.RULES
    assert p.PROFILE_ID not in exam.RULES
    assert all("decision" not in str(rule).lower() for rule in exam.RULES.values())


def test_the_proposal_is_pinned_and_reads_the_frozen_contract_unchanged():
    contract, digest = load(REPOSITORY / p.DECISION_CONTRACT["path"])
    assert digest == p.DECISION_CONTRACT["digest"]
    assert contract["contract_id"] == p.DECISION_CONTRACT["contract_id"]
    assert p.profile(contract)["weights"] == {
        "physics": 0.0,
        "robustness": 1.0,
        "accuracy": 0.0,
    }
    # A changed record is a new version, not a silent edit.
    assert p.proposal_digest() == (
        "sha256:fb7652a80b07ef3b3b1d911f481a7a062e4a48d3443f80849fd6abbf8de7a3a7"
    )


def test_the_recorded_evidence_is_the_retained_ev2_result():
    results, evidence = ev2(), p.EVIDENCE
    ranking = evidence["ranking_real_models"]
    assert (
        ranking["proposed"] == results["comparison"][p.PROFILE_ID]["tau_verification"]
    )
    assert (
        ranking["deciding"]
        == results["comparison"]["control-exam-v1"]["tau_verification"]
    )
    assert ranking["proposed"] < ranking["deciding"]
    check = results["summary"]["boundary_optimist_check"]
    assert check[p.PROFILE_ID]["members_scored_below_it"] == 0
    assert check["control-exam-v1"]["members_scored_below_it"] == 14


def test_both_rankings_are_reported_side_by_side():
    lines = two_rankings(ev2())
    table = [line for line in lines if line.startswith(("| deciding", "| proposed"))]
    assert len(table) == 2
    deciding, proposed = table
    # Each row carries both halves: the ranking figure and the optimist check.
    assert "0.298" in deciding and "not caught" in deciding
    assert "0.202" in proposed and "(caught)" in proposed
    assert "Basis:" in "\n".join(lines)
    assert "## The deciding rule and the proposed rule, side by side" in render(
        ev2(), "EV2"
    )


def test_a_result_without_both_rules_reports_neither_table():
    results = ev2()
    del results["comparison"][p.PROFILE_ID]
    assert two_rankings(results) == []
