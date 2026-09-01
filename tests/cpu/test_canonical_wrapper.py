"""Dry-run construction contracts for the cross-host canonical wrapper."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPOSITORY_ROOT / "scripts/dev/canonical.sh"


def _is_ubuntu_2404() -> bool:
    try:
        identity = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return False
    return "ID=ubuntu" in identity and 'VERSION_ID="24.04"' in identity


def _dry_run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("CARBON_CANONICAL_DEV_ENV", None)
    return subprocess.run(
        [str(WRAPPER), "--dry-run", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_full_dry_run_uses_pinned_nonroot_linux_amd64_container() -> None:
    process = _dry_run("--full")
    assert process.returncode == 0, process.stderr
    output = process.stdout
    assert "BUILD_IF_MISSING" in output
    assert "RUN" in output
    assert "--platform linux/amd64" in output
    assert "--user 1000:1000" in output
    assert "target=/workspaces/Carbon" in output
    assert "target=/workspaces/Carbon/.venv" in output
    assert "target=/home/ubuntu/.cache/uv" in output
    assert "./scripts/dev/ci.sh" in output
    assert "--no-cache" not in output


def test_linked_worktree_metadata_and_persistent_volumes_are_mounted() -> None:
    process = _dry_run("python3", "-m", "pytest", "tests/cpu/test_registry.py")
    assert process.returncode == 0, process.stderr
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    readable_output = process.stdout.replace("\\ ", " ")
    if (REPOSITORY_ROOT / ".git").is_file():
        assert f"source={common}" in readable_output
        assert f"source={REPOSITORY_ROOT}/.git" in readable_output
    else:
        assert Path(common) == REPOSITORY_ROOT / ".git"
        assert f"source={REPOSITORY_ROOT},target=/workspaces/Carbon" in readable_output
    assert "carbon-canonical-venv-" in process.stdout
    assert "carbon-canonical-uv-cache-v1" in process.stdout
    assert "GIT_CONFIG_KEY_0=safe.directory" in process.stdout


def test_focused_and_interactive_modes_construct_expected_commands() -> None:
    focused = _dry_run("--focused", "tests/cpu/test_registry.py", "-k", "identity")
    assert focused.returncode == 0, focused.stderr
    assert "./scripts/dev/test.sh" in focused.stdout
    assert "test_registry.py" in focused.stdout
    interactive = _dry_run("--interactive")
    assert interactive.returncode == 0, interactive.stderr
    assert "bash -l" in interactive.stdout
    assert "--interactive --tty" in interactive.stdout


def test_wrapper_source_has_exact_direct_identity_and_docker_fail_closed() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    for marker in (
        '"Linux"',
        '"x86_64"',
        '"1000"',
        '"ubuntu"',
        '"24.04"',
        '"uv 0.12.7"',
        '"Python 3.11.16"',
        "Docker is unavailable",
        "Docker is installed but unavailable",
    ):
        assert marker in source


def test_noncanonical_execution_fails_closed_without_docker(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for command in ("bash", "dirname", "git"):
        executable = shutil.which(command)
        assert executable is not None
        (fake_bin / command).symlink_to(executable)
    environment = os.environ.copy()
    environment["PATH"] = str(fake_bin)
    environment.pop("CARBON_CANONICAL_DEV_ENV", None)
    process = subprocess.run(
        [str(WRAPPER), "/usr/bin/true"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 2
    assert "Docker is unavailable" in process.stderr


@pytest.mark.skipif(not _is_ubuntu_2404(), reason="exact direct-mode OS fixture")
def test_exact_identity_executes_directly_without_docker(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    identity = fake_bin / "identity"
    identity.write_text(
        """#!/bin/sh
case "$(basename "$0"):$*" in
  uname:-s) echo Linux ;;
  uname:-m) echo x86_64 ;;
  id:-u) echo 1000 ;;
  id:-g) echo 1000 ;;
  id:-un) echo ubuntu ;;
  uv:*) echo 'uv 0.12.7' ;;
  python3:*) echo 'Python 3.11.16' ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    identity.chmod(0o755)
    for command in ("uname", "id", "uv", "python3"):
        (fake_bin / command).symlink_to(identity)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["CARBON_CANONICAL_DEV_ENV"] = (
        "ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64"
    )
    process = subprocess.run(
        [str(WRAPPER), "--dry-run", "/usr/bin/true"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout == "DIRECT /usr/bin/true\n"
