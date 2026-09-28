#!/usr/bin/env python3
"""Path-scoped requirement for the Julia service suite.

The C-03 isolated service job also runs the Julia service suite
(`scripts/dev/julia_worker_service.sh`), but the classifier's C-03 rule names
no Julia path. A change to the pinned SciML environments, their images or
builders, or the suite itself could therefore reach main without the suite
that exercises it ever running.

This module derives that one extra requirement from the changed paths. It is
kept separate from ``classify_changes.py`` on purpose: that module and its
companion ``development_scope.py`` are digest-pinned by the
OWNER-CW1-DEVELOPMENT-CI-01 block in the CI workflow, and editing either would
silently re-authorise the owner's legacy classifier migration. The decision
here is additive and changes no existing classification.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from classify_changes import ChangeClassificationError, changed_paths, normalize_path

JULIA_SERVICE_SCRIPT = "scripts/dev/julia_worker_service.sh"
JULIA_EXACT = frozenset(
    {
        ".devcontainer/Dockerfile.julia-science",
        ".devcontainer/Dockerfile.julia-worker",
        "carbon/development_session/julia_analysis.py",
        "carbon/development_session/julia_depot.py",
        "carbon/development_session/julia_depot_build.py",
        "carbon/development_session/julia_envelope.py",
        "carbon/development_session/julia_research.py",
        "scripts/dev/build_julia_analysis_image.py",
        "scripts/dev/julia_depot.py",
        "scripts/dev/julia_depot.lock.json",
        "scripts/dev/julia_worker_image.sh",
        JULIA_SERVICE_SCRIPT,
        "scripts/dev/verify_julia_build_parent.py",
    }
)
JULIA_PREFIXES = ("carbon/development_session/julia_environments/",)


def julia_suite_tests() -> frozenset[str]:
    """The service tests the Julia suite actually runs, read from its script,
    so this requirement cannot drift from the suite it guards."""
    script = Path(__file__).resolve().parents[2] / JULIA_SERVICE_SCRIPT
    return frozenset(
        re.findall(r"tests/service/[A-Za-z0-9_]+\.py", script.read_text("utf-8"))
    )


def julia_service_required(paths: list[str] | tuple[str, ...]) -> bool:
    """True when a changed path is an input to the Julia service suite."""
    suite = julia_suite_tests()
    for raw_path in paths:
        path = normalize_path(raw_path)
        if path in JULIA_EXACT or path.startswith(JULIA_PREFIXES) or path in suite:
            return True
    return False


def _write_github_output(path: Path, required: bool) -> None:
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"julia_service_required={str(required).lower()}\n")
    except OSError as error:
        raise ChangeClassificationError(
            f"could not write the Julia requirement to {path}: {error}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = changed_paths(args.repository, args.base)
        required = julia_service_required(paths)
        if args.github_output is not None:
            _write_github_output(args.github_output, required)
    except ChangeClassificationError as error:
        print(f"Julia scope resolution failed: {error}", file=sys.stderr)
        return 2
    print(f"Julia service suite required: {str(required).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
