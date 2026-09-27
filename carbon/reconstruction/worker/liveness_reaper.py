"""Detached reaper for one exact miner-lane launch that has no deadline.

A miner's own research runs with no Carbon time limit, so the deadline
watchdog (`watchdog.py`) has nothing to wait for. What still has to be true is
that the container does not outlive the process that owns it: if the
controller dies, nothing is left to collect the run, and the container would
otherwise run on the miner's machine until someone notices.

This reaper removes the exact container - by name *and* launch-digest label,
through `remove_exact_container` - once its owning controller process is gone,
and never while it lives. It imposes no time limit of any kind.

**Why process identity, not a lease file.** A lease the controller renews
needs a renewal period and an expiry, and both are time limits Carbon would be
choosing: a controller that is alive but stalled - a suspended laptop, a
stopped process, a machine under heavy load - misses its renewals and has a
live run killed. The owning process's identity is exact instead: its pid
together with the kernel's record of when that pid started. A pid alone can be
reused by an unrelated process after the controller dies; the pair cannot be,
within one boot. A zombie (exited, not yet reaped) counts as gone.

Exit codes: 0 when the container is gone or not this launch's, or after
removing it; 2 on bad arguments; 3 when removal could not be confirmed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    remove_exact_container,
)
from carbon.reconstruction.worker.model import (
    WorkerCode,
    WorkerFailure,
    exact_digest,
    exact_token,
)

LAUNCH_LABEL = "org.opencontainers.image.carbon.c03.launch"
#: How often the reaper looks. A cost, not a limit: nothing is removed on a
#: schedule, only when the owner is observed gone.
POLL_SECONDS = 2.0


def process_identity(pid: int) -> str | None:
    """The live process `pid` as an identity that is not reused: its start
    time as the kernel records it. None when no such process is running."""
    if type(pid) is not int or pid <= 0:
        return None
    stat = Path("/proc") / str(pid) / "stat"
    if Path("/proc/self/stat").exists():
        try:
            raw = stat.read_text(encoding="ascii", errors="replace")
        except OSError:
            return None
        # The command name is in parentheses and may itself contain them.
        fields = raw[raw.rindex(")") + 2 :].split()
        if fields[0] in {"Z", "X"}:
            return None
        return "proc-start:" + fields[19]
    # Without /proc (macOS), ps reports the same two facts.
    try:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = result.stdout.decode("ascii", errors="replace").strip()
    if result.returncode != 0 or not text or text.startswith("Z"):
        return None
    return "ps-start:" + " ".join(text.split()[1:])


def _launch_label(cli, container_name):
    """The container's launch label; None when it is gone; "" when the
    runtime could not answer (keep watching - that is not absence)."""
    result = cli.run(
        [
            "inspect",
            container_name,
            "--format",
            '{{index .Config.Labels "' + LAUNCH_LABEL + '"}}',
        ],
        timeout=10,
        accepted=(0, 1),
    )
    if result.returncode != 0:
        return None if b"No such" in result.stderr else ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def watch(
    container_name,
    launch_digest,
    controller_pid,
    controller_identity,
    *,
    cli,
    identify=process_identity,
    sleep=time.sleep,
    poll=POLL_SECONDS,
):
    """Wait while the controller lives; remove the exact container when it
    does not. Returns the exit code."""
    while True:
        label = _launch_label(cli, container_name)
        if label is None:
            return 0  # The run finished and its owner cleaned up.
        if label and label != launch_digest:
            return 0  # Another launch's container: never this reaper's.
        if label and identify(controller_pid) != controller_identity:
            try:
                remove_exact_container(
                    cli=cli, container_name=container_name, launch_digest=launch_digest
                )
            except WorkerFailure:
                return 3
            return 0
        sleep(poll)


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(arguments) != 4:
        return 2
    container_name, launch_digest, raw_pid, identity = arguments
    try:
        exact_token(container_name)
        exact_digest(launch_digest)
        pid = int(raw_pid)
    except (WorkerFailure, ValueError):
        return 2
    return watch(container_name, launch_digest, pid, identity, cli=DockerCLI())


def controller_guard() -> dict:
    """This process as the owner a reaper watches, recorded in the launch's
    durable intent before the container exists. Raises when the identity
    cannot be read, so an unbounded run never starts unguarded."""
    pid = os.getpid()
    identity = process_identity(pid)
    if identity is None:
        raise WorkerFailure(WorkerCode.UNAVAILABLE)
    return {"kind": "CONTROLLER_LIVENESS", "pid": pid, "identity": identity}


def spawn_liveness_reaper(
    *, container_name: str, launch_digest: str, guard: dict
) -> None:
    """Start the detached reaper guarding one launch for `guard`'s owner.
    Raises when it cannot start; the caller then removes the container."""
    exact_token(container_name)
    exact_digest(launch_digest)
    if (
        type(guard) is not dict
        or guard.get("kind") != "CONTROLLER_LIVENESS"
        or guard.get("pid") != os.getpid()
        or process_identity(os.getpid()) != guard.get("identity")
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    pid, identity = guard["pid"], guard["identity"]
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
                "carbon.reconstruction.worker.liveness_reaper",
                container_name,
                launch_digest,
                str(pid),
                identity,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Its own session, so a signal to the controller's terminal or
            # process group does not take the reaper with it.
            start_new_session=True,
            close_fds=True,
            env=environment,
        )
    except OSError:
        raise WorkerFailure(WorkerCode.UNAVAILABLE) from None


if __name__ == "__main__":
    raise SystemExit(main())
