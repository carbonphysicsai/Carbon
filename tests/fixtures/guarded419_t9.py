"""Synthetic-only raw delivery factory. Never imported by production code."""

from __future__ import annotations

import hashlib
import json

from carbon.design_search import tasks
from scripts.dev.battery import guarded_reference as guard
from scripts.dev.score_lab import guarded419_t9 as t9


def _bytes(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _phase(name, start, job):
    rest = name not in ("cc1", "cc2", "cv", "discharge")
    cv = name == "cv"
    duration = 120 if name == "initial_rest" else 600 if rest else 900
    target = (
        job["switch_voltage_v"]
        if name == "cc1"
        else 2.5 if name == "discharge" else guard.CONTROL_V
    )
    values = (
        [3.7] * 3
        if rest
        else [target] * 3 if cv else [target - 0.1, target - 0.05, target]
    )
    points = [
        {"index": i, "time_s": start + i * duration / 2, "value_v": v}
        for i, v in enumerate(values)
    ]
    event = (
        "C-rate cut-off [experiment]"
        if cv
        else f"Voltage {'<' if name == 'discharge' else '>'} {target} [V] [experiment]"
    )
    definition = {
        "class": "Rest" if rest else "Voltage" if cv else "CRate",
        "module": "pybamm.experiment.step.steps",
        "description": "SYNTHETIC_FIXTURE",
        "control_kind": "voltage" if cv else "current",
        "value": (
            0
            if rest
            else (
                target
                if cv
                else (
                    -job["c1"]
                    if name == "cc1"
                    else -job["c2"] if name == "cc2" else 1.0
                )
            )
        ),
        "direction": (
            "rest"
            if rest
            else None if cv else "discharge" if name == "discharge" else "charge"
        ),
        "duration_s": duration,
        "terminations": (
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
        ),
    }
    observation = {
        "schema": "carbon.battery.voltage-contact-observation.v1",
        "status": "OBSERVED",
        "descriptor": definition,
        "termination": "final time" if rest else "event: " + event,
        "closest_event_idx": None if rest else 0,
        "samples": {
            "all": {
                "count": 3,
                "minimum": min(points, key=lambda p: p["value_v"]),
                "maximum": max(points, key=lambda p: p["value_v"]),
            },
            "strict_interior": {"count": 1, "minimum": points[1], "maximum": points[1]},
            "first": {"time_s": start, "voltage_v": values[0]},
            "terminal": {"time_s": start + duration, "voltage_v": values[-1]},
        },
        "terminal_state": {
            "status": "OBSERVED",
            "matches_last_observed_time": True,
            "time_s": start + duration,
            "state_count": 100,
            "Voltage [V]": values[-1],
            "Battery voltage [V]": values[-1],
            "termination_events": (
                [] if rest else [{"name": event, "signed_residual": 0.0}]
            ),
            "library_closest_event_name": None if rest else event,
            "external_circuit_class": "ExplicitCurrentControl",
            "external_circuit_control": None,
            "current_control_equations": (
                [
                    {
                        "collection": "model.algebraic",
                        "identity": "PROCESSED_VOLTAGE_MINUS_TARGET_OVER_CURRENT_SCALE",
                        "signed_residual": 0.0,
                        "normalization": {
                            "schema": "carbon.battery.cv-equation-normalization.v1",
                            "status": "VERIFIED_SYMBOLIC_RELATION",
                            "scale_source": "OPERATIVE_ALGEBRAIC_VARIABLE_SCALE",
                            "parameter_source": "OPERATIVE_MODEL_SYMBOL_PROCESSOR_PARAMETER_VALUES",
                            "parameter_name": "Nominal cell capacity [A.h]",
                            "scale_is_constant": True,
                            "scale": 5.0,
                            "nominal_capacity_ah": 5.0,
                            "target_v": target,
                            "symbolic_equality_basis": "PINNED_PYBAMM_FULL_SYMBOL_IDENTITY",
                            "normalized_residual_units": "SOLVER_NORMALIZED",
                            "voltage_residual_units": "V",
                            "signed_voltage_residual_v": 0.0,
                            "independent_voltage_residual_v": 0.0,
                        },
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
        "t_start_s": start,
        "t_end_s": start + duration,
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


def record(job, *, fixture=True):
    guarded_t9 = "reference_admission" in job
    row = {
        **job,
        "schema": t9.RECORD if guarded_t9 else guard.RECORD,
        "status": "OK",
        "fixture": fixture,
        "reference_identity": t9.observer() if guarded_t9 else guard.observer({}),
        "solver_provenance": {
            "schema": "carbon.battery.solver-provenance.v1",
            "solver_image": "ghcr.io/carbonphysicsai/carbon-determinism-study@"
            + guard.IMAGE,
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
                for role, sha in guard.INSTALLED_SOURCES.items()
            },
        },
        "initial_rest": _phase("initial_rest", 0, job),
        "per_cycle": [],
        "capacity_all_ah": [5.0] * 30,
        "q30_over_q1": 1.0,
        "soc_clock": {"status": "REACHED", "time_s": 1800.0, "minutes": 30.0},
        "whole_programme": {"v_max_v": guard.CONTROL_V, "t_max_c": 27.0},
    }
    time = 120
    for cycle in range(1, 31):
        phases = {}
        for name in guard.PHASES:
            phases[name] = _phase(name, time, job)
            time = phases[name]["t_end_s"]
        row["per_cycle"].append({"cycle": cycle, "phases": phases})
    return row


def refresh_delivery(delivery, records):
    raw = b"".join(_bytes(row) for row in records)
    mappings = [
        {"line": i, "job_id": row["case_id"]} for i, row in enumerate(records, 1)
    ]
    manifest = t9.delivery_manifest(delivery["binding"], raw, mappings)
    delivery.update(
        manifest=manifest,
        raw_chunks={"t9": raw},
        expected_manifest_digest=tasks.digest(manifest),
    )
    return delivery


def make_delivery(tmp_path, *, scope="SYNTHETIC_FIXTURE"):
    files = {}
    for path in t9.REQUIRED_SOURCES:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"SYNTHETIC_SOURCE_ONLY")
        files[path] = hashlib.sha256(target.read_bytes()).hexdigest()
    prior = guard.execution_binding(
        source_commit="a" * 40,
        source_files={p: files[p] for p in guard.REQUIRED_SOURCES},
    )
    raw_binding = _bytes(prior)
    rows = [record(j, fixture=scope == "SYNTHETIC_FIXTURE") for j in guard.first_jobs()]
    raw_records = b"".join(_bytes(r) for r in rows)
    report = guard.calibration_report(prior, rows)
    receipt = {
        "schema": "carbon.scorelab.guarded419-calibration-execution-receipt.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "binding_sha256": hashlib.sha256(raw_binding).hexdigest(),
        "execution_source": prior["execution_source"],
        "source_files": prior["source_files"],
        "observer": prior["observer"],
        "plan_digest": prior["plan_digest"],
        "offered_jobs_digest": tasks.digest(guard.first_jobs()),
        "per_job": {j["case_id"]: "OK" for j in guard.first_jobs()},
        "per_completed_triple": [report],
        "status": "COMPATIBLE_GUARDED_FIRST_TRIPLE_ONLY",
        "full_calibration_release": False,
        "qualification": False,
        "records_sha256": hashlib.sha256(raw_records).hexdigest(),
        "calibration": report,
    }
    raw_receipt = _bytes(receipt)
    binding = t9.execution_binding(
        source_commit="c" * 40,
        source_files=files,
        scope=scope,
        dispatch_id="SYNTHETIC_ROOT_DISPATCH",
        g0={
            "binding_sha256": hashlib.sha256(raw_binding).hexdigest(),
            "records_sha256": hashlib.sha256(raw_records).hexdigest(),
            "receipt_sha256": hashlib.sha256(raw_receipt).hexdigest(),
        },
    )
    return refresh_delivery(
        {
            "binding": binding,
            "expected_binding_digest": tasks.digest(binding),
            "g0_binding": raw_binding,
            "g0_raw": raw_records,
            "g0_receipt": raw_receipt,
        },
        [record(j, fixture=scope == "SYNTHETIC_FIXTURE") for j in t9.jobs()],
    )
