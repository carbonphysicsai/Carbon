"""The miner's remote setup: one interface over every transport (LINKONLY-D5).

OWNER-MINER-COMPUTE-LINK-ONLY-01, as amended on 2026-10-02: "miners should be
able to use whatever they want to run their setup. We are just facilitating
and providing wiring and tooling." The miner runs the machine or container;
Carbon never starts, stops or bills it. The miner names how Carbon reaches it:

- `ssh-docker`: a machine with Docker and the NVIDIA Container Toolkit. One
  job container per trial, by the pinned worker's image ID
  (`remote_machine`).
- `ssh-container`: a container the miner started from the pinned worker image,
  with no Docker inside. One job server process per trial, its build identity
  checked first (`remote_container`).
- `endpoint`: a job endpoint the miner exposes. Designed and not built
  (LINKONLY-D7): today's job server serves one job per process with a token
  set when it starts, so an endpoint would need a long-lived job door with a
  standing secret, reachable from the internet. That is the owner's security
  call; until then it is refused by name.

Every transport has the same interface, and every trial records the same
fields (`describe` and `outcome`): the transport, the pinned worker's image
identity, how that identity was verified, the job transport, and whether the
cleanup was confirmed. The job always travels inside the miner's SSH, through
a forward to where the job listens: the container's loopback (`ssh-container`)
or the job container's address on its private network (`ssh-docker`).

Isolation differs, and is stated, never implied (RSURF-D20 review,
2026-10-03): an `ssh-docker` job runs in a hardened container
(`remote_machine.start_script`). An `ssh-container` job runs inside the
miner's own container with no sandbox and whatever network that container
has, so the GPU code cell, which runs agent-written code, runs there only
when the miner opted in, in their own runner profile
(`unsandboxed_code_cell: true`). Carbon's fixed practice program needs no
opt-in.

`RemoteMachine` is where the setup is: the miner's choice, kept in their own
runner profile and never in a campaign record (LINKONLY-D9).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import remote_container
from .remote_machine import (
    JOB_PORT,
    NO_WORKER_IMAGE,
    JobEndpoint,
    RemoteMachineError,
    SSHClient,
    check_script,
    checked_destination,
    failure_for,
    job_endpoint,
    remove_script,
    send_image,
    start_script,
)

__all__ = [
    "BUILT",
    "ENDPOINT",
    "ENDPOINT_NOT_BUILT",
    "JOB_TRANSPORT",
    "SSH_CONTAINER",
    "SSH_DOCKER",
    "TRANSPORTS",
    "RemoteMachine",
    "RemoteTransport",
    "SSHContainer",
    "SSHDocker",
    "outcome",
    "transport_for",
]

SSH_DOCKER, SSH_CONTAINER, ENDPOINT = "ssh-docker", "ssh-container", "endpoint"
TRANSPORTS = (SSH_DOCKER, SSH_CONTAINER, ENDPOINT)
#: The transports Carbon can run today.
BUILT = (SSH_DOCKER, SSH_CONTAINER)
#: How the pinned worker's identity was verified on the machine.
IMAGE_ID, BUILD_IDENTITY = "image-id", "build-identity"
#: How the controller reaches the job: an SSH local port forward.
JOB_TRANSPORT = "ssh-tunnel"
ENDPOINT_NOT_BUILT = "endpoint_transport_not_built"
ENDPOINT_NEXT_STEP = (
    "use ssh-container: start your container from the pinned GPU worker image "
    "with SSH into it, and give setup its SSH destination"
)
#: How long a live check may take.
CHECK_SECONDS = 60


def endpoint_refused() -> RemoteMachineError:
    return RemoteMachineError(ENDPOINT_NOT_BUILT, ENDPOINT_NEXT_STEP)


@dataclass(frozen=True)
class RemoteMachine:
    """Where the miner's remote setup is, and how Carbon reaches it."""

    transport: str
    destination: str
    port: int | None = None
    #: The miner's own opt-in to running the GPU code cell (agent-written
    #: code) inside their container with no sandbox and its network
    #: (`ssh-container` only). Absent means no.
    unsandboxed_code_cell: bool = False

    def __post_init__(self):
        if self.transport == ENDPOINT:
            raise endpoint_refused()
        if self.transport not in BUILT:
            raise ValueError("a remote transport is ssh-docker or ssh-container")
        checked_destination(self.destination)
        if self.port is not None and (
            type(self.port) is not int or not 1 <= self.port <= 65535
        ):
            raise ValueError("invalid SSH port")
        if type(self.unsandboxed_code_cell) is not bool or (
            self.unsandboxed_code_cell and self.transport != SSH_CONTAINER
        ):
            raise ValueError(
                "unsandboxed_code_cell is an ssh-container opt-in: true or absent"
            )

    @classmethod
    def from_document(cls, value) -> RemoteMachine:
        """The profile's `remote_machine`, closed and checked."""
        if type(value) is not dict:
            raise ValueError("remote_machine is a transport and a destination")
        if value.get("transport") == ENDPOINT:
            raise endpoint_refused()
        if not {"transport", "destination"} <= set(value) or not set(value) <= {
            "transport",
            "destination",
            "port",
            "unsandboxed_code_cell",
        }:
            raise ValueError("remote_machine is a transport and a destination")
        if value.get("unsandboxed_code_cell", True) is not True:
            raise ValueError(
                "unsandboxed_code_cell is an ssh-container opt-in: true or absent"
            )
        return cls(
            value["transport"],
            value["destination"],
            value.get("port"),
            "unsandboxed_code_cell" in value,
        )

    def document(self) -> dict:
        found = {"transport": self.transport, "destination": self.destination}
        if self.port is not None:
            found["port"] = self.port
        if self.unsandboxed_code_cell:
            found["unsandboxed_code_cell"] = True
        return found


def outcome(described: dict, cleaned: bool) -> dict:
    """The one result record: `describe` plus whether cleanup was confirmed."""
    return {**described, "cleanup": "confirmed" if cleaned else "unconfirmed"}


class RemoteTransport:
    """How Carbon reaches a remote setup and runs one job there.

    `ssh` is a `remote_machine.SSHClient`, or a double with its `run` and
    `tunnel`. Every method that touches the machine raises
    `RemoteMachineError`, except `cleanup`, which answers whether the machine
    confirmed it and never raises.
    """

    name: str = ""
    image_verified_by: str = ""
    job_transport: str = JOB_TRANSPORT
    #: What a trial leaves on the machine and cleanup removes.
    cleans: str = ""
    #: Whether the job runs in a hardened container Carbon starts. Not unless
    #: a transport says so.
    sandboxed: bool = False
    #: The miner's opt-in to agent-written code with no sandbox; only a
    #: transport with no sandbox can carry it.
    unsandboxed_code_cell: bool = False

    def __init__(self, ssh):
        self.ssh = ssh

    def describe(self, image) -> dict:
        """What every trial on this transport records, before anything runs."""
        return {
            "transport": self.name,
            "image": image.image_id,
            "image_verified_by": self.image_verified_by,
            "job_transport": self.job_transport,
        }

    def check(self, image) -> dict:
        """Setup's live check: reach the setup and check what a trial needs,
        starting nothing. Public facts only."""
        raise NotImplementedError

    def verify(self, image) -> None:
        """Before each trial: the setup holds the pinned worker."""
        raise NotImplementedError

    def start(self, name, image, env, command, *, timeout) -> JobEndpoint:
        """Start one job; where it listens, as the machine sees it."""
        raise NotImplementedError

    def tunnel(self, endpoint: JobEndpoint):
        """The SSH forward to a started job's endpoint."""
        if type(endpoint) is not JobEndpoint:
            raise ValueError("a tunnel targets a started job's endpoint")
        return self.ssh.tunnel(endpoint.port, host=endpoint.host)

    def cleanup(self, name) -> bool:
        """Remove what the trial left; True only once the machine confirms."""
        raise NotImplementedError

    def _started(self, script, timeout) -> JobEndpoint:
        code, stdout = self.ssh.run(script, timeout=timeout)
        if code != 0:
            raise failure_for(code)
        return job_endpoint(stdout)

    def _cleaned(self, script) -> bool:
        try:
            code, _ = self.ssh.run(script, timeout=120)
        except OSError:
            return False
        return code == 0


class SSHDocker(RemoteTransport):
    """A machine with Docker and the NVIDIA Container Toolkit (LINKONLY-D4)."""

    name = SSH_DOCKER
    image_verified_by = IMAGE_ID
    cleans = "job-container"
    sandboxed = True

    def check(self, image) -> dict:
        code, _ = self.ssh.run(check_script(image.image_id), timeout=CHECK_SECONDS)
        if code not in (0, NO_WORKER_IMAGE):
            raise failure_for(code)
        return {
            "transport": self.name,
            "reached": True,
            "docker": "usable without sudo",
            "nvidia_container_toolkit": "present",
            "worker_image": "present" if code == 0 else "missing",
            "image_verified_by": self.image_verified_by,
        }

    def verify(self, image) -> None:
        # The start script itself refuses an image not present by ID (93).
        return None

    def send(self, image) -> str:
        """Stream the pinned worker to the machine: "present" or "sent"."""
        return send_image(self.ssh, image.image_id)

    def start(self, name, image, env, command, *, timeout) -> JobEndpoint:
        script = start_script(
            image_id=image.image_id,
            name=name,
            env=(*env, ("CARBON_JOB_PORT", str(JOB_PORT))),
            command=command,
        )
        endpoint = self._started(script, timeout)
        # The job container's address on its own private network, never the
        # machine's loopback: no port is published on the machine.
        if endpoint.port != JOB_PORT or endpoint.host.startswith("127."):
            raise RemoteMachineError(
                "job_port_unreadable", "check `docker inspect` works on your machine"
            )
        return endpoint

    def cleanup(self, name) -> bool:
        return self._cleaned(remove_script(name))


class SSHContainer(RemoteTransport):
    """A container the miner started from the pinned worker, with no Docker
    inside (the owner's amendment, LINKONLY-D5 and D6)."""

    name = SSH_CONTAINER
    image_verified_by = BUILD_IDENTITY
    cleans = "job-process"
    #: No sandbox: the job is a process in the miner's container, with that
    #: container's network.
    sandboxed = False

    def __init__(
        self,
        ssh,
        *,
        python: str = remote_container.WORKER_PYTHON,
        build_file: str = remote_container.BUILD_FILE,
        root: str = remote_container.JOB_ROOT,
        unsandboxed_code_cell: bool = False,
    ):
        super().__init__(ssh)
        self.python, self.build_file, self.root = python, build_file, root
        if type(unsandboxed_code_cell) is not bool:
            raise ValueError("unsandboxed_code_cell is the miner's true or false")
        self.unsandboxed_code_cell = unsandboxed_code_cell

    def _identity(self, image) -> None:
        script = remote_container.identity_script(
            python=self.python, build_file=self.build_file
        )
        code, stdout = self.ssh.run(script, timeout=CHECK_SECONDS)
        if code != 0:
            raise failure_for(code)
        remote_container.checked_identity(stdout, image)

    def check(self, image) -> dict:
        self._identity(image)
        return {
            "transport": self.name,
            "reached": True,
            "worker_runtime": "present",
            "build_identity": "matches the pinned GPU worker",
            "image_verified_by": self.image_verified_by,
        }

    def verify(self, image) -> None:
        self._identity(image)

    def start(self, name, image, env, command, *, timeout) -> JobEndpoint:
        script = remote_container.start_script(
            name=name, env=env, command=command, root=self.root
        )
        endpoint = self._started(script, timeout)
        # A process in the miner's container listens on its loopback only.
        if endpoint.host != "127.0.0.1":
            raise RemoteMachineError(
                "job_port_unreadable", "check your container can run the worker"
            )
        return endpoint

    def cleanup(self, name) -> bool:
        return self._cleaned(remote_container.stop_script(name, root=self.root))


def transport_for(machine: RemoteMachine, *, ssh=SSHClient) -> RemoteTransport:
    """The transport for the miner's `machine`, over their own SSH."""
    client = ssh(machine.destination, port=machine.port)
    if machine.transport == SSH_DOCKER:
        return SSHDocker(client)
    if machine.transport == SSH_CONTAINER:
        return SSHContainer(client, unsandboxed_code_cell=machine.unsandboxed_code_cell)
    raise endpoint_refused()
