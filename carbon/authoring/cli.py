"""Command line entry point for bounded goal-authoring compilation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .goals import (
    GoalAuthoringError,
    compile_goal_intake,
    load_goal_document,
    write_compiled_proposal,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m carbon.authoring")
    subcommands = parser.add_subparsers(dest="command", required=True)
    compile_parser = subcommands.add_parser(
        "compile-goal", help="compile a supported structured goal into a proposal"
    )
    compile_parser.add_argument("input", type=Path)
    compile_parser.add_argument("output_directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        document = load_goal_document(arguments.input)
        proposal = compile_goal_intake(document)
        disposition = write_compiled_proposal(arguments.output_directory, proposal)
    except GoalAuthoringError as exc:
        print(
            json.dumps(
                {"error": exc.code.value, "path": exc.path},
                separators=(",", ":"),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "content_digest": proposal.content_digest,
                "disposition": disposition.value,
                "status": "DEVELOPMENT_PROPOSAL",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
