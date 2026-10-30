"""The one supported launch setup and the warning every other machine gets
(OWNER-LAUNCH-SUPPORTED-MACHINE-01): Ubuntu 22.04/24.04 x86-64, Docker 29, 16 GB RAM,
about 150 GiB disk, GPU optional (any NVIDIA, driver >= the figure our CUDA 13.0 builds
need). Anything else is warned about, never blocked; the installer and the Python check
say the same thing from the same numbers."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from carbon.development_session import supported_setup as ss

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = (ROOT / "scripts" / "install_miner.sh").read_text(encoding="utf-8")

SUPPORTED = {
    "os_id": "ubuntu",
    "os_version": "24.04",
    "arch": "x86_64",
    "docker_version": "29.1.2",
    "ram_gib": 31.2,
    "cpus": 8,
    "disk_free_gib": 400,
    "nvidia_driver": "580.65.06",
}


def test_the_supported_setup_has_no_warning():
    assert ss.assess(SUPPORTED) == []
    assert ss.warning(SUPPORTED) is None
    assert ss.assess({**SUPPORTED, "os_version": "22.04", "nvidia_driver": None}) == []
    assert ss.assess({**SUPPORTED, "nvidia_driver": "590.10"}) == []  # newer is fine


@pytest.mark.parametrize(
    ("change", "check"),
    [
        ({"os_id": "debian", "os_version": "12"}, "operating_system"),
        ({"os_id": "ubuntu", "os_version": "20.04"}, "operating_system"),
        ({"arch": "aarch64"}, "architecture"),
        ({"docker_version": "28.5.1"}, "docker"),
        ({"docker_version": "30.0.0"}, "docker"),
        ({"ram_gib": 8.0}, "memory"),
        ({"ram_gib": 15.6}, "memory"),  # a "16 GB" machine: Docker sees 15.6 GiB
        ({"cpus": 2}, "cpus"),
        ({"disk_free_gib": 90}, "disk"),
        ({"nvidia_driver": "575.57.08"}, "nvidia_driver"),
        ({"nvidia_driver": "580.65.05"}, "nvidia_driver"),
    ],
)
def test_each_difference_is_a_warning_naming_the_check(change, check):
    rows = ss.assess({**SUPPORTED, **change})
    assert [row["check"] for row in rows] == [check]
    warning = ss.warning({**SUPPORTED, **change})
    assert warning["result"] == "not_a_supported_setup_yet"
    assert "may work" in warning["message"] and "guaranteed" in warning["message"]
    assert "Ubuntu 22.04 or 24.04" in warning["supported"]


def test_carbon_needs_32_gb_so_17_gib_and_16_gb_machines_both_differ():
    """Owner ruling (bug hunt R6): Carbon needs 32 GB to install and practise. A 32 GB machine reports about 31 GiB;
    the floor is 30 GiB, the same number the installer stops at."""
    assert ss.MIN_MACHINE_RAM_GIB == 30
    assert ss.assess({**SUPPORTED, "ram_gib": 30.0, "cpus": 4}) == []
    for ram in (17.0, 15.6, 29.9):
        (row,) = ss.assess({**SUPPORTED, "ram_gib": ram})
        assert row["check"] == "memory"
        assert "Carbon needs 32 GB to install and practise" in row["supported"]
        assert "17 GiB" in row["supported"] and f"{ram:.1f} GB seen" == row["found"]


def test_what_cannot_be_read_is_not_a_difference_but_is_named():
    assert ss.assess({}) == []
    assert ss.assess({"docker_version": "not a version"}) == []
    note = ss.warning({**SUPPORTED, "docker_version": None, "ram_gib": None})
    assert note["result"] == "setup_not_fully_checked" and note["differences"] == []
    assert note["could_not_check"] == ["Docker version", "memory"]
    assert "Could not check: Docker version, memory." in note["message"]
    # A difference and an unreadable fact together: both are said.
    both = ss.warning({**SUPPORTED, "arch": "aarch64", "cpus": None})
    assert both["result"] == "not_a_supported_setup_yet"
    assert "Could not check: CPU count." in both["message"]
    # No NVIDIA tool is a normal CPU machine, never "could not check".
    assert ss.warning({**SUPPORTED, "nvidia_driver": None}) is None


def test_the_driver_figure_comes_from_the_gpu_builds_and_cites_its_source():
    """CUDA 13.0 is what both GPU runtimes are built on; the minimum driver is NVIDIA's
    figure for that, with the source stated."""
    from carbon.development_session import gpu_practice

    assert gpu_practice.runtime_cuda(gpu_practice.GPU_RUNTIMES["pytorch"]) == 13
    assert gpu_practice.runtime_cuda(gpu_practice.GPU_RUNTIMES["jax"]) == 13
    pin = (ROOT / ".devcontainer" / "accelerators" / "cuda13-py311.txt").read_text(
        encoding="utf-8"
    )
    assert "nvidia-cuda-runtime==13.0." in pin
    assert ss.MIN_NVIDIA_DRIVER == "580.65.06"
    assert "CUDA Toolkit 13.0 release notes" in ss.MIN_NVIDIA_DRIVER_SOURCE


def test_the_requirement_is_the_workers_own_doctor_check():
    """The worker is held to MemTotal >= its memory + 1 GiB and NCPU >= its CPUs
    (docker_runtime.doctor), under allowlist v7's large-model profile."""
    from carbon.reconstruction.worker import model

    gib = 1024**3
    resources = model.LARGE_MODEL_RESOURCES
    assert resources["memory_bytes"] // gib + 1 == ss.MIN_DOCKER_MEMORY_GIB
    assert model.LARGE_MODEL_CPU_COUNT == ss.MIN_CPUS


def test_the_installer_and_the_python_check_hold_the_same_numbers():
    def value(name):
        return re.search(rf'^{name}="?([^"\n]+)"?$', INSTALLER, re.MULTILINE).group(1)

    assert value("SUPPORTED_UBUNTU").split() == list(ss.SUPPORTED_UBUNTU)
    assert int(value("SUPPORTED_DOCKER_MAJOR")) == ss.SUPPORTED_DOCKER_MAJOR
    assert int(value("SUPPORTED_DOCKER_MEMORY_GIB")) == ss.MIN_DOCKER_MEMORY_GIB
    assert int(value("SUPPORTED_RAM_GB")) == ss.RECOMMENDED_RAM_GB
    assert int(value("SUPPORTED_MIN_RAM_GIB")) == ss.MIN_MACHINE_RAM_GIB
    assert int(value("SUPPORTED_CPUS")) == ss.MIN_CPUS
    assert int(value("SUPPORTED_DISK_GIB")) == ss.DISK_GIB
    assert value("SUPPORTED_NVIDIA_DRIVER") == ss.MIN_NVIDIA_DRIVER


def test_mining_md_states_the_supported_setup_and_the_driver_source():
    text = (ROOT / "docs" / "MINING.md").read_text(encoding="utf-8")
    section = text.split("## Supported setup", 1)[1].split("\n## ", 1)[0]
    for needle in (
        "Ubuntu 22.04",
        "24.04",
        "x86-64",
        "Docker 29",
        "32 GB",
        "17 GiB",
        "15.6 GiB",
        "150 GiB",
        ss.MIN_NVIDIA_DRIVER,
        "CUDA Toolkit 13.0 release notes",
        "not a supported setup yet",
    ):
        assert needle in section, needle
    assert "\n---\n\n---\n" not in text  # no doubled rule


def test_the_installer_warns_and_never_stops_on_the_check():
    start = INSTALLER.index("supported_setup_warning() {")
    body = INSTALLER[start : INSTALLER.index("\n}\n", start)]
    assert "fail " not in body and "exit " not in body  # a warning, not a block
    assert INSTALLER.count("\nsupported_setup_warning\n") == 1


def _run_installer_function(tmp_path, docker_script, free_gib_body):
    start = INSTALLER.index('SUPPORTED_UBUNTU="')
    end = INSTALLER.index("\n}\n", INSTALLER.index("supported_setup_warning() {")) + 3
    tools = tmp_path / "bin"
    tools.mkdir()
    for name, text in docker_script.items():
        tool = tools / name
        tool.write_text(text)
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    script = (
        "free_gib() { "
        + free_gib_body
        + " }\nrepo_root=/\n"
        + INSTALLER[start:end]
        + "\n"
        "supported_setup_warning\necho done-$?\n"
    )
    return subprocess.run(  # fixed argv
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{tools}:{os.environ['PATH']}"},
        check=False,
    )


@pytest.mark.skipif(os.name == "nt", reason="runs the installer's own bash function")
def test_the_installer_function_prints_the_warning_for_an_unsupported_machine(tmp_path):
    docker = (
        "#!/bin/sh\n"
        'if [ "$1" = info ]; then echo "8589934592 2"; else echo 28.5.1; fi\n'
    )
    done = _run_installer_function(
        tmp_path,
        {"docker": docker, "nvidia-smi": "#!/bin/sh\necho 575.57.08\n"},
        "echo 90;",
    )
    assert done.returncode == 0 and "done-0" in done.stdout
    assert "not a supported setup yet; it may work" in done.stderr
    assert "Docker 28.5.1 (supported: Docker 29)" in done.stderr
    assert "NVIDIA driver 575.57.08 (supported: 580.65.06 or newer)" in done.stderr
    assert "90 GiB of free disk" in done.stderr
    assert "Docker sees 8 GiB" in done.stderr and "17 GiB" in done.stderr
    assert "2 CPUs (supported: 4 or more" in done.stderr


@pytest.mark.skipif(os.name == "nt", reason="runs the installer's own bash function")
def test_the_installer_function_says_what_it_could_not_check(tmp_path):
    done = _run_installer_function(
        tmp_path, {"docker": "#!/bin/sh\nexit 1\n"}, "return 1;"
    )
    assert done.returncode == 0
    for what in ("Docker version", "memory", "CPU count", "free disk"):
        assert what in done.stderr, done.stderr


def _memory_check(tmp_path, kb, allow=0):
    start = INSTALLER.index("step_memory_check() {")
    end = INSTALLER.index("\n}\n", start) + 3
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(f"MemTotal:       {kb} kB\n" if kb else "garbage\n")
    script = (
        "set -euo pipefail\n"
        "fail() { printf 'Carbon install stopped: %s\\n' \"$*\" >&2; exit 2; }\n"
        f"SUPPORTED_RAM_GB=32\nSUPPORTED_MIN_RAM_GIB=30\nALLOW_LOW_MEMORY={allow}\n"
        f"export CARBON_INSTALL_MEMINFO_FILE={meminfo.as_posix()}\n"
        + INSTALLER[start:end]
        + "step_memory_check\necho passed\n"
    )
    return subprocess.run(  # fixed argv
        ["bash", "-c", script], capture_output=True, text=True, check=False
    )


def test_the_memory_check_function_stops_below_the_floor_and_says_it_in_plain_words(
    tmp_path,
):
    low = _memory_check(tmp_path, 16_367_000)
    assert low.returncode == 2 and "passed" not in low.stdout
    assert (
        "Carbon install stopped: This machine has 15.6 GB of memory. Carbon needs 32 GB to install and practise; "
        "with less, the install fails partway. Use a machine with 32 GB or more."
    ) in low.stderr
    assert "--allow-low-memory" in low.stderr
    assert (
        _memory_check(tmp_path, 31_457_280).stdout.strip() == "passed"
    )  # exactly 30 GiB
    assert _memory_check(tmp_path, 31_457_279).returncode == 2
    assert (
        _memory_check(tmp_path, 0).stdout.strip() == "passed"
    )  # unreadable: not a block
    override = _memory_check(tmp_path, 16_367_000, allow=1)
    assert override.stdout.strip() == "passed"
    assert "Going on because you passed --allow-low-memory" in override.stderr
