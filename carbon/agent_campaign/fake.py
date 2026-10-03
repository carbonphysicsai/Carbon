"""A deterministic in-process research-agent provider for tests and dry runs.

A test double, never a research agent: it runs nothing, spends nothing real and
its "costs" are synthetic numbers. Its state lives outside any controller, as a
real provider's would, so a controller can crash and reconnect to it.

Faults are injected by name (`faults`), each consumed once unless noted:

- ``start_timeout_after_create``: the run is created, then the call times out.
- ``start_timeout_before_create``: the call times out and nothing is created.
- ``status_unknown``: status reports UNKNOWN (persistent).
- ``usage_unknown``: usage is not known (persistent).
- ``cancel_leaves_workers``: cancellation stops the run but leaves a worker
  alive and reports `workers_terminated=False`.
- ``cancel_timeout``: the cancel call times out without effect.
"""

from __future__ import annotations

from decimal import Decimal

from .provider import (
    Artifact,
    Capabilities,
    IntegrationMode,
    ProviderTimeout,
    RunHandle,
    RunState,
    RunStatus,
    TaskSpec,
    Usage,
)

PROVIDER = "fake"


class FakeProvider:
    def __init__(self, *, cost_per_run="1.00", faults=(), verified=True):
        self.cost_per_run = Decimal(cost_per_run)
        self.faults = list(faults)
        self.verified = verified
        self.runs = {}
        self.by_key = {}
        self.calls = []
        self._next = 0

    # -- fault helpers -------------------------------------------------------------
    def _take(self, name):
        if name in self.faults:
            self.faults.remove(name)
            return True
        return False

    def _has(self, name):
        return name in self.faults

    # -- test controls ---------------------------------------------------------------
    def emit(self, run_id, event):
        self.runs[run_id]["events"].append(dict(event))

    def export(self, run_id, name, body):
        self.runs[run_id]["artifacts"].append(Artifact(name, body))

    def finish(self, run_id, state=RunState.SUCCEEDED):
        run = self.runs[run_id]
        run["state"] = state
        run["live_workers"] = set()

    # -- the adapter operations ------------------------------------------------------
    def capabilities(self):
        return Capabilities(
            provider=PROVIDER,
            mode=IntegrationMode.ARTIFACT_HANDOFF,
            verified=self.verified,
            supports_idempotent_start=True,
            supports_cancel=True,
            reports_worker_termination=True,
            reports_usage=True,
            basis="in-process test double; synthetic costs; runs nothing",
        )

    def start(self, spec: TaskSpec, idempotency_key: str):
        self.calls.append(("start", idempotency_key))
        if self._take("start_timeout_before_create"):
            raise ProviderTimeout("start timed out")
        if idempotency_key in self.by_key:
            return self._handle(self.by_key[idempotency_key])
        self._next += 1
        run_id = f"fake-run-{self._next:04d}"
        workers = (f"fake-worker-{self._next:04d}",)
        self.runs[run_id] = {
            "spec": spec,
            "key": idempotency_key,
            "state": RunState.RUNNING,
            "workers": workers,
            "live_workers": set(workers),
            "events": [],
            "artifacts": [],
        }
        self.by_key[idempotency_key] = run_id
        if self._take("start_timeout_after_create"):
            raise ProviderTimeout("start timed out after the run was created")
        return self._handle(run_id)

    def _handle(self, run_id):
        return RunHandle(run_id, self.runs[run_id]["workers"])

    def find(self, idempotency_key):
        self.calls.append(("find", idempotency_key))
        run_id = self.by_key.get(idempotency_key)
        return None if run_id is None else self._handle(run_id)

    def status(self, run_id):
        self.calls.append(("status", run_id))
        run = self.runs[run_id]
        if self._has("status_unknown"):
            return RunStatus(RunState.UNKNOWN, run["workers"], None)
        return RunStatus(run["state"], run["workers"], not run["live_workers"])

    def events(self, run_id, after):
        return [dict(e) for e in self.runs[run_id]["events"][after:]]

    def artifacts(self, run_id):
        return list(self.runs[run_id]["artifacts"])

    def cancel(self, run_id):
        self.calls.append(("cancel", run_id))
        if self._take("cancel_timeout"):
            raise ProviderTimeout("cancel timed out")
        run = self.runs[run_id]
        if run["state"] not in (RunState.SUCCEEDED, RunState.FAILED):
            run["state"] = RunState.CANCELLED
        if self._take("cancel_leaves_workers"):
            return
        run["live_workers"] = set()

    def usage(self, run_id):
        if self._has("usage_unknown"):
            return Usage(False, None, None, "synthetic-usd")
        run = self.runs[run_id]
        done = run["state"] in (RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED)
        return Usage(
            True,
            self.cost_per_run if done else Decimal(0),
            Decimal(0) if done else self.cost_per_run,
            "synthetic-usd",
        )
