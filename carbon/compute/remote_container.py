"""A container the miner started from the pinned worker, reached over SSH.

OWNER-MINER-COMPUTE-LINK-ONLY-01, as amended on 2026-10-02: "miners should be
able to use whatever they want to run their setup." Some rentals are a
container with no Docker daemon inside, such as a RunPod or Lium pod. The
miner starts it from the pinned GPU worker image, with SSH into it; Carbon
never starts, stops or bills it (LINKONLY-D5).

**What runs in the container is fixed.** Each script runs with `bash -s` over
the miner's own SSH (`remote_machine.SSHClient`):

- `identity_script` checks the pinned worker's Python is there and prints the
  build identity the image carries (`/opt/carbon/worker-image-build.json`,
  written at build). `checked_identity` refuses any difference from the
  pinned manifest (LINKONLY-D6). This is a self-report, recorded as
  `build-identity`, never as an image ID.
- `start_script` starts one job server as a process for one trial:
  - in its own directory, `/tmp/carbon-job-<24 hex>`, made with
    `mkdir -m 700`, so an existing path is never reused;
  - its environment through an owner-only file the starting shell deletes,
    never on a command line;
  - in its own session (`setsid`), so it outlives the SSH session;
  - listening on the container's loopback only, on a free port it writes
    back, which the script prints as `127.0.0.1:<port>`;
  - with a record the controller keeps, never the container: when the job
    started and the job server's session (`job_record`).
- `stop_script` stops the job's processes: those whose environment names the
  job's directory, and those in the job server's session or process group.
  It then removes the directory, and exits 0 only when it can confirm the job
  is gone (see `stop_script`).

The scripts install nothing and never use sudo. The job server also ends
itself after the job's lifetime, even if the controller never returns.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Sequence
from dataclasses import dataclass

from .remote_machine import (
    JOB_DIRECTORY_PRESENT,
    JOB_SERVER_NOT_STARTED,
    NO_WORKER_RUNTIME,
    RemoteMachineError,
    checked_command,
    checked_name,
    environment_lines,
)

__all__ = [
    "BUILD_FIELDS",
    "BUILD_FILE",
    "BUILD_SCHEMA",
    "JOB_ROOT",
    "WORKER_PYTHON",
    "JobRecord",
    "checked_identity",
    "expected_identity",
    "identity_script",
    "job_directory",
    "job_record",
    "start_script",
    "stop_script",
]

#: The pinned worker's interpreter, as the image installs it.
WORKER_PYTHON = "/opt/carbon-worker/bin/python"
#: The build identity every Carbon worker image carries, written at build
#: (`.devcontainer/Dockerfile.reconstruction-worker`; the GPU worker's
#: `.devcontainer/accelerators/Dockerfile` updates its base, recipe and lock).
BUILD_FILE = "/opt/carbon/worker-image-build.json"
BUILD_SCHEMA = "carbon.c03.worker-image-build.v1"
#: The pinned manifest's fields the build file carries: everything but the
#: image ID, which no image can know about itself.
BUILD_FIELDS = (
    "source_tree_digest",
    "wheel_digest",
    "lock_digest",
    "base_image_digest",
    "build_recipe_digest",
    "entrypoint_digest",
)
MAX_BUILD_BYTES = 4096
#: Where a job's directory is made in the container.
JOB_ROOT = "/tmp"
#: How long the start script waits for the job server's port.
START_WAIT_SECONDS = 30
#: The environment the transport sets itself; a caller never names these.
TRANSPORT_ENV = frozenset(
    {"CARBON_JOB_BIND", "CARBON_JOB_PORT", "CARBON_JOB_PORT_FILE", "CARBON_JOB_ROOT"}
)
_PATH = re.compile(r"^/[A-Za-z0-9._/-]{0,255}$")
#: The start script's record line: the job's start, in clock ticks since boot
#: (field 22 of /proc/<pid>/stat), and the job server's session.
_RECORD = re.compile(rb"^carbon-job-record ([0-9]{1,20}) ([0-9]{1,7})$", re.MULTILINE)
#: The kernel's largest process ID (PID_MAX_LIMIT).
_PID_MAX = 4194304


@dataclass(frozen=True)
class JobRecord:
    """What the start script reports and the controller keeps for cleanup.

    `start` is when the job started, in clock ticks since boot (field 22 of
    /proc/<pid>/stat); `session` is the job server's session, which is also
    its process group. Never 1: that would name the container's init.
    """

    start: int
    session: int

    def __post_init__(self):
        if type(self.start) is not int or not 0 <= self.start < 10**20:
            raise ValueError("a job's start is clock ticks since boot")
        if type(self.session) is not int or not 2 <= self.session <= _PID_MAX:
            raise ValueError("a job's session is its server's process ID")


def job_record(stdout: bytes) -> JobRecord | None:
    """The record the start script printed, or None when there is not
    exactly one well-formed record line."""
    found = _RECORD.findall(stdout)
    if len(found) != 1:
        return None
    try:
        return JobRecord(int(found[0][0]), int(found[0][1]))
    except ValueError:
        return None


def _checked_path(value) -> str:
    if type(value) is not str or not _PATH.fullmatch(value) or "/../" in value + "/":
        raise ValueError("a plain absolute path is required")
    return value


def job_directory(name: str, *, root: str = JOB_ROOT) -> str:
    """The job's directory in the container, named like a job container."""
    return _checked_path(root).rstrip("/") + "/" + checked_name(name)


def identity_script(*, python: str = WORKER_PYTHON, build_file: str = BUILD_FILE):
    """Exit NO_WORKER_RUNTIME without the pinned worker; otherwise print its
    build identity, bounded."""
    python, build = (shlex.quote(_checked_path(p)) for p in (python, build_file))
    return f"""set -u
[ -x {python} ] || exit {NO_WORKER_RUNTIME}
[ -f {build} ] && [ ! -L {build} ] || exit {NO_WORKER_RUNTIME}
head -c {MAX_BUILD_BYTES + 1} {build}
"""


def expected_identity(image) -> dict:
    """The build identity the pinned worker `image` was built with."""
    return {"schema": BUILD_SCHEMA, **{f: getattr(image, f) for f in BUILD_FIELDS}}


def checked_identity(stdout: bytes, image) -> dict:
    """The container's build identity, exactly the pinned worker's, or a
    refusal. Nothing the container printed is copied into the refusal."""
    try:
        if len(stdout) > MAX_BUILD_BYTES:
            raise ValueError("bounded build identity")
        reported = json.loads(stdout)
    except (ValueError, UnicodeError):
        reported = None
    if reported != expected_identity(image):
        raise RemoteMachineError(
            "worker_identity_mismatch",
            (
                "start your container from the pinned GPU worker image this "
                "checkout built (push it with scripts/dev/push_worker_image.sh), "
                "then retry"
            ),
        )
    return reported


def start_script(
    *,
    name: str,
    env: Sequence[tuple[str, str]],
    command: Sequence[str],
    root: str = JOB_ROOT,
    wait_seconds: int = START_WAIT_SECONDS,
) -> str:
    """The script that starts one job server process in the container.

    It prints `127.0.0.1:<port>`, the loopback address the server took, so
    the same SSH port forward reaches it as reaches a job container. As soon
    as the server is launched, before any job program runs, it also prints
    `carbon-job-record <start> <session>` (`job_record`): when this script
    started, in clock ticks since boot, and the server's session, which
    `setsid` makes the server's own process ID. The controller keeps that
    record for cleanup; nothing in the container can change it.
    """
    directory = job_directory(name, root=root)
    if any(key in TRANSPORT_ENV for key, _ in env):
        raise ValueError("the transport sets where the job server listens")
    if type(wait_seconds) is not int or not 1 <= wait_seconds <= 300:
        raise ValueError("bounded start wait required")
    entry, *args = checked_command(command)
    lines = environment_lines(
        (
            *env,
            ("CARBON_JOB_BIND", "127.0.0.1"),
            ("CARBON_JOB_PORT", "0"),
            ("CARBON_JOB_PORT_FILE", directory + "/port"),
            ("CARBON_JOB_ROOT", directory),
        )
    )
    quoted = shlex.quote(directory)
    return f"""set -eu
umask 077
[ -x {shlex.quote(entry)} ] || exit {NO_WORKER_RUNTIME}
carbon_dir={quoted}
read -r carbon_stat < "/proc/$$/stat"
set -f
set -- ${{carbon_stat##*)}}
set +f
carbon_start="${{20}}"
mkdir -m 700 "$carbon_dir" 2>/dev/null || exit {JOB_DIRECTORY_PRESENT}
{{
{lines}}} > "$carbon_dir/env"
(
  set -a
  . "$carbon_dir/env"
  set +a
  rm -f "$carbon_dir/env"
  exec setsid {shlex.quote(entry)} {" ".join(map(shlex.quote, args))}
) </dev/null >/dev/null 2>&1 &
printf 'carbon-job-record %s %s\\n' "$carbon_start" "$!"
carbon_waited=0
while [ ! -s "$carbon_dir/port" ]; do
  carbon_waited=$((carbon_waited + 1))
  [ "$carbon_waited" -le {wait_seconds * 10} ] || exit {JOB_SERVER_NOT_STARTED}
  sleep 0.1
done
printf '127.0.0.1:%s\\n' "$(head -c 8 "$carbon_dir/port" | tr -cd 0-9)"
"""


def stop_script(
    name: str,
    *,
    root: str = JOB_ROOT,
    record: JobRecord | None = None,
    grace_seconds: int = 10,
) -> str:
    """Stop the job's processes and remove its directory; exit 0 only when
    the job is confirmed gone.

    The job's processes are sent TERM, then KILL:
    - those whose environment names the job's directory (`CARBON_JOB_ROOT`),
      which only Carbon's start script sets and the job's program inherits;
    - with the controller's `record`, those in the job server's session or
      process group, whatever their environment.

    Nothing else is ever signalled. A process the job detached into a session
    of its own (`setsid`), with its environment cleared, is neither, so it is
    not stopped: cleanup is reported unconfirmed instead. The script exits 0
    only when none of the job's processes remain, no process of this user
    that started at or after the job's start remains (the script itself and
    its ancestors aside), and the directory is gone. Carbon cannot tell a
    process the miner started meanwhile from one the job left, so either
    leaves cleanup unconfirmed. Any other outcome exits 1. Without a record
    (a controller that restarted), the marked processes are stopped and the
    directory removed, but cleanup is never confirmed.

    Zombies are already gone and are not counted; nor are kernel threads.
    """
    directory = job_directory(name, root=root)
    if type(grace_seconds) is not int or not 1 <= grace_seconds <= 60:
        raise ValueError("bounded grace required")
    if record is not None and type(record) is not JobRecord:
        raise ValueError("a job record is the one its start script printed")
    marker = shlex.quote("CARBON_JOB_ROOT=" + directory)
    session = record.session if record is not None else 0
    since = shlex.quote(str(record.start) if record is not None else "")
    return f"""set -u
carbon_dir={shlex.quote(directory)}
carbon_marker={marker}
carbon_session={session}
carbon_since={since}
carbon_status() {{
  carbon_state='' carbon_ppid='' carbon_uid='' carbon_pgid='' carbon_sid=''
  {{ while read -r carbon_key carbon_value carbon_rest; do
      case "$carbon_key" in
        State:) carbon_state="$carbon_value" ;;
        PPid:) carbon_ppid="$carbon_value" ;;
        Uid:) carbon_uid="$carbon_value" ;;
        NSpgid:) carbon_pgid="$carbon_value" ;;
        NSsid:) carbon_sid="$carbon_value" ;;
      esac
    done < "/proc/$1/status"; }} 2>/dev/null
  [ -n "$carbon_uid" ]
}}
carbon_started() {{
  carbon_flags='' carbon_start=''
  {{ read -r carbon_stat < "/proc/$1/stat"; }} 2>/dev/null || return 1
  set -f
  set -- ${{carbon_stat##*)}}
  set +f
  [ "$#" -ge 20 ] || return 1
  carbon_flags="$7" carbon_start="${{20}}"
  case "$carbon_flags$carbon_start" in ''|*[!0-9]*) return 1 ;; esac
}}
carbon_spare=' '
carbon_pid=$$
while [ "${{carbon_pid:-0}}" -gt 0 ] 2>/dev/null && carbon_status "$carbon_pid"; do
  carbon_spare="$carbon_spare$carbon_pid "
  carbon_pid="$carbon_ppid"
done
carbon_me=''
if carbon_status $$; then carbon_me="$carbon_uid"; fi
carbon_scan() {{
  carbon_targets='' carbon_remaining=''
  for carbon_proc in /proc/[0-9]*; do
    carbon_pid="${{carbon_proc#/proc/}}"
    case "$carbon_spare" in *" $carbon_pid "*) continue ;; esac
    carbon_status "$carbon_pid" || continue
    case "$carbon_state" in Z*|X*) continue ;; esac
    if [ "$carbon_session" -gt 1 ] && {{ [ "$carbon_pgid" = "$carbon_session" ] || [ "$carbon_sid" = "$carbon_session" ]; }}; then
      carbon_targets="$carbon_targets $carbon_pid"
    elif [ -r "$carbon_proc/environ" ] && tr '\\0' '\\n' < "$carbon_proc/environ" 2>/dev/null | grep -qxF -- "$carbon_marker"; then
      carbon_targets="$carbon_targets $carbon_pid"
    elif [ -n "$carbon_since" ] && [ "$carbon_uid" = "$carbon_me" ]; then
      if ! carbon_started "$carbon_pid"; then
        [ ! -e "$carbon_proc" ] || carbon_remaining="$carbon_remaining $carbon_pid"
      elif [ $((carbon_flags & 2097152)) -eq 0 ] && [ "$carbon_start" -ge "$carbon_since" ]; then
        carbon_remaining="$carbon_remaining $carbon_pid"
      fi
    fi
  done
  carbon_remaining="$carbon_targets$carbon_remaining"
}}
carbon_scan
for carbon_pid in $carbon_targets; do kill -TERM "$carbon_pid" 2>/dev/null || true; done
carbon_waited=0
carbon_scan
while [ -n "$carbon_targets" ] && [ "$carbon_waited" -lt {grace_seconds * 10} ]; do
  carbon_waited=$((carbon_waited + 1))
  sleep 0.1
  carbon_scan
done
carbon_waited=0
while [ -n "$carbon_targets" ] && [ "$carbon_waited" -lt 50 ]; do
  for carbon_pid in $carbon_targets; do kill -KILL "$carbon_pid" 2>/dev/null || true; done
  carbon_waited=$((carbon_waited + 1))
  sleep 0.1
  carbon_scan
done
rm -rf -- "$carbon_dir"
# A process that is only ending, such as the tunnel's own SSH session just
# closed, is given a moment before confirmation is refused.
carbon_waited=0
carbon_scan
while [ -n "$carbon_remaining" ] && [ "$carbon_waited" -lt 20 ]; do
  carbon_waited=$((carbon_waited + 1))
  sleep 0.1
  carbon_scan
done
[ -n "$carbon_since" ] && [ -n "$carbon_me" ] || exit 1
[ -z "$carbon_remaining" ] || exit 1
[ ! -e "$carbon_dir" ] || exit 1
exit 0
"""
