"""Motor boundary step (registry motor-feasibility-02/registry.json, amendment_2).

    python -m scripts.dev.motor.feasibility02.boundary round1 --s1plan P --out PLAN
    python -m scripts.dev.motor.feasibility02.boundary round2 --s1plan P --runs DIR... --out PLAN
    python -m scripts.dev.motor.feasibility02.boundary rung2 --s1plan P --runs DIR... --out PLAN
    python -m scripts.dev.motor.feasibility02.boundary analyze --s1plan P --runs DIR... --out JSON

Test Lead 2026-10-08: T2(a) failed by one near-limit INFEASIBLE design; add
resolution at the frontier, never a looser band. For each FEASIBLE design,
its nearest near-limit INFEASIBLE design in the normalised grammar space
(each variable scaled to [0, 1] over its bounds) is its pair. Round 1 solves
the midpoint of each pair (t = 0.5 from the feasible end). Round 2 moves one
step toward the frontier: t = 0.75 if the midpoint is FEASIBLE at standard,
0.25 if INFEASIBLE, none if in-band (rung 2 decides first). A point that
fails the geometric validity rule moves to the nearest valid t on the same
segment in 0.05 steps. Every point is solved at the frozen precision command
(J 10, gamma 0) with the 4-deg three-slice skew (gamma -10/0/+10) and at
J 0; a point within one band of a limit gets the S3 rung-2 settings.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.motor.feasibility02 import stages
from scripts.dev.motor.feasibility02 import topology as tp

FEASIBLE = ("d06", "d09", "d12", "d16", "d21")  # value-checks.json @ 5f373b199
NEAR = ("d01", "d02", "d10", "d17")
SPAN = 4.0
COMMANDS = ((0.0, 0.0), (10.0, -10.0), (10.0, 0.0), (10.0, 10.0))
RUNG2 = {"n_gap": 2880, "h_max": 0.5}  # S3's registered rung 2
LIMITS = {"mean": (6.0, 0.10), "pk": (0.30, 0.02), "cog": (0.05, 0.02)}


def _norm(design):
    return [(design[k] - lo) / (hi - lo) for k, (lo, hi) in tp.GRAMMAR.items()]


def pairs(designs):
    out = []
    for f in FEASIBLE:
        df = _norm(designs[int(f[1:])])
        n = min(NEAR, key=lambda n: math.dist(df, _norm(designs[int(n[1:])])))
        out.append((f, n))
    return out


def point(designs, f, n, t):
    """The valid design nearest t on segment f -> n (0.05 steps), or None."""
    a, b = designs[int(f[1:])], designs[int(n[1:])]
    topo = tp.TOPOLOGIES["10p12s"]
    for dt in (0.0, 0.05, -0.05, 0.10, -0.10, 0.15, -0.15, 0.20, -0.20):
        s = round(t + dt, 2)
        if not 0 < s < 1:
            continue
        d = {k: a[k] + s * (b[k] - a[k]) for k in tp.GRAMMAR}
        if not tp.validity(topo, d):
            return s, d
    return None, None


def cases(tag, design, options=None):
    rows = []
    for j, g in COMMANDS:
        row = {
            "case_id": f"{tag}-j{j:g}g{g:g}",
            "topology": "10p12s",
            "design": design,
            "j_a_mm2": j,
            "gamma_deg": g,
        }
        if options:
            row["options"] = dict(options)
        rows.append(row)
    return rows


def _metrics(records, prefix, step):
    """Holding (4-deg stack) metrics and cogging for one solved point, or None."""
    curves = {}
    for j, g in COMMANDS:
        r = records.get(f"{prefix}-j{j:g}g{g:g}")
        if r is None or r.get("status") != "OK":
            return None
        curves[(j, g)] = r["outputs"]["torque_nm"]
    off = round(SPAN / 2 / step)
    slices = [
        tp.slice_curve(curves[(10.0, -stages.PP * d)], round(d / step))
        for d in (-SPAN / 2, 0.0, SPAN / 2)
    ]
    hold = tp.metrics(tp.stack_curve(slices))
    cog = tp.metrics(
        tp.stack_curve([tp.slice_curve(curves[(0.0, 0.0)], o) for o in (-off, 0, off)])
    )["pk_pk_nm"]
    return {"mean_nm": hold["mean_nm"], "pk_pk_nm": hold["pk_pk_nm"], "ripple_fraction": hold["ripple_fraction"],
            "cogging_nm": cog}  # fmt: skip


def overshoot_bands(m):
    """Largest normalised overshoot (positive = beyond a limit)."""
    return max((LIMITS["mean"][0] - m["mean_nm"]) / LIMITS["mean"][1], (m["pk_pk_nm"] - LIMITS["pk"][0]) / LIMITS["pk"][1],
               (m["ripple_fraction"] - 0.05) * abs(m["mean_nm"]) / LIMITS["pk"][1],
               (m["cogging_nm"] - LIMITS["cog"][0]) / LIMITS["cog"][1])  # fmt: skip


def in_band(m):
    return abs(overshoot_bands(m)) <= 1.0


def round1(designs):
    out, registry = [], []
    for i, (f, n) in enumerate(pairs(designs)):
        s, d = point(designs, f, n, 0.5)
        registry.append({"point": f"b{i:02d}", "pair": [f, n], "t": s})
        if d is not None:
            out += cases(f"s4b-b{i:02d}", d)
    return out, registry


def round2(designs, records):
    out, registry = [], []
    for i, (f, n) in enumerate(pairs(designs)):
        m = _metrics(records, f"s4b-b{i:02d}", stages.STEP_DEG)
        if m is None or in_band(m):
            continue
        t = 0.75 if overshoot_bands(m) < 0 else 0.25
        s, d = point(designs, f, n, t)
        registry.append({"point": f"b{i + 5:02d}", "pair": [f, n], "t": s})
        if d is not None:
            out += cases(f"s4b-b{i + 5:02d}", d)
    return out, registry


def rung2(records, plans):
    out = []
    for case in plans:
        tag = case["case_id"].rsplit("-j", 1)[0]
        m = _metrics(records, tag, stages.STEP_DEG)
        if (
            m is not None
            and in_band(m)
            and not any(
                c["case_id"].startswith(tag.replace("s4b", "s4r2")) for c in out
            )
        ):
            out += cases(tag.replace("s4b", "s4r2"), case["design"], RUNG2)
    return out


def analyze(records, plans):
    rows = {}
    for case in plans:
        tag = case["case_id"].rsplit("-j", 1)[0]
        if tag in rows:
            continue
        std = _metrics(records, tag, stages.STEP_DEG)
        r2 = _metrics(records, tag.replace("s4b", "s4r2"), stages.STEP_DEG / 2)
        if std is None:
            rows[tag] = {"verdict": "FAILED_INFRA_OR_NOT_RUN"}
            continue
        ob = overshoot_bands(std)
        if r2 is not None:
            o2 = overshoot_bands(r2)
            verdict = (
                "REFERENCE_UNRESOLVED"
                if (ob <= 0) != (o2 <= 0)
                else ("FEASIBLE" if o2 <= 0 else "INFEASIBLE")
            )
        elif in_band(std):
            verdict = "REFERENCE_UNRESOLVED"
        else:
            verdict = "FEASIBLE" if ob <= 0 else "INFEASIBLE"
        rows[tag] = {
            "standard": std,
            "rung2": r2,
            "overshoot_bands": ob,
            "verdict": verdict,
        }
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="motor boundary")
    parser.add_argument("command", choices=("round1", "round2", "rung2", "analyze"))
    parser.add_argument("--s1plan", type=Path, required=True)
    parser.add_argument("--runs", type=Path, nargs="*", default=[])
    parser.add_argument("--plans", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    designs = json.loads(args.s1plan.read_text())["designs"]
    records = stages._records(args.runs)
    planned = [c for p in args.plans for c in json.loads(p.read_text())["cases"]]
    if args.command == "round1":
        cases_, reg = round1(designs)
    elif args.command == "round2":
        cases_, reg = round2(designs, records)
    elif args.command == "rung2":
        cases_, reg = rung2(records, planned), None
    else:
        args.out.write_text(
            json.dumps(analyze(records, planned), indent=1, sort_keys=True) + "\n"
        )
        return 0
    args.out.write_text(
        json.dumps(
            {
                "batch": f"motor-feas02-boundary-{args.command}",
                "points": reg,
                "cases": cases_,
            },
            indent=1,
        )
        + "\n"
    )
    print(json.dumps({"cases": len(cases_), "points": reg}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
