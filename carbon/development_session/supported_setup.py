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
#: Practice's worker runs under a 16 GiB limit and Docker must see that plus 1 GiB
#: (`docker_runtime.doctor`: MemTotal >= memory_bytes + 1 GiB, NCPU >= 4), so a
#: "16 GB" machine, which Docker reports as about 15.6 GiB, cannot run it.
MIN_DOCKER_MEMORY_GIB = 17
MIN_CPUS = 4
RECOMMENDED_RAM_GB = 32
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
    f"Ubuntu 22.04 or 24.04 (x86-64), Docker 29, {RECOMMENDED_RAM_GB} GB of RAM "
    f"(practice needs Docker to see {MIN_DOCKER_MEMORY_GIB} GiB; a 16 GB machine "
    f"reports about 15.6 GiB), {MIN_CPUS} CPUs and about {DISK_GIB} GB of free disk; "
    f"a GPU is optional (any NVIDIA GPU with driver {MIN_NVIDIA_DRIVER} or newer)."
)


#: The facts a miner can act on when they cannot be read, by their `facts` key. The
#: GPU driver is left out: a machine with no NVIDIA tool is a normal CPU machine.
CHECKED = {
    "os_id": "operating system",
    "docker_version": "Docker version",
    "ram_gib": "memory",
    "cpus": "CPU count",
    "disk_free_gib": "free disk",
}


def unchecked(facts: dict) -> list[str]:
    """What this machine could not be asked about, in words ("Docker version")."""
    return [label for key, label in CHECKED.items() if facts.get(key) is None]


def _numbers(version) -> tuple[int, ...] | None:
    parts = re.findall(r"\d+", str(version or ""))
    return tuple(int(p) for p in parts) or None


def assess(facts: dict) -> list[dict]:
    """Every way this machine differs from the supported setup, as
    `{"check", "found", "supported"}` rows (empty = supported). A fact that is
    absent (`None`) could not be read: it is not a difference, and `unchecked`
    names it. Never raises and never blocks: the caller prints `NOT_SUPPORTED`
    with the rows."""
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
    if ram is not None and ram < MIN_DOCKER_MEMORY_GIB:
        add(
            "memory",
            f"{ram:.1f} GiB seen",
            f"{RECOMMENDED_RAM_GB} GB of RAM (Docker must see {MIN_DOCKER_MEMORY_GIB} GiB: "
            "the practice worker runs under a 16 GiB limit plus 1 GiB)",
        )
    cpus = facts.get("cpus")
    if cpus is not None and cpus < MIN_CPUS:
        add("cpus", f"{cpus}", f"{MIN_CPUS} or more (the practice worker uses {MIN_CPUS})")
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
    ram = cpus = None
    # What Docker sees is what practice is held to (`docker info`: MemTotal, NCPU).
    seen = _run(["docker", "info", "--format", "{{.MemTotal}} {{.NCPU}}"])
    try:
        total, count = (seen or "").split()
        ram, cpus = int(total) / 2**30, int(count)
    except ValueError:
        pass
    if ram is None:
        try:
            with open("/proc/meminfo", encoding="ascii") as stream:
                for line in stream:
                    if line.startswith("MemTotal:"):
                        ram = int(line.split()[1]) / (1024 * 1024)
        except (OSError, ValueError, IndexError):
            pass
    if cpus is None:
        cpus = os.cpu_count()
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
        "cpus": cpus,
        "disk_free_gib": disk,
        "nvidia_driver": driver.splitlines()[0] if driver else None,
    }


def warning(facts: dict | None = None) -> dict | None:
    """The note for this machine, or None when it is the supported setup and every
    fact could be read: `{"result": "not_a_supported_setup_yet" | "setup_not_fully_checked",
    "differences": [...], "could_not_check": [...], "message", "supported"}`."""
    facts = facts if facts is not None else host_facts()
    rows, missing = assess(facts), unchecked(facts)
    if not rows and not missing:
        return None
    message = NOT_SUPPORTED if rows else "Could not check this machine fully."
    if missing:
        message += " Could not check: " + ", ".join(missing) + "."
    return {
        "result": "not_a_supported_setup_yet" if rows else "setup_not_fully_checked",
        "differences": rows,
        "could_not_check": missing,
        "message": message,
        "supported": SUPPORTED_SUMMARY,
    }


@functools.lru_cache(maxsize=1)
def cached_warning() -> dict | None:
    """`warning()` for this machine, read once per process (it asks Docker and
    the NVIDIA tool, which a page that polls its state must not repeat)."""
    return warning()
