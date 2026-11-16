"""Two grade lanes per grading host (owner 15 Nov 2026, ledger "Yes"; Lead 10:0x CST; Validator-Motor F1-F4 09:55).

Today one host-wide flock (`receipt_job.GRADING_LOCK`) lets one official round run per host at a time. This module lets
a door whose version a values row allows, on a host whose execution record lists two disjoint core sets, hold ONE of two
lanes instead, so two rounds run at once on separate cores. Nothing else changes order: the host's waiting list
(`direct_intake._WorkLock`) decides who may try, exactly as before.

**Fail closed to one lane.** A door runs in two-lane mode only when ALL of these hold (`door_lanes`); otherwise it holds
EVERY lane for each round, which is today's single host lock, so it never runs next to anyone:

1. `REGISTRY` has the row ``"<challenge> <version>": {"lanes": 2}`` (a values-only path; no file, no row, any other
   value = one lane);
2. the host's execution record (`host_execution.HostExecutionRecord`, schema v2) lists at least two lane cpusets,
   pairwise disjoint and of one size;
3. no core shares an SMT sibling with a core of another lane (the kernel's ``thread_siblings_list``; F1). A sibling list
   that cannot be read is not proof, so it fails closed.

**Per-lane cores.** The held lane is bound for the round (`bound`, a ContextVar read by
`host_execution.resolve_cpuset`), so every container the round starts is pinned to that lane's cores and its controls
check compares against them. The lane and its cpuset go into the door's in-flight record.

**The speed stage runs alone (F3).** Every container a lane-bound round starts holds the host timing gate
(`TIMING_LOCK`) SHARED for its whole life (`container_hold`, entered by the carrier before create and released after the
container is removed). A TIMING stage takes it EXCLUSIVE instead: the single-design speed calls, recognised by their
carrier identity (`TIMING_IDENTITY_PREFIXES`), or anything run inside `timing_exclusive`. It announces itself first
(`TIMING_WANTED_DIR`), so no lane starts a new container once it waits: it starts when the neighbour's current
container has ended. Nothing is frozen or preempted, so no neighbour's own walls are stretched.

**Not ruled here.** Whether a wall stop next to a running neighbour counts as the model's result is `host_quiet`'s rule
(Validator-2, 5 Nov), unchanged by this module: until Validator-Motor / Validator-2 rule otherwise, another container on
the host still makes the host not quiet. Two lanes go live only with the owner's values row and Deploy-B's measured
contention inside one lane's run-to-run spread (F2); this module sets no threshold.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "grade_lanes.json"
)
SCHEMA = "carbon.exam.grade-lanes.v1"
#: The most lanes a values row may ask for (the owner's pick: two).
MAX_LANES = 2
#: The most REMOTE lanes (`carbon.reconstruction.remote_lane`) a values row may ask for, beside the local ones: lane
#: indices ``MAX_LANES`` onwards. A one-lane round holds them too (`ALL_LANES`), so it never runs beside a remote round.
#: Two remote boxes x 4 lanes (owner's FSN1 + HEL1 acceptance, 16 Nov 2026; CV-Motor L12464): operational, not science.
MAX_REMOTE_LANES = 8
ALL_LANES = MAX_LANES + MAX_REMOTE_LANES
#: Lane 0's lock is the host's existing official-grading lock (`receipt_job.GRADING_LOCK`), so every reader of "is the
#: host grading" keeps working; lane k >= 1 has its own file beside it.
LANE_LOCK = "official-grading.lane-{index}.lock"
#: Who holds a lane, and in which mode (one file per held lane, written after the lock is taken).
LANE_HOLDER = "official-grading.lane-{index}.holder"
#: The host timing gate: SHARED for every lane container, EXCLUSIVE for a timing stage.
TIMING_LOCK = "official-grading.timing.lock"
#: One file per live timing stage waiting for, or holding, the gate exclusively.
TIMING_WANTED_DIR = "official-grading.timing.wanted"
#: The carrier identities of TIMING stages: the single-design speed calls (`lean_recipe_retention._single_call_raw`
#: names its operation ``single-call-<digest>``). A container with one of these identities takes the timing gate
#: EXCLUSIVE, as inside `timing_exclusive`, so no grading file outside the carrier needs a lane line.
TIMING_IDENTITY_PREFIXES = ("single-call-",)
#: How often a waiting container retries the timing gate (an operational poll, not a scientific value).
POLL_S = 0.2
#: Where the kernel reports CPU topology.
SYS_CPU = Path("/sys/devices/system/cpu")
#: The mode a holder records: a lane-aware door in two-lane mode.
TWO_LANE_MODE = "lanes-2"
ONE_LANE_MODE = "lanes-1"


def _log(event, **fields):
    # a log line never stops grading
    with suppress(Exception):
        from carbon.battery.intake import log

        log(event, **fields)


def _row(challenge_id, version, path):
    """The well-formed values row of ``"<challenge_id> <version>"`` (``{"lanes": n}``, optionally with
    ``"remote_lanes": m``), or None."""
    document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
    if type(document) is not dict or document.get("schema") != SCHEMA:
        return None
    row = (document.get("rows") or {}).get(f"{challenge_id} {version}")
    if type(row) is not dict or set(row) not in ({"lanes"}, {"lanes", "remote_lanes"}):
        return None
    lanes = row["lanes"]
    if type(lanes) is not int or not 1 <= lanes <= MAX_LANES:
        return None
    remote = row.get("remote_lanes", 0)
    if type(remote) is not int or not 0 <= remote <= MAX_REMOTE_LANES:
        return None
    return row


def registered_lanes(challenge_id, version, *, path=None):
    """The lane count the values row of ``"<challenge_id> <version>"`` allows: 2 only for a well-formed row
    ``{"lanes": 2}`` (with or without ``"remote_lanes"``), else 1. Never raises."""
    try:
        row = _row(challenge_id, version, path)
        return 1 if row is None else row["lanes"]
    except Exception:  # noqa: BLE001 - one lane, never a failure
        return 1


def registered_remote_lanes(challenge_id, version, *, path=None):
    """The REMOTE lane count the values row of ``"<challenge_id> <version>"`` allows: ``"remote_lanes"`` of a
    well-formed row, else 0. Never raises."""
    try:
        row = _row(challenge_id, version, path)
        return 0 if row is None else row.get("remote_lanes", 0)
    except Exception:  # noqa: BLE001 - no remote lane, never a failure
        return 0


def lane_lock_name(index):
    """The lock file of lane ``index`` (lane 0 is the host's existing grading lock)."""
    from carbon.backbone_catalog.receipt_job import GRADING_LOCK

    if type(index) is not int or index < 0:
        raise ValueError("grade_lane_index_invalid")
    return GRADING_LOCK if index == 0 else LANE_LOCK.format(index=index)


def _cores(value):
    from carbon.reconstruction.host_execution import parse_cpuset

    return set(parse_cpuset(value))


def siblings_inside(cpusets, *, sys_cpu=None):
    """Whether every core of every lane is online and shares an SMT sibling with no core outside its own lane (F1).
    Anything unreadable is not proof: False."""
    root = SYS_CPU if sys_cpu is None else Path(sys_cpu)
    try:
        lanes = [_cores(value) for value in cpusets]
        for own in lanes:
            for core in sorted(own):
                base = root / f"cpu{core}"
                if not base.is_dir():
                    return False
                online = base / "online"
                if online.exists() and online.read_text().strip() != "1":
                    return False
                siblings = _cores(
                    (base / "topology" / "thread_siblings_list").read_text().strip()
                )
                if not siblings <= own:
                    return False
        return True
    except Exception:  # noqa: BLE001 - not proof
        return False


def door_lanes(challenge_id, version, *, registry=None, host_root=None, sys_cpu=None):
    """The lane cpusets a door of ``"<challenge_id> <version>"`` grades with: a tuple of two or more when two-lane mode
    holds (see the module docstring), else ``()`` (one lane: every round holds every lane, today's behaviour). Says
    which, and why, once. Never raises."""
    reason = None
    lanes = ()
    try:
        if registered_lanes(challenge_id, version, path=registry) < 2:
            reason = "no_values_row"
        else:
            from carbon.reconstruction.host_execution import HostExecutionRecord
            from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

            record = HostExecutionRecord.load(
                HOST_ROOT if host_root is None else host_root
            )
            listed = () if record is None else record.lanes
            if len(listed) < 2:
                reason = "no_host_lanes"
            elif not siblings_inside(listed[:MAX_LANES], sys_cpu=sys_cpu):
                reason = "smt_siblings_shared_or_unreadable"
            else:
                lanes = tuple(listed[:MAX_LANES])
    except Exception as failure:  # noqa: BLE001 - one lane, never a failure
        reason = f"unreadable:{type(failure).__name__}"
        lanes = ()
    _log(
        "grade_lanes",
        lanes=max(1, len(lanes)),
        cpusets=list(lanes),
        reason=reason,
    )
    return lanes


def door_remote_lanes(
    challenge_id,
    version,
    *,
    registry=None,
    host_root=None,
    sys_cpu=None,
    state_root=None,
):
    """The REMOTE lanes (`remote_lane.RemoteSpec`) a door of ``"<challenge_id> <version>"`` may also grade on, only in
    two-lane mode (`door_lanes`): the door's OWN record (``remote-grade-lanes.json`` in its state root ``state_root``:
    that door alone, e.g. a scratch door, every lane it lists), else the host's record with ``"remote_lanes"`` in the
    version's values row (the first that many). Else ``()``. Says which, and why, once. Never raises.
    """
    reason = None
    remote = ()
    try:
        from carbon.reconstruction import remote_lane
        from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

        own = (
            remote_lane.load(state_root)
            if state_root is not None
            # a door whose state root IS the host root has no record of its own: the host's needs the values row
            and Path(state_root).resolve()
            != Path(HOST_ROOT if host_root is None else host_root).resolve()
            else ()
        )
        wanted = registered_remote_lanes(challenge_id, version, path=registry)
        if not door_lanes(
            challenge_id,
            version,
            registry=registry,
            host_root=host_root,
            sys_cpu=sys_cpu,
        ):
            reason = "not_two_lane_mode"
        elif own:
            remote = own
            reason = "door_record"
        elif wanted < 1:
            reason = "no_values_row"
        else:
            listed = remote_lane.load(host_root)
            if not listed:
                reason = "no_remote_record"
            else:
                remote = tuple(listed[:wanted])
    except Exception as failure:  # noqa: BLE001 - no remote lane, never a failure
        reason = f"unreadable:{type(failure).__name__}"
        remote = ()
    _log(
        "grade_remote_lanes",
        lanes=len(remote),
        hosts=[spec.docker_host for spec in remote],
        reason=reason,
    )
    return remote


def door_remote_only(state_root):
    """Whether the door's OWN remote record (in ``state_root``) asks for its remote lanes alone (``"only": true``)."""
    if state_root is None:
        return False
    try:
        from carbon.reconstruction import remote_lane

        specs, only = remote_lane.load_record(state_root)
        return bool(specs) and only
    except Exception:  # noqa: BLE001 - unreadable: not remote-only
        return False


@dataclass(frozen=True)
class Lane:
    """The lane a round holds: its index, its cores, and the host lock directory its gates live in. A REMOTE lane
    (`carbon.reconstruction.remote_lane`) also names its daemon (``docker_host``, ssh) and the path under which inputs
    may be mirrored there (``stage_root``); its cores are the remote machine's."""

    index: int
    cpuset: str
    lock_dir: str
    docker_host: str | None = None
    stage_root: str | None = None


_BOUND: ContextVar[Lane | None] = ContextVar("carbon_grade_lane", default=None)
_EXCLUSIVE: ContextVar[bool] = ContextVar(
    "carbon_grade_lane_timing_exclusive", default=False
)
#: A watcher of the calling context's container holds (`watch_holds`): told ``("held", identity)`` once the hold is
#: taken (after any wait for the timing gate) and ``("release", identity)`` before it is let go.
_HOLD_WATCH: ContextVar = ContextVar("carbon_grade_lane_hold_watch", default=None)


@contextmanager
def watch_holds(callback):
    """Tell ``callback(event, identity)`` about every container hold taken in this context (A19 speed stage: its host
    probe covers the hold's own window only, never the wait for the exclusive gate)."""
    token = _HOLD_WATCH.set(callback)
    try:
        yield
    finally:
        _HOLD_WATCH.reset(token)


def _tell(event, identity):
    watch = _HOLD_WATCH.get()
    if watch is not None:
        watch(event, identity)


def current():
    """The lane the running round holds, or None (one-lane mode, or outside a round)."""
    return _BOUND.get()


def bind(lane):
    """Bind ``lane`` for the calling context; returns the token for `unbind`."""
    if lane is not None and type(lane) is not Lane:
        raise TypeError("grade_lane_invalid")
    return _BOUND.set(lane)


def unbind(token):
    _BOUND.reset(token)


@contextmanager
def bound(lane):
    token = bind(lane)
    try:
        yield lane
    finally:
        unbind(token)


def timing_requested():
    """Whether the calling context is inside `timing_exclusive`."""
    return _EXCLUSIVE.get()


@contextmanager
def timing_exclusive():
    """Mark the containers started inside as a TIMING stage: each one waits until no other lane container runs, and
    no lane starts one while it waits or runs (F3). Outside two-lane mode it changes nothing.
    """
    token = _EXCLUSIVE.set(True)
    try:
        yield
    finally:
        _EXCLUSIVE.reset(token)


def process_start(pid):
    """The kernel's start time of ``pid`` (clock ticks since boot), or None."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            return int(handle.read().rsplit(b")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _live(name):
    """Whether a ``<pid>-<start>[-...]`` entry names a live process."""
    parts = name.split("-")
    if len(parts) < 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return False
    return process_start(int(parts[0])) == int(parts[1])


def _wanted_by_others(lock_dir, mine=None):
    try:
        entries = list((Path(lock_dir) / TIMING_WANTED_DIR).iterdir())
    except OSError:
        return False
    return any(entry.name != mine and _live(entry.name) for entry in entries)


def is_timing_identity(identity):
    """Whether a carrier operation ``identity`` is a timing stage (`TIMING_IDENTITY_PREFIXES`)."""
    return type(identity) is str and identity.startswith(TIMING_IDENTITY_PREFIXES)


@contextmanager
def container_hold(*, identity=None, poll_s=None, sleep=None):
    """Held by the carrier for one container's whole life (before create, until it is removed). Outside a lane-bound
    round: nothing. Inside one: the host timing gate SHARED, or EXCLUSIVE for a timing stage (inside
    `timing_exclusive`, or an operation ``identity`` that `is_timing_identity`)."""
    lane = current()
    if lane is None:
        _tell("held", identity)
        try:
            yield None
        finally:
            _tell("release", identity)
        return
    import fcntl

    poll = POLL_S if poll_s is None else poll_s
    pause = time.sleep if sleep is None else sleep
    exclusive = _EXCLUSIVE.get() or is_timing_identity(identity)
    directory = Path(lane.lock_dir)
    fd = os.open(directory / TIMING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    wanted = None
    began = time.monotonic()
    held = False
    try:
        if exclusive:
            name = f"{os.getpid()}-{process_start(os.getpid())}-{threading.get_ident()}"
            (directory / TIMING_WANTED_DIR).mkdir(mode=0o700, exist_ok=True)
            wanted = directory / TIMING_WANTED_DIR / name
            wanted.touch(mode=0o600)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    pause(poll)
        else:
            while True:
                if not _wanted_by_others(directory):
                    try:
                        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        pass
                pause(poll)
        waited = time.monotonic() - began
        if exclusive or waited >= 1.0:
            _log(
                "grade_lane_timing_gate",
                lane=lane.index,
                exclusive=exclusive,
                waited_s=round(waited, 1),
            )
        held = True
        _tell("held", identity)
        yield lane
    finally:
        try:
            if held:
                _tell(
                    "release", identity
                )  # before the gate is let go: no waiting lane has started yet
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
            if wanted is not None:
                wanted.unlink(missing_ok=True)


def write_holder(lock_dir, index, mode):
    """Record this process as the holder of lane ``index`` (written after its lock is taken)."""
    path = Path(lock_dir) / LANE_HOLDER.format(index=index)
    staged = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}")
    staged.write_text(f"{os.getpid()}-{process_start(os.getpid())}-{mode}")
    os.chmod(staged, 0o600)
    os.replace(staged, path)


def clear_holder(lock_dir, index):
    """Remove this process's holder record of lane ``index`` (before its lock is released); another's is left."""
    path = Path(lock_dir) / LANE_HOLDER.format(index=index)
    try:
        if path.read_text().startswith(f"{os.getpid()}-"):
            path.unlink(missing_ok=True)
    except OSError:
        pass


def held_in_two_lane_mode(lock_dir, index):
    """Whether lane ``index``'s recorded holder is a live process in two-lane mode. A lane held by a door that wrote no
    such record (an older build, or one in the gap before it writes) is not: a two-lane round must not run beside it.
    """
    try:
        text = (Path(lock_dir) / LANE_HOLDER.format(index=index)).read_text().strip()
    except OSError:
        return False
    pid, _, rest = text.partition("-")
    started, _, mode = rest.partition("-")
    return (
        mode == TWO_LANE_MODE
        and pid.isdigit()
        and started.isdigit()
        and process_start(int(pid)) == int(started)
    )
