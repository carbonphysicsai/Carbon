"""Toy score-bridge contracts and battery-v8-shaped parity; no private bank."""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery import quiz_stratum as battery_stratum
from carbon.battery.value import quiz as battery_quiz
from carbon.battery.value import score_tuning
from carbon.design_search import battery_q3_v8, optimizer, tasks
from carbon.design_search import score_bridge as bridge
from carbon.design_search.indexed import EQUIVALENCE_RULE


def _task(name, *, budget=2, band=0):
    return tasks.task(
        name,
        identity={
            "challenge": "toy-score",
            "contract_version": "fixture-v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy-v1",
                "variables": [{"name": "choice", "type": "enum", "values": ["a", "b"]}],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": budget,
            "seed": 19,
            "observer_version": "fixture-v1",
            "reference_bank": "protected-toy-bank",
        },
        conditions=[{"id": "protected-condition", "stratum": "toy"}],
        strata={"toy": {"p": 1, "q": 1, "w": 1}},
        candidates=["a", "b"],
        actions={"a": {"choice": "a"}, "b": {"choice": "b"}},
        objective={
            "quantity": "time",
            "unit": "toy-min",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[
            {
                "quantity": "margin",
                "unit": "toy-margin",
                "op": ">=",
                "value": 0,
                "band": band,
            }
        ],
    )


def _panel(a_time, b_time, *, a_margin=1, b_margin=1):
    return [
        {
            "candidate": candidate,
            "condition": "protected-condition",
            "values": {"time": time, "margin": margin},
        }
        for candidate, time, margin in (
            ("a", a_time, a_margin),
            ("b", b_time, b_margin),
        )
    ]


def _rule(*, tolerance=0.5):
    return bridge.register_score_rule(
        {
            "schema": bridge.RULE_SCHEMA,
            "version": "fixture-v1",
            "challenge": "toy-score",
            "contract_version": "fixture-v1",
            "objective": {"quantity": "time", "unit": "toy-min", "sense": "min"},
            "value_equivalence": {
                "quantity": "time",
                "unit": "toy-min",
                "tolerance": tolerance,
                "rule": EQUIVALENCE_RULE,
            },
            "loss": {
                "unit": "toy-loss",
                "regret_multiplier": 1,
                "regret_divisor": 2,
            },
            "kind_costs": {
                "SELECTED_INFEASIBLE": 10,
                "MISSED_OPPORTUNITY": 1,
                "SELECTED_UNRESOLVED": 10,
                "ABSTENTION_UNRESOLVED": 1,
                "CORRECT_ABSTENTION": 0,
            },
            "question_aggregate": bridge.QUESTION_AGGREGATE,
            "q_transform": bridge.Q_TRANSFORM,
        }
    )


def _bank(rows):
    return bridge.seal_score_bank(
        [
            {
                "question_id": f"protected-question-{number}",
                "task": task,
                "reference": {"status": "OK", "panel": reference},
            }
            for number, (task, reference, _) in enumerate(rows)
        ]
    )


def _committed(bank, rows):
    return bridge.commit_prediction_panels(
        "toy-submission",
        [
            {
                "question_id": question["question_id"],
                "task_digest": question["task"]["task_digest"],
                "panel": predicted,
            }
            for question, (_, _, predicted) in zip(bank["questions"], rows)
        ],
    )


def test_plain_q_applies_equivalence_and_registered_kind_costs():
    rows = [
        (_task("near"), _panel(10, 9.6), _panel(9, 10)),
        (_task("beyond"), _panel(10, 9), _panel(9, 10)),
        (
            _task("false-feasible"),
            _panel(10, 9, a_margin=-1),
            _panel(9, 10),
        ),
        (
            _task("abstention"),
            _panel(10, 9),
            _panel(9, 10, a_margin=-1, b_margin=-1),
        ),
    ]
    bank = _bank(rows)
    predicted = _committed(bank, rows)
    result = bridge.evaluate_design_score(bank, predicted, _rule())
    assert result == bridge.evaluate_design_score(bank, predicted, _rule())
    assert result["status"] == "OK" and result["eligible"] is True
    assert [row["outcome"]["kind"] for row in result["per_question"]] == [
        "SELECTED_FEASIBLE",
        "SELECTED_FEASIBLE",
        "SELECTED_INFEASIBLE",
        "MISSED_OPPORTUNITY",
    ]
    assert [row["regret"] for row in result["per_question"]] == [0, 1, None, None]
    assert result["mean_regret"] == 0.5
    assert result["mean_loss"] == statistics.fmean((0, 0.5, 10, 1))
    assert result["q"] == 1.0 / (1.0 + result["mean_loss"])
    assert all(
        row["accounting"]["attempted_queries"] == 2 for row in result["per_question"]
    )


def test_pure_bridge_uses_no_clock_without_cost_ledger(monkeypatch):
    rows = [(_task("clock-free"), _panel(10, 9), _panel(9, 10))]
    bank = _bank(rows)

    def forbidden_clock():
        raise AssertionError("pure scoring read the clock")

    monkeypatch.setattr(optimizer.time, "perf_counter", forbidden_clock)
    assert (
        bridge.evaluate_design_score(bank, _committed(bank, rows), _rule())["status"]
        == "OK"
    )


def test_reference_band_uncertainty_is_rule_priced_but_missing_truth_is_void():
    task = _task("band", band=0.2)
    rows = [(task, _panel(9, 10, a_margin=0.1), _panel(9, 10))]
    bank = _bank(rows)
    committed = _committed(bank, rows)
    result = bridge.evaluate_design_score(bank, committed, _rule())
    assert result["status"] == "OK"
    assert result["per_question"][0]["outcome"]["kind"] == "SELECTED_UNRESOLVED"
    assert result["mean_loss"] == 10
    assert result["q"] == 1 / 11
    missing = json.loads(json.dumps(bank))
    missing["questions"][0]["reference"] = None
    missing = bridge.seal_score_bank(missing["questions"])
    void = bridge.evaluate_design_score(missing, committed, _rule())
    assert void["status"] == "VOID" and void["eligible"] is None
    assert void["q"] is None and void["per_question"] == []


def test_candidate_failures_and_infra_failures_never_share_a_status():
    rows = [(_task("failure"), _panel(10, 9), _panel(9, 10))]
    bank = _bank(rows)
    committed = _committed(bank, rows)
    invalid = json.loads(json.dumps(committed))
    invalid["questions"][0]["panel"][0]["values"]["time"] = math.nan
    invalid = bridge.commit_prediction_panels("toy-submission", invalid["questions"])
    candidate = bridge.evaluate_design_score(bank, invalid, _rule())
    assert candidate["status"] == "INELIGIBLE"
    assert candidate["cause"] == "q_candidate_failed" and candidate["q"] is None
    missing_query = bridge.commit_prediction_panels(
        "toy-submission",
        [
            {
                **committed["questions"][0],
                "panel": committed["questions"][0]["panel"][:1],
            }
        ],
    )
    assert (
        bridge.evaluate_design_score(bank, missing_query, _rule())["status"]
        == "INELIGIBLE"
    )
    tampered = json.loads(json.dumps(committed))
    tampered["questions"][0]["panel"][0]["values"]["time"] += 1
    assert (
        bridge.evaluate_design_score(bank, tampered, _rule())["status"] == "INELIGIBLE"
    )
    failed_reference = bridge.seal_score_bank(
        [{**bank["questions"][0], "reference": {"status": "FAILED_INFRA"}}]
    )
    infra = bridge.evaluate_design_score(failed_reference, invalid, _rule())
    assert infra["status"] == "FAILED_INFRA" and infra["eligible"] is None
    assert (
        bridge.evaluate_design_score(None, committed, _rule())["status"]
        == "FAILED_INFRA"
    )
    broken_seal = json.loads(json.dumps(bank))
    broken_seal["questions"][0]["reference"]["panel"][0]["values"]["time"] += 1
    assert (
        bridge.evaluate_design_score(broken_seal, committed, _rule())["status"]
        == "FAILED_INFRA"
    )
    nonfinite_reference = json.loads(json.dumps(bank))
    nonfinite_reference["questions"][0]["reference"]["panel"][0]["values"][
        "time"
    ] = math.nan
    nonfinite_reference = bridge.seal_score_bank(nonfinite_reference["questions"])
    assert (
        bridge.evaluate_design_score(nonfinite_reference, committed, _rule())["status"]
        == "VOID"
    )


def test_indexed_map_scores_once_after_every_band_and_keeps_per_index():
    indexed_task = tasks.indexed_task(
        "protected-map",
        index_axis="toy-band",
        indices=[
            {"index_value": 5, "buyer_weight": 0.75, "task": _task("band-5")},
            {"index_value": 35, "buyer_weight": 0.25, "task": _task("band-35")},
        ],
        query_budget=4,
        value_equivalence=_rule()["value_equivalence"],
    )
    reference = [
        {"index_value": 5, "panel": _panel(10, 9)},
        {"index_value": 35, "panel": _panel(10, 8)},
    ]
    bank = bridge.seal_score_bank(
        [
            {
                "question_id": "protected-map-question",
                "task": indexed_task,
                "reference": {"status": "OK", "per_index": reference},
            }
        ]
    )
    committed = bridge.commit_prediction_panels(
        "toy-submission",
        [
            {
                "question_id": "protected-map-question",
                "task_digest": indexed_task["task_digest"],
                "per_index": [
                    {"index_value": 5, "panel": _panel(9, 10)},
                    {"index_value": 35, "panel": _panel(9, 10)},
                ],
            }
        ],
    )
    result = bridge.evaluate_design_score(bank, committed, _rule())
    assert result["status"] == "OK"
    assert result["per_question"][0]["outcome"]["kind"] == "SELECTED_FEASIBLE"
    assert len(result["per_question"][0]["outcome"]["per_index"]) == 2
    assert result["per_question"][0]["regret"] == 1.25
    assert result["mean_loss"] == 0.625
    assert (
        bridge.evaluate_design_score(bank, committed, _rule(tolerance=0.25))["status"]
        == "FAILED_INFRA"
    )
    breached = json.loads(json.dumps(reference))
    breached[1]["panel"][0]["values"]["margin"] = -1
    bad_bank = bridge.seal_score_bank(
        [{**bank["questions"][0], "reference": {"status": "OK", "per_index": breached}}]
    )
    bad = bridge.evaluate_design_score(bad_bank, committed, _rule())
    assert bad["status"] == "OK"
    assert bad["per_question"][0]["outcome"]["kind"] == "SELECTED_INFEASIBLE"
    assert bad["mean_loss"] == 10


def test_miner_projection_is_one_sealed_outcome_with_no_private_fields():
    rows = [(_task("private"), _panel(10, 9), _panel(9, 10))]
    bank = _bank(rows)
    internal = bridge.evaluate_design_score(bank, _committed(bank, rows), _rule())
    public = bridge.miner_score_projection(internal)
    assert public == {"schema": bridge.MINER_SCHEMA, "outcome": "SEALED"}
    for secret in ("protected", "reference", "task_digest", "mean_loss", "q"):
        assert secret not in json.dumps(public)
    assert (
        bridge.miner_score_projection({**internal, "extra_private": "secret"}) == public
    )


def test_rule_requires_unit_matched_tolerance_and_all_cost_values():
    body = {k: v for k, v in _rule().items() if k != "registration_digest"}
    body["value_equivalence"] = {**body["value_equivalence"], "unit": "seconds"}
    with pytest.raises(bridge.InfrastructureFailure):
        bridge.register_score_rule(body)
    body["value_equivalence"] = _rule()["value_equivalence"]
    body["kind_costs"] = {"SELECTED_INFEASIBLE": 10}
    with pytest.raises(bridge.InfrastructureFailure):
        bridge.register_score_rule(body)


def test_nonfinite_derived_loss_is_infra_not_a_candidate_penalty():
    rows = [(_task("overflow"), _panel(1e308, 0), _panel(0, 1e308))]
    bank = _bank(rows)
    body = {
        key: value for key, value in _rule().items() if key != "registration_digest"
    }
    body["loss"] = {**body["loss"], "regret_multiplier": 1e308}
    result = bridge.evaluate_design_score(
        bank, _committed(bank, rows), bridge.register_score_rule(body)
    )
    assert result["status"] == "FAILED_INFRA"
    assert result["eligible"] is None and result["q"] is None


def test_battery_v8_tuning_q_parity_on_synthetic_grid_predictions():
    """Compare the neutral q to the existing Q3 judge and tuning q formula."""
    contract = battery_stratum.contract(Path(__file__).resolve().parents[2])
    candidates = battery_quiz.q3_candidates()
    costs = contract["mistake_costs"]
    rule = bridge.register_score_rule(
        {
            "schema": bridge.RULE_SCHEMA,
            "version": "synthetic-v8-parity",
            "challenge": battery_q3_v8.JOB,
            "contract_version": contract["version"],
            "objective": {
                "quantity": "time_to_cv_onset_s",
                "unit": "s",
                "sense": "min",
            },
            "value_equivalence": {
                "quantity": "time_to_cv_onset_s",
                "unit": "s",
                "tolerance": 0,
                "rule": EQUIVALENCE_RULE,
            },
            "loss": {
                "unit": costs["unit"],
                "regret_multiplier": costs["regret_per_minimum_useful_improvement"],
                "regret_divisor": contract["minimum_useful_improvement_s"],
            },
            "kind_costs": {
                "SELECTED_INFEASIBLE": costs["false_acceptance"],
                "MISSED_OPPORTUNITY": costs["missed_opportunity"],
                "SELECTED_UNRESOLVED": costs["false_acceptance"],
                "ABSTENTION_UNRESOLVED": costs["missed_opportunity"],
                "CORRECT_ABSTENTION": 0,
            },
            "question_aggregate": bridge.QUESTION_AGGREGATE,
            "q_transform": bridge.Q_TRANSFORM,
        }
    )
    questions = []
    prediction_rows = []
    native = []
    modes = (
        "regret",
        "false-feasible",
        "abstention",
        "regret",
        "false-feasible",
        "regret",
        "abstention",
        "regret",
    )
    for number, mode in enumerate(modes):
        entry = {
            "scenario_id": f"synthetic-battery-q3-{number}",
            "condition": [25.0, 0.2],
            "attempt": number,
        }
        task = battery_q3_v8._neutral_task(entry, "synthetic-seal", contract)
        grid = battery_quiz.q3_grid(contract, battery_stratum.scenario(entry))
        raw_reference = {}
        raw_prediction = {}
        reference_panel = []
        prediction_panel = []
        for position, (candidate, job) in enumerate(zip(candidates, grid)):
            voltage = [3.9, 4.5, 4.5, 4.5] if position == 0 else [3.9, 4.2, 4.5, 4.5]
            reference_outputs = {
                "voltage_v": voltage,
                "temperature_c": [40.0] * 4,
                "plating_margin_v": (
                    -0.01 if mode == "false-feasible" and position == 0 else 0.01
                ),
            }
            predicted_outputs = {
                **reference_outputs,
                "plating_margin_v": (
                    -0.01
                    if mode == "abstention" or (mode == "regret" and position == 0)
                    else 0.01
                ),
            }
            raw_reference[job["case_id"]] = {
                "status": "OK",
                "outputs": reference_outputs,
            }
            raw_prediction[job["case_id"]] = predicted_outputs
            reference_panel.append(
                {
                    "candidate": candidate["id"],
                    "condition": "one-condition",
                    "values": battery_q3_v8._projection(
                        contract, raw_reference[job["case_id"]]
                    ),
                }
            )
            prediction_panel.append(
                {
                    "candidate": candidate["id"],
                    "condition": "one-condition",
                    "values": battery_q3_v8._projection(
                        contract, {"status": "OK", "outputs": predicted_outputs}
                    ),
                }
            )
        native.append(
            battery_quiz.q3_judge(
                contract,
                battery_stratum.scenario(entry),
                raw_prediction,
                raw_reference,
            )
        )
        questions.append(
            {
                "question_id": entry["scenario_id"],
                "task": task,
                "reference": {"status": "OK", "panel": reference_panel},
            }
        )
        prediction_rows.append(
            {
                "question_id": entry["scenario_id"],
                "task_digest": task["task_digest"],
                "panel": prediction_panel,
            }
        )
    bank = bridge.seal_score_bank(questions)
    committed = bridge.commit_prediction_panels("synthetic-model", prediction_rows)
    result = bridge.evaluate_design_score(bank, committed, rule)
    native_measures = battery_quiz.q3_measures(native, contract)
    assert result["status"] == "OK"
    assert [row["kind"] for row in native[:3]] == [
        "SELECTED_FEASIBLE",
        "SELECTED_INFEASIBLE",
        "MISSED_OPPORTUNITY",
    ]
    assert native[0]["decision_loss"] > 0
    assert [row["outcome"]["kind"] for row in result["per_question"]] == [
        row["kind"] for row in native
    ]
    assert [row["loss"] for row in result["per_question"]] == [
        row["decision_loss"] for row in native
    ]
    assert result["mean_loss"] == native_measures["regret"]
    tuning_legs = score_tuning.member_legs(
        contract,
        {},
        SimpleNamespace(refs={}, twins={}),
        [],
        decision_regret=native_measures["regret"],
    )
    assert result["q"] == tuning_legs["legs"]["q"]
