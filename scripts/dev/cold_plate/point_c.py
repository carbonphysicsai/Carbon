"""Cooling stress point C: a DEVELOPMENT envelope derived from point B's
measurements, then the same value-check sheet (no new solves).

    python -m scripts.dev.cold_plate.point_c --runs DIR --registry OUT.json --out OUT.json

Test Lead 2026-10-11 under the owner's development autonomy: derive C from B,
not by hand. Adopting C into the frozen envelope stays the owner's.

The rules below are scripted and run in this order. The registry is written
before the evaluation. C reuses B's 96 cell solves, so its check is a
calibration on B's outcomes, not out-of-sample evidence.

1. **Lid thickness.** Take the largest of 3.0/2.5/2.0/1.5/1.0 mm at which the
   median design's ratio-2 vs ratio-1.5 interface peak differs by >= 1 K
   (half the 2 K contested window), at 40 C, 1,000 W, k 5,000.
2. **Low-heat corner.** Raise B's 900 W level in 25 W steps until no stratum's
   thermal pass fraction exceeds 80 %.
3. **dp allocation.** Use the median, over strata, of the largest pressure
   drop among thermally passing designs, rounded to 100 Pa. It then excludes a
   thermally adequate design in about half of the strata.
4. **Validity.** Any design-stratum whose predicted coolant maximum exceeds
   the PG25 model's 99 C is UNRESOLVED; nothing is extrapolated.
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

from scripts.dev.cold_plate import point_b as pb

THICKNESSES = (3.0, 2.5, 2.0, 1.5, 1.0)
RATIO_GAP_K = 1.0
HEAT_STEP_W, MAX_PASS = 25.0, 0.80
BASE_K = 5000.0


def _peak(d, inlet, heat, ratio, lid_t, lid_k, validity):
    peaks = [
        pb.interface_peak(d, inlet, heat, ratio, b, lid_k, lid_t, validity)
        for b in (pb.BANDS if ratio > 1 else ["central"])
    ]
    return None if any(p is None for p in peaks) else max(peaks)


def derive(prepared):
    steps = {}
    gaps = {}
    for t in THICKNESSES:
        diffs = []
        for d in prepared.values():
            if d is None:
                continue
            a = _peak(d, 40.0, 1000.0, 2.0, t, BASE_K, True)
            b = _peak(d, 40.0, 1000.0, 1.5, t, BASE_K, True)
            if a is not None and b is not None:
                diffs.append(a - b)
        gaps[t] = float(np.median(diffs))
    lid_t = next((t for t in THICKNESSES if gaps[t] >= RATIO_GAP_K), THICKNESSES[-1])
    steps["lid_t_mm"] = {"value": lid_t, "median_ratio2_minus_ratio1p5_k": gaps,
                         "rationale": f"largest thickness where the median design's ratio-2 vs ratio-1.5 peak differs by >= {RATIO_GAP_K} K (B's 3 mm gives {gaps[3.0]:.2f} K)"}  # fmt: skip
    env = {**pb.B, "lid_t_mm": lid_t, "dp_limit_pa": float("inf"), "validity": True}
    low, fractions = 900.0, {}
    while True:
        env["heats_w"] = (low, 1000.0, 1100.0)
        worst = 0.0
        for inlet, ratio in itertools.product(env["inlets_c"], env["ratios"]):
            s = pb.stratum(prepared, inlet, low, ratio, BASE_K, env)
            rows = [r for r in s["rows"].values() if r]
            if rows:
                worst = max(worst, sum(r["margin_k"] >= 0 for r in rows) / len(rows))
        fractions[low] = worst
        if worst <= MAX_PASS or low >= 1000.0 - HEAT_STEP_W:
            break
        low += HEAT_STEP_W
    steps["low_heat_w"] = {"value": low, "max_thermal_pass_fraction_by_level": fractions,
                           "rationale": f"smallest step up from B's 900 W at which no stratum passes more than {MAX_PASS:.0%} thermally"}  # fmt: skip
    maxima = []
    for inlet, heat, ratio in itertools.product(
        env["inlets_c"], env["heats_w"], env["ratios"]
    ):
        s = pb.stratum(prepared, inlet, heat, ratio, BASE_K, env)
        dps = [r["dp_pa"] for r in s["rows"].values() if r and r["margin_k"] >= 0]
        if dps:
            maxima.append(max(dps))
    cap = round(float(np.median(maxima)) / 100.0) * 100.0
    steps["dp_limit_pa"] = {"value": cap, "stratum_max_thermal_pass_dp_pa": sorted(maxima),
                            "rationale": "median over strata of the largest dp among thermally passing designs: the allocation excludes a thermally adequate design in about half the strata (B's 25 kPa never bound)"}  # fmt: skip
    env["dp_limit_pa"] = cap
    steps["dp_limit_pa"]["binding_strata"] = sum(m > cap for m in maxima)
    steps["dp_limit_pa"]["note"] = (
        "one high-dp design is the largest thermal passer everywhere, so the allocation can only bind by heat level "
        "(0, 9, 18 or 27 of 27 strata); under the registered selection (lowest dp among PASS) an allocation removes "
        "high-dp designs but never changes the best"
    )
    return env, steps


def validity_finding(designs, prepared):
    invalid = []
    for did, recs in sorted(designs.items()):
        for stratum, r in sorted(recs.items()):
            if r["status"] != "OK":
                invalid.append({"design": did, "stratum": stratum, "fluid_max_c": round(r["checks"]["fluid_max_c"], 2),
                                "reasons": r["reasons"]})  # fmt: skip
    unresolved = {}
    for checked in (False, True):
        env = {**pb.B_V1, "validity": checked}
        unresolved[checked] = sum(
            pb.stratum(prepared, inlet, heat, ratio, BASE_K, env)["unresolved"]
            for inlet, heat, ratio in itertools.product(
                env["inlets_c"], env["heats_w"], env["ratios"]
            )
        )
    return {
        "invalid_solves": invalid,
        "designs_affected": sorted({x["design"] for x in invalid}),
        "point_b_unresolved_design_strata": {
            "as_registered": unresolved[False],
            "with_the_99c_check": unresolved[True],
            "of": 27 * len(prepared),
            "note": "the extra design-strata are scaled predictions past 99 C (higher inlet or heat than the solve) that B's registered evaluation scored by extrapolation",
        },
        "finding": "the PG25 coolant model (30-99 C) is the cell envelope's validity boundary: at point B, 14 of 96 solves (8 of 32 designs, mostly in the hotspot bands) take the coolant past 99 C and are UNRESOLVED; they are never scored as FAIL. A buyer envelope that keeps these designs needs either a pre-check that excludes them or a coolant model valid above 99 C",
    }  # fmt: skip


def main(runs, registry_out, out):
    designs = pb.load(runs)
    prepared = pb.prepare(designs)
    env, steps = derive(prepared)
    registry = {
        "schema": "carbon.cooling.point-c-registry.v1",
        "status": "DEVELOPMENT stress stratum (Test Lead 2026-10-11, dev autonomy); adoption into the frozen envelope is the owner's",
        "derived_from": "point B's 96 cell solves (~carbon/runs/cpb, plan sha256 dc11be08...) by scripts/dev/cold_plate/point_c.py; no new solves",
        "independence": "C's values are tuned on B's outcomes: its value check is a calibration, not out-of-sample evidence",
        "envelope": {k: v for k, v in env.items()},
        "derivation": steps,
        "unchanged_from_B": "inlets 37/40/42 C, ratios 1/1.5/2 (worse of the central and outlet bands), 1,000 and 1,100 W, flow 1.5 L/min/kW, TIM2 5e-6, limit 85 C, lid k 2,000/5,000/10,000 as a sensitivity",
    }  # fmt: skip
    Path(registry_out).write_text(
        json.dumps(registry, indent=1, sort_keys=True, default=str) + "\n"
    )
    doc = {
        "schema": "carbon.cooling.point-c-value-check.v1",
        "registry": str(registry_out),
        "envelope": env,
        "lid_k": {f"k{k:g}": pb.evaluate(prepared, k, env) for k in env["lid_k"]},
        "validity_boundary": validity_finding(designs, prepared),
    }
    Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    return registry, doc


def rescore(runs, registry_path, out, validity="full"):
    """The registered C envelope rescored with the full validity check (v2)."""
    prepared = pb.prepare(pb.load(runs))
    env = json.loads(Path(registry_path).read_text())["envelope"]
    env = {**env, "validity": validity}
    for key in ("inlets_c", "heats_w", "ratios", "lid_k"):
        env[key] = tuple(env[key])
    doc = {
        "schema": "carbon.cooling.point-c-value-check.v2",
        "registry": str(registry_path),
        "envelope": env,
        "lid_k": {f"k{k:g}": pb.evaluate(prepared, k, env) for k in env["lid_k"]},
    }
    Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="point_c")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    registry, doc = main(args.runs, args.registry, args.out)
    print(json.dumps(registry["derivation"], indent=1, default=str)[:3000])
    for key, res in doc["lid_k"].items():
        print(key, {k: v for k, v in res.items() if k != "strata"})
