"""Carbon's pod runner for Graphite phase 3: one proposal, one RunPod pod.

The agent never holds a pod key. Carbon's runner launches every pod (plan §2,
rule 3), the way EV4 did (`scripts/dev/exam_design/runpod/pod_control.py`):

- the EV4 study image, pinned by digest (`pod_control.IMAGE`), on one A40
  Secure pod at no more than `pod_control.MAX_RATE` an hour;
- **a hash-pinned code ship**: the pod fetches every shipped file from GitHub
  at a pushed commit and refuses any whose sha256 differs from the manifest
  (`bootstrap.py`). The manifest is the same sha256-per-file map
  `pod_control.code_manifest` builds;
- the pod runs one phase, `graphite_practice` (`pod_phase.py`), and serves its
  output files by token; Carbon fetches them file by file, each checked
  against its listed sha256 (`pod_control.fetch_files`);
- the pod is terminated and its absence verified, whether the job succeeded
  or not, as EV4 did.

The lifecycle runs on Carbon's operator RunPod layer
(`scripts/dev/exam_design/runpod/operator_compute`, GRAPHITE-D32): `ComputeService`
with the `RunPodAdapter` (whose request shapes come from `pod_control`), on
Carbon's own account only, never a miner's key (OWNER-MINER-COMPUTE-LINK-ONLY-01,
LINKONLY-D1). That gives each pod a durable intent
before the create call, an ownership tag that resolves a lost create response
without resending it, a balance observation before any create, a rate ceiling
and deadline bound, verified termination, and the provider's own charge when it
reports one.

`ScriptedPods` is the deterministic stand-in for tests and `--dry-run`: a
scripted pod lifecycle with rates, charges, failures and process deaths. It
creates nothing and spends nothing. It never touches the operator layer, so
`real_path_check` drives the live backend itself, with only RunPod in memory
(`InMemoryRunPod`), across the threads a live session uses: a dry run that
only scripts pods could not see a defect in that layer (POD-STORE-THREADS-01).

**Prices are not invented here.** The hourly rate ceiling and the disk price
are pod_control's (EV4's ledger records `costPerHr` 0.49 on every pod it
created), and the cleanup reserve is pod_control's `CLEANUP_RESERVE_USD`.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Protocol

REPOSITORY = Path(__file__).resolve().parents[3]
PHASE = "graphite_practice"
#: The data files the pod's phase reads, beside the `carbon` package and the
#: pod tooling. Public development material only: TRAIN v1, the OCV table and
#: the public PRACTICE records. Each is pinned again by its own digest when the
#: phase loads it (`carbon.battery.challenge`, `carbon.battery.practice`).
DATA_PATHS = (
    "docs/development/evidence/exam-design-2026-09-24/datasets/train-v1.jsonl.gz",
    "docs/development/evidence/exam-design-2026-09-24/ocv_table.json",
    "docs/development/evidence/exam-design-2026-09-24/refs-a-part2/out/records.jsonl",
)
#: Never shipped to a pod, whatever a path list says (lower-case fragments).
FORBIDDEN_DATA = ("ev4", "confirmation", "private", "secret", "credential", "canary")
SHIP_TREES = ("carbon", "scripts/dev/exam_design")
#: Engineering allowances per proposal, each taken from an existing record
#: (GRAPHITE-D20): the pod's start-up allowance is the rented runner's
#: (`RentedCompute.startup_seconds`, 900 s); the job's own allowance is the
#: battery contract's worker deadline (`envelope.worker_deadline_seconds`,
#: 600 s); the export window is pod_control's default (`--export-minutes 5`).
STARTUP_MINUTES = 15
EXPORT_MINUTES = 5
POLL_SECONDS = 15.0


def contract_work_seconds():
    """The battery contract's worker deadline: the job's own allowance."""
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE, contract

    envelope = dict(contract(BATTERY_CHALLENGE).envelope)
    seconds = envelope["worker_deadline_seconds"]
    if type(seconds) is not int or seconds <= 0:
        raise ValueError("the battery contract states no worker deadline")
    return seconds


def proposal_minutes():
    """A pod's full lifetime for one proposal: start-up, the job, export."""
    return STARTUP_MINUTES + -(-contract_work_seconds() // 60) + EXPORT_MINUTES


def prices():
    """The EV4 pod economics, read from pod_control (never restated here)."""
    from scripts.dev.exam_design.runpod import pod_control

    rate = Decimal(str(pod_control.MAX_RATE))
    disk = (
        Decimal(pod_control.DISK_GB)
        * Decimal(str(pod_control.DISK_USD_PER_GB_MONTH))
        / Decimal(730)
    )
    return {
        "image": pod_control.IMAGE,
        "gpu": pod_control.GPU,
        "rate_ceiling_usd_per_hr": rate,
        "disk_gb": pod_control.DISK_GB,
        "disk_usd_per_gb_month": Decimal(str(pod_control.DISK_USD_PER_GB_MONTH)),
        "disk_usd_per_hr": disk,
        "hourly_usd": rate + disk,
        "cleanup_reserve_usd": Decimal(str(pod_control.CLEANUP_RESERVE_USD)),
        "basis": (
            "scripts/dev/exam_design/runpod/pod_control.py: MAX_RATE, DISK_GB, "
            "DISK_USD_PER_GB_MONTH, CLEANUP_RESERVE_USD; the EV4 ledger records "
            "costPerHr 0.49 on each pod it created. The account balance floor is "
            "operator configuration, never committed (POD-LEDGER-PRIVATE-01): "
            "`operator_balance_floor`"
        ),
    }


def operator_balance_floor():
    """The account balance floor from the operator's private configuration,
    `~/.runpod/campaigns.json` (`balance_floor_usd`), the file pod_control's
    `operator_limits` reads (POD-LEDGER-PRIVATE-01). Read only when a pod is
    about to be launched, and never recorded. A missing or invalid value
    refuses the launch: nothing spends under a floor nobody set."""
    import math

    from scripts.dev.exam_design.runpod import pod_control

    path = Path(pod_control.STATE_DIR) / pod_control.OPERATOR_CONFIG
    try:
        floor = json.loads(path.read_text()).get("balance_floor_usd")
    except (OSError, ValueError, AttributeError):
        floor = None
    if (
        not isinstance(floor, (int, float))
        or isinstance(floor, bool)
        or not math.isfinite(floor)
        or floor < 0
    ):
        raise PodFailure(
            "launch",
            "no balance_floor_usd in the operator configuration "
            "(~/.runpod/campaigns.json)",
            executed=False,
        )
    return Decimal(str(floor))


def cents_up(amount):
    return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_CEILING)


NANODOLLAR = Decimal("0.000000001")


def pod_reservation(minutes, hourly):
    """What one pod may cost: its full deadline at the rate ceiling plus disk,
    as pod_control's `pod_cost_usd` computes it, rounded up to the
    nanodollar (the unit every Graphite ledger meters in)."""
    exact = (Decimal(minutes) / Decimal(60)) * Decimal(hourly)
    return exact.quantize(NANODOLLAR, rounding=ROUND_CEILING)


class PodFailure(RuntimeError):
    """A pod step failed. `executed` says whether anything may have been created
    or charged: False only when the failure precedes any provider write."""

    def __init__(self, stage, detail, *, executed):
        super().__init__(f"{stage}: {detail}")
        self.stage, self.detail, self.executed = stage, detail, executed


@dataclass(frozen=True)
class PodJob:
    """One proposal's pod job. Everything here is Carbon's, never the agent's
    text: the compiled strategy, the contract it compiled under, the practice
    randomness and the digests the pod must reproduce before it runs."""

    intent_id: str
    strategy: dict
    contract_digest: str
    seed: int
    expected: dict
    minutes: int
    seconds: int

    def config(self, stop_admitting_epoch):
        return {
            "strategy": self.strategy,
            "contract_digest": self.contract_digest,
            "seed": self.seed,
            "expected": self.expected,
            "seconds": self.seconds,
            "stop_admitting_epoch": stop_admitting_epoch,
        }


@dataclass(frozen=True)
class PodHandle:
    intent_id: str
    pod_id: str
    rate_usd_per_hr: str | None

    def record(self):
        return {
            "intent_id": self.intent_id,
            "pod_id": self.pod_id,
            "rate_usd_per_hr": self.rate_usd_per_hr,
        }


class PodBackend(Protocol):
    name: str

    def describe(self) -> dict: ...

    def launch(self, job: PodJob, private: Path) -> PodHandle: ...

    def wait(self, handle: PodHandle, *, deadline: float, cancelled) -> str: ...

    def fetch(self, handle: PodHandle) -> dict: ...

    def terminate(self, handle: PodHandle) -> bool: ...

    def charge(self, handle: PodHandle) -> Decimal | None: ...

    def recover(self, intent_id: str, private: Path) -> PodHandle | None:
        """The pod an uncertain create made; None only when none exists."""
        ...


# -- the hash-pinned code ship -------------------------------------------------------------
def tracked(ref, prefixes, repository=REPOSITORY):
    """Every tracked file under each prefix at `ref` (pod_control.ship_paths)."""
    out = []
    for prefix in prefixes:
        files = subprocess.run(
            ["git", "-C", str(repository), "ls-tree", "-r", "--name-only", ref, "--"]
            + [prefix],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if not files:
            raise PodFailure("ship", f"nothing tracked under {prefix}", executed=False)
        out += files
    return out


def code_manifest(ref, paths, repository=REPOSITORY):
    """sha256 of each path's bytes at `ref`: `pod_control.code_manifest`, read
    through one `git cat-file --batch` process instead of one per file."""
    request = "".join(f"{ref}:{path}\n" for path in paths).encode()
    result = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "--batch"],
        input=request,
        capture_output=True,
        check=True,
    ).stdout
    manifest, offset = {}, 0
    for path in paths:
        end = result.index(b"\n", offset)
        header = result[offset:end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise PodFailure("ship", f"{path} is not a blob at {ref}", executed=False)
        size = int(header[2])
        body = result[end + 1 : end + 1 + size]
        manifest[path] = hashlib.sha256(body).hexdigest()
        offset = end + 1 + size + 1
    return manifest


def ship_list(ref, repository=REPOSITORY):
    for path in DATA_PATHS:
        if any(fragment in path.lower() for fragment in FORBIDDEN_DATA):
            raise PodFailure("ship", "forbidden data path " + path, executed=False)
    paths = tracked(ref, SHIP_TREES, repository) + list(DATA_PATHS)
    return list(dict.fromkeys(paths))


def manifest_digest(manifest):
    """The digest pod_control records as `code_manifest_sha256`."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


# -- the live backend ----------------------------------------------------------------------
class RunPodPods:
    """RunPod pods on Carbon's account through the operator layer (`operator_compute`).

    `key_file` is an owner-only file holding the RunPod key; the adapter reads
    it per request, into its own request header only. Nothing here prints,
    logs or stores the key.
    """

    name = "runpod"
    CAMPAIGN = "graphite-phase3"

    def __init__(
        self,
        *,
        root,
        key_file,
        code_ref,
        repository=REPOSITORY,
        clock=time.time,
        sleep=time.sleep,
        http=None,
        transport=None,
        balance_floor=operator_balance_floor,
    ):
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeService,
            ComputeStore,
            FileCredentialProvider,
            RunPodAdapter,
            UrllibTransport,
        )

        if type(code_ref) is not str or len(code_ref) != 40:
            raise PodFailure(
                "ship", "a 40-hex pushed commit is required", executed=False
            )
        self.economics = prices()
        self.repository, self.code_ref = Path(repository), code_ref
        self.clock, self.sleep = clock, sleep
        self.balance_floor = balance_floor
        self.http = http or _https_get
        self._record_lock = threading.Lock()
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.store = ComputeStore(root / "compute", clock=clock)
        if self.store.campaign_status(self.CAMPAIGN) is None:
            self.store.start_campaign(self.CAMPAIGN)
        self.adapter = RunPodAdapter(
            FileCredentialProvider(Path(key_file)),
            transport or UrllibTransport(),
            clock=clock,
            sleep=sleep,
        )
        self.service = ComputeService(self.store, self.adapter, clock=clock)
        self._tokens = {}
        paths = ship_list(code_ref, self.repository)
        self.manifest = code_manifest(code_ref, paths, self.repository)
        self.boot = (
            self.repository / "scripts/dev/exam_design/runpod/bootstrap.py"
        ).read_text()

    def describe(self):
        return {
            "backend": self.name,
            "image": self.economics["image"],
            "gpu": self.economics["gpu"],
            "rate_ceiling_usd_per_hr": str(self.economics["rate_ceiling_usd_per_hr"]),
            "code_ref": self.code_ref,
            "code_files": len(self.manifest),
            "code_manifest_sha256": manifest_digest(self.manifest),
            "phase": PHASE,
        }

    def _env(self, job, record):
        from scripts.dev.exam_design.runpod import pod_control

        stop = record["deadline_at"] - EXPORT_MINUTES * 60
        env = {
            "PROBE_TOKEN": record["token"],
            "PROBE_DEADLINE": str(int(record["deadline_at"] + 60)),
            "PROBE_CA_GZ_B64": _ca_bundle(),
            "CODE_REF": self.code_ref,
            **pod_control.manifest_env(self.manifest),
            "PHASE": PHASE,
            "PHASE_CONFIG": json.dumps(job.config(stop), sort_keys=True),
            # EV4's GPU settings (`--jax-platform cuda,cpu --pinned-xla`).
            "JAX_PLATFORMS": "cuda,cpu",
            "XLA_FLAGS": "--xla_gpu_deterministic_ops=true "
            "--xla_gpu_exclude_nondeterministic_ops=true --xla_gpu_autotune_level=0",
            "NVIDIA_TF32_OVERRIDE": "0",
            "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
            "JAX_DEFAULT_MATMUL_PRECISION": "highest",
            "JAX_ENABLE_COMPILATION_CACHE": "false",
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        }
        return tuple(sorted(env.items()))

    def _record(self, job, private):
        """The job's token and deadline, fixed once before any provider call,
        so a restart re-derives the same create request (`RentedRunner`)."""
        from carbon.development_session.data import write_once

        path = Path(private) / "pod-job.json"
        # One writer at a time: a second thread launching the same job reads
        # the first one's record, never a half-written or rival one.
        with self._record_lock:
            if not path.exists():
                write_once(
                    path,
                    json.dumps(
                        {
                            "intent_id": job.intent_id,
                            "token": secrets.token_urlsafe(24),
                            "deadline_at": int(self.clock() + job.minutes * 60),
                        },
                        sort_keys=True,
                    ).encode(),
                )
            record = json.loads(path.read_bytes())
        if record["intent_id"] != job.intent_id:
            raise PodFailure("launch", "pod job record conflict", executed=False)
        return record

    def launch(self, job, private):
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeError,
            Execution,
            PodSpec,
            ProvisionRequest,
        )

        economics = self.economics
        record = self._record(job, private)
        try:
            balance, _ = self.service.observe_balance(self.CAMPAIGN)
            cost = pod_reservation(job.minutes, economics["hourly_usd"])
            if Decimal(str(balance)) - cost < self.balance_floor():
                raise PodFailure(
                    "launch", "balance would fall below the floor", executed=False
                )
            [offer] = self.adapter.offers([economics["gpu"]], gpu_count=1)
            if (
                offer.usd_per_hr is None
                or Decimal(str(offer.usd_per_hr)) > economics["rate_ceiling_usd_per_hr"]
                or not offer.stock_status
            ):
                raise PodFailure(
                    "launch",
                    "no A40 Secure pod at or below the rate ceiling now",
                    executed=False,
                )
            spec = PodSpec(
                image=economics["image"],
                gpu_type_id=economics["gpu"],
                gpu_count=1,
                cloud_type="SECURE",
                container_disk_gb=economics["disk_gb"],
                ports=("8000/http",),
                env=self._env(job, record),
                max_rate_usd_per_hr=float(economics["rate_ceiling_usd_per_hr"]),
                storage_usd_per_gb_month=float(economics["disk_usd_per_gb_month"]),
                start_command=("/opt/carbon-worker/bin/python", "-I", "-c", self.boot),
            )
            resource = self.service.provision(
                ProvisionRequest(
                    tenant="graphite",
                    miner="graphite",
                    campaign_id=self.CAMPAIGN,
                    intent_id=job.intent_id,
                    spec=spec,
                    deadline_at=float(record["deadline_at"]),
                )
            )
        except ComputeError as failure:
            raise PodFailure(
                "launch",
                failure.failed,
                executed=failure.execution is not Execution.NOT_EXECUTED,
            ) from None
        self._tokens[job.intent_id] = record["token"]
        return PodHandle(
            job.intent_id, resource.resource_id, _rate(resource.rate_usd_per_hr)
        )

    def _owned(self, handle):
        return self.service.owned(self.CAMPAIGN, handle.intent_id, handle.pod_id)

    def _get(self, handle, path, timeout=60):
        token = self._token(handle)
        base = self.adapter.connect_url(self._owned(handle), 8000)
        return self.http(base + path, token, timeout)

    def _token(self, handle):
        token = self._tokens.get(handle.intent_id)
        if not token:
            # Only the process that launched a pod reads it; after a restart a
            # pod is terminated, never read (no result is trusted across one).
            raise PodFailure("status", "pod token unavailable", executed=True)
        return token

    def recover(self, intent_id, private):
        """A pod whose create may have happened: adopted by its ownership tag
        (`ComputeService.recover`), never created again.

        None means no pod exists for the intent, definitively: it was never
        dispatched, or the compute layer settled it `NOT_FOUND` after its
        grace period. `PodFailure` means it cannot yet say."""
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeError,
            IntentState,
        )

        intent = self.store.intent(self.CAMPAIGN, intent_id)
        if intent is None or intent.state in (
            IntentState.REQUESTED,
            IntentState.CANCELLED,
            IntentState.REJECTED,
            IntentState.NOT_FOUND,
        ):
            return None
        try:
            resource = self.service.recover(intent)
        except ComputeError as failure:
            if not failure.resources_may_remain:
                return None
            raise PodFailure("recover", failure.failed, executed=True) from None
        return PodHandle(
            intent_id, resource.resource_id, _rate(resource.rate_usd_per_hr)
        )

    def wait(self, handle, *, deadline, cancelled):
        while True:
            if cancelled():
                return "cancelled"
            if self.clock() >= deadline:
                return "timeout"
            code, body = self._get(handle, "/status")
            if code == 200:
                try:
                    stage = json.loads(body).get("stage")
                except ValueError:
                    stage = None
                if stage == "done":
                    return "done"
                if stage in ("phase_failed", "bootstrap_failed"):
                    return "failed"
            self.sleep(POLL_SECONDS)

    def fetch(self, handle):
        from scripts.dev.exam_design.runpod import pod_control

        code, body = self._get(handle, "/files")
        if code != 200:
            raise PodFailure("fetch", f"listing failed ({code})", executed=True)
        listing = json.loads(body)
        files = {}

        def get(path):
            status, data = self._get(handle, "/file/" + urllib.parse.quote(path), 600)
            return status, data

        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            try:
                pod_control.fetch_files(listing, get, directory)
            except SystemExit as refused:
                raise PodFailure("fetch", str(refused), executed=True) from None
            for row in listing:
                files[row["path"]] = (Path(directory) / row["path"]).read_bytes()
        return files

    def terminate(self, handle):
        from scripts.dev.exam_design.runpod.operator_compute import ComputeError

        try:
            self.service.terminate(self.CAMPAIGN, handle.intent_id, handle.pod_id)
        except ComputeError:
            return False
        return True

    def charge(self, handle):
        from scripts.dev.exam_design.runpod.operator_compute import ComputeError

        try:
            charge = self.adapter.provider_charge(self._owned(handle))
        except ComputeError:
            return None
        return None if charge is None else Decimal(str(charge.amount_usd))


def _rate(rate):
    return None if rate is None else str(Decimal(str(rate)))


def _ca_bundle():
    """pod_control's CA bundle, gzipped with no timestamp: the same bundle
    gives the same bytes, so a replayed launch of one job makes the same
    create request (its digest) in any second, and is never refused as a
    different request."""
    import base64
    import gzip

    from scripts.dev.exam_design.runpod import pod_control

    pem = gzip.decompress(base64.b64decode(pod_control.ca_bundle_gz_b64()))
    return base64.b64encode(gzip.compress(pem, 9, mtime=0)).decode()


def _https_get(url, token, timeout):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url, headers={"X-Probe-Token": token, "User-Agent": "carbon-graphite/1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, b""
    except Exception:  # noqa: BLE001 -- an unreachable pod is a typed status
        return 0, b""


# -- the scripted stand-in -----------------------------------------------------------------
@dataclass
class Step:
    """One scripted pod: what the provider and the job do.

    - `outcome`: "done", "failed" or "timeout" (the job's end);
    - `outputs`: a callable `(job) -> {name: bytes}` for the exported files;
    - `rate`: the provider-reported hourly rate; `charge`: the provider's
      reported charge for the pod, or None (unresolved);
    - `launch`: None, "refused" (definitive, nothing created), "ambiguous"
      (the create's answer was lost; the pod exists) or "lost" (the answer
      was lost; no pod exists);
    - `terminate_failures`: deletes that do not take before one does;
    - `hook`: a callable run while the job runs (for example to cancel);
    - `crash`: "wait" or "fetch" to die there, leaving the pod alive.
    """

    outcome: str = "done"
    outputs: object = None
    rate: str = "0.49"
    charge: str | None = "0.10"
    launch: str | None = None
    terminate_failures: int = 0
    hook: object = None
    crash: str | None = None


@dataclass
class ScriptedPods:
    """A deterministic pod account. It runs no code and spends nothing."""

    steps: list = field(default_factory=list)
    name: str = "scripted"
    launched: list = field(default_factory=list)
    alive: dict = field(default_factory=dict)
    terminated: list = field(default_factory=list)
    deletes: int = 0

    def describe(self):
        return {
            "backend": self.name,
            "image": "scripted-no-image",
            "gpu": "scripted-no-gpu",
            "code_ref": "scripted",
            "code_manifest_sha256": "scripted",
            "phase": PHASE,
            "synthetic": True,
        }

    def _step(self, intent_id):
        index = [i for i, _ in self.launched].index(intent_id)
        return self.steps[index] if index < len(self.steps) else Step()

    def launch(self, job, private):
        if job.intent_id in [i for i, _ in self.launched]:
            raise AssertionError("a pod job was launched twice: " + job.intent_id)
        self.launched.append((job.intent_id, job))
        step = self._step(job.intent_id)
        if step.launch == "refused":
            raise PodFailure("launch", "scripted refusal", executed=False)
        if step.launch == "lost":
            # The create's answer was lost and no pod exists.
            raise PodFailure("launch", "scripted lost create", executed=True)
        pod_id = "pod" + hashlib.sha256(job.intent_id.encode()).hexdigest()[:12]
        self.alive[pod_id] = {"intent_id": job.intent_id, "job": job, "failures": 0}
        if step.launch == "ambiguous":
            raise PodFailure("launch", "scripted ambiguous create", executed=True)
        return PodHandle(job.intent_id, pod_id, step.rate)

    def recover(self, intent_id, private):
        for pod_id, pod in self.alive.items():
            if pod["intent_id"] == intent_id:
                return PodHandle(intent_id, pod_id, self._step(intent_id).rate)
        return None

    def wait(self, handle, *, deadline, cancelled):
        step = self._step(handle.intent_id)
        if step.hook is not None:
            step.hook()
        if step.crash == "wait":
            from ..controller import SimulatedCrash

            raise SimulatedCrash("pod wait")
        if cancelled():
            return "cancelled"
        return step.outcome

    def fetch(self, handle):
        step = self._step(handle.intent_id)
        if step.crash == "fetch":
            from ..controller import SimulatedCrash

            raise SimulatedCrash("pod fetch")
        job = self.alive[handle.pod_id]["job"]
        return dict(step.outputs(job)) if step.outputs else {}

    def terminate(self, handle):
        self.deletes += 1
        pod = self.alive.get(handle.pod_id)
        if pod is None:
            return True
        step = self._step(handle.intent_id)
        if pod["failures"] < step.terminate_failures:
            pod["failures"] += 1
            return False
        del self.alive[handle.pod_id]
        self.terminated.append(handle.pod_id)
        return True

    def charge(self, handle):
        step = self._step(handle.intent_id)
        return None if step.charge is None else Decimal(step.charge)


#: Synthetic builds already computed (tests and dry runs only).
_SYNTHETIC_BUILDS = {}


def synthetic_outputs(quality, *, root=REPOSITORY, built=None):
    """SYNTHETIC pod outputs for tests and `--dry-run`: nothing is trained.

    The pod "builds" honestly (`pod_phase.built_record`, unless `built`
    overrides it to simulate a mismatch), and its predictions are the public
    PRACTICE references with a deterministic error of size `quality` after the
    initial instant (so no gate fails): lower is better, 0 is exact. They exist
    only to drive Carbon's real scoring and comparison code."""
    import math

    cache = {}

    def outputs(job):
        from carbon.battery.practice import PracticeSet

        from .pod_phase import built_record

        key = (json.dumps(job.strategy, sort_keys=True), job.contract_digest, job.seed)
        if built is not None:
            record = built
        elif key in _SYNTHETIC_BUILDS:
            record = _SYNTHETIC_BUILDS[key]
        else:
            record = built_record(job.strategy, job.contract_digest, job.seed, root)[0]
            _SYNTHETIC_BUILDS[key] = record
        predictions = {}
        records = cache.get("practice")
        if records is None:
            records = cache["practice"] = PracticeSet.load(root).records
        for index, ref in enumerate(records):
            wave = 1.0 + 0.5 * math.sin(index * 0.7)
            out = ref["outputs"]
            predictions[ref["case_id"]] = {
                "voltage_v": out["voltage_v"],
                "temperature_c": [out["temperature_c"][0]]
                + [t + quality * 0.5 * wave for t in out["temperature_c"][1:]],
                "plating_margin_v": out["plating_margin_v"] + quality * 0.002 * wave,
                "capacity_ah": out["capacity_ah"],
            }
        return {
            "built.json": json.dumps(record, sort_keys=True).encode(),
            "predictions.json": json.dumps(predictions).encode(),
            "fit.json": json.dumps({"final_loss": quality, "synthetic": True}).encode(),
            "runtime.json": json.dumps({"synthetic": True}).encode(),
            "DONE.json": b'{"exit": 0, "synthetic": true}',
        }

    return outputs


# -- the real-path check -------------------------------------------------------------------
#: The synthetic key `real_path_check` writes for its in-memory account. It is
#: no credential: nothing it is sent to leaves the process.
CHECK_KEY = "graphite-real-path-check-no-key"
CHECK_SCHEMA = "carbon.graphite.pod-real-path-check.v1"
_REST_PODS = "https://rest.runpod.io/v1/pods"


class InMemoryRunPod:
    """RunPod's REST and GraphQL, and each pod's bootstrap server, in memory,
    for `real_path_check`: the `transport` `RunPodAdapter` sends through and
    the `http` `RunPodPods` reads pods with. No network, no account, no spend.
    Safe to call from several threads at once, as the check does."""

    def __init__(self, *, balance=100.0, rate=0.44, charge=0.07):
        self.balance, self.rate, self.charge = balance, rate, charge
        self.pods, self.creates, self.threads = {}, [], set()
        self._lock = threading.Lock()

    def transport(self, method, url, *, body, headers, timeout):
        if headers.get("Authorization") != "Bearer " + CHECK_KEY:
            raise AssertionError("in-memory RunPod: not the check's synthetic key")
        with self._lock:
            self.threads.add(threading.get_ident())
            status, payload = self._answer(method, url, body)
        return status, json.dumps(payload).encode()

    def _view(self, pod):
        return {key: pod[key] for key in ("id", "name", "desiredStatus", "costPerHr")}

    def _answer(self, method, url, body):
        if url == "https://api.runpod.io/graphql":
            if "clientBalance" in json.loads(body)["query"]:
                return 200, {"data": {"myself": {"clientBalance": self.balance}}}
            price = {"uninterruptablePrice": self.rate, "stockStatus": "High"}
            return 200, {"data": {"gpuTypes": [{"lowestPrice": price}]}}
        if url == _REST_PODS and method == "POST":
            request = json.loads(body)
            pod_id = f"inmemory{len(self.creates):04d}"
            self.creates.append(pod_id)
            self.pods[pod_id] = {
                "id": pod_id,
                "name": request["name"],
                "desiredStatus": "RUNNING",
                "costPerHr": self.rate,
                "env": request["env"],
            }
            return 200, self._view(self.pods[pod_id])
        if url == _REST_PODS and method == "GET":
            return 200, [self._view(pod) for pod in self.pods.values()]
        if url.startswith(_REST_PODS + "/"):
            pod = self.pods.get(url[len(_REST_PODS) + 1 :])
            if pod is None:
                return 404, {"error": "not found"}
            if method == "GET":
                return 200, self._view(pod)
            if method == "DELETE":
                del self.pods[pod["id"]]
                return 200, {}
        if url.startswith("https://rest.runpod.io/v1/billing/pods?"):
            query = urllib.parse.parse_qs(url.split("?", 1)[1])
            return 200, [{"podId": query["podId"][0], "amount": self.charge}]
        return 404, {"error": "not modelled"}

    #: What every in-memory pod exports: a stated synthetic marker, nothing else.
    FILES = {
        "DONE.json": b'{"exit": 0, "synthetic": true}',
        "check.json": b'{"real_path_check": true, "synthetic": true}',
    }

    def http(self, url, token, timeout):
        pod_id = url.split("//", 1)[1].split("-8000.", 1)[0]
        with self._lock:
            pod = self.pods.get(pod_id)
            if pod is None:
                return 0, b""
            if token != pod["env"]["PROBE_TOKEN"]:
                return 403, b""
        path = url.split(".proxy.runpod.net", 1)[1]
        if path == "/status":
            return 200, b'{"stage": "done"}'
        if path == "/files":
            listing = [
                {"path": n, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                for n, b in self.FILES.items()
            ]
            return 200, json.dumps(listing).encode()
        name = urllib.parse.unquote(path.removeprefix("/file/"))
        return (200, self.FILES[name]) if name in self.FILES else (404, b"")


def real_path_check(root, *, code_ref=None, repository=REPOSITORY, launches=2):
    """Drive the live pod backend's real code path with no network and no
    spend, the way a live phase-3 session drives it (POD-STORE-THREADS-01).

    `RunPodPods` (the operator `ComputeStore`, `ComputeService` and
    `RunPodAdapter`) is built on the calling thread, as the phase-3 runner
    builds it on its main thread. Then `launches` pod lifecycles (launch, wait,
    fetch) run at once, each step through `asyncio.to_thread`, as
    `Phase3Tools.call` runs a proposal; the same intents are launched again
    (an idempotent replay sends no second create); every pod is recovered and
    terminated back on the calling thread, as `Experiment.reconcile` and
    cancellation do; charges are read off the thread; and the independent
    reconciler runs on a fresh store. Only RunPod itself is in memory
    (`InMemoryRunPod`).

    `root` must be a new or empty directory. Call it from synchronous code.
    Returns a report with `status` OK or FAILED; it never raises for a failed
    check. The phase-3 dry run runs it, and a pre-live gate can.
    """
    import asyncio

    from scripts.dev.exam_design.runpod.operator_compute import (
        ComputeStore,
        FileCredentialProvider,
        IntentState,
        RunPodAdapter,
        reconcile,
    )

    root = Path(root)
    report = {
        "schema": CHECK_SCHEMA,
        "synthetic": True,
        "network": False,
        "spend_usd": "0",
        "launches": launches,
    }
    try:
        if root.exists() and any(root.iterdir()):
            raise ValueError("the check's root must be new or empty")
        root = private_dir(root)
        if code_ref is None:
            code_ref = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        key = root / "runpod-key"
        key.write_text(CHECK_KEY + "\n")
        key.chmod(0o600)
        account = InMemoryRunPod()
        caller = threading.get_ident()
        backend = RunPodPods(
            root=root / "pods",
            key_file=key,
            code_ref=code_ref,
            repository=repository,
            transport=account.transport,
            http=account.http,
            sleep=lambda _seconds: None,
            balance_floor=lambda: Decimal(0),  # synthetic: the account is in memory
        )
        jobs = [
            PodJob(
                intent_id=f"real-path-check-{index}",
                strategy={"real_path_check": index},
                contract_digest="sha256:" + "0" * 64,
                seed=index,
                expected={"files": {}},
                minutes=30,
                seconds=600,
            )
            for index in range(launches)
        ]
        privates = {
            job.intent_id: private_dir(root / "private" / job.intent_id)
            for job in jobs
        }

        async def lifecycle(job):
            private = privates[job.intent_id]
            handle = await asyncio.to_thread(backend.launch, job, private)
            outcome = await asyncio.to_thread(
                backend.wait, handle, deadline=float("inf"), cancelled=lambda: False
            )
            files = await asyncio.to_thread(backend.fetch, handle)
            return handle, outcome, sorted(files)

        async def replay(job):
            return await asyncio.to_thread(backend.launch, job, privates[job.intent_id])

        async def run_all(step, items):
            return await asyncio.gather(*(step(item) for item in items))

        ran = asyncio.run(run_all(lifecycle, jobs))
        replayed = asyncio.run(run_all(replay, jobs))
        failures = []
        handles = [handle for handle, _outcome, _files in ran]
        if [h.pod_id for h in replayed] != [h.pod_id for h in handles]:
            failures.append("replay_returned_another_pod")
        if len(account.creates) != launches:
            failures.append("creates_not_one_per_intent")
        if any(outcome != "done" for _h, outcome, _f in ran):
            failures.append("a_pod_did_not_finish")
        if any(files != sorted(InMemoryRunPod.FILES) for _h, _o, files in ran):
            failures.append("a_pod_export_differs")
        if not account.threads - {caller}:
            failures.append("no_provider_call_ran_off_the_calling_thread")
        # Recover and terminate on the calling thread, as reconcile does.
        for job, handle in zip(jobs, handles, strict=True):
            found = backend.recover(job.intent_id, privates[job.intent_id])
            if found is None or found.pod_id != handle.pod_id:
                failures.append("recover_lost_a_pod")
            if not backend.terminate(handle):
                failures.append("termination_unverified")
        charges = asyncio.run(
            run_all(lambda handle: asyncio.to_thread(backend.charge, handle), handles)
        )
        if any(charge is None for charge in charges):
            failures.append("a_charge_unresolved")
        store = backend.store
        for job in jobs:
            intent = store.intent(backend.CAMPAIGN, job.intent_id)
            resources = store.resources(backend.CAMPAIGN, job.intent_id)
            if intent is None or intent.state is not IntentState.BOUND:
                failures.append("an_intent_not_bound")
            if [record.role for record in resources] != ["primary"]:
                failures.append("an_intent_without_exactly_one_pod")
        # The independent reconciler, on its own store, as its process runs.
        independent = reconcile(
            ComputeStore(root / "pods" / "compute"),
            RunPodAdapter(
                FileCredentialProvider(key),
                account.transport,
                sleep=lambda _seconds: None,
            ),
        )
        if (
            independent.adopted
            or independent.orphans
            or independent.unresolved_dispatches
            or independent.failures
            or independent.terminated
        ):
            failures.append("the_independent_reconciler_found_work")
        if account.pods:
            failures.append("a_pod_left_alive")
        report.update(
            {
                "status": "FAILED" if failures else "OK",
                "failures": sorted(set(failures)),
                "creates": len(account.creates),
                "provider_threads": len(account.threads),
                "off_caller_thread": bool(account.threads - {caller}),
                "pods_alive": sorted(account.pods),
                "backend": "runpod-real-path/in-memory-account",
            }
        )
    except Exception as error:  # noqa: BLE001 -- the check reports, typed
        report.update(
            {
                "status": "FAILED",
                "failures": ["exception"],
                "error_type": f"{type(error).__module__}.{type(error).__name__}",
                "error": str(error)[:500],
            }
        )
    return report


def private_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path
