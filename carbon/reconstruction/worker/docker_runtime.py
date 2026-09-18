"""Docker/OCI mechanism for the single-host C-03 DEVELOPMENT profile."""

from __future__ import annotations

import json
import os
import platform
import selectors
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


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Bounded best-effort reaping for one controller-owned CLI process."""

    if process.poll() is not None:
        return
    process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # The process is already kill-signalled.  Do not turn cleanup of the
        # local CLI child into an unbounded controller wait.
        pass


def _bounded_capture(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout: float,
    maximum: int,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Capture stdout/stderr while enforcing the aggregate cap during receipt."""

    if (
        type(command) is not list
        or not command
        or any(type(item) is not str or not item for item in command)
        or type(timeout) not in (int, float)
        or timeout <= 0
        or type(maximum) is not int
        or maximum < 1
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    process: subprocess.Popen[bytes] | None = None
    stdout = bytearray()
    stderr = bytearray()
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            cwd=cwd,
        )
        if process.stdout is None or process.stderr is None:
            raise WorkerFailure(WorkerCode.RUNTIME)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, stdout)
            selector.register(process.stderr, selectors.EVENT_READ, stderr)
            deadline = time.monotonic() + float(timeout)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerFailure(
                        WorkerCode.UNAVAILABLE,
                        private_diagnostic=b"bounded command timed out",
                    )
                for key, _ in selector.select(timeout=min(remaining, 0.25)):
                    block = os.read(key.fd, 1 << 16)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    destination = key.data
                    available = maximum - len(stdout) - len(stderr)
                    destination.extend(block[:available])
                    if len(block) > available:
                        raise WorkerFailure(
                            WorkerCode.RUNTIME,
                            private_diagnostic=(
                                b"controller response exceeded cap\nstdout:\n"
                                + bytes(stdout)
                                + b"\nstderr:\n"
                                + bytes(stderr)
                            )[:DIAGNOSTIC_BYTES],
                        )
        return_code = process.wait(timeout=1)
        return subprocess.CompletedProcess(
            command, return_code, bytes(stdout), bytes(stderr)
        )
    except WorkerFailure:
        if process is not None:
            _stop_process(process)
        raise
    except (OSError, subprocess.SubprocessError):
        if process is not None:
            _stop_process(process)
        raise WorkerFailure(
            WorkerCode.UNAVAILABLE,
            private_diagnostic=(bytes(stdout) + bytes(stderr))[:DIAGNOSTIC_BYTES],
        ) from None


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
        result = _bounded_capture(
            [self.executable, *arguments],
            environment=environment,
            timeout=timeout,
            maximum=DIAGNOSTIC_BYTES,
        )
        private_diagnostic = (
            f"exit={result.returncode}\nstdout:\n".encode("ascii")
            + result.stdout
            + b"\nstderr:\n"
            + result.stderr
        )[:DIAGNOSTIC_BYTES]
        if result.returncode not in accepted:
            raise WorkerFailure(
                WorkerCode.RUNTIME, private_diagnostic=private_diagnostic
            )
        return result

    def json(self, arguments: list[str], *, timeout: float = 30) -> object:
        result = self.run(arguments, timeout=timeout)
        if len(result.stdout) > DIAGNOSTIC_BYTES:
            raise WorkerFailure(WorkerCode.RUNTIME)
        try:
            return json.loads(result.stdout)
        except (UnicodeError, json.JSONDecodeError):
            raise WorkerFailure(WorkerCode.RUNTIME) from None

    def stream_to_file(
        self,
        arguments: list[str],
        destination: Path,
        *,
        maximum: int,
        timeout: float,
    ) -> int:
        """Stream one fixed Docker command without unbounded controller capture."""

        if (
            type(maximum) is not int
            or maximum < 1
            or type(timeout) not in (int, float)
            or timeout <= 0
            or not destination.is_absolute()
            or destination.is_symlink()
            or not destination.parent.is_dir()
        ):
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
        process: subprocess.Popen[bytes] | None = None
        diagnostic = bytearray()
        total = 0
        try:
            process = subprocess.Popen(
                [self.executable, *arguments],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
            )
            if process.stdout is None or process.stderr is None:
                raise WorkerFailure(WorkerCode.RUNTIME)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            deadline = time.monotonic() + float(timeout)
            with destination.open("xb") as stream:
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise WorkerFailure(
                            WorkerCode.RUNTIME,
                            private_diagnostic=b"stream command timed out",
                        )
                    events = selector.select(timeout=min(remaining, 0.25))
                    for key, _ in events:
                        block = os.read(key.fd, 1 << 16)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        if key.data == "stderr":
                            available = DIAGNOSTIC_BYTES - len(diagnostic)
                            diagnostic.extend(block[:available])
                            if len(block) > available:
                                raise WorkerFailure(
                                    WorkerCode.RUNTIME,
                                    private_diagnostic=bytes(diagnostic),
                                )
                            continue
                        total += len(block)
                        if total > maximum:
                            raise WorkerFailure(
                                WorkerCode.RUNTIME,
                                private_diagnostic=b"stream output exceeded cap",
                            )
                        stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            return_code = process.wait(timeout=1)
            if return_code != 0:
                raise WorkerFailure(
                    WorkerCode.RUNTIME,
                    private_diagnostic=(
                        f"exit={return_code}\nstderr:\n".encode("ascii")
                        + bytes(diagnostic)
                    )[:DIAGNOSTIC_BYTES],
                )
            return total
        except WorkerFailure:
            if process is not None:
                _stop_process(process)
            destination.unlink(missing_ok=True)
            raise
        except (OSError, subprocess.SubprocessError):
            if process is not None:
                _stop_process(process)
            destination.unlink(missing_ok=True)
            raise WorkerFailure(
                WorkerCode.RUNTIME, private_diagnostic=bytes(diagnostic)
            ) from None


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


def _require_supported_device_adapter(profile: DevelopmentWorkerProfile) -> None:
    from carbon.reconstruction.accelerators import GPU_PROFILE

    if type(profile) is not DevelopmentWorkerProfile:
        raise WorkerFailure(WorkerCode.INVALID)
    if profile.accelerator_profile_id not in (None, GPU_PROFILE.profile_id):
        raise WorkerFailure(WorkerCode.UNSUPPORTED)


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
    _require_supported_device_adapter(worker_profile)
    if (
        cpuset != "0,1"
        or not input_directory.is_absolute()
        or input_directory.is_symlink()
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    source = str(input_directory)
    if "," in source or "\n" in source:
        raise WorkerFailure(WorkerCode.INVALID)
    arguments = [
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
        "--log-opt",
        "compress=false",
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
    if worker_profile.accelerator_profile_id is not None:
        from carbon.reconstruction.accelerators import (
            GPU_PROFILE,
            AcceleratorRole,
            worker_environment,
        )

        replacements = worker_environment(
            GPU_PROFILE, AcceleratorRole(worker_profile.accelerator_role)
        )
        for index, value in enumerate(arguments):
            if index and arguments[index - 1] == "--env":
                key = value.split("=", 1)[0]
                if key in replacements:
                    arguments[index] = f"{key}={replacements.pop(key)}"
        extras = [
            "--runtime",
            "nvidia",
            "--gpus",
            f"device={GPU_PROFILE.device_uuid}",
            "--label",
            f"carbon.accelerator.device={GPU_PROFILE.device_uuid}",
            "--label",
            f"carbon.accelerator.grant={worker_profile.accelerator_grant_digest}",
        ]
        for key, value in replacements.items():
            extras.extend(["--env", f"{key}={value}"])
        extras.extend(
            [
                "--env",
                f"NVIDIA_VISIBLE_DEVICES={GPU_PROFILE.device_uuid}",
                "--env",
                "NVIDIA_DRIVER_CAPABILITIES=compute,utility",
            ]
        )
        arguments[-1:-1] = extras
    return arguments


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
    _require_supported_device_adapter(worker_profile)
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
    expected_requests = []
    if worker_profile.accelerator_profile_id is not None:
        from carbon.reconstruction.worker.accelerator_runtime import device_request

        expected_requests = [device_request()]
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
        != {
            "Type": "local",
            "Config": {
                "compress": "false",
                "max-file": "1",
                "max-size": "1m",
            },
        }
        or host.get("PidsLimit") != PIDS_LIMIT
        or host.get("Memory") != MEMORY_BYTES
        or host.get("MemorySwap") != MEMORY_BYTES
        or host.get("NanoCpus") != CPU_COUNT * 1_000_000_000
        or host.get("CpusetCpus") != cpuset
        or host.get("ShmSize") != _SHM_BYTES
        or host.get("CapAdd")
        or sorted(host.get("CapDrop") or []) != ["ALL"]
        or host.get("Devices")
        or (host.get("DeviceRequests") or []) != expected_requests
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
    gpu_observation = None
    if worker_profile.accelerator_profile_id is not None:
        from carbon.reconstruction.accelerators import (
            GPU_PROFILE,
            AcceleratorRole,
            worker_environment,
        )
        from carbon.reconstruction.worker.accelerator_runtime import inspect_gpu_device

        env = dict(item.split("=", 1) for item in config.get("Env", []) if "=" in item)
        required = worker_environment(
            GPU_PROFILE, AcceleratorRole(worker_profile.accelerator_role)
        )
        required.update(
            NVIDIA_VISIBLE_DEVICES=GPU_PROFILE.device_uuid,
            NVIDIA_DRIVER_CAPABILITIES="compute,utility",
        )
        if (
            host.get("Runtime") != "nvidia"
            or any(env.get(k) != v for k, v in required.items())
            or env.get("LD_LIBRARY_PATH")
            or env.get("JAX_SKIP_CUDA_CONSTRAINTS_CHECK")
            or config.get("Labels", {}).get("carbon.accelerator.grant")
            != worker_profile.accelerator_grant_digest
            or config.get("Labels", {}).get("carbon.accelerator.device")
            != GPU_PROFILE.device_uuid
        ):
            raise WorkerFailure(WorkerCode.POLICY)
        gpu_observation = inspect_gpu_device(cli=cli, container_name=container_name)
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
            [
                "exec",
                container_name,
                "/bin/df",
                "--output=itotal",
                "/scratch",
            ],
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
    if gpu_observation is not None:
        evidence["schema"] = "carbon.c03.effective-controls.v2"
        evidence["accelerator"] = gpu_observation
    return tagged_sha256(_canonical(evidence)), evidence


def observe_effective_resources(
    *, cli: DockerCLI, container_name: str
) -> dict[str, object]:
    """Read exact cgroup counters where available without inferring causes."""

    exact_token(container_name)

    def read(name: str) -> str | None:
        try:
            return (
                cli.run(
                    ["exec", container_name, "/bin/cat", f"/sys/fs/cgroup/{name}"],
                    timeout=10,
                )
                .stdout.decode("ascii", "strict")
                .strip()
            )
        except (WorkerFailure, UnicodeError):
            return None

    def scalar(name: str) -> int | None:
        value = read(name)
        try:
            return None if value is None else int(value)
        except ValueError:
            return None

    def counters(name: str) -> dict[str, int] | None:
        value = read(name)
        if value is None:
            return None
        result: dict[str, int] = {}
        try:
            for line in value.splitlines():
                key, raw = line.split()
                result[exact_token(key)] = int(raw)
        except (ValueError, WorkerFailure):
            return None
        return result

    def filesystem(path: str) -> dict[str, int] | None:
        try:
            byte_lines = cli.run(
                ["exec", container_name, "/bin/df", "-B1", "--output=size,used", path],
                timeout=10,
            ).stdout.splitlines()
            inode_lines = cli.run(
                ["exec", container_name, "/bin/df", "--output=itotal,iused", path],
                timeout=10,
            ).stdout.splitlines()
            size, used = (int(item) for item in byte_lines[-1].split())
            inodes, used_inodes = (int(item) for item in inode_lines[-1].split())
            return {
                "bounded_bytes": size,
                "observed_used_bytes": used,
                "bounded_inodes": inodes,
                "observed_used_inodes": used_inodes,
            }
        except (WorkerFailure, ValueError, IndexError):
            return None

    return {
        "schema": "carbon.c03.resource-observation.v1",
        "measurement_scope": "POST_EXPORT_PRE_TERMINATION",
        "memory": {
            "current_bytes": scalar("memory.current"),
            "peak_bytes": scalar("memory.peak"),
            "events": counters("memory.events"),
            "oom_cause_rule": "memory.events oom/oom_kill only; exit status is insufficient",
        },
        "cpu": counters("cpu.stat"),
        "pids": {
            "current": scalar("pids.current"),
            "peak": scalar("pids.peak"),
        },
        "filesystem": {
            "scratch": filesystem("/scratch"),
            "shm": filesystem("/dev/shm"),
            "high_water_status": "UNAVAILABLE_WITHOUT_CONTINUOUS_SAMPLING",
        },
    }


def remove_exact_container(
    *, cli: DockerCLI, container_name: str, launch_digest: str
) -> None:
    """Stop/remove only the exact launch-labeled container and confirm absence."""
    from carbon.reconstruction.worker.accelerator_runtime import (
        finish_device_allocation,
        owns_device_allocation,
    )

    owns_accelerator = owns_device_allocation(
        container_name=container_name, launch_digest=launch_digest
    )
    try:
        value = cli.json(["inspect", container_name, "--format", "{{json .}}"])
    except WorkerFailure:
        if owns_accelerator:
            # An inspect error alone never proves absence. This also handles a
            # controller lost after rm but before release verification.
            remaining = cli.run(
                [
                    "ps",
                    "--all",
                    "--filter",
                    f"name=^/{container_name}$",
                    "--format",
                    "{{.ID}}",
                ],
                timeout=10,
            )
            if remaining.stdout.strip():
                raise WorkerFailure(WorkerCode.CLEANUP)
            finish_device_allocation(
                container_name=container_name, launch_digest=launch_digest
            )
        return
    if (
        type(value) is not dict
        or value.get("Config", {})
        .get("Labels", {})
        .get("org.opencontainers.image.carbon.c03.launch")
        != launch_digest
    ):
        raise WorkerFailure(WorkerCode.CLEANUP)
    accelerator = (
        value.get("Config", {}).get("Labels", {}).get("carbon.accelerator.device")
    )
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
            if accelerator is not None:
                from carbon.reconstruction.accelerators import GPU_PROFILE

                if accelerator != GPU_PROFILE.device_uuid:
                    raise WorkerFailure(WorkerCode.CLEANUP)
                finish_device_allocation(
                    container_name=container_name, launch_digest=launch_digest
                )
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
    "observe_effective_resources",
    "remove_exact_container",
    "spawn_watchdog",
]
