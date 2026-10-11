"""Registered evidence entrypoint: battery v3 (EVIDENCE-ENTRYPOINTS-01).

    python -m scripts.dev.evidence_runs.battery_v3 check  --kind {panel-a,train}
    python -m scripts.dev.evidence_runs.battery_v3 solve  --kind {panel-a,train} --overlay DIR --out DIR [--workers N]
    python -m scripts.dev.evidence_runs.battery_v3 export-train --runs DIR --out FILE.jsonl

- **Plans** (committed, sha256-bound):
  - `panel-a`: the #965 middle-band stage-A plan, 284 new standard solves from
    accepted manifest bab5ae97 (reuse 16/12/6);
  - `train`: the v3 public TRAIN plan, 4,000 seeded solves, disjoint from the
    panel and every solved record.
- **Solver:** the pinned truth image (PyBaMM 26.8.0.0 overlay on
  `carbon-determinism-study@sha256:2d19b261...`), through
  `scripts.dev.battery.feasibility02 run`, no network, read-only root.
- **Output:** `<out>/records.jsonl`, one `carbon.battery.feasibility02-record.v1`
  per job: all 30 cycles' per-phase extrema, the every-charge plating minimum,
  programme voltage, Q30/Q1 and the charge-integral SOC clock.
- **export-train:** `carbon.battery-v3.train-record.v1` JSONL for the battery v3
  kit (#1034), inputs {c1, c2, switch_v, cooling, ambient_c, soc0} and outputs
  {charging_t_max_c, minutes, plating_min_v, q30_over_q1, v_max_v} from the
  panel's own measures; a record without a reached SOC clock keeps a null
  `minutes` (the kit excludes and counts it). Prints the file's sha256.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts.dev.evidence_runs import common

IMAGE_REF = "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
IMAGE_DIGEST = "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
PLANS = {
    "panel-a": ("docs/development/evidence/battery-feasibility-02/plans/middle-bands-stage-a-plan.json",
                "779076c69a1a22d04d73c1a7c08d9fadddea9c69453ae5daf69fa1e33f275c3c"),
    "train": ("docs/development/evidence/battery-feasibility-02/plans/v3-train-plan.json",
              "b42b41f149e317832c5b41d0c533b046ad16962f47416c553c63be8b7bcf60df"),
}  # fmt: skip
TRAIN_SCHEMA = "carbon.battery-v3.train-record.v1"


def check(kind, inspect=None):
    path, sha = PLANS[kind]
    plan = common.require_plan(path, sha)
    common.require_image(IMAGE_REF, IMAGE_DIGEST, inspect)
    return plan


def solve(kind, overlay, out, workers):
    plan = check(kind)
    cmd = [sys.executable, "-m", "scripts.dev.battery.feasibility02", "run", str(plan), "--overlay", str(overlay),
           "--out", str(out), "--workers", str(workers), "--cpus", str(workers)]  # fmt: skip
    return subprocess.run(cmd, cwd=common.ROOT, check=False).returncode


def train_record(record):
    """One kit TRAIN record from a feasibility02 record (None if not OK)."""
    sys.path.insert(0, str(common.ROOT / "scripts/dev/battery"))
    import feasibility02_v2 as v2

    if record.get("status") != "OK":
        return None
    m = v2.measures(record)
    return {
        "schema": TRAIN_SCHEMA,
        "case_id": record["case_id"],
        "inputs": {"c1": record["c1"], "c2": record["c2"], "switch_v": record["switch_voltage_v"],
                   "cooling": int(record["h_multiplier"]), "ambient_c": record["t_amb_c"], "soc0": record["soc0"]},
        "outputs": {k: m[k] for k in ("charging_t_max_c", "minutes", "plating_min_v", "q30_over_q1", "v_max_v")},
    }  # fmt: skip


def export_train(runs, out):
    records = common.read_jsonl(Path(runs) / "records.jsonl")
    rows = [r for r in map(train_record, records) if r is not None]
    sha = common.write_jsonl(out, rows)
    return {"records": len(records), "exported": len(rows), "not_ok": len(records) - len(rows),
            "null_minutes": sum(r["outputs"]["minutes"] is None for r in rows), "sha256": sha}  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="evidence_runs.battery_v3", description=__doc__.split("\n")[0]
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--kind", choices=sorted(PLANS), required=True)
    s = sub.add_parser("solve")
    s.add_argument("--kind", choices=sorted(PLANS), required=True)
    s.add_argument("--overlay", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--workers", type=int, default=4)
    e = sub.add_parser("export-train")
    e.add_argument("--runs", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "check":
            print(
                json.dumps(
                    {
                        "plan": str(check(args.kind)),
                        "image": IMAGE_DIGEST,
                        "status": "OK",
                    }
                )
            )
            return 0
        if args.cmd == "solve":
            return solve(args.kind, args.overlay, args.out, args.workers)
        print(json.dumps(export_train(args.runs, args.out)))
        return 0
    except common.Refused as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
