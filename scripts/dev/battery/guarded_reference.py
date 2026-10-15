"""Owner-approved PUBLIC_DEVELOPMENT guarded reference, first triple only.

Pure contracts/reduction; no solver, provider or credentials. Legacy records,
the legacy numerical policy and production interfaces retain their semantics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from carbon.design_search import tasks
from scripts.dev.score_lab import owner_v3_numerics as numerics
from scripts.dev.score_lab import owner_v3_panel_export as producer

METHOD_ID = "carbon.scorelab.battery-v3.guarded419-protocol.v1"
OBSERVER = "carbon.scorelab.battery-v3.guarded419-full30-observer.v1"
DATASET = "carbon.scorelab.battery-v3.guarded419-first-T5-h1.v1"
N1_CONTEXT = "carbon.scorelab.battery-v3.guarded419-n1-context.v1"
BINDING = "carbon.scorelab.guarded419-calibration-execution.v1"
REPORT = "carbon.scorelab.guarded419-calibration-reduction.v1"
RECORD = "carbon.battery.guarded419-feasibility-record.v1"
MODULE = "scripts/dev/battery/guarded_reference.py"
CONTROL_V = 4.19
RAW_MAX_V = 4.2
TRACKING_V = 1e-6
IMAGE = "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
PHASES = producer.PHASES
APPROVAL_SHA256 = "e4a7dd4d8f51e3aaac38d75d5e763dfbc6061cc59715d65a3bdad94e3c8c4696"
METHOD = {
    "id": METHOD_ID,
    "scope": "PUBLIC_DEVELOPMENT",
    "observer": OBSERVER,
    "dataset": DATASET,
    "record_schema": RECORD,
    "question_law_context": METHOD_ID,
    "n1_context_id": N1_CONTEXT,
    "owner_approval_sha256": APPROVAL_SHA256,
    "approved_document_sha256": "fc731a4ad5f5a700d0855f5763dce9f73b09fe2646f92fdc6988c0711b16e123",
    "control_voltage_v": CONTROL_V,
    "raw_maximum_v": RAW_MAX_V,
    "tracking_v": TRACKING_V,
    "experiment_model_mode": "legacy",
    "cycles": 30,
    "numerical_policy_digest": tasks.digest(numerics.POLICY),
    "claim": "SAMPLED_OPERATIONAL_DEVELOPMENT_NOT_CONTINUOUS_OR_PHYSICAL_CERTIFICATE",
    "legacy_train_or_fit_compatibility": "NOT_ESTABLISHED",
    "first_validation_only": {"T_c": 5, "h": 1, "meshes": [20, 40, 80]},
}
REQUIRED_SOURCES = {
    *producer.SOURCES,
    producer.EXPORTER,
    producer.NUMERICS,
    "scripts/dev/score_lab/owner_v3.py",
    "carbon/design_search/tasks.py",
    MODULE,
}
INSTALLED_SOURCES = {
    "simulation": "9973f3e02e5e62c9cc8368f0c663eddce72311e9a074e502acf79030df60515d",
    "solver": "3a6587fc82a124dc079aefcb0e672fbe49f8b53c68a5f4ece76a50e70001e9b2",
    "base_solver": "e7d7b7cf62186951968bcf9ae5ea7454312d842ecf3b8cc7fb3dcdf3898e4791",
    "solution": "4cfe8a90abe6808db1e746997ba94da40ca7f3493cd37b31a04739503ed2f7f0",
    "experiment": "01ce23ef8f349e236d812630a2f83c5b1e45ec7a7e19d614600244082673ecd6",
    "voltage_termination": "dec8604759478667d2b5b8bc27ce083ff765519aaa2d84600dd88c01bb4930a0",
    "voltage_step": "646840589957343587ab23916718dc5d3a5d645116d238c4fdfb23606e849d08",
    "base_step": "8e6a3ff7feeaa5976a4df93fb795cf4a3c0908883302252bb025dcc45a6aa644",
    "voltage_control": "63a902b35a2228428ebc2a74934076e88420dd2e23158c2d675b362f8489f471",
}


def first_jobs():
    return [
        {
            "case_id": f"scorelab-v3:guarded419-v1:cal:c1=1.25:c2=0.40:sv=4.00:T5:h1:mesh{mesh}",
            "c1": 1.25,
            "c2": 0.4,
            "switch_voltage_v": 4.0,
            "h_multiplier": 1,
            "t_amb_c": 5,
            "soc0": 0.1,
            "refined": mesh != 20,
            "rung": rung,
            "reference_method": METHOD_ID,
            "reference_method_digest": tasks.digest(METHOD),
        }
        for rung, mesh in enumerate((20, 40, 80), 1)
    ]


def validate_job(job):
    if (
        type(job) is not dict
        or type(job.get("rung")) is not int
        or not 1 <= job["rung"] <= 3
        or job not in first_jobs()
    ):
        raise tasks.TaskError("exact guarded first-validation job required")
    # Dict equality alone admits bools as numbers; registered input bytes do not.
    expected = first_jobs()[job["rung"] - 1]
    if tasks.digest(job) != tasks.digest(expected):
        raise tasks.TaskError("guarded job types or values differ")


def inputs():
    return {"batch": DATASET, "jobs": first_jobs()}


def observer(files):
    return {
        "id": OBSERVER,
        "protocol_id": METHOD_ID,
        "method_digest": tasks.digest(METHOD),
        "dataset_id": DATASET,
        "cycles": 30,
        "soc0": 0.1,
        "initial_state": "FRESH",
        "clock": "10% session start to 80% including registered 120-second initial rest",
        "source_files": dict(files),
    }


def execution_binding(*, source_commit, source_files):
    """Materialize inputs only; Root binds actual commit/delivery and resources."""
    if not isinstance(source_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source_commit
    ):
        raise tasks.TaskError("guarded exact source commit required")
    if set(source_files) != REQUIRED_SOURCES or any(
        not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
        for v in source_files.values()
    ):
        raise tasks.TaskError("complete guarded source-file hashes required")
    plan = {
        "schema": "carbon.scorelab.guarded419-first-plan.v1",
        "dataset_id": DATASET,
        "method": json.loads(json.dumps(METHOD)),
        "image_digest": IMAGE,
        "overlay_sha256": "6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee",
        "jobs": first_jobs(),
        "max_minutes": 45,
        "max_usd": 2,
        "full_calibration_release": False,
        "evaluation_release": False,
        "n1_release": False,
        "n1_context": {
            "id": N1_CONTEXT,
            "state": "UNBOUND_REQUIRES_MATCHING_PROTOCOL_DATA",
        },
    }
    return {
        "schema": BINDING,
        "scope": "PUBLIC_DEVELOPMENT",
        "execution_source": source_commit,
        "source_files": dict(source_files),
        "plan": plan,
        "plan_digest": tasks.digest(plan),
        "policy_digest": tasks.digest(numerics.POLICY),
        "observer": observer(source_files),
    }


def validate_binding(binding, jobs, *, root):
    expected = execution_binding(
        source_commit=binding["execution_source"], source_files=binding["source_files"]
    )
    if tasks.digest(binding) != tasks.digest(expected) or tasks.digest(
        jobs
    ) != tasks.digest(inputs()):
        raise tasks.TaskError("exact guarded first-triple binding and inputs required")
    if any(
        hashlib.sha256((Path(root) / path).read_bytes()).hexdigest() != sha
        for path, sha in binding["source_files"].items()
    ):
        raise tasks.TaskError("shipped guarded implementation differs")
    return binding, [first_jobs()]


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _point(point, start, end):
    _require(
        type(point) is dict
        and _finite(point.get("time_s"))
        and _finite(point.get("value_v"))
        and start <= point["time_s"] <= end,
        "INVALID_EXTREMUM",
    )


def _phase_evidence(phase):
    start, end = phase["t_start_s"], phase["t_end_s"]
    _require(_finite(start) and _finite(end) and end > start, "INVALID_PHASE_TIME")
    d = phase["voltage_contact_observation"]
    _require(
        d["schema"] == "carbon.battery.voltage-contact-observation.v1"
        and d["status"] == "OBSERVED",
        "UNAVAILABLE_VOLTAGE_EVIDENCE",
    )
    samples, terminal = d["samples"], d["terminal_state"]
    count = samples["all"]["count"]
    time = phase["time_observations"]
    _require(
        type(count) is int
        and count >= 2
        and time["status"] == "OBSERVED_NONDECREASING"
        and time["observation_sample_count"] == count
        and time["duplicate_time_count"] == 0
        and _finite(time["max_observed_time_gap_s"])
        and time["max_observed_time_gap_s"] > 0,
        "INVALID_SAMPLE_COVERAGE",
    )
    _require(
        samples["first"]["time_s"] == start and samples["terminal"]["time_s"] == end,
        "SAMPLE_PHASE_TIME_MISMATCH",
    )
    extrema = samples["all"]
    _point(extrema["minimum"], start, end)
    _point(extrema["maximum"], start, end)
    inner = samples["strict_interior"]
    values = [samples[key]["voltage_v"] for key in ("first", "terminal")]
    _require(all(_finite(v) for v in values), "NONFINITE_VOLTAGE")
    if count > 2:
        _require(inner["count"] == count - 2, "INCOMPLETE_INTERIOR")
        for key in ("minimum", "maximum"):
            _point(inner[key], start, end)
            _require(start < inner[key]["time_s"] < end, "NONINTERIOR_EXTREMUM")
        values.extend([inner["minimum"]["value_v"], inner["maximum"]["value_v"]])
    else:
        _require(inner is None, "UNEXPECTED_INTERIOR")
    _require(
        extrema["minimum"]["value_v"] == min(values)
        and extrema["maximum"]["value_v"] == max(values)
        and phase["v_max_v"] == max(values)
        and phase["v_min_v"] == min(values),
        "RAW_EXTREMA_MISMATCH",
    )
    _require(max(values) <= RAW_MAX_V, "RAW_VOLTAGE_ABOVE_4_2")
    _require(
        terminal["status"] == "OBSERVED"
        and terminal["matches_last_observed_time"] is True
        and terminal["time_s"] == end
        and type(terminal["state_count"]) is int
        and terminal["state_count"] > 0,
        "UNAVAILABLE_TERMINAL_STATE",
    )
    for key in ("Voltage [V]", "Battery voltage [V]"):
        _require(
            _finite(terminal[key])
            and abs(terminal[key] - samples["terminal"]["voltage_v"]) <= TRACKING_V,
            "TERMINAL_VOLTAGE_DISAGREEMENT",
        )
    return d, samples, terminal


def _event(d, terminal, name):
    events = terminal["termination_events"]
    matching = [event for event in events if event["name"] == name]
    index = d["closest_event_idx"]
    _require(
        type(index) is int
        and 0 <= index < len(events)
        and events[index]["name"] == name,
        "WRONG_EVENT_INDEX",
    )
    _require(
        d["termination"] == "event: " + name
        and len(matching) == 1
        and terminal["library_closest_event_name"] == name,
        "WRONG_OR_AMBIGUOUS_EVENT",
    )
    _require(
        all(_finite(e["signed_residual"]) for e in events), "NONFINITE_EVENT_RESIDUAL"
    )
    return matching[0]["signed_residual"]


def tracking_report(record):
    """Conjunctive real tracking checks; never changes a raw row or Vmax."""
    reasons = []
    checked = 0
    try:
        job = {key: record[key] for key in first_jobs()[0]}
        validate_job(job)
        _require(record["schema"] == RECORD, "WRONG_RECORD_SCHEMA")
        _require(record["status"] == "OK", "RAW_REFERENCE_NOT_OK")
        solver = record["solver_provenance"]
        _require(
            solver["schema"] == "carbon.battery.solver-provenance.v1"
            and solver["solver_image"]
            == "ghcr.io/carbonphysicsai/carbon-determinism-study@" + IMAGE
            and solver["overlay_lock"]
            == "scripts/dev/exam_design/locks/battery-overlay.lock.json"
            and solver["overlay_lock_sha256"]
            == "sha256:6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee"
            and solver["pybamm"] == "26.8.0.0",
            "WRONG_SOLVER_PROVENANCE",
        )
        _require(
            record["reference_identity"] == observer({}), "WRONG_REFERENCE_IDENTITY"
        )
        provenance = record["observation_provenance"]
        _require(
            _finite(provenance["runtime_voltage_scale"].get("series_cells"))
            and provenance["runtime_voltage_scale"]
            == {
                "status": "OBSERVED_PARAMETER_VALUE",
                "series_cells": 1.0,
                "basis": "ACTUAL_SIMULATION_PARAMETER_VALUE_NOT_A_BOUND_CERTIFICATE",
            },
            "WRONG_OR_UNKNOWN_VOLTAGE_SCALE",
        )
        for role, sha in INSTALLED_SOURCES.items():
            entry = provenance["installed_python_sources"][role]
            _require(
                entry["status"] == "ACTUAL_INSTALLED_PYTHON_BYTES_HASHED"
                and entry["sha256"] == sha,
                "INSTALLED_SOURCE_MISMATCH",
            )
        cycles = record["per_cycle"]
        _require(
            type(cycles) is list
            and len(cycles) == 30
            and all(type(c["cycle"]) is int for c in cycles)
            and [c["cycle"] for c in cycles] == list(range(1, 31)),
            "INCOMPLETE_CYCLES",
        )
        initial = record["initial_rest"]
        _require(
            initial["t_start_s"] == 0 and initial["t_end_s"] == 120,
            "WRONG_INITIAL_REST",
        )
        flat = [("initial_rest", initial)]
        for cycle in cycles:
            _require(set(cycle["phases"]) == set(PHASES), "INCOMPLETE_PHASES")
            flat.extend((name, cycle["phases"][name]) for name in PHASES)
        previous_end = 0
        for name, phase in flat:
            d, samples, terminal = _phase_evidence(phase)
            _require(phase["t_start_s"] >= previous_end, "REORDERED_PHASES")
            previous_end = phase["t_end_s"]
            definition = d["descriptor"]
            if name in ("cc1", "cc2", "discharge"):
                target = 4.0 if name == "cc1" else CONTROL_V if name == "cc2" else 2.5
                value = -1.25 if name == "cc1" else -0.4 if name == "cc2" else 1.0
                direction = "discharge" if name == "discharge" else "charge"
                operator = "<" if name == "discharge" else ">"
                event_name = f"Voltage {operator} {target} [V] [experiment]"
                _require(
                    definition["class"] == "CRate"
                    and definition["module"] == "pybamm.experiment.step.steps"
                    and definition["control_kind"] == "current"
                    and definition["value"] == value
                    and definition["direction"] == direction,
                    "WRONG_CC_CONTROL",
                )
                _require(
                    len(definition["terminations"]) == 1
                    and definition["terminations"][0]["value"] == target
                    and definition["terminations"][0]["class"] == "VoltageTermination"
                    and definition["terminations"][0]["module"]
                    == "pybamm.experiment.step.step_termination"
                    and definition["terminations"][0]["operator"] is None
                    and definition["terminations"][0]["event_name"] == event_name,
                    "WRONG_VOLTAGE_TERMINATION",
                )
                residual = _event(d, terminal, event_name)
                if name == "cc2":
                    _require(abs(residual) <= TRACKING_V, "CC2_EVENT_TRACKING")
                    _require(
                        max(
                            samples["first"]["voltage_v"],
                            (
                                samples["strict_interior"]["maximum"]["value_v"]
                                if samples["strict_interior"]
                                else -math.inf
                            ),
                        )
                        <= CONTROL_V + TRACKING_V,
                        "CC2_INTERIOR_TRACKING",
                    )
            elif name == "cv":
                _require(
                    definition["class"] == "Voltage"
                    and definition["module"] == "pybamm.experiment.step.steps"
                    and definition["control_kind"] == "voltage"
                    and definition["value"] == CONTROL_V
                    and definition["direction"] is None,
                    "WRONG_CV_CONTROL",
                )
                _require(
                    len(definition["terminations"]) == 1
                    and definition["terminations"][0]["class"] == "CRateTermination"
                    and definition["terminations"][0]["module"]
                    == "pybamm.experiment.step.step_termination"
                    and definition["terminations"][0]["value"] == 0.05,
                    "WRONG_CV_CUTOFF",
                )
                _event(d, terminal, "C-rate cut-off [experiment]")
                cv = d["cv_voltage_minus_target"]
                _require(
                    cv["target_v"] == CONTROL_V
                    and cv["extrema"]["count"] == samples["all"]["count"],
                    "INCOMPLETE_CV_RESIDUALS",
                )
                lo, hi = (
                    cv["extrema"][key]["value_v"] for key in ("minimum", "maximum")
                )
                _require(
                    _finite(lo)
                    and _finite(hi)
                    and lo == samples["all"]["minimum"]["value_v"] - CONTROL_V
                    and hi == samples["all"]["maximum"]["value_v"] - CONTROL_V
                    and max(abs(lo), abs(hi)) <= TRACKING_V,
                    "CV_SAMPLE_TRACKING",
                )
                _require(
                    terminal["external_circuit_class"] == "VoltageFunctionControl"
                    and terminal["external_circuit_control"] == "algebraic",
                    "WRONG_CV_MODE",
                )
                equations = terminal["current_control_equations"]
                _require(
                    len(equations) == 1
                    and equations[0]["identity"]
                    == "PROCESSED_VOLTAGE_MINUS_ACTUAL_TARGET"
                    and _finite(equations[0]["signed_residual"])
                    and abs(equations[0]["signed_residual"]) <= TRACKING_V,
                    "CV_EQUATION_TRACKING",
                )
            else:
                _require(
                    definition["class"] == "Rest"
                    and definition["value"] == 0
                    and definition["module"] == "pybamm.experiment.step.steps"
                    and definition["direction"] == "rest"
                    and definition["duration_s"]
                    == (120 if name == "initial_rest" else 600)
                    and definition["control_kind"] == "current"
                    and definition["terminations"] == []
                    and d["termination"] == "final time",
                    "WRONG_REST_CONTROL",
                )
            checked += 1
        _require(
            record["whole_programme"]["v_max_v"] == max(p["v_max_v"] for _, p in flat),
            "WHOLE_PROGRAMME_MAX_MISMATCH",
        )
    except (KeyError, TypeError, ValueError, OverflowError, tasks.TaskError) as exc:
        reasons.append(str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    return {
        "schema": "carbon.scorelab.guarded419-tracking.v1",
        "status": "TRACKING_COMPATIBLE" if not reasons else "REFERENCE_UNRESOLVED",
        "checked_phases": checked,
        "required_phases": 181,
        "reasons": reasons,
        "method_digest": tasks.digest(METHOD),
        "physical_certificate": False,
    }


def calibration_report(binding, records):
    """First-triple calibration AND authenticated per-rung tracking, no release."""
    expected_binding = execution_binding(
        source_commit=binding["execution_source"], source_files=binding["source_files"]
    )
    if tasks.digest(binding) != tasks.digest(expected_binding):
        raise tasks.TaskError("registered guarded reduction binding required")
    jobs = first_jobs()
    by_id, tracking, invalid = {}, {}, []
    for record in records:
        cid = record.get("case_id") if type(record) is dict else None
        if cid not in {j["case_id"] for j in jobs} or cid in by_id:
            invalid.append("UNEXPECTED_OR_DUPLICATE_ROW")
            continue
        by_id[cid] = record
        tracking[cid] = tracking_report(record)
    values = {}
    for job in jobs:
        cid = job["case_id"]
        if cid in by_id:
            extracted = producer._extract(by_id[cid])
            if extracted["state"] == "EXTRACTED":
                values[str({1: 20, 2: 40, 3: 80}[job["rung"]])] = extracted["values"]
    case = jobs[0]["case_id"].rsplit(":mesh", 1)[0]
    numeric = numerics.calibration_report(
        {case: values} if values else {},
        expected_cases=[case],
        expected_policy_digest=binding["policy_digest"],
    )
    bad = invalid or any(
        v["status"] != "TRACKING_COMPATIBLE" for v in tracking.values()
    )
    complete = len(by_id) == 3
    status = (
        "REFERENCE_UNRESOLVED"
        if bad
        else (
            "INCOMPLETE_REFERENCE"
            if not complete
            else (
                "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
                if numeric["status"] == "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES"
                else "REFERENCE_UNRESOLVED"
            )
        )
    )
    body = {
        "schema": REPORT,
        "status": status,
        "scope": "PUBLIC_DEVELOPMENT",
        "protocol_id": METHOD_ID,
        "observer_id": OBSERVER,
        "dataset_id": DATASET,
        "method_digest": tasks.digest(METHOD),
        "input_json_sha256": hashlib.sha256(
            json.dumps(records, sort_keys=True, allow_nan=True).encode()
        ).hexdigest(),
        "tracking": tracking,
        "invalid_rows": invalid,
        "numerical": numeric,
        "full_calibration_release": False,
        "evaluation_release": False,
        "n1_release": False,
        "qualification": False,
        "legacy_train_or_fit_compatibility": "NOT_ESTABLISHED",
    }
    return {**body, "receipt_digest": tasks.digest(body)}
