"""Synthetic actual-path controls; no physical solver, pod or real data."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from carbon.design_search import tasks
from scripts.dev.battery import feasibility02 as worker
from scripts.dev.battery import guarded_reference as guarded


def _binding():
    return guarded.execution_binding(
        source_commit="a" * 40,
        source_files={path: "b" * 64 for path in guarded.REQUIRED_SOURCES},
    )


def _phase(name, start):
    cv = name == "cv"
    rest = name not in ("cc1", "cc2", "cv", "discharge")
    duration = 120 if name == "initial_rest" else 600 if rest else 10
    target = 4.0 if name == "cc1" else 2.5 if name == "discharge" else guarded.CONTROL_V
    values = (
        [target] * 3
        if cv
        else (
            [3.7] * 3
            if rest
            else (
                [3.8, 3.9, target]
                if name == "cc1"
                else [4.0, 4.1, target] if name == "cc2" else [4.0, 3.7, target]
            )
        )
    )
    times = [start, start + duration / 2, start + duration]
    points = [
        {"index": i, "time_s": t, "value_v": v}
        for i, (t, v) in enumerate(zip(times, values))
    ]
    event = (
        "C-rate cut-off [experiment]"
        if cv
        else f"Voltage {'<' if name == 'discharge' else '>'} {target} [V] [experiment]"
    )
    termination = (
        []
        if rest
        else [
            {
                "class": "CRateTermination" if cv else "VoltageTermination",
                "module": "pybamm.experiment.step.step_termination",
                "value": 0.05 if cv else target,
                "operator": None,
                "event_name": event,
            }
        ]
    )
    definition = {
        "class": "Rest" if rest else "Voltage" if cv else "CRate",
        "module": "pybamm.experiment.step.steps",
        "description": "synthetic",
        "control_kind": "voltage" if cv else "current",
        "value": (
            0
            if rest
            else (
                target
                if cv
                else -1.25 if name == "cc1" else -0.4 if name == "cc2" else 1.0
            )
        ),
        "direction": (
            "rest"
            if rest
            else None if cv else "discharge" if name == "discharge" else "charge"
        ),
        "duration_s": duration if rest else 86400,
        "terminations": termination,
    }
    samples = {
        "all": {
            "count": 3,
            "minimum": min(points, key=lambda p: p["value_v"]),
            "maximum": max(points, key=lambda p: p["value_v"]),
        },
        "strict_interior": {"count": 1, "minimum": points[1], "maximum": points[1]},
        "first": {"time_s": times[0], "voltage_v": values[0]},
        "terminal": {"time_s": times[-1], "voltage_v": values[-1]},
        "penultimate": {"time_s": times[1], "voltage_v": values[1]},
    }
    observation = {
        "schema": "carbon.battery.voltage-contact-observation.v1",
        "status": "OBSERVED",
        "descriptor": definition,
        "samples": samples,
        "termination": "final time" if rest else "event: " + event,
        "closest_event_idx": None if rest else 0,
        "terminal_state": {
            "status": "OBSERVED",
            "matches_last_observed_time": True,
            "time_s": times[-1],
            "state_count": 100,
            "Voltage [V]": values[-1],
            "Battery voltage [V]": values[-1],
            "library_closest_event_name": None if rest else event,
            "termination_events": (
                [] if rest else [{"name": event, "signed_residual": 0.0}]
            ),
            "external_circuit_class": (
                "VoltageFunctionControl" if cv else "ExplicitCurrentControl"
            ),
            "external_circuit_control": "algebraic" if cv else None,
            "current_control_equations": (
                [
                    {
                        "identity": "PROCESSED_VOLTAGE_MINUS_ACTUAL_TARGET",
                        "collection": "model.algebraic",
                        "signed_residual": 0.0,
                    }
                ]
                if cv
                else []
            ),
        },
    }
    if cv:
        observation["cv_voltage_minus_target"] = {
            "target_v": target,
            "extrema": {
                "count": 3,
                "minimum": {"value_v": 0.0},
                "maximum": {"value_v": 0.0},
            },
        }
    return {
        "t_start_s": times[0],
        "t_end_s": times[-1],
        "v_max_v": max(values),
        "v_min_v": min(values),
        "t_max_c": 27.0,
        "plating_min_v": 0.01,
        "time_observations": {
            "status": "OBSERVED_NONDECREASING",
            "observation_sample_count": 3,
            "duplicate_time_count": 0,
            "max_observed_time_gap_s": duration / 2,
        },
        "voltage_contact_observation": observation,
    }


def _record(rung=1):
    result = {
        **guarded.first_jobs()[rung - 1],
        "schema": guarded.RECORD,
        "status": "OK",
        "reference_identity": guarded.observer({}),
        "solver_provenance": {
            "schema": "carbon.battery.solver-provenance.v1",
            "solver_image": "ghcr.io/carbonphysicsai/carbon-determinism-study@"
            + guarded.IMAGE,
            "overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json",
            "overlay_lock_sha256": "sha256:6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee",
            "pybamm": "26.8.0.0",
        },
        "observation_provenance": {
            "runtime_voltage_scale": {
                "status": "OBSERVED_PARAMETER_VALUE",
                "series_cells": 1.0,
                "basis": "ACTUAL_SIMULATION_PARAMETER_VALUE_NOT_A_BOUND_CERTIFICATE",
            },
            "installed_python_sources": {
                role: {"status": "ACTUAL_INSTALLED_PYTHON_BYTES_HASHED", "sha256": sha}
                for role, sha in guarded.INSTALLED_SOURCES.items()
            },
        },
        "initial_rest": _phase("initial_rest", 0),
        "per_cycle": [],
        "capacity_all_ah": [5.0] * 30,
        "q30_over_q1": 1.0,
        "soc_clock": {"status": "REACHED", "time_s": 3000.0, "minutes": 50.0},
        "whole_programme": {"v_max_v": guarded.CONTROL_V},
    }
    time = 120
    for cycle in range(1, 31):
        phases = {}
        for name in guarded.PHASES:
            phases[name] = _phase(name, time)
            time = phases[name]["t_end_s"]
        result["per_cycle"].append({"cycle": cycle, "phases": phases})
    return result


def _observation(record, phase="cv"):
    return record["per_cycle"][0]["phases"][phase]["voltage_contact_observation"]


def _set_voltage(record, phase, values):
    summary = record["per_cycle"][0]["phases"][phase]
    d = summary["voltage_contact_observation"]
    samples = d["samples"]
    times = [
        summary["t_start_s"],
        samples["strict_interior"]["maximum"]["time_s"],
        summary["t_end_s"],
    ]
    points = [
        {"index": i, "time_s": t, "value_v": v}
        for i, (t, v) in enumerate(zip(times, values))
    ]
    samples["all"].update(
        minimum=min(points, key=lambda p: p["value_v"]),
        maximum=max(points, key=lambda p: p["value_v"]),
    )
    samples["strict_interior"].update(minimum=points[1], maximum=points[1])
    samples["first"]["voltage_v"], samples["terminal"]["voltage_v"] = (
        values[0],
        values[-1],
    )
    summary.update(v_min_v=min(values), v_max_v=max(values))
    d["terminal_state"].update(
        {"Voltage [V]": values[-1], "Battery voltage [V]": values[-1]}
    )
    if phase == "cv":
        d["cv_voltage_minus_target"]["extrema"]["minimum"]["value_v"] = (
            min(values) - guarded.CONTROL_V
        )
        d["cv_voltage_minus_target"]["extrema"]["maximum"]["value_v"] = (
            max(values) - guarded.CONTROL_V
        )
    record["whole_programme"]["v_max_v"] = max(
        [record["initial_rest"]["v_max_v"]]
        + [p["v_max_v"] for c in record["per_cycle"] for p in c["phases"].values()]
    )


def test_valid_three_rung_tracking_and_numerics_only_release_first_triple():
    rows = [_record(rung) for rung in (1, 2, 3)]
    before = copy.deepcopy(rows)
    receipt = guarded.calibration_report(_binding(), rows)
    assert receipt["status"] == "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
    assert all(row["checked_phases"] == 181 for row in receipt["tracking"].values())
    assert receipt["full_calibration_release"] is False
    assert receipt["evaluation_release"] is receipt["n1_release"] is False
    assert receipt["legacy_train_or_fit_compatibility"] == "NOT_ESTABLISHED"
    assert rows == before


@pytest.mark.parametrize(
    "phase,values,reason",
    [
        ("cc2", [4.0, 4.195, 4.19], "CC2_INTERIOR_TRACKING"),
        ("cv", [4.199] * 3, "CV_SAMPLE_TRACKING"),
        ("rest_after_charge", [4.1, 4.200000000000001, 4.1], "RAW_VOLTAGE_ABOVE_4_2"),
    ],
)
def test_converged_but_wrong_tracking_and_strict_physical_excess_are_refused(
    phase, values, reason
):
    rows = [_record(rung) for rung in (1, 2, 3)]
    for row in rows:
        _set_voltage(row, phase, values)
    receipt = guarded.calibration_report(_binding(), rows)
    assert receipt["numerical"]["status"] == (
        "NUMERICAL_CALIBRATION_INADEQUATE"
        if phase == "rest_after_charge"
        else "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
    )
    assert receipt["status"] == "REFERENCE_UNRESOLVED"
    assert reason in receipt["tracking"][rows[0]["case_id"]]["reasons"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: _observation(r, "cc2").update(termination="final time"),
        lambda r: _observation(r, "cc2")["terminal_state"]["termination_events"][
            0
        ].update(signed_residual=2e-6),
        lambda r: _observation(r)["terminal_state"]["current_control_equations"][
            0
        ].update(signed_residual=2e-6),
        lambda r: _observation(r)["terminal_state"]["current_control_equations"][
            0
        ].update(identity="different equation with zero residual"),
        lambda r: _observation(r)["descriptor"].update(value=4.2),
        lambda r: _observation(r)["descriptor"].update(control_kind="current"),
        lambda r: _observation(r)["descriptor"]["terminations"][0].update(value=0.1),
        lambda r: _observation(r)["terminal_state"]["current_control_equations"][
            0
        ].update(collection="model.rhs"),
        lambda r: r["observation_provenance"].update(runtime_voltage_scale=None),
        lambda r: r["observation_provenance"].update(runtime_voltage_scale=[]),
        lambda r: r["observation_provenance"].update(runtime_voltage_scale=1),
        lambda r: r["observation_provenance"]["runtime_voltage_scale"].update(
            series_cells=2
        ),
        lambda r: r["observation_provenance"]["runtime_voltage_scale"].update(
            series_cells=True
        ),
        lambda r: r["observation_provenance"]["installed_python_sources"][
            "voltage_control"
        ].update(sha256="0" * 64),
        lambda r: r["per_cycle"].pop(),
        lambda r: r["per_cycle"][0]["phases"].pop("discharge"),
        lambda r: r["per_cycle"][0]["phases"]["cv"]["time_observations"].update(
            duplicate_time_count=1
        ),
        lambda r: _observation(r)["samples"]["all"]["maximum"].update(
            value_v=float("nan")
        ),
        lambda r: _observation(r)["terminal_state"].update(status="UNAVAILABLE"),
        lambda r: r.update(reference_identity={"id": "old-observer"}),
        lambda r: r.update(reference_method="legacy"),
        lambda r: r["solver_provenance"].update(pybamm="wrong-version"),
    ],
)
def test_missing_wrong_ambiguous_nonfinite_or_partial_evidence_is_unresolved(mutation):
    row = _record()
    mutation(row)
    result = guarded.calibration_report(_binding(), [row])
    assert result["status"] == "REFERENCE_UNRESOLVED"
    json.dumps(result, allow_nan=False)


def test_old_rows_incomplete_or_duplicate_triples_never_release():
    binding = _binding()
    assert (
        guarded.calibration_report(binding, [_record()])["status"]
        == "INCOMPLETE_REFERENCE"
    )
    assert (
        guarded.calibration_report(binding, [_record(), _record()])["status"]
        == "REFERENCE_UNRESOLVED"
    )
    old = _record()
    old["case_id"] = old["case_id"].replace("guarded419-v1:", "")
    assert (
        guarded.calibration_report(binding, [old])["status"] == "REFERENCE_UNRESOLVED"
    )


def test_exact_first_tuple_binding_refuses_more_cases_source_drift_or_legacy_jobs(
    tmp_path,
):
    files = {}
    for path in guarded.REQUIRED_SOURCES:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"synthetic source")
        files[path] = hashlib.sha256(target.read_bytes()).hexdigest()
    binding = guarded.execution_binding(source_commit="a" * 40, source_files=files)
    guarded.validate_binding(binding, guarded.inputs(), root=tmp_path)
    changed = copy.deepcopy(guarded.inputs())
    changed["jobs"].append({**changed["jobs"][0], "t_amb_c": 15})
    with pytest.raises(tasks.TaskError):
        guarded.validate_binding(binding, changed, root=tmp_path)
    (tmp_path / guarded.MODULE).write_bytes(b"changed")
    with pytest.raises(tasks.TaskError):
        guarded.validate_binding(binding, guarded.inputs(), root=tmp_path)


def test_worker_guarded_protocol_is_explicit_and_legacy_simulation_unchanged(
    monkeypatch,
):
    from carbon.battery import reference

    captured = []

    class Parameters(dict):
        def __init__(self, _):
            super().__init__(
                {worker.H_NAME: 1, worker.AREA_NAME: 1, worker.CAPACITY_NAME: 5}
            )

    fake = SimpleNamespace(
        lithium_ion=SimpleNamespace(DFN=lambda _: "synthetic-model"),
        ParameterValues=Parameters,
        IDAKLUSolver=lambda **kw: kw,
        Experiment=lambda cycles: cycles,
        Simulation=lambda *args, **kw: captured.append(kw),
    )
    monkeypatch.setitem(sys.modules, "pybamm", fake)
    before = copy.deepcopy(reference.SPEC)
    worker._simulation(guarded.first_jobs()[0])
    guarded_spec = captured[-1]
    assert "4.19 V" in guarded_spec["experiment"][0][2]
    assert "4.19 V" in guarded_spec["experiment"][0][3]
    assert guarded_spec["experiment_model_mode"] == "legacy"
    legacy = {
        k: v
        for k, v in guarded.first_jobs()[0].items()
        if not k.startswith("reference_method")
    }
    worker._simulation(legacy)
    assert "4.2 V" in captured[-1]["experiment"][0][2]
    assert "experiment_model_mode" not in captured[-1]
    assert reference.SPEC == before


def test_unbound_solve_refuses_guarded_jobs_before_pool_or_solver(
    tmp_path, monkeypatch
):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps(guarded.inputs()), encoding="utf-8")
    monkeypatch.setattr(
        worker, "ProcessPoolExecutor", lambda *_: pytest.fail("unbound worker pool")
    )
    from carbon.battery import truth_env

    monkeypatch.setattr(truth_env, "provenance", lambda _: {})
    with pytest.raises(ValueError, match="prospectively bound"):
        worker.solve(jobs, tmp_path / "records", 2)


@pytest.mark.parametrize("failure", ["none", "wrong_hold", "null_scale"])
def test_real_guarded_collector_path_persists_all_rows_and_checks_tracking(
    tmp_path, monkeypatch, failure
):
    from carbon.battery import truth_env

    binding = _binding()
    submitted = []

    class Future:
        def __init__(self, job):
            self.job = job

        def result(self):
            row = _record(self.job["rung"])
            if failure == "wrong_hold":
                _set_voltage(row, "cv", [4.199] * 3)
            elif failure == "null_scale":
                row["observation_provenance"]["runtime_voltage_scale"] = None
            return row

    class Pool:
        def __init__(self, workers):
            assert workers == 2

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, function, job):
            assert function is worker._timed
            submitted.append(job)
            return Future(job)

    monkeypatch.setattr(
        worker, "_calibration_contract", lambda *_: (binding, [guarded.first_jobs()])
    )
    monkeypatch.setattr(worker, "ProcessPoolExecutor", Pool)
    monkeypatch.setattr(worker, "as_completed", lambda futures: list(futures))
    monkeypatch.setattr(
        truth_env, "provenance", lambda _: _record()["solver_provenance"]
    )
    monkeypatch.setattr(truth_env, "stamp", lambda row, _: row)
    output = tmp_path / "records.jsonl"
    result = worker.solve_calibration(None, output, 2, None, "synthetic-binding-sha")
    rows = [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()
    ]
    receipt = json.loads(
        output.with_name(output.name + ".calibration.json").read_text(encoding="utf-8")
    )
    assert len(rows) == len(submitted) == 3
    assert all(row["status"] == "OK" for row in rows)
    assert (
        receipt["schema"]
        == "carbon.scorelab.guarded419-calibration-execution-receipt.v1"
    )
    assert receipt["records_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert receipt["full_calibration_release"] is False
    if failure != "none":
        assert result == 2
        assert receipt["status"] == "REFERENCE_UNRESOLVED"
        assert all(row["whole_programme"]["v_max_v"] < 4.2 for row in rows)
        assert (
            receipt["calibration"]["numerical"]["status"]
            == "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
        )
    else:
        assert result == 0
        assert receipt["status"] == "COMPATIBLE_GUARDED_FIRST_TRIPLE_ONLY"


def test_numeric_failure_cannot_be_compensated_by_tracking():
    rows = [_record(rung) for rung in (1, 2, 3)]
    rows[2]["soc_clock"].update(time_s=12000.0, minutes=200.0)
    report = guarded.calibration_report(_binding(), rows)
    assert all(
        r["status"] == "TRACKING_COMPATIBLE" for r in report["tracking"].values()
    )
    assert report["status"] == "REFERENCE_UNRESOLVED"
    assert report["numerical"]["status"] == "NUMERICAL_CALIBRATION_INADEQUATE"


@pytest.mark.parametrize(
    "collection,correct_relation,stale_class,compatible",
    [
        ("algebraic", True, "ExplicitCurrentControl", True),
        ("rhs", True, "ExplicitCurrentControl", False),
        ("algebraic", False, "ExplicitCurrentControl", False),
        ("rhs", True, "VoltageFunctionControl", False),
    ],
)
def test_cv_extraction_uses_actual_processed_algebraic_equation_not_stale_submodel(
    collection, correct_relation, stale_class, compatible
):
    class Symbol:
        def __init__(self, code, function):
            self.code, self.function = code, function

        def __sub__(self, target):
            return Symbol(
                ("subtract", self.code, target), lambda y: self.function(y) - target
            )

        def __eq__(self, other):
            return isinstance(other, Symbol) and self.code == other.code

        def __str__(self):
            return repr(self.code)

        def evaluate(self, *, t, y, inputs):
            return self.function(y)

    class Unprocessed:
        def evaluate(self, **_):
            pytest.fail("must use the pinned public processed-variable accessor")

    class Variable:
        name = "Current variable [A]"

    class Step(dict):
        pass

    record = _record()
    phase = record["per_cycle"][0]["phases"]["cv"]
    start, end = phase["t_start_s"], phase["t_end_s"]
    sample = Step(
        {
            "Time [s]": SimpleNamespace(entries=[start, (start + end) / 2, end]),
            "Voltage [V]": SimpleNamespace(entries=[guarded.CONTROL_V] * 3),
        }
    )
    sample.termination = "event: C-rate cut-off [experiment]"
    sample.closest_event_idx = 0
    sample.t_event, sample.y_event = [end], [[guarded.CONTROL_V]]
    voltage = Symbol("processed_voltage", lambda y: float(y[0, 0]))
    equation = (
        voltage - guarded.CONTROL_V
        if correct_relation
        else Symbol("wrong_zero_equation", lambda y: 0.0)
    )
    actual = {Variable(): equation}
    circuit = type(
        stale_class,
        (),
        {"control": "algebraic" if stale_class == "VoltageFunctionControl" else None},
    )()
    model = SimpleNamespace(
        algebraic=actual if collection == "algebraic" else {},
        rhs=actual if collection == "rhs" else {},
        submodels={"external circuit": circuit},
        variables={"Voltage [V]": Unprocessed(), "Battery voltage [V]": Unprocessed()},
        get_processed_variable_or_event=lambda _: voltage,
        events=[
            SimpleNamespace(
                name="C-rate cut-off [experiment]",
                event_type=SimpleNamespace(name="TERMINATION"),
                expression=Symbol("cutoff_residual", lambda y: 0.0),
            )
        ],
    )
    sample.all_models, sample.all_inputs = [model], [{}]
    termination = type(
        "CRateTermination",
        (),
        {
            "__module__": "pybamm.experiment.step.step_termination",
            "value": 0.05,
            "operator": None,
            "get_event_name": lambda *_: "C-rate cut-off [experiment]",
        },
    )()
    definition = type(
        "Voltage",
        (),
        {
            "__module__": "pybamm.experiment.step.steps",
            "value": guarded.CONTROL_V,
            "description": "synthetic actual CV descriptor",
            "direction": None,
            "duration": 86400,
            "control_kind": SimpleNamespace(value="voltage"),
            "termination": [termination],
        },
    )()
    observation = worker._voltage_contact_observation(sample, definition)
    phase["voltage_contact_observation"] = observation
    terminal = observation["terminal_state"]
    assert terminal["status"] == "OBSERVED"
    assert terminal["external_circuit_class"] == stale_class
    equations = terminal["current_control_equations"]
    if collection == "algebraic":
        assert equations[0]["collection"] == "model.algebraic"
        assert equations[0]["signed_residual"] == 0
    report = guarded.tracking_report(record)
    assert (report["status"] == "TRACKING_COMPATIBLE") is compatible
    if not compatible:
        assert "CV_EQUATION_TRACKING" in report["reasons"]
