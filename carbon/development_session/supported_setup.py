"""The one machine setup Carbon's launch supports, and the warning every other
machine gets (OWNER-LAUNCH-SUPPORTED-MACHINE-01).

Supported: Ubuntu 22.04 or 24.04, x86-64, Docker 29, at least 16 GB of RAM and
about 150 GB of free disk; a GPU is optional, and any NVIDIA GPU whose driver is
at least `MIN_NVIDIA_DRIVER` works. Any other setup is *warned about, never
blocked*: it may work, but only the supported setup is guaranteed.

`scripts/install_miner.sh` prints the same words from the same numbers (a test
holds the two together), and docs/MINING.md "Supported setup" states them.
"""

from __future__ import annotations

import functools
import os
import platform
import re
import shutil
import subprocess

SUPPORTED_UBUNTU = ("22.04", "24.04")
SUPPORTED_ARCH = "x86_64"
SUPPORTED_DOCKER_MAJOR = 29
MIN_RAM_GIB = 16
DISK_GIB = 150

#: The oldest NVIDIA Linux driver that runs Carbon's GPU builds. Both GPU
#: runtimes (`torch-cu130-py311`, `jax-cuda13-py311`) are built on CUDA 13.0
#: (`nvidia-cuda-runtime==13.0.48`, `.devcontainer/accelerators/cuda13-py311.txt`).
MIN_NVIDIA_DRIVER = "580.65.06"
#: Where that figure comes from: NVIDIA's CUDA Toolkit 13.0 release notes
#: (driver/toolkit compatibility table, Linux x86_64: ">=580.65.06"); later 13.x
#: runs on any driver >= 580 under CUDA minor-version compatibility.
MIN_NVIDIA_DRIVER_SOURCE = (
    "NVIDIA CUDA Toolkit 13.0 release notes, "
    "https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html"
)

NOT_SUPPORTED = (
    "This is not a supported setup yet; it may work. Use the supported setup "
    "for a guaranteed run."
)
SUPPORTED_SUMMARY = (
    "Ubuntu 22.04 or 24.04 (x86-64), Docker 29, at least 16 GB of RAM and about "
    "150 GB of free disk; a GPU is optional (any NVIDIA GPU with driver "
    f"{MIN_NVIDIA_DRIVER} or newer)."
)


def _numbers(version) -> tuple[int, ...] | None:
    parts = re.findall(r"\d+", str(version or ""))
    return tuple(int(p) for p in parts) or None


def assess(facts: dict) -> list[dict]:
    """Every way this machine differs from the supported setup, as
    `{"check", "found", "supported"}` rows (empty = supported). A fact that is
    absent (`None`) could not be read and is not warned about. Never raises and
    never blocks: the caller prints `NOT_SUPPORTED` with the rows."""
    rows = []

    def add(check, found, supported):
        rows.append({"check": check, "found": found, "supported": supported})

    os_id, os_version = facts.get("os_id"), facts.get("os_version")
    if os_id is not None and not (
        os_id == "ubuntu" and str(os_version) in SUPPORTED_UBUNTU
    ):
        add(
            "operating_system",
            f"{os_id} {os_version or ''}".strip(),
            "Ubuntu 22.04 or 24.04",
        )
    arch = facts.get("arch")
    if arch is not None and arch != SUPPORTED_ARCH:
        add("architecture", arch, "x86-64")
    docker = _numbers(facts.get("docker_version"))
    if docker is not None and docker[0] != SUPPORTED_DOCKER_MAJOR:
        add("docker", str(facts["docker_version"]), f"Docker {SUPPORTED_DOCKER_MAJOR}")
    ram = facts.get("ram_gib")
    if ram is not None and ram < MIN_RAM_GIB:
        add("memory", f"{ram:.0f} GB", f"{MIN_RAM_GIB} GB or more")
    disk = facts.get("disk_free_gib")
    if disk is not None and disk < DISK_GIB:
        add("disk", f"{disk:.0f} GB free", f"about {DISK_GIB} GB free")
    driver = facts.get("nvidia_driver")
    if driver is not None:
        have, need = _numbers(driver), _numbers(MIN_NVIDIA_DRIVER)
        if have is not None and have < need:
            add("nvidia_driver", str(driver), f"{MIN_NVIDIA_DRIVER} or newer")
    return rows


def _run(argv):
    try:
        done = subprocess.run(  # fixed argv
            argv, capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def host_facts(path=".") -> dict:
    """What this machine says about itself; anything unreadable is `None`."""
    os_id = os_version = None
    try:
        with open("/etc/os-release", encoding="utf-8") as stream:
            release = dict(
                line.rstrip("\n").split("=", 1) for line in stream if "=" in line
            )
        os_id = release.get("ID", "").strip('"').lower() or None
        os_version = release.get("VERSION_ID", "").strip('"') or None
    except OSError:
        pass
    ram = None
    try:
        with open("/proc/meminfo", encoding="ascii") as stream:
            for line in stream:
                if line.startswith("MemTotal:"):
                    ram = int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        pass
    try:
        disk = shutil.disk_usage(os.path.abspath(path)).free / 2**30
    except OSError:
        disk = None
    driver = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    return {
        "os_id": os_id,
        "os_version": os_version,
        "arch": platform.machine() or None,
        "docker_version": _run(
            ["docker", "version", "--format", "{{.Server.Version}}"]
        ),
        "ram_gib": ram,
        "disk_free_gib": disk,
        "nvidia_driver": driver.splitlines()[0] if driver else None,
    }


def warning(facts: dict | None = None) -> dict | None:
    """The warning for this machine, or None when it is the supported setup:
    `{"result": "not_a_supported_setup_yet", "differences": [...], "message",
    "supported"}`."""
    rows = assess(facts if facts is not None else host_facts())
    if not rows:
        return None
    return {
        "result": "not_a_supported_setup_yet",
        "differences": rows,
        "message": NOT_SUPPORTED,
        "supported": SUPPORTED_SUMMARY,
    }


@functools.lru_cache(maxsize=1)
def cached_warning() -> dict | None:
    """`warning()` for this machine, read once per process (it asks Docker and
    the NVIDIA tool, which a page that polls its state must not repeat)."""
    return warning()
