"""Cooling value check at #1084 point B (registry
cooling-feasibility-02/point-b-registry.json), and the evaluation `point_c`
reuses with its own envelope.

    python -m scripts.dev.cold_plate.point_b --runs DIR --out OUT.json

The registered value-search composition applied to the point-B solves:
- per design: the cell conductance h and face profile from its B uniform
  solve (40 C, 1,000 W, 1.5 L/min/kW); the coolant rise is that solve's
  outlet minus inlet (power-independent at fixed flow per kW);
- a stratum (inlet, heat, map ratio, band) scales the face rise linearly in
  heat, adds the inlet, and for a ratio > 1 adds the solved ratio-2 band
  response scaled by the post-spreader excess, (peak/mean - 1) / (2 - 1);
- the post-spreader flux is the exact 2D lid series (lid k, thickness, TIM2
  5e-6 m2K/W) from `lid_spreading.presolve`; the interface peak is
  max(face + TIM2 * q_b);
- a ratio > 1 stratum is scored on the worse of the central (15 mm) and
  outlet (25 mm) bands;
- hydraulics: dp at the stratum flow = base dp x heat / 1,000 (laminar,
  flow per kW fixed), feasible when <= the allocation.

PASS = interface peak <= 85 C and dp feasible. A design with an invalid
reference solve for a needed map is UNRESOLVED there, never a FAIL. With
`validity` on, a stratum whose predicted coolant maximum (inlet + heat-scaled
rise of the design's own valid solve) exceeds the PG25 model's 99 C is also
UNRESOLVED for that design.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.cold_plate import lid_spreading as ls

LIMIT_C, TIM2, COOLANT_MAX_C = 85.0, 5e-6, 99.0
BASE_INLET_C, BASE_HEAT_W, SOLVED_RATIO = 40.0, 1000.0, 2.0
BANDS = {"central": ("B_central_r2", 15.0), "outlet": ("B_outlet_r2", 25.0)}
NEAR_K = 2.0
#: the registered point-B envelope
B = {
    "inlets_c": (37.0, 40.0, 42.0),
    "heats_w": (900.0, 1000.0, 1100.0),
    "ratios": (1.0, 1.5, 2.0),
    "lid_t_mm": 3.0,
    "lid_k": (2000.0, 5000.0, 10000.0),
    "dp_limit_pa": 25_000.0,
    "validity": False,
}


def load(runs):
    designs = {}
    for line in Path(runs, "records.jsonl").read_text().splitlines():
        r = json.loads(line)
        designs.setdefault(r["design_id"], {})[r["stratum"]] = r
    return designs


def _ok(rec):
    return rec is not None and rec["status"] == "OK"


def prepare(designs):
    out = {}
    for did, recs in sorted(designs.items()):
        u = recs.get("B_uniform")
        if not _ok(u):
            out[did] = None
            continue
        h, prof = ls.design_h(u)
        fluid = {"uniform": u["checks"]["fluid_max_c"] - BASE_INLET_C}
        for name, (s, _) in BANDS.items():
            fluid[name] = (
                recs[s]["checks"]["fluid_max_c"] - BASE_INLET_C
                if _ok(recs.get(s))
                else None
            )
        out[did] = {
            "h": h,
            "rise": prof - BASE_INLET_C,
            "coolant_rise": u["outputs"]["outlet_c"] - BASE_INLET_C,
            "fluid_rise": fluid,
            "dp_pa": u["outputs"]["pressure_drop_pa"],
            "bands": {
                name: np.array(recs[s]["outputs"]["profile_c"]) - prof if _ok(recs.get(s)) else None
                for name, (s, _) in BANDS.items()
            },
        }  # fmt: skip
    return out


def interface_peak(d, inlet, heat, ratio, band, lid_k, lid_t_mm, validity=False):
    s = heat / BASE_HEAT_W
    seg = (np.arange(len(d["rise"])) + 0.5) * ls.L / len(d["rise"])
    if validity:
        rise = d["fluid_rise"]["uniform" if ratio == 1.0 else band]
        if rise is None or inlet + s * rise > COOLANT_MAX_C:
            return None
    if ratio == 1.0:
        return inlet + s * float(d["rise"].max()) + TIM2 * heat / ls.L**2
    if d["bands"][band] is None:
        return None
    x, q = ls.raw_flux(heat, ratio, BANDS[band][1])
    qb = ls.presolve(q, x, lid_t_mm, lid_k, TIM2, d["h"], d["coolant_rise"])
    beta = (qb.max() / qb.mean() - 1.0) / (SOLVED_RATIO - 1.0)
    face = inlet + s * (d["rise"] + beta * d["bands"][band])
    return float(np.max(face + TIM2 * np.interp(seg, x, qb)))


def stratum(prepared, inlet, heat, ratio, lid_k, env):
    rows = {}
    for did, d in prepared.items():
        if d is None:
            rows[did] = None
            continue
        peaks = [
            interface_peak(
                d, inlet, heat, ratio, b, lid_k, env["lid_t_mm"], env["validity"]
            )
            for b in (BANDS if ratio > 1 else ["central"])
        ]
        if any(p is None for p in peaks):
            rows[did] = None
            continue
        margin = LIMIT_C - max(peaks)
        dp = d["dp_pa"] * heat / BASE_HEAT_W
        rows[did] = {
            "margin_k": margin,
            "dp_pa": dp,
            "pass": margin >= 0 and dp <= env["dp_limit_pa"],
        }
    resolved = {k: v for k, v in rows.items() if v is not None}
    passing = [k for k, v in resolved.items() if v["pass"]]
    thermal = [k for k, v in resolved.items() if v["margin_k"] >= 0]
    margins = [v["margin_k"] for v in resolved.values()]
    best = (
        min(passing, key=lambda k: (resolved[k]["dp_pa"], -resolved[k]["margin_k"]))
        if passing
        else None
    )
    median_margin = float(np.median(margins)) if margins else None
    return {
        "resolved": len(resolved), "unresolved": len(rows) - len(resolved), "pass": len(passing),
        "pass_fraction": len(passing) / len(resolved) if resolved else None,
        "near_pass_2k": sum(v["pass"] and v["margin_k"] <= NEAR_K for v in resolved.values()),
        "near_fail_2k": sum((not v["pass"]) and -NEAR_K <= v["margin_k"] < 0 and v["dp_pa"] <= env["dp_limit_pa"]
                            for v in resolved.values()),
        "dp_infeasible": sum(v["dp_pa"] > env["dp_limit_pa"] for v in resolved.values()),
        "dp_binds": len(thermal) > len(passing),
        "margin_spread_k": max(margins) - min(margins) if margins else None,
        "margin_range_k": [min(margins), max(margins)] if margins else None,
        "median_margin_k": median_margin,
        "best": best,
        "best_margin_k": resolved[best]["margin_k"] if best else None,
        "best_dp_pa": resolved[best]["dp_pa"] if best else None,
        "best_minus_median_k": resolved[best]["margin_k"] - median_margin if best else None,
        "rows": rows,
    }  # fmt: skip


def evaluate(prepared, lid_k, env=B):
    per = {}
    for inlet, heat, ratio in itertools.product(
        env["inlets_c"], env["heats_w"], env["ratios"]
    ):
        per[f"i{inlet:g}-q{heat:g}-r{ratio:g}"] = stratum(
            prepared, inlet, heat, ratio, lid_k, env
        )
    frac = [v["pass_fraction"] for v in per.values()]
    bests = {v["best"] for v in per.values() if v["best"]}
    return {
        "strata": per,
        "pass_fraction_20_80_all": all(f is not None and 0.2 <= f <= 0.8 for f in frac),
        "pass_fraction_20_80_count": sum(f is not None and 0.2 <= f <= 0.8 for f in frac),
        "spread_5k_all": all(v["margin_spread_k"] is not None and v["margin_spread_k"] >= 5 for v in per.values()),
        "pass_every_stratum": all(v["pass"] >= 1 for v in per.values()),
        "contested_strata": sum(v["near_pass_2k"] >= 5 and v["near_fail_2k"] >= 5 for v in per.values()),
        "dp_binding_strata": sum(v["dp_binds"] for v in per.values()),
        "distinct_bests": sorted(bests),
        "best_changes": len(bests) >= 2,
    }  # fmt: skip


def main(runs, out):
    prepared = prepare(load(runs))
    doc = {
        "schema": "carbon.cooling.point-b-value-check.v1",
        "registry": "docs/development/evidence/cooling-feasibility-02/point-b-registry.json",
        "designs": len(prepared),
        "designs_without_valid_uniform": sorted(
            k for k, v in prepared.items() if v is None
        ),
        "lid_k": {f"k{k:g}": evaluate(prepared, k) for k in B["lid_k"]},
    }
    Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="point_b")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    doc = main(args.runs, args.out)
    for key, res in doc["lid_k"].items():
        print(key, {k: v for k, v in res.items() if k != "strata"})
