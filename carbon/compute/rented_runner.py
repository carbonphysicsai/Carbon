"""Carbon's fixed practice program on a rented GPU (C-MLP-03 slice 4).

`RentedRunner` has the carrier's call signature (`research_carrier._run`), so
battery practice runs on a rented GPU exactly as it runs locally: the same
staged files, the same program, the same output files, scored on the miner's
machine. What differs is where the program runs:

1. The ledger reserves the trial first, as the carrier does.
2. A durable job record (`operation/rented-job.json`, owner-only) fixes the
   request, the job token and the deadline before anything is sent, so a
   restart re-derives the same provisioning request and never resends a
   different one.
3. `ComputeService` provisions one pod from the pinned worker image on the
   miner's own provider account: balance observed and recorded first, rate
   ceiling and deadline bound, the miner's budget applied, an ownership tag on
   the resource.
4. The pod runs `carbon.compute.job_server`. The controller stages the job's
   public inputs, runs it, and fetches its output (`RemoteJob`).
5. The pod is terminated whether the job succeeded or not, and the adapter
   verifies it is gone. The provider's own charge is read when it reports one.

**The trust boundary stays on the miner's machine.** The controller, the
provider key and the hotkey signer never leave it. The pod receives the pinned
worker image, the job's public inputs and a per-job token, nothing else.
Nothing measured on a rented GPU is evidence the validator reads.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .errors import ComputeError
from .job_server import PROGRAM
from .model import PodSpec, ProvisionRequest, ResourceState
from .remote_job import RemoteJob, RemoteJobFailure, new_token

SCHEMA = "carbon.compute.rented-job-record.v1"
#: The port the job server listens on inside the pod.
JOB_PORT = 8000
#: The pod's start command: the job server from the pinned worker's own wheel.
START_COMMAND = (
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.compute.job_server",
)


@dataclass(frozen=True)
class RentedCompute:
    """What the miner chose in setup for one provider account."""

    provider: str
    image_ref: str
    gpu_type_id: str
    max_rate_usd_per_hr: float
    storage_usd_per_gb_month: float
    cloud_type: str = "SECURE"
    container_disk_gb: int = 20
    #: Time a pod may take to start and pull the image, before the job's own.
    startup_seconds: int = 900
    #: A VM provider's image (Targon): the operating system the VM boots, in
    #: which the pinned worker then runs with Docker. None for a provider that
    #: runs the worker image itself.
    vm_image: str | None = None

    def __post_init__(self):
        from .providers import VM_PROVIDERS

        if "@sha256:" not in self.image_ref:
            raise ValueError("the rented worker image must be pinned by digest")
        if (self.provider in VM_PROVIDERS) != (self.vm_image is not None):
            raise ValueError("a VM provider, and only one, names a VM image")
        if self.vm_image is not None and (
            type(self.vm_image) is not str
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", self.vm_image)
        ):
            raise ValueError("invalid VM image name")
        for value in (self.max_rate_usd_per_hr, self.storage_usd_per_gb_month):
            if not (isinstance(value, int | float) and math.isfinite(value)):
                raise ValueError("a finite rate ceiling is required")
            if value <= 0:
                raise ValueError("a positive rate ceiling is required")

    def document(self):
        return {
            "provider": self.provider,
            "image_ref": self.image_ref,
            "gpu_type_id": self.gpu_type_id,
            "max_rate_usd_per_hr": self.max_rate_usd_per_hr,
            "storage_usd_per_gb_month": self.storage_usd_per_gb_month,
            "cloud_type": self.cloud_type,
            # Present only for a VM provider, so no other choice's identity moves.
            **({} if self.vm_image is None else {"vm_image": self.vm_image}),
        }


def _cancel_requested(ledger, owner, identity):
    """The carrier's own stop signal for this task."""
    from carbon.development_session.research_carrier import _cancel_path

    return _cancel_path(ledger, owner, identity).exists()


class RentedRunner:
    """A carrier-compatible practice runner on the miner's rented GPU."""

    def __init__(
        self,
        *,
        compute: RentedCompute,
        service,
        tenant: str,
        miner: str,
        campaign_id: str,
        clock: Callable[[], float] = time.time,
        job: Callable = RemoteJob,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if service.provider.name != compute.provider:
            raise ValueError("the service's provider is not the chosen one")
        self.compute, self.service = compute, service
        self.tenant, self.miner, self.campaign_id = tenant, miner, campaign_id
        self.clock, self.job, self.sleep = clock, job, sleep

    def _record(self, operation, request, seconds):
        """The durable job record: written once, before any provider call."""
        path = operation / "rented-job.json"
        if not path.exists():
            operation.mkdir(mode=0o700, exist_ok=True)
            write_once(
                path,
                canonical(
                    {
                        "schema": SCHEMA,
                        "request": request,
                        "token": new_token(),
                        "deadline_at": math.ceil(
                            self.clock() + self.compute.startup_seconds + seconds + 300
                        ),
                    }
                ),
            )
            path.chmod(0o600)
        record = json.loads(path.read_bytes())
        if record.get("schema") != SCHEMA or record.get("request") != request:
            raise ValueError("rented job record conflict")
        return record

    def _provision_request(self, intent_id, record, seconds):
        compute = self.compute
        spec = PodSpec(
            image=compute.image_ref,
            gpu_type_id=compute.gpu_type_id,
            gpu_count=1,
            cloud_type=compute.cloud_type,
            container_disk_gb=compute.container_disk_gb,
            ports=(f"{JOB_PORT}/http",),
            env=(
                ("CARBON_JOB_TOKEN", record["token"]),
                ("CARBON_JOB_PORT", str(JOB_PORT)),
                ("CARBON_JOB_SECONDS", str(seconds)),
                ("CARBON_JOB_LIFETIME", str(compute.startup_seconds + seconds + 300)),
                ("JAX_PLATFORMS", "cuda"),
            ),
            start_command=START_COMMAND,
            max_rate_usd_per_hr=compute.max_rate_usd_per_hr,
            storage_usd_per_gb_month=compute.storage_usd_per_gb_month,
        )
        return ProvisionRequest(
            tenant=self.tenant,
            miner=self.miner,
            campaign_id=self.campaign_id,
            intent_id=intent_id,
            spec=spec,
            deadline_at=float(record["deadline_at"]),
        )

    def __call__(
        self,
        ledger,
        *,
        owner,
        identity,
        source,
        files,
        image,
        seconds,
        provenance,
        extra_resources,
        accelerator=None,
    ):
        del image, accelerator  # The rented worker is the chosen pinned image.
        if type(seconds) is not int or not 40 <= seconds <= 3600:
            raise ValueError("bounded worker wall allowance required")
        if type(files) is not dict or PROGRAM in files:
            raise ValueError("closed stage required")
        request = {
            "source": digest(source.encode()),
            "files": {n: digest(b) for n, b in files.items()},
            "seconds": seconds,
            "provenance": provenance,
            "rented": self.compute.document(),
        }
        launch = digest(
            canonical({"owner": owner, "identity": identity, "request": request})
        )
        operation = ledger.root / ("operation-" + launch[7:])
        resources = {
            "numerical_milliseconds": seconds * 1000,
            "retained_bytes": sum(map(len, files.values())) + 2 * 64 * 1024**2,
            **extra_resources,
        }
        admission = ledger.reserve(
            identity,
            owner=owner,
            phase="research",
            request=request,
            resources=resources,
        )
        if not admission["dispatch"]:
            if admission["state"] == "RESERVED":
                raise ValueError(
                    "rented operation ambiguous; reconcile, never duplicate"
                )
            return admission["result"]
        record = self._record(operation, request, seconds)
        intent_id = "job-" + launch[7:31]
        provision = self._provision_request(intent_id, record, seconds)
        started = time.monotonic()
        resource = None
        rented = {**self.compute.document(), "intent_id": intent_id}
        try:
            self.service.observe_balance(self.campaign_id)
            resource = self.service.provision(provision)
            rented["resource_id"] = resource.resource_id
            rented["rate_usd_per_hr"] = resource.rate_usd_per_hr
            owned = self.service.owned(
                self.campaign_id, intent_id, resource.resource_id
            )
            # https through a provider proxy unless the adapter states another
            # route: Lium's node IP over plain HTTP, or Targon's SSH forward.
            transport = getattr(self.service.provider, "job_transport", "https")
            plain = transport == "http-direct"
            rented["job_transport"] = transport
            job = self.job(
                self._job_url(owned, ledger, owner, identity),
                record["token"],
                cancelled=lambda: _cancel_requested(ledger, owner, identity),
                **({"plain_http": True} if plain else {}),
            )
            now = job.clock()
            outcome, output = job.run(
                {**files, PROGRAM: source.encode()},
                ready_deadline=now + self.compute.startup_seconds,
                run_deadline=now + self.compute.startup_seconds + seconds + 60,
            )
        except (ComputeError, RemoteJobFailure, OSError, ValueError) as failure:
            rented["teardown"] = self._teardown(intent_id, resource)
            ledger.finish(
                identity,
                owner=owner,
                state="FAILED_INFRA",
                actual=resources,
                result={
                    "schema": "carbon.autoresearch.worker-reconciliation.v1",
                    "operation": operation.name,
                    "state": "FAILED_INFRA",
                    "rented": rented,
                    "failed": type(failure).__name__,
                    "accounting": "full original reservation retained",
                    "scientific_outcome": "UNRESOLVED",
                    "retry_dispatched": False,
                },
            )
            raise
        rented["teardown"] = self._teardown(intent_id, resource)
        rented["job"] = outcome
        snapshot = operation / "snapshot"
        snapshot.mkdir(mode=0o700)
        for name, body in output.items():
            write_once(snapshot / name, body)
        result = {
            "schema": "carbon.autoresearch.worker-result.v1",
            "provenance": provenance,
            "output_digest": digest(
                canonical({n: digest(b) for n, b in output.items()})
            ),
            "files": {name: digest(body) for name, body in sorted(output.items())},
            "operation": operation.name,
            "rented": rented,
            "scientific_qualification": False,
            "official_eligible": False,
        }
        ledger.finish(
            identity,
            owner=owner,
            state="SUCCEEDED",
            actual={
                **resources,
                "numerical_milliseconds": math.ceil(
                    (time.monotonic() - started) * 1000
                ),
                "retained_bytes": sum(
                    p.stat().st_size for p in operation.rglob("*") if p.is_file()
                ),
            },
            result=result,
        )
        return result

    def _job_url(self, owned, ledger, owner, identity):
        """The job's address, once the pod exposes it (within startup time)."""
        deadline = time.monotonic() + self.compute.startup_seconds
        while True:
            try:
                return self.service.provider.connect_url(owned, JOB_PORT)
            except ComputeError as failure:
                if not failure.retry_safe or time.monotonic() >= deadline:
                    raise
            if _cancel_requested(ledger, owner, identity):
                raise RemoteJobFailure("cancelled", "the campaign was stopped")
            self.sleep(10.0)

    def _teardown(self, intent_id, resource):
        """Terminate and verify; read the provider's charge if it reports one."""
        if resource is None:
            # Nothing bound: an ambiguous dispatch is the reconciler's to adopt
            # and terminate by its ownership tag.
            try:
                state = self.service.cancel_provisioning(self.campaign_id, intent_id)
            except ComputeError as failure:
                return {"verified": False, "next_action": failure.next_action}
            return {"verified": True, "intent": str(state)}
        try:
            self.service.terminate(self.campaign_id, intent_id, resource.resource_id)
        except ComputeError as failure:
            return {"verified": False, "next_action": failure.next_action}
        teardown = {"verified": True, "state": str(ResourceState.TERMINATED)}
        owned = self.service.owned(self.campaign_id, intent_id, resource.resource_id)
        try:
            charge = self.service.provider.provider_charge(owned)
        except ComputeError:
            charge = None
        if charge is not None:
            self.service.store.record_provider_charge(
                owned.provider, owned.resource_id, charge.amount_usd, charge.basis
            )
            teardown["charge"] = {
                "amount_usd": charge.amount_usd,
                "basis": charge.basis,
            }
        else:
            teardown["charge"] = "unresolved: the provider reported no charge yet"
        return teardown
