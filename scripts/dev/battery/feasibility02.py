"""Battery customer feasibility with cooling as an action (#758 at 1ac5acfa).
DEVELOPMENT.

    python -m scripts.dev.battery.feasibility02 plan --out PLAN.json
    python -m scripts.dev.battery.feasibility02 run PLAN.json --overlay DIR --out DIR
    (inside the truth image) python -m scripts.dev.battery.feasibility02 solve \
        --jobs JOBS --records RECORDS --workers N

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
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
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
    var_pts = {"x_n": npts, "x_s": npts, "x_p": npts, "r_n": npts, "r_p": npts}
    s = spec["refined_solver"] if job["refined"] else spec["solver"]
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
        }
    k = int(above[0])
    if k == 0:
        return {"status": "AT_START", "time_s": float(times[0])}
    f = (0.80 - socs[k - 1]) / (socs[k] - socs[k - 1])
    t80 = times[k - 1] + f * (times[k] - times[k - 1])
    return {
        "status": "REACHED",
        "time_s": float(t80),
        "minutes": float(t80 / 60.0),
        "soc10_time_s": t10,
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


def solve(jobs_path, records_path, workers):
    from carbon.battery import truth_env

    truth_env.require_truth_runtime(".")
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
        for record in pool.map(solve_one, todo):
            with records.open("a") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            print(record["case_id"], record["status"], round(record.get("wall_s", 0), 1),
                  flush=True)  # fmt: skip


def run(plan_path, overlay, out, workers, cpus):
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
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(plan(args.out))
    elif args.command == "solve":
        solve(args.jobs, args.records, args.workers)
    else:
        return run(args.plan, args.overlay, args.out, args.workers, args.cpus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
