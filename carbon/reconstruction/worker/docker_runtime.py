"""Docker/OCI mechanism for the single-host C-03 DEVELOPMENT profile."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.worker.model import (
    CLEANUP_CONFIRMATION_SECONDS,
    CPU_COUNT,
    DIAGNOSTIC_BYTES,
    GRACEFUL_CANCELLATION_SECONDS,
    MEMORY_BYTES,
    NOFILE_LIMIT,
    PIDS_LIMIT,
    SCRATCH_BYTES,
    SCRATCH_INODES,
    WORKER_GID,
    WORKER_UID,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    exact_digest,
    exact_token,
    tagged_sha256,
)

_SHM_BYTES = 8 * 1024**2
_SCRATCH_TMPFS_BYTES = SCRATCH_BYTES - _SHM_BYTES


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class DockerDoctor:
    eligible: bool
    code: str
    host: dict[str, object]
    cpuset: str | None


class DockerCLI:
    """Small fixed-argv adapter; no request value becomes a Docker option."""

    def __init__(self, executable: str = "docker") -> None:
        if executable != "docker":
            raise WorkerFailure(WorkerCode.INVALID)
        self.executable = executable

    def run(
        self,
        arguments: list[str],
        *,
        timeout: float = 30,
        accepted: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[bytes]:
        environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
        for name in (
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_TLS_VERIFY",
            "DOCKER_CERT_PATH",
        ):
            if name in os.environ:
                environment[name] = os.environ[name]
        try:
            result = subprocess.run(
                [self.executable, *arguments],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
                check=False,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        if len(result.stdout) + len(result.stderr) > DIAGNOSTIC_BYTES:
            raise WorkerFailure(WorkerCode.RUNTIME)
        if result.returncode not in accepted:
            raise WorkerFailure(WorkerCode.RUNTIME)
        return result

    def json(self, arguments: list[str], *, timeout: float = 30) -> object:
        result = self.run(arguments, timeout=timeout)
        if len(result.stdout) > DIAGNOSTIC_BYTES:
            raise WorkerFailure(WorkerCode.RUNTIME)
        try:
            return json.loads(result.stdout)
        except (UnicodeError, json.JSONDecodeError):
            raise WorkerFailure(WorkerCode.RUNTIME) from None


def doctor(
    *,
    image_id: str | None = None,
    image_identity: WorkerImageIdentity | None = None,
    cli: DockerCLI | None = None,
) -> DockerDoctor:
    """Read-only eligibility check; never changes daemon or host configuration."""
    cli = cli or DockerCLI()
    docker_host = os.environ.get("DOCKER_HOST", "")
    if docker_host.startswith("tcp://") and os.environ.get("DOCKER_TLS_VERIFY") != "1":
        return DockerDoctor(
            False, "worker.doctor.unauthenticated_remote_daemon", {}, None
        )
    if image_identity is not None and (
        type(image_identity) is not WorkerImageIdentity
        or image_id != image_identity.image_id
    ):
        return DockerDoctor(False, "worker.doctor.image_identity_invalid", {}, None)
    try:
        server = cli.json(["version", "--format", "{{json .Server}}"])
        info = cli.json(["info", "--format", "{{json .}}"])
    except WorkerFailure:
        return DockerDoctor(False, "worker.doctor.docker_unavailable", {}, None)
    if type(server) is not dict or type(info) is not dict:
        return DockerDoctor(False, "worker.doctor.runtime_unknown", {}, None)
    ncpu = info.get("NCPU")
    memory = info.get("MemTotal")
    cgroup_version = str(info.get("CgroupVersion", ""))
    security = info.get("SecurityOptions")
    if (
        type(ncpu) is not int
        or ncpu < CPU_COUNT
        or type(memory) is not int
        or memory < MEMORY_BYTES + 1024**3
        or cgroup_version != "2"
        or type(security) is not list
    ):
        return DockerDoctor(
            False,
            "worker.doctor.capacity_or_cgroup_ineligible",
            {"server": server, "info": info},
            None,
        )
    if any("rootless" in str(item).lower() for item in security):
        # Rootless may be supportable later, but it is not the selected/tested
        # daemon profile and must not silently replace it.
        return DockerDoctor(
            False, "worker.doctor.engine_mode_unsupported", {"info": info}, None
        )
    if image_id is not None:
        try:
            exact_digest(image_id)
            image = cli.json(["image", "inspect", image_id, "--format", "{{json .}}"])
        except WorkerFailure:
            return DockerDoctor(
                False, "worker.doctor.image_unavailable", {"info": info}, None
            )
        if (
            type(image) is not dict
            or image.get("Id") != image_id
            or image.get("Os") != "linux"
            or image.get("Architecture") != "amd64"
            or image.get("Config", {}).get("User") != f"{WORKER_UID}:{WORKER_GID}"
        ):
            return DockerDoctor(
                False, "worker.doctor.image_ineligible", {"info": info}, None
            )
        if image_identity is not None:
            labels = image.get("Config", {}).get("Labels") or {}
            expected_labels = {
                "org.opencontainers.image.carbon.c03.scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
                "org.opencontainers.image.carbon.c03.source-tree": image_identity.source_tree_digest,
                "org.opencontainers.image.carbon.c03.lock": image_identity.lock_digest,
                "org.opencontainers.image.carbon.c03.base-image": image_identity.base_image_digest,
                "org.opencontainers.image.carbon.c03.build-recipe": image_identity.build_recipe_digest,
                "org.opencontainers.image.carbon.c03.entrypoint": image_identity.entrypoint_digest,
            }
            entrypoint = image.get("Config", {}).get("Entrypoint")
            if any(
                labels.get(key) != value for key, value in expected_labels.items()
            ) or entrypoint != [
                "/opt/carbon-worker/bin/python",
                "-I",
                "-m",
                "carbon.reconstruction.worker.entrypoint",
            ]:
                return DockerDoctor(
                    False, "worker.doctor.image_binding_mismatch", {"info": info}, None
                )
    return DockerDoctor(
        True,
        "worker.doctor.eligible",
        {
            "controller_platform": platform.system(),
            "controller_machine": platform.machine(),
            "server_version": server.get("Version"),
            "api_version": server.get("ApiVersion"),
            "kernel_version": info.get("KernelVersion"),
            "operating_system": info.get("OperatingSystem"),
            "architecture": info.get("Architecture"),
            "cgroup_driver": info.get("CgroupDriver"),
            "cgroup_version": cgroup_version,
            "security_options": security,
            "logical_cpus": ncpu,
            "memory_bytes": memory,
        },
        "0,1",
    )


def create_arguments(
    *,
    container_name: str,
    image_id: str,
    input_directory: Path,
    cpuset: str,
    launch_digest: str,
    worker_profile: DevelopmentWorkerProfile,
) -> list[str]:
    exact_token(container_name)
    exact_digest(image_id)
    exact_digest(launch_digest)
    if type(worker_profile) is not DevelopmentWorkerProfile:
        raise WorkerFailure(WorkerCode.INVALID)
    if (
        cpuset != "0,1"
        or not input_directory.is_absolute()
        or input_directory.is_symlink()
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    source = str(input_directory)
    if "," in source or "\n" in source:
        raise WorkerFailure(WorkerCode.INVALID)
    return [
        "create",
        "--name",
        container_name,
        "--platform",
        "linux/amd64",
        "--label",
        f"org.opencontainers.image.carbon.c03.launch={launch_digest}",
        "--label",
        f"org.opencontainers.image.carbon.c03.policy={worker_profile.digest}",
        "--network",
        "none",
        "--ipc",
        "private",
        # Docker's empty/default PID mode is a private PID namespace. Unlike
        # IPC mode, the CLI does not accept the literal value ``private``.
        # Effective inspection below rejects host/container PID modes.
        "--read-only",
        "--user",
        f"{WORKER_UID}:{WORKER_GID}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--pids-limit",
        str(PIDS_LIMIT),
        "--memory",
        str(MEMORY_BYTES),
        "--memory-swap",
        str(MEMORY_BYTES),
        "--cpus",
        str(CPU_COUNT),
        "--cpuset-cpus",
        cpuset,
        "--ulimit",
        f"nofile={NOFILE_LIMIT}:{NOFILE_LIMIT}",
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
        "--stop-timeout",
        str(GRACEFUL_CANCELLATION_SECONDS),
        "--shm-size",
        str(_SHM_BYTES),
        "--tmpfs",
        (
            "/scratch:rw,nosuid,nodev,noexec,size="
            f"{_SCRATCH_TMPFS_BYTES},nr_inodes={SCRATCH_INODES},mode=700,"
            f"uid={WORKER_UID},gid={WORKER_GID}"
        ),
        "--mount",
        f"type=bind,source={source},target=/input,readonly,bind-propagation=rprivate",
        "--env",
        "HOME=/scratch/home",
        "--env",
        "TMPDIR=/scratch/tmp",
        "--env",
        "XDG_CACHE_HOME=/scratch/cache",
        "--env",
        "JAX_PLATFORMS=cpu",
        "--env",
        "JAX_COMPILATION_CACHE_DIR=/scratch/jax-cache",
        "--env",
        "XLA_PYTHON_CLIENT_PREALLOCATE=false",
        "--env",
        "OMP_NUM_THREADS=2",
        "--env",
        "OPENBLAS_NUM_THREADS=2",
        "--env",
        "MKL_NUM_THREADS=2",
        image_id,
    ]


def inspect_effective_controls(
    *,
    cli: DockerCLI,
    container_name: str,
    image_id: str,
    input_directory: Path,
    cpuset: str,
    launch_digest: str,
    worker_profile: DevelopmentWorkerProfile,
) -> tuple[str, dict[str, object]]:
    """Verify daemon config and kernel-visible controls after create/start."""
    value = cli.json(["inspect", container_name, "--format", "{{json .}}"])
    if type(value) is not dict:
        raise WorkerFailure(WorkerCode.POLICY)
    host = value.get("HostConfig")
    config = value.get("Config")
    state = value.get("State")
    mounts = value.get("Mounts")
    if (
        not all(type(item) is dict for item in (host, config, state))
        or type(mounts) is not list
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    expected_label = f"org.opencontainers.image.carbon.c03.launch={launch_digest}"
    security = host.get("SecurityOpt") or []
    ulimits = {
        item.get("Name"): (item.get("Soft"), item.get("Hard"))
        for item in host.get("Ulimits") or []
    }
    input_mounts = [item for item in mounts if item.get("Destination") == "/input"]
    unexpected_mounts = [
        item for item in mounts if item.get("Destination") not in {"/input", "/scratch"}
    ]
    tmpfs_options = set(str((host.get("Tmpfs") or {}).get("/scratch", "")).split(","))
    expected_tmpfs = {
        "rw",
        "nosuid",
        "nodev",
        "noexec",
        f"size={_SCRATCH_TMPFS_BYTES}",
        f"nr_inodes={SCRATCH_INODES}",
        "mode=700",
        f"uid={WORKER_UID}",
        f"gid={WORKER_GID}",
    }
    if (
        value.get("Image") != image_id
        or config.get("User") != f"{WORKER_UID}:{WORKER_GID}"
        or config.get("Labels", {}).get("org.opencontainers.image.carbon.c03.launch")
        != launch_digest
        or not host.get("ReadonlyRootfs")
        or host.get("Privileged")
        or host.get("NetworkMode") != "none"
        or host.get("IpcMode") not in ("private", "")
        or host.get("PidMode") not in ("", "private")
        or host.get("RestartPolicy", {}).get("Name") != "no"
        or host.get("LogConfig")
        != {"Type": "local", "Config": {"max-file": "1", "max-size": "1m"}}
        or host.get("PidsLimit") != PIDS_LIMIT
        or host.get("Memory") != MEMORY_BYTES
        or host.get("MemorySwap") != MEMORY_BYTES
        or host.get("NanoCpus") != CPU_COUNT * 1_000_000_000
        or host.get("CpusetCpus") != cpuset
        or host.get("ShmSize") != _SHM_BYTES
        or host.get("CapAdd")
        or sorted(host.get("CapDrop") or []) != ["ALL"]
        or host.get("Devices")
        or host.get("DeviceRequests")
        or host.get("PortBindings")
        or host.get("PublishAllPorts")
        or "no-new-privileges=true" not in security
        or ulimits.get("nofile") != (NOFILE_LIMIT, NOFILE_LIMIT)
        or ulimits.get("core") != (0, 0)
        or len(input_mounts) != 1
        or input_mounts[0].get("Source") != str(input_directory)
        or input_mounts[0].get("RW") is not False
        or unexpected_mounts
        or tmpfs_options != expected_tmpfs
        or expected_label
        not in create_arguments(
            container_name=container_name,
            image_id=image_id,
            input_directory=input_directory,
            cpuset=cpuset,
            launch_digest=launch_digest,
            worker_profile=worker_profile,
        )
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    status = cli.run(
        ["exec", container_name, "/bin/cat", "/proc/1/status"], timeout=10
    ).stdout.decode("ascii", "replace")
    facts = {}
    for line in status.splitlines():
        if line.startswith(("CapEff:", "NoNewPrivs:", "Seccomp:")):
            key, value_text = line.split(":", 1)
            facts[key] = value_text.strip()
    if facts != {"CapEff": "0000000000000000", "NoNewPrivs": "1", "Seccomp": "2"}:
        raise WorkerFailure(WorkerCode.POLICY)
    cgroup: dict[str, str] = {}
    for name in (
        "cpu.max",
        "cpuset.cpus.effective",
        "memory.max",
        "memory.swap.max",
        "pids.max",
    ):
        result = cli.run(
            ["exec", container_name, "/bin/cat", f"/sys/fs/cgroup/{name}"], timeout=10
        )
        cgroup[name] = result.stdout.decode("ascii", "replace").strip()
    cpu_quota = cgroup["cpu.max"].split()
    eligible = {str(item) for item in range(2)}
    observed_cpuset = set()
    for group in cgroup["cpuset.cpus.effective"].split(","):
        if "-" in group:
            start, end = (int(item) for item in group.split("-", 1))
            observed_cpuset.update(str(item) for item in range(start, end + 1))
        elif group:
            observed_cpuset.add(group)
    if (
        len(cpu_quota) != 2
        or int(cpu_quota[0]) != CPU_COUNT * int(cpu_quota[1])
        or observed_cpuset != eligible
        or cgroup["memory.max"] != str(MEMORY_BYTES)
        or cgroup["memory.swap.max"] != "0"
        or cgroup["pids.max"] != str(PIDS_LIMIT)
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    scratch_size = int(
        cli.run(
            ["exec", container_name, "/bin/df", "-B1", "--output=size", "/scratch"],
            timeout=10,
        ).stdout.splitlines()[-1]
    )
    scratch_inodes = int(
        cli.run(
            ["exec", container_name, "/bin/df", "-i", "--output=inodes", "/scratch"],
            timeout=10,
        ).stdout.splitlines()[-1]
    )
    shm_size = int(
        cli.run(
            ["exec", container_name, "/bin/df", "-B1", "--output=size", "/dev/shm"],
            timeout=10,
        ).stdout.splitlines()[-1]
    )
    if (
        scratch_size > _SCRATCH_TMPFS_BYTES
        or scratch_inodes > SCRATCH_INODES
        or shm_size > _SHM_BYTES
        or scratch_size + shm_size > SCRATCH_BYTES
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    evidence = {
        "schema": "carbon.c03.effective-controls.v1",
        "image_id": image_id,
        "launch_digest": launch_digest,
        "worker_profile_digest": worker_profile.digest,
        "container_id": value.get("Id"),
        "apparmor_profile": value.get("AppArmorProfile") or "NOT_ACTIVE_OR_UNREPORTED",
        "daemon_host_config": {
            "read_only_root": host.get("ReadonlyRootfs"),
            "network_mode": host.get("NetworkMode"),
            "ipc_mode": host.get("IpcMode") or "private-default",
            "pid_mode": host.get("PidMode") or "private-default",
            "memory": host.get("Memory"),
            "memory_swap": host.get("MemorySwap"),
            "nano_cpus": host.get("NanoCpus"),
            "cpuset_cpus": host.get("CpusetCpus"),
            "pids_limit": host.get("PidsLimit"),
            "security_opt": security,
            "cap_drop": host.get("CapDrop"),
            "ulimits": host.get("Ulimits"),
            "tmpfs": host.get("Tmpfs"),
            "shm_size": host.get("ShmSize"),
        },
        "process": facts,
        "cgroup_v2": cgroup,
        "filesystem": {
            "scratch_bytes": scratch_size,
            "scratch_inodes": scratch_inodes,
            "shm_bytes": shm_size,
            "aggregate_bytes": scratch_size + shm_size,
        },
    }
    return tagged_sha256(_canonical(evidence)), evidence


def remove_exact_container(
    *, cli: DockerCLI, container_name: str, launch_digest: str
) -> None:
    """Stop/remove only the exact launch-labeled container and confirm absence."""
    try:
        value = cli.json(["inspect", container_name, "--format", "{{json .}}"])
    except WorkerFailure:
        return
    if (
        type(value) is not dict
        or value.get("Config", {})
        .get("Labels", {})
        .get("org.opencontainers.image.carbon.c03.launch")
        != launch_digest
    ):
        raise WorkerFailure(WorkerCode.CLEANUP)
    cli.run(
        ["stop", "--time", str(GRACEFUL_CANCELLATION_SECONDS), container_name],
        timeout=GRACEFUL_CANCELLATION_SECONDS + 10,
        accepted=(0, 1),
    )
    cli.run(["kill", container_name], timeout=10, accepted=(0, 1))
    cli.run(["rm", "--force", container_name], timeout=10, accepted=(0, 1))
    deadline = time.monotonic() + CLEANUP_CONFIRMATION_SECONDS
    while time.monotonic() < deadline:
        result = cli.run(["inspect", container_name], timeout=5, accepted=(0, 1))
        if result.returncode != 0:
            return
        time.sleep(0.1)
    raise WorkerFailure(WorkerCode.CLEANUP)


def spawn_watchdog(
    *, container_name: str, launch_digest: str, deadline_unix: float
) -> None:
    exact_token(container_name)
    exact_digest(launch_digest)
    if type(deadline_unix) is not float or deadline_unix <= time.time():
        raise WorkerFailure(WorkerCode.INVALID)
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        if name in os.environ:
            environment[name] = os.environ[name]
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "carbon.reconstruction.worker.watchdog",
                container_name,
                launch_digest,
                str(deadline_unix),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=environment,
        )
    except OSError:
        raise WorkerFailure(WorkerCode.UNAVAILABLE) from None


def load_image_identity(path: Path) -> WorkerImageIdentity:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            type(value) is not dict
            or set(value)
            != {
                "schema",
                "image_id",
                "config_digest",
                "source_tree_digest",
                "wheel_digest",
                "lock_digest",
                "base_image_digest",
                "build_recipe_digest",
                "entrypoint_digest",
            }
            or value["schema"] != "carbon.c03.worker-image.v1"
        ):
            raise ValueError
        return WorkerImageIdentity(
            **{key: value[key] for key in value if key != "schema"}
        )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        raise WorkerFailure(WorkerCode.INVALID) from None


__all__ = [
    "DockerCLI",
    "DockerDoctor",
    "create_arguments",
    "doctor",
    "inspect_effective_controls",
    "load_image_identity",
    "remove_exact_container",
    "spawn_watchdog",
]
