"""A build lane on rented GPUs: a door's GPU BUILD containers run on a POOL of remote docker daemons over ssh.

Owner's order (Mon 16 Nov 2026, via the Lead; TE3): Motor 1.8 builds (construction) run on hourly rented A100s (ONE
fixed variant) instead of only on the door host, so miners can train real neural operators and build backlogs clear.
Part 2 (17 Nov): the rented boxes are ON DEMAND: adding, swapping or dropping a box needs no door migration, no restart
and no per-box record in the door binding. It is the remote grade lane's mechanism (`carbon.reconstruction.remote_lane`:
ssh ``DOCKER_HOST``, ``/input`` mirrored to the same path under ``stage_root``, link loss = FAILED_INFRA) applied to one
kind of operation only:

- **Only builds go.** An op is sent to a box only when it is a GPU BUILD (`eligible`): a direct task's build child
  (``direct-<sha256>-build``), the graph route's first-build shadow (``<task>~shadow``) or an old GPU repeat probe
  (``<task>~gpu1``/``~gpu2``), with a GPU accelerator, never the miner's own lane, never a timed control. Its stage holds
  the recipe's source and the Challenge's PUBLIC TRAIN only; inference, timing and grading ops stay on the door.
- **The door stays the only authority.** The ledger, the intents, the receipts and the state digest (computed by the
  door over the export streamed back by ``docker exec``) never leave the door. A box holds no key, no ledger and no
  pack; it only runs the pinned worker image (verified there by its image id) on the staged inputs.
- **Determinism.** The worker gets exactly the pinned environment every GPU rebuild gets
  (`accelerators.worker_environment`). The request binds the box's device record digest (and the slot count when there
  is more than one slot), so a build is compared only with the same build on the same GPU class and slot configuration.

**The box pool** (`door_pool`). The door's values row (`VALUES`: ``"<challenge> <version>"`` -> ``device_kind`` = the
CLASS, ``slots``, ``memory``) names the class. The boxes are the box files ``gpu_box_up.py door`` writes on PASS, in
``<HOST_ROOT>/remote-gpu-build-boxes.d/<name>.json`` (`BOXES_DIR`), read again at EVERY op (no restart). A box is
eligible only when (`read_box`): the directory is a 0700 directory of the door user; the file is a regular 0600 file
of the door user (never followed through a link); it is the box schema, its device kind is the class kind, its
``slot_cpusets`` are exactly 7 x 4 cores (`BOX_SLOT_CPUSETS`; a box set up before 17 Nov keeps its 4 x 4,
`LEGACY_BOX_SLOT_CPUSETS`, until `gpu_box_up.py` runs on it again), its ``host_key`` parses (an ed25519 known_hosts line for
its address) and its device record is well formed with its digest; and it is not DOWN (`mark_down`). A box file renamed
``<name>.json.refused`` (`refuse`) or removed is not read: removing it DRAINS the box (no new op starts there; a running
op keeps its binding to the end). The receiver binds the CLASS (`GpuClass`: ``{"kind", "class": true}``), never a box.

**Per box**, under ``<HOST_ROOT>/remote-gpu-build/box-<name>/`` (`BOX_DIR`): the slot locks and per-slot allocation
records, the lane gate, a copy of the box file (`BOX_COPY`, what recovery reads once the file is gone), and the ssh
material: ``known_hosts`` holding exactly the box's pinned host key, ``bin/ssh`` (a shim that runs the system ssh with
``StrictHostKeyChecking=yes`` and ``UserKnownHostsFile`` = that file, ``GlobalKnownHostsFile=/dev/null``) and the docker
wrapper ``docker`` (the local docker CLI with the box's ``DOCKER_HOST`` and ``PATH`` = the box's ``bin`` first, so
Docker's ssh:// connection helper, which runs ``ssh`` from ``PATH``, takes the shim). Every other ssh this module runs to
a box (mirror, discard, probes) passes the same pinned options itself (`_box_ssh`). ``~/.ssh/config`` is never edited.

**Choice, down, proven.** Each op takes a free slot on an eligible box: the box with the most free slots, then the name.
A box whose op failed with its link or GPU unhealthy is marked DOWN (`DOWN_MARKER`, a timestamp) and skipped for
`DOWN_SECONDS`, or until its next successful health probe, so a retry lands on another box. A box's FIRST real build is
also built, with the same graph/seed/recipe, on an already PROVEN box (the graph route's ``<task>~shadow``,
`research_tasks`): equal state digests mark the new box PROVEN (`PROVEN_MARKER`, bound to its box file's digest); unequal
ones refuse it and the task is FAILED_INFRA. While a box's first build runs, no other op starts there (`FIRST_BUILD`),
so that is the only extra build. With no proven box at all, the first box is proven by its own class check at once.

**Per build** (Validator-2's re-read): before the container is created, the box's GPU name and uuid (``nvidia-smi``) and
the image id (``docker image inspect``, `check_host`) are read again on the box; a mismatch with the box file is
FAILED_INFRA and the box file is renamed ``.refused``.

**Local slot lanes** (Lead, Mon 16 Nov: one design for both): the OLD lane record ``<HOST_ROOT>/remote-gpu-build-lanes.json``
(`RECORD`) is kept ONLY for a lane with ``"docker_host": null`` and ``"stage_root": null``: THIS host's own GPU (the
GPUYard 4090 lane), with this host's installed device record and daemon. A remote lane in that record refuses: a rented
box comes only from a box file. A local lane joins the pool as an always-proven member, never marked down.

**Zero boxes.** A pool with no box up (all released, drained or down) and no local lane builds graphs on the CPU, as a
door with no GPU lane does (`no_machine`, Lead + owner 17 Nov 2026), so boxes can be released when the queue is empty.

**Failure typing.** Any link fault raises `remote_lane.RemoteLaneDown` (WorkerFailure UNAVAILABLE: Carbon's
infrastructure, never the candidate's); an op that finds no eligible box after its graph was sent to the pool is the
same. A remote op that fails while the link or the GPU
is unhealthy (`healthy`) is retyped to it. This module sets no threshold and makes no scientific decision; the GPU class
is admitted for scoring only by the owner's hardware acceptance (`hardware_acceptance.require_accepted`), which the
receiver checks at start for the class kind.
"""

from __future__ import annotations

import ast
import base64
import binascii
import dataclasses
import fcntl
import json
import math
import os
import re
import shlex
import shutil
import stat
import subprocess
import time
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction import remote_lane
from carbon.reconstruction.remote_lane import RemoteLaneDown
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

#: The OLD lane record: kept for a LOCAL slot lane only (this host's GPU).
RECORD = "remote-gpu-build-lanes.json"
SCHEMA = "carbon.remote-gpu-build-lanes.v1"
#: The per-lane directory under HOST_ROOT of a local slot lane: its slot locks and records.
LANE_DIR = "remote-gpu-build/lane-{index}"
#: Under HOST_ROOT: what the pool shares (the alone marks, the pool lock), and each box's own directory.
POOL_DIR = "remote-gpu-build"
BOX_DIR = "remote-gpu-build/box-{name}"
#: Under HOST_ROOT: the box files `gpu_box_up.py door` writes (``--boxes-dir``), read at every op.
BOXES_DIR = "remote-gpu-build-boxes.d"
BOX_SCHEMA = "carbon.remote-gpu-build-box.v1"
#: Every box has the same shape (`gpu_box_up.SLOT_CPUSETS`): 7 slots of 4 cores (owner, 17 Nov 2026: "More build
#: spots per A100"; the Lambda A100 40GB box has 30 vCPUs, so 28 for the slots and 2 for the host; bench on the box,
#: commit 423c2bce: bit-identical at N=1/2/4/7, 2.5x throughput at 7, 524 MiB per build).
BOX_SLOT_CPUSETS = ("0-3", "4-7", "8-11", "12-15", "16-19", "20-23", "24-27")
#: The shape of a box set up before 17 Nov 2026 (4 slots): still read, its lane offers at most 4 slots.
LEGACY_BOX_SLOT_CPUSETS = BOX_SLOT_CPUSETS[:4]
#: A refused box file's suffix (`refuse`): the loader reads ``*.json`` only, so it drops out of the pool.
REFUSED_SUFFIX = ".refused"
#: In a box's directory: down since (`mark_down`), proven (`mark_proven`), its first build's claim, a copy of its file.
DOWN_MARKER = "down"
PROVEN_MARKER = "proven"
FIRST_BUILD = "first-build"
BOX_COPY = "box.json"
REFUSED_NOTE = "refused.json"
#: How long a box marked down is skipped (an operational bound, not a scientific value).
DOWN_SECONDS = 600
#: The graph route's first-build shadow op: ``<task>~shadow``, on a proven box other than the new one.
SHADOW_SUFFIX = "~shadow"
#: The values rows: ``{"schema", "rows": {"<challenge> <version>": {"device_kind": str, "slots"?: int}}}``.
VALUES = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "remote_gpu_build.json"
)
VALUES_SCHEMA = "carbon.remote-gpu-build.values.v1"
#: A local slot lane record names one lane.
MAX_LANES = 1
DEFAULT_SLOTS = 1
#: The most build slots one GPU may be split into (an operational bound, not a scientific value).
MAX_SLOTS = 8
#: How N > 1 slots share the device (the values row's ``"memory"``): ``"capped"`` (the default) = each process caps its
#: own share in-process (`SLOT_PRELUDE`, waits on Validator-2: `SLOT_PRELUDE_RULED`); ``"shared"`` = no cap at all: the
#: image-pinned platform allocator with no preallocation, so each build holds only the device memory it uses (Lead +
#: owner, 16 Nov: "no way we can only build 1 at a time"). Under ``"shared"`` a build's device memory exhaustion beside
#: another build is Carbon's (`shared_memory_exhausted`; a GPU OOM is never the miner's anyway).
SLOT_MEMORY_MODES = ("capped", "shared")
#: The share of device memory all slots together may take; each slot gets an equal part of it, rounded down to 0.01.
#: Operational headroom for the CUDA context and the driver, not a scientific value.
MEMORY_SHARE = 0.9
#: How long an op waits for a free slot before it is Carbon's (UNAVAILABLE); an operational bound.
SLOT_WAIT_SECONDS = 3600
POLL_S = 0.5
#: How long the GPU probe may take.
PROBE_SECONDS = 20
#: Whether more than one build may share a lane's GPU with an in-process cap (JAX_MEMORY_CAP_PLAN option A): that
#: override is Validator-2's to accept: False until V2 says yes, so a values row asking for more than one CAPPED slot
#: refuses (`door_pool`). It is the ONLY switch; flipping it changes nothing for a one-slot lane.
SLOT_PRELUDE_RULED = False
#: The environment variable the slot prelude reads: this process's share of the device (``0.9 / N``, two decimals).
SLOT_FRACTION_ENV = "CARBON_SLOT_MEMORY_FRACTION"
#: What the prelude sets for JAX before any import (read when JAX's GPU backend starts).
SLOT_JAX_ENVIRONMENT = {
    "XLA_PYTHON_CLIENT_ALLOCATOR": "bfc",
    "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
}
#: The ops a box may run: a direct task's build child, a graph first-build shadow, or an old GPU repeat probe.
_BUILD_IDENTITY = re.compile(r"direct-[0-9a-f]{64}-build|.{1,200}(~gpu[12]|~shadow)")
_DEVICE_KIND = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()-]{0,63}")
_HOME = re.compile(r"/[A-Za-z0-9._/-]{0,255}")
_BOX_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_BOX_FILE_MAX = 1 << 20
_SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"


@dataclass(frozen=True)
class GpuBuildSpec:
    """One GPU build machine: a box (`read_box`) or a local slot lane (`load`)."""

    index: int
    #: The box's ssh daemon, or None: THIS host's own GPU (a local slot lane: the GPUYard 4090's).
    docker_host: str | None
    #: Where inputs are mirrored on the box; None for a local lane (nothing to mirror).
    stage_root: str | None

    @property
    def local(self):
        return self.docker_host is None

    slot_cpusets: tuple[str, ...]
    #: The box's name (its file's stem); a local lane's is ``lane-<index>``.
    name: str = "lane-0"
    #: The box's pinned known_hosts line (its ssh host key); None for a local lane.
    host_key: str | None = None
    #: The worker image ids the box was admitted with (its file's ``images``); () for a local lane.
    images: tuple[str, ...] = ()
    #: The box file it was read from; None for a local lane.
    box_file: str | None = None
    #: The digest of the box document (binds its proven marker to this admission); None for a local lane.
    box_digest: str | None = None
    #: The box document, canonical JSON (copied to `BOX_COPY` for recovery); None for a local lane.
    box_document: str | None = None
    #: The door's private key for the box's lane user, as its box file names it (``ssh_key``: an absolute path on the
    #: door, never the key itself); None: the door's own ssh configuration decides (a box admitted before this field).
    ssh_key: str | None = None


@dataclass(frozen=True)
class DoorLane:
    """One machine of the pool an op can take a slot on: its spec, the class slot count and its device record."""

    spec: GpuBuildSpec
    slots: int
    device: object  # host_inventory.HostDeviceRecord (None only for a gone box's binding: `recorded`)
    lane_dir: str
    #: `SLOT_MEMORY_MODES`: how N > 1 slots share the device (meaningless at N = 1)
    memory: str = "capped"

    @property
    def pool_dir(self) -> Path:
        return Path(self.lane_dir).parent


@dataclass(frozen=True)
class DoorPool:
    """The CLASS a door's builds are offered (`door_pool`): the values row and where its boxes are read from. The
    machines themselves are read at each op (`_candidates`)."""

    kind: str
    slots: int
    memory: str
    root: str
    #: a local slot lane of the old record (this host's GPU), or None
    local: DoorLane | None = None

    @property
    def pool_dir(self) -> Path:
        return Path(self.root) / POOL_DIR


@dataclass(frozen=True)
class GpuClass:
    """What the receiver binds about its graph GPU lane when the door builds on the pool: the class, never a box."""

    device_kind: str

    def door_binding(self):
        return {"kind": self.device_kind, "class": True}


@dataclass(frozen=True)
class OpBinding:
    """One op bound to one slot of one machine (`op`, `recorded`)."""

    lane: DoorLane
    slot: int
    #: the build's content key (`alone_key`): where an uncounted wall stop marks the build for an ALONE retry
    key: str | None = None
    #: whether this op holds every slot of its machine (an alone retry)
    alone: bool = False
    #: a recorded op whose box file is gone (`recorded`): recovery only clears its local slot record
    gone: bool = False

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


class _Offer:
    """What one build was offered (`offered`, `offered_for`): a pool, or one fixed machine; and the first-build claims
    its ops took (released when the offer ends)."""

    def __init__(self, pool=None, *, fixed=None, withheld=False, image_id=None):
        self.pool, self.fixed, self.withheld = pool, fixed, withheld
        #: the GPU worker image this build's ops run (the door's graph GPU image), or None (unknown: every box)
        self.image_id = image_id
        self.claims = []

    def serves(self, lane):
        """Whether ``lane`` may take this build's ops: a local lane always; a box only when it was admitted with the
        build's image (a box admitted before a door switched its image is skipped, never refused).
        """
        return (
            lane.spec.local
            or self.image_id is None
            or not lane.spec.images
            or self.image_id in lane.spec.images
        )

    @property
    def slots(self):
        return (self.fixed or self.pool).slots

    @property
    def offered(self):
        return self.fixed or self.pool


_OFFERED: ContextVar[_Offer | None] = ContextVar(
    "carbon_remote_gpu_build_offered", default=None
)
_OP: ContextVar[OpBinding | None] = ContextVar(
    "carbon_remote_gpu_build_op", default=None
)
#: Inside `shadowing`: the new box a shadow op must NOT run on (it runs on a proven box).
_SHADOW_OF: ContextVar[str | None] = ContextVar(
    "carbon_remote_gpu_build_shadow_of", default=None
)
#: A slot op's binding handed to a process it spawns (its watchdog): the op's intent fields as JSON. Read only when no
#: binding is set in the context, so the door process itself (which never sets it) is unaffected.
ENVIRONMENT = "CARBON_REMOTE_GPU_BUILD"
#: The class each door bound at start (`pin`): ``{(challenge_id, version): class fingerprint or None}``.
_PINNED: dict = {}
_ENVIRONMENT_BINDING: list = []


def _current():
    """The running op's slot binding: the context's, else (in a process a slot op spawned) the one it was handed."""
    binding = _OP.get()
    if binding is not None or ENVIRONMENT not in os.environ:
        return binding
    if not _ENVIRONMENT_BINDING:
        # Self-contained (`_handoff`): never re-read from the operator's files, which may have changed since the op
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
            "name": spec.name,
            "host_key": spec.host_key,
            "images": list(spec.images),
            "box_file": spec.box_file,
            "box_digest": spec.box_digest,
            "slots": binding.lane.slots,
            "memory": binding.lane.memory,
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
            entry.get("name", "lane-0"),
            entry.get("host_key"),
            tuple(entry.get("images", ())),
            entry.get("box_file"),
            entry.get("box_digest"),
        )
        slot = entry["slot"]
        if type(slot) is not int or not 0 <= slot < len(spec.slot_cpusets):
            return None
        memory = entry.get("memory", "capped")
        if memory not in SLOT_MEMORY_MODES:
            return None
        return OpBinding(
            DoorLane(spec, entry["slots"], device, entry["lane_dir"], memory), slot
        )
    except (ValueError, TypeError, KeyError, WorkerFailure):
        return None


# -- configuration ---------------------------------------------------------------------------------------------------------


def _host_root(root):
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    return Path(HOST_ROOT if root is None else root)


def load(root=None):
    """The installed LOCAL slot lane of the old record (a tuple of `GpuBuildSpec`), ``()`` when none is installed. A
    record that is present but malformed, or that names a remote lane (a rented box is a box file now), raises
    ValueError: an operator who installed one meant something by it.
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
        if entry["docker_host"] is not None or entry["stage_root"] is not None:
            # a rented box is admitted by its own box file (`BOXES_DIR`), with its pinned host key
            raise ValueError("remote_gpu_build_record_remote_lane_needs_a_box_file")
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
        specs.append(GpuBuildSpec(index, None, None, tuple(cpusets), f"lane-{index}"))
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
        {"device_kind", "slots", "memory"},
    ):
        return None
    kind = row["device_kind"]
    slots = row.get("slots", DEFAULT_SLOTS)
    if type(kind) is not str or not _DEVICE_KIND.fullmatch(kind):
        return None
    if type(slots) is not int or not 1 <= slots <= MAX_SLOTS:
        return None
    memory = row.get("memory", "capped")
    if memory not in SLOT_MEMORY_MODES:
        return None
    return {"device_kind": kind, "slots": slots, "memory": memory}


def door_pool(challenge_id, version, *, root=None, values=None):
    """The box pool a door of ``"<challenge_id> <version>"`` offers its GPU builds (a `DoorPool`: the CLASS), or None
    (no values row, or neither the boxes directory nor a local slot lane is installed: today's path). It needs no box:
    a pool with no box up is still the pool; a graph offered it then builds on the CPU (`no_machine`), and an op that
    finds no box after all (the last one went while it was chosen) is Carbon's (`RemoteLaneDown`). A row asking for more
    slots than a machine has cores for, a capped N > 1 before Validator-2's ruling, or a local lane whose device record
    is missing or of another kind raises ValueError: the door refuses rather than build on a machine it cannot describe.
    """
    row = values_row(challenge_id, version, path=values)
    if row is None:
        return None
    host = _host_root(root)
    specs = load(root)
    boxes = os.path.lexists(host / BOXES_DIR)
    if not specs and not boxes:
        return None
    if row["slots"] > 1 and row["memory"] == "capped" and not SLOT_PRELUDE_RULED:
        # every build offered a box is a graph build on the JAX worker: N > 1 shares the device, capped per process
        # only by the slot prelude, which waits on Validator-2's ruling (`SLOT_PRELUDE_RULED`)
        raise ValueError("remote_gpu_build_slots_need_jax_memory_cap")
    if boxes and row["slots"] > len(BOX_SLOT_CPUSETS):
        raise ValueError("remote_gpu_build_slots_exceed_cpusets")
    local = None
    if specs:
        spec = specs[0]
        if row["slots"] > len(spec.slot_cpusets):
            raise ValueError("remote_gpu_build_slots_exceed_cpusets")
        device = _lane_device(host)
        if device.device_kind != row["device_kind"]:
            raise ValueError("remote_gpu_build_device_kind")
        local = DoorLane(
            spec,
            row["slots"],
            device,
            str(host / LANE_DIR.format(index=spec.index)),
            row["memory"],
        )
    return DoorPool(row["device_kind"], row["slots"], row["memory"], str(host), local)


#: The most boxes a pool may hold at once: the owner's on-demand line (16 Nov 2026, Compute Ops: "up to 3 boxes and
#: USD 6/h total"). It sizes the door's build rounds only (`door_build_slots`); the renting itself is Compute Ops'.
MAX_BOXES = 3


def door_build_slots(challenge_id, version, *, root=None, values=None):
    """How many build rounds a door's REMOTE GPU build boxes may keep busy at once (its extra build rounds,
    `direct_intake._remote_build_slots`): ``slots`` per box times `MAX_BOXES` for a box pool (boxes come and go without
    a restart, so the door sizes for the most it may have; a round that finds every slot busy waits for one with its
    local lane given back), 0 without a pool. A local slot lane adds nothing (its builds hold their lane). ValueError as
    `door_pool`."""
    pool = door_pool(challenge_id, version, root=root, values=values)
    if pool is None or not os.path.lexists(Path(pool.root) / BOXES_DIR):
        return 0
    return pool.slots * MAX_BOXES


def _lane_device(directory):
    """A strict device record bound to the GPU profile (a local lane's: this host's installed record), or ValueError."""
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.host_inventory import (
        HostDeviceRecord,
        require_host_device,
    )

    try:
        return require_host_device(HostDeviceRecord.load(directory), GPU_PROFILE)
    except WorkerFailure:
        raise ValueError("remote_gpu_build_device_record") from None


# -- box files --------------------------------------------------------------------------------------------------------------


def parse_host_key(line, docker_host):
    """The box's pinned known_hosts line, exactly as the box file has it, or ValueError: ``<host> ssh-ed25519 <key>``
    for the box's own address (``[host]:port`` off port 22), the key a well-formed ed25519 public key.
    """
    if type(line) is not str:
        raise ValueError("remote_gpu_build_box_host_key")
    parts = line.split(" ")
    _, host, port = remote_lane.parse_docker_host(docker_host)
    if len(parts) != 3 or parts[1] != "ssh-ed25519":
        raise ValueError("remote_gpu_build_box_host_key")
    if parts[0] != (host if port == 22 else f"[{host}]:{port}"):
        raise ValueError("remote_gpu_build_box_host_key")
    try:
        blob = base64.b64decode(parts[2], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("remote_gpu_build_box_host_key") from None
    if (
        len(blob) != 51
        or blob[:15] != b"\x00\x00\x00\x0bssh-ed25519"
        or blob[15:19] != b"\x00\x00\x00\x20"
    ):
        raise ValueError("remote_gpu_build_box_host_key")
    return line


def _private_dir(path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return (
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.geteuid()
        and stat.S_IMODE(info.st_mode) == 0o700
    )


def _read_private(path, *, limit=_BOX_FILE_MAX):
    """A regular 0600 file of this user (never through a link), or ValueError naming why not."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ValueError("remote_gpu_build_box_unreadable") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("remote_gpu_build_box_not_a_file")
        if info.st_uid != os.geteuid():
            raise ValueError("remote_gpu_build_box_owner")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("remote_gpu_build_box_mode")
        if info.st_size > limit:
            raise ValueError("remote_gpu_build_box_size")
        chunks = []
        while chunk := os.read(fd, 65536):
            chunks.append(chunk)
            if sum(map(len, chunks)) > limit:
                raise ValueError("remote_gpu_build_box_size")
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_box(path, *, kind, slots=DEFAULT_SLOTS, memory="capped", root=None):
    """One box file as a pool machine (a `DoorLane`), or ValueError naming why it is not eligible (`BOXES_DIR`): its
    mode, owner, shape, schema, name, address, stage root, host key, images, device record or class kind. Marks (down,
    proven) are not read here."""
    path = Path(path)
    name = path.name[: -len(".json")] if path.name.endswith(".json") else ""
    if not _BOX_NAME.fullmatch(name):
        raise ValueError("remote_gpu_build_box_name")
    try:
        document = json.loads(_read_private(path))
    except UnicodeDecodeError:
        raise ValueError("remote_gpu_build_box_json") from None
    return _box_lane(
        document,
        name=name,
        kind=kind,
        slots=slots,
        memory=memory,
        root=_host_root(root),
        box_file=str(path),
    )


def _box_lane(document, *, name, kind, slots, memory, root, box_file):
    from carbon.development_session.profile import canonical, digest

    if type(document) is not dict or document.get("schema") != BOX_SCHEMA:
        raise ValueError("remote_gpu_build_box_schema")
    if document.get("name") != name:
        raise ValueError("remote_gpu_build_box_name")
    cpusets = document.get("slot_cpusets")
    if cpusets not in (list(BOX_SLOT_CPUSETS), list(LEGACY_BOX_SLOT_CPUSETS)):
        raise ValueError("remote_gpu_build_box_shape")
    cpusets = tuple(cpusets)
    docker_host = document.get("docker_host")
    remote_lane.parse_docker_host(docker_host)
    stage_root = remote_lane._checked_root(document.get("stage_root"))
    host_key = parse_host_key(document.get("host_key"), docker_host)
    images = document.get("images")
    if (
        type(images) is not list
        or not images
        or any(
            type(image) is not str or not _IMAGE_ID.fullmatch(image) for image in images
        )
    ):
        raise ValueError("remote_gpu_build_box_images")
    ssh_key = document.get("ssh_key")
    if ssh_key is not None and (
        type(ssh_key) is not str or not _HOME.fullmatch(ssh_key)
    ):
        raise ValueError("remote_gpu_build_box_ssh_key")
    device = _box_device(document.get("device"), document.get("device_digest"))
    if kind is not None and device.device_kind != kind:
        raise ValueError("remote_gpu_build_box_device_kind")
    text = canonical(document).decode("utf-8")
    spec = GpuBuildSpec(
        0,
        docker_host,
        stage_root,
        cpusets,
        name,
        host_key,
        tuple(images),
        box_file,
        digest(text.encode("utf-8")),
        text,
        ssh_key,
    )
    # a legacy 4-slot box offers at most its own 4 slots, whatever the values row asks
    return DoorLane(
        spec,
        min(slots, len(cpusets)),
        device,
        str(root / BOX_DIR.format(name=name)),
        memory,
    )


def _box_device(document, device_digest):
    from carbon.development_session.profile import canonical
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.host_inventory import (
        HostDeviceRecord,
        require_host_device,
        tagged_sha256,
    )

    try:
        if (
            type(document) is not dict
            or tagged_sha256(canonical(document)) != device_digest
        ):
            raise ValueError("remote_gpu_build_box_device")
        return require_host_device(
            HostDeviceRecord(document, device_digest), GPU_PROFILE
        )
    except (WorkerFailure, TypeError, AttributeError):
        raise ValueError("remote_gpu_build_box_device") from None


def boxes(pool):
    """Every well-formed box of ``pool``'s class, read now, by name (down boxes included: `_candidates` skips them). A
    boxes directory that is not this user's 0700 directory holds no box."""
    directory = Path(pool.root) / BOXES_DIR
    if not _private_dir(directory):
        return ()
    found = []
    for path in sorted(directory.glob("*.json")):
        if "." in path.name[: -len(".json")]:
            continue  # <name>.class-check.json, <name>.ops-record.json
        try:
            found.append(
                read_box(
                    path,
                    kind=pool.kind,
                    slots=pool.slots,
                    memory=pool.memory,
                    root=pool.root,
                )
            )
        except ValueError:
            continue
    return tuple(found)


# -- marks: down, proven, first build, refused ---------------------------------------------------------------------------


def _write_mark(path, document):
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}")
        temporary.write_text(json.dumps(document, sort_keys=True) + "\n")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    except OSError:
        return False
    return True


def _read_mark(path):
    try:
        if path.is_symlink():
            return None
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return value if type(value) is dict else None


def mark_down(lane, reason=b""):
    """Mark ``lane``'s box DOWN now (its link or GPU was lost): skipped for `DOWN_SECONDS` or until it is healthy."""
    if lane is None or lane.spec.local:
        return False
    return _write_mark(
        Path(lane.lane_dir) / DOWN_MARKER,
        {"unix": time.time(), "reason": bytes(reason)[:200].decode("utf-8", "replace")},
    )


def is_down(lane):
    """Whether ``lane``'s box was marked down less than `DOWN_SECONDS` ago."""
    if lane.spec.local:
        return False
    mark = _read_mark(Path(lane.lane_dir) / DOWN_MARKER)
    if mark is None or type(mark.get("unix")) not in (int, float):
        return False
    return time.time() - mark["unix"] < DOWN_SECONDS


def clear_down(lane):
    if lane is not None and not lane.spec.local:
        try:
            (Path(lane.lane_dir) / DOWN_MARKER).unlink(missing_ok=True)
        except OSError:
            pass


def is_proven(lane):
    """Whether ``lane`` is PROVEN: a local lane always; a box when its proven marker names its box file's digest."""
    if lane.spec.local:
        return True
    mark = _read_mark(Path(lane.lane_dir) / PROVEN_MARKER)
    return mark is not None and mark.get("box_digest") == lane.spec.box_digest


def mark_proven(lane, how):
    """Mark ``lane``'s box PROVEN (``how``: ``"first_box"``, its own class check; ``"shadow"``, equal state digests)."""
    if lane.spec.local:
        return True
    return _write_mark(
        Path(lane.lane_dir) / PROVEN_MARKER,
        {"box_digest": lane.spec.box_digest, "how": how, "unix": time.time()},
    )


def refuse(lane, reason):
    """Drop ``lane``'s box out of the pool: its box file is renamed ``<name>.json.refused`` (atomic), and the reason is
    noted in its directory. Returns the `RemoteLaneDown` (FAILED_INFRA) the caller raises.
    """
    error = RemoteLaneDown(bytes(reason)[:512])
    error.box_refused = True
    if lane is None or lane.spec.local or lane.spec.box_file is None:
        return error
    try:
        os.rename(lane.spec.box_file, lane.spec.box_file + REFUSED_SUFFIX)
    except OSError:
        pass
    _write_mark(
        Path(lane.lane_dir) / REFUSED_NOTE,
        {
            "box_digest": lane.spec.box_digest,
            "reason": bytes(reason)[:200].decode("utf-8", "replace"),
            "unix": time.time(),
        },
    )
    return error


def _claim_owner():
    from carbon.reconstruction import grade_lanes

    return (
        f"{os.getpid()}-{grade_lanes.process_start(os.getpid())}-{time.monotonic_ns()}"
    )


def _claim(lane):
    """Take ``lane``'s first-build claim (`FIRST_BUILD`), or None while another live op holds it."""
    from carbon.reconstruction import grade_lanes

    path = Path(lane.lane_dir) / FIRST_BUILD
    owner = _claim_owner()
    for _ in range(2):
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                held = path.read_text().strip()
            except OSError:
                continue
            if grade_lanes._live(held):
                return None
            path.unlink(missing_ok=True)  # a lost process's claim
            continue
        except OSError as error:
            raise RemoteLaneDown(repr(error).encode()[:512]) from None
        with os.fdopen(fd, "w") as stream:
            stream.write(owner)
        return owner
    return None


def _release_claim(lane, owner):
    if owner is None:
        return  # a replay's entry (`_settled_binding`): it took no claim file
    path = Path(lane.lane_dir) / FIRST_BUILD
    try:
        if path.read_text().strip() == owner:
            path.unlink()
    except OSError:
        pass


@contextmanager
def _pool_lock(pool):
    path = pool.pool_dir / "pool.lock"
    fd = _open(path)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _proven_other(pool, name):
    return any(box.spec.name != name and is_proven(box) for box in boxes(pool))


def _admit(offer, lane):
    """Whether an ordinary op may start on ``lane``: a proven box (or a local lane, or a fixed offer); the first box of
    a pool with no proven box (proven at once by its own class check); or an unproven box whose first-build claim this
    op takes (its build is then shadowed on a proven box: `first_build_box`)."""
    if offer.fixed is not None or is_proven(lane):
        return True
    with _pool_lock(offer.pool):
        if is_proven(lane):
            return True
        if not _proven_other(offer.pool, lane.spec.name):
            mark_proven(lane, "first_box")
            return True
        # under the pool lock: a claim file read between another op's create and its write is never taken as dead
        owner = _claim(lane)
    if owner is None:
        return False
    offer.claims.append((lane, owner))
    return True


def first_build_box():
    """The unproven box a real build of the current offer ran on (it holds that box's first-build claim), or None."""
    offer = _OFFERED.get()
    if offer is None:
        return None
    for lane, _ in offer.claims:
        if not is_proven(lane):
            return lane
    return None


def proven_elsewhere(lane):
    """Whether a proven box of the current offer's pool other than ``lane`` exists (else ``lane`` is the first box)."""
    offer = _OFFERED.get()
    return (
        offer is not None
        and offer.pool is not None
        and _proven_other(offer.pool, lane.spec.name)
    )


@contextmanager
def shadowing(lane):
    """Ops started inside run only on a proven box other than ``lane`` (the first-build shadow of ``lane``)."""
    token = _SHADOW_OF.set(lane.spec.name)
    try:
        yield
    finally:
        _SHADOW_OF.reset(token)


# -- binding ---------------------------------------------------------------------------------------------------------------


@contextmanager
def _offering(offer):
    token = _OFFERED.set(offer)
    try:
        yield
    finally:
        _OFFERED.reset(token)
        for lane, owner in offer.claims:
            _release_claim(lane, owner)


@contextmanager
def offered(lane):
    """Offer ``lane`` (a `DoorPool`, one fixed `DoorLane`, or None: nothing changes) to the GPU builds started inside."""
    if lane is None:
        with _offering_none():
            yield None
        return
    if type(lane) is DoorPool:
        offer = _Offer(lane)
    elif type(lane) is DoorLane:
        offer = _Offer(fixed=lane)
    else:
        raise ValueError("remote_gpu_build_lane")
    with _offering(offer):
        yield lane


@contextmanager
def _offering_none():
    token = _OFFERED.set(None)
    try:
        yield
    finally:
        _OFFERED.reset(token)


def pin(challenge_id, version, pool):
    """Record the class a door bound at start (``pool`` a `DoorPool`, or None), so a build never runs on another
    class than the one the door's binding names (`offered_for`). No box is pinned: boxes come and go.
    """
    _PINNED[(challenge_id, version)] = fingerprint(pool)


def fingerprint(pool):
    """What a door binds about its pool: the class (kind, slots, memory) and whether a local lane is in it."""
    if pool is None:
        return None
    return (pool.kind, pool.slots, pool.memory, pool.local is not None)


@contextmanager
def offered_for(
    challenge_id, version, *, root=None, values=None, withhold=False, image_id=None
):
    """`offered` with the door's pool for ``"<challenge_id> <version>"`` (`door_pool`), read at the build. Carbon's
    (`RemoteLaneDown`), never the build's: a configuration that broke since the door started, or a class that differs
    from the one the door bound at start (`pin`).

    ``withhold``: this build's stage holds something that may not leave the door (a HOST-PRIVATE seed: the crown's
    averaging rebuilds). Whether such a build may go to a rented machine is the owner's decision, not made here: while
    a pool is configured, its GPU build ops refuse as Carbon's instead of running anywhere else.
    """
    try:
        pool = door_pool(challenge_id, version, root=root, values=values)
    except (ValueError, OSError) as error:
        raise RemoteLaneDown(str(error).encode()[:512]) from None
    key = (challenge_id, version)
    if key in _PINNED and _PINNED[key] != fingerprint(pool):
        raise RemoteLaneDown(b"remote_gpu_build_class_changed_since_start")
    if pool is None:
        with _offering_none():
            yield None
        return
    with _offering(_Offer(pool, withheld=withhold, image_id=image_id)):
        yield pool


def offered_lane():
    """What the running build was offered (a `DoorPool` or a fixed `DoorLane`), or None (also when withheld)."""
    offer = _OFFERED.get()
    return None if offer is None or offer.withheld else offer.offered


def offered_off_host():
    """Whether an op the running build was offered runs on none of this host's cores: a fixed REMOTE machine, or a box
    pool with no local slot lane (every machine in it is a rented box). A pool that also holds this host's GPU lane may
    place an op here, so it is not (the op keeps its round's local lane). False when nothing is offered or withheld.
    """
    offer = offered_lane()
    if offer is None:
        return False
    if type(offer) is DoorPool:
        return offer.local is None
    return not offer.spec.local


def eligible(identity, *, accelerator, provenance, timed):
    """Whether an op may run on a GPU build box: a GPU build (`_BUILD_IDENTITY`) with an accelerator, never the miner's
    own lane, never a timing measurement."""
    return (
        accelerator is not None
        and provenance != "MINER_SELF_REPORTED"
        and not timed
        and type(identity) is str
        and _BUILD_IDENTITY.fullmatch(identity) is not None
    )


def no_machine():
    """Whether the running build was offered a POOL that has no machine up now: no local slot lane and no eligible box
    that is not down (read now, `boxes`). Its graph then builds on the CPU exactly as a door with no GPU lane does (Lead
    + owner, 17 Nov 2026: with zero boxes the door builds on the CPU; a box comes back when the queue grows). A withheld
    build or a fixed machine is never "no machine" here: those keep their own refusal (`op`).
    """
    offer = _OFFERED.get()
    if offer is None or offer.withheld or offer.fixed is not None:
        return False
    pool = offer.pool
    if pool.local is not None:
        return False
    return not any(not is_down(box) and offer.serves(box) for box in boxes(pool))


def current_op():
    """The slot binding of the running op, or None (the door's own daemon)."""
    return _current()


# -- the alone retry (Validator-2, 16 Nov: a wall stop beside a neighbour is never counted, so its retry runs ALONE) ----


#: Where builds marked for an alone retry are recorded, in the pool's directory: one file per build content key (a
#: retry may land on any box).
ALONE_DIR = "alone"
#: Live alone retries waiting for a box: while one waits, no new op starts on that box.
ALONE_WANTED_DIR = "alone.wanted"
#: Every op of a box with more than one slot holds this SHARED for its life; an alone retry holds it EXCLUSIVE.
GATE_LOCK = "gate.lock"
_KEY = re.compile(r"[0-9a-f]{64}")


def alone_key(*, source, files, image_id):
    """A build's content key: its program, its staged files and its worker image. A retry of the same build (same
    recipe, TRAIN, seed and image) has the same key whatever its task or operation identity.
    """
    import hashlib

    if type(source) is not str or type(files) is not dict or type(image_id) is not str:
        return None
    entries = []
    for name in sorted(files):
        body = files[name]
        if type(name) is not str or type(body) not in (bytes, str):
            return None
        data = body.encode() if type(body) is str else body
        entries.append([name, hashlib.sha256(data).hexdigest()])
    document = json.dumps(
        {
            "source": hashlib.sha256(source.encode()).hexdigest(),
            "files": entries,
            "image": image_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(document).hexdigest()


def _marker(where, key):
    if type(key) is not str or not _KEY.fullmatch(key):
        return None
    return where.pool_dir / ALONE_DIR / key


#: How long a mark stands: a build not retried within this is not waiting for its retry any more (an operational
#: bound, so a mark nothing cleared, e.g. a repeat probe's or a withdrawn build's, never costs a box for good).
ALONE_MARK_SECONDS = 24 * 3600


def needs_alone(where, key):
    """Whether the build of ``key`` is marked for an alone retry in ``where``'s pool (a `DoorPool` or a `DoorLane`; a
    mark younger than `ALONE_MARK_SECONDS`; an older one is removed)."""
    marker = None if where is None else _marker(where, key)
    if marker is None:
        return False
    try:
        age = time.time() - marker.stat().st_mtime
    except OSError:
        return False
    if age > ALONE_MARK_SECONDS:
        marker.unlink(missing_ok=True)
        return False
    return True


def note_uncounted_wall(binding=None):
    """Mark the running op's build for an ALONE retry: its wall stop was not counted on a box shared by more than one
    slot (a busy box is never quiet, so only a retry with the GPU to itself can give a decisive verdict). Best effort:
    a marker that cannot be written leaves the build to an ordinary retry."""
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.slots == 1:
        return False
    marker = _marker(binding.lane, binding.key)
    if marker is None:
        return False
    if binding.alone:
        # the alone retry itself was not counted (a foreign process or the link, not a neighbour): it is not retried
        # alone again, so a box that cannot be read never holds the whole box over and over; its retry is ordinary
        marker.unlink(missing_ok=True)
        return False
    try:
        marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        marker.write_text(json.dumps({"key": binding.key, "unix": time.time()}) + "\n")
        marker.chmod(0o600)
    except OSError:
        return False
    return True


def clear_alone(binding=None):
    """The running alone retry reached a verdict: its build's mark is removed."""
    binding = _current() if binding is None else binding
    if binding is None or not binding.alone:
        return
    marker = _marker(binding.lane, binding.key)
    if marker is not None:
        marker.unlink(missing_ok=True)


def _wanted_by_others(directory, own):
    """Whether a live alone retry other than ``own`` waits for the box."""
    from carbon.reconstruction import grade_lanes

    folder = directory / ALONE_WANTED_DIR
    try:
        names = [entry.name for entry in folder.iterdir()]
    except OSError:
        return False
    return any(name != own and grade_lanes._live(name) for name in names)


def _candidates(offer, *, shadow):
    """The machines an op may start on now: the offer's fixed machine, or the pool's local lane and every eligible box
    (read now, down ones skipped). A shadow op: only proven ones, never the box it shadows.
    """
    if offer.fixed is not None:
        lanes = (offer.fixed,)
    else:
        pool = offer.pool
        lanes = (() if pool.local is None else (pool.local,)) + tuple(
            box for box in boxes(pool) if not is_down(box) and offer.serves(box)
        )
    if shadow:
        avoid = _SHADOW_OF.get()
        lanes = tuple(
            lane for lane in lanes if lane.spec.name != avoid and is_proven(lane)
        )
    return lanes


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
    key=None,
    recorded=None,
):
    """Bind an eligible op (`eligible`) of a build that was offered a pool to one free slot of one machine for its
    whole life; anything else: unchanged (yields None). The machine: an eligible box with a free slot, the most free
    slots first, then the name (`_take`). No eligible box is Carbon's at once (`RemoteLaneDown`); no free slot within
    `SLOT_WAIT_SECONDS` too. ``check`` is called while waiting (the op's cancellation), and may raise. A slot whose
    allocation record a lost controller left behind is passed over until recovery clears it.

    On a machine with more than one slot every op holds its gate (`GATE_LOCK`) SHARED. A build whose ``key`` is marked
    for an ALONE retry (`needs_alone`) announces itself on the box it chose (`ALONE_WANTED_DIR`), so no new op starts
    there; takes the gate EXCLUSIVE once the running ops have ended; and holds EVERY slot for its life, so its box is
    quiet and its wall can count (CV-Motor L12624).

    An op whose link or GPU is found unhealthy when it fails as Carbon's marks its box DOWN (`mark_down`).
    ``recorded``: a settled op's recorded binding (`recorded`), which its replay binds (its request names that box).
    """
    offer = _OFFERED.get()
    if offer is None or not eligible(
        identity, accelerator=accelerator, provenance=provenance, timed=timed
    ):
        yield None
        return
    if offer.withheld:
        raise RemoteLaneDown(b"remote_gpu_build_withheld_host_private_build")
    if settled:
        # an op the ledger has settled replays its recorded result: bound to the box it ran on (its request, its
        # device, its program are that box's, so the replay matches what was reserved), but it runs nothing and takes
        # no slot
        token = _OP.set(_settled_binding(offer, recorded, key))
        try:
            yield _OP.get()
        finally:
            _OP.reset(token)
        return
    pause = time.sleep if sleep is None else sleep
    poll = POLL_S if poll_s is None else poll_s
    deadline = time.monotonic() + SLOT_WAIT_SECONDS
    from carbon.reconstruction import grade_lanes

    with ExitStack() as held:
        with grade_lanes.timed_wait():  # a slot wait is Carbon's queue (`grade_lanes.waited_seconds`)
            binding = _take(
                offer,
                identity,
                key,
                held=held,
                check=check,
                pause=pause,
                poll=poll,
                deadline=deadline,
            )
        token = _OP.set(binding)
        try:
            yield binding
        except RemoteLaneDown as error:
            _note_loss(binding, error)
            raise
        finally:
            _OP.reset(token)


def _settled_binding(offer, recorded, key):
    if recorded is not None and recorded.lane.device is not None:
        lane = recorded.lane
        if offer.fixed is None:
            lane = dataclasses.replace(
                lane, slots=offer.pool.slots, memory=offer.pool.memory
            )
            if not is_proven(lane):
                # a build settled on a box never proven (a restart during its shadow): it is still that box's first
                # build, so the task shadows it again (`first_build_box`); no claim file is taken for a replay
                offer.claims.append((lane, None))
        return OpBinding(lane, recorded.slot, key)
    if offer.fixed is None:
        # a pool: the box a settled op ran on is never guessed (a wrong box's request is a replay conflict)
        raise RemoteLaneDown(b"remote_gpu_build_settled_box_unknown")
    lanes = _candidates(offer, shadow=False)
    if not lanes:
        raise RemoteLaneDown(b"remote_gpu_build_no_box")
    return OpBinding(lanes[0], 0, key)


def _note_loss(binding, error):
    """A box op that failed as Carbon's with its link or GPU lost: its box is DOWN (`DOWN_SECONDS`)."""
    if binding.lane.spec.local or getattr(error, "box_refused", False):
        return
    diagnostic = getattr(error, "private_diagnostic", b"")
    if diagnostic == b"remote_gpu_build_unhealthy_after_failure" or not healthy(
        binding
    ):
        mark_down(binding.lane, diagnostic)


def _take(offer, identity, key, *, held, check, pause, poll, deadline):
    shadow = type(identity) is str and identity.endswith(SHADOW_SUFFIX)
    alone = offer.slots > 1 and needs_alone(offer.offered, key)
    while True:
        lanes = _candidates(offer, shadow=shadow)
        if not lanes:
            raise RemoteLaneDown(
                b"remote_gpu_build_no_proven_box"
                if shadow
                else b"remote_gpu_build_no_box"
            )
        order = sorted(lanes, key=lambda lane: (-_free_slots(lane), lane.spec.name))
        if alone:
            lane = next((lane for lane in order if shadow or _admit(offer, lane)), None)
            if lane is not None:
                _ensure_box_files(lane)
                held.enter_context(
                    _gate(
                        lane,
                        alone=True,
                        check=check,
                        pause=pause,
                        poll=poll,
                        deadline=deadline,
                    )
                )
                held.enter_context(
                    _all_slots(
                        lane, check=check, pause=pause, poll=poll, deadline=deadline
                    )
                )
                return OpBinding(lane, 0, key, alone=True)
        else:
            for lane in order:
                binding = _try_lane(offer, lane, key, held=held, shadow=shadow)
                if binding is not None:
                    return binding
        if offer.fixed is None and any(_live_ops(lane) for lane in lanes):
            # a pool's build rounds are sized for its most boxes (`door_build_slots`), so a round may wait behind
            # live builds on the boxes up: that wait is progress, never Carbon's failure; the wall-clock bound is for
            # slots no live op holds (a lost controller's record)
            deadline = max(deadline, time.monotonic() + SLOT_WAIT_SECONDS)
        _wait(check, deadline, pause, poll, b"remote_gpu_build_slots_busy")


def _try_lane(offer, lane, key, *, held, shadow):
    """One free slot of ``lane`` (with its gate SHARED on a multi-slot machine) for an ordinary op, or None."""
    inner = ExitStack()
    try:
        if lane.slots > 1:
            fd = _try_gate(lane)
            if fd is None:
                return None
            inner.callback(_unlock, fd)
        got = _try_slot(lane)
        if got is None:
            inner.close()
            return None
        slot, fd = got
        inner.callback(_unlock, fd)
        if not shadow and not _admit(offer, lane):
            inner.close()
            return None
        _ensure_box_files(lane)
    except BaseException:
        inner.close()
        raise
    held.enter_context(inner)
    return OpBinding(lane, slot, key)


def _unlock(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _open(path):
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as error:
        raise RemoteLaneDown(repr(error).encode()[:512]) from None


def _wait(check, deadline, pause, poll, reason):
    if check is not None:
        check()
    if time.monotonic() >= deadline:
        raise RemoteLaneDown(reason)
    pause(poll)


def _try_gate(lane):
    """``lane``'s gate SHARED now (no alone retry waiting for it), or None."""
    directory = Path(lane.lane_dir)
    fd = _open(directory / GATE_LOCK)
    if not _wanted_by_others(directory, None):
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            pass
    os.close(fd)
    return None


def _try_slot(lane):
    """One free slot of ``lane`` now (its lock held, no lost controller's record in it), or None."""
    for slot in range(lane.slots):
        directory = Path(lane.lane_dir) / f"slot-{slot}"
        fd = _open(directory / "slot.lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            continue
        if (directory / "active-allocation.json").exists():
            # a lost controller's record: this slot waits for recovery, another may be free
            _unlock(fd)
            continue
        return slot, fd
    return None


def _live_ops(lane):
    """Whether a live op holds one of ``lane``'s slots now (its slot lock is held)."""
    for slot in range(lane.slots):
        try:
            fd = os.open(Path(lane.lane_dir) / f"slot-{slot}" / "slot.lock", os.O_RDWR)
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            return True
        finally:
            os.close(fd)
    return False


def _free_slots(lane):
    """How many of ``lane``'s slots are free now (a snapshot: each is tried and let go at once)."""
    free = 0
    for slot in range(lane.slots):
        directory = Path(lane.lane_dir) / f"slot-{slot}"
        if (directory / "active-allocation.json").exists():
            continue
        try:
            fd = os.open(directory / "slot.lock", os.O_RDWR)
        except FileNotFoundError:
            free += 1
            continue
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            free += 1
            fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            pass
        finally:
            os.close(fd)
    return free


@contextmanager
def _gate(lane, *, alone, check, pause, poll, deadline):
    """The box gate for one op: SHARED (an ordinary op, which waits while an alone retry is announced) or EXCLUSIVE (an
    alone retry, announced in `ALONE_WANTED_DIR` while it waits). Yields whether the op runs alone.
    """
    from carbon.reconstruction import grade_lanes

    directory = Path(lane.lane_dir)
    fd = _open(directory / GATE_LOCK)
    wanted = None
    own = f"{os.getpid()}-{grade_lanes.process_start(os.getpid())}-{id(fd)}"
    try:
        if alone:
            try:
                (directory / ALONE_WANTED_DIR).mkdir(mode=0o700, exist_ok=True)
                wanted = directory / ALONE_WANTED_DIR / own
                wanted.touch(mode=0o600)
            except OSError as error:
                raise RemoteLaneDown(repr(error).encode()[:512]) from None
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    _wait(check, deadline, pause, poll, b"remote_gpu_build_alone_busy")
        else:
            while True:
                if not _wanted_by_others(directory, own):
                    try:
                        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        pass
                _wait(check, deadline, pause, poll, b"remote_gpu_build_slots_busy")
        yield alone
    finally:
        if wanted is not None:
            wanted.unlink(missing_ok=True)
        _unlock(fd)


@contextmanager
def _all_slots(lane, *, check, pause, poll, deadline):
    """Every slot of ``lane`` (an alone retry, holding the gate EXCLUSIVE, so none is being taken meanwhile)."""
    held = []
    try:
        for slot in range(lane.slots):
            fd = _open(Path(lane.lane_dir) / f"slot-{slot}" / "slot.lock")
            held.append(fd)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    _wait(check, deadline, pause, poll, b"remote_gpu_build_alone_busy")
                    continue
                if not (
                    Path(lane.lane_dir) / f"slot-{slot}" / "active-allocation.json"
                ).exists():
                    break
                # a lost controller's record: its container may still run, so the box is not this op's alone yet
                fcntl.flock(fd, fcntl.LOCK_UN)
                _wait(check, deadline, pause, poll, b"remote_gpu_build_alone_busy")
        yield
    finally:
        for fd in held:
            _unlock(fd)


# -- what the carrier asks of a bound op ------------------------------------------------------------------------------------


def device():
    """The device record of the running op's machine, or None."""
    binding = _current()
    return None if binding is None else binding.lane.device


def allocation_root():
    """Where the running op's device allocation record lives (its slot's directory), or None (HOST_ROOT)."""
    binding = _current()
    return None if binding is None else binding.slot_dir


def cpuset():
    """The running op's slot cores on its machine, or None."""
    binding = _current()
    return None if binding is None else binding.cpuset


def docker_host():
    """The ``DOCKER_HOST`` of the running op's box, or None."""
    binding = _current()
    return None if binding is None else binding.docker_host


def _docker_binary():
    found = shutil.which("docker", path=_SYSTEM_PATH)
    if found is None:
        raise RemoteLaneDown(b"remote_gpu_build_no_docker_cli")
    return found


def _ssh_binary():
    found = shutil.which("ssh", path=_SYSTEM_PATH)
    if found is None:
        raise RemoteLaneDown(b"remote_gpu_build_no_ssh")
    return found


def _checked_path(value, reason):
    if type(value) is not str or not _HOME.fullmatch(value):
        raise RemoteLaneDown(reason)
    return value


#: Under the door user's HOME: the lane key a box link uses when its box file names none (Lead, 18 Nov 2026).
DEFAULT_LANE_KEY = ".ssh/remote_lane_ed25519"


def known_hosts_path(lane) -> Path:
    return Path(lane.lane_dir) / "known_hosts"


def pinned_ssh_options(lane):
    """The ssh options every connection to ``lane``'s box carries: ITS pinned host key only, strictly; and the key its
    box file names (``ssh_key``), only that one (live 116, 18 Nov 2026: a replacement box at a new address got
    "Permission denied (publickey)" for hours, because only a hand-written ssh config block named the old address's key).
    """
    known = _checked_path(str(known_hosts_path(lane)), b"remote_gpu_build_box_dir")
    identity = []
    key = lane.spec.ssh_key
    if key is None:
        # a box file without ``ssh_key`` (admitted before it): the door's lane key (`DEFAULT_LANE_KEY`) when present
        default = os.path.join(os.environ.get("HOME", "/"), DEFAULT_LANE_KEY)
        key = default if os.path.isfile(default) else None
    if key is not None:
        key = _checked_path(key, b"remote_gpu_build_box_ssh_key")
        identity = ["-i", key, "-o", "IdentitiesOnly=yes"]
    return [
        *identity,
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "CheckHostIP=no",
    ]


def ssh_shim_text(lane, ssh):
    """The box's ``bin/ssh``: the system ssh with the box's `pinned_ssh_options` before the caller's arguments (Docker's
    ssh:// connection helper runs ``ssh`` from ``PATH``; the box's wrapper puts this first).
    """
    _checked_path(ssh, b"remote_gpu_build_no_ssh")
    return (
        "#!/bin/sh\n"
        "# GENERATED by carbon.reconstruction.remote_gpu_build; do not edit.\n"
        f'exec {shlex.join([ssh, *pinned_ssh_options(lane)])} "$@"\n'
    )


def wrapper_text(docker_host_value, home, docker, ssh_dir=None):
    """The box's docker wrapper: the local docker CLI talking to the box's ssh daemon, with the box's ssh shim first on
    ``PATH`` (``ssh_dir``). Every value is checked, so nothing a request carries can become a shell word.
    """
    remote_lane.parse_docker_host(docker_host_value)
    _checked_path(home, b"remote_gpu_build_home")
    _checked_path(docker, b"remote_gpu_build_no_docker_cli")
    path = _SYSTEM_PATH
    if ssh_dir is not None:
        path = _checked_path(ssh_dir, b"remote_gpu_build_box_dir") + ":" + path
    return (
        "#!/bin/sh\n"
        "# GENERATED by carbon.reconstruction.remote_gpu_build; do not edit.\n"
        f"DOCKER_HOST={shlex.quote(docker_host_value)}\n"
        f"HOME={shlex.quote(home)}\n"
        f"PATH={shlex.quote(path)}\n"
        "export DOCKER_HOST HOME PATH\n"
        f'exec {shlex.quote(docker)} "$@"\n'
    )


def _write_if_changed(path, data, mode):
    import threading

    if path.is_symlink():
        raise RemoteLaneDown(b"remote_gpu_build_wrapper_link")
    try:
        if path.exists() and path.read_bytes() == data:
            return path
    except OSError:
        pass
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # one temporary per writer: concurrent ops of one box each write the same text, and the last rename wins
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    temporary.unlink(missing_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _ensure_box_files(lane):
    """``lane``'s box files under its directory, (re)written when they differ: ``known_hosts`` (exactly its pinned key),
    ``bin/ssh`` (the shim), ``docker`` (the wrapper) and the box file's copy (`BOX_COPY`). Returns the wrapper's path;
    None for a local lane."""
    if lane.spec.local:
        return None
    if lane.spec.host_key is None:
        raise RemoteLaneDown(b"remote_gpu_build_no_host_key")
    directory = Path(lane.lane_dir)
    try:
        _write_if_changed(
            known_hosts_path(lane), (lane.spec.host_key + "\n").encode(), 0o600
        )
        _write_if_changed(
            directory / "bin" / "ssh",
            ssh_shim_text(lane, _ssh_binary()).encode(),
            0o500,
        )
        if lane.spec.box_document is not None:
            _write_if_changed(
                directory / BOX_COPY, lane.spec.box_document.encode(), 0o600
            )
        return _write_if_changed(
            directory / "docker",
            wrapper_text(
                lane.spec.docker_host,
                os.environ.get("HOME", "/"),
                _docker_binary(),
                str(directory / "bin"),
            ).encode(),
            0o500,
        )
    except OSError as error:
        raise RemoteLaneDown(repr(error).encode()[:512]) from None


def wrapper(lane):
    """The box's docker wrapper, (re)written when its text differs: ``<box dir>/docker`` (0500)."""
    return _ensure_box_files(lane)


def cli(binding=None):
    """A Docker CLI for the running op's box daemon (through the box's wrapper), or None outside a remote op."""
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.spec.local:
        # outside a slot, or a local slot lane: this host's own daemon (the caller's DockerCLI)
        return None
    from carbon.reconstruction.worker.docker_runtime import DockerCLI

    remote = DockerCLI()
    # DockerCLI (a worker image input, A16's bytes) always runs ``docker`` with the operator's own DOCKER_*; the box's
    # wrapper is that same CLI with the box's DOCKER_HOST and ssh shim, so every bounded capture and stream is DockerCLI's.
    remote.executable = str(wrapper(binding.lane))
    remote.docker_host = binding.docker_host
    return remote


def _box_environment():
    environment = {"PATH": _SYSTEM_PATH}
    if "HOME" in os.environ:
        environment["HOME"] = os.environ["HOME"]
    return environment


def box_docker(binding):
    """``(argv prefix, environment)`` of one docker call on ``binding``'s box: its wrapper (`cli`'s)."""
    return [str(wrapper(binding.lane))], _box_environment()


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
    if binding is None or binding.lane.slots == 1 or binding.lane.memory != "capped":
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


def _prelude_statements():
    return [ast.dump(node) for node in ast.parse(SLOT_PRELUDE).body]


def with_slot_prelude(source, binding=None, *, program_name="program.py"):
    """The build program with `SLOT_PRELUDE` after its docstring and ``__future__`` imports: only with N > 1 slots.
    Unchanged otherwise, so a one-slot lane runs exactly the local program. With N > 1 the result is checked: its first
    statements after the docstring and ``__future__`` imports ARE the prelude (else Carbon's, `RemoteLaneDown`: a
    build whose cap might not run never starts). Only a Python program (``program.py``) can carry the cap.
    """
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.slots == 1 or binding.lane.memory != "capped":
        return source
    if program_name != "program.py":
        raise RemoteLaneDown(b"remote_gpu_build_slot_cap_needs_python_program")
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
    # line ends as the parser counts them: "\n" only (str.splitlines also splits on \x0c, \x1c,  , ...)
    lines = re.split(r"(?<=\n)", source)
    if after and not lines[after - 1].endswith("\n"):
        lines[after - 1] += "\n"
    changed = "".join(lines[:after]) + SLOT_PRELUDE + "".join(lines[after:])
    try:
        body = [
            ast.dump(node)
            for node in ast.parse(changed).body
            if not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
        ]
    except SyntaxError:
        raise RemoteLaneDown(b"remote_gpu_build_slot_prelude_misplaced") from None
    prelude = _prelude_statements()
    start = 1 if after and module.body and isinstance(module.body[0], ast.Expr) else 0
    if body[start : start + len(prelude)] != prelude:
        raise RemoteLaneDown(b"remote_gpu_build_slot_prelude_misplaced")
    return changed


def request_fields(binding=None):
    """What a bound op's request records beside its accelerator: the slot count when it is above one (the per-process
    memory share is part of the build's environment), else nothing (identities as before).
    """
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.slots == 1:
        return {}
    if binding.lane.memory == "shared":
        # no cap: the pinned platform allocator, each build holding only what it uses
        return {"remote_gpu_slots": binding.lane.slots, "slot_memory": "shared"}
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
    """What an op's durable intent records about where its container runs: ``{"remote_gpu_build": {...}}`` for a slot
    op (the daemon, the mirror root, the lane index, the slot and the BOX NAME recovery must use), else ``{}``.
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
            "box": binding.lane.spec.name,
        }
    }


def recorded(intent, *, root=None):
    """The slot binding an intent recorded (an `OpBinding`), or None (the door's own daemon). A box op is found by its
    recorded box NAME even once its box file is gone (drained or refused): its binding is then ``gone`` (recovery only
    clears its local slot record; the op is FAILED_INFRA), with the device of the box copy it ran with when that copy
    still names the recorded daemon. A malformed record raises ValueError: recovery never guesses which daemon holds a
    container."""
    entry = intent.get("remote_gpu_build") if type(intent) is dict else None
    if entry is None:
        return None
    if type(entry) is not dict or set(entry) not in (
        {"docker_host", "stage_root", "lane", "slot"},
        {"docker_host", "stage_root", "lane", "slot", "box"},
    ):
        raise ValueError("remote_gpu_build_intent")
    slot, index = entry["slot"], entry["lane"]
    if type(slot) is not int or slot < 0 or type(index) is not int or index < 0:
        raise ValueError("remote_gpu_build_intent")
    host = _host_root(root)
    name = entry.get("box")
    if entry["docker_host"] is None:
        # a local slot lane: rebuilt from the installed record as it was
        specs = {spec.index: spec for spec in load(root)}
        spec = specs.get(index)
        if (
            spec is None
            or entry["stage_root"] is not None
            or name not in (None, spec.name)
            or not slot < len(spec.slot_cpusets)
        ):
            raise ValueError("remote_gpu_build_intent")
        lane = DoorLane(
            spec,
            len(spec.slot_cpusets),
            _lane_device(host),
            str(host / LANE_DIR.format(index=spec.index)),
        )
        return OpBinding(lane, slot)
    remote_lane.parse_docker_host(entry["docker_host"])
    if name is None:
        # an op of the old single remote lane: that lane is not installed any more (a box is a box file now)
        spec = GpuBuildSpec(
            index,
            entry["docker_host"],
            entry["stage_root"],
            BOX_SLOT_CPUSETS,
            f"lane-{index}",
        )
        lane = DoorLane(spec, 1, None, str(host / LANE_DIR.format(index=index)))
        return OpBinding(lane, slot, gone=True)
    if (
        type(name) is not str
        or not _BOX_NAME.fullmatch(name)
        or not slot < len(BOX_SLOT_CPUSETS)
    ):
        raise ValueError("remote_gpu_build_intent")
    box_dir = host / BOX_DIR.format(name=name)
    copy = None
    try:
        document = json.loads(_read_private(box_dir / BOX_COPY))
        copy = _box_lane(
            document,
            name=name,
            kind=None,
            slots=len(BOX_SLOT_CPUSETS),
            memory="capped",
            root=host,
            box_file=str(host / BOXES_DIR / f"{name}.json"),
        )
    except (ValueError, UnicodeDecodeError):
        copy = None
    if copy is not None and (
        copy.spec.docker_host != entry["docker_host"]
        or copy.spec.stage_root != entry["stage_root"]
    ):
        copy = None
    if copy is not None:
        try:
            live = read_box(
                host / BOXES_DIR / f"{name}.json",
                kind=None,
                slots=copy.slots,
                root=host,
            )
        except ValueError:
            live = None
        if (
            live is not None
            and _private_dir(host / BOXES_DIR)
            and live.spec.box_digest == copy.spec.box_digest
        ):
            return OpBinding(live, slot)
        return OpBinding(copy, slot, gone=True)
    spec = GpuBuildSpec(
        0, entry["docker_host"], entry["stage_root"], BOX_SLOT_CPUSETS, name
    )
    return OpBinding(DoorLane(spec, 1, None, str(box_dir)), slot, gone=True)


def forget(binding):
    """A gone box's recorded op: its local slot record is cleared (its container, if any, is the box's own watchdog's
    and the box's sweep's; the box takes no new op)."""
    if binding is None:
        return
    try:
        (binding.slot_dir / "active-allocation.json").unlink(missing_ok=True)
    except OSError:
        pass


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


def _box_ssh(binding):
    """The ssh argv (up to the remote command) to ``binding``'s box: its pinned host key, strictly (`pinned_ssh_options`)."""
    user, host, port = remote_lane.parse_docker_host(binding.docker_host)
    _ensure_box_files(binding.lane)
    return [
        _ssh_binary(),
        *pinned_ssh_options(binding.lane),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=3",
        "-p",
        str(port),
        f"{user}@{host}",
        "--",
    ]


def _box_run(binding, script, *, feed=None, timeout=remote_lane.SSH_SECONDS):
    """One remote shell script on ``binding``'s box over its pinned ssh (as `remote_lane`'s, bounded as a whole: a
    helper thread feeds stdin, another drains stderr, and a link that stalls is killed at the deadline).
    """
    import threading

    command = [*_box_ssh(binding), "sh -c " + shlex.quote(script)]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if feed is not None else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=_box_environment(),
            cwd=os.sep,
        )
    except OSError as error:
        raise RemoteLaneDown(repr(error).encode()[:512]) from None
    deadline = time.monotonic() + timeout
    fed, err = [], bytearray()

    def write():
        try:
            feed(process.stdin)
        except BaseException as error:  # noqa: BLE001 - reported below
            fed.append(error)
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    def drain():
        try:
            while chunk := process.stderr.read(4096):
                if len(err) < 4096:
                    err.extend(chunk)
        except (OSError, ValueError):
            pass

    helpers = [threading.Thread(target=drain, daemon=True)]
    if feed is not None:
        helpers.append(threading.Thread(target=write, daemon=True))
    for helper in helpers:
        helper.start()
    try:
        for helper in helpers[1:]:
            helper.join(max(0.0, deadline - time.monotonic()))
            if helper.is_alive():
                raise subprocess.TimeoutExpired(command, timeout)
        process.wait(timeout=max(0.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise RemoteLaneDown(b"remote_lane_ssh_timeout") from None
    finally:
        helpers[0].join(timeout=5)
    if fed:
        raise RemoteLaneDown(repr(fed[0]).encode()[:512])
    if process.returncode != 0:
        raise RemoteLaneDown(b"exit=%d\n" % process.returncode + bytes(err)[-512:])


def mirror(stage):
    """Mirror the running op's ``/input`` to the same path on its box (contents replaced in place, modes kept, owned by
    the ssh user), over the box's pinned ssh. No-op outside a remote op."""
    import tarfile

    binding = _current()
    if binding is None or binding.lane.spec.local:
        return
    local = Path(stage)
    quoted = shlex.quote(remote_lane._remote_path(local, binding))
    script = (
        "set -eu; umask 022; "
        f"mkdir -p -- {quoted}; chmod 0755 {quoted}; "
        f"chmod -R u+w -- {quoted}; find {quoted} -mindepth 1 -delete; "
        f"tar -x -f - -C {quoted} --no-same-owner"
    )

    def feed(stream):
        with tarfile.open(fileobj=stream, mode="w|") as archive:
            for entry in sorted(local.rglob("*")):
                if entry.is_symlink():
                    raise tarfile.TarError("remote_lane_symlink")
                archive.add(
                    entry, arcname=str(entry.relative_to(local)), recursive=False
                )

    _box_run(binding, script, feed=feed)


def discard(stage, binding=None):
    """Remove the box's copy of ``stage`` (and its parent, when that leaves it empty). No-op outside a remote op or for
    a gone box."""
    import posixpath

    binding = _current() if binding is None else binding
    if binding is None or binding.lane.spec.local or binding.gone:
        return
    path = remote_lane._remote_path(Path(stage), binding)
    quoted = shlex.quote(path)
    parent = shlex.quote(posixpath.dirname(path))
    script = (
        "set -eu; "
        f"if [ -d {quoted} ]; then chmod -R u+w -- {quoted}; find {quoted} -delete; fi; "
        f"rmdir -- {parent} 2>/dev/null || true"
    )
    _box_run(binding, script)


def _ssh_capture(binding, argv, timeout=PROBE_SECONDS):
    """``argv``'s stdout on the op's machine: over the box's pinned ssh, or directly for a local lane."""
    local = binding.lane.spec.local
    try:
        command = (
            list(argv)
            if local
            else [*_box_ssh(binding), " ".join(shlex.quote(item) for item in argv)]
        )
        done = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": _SYSTEM_PATH} if local else _box_environment(),
            cwd=os.sep,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise RemoteLaneDown(repr(error).encode()[:512]) from None
    if done.returncode != 0:
        raise RemoteLaneDown(b"exit=%d\n" % done.returncode + done.stderr[-512:])
    return done.stdout


def box_output(binding, script, *, timeout=remote_lane.PROBE_SECONDS):
    """The stdout of one short read-only shell ``script`` on ``binding``'s box (bounded), or None on any fault."""
    try:
        done = subprocess.run(
            [*_box_ssh(binding), "sh -c " + shlex.quote(script)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=_box_environment(),
            timeout=timeout,
            check=False,
            cwd=os.sep,
        )
    except (OSError, ValueError, subprocess.SubprocessError, WorkerFailure):
        return None
    if done.returncode != 0 or len(done.stdout) > 65536:
        return None
    return done.stdout


def _gpu_rows(binding):
    """``nvidia-smi``'s ``(uuid, name)`` rows on the op's machine, or None when they cannot be read."""
    try:
        raw = _ssh_capture(
            binding,
            ["nvidia-smi", "--query-gpu=uuid,name", "--format=csv,noheader"],
        )
    except RemoteLaneDown:
        return None
    rows = []
    for line in raw.decode("utf-8", "replace").splitlines():
        fields = [field.strip() for field in line.split(",", 1)]
        if len(fields) == 2:
            rows.append(tuple(fields))
    return rows


def gpu_present(binding=None):
    """Whether the machine's ``nvidia-smi`` names the recorded device (its uuid, with the recorded kind)."""
    binding = _current() if binding is None else binding
    record = binding.lane.device
    rows = _gpu_rows(binding)
    return rows is not None and (record.device_uuid, record.device_kind) in rows


def link_up(binding=None, *, timeout=remote_lane.PROBE_SECONDS):
    """Whether the box's daemon answers now (``docker version``, through the box's wrapper). True outside a box op."""
    binding = _current() if binding is None else binding
    if binding is None or binding.lane.spec.local:
        return True
    try:
        prefix, environment = box_docker(binding)
        done = subprocess.run(
            [*prefix, "version", "--format", "{{.Server.Version}}"],
            env=environment,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=os.sep,
        )
    except (OSError, subprocess.TimeoutExpired, WorkerFailure):
        return False
    return done.returncode == 0 and bool(done.stdout.strip())


def healthy(binding=None):
    """Whether the running op's link and GPU are sound now: the daemon answers and the device is still there. A box
    found healthy is not down any more."""
    binding = _current() if binding is None else binding
    if binding is None:
        return True
    if binding.lane.spec.local:
        return gpu_present(binding)
    sound = link_up(binding) and gpu_present(binding)
    if sound:
        clear_down(binding.lane)
    return sound


def check_host(cli_, image, record, pins=None):
    """The GPU readiness a build needs on its box's daemon, read again on the box before the container is created
    (Validator-2's per-build re-read): the image the box file admitted, present on the box by its id (and lock and
    labels) with the NVIDIA runtime, and ``nvidia-smi`` naming the box file's GPU (uuid and name). A mismatch with the
    box file refuses the box (`refuse`); a link or GPU that cannot be read is the box DOWN. Both are Carbon's
    (`RemoteLaneDown`). Success is the box's health probe (its down mark is cleared).
    """
    binding = _current()
    if binding is None:
        raise RemoteLaneDown(b"remote_gpu_build_unbound")
    lane = binding.lane
    if record is None or record.digest != lane.device.digest:
        raise RemoteLaneDown(b"remote_gpu_build_device_changed")
    image_id = getattr(image, "image_id", None)
    if image is not None and lane.spec.images and image_id not in lane.spec.images:
        # not admitted with this image (its offer named none, `_Offer.serves`): Carbon's, the box itself is not refused
        raise RemoteLaneDown(b"remote_gpu_build_box_image_not_admitted")
    for attempt in (1, 2):
        try:
            _verify_box_image(cli_, image, pins)
            break
        except RemoteLaneDown:
            raise
        except WorkerFailure as error:
            if not link_up(binding):
                raise RemoteLaneDown(b"remote_gpu_build_link_down") from error
            if lane.spec.local:
                raise
            if attempt == 2:
                # twice, with the daemon answering: the image the box file admitted is not there as it was
                raise refuse(lane, b"remote_gpu_build_box_image_mismatch") from error
    rows = _gpu_rows(binding)
    if rows is None:
        raise RemoteLaneDown(b"remote_gpu_build_device_absent")
    if (lane.device.device_uuid, lane.device.device_kind) not in rows:
        if lane.spec.local:
            raise RemoteLaneDown(b"remote_gpu_build_device_absent")
        raise refuse(lane, b"remote_gpu_build_box_gpu_mismatch")
    clear_down(lane)


def _verify_box_image(cli_, image, pins):
    from carbon.reconstruction.worker.accelerator_runtime import (
        verify_image_and_toolkit,
    )

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


def reject_crowded(cli_, binding=None):
    """Before create: the slot's own allocation record is free, and the box's daemon runs fewer Carbon containers on
    the device than it has slots (a lost controller's retained container still counts). CONFLICT otherwise.
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
    running = len([line for line in raw.splitlines() if line.strip()])
    # an alone retry needs the device to itself: no other Carbon container on it at all
    if running >= (1 if binding.alone else binding.lane.slots):
        raise WorkerFailure(WorkerCode.CONFLICT)


def spawn_watchdog(*, container_name, launch_digest, deadline_unix, intent_path=None):
    """`docker_runtime.spawn_watchdog` for the running op's container on its box's daemon: the same watchdog process,
    handed the op's binding (`_handoff`), so it inspects and removes the container through the box's wrapper (its
    pinned ssh) where it runs (a link fault there keeps it alive until the deadline: `watchdog.main`).
    """
    import sys

    from carbon.reconstruction.worker.model import exact_digest, exact_token

    binding = _current()
    if binding is None:
        raise RemoteLaneDown(b"remote_gpu_build_unbound")
    environment = remote_lane.docker_environment(binding.docker_host)
    # the watchdog finishes the slot's own allocation record against the box's device record (`_current`)
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
    """The running op's slot binding when its machine is a REMOTE box (it has the ``docker_host`` a box probe and a link
    check need), else None."""
    binding = _current() if binding is None else binding
    return None if binding is None or binding.lane.spec.local else binding


def wall_counts(binding=None):
    """Whether this machine lets a wall stop of the running op be read as the candidate's at all. Outside a slot, and on
    a one-slot local lane (as a local GPU build's always was): yes. On a REMOTE box: yes, but only as CV-Motor ruled
    (L12624, 16 Nov), each part read from records by its own check: (a) the box's own clock and (c) the link
    (`wall_stop_observable`, which reads this slot's box), (b) the box quiet for the op and (c) every in-run sample
    answered (the op's box guard, `research_carrier.REMOTE_BUILD_GUARD`). On a local lane shared by more than one slot:
    never (its neighbours are this host's, not sampled per slot)."""
    binding = _current() if binding is None else binding
    if binding is None or not binding.lane.spec.local:
        return True
    # an alone retry holds every slot: its lane is, for this op, a one-slot lane
    return binding.lane.slots == 1 or binding.alone


def wall_stop_observable(observation, *, box_seconds=None, needed=None):
    """`remote_lane.wall_stop_observable` for the running op: on a REMOTE box, the same rule read on that box through
    its pinned link (`link_up`): the container observed at the stop, the daemon answering now and the program's age on
    the box's own clock at least ``needed``; anything else, `remote_lane`'s own reading.
    """
    binding = remote_box()
    if binding is None:
        return remote_lane.wall_stop_observable(
            observation, box_seconds=box_seconds, needed=needed
        )
    if type(observation) is not dict or observation.get("status") != "OBSERVED":
        return False
    if box_seconds is None or type(needed) not in (int, float):
        return False
    if not link_up(binding):
        return False
    try:
        age = box_seconds()
    except Exception:  # noqa: BLE001 - unreadable: Carbon's
        return False
    return type(age) is float and math.isfinite(age) and age >= needed


def shared_memory_exhausted(error, markers, binding=None):
    """Whether ``error`` of the running op is device memory exhaustion (one of ``markers`` in its diagnostic) on a box
    whose GPU more than one build shares: Carbon's (`RemoteLaneDown`), so a build that ran out of memory beside a
    neighbour is never the miner's.
    """
    binding = _current() if binding is None else binding
    if (
        binding is None
        or binding.lane.slots == 1
        or binding.alone
        or isinstance(error, RemoteLaneDown)
    ):
        return False
    diagnostic = getattr(error, "private_diagnostic", b"")
    return type(diagnostic) is bytes and any(marker in diagnostic for marker in markers)


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
    "ALONE_DIR",
    "ALONE_MARK_SECONDS",
    "BOXES_DIR",
    "BOX_DIR",
    "BOX_SCHEMA",
    "BOX_SLOT_CPUSETS",
    "DEFAULT_SLOTS",
    "DOWN_SECONDS",
    "GATE_LOCK",
    "MAX_LANES",
    "MAX_SLOTS",
    "RECORD",
    "SCHEMA",
    "SHADOW_SUFFIX",
    "SLOT_PRELUDE",
    "VALUES",
    "VALUES_SCHEMA",
    "DoorLane",
    "DoorPool",
    "GpuBuildSpec",
    "GpuClass",
    "OpBinding",
    "allocation_root",
    "alone_key",
    "bound",
    "box_docker",
    "box_output",
    "boxes",
    "check_host",
    "clear_alone",
    "cli",
    "cpuset",
    "current_op",
    "device",
    "discard",
    "docker_host",
    "door_pool",
    "eligible",
    "fingerprint",
    "first_build_box",
    "forget",
    "gpu_present",
    "healthy",
    "intent_fields",
    "is_down",
    "is_proven",
    "link_up",
    "load",
    "mark_down",
    "mark_proven",
    "mirror",
    "needs_alone",
    "note_uncounted_wall",
    "offered",
    "offered_for",
    "offered_lane",
    "op",
    "parse_host_key",
    "pin",
    "proven_elsewhere",
    "read_box",
    "recorded",
    "refuse",
    "reject_crowded",
    "remote_box",
    "request_fields",
    "retyped",
    "shadowing",
    "slot_environment",
    "slot_fraction",
    "spawn_watchdog",
    "values_row",
    "wall_counts",
    "wall_stop_observable",
    "with_slot_environment",
    "with_slot_prelude",
    "wrapper",
    "wrapper_text",
]
