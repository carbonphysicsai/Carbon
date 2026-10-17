"""ScoreLab entry point: the active benchmark has no historical imports."""

from __future__ import annotations

import argparse
import importlib
import sys


def __getattr__(name):
    """Preserve the existing Python CLI patch points without eager imports."""
    if name in {"candidates", "campaign_feedback", "campaign_goodhart"}:
        return importlib.import_module(f".{name}", __package__)
    raise AttributeError(name)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "benchmark":
        from .benchmark_cli import main as benchmark_main

        return benchmark_main(args[1:])
    if args and args[0] == "legacy":
        from .legacy_cli import main as legacy_main

        return legacy_main(args[1:])
    if args:
        from .legacy_cli import main as legacy_main

        return legacy_main(args)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("benchmark", "legacy"))
    if not args:
        parser.print_help()
        return 0
    parser.parse_args(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
