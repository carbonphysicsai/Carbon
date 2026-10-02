"""Summarize a cold plate reference batch: outcomes, checks, costs,
refinement pairs and the closed-form baseline's error.

    python scripts/dev/cold_plate/reference/pilot_report.py BATCH_DIR [--json OUT]

Reads `BATCH_DIR/records.jsonl` only. Every number it prints is computed from
those records; nothing is assumed for a case that is missing.
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

from carbon.cold_plate import analytic, population
from carbon.cold_plate.domain import PG25_VALID_C


def load(batch):
    records = [
        json.loads(line)
        for line in (Path(batch) / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]
    plan = json.loads((Path(batch) / "plan.json").read_text())
    return records, plan


def report(batch):
    records, plan = load(batch)
    by_id = {r["case_id"]: r for r in records}
    planned = [c["case_id"] for c in plan["cases"]]
    counts = {}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    ok = [r for r in records if r["status"] == "OK"]
    out = {
        "batch": plan["batch"],
        "planned": len(planned),
        "recorded": len(records),
        "missing": [i for i in planned if i not in by_id],
        "outcomes": counts,
    }
    if ok:
        checks = {
            name: max(abs(r["checks"][name]) for r in ok)
            for name in (
                "mass_imbalance_rel",
                "energy_balance_rel",
                "iteration_change_k",
                "iteration_change_pressure_rel",
            )
        }
        out["worst_checks"] = checks
        out["fluid_max_c"] = max(r["checks"]["fluid_max_c"] for r in ok)
        out["fluid_ceiling_c"] = PG25_VALID_C[1]
        out["inlet_undershoot_k"] = max(r["checks"]["inlet_undershoot_k"] for r in ok)
        out["re_outlet_max"] = max(r["checks"]["re_outlet"] for r in ok)
        walls = {r["kind"]: r["wall_s"] for r in ok}
        out["wall_s"] = {
            kind: [
                min(r["wall_s"] for r in ok if r["kind"] == kind),
                max(r["wall_s"] for r in ok if r["kind"] == kind),
            ]
            for kind in sorted({r["kind"] for r in ok})
        }
        del walls
        rows = []
        for r in ok:
            if r["kind"] == "refinement":
                continue
            p = analytic.predict(r["inputs"])
            o = r["outputs"]
            screen = population.screen(r["inputs"])[2]
            profile_rms = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(p["profile_c"], o["profile_c"])) / 30
            )
            rows.append(
                {
                    "case_id": r["case_id"],
                    "peak_c": o["peak_c"],
                    "baseline_peak_error_k": p["peak_c"] - o["peak_c"],
                    "baseline_profile_rms_k": profile_rms,
                    "baseline_dp_error_rel": p["pressure_drop_pa"]
                    / o["pressure_drop_pa"]
                    - 1,
                    "screen_wall_c": screen["max_wall_c"],
                    "fluid_max_c": r["checks"]["fluid_max_c"],
                }
            )
        out["baseline"] = rows
        pairs = []
        for r in ok:
            if r["kind"] != "refinement":
                continue
            base = by_id.get(r["case_id"].removesuffix("-r3"))
            if base is None or base["status"] != "OK":
                continue
            a, b = base["outputs"], r["outputs"]
            pairs.append(
                {
                    "case_id": base["case_id"],
                    "peak_change_k": b["peak_c"] - a["peak_c"],
                    "profile_max_change_k": max(
                        abs(x - y) for x, y in zip(a["profile_c"], b["profile_c"])
                    ),
                    "dp_change_rel": b["pressure_drop_pa"] / a["pressure_drop_pa"] - 1,
                    "wall_s": [base["wall_s"], r["wall_s"]],
                }
            )
        out["refinement"] = pairs
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("batch", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    out = report(args.batch)
    text = json.dumps(out, indent=2)
    if args.json:
        args.json.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
