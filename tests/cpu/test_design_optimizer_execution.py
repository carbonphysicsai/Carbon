"""Toy-only tests of registered design optimizers and comparison masks."""

from __future__ import annotations

import pytest

from carbon.design_search import tasks as dt

GRAMMAR = {
    "schema": dt.GRAMMAR_SCHEMA,
    "version": "toy-grid.v1",
    "variables": [{"name": "x", "type": "integer", "min": 0, "max": 3, "step": 1}],
    "rules": [{"kind": "linear", "coefficients": {"x": 1}, "op": "<=", "value": 2}],
}
CONDITIONS = [{"id": "warm", "stratum": "s"}, {"id": "cold", "stratum": "s"}]
ACTIONS = {"a": {"x": 0}, "b": {"x": 1}, "c": {"x": 2}}


def make(*, optimizer=None, budget=6, seed=7):
    identity = {
        "challenge": "toy",
        "contract_version": "v1",
        "action_grammar": GRAMMAR,
        "optimizer": optimizer or {"class": "exhaustive", "version": "v1"},
        "query_budget": budget,
        "seed": seed,
        "observer_version": "toy.v1",
        "reference_bank": "toy.v1",
    }
    return dt.task(
        "toy-question",
        identity=identity,
        conditions=CONDITIONS,
        strata={"s": {"p": 1.0, "q": 1.0, "w": 1.0}},
        candidates=list(ACTIONS),
        actions=ACTIONS,
        objective={
            "quantity": "loss",
            "unit": "1",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "heat", "unit": "K", "op": "<=", "value": 10}],
    )


def model(action, condition):
    assert action["x"] in (0, 1, 2)
    assert condition["id"] in ("warm", "cold")
    return {"loss": 2 - action["x"], "heat": action["x"]}


def test_registered_multistart_replays_and_ignores_caller_starts():
    optimizer = {"class": "multi_start_local", "version": "v1", "starts": ["a", "c"]}
    task = make(optimizer=optimizer, budget=10)
    calls = []

    def predictor(action, condition):
        calls.append((action["x"], condition["id"]))
        return model(action, condition)

    first = dt.run_optimizer(task, predictor, model_id="m")
    first_calls = list(calls)
    calls.clear()
    second = dt.run_optimizer(
        make(optimizer=optimizer, budget=10), predictor, model_id="m"
    )
    assert first == second
    assert calls == first_calls
    assert first["commitment"]["selected"] == "c"
    assert first["accounting"]["attempted_queries"] <= 10
    with pytest.raises(TypeError):
        dt.run_optimizer(task, predictor, model_id="m", starts=["b"])
    with pytest.raises(dt.TaskError):
        dt.commit(task, {}, model_id="m")


def test_local_search_uses_predictions_without_gradient_access():
    class DifferentiableToy:
        def __call__(self, action, condition):
            return model(action, condition)

        def gradient(self, *args):
            raise AssertionError("gradient must not be used")

    task = make(
        optimizer={"class": "multi_start_local", "version": "v1", "starts": ["a"]},
        budget=8,
    )
    assert (
        dt.run_optimizer(task, DifferentiableToy(), model_id="level4")["commitment"][
            "selected"
        ]
        == "c"
    )


def test_malformed_registered_starts_are_refused():
    with pytest.raises(dt.TaskError):
        make(optimizer={"class": "multi_start_local", "version": "v1", "starts": [{}]})


def test_exhaustive_budget_stops_before_incomplete_panel():
    calls = []

    def predictor(action, condition):
        calls.append((action["x"], condition["id"]))
        return model(action, condition)

    result = dt.run_optimizer(make(budget=5), predictor, model_id="m")
    assert result["accounting"] == {
        "attempted_queries": 4,
        "query_budget": 5,
        "invalid_queries": 0,
        "model_failures": 0,
        "complete_panels": 2,
        "exhaustive_coverage": False,
        "stopped_for_budget": True,
    }
    assert len(calls) == 4
    assert result["commitment"]["selected"] == "b"


def test_invalid_geometry_and_model_failures_consume_budget():
    local = make(
        optimizer={"class": "multi_start_local", "version": "v1", "starts": ["c"]},
        budget=5,
    )
    result = dt.run_optimizer(local, model, model_id="m")
    assert result["accounting"]["invalid_queries"] == 1  # x=3 violates grammar
    assert result["accounting"]["attempted_queries"] == 5

    def failing(action, condition):
        if action["x"] == 1:
            raise RuntimeError("toy model failure")
        return model(action, condition)

    failed = dt.run_optimizer(make(), failing, model_id="m")
    assert failed["accounting"]["model_failures"] == 1
    assert failed["accounting"]["attempted_queries"] == 5
    assert failed["accounting"]["exhaustive_coverage"] is False


def test_snapping_and_grammar_are_versioned_in_task_identity():
    assert dt.snap_action(GRAMMAR, {"x": 1.5}) == {"x": 1}
    with pytest.raises(dt.TaskError):
        dt.snap_action(GRAMMAR, {"x": 2.8})
    altered = {**GRAMMAR, "version": "toy-grid.v2"}
    other = make()
    other_identity = {**other["identity"], "action_grammar": altered}
    changed = dt.task(
        other["task_id"],
        identity=other_identity,
        conditions=other["conditions"],
        strata=other["strata"],
        candidates=other["candidates"],
        actions=other["actions"],
        objective=other["objective"],
        limits=other["limits"],
    )
    assert changed["task_digest"] != other["task_digest"]
    original = make()
    GRAMMAR["version"] = "locally-mutated"
    try:
        assert original["identity"]["action_grammar"]["version"] == "toy-grid.v1"
        dt.run_optimizer(original, model, model_id="m")
    finally:
        GRAMMAR["version"] = "toy-grid.v1"
    tampered = {**original, "identity": {**original["identity"], "seed": 999}}
    with pytest.raises(dt.TaskError):
        dt.run_optimizer(tampered, model, model_id="m")


def test_audit_is_separate_equal_budget_diagnostic():
    primary = make(budget=8)
    audit = make(
        optimizer={"class": "multi_start_local", "version": "v1", "starts": ["a"]},
        budget=8,
    )
    result = dt.audit_optimizer(primary, audit, model, model_id="m")
    assert result["primary"]["commitment"]["selected"] == "c"
    assert result["primary"]["accounting"]["query_budget"] == 8
    assert result["audit"]["accounting"]["query_budget"] == 8
    with pytest.raises(dt.TaskError):
        dt.audit_optimizer(primary, make(budget=7), model, model_id="m")


def test_common_mask_reports_partial_reference_for_both_models():
    resolved = {"kind": "SELECTED_FEASIBLE", "regret": 0.0, "reference_resolved": True}
    partial = {"kind": "SELECTED_FEASIBLE", "regret": None, "reference_resolved": False}
    outcomes = {
        "m1": {"q1": resolved, "q2": partial},
        "m2": {"q1": resolved, "q2": resolved},
    }
    mask = dt.common_resolved_mask(["q1", "q2", "q3"], outcomes)
    assert mask["included"] == ["q1"]
    assert mask["excluded"] == ["q2", "q3"]
    assert mask["unresolved_by_model"] == {"m1": ["q2", "q3"], "m2": ["q3"]}
    assert mask["measures_by_model"]["m1"]["unresolved"] == 0
    assert mask["measures_by_model"]["m2"]["unresolved"] == 0
    mismatched = {
        "m1": {"q1": {**resolved, "task_digest": "task-a"}},
        "m2": {"q1": {**resolved, "task_digest": "task-b"}},
    }
    with pytest.raises(dt.TaskError):
        dt.common_resolved_mask(["q1"], mismatched)


def test_judged_partial_bank_cannot_enter_common_mask():
    task = make()
    commitment = dt.run_optimizer(task, model, model_id="m")["commitment"]
    full = {
        (candidate, condition["id"]): model(action, condition)
        for candidate, action in task["actions"].items()
        for condition in task["conditions"]
    }
    partial = {key: row for key, row in full.items() if key != ("a", "warm")}
    complete_outcome = dt.judge(task, commitment, full)
    partial_outcome = dt.judge(task, commitment, partial)
    assert partial_outcome["kind"] == "SELECTED_FEASIBLE"
    assert partial_outcome["reference_resolved"] is False
    mask = dt.common_resolved_mask(
        ["q"], {"complete": {"q": complete_outcome}, "partial": {"q": partial_outcome}}
    )
    assert mask["included"] == []
    assert mask["unresolved_by_model"] == {"complete": [], "partial": ["q"]}
