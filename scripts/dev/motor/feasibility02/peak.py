"""Motor peak completion and peak frontier search (registry motor-feasibility-02, amendment_3).

    python -m scripts.dev.motor.feasibility02.peak complete --s1plan P --boundary B1PLAN --out PLAN
    python -m scripts.dev.motor.feasibility02.peak frontier --s1plan P --runs DIR... --out PLAN
    python -m scripts.dev.motor.feasibility02.peak skew --runs DIR... --plans PLAN... --out PLAN
    python -m scripts.dev.motor.feasibility02.peak rung2 --runs DIR... --plans PLAN... --out PLAN
    python -m scripts.dev.motor.feasibility02.peak analyze --s1plan P --runs DIR... --plans PLAN... --out JSON

Test Lead 2026-10-09 (#922): the buyer's peak floor is 12 N m at J 15,
gamma 0; the S3 peak rows reached 7.9-9.9 N m and the other designs had no
peak rows. Never relax a limit. Full question per geometry/skew action:
holding (J 10 gamma 0) mean >= 6, pk-pk <= 0.30 and <= 5 %; peak (J 15
gamma 0) mean >= 12, pk-pk <= 0.60 and <= 5 %; zero-current cogging <= 0.05.
Skew s in {0, 2, 4} deg: slice k at gamma - 5 d_k, d in {-s/2, 0, s/2}.

- **complete:** J 15 gamma 0 for every public design without it; J 15 gamma
  +-5/+-10 for the holding-FEASIBLE and near-limit designs (d01, d02, d06,
  d10, d17) and the five boundary midpoints. Nothing else.
- **frontier:** an OLS fit of the S1 J 10 gamma 0 mean on the six normalised
  coordinates (R2 0.99 on 24 designs) predicts the holding mean; the search
  region is the valid designs predicted >= 8.0 N m (peak/holding was 1.28-1.42
  in S3). Eight designs: the predicted maximum (random search, 200,000
  valid-checked points, seed 0) and seven maximin-spread points from the
  region (seed 0). Each: J 0, J 10 gamma 0, J 15 gamma 0, unskewed, standard.
- **skew:** every frontier or completed design whose J 15 gamma 0 mean is
  >= 11.5 N m gets J 10 and J 15 at gamma +-5/+-10.
- **rung2:** S3's rung 2 for every action whose full panel lies within one
  band of a limit (bands: mean 0.10, pk-pk 0.02 holding / 0.04 peak,
  cogging 0.02).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.motor.feasibility02 import stages
from scripts.dev.motor.feasibility02 import topology as tp

KEYS = list(tp.GRAMMAR)
TOPO = tp.TOPOLOGIES["10p12s"]
PEAK_CHECK = ("d01", "d02", "d06", "d10", "d17")
SKEWS = (-10.0, -5.0, 5.0, 10.0)
LIMITS = {
    "hold": {"mean": (6.0, 0.10), "pk": (0.30, 0.02), "frac": 0.05},
    "peak": {"mean": (12.0, 0.10), "pk": (0.60, 0.04), "frac": 0.05},
    "cog": (0.05, 0.02),
}
RUNG2 = {"n_gap": 2880, "h_max": 0.5}


def case(cid, design, j, g, options=None):
    row = {
        "case_id": cid,
        "topology": "10p12s",
        "design": design,
        "j_a_mm2": j,
        "gamma_deg": g,
    }
    if options:
        row["options"] = dict(options)
    return row


def _u(design):
    return np.array(
        [
            (design[k] - tp.GRAMMAR[k][0]) / (tp.GRAMMAR[k][1] - tp.GRAMMAR[k][0])
            for k in KEYS
        ]
    )


def complete(designs, boundary_cases, records):
    out = []
    for i, d in enumerate(designs):
        if f"s3pk-d{i:02d}-j15g0" not in records:
            out.append(case(f"pkc-d{i:02d}-j15g0", d, 15.0, 0.0))
        if f"d{i:02d}" in PEAK_CHECK:
            out += [case(f"pkc-d{i:02d}-j15g{g:g}", d, 15.0, g) for g in SKEWS]
    points = {c["case_id"].rsplit("-j", 1)[0]: c["design"] for c in boundary_cases}
    for tag, d in sorted(points.items()):
        b = tag.split("-")[-1]
        out += [case(f"pkc-{b}-j15g{g:g}", d, 15.0, g) for g in (0.0, *SKEWS)]
    return out


def frontier(designs, records):
    rows = [
        (i, d)
        for i, d in enumerate(designs)
        if records.get(f"s1-d{i:02d}-j10g0", {}).get("status") == "OK"
    ]
    x = np.array([_u(d) for _, d in rows])
    y = np.array([records[f"s1-d{i:02d}-j10g0"]["derived"]["mean_nm"] for i, _ in rows])
    coef, *_ = np.linalg.lstsq(np.c_[np.ones(len(x)), x], y, rcond=None)
    rng = np.random.default_rng(0)
    region, best = [], None
    for _ in range(200_000):
        u = rng.random(6)
        d = {
            k: tp.GRAMMAR[k][0] + u[j] * (tp.GRAMMAR[k][1] - tp.GRAMMAR[k][0])
            for j, k in enumerate(KEYS)
        }
        p = float(coef[0] + coef[1:] @ u)
        if p < 8.0 or tp.validity(TOPO, d):
            continue
        region.append((u, d, p))
        if best is None or p > best[2]:
            best = (u, d, p)
    chosen = [best]
    while len(chosen) < 8:  # maximin from the region, deterministic
        far = max(
            region, key=lambda r: min(np.linalg.norm(r[0] - c[0]) for c in chosen)
        )
        chosen.append(far)
    out, reg = [], []
    for n, (_, d, p) in enumerate(chosen):
        tag = f"pkf-f{n:02d}"
        reg.append(
            {"point": tag, "predicted_holding_mean_nm": round(p, 3), "design": d}
        )
        out += [
            case(f"{tag}-j0g0", d, 0.0, 0.0),
            case(f"{tag}-j10g0", d, 10.0, 0.0),
            case(f"{tag}-j15g0", d, 15.0, 0.0),
        ]
    return out, reg, {"coef": [float(c) for c in coef], "region_points": len(region)}


def _mean(records, cid):
    r = records.get(cid)
    return r["derived"]["mean_nm"] if r and r.get("status") == "OK" else None


def skew(records, planned):
    out = []
    for c in planned:
        if c["j_a_mm2"] == 15.0 and c["gamma_deg"] == 0.0:
            m = _mean(records, c["case_id"])
            if m is not None and m >= 11.5:
                tag = c["case_id"].rsplit("-j", 1)[0]
                out += [
                    case(f"{tag}-j{j:g}g{g:g}", c["design"], j, g)
                    for j in (10.0, 15.0)
                    for g in SKEWS
                ]
    return [c for c in out if c["case_id"] not in records]


def _stack(records, tag, j, span, step):
    slices = []
    for d in (-span / 2, 0.0, span / 2):
        r = records.get(f"{tag}-j{j:g}g{-stages.PP * d:g}")
        if r is None or r.get("status") != "OK":
            return None
        slices.append(tp.slice_curve(r["outputs"]["torque_nm"], round(d / step)))
    return tp.metrics(tp.stack_curve(slices))


def _cog(records, tag, span, step):
    r = records.get(f"{tag}-j0g0")
    if r is None or r.get("status") != "OK":
        return None
    off = round(span / 2 / step)
    curve = r["outputs"]["torque_nm"]
    return tp.metrics(
        tp.stack_curve([tp.slice_curve(curve, o) for o in (-off, 0, off)])
    )["pk_pk_nm"]


def panel(records, tags_hold, tag_peak, tag_cog, span, step=stages.STEP_DEG):
    hold = _stack(records, tags_hold, 10.0, span, step)
    peak = _stack(records, tag_peak, 15.0, span, step)
    cog = _cog(records, tag_cog, span, step)
    if hold is None or peak is None or cog is None:
        return None
    over = {
        "hold_mean": (LIMITS["hold"]["mean"][0] - hold["mean_nm"])
        / LIMITS["hold"]["mean"][1],
        "hold_pk": (hold["pk_pk_nm"] - LIMITS["hold"]["pk"][0])
        / LIMITS["hold"]["pk"][1],
        "hold_frac": (hold["pk_pk_nm"] - 0.05 * abs(hold["mean_nm"]))
        / LIMITS["hold"]["pk"][1],
        "peak_mean": (LIMITS["peak"]["mean"][0] - peak["mean_nm"])
        / LIMITS["peak"]["mean"][1],
        "peak_pk": (peak["pk_pk_nm"] - LIMITS["peak"]["pk"][0])
        / LIMITS["peak"]["pk"][1],
        "peak_frac": (peak["pk_pk_nm"] - 0.05 * abs(peak["mean_nm"]))
        / LIMITS["peak"]["pk"][1],
        "cog": (cog - LIMITS["cog"][0]) / LIMITS["cog"][1],
    }
    return {
        "hold": hold,
        "peak": peak,
        "cogging_nm": cog,
        "overshoot_bands": over,
        "worst": max(over.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="motor peak")
    parser.add_argument(
        "command", choices=("complete", "frontier", "skew", "rung2", "analyze")
    )
    parser.add_argument("--s1plan", type=Path)
    parser.add_argument("--boundary", type=Path)
    parser.add_argument("--runs", type=Path, nargs="*", default=[])
    parser.add_argument("--plans", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    records = stages._records(args.runs)
    planned = [c for p in args.plans for c in json.loads(p.read_text())["cases"]]
    designs = json.loads(args.s1plan.read_text())["designs"] if args.s1plan else None
    extra = None
    if args.command == "complete":
        cases = complete(
            designs, json.loads(args.boundary.read_text())["cases"], records
        )
    elif args.command == "frontier":
        cases, points, fit = frontier(designs, records)
        extra = {"points": points, "fit": fit}
    elif args.command == "skew":
        cases = skew(records, planned)
    elif args.command == "rung2":
        cases = []  # filled by analyze's in-band list (see the registry); kept explicit
        for row in json.loads(args.plans[0].read_text()).get("in_band", []):
            cases += [
                case(f"{row['tag']}r2-j{j:g}g{g:g}", row["design"], j, g, RUNG2)
                for j, g in row["commands"]
            ]
    else:
        args.out.write_text(json.dumps({"records": len(records)}, indent=1) + "\n")
        return 0
    body = {
        "batch": f"motor-feas02-peak-{args.command}",
        "cases": cases,
        **(extra or {}),
    }
    args.out.write_text(json.dumps(body, indent=1) + "\n")
    print(json.dumps({"cases": len(cases), **({"fit": extra["fit"]} if extra else {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
