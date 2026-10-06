"""python -m carbon.challenge_pipeline {validate,queue,lessons,render,readiness} [--check]

`validate --conditional-ledger STORE` (repeatable) also consults a campaign
controller's attempt ledger, read-only, at every citation check
(conditional-evidence.v2): bytes it recorded on a result while a finding was
open are refused as TESTED or FROZEN evidence or a frozen run.
"""

from __future__ import annotations

import argparse
import sys

from carbon.challenge_pipeline import admission_controllers, render
from carbon.challenge_pipeline.lessons import load_lessons, open_revisions
from carbon.challenge_pipeline.roadmap import rank_all
from carbon.challenge_pipeline.state import load_state, measured_times, stage_of
from carbon.challenge_readiness.conditional_evidence import ConditionalLedger


def _readiness(args):
    import json

    from carbon.challenge_pipeline.readiness import runner

    try:
        only = args.only.split(",") if args.only else None
        report = runner.run_gate(args.challenge, args.level, only=only)
    except runner.ReadinessRefused as refused:
        print(f"readiness refused: {refused}")
        return 2
    runner.append_history(report)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(runner.render_text(report))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline=chr(10)) as out:
            json.dump(report, out, indent=1, sort_keys=True)
            out.write(chr(10))
    return 0 if report["green"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.challenge_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser(
        "validate",
        help="check the protocol, rubric, records, lessons and admission controllers",
    )
    v.add_argument(
        "--conditional-ledger",
        action="append",
        default=[],
        metavar="STORE",
        help="a campaign controller root (or its campaign.sqlite3) to consult",
    )
    sub.add_parser("queue", help="print the priority queue")
    sub.add_parser("lessons", help="print the lessons log, oldest first")
    g = sub.add_parser(
        "readiness",
        help="run the Graphite readiness gate for one challenge "
        "(exit 0 only if every item passes)",
    )
    g.add_argument("--challenge", required=True)
    g.add_argument("--level", type=int, default=0)
    g.add_argument("--json", metavar="OUT", help="also write the digest-bound report")
    g.add_argument(
        "--only", help="comma-separated item ids (a partial run is never green)"
    )
    r = sub.add_parser("render", help="write docs/development/CHALLENGE_PIPELINE.md")
    r.add_argument("--check", action="store_true", help="fail if the view is stale")
    args = parser.parse_args(argv)
    if args.command == "readiness":
        return _readiness(args)
    ledgers = tuple(
        ConditionalLedger.load(path) for path in getattr(args, "conditional_ledger", [])
    )
    families, protocol, _, records = load_state(ledgers=ledgers)
    if args.command == "validate":
        entries = load_lessons(protocol)
        controllers = admission_controllers.load()["controllers"]
        pending = sum(map(admission_controllers.pending, controllers))
        print(
            f"protocol {protocol['state']}; {len(records)} records valid; "
            f"{len(entries)} lessons valid, {len(open_revisions(entries))} awaiting a decision; "
            f"{len(controllers)} admission controllers designated, {pending} pending identity"
        )
    elif args.command == "queue":
        for row in rank_all(families, measured_times(records)):
            f = row["family"]
            print(
                f"{row['rank']:>2} {f['id']} {row['composite']:.2f} "
                f"{stage_of(records, f['id']):<9} {f['name']}"
            )
    elif args.command == "lessons":
        for e in load_lessons(protocol):
            print(
                f"{e['lesson_id']} [{e['status']}] {e['challenge']} "
                f"{e['execution']['kind']}: {e['observed']}"
            )
    elif not render.write(check=args.check):
        print(
            f"{render.DOCUMENT} is stale: run python -m carbon.challenge_pipeline render"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
