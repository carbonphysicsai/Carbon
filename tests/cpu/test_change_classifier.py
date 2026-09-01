"""Strict path-classification and aggregate Merge gate tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts/dev"
sys.path.insert(0, str(SCRIPT_ROOT))

from check_merge_gate import JOB_NAMES, REQUIRED_JOBS, gate_failures
from classify_changes import ChangeScope, classify_paths


@pytest.mark.parametrize(
    ("path", "scope"),
    (
        ("carbon/runtime.py", ChangeScope.RUNTIME_FULL),
        ("tests/cpu/test_runtime.py", ChangeScope.RUNTIME_FULL),
        ("scripts/dev/apply_github_ruleset.py", ChangeScope.RUNTIME_FULL),
        (".github/workflows/ci.yml", ChangeScope.RUNTIME_FULL),
        ("pyproject.toml", ChangeScope.RUNTIME_FULL),
        ("requirements-dev.txt", ChangeScope.RUNTIME_FULL),
        (".agent/CODE_AUTHORITY.toml", ChangeScope.RUNTIME_FULL),
        ("docs/development/ENVIRONMENT.md", ChangeScope.RUNTIME_FULL),
        ("Design_Specs/Scoring.md", ChangeScope.CONTRACT_AUTHORITY),
        (".agent/tickets/B-04.md", ChangeScope.CONTRACT_AUTHORITY),
        (".agent/DECISIONS.md", ChangeScope.CONTRACT_AUTHORITY),
        (".agent/evidence/wave_b/b-04.md", ChangeScope.CONTRACT_AUTHORITY),
        ("Business/Business_Canon.md", ChangeScope.CONTRACT_AUTHORITY),
        (".github/rulesets/main.v1.json", ChangeScope.CONTRACT_AUTHORITY),
        (
            "docs/development/carbon_hub/data/hub_data_v2.json",
            ChangeScope.CONTRACT_AUTHORITY,
        ),
        (
            "docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md",
            ChangeScope.CONTRACT_AUTHORITY,
        ),
        (
            "docs/development/carbon_hub/data/hub_index_v2.yaml",
            ChangeScope.DERIVED_DOCUMENTATION,
        ),
        (
            "docs/development/carbon_hub/orientation/START_HERE.md",
            ChangeScope.DERIVED_DOCUMENTATION,
        ),
        (
            "docs/development/carbon_hub/README.md",
            ChangeScope.DERIVED_DOCUMENTATION,
        ),
        (
            "docs/development/carbon_hub/explainers/tickets/b_04.md",
            ChangeScope.DERIVED_DOCUMENTATION,
        ),
        ("docs/development/carbon_hub/index.html", ChangeScope.DERIVED_DOCUMENTATION),
        ("unclassified/new-area/file.txt", ChangeScope.RUNTIME_FULL),
    ),
)
def test_representative_manifests(path: str, scope: ChangeScope) -> None:
    assert classify_paths([path]).scope is scope


def test_runtime_and_contract_paths_dominate_weaker_scopes() -> None:
    derived = "docs/development/carbon_hub/index.html"
    contract = ".agent/tickets/B-05.md"
    runtime = "carbon/runtime.py"
    assert classify_paths([derived, contract]).scope is ChangeScope.CONTRACT_AUTHORITY
    assert (
        classify_paths([derived, contract, runtime]).scope is ChangeScope.RUNTIME_FULL
    )


def test_unknown_and_empty_manifests_fail_closed_to_runtime() -> None:
    unknown = classify_paths(["new-root/readme.txt"])
    assert unknown.scope is ChangeScope.RUNTIME_FULL
    assert unknown.unknown_paths == ("new-root/readme.txt",)
    empty = classify_paths([])
    assert empty.scope is ChangeScope.RUNTIME_FULL
    assert empty.unknown_paths == ("<empty-manifest>",)


@pytest.mark.parametrize(
    "path",
    (
        "docs/development/carbon_hub/explainers/tickets/unexpected.html",
        "docs/development/carbon_hub/explainers/tickets/nested/b_04.md",
        "docs/publications/generated/unowned.md",
    ),
)
def test_derived_allowlist_does_not_cover_unowned_outputs(path: str) -> None:
    classification = classify_paths([path])
    assert classification.scope is ChangeScope.RUNTIME_FULL
    assert classification.unknown_paths == (path,)


@pytest.mark.parametrize("scope", tuple(ChangeScope))
def test_merge_gate_accepts_only_exact_scope_matrix(scope: ChangeScope) -> None:
    statuses = {
        job: "success" if job in REQUIRED_JOBS[scope] else "skipped"
        for job in JOB_NAMES
    }
    assert gate_failures(scope, statuses) == ()
    required = next(iter(REQUIRED_JOBS[scope]))
    statuses[required] = "failure"
    assert gate_failures(scope, statuses)


def test_merge_gate_rejects_unexpected_nonrequired_execution() -> None:
    scope = ChangeScope.CONTRACT_AUTHORITY
    statuses = {
        job: "success" if job in REQUIRED_JOBS[scope] else "skipped"
        for job in JOB_NAMES
    }
    statuses["dev_image"] = "success"
    assert gate_failures(scope, statuses) == (
        "dev_image: expected skipped, observed success",
    )
