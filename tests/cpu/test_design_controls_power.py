"""Toy-only behaviour controls and producer power diagnostics."""

from __future__ import annotations

import json

import pytest

from carbon.battery.value import panel as battery_panel
from carbon.design_search import controls, diversity, power, tasks
from carbon.design_search.__main__ import main


def _task(case, cluster, threshold):
    return tasks.task(
        case,
        identity={
            "challenge": "toy-control",
            "contract_version": "v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "toy-grid.v1",
                "variables": [
                    {"name": "x", "type": "integer", "min": 0, "max": 2, "step": 1}
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 3,
            "seed": 7,
            "observer_version": "toy-observer.v1",
            "reference_bank": cluster,
        },
        conditions=[{"id": "probe", "stratum": "boundary"}],
        strata={"boundary": {"p": 1, "q": 1, "w": 1}},
        candidates=["a", "b", "c"],
        actions={"a": {"x": 0}, "b": {"x": 1}, "c": {"x": 2}},
        objective={
            "quantity": "cost",
            "unit": "toy",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "safety", "unit": "toy", "op": ">=", "value": threshold}],
    )


def _reference():
    return [
        {
            "candidate": "a",
            "condition": "probe",
            "values": {"cost": 2.0, "safety": 2.0},
        },
        {
            "candidate": "b",
            "condition": "probe",
            "values": {"cost": 1.0, "safety": 0.1},
        },
        {
            "candidate": "c",
            "condition": "probe",
            "values": {"cost": 0.0, "safety": -0.1},
        },
    ]


def _control(name, kind, severity, **extra):
    return {
        "schema": controls.CONTROL_SCHEMA,
        "name": name,
        "kind": kind,
        "severity": {"safety": {"value": severity, "unit": "toy"}},
        "limit_quantities": ["safety"],
        **extra,
    }


def test_control_severity_requires_each_quantity_and_matching_unit():
    task = _task("two-units", "bank", 0.0)
    task["limits"].append(
        {"quantity": "temperature", "unit": "degC", "op": "<=", "value": 45.0}
    )
    task["task_digest"] = tasks.digest(
        {key: value for key, value in task.items() if key != "task_digest"}
    )
    spec = _control("edge", "edge_optimist", 0.2)
    spec["limit_quantities"].append("temperature")
    spec["severity"]["temperature"] = {"value": 0.5, "unit": "degC"}
    controls.validate_controls(controls.register_controls([spec]), task=task)
    predicted = controls.task_control_prediction(
        task,
        spec,
        {"x": 1},
        task["conditions"][0],
        {"cost": 0.0, "safety": -0.1, "temperature": 45.3},
    )
    assert predicted["safety"] > 0
    assert predicted["temperature"] < 45

    wrong_unit = json.loads(json.dumps(spec))
    wrong_unit["severity"]["safety"]["unit"] = "degC"
    with pytest.raises(tasks.TaskError, match="unit does not match"):
        controls.validate_controls(controls.register_controls([wrong_unit]), task=task)
    missing = json.loads(json.dumps(spec))
    del missing["severity"]["temperature"]
    with pytest.raises(tasks.TaskError, match="one severity per controlled"):
        controls.register_controls([missing])
    scalar = json.loads(json.dumps(spec))
    scalar["severity"] = 0.5
    with pytest.raises(tasks.TaskError, match="one severity per controlled"):
        controls.register_controls([scalar])


def _fixture(*, clusters=("sealed-bank-1", "sealed-bank-2")):
    cases = []
    power_cases = []
    predictor_cases = []
    for cluster in clusters:
        for suffix, threshold in (("edge", 0.0), ("caution", 1.9)):
            case = f"private-{cluster}-{suffix}"
            task = _task(case, cluster, threshold)
            reference = _reference()
            truth = tasks.assess(
                task,
                {
                    (row["candidate"], row["condition"]): row["values"]
                    for row in reference
                },
                reference=True,
            )
            cases.append(
                {
                    "case": case,
                    "state": tasks.reference_state(task, truth),
                    "winner": tasks.select(task, truth),
                    "close_call": suffix == "edge",
                    "refinement_demand": False,
                }
            )
            power_cases.append(
                {
                    "case": case,
                    "support_case": cluster,
                    "task": task,
                    "reference": reference,
                }
            )
            predictor_cases.append({"case": case, "predictions": reference})
    bank = diversity.seal_bank(
        {
            "schema": diversity.BANK_SCHEMA,
            "sealed": True,
            "exposure": [
                {"support_case": cluster, "limit": 20, "used": 0}
                for cluster in clusters
            ],
            "cases": cases,
            "power_cases": power_cases,
            "private_marker": "NEVER_EXPORT_PRIVATE_MARKER",
        }
    )
    count = len(cases)
    grid = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA,
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 4,
            "bins": [
                {"case": row["case"], "p_mass": 1 / count, "q_mass": 1 / count}
                for row in cases
            ],
            "mass_l1_error_bound": 0.0,
        }
    )
    continuous = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA,
            "kind": "continuous",
            "draw_model": "iid_with_replacement",
            "batch_size": 4,
            "bins": [
                {
                    "case": row["case"],
                    "p_mass": (2 if row["case"].endswith("edge") else 1)
                    / (count * 1.5),
                    "q_mass": (1 if row["case"].endswith("edge") else 2)
                    / (count * 1.5),
                }
                for row in cases
            ],
            "mass_l1_error_bound": 0.01,
            "integration_evidence": "toy outcome-homogeneous cells",
        }
    )
    specs = controls.register_controls(
        [
            _control("edge", "edge_optimist", 0.25),
            _control("caution", "over_cautious", 0.2),
            _control(
                "sign",
                "localized_sign_error",
                0.25,
                region={"action": {"x": {"min": 2, "max": 2}}, "strata": ["boundary"]},
            ),
            _control(
                "lattice",
                "optimizer_or_lattice_aware",
                0.25,
                scope="registered_lattice",
            ),
        ]
    )
    good = power.register_good_predictor(predictor_cases)
    return bank, grid, continuous, specs, good


def _report(fixture):
    return power.power_report(
        *fixture,
        alpha=0.25,
        power_target=0.2,
        simulation_seed=11,
        replicates=300,
        max_questions=8,
    )


def test_battery_historical_controls_have_exact_neutral_parity():
    references = {
        f"case-{i}": {
            "status": "OK",
            "outputs": {
                "plating_margin_v": margin,
                "temperature_c": [20.0, peak - 1, peak],
                "voltage_v": [3.0, 3.5, 4.0],
                "extra": {"keep": [1, 2]},
            },
        }
        for i, (margin, peak) in enumerate(
            ((-0.012, 44.0), (-0.005, 45.0), (0.0, 47.0), (0.003, 48.5), (0.01, 50.0))
        )
    }
    references["unresolved"] = {"status": "FAILED_INFRA", "outputs": {}}
    original = json.dumps(references, sort_keys=True)
    for kind in battery_panel.CONTROLS:
        assert controls.battery_control_predictions(
            kind, references
        ) == battery_panel.control_predictions(kind, references)
    assert json.dumps(references, sort_keys=True) == original


def test_task_control_behaviour_uses_signed_reference_margins():
    task = _task("toy", "bank", 0.0)
    condition = task["conditions"][0]
    near_fail = {"cost": 0.0, "safety": -0.1}
    near_pass = {"cost": 1.0, "safety": 0.1}
    edge = _control("edge", "edge_optimist", 0.2)
    caution = _control("caution", "over_cautious", 0.2)
    sign = _control(
        "sign",
        "localized_sign_error",
        0.2,
        region={"action": {"x": {"min": 2, "max": 2}}, "strata": ["boundary"]},
    )
    assert (
        controls.task_control_prediction(task, edge, {"x": 2}, condition, near_fail)[
            "safety"
        ]
        > 0
    )
    assert (
        controls.task_control_prediction(task, caution, {"x": 1}, condition, near_pass)[
            "safety"
        ]
        < 0
    )
    assert (
        controls.task_control_prediction(task, sign, {"x": 2}, condition, near_fail)[
            "safety"
        ]
        > 0
    )
    assert (
        controls.task_control_prediction(task, sign, {"x": 1}, condition, near_fail)
        == near_fail
    )
    lattice = _control(
        "lattice", "optimizer_or_lattice_aware", 0.2, scope="registered_lattice"
    )
    assert (
        controls.task_control_prediction(task, lattice, {"x": 2}, condition, near_fail)
        == near_fail
    )
    assert (
        controls.task_control_prediction(
            task, lattice, {"x": 1.5}, condition, near_fail
        )["safety"]
        > near_fail["safety"]
    )
    path = _control(
        "path", "optimizer_or_lattice_aware", 0.2, scope="registered_search_path"
    )
    known_path = {tasks.digest({"x": 1})}
    assert (
        controls.task_control_prediction(
            task,
            path,
            {"x": 1},
            condition,
            near_fail,
            accurate_actions=known_path,
        )
        == near_fail
    )
    assert (
        controls.task_control_prediction(
            task,
            path,
            {"x": 2},
            condition,
            near_fail,
            accurate_actions=known_path,
        )["safety"]
        > near_fail["safety"]
    )
    upper = _task("upper", "bank", 0.0)
    upper["limits"][0]["op"] = "<="
    upper["task_digest"] = tasks.digest(
        {key: value for key, value in upper.items() if key != "task_digest"}
    )
    assert (
        controls.task_control_prediction(
            upper, edge, {"x": 2}, condition, {"cost": 0.0, "safety": 0.1}
        )["safety"]
        < 0
    )


def test_power_report_retains_cluster_and_compares_grid_with_continuous():
    fixture = _fixture()
    report = _report(fixture)
    assert report == _report(fixture)
    assert set(report["laws"]) == {"grid", "continuous"}
    grid = report["laws"]["grid"]
    continuous = report["laws"]["continuous"]
    assert grid["P"]["controls"][0]["metrics"]["false_feasible"]["control"] > 0
    assert grid["P"]["controls"][1]["metrics"]["missed_opportunity"]["control"] > 0
    assert grid["P"]["controls"][3]["metrics"]["false_feasible"]["control"] == 0
    assert (
        grid["P"]["controls"][3]["metrics"]["false_feasible"]["power"][
            "first_questions_meeting_target_estimate"
        ]
        is None
    )
    assert (
        continuous["P"]["controls"][0]["metrics"]["false_feasible"]["control"]
        != continuous["Q"]["controls"][0]["metrics"]["false_feasible"]["control"]
    )
    assert (
        grid["P"]["controls"][0]["metrics"]["false_feasible"]["power"]["points"][-1][
            "mean_nonzero_bank_clusters"
        ]
        <= 2
    )
    serialized = json.dumps(report)
    for secret in (
        "private-",
        "sealed-bank",
        "NEVER_EXPORT_PRIVATE_MARKER",
        "task_digest",
        "reference_bank",
        "winner",
    ):
        assert secret not in serialized


def test_shared_bank_variants_never_become_independent_signs():
    report = _report(_fixture(clusters=("one-protected-bank",)))
    curve = report["laws"]["grid"]["P"]["controls"][0]["metrics"]["false_feasible"][
        "power"
    ]
    assert all(
        point["estimated_detection_probability"] == 0 for point in curve["points"]
    )
    assert curve["first_questions_meeting_target_estimate"] is None


def test_unresolved_question_stays_in_draw_mass_but_not_resolved_evidence():
    bank, grid, continuous, specs, good = _fixture()
    task = bank["power_cases"][0]["task"]
    task["limits"][0]["band"] = 0.2
    task["task_digest"] = tasks.digest(
        {key: value for key, value in task.items() if key != "task_digest"}
    )
    bank["cases"][0]["state"] = "UNRESOLVED"
    bank["cases"][0]["winner"] = None
    bank = diversity.seal_bank(
        {key: value for key, value in bank.items() if key != "seal_digest"}
    )
    report = _report((bank, grid, continuous, specs, good))
    view = report["laws"]["grid"]["P"]
    assert view["unresolved_mass"] == 0.25
    assert view["controls"][0]["metrics"]["false_feasible"]["common_mass"] == 0.75


def test_power_inputs_fail_closed_and_cli_prints_aggregates_only(tmp_path, capsys):
    bank, grid, continuous, specs, good = _fixture()
    wrong_unit = json.loads(json.dumps(specs))
    wrong_unit["controls"][0]["severity"]["safety"]["unit"] = "degC"
    wrong_unit = controls.register_controls(wrong_unit["controls"])
    with pytest.raises(tasks.TaskError, match="unit does not match"):
        _report((bank, grid, continuous, wrong_unit, good))
    tampered = json.loads(json.dumps(good))
    tampered["cases"][0]["predictions"][0]["values"]["safety"] = 999
    with pytest.raises(tasks.TaskError):
        _report((bank, grid, continuous, specs, tampered))
    mixed_units = json.loads(json.dumps(bank))
    mixed_task = mixed_units["power_cases"][0]["task"]
    mixed_task["objective"]["unit"] = "incompatible-toy-unit"
    mixed_task["task_digest"] = tasks.digest(
        {key: value for key, value in mixed_task.items() if key != "task_digest"}
    )
    mixed_units = diversity.seal_bank(
        {key: value for key, value in mixed_units.items() if key != "seal_digest"}
    )
    with pytest.raises(tasks.TaskError, match="share an objective"):
        _report((mixed_units, grid, continuous, specs, good))
    with pytest.raises(tasks.TaskError):
        power.power_report(
            bank,
            grid,
            continuous,
            specs,
            good,
            alpha=None,
            power_target=0.8,
            simulation_seed=1,
            replicates=10,
            max_questions=4,
        )
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
    main(
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
            "0.2",
            "--simulation-seed",
            "11",
            "--replicates",
            "10",
            "--max-questions",
            "4",
        ]
    )
    output = capsys.readouterr().out
    assert json.loads(output)["schema"] == power.REPORT_SCHEMA
    assert "private-" not in output and "NEVER_EXPORT_PRIVATE_MARKER" not in output
