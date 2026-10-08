"""Toy-only disclosure, population and producer-report tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.design_search import (
    cost,
    diversity,
    experiment,
    query_cost,
    task_freeze,
    task_measures,
    task_projection,
    tasks,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def toy_task():
    return tasks.task(
        "protected-task-id",
        identity={
            "challenge": "toy",
            "contract_version": "v1",
            "action_grammar": "grammar.v1",
            "optimizer": {
                "class": "multi_start",
                "starts": ["secret-start"],
                "neighbor_order": ["private"],
            },
            "query_budget": 8,
            "seed": "secret-seed",
            "observer_version": "secret-observer",
            "reference_bank": "secret-reference-bank",
            "digest_preimage": "secret-preimage",
        },
        conditions=[{"id": "secret-condition", "stratum": "s", "reference_value": 91}],
        strata={"s": {"p": 1, "q": 1, "w": 1}},
        candidates=["secret-candidate"],
        objective={
            "quantity": "loss",
            "unit": "W",
            "sense": "min",
            "aggregate": "worst",
            "reference_value": 17,
        },
        limits=[
            {
                "quantity": "heat",
                "unit": "K",
                "op": "<=",
                "value": 40,
                "band": 0.1,
                "reference_value": 39,
            }
        ],
    )


def test_miner_projection_drops_every_unlisted_field_and_digest():
    registered = toy_task()
    registered["future_producer_only_field"] = {"protected": "secret-future"}
    registered["task_digest"] = tasks.digest(
        {k: v for k, v in registered.items() if k != "task_digest"}
    )
    public = task_projection.miner_projection(registered)
    assert public == {
        "schema": task_projection.SCHEMA,
        "challenge": "toy",
        "contract_version": "v1",
        "action_grammar_version": "grammar.v1",
        "action_space": None,
        "condition_count": 1,
        "objective": {
            "quantity": "loss",
            "unit": "W",
            "sense": "min",
            "aggregate": "worst",
        },
        "limits": [{"quantity": "heat", "unit": "K", "op": "<=", "value": 40}],
        "secondary": None,
    }
    serialized = json.dumps(public)
    for secret in (
        "protected-task-id",
        "secret-start",
        "private",
        "secret-seed",
        "secret-reference-bank",
        "secret-condition",
        "secret-candidate",
        "secret-preimage",
        "secret-observer",
        "secret-future",
        "reference_value",
        "bank_digest",
        "task_digest",
        registered["task_digest"],
    ):
        assert secret not in serialized
    assert tasks.digest(public) != registered["task_digest"]
    another = toy_task()
    another["identity"]["seed"] = "different-private-seed"
    another["task_digest"] = tasks.digest(
        {k: v for k, v in another.items() if k != "task_digest"}
    )
    assert task_projection.miner_projection(another) == public
    assert another["task_digest"] != registered["task_digest"]


def test_projection_rejects_altered_registration():
    registered = toy_task()
    registered["identity"]["seed"] = "altered"
    with pytest.raises(tasks.TaskError):
        task_projection.miner_projection(registered)


def test_projection_refuses_nested_payload_inside_public_scalar():
    registered = toy_task()
    registered["limits"][0]["value"] = {"secret": "nested-protected"}
    registered["task_digest"] = tasks.digest(
        {k: v for k, v in registered.items() if k != "task_digest"}
    )
    with pytest.raises(tasks.TaskError, match="public limit value"):
        task_projection.miner_projection(registered)


def test_public_action_space_sorts_away_frozen_neighbor_order():
    grammar = {
        "schema": "carbon.action-grammar.v1",
        "version": "toy-grid.v1",
        "variables": [
            {"name": "z", "type": "enum", "values": ["right", "left"]},
            {"name": "a", "type": "integer", "min": 0, "max": 2, "step": 1},
        ],
        "rules": [{"kind": "linear", "coefficients": {"a": 1}, "op": "<=", "value": 2}],
    }
    first = toy_task()
    first["identity"]["action_grammar"] = grammar
    first["task_digest"] = tasks.digest(
        {k: v for k, v in first.items() if k != "task_digest"}
    )
    second = toy_task()
    second["identity"]["action_grammar"] = {
        **grammar,
        "variables": [
            grammar["variables"][1],
            {**grammar["variables"][0], "values": ["left", "right"]},
        ],
    }
    second["task_digest"] = tasks.digest(
        {k: v for k, v in second.items() if k != "task_digest"}
    )
    public = task_projection.miner_projection(first)
    assert public == task_projection.miner_projection(second)
    assert first["task_digest"] != second["task_digest"]
    assert [v["name"] for v in public["action_space"]["variables"]] == ["a", "z"]
    assert public["action_space"]["variables"][1]["values"] == ["left", "right"]


def test_registered_condition_quantile_is_frozen_and_uses_left_inverse_cdf():
    base = toy_task()
    conditions = [{"id": f"c{i}", "stratum": "s"} for i in range(3)]

    def make(probability, rule=tasks.QUANTILE_RULE):
        return tasks.task(
            "q",
            identity=base["identity"],
            conditions=conditions,
            strata={"s": {"p": 1, "q": 1, "w": 1}},
            candidates=["x"],
            objective={
                "quantity": "loss",
                "unit": "W",
                "sense": "min",
                "aggregate": "quantile",
                "probability": probability,
                "rule": rule,
            },
            limits=[],
        )

    values = {
        ("x", "c0"): {"loss": 9},
        ("x", "c1"): {"loss": 1},
        ("x", "c2"): {"loss": 5},
    }
    assert tasks.assess(make(0.5), values)["x"]["objective"] == 5
    assert tasks.assess(make(0.1), values)["x"]["objective"] == 1
    assert tasks.assess(make(1), values)["x"]["objective"] == 9
    assert task_projection.miner_projection(make(0.5))["objective"] == {
        "quantity": "loss",
        "unit": "W",
        "sense": "min",
        "aggregate": "quantile",
        "probability": 0.5,
        "rule": tasks.QUANTILE_RULE,
    }
    assert make(0.5)["task_digest"] != make(0.1)["task_digest"]
    with pytest.raises(tasks.TaskError):
        make(0.5, "unregistered")
    with pytest.raises(tasks.TaskError):
        make(1.1)


def outcome(kind, regret=None):
    return {"kind": kind, "regret": regret, "unit": "W", "reference_resolved": True}


def test_per_stratum_p_and_q_never_mix_and_quantile_is_registered():
    records = [
        {"stratum": "a", "outcome": outcome("SELECTED_FEASIBLE", 1)},
        {"stratum": "b", "outcome": outcome("SELECTED_INFEASIBLE")},
        {"stratum": "b", "outcome": outcome("SELECTED_FEASIBLE", 9)},
    ]
    report = task_measures.per_stratum_measures(
        records,
        strata={"a": {"p": 0.8, "q": 0.2, "w": 1}, "b": {"p": 0.2, "q": 0.8, "w": 1}},
        aggregate={"schema": task_measures.AGGREGATE_SCHEMA, "probability": 0.5},
    )
    assert report["per_stratum"]["b"]["jobs"] == 2
    assert report["P"]["false_feasible"] == pytest.approx(0.1)
    assert report["Q"]["false_feasible"] == pytest.approx(0.4)
    assert report["P"]["regret_quantile"] == 1
    assert report["Q"]["regret_quantile"] == 9
    with pytest.raises(tasks.TaskError):
        task_measures.per_stratum_measures(
            records,
            strata={"a": {"p": 1, "q": 1, "w": 1}},
            aggregate={"schema": task_measures.AGGREGATE_SCHEMA, "probability": 0.5},
        )


def test_evidence_weight_changes_each_view_without_substituting_q_for_p():
    report = task_measures.per_stratum_measures(
        [
            {"stratum": "a", "outcome": outcome("SELECTED_INFEASIBLE")},
            {"stratum": "b", "outcome": outcome("SELECTED_FEASIBLE", 0)},
        ],
        strata={
            "a": {"p": 0.8, "q": 0.2, "w": 2},
            "b": {"p": 0.2, "q": 0.8, "w": 1},
        },
        aggregate={"schema": task_measures.AGGREGATE_SCHEMA, "probability": 0.5},
    )
    assert report["P"]["false_feasible"] == pytest.approx(0.8)
    assert report["Q"]["false_feasible"] == pytest.approx(0.2)
    assert report["weighted_Q"]["false_feasible"] == pytest.approx(0.4 / 1.2)


def test_unresolved_reference_question_is_reported_even_with_a_feasible_pick():
    report = task_measures.per_stratum_measures(
        [
            {
                "stratum": "only",
                "outcome": {
                    **outcome("SELECTED_FEASIBLE"),
                    "reference_state": "UNRESOLVED",
                },
            }
        ],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        aggregate={"schema": task_measures.AGGREGATE_SCHEMA, "probability": 0.5},
    )
    assert report["per_stratum"]["only"]["unresolved"] == 1
    assert report["P"]["unresolved_rate"] == 1
    assert report["P"]["false_feasible"] is None
    partial = task_measures.per_stratum_measures(
        [
            {
                "stratum": "only",
                "outcome": {
                    **outcome("SELECTED_FEASIBLE"),
                    "reference_state": "FEASIBLE_EXISTS",
                    "reference_resolved": False,
                },
            }
        ],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        aggregate={"schema": task_measures.AGGREGATE_SCHEMA, "probability": 0.5},
    )
    assert partial["P"]["unresolved_rate"] == 1
    with pytest.raises(tasks.TaskError, match="known judged outcome"):
        task_measures.per_stratum_measures(
            [
                {
                    "stratum": "only",
                    "outcome": {"kind": "SELECTED_FEASIBLE", "regret": 0, "unit": "W"},
                }
            ],
            strata={"only": {"p": 1, "q": 1, "w": 1}},
            aggregate={"schema": task_measures.AGGREGATE_SCHEMA, "probability": 0.5},
        )


def test_query_cost_ledger_charges_invalid_and_failed_attempts():
    ledger = cost.Ledger()
    recorder = query_cost.QueryCostRecorder(
        ledger, arm="toy-model-primary", route="toy-cpu", allocated_cores=2
    )
    recorder.record("MODEL_OK", wall_seconds=0.25)
    recorder.record("MODEL_FAILED", wall_seconds=0.5)
    recorder.record("INVALID", wall_seconds=0.125)
    result = recorder.reconcile(
        {"attempted_queries": 3, "invalid_queries": 1, "model_failures": 1}
    )
    assert result["charged_core_seconds"] == 1.75
    assert [charge.category for charge in ledger.charges()] == [
        "inference",
        "inference",
        "query_validation",
    ]
    with pytest.raises(cost.CostError, match="query_cost_accounting_mismatch"):
        recorder.reconcile(
            {"attempted_queries": 4, "invalid_queries": 1, "model_failures": 1}
        )


def producer_inputs(kind="grid"):
    bank = diversity.seal_bank(
        {
            "schema": diversity.BANK_SCHEMA,
            "sealed": True,
            "exposure": [
                {"support_case": "secret-support-a", "limit": 10, "used": 3},
                {"support_case": "secret-support-b", "limit": 9, "used": 1},
            ],
            "cases": [
                {
                    "case": "secret-1",
                    "state": "FEASIBLE_EXISTS",
                    "winner": "secret-A",
                    "close_call": False,
                    "refinement_demand": False,
                },
                {
                    "case": "secret-2",
                    "state": "FEASIBLE_EXISTS",
                    "winner": "secret-B",
                    "close_call": True,
                    "refinement_demand": True,
                },
                {
                    "case": "secret-3",
                    "state": "NONE_FEASIBLE",
                    "winner": None,
                    "close_call": False,
                    "refinement_demand": False,
                },
                {
                    "case": "secret-4",
                    "state": "UNRESOLVED",
                    "winner": None,
                    "close_call": True,
                    "refinement_demand": True,
                },
            ],
        }
    )
    law = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA,
            "kind": kind,
            "draw_model": "iid_with_replacement",
            "batch_size": 2,
            "integration_evidence": "toy-exact" if kind == "continuous" else None,
            "mass_l1_error_bound": 0,
            "bins": [
                {"case": "secret-1", "p_mass": 0.5, "q_mass": 0.1},
                {"case": "secret-2", "p_mass": 0.25, "q_mass": 0.4},
                {"case": "secret-3", "p_mass": 0.125, "q_mass": 0.2},
                {"case": "secret-4", "p_mass": 0.125, "q_mass": 0.3},
            ],
        }
    )
    return bank, law


@pytest.mark.parametrize("kind", ["grid", "continuous"])
def test_diversity_report_only_aggregates(kind):
    report = diversity.diversity_report(*producer_inputs(kind))
    assert report["P"]["expected_distinct_winners_per_batch"] == pytest.approx(1.1875)
    assert report["Q"]["expected_distinct_winners_per_batch"] == pytest.approx(0.83)
    assert report["P"]["status_mix"] == {
        "FEASIBLE_EXISTS": 0.75,
        "NONE_FEASIBLE": 0.125,
        "UNRESOLVED": 0.125,
    }
    assert report["P"]["close_call_rate"] == 0.375
    assert report["Q"]["refinement_demand_rate"] == 0.7
    assert report["exposure_remaining"] == 7
    serialized = json.dumps(report)
    for secret in (
        "secret-1",
        "secret-A",
        "secret-support-a",
        "toy-exact",
        "seal_digest",
        "registration_digest",
    ):
        assert secret not in serialized


def test_diversity_refuses_unsealed_or_unregistered_inputs():
    bank, law = producer_inputs()
    with pytest.raises(tasks.TaskError):
        diversity.diversity_report({**bank, "sealed": False}, law)
    with pytest.raises(tasks.TaskError):
        diversity.diversity_report(bank, {**law, "batch_size": 3})


def test_exposure_shortage_suppresses_batch_diversity_claim():
    bank, law = producer_inputs()
    body = {k: v for k, v in bank.items() if k != "seal_digest"}
    body["exposure"] = [{**body["exposure"][0], "used": 9}, body["exposure"][1]]
    exhausted = diversity.seal_bank(body)
    report = diversity.diversity_report(exhausted, law)
    assert report["exposure_remaining"] == 1
    assert report["exposure_shortage"] == 1
    assert report["batch_drawable"] is False
    assert report["P"]["expected_distinct_winners_per_batch"] is None


def test_diversity_cli_prints_only_aggregate_json(tmp_path):
    bank, law = producer_inputs()
    bank_path, law_path = tmp_path / "bank.json", tmp_path / "law.json"
    bank_path.write_text(json.dumps(bank), encoding="utf-8")
    law_path.write_text(json.dumps(law), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.design_search",
            "diversity-report",
            "--bank",
            str(bank_path),
            "--law",
            str(law_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["exposure_remaining"] == 7
    assert "secret-" not in result.stdout


def test_task_aware_freeze_and_pilot_pin_new_code_without_changing_legacy(tmp_path):
    class Oracle:
        used = 0
        budget = 1
        elapsed = 0.0

    adapter = experiment.SearchAdapter(
        challenge="toy",
        design_variables=("x",),
        condition_variables=("x",),
        contract_digest="toy-contract",
        modes=("toy",),
        request=lambda request: (request, None),
        oracle=lambda engine, space, infer: Oracle(),
        baseline=lambda oracle, engine, space: [],
        view=lambda engine, space: None,
        commit=lambda engine, selections, oracle, directory: {"committed": True},
        verify=lambda commitment, reference: {"verdicts": {}},
        code_paths=(),
        tie_policy="toy-tie",
    )
    common = {
        "repository": REPOSITORY,
        "mode": "toy",
        "designs": [{"x": 0}],
        "conditions": [{"x": 1}],
        "query_budget": 1,
        "verification_budget": 1,
        "seed_policy": "toy",
        "panel": [
            {
                "member": "m",
                "recipe_digest": "toy",
                "seed": 0,
                "material": "DEVELOPMENT",
            }
        ],
        "proposals": {},
    }
    legacy = experiment.freeze(adapter, **common)
    frozen = task_freeze.freeze(adapter, toy_task(), **common)
    assert legacy["schema"] == experiment.FREEZE_SCHEMA
    assert not set(task_freeze.DESIGN_TASK_CODE) & set(legacy["code"])
    assert set(task_freeze.DESIGN_TASK_CODE) <= set(frozen["code"])
    assert frozen["decision_contract"] != legacy["decision_contract"]
    result = task_freeze.pilot(
        frozen,
        adapter,
        toy_task(),
        repository=REPOSITORY,
        models={"m": lambda *args: None},
        reference=None,
        directory=tmp_path,
    )
    assert result["freeze_digest"] == frozen["freeze_digest"]
    changed_task = toy_task()
    changed_task["identity"]["seed"] = "another-seed"
    changed_task["task_digest"] = tasks.digest(
        {k: v for k, v in changed_task.items() if k != "task_digest"}
    )
    with pytest.raises(
        experiment.ExperimentError, match="design_task_identity_changed"
    ):
        task_freeze.pilot(
            frozen,
            adapter,
            changed_task,
            repository=REPOSITORY,
            models={"m": lambda *args: None},
            reference=None,
            directory=tmp_path,
        )
    with pytest.raises(experiment.ExperimentError, match="frozen_code_changed"):
        experiment.check_frozen(frozen, adapter, REPOSITORY)
    copied = tmp_path / "repo"
    for relative in (
        *experiment.NEUTRAL_CODE,
        *task_freeze.DESIGN_TASK_CODE,
        *experiment.DEPENDENCIES,
    ):
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, destination)
    (copied / "carbon/design_search/diversity.py").write_text(
        "# drift", encoding="utf-8"
    )
    with pytest.raises(experiment.ExperimentError, match="frozen_code_changed"):
        task_freeze.pilot(
            frozen,
            adapter,
            toy_task(),
            repository=copied,
            models={"m": lambda *args: None},
            reference=None,
            directory=tmp_path,
        )
