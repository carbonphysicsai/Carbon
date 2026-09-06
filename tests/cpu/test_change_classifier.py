"""Strict path-classification and aggregate Merge gate tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts/dev"
sys.path.insert(0, str(SCRIPT_ROOT))

from check_merge_gate import JOB_NAMES, REQUIRED_JOBS, gate_failures
from classify_changes import ChangeScope, changed_paths, classify_paths


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


def _init_repository(repository: Path) -> str:
    repository.mkdir()
    for arguments in (
        ("init", "--quiet"),
        ("config", "user.name", "Carbon Test"),
        ("config", "user.email", "carbon-test@example.invalid"),
        ("config", "commit.gpgsign", "false"),
    ):
        process = _git(repository, *arguments)
        assert process.returncode == 0, process.stderr
    runtime = repository / "carbon/runtime.py"
    runtime.parent.mkdir()
    runtime.write_text("VALUE = 1\n", encoding="utf-8")
    assert _git(repository, "add", "--all").returncode == 0
    commit = _git(repository, "commit", "--quiet", "-m", "base")
    assert commit.returncode == 0, commit.stderr
    return _git(repository, "rev-parse", "HEAD").stdout.strip()


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
        ("docs/DEVELOPMENT.md", ChangeScope.RUNTIME_FULL),
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
    classification = classify_paths([path])
    assert classification.scope is scope
    if path != "unclassified/new-area/file.txt":
        assert classification.unknown_paths == ()


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


def test_staged_and_committed_cross_scope_rename_keeps_runtime_source(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    base = _init_repository(repository)
    destination = repository / ".agent/tickets/moved-runtime.py"
    destination.parent.mkdir(parents=True)
    moved = _git(
        repository, "mv", "carbon/runtime.py", ".agent/tickets/moved-runtime.py"
    )
    assert moved.returncode == 0, moved.stderr

    staged = changed_paths(repository, base)
    assert staged == (".agent/tickets/moved-runtime.py", "carbon/runtime.py")
    assert classify_paths(staged).scope is ChangeScope.RUNTIME_FULL

    commit = _git(repository, "commit", "--quiet", "-m", "move runtime authority")
    assert commit.returncode == 0, commit.stderr
    committed = changed_paths(repository, base)
    assert committed == (".agent/tickets/moved-runtime.py", "carbon/runtime.py")
    assert classify_paths(committed).scope is ChangeScope.RUNTIME_FULL


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


@pytest.mark.parametrize(
    ("path", "required"),
    [
        ("carbon/measurement/models.py", False),
        ("tests/cpu/test_measurement.py", False),
        ("AGENTS.md", False),
        (".devcontainer/Dockerfile", True),
        (".github/workflows/ci.yml", True),
        ("scripts/dev/canonical.sh", True),
        ("uv.lock", True),
        ("pyproject.toml", True),
        ("requirements-dev.txt", True),
        ("unclassified-file", True),
    ],
)
def test_clean_image_follows_execution_environment(path: str, required: bool) -> None:
    assert classify_paths([path]).dev_image_required is required


def test_empty_manifest_retains_full_image_acceptance() -> None:
    assert classify_paths([]).dev_image_required is True


def test_runtime_source_still_requires_real_canonical_and_hub_success() -> None:
    statuses = {name: "skipped" for name in JOB_NAMES}
    for name in ("preflight", "canonical", "hub_validation"):
        statuses[name] = "success"
    assert not gate_failures(
        ChangeScope.RUNTIME_FULL, statuses, dev_image_required=False
    )
    for name in ("preflight", "canonical", "hub_validation"):
        for bad in ("skipped", "failure", "cancelled", ""):
            broken = dict(statuses, **{name: bad})
            assert gate_failures(
                ChangeScope.RUNTIME_FULL, broken, dev_image_required=False
            )
    assert gate_failures(ChangeScope.RUNTIME_FULL, statuses, dev_image_required=True)
    with pytest.raises(ValueError, match="bool"):
        gate_failures(ChangeScope.RUNTIME_FULL, statuses, dev_image_required="false")
