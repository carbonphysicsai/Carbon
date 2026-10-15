"""Battery customer feasibility with cooling as an action (#758 at 1ac5acfa).
DEVELOPMENT.

    python -m scripts.dev.battery.feasibility02 plan --out PLAN.json
    python -m scripts.dev.battery.feasibility02 run PLAN.json --overlay DIR --out DIR
    (inside the truth image) python -m scripts.dev.battery.feasibility02 solve \
        --jobs JOBS --records RECORDS --workers N

Optional guarded v3 pilot: solve --workers 2 --calibration-binding BINDING
--calibration-binding-sha256 HEX (plus --jobs/--records). BINDING has exact
schema/scope/execution_source/source_files/plan/plan_digest/policy_digest/
observer fields; see SCORELAB-V3-CALIBRATION-STOP-01. Source/observer hashes
are prospectively bound by Root, never rewritten into historical receipts.

The registered battery reference's model, parameters, protocol and solver
(`carbon.battery.reference`, PyBaMM 26.8.0.0 from the pinned overlay), with
two prospective changes for this study only:

- **Cooling action.** The lumped model's total heat-transfer coefficient is
  multiplied by m in {1, 2, 4} for the whole programme (charge, CV, rests and
  discharge), with the cell's area and ambient unchanged.
- **Observers.** All 30 cycles are kept (the registered extraction keeps
  cycle 1 and the checkpoints). Per cycle and per phase: temperature and
  voltage extrema with their times, the plating overpotential minimum over
  space and time on every charge step, the charge passed, and the cooling
  heat removal hA (T - T_amb) (peak and energy). Whole-programme extrema
  carry their cycle, phase and time. The first-session SOC clock is the
  pinned initial SOC plus the charge integral over the nominal capacity,
  from session start (including the 120 s rest) to the first 80 % crossing,
  interpolated; NOT_REACHED when the first charge ends below 80 %.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

N_CYCLES = 30
CHECKPOINTS = (1, 10, 20, 30)
H_NAME = "Total heat transfer coefficient [W.m-2.K-1]"
AREA_NAME = "Cell cooling surface area [m2]"
CAPACITY_NAME = "Nominal cell capacity [A.h]"
PHASES = ("cc1", "cc2", "cv", "rest_after_charge", "discharge", "rest_after_discharge")
VARIABLES = [
    "Voltage [V]",
    "Current [A]",
    "Volume-averaged cell temperature [K]",
    "Negative electrode lithium plating reaction overpotential [V]",
    "Discharge capacity [A.h]",
    "Loss of capacity to negative lithium plating [A.h]",
    "Total heating [W]",
]
#: Frozen before any reference: the old fastest/safe controls and near misses
#: at 25/35 C (c1 1.25-2.0 C, c2 0.2-1.0 C), crossed with the cooling actions,
#: at the packet's five service ambients and initial SOC 0.10.
PROTOCOLS = [
    (c1, c2) for c1 in (1.25, 1.5, 1.75, 2.0) for c2 in (0.4, 0.7, 1.0)
]  # fmt: skip
COOLING = (1.0, 2.0, 4.0)
AMBIENTS = (5.0, 15.0, 25.0, 35.0, 40.0)
SOC0 = 0.10


def plan(out):
    jobs = [
        {
            "case_id": f"c1={c1:g},c2={c2:g}:h{m:g}:T{t:g}",
            "c1": c1,
            "c2": c2,
            "t_amb_c": t,
            "soc0": SOC0,
            "h_multiplier": m,
            "switch_voltage_v": 4.0,
            "refined": False,
        }
        for c1, c2 in PROTOCOLS
        for m in COOLING
        for t in AMBIENTS
    ]
    Path(out).write_text(
        json.dumps(
            {"batch": "battery-feas02", "pr": "#758 @ 1ac5acfa", "jobs": jobs}, indent=1
        )
        + "\n"
    )
    return len(jobs)


def _simulation(job):
    import pybamm

    from carbon.battery import reference as ref

    spec = ref.SPEC
    model = pybamm.lithium_ion.DFN(dict(spec["options"]))
    params = pybamm.ParameterValues(spec["parameter_set"])
    t_k = 273.15 + job["t_amb_c"]
    h0 = params[H_NAME]
    params.update(
        {
            "Ambient temperature [K]": t_k,
            "Initial temperature [K]": t_k,
            H_NAME: h0 * job["h_multiplier"],
        }
    )
    npts = spec["refined_mesh_points"] if job["refined"] else spec["mesh_points"]
    rung3 = job.get("rung") == 3  # registered third rung (v3-panel-export.json)
    # rung 0: one step below the standard rung on the same ladder (mesh / 2,
    # tolerances x 10), a control-variate companion, never a reference value
    rung0 = job.get("rung") == 0
    if rung3:
        npts = 80
    if rung0:
        npts = 10
    var_pts = {"x_n": npts, "x_s": npts, "x_p": npts, "r_n": npts, "r_p": npts}
    s = spec["refined_solver"] if job["refined"] else spec["solver"]
    if rung3:
        s = {"rtol": 1e-7, "atol": 1e-9}
    if rung0:
        s = {"rtol": 1e-4, "atol": 1e-6}
    solver = pybamm.IDAKLUSolver(
        rtol=s["rtol"], atol=s["atol"], output_variables=VARIABLES
    )
    body = (
        f"Charge at {job['c1']}C until {job['switch_voltage_v']} V",
        f"Charge at {job['c2']}C until {spec['v_max']} V",
        f"Hold at {spec['v_max']} V until {spec['cv_cutoff']}",
        "Rest for 10 minutes",
        f"Discharge at {spec['discharge_rate']} until {spec['v_min']} V",
        "Rest for 10 minutes",
    )
    first = (f"Rest for {spec['initial_rest_s'] // 60} minutes",) + body
    experiment = pybamm.Experiment([first] + [body] * (N_CYCLES - 1))
    sim = pybamm.Simulation(
        model,
        parameter_values=params,
        experiment=experiment,
        var_pts=var_pts,
        solver=solver,
    )
    return sim, {
        "h0_w_m2k": float(h0),
        "h_w_m2k": float(h0 * job["h_multiplier"]),
        "area_m2": float(params[AREA_NAME]),
        "nominal_capacity_ah": float(params[CAPACITY_NAME]),
        "t_amb_k": t_k,
    }


def _time_observations(times):
    """Inventory recorded points, never solver-internal steps or adequacy."""
    result = {
        "schema": "carbon.battery.observed-time-vector.v1",
        "observation_sample_count": len(times),
        "max_observed_time_gap_s": None,
        "duplicate_time_count": None,
        "status": "EMPTY_TIME_VECTOR",
    }
    if not len(times):
        return result
    try:
        values = [float(t) for t in times]
    except (TypeError, ValueError, OverflowError):
        return {**result, "status": "INVALID_TIME_VECTOR"}
    if not all(math.isfinite(t) for t in values):
        return {**result, "status": "NONFINITE_TIME_VECTOR"}
    if len(values) == 1:
        return {**result, "status": "SINGLE_TIME_POINT"}
    gaps = [b - a for a, b in zip(values, values[1:])]
    if not all(math.isfinite(gap) for gap in gaps):
        return {**result, "status": "NONFINITE_TIME_DIFFERENCE"}
    if any(gap < 0 for gap in gaps):
        return {**result, "status": "BACKWARDS_TIME_VECTOR"}
    return {
        **result,
        "status": "OBSERVED_NONDECREASING",
        "max_observed_time_gap_s": max(gaps),
        "duplicate_time_count": sum(gap == 0 for gap in gaps),
    }


def _soc80_observation(times, socs, *, crossing=None, fraction=None, unavailable=None):
    """Retain the original first crossing's bracket; do not recompute a clock."""
    time_observations = _time_observations(times)
    result = {
        "schema": "carbon.battery.observed-soc80-bracket.v1",
        "time_observations": time_observations,
        "status": unavailable,
        "time_endpoints_s": None,
        "soc_endpoints": None,
        "interpolation_fraction": None,
        "observed_bracket_width_s": None,
        "exact_upper_sample_hit": None,
    }
    if unavailable is not None:
        return result
    if time_observations["status"] != "OBSERVED_NONDECREASING":
        return {**result, "status": "INVALID_TIME_VECTOR"}
    try:
        soc_values = [float(soc) for soc in socs]
        if len(soc_values) != len(times) or not all(
            math.isfinite(soc) for soc in soc_values
        ):
            return {**result, "status": "NONFINITE_OR_MISMATCHED_SOC_VECTOR"}
        if type(crossing) is not int or not 0 < crossing < len(times):
            return {**result, "status": "INVALID_CROSSING_INDEX"}
        lower, upper = crossing - 1, crossing
        t0, t1 = float(times[lower]), float(times[upper])
        s0, s1 = soc_values[lower], soc_values[upper]
        result.update(time_endpoints_s=[t0, t1], soc_endpoints=[s0, s1])
        width, delta_soc, offset = t1 - t0, s1 - s0, 0.80 - s0
        if not all(math.isfinite(v) for v in (width, delta_soc, offset)):
            return {**result, "status": "NONFINITE_BRACKET_ARITHMETIC"}
        f = float(fraction)
        if not (s0 < 0.80 <= s1) or delta_soc <= 0:
            return {**result, "status": "INVALID_SOC_CROSSING"}
        if not math.isfinite(f) or not 0 <= f <= 1:
            return {**result, "status": "INVALID_INTERPOLATION_FRACTION"}
    except (TypeError, ValueError, OverflowError):
        return {**result, "status": "INVALID_BRACKET_VALUE"}
    return {
        **result,
        "status": "OBSERVED_BRACKET",
        "interpolation_fraction": f,
        "observed_bracket_width_s": width,
        "exact_upper_sample_hit": s1 == 0.80,
    }


def _observation_source_metadata(sim):
    """Hash readable module-file bytes now, not loaded code or wheel identity."""
    import inspect

    import pybamm

    sources = {}
    for role, obj in (
        ("simulation", type(sim)),
        ("solver", type(getattr(sim, "solver", None))),
        ("base_solver", getattr(pybamm, "BaseSolver", None)),
        ("solution", getattr(pybamm, "Solution", None)),
        ("experiment", getattr(pybamm, "Experiment", None)),
    ):
        entry = {
            "module": getattr(obj, "__module__", None),
            "sha256": None,
            "status": "INSTALLED_PYTHON_SOURCE_UNAVAILABLE",
        }
        try:
            source = inspect.getsourcefile(obj)
            if source is not None and source.endswith(".py"):
                entry.update(
                    sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                    status="ACTUAL_INSTALLED_PYTHON_BYTES_HASHED",
                )
        except (OSError, TypeError, ValueError):
            pass
        sources[role] = entry
    return {
        "schema": "carbon.battery.observation-source-inventory.v1",
        "installed_python_sources": sources,
        "inventory_scope": "NAMED_MODULE_SUBSET_READABLE_FILE_BYTES_AT_CAPTURE_TIME",
        "loaded_code_attestation": "NOT_PERFORMED",
        "transitive_dependency_attestation": "NOT_PERFORMED",
        "wheel_authenticity_verification": "NOT_PERFORMED_BY_THIS_DIAGNOSTIC",
        "native_solver_source_verification": "NOT_PERFORMED",
        "expected_environment_identity": "SEPARATE_SOLVER_PROVENANCE_AND_OVERLAY_LOCK",
        "output_time_configuration": {
            "experiment_period_argument": "OMITTED",
            "solve_t_interp_argument": "OMITTED",
            "fixed_output_period_s": None,
            "basis": "ACTUAL_RECORDED_POINTS_LIBRARY_DEFAULTS_NOT_A_FIXED_PERIOD_CLAIM",
        },
    }


def _step_summary(step, cooling):
    import numpy as np

    t = step["Time [s]"].entries
    temp = step["Volume-averaged cell temperature [K]"].entries
    volt = step["Voltage [V]"].entries
    removal = cooling["h_w_m2k"] * cooling["area_m2"] * (temp - cooling["t_amb_k"])
    heating = step["Total heating [W]"].entries
    q = step["Discharge capacity [A.h]"].entries
    eta = step["Negative electrode lithium plating reaction overpotential [V]"].entries
    i_max, i_min = int(np.argmax(temp)), int(np.argmin(temp))
    return {
        "t_start_s": float(t[0]),
        "t_end_s": float(t[-1]),
        "t_max_c": float(temp[i_max] - 273.15),
        "t_max_at_s": float(t[i_max]),
        "t_min_c": float(temp[i_min] - 273.15),
        "v_max_v": float(np.max(volt)),
        "v_max_at_s": float(t[int(np.argmax(volt))]),
        "v_min_v": float(np.min(volt)),
        "plating_min_v": float(np.min(eta)),
        "charge_ah": float(q[0] - q[-1]),
        "cooling_peak_w": float(np.max(removal)),
        "cooling_energy_j": float(np.trapezoid(removal, t)),
        "heating_energy_j": float(np.trapezoid(heating, t)),
        "time_observations": _time_observations(t),
    }


def _soc_clock(cycle1, soc0, capacity):
    """Seconds from session start to SOC 0.80 on the first charge."""
    import numpy as np

    times, socs = [], []
    for step in cycle1.steps[:4]:  # initial rest, cc1, cc2, cv
        t = step["Time [s]"].entries
        q = step["Discharge capacity [A.h]"].entries
        times.extend(t.tolist())
        socs.extend(
            (
                soc0
                - (q - cycle1.steps[0]["Discharge capacity [A.h]"].entries[0])
                / capacity
            ).tolist()
        )
    times, socs = np.array(times), np.array(socs)
    start10 = np.nonzero(socs >= 0.10)[0]
    t10 = None
    if len(start10) and start10[0] > 0:
        j = int(start10[0])
        g = (0.10 - socs[j - 1]) / (socs[j] - socs[j - 1])
        t10 = float(times[j - 1] + g * (times[j] - times[j - 1]))
    above = np.nonzero(socs >= 0.80)[0]
    if not len(above):
        return {
            "status": "NOT_REACHED",
            "horizon_s": float(times[-1]),
            "soc_end": float(socs[-1]),
            "soc80_observation": _soc80_observation(
                times, socs, unavailable="UNAVAILABLE_NOT_REACHED"
            ),
        }
    k = int(above[0])
    if k == 0:
        return {
            "status": "AT_START",
            "time_s": float(times[0]),
            "soc80_observation": _soc80_observation(
                times, socs, unavailable="UNAVAILABLE_AT_START"
            ),
        }
    f = (0.80 - socs[k - 1]) / (socs[k] - socs[k - 1])
    t80 = times[k - 1] + f * (times[k] - times[k - 1])
    return {
        "status": "REACHED",
        "time_s": float(t80),
        "minutes": float(t80 / 60.0),
        "soc10_time_s": t10,
        "soc80_observation": _soc80_observation(times, socs, crossing=k, fraction=f),
    }


def solve_one(job):
    import pybamm

    pybamm.set_logging_level("ERROR")
    record = {**job, "schema": "carbon.battery.feasibility02-record.v1"}
    started = time.perf_counter()
    try:
        sim, cooling = _simulation(job)
        sol = sim.solve(initial_soc=job["soc0"], calc_esoh=False)
    except Exception as exc:  # noqa: BLE001 -- typed below
        return {**record, "status": "REFERENCE_SOLVER_FAILED", "error": repr(exc)[:300],
                "wall_s": time.perf_counter() - started}  # fmt: skip
    record["cooling"] = cooling
    record["observation_provenance"] = _observation_source_metadata(sim)
    cycles = list(sol.cycles)
    if len(cycles) < N_CYCLES or any(c is None for c in cycles):
        return {**record, "status": "REFERENCE_SOLVER_FAILED",
                "error": f"completed {len(cycles)} of {N_CYCLES} cycles",
                "wall_s": time.perf_counter() - started}  # fmt: skip
    try:
        per_cycle, capacity = [], {}
        for k, cycle in enumerate(cycles, start=1):
            steps = list(cycle.steps)
            if k == 1:
                steps = steps[1:]  # the initial rest is reported separately
            if len(steps) != len(PHASES):
                raise ValueError(f"cycle {k} has {len(steps)} steps")
            phases = {name: _step_summary(s, cooling) for name, s in zip(PHASES, steps)}
            capacity[k] = -phases["discharge"]["charge_ah"]
            per_cycle.append({"cycle": k, "phases": phases})
        initial_rest = _step_summary(cycles[0].steps[0], cooling)
        flat = [("initial_rest", 1, initial_rest)] + [
            (name, c["cycle"], p) for c in per_cycle for name, p in c["phases"].items()
        ]
        t_max = max(flat, key=lambda x: x[2]["t_max_c"])
        v_max = max(flat, key=lambda x: x[2]["v_max_v"])
        charges = [x for x in flat if x[0] in ("cc1", "cc2", "cv")]
        plating = min(charges, key=lambda x: x[2]["plating_min_v"])
        charge_t_max = max(charges, key=lambda x: x[2]["t_max_c"])
        rest = [x for x in flat if x[0] not in ("cc1", "cc2", "cv")]
        other_t_max = max(rest, key=lambda x: x[2]["t_max_c"])
        record.update(
            status="OK",
            soc_clock=_soc_clock(cycles[0], job["soc0"], cooling["nominal_capacity_ah"]),
            whole_programme={
                "t_max_c": t_max[2]["t_max_c"], "t_max_phase": t_max[0], "t_max_cycle": t_max[1],
                "t_max_at_s": t_max[2]["t_max_at_s"],
                "t_max_charging_c": charge_t_max[2]["t_max_c"],
                "t_max_non_charging_c": other_t_max[2]["t_max_c"],
                "t_max_non_charging_phase": other_t_max[0],
                "v_max_v": v_max[2]["v_max_v"], "v_max_phase": v_max[0], "v_max_cycle": v_max[1],
                "plating_min_v": plating[2]["plating_min_v"], "plating_min_phase": plating[0],
                "plating_min_cycle": plating[1],
                "cooling_peak_w": max(x[2]["cooling_peak_w"] for x in flat),
                "cooling_energy_j": sum(x[2]["cooling_energy_j"] for x in flat),
                "plated_capacity_ah": float(
                    sol["Loss of capacity to negative lithium plating [A.h]"].entries[-1]
                ),
            },
            capacity_ah={str(k): capacity[k] for k in CHECKPOINTS},
            capacity_all_ah=[capacity[k] for k in range(1, N_CYCLES + 1)],
            q30_over_q1=capacity[30] / capacity[1],
            initial_rest=initial_rest,
            per_cycle=per_cycle,
        )  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        record.update(
            status="REFERENCE_SOLVER_FAILED", error="extraction: " + repr(exc)[:300]
        )
    record["wall_s"] = time.perf_counter() - started
    return record


def _timed(job):
    """`solve_one` in its worker, with the worker's CPU core-seconds (user +
    system, every thread) for this case beside `wall_s`."""
    started = time.process_time()
    record = solve_one(job)
    return {**record, "core_s": time.process_time() - started}


def solve(jobs_path, records_path, workers):
    from carbon.battery import truth_env

    solver_provenance = truth_env.provenance(".")
    jobs = json.loads(Path(jobs_path).read_text())["jobs"]
    records = Path(records_path)
    done = set()
    if records.exists():
        done = {
            json.loads(x)["case_id"]
            for x in records.read_text().splitlines()
            if x.strip()
        }
    todo = [j for j in jobs if j["case_id"] not in done]
    with ProcessPoolExecutor(workers) as pool:
        for record in pool.map(_timed, todo):
            record = truth_env.stamp(record, solver_provenance)
            with records.open("a") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            print(record["case_id"], record["status"], round(record.get("wall_s", 0), 1),
                  flush=True)  # fmt: skip


def _calibration_contract(jobs_path, binding_path, expected_sha256):
    """Prospective input/source binding, before any worker or output is opened.

    Root authenticates the execution commit and binding delivery externally.
    File hashes below check the shipped implementation, not a Git signature.
    """
    from carbon.design_search import tasks
    from scripts.dev.score_lab import owner_v3
    from scripts.dev.score_lab import owner_v3_numerics as numerics
    from scripts.dev.score_lab import owner_v3_panel_export as producer

    raw = Path(binding_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise tasks.TaskError("calibration binding bytes differ")
    binding = json.loads(raw)
    producer._fields(
        binding,
        (
            "schema",
            "scope",
            "execution_source",
            "source_files",
            "plan",
            "plan_digest",
            "policy_digest",
            "observer",
        ),
        "calibration binding",
    )
    if (
        binding["schema"] != "carbon.scorelab.calibration-execution.v1"
        or binding["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or not isinstance(binding["execution_source"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", binding["execution_source"])
        or binding["policy_digest"] != tasks.digest(numerics.POLICY)
    ):
        raise tasks.TaskError("registered calibration execution required")
    files = binding["source_files"]
    required = {
        *producer.SOURCES,
        producer.EXPORTER,
        producer.NUMERICS,
        "scripts/dev/score_lab/owner_v3.py",
        "carbon/design_search/tasks.py",
    }
    producer._fields(files, required, "calibration source files")
    if any(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != files[p]
        for p in required
    ):
        raise tasks.TaskError("shipped calibration implementation differs")
    plan = binding["plan"]
    expected = owner_v3.acquisition_inputs(
        plan, expected_digest=binding["plan_digest"], stage="calibration-pilot"
    )
    if (
        json.loads(Path(jobs_path).read_text(encoding="utf-8")) != expected
        or binding["observer"] != producer._observer(plan, {"files": files})
        or plan["numerical_policy_digest"] != binding["policy_digest"]
    ):
        raise tasks.TaskError("complete pilot inputs, observer and policy required")
    jobs = expected["jobs"]
    # Freeze complete ordered triples; never infer missing rungs from outcomes.
    groups = [jobs[i : i + 3] for i in range(0, len(jobs), 3)]
    if not groups or any(
        len(g) != 3
        or [j["rung"] for j in g] != [1, 2, 3]
        or len({j["case_id"].rsplit(":mesh", 1)[0] for j in g}) != 1
        for g in groups
    ):
        raise tasks.TaskError("complete registered calibration triples required")
    return binding, groups


def _calibration_rows(binding, group, rows):
    """Reuse exact producer authentication/extraction and numerical policy."""
    from scripts.dev.score_lab import owner_v3_panel_export as producer

    lines = [json.dumps(row, sort_keys=True) for row in rows]
    raw = ("\n".join(lines) + "\n").encode()
    jobs = {job["case_id"]: job for job in group}
    manifest = {
        "scope": binding["scope"],
        "chunks": [
            {
                "id": "completed-triple",
                "sha256": producer._hash(raw),
                "role": "PUBLIC_CALIBRATION",
                "source_commit": binding["execution_source"],
                "source_files": binding["source_files"],
                "rows": [
                    {"line": i, "job_id": row["case_id"], "case_id": row["case_id"]}
                    for i, row in enumerate(rows, 1)
                ],
            }
        ],
    }
    found, _ = producer._raw_rows(
        manifest,
        {"completed-triple": raw},
        jobs,
        binding["source_files"],
        binding["plan"],
    )
    return {
        str({1: 20, 2: 40, 3: 80}[job["rung"]]): producer._extract(
            found.get(job["case_id"])
        )["values"]
        for job in group
    }


def solve_calibration(jobs_path, records_path, workers, binding_path, expected_sha256):
    """Within-pilot stop: no next tuple is submitted before this one passes.

    All returned rows survive even a failed extraction. Ordinary solve/resume
    is unchanged. The six-tuple result cannot release full calibration.
    """
    from carbon.battery import truth_env
    from carbon.design_search import tasks
    from scripts.dev.score_lab import owner_v3_numerics as numerics

    if type(workers) is not int or not 1 <= workers <= 2:
        raise tasks.TaskError("calibration requires one or two workers")
    binding, groups = _calibration_contract(jobs_path, binding_path, expected_sha256)
    provenance = truth_env.provenance(".")
    plan = binding["plan"]
    if (
        provenance.get("schema") != "carbon.battery.solver-provenance.v1"
        or provenance.get("solver_image", "").split("@")[-1] != plan["image_digest"]
        or provenance.get("overlay_lock_sha256") != "sha256:" + plan["overlay_sha256"]
        or provenance.get("overlay_lock")
        != "scripts/dev/exam_design/locks/battery-overlay.lock.json"
        or provenance.get("pybamm") != "26.8.0.0"
    ):
        raise tasks.TaskError("calibration truth runtime differs")
    records = Path(records_path)
    receipt_path = records.with_name(records.name + ".calibration.json")
    if records.exists() or receipt_path.exists():
        raise tasks.TaskError("calibration requires fresh records and receipt")
    cases = [g[0]["case_id"].rsplit(":mesh", 1)[0] for g in groups]
    triples = {}
    states = {j["case_id"]: "NOT_DISPATCHED" for g in groups for j in g}
    receipt = {
        "schema": "carbon.scorelab.calibration-execution-receipt.v1",
        "scope": binding["scope"],
        "binding_sha256": expected_sha256,
        "execution_source": binding["execution_source"],
        "source_files": binding["source_files"],
        "observer": binding["observer"],
        "plan_digest": binding["plan_digest"],
        "offered_jobs_digest": tasks.digest([j for g in groups for j in g]),
        "status": "INCOMPLETE_REFERENCE",
        "per_job": states,
        "per_completed_triple": [],
        "full_calibration_release": False,
        "qualification": False,
    }

    def save():
        receipt["calibration"] = numerics.calibration_report(
            triples,
            expected_cases=cases,
            expected_policy_digest=binding["policy_digest"],
        )
        receipt["records_sha256"] = hashlib.sha256(records.read_bytes()).hexdigest()
        temporary = receipt_path.with_name(receipt_path.name + ".tmp")
        temporary.write_text(
            json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(receipt_path)

    with records.open("x", encoding="utf-8"):
        pass
    save()
    try:
        with ProcessPoolExecutor(workers) as pool:
            for case, group in zip(cases, groups):
                futures = {}
                for job in group:
                    future = pool.submit(_timed, job)
                    futures[future] = job
                    states[job["case_id"]] = "SUBMITTED"
                    save()
                rows = []
                for future in as_completed(futures):
                    job = futures[future]
                    try:
                        record = future.result()
                    except Exception as exc:  # noqa: BLE001
                        # Preserve worker infrastructure failure, not science failure.
                        record = {
                            **job,
                            "schema": "carbon.battery.feasibility02-record.v1",
                            "status": "FAILED_INFRA",
                            "error": repr(exc)[:300],
                        }
                    record = truth_env.stamp(record, provenance)
                    with records.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(record, sort_keys=True) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    rows.append(record)
                    states[job["case_id"]] = record.get("status", "MALFORMED_RECORD")
                    save()
                # Assessment occurs only after the current triple is durable;
                # no futures for a later physical tuple exist yet.
                triples[case] = _calibration_rows(binding, group, rows)
                current = numerics.calibration_report(
                    {case: triples[case]},
                    expected_cases=[case],
                    expected_policy_digest=binding["policy_digest"],
                )
                receipt["per_completed_triple"].append(current)
                if current["status"] != "COMPATIBLE_FOR_REGISTERED_CALIBRATION_CASES":
                    receipt["status"] = current["status"]
                    save()
                    return 2
                save()
    except BaseException:
        receipt["status"] = "INTERRUPTED_OR_INVALID_REFERENCE"
        save()
        raise
    receipt["status"] = "COMPATIBLE_PILOT_ONLY"
    save()
    return 0


def run(plan_path, overlay, out, workers, cpus, cpu_shares=None):
    from carbon.battery import truth_env

    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs.json").write_text(Path(plan_path).read_text())
    command = truth_env.solve_command(
        overlay, out, repository=str(ROOT), workers=workers
    )
    # Same isolation as the truth service; this study's own module as the entry.
    entry = command.index("carbon.battery.truth_env")
    command[entry:] = [
        "scripts.dev.battery.feasibility02", "solve", "--jobs", "/work/jobs.json",
        "--records", "/work/records.jsonl", "--workers", str(workers),
    ]  # fmt: skip
    command[command.index("--rm") + 1 : command.index("--rm") + 1] = [
        "--cpus",
        str(cpus),
    ]
    if cpu_shares:  # low priority behind other operator work; never preempts it
        at = command.index("--rm") + 1
        command[at:at] = ["--cpu-shares", str(cpu_shares)]
    parent = os.environ.get("CARBON_STAGE_CGROUP_PARENT")
    if parent:  # campaign stage metering only; the solve is unchanged
        at = command.index("--rm") + 1
        command[at:at] = ["--cgroup-parent", parent]
    return subprocess.run(command, check=False).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(prog="battery feasibility02")
    parser.add_argument("command", choices=("plan", "run", "solve"))
    parser.add_argument("plan", type=Path, nargs="?")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--records", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--cpu-shares", type=int)
    parser.add_argument("--calibration-binding", type=Path)
    parser.add_argument("--calibration-binding-sha256")
    args = parser.parse_args(argv)
    if bool(args.calibration_binding) != bool(args.calibration_binding_sha256):
        parser.error("calibration binding and SHA256 are required together")
    if args.calibration_binding and args.command != "solve":
        parser.error("calibration binding is only supported by in-image solve")
    if args.command == "plan":
        print(plan(args.out))
    elif args.command == "solve":
        if args.calibration_binding:
            return solve_calibration(
                args.jobs,
                args.records,
                args.workers,
                args.calibration_binding,
                args.calibration_binding_sha256,
            )
        solve(args.jobs, args.records, args.workers)
    else:
        return run(
            args.plan, args.overlay, args.out, args.workers, args.cpus, args.cpu_shares
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
