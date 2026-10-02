"""python -m carbon.challenge_pipeline {validate,queue,render} [--check]"""

from __future__ import annotations

import argparse
import sys

from carbon.challenge_pipeline import render
from carbon.challenge_pipeline.roadmap import rank_all
from carbon.challenge_pipeline.state import load_state, measured_times, stage_of


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.challenge_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check the protocol, rubric and records")
    sub.add_parser("queue", help="print the priority queue")
    r = sub.add_parser("render", help="write docs/development/CHALLENGE_PIPELINE.md")
    r.add_argument("--check", action="store_true", help="fail if the view is stale")
    args = parser.parse_args(argv)
    families, protocol, _, records = load_state()
    if args.command == "validate":
        print(f"protocol {protocol['state']}; {len(records)} records valid")
    elif args.command == "queue":
        for row in rank_all(families, measured_times(records)):
            f = row["family"]
            print(
                f"{row['rank']:>2} {f['id']} {row['composite']:.2f} "
                f"{stage_of(records, f['id']):<9} {f['name']}"
            )
    elif not render.write(check=args.check):
        print(
            f"{render.DOCUMENT} is stale: run python -m carbon.challenge_pipeline render"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
