"""Public acceptance metadata CLI. Status never executes acceptance activities."""

from __future__ import annotations

import argparse
import json
import sys

from .cell import decode_cell, write_cell
from .status import read_public_json, render, scoreboard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser(
        "status", help="read the public matrix and seven completion predicates"
    )
    status.add_argument("--json", action="store_true")
    status.add_argument(
        "--revision", help="exact source revision for optional evidence/capture"
    )
    status.add_argument(
        "--door-capture", help="relative public Launchpad evidence JSON"
    )
    status.add_argument(
        "--completion-evidence",
        help="relative public digest-bound acknowledgment/disposition JSON",
    )
    commands.add_parser(
        "validate", help="validate one prospective public cell supplied on stdin"
    )
    commands.add_parser(
        "write",
        help="validate and exclusively append one stdin cell to the public tree",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            capture = read_public_json(args.door_capture) if args.door_capture else None
            evidence = (
                read_public_json(args.completion_evidence)
                if args.completion_evidence
                else None
            )
            report = scoreboard(
                revision=args.revision,
                door_capture=capture,
                completion_evidence=evidence,
            )
            print(
                json.dumps(report, sort_keys=True, indent=2)
                if args.json
                else render(report)
            )
        else:
            document = decode_cell(sys.stdin.buffer.read(65537))
            if args.command == "write":
                print(
                    json.dumps(
                        {
                            "status": "RECORDED",
                            "reference": write_cell(document),
                            "qualification": False,
                        }
                    )
                )
            else:
                print(
                    json.dumps(
                        {
                            "status": "VALID_PUBLIC_CELL",
                            "cell": document["cell"],
                            "qualification": False,
                        }
                    )
                )
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Never echo rejected input, provider output, an arbitrary path or trace.
        print(
            "Acceptance input refused; check schema, public evidence, provenance and immutable destination.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
