"""Toy-only indexed design decisions; no battery physics or hidden bank."""

from __future__ import annotations

import json

import pytest

from carbon.design_search import controls, diversity, power, tasks
from carbon.design_search.__main__ import main as report_main
from carbon.design_search.indexed import EQUIVALENCE_RULE
from carbon.design_search.task_projection import miner_projection

BANDS = (5, 15, 25, 35, 40)


def _subtask(index, *, budget=2, optimizer="exhaustive", conditions=1):
    optimizer_spec = {"class": optimizer, "version": "v1"}
    if optimizer == "multi_start_local":
        optimizer_spec["starts"] = ["a", "b"]
    return tasks.task(
        f"toy-private-{index}",
        identity={
            "challenge": "toy-indexed",
            "contract_version": "fixture-v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy-protocol-cooling-v1",
                "variables": [
                    {"name": "protocol", "type": "enum", "values": ["a", "b"]},
                    {
                        "name": "cooling",
                        "type": "integer",
                        "min": 0,
                        "max": 1,
                        "step": 1,
                    },
                ],
                "rules": [],
            },
            "optimizer": optimizer_spec,
            "query_budget": budget,
            "seed": 314159,
            "observer_version": "toy-observer",
            "reference_bank": "private-bank-marker",
        },
        conditions=[
            {"id": f"private-condition-{i}", "stratum": "toy"}
            for i in range(conditions)
        ],
        strata={"toy": {"p": 1, "q": 1, "w": 1}},
        candidates=["a", "b"],
        actions={
            "a": {"protocol": "a", "cooling": 0},
            "b": {"protocol": "b", "cooling": 1},
        },
        objective={
            "quantity": "time",
            "unit": "toy-min",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "margin", "unit": "toy-margin", "op": ">=", "value": 0}],
    )


def _indexed(
    *, bands=BANDS, weights=None, budgets=None, optimizer="exhaustive", tolerance=0.5
):
    weights = weights or [0.2] * len(bands)
    budgets = budgets or [2] * len(bands)
    return tasks.indexed_task(
        "private-indexed-task",
        index_axis="ambient-band",
        indices=[
            {
                "index_value": band,
                "buyer_weight": weight,
                "task": _subtask(band, budget=budget, optimizer=optimizer),
            }
            for band, weight, budget in zip(bands, weights, budgets)
        ],
        query_budget=sum(budgets),
        value_equivalence={
            "quantity": "time",
            "unit": "toy-min",
            "tolerance": tolerance,
            "rule": EQUIVALENCE_RULE,
        },
    )


def _references(indexed, *, delta=0.4, bad_band=None):
    return [
        {
            "index_value": row["index_value"],
            "values": {
                (candidate, condition["id"]): {
                    "time": 10.0 if candidate == "a" else 10.0 - delta,
                    "margin": (
                        -1.0
                        if row["index_value"] == bad_band and candidate == "a"
                        else 1.0
                    ),
                }
                for candidate in row["task"]["candidates"]
                for condition in row["task"]["conditions"]
            },
        }
        for row in indexed["indices"]
    ]


def _pick_a(_index, action, _condition):
    return {
        "time": 9.0 if action["protocol"] == "a" else 10.0,
        "margin": 1.0,
    }


def test_five_band_map_has_zero_regret_within_registered_tolerance():
    indexed = _indexed()
    run = tasks.run_indexed_optimizer(indexed, _pick_a, model_id="toy-model")
    result = tasks.judge_indexed(indexed, run["commitment"], _references(indexed))
    assert run == tasks.run_indexed_optimizer(indexed, _pick_a, model_id="toy-model")
    assert run["accounting"]["attempted_queries"] == 10
    assert run["accounting"]["query_budget"] == 10
    assert run["accounting"]["exhaustive_coverage"] is True
    assert result["kind"] == "SELECTED_FEASIBLE"
    assert result["aggregate"]["selected_objective"] == pytest.approx(10)
    assert result["aggregate"]["reference_best_objective"] == pytest.approx(9.6)
    assert result["aggregate"]["regret"] == 0
    assert len(result["per_index"]) == 5
    assert all(item["outcome"]["regret"] == 0 for item in result["per_index"])
    beyond = tasks.judge_indexed(
        indexed, run["commitment"], _references(indexed, delta=0.8)
    )
    assert beyond["aggregate"]["regret"] == pytest.approx(0.8)
    assert all(
        item["outcome"]["kind"] == "SELECTED_FEASIBLE" for item in beyond["per_index"]
    )


def test_zero_weight_band_breach_makes_entire_map_infeasible():
    indexed = _indexed(bands=(5, 15), weights=[1, 0], budgets=[2, 2])
    run = tasks.run_indexed_optimizer(indexed, _pick_a, model_id="toy-model")
    result = tasks.judge_indexed(
        indexed, run["commitment"], _references(indexed, bad_band=15)
    )
    assert result["kind"] == "SELECTED_INFEASIBLE"
    assert result["per_index"][0]["outcome"]["kind"] == "SELECTED_FEASIBLE"
    assert result["per_index"][1]["outcome"]["kind"] == "SELECTED_INFEASIBLE"
    assert result["aggregate"] is None


def test_registered_quotas_hard_stop_and_multi_start_replay():
    indexed = _indexed(bands=(5, 15), weights=[0.5, 0.5], budgets=[1, 2])
    run = tasks.run_indexed_optimizer(indexed, _pick_a, model_id="toy-model")
    assert run["accounting"]["attempted_queries"] <= 3
    assert run["accounting"]["exhaustive_coverage"] is False
    assert run["accounting"]["stopped_for_budget"] is True
    assert run["accounting"]["per_index"][0]["query_budget"] == 1
    local = _indexed(
        bands=(5, 15), weights=[0.5, 0.5], budgets=[4, 4], optimizer="multi_start_local"
    )
    first = tasks.run_indexed_optimizer(local, _pick_a, model_id="toy-model")
    assert first == tasks.run_indexed_optimizer(local, _pick_a, model_id="toy-model")
    assert first["accounting"]["attempted_queries"] <= 8
    assert first["accounting"]["invalid_queries"] == sum(
        row["invalid_queries"] for row in first["accounting"]["per_index"]
    )


def test_unaffordable_condition_panel_stops_before_model_query():
    subtasks = [
        _subtask(5, budget=1, conditions=2),
        _subtask(15, budget=2, conditions=1),
    ]
    indexed = tasks.indexed_task(
        "toy-two-condition",
        index_axis="ambient-band",
        indices=[
            {"index_value": 5, "buyer_weight": 0.5, "task": subtasks[0]},
            {"index_value": 15, "buyer_weight": 0.5, "task": subtasks[1]},
        ],
        query_budget=3,
        value_equivalence={
            "quantity": "time",
            "unit": "toy-min",
            "tolerance": 0.5,
            "rule": EQUIVALENCE_RULE,
        },
    )
    queried = []

    def predict(index_value, action, condition):
        queried.append(index_value)
        return _pick_a(index_value, action, condition)

    run = tasks.run_indexed_optimizer(indexed, predict, model_id="toy-model")
    assert 5 not in queried
    assert run["accounting"]["per_index"][0]["attempted_queries"] == 0
    assert run["accounting"]["per_index"][0]["stopped_for_budget"] is True
    assert run["accounting"]["attempted_queries"] <= 3
    assert run["accounting"]["exhaustive_coverage"] is False


def test_reference_band_is_unresolved_but_objective_near_tie_is_not():
    indexed = _indexed(bands=(5, 15), weights=[0.5, 0.5], budgets=[2, 2])
    rows = json.loads(json.dumps(indexed["indices"]))
    first = rows[0]["task"]
    first["limits"][0]["band"] = 0.2
    first["task_digest"] = tasks.digest(
        {key: value for key, value in first.items() if key != "task_digest"}
    )
    indexed = tasks.indexed_task(
        indexed["task_id"],
        index_axis=indexed["identity"]["index_axis"],
        indices=rows,
        query_budget=indexed["identity"]["query_budget"],
        value_equivalence=indexed["identity"]["value_equivalence"],
    )
    run = tasks.run_indexed_optimizer(indexed, _pick_a, model_id="toy-model")
    references = _references(indexed)
    references[0]["values"][("a", "private-condition-0")]["margin"] = 0.1
    result = tasks.judge_indexed(indexed, run["commitment"], references)
    assert result["kind"] == "SELECTED_UNRESOLVED"
    assert result["reference_resolved"] is False
    assert result["aggregate"] is None
    assert len(result["per_index"]) == 2


def test_indexed_registration_and_projection_fail_closed():
    indexed = _indexed()
    projection = miner_projection(indexed)
    public = json.dumps(projection, sort_keys=True)
    for secret in (
        "private-",
        "314159",
        "starts",
        "seed",
        "task_digest",
        "bank_digest",
        "candidates",
        "0.2",
    ):
        assert secret not in public
    assert '"buyer_weight":' not in public
    assert projection["index_count"] == 5
    assert "index_value" not in public
    tampered = json.loads(json.dumps(indexed))
    tampered["indices"][0]["buyer_weight"] = 0.9
    with pytest.raises(tasks.TaskError):
        miner_projection(tampered)
    with pytest.raises(tasks.TaskError, match="weights must sum"):
        _indexed(weights=[0.3] * 5)
    with pytest.raises(tasks.TaskError, match="shared budget"):
        tasks.indexed_task(
            "bad-budget",
            index_axis="ambient-band",
            indices=indexed["indices"],
            query_budget=9,
            value_equivalence=indexed["identity"]["value_equivalence"],
        )
    with pytest.raises(tasks.TaskError, match="distinct"):
        _indexed(bands=(5, 5.0), weights=[0.5, 0.5], budgets=[2, 2])
    with pytest.raises(tasks.TaskError, match="match objective and unit"):
        tasks.indexed_task(
            "wrong-unit",
            index_axis="ambient-band",
            indices=indexed["indices"],
            query_budget=indexed["identity"]["query_budget"],
            value_equivalence={
                **indexed["identity"]["value_equivalence"],
                "unit": "seconds",
            },
        )
    run = tasks.run_indexed_optimizer(indexed, _pick_a, model_id="toy-model")
    altered = json.loads(json.dumps(run["commitment"]))
    altered["subcommitments"][0]["selected"] = "b"
    with pytest.raises(tasks.TaskError):
        tasks.judge_indexed(indexed, altered, _references(indexed))
    malformed = json.loads(json.dumps(run["commitment"]))
    malformed["subcommitments"][0]["execution"]["attempted_queries"] = "two"
    malformed["commitment_digest"] = tasks.digest(
        {key: value for key, value in malformed.items() if key != "commitment_digest"}
    )
    with pytest.raises(tasks.TaskError, match="invalid indexed query accounting"):
        tasks.judge_indexed(indexed, malformed, _references(indexed))


def _power_panels(indexed):
    references = _references(indexed, delta=1.0)
    for reference in references:
        if reference["index_value"] == 5:
            for (candidate, _condition), values in reference["values"].items():
                if candidate == "b":
                    values["margin"] = -0.1
                else:
                    values["margin"] = 0.1
    return [
        {
            "index_value": row["index_value"],
            "panel": [
                {"candidate": candidate, "condition": condition, "values": values}
                for (candidate, condition), values in reference["values"].items()
            ],
        }
        for row, reference in zip(indexed["indices"], references)
    ]


def test_indexed_power_reports_per_index_and_whole_map_without_ids(tmp_path, capsys):
    cases = []
    power_cases = []
    good_cases = []
    exposure = []
    for number in range(2):
        indexed = _indexed(bands=(5, 15), weights=[0.5, 0.5], budgets=[2, 2])
        reference = _power_panels(indexed)
        case = f"private-question-{number}"
        support_case = f"private-bank-{number}"
        cases.append(
            {
                "case": case,
                "state": "FEASIBLE_EXISTS",
                "winner": tasks.digest(["a", "b"]),
                "close_call": False,
                "refinement_demand": False,
            }
        )
        power_cases.append(
            {
                "case": case,
                "support_case": support_case,
                "task": indexed,
                "reference": reference,
            }
        )
        good_cases.append({"case": case, "predictions": reference})
        exposure.append({"support_case": support_case, "limit": 20, "used": 0})
    bank = diversity.seal_bank(
        {
            "schema": diversity.BANK_SCHEMA,
            "sealed": True,
            "exposure": exposure,
            "cases": cases,
            "indexed_power_cases": power_cases,
            "private_marker": "DO_NOT_PRINT_PRIVATE_MARKER",
        }
    )
    grid = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA,
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 2,
            "bins": [
                {"case": row["case"], "p_mass": 0.5, "q_mass": 0.5} for row in cases
            ],
            "mass_l1_error_bound": 0.0,
        }
    )
    continuous = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA,
            "kind": "continuous",
            "draw_model": "iid_with_replacement",
            "batch_size": 2,
            "bins": [
                {"case": row["case"], "p_mass": 0.5, "q_mass": 0.5} for row in cases
            ],
            "mass_l1_error_bound": 0.01,
            "integration_evidence": "toy outcome-homogeneous cells",
        }
    )
    specs = controls.register_controls(
        [
            {
                "schema": controls.CONTROL_SCHEMA,
                "name": "edge",
                "kind": "edge_optimist",
                "severity": {"margin": {"value": 0.2, "unit": "toy-margin"}},
                "limit_quantities": ["margin"],
            },
            {
                "schema": controls.CONTROL_SCHEMA,
                "name": "caution",
                "kind": "over_cautious",
                "severity": {"margin": {"value": 0.2, "unit": "toy-margin"}},
                "limit_quantities": ["margin"],
            },
            {
                "schema": controls.CONTROL_SCHEMA,
                "name": "sign",
                "kind": "localized_sign_error",
                "severity": {"margin": {"value": 0.2, "unit": "toy-margin"}},
                "limit_quantities": ["margin"],
                "region": {
                    "action": {"protocol": {"values": ["a"]}},
                    "strata": [],
                },
            },
            {
                "schema": controls.CONTROL_SCHEMA,
                "name": "path",
                "kind": "optimizer_or_lattice_aware",
                "severity": {"margin": {"value": 0.2, "unit": "toy-margin"}},
                "limit_quantities": ["margin"],
                "scope": "registered_search_path",
            },
        ]
    )
    good = power.register_good_predictor(good_cases)
    args = (bank, grid, continuous, specs, good)
    report = power.power_report(
        *args,
        alpha=0.25,
        power_target=0.5,
        simulation_seed=11,
        replicates=40,
        max_questions=4,
    )
    assert report == power.power_report(
        *args,
        alpha=0.25,
        power_target=0.5,
        simulation_seed=11,
        replicates=40,
        max_questions=4,
    )
    assert report["schema"] == "carbon.design-search.indexed-power-report.v1"
    grid_p = report["laws"]["grid"]["aggregate"]["P"]
    assert grid_p["controls"][0]["metrics"]["false_feasible"]["control"] > 0
    assert (
        report["laws"]["grid"]["per_index"][0]["views"]["P"]["controls"][0]["metrics"][
            "false_feasible"
        ]["control"]
        > 0
    )
    assert (
        report["laws"]["grid"]["per_index"][1]["views"]["P"]["controls"][0]["metrics"][
            "false_feasible"
        ]["control"]
        == 0
    )
    assert grid_p["controls"][1]["metrics"]["missed_opportunity"]["control"] > 0
    assert grid_p["controls"][2]["metrics"]["missed_opportunity"]["control"] > 0
    assert grid_p["controls"][3]["metrics"]["false_feasible"]["control"] == 0
    public = json.dumps(report)
    for secret in (
        "private-",
        "DO_NOT_PRINT_PRIVATE_MARKER",
        "winner",
        "reference_bank",
        "task_digest",
    ):
        assert secret not in public
    paths = []
    for name, value in (
        ("bank", bank),
        ("grid", grid),
        ("continuous", continuous),
        ("controls", specs),
        ("good", good),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths.append(path)
    report_main(
        [
            "power-report",
            "--bank",
            str(paths[0]),
            "--grid-law",
            str(paths[1]),
            "--continuous-law",
            str(paths[2]),
            "--controls",
            str(paths[3]),
            "--good-predictor",
            str(paths[4]),
            "--alpha",
            "0.25",
            "--power-target",
            "0.5",
            "--simulation-seed",
            "11",
            "--replicates",
            "40",
            "--max-questions",
            "4",
        ]
    )
    printed = capsys.readouterr().out
    assert json.loads(printed)["schema"] == report["schema"]
    assert "private-" not in printed
    wrong_unit = json.loads(json.dumps(specs))
    wrong_unit["controls"][0]["severity"]["margin"]["unit"] = "wrong-unit"
    wrong_unit = controls.register_controls(wrong_unit["controls"])
    with pytest.raises(tasks.TaskError, match="unit does not match"):
        power.power_report(
            bank,
            grid,
            continuous,
            wrong_unit,
            good,
            alpha=0.25,
            power_target=0.5,
            simulation_seed=11,
            replicates=10,
            max_questions=4,
        )
