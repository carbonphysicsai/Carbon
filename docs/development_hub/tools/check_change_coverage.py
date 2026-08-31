#!/usr/bin/env python3
"""Require every relevant pull request to classify its Development Hub impact.

The check keeps Carbon's orientation map current without turning the hub into
protocol authority. A pull request must declare one of these in its body:

    HUB_UPDATE_REQUIRED: <map refs and changed hub sources>
    HUB_IMPACT_NONE: <specific reason the map remains accurate>

Wave, ticket, and long-horizon sequencing changes always require a structural
hub update. Other implementation, decision, evidence, specification, and
business changes may use HUB_IMPACT_NONE when they do not change map-visible
purpose, placement, status, dependencies, boundaries, maturity, or links.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HUB_PREFIX = "docs/development_hub/"
DATA_PATH = HUB_PREFIX + "data/hub_data_v2.json"
EVENTS_PATH = HUB_PREFIX + "data/change_events.json"

STRUCTURAL_PATTERNS = (
    ".agent/WAVE.md",
    ".agent/WAVE_",
    ".agent/tickets/",
    "Design_Specs/Agentic_Development_Master_Plan.md",
    "Design_Specs/Build_Out.md",
    "Design_Specs/Build_Out_Constitutional_Overlay.md",
)

RELEVANT_PATTERNS = (
    "AGENTS.md",
    "CONSTITUTION.md",
    "SPEC.md",
    ".agent/DECISIONS.md",
    ".agent/INVARIANTS.md",
    ".agent/DELEGATED_DECISION_PROTOCOL.md",
    ".agent/evidence/",
    ".agent/plans/",
    "agent_pack/",
    "Business/",
    "Design_Specs/",
    "carbon/",
    "docs/context/",
    "docs/publications/",
    "launch/",
    "tests/",
)

UPDATE_RE = re.compile(r"(?m)^\s*HUB_UPDATE_REQUIRED:\s*(\S.*)$")
NONE_RE = re.compile(r"(?m)^\s*HUB_IMPACT_NONE:\s*(\S.*)$")


def changed_files(repo_root: Path, base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(path == pattern or path.startswith(pattern) for pattern in patterns)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument(
        "--pr-body-file",
        type=Path,
        default=None,
        help="Optional file containing the pull-request body; otherwise HUB_PR_BODY is used.",
    )
    args = parser.parse_args()

    files = changed_files(args.repo_root.resolve(), args.base, args.head)
    if not files:
        print("No changed files; Development Hub impact check passed.")
        return

    non_hub = [path for path in files if not path.startswith(HUB_PREFIX)]
    structural = [path for path in non_hub if matches(path, STRUCTURAL_PATTERNS)]
    relevant = [path for path in non_hub if matches(path, RELEVANT_PATTERNS)]

    # A hub-only change does not need a second declaration to explain itself.
    if not structural and not relevant:
        print("No Carbon development records changed; Development Hub impact check passed.")
        return

    if args.pr_body_file:
        body = args.pr_body_file.read_text(encoding="utf-8")
    else:
        body = os.environ.get("HUB_PR_BODY", "")

    updates = UPDATE_RE.findall(body)
    none = NONE_RE.findall(body)
    errors: list[str] = []

    if len(updates) + len(none) != 1:
        errors.append(
            "Pull-request body must contain exactly one completed declaration: "
            "HUB_UPDATE_REQUIRED or HUB_IMPACT_NONE."
        )

    data_changed = DATA_PATH in files
    events_changed = EVENTS_PATH in files

    if structural and not data_changed:
        errors.append(
            "Wave, ticket, or sequencing structure changed without updating " + DATA_PATH
        )
    if updates and not (data_changed or events_changed):
        errors.append(
            "HUB_UPDATE_REQUIRED was declared, but neither the hub data nor change-event source changed."
        )
    if structural and none:
        errors.append(
            "HUB_IMPACT_NONE cannot cover a Wave, ticket, Build Out, or master-plan structure change."
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("Relevant changed files:")
        for path in sorted(set(structural + relevant)):
            print(f"- {path}")
        print(
            "Update the map sources and generated outputs, or explain why all map-visible "
            "purpose, placement, status, dependencies, boundaries, maturity, and links remain accurate."
        )
        sys.exit(1)

    declaration = "HUB_UPDATE_REQUIRED" if updates else "HUB_IMPACT_NONE"
    print(f"Development Hub impact check passed: {declaration}; {len(files)} changed files.")


if __name__ == "__main__":
    main()
