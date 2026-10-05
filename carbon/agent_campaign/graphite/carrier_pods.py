"""Graphite's CPU carrier lane: a second experiment backend beside RunPod.

`CarrierPods` implements the `pods.PodBackend` protocol the experiment uses
(launch, wait, fetch, timing, listing, terminate, charge, recover). It runs
each job's practice program on this host in the isolated C-03 carrier
(`carbon.development_session.research_carrier`, trusted lane) instead of on a
rented GPU pod. The backend is challenge-neutral: what it runs comes from the
job's Challenge (`ChallengeScoring.built_record`, through `pod_phase`), never
from this module.

**Where it runs.** On the operator host only, for Graphite's internal runs.
Never on a miner host. The carrier enforces its own controls on every run:
- no network;
- a read-only root and uid 65532 with all capabilities dropped;
- cgroup CPU, memory and pid limits, and a wall-clock watchdog;
- staged inputs read-only and outputs exported through the bounded C-03
  stream.

`inspect_effective_controls` verifies them after start. They are engineering
controls, not a security qualification: this lane needs the dedicated
security review (AGENTS.md §13) before anything but Carbon's own Level 0-3
program runs in it.

**What it refuses.**
- A job at Level 4 or 5 is refused, typed, before anything is created: only
  Carbon's fixed program for Levels 0-3 runs here.
- The lane costs no provider money (`hourly_usd` = 0, `charge` = 0), so a
  run on it reserves no pod allowance and its grant's whole run cap goes to
  tokens.

**Evidence.**
- The compile runs on this host exactly as `pod_phase.run` does on a pod. A
  compile failure is the `compile` claim, as on a pod.
- A non-zero program exit is the `program` claim. The carrier's deadline is
  the `timeout` claim. Any other carrier failure is infrastructure: no
  claim, and the experiment types it FAILED_INFRA.
- Host-observed time is authoritative, as on pods: `timing` is the clock
  around the whole carrier call.
- The lane declares its effective program deadline (`effective_work_seconds`):
  the contract's work seconds minus the carrier's setup margin
  (`SETUP_MARGIN_S`). The trusted lane gives the program `seconds - 45` from
  the start of the run, so a carrier deadline stop always takes at least that
  long on the host clock.
- The experiment compares host timing with that declared deadline. A
  carrier stop at its own deadline is therefore "confirmed", never
  "contradicted", and gets the pods' rule: one retry, then a candidate
  resource outcome on a second confirmed timeout.
- The shorter deadline is a declared property of the lane, in its
  `describe()` manifest. A recipe that needs the full contract deadline
  should run on a pod.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from decimal import Decimal
from pathlib import Path

from .pods import PodFailure, PodHandle, fetch_limits

BACKEND = "c03-carrier"
OWNER = "graphite-carrier"
PROVENANCE = "GRAPHITE_CARRIER_PRACTICE"
#: Levels whose program is Carbon's own; only these run in this lane.
CARRIER_LEVELS = frozenset({0, 1, 2, 3})
#: Bounded copies of the carrier's logs kept for the operator (`pod_logs`).
LOG_BYTES = 64 * 1024
#: The carrier's trusted-lane setup margin: its program exec times out at
#: `seconds - 45` from the run's start (`research_carrier._run_locked`).
SETUP_MARGIN_S = 45
OUTPUTS = ("predictions.json", "fit.json", "runtime.json")
REPOSITORY = Path(__file__).resolve().parents[3]


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(value):
    return hashlib.sha256(value.encode() if type(value) is str else value).hexdigest()


def _owner_only_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise PodFailure("launch", "carrier_root_not_a_directory", executed=False)
    if info.st_mode & 0o077:
        raise PodFailure("launch", "carrier_root_not_owner_only", executed=False)
    return path


class CarrierLedger:
    """The carrier's operation ledger for one job (`root`, `reserve`,
    `finish`, `status`), with the carrier's semantics: a new identity is
    dispatched once, a finished one replays its result, and one left
    RESERVED by a crash is never dispatched again. One ledger per job, so two
    jobs never contend for the carrier's per-ledger lease."""

    def __init__(self, root):
        self.root = _owner_only_directory(root)

    def _path(self, identity):
        return self.root / ("op-" + _sha(identity) + ".json")

    def _write(self, identity, body):
        path = self._path(identity)
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical(body))
        os.replace(temporary, path)

    def reserve(self, identity, *, owner, phase, request, resources):
        wanted = {
            "owner": owner,
            "phase": phase,
            "request": request,
            "resources": resources,
        }
        path = self._path(identity)
        if not path.exists():
            self._write(identity, {**wanted, "state": "RESERVED"})
            return {"dispatch": True, "state": "RESERVED"}
        stored = json.loads(path.read_bytes())
        if {k: stored[k] for k in wanted} != json.loads(_canonical(wanted)):
            raise ValueError("operation identity reused with another request")
        return {
            "dispatch": False,
            "state": stored["state"],
            "result": stored.get("result"),
        }

    def finish(self, identity, *, owner, state, actual, result):
        path = self._path(identity)
        if not path.exists():
            raise ValueError("operation unavailable")
        stored = json.loads(path.read_bytes())
        if stored["state"] != "RESERVED":
            if stored.get("result") == result and stored["state"] == state:
                return
            raise ValueError("terminal conflict")
        self._write(
            identity, {**stored, "state": state, "actual": actual, "result": result}
        )

    def status(self, *, owner):
        return {
            "operations": [
                json.loads(p.read_bytes()) for p in sorted(self.root.glob("op-*.json"))
            ]
        }


class CarrierPods:
    """Run Graphite jobs in the isolated C-03 carrier on this host."""

    name = "carrier"
    #: No provider money: a run on this lane reserves no pod allowance.
    hourly_usd = Decimal(0)

    def __init__(
        self, root, *, image, repository=REPOSITORY, runner=None, clock=time.time
    ):
        self.root = _owner_only_directory(root)
        self.image = image
        self.repository = Path(repository)
        self.clock = clock
        self._runner = runner
        self._jobs, self._files, self._timings = {}, {}, {}

    def runner(self):
        if self._runner is None:
            from carbon.development_session.research_carrier import _run

            self._runner = _run
        return self._runner

    def describe(self):
        return {
            "backend": BACKEND,
            "image": "c03:" + str(self.image.image_id),
            "host": "operator",
            "hourly_usd": "0",
            "levels": sorted(CARRIER_LEVELS),
            # A declared lane property: the program deadline is the
            # contract's work seconds minus this margin.
            "program_deadline_margin_s": SETUP_MARGIN_S,
        }

    def effective_work_seconds(self, contract_seconds):
        """The deadline a program has in this lane (module notes)."""
        return contract_seconds - SETUP_MARGIN_S

    def launch(self, job, private):
        level = 0
        if job.development_variant is not None:
            from carbon.reconstruction import development_variants

            try:
                level = development_variants.registered(job.development_variant).level
            except Exception:  # noqa: BLE001 -- typed, never echoed
                raise PodFailure(
                    "launch", "carrier_variant_unregistered", executed=False
                ) from None
        if level not in CARRIER_LEVELS:
            # Levels 4-5 run participant code: never in this lane.
            raise PodFailure("launch", "carrier_level_refused", executed=False)
        self._jobs[job.intent_id] = job
        return PodHandle(job.intent_id, "carrier-" + _sha(job.intent_id)[:16], "0")

    def recover(self, intent_id, private):
        # A carrier run is synchronous inside `wait`; nothing outlives the
        # process, and nothing costs provider money.
        return None

    def wait(self, handle, *, deadline, cancelled):
        job = self._jobs.get(handle.intent_id)
        if job is None:
            raise PodFailure("wait", "carrier_job_unknown", executed=False)
        if cancelled():
            return "cancelled"
        started = self.clock()
        files, outcome = self._run(job)
        ended = self.clock()
        self._files[handle.intent_id] = files
        # Host-observed: the whole carrier call, compared with the lane's
        # declared program deadline (module notes).
        self._timings[handle.intent_id] = {
            "before_running": started,
            "first_running": started,
            "last_running": ended,
            "ended": ended,
        }
        return outcome

    def _run(self, job):
        from . import pod_phase

        cfg = job.config(None)
        try:
            if job.development_variant is not None:
                record, staged, program = pod_phase.development_built_record(
                    job.strategy,
                    job.contract_digest,
                    job.development_variant,
                    job.seed,
                    self.repository,
                )
            else:
                record, staged, program = pod_phase.built_record(
                    job.strategy, job.contract_digest, job.seed, self.repository
                )
        except Exception as failure:  # noqa: BLE001 -- typed, never echoed
            claim = {"stage": "compile", "error": type(failure).__name__}
            return {"failure.json": _canonical(claim)}, "failed"
        files = {"built.json": _canonical(record)}
        if not pod_phase.pinned(record, cfg["expected"]):
            claim = {"stage": "verification", "error": "digest"}
            return {**files, "failure.json": _canonical(claim)}, "failed"
        from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

        ledger = CarrierLedger(self.root / "ledger" / _sha(job.intent_id)[:32])
        try:
            result = self.runner()(
                ledger,
                owner=OWNER,
                identity=job.intent_id,
                source=program,
                files=dict(staged),
                image=self.image,
                seconds=int(job.seconds),
                provenance=PROVENANCE,
                extra_resources={},
            )
        except WorkerFailure as failure:
            log = {"program.log": failure.private_diagnostic[:LOG_BYTES]}
            if failure.code is WorkerCode.RUNTIME:
                claim = {"stage": "program", "error": "nonzero exit"}
            elif failure.code is WorkerCode.DEADLINE:
                claim = {"stage": "timeout", "error": "deadline"}
            else:
                # The carrier's own failure: infrastructure, with no claim.
                return {**files, **log}, "infra"
            return {**files, **log, "failure.json": _canonical(claim)}, "failed"
        except Exception:  # noqa: BLE001 -- the carrier's own, never the program's
            return files, "infra"
        operation = ledger.root / str(result.get("operation", ""))
        snapshot = operation / "snapshot"
        for name in OUTPUTS:
            path = snapshot / name
            if path.is_file() and not path.is_symlink():
                files[name] = path.read_bytes()
        stdout = operation / "stdout.txt"
        if stdout.is_file() and not stdout.is_symlink():
            files["program.log"] = stdout.read_bytes()[:LOG_BYTES]
        files["DONE.json"] = _canonical({"phase": "graphite_practice", "exit": 0})
        return files, "done"

    def fetch(self, handle):
        files = self._files.get(handle.intent_id)
        if files is None:
            raise PodFailure("fetch", "carrier_nothing_ran", executed=True)
        fetch_limits(
            [{"path": name, "size": len(body)} for name, body in sorted(files.items())]
        )
        return dict(files)

    def listing(self, handle):
        files = self._files.get(handle.intent_id)
        if files is None:
            return None
        return {name: _sha(body) for name, body in files.items()}

    def timing(self, handle):
        from .pod_outcome import HostTiming

        seen = self._timings.get(handle.intent_id)
        return None if seen is None else HostTiming(**seen)

    def terminate(self, handle):
        return True

    def charge(self, handle):
        return Decimal(0)
