"""python -m carbon.challenge_pipeline {validate,queue,lessons,render,suite}"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon.challenge_pipeline import render, suite
from carbon.challenge_pipeline.lessons import load_lessons, open_revisions
from carbon.challenge_pipeline.roadmap import rank_all
from carbon.challenge_pipeline.state import load_state, measured_times, stage_of


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.challenge_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check the protocol, rubric, records and lessons")
    sub.add_parser("queue", help="print the priority queue")
    sub.add_parser("lessons", help="print the lessons log, oldest first")
    r = sub.add_parser("render", help="write docs/development/CHALLENGE_PIPELINE.md")
    r.add_argument("--check", action="store_true", help="fail if the view is stale")
    s = sub.add_parser("suite", help="run one challenge's Track A checks (suite v1)")
    s.add_argument("challenge", help="the challenge's contract token, with a suite map")
    s.add_argument("--sandbox", action="store_true", help="include container checks")
    s.add_argument("--out", type=Path, help="write the coverage report here")
    args = parser.parse_args(argv)
    if args.command == "suite":
        report = suite.run(args.challenge, sandbox=args.sandbox)
        if args.out:
            args.out.write_text(json.dumps(report, indent=1) + "\n")
        print(f"construction level {report['construction_level']}")
        for vector in report["vectors"]:
            code = vector["participant_code"]
            note = f"  participant code: {code['status']}" if code else ""
            print(f"{vector['id']} {vector['status']:<17} {vector['name']}{note}")
        return 0
    families, protocol, _, records = load_state()
    if args.command == "validate":
        entries = load_lessons(protocol)
        print(
            f"protocol {protocol['state']}; {len(records)} records valid; "
            f"{len(entries)} lessons valid, {len(open_revisions(entries))} awaiting a decision"
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
