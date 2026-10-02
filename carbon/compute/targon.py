"""Targon adapter (Bittensor subnet 4): a GPU VM reached over SSH, on the
miner's own account (C-MLP-03 slice 4b, OWNER-C-MLP-03-ANSWERS-01).

Targon's current API runs no container image: its rental type is deprecated,
and its VM, bare-metal and sandbox types take no OCI image. So this route
rents a GPU **VM**, signs in over SSH with a key made for that one VM, and
runs the pinned GPU worker there with Docker. The job server listens on the
VM's loopback only, and the miner's machine reaches it through an SSH local
port forward: the job token and public inputs travel inside SSH, and no port
is opened on the VM.

Request shapes are from docs.targon.com and the API's own `/tha/v3/version`
(v3.7.0), read 2026-10-02. None has been run live by Carbon; every shape a
live run has not confirmed is marked `SHAPES_VERIFIED_LIVE = False`, and an
unparseable answer is reported as unresolved, never replaced by an estimate.

* Auth: `Authorization: Bearer <token>` (a personal or org service token).
  Everything is scoped to an organisation: `GET /tha/v3/orgs` lists the
  caller's; this adapter uses the PERSONAL one, or the only one.
* Offers: `GET /tha/v3/inventory?type=vm&gpu=true` (no key): each SKU's
  `name` (the `resource_name`), `cost_per_hour` (USD) and `available`. The
  GPU type a miner chooses is a SKU name, such as `h100-small`.
* Balance: `GET /tha/v3/orgs/{org}/credits` (`credits`, USD).
* Create is three calls: an SSH key (`POST .../ssh-keys`), a VM workload
  registered with that key, the SKU, the miner's chosen VM image and a sudo
  password (`POST .../workloads`), then `POST .../workloads/{uid}/deploy`.
  Targon documents **no idempotency key and no termination time** for a VM:
  a lost answer is recovered by the workload's name (the ownership tag), and
  the trial's own teardown is the only end.
* Reach: `GET .../workloads/{uid}/state` gives `public_ip` and `ssh_port`;
  the user is always `ubuntu`. Whether a VM image ships Docker and the NVIDIA
  Container Toolkit is **not documented**: the worker start refuses with a
  named cause when either is missing, and installs nothing.
* Teardown: `DELETE .../workloads/{uid}` (204), verified by the workload
  answering 404 or `deleted`; the VM's SSH key is then deleted too. Targon has
  no stop for a VM, so stopping is terminating.
* Charges: Targon reports **no per-workload charge**, only `cost_per_hour`
  and the account balance. `provider_charge` therefore answers None, and the
  teardown record says the charge is unresolved; Carbon never substitutes
  rate x time for the provider's figure.

**What stays on the miner's machine:** the Targon token (read per request,
only into its own header), the VM's private SSH key and sudo password (an
owner-only directory per VM, removed at teardown), and the controller. The VM
receives the pinned worker image, the job's public inputs and a per-job token.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import time
import urllib.parse
from collections.abc import Callable, Sequence
from pathlib import Path

from .credentials import CredentialProvider, CredentialUnavailable
from .errors import ComputeError, Execution
from .model import CarbonOwnedResource, Offer, PodSpec, ResourceState, ownership_name
from .provider import (
    BalanceObservation,
    CreateResult,
    ListedResource,
    Observation,
    ProviderCharge,
)
from .runpod import UrllibTransport, _refuse_non_owned

__all__ = ["TargonAdapter", "targon_state", "worker_script"]

API = "https://api.targon.com/tha/v3"
_SLUG = r"[a-z0-9][a-z0-9-]{0,62}"
_UID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SKU = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_ORG = re.escape(API) + "/orgs/" + _SLUG
_WORKLOAD = _ORG + r"/workloads/[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
ALLOWED_OPERATIONS: tuple[tuple[str, str, str], ...] = (
    ("orgs", "GET", re.escape(API) + r"/orgs"),
    ("offers", "GET", re.escape(API) + r"/inventory\?type=vm&gpu=true"),
    ("balance", "GET", _ORG + r"/credits"),
    ("images", "GET", _ORG + r"/workloads/vm-images"),
    ("ssh_key", "POST", _ORG + r"/ssh-keys"),
    ("ssh_key_delete", "DELETE", _ORG + r"/ssh-keys/[A-Za-z0-9][A-Za-z0-9_-]{0,63}"),
    ("provision", "POST", _ORG + r"/workloads"),
    ("deploy", "POST", _WORKLOAD + r"/deploy"),
    ("list", "GET", _ORG + r"/workloads\?[A-Za-z0-9=&_-]{1,256}"),
    ("status", "GET", _WORKLOAD),
    ("state", "GET", _WORKLOAD + r"/state"),
    ("terminate", "DELETE", _WORKLOAD),
)
_ALLOWED = {
    (operation, method): re.compile(pattern)
    for operation, method, pattern in ALLOWED_OPERATIONS
}
#: Nothing here has been run live; see the module docstring.
SHAPES_VERIFIED_LIVE = False
#: How a rented job on Targon is reached: an SSH local port forward.
JOB_TRANSPORT = "ssh-tunnel"
#: The VM's sign-in user (docs.targon.com/guides/virtual-machines).
SSH_USER = "ubuntu"
#: The worker container's fixed name on the VM.
CONTAINER = "carbon-job"
#: Exit codes the worker script uses for causes the miner must fix.
NO_DOCKER, NO_NVIDIA_TOOLKIT = 90, 91
#: Local outcomes of the SSH run itself.
TIMED_OUT, NO_SSH_CLIENT = 124, 127
_LIST_PAGES = 20
_ENV_VALUE = re.compile(r"^[A-Za-z0-9._:/@=+-]{0,256}$")

log = logging.getLogger("carbon.compute.targon")


def targon_state(status: object) -> ResourceState:
    """Map a Targon workload status to a provider-neutral state (conservatively)."""
    value = str(status or "").lower()
    if value == "running":
        return ResourceState.RUNNING
    if value in {"registered", "provisioning"}:
        return ResourceState.STARTING
    if value == "deleted":
        return ResourceState.TERMINATED
    return ResourceState.UNKNOWN


def _ssh_keypair() -> tuple[bytes, str]:
    """A fresh ed25519 key for one VM: (OpenSSH private key, public line)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    )
    return private, public.decode()


def worker_script(spec: PodSpec, password: str, port: int) -> str:
    """The shell script run on the VM over SSH: start the pinned worker once.

    It refuses with a named exit code when the VM has no Docker or no NVIDIA
    Container Toolkit, and installs nothing. The job server binds the VM's
    loopback only; a second run finds the container and changes nothing.
    """
    env = dict(spec.env)
    for name, value in env.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", name) or not _ENV_VALUE.fullmatch(
            value
        ):
            raise ValueError("a worker environment value is not plain")
    if not spec.start_command:
        raise ValueError("the worker start command is required")
    if not 1024 <= port <= 65535:
        raise ValueError("invalid job port")
    lines = "\n".join(f"{name}={value}" for name, value in sorted(env.items()))
    entry, *args = spec.start_command
    run = " ".join(
        [
            "run docker run -d",
            f"--name {CONTAINER}",
            "--restart no",
            "--gpus all",
            f"-p 127.0.0.1:{port}:{port}",
            '--env-file "$HOME/carbon-job.env"',
            f"--entrypoint {shlex.quote(entry)}",
            shlex.quote(spec.image),
            *map(shlex.quote, args),
        ]
    )
    return f"""set -eu
umask 077
command -v docker >/dev/null 2>&1 || exit {NO_DOCKER}
command -v nvidia-ctk >/dev/null 2>&1 || command -v nvidia-container-cli >/dev/null 2>&1 || exit {NO_NVIDIA_TOOLKIT}
CARBON_SUDO={shlex.quote(password)}
run() {{ if docker info >/dev/null 2>&1; then "$@"; else printf '%s\\n' "$CARBON_SUDO" | sudo -S -p '' "$@"; fi; }}
if [ -n "$(run docker ps -aq --filter name=^{CONTAINER}$)" ]; then exit 0; fi
cat > "$HOME/carbon-job.env" <<'CARBON_ENV'
{lines}
CARBON_ENV
run docker pull {shlex.quote(spec.image)} >/dev/null
{run} >/dev/null
"""


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


class SSH:
    """The system `ssh` client, with a per-VM key, known-hosts file and options."""

    def __init__(self, binary="ssh"):
        self.binary = binary

    def options(self, directory: Path, host: str, port: int) -> list[str]:
        return [
            self.binary,
            "-i",
            str(directory / "id_ed25519"),
            "-p",
            str(port),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"UserKnownHostsFile={directory / 'known_hosts'}",
            "-o",
            "ConnectTimeout=15",
            "-o",
            "ServerAliveInterval=15",
            f"{SSH_USER}@{host}",
        ]

    def run(self, directory, host, port, script: str, timeout: float) -> int:
        """Run `script` on the VM with `bash -s`; the exit status only.

        A run that outlasts `timeout` is 124 and a missing `ssh` client 127, so
        every outcome is a status the adapter types, never an exception that
        could skip the trial's teardown.
        """
        try:
            completed = subprocess.run(  # fixed argv, no shell
                [*self.options(directory, host, port), "bash", "-s"],
                input=script.encode(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return TIMED_OUT
        except FileNotFoundError:
            return NO_SSH_CLIENT
        return completed.returncode

    def forward(self, directory, host, port, local: int, remote: int):
        """An SSH local port forward to the VM's loopback; a Popen to close."""
        argv = self.options(directory, host, port)
        argv[1:1] = [
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            "-L",
            f"127.0.0.1:{local}:127.0.0.1:{remote}",
        ]
        return subprocess.Popen(  # fixed argv, no shell
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


class TargonAdapter:
    name = "targon"
    job_transport = JOB_TRANSPORT

    def __init__(
        self,
        credentials: CredentialProvider,
        transport=None,
        *,
        state_dir: Path,
        vm_image: str | None,
        ssh: SSH | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        listening: Callable[[int], bool] = _listening,
        free_port: Callable[[], int] = _free_port,
        verify_attempts: int = 6,
        verify_interval_s: float = 10.0,
    ) -> None:
        if vm_image is not None and not _IMAGE.fullmatch(vm_image):
            raise ValueError("invalid Targon VM image name")
        self._credentials = credentials
        self._transport = transport or UrllibTransport()
        self._state = Path(state_dir)
        self.vm_image = vm_image
        self._ssh = ssh or SSH()
        self._clock, self._sleep = clock, sleep
        self._listening, self._free_port = listening, free_port
        self._verify_attempts = verify_attempts
        self._verify_interval_s = verify_interval_s
        self._org_slug = None
        self._tunnels = {}

    # --- requests ---------------------------------------------------------------

    def _send(self, operation, method, url, body=None, *, mutating, keyed=True):
        pattern = _ALLOWED.get((operation, method))
        if pattern is None or not pattern.fullmatch(url):
            raise ComputeError(
                operation=operation,
                failed="request outside the adapter's VM-lifecycle allow-list",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="this adapter issues VM lifecycle, SSH key, balance "
                "and price requests only",
            )
        sent = {"Content-Type": "application/json", "User-Agent": "carbon-compute/1"}
        key = None
        if keyed:
            try:
                key = self._credentials.load()
            except CredentialUnavailable as missing:
                raise ComputeError(
                    operation=operation,
                    failed=f"Targon credential unavailable ({missing.status})",
                    execution=Execution.NOT_EXECUTED,
                    resources_may_remain=False,
                    retry_safe=True,
                    next_action="configure an owner-only Targon API token file",
                ) from None
            sent["Authorization"] = "Bearer " + key.reveal()
        data = None if body is None else json.dumps(body).encode()
        failure_type = None
        try:
            status, raw = self._transport(
                method, url, body=data, headers=sent, timeout=60
            )
        except Exception as failure:  # noqa: BLE001 - typed below, text dropped
            failure_type = type(failure).__name__
        finally:
            del sent, key
        if failure_type is not None:
            log.warning("targon %s transport failure (%s)", operation, failure_type)
            raise ComputeError(
                operation=operation,
                failed=f"transport failure ({failure_type})",
                execution=(
                    Execution.MAY_HAVE_EXECUTED if mutating else Execution.NOT_EXECUTED
                ),
                resources_may_remain=mutating,
                retry_safe=not mutating,
                next_action="reconcile before retrying" if mutating else "retry",
            )
        try:
            payload = json.loads(raw or b"null")
        except (ValueError, UnicodeDecodeError):
            payload = None
        return status, payload

    def _org(self):
        """The miner's PERSONAL organisation, or the only one."""
        if self._org_slug is None:
            status, payload = self._send("orgs", "GET", f"{API}/orgs", mutating=False)
            items = payload.get("items") if isinstance(payload, dict) else payload
            orgs = [
                o
                for o in (items if isinstance(items, list) else [])
                if isinstance(o, dict)
                and isinstance(o.get("slug"), str)
                and re.fullmatch(_SLUG, o["slug"])
            ]
            personal = [o for o in orgs if o.get("org_type") == "PERSONAL"]
            chosen = orgs if len(orgs) == 1 else personal
            if status != 200 or len(chosen) != 1:
                raise ComputeError(
                    operation="orgs",
                    failed="no single Targon organisation to rent in",
                    execution=Execution.EXECUTED,
                    resources_may_remain=False,
                    retry_safe=False,
                    next_action="use a token for your personal Targon organisation",
                    http_status=status,
                )
            self._org_slug = chosen[0]["slug"]
        return f"{API}/orgs/{self._org_slug}"

    # --- offers and balance ------------------------------------------------------

    def _inventory(self):
        status, payload = self._send(
            "offers",
            "GET",
            f"{API}/inventory?type=vm&gpu=true",
            mutating=False,
            keyed=False,
        )
        if status != 200 or not isinstance(payload, list):
            return []
        return [
            item
            for item in payload
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and _SKU.fullmatch(item["name"])
            and isinstance(item.get("cost_per_hour"), int | float)
            and math.isfinite(item["cost_per_hour"])
            and isinstance(item.get("spec"), dict)
        ]

    def offers(
        self, gpu_type_ids: Sequence[str], *, gpu_count: int = 1, cloud_type="SECURE"
    ) -> list[Offer]:
        inventory = {item["name"]: item for item in self._inventory()}
        found = []
        for sku in gpu_type_ids:
            item = inventory.get(sku)
            fits = item is not None and item["spec"].get("gpu_count") == gpu_count
            available = item.get("available") if fits else None
            found.append(
                Offer(
                    provider=self.name,
                    gpu_type_id=sku,
                    gpu_count=gpu_count,
                    cloud_type=cloud_type,
                    usd_per_hr=float(item["cost_per_hour"]) if fits else None,
                    stock_status=(
                        f"{available} available"
                        if isinstance(available, int) and available > 0
                        else "None"
                    ),
                    observed_at=self._clock(),
                    source="targon.inventory.cost_per_hour",
                )
            )
        return found

    def read_balance(self) -> BalanceObservation:
        status, payload = self._send(
            "balance", "GET", f"{self._org()}/credits", mutating=False
        )
        value = payload.get("credits") if isinstance(payload, dict) else None
        if status != 200 or not isinstance(value, int | float):
            raise ComputeError(
                operation="balance",
                failed="account credits unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="retry, or check the token belongs to your organisation",
                http_status=status,
            )
        return BalanceObservation(float(value), self._clock(), "targon.orgs.credits")

    def vm_images(self) -> list[str]:
        """The VM image names this account may start."""
        status, payload = self._send(
            "images", "GET", f"{self._org()}/workloads/vm-images", mutating=False
        )
        items = payload.get("items") if isinstance(payload, dict) else payload
        if status != 200 or not isinstance(items, list):
            raise ComputeError(
                operation="images",
                failed="VM image list unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="retry",
                http_status=status,
            )
        return [
            i["name"]
            for i in items
            if isinstance(i, dict) and isinstance(i.get("name"), str)
        ]

    # --- the VM's local state -----------------------------------------------------

    def _directory(self, name):
        if not re.fullmatch(r"carbon-[0-9a-f]{24}", name):
            raise ValueError("malformed ownership name")
        return self._state / name

    def _write_private(self, path, data):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)

    def _prepare(self, name, spec):
        """Owner-only key, password and worker spec for one VM, made once."""
        self._state.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = self._directory(name)
        if directory.exists():
            raise ComputeError(
                operation="provision",
                failed="this intent already prepared a VM",
                execution=Execution.MAY_HAVE_EXECUTED,
                resources_may_remain=True,
                retry_safe=False,
                next_action="reconcile by workload name; do not resend",
            )
        directory.mkdir(mode=0o700)
        private, public = _ssh_keypair()
        password = secrets.token_hex(24)
        self._write_private(directory / "id_ed25519", private)
        self._write_private(directory / "password", password.encode())
        self._write_private(
            directory / "worker.json",
            json.dumps(
                {
                    "image": spec.image,
                    "env": [list(pair) for pair in spec.env],
                    "start_command": list(spec.start_command),
                }
            ).encode(),
        )
        return public, password

    def _worker(self, directory):
        recorded = json.loads((directory / "worker.json").read_bytes())
        return PodSpec(
            image=recorded["image"],
            gpu_type_id=None,
            env=tuple(tuple(pair) for pair in recorded["env"]),
            start_command=tuple(recorded["start_command"]),
        )

    # --- lifecycle -----------------------------------------------------------------

    def create(self, spec: PodSpec, *, ownership_tag: str) -> CreateResult:
        if self.vm_image is None:
            raise ComputeError(
                operation="provision",
                failed="no Targon VM image chosen",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="choose a VM image with Docker and the NVIDIA "
                "Container Toolkit in setup",
            )
        (offer,) = self.offers([spec.gpu_type_id], gpu_count=spec.gpu_count)
        if (
            offer.usd_per_hr is None
            or offer.stock_status == "None"
            or (
                spec.max_rate_usd_per_hr is not None
                and offer.usd_per_hr > spec.max_rate_usd_per_hr
            )
        ):
            raise ComputeError(
                operation="provision",
                failed="Targon offers no VM of this type within the rate ceiling now",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="raise the ceiling, choose another VM type, or retry later",
            )
        org = self._org()
        name = ownership_name(ownership_tag)
        public, password = self._prepare(name, spec)
        status, key = self._send(
            "ssh_key",
            "POST",
            f"{org}/ssh-keys",
            {"name": name, "ssh_key": public},
            mutating=False,
        )
        key_uid = key.get("uid") if isinstance(key, dict) else None
        if status not in {200, 201} or not (
            isinstance(key_uid, str) and _UID.fullmatch(key_uid)
        ):
            shutil.rmtree(self._directory(name), ignore_errors=True)
            raise ComputeError(
                operation="provision",
                failed="SSH key refused",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="check the token may manage SSH keys",
                http_status=status,
            )
        self._write_private(self._directory(name) / "ssh_key_uid", key_uid.encode())
        status, workload = self._send(
            "provision",
            "POST",
            f"{org}/workloads",
            {
                "type": "VM",
                "name": name,
                "image": self.vm_image,
                "resource_name": spec.gpu_type_id,
                "ssh_keys": [key_uid],
                "vm_config": {"password": password},
            },
            mutating=True,
        )
        uid = workload.get("uid") if isinstance(workload, dict) else None
        if status not in {200, 201} or not (
            isinstance(uid, str) and _UID.fullmatch(uid)
        ):
            definitive = status in {400, 401, 402, 403, 404, 409, 422}
            raise ComputeError(
                operation="provision",
                failed="provider did not register the VM",
                execution=(
                    Execution.EXECUTED if definitive else Execution.MAY_HAVE_EXECUTED
                ),
                resources_may_remain=not definitive,
                retry_safe=False,
                next_action=(
                    "fix the request and use a new intent"
                    if definitive
                    else "reconcile by workload name; do not resend"
                ),
                http_status=status,
            )
        status, deployed = self._send(
            "deploy", "POST", f"{org}/workloads/{uid}/deploy", mutating=True
        )
        if status not in {200, 201, 202}:
            definitive = status in {400, 401, 402, 403, 404, 409, 422}
            if definitive:
                # Registered but refused: remove the registration so nothing
                # remains under this name.
                self._send(
                    "terminate", "DELETE", f"{org}/workloads/{uid}", mutating=True
                )
            raise ComputeError(
                operation="provision",
                failed="provider did not deploy the VM",
                execution=(
                    Execution.EXECUTED if definitive else Execution.MAY_HAVE_EXECUTED
                ),
                resources_may_remain=not definitive,
                retry_safe=False,
                next_action=(
                    "check credits and stock, then use a new intent"
                    if definitive
                    else "reconcile by workload name; do not resend"
                ),
                http_status=status,
            )
        rate = deployed.get("cost_per_hour") if isinstance(deployed, dict) else None
        return CreateResult(
            uid, float(rate) if isinstance(rate, int | float) else offer.usd_per_hr
        )

    def _workload(self, resource_id):
        if not _UID.fullmatch(resource_id):
            raise ValueError("invalid workload id")
        return self._send(
            "status", "GET", f"{self._org()}/workloads/{resource_id}", mutating=False
        )

    def observe(self, resource_id: str) -> Observation:
        status, payload = self._workload(resource_id)
        now = self._clock()
        state = payload.get("state") if isinstance(payload, dict) else None
        value = state.get("status") if isinstance(state, dict) else None
        if status == 404 or (status == 200 and value == "deleted"):
            return Observation(
                resource_id, False, ResourceState.TERMINATED, None, None, now
            )
        if status != 200 or not isinstance(payload, dict):
            raise ComputeError(
                operation="status",
                failed="workload status unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=True,
                retry_safe=True,
                next_action="retry status",
                http_status=status,
            )
        rate = payload.get("cost_per_hour")
        return Observation(
            resource_id,
            True,
            targon_state(value),
            payload.get("name"),
            float(rate) if isinstance(rate, int | float) else None,
            now,
        )

    def list_resources(self) -> list[ListedResource]:
        found, cursor = [], None
        for _ in range(_LIST_PAGES):
            query = {"type": "VM", "limit": "1000"}
            if cursor:
                query["cursor"] = cursor
            status, payload = self._send(
                "list",
                "GET",
                f"{self._org()}/workloads?{urllib.parse.urlencode(query)}",
                mutating=False,
            )
            items = payload.get("items") if isinstance(payload, dict) else None
            if status != 200 or not isinstance(items, list):
                raise ComputeError(
                    operation="list",
                    failed="workload list unreadable",
                    execution=Execution.EXECUTED,
                    resources_may_remain=True,
                    retry_safe=True,
                    next_action="retry reconcile",
                    http_status=status,
                )
            found += [
                ListedResource(item["uid"], item.get("name"))
                for item in items
                if isinstance(item, dict)
                and isinstance(item.get("uid"), str)
                and _UID.fullmatch(item["uid"])
                and (item.get("state") or {}).get("status") != "deleted"
            ]
            cursor = payload.get("next_cursor")
            if not (isinstance(cursor, str) and _UID.fullmatch(cursor)):
                return found
        raise ComputeError(
            operation="list",
            failed="workload list longer than this adapter reads",
            execution=Execution.EXECUTED,
            resources_may_remain=True,
            retry_safe=False,
            next_action="check the account's workloads in Targon's console",
        )

    def _confirm_ownership(self, owned, operation):
        seen = self.observe(owned.resource_id)
        if not seen.present:
            return False
        if seen.name != owned.expected_name:
            raise ComputeError(
                operation=operation,
                failed="live resource does not carry this intent's ownership tag",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=True,
                retry_safe=False,
                next_action="investigate; Carbon never acts on an untagged resource",
            )
        return True

    def stop(self, owned: CarbonOwnedResource) -> None:
        # Targon has no stop for a VM; stopping is terminating.
        self.terminate(owned)

    def terminate(self, owned: CarbonOwnedResource) -> bool:
        owned = _refuse_non_owned(owned, "terminate")
        self._close_tunnel(owned.resource_id)
        if self._confirm_ownership(owned, "terminate"):
            for attempt in range(self._verify_attempts):
                self._send(
                    "terminate",
                    "DELETE",
                    f"{self._org()}/workloads/{owned.resource_id}",
                    mutating=True,
                )
                if not self.observe(owned.resource_id).present:
                    break
                if attempt + 1 < self._verify_attempts:
                    self._sleep(self._verify_interval_s)
            else:
                raise ComputeError(
                    operation="terminate",
                    failed="deletion not verified",
                    execution=Execution.MAY_HAVE_EXECUTED,
                    resources_may_remain=True,
                    retry_safe=True,
                    next_action="run the compute reconciler again",
                )
        self._forget(owned.expected_name)
        return True

    def _forget(self, name):
        """Delete the VM's SSH key at Targon, then its local key material."""
        directory = self._directory(name)
        recorded = directory / "ssh_key_uid"
        if recorded.exists():
            key_uid = recorded.read_text()
            if _UID.fullmatch(key_uid):
                try:
                    self._send(
                        "ssh_key_delete",
                        "DELETE",
                        f"{self._org()}/ssh-keys/{key_uid}",
                        mutating=False,
                    )
                except ComputeError:
                    pass  # An unused key costs nothing; the VM is gone.
        shutil.rmtree(directory, ignore_errors=True)

    # --- reaching the job ------------------------------------------------------------

    def _close_tunnel(self, resource_id):
        tunnel = self._tunnels.pop(resource_id, None)
        if tunnel is not None:
            process, _ = tunnel
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    def _not_ready(self, failed, *, retry_safe=True, next_action=None, status=None):
        return ComputeError(
            operation="connect",
            failed=failed,
            execution=Execution.NOT_EXECUTED,
            resources_may_remain=True,
            retry_safe=retry_safe,
            next_action=next_action or "wait for the VM to become ready",
            http_status=status,
        )

    def connect_url(self, owned: CarbonOwnedResource, port: int) -> str:
        """Start the worker on the VM over SSH (once), then forward its port."""
        owned = _refuse_non_owned(owned, "connect")
        tunnel = self._tunnels.get(owned.resource_id)
        if tunnel is not None and tunnel[0].poll() is None:
            return f"http://127.0.0.1:{tunnel[1]}"
        self._close_tunnel(owned.resource_id)
        status, state = self._send(
            "state",
            "GET",
            f"{self._org()}/workloads/{owned.resource_id}/state",
            mutating=False,
        )
        value = state.get("status") if isinstance(state, dict) else None
        if value in {"error", "deleted"}:
            raise self._not_ready(
                f"the VM is {value}",
                retry_safe=False,
                next_action="the trial's teardown removes it; try another VM type",
                status=status,
            )
        host = state.get("public_ip") if isinstance(state, dict) else None
        ssh_port = state.get("ssh_port") if isinstance(state, dict) else None
        if (
            status != 200
            or value != "running"
            or not isinstance(host, str)
            or not re.fullmatch(r"[0-9A-Fa-f.:]{2,45}", host)
            or type(ssh_port) is not int
            or not 1 <= ssh_port <= 65535
        ):
            raise self._not_ready("the VM is not running yet", status=status)
        directory = self._directory(owned.expected_name)
        password = (directory / "password").read_text()
        code = self._ssh.run(
            directory,
            host,
            ssh_port,
            worker_script(self._worker(directory), password, port),
            timeout=1200,
        )
        if code == NO_DOCKER:
            raise self._not_ready(
                "the VM image has no Docker",
                retry_safe=False,
                next_action="choose a Targon VM image with Docker and the NVIDIA "
                "Container Toolkit",
            )
        if code == NO_NVIDIA_TOOLKIT:
            raise self._not_ready(
                "the VM image has no NVIDIA Container Toolkit",
                retry_safe=False,
                next_action="choose a Targon VM image with Docker and the NVIDIA "
                "Container Toolkit",
            )
        if code in (TIMED_OUT, NO_SSH_CLIENT):
            raise self._not_ready(
                (
                    "the worker did not start within the time allowed"
                    if code == TIMED_OUT
                    else "this machine has no ssh client"
                ),
                retry_safe=False,
                next_action=(
                    "retry the trial; the VM is deleted by its teardown"
                    if code == TIMED_OUT
                    else "install an OpenSSH client"
                ),
            )
        if code != 0:
            # 255 is SSH itself: the VM's sshd may not be up yet.
            raise self._not_ready(f"the worker did not start over SSH ({code})")
        local = self._free_port()
        try:
            process = self._ssh.forward(directory, host, ssh_port, local, port)
        except OSError:
            raise self._not_ready(
                "this machine has no ssh client",
                retry_safe=False,
                next_action="install an OpenSSH client",
            ) from None
        for _ in range(15):
            if self._listening(local):
                self._tunnels[owned.resource_id] = (process, local)
                return f"http://127.0.0.1:{local}"
            if process.poll() is not None:
                break
            self._sleep(1.0)
        process.terminate()
        raise self._not_ready("the SSH port forward did not open")

    def provider_charge(self, owned: CarbonOwnedResource) -> ProviderCharge | None:
        # Targon reports no per-workload charge (only cost_per_hour and the
        # account's credits), so there is no provider figure to read.
        _refuse_non_owned(owned, "charges")
        return None
