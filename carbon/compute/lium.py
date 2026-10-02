"""Lium adapter (Bittensor subnet 51), on the miner's own account.

Request shapes are from Lium's live OpenAPI (https://lium.io/api/openapi.json,
"Lium Backend API 1.0.0") and docs.lium.io, read 2026-10-02. None has been run
live by Carbon; every shape a live run has not confirmed is marked
`*_VERIFIED_LIVE = False` and an unparseable answer is reported as unresolved,
never replaced by an estimate.

* Auth: `X-API-Key: <key>`. A Lium key can be scoped (`read`, `rent`,
  `manage`, `billing`) and budgeted (daily, monthly or total USD, enforced by
  Lium); a miner should give this adapter a key with `read`, `rent` and
  `manage`, and may give it `billing` so charges are read.
* Offers: `GET /executors?machine_names=<gpu>` lists unrented nodes with
  `price_per_gpu` (USD per GPU-hour).
* Create is two calls: a one-time template (`POST /templates`: the image by
  digest, its environment, the start command, the job port), then a rent
  (`POST /executors/{id}/rent`: the pod name, a throwaway SSH public key Lium
  requires, one GPU, a termination time). The rent carries an
  `Idempotency-Key` (honoured 24 h); a lost answer is recovered by pod name.
* Reach: `ports_mapping` maps the job port to a port on the node's IP. **Lium
  documents no managed HTTPS proxy**, so a rented job on Lium is reached over
  plain HTTP; its token and public inputs cross unencrypted, and the backend
  record says so. Nothing secret is on the pod.
* Teardown: `DELETE /pods/{id}`, verified by `GET /pods/{id}` answering 404.
  Lium has no stop endpoint.
* Balance: `GET /users/me` (`balance`). Charges: `GET /pods/{id}/statement`
  (`total`, the ledger's own figure; it answers after removal).
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
import urllib.parse
from collections.abc import Callable, Sequence

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

__all__ = ["LiumAdapter", "lium_state"]

API = "https://lium.io/api"
_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_GPU = re.compile(r"^[A-Za-z0-9 ._-]{1,64}$")
_POD = API + r"/pods/[A-Za-z0-9-]{1,64}"
ALLOWED_OPERATIONS: tuple[tuple[str, str, str], ...] = (
    ("offers", "GET", re.escape(API) + r"/executors\?[A-Za-z0-9=&%+._-]{1,512}"),
    ("balance", "GET", re.escape(API) + r"/users/me"),
    ("template", "POST", re.escape(API) + r"/templates"),
    ("provision", "POST", re.escape(API) + r"/executors/[A-Za-z0-9-]{1,64}/rent"),
    ("list", "GET", re.escape(API) + r"/pods"),
    ("status", "GET", re.escape(API) + _POD[len(API) :]),
    ("terminate", "DELETE", re.escape(API) + _POD[len(API) :]),
    ("charges", "GET", re.escape(API) + _POD[len(API) :] + "/statement"),
)
_ALLOWED = {
    (operation, method): re.compile(pattern)
    for operation, method, pattern in ALLOWED_OPERATIONS
}
#: Nothing here has been run live; see the module docstring.
SHAPES_VERIFIED_LIVE = False
#: How a rented job on Lium is reached: the node's IP, plain HTTP.
JOB_TRANSPORT = "http-direct"

log = logging.getLogger("carbon.compute.lium")


def lium_state(status: object) -> ResourceState:
    """Map a Lium pod status to a provider-neutral state (conservatively)."""
    value = str(status or "").upper()
    if value == "RUNNING":
        return ResourceState.RUNNING
    if value in {"PENDING", "START_PENDING", "REBOOT_PENDING"}:
        return ResourceState.STARTING
    if value in {"STOPPED", "STOP_PENDING"}:
        return ResourceState.STOPPED
    if value == "DELETING":
        return ResourceState.TERMINATING
    return ResourceState.UNKNOWN


def throwaway_public_key() -> str:
    """An SSH public key Lium's rent requires; its private half is discarded,
    so nobody can sign in with it. Carbon never uses SSH."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    public = Ed25519PrivateKey.generate().public_key()
    return public.public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    ).decode()


class LiumAdapter:
    name = "lium"
    job_transport = JOB_TRANSPORT

    def __init__(
        self,
        credentials: CredentialProvider,
        transport=None,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        verify_attempts: int = 6,
        verify_interval_s: float = 10.0,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or UrllibTransport()
        self._clock, self._sleep = clock, sleep
        self._verify_attempts = verify_attempts
        self._verify_interval_s = verify_interval_s

    def _send(self, operation, method, url, body=None, *, mutating, headers=None):
        pattern = _ALLOWED.get((operation, method))
        if pattern is None or not pattern.fullmatch(url):
            raise ComputeError(
                operation=operation,
                failed="request outside the adapter's pod-lifecycle allow-list",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="this adapter issues pod lifecycle, balance and "
                "price requests only",
            )
        try:
            key = self._credentials.load()
        except CredentialUnavailable as missing:
            raise ComputeError(
                operation=operation,
                failed=f"Lium credential unavailable ({missing.status})",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="configure an owner-only Lium API key file",
            ) from None
        sent = {
            "X-API-Key": key.reveal(),
            "Content-Type": "application/json",
            "User-Agent": "carbon-compute/1",
            **(headers or {}),
        }
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
            log.warning("lium %s transport failure (%s)", operation, failure_type)
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

    def _executors(self, gpu, gpu_count):
        if not _GPU.fullmatch(gpu) or not 1 <= gpu_count <= 16:
            raise ValueError("invalid GPU offer query")
        query = urllib.parse.urlencode(
            {"machine_names": gpu, "gpu_count_gte": gpu_count, "view": "summary"}
        )
        status, payload = self._send(
            "offers", "GET", f"{API}/executors?{query}", mutating=False
        )
        if status != 200 or not isinstance(payload, list):
            return []
        return [
            item
            for item in payload
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and _ID.fullmatch(item["id"])
            and isinstance(item.get("price_per_gpu"), int | float)
            and math.isfinite(item["price_per_gpu"])
            and (item.get("available_gpu_count") or 0) >= gpu_count
            and (item.get("min_gpu_count_for_rental") or 1) <= gpu_count
        ]

    def offers(
        self, gpu_type_ids: Sequence[str], *, gpu_count: int = 1, cloud_type="SECURE"
    ) -> list[Offer]:
        found = []
        for gpu in gpu_type_ids:
            nodes = self._executors(gpu, gpu_count)
            cheapest = min((n["price_per_gpu"] for n in nodes), default=None)
            found.append(
                Offer(
                    provider=self.name,
                    gpu_type_id=gpu,
                    gpu_count=gpu_count,
                    cloud_type=cloud_type,
                    usd_per_hr=None if cheapest is None else cheapest * gpu_count,
                    stock_status=f"{len(nodes)} nodes" if nodes else "None",
                    observed_at=self._clock(),
                    source="lium.executors.price_per_gpu",
                )
            )
        return found

    def read_balance(self) -> BalanceObservation:
        status, payload = self._send(
            "balance", "GET", f"{API}/users/me", mutating=False
        )
        value = payload.get("balance") if isinstance(payload, dict) else None
        if status != 200 or not isinstance(value, int | float):
            raise ComputeError(
                operation="balance",
                failed="account balance unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="retry, or check the key has the read scope",
                http_status=status,
            )
        return BalanceObservation(float(value), self._clock(), "lium.users.me")

    def template_body(self, spec: PodSpec, ownership_tag: str) -> dict:
        repository, digest = spec.image.split("@", 1)
        env = dict(spec.env)
        env["CARBON_OWNERSHIP_TAG"] = ownership_tag
        ports = sorted({int(port.split("/", 1)[0]) for port in spec.ports})
        return {
            "name": ownership_name(ownership_tag),
            "docker_image": repository,
            "docker_image_digest": digest,
            "environment": env,
            "entrypoint": " ".join(spec.start_command),
            "internal_ports": ports,
            "one_time_template": True,
            "is_private": True,
        }

    def create(self, spec: PodSpec, *, ownership_tag: str) -> CreateResult:
        nodes = [
            n
            for n in self._executors(spec.gpu_type_id, spec.gpu_count)
            if spec.max_rate_usd_per_hr is None
            or n["price_per_gpu"] * spec.gpu_count <= spec.max_rate_usd_per_hr
        ]
        if not nodes:
            raise ComputeError(
                operation="provision",
                failed="no Lium node offers this GPU within the rate ceiling now",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="raise the ceiling, choose another GPU, or retry later",
            )
        node = min(nodes, key=lambda n: n["price_per_gpu"])
        status, template = self._send(
            "template",
            "POST",
            f"{API}/templates",
            self.template_body(spec, ownership_tag),
            mutating=False,
        )
        template_id = template.get("id") if isinstance(template, dict) else None
        if status not in {200, 201} or not isinstance(template_id, str):
            raise ComputeError(
                operation="provision",
                failed="template refused",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="check the image reference and the key's rent scope",
                http_status=status,
            )
        status, payload = self._send(
            "provision",
            "POST",
            f"{API}/executors/{node['id']}/rent",
            {
                "pod_name": ownership_name(ownership_tag),
                "user_public_key": throwaway_public_key(),
                "template_id": template_id,
                "gpu_count": spec.gpu_count,
                "termination_hours": 2,
                "initial_port_count": len(spec.ports),
            },
            mutating=True,
            headers={"Idempotency-Key": ownership_tag},
        )
        pod_id = None
        if isinstance(payload, dict):
            pod_id = payload.get("id") or payload.get("pod_id")
        if status in {200, 201} and isinstance(pod_id, str) and _ID.fullmatch(pod_id):
            return CreateResult(pod_id, float(node["price_per_gpu"]) * spec.gpu_count)
        definitive = status in {400, 401, 402, 403, 404, 422}
        raise ComputeError(
            operation="provision",
            failed="provider did not return a pod id",
            execution=Execution.EXECUTED if definitive else Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=not definitive,
            retry_safe=False,
            next_action=(
                "fix the request and use a new intent"
                if definitive
                else "reconcile by pod name; do not resend"
            ),
            http_status=status,
        )

    def _pod(self, resource_id):
        if not _ID.fullmatch(resource_id):
            raise ValueError("invalid pod id")
        return self._send("status", "GET", f"{API}/pods/{resource_id}", mutating=False)

    def observe(self, resource_id: str) -> Observation:
        status, payload = self._pod(resource_id)
        now = self._clock()
        if status == 404:
            return Observation(
                resource_id, False, ResourceState.TERMINATED, None, None, now
            )
        if status != 200 or not isinstance(payload, dict):
            raise ComputeError(
                operation="status",
                failed="pod status unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=True,
                retry_safe=True,
                next_action="retry status",
                http_status=status,
            )
        price = payload.get("price")
        return Observation(
            resource_id,
            True,
            lium_state(payload.get("status")),
            payload.get("pod_name"),
            float(price) if isinstance(price, int | float) else None,
            now,
        )

    def list_resources(self) -> list[ListedResource]:
        status, payload = self._send("list", "GET", f"{API}/pods", mutating=False)
        if status != 200 or not isinstance(payload, list):
            raise ComputeError(
                operation="list",
                failed="pod list unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=True,
                retry_safe=True,
                next_action="retry reconcile",
                http_status=status,
            )
        return [
            ListedResource(str(item["id"]), item.get("pod_name"))
            for item in payload
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

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
        # Lium has no stop: a pod runs until it is deleted or its termination
        # time passes. Stopping is therefore terminating.
        self.terminate(owned)

    def terminate(self, owned: CarbonOwnedResource) -> bool:
        owned = _refuse_non_owned(owned, "terminate")
        if not self._confirm_ownership(owned, "terminate"):
            return True
        for attempt in range(self._verify_attempts):
            self._send(
                "terminate",
                "DELETE",
                f"{API}/pods/{owned.resource_id}",
                mutating=True,
            )
            if not self.observe(owned.resource_id).present:
                return True
            if attempt + 1 < self._verify_attempts:
                self._sleep(self._verify_interval_s)
        raise ComputeError(
            operation="terminate",
            failed="deletion not verified",
            execution=Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=True,
            retry_safe=True,
            next_action="run the compute reconciler again",
        )

    def connect_url(self, owned: CarbonOwnedResource, port: int) -> str:
        owned = _refuse_non_owned(owned, "connect")
        status, payload = self._pod(owned.resource_id)
        mapping = payload.get("ports_mapping") if isinstance(payload, dict) else None
        executor = payload.get("executor") if isinstance(payload, dict) else None
        host = (
            executor.get("executor_ip_address") if isinstance(executor, dict) else None
        )
        external = mapping.get(str(port)) if isinstance(mapping, dict) else None
        if (
            status != 200
            or not isinstance(host, str)
            or not re.fullmatch(r"[0-9A-Za-z.:-]{1,64}", host)
            or not isinstance(external, int | str)
            or not str(external).isdigit()
        ):
            raise ComputeError(
                operation="connect",
                failed="the job port is not mapped yet",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=True,
                retry_safe=True,
                next_action="wait for the pod to become ready",
                http_status=status,
            )
        return f"http://{host}:{int(external)}"

    def provider_charge(self, owned: CarbonOwnedResource) -> ProviderCharge | None:
        owned = _refuse_non_owned(owned, "charges")
        status, payload = self._send(
            "charges",
            "GET",
            f"{API}/pods/{owned.resource_id}/statement",
            mutating=False,
        )
        total = payload.get("total") if isinstance(payload, dict) else None
        if status != 200 or not isinstance(total, int | float):
            return None
        return ProviderCharge(
            float(total),
            "lium.pods.statement"
            + ("" if SHAPES_VERIFIED_LIVE else ".unverified_shape"),
        )
