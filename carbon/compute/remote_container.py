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
    back, which the script prints as `127.0.0.1:<port>`.
- `stop_script` stops only processes whose environment names that job's
  directory, then removes the directory. It exits 0 only once both are gone.

The scripts install nothing and never use sudo. The job server also ends
itself after the job's lifetime, even if the controller never returns.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Sequence

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
    "checked_identity",
    "expected_identity",
    "identity_script",
    "job_directory",
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
    the same SSH port forward reaches it as reaches a job container.
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
carbon_waited=0
while [ ! -s "$carbon_dir/port" ]; do
  carbon_waited=$((carbon_waited + 1))
  [ "$carbon_waited" -le {wait_seconds * 10} ] || exit {JOB_SERVER_NOT_STARTED}
  sleep 0.1
done
printf '127.0.0.1:%s\\n' "$(head -c 8 "$carbon_dir/port" | tr -cd 0-9)"
"""


def stop_script(name: str, *, root: str = JOB_ROOT, grace_seconds: int = 10) -> str:
    """Stop the job's processes and remove its directory; exit 0 only once
    both are gone.

    A process is the job's only when its environment names the job's
    directory (`CARBON_JOB_ROOT`), which only Carbon's start script sets; the
    job's program inherits it too, so it is stopped with its server.
    """
    directory = job_directory(name, root=root)
    if type(grace_seconds) is not int or not 1 <= grace_seconds <= 60:
        raise ValueError("bounded grace required")
    marker = shlex.quote("CARBON_JOB_ROOT=" + directory)
    return f"""set -u
carbon_dir={shlex.quote(directory)}
carbon_marker={marker}
carbon_job_pids() {{
  for carbon_env in /proc/[0-9]*/environ; do
    [ -r "$carbon_env" ] || continue
    if tr '\\0' '\\n' < "$carbon_env" 2>/dev/null | grep -qxF -- "$carbon_marker"; then
      carbon_pid="${{carbon_env#/proc/}}"
      printf '%s\\n' "${{carbon_pid%/environ}}"
    fi
  done
}}
for carbon_pid in $(carbon_job_pids); do kill -TERM "$carbon_pid" 2>/dev/null || true; done
carbon_waited=0
while [ -n "$(carbon_job_pids)" ] && [ "$carbon_waited" -lt {grace_seconds * 10} ]; do
  carbon_waited=$((carbon_waited + 1))
  sleep 0.1
done
carbon_waited=0
while [ -n "$(carbon_job_pids)" ] && [ "$carbon_waited" -lt 50 ]; do
  for carbon_pid in $(carbon_job_pids); do kill -KILL "$carbon_pid" 2>/dev/null || true; done
  carbon_waited=$((carbon_waited + 1))
  sleep 0.1
done
rm -rf -- "$carbon_dir"
[ -z "$(carbon_job_pids)" ] || exit 1
[ ! -e "$carbon_dir" ] || exit 1
exit 0
"""
