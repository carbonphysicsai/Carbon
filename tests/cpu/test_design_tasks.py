"""The Challenge-neutral design-task interface on hand-made quantities."""

from __future__ import annotations

import pytest

from carbon.design_search import tasks as dt

IDENTITY = {
    "challenge": "toy",
    "contract_version": "toy-contract.v1",
    "action_grammar": "toy-grammar.v1",
    "optimizer": "exhaustive.v1",
    "query_budget": 6,
    "seed": 0,
    "observer_version": "toy-observer.v1",
    "reference_bank": "toy-bank.v1",
}
OBJ = {"quantity": "rf", "unit": "1", "sense": "min", "aggregate": "worst"}
SEC = {"quantity": "t", "unit": "N m", "sense": "max", "aggregate": "worst"}
LIMITS = [
    {"quantity": "t", "unit": "N m", "op": ">=", "value": 4.0, "band": 0.05},
    {"quantity": "rf", "unit": "1", "op": "<=", "value": 0.3},
]
STRATA = {
    "warm": {"p": 0.5, "q": 0.5, "w": 1.0},
    "cold": {"p": 0.5, "q": 0.5, "w": 1.0},
}
CONDS = [{"id": "c1", "stratum": "warm"}, {"id": "c2", "stratum": "cold"}]


def make(candidates=("a", "b", "c")):
    return dt.task(
        "T",
        identity=IDENTITY,
        conditions=CONDS,
        strata=STRATA,
        candidates=list(candidates),
        objective=OBJ,
        limits=LIMITS,
        secondary=SEC,
    )


TASK = make()


def grid(**rows):
    return {
        (cand, cond): {"t": t, "rf": rf}
        for cand, pairs in rows.items()
        for cond, (t, rf) in zip(("c1", "c2"), pairs)
    }


REF = grid(
    a=[(5, 0.2), (4.5, 0.25)], b=[(5, 0.1), (3.9, 0.12)], c=[(6, 0.28), (6, 0.29)]
)


def run(predicted, reference, task_=TASK):
    return dt.judge(task_, dt.commit(task_, predicted, model_id="m"), reference)


def test_oracle_picks_best_feasible_with_zero_regret():
    out = run(REF, REF)
    assert out["kind"] == "SELECTED_FEASIBLE" and out["selected"] == "a"
    assert out["regret"] == 0.0 and out["reference_state"] == "FEASIBLE_EXISTS"


def test_false_feasible_is_counted_not_priced():
    pred = dict(REF) | {("b", "c2"): {"t": 4.1, "rf": 0.12}}
    out = run(pred, REF)
    assert out["kind"] == "SELECTED_INFEASIBLE" and out["regret"] is None


def test_cautious_pick_costs_regret_in_objective_units():
    pred = dict(REF) | {("a", "c2"): {"t": 3.5, "rf": 0.25}}
    out = run(pred, REF)
    assert out["selected"] == "c" and out["regret"] == pytest.approx(0.04)


def test_reference_band_makes_a_close_call_unresolved():
    near = dict(REF) | {("a", "c2"): {"t": 4.03, "rf": 0.25}}
    out = run(REF, near)
    assert out["kind"] == "SELECTED_UNRESOLVED" and out["regret"] is None
    assert dt.assess(TASK, near, reference=True)["a"]["feasible"] is None
    assert dt.assess(TASK, near)["a"]["feasible"] is True  # models get no band


def test_abstention_states():
    none = {k: {"t": 1.0, "rf": 0.9} for k in REF}
    assert run(none, REF)["kind"] == "MISSED_OPPORTUNITY"
    out = run(none, none)
    assert (
        out["kind"] == "CORRECT_ABSTENTION"
        and out["reference_state"] == "NONE_FEASIBLE"
    )
    partial = {k: v for k, v in none.items() if k[0] != "a"}
    assert run(none, partial)["kind"] == "ABSTENTION_UNRESOLVED"


def test_missing_reference_never_reads_feasible():
    partial = {k: v for k, v in REF.items() if k != ("c", "c1")}
    out = run(REF, partial)
    assert out["kind"] == "SELECTED_FEASIBLE" and out["regret"] is None
    assert dt.assess(TASK, partial, reference=True)["c"]["feasible"] is None


def test_ties_break_on_secondary_then_bank_order():
    ref = grid(a=[(5, 0.2), (5, 0.2)], b=[(6, 0.2), (6, 0.2)], c=[(6, 0.2), (6, 0.2)])
    assert dt.select(TASK, dt.assess(TASK, ref)) == "b"
    reordered = make(("c", "b", "a"))
    assert dt.select(reordered, dt.assess(reordered, ref)) == "c"


def test_commitment_binds_the_task():
    commitment = dt.commit(TASK, REF, model_id="m")
    with pytest.raises(dt.TaskError):
        dt.judge(make(("a", "b")), commitment, REF)
    with pytest.raises(dt.TaskError):
        dt.judge(TASK, {**commitment, "selected": "c"}, REF)


def test_registration_is_validated():
    with pytest.raises(dt.TaskError):
        make(("a", "a"))
    with pytest.raises(dt.TaskError):
        dt.task(
            "x",
            identity={},
            conditions=CONDS,
            strata=STRATA,
            candidates=["a"],
            objective=OBJ,
            limits=[],
        )
    with pytest.raises(dt.TaskError):
        dt.task(
            "x",
            identity=IDENTITY,
            conditions=[{"id": "c1", "stratum": "hot"}],
            strata=STRATA,
            candidates=["a"],
            objective=OBJ,
            limits=[],
        )
    assert make()["task_digest"] == TASK["task_digest"]


def test_measures():
    m = dt.measures(
        [
            {"kind": "SELECTED_FEASIBLE", "regret": 0.02},
            {"kind": "SELECTED_INFEASIBLE", "regret": None},
            {"kind": "MISSED_OPPORTUNITY", "regret": None},
            {"kind": "SELECTED_UNRESOLVED", "regret": None},
            {"kind": "ABSTENTION_UNRESOLVED", "regret": None},
        ]
    )
    assert m == {
        "false_feasible": 1 / 3,
        "over_caution": 1 / 3,
        "regret": 0.02,
        "unresolved": 2,
    }
