"""A GPU machine the miner runs, reached over SSH (LINKONLY-D4).

OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon never starts, stops or bills a
machine. The miner runs their own GPU machine, with Docker and the NVIDIA
Container Toolkit, and Carbon connects to it over SSH to run one job
container per practice trial, then removes that container.

**The miner's SSH decides how the machine is reached.** `SSHClient` passes
no `-i`, no `IdentitiesOnly`, no known-hosts file of Carbon's and no
`StrictHostKeyChecking=accept-new`: the miner's own agent, `~/.ssh/config`
and known hosts apply, so their key never leaves their machine and an
unknown host key is refused as SSH refuses it. `BatchMode=yes` means nothing
ever prompts. The destination is `[user@]host` or an ssh-config alias, never
an option.

**What runs on the machine is fixed.** `start_script` checks Docker, the
NVIDIA Container Toolkit, that Docker is usable without sudo (Carbon never
holds a sudo password) and that the pinned worker image is present by ID. It
then starts one container by image ID with a per-job name, `--rm`, the GPUs,
and the job port published on the machine's loopback only; the job's
environment goes through an owner-only temporary file, deleted at once. It
installs nothing. `remove_script` removes only a container named
`carbon-job-<24 hex>`. `send_image` streams the pinned worker
(`docker save | ssh docker load`) and checks it arrived by image ID.

Every outcome of a run is an exit status (a timeout 124, no `ssh` client
127), never an exception that could skip a trial's cleanup.

This module is the `ssh-docker` transport's machine side and the SSH client
every transport shares; a container with no Docker inside (`ssh-container`)
has its own scripts in `remote_container` (LINKONLY-D5).
"""

from __future__ import annotations

import os
import re
import select
import shlex
import socket
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

__all__ = [
    "CONTAINER_NAME",
    "JOB_PORT",
    "RemoteMachineError",
    "SSHClient",
    "Tunnel",
    "check_script",
    "checked_command",
    "checked_destination",
    "checked_name",
    "environment_lines",
    "failure_for",
    "image_check_script",
    "published_port",
    "remove_script",
    "send_image",
    "start_script",
]

#: The port the job server listens on inside the worker container.
JOB_PORT = 8000
#: Exit codes the start script uses for causes the miner must fix.
NO_DOCKER, NO_NVIDIA_TOOLKIT, NO_DOCKER_ACCESS, NO_WORKER_IMAGE = 90, 91, 92, 93
#: Exit codes of a container's scripts (`remote_container`, LINKONLY-D5): no
#: pinned worker runtime in it, the job server did not start, and a job
#: directory of the same name still present.
NO_WORKER_RUNTIME, JOB_SERVER_NOT_STARTED, JOB_DIRECTORY_PRESENT = 94, 95, 96
#: Local outcomes of the SSH run itself, and SSH's own failure.
TIMED_OUT, NO_SSH_CLIENT, SSH_FAILED = 124, 127, 255
#: Bound on what a script's standard output may return.
MAX_STDOUT_BYTES = 64 * 1024
#: Only containers Carbon names are ever removed.
CONTAINER_NAME = re.compile(r"^carbon-job-[0-9a-f]{24}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_USER = r"[A-Za-z0-9_][A-Za-z0-9._-]{0,31}"
_HOST = r"[A-Za-z0-9_][A-Za-z0-9._-]{0,252}"
#: `[user@]host` or an ssh-config alias; nothing that ssh reads as an option.
DESTINATION = re.compile(rf"^(?:{_USER}@)?{_HOST}$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ENV_VALUE = re.compile(r"^[A-Za-z0-9._:/@=+-]{0,256}$")
_ARGUMENT = re.compile(r"^[A-Za-z0-9._:/=+-]{1,256}$")
_PUBLISHED = re.compile(rb"^127\.0\.0\.1:([0-9]{1,5})$", re.MULTILINE)


class RemoteMachineError(Exception):
    """A typed failure on the miner's machine; `code` is closed, and
    `next_step` is Carbon-authored text. Nothing the machine printed is
    copied in."""

    def __init__(self, code: str, next_step: str, *, exit_status: int | None = None):
        super().__init__(code)
        self.code, self.next_step, self.exit_status = code, next_step, exit_status


#: Exit status -> (code, next step). Anything else is `remote_start_failed`.
FAILURES = {
    NO_DOCKER: ("no_docker", "install Docker on your GPU machine"),
    NO_NVIDIA_TOOLKIT: (
        "no_nvidia_container_toolkit",
        "install the NVIDIA Container Toolkit on your GPU machine",
    ),
    NO_DOCKER_ACCESS: (
        "no_docker_access",
        (
            "let your SSH user run docker without sudo (for example, add it to "
            "the docker group); Carbon never asks for a sudo password"
        ),
    ),
    NO_WORKER_IMAGE: (
        "no_worker_image",
        "send the pinned GPU worker image to your machine, then retry",
    ),
    NO_WORKER_RUNTIME: (
        "no_worker_runtime",
        (
            "start your container from the pinned GPU worker image (or an "
            "image built on it), then retry"
        ),
    ),
    JOB_SERVER_NOT_STARTED: (
        "job_server_not_started",
        "check your container can run the worker's Python and write to /tmp",
    ),
    JOB_DIRECTORY_PRESENT: (
        "job_directory_present",
        "an earlier attempt's job directory is still there; retry the practice",
    ),
    TIMED_OUT: ("ssh_timed_out", "check that your machine is up and reachable"),
    NO_SSH_CLIENT: ("no_ssh_client", "install an OpenSSH client on this machine"),
    SSH_FAILED: (
        "ssh_unreachable",
        (
            "check `ssh <your destination>` works from this machine without a "
            "prompt, using your own key and known hosts"
        ),
    ),
}


def failure_for(status: int) -> RemoteMachineError:
    code, next_step = FAILURES.get(
        status, ("remote_start_failed", "check Docker on your GPU machine")
    )
    return RemoteMachineError(code, next_step, exit_status=status)


def checked_destination(value) -> str:
    if type(value) is not str or not DESTINATION.fullmatch(value):
        raise ValueError("an SSH destination is [user@]host or an ssh-config alias")
    return value


def _checked_port(value) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError("invalid SSH port")
    return value


def _checked_image(image_id) -> str:
    if type(image_id) is not str or not _IMAGE_ID.fullmatch(image_id):
        raise ValueError("a worker image is named by its sha256 image ID")
    return image_id


def checked_name(name) -> str:
    """A job's name: `carbon-job-<24 hex>`, for a container or a directory."""
    if type(name) is not str or not CONTAINER_NAME.fullmatch(name):
        raise ValueError("only a carbon-job-<24 hex> container is Carbon's")
    return name


def environment_lines(env: Sequence[tuple[str, str]]) -> str:
    """Shell lines that print `env` as KEY=value lines, each value plain."""
    if not env:
        raise ValueError("a job's environment carries at least its token")
    for key, value in env:
        if (
            type(key) is not str
            or type(value) is not str
            or not _ENV_NAME.fullmatch(key)
            or not _ENV_VALUE.fullmatch(value)
        ):
            raise ValueError("a worker environment value is not plain")
    return "".join(f"printf '%s\\n' {shlex.quote(f'{k}={v}')}\n" for k, v in env)


def checked_command(command: Sequence[str]) -> tuple[str, ...]:
    """A worker start command of plain arguments only."""
    if not command or not all(
        type(part) is str and _ARGUMENT.fullmatch(part) for part in command
    ):
        raise ValueError("a plain worker start command is required")
    return tuple(command)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def _stop(process) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@dataclass
class Tunnel:
    """An SSH local port forward to the machine's loopback."""

    process: object
    local_port: int

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.local_port}"

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            _stop(self.process)


class SSHClient:
    """The system `ssh` client, driven by the miner's own SSH configuration."""

    def __init__(
        self,
        destination: str,
        *,
        port: int | None = None,
        binary: str = "ssh",
        free_port: Callable[[], int] = _free_port,
        listening: Callable[[int], bool] = _listening,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.destination = checked_destination(destination)
        # None leaves the port to the miner's ssh config (an alias's Port).
        self.port = _checked_port(port)
        self.binary = binary
        self._free_port, self._listening, self._sleep = free_port, listening, sleep

    def command(self, *options: str) -> list[str]:
        """`ssh [-p P] -o BatchMode=yes ... [options] -- DEST`."""
        argv = [self.binary]
        if self.port is not None:
            argv += ["-p", str(self.port)]
        argv += [
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            "-o",
            "ServerAliveInterval=15",
            *options,
            "--",
            self.destination,
        ]
        return argv

    def run(self, script: str, *, timeout: float) -> tuple[int, bytes]:
        """Run `script` on the machine with `bash -s`: (exit status, the first
        MAX_STDOUT_BYTES of standard output). Standard error is discarded."""
        deadline = time.monotonic() + timeout
        try:
            process = subprocess.Popen(  # fixed argv, no shell
                [*self.command(), "bash", "-s"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return NO_SSH_CLIENT, b""
        try:
            try:
                process.stdin.write(script.encode())
                process.stdin.close()
            except BrokenPipeError:
                pass
            kept = _bounded_read(process.stdout, deadline)
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            _stop(process)
            return TIMED_OUT, b""
        finally:
            process.stdout.close()
        return process.returncode, kept

    def forward(self, local: int, remote: int):
        """A local port forward to the machine's loopback; a Popen to close."""
        return subprocess.Popen(  # fixed argv, no shell
            self.command(
                "-N",
                "-o",
                "ExitOnForwardFailure=yes",
                "-L",
                f"127.0.0.1:{int(local)}:127.0.0.1:{int(remote)}",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def tunnel(self, remote: int, *, attempts: int = 15) -> Tunnel:
        """Forward a free local port to `remote` on the machine's loopback."""
        local = self._free_port()
        try:
            process = self.forward(local, remote)
        except FileNotFoundError:
            raise failure_for(NO_SSH_CLIENT) from None
        for _ in range(attempts):
            if self._listening(local):
                return Tunnel(process, local)
            if process.poll() is not None:
                break
            self._sleep(1.0)
        Tunnel(process, local).close()
        raise RemoteMachineError(
            "ssh_forward_failed", "check port forwarding is allowed on your machine"
        )


def _bounded_read(stream, deadline: float) -> bytes:
    """Read `stream` to its end by `deadline`, keeping MAX_STDOUT_BYTES."""
    kept = bytearray()
    descriptor = stream.fileno()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("ssh", 0)
        ready, _, _ = select.select([descriptor], [], [], min(remaining, 1.0))
        if not ready:
            continue
        chunk = os.read(descriptor, 65536)
        if not chunk:
            return bytes(kept)
        kept += chunk[: max(0, MAX_STDOUT_BYTES - len(kept))]


def image_check_script(image_id: str) -> str:
    """Exit 0 when the machine holds `image_id`, else NO_WORKER_IMAGE."""
    image = shlex.quote(_checked_image(image_id))
    return f"""set -u
[ "$(docker image inspect --format '{{{{.Id}}}}' {image} 2>/dev/null)" = {image} ] || exit {NO_WORKER_IMAGE}
"""


def check_script(image_id: str) -> str:
    """Setup's live check: the start script's own checks, in its order, and
    nothing started. Exit 0, or the code of the first thing missing; a
    missing image (93) is what "send your worker" fixes."""
    image = shlex.quote(_checked_image(image_id))
    return f"""set -u
command -v docker >/dev/null 2>&1 || exit {NO_DOCKER}
command -v nvidia-ctk >/dev/null 2>&1 || command -v nvidia-container-cli >/dev/null 2>&1 || exit {NO_NVIDIA_TOOLKIT}
docker info >/dev/null 2>&1 || exit {NO_DOCKER_ACCESS}
[ "$(docker image inspect --format '{{{{.Id}}}}' {image} 2>/dev/null)" = {image} ] || exit {NO_WORKER_IMAGE}
exit 0
"""


def start_script(
    *,
    image_id: str,
    name: str,
    env: Sequence[tuple[str, str]],
    command: Sequence[str],
    port: int = JOB_PORT,
) -> str:
    """The script that starts one job container, by image ID, on the machine.

    It prints the container's published loopback address (`docker port`), so
    Carbon learns the host port. It installs nothing and never uses sudo.
    """
    image = shlex.quote(_checked_image(image_id))
    name = checked_name(name)
    if not 1024 <= port <= 65535:
        raise ValueError("invalid job port")
    lines = environment_lines(env)
    entry, *args = checked_command(command)
    return f"""set -eu
umask 077
command -v docker >/dev/null 2>&1 || exit {NO_DOCKER}
command -v nvidia-ctk >/dev/null 2>&1 || command -v nvidia-container-cli >/dev/null 2>&1 || exit {NO_NVIDIA_TOOLKIT}
docker info >/dev/null 2>&1 || exit {NO_DOCKER_ACCESS}
[ "$(docker image inspect --format '{{{{.Id}}}}' {image} 2>/dev/null)" = {image} ] || exit {NO_WORKER_IMAGE}
carbon_env="$(mktemp)"
trap 'rm -f "$carbon_env"' EXIT
{{
{lines}}} > "$carbon_env"
docker run -d --rm --name {name} --gpus all -p 127.0.0.1::{port} --env-file "$carbon_env" --entrypoint {shlex.quote(entry)} {image} {" ".join(map(shlex.quote, args))} >/dev/null
rm -f "$carbon_env"
docker port {name} {port}/tcp
"""


def remove_script(name: str) -> str:
    """Remove Carbon's job container `name`; exit 0 only once it is gone."""
    name = checked_name(name)
    return f"""set -u
docker rm -f {name} >/dev/null 2>&1 || true
if docker container inspect {name} >/dev/null 2>&1; then exit 1; fi
exit 0
"""


def published_port(stdout: bytes) -> int:
    """The host port `docker port` printed for the job's loopback binding."""
    found = _PUBLISHED.findall(stdout)
    if len(found) != 1 or not 1 <= int(found[0]) <= 65535:
        raise RemoteMachineError(
            "job_port_unreadable", "check `docker port` works on your machine"
        )
    return int(found[0])


def send_image(
    ssh: SSHClient, image_id: str, *, docker: str = "docker", timeout: float = 3600
) -> str:
    """Stream the pinned worker to the machine unless it holds it already.

    `docker save <id> | ssh DEST docker load`, then the image ID is checked
    on the machine. Returns "present" or "sent"; raises RemoteMachineError.
    """
    check = image_check_script(image_id)
    code, _ = ssh.run(check, timeout=60)
    if code == 0:
        return "present"
    if code != NO_WORKER_IMAGE:
        raise failure_for(code)
    deadline = time.monotonic() + timeout
    try:
        save = subprocess.Popen(  # fixed argv, no shell
            [docker, "save", image_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RemoteMachineError(
            "no_local_docker", "install Docker on this machine"
        ) from None
    try:
        load = subprocess.Popen(  # fixed argv, no shell
            [*ssh.command(), "docker", "load"],
            stdin=save.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        _stop(save)
        raise failure_for(NO_SSH_CLIENT) from None
    save.stdout.close()  # the load owns the pipe now
    try:
        load.wait(timeout=max(0.0, deadline - time.monotonic()))
        save.wait(timeout=max(1.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        _stop(load)
        _stop(save)
        raise failure_for(TIMED_OUT) from None
    if load.returncode == SSH_FAILED:
        raise failure_for(SSH_FAILED)
    if load.returncode != 0:
        raise RemoteMachineError(
            "worker_image_not_loaded",
            "check `docker load` works for your SSH user on your machine",
            exit_status=load.returncode,
        )
    if save.returncode != 0:
        raise RemoteMachineError(
            "worker_image_not_saved", "check the pinned GPU worker is built here"
        )
    code, _ = ssh.run(check, timeout=60)
    if code != 0:
        raise RemoteMachineError(
            "worker_image_not_loaded",
            "the image your machine holds is not the pinned GPU worker",
            exit_status=code,
        )
    return "sent"
