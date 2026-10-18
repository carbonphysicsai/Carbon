"""Maintained Graphite commands: historical run-checked and direct-agent."""

from __future__ import annotations

import sys

from . import run_checked


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "direct-agent":
        from .direct_tool_session import cli_main

        return cli_main(argv[1:])
    return run_checked.main(argv)


if __name__ == "__main__":
    sys.exit(main())
