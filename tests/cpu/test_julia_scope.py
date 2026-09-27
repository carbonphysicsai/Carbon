"""The Julia service suite runs whenever a change touches what it exercises.

The C-03 job also runs `scripts/dev/julia_worker_service.sh`, but the owner-
pinned classifier's C-03 rule names no Julia path, so a change to the pinned
SciML environments alone would not have run the suite that tests them.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts/dev"
sys.path.insert(0, str(SCRIPT_ROOT))

from classify_changes import classify_paths
from julia_scope import julia_service_required, julia_suite_tests

JULIA_ONLY = (
    "carbon/development_session/julia_environments/pde/Manifest.toml",
    "carbon/development_session/julia_environments/current/Project.toml",
    "carbon/development_session/julia_analysis.py",
    "carbon/development_session/julia_envelope.py",
    "carbon/development_session/julia_research.py",
    ".devcontainer/Dockerfile.julia-worker",
    ".devcontainer/Dockerfile.julia-science",
    "scripts/dev/julia_worker_image.sh",
    "scripts/dev/julia_worker_service.sh",
    "scripts/dev/build_julia_analysis_image.py",
    "scripts/dev/verify_julia_build_parent.py",
)


@pytest.mark.parametrize("path", JULIA_ONLY)
def test_a_julia_only_change_requires_the_suite(path):
    assert julia_service_required([path]) is True
    # The pinned classifier alone did not: this is the gap being closed.
    assert classify_paths([path]).c03_worker_required is False
    assert classify_paths([path]).scope.value == "RUNTIME_FULL"


def test_every_test_the_suite_runs_requires_it():
    script = (SCRIPT_ROOT / "julia_worker_service.sh").read_text()
    suite = set(re.findall(r"tests/service/[A-Za-z0-9_]+\.py", script))
    assert suite == julia_suite_tests()
    # Specimen: the suite does run the authored-Julia service tests.
    assert "tests/service/test_authored_julia_service.py" in suite
    for path in sorted(suite):
        assert julia_service_required([path]) is True, path


@pytest.mark.parametrize(
    "path",
    (
        "tests/service/test_battery_mcp_research.py",
        "carbon/development_session/research_campaign.py",
        "docs/development/CONTROL_CENTER_PROGRAMME.md",
        "carbon/development_session/julia_environments_notes.md",
    ),
)
def test_unrelated_paths_do_not_require_the_suite(path):
    assert julia_service_required([path]) is False


def test_the_owner_pinned_classifier_files_are_untouched():
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text("utf-8")
    for name in ("classify_changes.py", "development_scope.py"):
        digest = hashlib.sha256((SCRIPT_ROOT / name).read_bytes()).hexdigest()
        assert digest in workflow, f"{name} no longer matches its pinned digest"


def test_the_workflow_runs_the_c03_job_for_the_julia_requirement():
    workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text("utf-8")
    assert (
        "julia_service_required: ${{ steps.delivery.outputs.julia_service_required }}"
        in workflow
    )
    assert "needs.preflight.outputs.julia_service_required == 'true'" in workflow
    assert (
        "PREFLIGHT_JULIA: ${{ needs.preflight.outputs.julia_service_required }}"
        in workflow
    )
    assert "scripts/dev/julia_scope.py" in (SCRIPT_ROOT / "ci_preflight.sh").read_text()


def test_cli_emits_an_explicit_requirement(tmp_path):
    out = tmp_path / "output.txt"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "julia_scope.py"),
            "--repository",
            str(REPOSITORY_ROOT),
            "--base",
            "HEAD",
            "--github-output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert re.fullmatch(r"julia_service_required=(true|false)\n", out.read_text())
