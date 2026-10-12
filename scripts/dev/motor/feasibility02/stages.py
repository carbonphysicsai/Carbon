"""Motor feasibility (#758 at 1ac5acfa): stage plans and the stack analysis.

    python -m scripts.dev.motor.feasibility02.stages s2 --s1 DIR --plan S1PLAN --out PLAN
    python -m scripts.dev.motor.feasibility02.stages analyze --runs DIR... --plan S1PLAN --out JSON
    python -m scripts.dev.motor.feasibility02.stages s3 --runs DIR... --plan S1PLAN --out JSON

Zero-current skew is exact from the J0 curve (slices are pure rotor shifts).
Loaded skew combines, per command (J, gamma), the 2D curves at current angle
gamma - 5 d for the slice offsets d (`topology` docstring), each read at
theta + d, averaged with weight 1/3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.motor.feasibility02 import topology as tp

STEP_DEG = 0.25
PP = 5
S2_COMMANDS = ((10.0, 0.0), (10.0, 15.0))
SPANS = (0.0, 2.0, 4.0)


def _records(dirs):
    out = {}
    for d in dirs:
        path = Path(d) / "records.jsonl"
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    # An OK record is never displaced by a later failed one.
                    if out.get(r["case_id"], {}).get("status") != "OK":
                        out[r["case_id"]] = r
    return out


def _curve(records, case_id):
    r = records.get(case_id)
    if r is None or r.get("status") != "OK":
        return None
    return r["outputs"]["torque_nm"]


def cid(design, j, gamma, stage="s1"):
    return f"{stage}-d{design:02d}-j{j:g}g{gamma:g}"


def skewed_cogging(records, design):
    curve = _curve(records, cid(design, 0, 0))
    if curve is None:
        return None
    out = {}
    for span in SPANS:
        off = round(span / 2 / STEP_DEG)
        stack = tp.stack_curve([tp.slice_curve(curve, o) for o in (-off, 0, off)])
        out[f"{span:g}"] = tp.metrics(stack)["pk_pk_nm"]
    return out


def skewed_loaded(records, design, j, gamma):
    """{span: metrics} for the command, from whichever variants exist."""
    out = {}
    for span in SPANS:
        half = span / 2
        slices = []
        for d in (-half, 0.0, half):
            g = gamma - PP * d
            stage = "s1" if d == 0 else "s2"
            curve = _curve(records, cid(design, j, g, stage))
            if curve is None:
                slices = None
                break
            slices.append(tp.slice_curve(curve, round(d / STEP_DEG)))
        if slices:
            out[f"{span:g}"] = tp.metrics(tp.stack_curve(slices))
    return out


def s2_plan(s1_dir, s1_plan, out):
    records = _records([s1_dir])
    designs = json.loads(Path(s1_plan).read_text())["designs"]
    cases, chosen = [], []
    for i, design in enumerate(designs):
        cog = skewed_cogging(records, i)
        means = [
            records[c]["derived"]["mean_nm"]
            for c in (cid(i, j, g) for j in (8, 10) for g in (0, 15))
            if records.get(c, {}).get("status") == "OK"
        ]
        if cog is None or not means:
            continue
        if min(cog.values()) <= 0.10 and max(means) >= 5.4:
            chosen.append(i)
            for j, gamma in S2_COMMANDS:
                for d in (-2.0, -1.0, 1.0, 2.0):
                    g = gamma - PP * d
                    # Commands share variants (gamma 0 at d -1 is gamma 15
                    # at d +2): one solve serves both.
                    if any(c["case_id"] == cid(i, j, g, "s2") for c in cases):
                        continue
                    cases.append(
                        {
                            "case_id": cid(i, j, g, "s2"),
                            "topology": "10p12s",
                            "design": design,
                            "j_a_mm2": j,
                            "gamma_deg": g,
                        }
                    )
    Path(out).write_text(
        json.dumps(
            {"batch": "motor-feas02-s2", "designs_chosen": chosen, "cases": cases},
            indent=1,
        )
        + "\n"
    )
    return {"designs": chosen, "cases": len(cases)}


def analyze(dirs, s1_plan):
    records = _records(dirs)
    designs = json.loads(Path(s1_plan).read_text())["designs"]
    rows = []
    for i, design in enumerate(designs):
        row = {
            "design": f"d{i:02d}",
            "geometry": design,
            "cogging_pk_pk_nm": skewed_cogging(records, i),
        }
        for j, gamma in ((8.0, 0.0), (8.0, 15.0), (10.0, 0.0), (10.0, 15.0)):
            row[f"j{j:g}g{gamma:g}"] = skewed_loaded(records, i, j, gamma)
        rows.append(row)
    return rows


HOLD = {"mean_min": 6.0, "pk_max": 0.30, "frac_max": 0.05}
PEAK = {"mean_min": 12.0, "pk_max": 0.60, "frac_max": 0.05}
COG_MAX = 0.05
RUNG = {"mean_nm": 0.10, "pk_pk_nm": 0.02}
S3_SPANS = {"d12": (2.0, 4.0)}  # registered s3_plan; every other S3 design at 4 deg


def _stack(records, design, j, gamma, span, prefix, step):
    """Skewed stack metrics from one stage's slice variants (or None)."""
    slices = []
    for d in (-span / 2, 0.0, span / 2):
        curve = _curve(records, cid(design, j, gamma - PP * d, prefix))
        if curve is None:
            return None
        slices.append(tp.slice_curve(curve, round(d / step)))
    return tp.metrics(tp.stack_curve(slices))


def _cog(records, design, span, prefix, step):
    curve = _curve(records, cid(design, 0, 0, prefix))
    if curve is None:
        return None
    off = round(span / 2 / step)
    return tp.metrics(
        tp.stack_curve([tp.slice_curve(curve, o) for o in (-off, 0, off)])
    )["pk_pk_nm"]


def _side(value, limit, upper):
    return value <= limit if upper else value >= limit


def _verdict(pairs):
    """pairs: (standard, rung2, limit, upper). A limit between the rungs is
    UNRESOLVED; otherwise rung 2 decides."""
    for std, r2, limit, upper in pairs:
        if std is None or r2 is None:
            return "REFERENCE_UNRESOLVED"
        if _side(std, limit, upper) != _side(r2, limit, upper):
            return "REFERENCE_UNRESOLVED"
    ok = all(_side(r2, limit, upper) for _, r2, limit, upper in pairs)
    return "RESOLVED_FEASIBLE (2D)" if ok else "RESOLVED_INFEASIBLE"


def s3_analyze(dirs, s1_plan):
    """Registered s3_plan: rung-2 convergence of the frozen precision command
    (J 10, gamma 0) and cogging at the passing span, the holding verdict, and
    the J 15 peak command with skew at standard."""
    records = _records(dirs)
    designs = json.loads(Path(s1_plan).read_text())["designs"]
    present = sorted(
        {int(c.split("-")[1][1:]) for c in records if c.startswith("s3r2-")}
    )
    out = {}
    for i in present:
        name = f"d{i:02d}"
        row = {"geometry": designs[i], "spans": {}}
        for span in S3_SPANS.get(name, (4.0,)):
            std = skewed_loaded(records, i, 10.0, 0.0).get(f"{span:g}")
            r2 = _stack(records, i, 10.0, 0.0, span, "s3r2", STEP_DEG / 2)
            cog_std = (skewed_cogging(records, i) or {}).get(f"{span:g}")
            cog_r2 = _cog(records, i, span, "s3r2", STEP_DEG / 2)
            entry = {
                "standard": std,
                "rung2": r2,
                "cogging_standard_nm": cog_std,
                "cogging_rung2_nm": cog_r2,
            }
            if std and r2:
                entry["rung_change"] = {k: abs(r2[k] - std[k]) for k in RUNG}
                entry["cogging_change_nm"] = (
                    abs(cog_r2 - cog_std)
                    if cog_std is not None and cog_r2 is not None
                    else None
                )
                entry["converged"] = all(
                    entry["rung_change"][k] <= v for k, v in RUNG.items()
                ) and (
                    entry["cogging_change_nm"] is not None
                    and entry["cogging_change_nm"] <= RUNG["pk_pk_nm"]
                )
                frac = lambda m: m["pk_pk_nm"] / abs(m["mean_nm"])
                entry["holding_verdict"] = _verdict([
                    (std["mean_nm"], r2["mean_nm"], HOLD["mean_min"], False),
                    (std["pk_pk_nm"], r2["pk_pk_nm"], HOLD["pk_max"], True),
                    (frac(std), frac(r2), HOLD["frac_max"], True),
                    (cog_std, cog_r2, COG_MAX, True),
                ])  # fmt: skip
                entry["third_rung_needed"] = (
                    entry["holding_verdict"] == "REFERENCE_UNRESOLVED"
                )
            peak = _stack(records, i, 15.0, 0.0, span, "s3pk", STEP_DEG)
            if peak:
                peak["meets_peak_limits"] = (
                    peak["mean_nm"] >= PEAK["mean_min"]
                    and peak["pk_pk_nm"] <= PEAK["pk_max"]
                    and peak["pk_pk_nm"] / abs(peak["mean_nm"]) <= PEAK["frac_max"]
                )
            entry["peak_j15_standard"] = peak
            row["spans"][f"{span:g}"] = entry
        out[name] = row
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="feasibility02.stages")
    parser.add_argument("command", choices=("s2", "analyze", "s3"))
    parser.add_argument("--s1", type=Path)
    parser.add_argument("--runs", type=Path, nargs="*")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "s2":
        print(json.dumps(s2_plan(args.s1, args.plan, args.out)))
    elif args.command == "s3":
        args.out.write_text(
            json.dumps(s3_analyze(args.runs, args.plan), indent=1, sort_keys=True)
            + chr(10)
        )
    else:
        rows = analyze(args.runs, args.plan)
        args.out.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
