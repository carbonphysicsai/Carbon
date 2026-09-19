"""The Workbench product lane must be required by its own changed inputs.

Before this requirement existed, a Workbench source or packaging change was
classified CONTRACT_AUTHORITY and accepted by a lane that never built or ran the
application, so stale release artifacts could reach main unopposed.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts/dev"
sys.path.insert(0, str(SCRIPT_ROOT))

from workbench_scope import workbench_required  # noqa: E402


@pytest.mark.parametrize(
    "path",
    [
        "Business/Carbon_Fit/workbench/src/scientific_studies.js",
        "Business/Carbon_Fit/workbench/src/team_review.js",
        "Business/Carbon_Fit/workbench/tools/build.py",
        "Business/Carbon_Fit/workbench/tools/package_release.py",
        "Business/Carbon_Fit/workbench/tools/check_release_freshness.py",
        "Business/Carbon_Fit/workbench/Carbon_Opportunity_Workbench.html",
        "Business/Carbon_Fit/workbench/MANIFEST.json",
        "Business/Carbon_Fit/workbench/Carbon_Physics_Goal_Workbench_v0_10.zip",
        "Business/Carbon_Fit/workbench/data/goal_constants.json",
        "Business/Carbon_Fit/workbench/tests/test_sources.py",
        "scripts/dev/workbench_release_checks.sh",
        "scripts/dev/workbench_science_checks.sh",
    ],
)
def test_workbench_inputs_require_the_product_lane(path: str) -> None:
    assert workbench_required([path]) is True


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/development/carbon_hub/data/decisions.json",
        "carbon/execution/worker.py",
        "Business/Business_Canon.md",
        "website/ask-carbon/index.html",
    ],
)
def test_unrelated_changes_do_not_require_the_product_lane(path: str) -> None:
    """A documentation or unrelated runtime PR must not be dragged through it."""
    assert workbench_required([path]) is False


def test_requirement_survives_a_mixed_change() -> None:
    assert (
        workbench_required(
            ["README.md", "Business/Carbon_Fit/workbench/src/workflow.js"]
        )
        is True
    )


def test_empty_change_set_does_not_require_the_lane() -> None:
    assert workbench_required([]) is False


def test_a_non_normalised_path_fails_closed() -> None:
    """The shared path validator rejects rather than rewrites.

    Matching a rewritten path would let an unusual diff entry slip past the
    requirement, so an unexpected shape must raise instead.
    """
    from classify_changes import ChangeClassificationError

    with pytest.raises(ChangeClassificationError):
        workbench_required(["./Business/Carbon_Fit/workbench/src/app.js"])


def test_a_similarly_named_sibling_does_not_match() -> None:
    assert workbench_required(["Business/Carbon_Fit/workbench_notes.md"]) is False


def test_owner_pinned_classifier_files_are_untouched() -> None:
    """The requirement must not edit the OWNER-CW1-DEVELOPMENT-CI-01 artifacts.

    Those two files are digest-pinned inside the CI workflow. Changing either
    would re-authorise the owner's legacy classifier migration as a side effect
    of an unrelated repair, so this requirement lives in its own module.
    """
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )
    for name in ("classify_changes.py", "development_scope.py"):
        digest = hashlib.sha256((SCRIPT_ROOT / name).read_bytes()).hexdigest()
        assert digest in workflow, f"{name} no longer matches its pinned digest"


def test_cli_reports_the_requirement_for_the_repository() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "workbench_scope.py"),
            "--repository",
            str(REPOSITORY_ROOT),
            "--base",
            "HEAD",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Workbench acceptance required:" in result.stdout


def test_cli_writes_the_github_output_key(tmp_path: Path) -> None:
    output = tmp_path / "gh-output.txt"
    output.write_text("", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "workbench_scope.py"),
            "--repository",
            str(REPOSITORY_ROOT),
            "--base",
            "HEAD",
            "--github-output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    written = output.read_text(encoding="utf-8")
    assert written.startswith("workbench_required=")
    assert written.strip().endswith(("true", "false"))


def test_cli_fails_closed_on_an_unusable_base() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "workbench_scope.py"),
            "--repository",
            str(REPOSITORY_ROOT),
            "--base",
            "not-a-real-reference",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
