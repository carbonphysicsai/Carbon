"""TRAINING-BUDGET-01 slice 7: the contract's compute-budget check, built and
switched off.

No live contract declares a compute budget, so admission computes nothing for
them. A contract that declares one refuses a recipe over it, and a recipe whose
cost cannot be calculated in the budget's unit, by name.
"""

from __future__ import annotations

import pytest

from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import challenge_contracts as cc
from carbon.training_budget import cost

BATTERY = cr.BATTERY_CHALLENGE


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": parameters,
    }


class Declared:
    """A contract stand-in whose envelope declares `budget`."""

    def __init__(self, budget):
        self.budget = budget

    def document(self):
        return {"envelope": {"train_cases": 400, cc.COMPUTE_BUDGET: self.budget}}


def test_no_live_contract_declares_a_compute_budget():
    for item in cr.CONTRACTS.values():
        assert cc.COMPUTE_BUDGET not in dict(item.document()["envelope"])


def test_an_undeclared_budget_computes_nothing(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("no cost is computed without a declared budget")

    monkeypatch.setattr(cost, "cost", never)
    assert cc.check_compute_budget(cr.contract(BATTERY), strategy()) is None
    assert cc.compile_submission(strategy(width=32)).challenge == BATTERY


@pytest.mark.parametrize(
    ("report", "code"),
    [
        ({"F4_flops": 2.0e9}, "budget.over_compute_budget"),
        ({"F4_flops": cost.HUMAN_INPUT}, "budget.cost_unmeasurable"),
        ({}, "budget.cost_unmeasurable"),
    ],
)
def test_a_declared_budget_refuses_by_name(monkeypatch, report, code):
    monkeypatch.setattr(cost, "cost", lambda challenge, s, **kw: report)
    with pytest.raises(cc.SubmissionRefused) as refused:
        cc.check_compute_budget(
            Declared({"unit": "F4_flops", "value": 1.0e9}), strategy()
        )
    assert [i.code for i in refused.value.issues] == [code]


def test_a_refused_cost_is_unmeasurable_not_admitted(monkeypatch):
    def refuse(challenge, s, **kw):
        raise cost.CostRefused("cost_unbounded_loop")

    monkeypatch.setattr(cost, "cost", refuse)
    with pytest.raises(cc.SubmissionRefused) as refused:
        cc.check_compute_budget(
            Declared({"unit": "F4_flops", "value": 1.0}), strategy()
        )
    assert refused.value.issues[0].code == "budget.cost_unmeasurable"


def test_a_recipe_within_the_budget_is_admitted(monkeypatch):
    monkeypatch.setattr(cost, "cost", lambda challenge, s, **kw: {"F4_flops": 5.0e8})
    report = cc.check_compute_budget(
        Declared({"unit": "F4_flops", "value": 1.0e9}), strategy()
    )
    assert report["F4_flops"] == 5.0e8


@pytest.mark.parametrize(
    "budget",
    [{"unit": "F4_flops"}, {"unit": 4, "value": 1}, {"unit": "F4_flops", "value": -1}],
)
def test_a_malformed_declaration_is_a_repository_defect(budget):
    with pytest.raises(RuntimeError):
        cc.check_compute_budget(Declared(budget), strategy())
