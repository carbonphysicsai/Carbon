"""The validator installer refuses a machine that fails the published requirements.

Stub commands stand in for docker, curl, nvidia-smi and nproc; nothing is installed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install_validator.sh"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="the installer runs on Linux hosts"
)


def _stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def machine(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub(
        stubs,
        "docker",
        'if [[ "$1" == info ]]; then\n'
        '  [[ "${STUB_DOCKER_DOWN:-0}" == 1 ]] && exit 1\n'
        '  [[ "$*" == *CgroupVersion* ]] && { echo "${STUB_CGROUP:-2}"; exit 0; }\n'
        '  [[ "$*" == *Runtimes* ]] && { echo "${STUB_RUNTIMES:-{\\"runc\\":{}}}"; exit 0; }\n'
        "  exit 0\nfi\nexit 0",
    )
    _stub(stubs, "curl", '[[ "${STUB_CURL_FAIL:-0}" == 1 ]] && exit 6; exit 0')
    _stub(stubs, "nvidia-smi", 'echo "${STUB_DRIVER:-}"')
    state = tmp_path / "state"

    def run(*args, **env):
        merged = {
            **os.environ,
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "CARBON_STATE_DIR": str(state),
            "CARBON_VALIDATOR_MIN_FREE_GIB": "0",
            "CARBON_VALIDATOR_MIN_CPUS": "1",
            "CARBON_VALIDATOR_MIN_RAM_GIB": "0",
            **env,
        }
        return subprocess.run(
            ["bash", str(SCRIPT), "--check-only", *args],
            capture_output=True,
            text=True,
            env=merged,
            check=False,
        )

    return run


def test_script_is_executable_in_the_index():
    listed = subprocess.run(
        ["git", "ls-files", "--stage", "--", "scripts/install_validator.sh"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert listed.split()[0] == "100755"


def test_a_machine_that_meets_the_requirements_passes(machine):
    done = machine()
    assert done.returncode == 0, done.stderr
    assert "meets the requirements" in done.stdout


def test_unreachable_docker_is_refused_with_its_code_and_next_step(machine):
    done = machine(STUB_DOCKER_DOWN="1")
    assert done.returncode == 2
    assert "V_DOCKER" in done.stderr and "Next:" in done.stderr


def test_cgroup_v1_is_refused(machine):
    done = machine(STUB_CGROUP="1")
    assert done.returncode == 2
    assert "V_CGROUP" in done.stderr


def test_unreachable_network_is_refused(machine):
    done = machine(STUB_CURL_FAIL="1")
    assert done.returncode == 2
    assert "V_NETWORK" in done.stderr and "github.com" in done.stderr


def test_too_little_disk_is_refused(machine):
    done = machine(CARBON_VALIDATOR_MIN_FREE_GIB="99999999")
    assert done.returncode == 2
    assert "V_DISK" in done.stderr


def test_gpu_needs_a_recent_driver_and_the_nvidia_runtime(machine):
    old = machine("--gpu", STUB_DRIVER="535.10")
    assert old.returncode == 2
    assert "V_GPU_DRIVER" in old.stderr and "V_GPU_TOOLKIT" in old.stderr
    ready = machine(
        "--gpu", STUB_DRIVER="595.45", STUB_RUNTIMES='{"nvidia":{},"runc":{}}'
    )
    assert ready.returncode == 0, ready.stderr


def test_every_failed_requirement_is_reported_together(machine):
    done = machine(STUB_CGROUP="1", STUB_CURL_FAIL="1")
    assert done.returncode == 2
    assert "V_CGROUP" in done.stderr and "V_NETWORK" in done.stderr
