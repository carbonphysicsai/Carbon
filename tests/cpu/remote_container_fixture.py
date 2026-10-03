"""A container the miner started from the pinned worker, here on this machine.

`LocalContainer` stands in for the miner's SSH into an `ssh-container`
setup: `run` executes each fixed script in real bash, with only the tools a
container has on PATH, and `tunnel` is the identity, because the job server
the script starts listens on this machine's loopback. The worker's Python is
a wrapper that runs this interpreter, so the script starts the real
`carbon.compute.job_server` as a real process. No SSH connection is made.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from carbon.compute import remote_container
from carbon.compute.remote_machine import MAX_STDOUT_BYTES, TIMED_OUT, Tunnel
from carbon.compute.remote_runner import RemoteWorker
from carbon.compute.remote_transport import SSHContainer

#: The tools a container from the pinned worker image has, and the scripts
#: use. Nothing else is on PATH.
TOOLS = ("mkdir", "rm", "setsid", "sleep", "head", "tr", "grep", "cat")


class Process:
    """The tunnel's ssh process, as a fixture: it records being closed."""

    def __init__(self):
        self.closed = False

    def poll(self):
        return 0 if self.closed else None

    def terminate(self):
        self.closed = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.closed = True


class LocalContainer:
    """`SSHClient`'s `run` and `tunnel`, on this machine."""

    def __init__(self, root: Path):
        self.root = root
        self.tools = root / "tools"
        self.tools.mkdir()
        for name in TOOLS:
            (self.tools / name).symlink_to(shutil.which(name))
        self.scripts, self.tunnels = [], []

    def run(self, script, *, timeout):
        self.scripts.append(script)
        try:
            completed = subprocess.run(
                ["/bin/bash", "-s"],
                input=script.encode(),
                env={"PATH": str(self.tools)},
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return TIMED_OUT, b""
        return completed.returncode, completed.stdout[:MAX_STDOUT_BYTES]

    def tunnel(self, remote):
        tunnel = Tunnel(Process(), remote)
        self.tunnels.append(tunnel)
        return tunnel


def worker_python(root: Path) -> Path:
    """The pinned worker's Python in the container: this interpreter."""
    path = root / "python"
    path.write_text(f'#!/bin/bash\nexec {sys.executable} "$@"\n')
    path.chmod(0o755)
    return path


def build_file(root: Path, image, **changed) -> Path:
    """The build identity the pinned worker image carries."""
    path = root / "worker-image-build.json"
    path.write_text(
        json.dumps({**remote_container.expected_identity(image), **changed}) + "\n"
    )
    return path


def container(tmp_path: Path, image, **changed):
    """An `ssh-container` transport on this machine, holding `image`'s build
    identity (with `changed` fields, to build a mismatch)."""
    root = tmp_path / "container"
    root.mkdir()
    (root / "jobs").mkdir()
    ssh = LocalContainer(root)
    python = worker_python(root)
    transport = SSHContainer(
        ssh,
        python=str(python),
        build_file=str(build_file(root, image, **changed)),
        root=str(root / "jobs"),
    )
    return transport, ssh, python


def local_worker(image, python, environment=(("JAX_PLATFORMS", "cpu"),)):
    """The Challenge's worker, started with the container's Python."""
    return RemoteWorker(
        image,
        environment,
        (str(python), "-I", "-m", "carbon.compute.job_server"),
    )
