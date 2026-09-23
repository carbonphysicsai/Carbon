"""The container a miner's own research runs in: isolated, and not limited.

Owner direction (23 September 2026): the research environment is the miner's
machine, cost, time and choice, so Carbon imposes no CPU, memory, process,
file-descriptor, scratch or wall-clock limit on it. What stays is isolation,
which is not a limit on the miner's resources but the separation between
hostile research code and the controller that records its results: no network,
a read-only image, no capabilities, no privilege escalation, a non-root user,
and nothing mounted but the run's own input (read-only) and scratch.

This is a separate lane from the validator's grading worker in
`carbon.reconstruction.worker.docker_runtime`, which keeps every one of its
limits. The two share no argument builder: the miner lane cannot reach the
validator's settings, and the validator's cannot be loosened through this one.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.worker.model import (
    GRACEFUL_CANCELLATION_SECONDS,
    WORKER_GID,
    WORKER_UID,
    WorkerCode,
    WorkerFailure,
    exact_digest,
    exact_token,
)

LANE = "carbon.miner-research.unlimited.v1"


@dataclass(frozen=True)
class MinerResearchLaunch:
    """One miner research run. Only the carrier's miner lane constructs it."""

    container_name: str
    image_id: str
    launch_digest: str
    input_directory: Path
    scratch_directory: Path

    def __post_init__(self):
        exact_token(self.container_name)
        exact_digest(self.image_id)
        exact_digest(self.launch_digest)
        for directory in (self.input_directory, self.scratch_directory):
            if (
                not directory.is_absolute()
                or directory.is_symlink()
                or "," in str(directory)
                or "\n" in str(directory)
            ):
                raise WorkerFailure(WorkerCode.INVALID)


def prepare_scratch(directory: Path) -> Path:
    """A scratch directory on the miner's own disk, writable by the worker user.

    World-writable because the worker runs as a fixed non-root uid the host
    user cannot chown to without root; its parent is the owner-only campaign
    root, so no other host user can reach it.
    """
    directory.mkdir(mode=0o700)
    for name in ("output", "home", "tmp", "cache", "jax-cache"):
        (directory / name).mkdir(mode=0o777)
        (directory / name).chmod(0o777)
    directory.chmod(0o777)
    return directory


def create_arguments(launch: MinerResearchLaunch) -> list[str]:
    if type(launch) is not MinerResearchLaunch:
        raise WorkerFailure(WorkerCode.INVALID)
    threads = str(os.cpu_count() or 1)
    return [
        "create",
        "--name",
        launch.container_name,
        "--platform",
        "linux/amd64",
        "--label",
        f"org.opencontainers.image.carbon.c03.launch={launch.launch_digest}",
        "--label",
        f"org.opencontainers.image.carbon.lane={LANE}",
        # Isolation: every one of these stays.
        "--network",
        "none",
        "--ipc",
        "private",
        "--read-only",
        "--user",
        f"{WORKER_UID}:{WORKER_GID}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--ulimit",
        "core=0:0",
        "--restart",
        "no",
        "--log-driver",
        "local",
        "--log-opt",
        "max-size=1m",
        "--log-opt",
        "max-file=1",
        "--log-opt",
        "compress=false",
        "--stop-timeout",
        str(GRACEFUL_CANCELLATION_SECONDS),
        # No limits: no --memory, --cpus, --cpuset-cpus, --pids-limit or nofile
        # ulimit, and shared memory as large as the host's, for data loaders.
        "--shm-size",
        str(_host_memory_bytes()),
        "--mount",
        (
            f"type=bind,source={launch.input_directory},target=/input,"
            "readonly,bind-propagation=rprivate"
        ),
        "--mount",
        (
            f"type=bind,source={launch.scratch_directory},target=/scratch,"
            "bind-propagation=rprivate"
        ),
        "--env",
        "HOME=/scratch/home",
        "--env",
        "TMPDIR=/scratch/tmp",
        "--env",
        "XDG_CACHE_HOME=/scratch/cache",
        "--env",
        "JAX_COMPILATION_CACHE_DIR=/scratch/jax-cache",
        "--env",
        "XLA_PYTHON_CLIENT_PREALLOCATE=false",
        "--env",
        f"OMP_NUM_THREADS={threads}",
        "--env",
        f"OPENBLAS_NUM_THREADS={threads}",
        "--env",
        f"MKL_NUM_THREADS={threads}",
        launch.image_id,
    ]


def _host_memory_bytes() -> int:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        return 64 * 1024**3


def inspect_isolation(cli, launch: MinerResearchLaunch) -> dict:
    """Refuse a container whose isolation is not exactly what was asked for.

    Checks every isolation property after create; asserts nothing about size,
    because the miner's research has none.
    """
    value = cli.json(["inspect", launch.container_name, "--format", "{{json .}}"])
    host = value.get("HostConfig") if type(value) is dict else None
    config = value.get("Config") if type(value) is dict else None
    mounts = value.get("Mounts") if type(value) is dict else None
    if type(host) is not dict or type(config) is not dict or type(mounts) is not list:
        raise WorkerFailure(WorkerCode.POLICY)
    by_target = {item.get("Destination"): item for item in mounts}
    security = host.get("SecurityOpt") or []
    if (
        value.get("Image") != launch.image_id
        or config.get("User") != f"{WORKER_UID}:{WORKER_GID}"
        or config.get("Labels", {}).get("org.opencontainers.image.carbon.lane") != LANE
        or not host.get("ReadonlyRootfs")
        or host.get("Privileged")
        or host.get("NetworkMode") != "none"
        or host.get("IpcMode") not in ("private", "")
        or host.get("PidMode") not in ("", "private")
        or host.get("CapAdd")
        or sorted(host.get("CapDrop") or []) != ["ALL"]
        or host.get("Devices")
        or host.get("DeviceRequests")
        or host.get("PortBindings")
        or host.get("PublishAllPorts")
        or "no-new-privileges=true" not in security
        or set(by_target) != {"/input", "/scratch"}
        or by_target["/input"].get("Source") != str(launch.input_directory)
        or by_target["/input"].get("RW") is not False
        or by_target["/scratch"].get("Source") != str(launch.scratch_directory)
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    return {
        "lane": LANE,
        "network": host.get("NetworkMode"),
        "read_only_root": True,
        "memory": host.get("Memory") or None,
        "nano_cpus": host.get("NanoCpus") or None,
        "pids_limit": host.get("PidsLimit") or None,
    }


def collect_outputs(scratch: Path, snapshot: Path) -> dict[str, int]:
    """Copy the run's own outputs into the snapshot, as untrusted bytes.

    Regular files only: a symlink, device, socket or FIFO written by hostile
    code is refused rather than followed, and every path stays inside the
    output directory. No size or count limit - it is the miner's disk.
    """
    source = scratch / "output"
    snapshot.mkdir(mode=0o700)
    copied = {}
    for directory, dirnames, filenames in os.walk(source, followlinks=False):
        base = Path(directory)
        for name in dirnames:
            if (base / name).is_symlink():
                raise ValueError("research output may not contain links")
        for name in filenames:
            path = base / name
            relative = path.relative_to(source)
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("research output may contain regular files only")
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(handle, "rb") as reader, open(target, "xb") as writer:
                while chunk := reader.read(1024**2):
                    writer.write(chunk)
            copied[relative.as_posix()] = info.st_size
    return copied
