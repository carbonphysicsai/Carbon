#!/usr/bin/env python3
"""Select bounded tooling acceptance; runtime and unknown inputs keep full CPU CI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from classify_changes import (
    ChangeClassificationError,
    ChangeScope,
    changed_paths,
    classify_paths,
)

# This list owns only development-tooling regression files. A new file is not
# implicitly exempt from runtime acceptance merely because it has a similar name.
TOOLING_TESTS = (
    "tests/cpu/test_canonical_wrapper.py",
    "tests/cpu/test_change_classifier.py",
    "tests/cpu/test_code_authority.py",
    "tests/cpu/test_delivery_hygiene.py",
    "tests/cpu/test_github_ruleset.py",
    "tests/cpu/test_gpt_review_gate.py",
    "tests/cpu/test_hoh_adapters.py",
    "tests/cpu/test_hoh_controller.py",
    "tests/cpu/test_hoh_models.py",
    "tests/cpu/test_select_cpu_profile.py",
)
_TOOLING_PATHS = frozenset(TOOLING_TESTS) | frozenset(
    {
        ".github/workflows/ci.yml",
        ".github/workflows/development-hub.yml",
        ".github/workflows/gpt-review.yml",
        ".github/workflows/main-smoke.yml",
        "scripts/dev/apply_github_ruleset.py",
        "scripts/dev/check_delivery_hygiene.py",
        "scripts/dev/check_diff_hygiene.py",
        "scripts/dev/check_gpt_review_gate.py",
        "scripts/dev/check_merge_gate.py",
        "scripts/dev/ci.sh",
        "scripts/dev/ci_contract_authority.sh",
        "scripts/dev/ci_derived_documentation.sh",
        "scripts/dev/ci_hub.sh",
        "scripts/dev/ci_preflight.sh",
        "scripts/dev/classify_changes.py",
        "scripts/dev/select_cpu_profile.py",
        "docs/development/carbon_hub/tools/validate_hub.py",
        "docs/development/carbon_hub/tools/test_validator.py",
    }
)


def select_cpu_profile(paths: tuple[str, ...] | list[str]) -> str:
    """Allow only known tooling plus already lighter authority/document paths.

    Runtime code, scientific tests, dependency manifests, shared test fixtures,
    environment/bootstrap changes, and unclassified paths retain full CPU CI.
    No caller-supplied flag can label one of those paths as tooling-only.
    """
    classification = classify_paths(paths)
    if classification.unknown_paths:
        return "RUNTIME_FULL"
    for item in classification.paths:
        if item.scope is ChangeScope.RUNTIME_FULL and item.path not in _TOOLING_PATHS:
            return "RUNTIME_FULL"
    return "TOOLING_ONLY"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--tooling-tests", action="store_true")
    args = parser.parse_args()
    try:
        profile = select_cpu_profile(changed_paths(args.repository, args.base))
    except (ChangeClassificationError, OSError) as error:
        print(f"CPU profile selection failed: {error}", file=sys.stderr)
        return 2
    if args.tooling_tests:
        if profile != "TOOLING_ONLY":
            print("Full runtime acceptance is required.", file=sys.stderr)
            return 2
        for path in TOOLING_TESTS:
            if not (args.repository / path).is_file():
                print(f"Required tooling test is missing: {path}", file=sys.stderr)
                return 2
        print("\n".join(TOOLING_TESTS))
    else:
        print(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
