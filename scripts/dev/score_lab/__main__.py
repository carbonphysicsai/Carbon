"""ScoreLab entry point: the active benchmark has no historical imports."""

from __future__ import annotations

import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "benchmark":
        from .benchmark_cli import main as benchmark_main

        return benchmark_main(args[1:])
    from .legacy_cli import main as legacy_main

    return legacy_main(args)


def _report(rows):
    """Historical test/caller compatibility; loaded only when requested."""
    from .legacy_cli import _report as legacy_report

    return legacy_report(rows)


if __name__ == "__main__":
    raise SystemExit(main())
