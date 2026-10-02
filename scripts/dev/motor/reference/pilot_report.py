"""Summarize a motor reference batch: outcomes, checks, costs, refinement
pairs, angle resolution and the textbook baseline's error.

    python scripts/dev/motor/reference/pilot_report.py BATCH_DIR [--json OUT]

Reads `BATCH_DIR/records.jsonl` and `plan.json` only; every number is
computed from those records, and nothing is assumed for a missing case.

- **Mesh pairs:** a `-n2880` record (every 1 degree on the 2,880-node mesh)
  against its 1,440-node record at the same angles (every fourth position).
- **Angle resolution:** the 0.125 degree window on the 2,880-node mesh. Its
  even positions are the 0.25 degree samples the Challenge uses; linear
  interpolation between them is compared with the odd positions, and the
  window's ripple with and without them. Its 1 degree positions must equal
  the refined full-period record's, which used the same mesh (a
  determinism check).
- **Baseline:** the textbook model's mean-torque error and the ripple it
  omits, per case.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import pairwise
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import analytic


def load(batch):
    batch = Path(batch)
    records = [
        json.loads(line)
        for line in (batch / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return records, json.loads((batch / "plan.json").read_text())


def _span(values):
    return [min(values), max(values)]


def mesh_pairs(by_id, plan):
    pairs = []
    for case in plan["cases"]:
        if case["kind"] != "refinement":
            continue
        fine, base = by_id.get(case["case_id"]), by_id.get(case["pairs_with"])
        if not (fine and base and fine["status"] == base["status"] == "OK"):
            continue
        f = fine["outputs"]["torque_nm"]
        b = base["outputs"]["torque_nm"][:: len(base["outputs"]["torque_nm"]) // len(f)]
        scale = max(abs(t) for t in f)
        pairs.append(
            {
                "case_id": case["pairs_with"],
                "max_abs_nm": max(abs(x - y) for x, y in zip(f, b)),
                "max_rel_to_peak": max(abs(x - y) for x, y in zip(f, b)) / scale,
                "mean_rel": (
                    (fmean(b) - fmean(f)) / fmean(f) if abs(fmean(f)) > 1e-9 else None
                ),
                "ripple_fine_nm": max(f) - min(f),
                "ripple_base_nm": max(b) - min(b),
            }
        )
    return pairs


def angle_resolution(by_id, plan):
    case = next((c for c in plan["cases"] if c["kind"] == "diagnostic"), None)
    if case is None or by_id.get(case["case_id"], {}).get("status") != "OK":
        return None
    window = by_id[case["case_id"]]["outputs"]["torque_nm"]
    even, odd = window[0::2], window[1::2]
    interpolated = [(a + b) / 2 for a, b in pairwise(even)]
    errors = [abs(x - y) for x, y in zip(interpolated, odd)]
    scale = max(abs(t) for t in window)
    result = {
        "case_id": case["case_id"],
        "positions": len(window),
        "midpoint_max_abs_nm": max(errors),
        "midpoint_max_rel_to_peak": max(errors) / scale,
        "window_pk_pk_full_nm": max(window) - min(window),
        "window_pk_pk_even_nm": max(even) - min(even),
    }
    refined = by_id.get(case["pairs_with"] + "-n2880")
    if refined and refined["status"] == "OK":
        # 1 degree = every 8th window position = every position of the refined
        # 15-step record; the window covers its first four.
        same = window[::8]
        result["determinism_max_abs_nm"] = max(
            abs(x - y) for x, y in zip(same, refined["outputs"]["torque_nm"])
        )
    return result


def baseline(ok):
    rows = []
    for r in ok:
        if r["kind"] in ("refinement", "diagnostic"):
            continue
        curve = r["outputs"]["torque_nm"]
        mean = fmean(curve)
        predicted = fmean(analytic.predict(r["inputs"])["torque_nm"])
        rows.append(
            {
                "case_id": r["case_id"],
                "j_a_mm2": r["inputs"]["current_density_a_mm2"],
                "mean_nm": mean,
                "ripple_pk_pk_nm": max(curve) - min(curve),
                "baseline_mean_nm": predicted,
                "mean_error_nm": predicted - mean,
                "mean_error_rel": (
                    (predicted - mean) / mean if abs(mean) > 1e-6 else None
                ),
                "omitted_ripple_rms_nm": math.sqrt(
                    fmean((t - mean) ** 2 for t in curve)
                ),
            }
        )
    return rows


def report(batch):
    records, plan = load(batch)
    by_id = {r["case_id"]: r for r in records}
    planned = [c["case_id"] for c in plan["cases"]]
    counts = {}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    ok = [r for r in records if r["status"] == "OK"]
    full = [r for r in ok if r["checks"]["periodicity_rel"] is not None]
    out = {
        "batch": plan["batch"],
        "planned": len(planned),
        "recorded": len(records),
        "missing": [i for i in planned if i not in by_id],
        "outcomes": counts,
        "failures": {
            r["case_id"]: r.get("reasons", []) for r in records if r["status"] != "OK"
        },
    }
    if full:
        out["worst_periodicity_rel"] = max(r["checks"]["periodicity_rel"] for r in full)
    out["wall_s"] = {
        kind: _span([r["wall_s"] for r in ok if r["kind"] == kind])
        for kind in sorted({r["kind"] for r in ok})
    }
    out["mean_torque_nm"] = (
        _span([r["derived"]["mean_nm"] for r in full]) if full else None
    )
    out["ripple_pk_pk_nm"] = (
        _span([r["derived"]["ripple_pk_pk_nm"] for r in full]) if full else None
    )
    out["mesh_pairs"] = mesh_pairs(by_id, plan)
    out["angle_resolution"] = angle_resolution(by_id, plan)
    rows = baseline(ok)
    out["baseline"] = rows
    if rows:
        rel = [
            abs(r["mean_error_rel"]) for r in rows if r["mean_error_rel"] is not None
        ]
        out["baseline_summary"] = {
            "mean_error_nm": _span([r["mean_error_nm"] for r in rows]),
            "mean_error_rel_abs_max": max(rel) if rel else None,
            "omitted_ripple_rms_nm": _span([r["omitted_ripple_rms_nm"] for r in rows]),
        }
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
