"""Motor feasibility (#758 at 1ac5acfa): stage plans and the stack analysis.

    python -m scripts.dev.motor.feasibility02.stages s2 --s1 DIR --plan S1PLAN --out PLAN
    python -m scripts.dev.motor.feasibility02.stages analyze --runs DIR... --plan S1PLAN --out JSON

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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="feasibility02.stages")
    parser.add_argument("command", choices=("s2", "analyze"))
    parser.add_argument("--s1", type=Path)
    parser.add_argument("--runs", type=Path, nargs="*")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "s2":
        print(json.dumps(s2_plan(args.s1, args.plan, args.out)))
    else:
        rows = analyze(args.runs, args.plan)
        args.out.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
