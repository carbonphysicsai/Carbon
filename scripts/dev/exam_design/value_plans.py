"""Plan builders for the EV4 pod phases (`value_phases.py`).

    python -m scripts.dev.exam_design.value_plans refs   --shards 2 [--out-dir DIR]
    python -m scripts.dev.exam_design.value_plans panel  --shards 1 [--out-dir DIR]
    python -m scripts.dev.exam_design.value_plans verify --jobs ROOT/optimizer/jobs.json \
        --shards 3 [--out-dir DIR]

A plan is a small committed JSON file. `pod_control dispatch --plan` ships it,
every tracked file it names, and every tree in its ``ship`` list, each
hash-pinned at the dispatch commit. Plans name their jobs (the contract, or a
committed jobs file) instead of copying them, so a plan cannot drift from the
contract it serves. The optimizer's verification jobs are copied into the plan
directory, because the pod can read only committed files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
PLANS = "docs/development/evidence/ev4-2026-10-01/plans"
EVIDENCE = "docs/development/evidence/exam-design-2026-09-24"
#: Public material the panel reads: TRAIN v1, the OCV table, the frozen
#: calibration and the scoring set (inputs only are given to members).
PANEL_DATA = (
    f"{EVIDENCE}/datasets/train-v1.jsonl.gz",
    f"{EVIDENCE}/ocv_table.json",
    f"{EVIDENCE}/prepare.json",
    f"{EVIDENCE}/refs-b/out/battery_refs/records.jsonl",
)
MAX_SHARDS = 3


def _shards(count):
    if not 1 <= count <= MAX_SHARDS:
        raise SystemExit(f"shards must be 1..{MAX_SHARDS}")
    return range(count)


def refs_plans(shards, contract=CONTRACT):
    return {
        f"ev4-refs-shard{i}-of{shards}.json": {
            "phase": "value_refs",
            "contract": contract,
            "shard": i,
            "shards": shards,
            "timeout_s": 1200,
            "ship": ["carbon"],
        }
        for i in _shards(shards)
    }


def panel_plans(shards, contract=CONTRACT):
    return {
        f"ev4-panel-shard{i}-of{shards}.json": {
            "phase": "value_panel",
            "contract": contract,
            "shard": i,
            "shards": shards,
            "ship": ["carbon", *PANEL_DATA],
        }
        for i in _shards(shards)
    }


def verify_plans(shards, jobs_file):
    return {
        f"optimizer-verify-shard{i}-of{shards}.json": {
            "phase": "value_refs",
            "jobs_file": jobs_file,
            "shard": i,
            "shards": shards,
            "timeout_s": 1200,
            "ship": ["carbon"],
        }
        for i in _shards(shards)
    }


def write(plans, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, plan in plans.items():
        (out / name).write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n")
    return sorted(str(out / name) for name in plans)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.dev.exam_design.value_plans"
    )
    parser.add_argument("kind", choices=("refs", "panel", "verify"))
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--out-dir", default=str(REPO / PLANS))
    parser.add_argument("--jobs", help="verify: the optimizer's jobs.json")
    args = parser.parse_args(argv)
    if args.kind == "refs":
        plans = refs_plans(args.shards)
    elif args.kind == "panel":
        plans = panel_plans(args.shards)
    else:
        if not args.jobs:
            raise SystemExit("verify needs --jobs")
        from carbon.battery.value.optimizer import MAX_MODE_D_SOLVES, MAX_MODE_X_SOLVES

        jobs = json.loads(Path(args.jobs).read_text())["jobs"]
        if len(jobs) > MAX_MODE_D_SOLVES + MAX_MODE_X_SOLVES:
            raise SystemExit(
                f"refusing: {len(jobs)} verification jobs over the maximum"
            )
        target = Path(args.out_dir) / "optimizer-jobs.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"jobs": jobs}, indent=1, sort_keys=True) + "\n")
        try:
            relative = target.resolve().relative_to(REPO)
        except ValueError:
            raise SystemExit("the jobs copy must be inside the repository") from None
        plans = verify_plans(args.shards, str(relative))
    print(json.dumps({"plans": write(plans, args.out_dir)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
