"""Toy contract tests; no solver or Challenge reference material."""

import copy
import json
from pathlib import Path

import pytest

from carbon.design_search import budget_registration as br

REGISTRATION = (
    Path(__file__).resolve().parents[2]
    / "docs/development/challenge_pipeline/equal-budget-registration-v1.json"
)
BASE_RULE = (
    Path(__file__).resolve().parents[2]
    / "docs/development/challenge_pipeline/value-bar-v1.json"
)


def registration():
    return json.loads(REGISTRATION.read_text(encoding="utf-8"))


def test_prospective_budget_registry_and_value_rule_are_digest_bound():
    raw = registration()
    resolved = br.validate(raw)
    assert set(resolved.challenges) == set(br.CHALLENGES)
    assert all(
        resolved.cap(challenge, "double").solver_evaluations
        == 2 * resolved.cap(challenge, "base").solver_evaluations
        for challenge in br.CHALLENGES
    )
    assert resolved.cap("f02", "half").solver_evaluations == 5
    rule = br.materialize_value_rule(
        json.loads(BASE_RULE.read_text(encoding="utf-8")), raw, "motor"
    )
    assert rule["rule_id"] == "VALUE-BAR-V1:motor:EQUAL-BUDGET-V1"
    assert br.validate_rule_tiers(rule["item_5"])["base"] == resolved.cap(
        "motor", "base"
    )
    assert rule["item_5"]["budget_registration_digest"] == raw["registration_digest"]


def test_changed_provenance_and_post_hoc_cap_are_refused():
    raw = registration()
    raw["challenge_budgets"]["f13"]["tiers"]["base"]["solver_evaluations"] = 100
    with pytest.raises(br.BudgetRegistrationError, match="digest mismatch"):
        br.validate(raw)
    raw = br.seal(
        {key: value for key, value in raw.items() if key != "registration_digest"}
    )
    with pytest.raises(br.BudgetRegistrationError, match="sensitivity tiers"):
        br.validate(raw)
    raw = registration()
    raw["challenge_budgets"]["f13"]["basis"] = "MEASURED"
    raw = br.seal(
        {key: value for key, value in raw.items() if key != "registration_digest"}
    )
    with pytest.raises(br.BudgetRegistrationError, match="ASSUMPTION"):
        br.validate(raw)
    rule = br.materialize_value_rule(
        json.loads(BASE_RULE.read_text(encoding="utf-8")), registration(), "f02"
    )
    item5 = copy.deepcopy(rule["item_5"])
    item5["solver_evaluation_caps"]["base"] += 1
    with pytest.raises(br.BudgetRegistrationError, match="sensitivity tiers"):
        br.validate_rule_tiers(item5)


@pytest.mark.parametrize(
    "arm",
    ["solver_alone", "model_then_solver", "ordinary_surrogate", "adaptive_solver"],
)
def test_every_present_or_future_arm_uses_same_complete_panel_ledger(arm):
    # The arm label deliberately does not change accounting. Future policies
    # must use this shared object rather than their own budget interpretation.
    cap = br.BudgetCap(2, 10.0, 12.0)
    ledger = br.BudgetLedger(cap)
    assert ledger.charge_overhead({"wall_s": 1.0, "core_s": 2.0})
    assert ledger.charge_solver_attempt(
        {"wall_s": 4.0, "core_s": 5.0}, {"wall_s": 3.0, "core_s": 4.0}
    )
    assert ledger.charge_solver_attempt(
        {"wall_s": 4.0, "core_s": 5.0}, {"wall_s": 3.0, "core_s": 4.0}
    )
    assert not ledger.charge_solver_attempt(
        {"wall_s": 1.0, "core_s": 1.0}, {"wall_s": 1.0, "core_s": 1.0}
    )
    assert (ledger.solver_evaluations, ledger.wall_s, ledger.core_s) == (
        2,
        7.0,
        10.0,
    ), arm


def test_overhead_and_planning_bound_stop_before_unaffordable_attempt():
    ledger = br.BudgetLedger(br.BudgetCap(4, 5.0, 5.0))
    assert not ledger.charge_overhead({"wall_s": 6.0, "core_s": 1.0})
    assert not ledger.charge_solver_attempt(
        {"wall_s": 6.0, "core_s": 1.0}, {"wall_s": 1.0, "core_s": 1.0}
    )
    assert ledger.solver_evaluations == 0
    with pytest.raises(br.BudgetRegistrationError, match="planning bound"):
        ledger.charge_solver_attempt(
            {"wall_s": 1.0, "core_s": 1.0}, {"wall_s": 2.0, "core_s": 1.0}
        )
    assert ledger.solver_evaluations == 0
