"""Assemble one pool's records from the runs that produced them.

    python -m scripts.dev.challenge_pools.assemble PLAN.json --first N \\
        --records RUN_A/records.jsonl RUN_B/records.jsonl ... --out POOL.jsonl

A pool is the first N cases of its plan, in the plan's deterministic draw
order. Its cases may have been solved in several runs: the owner's host in a
container, a rented pod natively, or a restarted batch. For each case this
keeps the first OK record in source order, or else the first typed record of
any outcome.
- Two OK records of one case must agree. Each source's run is recorded on
  its record (`execution`, `image`, `batch`), so disagreeing duplicates are
  refused rather than chosen between.
- **A case with no record is reported missing, and the pool is not silently
  shortened.** The tool fails unless --allow-missing is given.

Each assembled record carries `assembled_from`, the source it came from,
relative to the sources' common directory: a pool is committed, and a host
path never is. The summary prints counts per outcome and per source.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path


def _close(a, b, rel=1e-9, abs_tol=1e-9):
    """Equal outputs, up to analysis round-off, which differs across Python
    versions at about 1e-13."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], rel, abs_tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            _close(x, y, rel, abs_tol) for x, y in zip(a, b)
        )
    if isinstance(a, float | int) and isinstance(b, float | int):
        return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)
    return a == b


def assemble(plan, first, sources):
    """(records in plan order, missing case ids, summary)."""
    wanted = [c["case_id"] for c in plan["cases"][:first]]
    chosen = {}
    base = os.path.commonpath([str(Path(s).resolve().parent) for s in sources])
    for source in sources:
        label = os.path.relpath(Path(source).resolve(), base)
        for line in Path(source).read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            case_id = record["case_id"]
            if case_id not in wanted:
                continue
            record = {**record, "assembled_from": label}
            held = chosen.get(case_id)
            if held is None or (held["status"] != "OK" and record["status"] == "OK"):
                chosen[case_id] = record
            elif (
                held["status"] == "OK"
                and record["status"] == "OK"
                and not _close(held.get("outputs"), record.get("outputs"))
            ):
                raise ValueError(f"{case_id}: OK records disagree between sources")
    records = [chosen[c] for c in wanted if c in chosen]
    missing = [c for c in wanted if c not in chosen]
    by_status, by_source = {}, {}
    for r in records:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_source[r["assembled_from"]] = by_source.get(r["assembled_from"], 0) + 1
    summary = {
        "cases": len(wanted),
        "recorded": len(records),
        "missing": len(missing),
        "outcomes": by_status,
        "sources": by_source,
    }
    return records, missing, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--records", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text())
    records, missing, summary = assemble(plan, args.first, args.records)
    if missing and not args.allow_missing:
        print(json.dumps(summary))
        raise SystemExit(f"{len(missing)} cases have no record: {missing[:10]}")
    with args.out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
