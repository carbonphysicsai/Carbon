"""PLATING-CONVERGENCE-01: does the battery reference's plating margin converge?

    python -m scripts.dev.battery.plating_convergence run --cases CASES.json --out DIR [--workers N]

Prerequisite for REF-RESOLVE (BANK_SPEC section 9, #1253). The accepted code
verification of the pinned battery image covers voltage and temperature, not the
plating output. The reference (`carbon.battery.reference.SPEC`) solves every bank
and public-development case at 20 mesh points per domain (rtol 1e-5), and the
refined rung at 40 (rtol 1e-6). A probe on one public case moved the cycle-1
plating margin by 0.58 mV from 20 to 40 points and 0.97 mV from 20 to 80, against
a 0 V limit and a 1.97 mV band.

This study runs one fixed ladder per case in the pinned image, with the reference
model, parameters and experiment unchanged; it varies only the mesh, the solver
tolerance and the output period:
- mesh 20 at rtol 1e-5 (the reference's standard rung) and mesh 40, 80, 160 at
  rtol 1e-6 (40 is the refined rung), for every case;
- mesh 320 at rtol 1e-6 for the first `FINE_CASES` cases (it is the costly rung,
  one solve at a time; a solve the host kills is recorded `KILLED_BY_HOST`);
- at mesh 80: rtol 1e-8 (tolerance check) and a 5 s output period (sampling check);
- for the first case only, the standard rung over all 30 cycles: cycle 1 is the
  plating window, so its margin must equal the one-cycle solve's.

The margin is the reference's own: the minimum negative-electrode plating reaction
overpotential over cycle 1's three charge steps. Each case gets Richardson
extrapolation over its three finest mesh rungs (observed order and an
extrapolated margin), so each rung's discretisation error can be read off.

It reports evidence for the Validator's band and reference-adequacy decision. It
sets no band, tolerance or mesh, and it does not change the reference.
DEVELOPMENT only; public cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = "carbon.battery.plating-convergence.v1"
CASES_SCHEMA = "carbon.battery.plating-convergence-cases.v1"
MESHES = (20, 40, 80, 160, 320)
FINE_CASES = 3
#: Workers for the finest rung, whose memory is the largest (a cap, not a count).
FINE_WORKERS = 3
PLATING = "Negative electrode lithium plating reaction overpotential [V]"
#: A finest-rung solve the host killed (out of memory): not a solver result.
KILLED = "KILLED_BY_HOST"


def ladder(cases):
    """Every (case index, rung) solve, coarse first; the finest rung last."""
    jobs = []
    for i, _case in enumerate(cases):
        jobs.append(
            {"case": i, "mesh": 20, "rtol": 1e-5, "period_s": None, "cycles": 1}
        )
        for mesh in (40, 80, 160):
            jobs.append(
                {"case": i, "mesh": mesh, "rtol": 1e-6, "period_s": None, "cycles": 1}
            )
        jobs.append(
            {"case": i, "mesh": 80, "rtol": 1e-8, "period_s": None, "cycles": 1}
        )
        jobs.append({"case": i, "mesh": 80, "rtol": 1e-6, "period_s": 5, "cycles": 1})
    jobs.append({"case": 0, "mesh": 20, "rtol": 1e-5, "period_s": None, "cycles": 30})
    for i in range(min(FINE_CASES, len(cases))):
        jobs.append(
            {"case": i, "mesh": 320, "rtol": 1e-6, "period_s": None, "cycles": 1}
        )
    return jobs


def richardson(e1, e2, e3):
    """Margins at meshes h, h/2, h/4: (observed order p, extrapolated margin),
    or (None, None) when the differences do not shrink monotonically."""
    d1, d2 = e1 - e2, e2 - e3
    if d1 == 0 or d2 == 0 or (d1 > 0) != (d2 > 0) or abs(d2) >= abs(d1):
        return None, None
    p = math.log2(d1 / d2)
    return p, e3 + (e3 - e2) / (2**p - 1)


def solve(case, job):
    """One rung of one case in the pinned image (imports PyBaMM here)."""
    import resource

    import numpy as np
    import pybamm

    from carbon.battery import reference as ref

    pybamm.set_logging_level("ERROR")
    spec = ref.SPEC
    record = {**job, "case_id": case["case_id"]}
    started, cpu = time.perf_counter(), time.process_time()
    try:
        body = (
            f"Charge at {case['c1']}C until {spec['switch_voltage_v']} V",
            f"Charge at {case['c2']}C until {spec['v_max']} V",
            f"Hold at {spec['v_max']} V until {spec['cv_cutoff']}",
            "Rest for 10 minutes",
            f"Discharge at {spec['discharge_rate']} until {spec['v_min']} V",
            "Rest for 10 minutes",
        )
        first = (f"Rest for {spec['initial_rest_s'] // 60} minutes",) + body
        cycles = [first] + [body] * (job["cycles"] - 1)
        kwargs = (
            {} if job["period_s"] is None else {"period": f"{job['period_s']} seconds"}
        )
        model = pybamm.lithium_ion.DFN(dict(spec["options"]))
        params = pybamm.ParameterValues(spec["parameter_set"])
        t_k = 273.15 + case["t_amb_c"]
        params.update({"Ambient temperature [K]": t_k, "Initial temperature [K]": t_k})
        mesh = job["mesh"]
        sim = pybamm.Simulation(
            model,
            parameter_values=params,
            experiment=pybamm.Experiment(cycles, **kwargs),
            var_pts={k: mesh for k in ("x_n", "x_s", "x_p", "r_n", "r_p")},
            solver=pybamm.IDAKLUSolver(
                rtol=job["rtol"],
                atol=job["rtol"] * 1e-2,
                output_variables=ref.STORED_VARIABLES,
            ),
        )
        solution = sim.solve(initial_soc=case["soc0"], calc_esoh=False)
        charge = solution.cycles[0].steps[1:4]  # after the initial rest
        record.update(
            status="OK",
            plating_margin_v=min(float(np.min(s[PLATING].entries)) for s in charge),
            points=sum(len(s["Time [s]"].entries) for s in charge),
        )
    except Exception as exc:  # noqa: BLE001 -- a failed rung is a typed record
        record.update(status="SOLVER_FAILED", error=repr(exc)[:300])
    record.update(
        wall_s=round(time.perf_counter() - started, 2),
        cpu_s=round(time.process_time() - cpu, 2),
        maxrss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
    )
    return record


def _one(args):
    return solve(*args)


def summarise(cases, records):
    """Per case: the margin at each rung, the checks, and Richardson over the
    three finest mesh rungs it has."""
    out = []
    for i, case in enumerate(cases):
        mine = [r for r in records if r["case"] == i and r.get("status") == "OK"]
        mesh = {
            r["mesh"]: r["plating_margin_v"]
            for r in mine
            if r["cycles"] == 1 and r["period_s"] is None and r["rtol"] in (1e-6,)
        }
        standard = next(
            (
                r["plating_margin_v"]
                for r in mine
                if r["mesh"] == 20 and r["cycles"] == 1
            ),
            None,
        )
        fine = sorted(mesh)[-3:]
        p, extrapolated = (
            richardson(*(mesh[m] for m in fine)) if len(fine) == 3 else (None, None)
        )
        row = {
            "case_id": case["case_id"],
            "question": case.get("question"),
            "reference_margin_v": case.get("reference_margin_v"),
            "standard_rung_v": standard,
            "mesh_rungs_v": {str(m): mesh[m] for m in sorted(mesh)},
            "richardson_meshes": fine if p is not None else None,
            "observed_order": p,
            "extrapolated_margin_v": extrapolated,
        }
        if extrapolated is not None:
            row["error_v"] = {
                "standard_20": None if standard is None else standard - extrapolated,
                **{str(m): mesh[m] - extrapolated for m in sorted(mesh)},
            }
        for r in mine:
            if r["mesh"] == 80 and r["rtol"] == 1e-8 and 80 in mesh:
                row["rtol_check_v"] = r["plating_margin_v"] - mesh[80]
            if r["mesh"] == 80 and r["period_s"] and 80 in mesh:
                row["period_check_v"] = r["plating_margin_v"] - mesh[80]
            if r["cycles"] == 30 and standard is not None:
                row["thirty_cycle_check_v"] = r["plating_margin_v"] - standard
        out.append(row)
    return out


def run(cases_path, out, workers):
    document = json.loads(Path(cases_path).read_text())
    if document.get("schema") != CASES_SCHEMA:
        raise SystemExit("refused: not a plating-convergence case list")
    cases = document["cases"]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = ladder(cases)
    coarse = [j for j in jobs if j["mesh"] < max(MESHES)]
    finest = [j for j in jobs if j["mesh"] == max(MESHES)]
    records = []
    with (out / "records.jsonl").open("a") as stream:

        def keep(record):
            records.append(record)
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()

        with ProcessPoolExecutor(
            max_workers=max(1, workers), max_tasks_per_child=1
        ) as pool:
            for record in pool.map(_one, [(cases[j["case"]], j) for j in coarse]):
                keep(record)
        write_summary(cases_path, cases, records, out)
        # The finest rung one solve per pool: a solve the host kills (out of
        # memory, 2026-10-13) is a typed failed rung, never the end of the study.
        for job in finest:
            try:
                with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
                    keep(pool.submit(_one, (cases[job["case"]], job)).result())
            except BrokenProcessPool:
                keep(
                    {**job, "case_id": cases[job["case"]]["case_id"], "status": KILLED}
                )
    summary = write_summary(cases_path, cases, records, out)
    return {k: summary[k] for k in ("solves", "failed")}


def write_summary(cases_path, cases, records, out):
    """The summary of the records so far, rewritten after each stage."""
    summary = {
        "schema": SCHEMA,
        "cases_sha256": hashlib.sha256(Path(cases_path).read_bytes()).hexdigest(),
        "reference_spec": {
            "standard": "mesh 20, rtol 1e-5",
            "refined": "mesh 40, rtol 1e-6",
        },
        "solves": len(records),
        "failed": sum(r.get("status") != "OK" for r in records),
        "cases": summarise(cases, records),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n"
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(prog="plating_convergence")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("run")
    command.add_argument("--cases", required=True)
    command.add_argument("--out", required=True)
    command.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.cases, args.out, args.workers)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
