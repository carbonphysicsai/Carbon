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
on a remote lane is the candidate's only when the link is up and the container was observed at the stop
(`wall_stop_observable`); otherwise it stays Carbon's.

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
#: The most remote lanes a host may name (the owner's order: one second machine).
MAX_REMOTE_LANES = 1
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
    from carbon.reconstruction.host_execution import parse_cpuset
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    path = Path(HOST_ROOT if root is None else root) / RECORD
    if not path.exists():
        return ()
    document = json.loads(path.read_bytes())
    if (
        type(document) is not dict
        or set(document) != {"schema", "lanes"}
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
    return tuple(specs)


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
def local_for(identity):
    """Inside a remote round, run a TIMING container (`grade_lanes.is_timing_identity`, or inside
    `grade_lanes.timing_exclusive`) on the grading host: the round's lane is rebound to its local twin (same index and
    lock directory, so the host timing gate is still taken EXCLUSIVE; the host record's cores; the local daemon).
    Anything else, or outside a remote round: unchanged. A host with no execution record has no local cores to name, so
    the timing stage refuses (Carbon's, UNAVAILABLE) rather than guess."""
    from carbon.reconstruction import grade_lanes

    lane = current()
    if lane is None or not (
        grade_lanes.is_timing_identity(identity) or grade_lanes.timing_requested()
    ):
        yield
        return
    from carbon.reconstruction.host_execution import HostExecutionRecord
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT

    record = HostExecutionRecord.load(HOST_ROOT)
    if record is None:
        raise RemoteLaneDown(b"remote_lane_timing_no_local_cores")
    twin = grade_lanes.Lane(lane.index, record.cpuset, lane.lock_dir)
    with grade_lanes.bound(twin):
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


def _run(lane, script, *, stdin=None, feed=None, timeout=SSH_SECONDS):
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
    try:
        if feed is not None:
            try:
                feed(process.stdin)
            finally:
                process.stdin.close()
        _out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise RemoteLaneDown(b"remote_lane_ssh_timeout") from None
    except (OSError, ValueError, tarfile.TarError) as error:
        process.kill()
        process.wait()
        raise RemoteLaneDown(repr(error).encode()[:512]) from None
    if process.returncode != 0:
        raise RemoteLaneDown(b"exit=%d\n" % process.returncode + (err or b"")[-512:])


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
        f"find {quoted} -mindepth 1 -delete; "
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
        f"if [ -d {quoted} ]; then find {quoted} -delete; fi; "
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


def wall_stop_observable(observation):
    """Whether a wall stop may be read as the candidate's: always outside a remote round; inside one, only with the
    container observed at the stop and the link up now (a stalled link looks exactly like a stalled program).
    """
    if current() is None:
        return True
    return (
        type(observation) is dict
        and observation.get("status") == "OBSERVED"
        and link_up()
    )


__all__ = [
    "MAX_REMOTE_LANES",
    "RECORD",
    "SCHEMA",
    "RemoteLaneDown",
    "RemoteSpec",
    "current",
    "current_environment",
    "discard",
    "docker_environment",
    "docker_host",
    "is_remote_environment",
    "link_up",
    "load",
    "local_for",
    "mirror",
    "parse_docker_host",
    "wall_stop_observable",
]
