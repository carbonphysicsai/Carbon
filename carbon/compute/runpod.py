"""RunPod adapter.

Request shapes are taken from the operator script
``scripts/dev/exam_design/runpod/pod_control.py``, which exercised them against
the live API: REST ``POST/GET/DELETE https://rest.runpod.io/v1/pods`` and the
GraphQL ``gpuTypes { lowestPrice { uninterruptablePrice stockStatus } }``
price/stock query. Two shapes were *not* exercised by that script and are
marked where used: ``POST /pods/{id}/stop`` and the pod billing read. Neither is
evidence until a bounded live run confirms it; an unparseable billing answer is
reported as unresolved, never replaced by an estimate.

The adapter never sees a raw key: it asks a credential provider per request and
places the value only in the ``Authorization`` header handed to the transport.
Provider bodies and transport exception text are never copied into errors or
logs, because either can echo the request.

Key scope. Every request passes through one allow-list,
:data:`ALLOWED_OPERATIONS`, and anything else is refused before the credential
is loaded. The adapter therefore needs exactly:

* pod lifecycle (write): ``POST /v1/pods`` (create), ``POST /v1/pods/{id}/stop``,
  ``DELETE /v1/pods/{id}`` (terminate);
* pod reads: ``GET /v1/pods``, ``GET /v1/pods/{id}``;
* account/catalog reads over GraphQL: ``myself { clientBalance }`` (the
  spending cap is the balance) and ``gpuTypes { lowestPrice }`` (price/stock);
* optionally ``GET /v1/billing/pods`` (charges; refusal leaves them unresolved).

No template, network-volume, endpoint, secret, registry, SSH-key or billing
*write* is ever issued. Whether a RunPod API key can be restricted to exactly
this set is not verified here: the balance and price reads go through GraphQL,
and if RunPod's key scoping cannot grant those reads alongside pod lifecycle,
the operator must either grant the broader read scope or supply balance and
price observations some other way - the provision gate only requires that a
balance observation is recorded, not that this adapter made it.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from typing import Protocol

from .credentials import CredentialProvider, CredentialUnavailable
from .errors import ComputeError, Execution
from .model import (
    CarbonOwnedResource,
    Offer,
    PodSpec,
    ResourceState,
    UserManagedHost,
    ownership_name,
)
from .provider import (
    BalanceObservation,
    CreateResult,
    ListedResource,
    Observation,
    ProviderCharge,
)

__all__ = ["RunPodAdapter", "RunPodTransport", "UrllibTransport", "runpod_state"]

REST = "https://rest.runpod.io/v1"
GRAPHQL = "https://api.runpod.io/graphql"
MAX_RESPONSE_BYTES = 4 * 1024**2
_GPU_ID = re.compile(r"^[A-Za-z0-9 ._-]{1,64}$")
_POD_ID = re.compile(r"^[A-Za-z0-9]{1,64}$")
_POD_PATH = r"/v1/pods/[A-Za-z0-9]{1,64}"
ALLOWED_OPERATIONS: tuple[tuple[str, str, str], ...] = (
    # (operation, method, full-url pattern)
    ("provision", "POST", r"https://rest\.runpod\.io/v1/pods"),
    ("list", "GET", r"https://rest\.runpod\.io/v1/pods"),
    ("status", "GET", r"https://rest\.runpod\.io" + _POD_PATH),
    ("stop", "POST", r"https://rest\.runpod\.io" + _POD_PATH + "/stop"),
    ("terminate", "DELETE", r"https://rest\.runpod\.io" + _POD_PATH),
    ("offers", "POST", r"https://api\.runpod\.io/graphql"),
    ("balance", "POST", r"https://api\.runpod\.io/graphql"),
    (
        "charges",
        "GET",
        r"https://rest\.runpod\.io/v1/billing/pods\?podId=[A-Za-z0-9]{1,64}",
    ),
)
_ALLOWED = {
    (operation, method): re.compile(pattern)
    for operation, method, pattern in ALLOWED_OPERATIONS
}
# GraphQL bodies are fixed shapes: only these two query roots are ever sent.
_GRAPHQL_PREFIX = {
    "offers": "query { gpuTypes(",
    "balance": "query { myself { clientBalance } }",
}
# Not exercised by pod_control.py; see module docstring.
STOP_SHAPE_VERIFIED_LIVE = False
BILLING_SHAPE_VERIFIED_LIVE = False

log = logging.getLogger("carbon.compute.runpod")


class RunPodTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes]: ...


class UrllibTransport:
    """The real HTTPS transport: no redirects, bounded response."""

    def __call__(self, method, url, *, body, headers, timeout):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect())
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
        except urllib.error.HTTPError as refused:
            return refused.code, refused.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("provider response exceeds bound")
        return status, payload


def runpod_state(pod: dict[str, object]) -> ResourceState:
    """Map a RunPod pod object to a provider-neutral state (conservatively)."""

    desired = str(pod.get("desiredStatus") or "").upper()
    change = str(pod.get("lastStatusChange") or "").lower()
    if desired == "TERMINATED":
        return ResourceState.TERMINATED
    if desired == "EXITED":
        return ResourceState.STOPPED
    if desired == "RUNNING":
        if "pull" in change:
            return ResourceState.PULLING_IMAGE
        if pod.get("runtime") or pod.get("lastStartedAt") or pod.get("publicIp"):
            return ResourceState.RUNNING
        return ResourceState.STARTING
    return ResourceState.UNKNOWN


def _refuse_non_owned(target: object, operation: str) -> CarbonOwnedResource:
    if isinstance(target, CarbonOwnedResource):
        return target
    what = (
        "a user-managed host has no stop or terminate capability"
        if isinstance(target, UserManagedHost)
        else "only a store-issued Carbon-owned resource can be stopped or terminated"
    )
    raise ComputeError(
        operation=operation,
        failed=what,
        execution=Execution.NOT_EXECUTED,
        resources_may_remain=False,
        retry_safe=False,
        next_action="obtain the resource through ComputeStore.owned, or manage "
        "the host yourself",
    )


class RunPodAdapter:
    name = "runpod"

    def __init__(
        self,
        credentials: CredentialProvider,
        transport: RunPodTransport,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        verify_attempts: int = 6,
        verify_interval_s: float = 10.0,
    ) -> None:
        self._credentials = credentials
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._verify_attempts = verify_attempts
        self._verify_interval_s = verify_interval_s

    # transport ----------------------------------------------------------
    def _send(
        self,
        operation: str,
        method: str,
        url: str,
        body: dict | None = None,
        *,
        mutating: bool,
        timeout: float = 60,
    ) -> tuple[int, object]:
        pattern = _ALLOWED.get((operation, method))
        graphql_prefix = _GRAPHQL_PREFIX.get(operation)
        if (
            pattern is None
            or not pattern.fullmatch(url)
            or (
                graphql_prefix is not None
                and not str((body or {}).get("query", "")).startswith(graphql_prefix)
            )
        ):
            raise ComputeError(
                operation=operation,
                failed="request outside the adapter's pod-lifecycle allow-list",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=False,
                next_action="this adapter issues pod lifecycle, balance and price "
                "requests only",
            )
        try:
            key = self._credentials.load()
        except CredentialUnavailable as missing:
            raise ComputeError(
                operation=operation,
                failed=f"RunPod credential unavailable ({missing.status})",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="configure an owner-only RunPod key file",
            ) from None
        headers = {
            "Authorization": "Bearer " + key.reveal(),
            "Content-Type": "application/json",
            "User-Agent": "carbon-compute/1",
        }
        data = None if body is None else json.dumps(body).encode()
        failure_type: str | None = None
        try:
            status, raw = self._transport(
                method, url, body=data, headers=headers, timeout=timeout
            )
        except Exception as failure:  # noqa: BLE001 -- typed below, text dropped
            # Only the exception's type survives: a transport may echo the
            # request, including the Authorization header, in its text. The
            # typed error is raised outside this block so it is not chained to
            # the original exception and no traceback can print it.
            failure_type = type(failure).__name__
        finally:
            del headers, key
        if failure_type is not None:
            log.warning("runpod %s transport failure (%s)", operation, failure_type)
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

    # interface ----------------------------------------------------------
    def offers(
        self, gpu_type_ids: Sequence[str], *, gpu_count: int = 1, cloud_type="SECURE"
    ) -> list[Offer]:
        found = []
        for gpu in gpu_type_ids:
            if not _GPU_ID.fullmatch(gpu) or not 1 <= gpu_count <= 16:
                raise ValueError("invalid GPU offer query")
            query = (
                'query { gpuTypes(input:{id:"' + gpu + '"}) { lowestPrice(input:{'
                f"gpuCount:{gpu_count}, secureCloud:"
                f"{'true' if cloud_type == 'SECURE' else 'false'}"
                "}) { uninterruptablePrice stockStatus } } }"
            )
            status, payload = self._send(
                "offers", "POST", GRAPHQL, {"query": query}, mutating=False
            )
            observed = self._clock()
            price = stock = None
            try:
                lowest = payload["data"]["gpuTypes"][0]["lowestPrice"]  # type: ignore[index]
                price = lowest.get("uninterruptablePrice")
                stock = lowest.get("stockStatus")
            except (TypeError, KeyError, IndexError, AttributeError):
                pass
            found.append(
                Offer(
                    provider=self.name,
                    gpu_type_id=gpu,
                    gpu_count=gpu_count,
                    cloud_type=cloud_type,
                    usd_per_hr=None if price is None else float(price),
                    stock_status=stock,
                    observed_at=observed,
                    source="runpod.graphql.gpuTypes.lowestPrice"
                    + ("" if status == 200 else f".http{status}"),
                )
            )
        return found

    def read_balance(self) -> BalanceObservation:
        """The account balance with its observation time (the spending cap)."""

        status, payload = self._send(
            "balance",
            "POST",
            GRAPHQL,
            {"query": _GRAPHQL_PREFIX["balance"]},
            mutating=False,
        )
        observed = self._clock()
        try:
            value = payload["data"]["myself"]["clientBalance"]  # type: ignore[index]
        except (TypeError, KeyError):
            value = None
        if status != 200 or not isinstance(value, int | float):
            raise ComputeError(
                operation="balance",
                failed="account balance unreadable",
                execution=Execution.EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="retry, or record an operator balance observation",
                http_status=status,
            )
        return BalanceObservation(float(value), observed, "runpod.graphql.myself")

    def create_body(self, spec: PodSpec, ownership_tag: str) -> dict[str, object]:
        env = dict(spec.env)
        env["CARBON_OWNERSHIP_TAG"] = ownership_tag
        body: dict[str, object] = {
            "name": ownership_name(ownership_tag),
            "imageName": spec.image,
            "computeType": "GPU" if spec.gpu_count else "CPU",
            "cloudType": spec.cloud_type,
            "interruptible": False,
            "containerDiskInGb": spec.container_disk_gb,
            "volumeInGb": spec.volume_gb,
            "ports": list(spec.ports),
            "env": env,
        }
        if spec.gpu_count:
            body["gpuTypeIds"] = [spec.gpu_type_id]
            body["gpuCount"] = spec.gpu_count
        return body

    def create(self, spec: PodSpec, *, ownership_tag: str) -> CreateResult:
        status, payload = self._send(
            "provision",
            "POST",
            REST + "/pods",
            self.create_body(spec, ownership_tag),
            mutating=True,
        )
        pod_id = payload.get("id") if isinstance(payload, dict) else None
        if isinstance(pod_id, str) and _POD_ID.fullmatch(pod_id):
            rate = payload.get("costPerHr")  # type: ignore[union-attr]
            return CreateResult(pod_id, None if rate is None else float(rate))
        definitive = status in {400, 401, 403, 404, 422}
        raise ComputeError(
            operation="provision",
            failed="provider did not return a resource id",
            execution=Execution.EXECUTED if definitive else Execution.MAY_HAVE_EXECUTED,
            resources_may_remain=not definitive,
            retry_safe=False,
            next_action=(
                "fix the request and use a new intent"
                if definitive
                else "reconcile by ownership tag; do not resend"
            ),
            http_status=status,
        )

    def observe(self, resource_id: str) -> Observation:
        if not _POD_ID.fullmatch(resource_id):
            raise ValueError("invalid pod id")
        status, payload = self._send(
            "status", "GET", f"{REST}/pods/{resource_id}", mutating=False
        )
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
        rate = payload.get("costPerHr")
        return Observation(
            resource_id,
            True,
            runpod_state(payload),
            payload.get("name"),
            None if rate is None else float(rate),
            now,
        )

    def list_resources(self) -> list[ListedResource]:
        status, payload = self._send("list", "GET", REST + "/pods", mutating=False)
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
            ListedResource(str(item["id"]), item.get("name"))
            for item in payload
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

    def _confirm_ownership(self, owned: CarbonOwnedResource, operation: str) -> bool:
        """True if present and carrying our tag; False if already absent."""

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
        owned = _refuse_non_owned(owned, "stop")
        if not self._confirm_ownership(owned, "stop"):
            return
        status, _ = self._send(
            "stop", "POST", f"{REST}/pods/{owned.resource_id}/stop", mutating=True
        )
        if status not in {200, 204}:
            raise ComputeError(
                operation="stop",
                failed="provider refused stop",
                execution=Execution.MAY_HAVE_EXECUTED,
                resources_may_remain=True,
                retry_safe=True,
                next_action="observe the pod, then retry stop or terminate",
                http_status=status,
            )

    def terminate(self, owned: CarbonOwnedResource) -> bool:
        owned = _refuse_non_owned(owned, "terminate")
        if not self._confirm_ownership(owned, "terminate"):
            return True
        for attempt in range(self._verify_attempts):
            self._send(
                "terminate",
                "DELETE",
                f"{REST}/pods/{owned.resource_id}",
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
            next_action="run `python -m carbon.compute reconcile` again",
        )

    def connect_url(self, owned: CarbonOwnedResource, port: int) -> str:
        owned = _refuse_non_owned(owned, "connect")
        if not 1 <= port <= 65535:
            raise ValueError("invalid port")
        return f"https://{owned.resource_id}-{port}.proxy.runpod.net"

    def provider_charge(self, owned: CarbonOwnedResource) -> ProviderCharge | None:
        """Provider-reported spend for one pod, or ``None`` when unresolved."""

        owned = _refuse_non_owned(owned, "charges")
        query = urllib.parse.urlencode({"podId": owned.resource_id})
        status, payload = self._send(
            "charges", "GET", f"{REST}/billing/pods?{query}", mutating=False
        )
        if status != 200 or not isinstance(payload, list):
            return None
        amounts = [
            item.get("amount")
            for item in payload
            if isinstance(item, dict) and item.get("podId") == owned.resource_id
        ]
        if not amounts or not all(isinstance(a, int | float) for a in amounts):
            return None
        return ProviderCharge(
            float(sum(amounts)),
            "runpod.billing.pods"
            + ("" if BILLING_SHAPE_VERIFIED_LIVE else ".unverified_shape"),
        )
