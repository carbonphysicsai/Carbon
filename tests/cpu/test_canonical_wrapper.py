"""Dry-run construction contracts for the cross-host canonical wrapper."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPOSITORY_ROOT / "scripts/dev/canonical.sh"
BOOTSTRAP = REPOSITORY_ROOT / "scripts/dev/bootstrap.sh"
DOCKERFILE = REPOSITORY_ROOT / ".devcontainer/Dockerfile"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        process = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return process.returncode == 0


DOCKER_AVAILABLE = _docker_available()
REQUIRE_DOCKER_TESTS = os.environ.get("CARBON_REQUIRE_DOCKER_TESTS") == "1"
SKIP_DOCKER_TESTS = not DOCKER_AVAILABLE and not REQUIRE_DOCKER_TESTS


def _readable_dry_run(output: str) -> str:
    return output.replace("\\,", ",").replace("\\ ", " ")


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
    output = _readable_dry_run(process.stdout)
    assert output.startswith("BUILD ")
    assert "BUILD_IF_MISSING" not in output
    assert "RUN_AFTER_BUILD_BY_IMMUTABLE_ID" in output
    assert "--platform linux/amd64" in output
    assert "--user 1000:1000" in output
    assert "target=/carbon-source,readonly" in output
    assert "target=/workspaces/Carbon/.git,readonly" in output
    assert "target=/workspaces/Carbon/.venv" not in output
    assert "target=/home/ubuntu/.cache/uv" in output
    assert "GIT_OPTIONAL_LOCKS=0" in output
    assert "bootstrap.sh" in output
    assert "doctor.sh" in output
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
    readable_output = _readable_dry_run(process.stdout)
    assert f"source={REPOSITORY_ROOT},target=/carbon-source,readonly" in readable_output
    assert (
        f"source={REPOSITORY_ROOT}/.git,target=/workspaces/Carbon/.git,readonly"
        in readable_output
    )
    if (REPOSITORY_ROOT / ".git").is_file():
        assert f"source={common},target={common},readonly" in readable_output
    else:
        assert Path(common) == REPOSITORY_ROOT / ".git"
    assert "carbon-canonical-venv-" not in process.stdout
    assert "carbon-canonical-uv-cache-v1" in process.stdout
    assert "GIT_CONFIG_KEY_0=safe.directory" in process.stdout


def test_focused_and_interactive_modes_construct_expected_commands() -> None:
    focused = _dry_run("--focused", "tests/cpu/test_registry.py", "-k", "identity")
    assert focused.returncode == 0, focused.stderr
    assert "./scripts/dev/test.sh" in focused.stdout
    assert "test_registry.py" in focused.stdout
    interactive = _dry_run("--interactive")
    assert interactive.returncode == 0, interactive.stderr
    assert "/usr/bin/bash --noprofile --norc -i" in interactive.stdout
    assert "--interactive --tty" in interactive.stdout
    readable_interactive = _readable_dry_run(interactive.stdout)
    assert f"source={REPOSITORY_ROOT},target=/workspaces/Carbon" in readable_interactive
    assert "target=/carbon-source" not in readable_interactive
    assert "target=/workspaces/Carbon/.venv" in readable_interactive
    assert "carbon-canonical-venv-" in readable_interactive


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
        "-f /.dockerenv",
        "/etc/carbon-canonical-environment",
        "/usr/local/bin/uv",
        "/usr/local/bin/python3",
        "is_trusted_root_executable",
        "CARBON_CANONICAL_VALIDATION_COPY",
        "refuses writable shared Git metadata",
        "image_id=",
        "RUN_AFTER_BUILD_BY_IMMUTABLE_ID",
        "target=/carbon-source,readonly",
        "Docker is unavailable",
        "Docker is installed but unavailable",
    ):
        assert marker in source
    trusted_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    assert source.count(f'export PATH="{trusted_path}"') == 2
    assert (
        source.count(f'export PATH="/workspaces/Carbon/.venv/bin:{trusted_path}"') == 2
    )
    assert 'export PATH="/workspaces/Carbon/.venv/bin:${PATH}"' not in source


def test_image_keeps_direct_identity_marker_and_runtime_root_owned() -> None:
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert "> /etc/carbon-canonical-environment" in source
    assert "chown root:root /etc/carbon-canonical-environment" in source
    assert "chmod 0444 /etc/carbon-canonical-environment" in source
    chown_line = next(line for line in source.splitlines() if "chown -R" in line)
    assert "/opt/uv-python" not in chown_line

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'python_path="/usr/local/bin/python3"' in bootstrap
    assert 'is_trusted_root_executable "${python_path}"' in bootstrap
    assert '"cpython|${python_version}"' in bootstrap
    assert (
        "claims a Carbon canonical identity without its root-owned marker" in bootstrap
    )


@pytest.mark.parametrize("interpreter_present", (True, False))
def test_bootstrap_installs_only_when_exact_interpreter_is_absent(
    tmp_path: Path, interpreter_present: bool
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "uv-calls.txt"
    installed_marker = tmp_path / "installed"
    interpreter = tmp_path / "python3.11"
    interpreter.write_text(
        """#!/bin/sh
if [ "$1" = "-I" ] && [ "$2" = "-c" ]; then
  printf '%s\\n' 'cpython|3.11.16'
  exit 0
fi
exit 97
""",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)

    uname = fake_bin / "uname"
    uname.write_text(
        """#!/bin/sh
[ "$1" = "-s" ] || exit 97
printf '%s\\n' Linux
""",
        encoding="utf-8",
    )
    uname.chmod(0o755)

    uv = fake_bin / "uv"
    uv.write_text(
        """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$CARBON_BOOTSTRAP_TEST_LOG"
case "$1" in
  --version)
    printf '%s\\n' 'uv 0.12.7'
    ;;
  python)
    case "$2" in
      find)
        if [ "$CARBON_BOOTSTRAP_INTERPRETER_PRESENT" = "1" ] || [ -f "$CARBON_BOOTSTRAP_INSTALLED_MARKER" ]; then
          printf '%s\\n' "$CARBON_BOOTSTRAP_INTERPRETER"
        else
          exit 1
        fi
        ;;
      install)
        : > "$CARBON_BOOTSTRAP_INSTALLED_MARKER"
        ;;
      *) exit 97 ;;
    esac
    ;;
  sync) ;;
  *) exit 97 ;;
esac
""",
        encoding="utf-8",
    )
    uv.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment.pop("CARBON_CANONICAL_DEV_ENV", None)
    environment.pop("OS", None)
    environment["CARBON_BOOTSTRAP_TEST_LOG"] = str(call_log)
    environment["CARBON_BOOTSTRAP_INSTALLED_MARKER"] = str(installed_marker)
    environment["CARBON_BOOTSTRAP_INTERPRETER"] = str(interpreter)
    environment["CARBON_BOOTSTRAP_INTERPRETER_PRESENT"] = (
        "1" if interpreter_present else "0"
    )
    process = subprocess.run(
        [str(BOOTSTRAP)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert calls[0] == "--version"
    assert calls.count("python find --no-project --no-python-downloads 3.11.16") == (
        1 if interpreter_present else 2
    )
    assert calls.count("python install 3.11.16") == (0 if interpreter_present else 1)
    assert calls[-1] == (f"sync --python {interpreter} --locked --group dev")


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


@pytest.mark.skipif(
    Path("/etc/carbon-canonical-environment").exists(),
    reason="the test requires a host outside the exact Carbon image",
)
def test_environment_and_path_spoof_cannot_enable_direct_mode(tmp_path: Path) -> None:
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
    assert process.stdout.startswith("BUILD ")
    assert "DIRECT_AFTER_BOOTSTRAP_DOCTOR" not in process.stdout


@pytest.mark.skipif(SKIP_DOCKER_TESTS, reason="Docker daemon is unavailable")
@pytest.mark.skipif(
    not (REPOSITORY_ROOT / ".git").is_dir(),
    reason="normal-checkout integration runs when .git is a directory",
)
def test_docker_backed_normal_checkout_isolated_from_host() -> None:
    assert DOCKER_AVAILABLE, "CI requires the Docker-backed wrapper tests to run"
    isolated_ref = f"refs/heads/carbon-wrapper-normal-{uuid.uuid4().hex}"
    before = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    command = r"""
set -euo pipefail
[[ -d .git ]]
[[ "$(git rev-parse --is-inside-work-tree)" == "true" ]]
[[ "$(id -u):$(id -g)" == "1000:1000" ]]
[[ "${PATH}" == "/workspaces/Carbon/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" ]]
if grep -Fq " /workspaces/Carbon/.venv " /proc/self/mountinfo; then
  echo "noninteractive validation reused a mounted venv" >&2
  exit 92
fi
touch container-only-normal-checkout.txt
git status --porcelain=v1 --untracked-files=all | grep -q container-only-normal-checkout.txt
if git update-ref "$1" HEAD 2>/dev/null; then
  echo "read-only normal-checkout Git metadata accepted a ref write" >&2
  exit 91
fi
"""
    environment = os.environ.copy()
    environment.pop("CARBON_CANONICAL_DEV_ENV", None)
    process = subprocess.run(
        [
            str(WRAPPER),
            "/usr/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            command,
            "carbon-wrapper-normal-integration",
            isolated_ref,
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert not (REPOSITORY_ROOT / "container-only-normal-checkout.txt").exists()
    after = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert after == before
    ref_check = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", isolated_ref],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    assert ref_check.returncode == 1


@pytest.mark.skipif(SKIP_DOCKER_TESTS, reason="Docker daemon is unavailable")
def test_docker_backed_linked_worktree_isolated_copy_and_direct_identity(
    tmp_path: Path,
) -> None:
    assert DOCKER_AVAILABLE, "CI requires the Docker-backed wrapper tests to run"
    linked = tmp_path / "linked-carbon"
    added = subprocess.run(
        ["git", "worktree", "add", "--detach", str(linked), "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert added.returncode == 0, added.stderr
    isolated_ref = f"refs/heads/carbon-wrapper-isolation-{uuid.uuid4().hex}"
    try:
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=linked,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        command = r"""
set -euo pipefail
[[ -f .git ]] || { echo "linked-worktree .git mount is not a regular file" >&2; exit 93; }
[[ "$(git rev-parse --is-inside-work-tree)" == "true" ]] || { echo "linked-worktree Git metadata did not resolve" >&2; exit 94; }
[[ "$(id -u):$(id -g)" == "1000:1000" ]] || { echo "canonical UID/GID changed" >&2; exit 95; }
[[ "${PATH}" == "/workspaces/Carbon/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" ]] || { printf 'unexpected canonical PATH: %s\n' "${PATH}" >&2; exit 96; }
if grep -Fq " /workspaces/Carbon/.venv " /proc/self/mountinfo; then
  echo "noninteractive validation reused a mounted venv" >&2
  exit 92
fi
[[ "$(stat -c '%u:%g:%a' /etc/carbon-canonical-environment)" == "0:0:444" ]] || { echo "canonical marker ownership or mode changed" >&2; exit 97; }
[[ "$(stat -Lc '%u:%g' /usr/local/bin/python3)" == "0:0" ]] || { echo "canonical Python is not root-owned" >&2; exit 98; }
[[ "$(stat -Lc '%u:%g' /usr/local/bin/uv)" == "0:0" ]] || { echo "canonical uv is not root-owned" >&2; exit 99; }
if ! direct="$(./scripts/dev/canonical.sh --dry-run /usr/bin/true)"; then
  echo "nested canonical direct-mode probe failed" >&2
  exit 100
fi
[[ "${direct}" == "DIRECT_AFTER_BOOTSTRAP_DOCTOR /usr/bin/true" ]] || { printf 'unexpected nested canonical dry-run: %q\n' "${direct}" >&2; exit 101; }
touch container-only-untracked.txt
if ! untracked_status="$(git status --porcelain=v1 --untracked-files=all -- container-only-untracked.txt)"; then
  echo "linked-worktree Git status failed" >&2
  exit 102
fi
[[ "${untracked_status}" == "?? container-only-untracked.txt" ]] || { printf 'unexpected isolated Git status: %q\n' "${untracked_status}" >&2; exit 103; }
if git update-ref "$1" HEAD 2>/dev/null; then
  echo "read-only shared Git metadata accepted a ref write" >&2
  exit 91
fi
"""
        environment = os.environ.copy()
        environment.pop("CARBON_CANONICAL_DEV_ENV", None)
        process = subprocess.run(
            [
                str(linked / "scripts/dev/canonical.sh"),
                "/usr/bin/bash",
                "--noprofile",
                "--norc",
                "-c",
                command,
                "carbon-wrapper-integration",
                isolated_ref,
            ],
            cwd=linked,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert process.returncode == 0, process.stdout + process.stderr
        assert not (linked / "container-only-untracked.txt").exists()
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=linked,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert after == before
        ref_check = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", isolated_ref],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        assert ref_check.returncode == 1
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(linked)],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
