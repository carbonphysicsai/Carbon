"""The Challenge-neutral design-task interface on hand-made quantities."""

from __future__ import annotations

import pytest

from carbon.design_search import tasks as dt

OBJ = {"quantity": "rf", "unit": "1", "sense": "min", "aggregate": "worst"}
SEC = {"quantity": "t", "unit": "N m", "sense": "max", "aggregate": "worst"}
CONS = [
    {"quantity": "t", "unit": "N m", "op": ">=", "limit": 4.0},
    {"quantity": "rf", "unit": "1", "op": "<=", "limit": 0.3},
]
TASK = dt.task(
    "T",
    conditions=["c1", "c2"],
    candidates=["a", "b", "c"],
    objective=OBJ,
    constraints=CONS,
    secondary=SEC,
)


def grid(**rows):
    return {
        (cand, cond): {"t": t, "rf": rf}
        for cand, pairs in rows.items()
        for cond, (t, rf) in zip(("c1", "c2"), pairs)
    }


REF = grid(
    a=[(5, 0.2), (4.5, 0.25)], b=[(5, 0.1), (3.9, 0.12)], c=[(6, 0.28), (6, 0.29)]
)


def test_oracle_picks_best_feasible_with_zero_regret():
    out = dt.judge(TASK, REF, REF)
    assert out == {
        "kind": "SELECTED_FEASIBLE",
        "selected": "a",
        "best": "a",
        "regret": 0.0,
        "unit": "1",
    }


def test_optimist_pick_is_false_feasible_and_unpriced():
    pred = dict(REF) | {("b", "c2"): {"t": 4.1, "rf": 0.12}}
    out = dt.judge(TASK, pred, REF)
    assert out["kind"] == "SELECTED_INFEASIBLE" and out["regret"] is None


def test_cautious_pick_costs_regret_in_objective_units():
    pred = dict(REF) | {("a", "c2"): {"t": 3.5, "rf": 0.25}}
    out = dt.judge(TASK, pred, REF)
    assert out["selected"] == "c" and out["regret"] == pytest.approx(0.04)


def test_abstention_kinds_and_missing_reference():
    none = {k: {"t": 1.0, "rf": 0.9} for k in REF}
    assert dt.judge(TASK, none, REF)["kind"] == "MISSED_OPPORTUNITY"
    assert dt.judge(TASK, none, none)["kind"] == "CORRECT_ABSTENTION"
    partial = {k: v for k, v in REF.items() if k != ("c", "c1")}
    out = dt.judge(TASK, REF, partial)
    assert out["kind"] == "SELECTED_FEASIBLE" and out["regret"] is None
    assert dt.assess(TASK, partial)["c"]["feasible"] is None
    unknown = {k: v for k, v in none.items() if k[0] != "a"}
    assert dt.judge(TASK, none, unknown)["kind"] == "SELECTED_UNRESOLVED"


def test_ties_break_on_secondary_then_id():
    ref = grid(a=[(5, 0.2), (5, 0.2)], b=[(6, 0.2), (6, 0.2)], c=[(6, 0.2), (6, 0.2)])
    assert dt.select(TASK, dt.assess(TASK, ref)) == "b"


def test_measures_and_validation():
    m = dt.measures(
        [
            {"kind": "SELECTED_FEASIBLE", "regret": 0.02},
            {"kind": "SELECTED_INFEASIBLE", "regret": None},
            {"kind": "MISSED_OPPORTUNITY", "regret": None},
            {"kind": "SELECTED_UNRESOLVED", "regret": None},
        ]
    )
    assert m == {
        "false_feasible": 1 / 3,
        "over_caution": 1 / 3,
        "regret": 0.02,
        "unresolved": 1,
    }
    with pytest.raises(dt.TaskError):
        dt.task(
            "x", conditions=["c"], candidates=["a", "a"], objective=OBJ, constraints=[]
        )
