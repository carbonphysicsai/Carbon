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

# Frozen public research panel; a different panel requires prospective review.
SENTINEL_SCHEMA = "carbon.research.plating-sentinel-jobs.v1"
SENTINEL_SHA256 = "2dd3884d1b9428997ef080415265182f5dd1d8723ddc8088069b53ad1107aa7f"


#: D2's wider panel (the Validator's PLATING_REFERENCE_DECISION_2026-10-13, sha
#: 10740f47): the standard rung and the mesh ladder only, plating in cycle 1.
PANEL = "panel"
#: D3's re-reference: the one mesh-160 rung (rtol 1e-6), plating in cycle 1.
RE_REFERENCE = "re-reference"
#: Workers for the mesh-160 stage (6.3 GB each); a cap, sized to the host.
MID_WORKERS = 12
#: D2's strata: ambient bins x rate (c1 >= 1.25 is high), weighted to cold and
#: high rates, 40 cases in all. Drawn from the public PDD decision cases.
PANEL_STRATA = (
    ((5.0, 12.5), True, 8),
    ((12.5, 20.0), True, 8),
    ((5.0, 12.5), False, 4),
    ((12.5, 20.0), False, 4),
    ((20.0, 30.0), True, 5),
    ((30.0, 40.01), True, 5),
    ((20.0, 30.0), False, 3),
    ((30.0, 40.01), False, 3),
)
PANEL_SALT = "PLATING-CONVERGENCE-02/D2"


def ladder(cases, kind="study"):
    """Every (case index, rung) solve, coarse first; the finest rung last."""
    if kind == RE_REFERENCE:
        # Mesh 160 for every case; 40 and 80 too for its convergence subsample.
        return [
            {"case": i, "mesh": mesh, "rtol": 1e-6, "period_s": None, "cycles": 1}
            for i, case in enumerate(cases)
            for mesh in ((40, 80, 160) if case.get("convergence_check") else (160,))
        ]
    if kind == PANEL:
        return [
            {"case": i, "mesh": mesh, "rtol": 1e-5 if mesh == 20 else 1e-6,
             "period_s": None, "cycles": 1}
            for i in range(len(cases))
            for mesh in (20, 40, 80, 160)
        ]  # fmt: skip
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


def run_probe(jobs_path, probe_index, out):
    """One frozen public research probe, with no retries or study fallback.

    The full byte binding rejects changed scope, methods, tuples, duplicate or
    extra fields before any solver import. The catalogue job.case is metadata;
    it is not an index into this nine-probe manifest.
    """
    if type(probe_index) is not int or not 0 <= probe_index < 9:
        raise ValueError("probe index must be an integer in 0..8")
    raw = Path(jobs_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SENTINEL_SHA256:
        raise ValueError("sentinel manifest does not match the frozen RESEARCH_V1 panel")
    document = json.loads(raw)
    if document.get("schema") != SENTINEL_SCHEMA or len(document["probes"]) != 9:
        raise ValueError("invalid sentinel manifest schema or probe count")
    probe = document["probes"][probe_index]
    # Reserve a new output before doing expensive work. Never append, overwrite,
    # retry or enter run/_stage on this route. Interrupted output is not evidence.
    with Path(out).open("x", encoding="utf-8", newline="\n") as stream:
        record = solve(probe["case"], probe["job"])
        record.update(
            probe_id=probe["probe_id"],
            probe_index=probe_index,
            manifest_sha256=SENTINEL_SHA256,
        )
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    return record


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


def _stage(jobs, cases, workers, keep):
    """Run `jobs` in a pool of `workers`; if the host kills a solve and breaks the
    pool, every unfinished job is retried alone, and a solve killed alone is a
    `KILLED_BY_HOST` record. Never ends the study."""
    from concurrent.futures import as_completed

    done = set()
    try:
        with ProcessPoolExecutor(
            max_workers=max(1, workers), max_tasks_per_child=1
        ) as pool:
            futures = {
                pool.submit(_one, (cases[j["case"]], j)): n for n, j in enumerate(jobs)
            }
            for future in as_completed(futures):
                keep(future.result())
                done.add(futures[future])
    except BrokenProcessPool:
        for n, job in enumerate(jobs):
            if n in done:
                continue
            try:
                with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
                    keep(pool.submit(_one, (cases[job["case"]], job)).result())
            except BrokenProcessPool:
                keep(
                    {**job, "case_id": cases[job["case"]]["case_id"], "status": KILLED}
                )


def run(cases_path, out, workers, mid_workers=MID_WORKERS):
    document = json.loads(Path(cases_path).read_text())
    if document.get("schema") != CASES_SCHEMA:
        raise SystemExit("refused: not a plating-convergence case list")
    cases = document["cases"]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = ladder(cases, document.get("ladder", "study"))
    coarse = [j for j in jobs if j["mesh"] < 160]
    middle = [j for j in jobs if j["mesh"] == 160]
    finest = [j for j in jobs if j["mesh"] > 160]
    records = []
    with (out / "records.jsonl").open("a") as stream:

        def keep(record):
            records.append(record)
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()

        _stage(coarse, cases, workers, keep)
        write_summary(cases_path, cases, records, out)
        # Mesh 160 at a memory-sized cap; mesh 320 one solve at a time (it ran
        # the host out of memory on 2026-10-13).
        _stage(middle, cases, min(workers, mid_workers), keep)
        write_summary(cases_path, cases, records, out)
        _stage(finest, cases, 1, keep)
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


def select_panel(contract_path, records_path):
    """D2's case list: public PDD decision cases (standard records that solved)
    drawn per stratum in a fixed hash order, at most one per question."""
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d

    contract = json.loads(Path(contract_path).read_text())
    jobs = {j["case_id"]: j for j in ev.decision_cases(contract)}
    margins = {}
    for line in Path(records_path).read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (
            record.get("refined")
            or record.get("status") != "OK"
            or record["case_id"] not in jobs
        ):
            continue
        margins[record["case_id"]] = d.measure(contract, record["outputs"])[
            "plating_margin_v"
        ]

    def order(case_id):
        return hashlib.sha256(f"{PANEL_SALT}:{case_id}".encode()).hexdigest()

    chosen, questions = [], set()
    for (low, high), high_rate, count in PANEL_STRATA:
        pool = sorted(
            (c for c in margins
             if low <= jobs[c]["t_amb_c"] < high and (jobs[c]["c1"] >= 1.25) == high_rate),
            key=order,
        )  # fmt: skip
        taken = 0
        for case_id in pool:
            job = jobs[case_id]
            if taken == count or job["scenario"] in questions:
                continue
            questions.add(job["scenario"])
            taken += 1
            chosen.append({
                "case_id": case_id, "question": job["scenario"], "candidate": job["candidate"],
                "c1": job["c1"], "c2": job["c2"], "t_amb_c": job["t_amb_c"], "soc0": job["soc0"],
                "reference_margin_v": margins[case_id], "reference_rung": "standard",
                "stratum": f"t_amb [{low:g},{min(high, 40):g}) {'high' if high_rate else 'low'} rate",
            })  # fmt: skip
        if taken < count:
            raise SystemExit(f"refused: stratum {low}-{high} has only {taken} cases")
    return {
        "schema": CASES_SCHEMA,
        "ladder": PANEL,
        "rule": "D2: public PDD decision cases with a solved standard record, per stratum "
        f"{[(b, h, n) for b, h, n in PANEL_STRATA]} (ambient bin, c1 >= 1.25, count), in "
        f"sha256('{PANEL_SALT}:'+case_id) order, at most one per question",
        "source": {
            "contract_sha256": hashlib.sha256(
                Path(contract_path).read_bytes()
            ).hexdigest(),
            "records_sha256": hashlib.sha256(
                Path(records_path).read_bytes()
            ).hexdigest(),
        },
        "cases": chosen,
    }


def bias_report(summary_path, contract_path, records_path):
    """D2's two answers: the worst mesh-20 bias over the panel, and the share of
    public PDD decision cases whose standard plating margin lies within that
    bias of the limit (labelled safe, but possibly plating). DEVELOPMENT
    ASSUMPTION for the interim band; no threshold is set here."""
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d

    rows = json.loads(Path(summary_path).read_text())["cases"]
    to_extrapolated = [
        r["error_v"]["standard_20"] for r in rows if r.get("error_v") and r["error_v"].get("standard_20") is not None
    ]  # fmt: skip
    to_160 = [
        r["standard_rung_v"] - r["mesh_rungs_v"]["160"]
        for r in rows
        if r.get("standard_rung_v") is not None and "160" in r.get("mesh_rungs_v", {})
    ]
    residual_160 = [
        r["error_v"]["160"] for r in rows if r.get("error_v") and "160" in r["error_v"]
    ]
    contract = json.loads(Path(contract_path).read_text())
    limit = d._constraint_rules(contract)["no_plating_onset"]["threshold"]
    jobs = {j["case_id"] for j in ev.decision_cases(contract)}
    standard = []
    for line in Path(records_path).read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            if (
                not record.get("refined")
                and record.get("status") == "OK"
                and record["case_id"] in jobs
            ):
                standard.append(
                    d.measure(contract, record["outputs"])["plating_margin_v"]
                )
    worst = max(to_extrapolated) if to_extrapolated else None
    within = (
        None if worst is None else sum(limit <= m < limit + worst for m in standard)
    )
    return {
        "schema": SCHEMA + ".d2-report",
        "status": "DEVELOPMENT ASSUMPTION, not a qualified threshold",
        "panel_cases": len(rows),
        "richardson_cases": len(to_extrapolated),
        "worst_mesh20_bias_v": {"to_extrapolated": worst, "to_mesh160": max(to_160) if to_160 else None},
        "median_mesh20_bias_v": None if not to_extrapolated else sorted(to_extrapolated)[len(to_extrapolated) // 2],
        "worst_mesh160_residual_v": max(residual_160) if residual_160 else None,
        "public_decision_cases": len(standard),
        "near_onset": {
            "rule": "standard-rung margin in [limit, limit + worst mesh-20 bias): labelled safe by the reference, could plate",
            "count": within,
            "share": None if within is None or not standard else within / len(standard),
        },
    }  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(prog="plating_convergence")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("run")
    command.add_argument("--cases", required=True)
    command.add_argument("--out", required=True)
    command.add_argument("--workers", type=int, default=6)
    command.add_argument("--mid-workers", type=int, default=MID_WORKERS)
    probe = sub.add_parser("run-probe")
    probe.add_argument("--jobs", required=True)
    probe.add_argument("--probe-index", type=int, required=True)
    probe.add_argument("--out", required=True)
    select = sub.add_parser("select-panel")
    select.add_argument("--contract", required=True)
    select.add_argument("--records", required=True)
    report = sub.add_parser("bias-report")
    report.add_argument("--summary", required=True)
    report.add_argument("--contract", required=True)
    report.add_argument("--records", required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run(args.cases, args.out, args.workers, args.mid_workers)
    elif args.command == "run-probe":
        try:
            result = run_probe(args.jobs, args.probe_index, args.out)
        except (OSError, ValueError) as exc:
            parser.error(f"refused: {exc}")
        # Exit zero is driver completion only; comparison/adequacy is downstream.
        return 0 if result.get("status") == "OK" else 1
    elif args.command == "select-panel":
        result = select_panel(args.contract, args.records)
    else:
        result = bias_report(args.summary, args.contract, args.records)
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
