#!/usr/bin/env python3
"""Fail closed unless the jobs required for one classified scope succeeded."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping

from classify_changes import ChangeScope

JOB_NAMES = (
    "preflight",
    "canonical",
    "dev_image",
    "contract_authority",
    "derived_documentation",
    "hub_validation",
)
REQUIRED_JOBS = {
    ChangeScope.RUNTIME_FULL: frozenset(
        {"preflight", "canonical", "dev_image", "hub_validation"}
    ),
    ChangeScope.CONTRACT_AUTHORITY: frozenset(
        {"preflight", "contract_authority", "hub_validation"}
    ),
    ChangeScope.DERIVED_DOCUMENTATION: frozenset(
        {"preflight", "derived_documentation"}
    ),
}


def gate_failures(scope: ChangeScope, statuses: Mapping[str, str]) -> tuple[str, ...]:
    """Return exact job/result mismatches for a scope-specific workflow run."""

    required = REQUIRED_JOBS[scope]
    failures: list[str] = []
    for job in JOB_NAMES:
        observed = statuses.get(job, "")
        expected = "success" if job in required else "skipped"
        if observed != expected:
            failures.append(
                f"{job}: expected {expected}, observed {observed or 'missing'}"
            )
    unknown = sorted(set(statuses) - set(JOB_NAMES))
    failures.extend(f"unknown job result: {job}" for job in unknown)
    return tuple(failures)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True, choices=tuple(ChangeScope))
    for job in JOB_NAMES:
        parser.add_argument(
            f"--{job.replace('_', '-')}",
            required=True,
            choices=("success", "failure", "cancelled", "skipped"),
        )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scope = ChangeScope(args.scope)
    statuses = {job: getattr(args, job) for job in JOB_NAMES}
    failures = gate_failures(scope, statuses)
    if failures:
        print(f"Merge gate rejected {scope.value} results:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"Merge gate accepted every required {scope.value} job.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
