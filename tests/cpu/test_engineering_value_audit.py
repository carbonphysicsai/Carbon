"""Known bad evidence must remain visible in the supplemental EV audit."""

import copy
import json
from pathlib import Path

import pytest

from carbon.battery.value.audit import audit

ROOT = Path(__file__).resolve().parents[2]


def specimen():
    names = ["a-s0", "a-s1", "b-s0", "c-s0", "bad-s0", "control"]
    members = {m: {"kind": "RECONSTRUCTED", "eligible": True} for m in names}
    members["bad-s0"]["eligible"] = False
    members["control"]["kind"] = "SYNTHETIC_CONTROL"
    return {
        "schema": "carbon.engineering-value-results.v1",
        "contract_digest": "fixture",
        "summary": {"members": members},
        "comparison": {"rule": {}},
        "rule_scores": {m: {"rule": i} for i, m in enumerate(names)},
        "references": {
            s: {"split": "verification", "status_counts": {"FEASIBLE": 1}}
            for s in ("v1", "v2")
        },
        # Deliberately backwards: larger scores produce WORSE decisions.
        "decisions": {
            m: {
                s: {"outcome": {"decision_loss": i, "kind": "SELECTED_FEASIBLE"}}
                for s in ("v1", "v2")
            }
            for i, m in enumerate(names)
        },
    }


def test_score_gaming_is_not_hidden_by_controls_or_ineligible_models():
    result = audit(specimen())
    rule = result["rules"]["rule"]
    assert rule["eligible_member_tau_on_common_cases"] == -1
    assert rule["discordant_pairs"] == 6
    assert rule["recipe_groups"] == 3  # two seeds did not become two methods
    assert result["excluded_ineligible_members"] == ["bad-s0"]
    assert "control" not in result["eligible_reconstructed_members"]
    assert result["admission_status"] == "NOT_ESTABLISHED"


def test_dropping_a_bad_outcome_reveals_coverage_loss():
    data = specimen()
    data["decisions"]["c-s0"]["v2"]["outcome"]["decision_loss"] = None
    result = audit(data)
    assert result["common_resolved_scenarios"] == 1
    assert not result["rules"]["rule"]["full_verification_coverage"]
    assert result["coverage"]["c-s0"]["unresolved_or_missing"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, -1])
def test_nonfinite_and_invalid_loss_cannot_disappear_into_an_average(value):
    data = specimen()
    data["decisions"]["a-s0"]["v1"]["outcome"]["decision_loss"] = value
    with pytest.raises(ValueError, match="invalid_decision_loss"):
        audit(data)


def test_no_observations_or_all_ties_is_not_a_positive_relationship():
    data = specimen()
    for member in data["decisions"].values():
        for row in member.values():
            row["outcome"]["decision_loss"] = None
    assert audit(data)["rules"]["rule"]["eligible_member_tau_on_common_cases"] is None
    for member in data["decisions"].values():
        for row in member.values():
            row["outcome"]["decision_loss"] = 0
    assert audit(data)["rules"]["rule"]["eligible_member_tau_on_common_cases"] is None


def test_real_ev1_exposes_its_limits_without_rewriting_the_evidence():
    data = json.loads(
        (ROOT / "docs/development/evidence/ev1-2026-09-25/results.json").read_bytes()
    )
    before = copy.deepcopy(data)
    result = audit(data)
    assert data == before
    assert result["excluded_ineligible_members"] == ["mlp_raw-s0"]
    assert len(result["eligible_reconstructed_members"]) == 10
    assert any(
        "No verification scenario has a feasible" in s for s in result["limitations"]
    )
    assert result["admission_status"] == "NOT_ESTABLISHED"
