"""A grade lane on another machine: the round's worker containers run on a REMOTE docker daemon over ssh.

Owner's order (Sun 15 Nov 2026, via the Lead): a second grading machine to clear the 116 queue. The controller (the
door, its ledger, scoring, truths, keys) stays on the grading host; only the round's worker CONTAINERS move. A remote
lane is one more grade lane (`carbon.reconstruction.grade_lanes`): a round that holds it is bound to it, and every
docker call the round makes goes to the lane's daemon (``DOCKER_HOST=ssh://user@host[:port]``), except:

- **The speed stage stays on the grading host.** A timing container (`grade_lanes.is_timing_identity`, or anything inside
  `grade_lanes.timing_exclusive`) of a remote round runs locally, on the host record's cores, under the host timing gate
  held EXCLUSIVE (`local_for`), exactly as a local lane's timing stage does.

**Inputs.** A container's ``/input`` is a bind mount of a controller directory. The remote daemon resolves that path on
ITS filesystem, so the directory is mirrored to the SAME absolute path there before the container is created (and, for a
grade session, after every op's link and clear), then removed after the container is (`mirror`, `discard`). Outputs
already come back through ``docker exec`` streams, never a copy. Only paths under the lane's ``stage_root`` are ever
written or removed there; anything else refuses.

**Failure typing.** Anything the link does wrong (ssh refused, timed out, a mirror that did not complete) raises
`RemoteLaneDown`, a ``WorkerFailure`` of code UNAVAILABLE: Carbon's infrastructure, never the candidate's. A wall stop
on a remote lane is the candidate's only as CV-Motor ruled (L12624, 16 Nov 2026), every part read from records: (a) the
BOX's own clock says the program was still running there and had run its whole wall (`wall_stop_observable`: the
program's age read inside its container, never a clock across the link); (b) the box was quiet for the run (no other
Carbon worker container on any of its lanes, no foreign GPU compute: sampled on the box itself, `host_quiet`'s box
probes); (c) the link stayed healthy for the whole run (every one of those samples answered, the stop observed, the
daemon answering at the stop). Anything else is Carbon's (FAILED_INFRA, never charged). Measured queries (a timed
control) stay on the grading host with the speed stage (`local_for`).

**Configuration.** Operator-installed, beside the host execution record: ``<HOST_ROOT>/remote-grade-lanes.json``
(`RECORD`), schema `SCHEMA`, ``{"lanes": [{"docker_host": ..., "cpuset": ..., "stage_root": ...}]}``, at most
`MAX_REMOTE_LANES`. A lane is used only when the door's values row also asks for it (`grade_lanes`); a missing or broken
record is no remote lane. This module sets no threshold and makes no scientific decision: whether timing on the remote
class may count is Validator-Motor's ruling, and the owner decides whether any hidden input may leave the host.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import subprocess
import tarfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

RECORD = "remote-grade-lanes.json"
SCHEMA = "carbon.remote-grade-lanes.v1"
#: The most remote lanes a record may name: two remote boxes x 4 lanes of 4 physical cores (the owner's FSN1 + HEL1
#: acceptance, 16 Nov 2026; CV-Motor L12464). An operational bound, not science.
MAX_REMOTE_LANES = 8
#: ``ssh://user@host`` or ``ssh://user@host:port``: plain names only, no options, no paths.
_DOCKER_HOST = re.compile(
    r"^ssh://(?P<user>[a-z_][a-z0-9_-]{0,31})@(?P<host>[A-Za-z0-9.-]{1,253})(?::(?P<port>[0-9]{1,5}))?$"
)
#: A path this module may write or remove on the remote machine: absolute, plain characters, no ``..``.
_PATH = re.compile(r"^/[A-Za-z0-9._/-]+$")
#: How long one mirror or discard may take (an operational bound, not a scientific value).
SSH_SECONDS = 120
#: How long the link probe may take.
PROBE_SECONDS = 10


class RemoteLaneDown(WorkerFailure):
    """The remote lane's link or daemon did not do what was asked: Carbon's infrastructure (UNAVAILABLE)."""

    def __init__(self, diagnostic: bytes = b"") -> None:
        super().__init__(WorkerCode.UNAVAILABLE, private_diagnostic=diagnostic)


@dataclass(frozen=True)
class RemoteSpec:
    """One remote lane as the operator installed it."""

    docker_host: str
    cpuset: str
    stage_root: str


def parse_docker_host(value):
    """``(user, host, port)`` of a remote lane's ``ssh://`` daemon address, or ValueError."""
    if type(value) is not str:
        raise ValueError("remote_lane_docker_host")
    found = _DOCKER_HOST.fullmatch(value)
    if found is None:
        raise ValueError("remote_lane_docker_host")
    port = int(found.group("port") or 22)
    if not 1 <= port <= 65535:
        raise ValueError("remote_lane_docker_host")
    return found.group("user"), found.group("host"), port


def _checked_root(value):
    if (
        type(value) is not str
        or not _PATH.fullmatch(value)
        or posixpath.normpath(value) != value
        or value == "/"
    ):
        raise ValueError("remote_lane_stage_root")
    return value


def load(root=None):
    """The installed remote lanes (a tuple of `RemoteSpec`), ``()`` when none is installed. A record that is present but
    malformed raises ValueError: an operator who installed one meant something by it."""
    return load_record(root)[0]


def load_record(root=None):
    """``(remote lanes, only)`` of the record in ``root`` (default HOST_ROOT): ``only`` (optional, a bool) asks that the
    door grade and build on its remote lanes alone (a scratch door's re-grades on a remote box). ``((), False)`` when
    none is installed; a record that is present but malformed raises ValueError."""
    from carbon.reconstruction.host_execution import parse_cpuset
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    path = Path(HOST_ROOT if root is None else root) / RECORD
    if not path.exists():
        return (), False
    document = json.loads(path.read_bytes())
    if (
        type(document) is not dict
        or not {"schema", "lanes"} <= set(document) <= {"schema", "lanes", "only"}
        or type(document.get("only", False)) is not bool
        or document["schema"] != SCHEMA
        or type(document["lanes"]) is not list
        or not 1 <= len(document["lanes"]) <= MAX_REMOTE_LANES
    ):
        raise ValueError("remote_lane_record")
    specs = []
    for entry in document["lanes"]:
        if type(entry) is not dict or set(entry) != {
            "docker_host",
            "cpuset",
            "stage_root",
        }:
            raise ValueError("remote_lane_record")
        parse_docker_host(entry["docker_host"])
        try:
            parse_cpuset(entry["cpuset"])
        except WorkerFailure:
            raise ValueError("remote_lane_cpuset") from None
        specs.append(
            RemoteSpec(
                entry["docker_host"],
                entry["cpuset"],
                _checked_root(entry["stage_root"]),
            )
        )
    return tuple(specs), document.get("only", False)


# -- the bound round ------------------------------------------------------------------------------------------------------


def current():
    """The remote lane the running round is bound to (a `grade_lanes.Lane` with a ``docker_host``), or None."""
    from carbon.reconstruction import grade_lanes

    lane = grade_lanes.current()
    if lane is None or getattr(lane, "docker_host", None) is None:
        return None
    return lane


def docker_host():
    """The ``DOCKER_HOST`` of the running round's remote lane, or None (the local daemon)."""
    lane = current()
    return None if lane is None else lane.docker_host


def docker_environment(host=None):
    """The environment one Docker CLI call passes: for a remote lane's daemon (``host``, ssh) exactly ``DOCKER_HOST`` plus
    ``HOME`` (ssh reads the door user's key, known hosts and connection settings from it); otherwise (``host`` None, the
    local daemon) ``PATH`` and the operator's own ``DOCKER_*``, as before."""
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    if host is not None:
        parse_docker_host(host)
        environment["DOCKER_HOST"] = host
        if "HOME" in os.environ:
            environment["HOME"] = os.environ["HOME"]
        return environment
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        if name in os.environ:
            environment[name] = os.environ[name]
    if environment.get("DOCKER_HOST", "").startswith("ssh://") and "HOME" in os.environ:
        # a watchdog or reaper spawned for a remote lane: its DOCKER_HOST is the lane's
        environment["HOME"] = os.environ["HOME"]
    return environment


def current_environment():
    """`docker_environment` for the running round: its remote lane's daemon, or the local one."""
    return docker_environment(docker_host())


def is_remote_environment():
    """Whether this process's own ``DOCKER_HOST`` names an ssh daemon (a watchdog or reaper spawned for a remote lane)."""
    return os.environ.get("DOCKER_HOST", "").startswith("ssh://")


@contextmanager
def local_for(identity, *, timed=False):
    """Inside a remote round, run a TIMING container (`grade_lanes.is_timing_identity`, inside
    `grade_lanes.timing_exclusive`, or ``timed``: a control that asks for a timing measurement) on the grading host: the round's lane is rebound to its local twin (same index and
    lock directory, so the host timing gate is still taken EXCLUSIVE; the host record's cores; the local daemon).
    Anything else, or outside a remote round: unchanged. A host with no execution record has no local cores to name, so
    the timing stage refuses (Carbon's, UNAVAILABLE) rather than guess."""
    from carbon.reconstruction import grade_lanes

    lane = current()
    if lane is None or not (
        timed
        or grade_lanes.is_timing_identity(identity)
        or grade_lanes.timing_requested()
    ):
        yield
        return
    from carbon.reconstruction.host_execution import HostExecutionRecord
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    record = HostExecutionRecord.load(HOST_ROOT)
    if record is None:
        raise RemoteLaneDown(b"remote_lane_timing_no_local_cores")
    twin = grade_lanes.Lane(lane.index, record.cpuset, lane.lock_dir)
    # EXCLUSIVE whatever the identity: the host record's cores may be a local lane's, so nothing else may run beside it
    with grade_lanes.bound(twin), grade_lanes.timing_exclusive():
        yield


# -- inputs on the remote machine -----------------------------------------------------------------------------------------


def _ssh(lane):
    user, host, port = parse_docker_host(lane.docker_host)
    return [
        "ssh",
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


def _remote_path(directory, lane):
    path = posixpath.normpath(str(directory))
    root = lane.stage_root
    if (
        not _PATH.fullmatch(path)
        or root is None
        or not path.startswith(root.rstrip("/") + "/")
    ):
        raise RemoteLaneDown(b"remote_lane_path_outside_stage_root")
    return path


def _run(lane, script, *, feed=None, timeout=SSH_SECONDS):
    """One remote shell script over ssh. ``feed`` writes its stdin from a helper thread and stderr is drained by
    another, so ``timeout`` bounds the WHOLE exchange: a link that stalls mid-upload is killed at the deadline, never
    waited on. (``communicate`` is not used: it would close the stdin pipe under the writer.)
    """
    import threading
    import time

    command = [*_ssh(lane), "sh -c " + shlex.quote(script)]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if feed is not None else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=docker_environment(lane.docker_host),
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


def mirror(directory, lane=None):
    """Make the remote machine's ``directory`` (the same absolute path) hold exactly the controller's: its contents are
    replaced in place (a bind-mounted directory keeps its inode), modes kept, owned by the ssh user. No-op outside a
    remote round. Any fault raises `RemoteLaneDown`."""
    lane = current() if lane is None else lane
    if lane is None:
        return
    local = Path(directory)
    path = _remote_path(local, lane)
    quoted = shlex.quote(path)
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

    _run(lane, script, feed=feed)


def discard(directory, lane=None):
    """Remove the remote copy of ``directory`` (and its parent, when that leaves it empty). No-op outside a remote
    round. Any fault raises `RemoteLaneDown`; callers that clean up best-effort catch it (the remote machine's own
    sweep removes what is left)."""
    lane = current() if lane is None else lane
    if lane is None:
        return
    path = _remote_path(Path(directory), lane)
    quoted = shlex.quote(path)
    parent = shlex.quote(posixpath.dirname(path))
    script = (
        "set -eu; "
        f"if [ -d {quoted} ]; then chmod -R u+w -- {quoted}; find {quoted} -delete; fi; "
        f"rmdir -- {parent} 2>/dev/null || true"
    )
    _run(lane, script)


def link_up(lane=None, *, timeout=PROBE_SECONDS):
    """Whether the remote lane's daemon answers now (``docker version``). True outside a remote round."""
    lane = current() if lane is None else lane
    if lane is None:
        return True
    try:
        done = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            env=docker_environment(lane.docker_host),
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=os.sep,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0 and bool(done.stdout.strip())


def wall_stop_observable(observation, *, box_seconds=None, needed=None):
    """Whether a wall stop may be read as the candidate's. Outside a remote round: always (unchanged). Inside one, only
    by the BOX's own records (CV-Motor L12624 (a) + the link part of (c)): the container was observed at the stop
    (``observation``), the lane's daemon answers now (`link_up`), and ``box_seconds()`` (the program's age on the box's
    own kernel clock, read in its container; None when the program is gone or unreadable) is at least ``needed`` seconds.
    A stalled link looks exactly like a stalled program, so a program that already ended there, or any read that fails,
    is Carbon's. Whether the box was quiet for the run is the caller's guard (`host_quiet`'s box probes).
    """
    import math

    if current() is None:
        return True
    if type(observation) is not dict or observation.get("status") != "OBSERVED":
        return False
    if box_seconds is None or type(needed) not in (int, float):
        return False
    if not link_up():
        return False
    try:
        age = box_seconds()
    except Exception:  # noqa: BLE001 - unreadable: Carbon's
        return False
    return type(age) is float and math.isfinite(age) and age >= needed


def box_output(lane, script, *, timeout=PROBE_SECONDS):
    """The stdout of one short read-only shell ``script`` on ``lane``'s box over ssh (bounded), or None on any fault."""
    try:
        done = subprocess.run(
            [*_ssh(lane), "sh -c " + shlex.quote(script)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=docker_environment(lane.docker_host),
            timeout=timeout,
            check=False,
            cwd=os.sep,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 or len(done.stdout) > 65536:
        return None
    return done.stdout


# -- recovery: the daemon an operation's intent names ---------------------------------------------------------------------


def intent_fields():
    """What an operation's or grade session's durable intent records about where its container runs: ``{"remote":
    {"docker_host", "stage_root"}}`` in a remote round, else ``{}`` (an intent outside one is byte-identical to before).
    """
    lane = current()
    if lane is None:
        return {}
    return {"remote": {"docker_host": lane.docker_host, "stage_root": lane.stage_root}}


def recorded(intent):
    """The remote lane an intent recorded (a `RemoteSpec` with no cores), or None (the local daemon). A malformed
    record raises ValueError: recovery never guesses which daemon holds a container."""
    entry = intent.get("remote") if type(intent) is dict else None
    if entry is None:
        return None
    if type(entry) is not dict or set(entry) != {"docker_host", "stage_root"}:
        raise ValueError("remote_lane_intent")
    parse_docker_host(entry["docker_host"])
    return RemoteSpec(entry["docker_host"], "", _checked_root(entry["stage_root"]))


def cli_for(spec):
    """A Docker CLI for ``spec``'s daemon (a recorded `RemoteSpec`), or the local daemon (None)."""
    from carbon.reconstruction.worker.docker_runtime import DockerCLI

    cli = DockerCLI()
    cli.docker_host = None if spec is None else spec.docker_host
    return cli


__all__ = [
    "MAX_REMOTE_LANES",
    "RECORD",
    "SCHEMA",
    "RemoteLaneDown",
    "RemoteSpec",
    "box_output",
    "cli_for",
    "current",
    "current_environment",
    "discard",
    "docker_environment",
    "docker_host",
    "intent_fields",
    "is_remote_environment",
    "link_up",
    "load",
    "local_for",
    "mirror",
    "parse_docker_host",
    "recorded",
    "wall_stop_observable",
]
