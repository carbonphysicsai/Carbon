"""A container the miner started from the pinned worker, here on this machine.

`LocalContainer` stands in for the miner's SSH into an `ssh-container`
setup: `run` executes each fixed script in real bash, with only the tools a
container has on PATH. `tunnel` is a `local_tunnel`: an owner-only Unix
socket relayed to the job server's port on this machine's loopback, as ssh's
forward relays it to the machine. The worker's Python is a wrapper that runs
this interpreter, so the script starts the real `carbon.compute.job_server`
as a real process. No SSH connection is made.

Unlike a container, the scripts see this machine's whole process table. The
stop script never confirms a cleanup while another process of this user that
started after the job still runs, because it cannot tell that process from
one the job left (`remote_container.stop_script`). A test expecting a
confirmed cleanup therefore needs no other process of this user to start
during it. CI and `scripts/dev/canonical.sh` are isolated. On a host where
other sessions run as the same user, run natively in a private PID namespace:
`unshare --user --map-current-user --pid --fork --mount-proc -- <pytest>`.
`unconfirmed_because` names what kept a cleanup unconfirmed.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from carbon.compute import remote_container
from carbon.compute.remote_machine import MAX_STDOUT_BYTES, TIMED_OUT, Tunnel
from carbon.compute.remote_runner import RemoteWorker
from carbon.compute.remote_transport import SSHContainer

#: The tools a container from the pinned worker image has, and the scripts
#: use. Nothing else is on PATH.
TOOLS = ("mkdir", "rm", "setsid", "sleep", "head", "tr", "grep", "cat")


def _pump(source, sink):
    try:
        while chunk := source.recv(65536):
            sink.sendall(chunk)
    except OSError:
        pass
    finally:
        try:
            sink.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class Relay:
    """The tunnel's ssh process, as a fixture: it serves the tunnel's Unix
    socket and relays each connection to `port` on this machine's loopback.
    It records being closed."""

    def __init__(self, path: str, port: int):
        self.closed, self.port = False, port
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(path)
        self.listener.listen()
        self.listener.settimeout(0.2)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self.closed:
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(target=self._relay, args=(client,), daemon=True).start()

    def _relay(self, client):
        with client:
            try:
                upstream = socket.create_connection(("127.0.0.1", self.port), 30)
            except OSError:
                return
            with upstream:
                back = threading.Thread(target=_pump, args=(upstream, client))
                back.start()
                _pump(client, upstream)
                back.join(60)

    def poll(self):
        return 0 if self.closed else None

    def terminate(self):
        self.closed = True
        self.listener.close()

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminate()


def local_tunnel(port: int) -> Tunnel:
    """A tunnel to the job server listening on this machine's loopback
    `port`, made as `SSHClient.tunnel` makes one: its socket in a new
    owner-only directory."""
    tunnel = Tunnel(None, tempfile.mkdtemp(prefix="carbon-tunnel-"))
    tunnel.process = Relay(tunnel.path, port)
    return tunnel


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

    def tunnel(self, remote, *, host="127.0.0.1"):
        # The container's loopback is this machine's.
        tunnel = local_tunnel(remote)
        self.tunnels.append(tunnel)
        return tunnel


def _stat(pid: int) -> list[str] | None:
    """The fields of /proc/<pid>/stat after the command name, or None."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (OSError, IndexError):
        return None


def unconfirmed_because(record) -> str:
    """Why a cleanup went unconfirmed, as far as this machine can tell.

    It names this user's other processes that started at or after the job's
    `record` and still run: the stop script refuses to confirm while any
    remains, whoever started it. This test process and its ancestors aside,
    as the stop script spares its own. An empty list points at the job
    itself, or at a process that has since ended.
    """
    if record is None:
        return "cleanup unconfirmed: no job record"
    spared, pid = set(), os.getpid()
    while pid > 0 and pid not in spared and (fields := _stat(pid)):
        spared.add(pid)
        pid = int(fields[1])
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in spared:
            continue
        fields = _stat(int(entry.name))
        try:
            mine = entry.stat().st_uid == os.getuid()
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").strip()
        except OSError:
            continue
        if (
            mine
            and fields
            and fields[0] not in ("Z", "X")
            and int(fields[19]) >= record.start
        ):
            found.append(f"{entry.name} {command.decode(errors='replace')[:80]}")
    return (
        "cleanup unconfirmed. Processes of this user started since the job and "
        f"still running: {found or 'none now'}. If they are not the job's, "
        "this host shares its process table with other sessions: see "
        "remote_container_fixture's docstring."
    )


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
