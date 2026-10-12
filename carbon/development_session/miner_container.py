"""The container a miner's own research runs in: isolated, and not limited.

Owner direction (23 September 2026): the research environment is the miner's
machine, cost, time and choice, so Carbon imposes no CPU, memory, process,
file-descriptor, scratch or wall-clock limit on it. What stays is isolation,
which is not a limit on the miner's resources but the separation between
hostile research code and the controller that records its results: no network,
a read-only image, no capabilities, no privilege escalation, a non-root user,
and nothing mounted but the run's own input (read-only) and scratch.

Carbon's own operator host is the one exception: it installs a resource
profile (`load_host_profile`; INTERNAL-RESOURCE-PROFILE-01, delivered to every
process on that host by LANE-RESOURCE-BOUND-01), and its Level 4 hostile-model
probe and staging sessions refuse to start without one
(`require_host_profile`). Nothing is installed on a miner's machine.

This is a separate lane from the validator's grading worker in
`carbon.reconstruction.worker.docker_runtime`, which keeps every one of its
limits. The two share no argument builder: the miner lane cannot reach the
validator's settings, and the validator's cannot be loosened through this one.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from carbon.development_session.profile import canonical, digest
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
#: An NVIDIA device UUID, a whole GPU or a MIG instance (`MIG-<uuid>`, as
#: `nvidia-smi -L` lists it today): the only device a miner-lane container may
#: hold.
_GPU_UUID = re.compile(r"(?:GPU|MIG)-[0-9a-fA-F-]{8,64}")
#: What attaching it adds, and nothing else (RSURF-D20).
GPU_CAPABILITIES = "compute,utility"
#: Carbon's own operator host may bound this lane for its internal runs
#: (INTERNAL-RESOURCE-PROFILE-01): a protection that keeps the research free
#: while sharing Carbon's host. It is read only from an owner-only file the
#: host's operator names in this variable; a miner's own machine sets nothing,
#: so its research stays unlimited exactly as before.
RESOURCE_PROFILE_ENV = "CARBON_RESEARCH_RESOURCE_PROFILE"
#: LANE-RESOURCE-BOUND-01: where Carbon's own host installs the same file, so
#: a process started without the variable (an MCP door another session starts
#: through `wsl.exe ... env PYTHONPATH=...`, or the detached supervisors it
#: spawns) is bounded too. Relative to the process user's home; read only when
#: the variable is unset and the file exists. A miner's machine has nothing
#: there, so its research stays unlimited exactly as before.
RESOURCE_PROFILE_FALLBACK = Path(".config", "carbon", "research-resource-profile.json")
RESOURCE_PROFILE_SCHEMA = "carbon.miner-research.resource-profile.v1"
#: The closed refusal codes of a Carbon-operated hostile-code path that must
#: never start unbounded (`require_host_profile`).
RESOURCE_PROFILE_REQUIRED = "resource_profile_required"
RESOURCE_PROFILE_INVALID = "resource_profile_invalid"
_PROFILE_FIELDS = ("cpus", "memory_bytes", "pids_limit", "nofile")
_PROFILE_LABEL = "carbon.resource-profile"


@dataclass(frozen=True)
class ResourceProfile:
    """An operator's bounds for the miner lane on Carbon's own host: whole
    CPUs, memory in bytes (swap included), processes and open files. Each is
    a positive integer; there is no default and no Carbon-chosen value."""

    cpus: int
    memory_bytes: int
    pids_limit: int
    nofile: int

    def __post_init__(self):
        for name in _PROFILE_FIELDS:
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise WorkerFailure(WorkerCode.INVALID)

    def record(self):
        return {
            "schema": RESOURCE_PROFILE_SCHEMA,
            **{name: getattr(self, name) for name in _PROFILE_FIELDS},
        }

    def digest(self):
        return digest(canonical(self.record()))


def load_host_profile(environ=None):
    """The host's resource profile, or None when the operator installs none.

    The file named in `RESOURCE_PROFILE_ENV` when it is set; otherwise
    `~/.config/carbon/research-resource-profile.json` when that exists
    (LANE-RESOURCE-BOUND-01). The variable takes precedence: a named file is
    the only one read, and the fallback is never consulted beside it.

    Fail closed: a file that is not a regular, owner-only file owned by this
    user, or whose record is not exactly the v1 schema, refuses the launch
    (POLICY) rather than running unbounded on a host that asked for bounds.
    Both locations are held to the same rules."""
    environ = os.environ if environ is None else environ
    named = environ.get(RESOURCE_PROFILE_ENV)
    if named:
        return _read_profile(Path(named))
    fallback = _fallback_profile(environ)
    if fallback is None:
        return None
    try:
        fallback.lstat()
    except (FileNotFoundError, NotADirectoryError):
        # Nothing installed: a miner's machine, exactly as before.
        return None
    except OSError:
        raise WorkerFailure(WorkerCode.POLICY) from None
    return _read_profile(fallback)


def _process_home():
    """This process's home: `HOME`, else the password database's entry."""
    home = os.environ.get("HOME")
    if home:
        return home
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError):
        return None


def _fallback_profile(environ):
    """The well-known profile path under the home `environ` gives (this
    process's own home for the process environment), or None without one."""
    home = _process_home() if environ is os.environ else environ.get("HOME")
    if not home or not Path(home).is_absolute():
        return None
    return Path(home) / RESOURCE_PROFILE_FALLBACK


def _read_profile(path):
    try:
        info = path.lstat()
        if (
            not path.is_absolute()
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise WorkerFailure(WorkerCode.POLICY)
        document = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise WorkerFailure(WorkerCode.POLICY) from None
    if (
        type(document) is not dict
        or set(document) != {"schema", *_PROFILE_FIELDS}
        or document["schema"] != RESOURCE_PROFILE_SCHEMA
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    return ResourceProfile(**{name: document[name] for name in _PROFILE_FIELDS})


class ResourceProfileRefused(ValueError):
    """A Carbon-operated hostile-code path refused to start: no host resource
    profile is in force (`RESOURCE_PROFILE_REQUIRED`), or the installed one
    is unreadable or malformed (`RESOURCE_PROFILE_INVALID`)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require_host_profile(environ=None):
    """The host's profile, for a Carbon-operated path that runs hostile code
    in this lane (the Level 4 hostile-model probe and staging sessions); it
    refuses to start without one (LANE-RESOURCE-BOUND-01).

    Never called on a miner's own research, which `load_host_profile` alone
    governs: with nothing installed it stays unlimited."""
    try:
        profile = load_host_profile(environ)
    except WorkerFailure:
        raise ResourceProfileRefused(RESOURCE_PROFILE_INVALID) from None
    if profile is None:
        raise ResourceProfileRefused(RESOURCE_PROFILE_REQUIRED)
    return profile


#: The free space a Carbon-operated Level 4-5 session needs on the filesystem
#: holding scratch before it starts (LANE-RESOURCE-BOUND-01): several capped
#: runs and the host's other sessions fit, and a full disk would make the
#: shared WSL host read-only.
SCRATCH_HOST_FLOOR_BYTES = 15 * 10**9
SCRATCH_HOST_LOW_SPACE = "scratch_host_low_space"


def require_scratch_floor(path, floor=SCRATCH_HOST_FLOOR_BYTES):
    """Refuse (`scratch_host_low_space`) unless the filesystem holding `path`
    has at least `floor` bytes free; an unreadable one refuses too. Only for
    the Carbon-operated hostile-code sessions, never a miner's research."""
    import shutil

    try:
        free = shutil.disk_usage(path).free
    except OSError:
        raise ResourceProfileRefused(SCRATCH_HOST_LOW_SPACE) from None
    if free < floor:
        raise ResourceProfileRefused(SCRATCH_HOST_LOW_SPACE)
    return free


#: LANE-RESOURCE-BOUND-01 (the Test Lead's choice (c), 2026-10-12): on a host
#: whose resource profile is in force, one run's scratch may hold at most this
#: many bytes. A named constant, so profile v1 is unchanged; a miner's machine
#: has no profile and so no watch and no cap.
SCRATCH_CAP_BYTES = 2 * 1024**3
#: How often the watchdog measures scratch (the ruling: every 2 s at most).
SCRATCH_POLL_SECONDS = 1.0
#: Consecutive failed measurements, while the run lives, after which its
#: scratch counts as unmeasurable and the run is stopped (fail closed: a run
#: that exhausts its own process bound must not blind the watch).
SCRATCH_UNMEASURED_POLLS = 15
#: The closed refusal a run stopped by the watchdog is typed with.
SCRATCH_CAP_EXCEEDED = "scratch_cap_exceeded"
#: Measured inside the container, as the worker that owns every byte of it:
#: the host user cannot list a directory the worker made private. `-I`, so
#: nothing the run wrote under /scratch is imported. Directories it hid from
#: its own user are reported, never skipped silently.
SCRATCH_MEASURE = r"""
import json, os
total, denied = 0, False
def refused(error):
    global denied
    if isinstance(error, PermissionError):
        denied = True
for directory, dirnames, filenames in os.walk("/scratch", onerror=refused):
    for name in dirnames + filenames:
        try:
            total += os.lstat(os.path.join(directory, name)).st_size
        except FileNotFoundError:
            pass
        except PermissionError:
            denied = True
print(json.dumps({"bytes": total, "denied": denied}))
"""


def measure_scratch(cli, container_name, timeout=10):
    """`(bytes, denied)` for the running container's scratch, measured inside
    it; a failed or malformed measurement raises (`WorkerFailure`)."""
    value = cli.json(
        [
            "exec",
            container_name,
            "/opt/carbon-worker/bin/python",
            "-I",
            "-c",
            SCRATCH_MEASURE,
        ],
        timeout=timeout,
    )
    if (
        type(value) is not dict
        or set(value) != {"bytes", "denied"}
        or type(value["bytes"]) is not int
        or value["bytes"] < 0
        or type(value["denied"]) is not bool
    ):
        raise WorkerFailure(WorkerCode.RUNTIME)
    return value["bytes"], value["denied"]


class ScratchWatchdog:
    """Stop a run whose scratch passes the cap (LANE-RESOURCE-BOUND-01).

    A thread measures every `interval` seconds while the run executes. It
    trips, once, when the measured bytes exceed `cap_bytes`, when the run hid
    part of its scratch from its own user, or after `unmeasured_limit`
    consecutive failed measurements; it then calls `stop_run` (the carrier
    kills the container). `tripped` holds the typed record, else None. Used
    only where a host profile is in force; never on a miner's machine."""

    def __init__(
        self,
        measure,
        stop_run,
        *,
        cap_bytes=SCRATCH_CAP_BYTES,
        interval=SCRATCH_POLL_SECONDS,
        unmeasured_limit=SCRATCH_UNMEASURED_POLLS,
    ):
        import threading

        if (
            type(cap_bytes) is not int
            or cap_bytes <= 0
            or type(unmeasured_limit) is not int
            or unmeasured_limit <= 0
            or type(interval) not in (int, float)
            or not 0 < interval <= 2
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        self.measure, self.stop_run = measure, stop_run
        self.cap_bytes, self.interval = cap_bytes, interval
        self.unmeasured_limit = unmeasured_limit
        self.tripped = None
        self.polls = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=60)
        return False

    def _trip(self, reason, observed):
        self.tripped = {
            "refusal": SCRATCH_CAP_EXCEEDED,
            "reason": reason,
            "observed_bytes": observed,
            "cap_bytes": self.cap_bytes,
        }
        try:
            self.stop_run()
        except Exception as error:  # noqa: BLE001 - the run may already be gone
            # Recorded, not raised: the carrier still removes the container
            # exactly, and the run is typed as stopped by the watchdog.
            self.tripped["stop_error"] = type(error).__name__

    def _watch(self):
        misses = 0
        while not self._stop.wait(self.interval):
            self.polls += 1
            try:
                used, denied = self.measure()
            except Exception:  # noqa: BLE001 - a miss, counted below
                misses += 1
                if misses >= self.unmeasured_limit:
                    self._trip("unmeasurable", None)
                    return
                continue
            misses = 0
            if used > self.cap_bytes:
                self._trip("over_cap", used)
                return
            if denied:
                self._trip("hidden_from_its_own_user", used)
                return


@dataclass(frozen=True)
class MinerResearchLaunch:
    """One miner research run. Only the carrier's miner lane constructs it."""

    container_name: str
    image_id: str
    launch_digest: str
    input_directory: Path
    scratch_directory: Path
    #: The host's installed GPU, by UUID, for a GPU code cell (RSURF-D20).
    #: None for every CPU run, whose arguments are exactly as before.
    gpu_device: str | None = None
    #: Carbon's own host's bounds (`load_host_profile`); None on a miner's
    #: machine, whose arguments are exactly as before.
    resource_profile: ResourceProfile | None = None

    def __post_init__(self):
        exact_token(self.container_name)
        exact_digest(self.image_id)
        exact_digest(self.launch_digest)
        if self.resource_profile is not None and (
            type(self.resource_profile) is not ResourceProfile
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        if self.gpu_device is not None and (
            type(self.gpu_device) is not str or not _GPU_UUID.fullmatch(self.gpu_device)
        ):
            raise WorkerFailure(WorkerCode.INVALID)
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
    # Empty: the worker's entrypoint creates home, tmp and caches itself and
    # refuses to start if they already exist, and the bootstrap creates output.
    directory.mkdir(mode=0o700)
    directory.chmod(0o777)
    return directory


def create_arguments(launch: MinerResearchLaunch) -> list[str]:
    if type(launch) is not MinerResearchLaunch:
        raise WorkerFailure(WorkerCode.INVALID)
    profile = launch.resource_profile
    cores = os.cpu_count() or 1
    threads = str(cores if profile is None else min(cores, profile.cpus))
    shm = _host_memory_bytes()
    if profile is not None:
        shm = min(shm, profile.memory_bytes)
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
        # On a miner's machine, no limits: no --memory, --cpus, --cpuset-cpus,
        # --pids-limit or nofile ulimit, and shared memory as large as the
        # host's, for data loaders. Carbon's own host adds its operator's
        # profile here, and nothing else changes.
        *_profile_arguments(profile),
        "--shm-size",
        str(shm),
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
        *_gpu_arguments(launch.gpu_device),
        launch.image_id,
    ]


def _profile_arguments(profile):
    """The operator's bounds, labelled by digest; nothing without a profile."""
    if profile is None:
        return []
    return [
        "--label",
        f"{_PROFILE_LABEL}={profile.digest()}",
        "--cpus",
        str(profile.cpus),
        "--memory",
        str(profile.memory_bytes),
        "--memory-swap",
        str(profile.memory_bytes),
        "--pids-limit",
        str(profile.pids_limit),
        "--ulimit",
        f"nofile={profile.nofile}:{profile.nofile}",
    ]


def _profile_exactly(profile, host, config):
    """No bounds asserted on a miner's machine; on Carbon's host, exactly the
    operator's profile was applied."""
    if profile is None:
        return True
    ulimits = {
        item.get("Name"): (item.get("Soft"), item.get("Hard"))
        for item in host.get("Ulimits") or []
        if type(item) is dict
    }
    return (
        (config.get("Labels") or {}).get(_PROFILE_LABEL) == profile.digest()
        and host.get("NanoCpus") == profile.cpus * 10**9
        and host.get("Memory") == profile.memory_bytes
        and host.get("MemorySwap") == profile.memory_bytes
        and host.get("PidsLimit") == profile.pids_limit
        and ulimits.get("nofile") == (profile.nofile, profile.nofile)
    )


def _gpu_arguments(device):
    """The one device, through the NVIDIA runtime; nothing for a CPU run."""
    if device is None:
        return []
    return [
        "--runtime",
        "nvidia",
        "--gpus",
        f"device={device}",
        "--label",
        f"carbon.accelerator.device={device}",
        "--env",
        f"NVIDIA_VISIBLE_DEVICES={device}",
        "--env",
        f"NVIDIA_DRIVER_CAPABILITIES={GPU_CAPABILITIES}",
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
    if not _gpu_exactly(launch.gpu_device, host, config):
        raise WorkerFailure(WorkerCode.POLICY)
    if not _profile_exactly(launch.resource_profile, host, config):
        raise WorkerFailure(WorkerCode.POLICY)
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
        or (launch.gpu_device is None and host.get("DeviceRequests"))
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
        "gpu_device": launch.gpu_device,
        "network": host.get("NetworkMode"),
        "read_only_root": True,
        "memory": host.get("Memory") or None,
        "nano_cpus": host.get("NanoCpus") or None,
        "pids_limit": host.get("PidsLimit") or None,
        **(
            {}
            if launch.resource_profile is None
            else {"resource_profile": launch.resource_profile.digest()}
        ),
    }


def _gpu_exactly(device, host, config):
    """No GPU for a CPU run; for a GPU code cell, exactly the one device,
    through the NVIDIA runtime, and nothing else added."""
    env = dict(item.split("=", 1) for item in config.get("Env") or [] if "=" in item)
    label = (config.get("Labels") or {}).get("carbon.accelerator.device")
    requests = host.get("DeviceRequests") or []
    if device is None:
        # A CPU run is checked exactly as before: no device requested.
        return not requests
    return (
        host.get("Runtime") == "nvidia"
        and len(requests) == 1
        and type(requests[0]) is dict
        and requests[0].get("DeviceIDs") == [device]
        and not requests[0].get("Count")
        and ["gpu"] in (requests[0].get("Capabilities") or [])
        and env.get("NVIDIA_VISIBLE_DEVICES") == device
        and env.get("NVIDIA_DRIVER_CAPABILITIES") == GPU_CAPABILITIES
        and label == device
    )


class MinerOutputRefused(ValueError):
    """The run's own output holds something other than regular files.

    Distinct from an unreadable output tree, which can be the host's doing: a
    link, FIFO, socket or device can only have been written by the run.
    """


def collect_outputs(scratch: Path, snapshot: Path) -> dict[str, int]:
    """Copy the run's own outputs into the snapshot, as untrusted bytes.

    Regular files only: a symlink, device, socket or FIFO written by hostile
    code is refused rather than followed, and every path stays inside the
    output directory. No size or count limit - it is the miner's disk.
    """
    source = scratch / "output"
    snapshot.mkdir(mode=0o700)
    copied = {}

    def unreadable(error):
        # os.walk skips a directory it cannot list unless told otherwise; a
        # snapshot missing part of the run's output must fail, never pass as
        # complete.
        raise ValueError("research output could not be read in full") from error

    for directory, dirnames, filenames in os.walk(
        source, followlinks=False, onerror=unreadable
    ):
        base = Path(directory)
        for name in dirnames:
            if (base / name).is_symlink():
                raise MinerOutputRefused("research output may not contain links")
        for name in filenames:
            path = base / name
            relative = path.relative_to(source)
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode):
                raise MinerOutputRefused(
                    "research output may contain regular files only"
                )
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(handle, "rb") as reader, open(target, "xb") as writer:
                while chunk := reader.read(1024**2):
                    writer.write(chunk)
            copied[relative.as_posix()] = info.st_size
    return copied
