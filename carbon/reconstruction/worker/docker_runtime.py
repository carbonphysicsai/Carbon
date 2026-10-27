"""Docker/OCI mechanism for the single-host C-03 DEVELOPMENT profile."""

from __future__ import annotations

import json
import os
import platform
import selectors
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

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
    SHM_BYTES,
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

# Today's profile's shm and scratch tmpfs. A launch is created and checked at
# its own profile's (`DevelopmentWorkerProfile.effective_*`): a next version's
# larger resources (OWNER-WORKER-RESOURCES-LARGE-MODELS-01) differ.
_SHM_BYTES = SHM_BYTES
_SCRATCH_TMPFS_BYTES = SCRATCH_BYTES - _SHM_BYTES

# Only fixed battery practice opts in. The prefix is never copied to a public
# result; the carrier accepts exact enum membership in its owner-only record.
_CONTROL_PREDICATE_PREFIX = b"carbon.controls.predicate.v1:"
_T = TypeVar("_T")
_CONTROL_PREDICATES = frozenset(
    {
        "INSPECT_DOCUMENT",
        "INSPECT_SHAPE",
        "GPU_ADAPTER_RECHECK",
        "DEVICE_REQUEST_RECHECK",
        "CREATE_ARGUMENTS_RECHECK",
        "GPU_HOST_RECORD_RECHECK",
        "GPU_ENVIRONMENT_RECHECK",
        "IMAGE",
        "USER",
        "LAUNCH_LABEL",
        "ROOT_READ_ONLY",
        "PRIVILEGED",
        "NETWORK",
        "IPC",
        "PID",
        "RESTART",
        "LOG_CONFIG",
        "PIDS_LIMIT",
        "MEMORY",
        "MEMORY_SWAP",
        "CPU_QUOTA",
        "CPUSET",
        "SHM",
        "CAP_ADD",
        "CAP_DROP",
        "DEVICES",
        "DEVICE_REQUESTS",
        "PORT_BINDINGS",
        "PUBLISH_PORTS",
        "NO_NEW_PRIVILEGES",
        "NOFILE_ULIMIT",
        "CORE_ULIMIT",
        "INPUT_MOUNT_COUNT",
        "INPUT_MOUNT_SOURCE",
        "INPUT_MOUNT_READ_ONLY",
        "UNEXPECTED_MOUNT",
        "SCRATCH_TMPFS_OPTIONS",
        "CREATE_LAUNCH_LABEL",
        "HOST_DEVICE_RECORD",
        "GPU_RUNTIME",
        "GPU_ENVIRONMENT",
        "GPU_LD_LIBRARY_PATH",
        "GPU_SKIP_CUDA_CHECK",
        "GPU_DEVICE_LABEL",
        "GPU_AUTHORITY_LABEL",
        "GPU_CONFLICTING_AUTHORITY_LABEL",
        "GPU_POLICY_LABEL",
        "GPU_DEVICE_OBSERVATION",
        "PROCESS_CAPABILITIES",
        "PROCESS_NO_NEW_PRIVILEGES",
        "PROCESS_SECCOMP",
        "KERNEL_CPUSET_FORMAT",
        "KERNEL_CPU_MAX_SHAPE",
        "KERNEL_CPU_QUOTA",
        "KERNEL_CPUSET",
        "KERNEL_MEMORY",
        "KERNEL_SWAP",
        "KERNEL_PIDS",
        "SCRATCH_BYTES",
        "SCRATCH_INODES",
        "SHM_BYTES",
        "SCRATCH_PLUS_SHM",
        "UNCLASSIFIED",
    }
)


def controls_predicate(error: WorkerFailure) -> str | None:
    """Decode only a known fixed name; never interpret arbitrary diagnostics."""
    if error.code is not WorkerCode.POLICY:
        return None
    raw = error.private_diagnostic
    if not raw.startswith(_CONTROL_PREDICATE_PREFIX):
        return None
    try:
        value = raw[len(_CONTROL_PREDICATE_PREFIX) :].decode("ascii", "strict")
    except UnicodeError:
        return None
    return value if value in _CONTROL_PREDICATES else None


def _policy_refusal(diagnose: bool, name: str) -> WorkerFailure:
    if not diagnose:
        return WorkerFailure(WorkerCode.POLICY)
    selected = name if name in _CONTROL_PREDICATES else "UNCLASSIFIED"
    return WorkerFailure(
        WorkerCode.POLICY,
        private_diagnostic=_CONTROL_PREDICATE_PREFIX + selected.encode("ascii"),
    )


def _installed_device_uuid(host_device) -> str:
    """The device identity of whichever record is installed, strict or the
    miner lane's. Used only to match a container being cleaned up to this host's
    device; it grants nothing."""
    try:
        return host_device().device_uuid
    except WorkerFailure:
        from carbon.reconstruction.worker.accelerator_runtime import (
            miner_host_device,
        )

        return miner_host_device().device_uuid


def _diagnose_policy_recheck(
    check: Callable[[], _T], *, diagnose: bool, name: str
) -> _T:
    """Name a nested policy refusal only for the private practice diagnostic."""
    try:
        return check()
    except WorkerFailure as error:
        if (
            diagnose
            and error.code is WorkerCode.POLICY
            and error.private_diagnostic == b""
        ):
            raise _policy_refusal(True, name) from None
        raise


def _first_failed(checks: tuple[tuple[str, Callable[[], bool]], ...]) -> str:
    """Diagnose an already-refused control without changing its policy path."""
    try:
        for name, fails in checks:
            if fails():
                return name
    except Exception:  # noqa: BLE001 - diagnosis must not replace refusal
        return "UNCLASSIFIED"
    return "UNCLASSIFIED"


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


#: The directory every Docker CLI call runs in. A Docker CLI (29.6.1) resolves some arguments against its
#: working directory (`docker cp CONTAINER:/x -` stats `./-`), so a controller whose own cwd is unreadable
#: (a service started from a private directory) failed with `stat -: permission denied`. The root is readable
#: by every user, and no controller call names a relative path.
DOCKER_CWD = Path(os.sep)


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
        # Recorded image id -> (exact tag, store-neutral fingerprint), only for a parent a containerd store (Docker 29)
        # does not answer to by its recorded config digest and whose fingerprint was verified (register_parent_alias).
        self._aliases: dict[str, tuple[str, str]] = {}
        # Aliases the install recorded, not yet checked against the live store: each is verified (the tag's
        # image must have exactly the recorded fingerprint) the first time the id's direct lookup fails.
        self._candidates: dict[str, tuple[str, str]] = {}
        # Every Docker call in this product sees this install's recorded aliases, so a check that is handed a plain
        # `DockerCLI()` (the carrier's host-readiness check among them) finds a parent a containerd store never knew
        # by its recorded id. A lookup only: each alias still needs the live image's exact fingerprint.
        self.load_installed_aliases()

    def register_parent_alias(
        self, image_id: str, store_tag: str | None, store_fingerprint: str | None
    ) -> bool:
        """Let `inspect_image` find `image_id` by its recorded exact tag, but only when the daemon does not answer to
        the id AND the tag's image has exactly the recorded fingerprint (layers and run configuration). Returns True
        when an alias is in force; False (and nothing changes) when the id answers directly or there is no matching
        record: the strict lookup then stands (fails closed, as before)."""
        try:
            self.json(["image", "inspect", image_id, "--format", "{{json .}}"])
            return False
        except WorkerFailure:
            pass
        if _image_by_recorded_tag(self, store_fingerprint, store_tag) is None:
            return False
        self._aliases[image_id] = (store_tag, store_fingerprint)
        return True

    @classmethod
    def from_installed(cls, state_dir=None) -> DockerCLI:
        """A CLI that knows this install's recorded parent aliases (`parent-aliases.json` in the state
        directory). Each alias is checked against the live store only when the id's own lookup fails, and
        only by exact tag and fingerprint: with no record the strict lookup stands."""
        cli = cls()
        cli.load_installed_aliases(state_dir)
        return cli

    def load_installed_aliases(self, state_dir=None) -> None:
        """Read the install's recorded aliases (see `from_installed`)."""
        from carbon.reconstruction.worker.image_fingerprint import read_aliases

        self._candidates = read_aliases(state_dir)

    def alias_of(self, image_id: str) -> tuple[str, str] | None:
        recorded = self._aliases.get(image_id)
        if recorded is None and image_id in self._candidates:
            tag, value = self._candidates[image_id]
            if _image_by_recorded_tag(self, value, tag) is not None:
                recorded = self._aliases[image_id] = (tag, value)
        return recorded

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
            cwd=DOCKER_CWD,
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
                cwd=DOCKER_CWD,
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


def _image_by_recorded_tag(cli, store_fingerprint, store_tag):
    """The inspect document of the image under `store_tag` when its store-neutral fingerprint equals the recorded one
    exactly, else None. One fingerprint format and function with the remote worker check (image_fingerprint).
    """
    import hmac

    from carbon.reconstruction.worker.image_fingerprint import (
        FINGERPRINT_FORMAT,
        PARENT_TAG,
        fingerprint_of_output,
    )

    if (
        type(store_fingerprint) is not str
        or type(store_tag) is not str
        or not PARENT_TAG.fullmatch(store_tag)
    ):
        return None
    try:
        printed = cli.run(
            ["image", "inspect", "--format", FINGERPRINT_FORMAT, store_tag]
        ).stdout
        if not printed.strip() or not hmac.compare_digest(
            fingerprint_of_output(printed), store_fingerprint
        ):
            return None
        document = cli.json(["image", "inspect", store_tag, "--format", "{{json .}}"])
    except WorkerFailure:
        return None
    return document if type(document) is dict else None


def inspect_image(cli, image_id):
    """(inspect document, answered_by_alias) of an image by its recorded id; on a store that does not answer to the id,
    the verified alias of `register_parent_alias` is used (and the document's own Id is then the store's). Raises
    WorkerFailure when neither finds it."""
    try:
        return cli.json(["image", "inspect", image_id, "--format", "{{json .}}"]), False
    except Exception:
        recorded = getattr(cli, "alias_of", lambda _id: None)(image_id)
        document = (
            _image_by_recorded_tag(cli, recorded[1], recorded[0])
            if recorded is not None
            else None
        )
        if type(document) is not dict:
            raise
        return document, True


def doctor(
    *,
    image_id: str | None = None,
    image_identity: WorkerImageIdentity | None = None,
    cli: DockerCLI | None = None,
    worker_profile: DevelopmentWorkerProfile | None = None,
    store_fingerprint: str | None = None,
    store_tag: str | None = None,
) -> DockerDoctor:
    """Read-only eligibility check; never changes daemon or host configuration.

    `store_fingerprint` and `store_tag` (recorded at install, see image_fingerprint) let the same image be found by its
    exact tag when the daemon's image store does not answer to `image_id`; without them an unanswered id fails closed.

    Capacity and the cpuset are sized for ``worker_profile`` when given (a next
    version's larger resources), else for today's C-03 profile."""
    from carbon.reconstruction.host_execution import resolve_cpuset
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

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
    cpu_count = (
        CPU_COUNT if worker_profile is None else worker_profile.effective_cpu_count
    )
    memory_bytes = (
        MEMORY_BYTES
        if worker_profile is None
        else worker_profile.effective_memory_bytes
    )
    cgroup_version = str(info.get("CgroupVersion", ""))
    security = info.get("SecurityOptions")
    if (
        type(ncpu) is not int
        or ncpu < cpu_count
        or type(memory) is not int
        or memory < memory_bytes + 1024**3
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
        by_tag = False
        try:
            exact_digest(image_id)
            image = cli.json(["image", "inspect", image_id, "--format", "{{json .}}"])
        except WorkerFailure:
            # A containerd image store (Docker 29) does not answer to the config digest. Only with the fingerprint
            # recorded at install, and only by the exact tag, is the same image accepted: its layers and run
            # configuration must equal the record exactly. No record, no fallback (fails closed, as before).
            if store_tag is None and store_fingerprint is None:
                recorded = getattr(cli, "alias_of", lambda _id: None)(image_id)
                if recorded is not None:
                    store_tag, store_fingerprint = recorded
            image = _image_by_recorded_tag(cli, store_fingerprint, store_tag)
            by_tag = image is not None
            if image is None:
                return DockerDoctor(
                    False, "worker.doctor.image_unavailable", {"info": info}, None
                )
        if (
            type(image) is not dict
            or (not by_tag and image.get("Id") != image_id)
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
        # Resolved from this host, and from an operator-installed execution
        # record when one exists, rather than named here. A literal in this file
        # is the defect this replaces, and writing a different literal would
        # only respell it.
        resolve_cpuset(logical_cpus=ncpu, root=HOST_ROOT, count=cpu_count),
    )


def _require_supported_device_adapter(profile: DevelopmentWorkerProfile) -> None:
    from carbon.reconstruction.accelerators import GPU_PROFILE

    if type(profile) is not DevelopmentWorkerProfile:
        raise WorkerFailure(WorkerCode.INVALID)
    if profile.accelerator_profile_id not in (None, GPU_PROFILE.profile_id):
        raise WorkerFailure(WorkerCode.UNSUPPORTED)


STRICT_GRANT_LABEL = "carbon.accelerator.grant"
LOCAL_APPROVAL_LABEL = "carbon.accelerator.approval"
SELF_SERVICE_RECORD_LABEL = "carbon.accelerator.host-record"


def _authority_label_key(worker_profile) -> str:
    """Which container label carries this profile's accelerator authority."""
    from carbon.reconstruction.worker.model import (
        LOCAL_DEVELOPMENT_AUTHORITY,
        MINER_HOST_AUTHORITY,
    )

    if worker_profile.accelerator_authority == MINER_HOST_AUTHORITY:
        return SELF_SERVICE_RECORD_LABEL
    if worker_profile.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
        return LOCAL_APPROVAL_LABEL
    return STRICT_GRANT_LABEL


def _other_authority_label_key(worker_profile) -> str:
    """The label this profile must NOT carry, so the two can never be confused."""
    if _authority_label_key(worker_profile) == STRICT_GRANT_LABEL:
        return LOCAL_APPROVAL_LABEL
    return STRICT_GRANT_LABEL


def _accelerator_authority_label(worker_profile) -> str:
    key = _authority_label_key(worker_profile)
    return f"{key}={worker_profile.accelerator_grant_digest}"


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
    from carbon.reconstruction.host_execution import parse_cpuset

    # Well-formed, not a specific pair of cores. Requiring the literal "0,1"
    # made two concurrent reconstructions impossible on any host, because both
    # demanded the same two cores. Which cores a worker gets is resolved from
    # the host; that it is a real, non-empty, non-repeating set is checked here.
    parse_cpuset(cpuset)  # refuses a malformed or empty set
    if not input_directory.is_absolute() or input_directory.is_symlink():
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
        str(worker_profile.effective_memory_bytes),
        "--memory-swap",
        str(worker_profile.effective_memory_bytes),
        "--cpus",
        str(worker_profile.effective_cpu_count),
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
        str(worker_profile.effective_shm_bytes),
        "--tmpfs",
        (
            "/scratch:rw,nosuid,nodev,noexec,size="
            f"{worker_profile.effective_scratch_tmpfs_bytes},"
            f"nr_inodes={SCRATCH_INODES},mode=700,"
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
        f"OMP_NUM_THREADS={worker_profile.effective_cpu_count}",
        "--env",
        f"OPENBLAS_NUM_THREADS={worker_profile.effective_cpu_count}",
        "--env",
        f"MKL_NUM_THREADS={worker_profile.effective_cpu_count}",
        image_id,
    ]
    if worker_profile.accelerator_profile_id is not None:
        from carbon.reconstruction.accelerators import (
            GPU_PROFILE,
            AcceleratorRole,
            worker_environment,
        )
        from carbon.reconstruction.worker.accelerator_runtime import (
            host_device,
            miner_host_device,
        )

        # The device comes from the launch's own profile, which the controller
        # filled from the installed host record. Nothing here reads a device
        # identity compiled into Carbon.
        device = worker_profile.accelerator_device_uuid
        record = (
            miner_host_device()
            if worker_profile.accelerator_role == AcceleratorRole.MINER_RESEARCH.value
            else host_device()
        )
        if device != record.device_uuid:
            raise WorkerFailure(WorkerCode.POLICY)
        replacements = worker_environment(
            GPU_PROFILE,
            AcceleratorRole(worker_profile.accelerator_role),
            host_device=record,
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
            f"driver=nvidia,device={device}",
            "--label",
            f"carbon.accelerator.device={device}",
            "--label",
            _accelerator_authority_label(worker_profile),
        ]
        for key, value in replacements.items():
            extras.extend(["--env", f"{key}={value}"])
        extras.extend(
            [
                "--env",
                f"NVIDIA_VISIBLE_DEVICES={device}",
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
    diagnose_policy: bool = False,
) -> tuple[str, dict[str, object]]:
    """Verify daemon config and kernel-visible controls after create/start."""
    _diagnose_policy_recheck(
        lambda: _require_supported_device_adapter(worker_profile),
        diagnose=diagnose_policy,
        name="GPU_ADAPTER_RECHECK",
    )
    value = cli.json(["inspect", container_name, "--format", "{{json .}}"])
    if type(value) is not dict:
        raise _policy_refusal(diagnose_policy, "INSPECT_DOCUMENT")
    host = value.get("HostConfig")
    config = value.get("Config")
    state = value.get("State")
    mounts = value.get("Mounts")
    if (
        not all(type(item) is dict for item in (host, config, state))
        or type(mounts) is not list
    ):
        raise _policy_refusal(diagnose_policy, "INSPECT_SHAPE")
    expected_requests = []
    if worker_profile.accelerator_profile_id is not None:
        from carbon.reconstruction.worker.accelerator_runtime import device_request

        expected_requests = [
            _diagnose_policy_recheck(
                device_request,
                diagnose=diagnose_policy,
                name="DEVICE_REQUEST_RECHECK",
            )
        ]
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
        f"size={worker_profile.effective_scratch_tmpfs_bytes}",
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
        or host.get("Memory") != worker_profile.effective_memory_bytes
        or host.get("MemorySwap") != worker_profile.effective_memory_bytes
        or host.get("NanoCpus") != worker_profile.effective_cpu_count * 1_000_000_000
        or host.get("CpusetCpus") != cpuset
        or host.get("ShmSize") != worker_profile.effective_shm_bytes
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
        not in _diagnose_policy_recheck(
            lambda: create_arguments(
                container_name=container_name,
                image_id=image_id,
                input_directory=input_directory,
                cpuset=cpuset,
                launch_digest=launch_digest,
                worker_profile=worker_profile,
            ),
            diagnose=diagnose_policy,
            name="CREATE_ARGUMENTS_RECHECK",
        )
    ):
        predicate = "UNCLASSIFIED"
        if diagnose_policy:
            predicate = _first_failed(
                (
                    ("IMAGE", lambda: value.get("Image") != image_id),
                    (
                        "USER",
                        lambda: config.get("User") != f"{WORKER_UID}:{WORKER_GID}",
                    ),
                    (
                        "LAUNCH_LABEL",
                        lambda: config.get("Labels", {}).get(
                            "org.opencontainers.image.carbon.c03.launch"
                        )
                        != launch_digest,
                    ),
                    ("ROOT_READ_ONLY", lambda: not host.get("ReadonlyRootfs")),
                    ("PRIVILEGED", lambda: bool(host.get("Privileged"))),
                    ("NETWORK", lambda: host.get("NetworkMode") != "none"),
                    ("IPC", lambda: host.get("IpcMode") not in ("private", "")),
                    ("PID", lambda: host.get("PidMode") not in ("", "private")),
                    (
                        "RESTART",
                        lambda: host.get("RestartPolicy", {}).get("Name") != "no",
                    ),
                    (
                        "LOG_CONFIG",
                        lambda: host.get("LogConfig")
                        != {
                            "Type": "local",
                            "Config": {
                                "compress": "false",
                                "max-file": "1",
                                "max-size": "1m",
                            },
                        },
                    ),
                    ("PIDS_LIMIT", lambda: host.get("PidsLimit") != PIDS_LIMIT),
                    (
                        "MEMORY",
                        lambda: host.get("Memory")
                        != worker_profile.effective_memory_bytes,
                    ),
                    (
                        "MEMORY_SWAP",
                        lambda: host.get("MemorySwap")
                        != worker_profile.effective_memory_bytes,
                    ),
                    (
                        "CPU_QUOTA",
                        lambda: host.get("NanoCpus")
                        != worker_profile.effective_cpu_count * 1_000_000_000,
                    ),
                    ("CPUSET", lambda: host.get("CpusetCpus") != cpuset),
                    (
                        "SHM",
                        lambda: host.get("ShmSize")
                        != worker_profile.effective_shm_bytes,
                    ),
                    ("CAP_ADD", lambda: bool(host.get("CapAdd"))),
                    ("CAP_DROP", lambda: sorted(host.get("CapDrop") or []) != ["ALL"]),
                    ("DEVICES", lambda: bool(host.get("Devices"))),
                    (
                        "DEVICE_REQUESTS",
                        lambda: (host.get("DeviceRequests") or []) != expected_requests,
                    ),
                    ("PORT_BINDINGS", lambda: bool(host.get("PortBindings"))),
                    ("PUBLISH_PORTS", lambda: bool(host.get("PublishAllPorts"))),
                    (
                        "NO_NEW_PRIVILEGES",
                        lambda: "no-new-privileges=true" not in security,
                    ),
                    (
                        "NOFILE_ULIMIT",
                        lambda: ulimits.get("nofile") != (NOFILE_LIMIT, NOFILE_LIMIT),
                    ),
                    ("CORE_ULIMIT", lambda: ulimits.get("core") != (0, 0)),
                    ("INPUT_MOUNT_COUNT", lambda: len(input_mounts) != 1),
                    (
                        "INPUT_MOUNT_SOURCE",
                        lambda: input_mounts[0].get("Source") != str(input_directory),
                    ),
                    (
                        "INPUT_MOUNT_READ_ONLY",
                        lambda: input_mounts[0].get("RW") is not False,
                    ),
                    ("UNEXPECTED_MOUNT", lambda: bool(unexpected_mounts)),
                    ("SCRATCH_TMPFS_OPTIONS", lambda: tmpfs_options != expected_tmpfs),
                    (
                        "CREATE_LAUNCH_LABEL",
                        lambda: expected_label
                        not in create_arguments(
                            container_name=container_name,
                            image_id=image_id,
                            input_directory=input_directory,
                            cpuset=cpuset,
                            launch_digest=launch_digest,
                            worker_profile=worker_profile,
                        ),
                    ),
                )
            )
        raise _policy_refusal(diagnose_policy, predicate)
    gpu_observation = None
    if worker_profile.accelerator_profile_id is not None:
        from carbon.reconstruction.accelerators import (
            GPU_PROFILE,
            AcceleratorRole,
            worker_environment,
        )
        from carbon.reconstruction.worker.accelerator_runtime import (
            host_device,
            inspect_gpu_device,
            miner_host_device,
        )

        record = _diagnose_policy_recheck(
            (
                miner_host_device
                if worker_profile.accelerator_role
                == AcceleratorRole.MINER_RESEARCH.value
                else host_device
            ),
            diagnose=diagnose_policy,
            name="GPU_HOST_RECORD_RECHECK",
        )
        device = worker_profile.accelerator_device_uuid
        if device != record.device_uuid:
            raise _policy_refusal(diagnose_policy, "HOST_DEVICE_RECORD")
        env = dict(item.split("=", 1) for item in config.get("Env", []) if "=" in item)
        required = _diagnose_policy_recheck(
            lambda: worker_environment(
                GPU_PROFILE,
                AcceleratorRole(worker_profile.accelerator_role),
                host_device=record,
            ),
            diagnose=diagnose_policy,
            name="GPU_ENVIRONMENT_RECHECK",
        )
        required.update(
            NVIDIA_VISIBLE_DEVICES=device,
            NVIDIA_DRIVER_CAPABILITIES="compute,utility",
        )
        if (
            host.get("Runtime") != "nvidia"
            or any(env.get(k) != v for k, v in required.items())
            or env.get("LD_LIBRARY_PATH")
            or env.get("JAX_SKIP_CUDA_CONSTRAINTS_CHECK")
            or (config.get("Labels") or {}).get("carbon.accelerator.device") != device
            or (config.get("Labels") or {}).get(_authority_label_key(worker_profile))
            != worker_profile.accelerator_grant_digest
            # Each authority has exactly its own label namespace. A second
            # authority label must never silently downgrade the checks.
            or any(
                (config.get("Labels") or {}).get(key) is not None
                for key in {
                    STRICT_GRANT_LABEL,
                    LOCAL_APPROVAL_LABEL,
                    SELF_SERVICE_RECORD_LABEL,
                }
                - {_authority_label_key(worker_profile)}
            )
        ):
            predicate = "UNCLASSIFIED"
            if diagnose_policy:
                predicate = _first_failed(
                    (
                        ("GPU_RUNTIME", lambda: host.get("Runtime") != "nvidia"),
                        (
                            "GPU_ENVIRONMENT",
                            lambda: any(env.get(k) != v for k, v in required.items()),
                        ),
                        (
                            "GPU_LD_LIBRARY_PATH",
                            lambda: bool(env.get("LD_LIBRARY_PATH")),
                        ),
                        (
                            "GPU_SKIP_CUDA_CHECK",
                            lambda: bool(env.get("JAX_SKIP_CUDA_CONSTRAINTS_CHECK")),
                        ),
                        (
                            "GPU_DEVICE_LABEL",
                            lambda: (config.get("Labels") or {}).get(
                                "carbon.accelerator.device"
                            )
                            != device,
                        ),
                        (
                            "GPU_AUTHORITY_LABEL",
                            lambda: (config.get("Labels") or {}).get(
                                _authority_label_key(worker_profile)
                            )
                            != worker_profile.accelerator_grant_digest,
                        ),
                        (
                            "GPU_CONFLICTING_AUTHORITY_LABEL",
                            lambda: any(
                                (config.get("Labels") or {}).get(key) is not None
                                for key in {
                                    STRICT_GRANT_LABEL,
                                    LOCAL_APPROVAL_LABEL,
                                    SELF_SERVICE_RECORD_LABEL,
                                }
                                - {_authority_label_key(worker_profile)}
                            ),
                        ),
                    )
                )
            raise _policy_refusal(diagnose_policy, predicate)
        from carbon.reconstruction.worker.model import (
            LOCAL_DEVELOPMENT_AUTHORITY,
            MINER_HOST_AUTHORITY,
        )

        if worker_profile.accelerator_authority == MINER_HOST_AUTHORITY:
            # The label and the complete profile digest must agree; a foreign
            # authority cannot be relabelled as host self-service.
            if (config.get("Labels") or {}).get(
                "org.opencontainers.image.carbon.c03.policy"
            ) != worker_profile.digest:
                raise _policy_refusal(diagnose_policy, "GPU_POLICY_LABEL")
            from carbon.reconstruction.worker.accelerator_runtime import (
                inspect_self_service_device,
            )

            try:
                gpu_observation = inspect_self_service_device(
                    cli=cli,
                    container_name=container_name,
                    worker_profile=worker_profile,
                )
            except WorkerFailure as error:
                if diagnose_policy and error.code is WorkerCode.POLICY:
                    raise _policy_refusal(True, "GPU_DEVICE_OBSERVATION") from None
                raise
        else:
            gpu_observation = inspect_gpu_device(
                cli=cli,
                container_name=container_name,
                # The approved diagnostic plan, not the approval record digest.
                # accelerator_grant_digest identifies the authority record; the plan
                # it authorizes is a separate identity and the observation records
                # that one.
                development_plan_digest=(
                    worker_profile.accelerator_plan_digest
                    if worker_profile.accelerator_authority
                    == LOCAL_DEVELOPMENT_AUTHORITY
                    else None
                ),
            )
    status = cli.run(
        ["exec", container_name, "/bin/cat", "/proc/1/status"], timeout=10
    ).stdout.decode("ascii", "replace")
    facts = {}
    for line in status.splitlines():
        if line.startswith(("CapEff:", "NoNewPrivs:", "Seccomp:")):
            key, value_text = line.split(":", 1)
            facts[key] = value_text.strip()
    if facts != {"CapEff": "0000000000000000", "NoNewPrivs": "1", "Seccomp": "2"}:
        predicate = "UNCLASSIFIED"
        if diagnose_policy:
            predicate = _first_failed(
                (
                    (
                        "PROCESS_CAPABILITIES",
                        lambda: facts.get("CapEff") != "0000000000000000",
                    ),
                    (
                        "PROCESS_NO_NEW_PRIVILEGES",
                        lambda: facts.get("NoNewPrivs") != "1",
                    ),
                    ("PROCESS_SECCOMP", lambda: facts.get("Seccomp") != "2"),
                )
            )
        raise _policy_refusal(diagnose_policy, predicate)
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
    from carbon.reconstruction.host_execution import parse_cpuset

    cpu_quota = cgroup["cpu.max"].split()
    # What the kernel reports must equal what this launch actually asked for -
    # not a fixed pair of cores. Both sides are parsed into the set they denote,
    # so an equivalent spelling compares equal and a different allocation does
    # not, and the quota is checked against the size of that allocation.
    eligible = set(parse_cpuset(cpuset))
    try:
        observed_cpuset = set(parse_cpuset(cgroup["cpuset.cpus.effective"]))
    except WorkerFailure:
        raise _policy_refusal(diagnose_policy, "KERNEL_CPUSET_FORMAT") from None
    if (
        len(cpu_quota) != 2
        or int(cpu_quota[0]) != len(eligible) * int(cpu_quota[1])
        or observed_cpuset != eligible
        or cgroup["memory.max"] != str(worker_profile.effective_memory_bytes)
        or cgroup["memory.swap.max"] != "0"
        or cgroup["pids.max"] != str(PIDS_LIMIT)
    ):
        predicate = "UNCLASSIFIED"
        if diagnose_policy:
            predicate = _first_failed(
                (
                    ("KERNEL_CPU_MAX_SHAPE", lambda: len(cpu_quota) != 2),
                    (
                        "KERNEL_CPU_QUOTA",
                        lambda: int(cpu_quota[0]) != len(eligible) * int(cpu_quota[1]),
                    ),
                    ("KERNEL_CPUSET", lambda: observed_cpuset != eligible),
                    (
                        "KERNEL_MEMORY",
                        lambda: cgroup["memory.max"]
                        != str(worker_profile.effective_memory_bytes),
                    ),
                    ("KERNEL_SWAP", lambda: cgroup["memory.swap.max"] != "0"),
                    ("KERNEL_PIDS", lambda: cgroup["pids.max"] != str(PIDS_LIMIT)),
                )
            )
        raise _policy_refusal(diagnose_policy, predicate)
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
    scratch_limit = worker_profile.effective_scratch_tmpfs_bytes
    shm_limit = worker_profile.effective_shm_bytes
    storage_limit = worker_profile.effective_storage_bytes
    if (
        scratch_size > scratch_limit
        or scratch_inodes > SCRATCH_INODES
        or shm_size > shm_limit
        or scratch_size + shm_size > storage_limit
    ):
        predicate = "UNCLASSIFIED"
        if diagnose_policy:
            predicate = _first_failed(
                (
                    ("SCRATCH_BYTES", lambda: scratch_size > scratch_limit),
                    ("SCRATCH_INODES", lambda: scratch_inodes > SCRATCH_INODES),
                    ("SHM_BYTES", lambda: shm_size > shm_limit),
                    (
                        "SCRATCH_PLUS_SHM",
                        lambda: scratch_size + shm_size > storage_limit,
                    ),
                )
            )
        raise _policy_refusal(diagnose_policy, predicate)
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
        allocation_authority,
        owns_device_allocation,
    )
    from carbon.reconstruction.worker.model import TASK_OWNED_AUTHORITIES

    owns_accelerator = owns_device_allocation(
        container_name=container_name, launch_digest=launch_digest
    )

    def finish_allocation() -> None:
        """Complete the allocation under the authority that created it.

        A task-owned allocation - development or miner lane - completes without
        claiming whole-device release, because neither ever had the evidence
        that claim needs. A strict allocation still goes through verified
        release. Neither may complete the other's allocation.
        """
        from carbon.reconstruction.worker.accelerator_runtime import (
            finish_device_allocation,
            finish_local_device_allocation,
        )

        authority = allocation_authority(
            container_name=container_name, launch_digest=launch_digest
        )
        if authority in TASK_OWNED_AUTHORITIES:
            finish_local_device_allocation(
                container_name=container_name, launch_digest=launch_digest
            )
            return
        finish_device_allocation(
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
            finish_allocation()
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
                from carbon.reconstruction.worker.accelerator_runtime import (
                    host_device,
                )

                if accelerator != _installed_device_uuid(host_device):
                    raise WorkerFailure(WorkerCode.CLEANUP)
                finish_allocation()
            return
        time.sleep(0.1)
    raise WorkerFailure(WorkerCode.CLEANUP)


def spawn_watchdog(
    *,
    container_name: str,
    launch_digest: str,
    deadline_unix: float,
    intent_path: Path | None = None,
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
                "-B",
                "-m",
                "carbon.reconstruction.worker.watchdog",
                container_name,
                launch_digest,
                str(deadline_unix),
                *([] if intent_path is None else [str(intent_path)]),
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
