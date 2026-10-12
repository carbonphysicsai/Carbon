"""Point C out of sample: a fresh design set placed around each stratum's
pass boundary, sized to test "contested" (>= 5 PASS and >= 5 FAIL within
2 K), registered before any solve.

    python -m scripts.dev.cold_plate.point_c_oos plan --runs DIR --out PLAN.json --summary OUT.json

Test Lead 2026-10-11. The B solves only place the designs; they never enter
the out-of-sample score. Placement:

1. **Surrogates.** Fit thin-plate RBF surrogates on B's valid designs over
   log design coordinates: the C-envelope margin per stratum, log dp and the
   coolant rise. Leave-one-out errors are reported, not hidden.
2. **Pool.** 20,000 seeded uniform draws over #758's straight-channel
   grammar.
3. **Selection.** For every stratum, fill PASS-side (predicted margin
   0..+1.5 K) and FAIL-side (-1.5..0 K) slots, NEED_PER_SIDE each.
   - Only dp-feasible (predicted dp <= 5.9 kPa x 0.8) and
     coolant-valid (predicted maximum <= 95 C) draws are eligible.
   - Greedy: each step takes the draw that fills the most open slots, ties
     broken by the largest distance to every chosen and B design. Stop when
     all slots are filled or at MAX_DESIGNS.
4. **Solves.** Each design gets the three B base solves (40 C, 1,000 W,
   1.5 L/min/kW; uniform, ratio-2 central at 15 mm, ratio-2 outlet at 25 mm)
   with the same pinned OpenFOAM reference. No new solver settings.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import RBFInterpolator

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.cold_plate import point_b as pb
from scripts.dev.cold_plate import point_c as pc
from scripts.dev.cold_plate.feasibility02 import GRAMMAR

KEYS = ("channel_width_mm", "fin_width_mm", "channel_depth_mm", "base_mm")
POOL, SEED = 20_000, "COOLING-FEAS02-POINT-C-OOS"
NEED_PER_SIDE, SIDE_K, MAX_DESIGNS = 7, 1.5, 48
DP_HEADROOM, FLUID_MAX_C = 0.8, 95.0
BASE_INPUTS = {
    "flow_lpm_per_kw": 1.5,
    "inlet_c": 40.0,
    "heat_load_w": 1000.0,
    "hotspot_width_mm": 2.5,
}
SOLVES = {
    "B_uniform": (1.0, 15.0),
    "B_central_r2": (2.0, 15.0),
    "B_outlet_r2": (2.0, 25.0),
}


def _x(design):
    return np.log([design[k] for k in KEYS])


def training(runs, env):
    designs = pb.load(runs)
    prepared = pb.prepare(designs)
    first = {did: next(iter(recs.values())) for did, recs in designs.items()}
    rows, targets = [], {}
    strata = list(itertools.product(env["inlets_c"], env["heats_w"], env["ratios"]))
    for did, d in prepared.items():
        if d is None or any(d["bands"][b] is None for b in pb.BANDS):
            continue
        rec = first[did]
        x = {**{k: rec["inputs"][k] for k in KEYS[:3]}, "base_mm": rec["base_mm"]}
        values = {}
        for inlet, heat, ratio in strata:
            peaks = [pb.interface_peak(d, inlet, heat, ratio, b, pc.BASE_K, env["lid_t_mm"])
                     for b in (pb.BANDS if ratio > 1 else ["central"])]  # fmt: skip
            values[(inlet, heat, ratio)] = pb.LIMIT_C - max(peaks)
        values["log_dp"] = float(np.log(d["dp_pa"]))
        values["fluid_rise"] = max(v for v in d["fluid_rise"].values() if v is not None)
        rows.append(_x(x))
        for key, value in values.items():
            targets.setdefault(key, []).append(value)
    return np.array(rows), {k: np.array(v) for k, v in targets.items()}, strata


def fit(X, targets):
    models, loo = {}, {}
    for key, y in targets.items():
        models[key] = RBFInterpolator(X, y, kernel="thin_plate_spline", smoothing=1e-3)
        errs = []
        for i in range(len(y)):
            keep = np.arange(len(y)) != i
            m = RBFInterpolator(
                X[keep], y[keep], kernel="thin_plate_spline", smoothing=1e-3
            )
            errs.append(float(m(X[i : i + 1])[0] - y[i]))
        loo[str(key)] = {
            "rmse": float(np.sqrt(np.mean(np.square(errs)))),
            "max_abs": float(np.max(np.abs(errs))),
        }
    return models, loo


def pool():
    rng = random.Random(
        int.from_bytes(hashlib.sha256(SEED.encode()).digest()[:8], "big")
    )
    return [{k: rng.uniform(*GRAMMAR[k]) for k in KEYS} for _ in range(POOL)]


def select(models, strata, X_train, env):
    draws = pool()
    Xp = np.array([_x(d) for d in draws])
    pred = {s: models[s](Xp) for s in strata}
    dp = np.exp(models["log_dp"](Xp)) * max(env["heats_w"]) / pb.BASE_HEAT_W
    fluid = (
        max(env["inlets_c"])
        + models["fluid_rise"](Xp) * max(env["heats_w"]) / pb.BASE_HEAT_W
    )
    eligible = (dp <= DP_HEADROOM * env["dp_limit_pa"]) & (fluid <= FLUID_MAX_C)
    slots = {(s, side): NEED_PER_SIDE for s in strata for side in ("pass", "fail")}
    fills = {}
    for s in strata:
        fills[(s, "pass")] = (pred[s] >= 0) & (pred[s] <= SIDE_K) & eligible
        fills[(s, "fail")] = (pred[s] < 0) & (pred[s] >= -SIDE_K) & eligible
    chosen, anchors = [], [x for x in X_train]
    while len(chosen) < MAX_DESIGNS and any(v > 0 for v in slots.values()):
        gain = sum(fills[k].astype(int) for k, v in slots.items() if v > 0)
        if gain.max() == 0:
            break
        top = np.flatnonzero(gain == gain.max())
        dist = np.min(
            np.linalg.norm(Xp[top][:, None, :] - np.array(anchors)[None, :, :], axis=2),
            axis=1,
        )
        pick = int(top[np.argmax(dist)])
        chosen.append(pick)
        anchors.append(Xp[pick])
        for k, left in slots.items():
            if left > 0 and fills[k][pick]:
                slots[k] = left - 1
        eligible[pick] = False
        for mask in fills.values():
            mask[pick] = False
    designs = [
        {"design_id": f"o{i:02d}", **{k: round(draws[p][k], 4) for k in KEYS}}
        for i, p in enumerate(chosen)
    ]
    predicted = {d["design_id"]: {f"i{s[0]:g}-q{s[1]:g}-r{s[2]:g}": round(float(pred[s][p]), 2) for s in strata}
                 for d, p in zip(designs, chosen)}  # fmt: skip
    return (
        designs,
        predicted,
        {
            f"{s[0]:g}/{s[1]:g}/{s[2]:g}:{side}": v
            for (s, side), v in slots.items()
            if v > 0
        },
    )


def cases(designs):
    out = []
    for d in designs:
        for stratum, (ratio, centre) in SOLVES.items():
            out.append({"case_id": f"{d['design_id']}-{stratum}", "design_id": d["design_id"], "stratum": stratum,
                        "base_mm": d["base_mm"],
                        "inputs": {"channel_width_mm": d["channel_width_mm"], "fin_width_mm": d["fin_width_mm"],
                                   "channel_depth_mm": d["channel_depth_mm"], **BASE_INPUTS,
                                   "hotspot_ratio": ratio, "hotspot_center_mm": centre}})  # fmt: skip
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="point_c_oos")
    parser.add_argument("command", choices=("plan",))
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args(argv)
    registry = json.loads(
        (
            ROOT
            / "docs/development/evidence/cooling-feasibility-02/point-c-registry.json"
        ).read_text()
    )
    env = {**registry["envelope"], "validity": True}
    for key in ("inlets_c", "heats_w", "ratios", "lid_k"):
        env[key] = tuple(env[key])
    X, targets, strata = training(args.runs, env)
    models, loo = fit(X, targets)
    designs, predicted, open_slots = select(models, strata, X, env)
    plan = {"batch": "cooling-feas02-point-c-oos", "cases": cases(designs)}
    body = json.dumps(plan, indent=1) + "\n"
    args.out.write_text(body)
    summary = {
        "schema": "carbon.cooling.point-c-oos-plan.v1",
        "plan_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "designs": designs, "solves": len(plan["cases"]), "training_designs": len(X),
        "surrogate_loo": loo, "predicted_margins_k": predicted, "unfilled_slots": open_slots,
    }  # fmt: skip
    args.summary.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in ("plan_sha256", "solves", "training_designs", "unfilled_slots")
            }
        )
    )
    print("loo rmse (K):", {k: round(v["rmse"], 2) for k, v in list(loo.items())[:6]})


if __name__ == "__main__":
    main()
