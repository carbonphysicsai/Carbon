"""Shared pod jobs (CLOUD-FIRST-COMPUTE-01): one launcher for every heavy public job.

    python -m carbon.agent_campaign.pod_jobs plan SPEC.json
    python -m carbon.agent_campaign.pod_jobs check SPEC.json --root NEW_DIR
    python -m carbon.agent_campaign.pod_jobs run SPEC.json --out DIR --key-file PATH [--root DIR]

A job is one registered Python module run on one RunPod pod, CPU or GPU, from
Carbon's own code at a pushed commit. The spec (`carbon.pod-job.spec.v1`) names:
- `code_ref`: a 40-hex pushed commit. The pod fetches every shipped file from
  GitHub at that commit and refuses any whose sha256 differs (`bootstrap.py`).
- `module` and `args`: what runs (`python -m module args...`), with `{out}`,
  `{root}` and `{inputs}` the only substitutions. No shell, no other command.
- `inputs`: repository paths (files or directories) at `code_ref`, shipped
  beside the code. Public material only: anything the ship guard refuses
  (`pods.shippable`, `FORBIDDEN_DATA`) refuses the job.
- `uploads` (path to {sha256, bytes}): files that are not in git, uploaded
  from a local directory once the pod waits for them (`run --uploads DIR`).
  The pod accepts each only at its declared size and sha256
  (`bootstrap.receive`) and starts the job when all have arrived. `collect`
  lists paths under the uploads directory that the phase copies back into
  the results after the job.
- `image` (`study`: the pinned EV4 study image, CPU or JAX GPU; `pytorch`: the
  released torch-gpu worker image), `overlays` (name to lock path), and
  `compute` (`{"kind": "cpu", "flavor", "vcpus"}` or
  `{"kind": "gpu", "type", "count"}`).
- `minutes`, `rate_ceiling_usd_per_hr` and `cap_usd`. The pod's worst case
  (`minutes` at the ceiling, plus disk and pod_control's cleanup reserve) must
  fit under `cap_usd`, and `cap_usd` under OWNER-TEST-GRANT-01's per-run cap.

The lifecycle composes Graphite's live pod backend (`graphite.pods.RunPodPods`
on the operator layer `operator_compute`), which this module never changes:
a durable intent before the create, an ownership tag that recovers a lost
create response, the account balance floor, the rate ceiling checked on the
created pod, the pod's own self-terminate at its deadline (`bootstrap.py`),
deletion verified by absence, and the provider's charge when it reports one.
Its own lane is the campaign `pod-jobs`.

`run` claims the job in the host ledger (`grant_runs.claim_pod_job`,
OWNER-TEST-GRANT-01: USD 50 per run, USD 300 per rolling week less the held
CONFIRM-02 reserve) before any provider call, then
launches, waits, fetches every result file checked against the pod's own
sha256 listing, and terminates the pod whatever happened. The receipt
(`carbon.pod-job.receipt.v1`, `OUT/receipt.json`) records the files and
their sha256, the teardown, the cost (reservation, provider charge or
unresolved) and the week's ledger line. A pod refused before any create
settles at zero.

`check` drives the same code path against an in-memory RunPod
(`pods.InMemoryRunPod`): no network, no account, no spend.

Only public or non-sensitive work runs here (CLOUD-FIRST-COMPUTE-01 rule 2).
Sealed or hidden material stays on the AX42 under its custody records.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from carbon.agent_campaign.graphite import pods
from carbon.agent_campaign.graphite.pods import PodFailure, PodHandle

REPOSITORY = Path(__file__).resolve().parents[2]
SPEC_SCHEMA = "carbon.pod-job.spec.v1"
RECEIPT_SCHEMA = "carbon.pod-job.receipt.v1"
CAMPAIGN = "pod-jobs"
#: The owner's enabling file, beside the RunPod key file: `{"enabled": true,
#: "upload_roots": [absolute directories]}`. Without it `run` refuses: a key
#: file alone never spends (`require_enabled`).
ENABLE_FILE = "pod-jobs.json"
#: Path fragments that mark sealed, hidden or evidence material on a host. An
#: upload directory or file whose resolved path holds one is refused, whatever
#: the allow-list says (CLOUD-FIRST-COMPUTE-01 rule 2: public material only).
SEALED_FRAGMENTS = (
    "shared/evidence",
    "deploy",
    "journal",
    "custody",
    "sealed",
    "hidden",
    "confirm",
    "tuning",
    "/.runpod",
    "/.ssh",
    *pods.FORBIDDEN_DATA,
)
#: Upload paths are plain: no character a URL path would have to encode.
_UPLOAD_PATH = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")
PHASE_MODULE = "carbon.agent_campaign.pod_job_phase"
GRANT_ID = "OWNER-TEST-GRANT-01:pod-jobs"
#: The code trees a job's module and its imports are taken from.
CODE_TREES = ("carbon", "scripts")
BOOTSTRAP = "scripts/dev/exam_design/runpod/bootstrap.py"
#: Placeholders a job's arguments may carry, filled on the pod by the phase.
PLACEHOLDERS = ("{out}", "{root}", "{inputs}")
#: Upload limits: one request through the pod proxy, and the job's total.
MAX_UPLOAD_FILE_BYTES = 95 * 1024 * 1024
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024
#: The time the pod keeps for listing and fetching its results after the job's
#: own allowance (`pods.EXPORT_MINUTES`).
EXPORT_MINUTES = pods.EXPORT_MINUTES
POLL_SECONDS = pods.POLL_SECONDS
_JOB_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,46}[a-z0-9]")
_MODULE = re.compile(r"(carbon|scripts)(\.[A-Za-z_][A-Za-z0-9_]*)+")
_SPEC_FIELDS = {
    "schema",
    "job_id",
    "code_ref",
    "module",
    "args",
    "inputs",
    "image",
    "overlays",
    "compute",
    "minutes",
    "rate_ceiling_usd_per_hr",
    "cap_usd",
    "disk_gb",
    "uploads",
    "collect",
}


class SpecRefused(ValueError):
    """The spec is not a valid pod job; nothing was claimed or launched."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _decimal(value, label):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise SpecRefused("spec_" + label) from None
    if not number.is_finite() or number <= 0:
        raise SpecRefused("spec_" + label)
    return number


@dataclass(frozen=True)
class JobSpec:
    """A validated `carbon.pod-job.spec.v1` (`load_spec`)."""

    document: dict

    @property
    def job_id(self):
        return self.document["job_id"]

    @property
    def minutes(self):
        return self.document["minutes"]

    @property
    def cpu(self):
        return self.document["compute"]["kind"] == "cpu"

    def digest(self):
        body = json.dumps(self.document, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(body.encode()).hexdigest()

    def economics(self):
        """The pod's worst case at its ceiling, from pod_control's disk price
        and cleanup reserve (never restated here)."""
        from scripts.dev.exam_design.runpod import pod_control

        rate = _decimal(self.document["rate_ceiling_usd_per_hr"], "rate_ceiling")
        disk_month = Decimal(str(pod_control.DISK_USD_PER_GB_MONTH))
        disk_hour = Decimal(self.document["disk_gb"]) * disk_month / Decimal(730)
        reserve = Decimal(str(pod_control.CLEANUP_RESERVE_USD))
        minutes = Decimal(self.minutes + EXPORT_MINUTES)
        worst = (rate + disk_hour) * minutes / Decimal(60) + reserve
        return {
            "rate_ceiling_usd_per_hr": rate,
            "disk_usd_per_gb_month": disk_month,
            "hourly_usd": rate + disk_hour,
            "worst_case_usd": pods.cents_up(worst),
            "cap_usd": _decimal(self.document["cap_usd"], "cap"),
        }


def load_spec(document):
    """A `JobSpec`, or `SpecRefused` with a typed code. Checks the shape and
    the money only; what ships is checked against `code_ref` (`ship_list`)."""
    from carbon.agent_campaign import grant_runs

    if type(document) is not dict or set(document) != _SPEC_FIELDS:
        raise SpecRefused("spec_fields", "the spec's fields are closed")
    if document["schema"] != SPEC_SCHEMA:
        raise SpecRefused("spec_schema")
    if type(document["job_id"]) is not str or not _JOB_ID.fullmatch(document["job_id"]):
        raise SpecRefused("spec_job_id")
    ref = document["code_ref"]
    if type(ref) is not str or not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise SpecRefused("spec_code_ref", "a 40-hex pushed commit is required")
    module = document["module"]
    if type(module) is not str or not _MODULE.fullmatch(module):
        raise SpecRefused("spec_module", "a carbon.* or scripts.* module")
    args = document["args"]
    if type(args) is not list or not all(type(a) is str for a in args):
        raise SpecRefused("spec_args")
    for arg in args:
        if "{" in arg and not any(p in arg for p in PLACEHOLDERS):
            raise SpecRefused("spec_args", "only {out}, {root} and {inputs}")
    inputs = document["inputs"]
    if type(inputs) is not list or not all(_repo_path(p) for p in inputs):
        raise SpecRefused("spec_inputs", "repository-relative paths only")
    uploads, collect = document["uploads"], document["collect"]
    if type(uploads) is not dict or not all(
        _upload_path(path) and _upload_entry(entry) for path, entry in uploads.items()
    ):
        raise SpecRefused("spec_uploads")
    if sum(entry["bytes"] for entry in uploads.values()) > MAX_UPLOAD_BYTES:
        raise SpecRefused("spec_uploads", "over the job's upload total")
    if type(collect) is not list or not all(_repo_path(c) for c in collect):
        raise SpecRefused("spec_collect")
    if not uploads and (collect or any("{inputs}" in a for a in args)):
        raise SpecRefused("spec_uploads", "{inputs} and collect need uploads")
    if document["image"] not in ("study", "pytorch"):
        raise SpecRefused("spec_image")
    overlays = document["overlays"]
    if type(overlays) is not dict or not all(
        type(k) is str and re.fullmatch(r"[a-z0-9_-]{1,32}", k) and _repo_path(v)
        for k, v in overlays.items()
    ):
        raise SpecRefused("spec_overlays")
    compute = document["compute"]
    if type(compute) is not dict:
        raise SpecRefused("spec_compute")
    if compute.get("kind") == "cpu":
        if set(compute) != {"kind", "flavor", "vcpus"}:
            raise SpecRefused("spec_compute")
        from scripts.dev.exam_design.runpod.operator_compute import CPUPlacement

        try:
            CPUPlacement(compute["flavor"], compute["vcpus"])
        except ValueError as refused:
            raise SpecRefused("spec_compute", str(refused)) from None
        if document["image"] != "study":
            raise SpecRefused("spec_compute", "a CPU pod runs the study image")
    elif compute.get("kind") == "gpu":
        if set(compute) != {"kind", "type", "count"}:
            raise SpecRefused("spec_compute")
        if type(compute["type"]) is not str or not compute["type"]:
            raise SpecRefused("spec_compute")
        if type(compute["count"]) is not int or not 1 <= compute["count"] <= 8:
            raise SpecRefused("spec_compute")
    else:
        raise SpecRefused("spec_compute")
    for key in ("minutes", "disk_gb"):
        if type(document[key]) is not int or document[key] <= 0:
            raise SpecRefused("spec_" + key)
    spec = JobSpec(document)
    money = spec.economics()
    if money["cap_usd"] > grant_runs.PER_RUN_CAP_USD:
        raise SpecRefused(
            grant_runs.PER_RUN_LIMIT,
            f"cap {money['cap_usd']} is above the {grant_runs.PER_RUN_CAP_USD} USD "
            "per-run cap",
        )
    if money["worst_case_usd"] > money["cap_usd"]:
        raise SpecRefused(
            "spec_cap_below_worst_case",
            f"worst case {money['worst_case_usd']} USD is above the cap "
            f"{money['cap_usd']} USD: shorten the job or lower the rate ceiling",
        )
    return spec


def _upload_path(path):
    """A plain relative path the ship guard accepts (no private directory, no
    forbidden name) and no URL would have to encode."""
    return (
        _repo_path(path)
        and _UPLOAD_PATH.fullmatch(path) is not None
        and not {".", ".."} & set(path.split("/"))
        and pods.shippable(path)
        and not _sealed(path)
    )


def _sealed(path):
    text = "/" + str(path).replace("\\", "/").lower()
    return any(fragment in text for fragment in SEALED_FRAGMENTS)


def _upload_entry(entry):
    return (
        type(entry) is dict
        and set(entry) == {"sha256", "bytes"}
        and type(entry["sha256"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None
        and type(entry["bytes"]) is int
        and 0 <= entry["bytes"] <= MAX_UPLOAD_FILE_BYTES
    )


def _repo_path(path):
    return (
        type(path) is str
        and bool(path)
        and not path.startswith("/")
        and "\\" not in path
        and ".." not in Path(path).parts
    )


# -- what ships -----------------------------------------------------------------------------
def ship_list(spec, repository=REPOSITORY):
    """The files a job's pod is shipped at `code_ref`: the import closure of the
    phase and the job's module, the non-code files beside that closure, the
    inputs and the overlay locks. Every path passes the ship guard; an input
    or lock it refuses refuses the job (`SpecRefused`), never silently drops."""
    from scripts.dev.exam_design.runpod.a40_acceptance import read_blobs
    from scripts.dev.exam_design.runpod.pod_env import import_closure

    ref = spec.document["code_ref"]
    named = []
    for path in list(spec.document["inputs"]) + list(
        spec.document["overlays"].values()
    ):
        files = pods.tracked(ref, [path], repository)
        refused = [f for f in files if not pods.shippable(f)]
        if refused:
            raise SpecRefused("spec_input_not_shippable", refused[0])
        named += files
    candidates = [
        p for p in pods.tracked(ref, CODE_TREES, repository) if pods.shippable(p)
    ]
    sources = [p for p in candidates if p.endswith(".py")]
    entries = [PHASE_MODULE, spec.document["module"]]
    code = import_closure(read_blobs(ref, repository, sources), entries)
    module_file = spec.document["module"].replace(".", "/")
    if not any(p in code for p in (module_file + ".py", module_file + "/__main__.py")):
        raise SpecRefused("spec_module", "not a module at code_ref")
    directories = {str(Path(p).parent) for p in code}
    beside = [
        p
        for p in candidates
        if not p.endswith(".py")
        and any(
            str(Path(p).parent) == d or str(Path(p).parent).startswith(d + "/")
            for d in directories
        )
    ]
    return list(dict.fromkeys(code + beside + named))


# -- the pod backend ------------------------------------------------------------------------
class JobPods(pods.RunPodPods):
    """Graphite's `RunPodPods` for one general job: its own campaign lane, ship
    list, environment and pod spec. Status, fetch, recover, terminate and
    charge are `RunPodPods`' own, unchanged."""

    CAMPAIGN = CAMPAIGN

    def __init__(
        self,
        spec,
        *,
        root,
        key_file,
        repository=REPOSITORY,
        clock=time.time,
        sleep=time.sleep,
        http=None,
        transport=None,
        balance_floor=pods.operator_balance_floor,
        post=None,
    ):
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeService,
            ComputeStore,
            FileCredentialProvider,
            RunPodAdapter,
            UrllibTransport,
        )

        # The owner's switch beside the key file: without it no backend exists,
        # so no caller (the CLI or a library) can spend with a key file alone.
        self.key_file = Path(key_file)
        self.upload_roots = require_enabled(key_file)
        self.spec = spec
        self.repository = Path(repository)
        self.code_ref = spec.document["code_ref"]
        self.clock, self.sleep = clock, sleep
        self.balance_floor = balance_floor
        self.retry_ambiguous_create = True
        self.http = http or pods._https_get
        self.post = post or _https_post
        self._record_lock = threading.Lock()
        root = pods.private_dir(root)
        self.store = ComputeStore(root / "compute", clock=clock)
        if self.store.campaign_status(self.CAMPAIGN) is None:
            self.store.start_campaign(self.CAMPAIGN)
        self.adapter = RunPodAdapter(
            FileCredentialProvider(Path(key_file)),
            transport or UrllibTransport(),
            clock=clock,
            sleep=sleep,
        )
        self.service = ComputeService(
            self.store, self.adapter, clock=clock, sleep=sleep
        )
        self._tokens = {}
        self.money = spec.economics()
        self.manifest = pods.code_manifest(
            self.code_ref, ship_list(spec, self.repository), self.repository
        )
        # The bootstrap the pod runs is the one at `code_ref`, as the code it
        # fetches is, never the working tree's.
        from scripts.dev.exam_design.runpod.a40_acceptance import read_blobs

        boot = read_blobs(self.code_ref, self.repository, [BOOTSTRAP])
        self.boot = boot[BOOTSTRAP].decode()

    def image(self):
        return pods.pod_image(
            "pytorch" if self.spec.document["image"] == "pytorch" else "jax"
        )

    def describe(self):
        compute = self.spec.document["compute"]
        return {
            "backend": self.name,
            "campaign": self.CAMPAIGN,
            "job_id": self.spec.job_id,
            "spec_digest": self.spec.digest(),
            "image": self.image(),
            "compute": dict(compute),
            "rate_ceiling_usd_per_hr": str(self.money["rate_ceiling_usd_per_hr"]),
            "worst_case_usd": str(self.money["worst_case_usd"]),
            "cap_usd": str(self.money["cap_usd"]),
            "code_ref": self.code_ref,
            "code_files": len(self.manifest),
            "code_manifest_sha256": pods.manifest_digest(self.manifest),
        }

    def record(self, private):
        """The job's token and deadline, fixed once before any provider call,
        so a restart re-derives the same create request."""
        from carbon.development_session.data import write_once

        path = Path(private) / "pod-job.json"
        with self._record_lock:
            if not path.exists():
                write_once(
                    path,
                    json.dumps(
                        {
                            "intent_id": self.spec.job_id,
                            "spec_digest": self.spec.digest(),
                            "token": secrets.token_urlsafe(24),
                            "deadline_at": int(
                                self.clock() + (self.spec.minutes + EXPORT_MINUTES) * 60
                            ),
                        },
                        sort_keys=True,
                    ).encode(),
                )
            record = json.loads(path.read_bytes())
        if (record["intent_id"], record["spec_digest"]) != (
            self.spec.job_id,
            self.spec.digest(),
        ):
            raise PodFailure("launch", "pod job record conflict", executed=False)
        return record

    def env(self, record):
        from scripts.dev.exam_design.runpod import pod_control

        document = self.spec.document
        env = {
            "PROBE_TOKEN": record["token"],
            "PROBE_DEADLINE": str(int(record["deadline_at"])),
            "PROBE_CA_GZ_B64": pods._ca_bundle(),
            "CODE_REF": self.code_ref,
            **pod_control.manifest_env(self.manifest),
            "PHASE": document["job_id"],
            "PHASE_MODULE": PHASE_MODULE,
            "JOB_CONFIG": json.dumps(
                {
                    "module": document["module"],
                    "args": document["args"],
                    "collect": document["collect"],
                    "stop_epoch": int(record["deadline_at"]) - EXPORT_MINUTES * 60,
                },
                sort_keys=True,
            ),
            "OVERLAYS": json.dumps(document["overlays"], sort_keys=True),
        }
        if document["uploads"]:
            manifest = json.dumps(document["uploads"], sort_keys=True).encode()
            env["INPUTS_MANIFEST_GZ_B64"] = base64.b64encode(
                gzip.compress(manifest, 9, mtime=0)
            ).decode()
        if self.spec.cpu:
            env["JAX_PLATFORMS"] = "cpu"
        return tuple(sorted(env.items()))

    def job_spec(self, record):
        """The create request's `PodSpec`, its environment measured first."""
        from scripts.dev.exam_design.runpod.operator_compute import (
            CPUPlacement,
            PodSpec,
        )
        from scripts.dev.exam_design.runpod.pod_env import ENV_LIMIT_CHARS, env_chars

        env = self.env(record)
        if env_chars(env) > ENV_LIMIT_CHARS:
            raise PodFailure(
                "launch",
                f"{pods.ENV_TOO_LARGE}: the pod environment is {env_chars(env)} "
                f"characters, over the {ENV_LIMIT_CHARS} limit",
                executed=False,
            )
        compute = self.spec.document["compute"]
        common = {
            "image": self.image(),
            "cloud_type": "SECURE",
            "container_disk_gb": self.spec.document["disk_gb"],
            "ports": ("8000/http",),
            "env": env,
            "max_rate_usd_per_hr": float(self.money["rate_ceiling_usd_per_hr"]),
            "storage_usd_per_gb_month": float(self.money["disk_usd_per_gb_month"]),
            "start_command": ("/opt/carbon-worker/bin/python", "-I", "-c", self.boot),
        }
        if self.spec.cpu:
            return PodSpec(
                gpu_type_id=None,
                gpu_count=0,
                cpu_placement=CPUPlacement(compute["flavor"], compute["vcpus"]),
                **common,
            )
        backend = "pytorch" if self.spec.document["image"] == "pytorch" else "jax"
        return PodSpec(
            gpu_type_id=compute["type"],
            gpu_count=compute["count"],
            allowed_cuda_versions=pods.allowed_cuda_versions(self.repository, backend),
            **common,
        )

    def launch_job(self, private):
        """Create the job's pod: the balance floor first, then (GPU) a priced
        offer at or below the ceiling; the operator layer checks the created
        pod's rate against the ceiling and refuses it otherwise."""
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeError,
            Execution,
            ProvisionRequest,
        )

        record = self.record(private)
        spec = self.job_spec(record)
        try:
            balance, _ = self.service.observe_balance(self.CAMPAIGN)
            if (
                Decimal(str(balance)) - self.money["worst_case_usd"]
                < self.balance_floor()
            ):
                raise PodFailure(
                    "launch", "balance would fall below the floor", executed=False
                )
            if not self.spec.cpu:
                compute = self.spec.document["compute"]
                offers = self.adapter.offers(
                    [compute["type"]], gpu_count=compute["count"]
                )
                if len(offers) != 1:
                    raise PodFailure(
                        "launch", "no single GPU pod offer now", executed=False
                    )
                [offer] = offers
                if (
                    offer.usd_per_hr is None
                    or Decimal(str(offer.usd_per_hr))
                    > self.money["rate_ceiling_usd_per_hr"]
                    or not offer.stock_status
                ):
                    raise PodFailure(
                        "launch",
                        "no GPU pod at or below the rate ceiling now (price "
                        f"{offer.usd_per_hr}, stock {offer.stock_status}, source "
                        f"{offer.source})",
                        executed=False,
                    )
            resource = self.service.provision(
                ProvisionRequest(
                    tenant="pod-jobs",
                    miner="pod-jobs",
                    campaign_id=self.CAMPAIGN,
                    intent_id=self.spec.job_id,
                    spec=spec,
                    deadline_at=float(record["deadline_at"]),
                ),
                retry_ambiguous=self.retry_ambiguous_create,
            )
        except ComputeError as failure:
            raise PodFailure(
                "launch",
                failure.failed,
                executed=failure.execution is not Execution.NOT_EXECUTED,
            ) from None
        self._tokens[self.spec.job_id] = record["token"]
        return PodHandle(
            self.spec.job_id, resource.resource_id, pods._rate(resource.rate_usd_per_hr)
        )

    def upload(self, handle, files, *, deadline):
        """Send each declared input once the pod waits for them. `PodFailure`
        when the pod is not waiting, refuses a file, or the deadline passes."""
        while True:
            if self.clock() >= deadline:
                raise PodFailure(
                    "upload", "the pod never waited for inputs", executed=True
                )
            code, body = self._get(handle, "/status")
            stage = None
            if code == 200:
                try:
                    stage = json.loads(body).get("stage")
                except (ValueError, AttributeError):
                    stage = None
            if stage == "waiting_inputs":
                break
            if stage in ("running_phase", "done", "phase_failed", "bootstrap_failed"):
                raise PodFailure("upload", f"the pod is {stage}", executed=True)
            self.sleep(POLL_SECONDS)
        base = self.adapter.connect_url(self._owned(handle), 8000)
        for path, body in sorted(files.items()):
            url = base + "/input/" + path  # plain by `_upload_path`
            code = self.post(url, self._token(handle), body, 600)
            if code != 200:
                raise PodFailure("upload", f"{path} refused ({code})", executed=True)


def _https_post(url, token, body, timeout):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"X-Probe-Token": token, "User-Agent": "carbon-pod-jobs/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as refused:
        return refused.code
    except Exception:  # noqa: BLE001 -- an unreachable pod is a typed status
        return 0


def uploads_manifest(directory):
    """`uploads` for a spec: every file under `directory`, its sha256 and size."""
    directory = Path(directory)
    return {
        p.relative_to(directory).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def read_uploads(spec, directory, roots):
    """The job's declared uploads, fail closed (CLOUD-FIRST-COMPUTE-01 rule 2).

    `directory` must resolve under one of `roots` (the owner's allow-list,
    `require_enabled`), and neither it, a root, nor any file may sit under a
    sealed, hidden or evidence path (`SEALED_FRAGMENTS`). No symbolic link
    anywhere in it. Its files must be exactly the declared ones, each at its
    declared size and sha256. `SpecRefused` otherwise; nothing is sent."""
    declared = spec.document["uploads"]
    if not declared:
        if directory is not None:
            raise SpecRefused("spec_uploads", "the spec declares no uploads")
        return {}
    if directory is None or not Path(directory).is_dir():
        raise SpecRefused("uploads_missing", "run --uploads DIR")
    directory = Path(directory)
    real = directory.resolve()
    allowed = [Path(r).resolve() for r in roots]
    if not any(real == r or real.is_relative_to(r) for r in allowed):
        raise SpecRefused("uploads_root_not_allowed", str(real))
    if _sealed(real) or any(_sealed(r) for r in allowed):
        raise SpecRefused("uploads_sealed_path", str(real))
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise SpecRefused("uploads_symlink", str(path.relative_to(directory)))
        if _sealed(path.resolve()) or not path.resolve().is_relative_to(real):
            raise SpecRefused("uploads_sealed_path", str(path.relative_to(directory)))
    if uploads_manifest(directory) != declared:
        raise SpecRefused("uploads_differ", "the directory is not the spec's uploads")
    files = {path: (directory / path).read_bytes() for path in declared}
    for path, body in files.items():  # read once more: the bytes that are sent
        want = declared[path]
        if (
            len(body) != want["bytes"]
            or hashlib.sha256(body).hexdigest() != want["sha256"]
        ):
            raise SpecRefused("uploads_differ", path)
    return files


def require_enabled(key_file):
    """The owner's enabling file beside the key file: `run` spends only when it
    says `"enabled": true`, and uploads come only from its `upload_roots`
    (absolute, or `~user/...`, expanded here). Missing or malformed:
    `SpecRefused("pod_jobs_not_enabled")`."""
    path = Path(key_file).expanduser().parent / ENABLE_FILE
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError):
        raise SpecRefused("pod_jobs_not_enabled", str(path)) from None
    if type(document) is not dict or document.get("enabled") is not True:
        raise SpecRefused("pod_jobs_not_enabled", str(path))
    roots = document.get("upload_roots")
    if type(roots) is not list or not all(type(r) is str for r in roots):
        raise SpecRefused("pod_jobs_not_enabled", str(path))
    expanded = [str(Path(r).expanduser()) for r in roots]
    if not all(Path(r).is_absolute() for r in expanded) or any(
        _sealed(r) for r in expanded
    ):
        raise SpecRefused("pod_jobs_not_enabled", str(path))
    return expanded


# -- one job end to end ---------------------------------------------------------------------
RECONCILE = (
    "python -m scripts.dev.exam_design.runpod.operator_compute reconcile "
    "--root ROOT/compute --runpod-key-file KEY"
)


def run(spec, out, *, backend, ledger=None, private=None, uploads=None):
    """Claim, launch, upload, wait, fetch, terminate and settle one job.

    Returns the receipt, always written to `out/receipt.json` whatever fails.
    `receipt["ok"]` is True only for a finished job whose pod (and every
    duplicate an ambiguous create made) is confirmed gone and whose cost is
    settled. A pod whose teardown is not confirmed keeps its full reservation
    in the ledger and the receipt names the reconcile to run."""
    from carbon.agent_campaign import grant_runs

    ledger = grant_runs if ledger is None else ledger
    if not all(hasattr(ledger, f) for f in ("claim_pod_job", "settle_pod_job")):
        raise SpecRefused("pod_job_grant_unavailable", "grant_runs has no pod_job kind")
    # The owner's switch, read again now: off (or gone since the backend was
    # built) refuses before any claim or provider call.
    roots = require_enabled(backend.key_file)
    files_in = read_uploads(spec, uploads, roots)  # only from the allow-list
    out = pods.private_dir(out)
    private = pods.private_dir(private or out / "private")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "job": backend.describe(),
        "grant": GRANT_ID,
        "outcome": None,
        "pod_id": None,
        "rate_usd_per_hr": None,
        "files": {},
        "errors": [],
        "teardown": None,
        "duplicates": [],
        "cost": None,
        "ok": False,
    }
    ledger.claim_pod_job(spec.job_id, backend.money["cap_usd"])
    handle, executed = None, False
    try:
        try:
            handle = backend.launch_job(private)
        except PodFailure as failure:
            executed = failure.executed
            receipt["outcome"] = "launch_refused:" + pods.refusal_code(failure.detail)
            receipt["refusal"] = pods.bounded_detail(failure.detail)
        if handle is not None:
            executed = True
            receipt["pod_id"] = handle.pod_id
            receipt["rate_usd_per_hr"] = handle.rate_usd_per_hr
            deadline = backend.clock() + (spec.minutes + EXPORT_MINUTES) * 60
            if files_in:
                backend.upload(handle, files_in, deadline=deadline)
                receipt["uploads"] = {
                    path: spec.document["uploads"][path]["sha256"]
                    for path in sorted(files_in)
                }
            state = backend.wait(handle, deadline=deadline, cancelled=lambda: False)
            receipt["outcome"] = state
            if state in ("done", "failed"):
                receipt["files"] = _keep(backend.fetch(handle), out / "files")
    except Exception as error:  # noqa: BLE001 -- recorded, then torn down
        if handle is not None or _maybe_created(error):
            executed = True
        receipt["errors"].append(_error("run", error))
        receipt["outcome"] = receipt["outcome"] or "error"
    finally:
        _finish(receipt, ledger, spec, backend, handle, executed, private, out)
    return receipt


def _maybe_created(error):
    """Whether an error during the launch may have followed a create: anything
    but a typed failure that says nothing ran."""
    return not (isinstance(error, PodFailure) and not error.executed)


def _error(stage, error):
    return {"stage": stage, "detail": pods.bounded_detail(repr(error))}


def _finish(receipt, ledger, spec, backend, handle, executed, private, out):
    """Teardown, duplicates and settlement, each guarded so the receipt is
    always written."""
    try:
        receipt["teardown"], handle = _teardown(
            backend, handle, executed, spec, private
        )
    except Exception as error:  # noqa: BLE001
        receipt["errors"].append(_error("teardown", error))
        receipt["teardown"] = {"pod": receipt["pod_id"], "terminated": None}
    if executed:
        try:
            receipt["duplicates"] = _duplicates(backend, spec)
        except Exception as error:  # noqa: BLE001
            receipt["errors"].append(_error("duplicates", error))
            receipt["duplicates"] = None
    try:
        receipt["cost"] = _settle(ledger, spec, backend, handle, executed, receipt)
    except Exception as error:  # noqa: BLE001 -- the claim stays at its cap
        receipt["errors"].append(_error("settle", error))
    try:
        receipt["weekly"] = ledger.weekly_line(ledger.weekly_report())
    except Exception as error:  # noqa: BLE001
        receipt["errors"].append(_error("weekly", error))
    gone = (receipt["teardown"] or {}).get("terminated") is True
    duplicates_gone = receipt["duplicates"] is not None and all(
        row["terminated"] is True for row in receipt["duplicates"]
    )
    if not (gone and duplicates_gone):
        receipt["reconcile"] = RECONCILE
    receipt["ok"] = (
        receipt["outcome"] == "done"
        and gone
        and duplicates_gone
        and receipt["cost"] is not None
        and not receipt["errors"]
    )
    (Path(out) / "receipt.json").write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    )


def _keep(files, directory):
    kept = {}
    for path, body in sorted(files.items()):
        if not _repo_path(path):
            raise PodFailure("fetch", "unsafe result path", executed=True)
        target = Path(directory) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        kept[path] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    return kept


def _teardown(backend, handle, executed, spec, private):
    """(record, handle). No create: nothing to tear down. A create that may
    have happened with no handle: recovered by its ownership tag first; when
    that cannot say, `terminated` is None (unknown), never True."""
    if handle is None and not executed:
        record = {"pod": None, "terminated": True, "note": "refused before any create"}
        return record, None
    if handle is None:
        try:
            handle = backend.recover(spec.job_id, private)
        except PodFailure as failure:
            record = {
                "pod": None,
                "terminated": None,
                "note": "the create may have happened; recover could not say: "
                + pods.bounded_detail(failure.detail),
            }
            return record, None
        if handle is None:
            return {"pod": None, "terminated": True, "note": "no pod exists"}, None
    gone = backend.terminate(handle) is True
    record = {
        "pod": handle.pod_id,
        "terminated": gone,
        "verified": "deletion verified by the pod's absence" if gone else None,
        "at_unix": int(backend.clock()),
    }
    return record, handle


def _duplicates(backend, spec):
    """Every further pod an ambiguous create made under this job's tag (#1068,
    #1178): terminated, each with its provider charge when known."""
    found = []
    for row in backend.duplicates(spec.job_id):
        gone = backend.terminate(PodHandle(spec.job_id, row["pod_id"], None))
        found.append(
            {
                "pod_id": row["pod_id"],
                "charge_usd": row["charge_usd"],
                "terminated": gone is True,
            }
        )
    return found


def _settle(ledger, spec, backend, handle, executed, receipt):
    """`grant_runs.settle_pod_job(cost, pending)`: cost is the total, pending the part
    still at a pod reservation. A refusal before any provider write settles at
    zero. A pod (or a duplicate) with no provider charge, or not confirmed
    gone, stays at its full reservation."""
    if not executed:
        ledger.settle_pod_job(spec.job_id, Decimal(0))
        return {"reserved_usd": "0", "charged_usd": "0", "pending_usd": "0"}
    reserved = backend.money["worst_case_usd"]
    charged, pending = Decimal(0), Decimal(0)
    confirmed = (receipt["teardown"] or {}).get("terminated") is True
    charge = None
    if handle is not None and confirmed:
        try:
            charge = backend.charge(handle)
        except Exception as error:  # noqa: BLE001 -- unknown: the reservation stays
            receipt["errors"].append(_error("charge", error))
    if charge is None:
        pending += reserved
    else:
        charged += charge
    duplicates = receipt["duplicates"]
    if duplicates is None:  # unknown: one more reservation, conservatively
        pending += reserved
    for row in duplicates or ():
        if row["charge_usd"] is None or row["terminated"] is not True:
            pending += reserved
        else:
            charged += Decimal(row["charge_usd"])
    total = charged + pending
    ledger.settle_pod_job(spec.job_id, total, pending_usd=pending)
    return {
        "reserved_usd": str(reserved),
        "charged_usd": str(charged),
        "pending_usd": str(pending),
        "total_usd": str(total),
    }


# -- the no-spend check ---------------------------------------------------------------------
class _MemoryInputs:
    """A pod's input door in memory, for `check`: it waits until every declared
    input has arrived at its declared size and sha256, and reads the request
    path as the real door does (`bootstrap.receive`: no decoding)."""

    def __init__(self, account, declared):
        self.account, self.declared, self.received = account, declared, {}

    def http(self, url, token, timeout):
        if url.endswith("/status") and len(self.received) < len(self.declared):
            return 200, b'{"stage": "waiting_inputs"}'
        return self.account.http(url, token, timeout)

    def post(self, url, token, body, timeout):
        path = url.split("/input/", 1)[1]
        want = self.declared.get(path)
        if want is None:
            return 404
        if (
            len(body) != want["bytes"]
            or hashlib.sha256(body).hexdigest() != want["sha256"]
        ):
            return 409
        self.received[path] = body
        return 200


def check(spec, root, *, repository=REPOSITORY, files=None, uploads=None, account=None):
    """`run` against an in-memory RunPod and the real ledger (`grant_runs`) in a
    ledger directory of its own under `root`: the real launch, upload, wait,
    fetch, terminate and settle code, no network and no spend. The uploads
    directory is its own allow-list root here; the sealed-path guard applies."""
    import os

    from carbon.agent_campaign import grant_runs

    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("the check's root must be new or empty")
    root = pods.private_dir(root)
    key = root / "runpod-key"
    key.write_text(pods.CHECK_KEY + "\n")
    key.chmod(0o600)
    # The check's own switch: its uploads directory is its only allowed root.
    (root / ENABLE_FILE).write_text(
        json.dumps(
            {"enabled": True, "upload_roots": [str(Path(uploads or root).resolve())]}
        )
    )
    account = account or pods.InMemoryRunPod()
    if files is not None:
        account.FILES = files
    door = _MemoryInputs(account, spec.document["uploads"])
    backend = JobPods(
        spec,
        root=root / "pods",
        key_file=key,
        repository=repository,
        transport=account.transport,
        http=door.http,
        post=door.post,
        sleep=lambda _seconds: None,
        balance_floor=lambda: Decimal(0),
    )
    previous = os.environ.get(grant_runs.ENV)
    os.environ[grant_runs.ENV] = str(root / "ledger")
    try:
        receipt = run(
            spec,
            root / "out",
            backend=backend,
            ledger=grant_runs,
            uploads=uploads,
        )
        weekly = grant_runs.ledger_dir() / grant_runs.WEEKLY_FILE
        ledger = [json.loads(x) for x in weekly.read_text().splitlines() if x]
    finally:
        if previous is None:
            os.environ.pop(grant_runs.ENV, None)
        else:
            os.environ[grant_runs.ENV] = previous
    return {
        "receipt": receipt,
        "ledger": ledger,
        "creates": list(account.creates),
        "pods_left": sorted(account.pods),
        "received": sorted(door.received),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.agent_campaign.pod_jobs")
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("uploads", help="print a directory's `uploads` field")
    manifest.add_argument("directory", type=Path)
    for name in ("plan", "check", "run"):
        command = sub.add_parser(name)
        command.add_argument("spec", type=Path)
        if name != "plan":
            command.add_argument("--uploads", type=Path)
        if name == "check":
            command.add_argument("--root", type=Path, required=True)
        if name == "run":
            command.add_argument("--out", type=Path, required=True)
            command.add_argument("--key-file", type=Path, required=True)
            command.add_argument(
                "--root",
                type=Path,
                default=Path("~/.local/state/carbon/pod-jobs").expanduser(),
            )
    args = parser.parse_args(argv)
    from carbon.agent_campaign import grant_runs

    if args.command == "uploads":
        print(json.dumps(uploads_manifest(args.directory), indent=1, sort_keys=True))
        return 0
    try:
        spec = load_spec(json.loads(args.spec.read_text()))
        if args.command == "plan":
            ships = ship_list(spec)
            result = {
                "job_id": spec.job_id,
                "spec_digest": spec.digest(),
                "files": len(ships),
                **{k: str(v) for k, v in spec.economics().items()},
            }
        elif args.command == "check":
            result = check(spec, args.root, uploads=args.uploads)
        else:
            roots = require_enabled(args.key_file)  # the owner's switch first
            read_uploads(spec, args.uploads, roots)  # before the backend is built
            backend = JobPods(spec, root=args.root, key_file=args.key_file)
            assert backend.upload_roots == roots
            result = run(spec, args.out, backend=backend, uploads=args.uploads)
    except SpecRefused as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2
    except grant_runs.SharedRunsError as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2
    print(json.dumps(result, indent=1, sort_keys=True, default=str))
    receipt = result.get("receipt", result) if args.command != "plan" else {"ok": True}
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
