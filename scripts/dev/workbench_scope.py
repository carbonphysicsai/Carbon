#!/usr/bin/env python3
"""Path-scoped requirement for the Workbench product acceptance lane.

The change classifier files every Workbench path under CONTRACT_AUTHORITY,
whose lane covers constitutional invariants and repository authority but never
builds or runs the application. A real source, generator or packaging change
can therefore reach main having executed none of the tests that cover it.

This module derives one extra requirement from the changed paths. It is kept
separate from ``classify_changes.py`` on purpose: that module and its companion
``development_scope.py`` are digest-pinned by the OWNER-CW1-DEVELOPMENT-CI-01
block in the CI workflow, and editing either would silently re-authorise the
owner's legacy classifier migration. The scope decision here is additive and
does not change any existing classification.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from classify_changes import ChangeClassificationError, changed_paths, normalize_path

# Everything the Workbench release is generated from, plus the scripts that
# run its acceptance.
WORKBENCH_PREFIXES = ("Business/Carbon_Fit/workbench/",)
WORKBENCH_EXACT = frozenset(
    {
        "scripts/dev/workbench_release_checks.sh",
        "scripts/dev/workbench_science_checks.sh",
    }
)


def workbench_required(paths: list[str] | tuple[str, ...]) -> bool:
    """True when a changed path is an input to the Workbench release."""
    for raw_path in paths:
        path = normalize_path(raw_path)
        if path in WORKBENCH_EXACT or path.startswith(WORKBENCH_PREFIXES):
            return True
    return False


def _write_github_output(path: Path, required: bool) -> None:
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"workbench_required={str(required).lower()}\n")
    except OSError as error:
        raise ChangeClassificationError(
            f"could not write the Workbench requirement to {path}: {error}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = changed_paths(args.repository, args.base)
        required = workbench_required(paths)
        if args.github_output is not None:
            _write_github_output(args.github_output, required)
    except ChangeClassificationError as error:
        print(f"Workbench scope resolution failed: {error}", file=sys.stderr)
        return 2
    print(f"Workbench acceptance required: {str(required).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
