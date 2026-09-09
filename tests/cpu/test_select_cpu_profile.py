"""A tooling-only delivery must never stand in for runtime acceptance."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[2] / "scripts/dev"
sys.path.insert(0, str(SCRIPT_ROOT))

from classify_changes import ChangeClassificationError
from select_cpu_profile import (
    NETWORK_TESTS,
    TOOLING_TESTS,
    chain_constraint_tightening,
    main,
    select_cpu_profile,
)


def test_known_network_scope_keeps_network_and_tooling_regressions() -> None:
    assert select_cpu_profile(["carbon/chain/sdk.py"]) == "NETWORK_FOUNDATION"
    assert "tests/cpu/test_net1_chain_adapter.py" in NETWORK_TESTS
    assert set(TOOLING_TESTS).issubset(NETWORK_TESTS)
    for path in ("carbon/scoring/engine.py", "carbon/chain/new.py", "uv.lock"):
        assert select_cpu_profile(["carbon/chain/sdk.py", path]) == "RUNTIME_FULL"


def test_pin_only_exception_cannot_change_a_resolved_package_or_manifest() -> None:
    before_project = 'chain = ["bittensor>=9.0.0"]\n' * 2
    after_project = before_project.replace(">=9.0.0", "==11.1.0")
    before_lock = (
        'name = "bittensor"\nversion = "11.1.0"\n' + 'specifier = ">=9.0.0"\n' * 2
    )
    after_lock = before_lock.replace(">=9.0.0", "==11.1.0")
    assert chain_constraint_tightening(
        before_project, after_project, before_lock, after_lock
    )
    for project, lock in (
        (after_project + "other = 1\n", after_lock),
        (after_project, after_lock.replace('version = "11.1.0"', 'version = "11.2.0"')),
        (after_project, after_lock + 'hash = "different"\n'),
    ):
        assert not chain_constraint_tightening(
            before_project, project, before_lock, lock
        )
    assert (
        select_cpu_profile(
            ["carbon/chain/sdk.py", "pyproject.toml", "uv.lock"],
            unchanged_chain_resolution=True,
        )
        == "NETWORK_FOUNDATION"
    )


@pytest.mark.parametrize(
    "path",
    (
        "carbon/generation/service.py",
        "tests/cpu/test_b03_conformance.py",
        "tests/invariants/test_no_leakage.py",
        "tests/conftest.py",
        "tests/cpu/hoh_support.py",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".agent/CODE_AUTHORITY.toml",
        ".devcontainer/Dockerfile",
        "scripts/dev/bootstrap.sh",
        "scripts/dev/canonical.sh",
        "scripts/dev/doctor.sh",
        "scripts/dev/test.sh",
        "scripts/dev/verify_image.sh",
        "scripts/check_quality.py",
        ".github/workflows/new-workflow.yml",
        "scripts/dev/new-runner.py",
        "tests/cpu/test_new_tool.py",
        "unknown.txt",
    ),
)
def test_runtime_or_unmapped_change_keeps_full_acceptance(path: str) -> None:
    assert select_cpu_profile([path]) == "RUNTIME_FULL"
    mixed = ["AGENTS.md", "scripts/dev/ci.sh", path]
    assert select_cpu_profile(mixed) == "RUNTIME_FULL"


@pytest.mark.parametrize(
    "path",
    (
        "AGENTS.md",
        ".agent/DELIVERY_PROTOCOL.md",
        ".github/rulesets/main.v1.json",
        "scripts/dev/check_merge_gate.py",
        "scripts/dev/classify_changes.py",
        "scripts/dev/select_cpu_profile.py",
        ".github/workflows/ci.yml",
        ".github/workflows/gpt-review.yml",
        ".github/workflows/main-smoke.yml",
        "docs/development/carbon_hub/tools/validate_hub.py",
        "docs/development/carbon_hub/tools/test_validator.py",
        *TOOLING_TESTS,
    ),
)
def test_explicit_tooling_paths_use_the_complete_tooling_suite(path: str) -> None:
    assert select_cpu_profile([path]) == "TOOLING_ONLY"


def test_empty_manifest_keeps_full_acceptance() -> None:
    assert select_cpu_profile([]) == "RUNTIME_FULL"


@pytest.mark.parametrize("path", ("../AGENTS.md", "/AGENTS.md", "./AGENTS.md"))
def test_unsafe_paths_do_not_authorize_a_lighter_profile(path: str) -> None:
    with pytest.raises(ChangeClassificationError):
        select_cpu_profile([path])


def test_tooling_suite_is_present_and_unique() -> None:
    repository = SCRIPT_ROOT.parent.parent
    assert len(TOOLING_TESTS) == len(set(TOOLING_TESTS))
    assert all((repository / path).is_file() for path in TOOLING_TESTS)
    assert "tests/cpu/test_canonical_wrapper.py" in TOOLING_TESTS
    assert "tests/cpu/test_hoh_controller.py" in TOOLING_TESTS
    assert "tests/cpu/test_select_cpu_profile.py" in TOOLING_TESTS


def test_ci_preserves_invariants_collection_packages_and_full_fallback() -> None:
    source = (SCRIPT_ROOT / "ci.sh").read_text(encoding="utf-8")
    assert "tests/invariants -m invariant -q" in source
    assert "--collect-only -q" in source
    assert '"${tooling_tests[@]}"' in source
    assert "tests/cpu/test_package_installation.py" in source
    assert "tests/cpu/test_optional_backends.py" in source
    assert "./scripts/dev/test.sh" in source
    assert "Invalid CPU acceptance profile" in source
    assert "|| true" not in source


def test_unresolvable_base_rejects_profile_selection(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "select_cpu_profile.py"),
            "--repository",
            str(tmp_path),
            "--base",
            "missing",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "TOOLING_ONLY" not in result.stdout


def test_missing_tooling_test_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "select_cpu_profile.changed_paths", lambda *_: ("scripts/dev/ci.sh",)
    )
    arguments = ["selector", "--repository", str(tmp_path), "--base", "HEAD"]
    arguments.append("--tooling-tests")
    monkeypatch.setattr(sys, "argv", arguments)
    assert main() == 2
    assert "Required tooling test is missing" in capsys.readouterr().err


def test_runtime_cannot_request_tooling_tests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "select_cpu_profile.changed_paths", lambda *_: ("carbon/generation/service.py",)
    )
    monkeypatch.setattr(sys, "argv", ["selector", "--base", "HEAD", "--tooling-tests"])
    assert main() == 2
    assert "Full runtime acceptance is required" in capsys.readouterr().err
