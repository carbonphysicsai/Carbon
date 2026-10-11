"""Cooling value search (registry cooling-feasibility-02/value-search-registry.json).

    python -m scripts.dev.cold_plate.value_search --cfeas DIR --out OUT.json

The lid pre-solve and design prediction of `lid_spreading`, vectorised over
the registered buyer-parameter grid. Existing cell solves only.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.cold_plate import lid_spreading as ls

GRID = {
    "warm_inlet_c": [30.0, 32.5, 35.0, 37.5, 40.0, 42.5, 45.0],
    "lid": [(391.0, 1.5), (391.0, 3.0), (2000.0, 1.5), (2000.0, 3.0),
            (3000.0, 1.5), (3000.0, 3.0), (5000.0, 1.5), (5000.0, 3.0)],
    "warm_power_w": [1200.0, 1350.0, 1500.0],
    "cold_power_w": [500.0, 1000.0, 1500.0],
}  # fmt: skip
R2 = ls.NOMINAL["R2"]
LIMIT = 85.0
X = (np.arange(ls.NX) + 0.5) * ls.L / ls.NX
N = np.arange(1, ls.MODES + 1)
KN = N * math.pi / ls.L
COS = np.cos(np.outer(KN, X))  # modes x points
RISE = ls.coolant_rise(
    1500.0
)  # flow scales with power: the bulk rise is power-independent
TBN = 2.0 * ((-1.0) ** N - 1.0) / (N * math.pi) ** 2 * RISE


def map_modes(centre):
    _, q = ls.raw_flux(1500.0, 3.0, centre)
    return q.mean(), (2.0 / ls.L) * (COS @ q) * (ls.L / ls.NX)


MAPS = {name: map_modes(c) for name, c in (("central", 15.0), ("outlet", 24.0))}


def post_map(name, k, t_mm, h, power):
    """Post-spreader q_b(x) at `power` (linear in power, sink rise fixed)."""
    qbar, qn = MAPS[name]
    s = power / 1500.0
    a = KN * t_mm * 1e-3
    u = 1.0 / (R2 + 1.0 / h)
    a = np.minimum(a, 600)
    qbn = (s * qn - k * KN * TBN * np.sinh(a)) / (
        np.cosh(a) + (k * KN / u) * np.sinh(a)
    )
    return s * qbar + qbn @ COS


def load(cfeas):
    designs = ls.h_cells(cfeas)
    out = {}
    for did, recs in designs.items():
        u = recs.get("warm_uniform")
        if not u or u["status"] != "OK":
            continue
        h, prof_u = ls.design_h(u)
        hyd = u["outputs"]["pressure_drop_pa"] * u["derived"]["flow_m3_s"]
        hot = {}
        for name, stratum in (
            ("central", "warm_central_hotspot"),
            ("outlet", "warm_outlet_hotspot"),
        ):
            r = recs.get(stratum)
            hot[name] = (
                np.array(r["outputs"]["profile_c"])
                if r and r["status"] == "OK"
                else None
            )
        out[did] = {"h": h, "prof_u": prof_u, "hyd_1500_w": hyd, "hot": hot}
    return out, len(designs)


def strata(point):
    w_in, w_p, c_p = point["warm_inlet_c"], point["warm_power_w"], point["cold_power_w"]
    return {
        "cold_uniform": (30.0, c_p, None),
        "typical_uniform": (min(40.0, w_in), 1000.0, None),
        "warm_uniform": (w_in, w_p, None),
        "warm_central_band": (w_in, w_p, "central"),
        "warm_outlet_band": (w_in, w_p, "outlet"),
    }


def evaluate(designs, n_designs, point):
    k, t_mm = point["lid"]
    seg = (np.arange(30) + 0.5) * ls.L / 30
    per, passes = {}, {}
    for sname, (inlet, power, band) in strata(point).items():
        s = power / 1500.0
        margins, best = {}, None
        for did, d in designs.items():
            rise_u = d["prof_u"] - 45.0
            if band is None:
                peak = inlet + s * float(rise_u.max()) + R2 * power / ls.L**2
            else:
                if d["hot"][band] is None:
                    continue
                qb = post_map(band, k, t_mm, d["h"], power)
                beta = (qb.max() / qb.mean() - 1.0) / 2.0
                face = inlet + s * (rise_u + beta * (d["hot"][band] - d["prof_u"]))
                peak = float(np.max(face + R2 * np.interp(seg, X, qb)))
            margins[did] = LIMIT - peak
        resolved = len(margins)
        n_pass = sum(m >= 2.0 for m in margins.values())
        passing = [did for did, m in margins.items() if m >= 2.0]
        for did in passing:
            passes.setdefault(did, set()).add(sname)
        if passing:
            best = min(
                passing, key=lambda dd: (designs[dd]["hyd_1500_w"] * s**2, -margins[dd])
            )
        by_margin = max(margins, key=margins.get) if margins else None
        frac = n_pass / resolved if resolved else None
        spread = max(margins.values()) - min(margins.values()) if margins else None
        per[sname] = {
            "resolved": resolved, "unresolved": n_designs - resolved, "pass": n_pass,
            "pass_fraction": frac, "margin_spread_k": spread,
            "margin_range_k": [min(margins.values()), max(margins.values())] if margins else None,
            "a": frac is not None and 0.2 <= frac <= 0.8,
            "b": spread is not None and spread >= 5.0,
            "best_min_hydraulic": best, "best_by_margin": by_margin,
        }  # fmt: skip
    all_pass = sorted(did for did, ss in passes.items() if len(ss) == 5)
    bests = {v["best_min_hydraulic"] for v in per.values() if v["best_min_hydraulic"]}
    return {
        "strata": per,
        "a_all": all(v["a"] for v in per.values()),
        "b_all": all(v["b"] for v in per.values()),
        "c": bool(all_pass),
        "designs_passing_all": all_pass,
        "d": len(bests) >= 2,
        "distinct_bests": sorted(bests),
    }


def _ratio(q):
    return float(q.max() / q.mean())


def main(cfeas, out):
    designs, n_designs = load(cfeas)
    h_med = float(np.median([d["h"] for d in designs.values()]))
    step1 = {}
    for name in MAPS:
        step1[name] = {
            f"k{k:g}": {f"t{t:g}": _ratio(post_map(name, k, t, h_med, 1500.0))
                        for t in (1.5, 2.0, 3.0)}
            for k in (391.0, 2000.0, 3000.0, 4000.0, 5000.0)
        }  # fmt: skip
    rows = []
    for w_in, lid, w_p, c_p in itertools.product(*GRID.values()):
        point = {
            "warm_inlet_c": w_in,
            "lid": lid,
            "warm_power_w": w_p,
            "cold_power_w": c_p,
        }
        res = evaluate(designs, n_designs, point)
        res["point"] = point
        res["n_criteria"] = sum(res[c] for c in ("a_all", "b_all", "c", "d"))
        rows.append(res)
    meeting = [r for r in rows if r["n_criteria"] == 4]
    document = {
        "schema": "carbon.cooling.value-search.v1",
        "step1_post_spreader_peak_over_mean": step1,
        "h_cell_median": h_med,
        "grid_points": len(rows),
        "meeting_all": len(meeting),
        "rows": rows,
    }
    Path(out).write_text(
        json.dumps(document, indent=1, sort_keys=True, default=list) + "\n"
    )
    return document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="value_search")
    parser.add_argument("--cfeas", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    doc = main(args.cfeas, args.out)
    print(json.dumps(doc["step1_post_spreader_peak_over_mean"], indent=1))
    print("grid", doc["grid_points"], "meeting all four:", doc["meeting_all"])
