"""POD-STORE-THREADS-01: the live pod backend across the threads a phase-3
session uses. No network, no spend: RunPod is a MOCK transport.

Live session 3 (run graphite-18fc7b1c1eeea8aa, REF ac78f661) ended at its
first pod launch with `sqlite3.ProgrammingError` ("SQLite objects created in a
thread can only be used in that same thread"): `RunPodPods` builds the
operator `ComputeStore` on the runner's main thread, and `Phase3Tools.call`
runs the proposal (and so `RunPodPods.launch`) through `asyncio.to_thread`.
Every test here drives the real `RunPodPods.launch` that way."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import threading
from contextlib import contextmanager
from decimal import Decimal

import pytest
from operator_fake_runpod import Clock, FakeRunPod, key_file

from carbon.agent_campaign.graphite import pods
from scripts.dev.exam_design.runpod.operator_compute import (
    ComputeStore,
    FileCredentialProvider,
    IntentState,
    RunPodAdapter,
    reconcile,
)
from scripts.dev.exam_design.runpod.operator_compute import store as store_module


def _head():
    return subprocess.run(
        ["git", "-C", str(pods.REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class LockedFake(FakeRunPod):
    """The MOCK account, safe to call from several threads at once."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lock = threading.Lock()
        self.threads = set()

    def __call__(self, method, url, *, body, headers, timeout):
        with self.lock:
            self.threads.add(threading.get_ident())
            return super().__call__(
                method, url, body=body, headers=headers, timeout=timeout
            )


def backend(tmp_path, fake, clock):
    return pods.RunPodPods(
        root=tmp_path / "pods",
        key_file=key_file(tmp_path),
        code_ref=_head(),
        clock=clock,
        transport=fake,
        http=lambda *_args: (0, b""),
        sleep=lambda _seconds: None,
        balance_floor=lambda: Decimal(0),  # synthetic; the operator's is private
    )


def job(index):
    return pods.PodJob(
        intent_id=f"threads-{index}",
        strategy={"index": index},
        contract_digest="sha256:" + "0" * 64,
        seed=index,
        expected={"files": {}},
        minutes=30,
        seconds=600,
    )


def private(tmp_path, item):
    return pods.private_dir(tmp_path / "private" / item.intent_id)


def launch_all(live, tmp_path, jobs):
    """Each launch through `asyncio.to_thread`, all at once, as the
    proposal tool runs; failures are returned, not raised."""

    async def run():
        return await asyncio.gather(
            *(
                asyncio.to_thread(live.launch, item, private(tmp_path, item))
                for item in jobs
            ),
            return_exceptions=True,
        )

    return asyncio.run(run())


def test_the_live_backend_launches_from_worker_threads(tmp_path):
    clock, fake = Clock(), LockedFake()
    live = backend(tmp_path, fake, clock)  # built on this (the main) thread
    jobs = [job(index) for index in range(3)]
    handles = launch_all(live, tmp_path, jobs)
    errors = [item for item in handles if isinstance(item, BaseException)]
    assert errors == []  # on main: sqlite3.ProgrammingError, before any create
    assert fake.creates() == 3
    assert threading.get_ident() not in fake.threads
    for item, handle in zip(jobs, handles, strict=True):
        intent = live.store.intent(live.CAMPAIGN, item.intent_id)
        assert intent.state is IntentState.BOUND
        [record] = live.store.resources(live.CAMPAIGN, item.intent_id)
        assert (record.role, record.resource_id) == ("primary", handle.pod_id)
    # Recovery and termination run on the main thread, as reconcile does.
    for item, handle in zip(jobs, handles, strict=True):
        assert live.recover(item.intent_id, private(tmp_path, item)) == handle
        assert live.terminate(handle) is True
    assert fake.pods == {}


def test_one_intent_launched_twice_at_once_sends_one_create(tmp_path):
    clock, fake = Clock(), LockedFake()
    live = backend(tmp_path, fake, clock)
    item = job(0)
    results = launch_all(live, tmp_path, [item, item])
    assert fake.creates() == 1
    pod_ids = {result.pod_id for result in results if isinstance(result, pods.PodHandle)}
    assert len(pod_ids) == 1
    for result in results:
        if isinstance(result, BaseException):
            # The second caller found the intent dispatched and its pod not
            # yet listed: an ambiguous launch, never a second create.
            assert isinstance(result, pods.PodFailure) and result.executed
    [record] = live.store.resources(live.CAMPAIGN, item.intent_id)
    assert record.role == "primary"


def test_concurrent_launches_are_admitted_against_one_balance(tmp_path):
    """The spend gate and the dispatch claim are one admission: two threads
    cannot both be admitted against a balance that holds one pod."""
    clock = Clock()
    cost = pods.pod_reservation(30, pods.prices()["hourly_usd"])
    fake = LockedFake(balance=float(cost * Decimal("1.5")))
    live = backend(tmp_path, fake, clock)
    results = launch_all(live, tmp_path, [job(0), job(1)])
    launched = [r for r in results if isinstance(r, pods.PodHandle)]
    refused = [r for r in results if isinstance(r, pods.PodFailure)]
    assert len(launched) == 1 and fake.creates() == 1
    assert len(refused) == 1 and refused[0].executed is False
    assert "observed account balance" in refused[0].detail


def test_the_store_serves_any_thread_and_the_reconciler_still_works(tmp_path):
    clock, fake = Clock(), LockedFake()
    store = ComputeStore(tmp_path / "compute", clock=clock)
    store.start_campaign("graphite-phase3")

    async def off_thread():
        return await asyncio.to_thread(store.campaign_status, "graphite-phase3")

    assert asyncio.run(off_thread()) == "active"
    live = backend(tmp_path, fake, clock)
    [handle] = launch_all(live, tmp_path, [job(0)])
    clock.advance(31 * 60)  # past the pod's deadline
    adapter = RunPodAdapter(
        FileCredentialProvider(key_file(tmp_path)), fake, sleep=lambda _s: None
    )

    async def reconciled():
        # The independent reconciler, on its own store, off this thread.
        return await asyncio.to_thread(
            reconcile, ComputeStore(tmp_path / "pods" / "compute"), adapter, clock=clock
        )

    report = asyncio.run(reconciled())
    assert report.terminated == [
        {"resource_id": handle.pod_id, "reason": "deadline_passed"}
    ]
    assert report.failures == [] and fake.pods == {}


def test_a_closed_store_refuses_use(tmp_path):
    store = ComputeStore(tmp_path / "compute")
    store.start_campaign("c")
    store.close()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        store.campaign_status("c")
    # The data stays for the next store on the same root.
    assert ComputeStore(tmp_path / "compute").campaign_status("c") == "active"


def test_a_replayed_launch_makes_the_same_create_request():
    """The CA bundle carries no gzip timestamp, so a job's create request (and
    its digest) is the same in any second: a replay is never refused as a
    different request."""
    import base64

    raw = base64.b64decode(pods._ca_bundle())
    assert raw[:2] == b"\x1f\x8b" and raw[4:8] == b"\x00\x00\x00\x00"
    assert pods._ca_bundle() == pods._ca_bundle()


def test_the_real_path_check_passes(tmp_path):
    report = pods.real_path_check(tmp_path / "check")
    assert report["status"] == "OK", json.dumps(report)
    assert report["failures"] == [] and report["creates"] == 2
    assert report["off_caller_thread"] and report["pods_alive"] == []
    assert report["synthetic"] is True and report["network"] is False


def test_the_real_path_check_catches_a_thread_bound_store(tmp_path, monkeypatch):
    """The defect as it was: one connection, made on the first thread that
    used the store. The check, as the dry run runs it, reports it."""

    @contextmanager
    def thread_bound(self):
        if getattr(self, "_legacy", None) is None:
            self._legacy = sqlite3.connect(self.path, isolation_level=None, timeout=30)
            self._legacy.row_factory = sqlite3.Row
        yield self._legacy

    monkeypatch.setattr(store_module.ComputeStore, "_connect", thread_bound)
    report = pods.real_path_check(tmp_path / "check")
    assert report["status"] == "FAILED"
    assert report["error_type"] == "sqlite3.ProgrammingError"
    assert "same thread" in report["error"]


def test_the_real_path_check_refuses_a_used_root(tmp_path):
    (tmp_path / "check").mkdir()
    (tmp_path / "check" / "left").write_text("x")
    report = pods.real_path_check(tmp_path / "check")
    assert report["status"] == "FAILED" and "new or empty" in report["error"]
