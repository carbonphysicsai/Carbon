"""Actual launcher/recovery/ledger functions over synthetic operator transport."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from operator_fake_runpod import Clock, FakeRunPod, key_file

from carbon.agent_campaign import grant_runs as gr
from carbon.agent_campaign import pod_jobs
from carbon.agent_campaign.graphite.pods import PodFailure
from scripts.dev.exam_design.runpod.operator_compute import (
    ComputeService,
    ComputeStore,
    FileCredentialProvider,
    IntentState,
    PodSpec,
    RunPodAdapter,
)


@pytest.fixture
def lane(tmp_path, monkeypatch):
    monkeypatch.setenv(gr.ENV, str(tmp_path / "synthetic-ledger"))
    clock, transport = Clock(), FakeRunPod()
    store = ComputeStore(tmp_path / "synthetic-compute", clock=clock)
    store.start_campaign("pod-jobs")
    adapter = RunPodAdapter(
        FileCredentialProvider(key_file(tmp_path)),
        transport,
        clock=clock,
        sleep=clock.advance,
    )
    service = ComputeService(store, adapter, clock=clock, sleep=clock.advance)
    # Avoid unrelated ship/build/NumPy dependencies. Only the transport and
    # published code manifest are fixtures; launch_job/ComputeService and the
    # actual durable claim/recovery/finish/settlement functions execute.
    backend = object.__new__(pod_jobs.JobPods)
    backend.store, backend.adapter, backend.service = store, adapter, service
    backend.clock, backend.balance_floor = clock, lambda: Decimal(0)
    backend.spec = SimpleNamespace(
        cpu=True, job_id="toy-job", digest=lambda: "sha256:" + "a" * 64
    )
    backend.money = {"cap_usd": Decimal(3), "worst_case_usd": Decimal(3)}
    backend.record = lambda private: {
        "deadline_at": clock() + 1200,
        "token": "synthetic-only",
    }
    backend.job_spec = lambda record: PodSpec(
        image="example.invalid/mock@sha256:" + "0" * 64,
        gpu_type_id="NVIDIA A40",
        gpu_count=1,
        container_disk_gb=20,
        max_rate_usd_per_hr=0.5,
        storage_usd_per_gb_month=0.1,
    )
    backend.retry_ambiguous_create = False
    backend._noncreation_evidence, backend._create_failure = None, None
    backend._tokens = {}
    gr.claim_pod_job("toy-job", "3", clock=clock, origin=backend.claim_origin())
    yield backend, transport, clock, tmp_path
    store.close()


def finish(backend, root, executed=True):
    out = root / "out"
    out.mkdir(exist_ok=True)
    receipt = {
        "outcome": "launch_refused",
        "pod_id": None,
        "errors": [],
        "duplicates": [],
        "cost": None,
        "ok": False,
    }
    pod_jobs._finish(receipt, gr, backend.spec, backend, None, executed, root, out)
    return receipt


def test_definitive_initial_provider_refusal_releases_with_reconcile_evidence(lane):
    backend, transport, clock, root = lane
    transport.fail_next_create_with = 422
    with pytest.raises(PodFailure) as caught:
        backend.launch_job(root)
    assert caught.value.executed is True  # the RPC executed, but created nothing
    assert backend.store.intent("pod-jobs", "toy-job").state is IntentState.REJECTED
    receipt = finish(backend, root)
    assert receipt["cost"]["basis"] == "DEFINITIVE_REJECTED"
    assert receipt["cost"]["pending_usd"] == "0"
    assert receipt["non_creation_reconcile"]["failure"]["http_status"] == 422
    assert receipt["create_failure"]["resources_may_remain"] is False
    assert gr.weekly_report(clock=clock)["spent_usd"] == "0.00"
    assert gr.count(gr.POD_JOB_GRANT_ID) == 1
    assert receipt["ok"] is False


def test_ambiguous_empty_listing_and_elapsed_grace_keep_reservation(lane):
    backend, transport, clock, root = lane
    transport.fail_next_create_with = 500
    with pytest.raises(PodFailure):
        backend.launch_job(root)
    assert backend._noncreation_evidence is None
    clock.advance(backend.service.not_found_grace_s + 1)
    assert backend.recover("toy-job", root) is None
    assert backend.store.intent("pod-jobs", "toy-job").state is IntentState.NOT_FOUND
    receipt = finish(backend, root)
    assert receipt["cost"]["pending_usd"] == "3"
    assert "non_creation_reconcile" not in receipt
    assert gr.weekly_report(clock=clock)["spent_usd"] == "3.00"


def test_current_not_executed_call_cannot_clear_prior_ambiguous_history(lane):
    backend, transport, clock, root = lane
    transport.fail_next_create_with = 500
    with pytest.raises(PodFailure):
        backend.launch_job(root)
    clock.advance(backend.service.not_found_grace_s + 1)
    backend.recover("toy-job", root)
    # Re-provision refuses the terminal NOT_FOUND intent without a new RPC.
    with pytest.raises(PodFailure) as caught:
        backend.launch_job(root)
    assert caught.value.executed is False
    receipt = finish(backend, root, executed=False)
    assert receipt["cost"]["pending_usd"] == "3"
    assert gr.weekly_report(clock=clock)["spent_usd"] == "3.00"
