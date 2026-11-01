"""The F08 2.0 U panel and edge-check payload (Validator spec 2026-11-01), as inputs-only shards for Data Collection.

    python3 f08_v2_payload.py plan --seed SEED --out DIR        # shards + plan.json (inputs only, no outputs)

The judgements (`u_per_output`, `judge_cell`, `cut_side`) take the results as ``{cell: {(h, fillet_h): {output: value}}}``.

1. **U panel first**: 12 interior cases over the 11-dim box (the old six drawn by the registered 1.7 lattice sampler, the
   new four uniform in their approved ranges from a seed-derived stream, alloy cycled 4/4/4), each solved at the full
   rung ladder: three mesh sizes (the registered h 3 / 2.25 / 1.7, fillet rung 0.5) and three fillet rungs (fillet h
   1.0 / 0.5 / 0.25, h 1.7). U per output is the largest Roache estimate over the panel (rounded up, never below the measured
   band). If two or more of the twelve fail to solve or are non-monotone, STOP.
2. **Edge check**, judged against that U: 8 edge cells (each new dim at its low and high end, the old six at the TRAIN
   centre, alloy 6061-T6), 3 corner cells (one per alloy: fillet min, angle max, |offset| max, damping min) and the
   pad-validity corner (max |offset| at the minimum width). A monotone series passes if its Roache estimate <= U; a
   non-monotone one only if its full range <= U. A failed side is cut once by 12.5 % and rechecked; a failed corner
   becomes an exclusion.
3. **Smoke first**: the heaviest cell alone, then everything else (shard 0 holds that one job).

The registered ranges are OWNER-F08-V2-VALUES-01; the alloy PROPERTIES are HUMAN_INPUT until the signed transcription,
so the shards carry alloy ids only and a run refuses until the table is signed. Nothing here solves.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_bank
import f08_deck_v2 as v2

SCHEMA = "carbon.f08.v2-payload.v1"
OUTPUTS = (
    "worst_dynamic_mm_per_n",
    "static_tip_mm_per_n",
    "cad_mass_kg",
    "static_fillet_stress_mpa_per_n",
    "dynamic_fillet_stress_mpa_per_n",
)
EXACT = frozenset({"cad_mass_kg"})  # geometry only: identical on every rung, U = 0
PANEL_SIZE = 12
STOP_FAILURES = 2
#: The mesh ladder is the REGISTERED F08 ladder (h 3 / 2.25 / 1.7, refinement ratio 4/3: Validator ruling 2026-11-01,
#: so U stays like-for-like with U v1/v2 and h 0.85, about 8x the elements, is never solved). The fillet ladder is local
#: refinement at ratio 2. The Roache estimate takes the NON-UNIFORM-ratio form (MOTOR_REF_UNCERTAINTY_METHOD_20261019).
MESH_RUNGS = (3.0, 2.25, 1.7)
FILLET_RUNGS = (1.0, 0.5, 0.25)
BASE = {"h_mm": 1.7, "fillet_h_mm": 0.5}
SAFETY = 1.25  # Roache's three-grid safety factor (F08-SCIENCE-VALUES-01 V10)
MIN_ORDER = 0.5  # an observed order below this is not a convergent series (the Battery U-record stop rule)
CUT = 0.125
#: The 1.7 TRAIN box centre and corners (the signed region of the old six inputs).
CENTRE = {
    "length_mm": 220.0,
    "width_mm": 80.0,
    "thickness_mm": 6.0,
    "rib_height_mm": 12.0,
    "rib_thickness_mm": 4.0,
    "relief_length_mm": 40.0,
}
ALLOY_ORDER = tuple(
    v2.ALLOYS
)  # 6061-T6 (lowest E, most in-band modes), 4130-normalized, Ti-6Al-4V-annealed


class Refused(ValueError):
    pass


def _uniform(seed, label, index, low, high):
    digest = hashlib.sha256(f"f08v2:{seed}:{label}:{index}".encode()).digest()
    return low + (high - low) * int.from_bytes(digest[:8], "big") / 2**64


def _new_dims_centre():
    return {
        "fillet_radius_mm": sum(v2.RANGES["fillet_radius_mm"]) / 2,
        "load_angle_deg": sum(v2.RANGES["load_angle_deg"]) / 2,
        "load_offset_frac": 0.0,
        "damping_ratio": sum(v2.RANGES["damping_ratio"]) / 2,
    }


def _case(geometry, new, alloy):
    case = {**geometry, **new, "alloy": alloy}
    v2.validate_case(
        case
    )  # registered ranges, the fillet fits the junction, the pad stays on the plate
    return case


def u_panel(seed, count=PANEL_SIZE):
    """The interior panel: the old six from the registered lattice sampler, the new four seed-uniform, alloy cycled."""
    geometry = f08_bank.draw(f08_bank.registration(), seed, count)
    cases = []
    for i, row in enumerate(geometry):
        old = {name: float(row[name]) for name in v2.GEOMETRY}
        new = {
            name: _uniform(seed, name, i, *v2.RANGES[name]) for name in v2.NEW_INPUTS
        }
        alloy = ALLOY_ORDER[i % len(ALLOY_ORDER)]
        case = None
        # a draw whose fillet exceeds the junction is pulled to the junction's limit, never skipped (keeps the cycle)
        limit = 0.45 * min(
            old["thickness_mm"], old["rib_thickness_mm"], old["rib_height_mm"]
        )
        new["fillet_radius_mm"] = min(new["fillet_radius_mm"], limit)
        case = _case(old, new, alloy)
        cases.append({"cell": f"U{i:02d}", "kind": "u_panel", "case": case})
    return cases


def edge_cells():
    """8 edge cells, 3 corner cells (one per alloy) and the pad-validity corner."""
    centre_new = _new_dims_centre()
    cells = []
    for name in v2.NEW_INPUTS:
        for side, bound in zip(("low", "high"), v2.RANGES[name], strict=True):
            new = {**centre_new, name: bound}
            cells.append(
                {
                    "cell": f"E-{name}-{side}",
                    "kind": "edge",
                    "case": _case(CENTRE, new, ALLOY_ORDER[0]),
                }
            )
    lo_fillet, hi_angle = (
        v2.RANGES["fillet_radius_mm"][0],
        v2.RANGES["load_angle_deg"][1],
    )
    corner = {
        "fillet_radius_mm": lo_fillet,
        "load_angle_deg": hi_angle,
        "load_offset_frac": v2.RANGES["load_offset_frac"][1],
        "damping_ratio": v2.RANGES["damping_ratio"][0],
    }
    for alloy in ALLOY_ORDER:
        cells.append(
            {
                "cell": f"C-{alloy}",
                "kind": "corner",
                "case": _case(CENTRE, corner, alloy),
            }
        )
    narrow = {**CENTRE, "width_mm": 60.0}
    pad = {**centre_new, "load_offset_frac": v2.RANGES["load_offset_frac"][1]}
    cells.append(
        {
            "cell": "P-pad-validity",
            "kind": "pad",
            "case": _case(narrow, pad, ALLOY_ORDER[0]),
        }
    )
    return cells


def ladder_jobs(cell):
    """The five distinct solves of one cell: three mesh rungs (fillet rung 0.5) and the two other fillet rungs (h 1.7)."""
    jobs = [
        {"h_mm": h, "fillet_h_mm": BASE["fillet_h_mm"], "axis": "mesh"}
        for h in MESH_RUNGS
    ]
    jobs += [
        {"h_mm": BASE["h_mm"], "fillet_h_mm": f, "axis": "fillet"}
        for f in FILLET_RUNGS
        if f != BASE["fillet_h_mm"]
    ]
    return [
        {"cell": cell["cell"], "kind": cell["kind"], "case": cell["case"], **job}
        for job in jobs
    ]


def heaviest(jobs):
    """The smoke job: the finest mesh of the widest, thickest cell (the most nodes)."""

    def weight(job):
        c = job["case"]
        volume = (
            c["length_mm"] * c["width_mm"] * (c["thickness_mm"] + c["rib_height_mm"])
        )
        return (volume / job["h_mm"] ** 3, 1.0 / job["fillet_h_mm"])

    return max(jobs, key=weight)


def plan(seed, shard_size=20):
    """The whole payload: shard 0 is the smoke (one job), then the U panel, then the edge and corner cells."""
    cells = [*u_panel(seed), *edge_cells()]
    jobs = [job for cell in cells for job in ladder_jobs(cell)]
    smoke = heaviest(jobs)
    rest = [job for job in jobs if job is not smoke]
    panel = [j for j in rest if j["kind"] == "u_panel"]
    edges = [j for j in rest if j["kind"] != "u_panel"]
    ordered = [smoke, *panel, *edges]
    for index, job in enumerate(ordered):
        job["job_id"] = f"f08v2-{index:04d}"
    shards = [ordered[:1]] + [
        ordered[i : i + shard_size] for i in range(1, len(ordered), shard_size)
    ]
    return {
        "schema": SCHEMA,
        "decision": v2.DECISION,
        "seed": seed,
        "outputs": list(OUTPUTS),
        "exact": sorted(EXACT),
        "alloy_properties": "signed: OWNER-F08-V2-ALLOYS-SIGNED-01, the shards carry alloy ids only",
        "alloy_table_sha256": v2.ALLOY_SHA256,
        "jobs": len(ordered),
        "shards": shards,
    }


# ---------------------------------------------------------------- the Roache rule and the judgements


def _order(e21, e32, r21, r32):
    """The observed order of a monotone three-grid series with NON-UNIFORM refinement ratios (Celik et al. 2008 / Roache):
    p = |ln|e32/e21| + q(p)| / ln r21, q = ln((r21**p - s) / (r32**p - s)), s = sign(e32/e21); a fixed-point iteration.
    """
    ratio = abs(e32 / e21)
    sign = 1.0 if e32 / e21 > 0 else -1.0
    p = abs(math.log(ratio)) / math.log(r21)
    for _ in range(500):
        q = math.log((r21**p - sign) / (r32**p - sign)) if r21 != r32 else 0.0
        new = abs(math.log(ratio) + q) / math.log(r21)
        if abs(new - p) < 1e-13:
            return new
        p = new
    return p


def roache(coarse, mid, fine, *, sizes=None, safety=SAFETY):
    """Three solutions, coarse to fine, on grids of ``sizes`` (default 4 / 2 / 1: ratio 2) ->
    ``{"monotone", "order", "estimate", "range"}``. The estimate is the Roache error at the finest rung,
    ``safety * |fine - mid| / (r**p - 1)`` with ``r`` the mid/fine ratio and ``p`` the observed order for the (possibly
    non-uniform) ratios; None for a non-monotone or non-convergent series (observed order below MIN_ORDER), where the
    full range is the figure."""
    h_coarse, h_mid, h_fine = sizes if sizes is not None else (4.0, 2.0, 1.0)
    r32, r21 = h_coarse / h_mid, h_mid / h_fine
    values = (coarse, mid, fine)
    span = max(values) - min(values)
    e32, e21 = coarse - mid, mid - fine
    if e32 == 0 and e21 == 0:
        return {"monotone": True, "order": None, "estimate": 0.0, "range": span}
    monotone = e32 != 0 and e21 != 0 and (e32 > 0) == (e21 > 0) and abs(e21) < abs(e32)
    if not monotone:
        return {"monotone": False, "order": None, "estimate": None, "range": span}
    order = _order(e21, e32, r21, r32)
    if order < MIN_ORDER:
        return {"monotone": False, "order": order, "estimate": None, "range": span}
    return {
        "monotone": True,
        "order": order,
        "estimate": safety * abs(e21) / (r21**order - 1),
        "range": span,
    }


def rung_sizes(axis):
    """The grid sizes of an axis, coarse to fine."""
    return MESH_RUNGS if axis == "mesh" else FILLET_RUNGS


def estimate(results, cell, axis, output):
    """The Roache record of one output on one axis of one cell (``Refused`` if a rung is missing)."""
    return roache(*series(results, cell, axis, output), sizes=rung_sizes(axis))


def series(results, cell, axis, output):
    """The (coarse, mid, fine) values of one output on one axis of one cell, or a Refused if a rung is missing."""
    rungs = MESH_RUNGS if axis == "mesh" else FILLET_RUNGS
    values = []
    for rung in rungs:
        key = (rung, BASE["fillet_h_mm"]) if axis == "mesh" else (BASE["h_mm"], rung)
        row = results.get(cell, {}).get(key)
        if row is None or output not in row:
            raise Refused("rung_missing")
        values.append(row[output])
    return tuple(values)


def figure(estimate):
    """A series' judged figure: its Roache estimate when monotone, else its full range."""
    return estimate["estimate"] if estimate["monotone"] else estimate["range"]


def u_per_output(results, panel_cells):
    """The U panel verdict: per output the largest figure over the panel and axes (never below the measured band), the
    cells that failed to solve or were non-monotone, and the STOP flag (two or more of twelve).
    """
    u, bad = {name: 0.0 for name in OUTPUTS if name not in EXACT}, []
    for cell in panel_cells:
        failed = False
        for output in [name for name in OUTPUTS if name not in EXACT]:
            for axis in ("mesh", "fillet"):
                try:
                    est = estimate(results, cell, axis, output)
                except Refused:
                    failed = True
                    continue
                if not est["monotone"]:
                    failed = True
                u[output] = max(u[output], figure(est))
        if failed:
            bad.append(cell)
    for name in EXACT:  # geometry only
        for cell in panel_cells:
            for axis in ("mesh", "fillet"):
                try:
                    vals = series(results, cell, axis, name)
                except Refused:
                    continue
                if max(vals) != min(vals):
                    bad.append(cell)
    return {
        "u": u,
        "failed_cells": sorted(set(bad)),
        "stop": len(set(bad)) >= STOP_FAILURES,
    }


def judge_cell(results, cell, u):
    """Edge/corner verdict against U: every output on both axes must have its figure <= U."""
    over = []
    for output, bound in u.items():
        for axis in ("mesh", "fillet"):
            est = estimate(results, cell, axis, output)
            if figure(est) > bound:
                over.append(
                    {"output": output, "axis": axis, "figure": figure(est), "u": bound}
                )
    return {"cell": cell, "passes": not over, "over": over}


def cut_side(bounds, side, fraction=CUT):
    """Cut a failed side of a range inward once by ``fraction`` of the span (low side raises the low bound)."""
    low, high = bounds
    step = (high - low) * fraction
    return (low + step, high) if side == "low" else (low, high - step)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    document = plan(args.seed)
    (out / "plan.json").write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n"
    )
    for index, shard in enumerate(document["shards"]):
        (out / f"shard-{index:02d}.json").write_text(
            json.dumps({"schema": SCHEMA, "jobs": shard}, indent=1, sort_keys=True)
            + "\n"
        )
    print(json.dumps({"jobs": document["jobs"], "shards": len(document["shards"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
