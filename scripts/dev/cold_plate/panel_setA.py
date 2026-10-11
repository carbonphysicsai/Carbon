"""Set-A spreader panel (registry cooling-feasibility-02/panel-setA-registry.json).

    python -m scripts.dev.cold_plate.panel_setA job JOB_ID --out DIR
    python -m scripts.dev.cold_plate.panel_setA plan --out PLAN.json
    python -m scripts.dev.cold_plate.panel_setA run PLAN.json --out DIR --parallel 8

One job is a candidate-specific fixed point between the lid (exact 2D
Fourier-cosine conduction, raw die map on top, TIM2 contact to the cell's
span-mean face temperature below) and the registered periodic-cell CFD,
which receives the lid's bottom flux q_b(x) as a cosine series in its
heated-patch expression. Under-relaxation 0.5 on q_b; converged when the
composed TIM2-interface peak moves <= 0.1 K and the L1 flux change is
<= 0.1 %; 20 iterations at most (then REFERENCE_UNRESOLVED).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analysis, domain, openfoam
from scripts.dev.cold_plate import feasibility02 as cf
from scripts.dev.cold_plate.reference import run_batch

L = 0.030
LID_K, LID_T_MM, R1, R2 = 3000.0, 3.0, 5.14e-6, 6e-6
LIMIT_C = 85.0
FLOW_LPM_PER_KW = 2.0
NX = 3000
X = (np.arange(NX) + 0.5) * L / NX
CELL_MODES = 60
CONTEXTS = {
    "cold_uniform": {
        "inlet_c": 30.0,
        "power_w": 1500.0,
        "ratio": 1.0,
        "centre_mm": 15.0,
    },
    "typical_uniform": {
        "inlet_c": 37.5,
        "power_w": 1250.0,
        "ratio": 1.0,
        "centre_mm": 15.0,
    },
    "warm_uniform": {
        "inlet_c": 37.5,
        "power_w": 1500.0,
        "ratio": 1.0,
        "centre_mm": 15.0,
    },
    "warm_central_band": {
        "inlet_c": 37.5,
        "power_w": 1500.0,
        "ratio": 3.0,
        "centre_mm": 15.0,
    },
    "warm_outlet_band": {
        "inlet_c": 37.5,
        "power_w": 1500.0,
        "ratio": 3.0,
        "centre_mm": 24.0,
    },
}
DESIGNS = {
    f"w{w:g}-d{d:g}": {
        "channel_width_mm": w,
        "fin_width_mm": 0.3,
        "channel_depth_mm": d,
        "base_mm": 0.5,
    }
    for w in (0.2, 0.3, 0.5)
    for d in (3.0, 6.0)
}


# --- maps and the lid ------------------------------------------------------------


def raw_map(ctx):
    case = {
        "channel_width_mm": 0.3, "fin_width_mm": 0.3, "channel_depth_mm": 2.0,
        "flow_lpm_per_kw": FLOW_LPM_PER_KW, "inlet_c": ctx["inlet_c"], "heat_load_w": ctx["power_w"],
        "hotspot_ratio": ctx["ratio"], "hotspot_center_mm": ctx["centre_mm"], "hotspot_width_mm": 2.5,
    }  # fmt: skip
    return np.array([domain.heat_flux(case, x * 1e3) for x in X])


def cosine(f, modes):
    """(a0, a_n) with f(x) = a0 + sum a_n cos(n pi x / L)."""
    n = np.arange(1, modes + 1)
    c = np.cos(np.outer(n * math.pi / L, X))
    return float(f.mean()), (2.0 / L) * (c @ f) * (L / NX)


def series(a0, an, x):
    n = np.arange(1, len(an) + 1)
    return a0 + np.cos(np.outer(np.atleast_1d(x), n * math.pi / L)) @ an


def lid(q_raw, sink, k=LID_K, t_mm=LID_T_MM, r2=R2, modes=200):
    """Bottom flux q_b(x), bottom (lid-side TIM2) and top (die-side lid)
    temperatures for raw top flux q_raw(x) and sink (cell face, span-mean)
    temperature profile sink(x), through the TIM2 contact r2."""
    t, u = t_mm * 1e-3, 1.0 / r2
    q0, qn = cosine(q_raw, modes)
    s0, sn = cosine(sink, modes)
    kn = np.arange(1, modes + 1) * math.pi / L
    a = np.minimum(kn * t, 600)
    sh, ch = np.sinh(a), np.cosh(a)
    qbn = (qn - k * kn * sn * sh) / (ch + (k * kn / u) * sh)
    bottom_n = sn + qbn / u
    top_n = bottom_n * ch + qbn / (k * kn) * sh
    qb = series(q0, qbn, X)
    bottom = series(s0 + q0 / u, bottom_n, X)
    top = series(s0 + q0 / u + q0 * t / k, top_n, X)
    return qb, bottom, top


# --- the cell with a tabulated (cosine-series) heated-face map ---------------------


@contextlib.contextmanager
def cell_map(a0, an):
    """Make the registered deck and analysis use q(x) = a0 + sum a_n cos."""
    terms = " + ".join(
        f"({float(c)!r})*cos({(i + 1) * math.pi / L!r}*pos().x())"
        for i, c in enumerate(an)
    )
    entry = (
        "q\n            {\n                type        expression;\n"
        f"                expression  #{{ {a0!r} + {terms} #}};\n            }}"
    )

    def flux(case, x_mm):
        return float(series(a0, an, x_mm * 1e-3)[0])

    saved = (openfoam._heat_flux_entry, domain.heat_flux, analysis.heat_flux)
    openfoam._heat_flux_entry = lambda case, d: entry
    domain.heat_flux = flux
    analysis.heat_flux = flux
    try:
        yield
    finally:
        openfoam._heat_flux_entry, domain.heat_flux, analysis.heat_flux = saved


def cell_inputs(design, ctx):
    return {
        "channel_width_mm": design["channel_width_mm"], "fin_width_mm": design["fin_width_mm"],
        "channel_depth_mm": design["channel_depth_mm"], "flow_lpm_per_kw": FLOW_LPM_PER_KW,
        "inlet_c": ctx["inlet_c"], "heat_load_w": ctx["power_w"], "hotspot_ratio": 1.0,
        "hotspot_center_mm": 15.0, "hotspot_width_mm": 2.5,
    }  # fmt: skip


def face_fields(case_dir, inputs):
    """Per x column: span-mean and max heated-face temperature (C), from the
    final solid fields (the registered face reconstruction)."""
    times = sorted(
        (t for t in (case_dir / "times").read_text().split() if t != "0"), key=float
    )
    t = times[-1]
    cells = list(
        zip(
            analysis.internal_field(case_dir / t / "solid" / "C"),
            analysis.internal_field(case_dir / t / "solid" / "T"),
        )
    )
    k_s = domain.FIXED["copper_k_w_mk"]
    z0 = min(c[0][2] for c in cells)
    cols = {}
    for (x, _y, z), temp in cells:
        if abs(z - z0) < 1e-12:
            face = temp + domain.heat_flux(inputs, x * 1e3) * z0 / k_s - domain.K0
            cols.setdefault(round(x, 12), []).append(face)
    xs = np.array(sorted(cols))
    return (
        xs,
        np.array([np.mean(cols[x]) for x in xs]),
        np.array([np.max(cols[x]) for x in xs]),
    )


def solve_cell(case_dir, design, ctx, qb, x_cells=None, resolution=None):
    a0, an = cosine(qb, CELL_MODES)
    inputs = cell_inputs(design, ctx)
    opts = {} if resolution is None else {"resolution": resolution}
    saved_x = openfoam.CELLS["x"]
    if x_cells:
        openfoam.CELLS["x"] = x_cells
    try:
        with cf.variant(design["base_mm"]), cell_map(a0, an):
            openfoam.write_case(inputs, case_dir, **opts)
            name = f"carbon-setA-{case_dir.parent.name}-{case_dir.name}"[:120]
            status, wall, detail = run_batch.solve(case_dir, name, 1, 14400)
            out = {"status": status or "RAN", "wall_s": round(wall, 1), "run": detail}
            if status is None:
                result = analysis.analyze_case(case_dir)
                out.update(outcome=result["outcome"], reasons=result["reasons"],
                           outputs=result.get("outputs"), checks=result.get("checks"),
                           derived=result["case"]["derived"])  # fmt: skip
                if result.get("outputs"):
                    xs, mean, peak = face_fields(case_dir, inputs)
                    out["face"] = {
                        "x_m": xs.tolist(),
                        "mean_c": mean.tolist(),
                        "max_c": peak.tolist(),
                    }
    finally:
        openfoam.CELLS["x"] = saved_x
    return out


def composed_peak(cell, qb):
    xs = np.array(cell["face"]["x_m"])
    q = np.interp(xs, X, qb)
    vals = np.array(cell["face"]["max_c"]) + R2 * q
    i = int(np.argmax(vals))
    return float(vals[i]), float(xs[i] * 1e3)


def run_job(job, out):
    out = Path(out) / job["job_id"]
    out.mkdir(parents=True, exist_ok=True)
    design, ctx = DESIGNS[job["design"]], CONTEXTS[job["context"]]
    q_raw = raw_map(ctx)
    modes = job.get("lid_modes", 200)
    # Start: the h-model face (bulk + qbar / h) under the raw map.
    rise = ctx["power_w"] / (domain.pg25("rho", domain.K0 + ctx["inlet_c"])
                             * ctx["power_w"] / 1000 * FLOW_LPM_PER_KW / 60000
                             * domain.pg25("cp", domain.K0 + ctx["inlet_c"]))  # fmt: skip
    sink0 = ctx["inlet_c"] + rise * X / L + q_raw.mean() / 55000.0
    qb, _, _ = lid(q_raw, sink0, modes=modes)
    history, prev_peak, record = [], None, {"job": job}
    for it in range(20):
        cell = solve_cell(
            out / f"iter{it:02d}",
            design,
            ctx,
            qb,
            job.get("x_cells"),
            job.get("resolution"),
        )
        step = {
            "iteration": it,
            "cell_status": cell.get("outcome", cell["status"]),
            "wall_s": cell["wall_s"],
        }
        if "face" not in cell:
            history.append(step)
            record.update(
                verdict="REFERENCE_UNRESOLVED",
                why=f"cell {step['cell_status']}: {cell.get('reasons') or cell.get('run')}",
            )
            break
        peak, at = composed_peak(cell, qb)
        sink = np.interp(
            X, np.array(cell["face"]["x_m"]), np.array(cell["face"]["mean_c"])
        )
        q_new, bottom, top = lid(q_raw, sink, modes=modes)
        l1 = float(np.mean(np.abs(q_new - qb)) / np.mean(np.abs(qb)))
        step.update(
            peak_c=peak, at_mm=at, l1_change=l1, applicability=cell.get("reasons")
        )
        history.append(step)
        converged = (
            prev_peak is not None and abs(peak - prev_peak) <= 0.1 and l1 <= 1e-3
        )
        if converged:
            record.update(
                verdict_inputs={
                    "interface_peak_c": peak,
                    "at_mm": at,
                    "last_peak_change_k": abs(peak - prev_peak),
                    "tim2_jump_peak_k": float(R2 * qb.max()),
                    "post_peak_over_mean": float(qb.max() / qb.mean()),
                    "lid_drop_mean_k": float(np.mean(top - bottom)),
                    "die_side_peak_c": float(np.max(top + R1 * q_raw)),
                    "pressure_drop_pa": cell["outputs"]["pressure_drop_pa"],
                    "hydraulic_power_w": cell["outputs"]["pressure_drop_pa"]
                    * cell["derived"]["flow_m3_s"],
                    "re_outlet": cell["checks"]["re_outlet"],
                    "fluid_max_c": cell["checks"]["fluid_max_c"],
                    "cell_outcome": cell["outcome"],
                    "cell_reasons": cell["reasons"],
                    "map_transfer_rel": float(
                        abs(np.mean(qb) - cosine(qb, CELL_MODES)[0]) / np.mean(qb)
                    ),
                },
            )
            break
        prev_peak = peak
        qb = 0.5 * q_new + 0.5 * qb
    else:
        record.update(
            verdict="REFERENCE_UNRESOLVED",
            why="coupling did not converge in 20 iterations",
        )
    record["iterations"] = history
    record["cell_wall_s_total"] = sum(h["wall_s"] for h in history)
    (out / "job.json").write_text(json.dumps(record, indent=1) + "\n")
    print(
        job["job_id"],
        len(history),
        record.get("verdict_inputs", {}).get("interface_peak_c"),
        record.get("verdict"),
        flush=True,
    )
    return record


def plan(out):
    jobs = [{"job_id": f"base-{d}-{c}", "kind": "base", "design": d, "context": c}
            for d in DESIGNS for c in CONTEXTS]  # fmt: skip
    for w in ("0.2", "0.3", "0.5"):
        for c in ("warm_central_band", "warm_outlet_band"):
            for rung, (xc, modes) in enumerate(((100, 400), (200, 800)), start=1):
                jobs.append({"job_id": f"refine{rung}-w{w}-d6-{c}", "kind": "refinement", "design": f"w{w}-d6",
                             "context": c, "x_cells": xc, "lid_modes": modes})  # fmt: skip
    Path(out).write_text(
        json.dumps({"batch": "cooling-setA-panel", "jobs": jobs}, indent=1) + "\n"
    )
    return len(jobs)


def run(plan_path, out, parallel):
    jobs = json.loads(Path(plan_path).read_text())["jobs"]
    done = {p.parent.name for p in Path(out).glob("*/job.json")}
    todo = [j for j in jobs if j["job_id"] not in done]
    with ProcessPoolExecutor(parallel) as pool:
        list(pool.map(run_job, todo, [out] * len(todo)))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="panel_setA")
    parser.add_argument("command", choices=("plan", "run", "job"))
    parser.add_argument("arg", nargs="?")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=8)
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(plan(args.out))
    elif args.command == "run":
        run(args.arg, args.out, args.parallel)
    else:
        jobs = {
            j["job_id"]: j
            for j in json.loads((args.out.parent / "panel-plan.json").read_text())[
                "jobs"
            ]
        }
        run_job(jobs[args.arg], args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
