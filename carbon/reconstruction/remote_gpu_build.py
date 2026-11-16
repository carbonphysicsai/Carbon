"""A build lane on a rented GPU: a door's GPU BUILD containers run on a remote docker daemon over ssh.

Owner's order (Mon 16 Nov 2026, via the Lead; TE3): Motor 1.8 builds (construction) run on an hourly A100 80GB (ONE
fixed variant) instead of only on the door host, so miners can train real neural operators and build backlogs clear.
It is the remote grade lane's mechanism (`carbon.reconstruction.remote_lane`: ssh ``DOCKER_HOST``, ``/input`` mirrored
to the same path under ``stage_root``, link loss = FAILED_INFRA) applied to one kind of operation only:

- **Only builds go.** An op is sent to the lane only when it is a GPU BUILD (`eligible`): a direct task's build child
  (``direct-<sha256>-build``) or the graph route's GPU repeat probes (``<task>~gpu1``/``~gpu2``), with a GPU
  accelerator, never the miner's own lane, never a timed control. Its stage holds the recipe's source and the
  Challenge's PUBLIC TRAIN only; inference, timing and grading ops (which may hold protected material) stay on the door.
- **The door stays the only authority.** The ledger, the intents, the receipts and the state digest (computed by the
  door over the export streamed back by ``docker exec``) never leave the door. The remote machine holds no key, no
  ledger and no pack; it only runs the pinned worker image (verified there by its image id) on the staged inputs.
- **Determinism.** The worker gets exactly the pinned environment every GPU rebuild gets
  (`accelerators.worker_environment`: XLA deterministic ops, autotune off, ``CUBLAS_WORKSPACE_CONFIG``, TF32 off) and
  PyTorch's in-process ``use_deterministic_algorithms`` is the build program's own. The request binds the remote
  device record's digest (and the slot count when there is more than one slot), so a build is compared only with the
  same build on the same GPU class and slot configuration; the graph route's two-rebuild repeat check runs here too.
- **N build slots per GPU** (`values_row` ``"slots"``, default 1, at most `MAX_SLOTS`): the door holds one of N slot
  locks per op (`op`), each slot with its own cores on the remote machine (``slot_cpusets``) and its own device
  allocation record. With N > 1 each process caps its own share of the device memory in-process, through a prelude the
  controller adds to the build program (`with_slot_prelude`): JAX's BFC allocator with no preallocation and
  ``XLA_PYTHON_CLIENT_MEM_FRACTION``, PyTorch's ``set_per_process_memory_fraction``; the container keeps the image-pinned
  environment, and the request records the cap. N > 1 waits on Validator-2 (`SLOT_PRELUDE_RULED`). With N = 1 the
  environment and the program are byte-identical to a local GPU build.
- **What stays on the door.** A build whose stage carries a HOST-PRIVATE seed (the crown's averaging rebuilds) or a
  derived rebind is withheld (`offered_for` ``withhold``): refused as Carbon's until the owner rules it may leave.
  Every build runs on exactly the lane the door bound at start (`pin`), or refuses as Carbon's.
- **Failure typing.** Any link fault raises `remote_lane.RemoteLaneDown` (WorkerFailure UNAVAILABLE: Carbon's
  infrastructure, never the candidate's). A remote op that fails while the link or the GPU is unhealthy (`healthy`:
  ``docker version`` answers and ``nvidia-smi`` still names the recorded device) is retyped to it. A wall stop on the
  lane is never the candidate's (as on the remote grade lane; whether a remote wall may count is Validator-Motor's
  ruling, not made here).

**Local slot lanes** (Lead, Mon 16 Nov: one design for both): a lane record with ``"docker_host": null`` and
``"stage_root": null`` is THIS host's own GPU (the GPUYard 4090 lane). It takes the same slot locks, per-slot cores,
per-slot allocation records and per-process memory shares, uses this host's installed device record and daemon, mirrors
nothing, and keeps a local GPU build's wall-stop reading; a GPU fault found after a failed build is still Carbon's.

**Configuration.** Operator-installed, beside the host execution record: ``<HOST_ROOT>/remote-gpu-build-lanes.json``
(`RECORD`, schema `SCHEMA`) ``{"lanes": [{"docker_host", "stage_root", "slot_cpusets"}]}``, and per lane the remote
machine's own strict host device record (``host-device.json``, written ON that machine by `scripts/dev/carbon_accelerator.py prepare`) in
``<HOST_ROOT>/remote-gpu-build/lane-<i>/``. A lane is used only when the values row `VALUES` names the door's
``"<challenge> <version>"`` with the one ``device_kind`` the record must report. No row, no record: today's path. This
module sets no threshold and makes no scientific decision; the GPU class is admitted for scoring only by the owner's
hardware acceptance (`hardware_acceptance.require_accepted`), which the receiver checks at start.
"""

from __future__ import annotations

import ast
import fcntl
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction import remote_lane
from carbon.reconstruction.remote_lane import RemoteLaneDown
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

RECORD = "remote-gpu-build-lanes.json"
SCHEMA = "carbon.remote-gpu-build-lanes.v1"
#: The per-lane directory under HOST_ROOT: the remote device record, the docker wrapper, the slot locks and records.
LANE_DIR = "remote-gpu-build/lane-{index}"
#: The values rows: ``{"schema", "rows": {"<challenge> <version>": {"device_kind": str, "slots"?: int}}}``.
VALUES = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "remote_gpu_build.json"
)
VALUES_SCHEMA = "carbon.remote-gpu-build.values.v1"
#: The owner's order: one rented machine, one fixed GPU variant.
MAX_LANES = 1
DEFAULT_SLOTS = 1
#: The most build slots one GPU may be split into (an operational bound, not a scientific value).
MAX_SLOTS = 4
#: The share of device memory all slots together may take; each slot gets an equal part of it, rounded down to 0.01.
#: Operational headroom for the CUDA context and the driver, not a scientific value.
MEMORY_SHARE = 0.9
#: How long an op waits for a free slot before it is Carbon's (UNAVAILABLE); an operational bound.
SLOT_WAIT_SECONDS = 3600
POLL_S = 0.5
#: How long the GPU probe may take.
PROBE_SECONDS = 20
#: Whether more than one build may share a lane's GPU (JAX_MEMORY_CAP_PLAN option A, Lead OK 16 Nov): each slot's
#: program caps its own device memory in-process (`SLOT_PRELUDE`: JAX's BFC allocator with no preallocation and
#: ``XLA_PYTHON_CLIENT_MEM_FRACTION``, PyTorch's ``set_per_process_memory_fraction``), while the container keeps the
#: image-pinned environment the controls check requires (``XLA_PYTHON_CLIENT_ALLOCATOR=platform``). That in-process
#: override is Validator-2's to accept: False until V2 says yes, so a values row asking for more than one slot refuses
#: at the door's start (`door_lane`). It is the ONLY switch; flipping it changes nothing for a one-slot lane.
SLOT_PRELUDE_RULED = False
#: The environment variable the slot prelude reads: this process's share of the device (``0.9 / N``, two decimals).
SLOT_FRACTION_ENV = "CARBON_SLOT_MEMORY_FRACTION"
#: What the prelude sets for JAX before any import (read when JAX's GPU backend starts).
SLOT_JAX_ENVIRONMENT = {
    "XLA_PYTHON_CLIENT_ALLOCATOR": "bfc",
    "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
}
#: The ops a lane may run: a direct task's build child, or a graph GPU repeat probe.
_BUILD_IDENTITY = re.compile(r"direct-[0-9a-f]{64}-build|.{1,200}~gpu[12]")
_DEVICE_KIND = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()-]{0,63}")
_HOME = re.compile(r"/[A-Za-z0-9._/-]{0,255}")


@dataclass(frozen=True)
class GpuBuildSpec:
    """One remote GPU build lane as the operator installed it (`load`)."""

    index: int
    #: The lane machine's ssh daemon, or None: THIS host's own GPU (a local slot lane: the GPUYard 4090's).
    docker_host: str | None
    #: Where inputs are mirrored on the lane machine; None for a local lane (nothing to mirror).
    stage_root: str | None

    @property
    def local(self):
        return self.docker_host is None

    slot_cpusets: tuple[str, ...]


@dataclass(frozen=True)
class DoorLane:
    """The lane a door's builds are offered (`door_lane`): the spec, its slot count and the remote device record."""

    spec: GpuBuildSpec
    slots: int
    device: object  # host_inventory.HostDeviceRecord
    lane_dir: str


@dataclass(frozen=True)
class OpBinding:
    """One op bound to one slot of a lane (`op`, `recovered`)."""

    lane: DoorLane
    slot: int

    @property
    def docker_host(self):
        return self.lane.spec.docker_host

    @property
    def stage_root(self):
        return self.lane.spec.stage_root

    @property
    def slot_dir(self) -> Path:
        return Path(self.lane.lane_dir) / f"slot-{self.slot}"

    @property
    def cpuset(self) -> str:
        return self.lane.spec.slot_cpusets[self.slot]


_OFFERED: ContextVar[DoorLane | None] = ContextVar(
    "carbon_remote_gpu_build_offered", default=None
)
_OP: ContextVar[OpBinding | None] = ContextVar(
    "carbon_remote_gpu_build_op", default=None
)
#: A slot op's binding handed to a process it spawns (its watchdog): the op's intent fields as JSON. Read only when no
#: binding is set in the context, so the door process itself (which never sets it) is unaffected.
ENVIRONMENT = "CARBON_REMOTE_GPU_BUILD"
#: Marks a lane withheld from this build (`offered_for` ``withhold``): an eligible op then refuses as Carbon's.
_WITHHELD = object()
#: The lane device each door bound at start (`pin`): ``{(challenge_id, version): record digest or None}``.
_PINNED: dict = {}
_ENVIRONMENT_BINDING: list = []


def _current():
    """The running op's slot binding: the context's, else (in a process a slot op spawned) the one it was handed."""
    binding = _OP.get()
    if binding is not None or ENVIRONMENT not in os.environ:
        return binding
    if not _ENVIRONMENT_BINDING:
        # Self-contained (`_handoff`): never re-read from the operator's records, which may have changed since the op
        # began. One that cannot be read back binds nothing: the watchdog still removes the container on the daemon
        # its DOCKER_HOST names, and the slot's record is left to recovery (`reconcile_worker`).
        _ENVIRONMENT_BINDING.append(_from_handoff(os.environ[ENVIRONMENT]))
    return _ENVIRONMENT_BINDING[0]


def _handoff(binding):
    """The running op's binding as the JSON a spawned process is handed: everything it needs, with the device record."""
    spec = binding.lane.spec
    return json.dumps(
        {
            "index": spec.index,
            "docker_host": spec.docker_host,
            "stage_root": spec.stage_root,
            "slot_cpusets": list(spec.slot_cpusets),
            "slots": binding.lane.slots,
            "lane_dir": binding.lane.lane_dir,
            "slot": binding.slot,
            "device": binding.lane.device.document,
            "device_digest": binding.lane.device.digest,
        },
        sort_keys=True,
    )


def _from_handoff(raw):
    """The `OpBinding` a `_handoff` describes, or None when it cannot be read back exactly."""
    from carbon.development_session.profile import canonical
    from carbon.reconstruction.host_inventory import HostDeviceRecord, tagged_sha256

    try:
        entry = json.loads(raw)
        device = HostDeviceRecord(entry["device"], entry["device_digest"])
        if tagged_sha256(canonical(entry["device"])) != entry["device_digest"]:
            return None
        device.validate()
        spec = GpuBuildSpec(
            entry["index"],
            entry["docker_host"],
            entry["stage_root"],
            tuple(entry["slot_cpusets"]),
        )
        slot = entry["slot"]
        if type(slot) is not int or not 0 <= slot < len(spec.slot_cpusets):
            return None
        return OpBinding(
            DoorLane(spec, entry["slots"], device, entry["lane_dir"]), slot
        )
    except (ValueError, TypeError, KeyError, WorkerFailure):
        return None


# -- configuration ---------------------------------------------------------------------------------------------------------


def _host_root(root):
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    return Path(HOST_ROOT if root is None else root)


def load(root=None):
    """The installed remote GPU build lanes (a tuple of `GpuBuildSpec`), ``()`` when none is installed. A record that is
    present but malformed raises ValueError: an operator who installed one meant something by it.
    """
    from carbon.reconstruction.host_execution import parse_cpuset

    path = _host_root(root) / RECORD
    if not path.exists():
        return ()
    document = json.loads(path.read_bytes())
    if (
        type(document) is not dict
        or set(document) != {"schema", "lanes"}
        or document["schema"] != SCHEMA
        or type(document["lanes"]) is not list
        or not 1 <= len(document["lanes"]) <= MAX_LANES
    ):
        raise ValueError("remote_gpu_build_record")
    specs = []
    for index, entry in enumerate(document["lanes"]):
        if type(entry) is not dict or set(entry) != {
            "docker_host",
            "stage_root",
            "slot_cpusets",
        }:
            raise ValueError("remote_gpu_build_record")
        local = entry["docker_host"] is None
        if local != (entry["stage_root"] is None):
            # a local lane names neither a daemon nor a mirror root; a remote one names both
            raise ValueError("remote_gpu_build_record")
        if not local:
            remote_lane.parse_docker_host(entry["docker_host"])
        cpusets = entry["slot_cpusets"]
        if (
            type(cpusets) is not list
            or not 1 <= len(cpusets) <= MAX_SLOTS
            or any(type(value) is not str for value in cpusets)
        ):
            raise ValueError("remote_gpu_build_slot_cpusets")
        seen = set()
        sizes = set()
        for value in cpusets:
            try:
                cores = set(parse_cpuset(value))
            except WorkerFailure:
                raise ValueError("remote_gpu_build_slot_cpusets") from None
            if cores & seen:
                raise ValueError("remote_gpu_build_slot_cpusets")
            seen |= cores
            sizes.add(len(cores))
        if len(sizes) != 1:
            raise ValueError("remote_gpu_build_slot_cpusets")
        specs.append(
            GpuBuildSpec(
                index,
                entry["docker_host"],
                None if local else remote_lane._checked_root(entry["stage_root"]),
                tuple(cpusets),
            )
        )
    return tuple(specs)


def values_row(challenge_id, version, *, path=None):
    """The well-formed values row of ``"<challenge_id> <version>"`` as ``{"device_kind", "slots"}`` (slots defaulted to
    `DEFAULT_SLOTS`), or None (no lane for this door). A values file that is unreadable or malformed is no lane.
    """
    try:
        document = json.loads(Path(VALUES if path is None else path).read_bytes())
    except (OSError, ValueError):
        return None
    if type(document) is not dict or document.get("schema") != VALUES_SCHEMA:
        return None
    row = (document.get("rows") or {}).get(f"{challenge_id} {version}")
    if type(row) is not dict or set(row) not in (
        {"device_kind"},
        {"device_kind", "slots"},
    ):
        return None
    kind = row["device_kind"]
    slots = row.get("slots", DEFAULT_SLOTS)
    if type(kind) is not str or not _DEVICE_KIND.fullmatch(kind):
        return None
    if type(slots) is not int or not 1 <= slots <= MAX_SLOTS:
        return None
    return {"device_kind": kind, "slots": slots}


def door_lane(challenge_id, version, *, root=None, values=None):
    """The remote GPU build lane a door of ``"<challenge_id> <version>"`` offers its builds (a `DoorLane`), or None
    (no values row, or no lane installed: today's path). A row with an installed lane whose device record is missing,
    malformed or of another kind than the row names, or that asks for more slots than the lane has cores for, raises
    ValueError: the door refuses rather than build on a machine it cannot describe."""
    row = values_row(challenge_id, version, path=values)
    if row is None:
        return None
    specs = load(root)
    if not specs:
        return None
    spec = specs[0]
    if row["slots"] > len(spec.slot_cpusets):
        raise ValueError("remote_gpu_build_slots_exceed_cpusets")
    if row["slots"] > 1 and not SLOT_PRELUDE_RULED:
        # every build offered a lane is a graph build on the JAX worker: N > 1 shares the device, capped per process
        # only by the slot prelude, which waits on Validator-2's ruling (`SLOT_PRELUDE_RULED`)
        raise ValueError("remote_gpu_build_slots_need_jax_memory_cap")
    lane_dir = _host_root(root) / LANE_DIR.format(index=spec.index)
    device = _lane_device(_host_root(root) if spec.local else lane_dir)
    if device.device_kind != row["device_kind"]:
        raise ValueError("remote_gpu_build_device_kind")
    return DoorLane(spec, row["slots"], device, str(lane_dir))


def _lane_device(lane_dir):
    """The lane machine's strict device record, bound to the GPU profile, or ValueError: a remote lane's own (in its
    lane directory, written ON that machine by `carbon_accelerator.py prepare`), or a local lane's: this host's installed record.
    """
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.host_inventory import (
        HostDeviceRecord,
        require_host_device,
    )

    try:
        return require_host_device(HostDeviceRecord.load(lane_dir), GPU_PROFILE)
    except WorkerFailure:
        raise ValueError("remote_gpu_build_device_record") from None


# -- binding ---------------------------------------------------------------------------------------------------------------


@contextmanager
def offered(lane):
    """Offer ``lane`` (a `DoorLane`, or None: nothing changes) to the GPU builds started inside."""
    if lane is not None and type(lane) is not DoorLane:
        raise ValueError("remote_gpu_build_lane")
    token = _OFFERED.set(lane)
    try:
        yield lane
    finally:
        _OFFERED.reset(token)


def pin(challenge_id, version, lane):
    """Record the lane device a door bound at start (``lane`` a `DoorLane`, or None: no lane), so a build never runs on
    a lane other than the one the door's binding names (`offered_for`)."""
    _PINNED[(challenge_id, version)] = fingerprint(lane)


def fingerprint(lane):
    """What a door binds about its lane: the device record, the daemon, the mirror root, the slots and their cores."""
    if lane is None:
        return None
    spec = lane.spec
    return (
        lane.device.digest,
        spec.docker_host,
        spec.stage_root,
        spec.slot_cpusets,
        lane.slots,
    )


@contextmanager
def offered_for(challenge_id, version, *, root=None, values=None, withhold=False):
    """`offered` with the door's lane for ``"<challenge_id> <version>"`` (`door_lane`), read at the build. Carbon's
    (`RemoteLaneDown`), never the build's: a lane configuration that broke since the door started, or a lane (or its
    device) that differs from the one the door bound at start (`pin`).

    ``withhold``: this build's stage holds something that may not leave the door (a HOST-PRIVATE seed: the crown's
    averaging rebuilds). Whether such a build may go to a rented machine is the owner's decision, not made here: while
    a lane is configured, its GPU build ops refuse as Carbon's instead of running anywhere else.
    """
    try:
        lane = door_lane(challenge_id, version, root=root, values=values)
    except (ValueError, OSError) as error:
        raise RemoteLaneDown(str(error).encode()[:512]) from None
    key = (challenge_id, version)
    if key in _PINNED and _PINNED[key] != fingerprint(lane):
        raise RemoteLaneDown(b"remote_gpu_build_lane_changed_since_start")
    token = _OFFERED.set(_WITHHELD if withhold and lane is not None else lane)
    try:
        yield lane
    finally:
        _OFFERED.reset(token)


def offered_lane():
    lane = _OFFERED.get()
    return None if lane is _WITHHELD else lane


def eligible(identity, *, accelerator, provenance, timed):
    """Whether an op may run on the remote GPU build lane: a GPU build (`_BUILD_IDENTITY`) with an accelerator, never
    the miner's own lane, never a timing measurement."""
    return (
        accelerator is not None
        and provenance != "MINER_SELF_REPORTED"
        and not timed
        and type(identity) is str
        and _BUILD_IDENTITY.fullmatch(identity) is not None
    )


def current_op():
    """The slot binding of the running op, or None (the door's own daemon)."""
    return _current()


@contextmanager
def op(
    identity,
    *,
    accelerator,
    provenance,
    timed,
    poll_s=None,
    sleep=None,
    check=None,
    settled=False,
):
    """Bind an eligible op (`eligible`) of a build that was offered a lane to one free slot for its whole life; anything
    else: unchanged (yields None). No free slot within `SLOT_WAIT_SECONDS` is Carbon's (`RemoteLaneDown`). ``check``
    is called while waiting (the op's cancellation), and may raise. A slot whose allocation record a lost controller
    left behind is passed over until recovery clears it."""
    lane = _OFFERED.get()
    if lane is None or not eligible(
        identity, accelerator=accelerator, provenance=provenance, timed=timed
    ):
        yield None
        return
    if lane is _WITHHELD:
        raise RemoteLaneDown(b"remote_gpu_build_withheld_host_private_build")
    if settled:
        # an op the ledger has settled replays its recorded result: bound to the lane (its request, its device, its
        # program are the lane's, so the replay matches what was reserved), but it runs nothing and takes no slot
        token = _OP.set(OpBinding(lane, 0))
        try:
            yield _OP.get()
        finally:
            _OP.reset(token)
        return
    pause = time.sleep if sleep is None else sleep
    poll = POLL_S if poll_s is None else poll_s
    if not lane.spec.local:
        wrapper(lane)
    deadline = time.monotonic() + SLOT_WAIT_SECONDS
    held = None
    while held is None:
        for slot in range(lane.slots):
            directory = Path(lane.lane_dir) / f"slot-{slot}"
            try:
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(directory / "slot.lock", os.O_RDWR | os.O_CREAT, 0o600)
            except OSError as error:
                raise RemoteLaneDown(repr(error).encode()[:512]) from None
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                continue
            if (directory / "active-allocation.json").exists():
                # a lost controller's record: this slot waits for recovery, another may be free
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                continue
            held = (slot, fd)
            break
        if held is None:
            if check is not None:
                check()
            if time.monotonic() >= deadline:
                raise RemoteLaneDown(b"remote_gpu_build_slots_busy")
            pause(poll)
    slot, fd = held
    token = _OP.set(OpBinding(lane, slot))
    try:
        yield _OP.get()
    finally:
        _OP.reset(token)
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


# -- what the carrier asks of a bound op ------------------------------------------------------------------------------------


def device():
    """The remote device record of the running op, or None."""
    binding = _current()
    return None if binding is None else binding.lane.device


def allocation_root():
    """Where the running op's device allocation record lives (its slot's directory), or None (HOST_ROOT)."""
    binding = _current()
    return None if binding is None else binding.slot_dir


def cpuset():
    """The running op's slot cores on the remote machine, or None."""
    binding = _current()
    return None if binding is None else binding.cpuset


def docker_host():
    """The ``DOCKER_HOST`` of the running op's lane, or None."""
    binding = _current()
    return None if binding is None else binding.docker_host


def _docker_binary():
    found = shutil.which("docker", path="/usr/local/bin:/usr/bin:/bin")
    if found is None:
        raise RemoteLaneDown(b"remote_gpu_build_no_docker_cli")
    return found


def wrapper_text(docker_host_value, home, docker):
    """The lane's docker wrapper: the local docker CLI talking to the lane's ssh daemon. Every value is checked, so
    nothing a request carries can become a shell word."""
    remote_lane.parse_docker_host(docker_host_value)
    if type(home) is not str or not _HOME.fullmatch(home):
        raise RemoteLaneDown(b"remote_gpu_build_home")
    if type(docker) is not str or not _HOME.fullmatch(docker):
        raise RemoteLaneDown(b"remote_gpu_build_no_docker_cli")
    return (
        "#!/bin/sh\n"
        "# GENERATED by carbon.reconstruction.remote_gpu_build; do not edit.\n"
        f"DOCKER_HOST={shlex.quote(docker_host_value)}\n"
        f"HOME={shlex.quote(home)}\n"
        "export DOCKER_HOST HOME\n"
        f'exec {shlex.quote(docker)} "$@"\n'
    )


def wrapper(lane):
    """The lane's docker wrapper, (re)written when its text differs: ``<lane_dir>/docker`` (0500)."""
    path = Path(lane.lane_dir) / "docker"
    text = wrapper_text(
        lane.spec.docker_host, os.environ.get("HOME", "/"), _docker_binary()
    ).encode()
    try:
        if path.is_symlink():
            raise RemoteLaneDown(b"remote_gpu_build_wrapper_link")
        if not path.exists() or path.read_bytes() != text:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # one temporary per writer: concurrent ops of one lane each write the same text, and the last rename wins
            import threading

            temporary = path.with_name(
                f".docker.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            temporary.unlink(missing_ok=True)
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(text)
                temporary.chmod(0o500)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    except OSError as error:
        raise RemoteLaneDown(repr(error).encode()[:512]) from None
    return path


def cli(binding=None):
    """A Docker CLI for the running op's lane daemon (through the lane's wrapper), or None outside a remote op."""
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.spec.local:
        # outside a slot, or a local slot lane: this host's own daemon (the caller's DockerCLI)
        return None
    from carbon.reconstruction.worker.docker_runtime import DockerCLI

    remote = DockerCLI()
    # DockerCLI (a worker image input, A16's bytes) always runs ``docker`` with the operator's own DOCKER_*; the lane's
    # wrapper is that same CLI with the lane's DOCKER_HOST, so every bounded capture and stream is DockerCLI's own.
    remote.executable = str(wrapper(binding.lane))
    remote.docker_host = binding.docker_host
    return remote


def slot_fraction(slots):
    """Each slot's share of the device memory, rounded down to 0.01: `MEMORY_SHARE` / ``slots``."""
    if type(slots) is not int or not 1 <= slots <= MAX_SLOTS:
        raise ValueError("remote_gpu_build_slots")
    return math.floor(MEMORY_SHARE / slots * 100) / 100


def slot_environment(binding=None):
    """The container environment the running op gets beyond the pinned worker environment: nothing with one slot (a
    local GPU build's environment, byte for byte); with N > 1 the slot's share (`SLOT_FRACTION_ENV`), which the
    program's `SLOT_PRELUDE` applies in-process.

    The container env never carries JAX's allocator settings: the pinned GPU environment
    (`accelerators.pinned_environment`, a worker-image input) fixes ``XLA_PYTHON_CLIENT_ALLOCATOR=platform`` and the
    controls check (`docker_runtime.inspect_effective_controls`) requires it exactly. The prelude switches JAX to the
    BFC allocator with the fraction inside the program, before JAX is imported (the carrier's BOOTSTRAP ``exec``s a
    fresh interpreter on the program), and the request records it (`request_fields`)."""
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.slots == 1:
        return {}
    return {SLOT_FRACTION_ENV: f"{slot_fraction(binding.lane.slots):.2f}"}


def with_slot_environment(arguments, binding=None):
    """``docker create`` arguments with the running op's `slot_environment`: an existing ``--env KEY=...`` is replaced,
    the rest are added before the image (the last argument). Unchanged with one slot or outside a remote op.
    """
    extra = slot_environment(binding)
    if not extra:
        return arguments
    result = list(arguments)
    for index, value in enumerate(result):
        if index and result[index - 1] == "--env":
            key = value.split("=", 1)[0]
            if key in extra:
                result[index] = f"{key}={extra.pop(key)}"
    added = []
    for key, value in extra.items():
        added.extend(["--env", f"{key}={value}"])
    result[-1:-1] = added
    return result


SLOT_PRELUDE = (
    "# Carbon GPU build slot (remote_gpu_build.SLOT_PRELUDE): this process's share of the device, before any import.\n"
    "import os as _carbon_os\n"
    f'_carbon_share = _carbon_os.environ.get("{SLOT_FRACTION_ENV}")\n'
    "if _carbon_share:\n"
    "    # JAX: the BFC allocator, no preallocation, at most this share (read when its GPU backend starts)\n"
    + "".join(
        f'    _carbon_os.environ["{key}"] = "{value}"\n'
        for key, value in SLOT_JAX_ENVIRONMENT.items()
    )
    + '    _carbon_os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] = _carbon_share\n'
    "    # PyTorch, when this image has it: the same share as a hard per-process cap\n"
    "    try:\n"
    "        import torch as _carbon_torch\n"
    "    except ImportError:\n"
    "        _carbon_torch = None\n"
    "    if _carbon_torch is not None and _carbon_torch.cuda.is_available():\n"
    "        _carbon_torch.cuda.set_per_process_memory_fraction(float(_carbon_share), 0)\n"
)


def with_slot_prelude(source, binding=None):
    """The build program with `SLOT_PRELUDE` after its docstring and ``__future__`` imports: only with N > 1 slots.
    Unchanged otherwise, so a one-slot lane runs exactly the local program."""
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.slots == 1:
        return source
    module = ast.parse(source)
    after = 0
    for position, node in enumerate(module.body):
        if (
            position == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ) or (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
            after = node.end_lineno
            continue
        break
    lines = source.splitlines(keepends=True)
    if after and not lines[after - 1].endswith("\n"):
        lines[after - 1] += "\n"
    return "".join(lines[:after]) + SLOT_PRELUDE + "".join(lines[after:])


def request_fields(binding=None):
    """What a bound op's request records beside its accelerator: the slot count when it is above one (the per-process
    memory share is part of the build's environment), else nothing (identities as before).
    """
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.slots == 1:
        return {}
    # the program's in-process memory cap (`SLOT_PRELUDE`), recorded where the container env cannot show it
    return {
        "remote_gpu_slots": binding.lane.slots,
        "slot_memory": {
            "fraction": f"{slot_fraction(binding.lane.slots):.2f}",
            "jax": dict(SLOT_JAX_ENVIRONMENT),
            "torch": "set_per_process_memory_fraction",
        },
    }


def intent_fields():
    """What an op's durable intent records about where its container runs: ``{"remote_gpu_build": {...}}`` for a
    remote op (the daemon, the mirror root, the lane and the slot recovery must use), else ``{}``.
    """
    binding = _current()
    if binding is None:
        return {}
    return {
        "remote_gpu_build": {
            "docker_host": binding.docker_host,
            "stage_root": binding.stage_root,
            "lane": binding.lane.spec.index,
            "slot": binding.slot,
        }
    }


def recorded(intent, *, root=None):
    """The slot binding an intent recorded (an `OpBinding` rebuilt from the installed lane), or None (the door's own
    daemon). A malformed record, or one that names a lane no longer installed as it was, raises ValueError: recovery
    never guesses which daemon holds a container."""
    entry = intent.get("remote_gpu_build") if type(intent) is dict else None
    if entry is None:
        return None
    if type(entry) is not dict or set(entry) != {
        "docker_host",
        "stage_root",
        "lane",
        "slot",
    }:
        raise ValueError("remote_gpu_build_intent")
    specs = {spec.index: spec for spec in load(root)}
    spec = specs.get(entry["lane"])
    if (
        spec is None
        or spec.docker_host != entry["docker_host"]
        or spec.stage_root != entry["stage_root"]
        or type(entry["slot"]) is not int
        or not 0 <= entry["slot"] < len(spec.slot_cpusets)
    ):
        raise ValueError("remote_gpu_build_intent")
    lane_dir = _host_root(root) / LANE_DIR.format(index=spec.index)
    lane = DoorLane(
        spec,
        len(spec.slot_cpusets),
        _lane_device(_host_root(root) if spec.local else lane_dir),
        str(lane_dir),
    )
    return OpBinding(lane, entry["slot"])


@contextmanager
def bound(binding):
    """Run recovery for a recorded op (`recorded`) as that op ran: its daemon, its slot's allocation record."""
    if binding is not None and type(binding) is not OpBinding:
        raise ValueError("remote_gpu_build_binding")
    token = _OP.set(binding)
    try:
        yield binding
    finally:
        _OP.reset(token)


# -- the remote machine ---------------------------------------------------------------------------------------------------


def mirror(stage):
    """Mirror the running op's ``/input`` to the same path on the lane machine (`remote_lane.mirror`). No-op outside
    a remote op."""
    binding = _current()
    if binding is not None and not binding.lane.spec.local:
        remote_lane.mirror(stage, binding)


def discard(stage, binding=None):
    """Remove the lane machine's copy of ``stage`` (`remote_lane.discard`). No-op outside a remote op."""
    binding = _current() if binding is None else binding
    if binding is not None and not binding.lane.spec.local:
        remote_lane.discard(stage, binding)


def _ssh_capture(binding, argv, timeout=PROBE_SECONDS):
    """``argv``'s stdout on the lane machine: over ssh for a remote lane, directly for a local one."""
    command = (
        list(argv)
        if binding.lane.spec.local
        else [*remote_lane._ssh(binding), " ".join(shlex.quote(item) for item in argv)]
    )
    try:
        done = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=(
                {"PATH": "/usr/local/bin:/usr/bin:/bin"}
                if binding.lane.spec.local
                else remote_lane.docker_environment(binding.docker_host)
            ),
            cwd=os.sep,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RemoteLaneDown(repr(error).encode()[:512]) from None
    if done.returncode != 0:
        raise RemoteLaneDown(b"exit=%d\n" % done.returncode + done.stderr[-512:])
    return done.stdout


def gpu_present(binding=None):
    """Whether the lane machine's ``nvidia-smi`` names the recorded device (its uuid, with the recorded kind)."""
    binding = _current() if binding is None else binding
    record = binding.lane.device
    try:
        raw = _ssh_capture(
            binding,
            ["nvidia-smi", "--query-gpu=uuid,name", "--format=csv,noheader"],
        )
    except RemoteLaneDown:
        return False
    for line in raw.decode("utf-8", "replace").splitlines():
        fields = [field.strip() for field in line.split(",", 1)]
        if fields == [record.device_uuid, record.device_kind]:
            return True
    return False


def healthy(binding=None):
    """Whether the running op's link and GPU are sound now: the daemon answers and the device is still there."""
    binding = _current() if binding is None else binding
    if binding is None:
        return True
    if binding.lane.spec.local:
        return gpu_present(binding)
    return remote_lane.link_up(binding) and gpu_present(binding)


def check_host(cli_, image, record, pins=None):
    """The remote GPU readiness a build needs, on the lane's daemon: the NVIDIA runtime and the pinned worker image
    (by id, lock and labels), and the recorded device present now. Fails as Carbon's (`RemoteLaneDown`).
    """
    from carbon.reconstruction.worker.accelerator_runtime import (
        verify_image_and_toolkit,
    )

    binding = _current()
    if binding is None:
        raise RemoteLaneDown(b"remote_gpu_build_unbound")
    if record is None or record.digest != binding.lane.device.digest:
        raise RemoteLaneDown(b"remote_gpu_build_device_changed")
    try:
        if image is None:
            info = cli_.json(["info", "--format", "{{json .}}"])
            if type(info) is not dict or "nvidia" not in (info.get("Runtimes") or {}):
                raise RemoteLaneDown(b"remote_gpu_build_no_nvidia_runtime")
        elif pins is None:
            verify_image_and_toolkit(cli=cli_, image=image)
        else:
            _, profile_digest, lock_digest = pins
            verify_image_and_toolkit(
                cli=cli_,
                image=image,
                profile_digest=profile_digest,
                lock_digest=lock_digest,
            )
    except RemoteLaneDown:
        raise
    except WorkerFailure as error:
        if remote_lane.link_up(binding):
            raise
        raise RemoteLaneDown(b"remote_gpu_build_link_down") from error
    if not gpu_present(binding):
        raise RemoteLaneDown(b"remote_gpu_build_device_absent")


def reject_crowded(cli_, binding=None):
    """Before create: the slot's own allocation record is free, and the lane's daemon runs fewer Carbon containers on
    the device than the lane has slots (a lost controller's retained container still counts). CONFLICT otherwise.
    """
    binding = _current() if binding is None else binding
    if (binding.slot_dir / "active-allocation.json").exists():
        raise WorkerFailure(WorkerCode.CONFLICT)
    if binding.lane.spec.local:
        from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

        # a local slot lane shares this host's GPU with its other Carbon work (practice, receipts), which holds the
        # host's single allocation record: while that is held, no slot starts
        if (Path(HOST_ROOT) / "active-allocation.json").exists():
            raise WorkerFailure(WorkerCode.CONFLICT)
    raw = cli_.run(
        [
            "ps",
            "--all",
            "--filter",
            f"label=carbon.accelerator.device={binding.lane.device.device_uuid}",
            "--format",
            "{{json .ID}}",
        ],
        timeout=10,
    ).stdout
    if len([line for line in raw.splitlines() if line.strip()]) >= binding.lane.slots:
        raise WorkerFailure(WorkerCode.CONFLICT)


def spawn_watchdog(*, container_name, launch_digest, deadline_unix, intent_path=None):
    """`docker_runtime.spawn_watchdog` for the running op's container on the lane's daemon: the same watchdog process,
    with the lane's ``DOCKER_HOST`` (and ``HOME`` for ssh) in its environment, so it inspects and removes the container
    where it runs (a link fault there keeps it alive until the deadline: `watchdog.main`).
    """
    import sys

    from carbon.reconstruction.worker.model import exact_digest, exact_token

    binding = _current()
    if binding is None:
        raise RemoteLaneDown(b"remote_gpu_build_unbound")
    environment = remote_lane.docker_environment(binding.docker_host)
    # the watchdog finishes the slot's own allocation record against the lane's device record (`_current`)
    environment[ENVIRONMENT] = _handoff(binding)
    exact_token(container_name)
    exact_digest(launch_digest)
    if type(deadline_unix) is not float or deadline_unix <= time.time():
        raise WorkerFailure(WorkerCode.INVALID)
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
        raise RemoteLaneDown(b"remote_gpu_build_watchdog") from None


def remote_box(binding=None):
    """The running op's slot binding when its lane is REMOTE (it has the ``docker_host`` a box probe and a link check
    need), else None."""
    binding = _current() if binding is None else binding
    return None if binding is None or binding.lane.spec.local else binding


def wall_counts(binding=None):
    """Whether this lane lets a wall stop of the running op be read as the candidate's at all. Outside a slot, and on a
    one-slot local lane (as a local GPU build's always was): yes. On a REMOTE lane: yes, but only as CV-Motor ruled
    (L12624, 16 Nov), each part read from records by its own check: (a) the box's own clock and (c) the link
    (`remote_lane.wall_stop_observable`, which reads this slot's box), (b) the box quiet for the op and (c) every in-run
    sample answered (the op's box guard, `research_carrier.REMOTE_BUILD_GUARD`). On a local lane shared by more than
    one slot: never (its neighbours are this host's, not sampled per slot)."""
    binding = _current() if binding is None else binding
    if binding is None or not binding.lane.spec.local:
        return True
    return binding.lane.slots == 1


def retyped(error, binding=None):
    """``error`` of a remote op, retyped as Carbon's (`RemoteLaneDown`) when the link or the GPU is unhealthy now; else
    None (the error stands as it is)."""
    binding = _current() if binding is None else binding
    if binding is None or isinstance(error, RemoteLaneDown):
        return None
    if healthy(binding):
        return None
    down = RemoteLaneDown(b"remote_gpu_build_unhealthy_after_failure")
    down.__cause__ = error
    return down


__all__ = [
    "DEFAULT_SLOTS",
    "MAX_LANES",
    "MAX_SLOTS",
    "RECORD",
    "SCHEMA",
    "SLOT_PRELUDE",
    "VALUES",
    "VALUES_SCHEMA",
    "DoorLane",
    "GpuBuildSpec",
    "OpBinding",
    "allocation_root",
    "bound",
    "check_host",
    "cli",
    "cpuset",
    "current_op",
    "device",
    "discard",
    "docker_host",
    "door_lane",
    "eligible",
    "fingerprint",
    "gpu_present",
    "healthy",
    "intent_fields",
    "load",
    "mirror",
    "offered",
    "offered_for",
    "offered_lane",
    "op",
    "pin",
    "recorded",
    "reject_crowded",
    "remote_box",
    "request_fields",
    "retyped",
    "slot_environment",
    "slot_fraction",
    "spawn_watchdog",
    "values_row",
    "wall_counts",
    "with_slot_environment",
    "with_slot_prelude",
    "wrapper",
    "wrapper_text",
]
