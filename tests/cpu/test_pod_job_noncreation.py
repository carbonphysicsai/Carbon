"""Synthetic durable operator state only; no provider, key or live ledger."""

import pytest

from carbon.agent_campaign import grant_runs as gr
from carbon.agent_campaign import pod_job_noncreation as nc
from scripts.dev.exam_design.runpod.operator_compute import (
    ComputeError,
    ComputeStore,
    Execution,
    IntentState,
    PodSpec,
    ProvisionRequest,
)

SPEC = "sha256:" + "a" * 64


@pytest.fixture
def rejected(tmp_path):
    store = ComputeStore(tmp_path / "synthetic-compute", clock=lambda: 1000.0)
    store.start_campaign("pod-jobs")
    request = ProvisionRequest(
        tenant="pod-jobs",
        miner="pod-jobs",
        campaign_id="pod-jobs",
        intent_id="toy-job",
        spec=PodSpec(
            image="example.invalid/fixture@sha256:" + "0" * 64,
            gpu_type_id="NVIDIA A40",
            gpu_count=1,
            container_disk_gb=20,
        ),
        deadline_at=2000.0,
    )
    store.begin_intent(request, provider="runpod")
    store.claim_dispatch("pod-jobs", "toy-job")
    store.set_intent_state("pod-jobs", "toy-job", IntentState.REJECTED)
    error = ComputeError(
        operation="provision",
        failed="synthetic provider rejection",
        execution=Execution.EXECUTED,
        resources_may_remain=False,
        retry_safe=False,
        next_action="new intent",
        http_status=422,
    )
    yield store, request, error
    store.close()


def test_positive_proof_is_operator_issued_origin_bound_and_has_typed_causality(
    rejected,
):
    store, request, error = rejected
    proof = nc.reconcile_rejection(store, request, SPEC, error)
    record = proof.verify("toy-job", nc.binding(store, SPEC))
    assert record["decision"] == "DEFINITIVE_REJECTED"
    assert record["intent"]["resources_ever_bound"] == 0
    assert record["failure"]["execution"] == "executed"
    assert "synthetic provider rejection" not in str(record)
    with pytest.raises(nc.NonCreationRefused, match="operator-issued"):
        nc.NonCreationEvidence(proof.encoded, store)


@pytest.mark.parametrize(
    "state",
    [
        IntentState.NOT_FOUND,
        IntentState.DISPATCHED,
        IntentState.BOUND,
        IntentState.REQUESTED,
        IntentState.CANCELLED,
    ],
)
def test_no_absence_timeout_or_other_state_can_issue_proof(rejected, state):
    store, request, error = rejected
    store.set_intent_state("pod-jobs", "toy-job", state)
    with pytest.raises(nc.NonCreationRefused, match="REJECTED"):
        nc.reconcile_rejection(store, request, SPEC, error)


def test_original_ambiguous_failure_cannot_be_relabelled_by_a_rejected_row(rejected):
    store, request, error = rejected
    error.execution = Execution.MAY_HAVE_EXECUTED
    with pytest.raises(nc.NonCreationRefused, match="typed create refusal"):
        nc.reconcile_rejection(store, request, SPEC, error)


def test_stale_bound_resource_and_prior_resend_refuse(rejected):
    store, request, error = rejected
    intent = store.intent("pod-jobs", "toy-job")
    proof = nc.reconcile_rejection(store, request, SPEC, error)
    store.bind_resource(
        intent, "toy-pod", rate_usd_per_hr=0.1, discovered_via="tag_reconcile"
    )
    store.set_intent_state("pod-jobs", "toy-job", IntentState.REJECTED)
    with pytest.raises(nc.NonCreationRefused, match="bound/adopted"):
        proof.verify("toy-job", nc.binding(store, SPEC))


def test_resend_fence_and_copied_job_root_scope_refuse(rejected):
    store, request, error = rejected
    proof = nc.reconcile_rejection(store, request, SPEC, error)
    with pytest.raises(nc.NonCreationRefused, match="another claim/root"):
        proof.verify(
            "toy-job", {**nc.binding(store, SPEC), "store_digest": "sha256:" + "b" * 64}
        )
    with pytest.raises(nc.NonCreationRefused, match="intent audit"):
        proof.verify("another-job", nc.binding(store, SPEC))
    store.claim_resend("pod-jobs", "toy-job")
    with pytest.raises(nc.NonCreationRefused, match="resend"):
        proof.verify("toy-job", nc.binding(store, SPEC))


@pytest.fixture
def claimed(rejected, tmp_path, monkeypatch):
    store, request, error = rejected
    monkeypatch.setenv(gr.ENV, str(tmp_path / "synthetic-weekly"))
    origin = nc.binding(store, SPEC)
    gr.claim_pod_job("toy-job", "3", origin=origin, clock=store.clock)
    proof = nc.reconcile_rejection(store, request, SPEC, error)
    return store, proof, origin


def test_release_is_audited_once_restores_headroom_and_retains_attempt(claimed):
    store, proof, origin = claimed
    gr.claim_pod_job("other-job", "7", clock=store.clock)
    assert gr.weekly_report(clock=store.clock)["spent_usd"] == "10.00"
    assert gr.release_pod_job_noncreation("toy-job", proof)
    assert gr.release_pod_job_noncreation("toy-job", proof)
    report = gr.weekly_report(clock=store.clock)
    assert report["spent_usd"] == "7.00" and report["runs"] == 2
    assert gr.count(gr.POD_JOB_GRANT_ID) == 2
    import json

    rows = [
        json.loads(line)
        for line in (gr.ledger_dir() / gr.WEEKLY_FILE).read_text().splitlines()
    ]
    releases = [row for row in rows if "non_creation_release" in row]
    assert len(releases) == 1
    assert releases[0]["evidence"]["source_id"] == proof.record()["source_id"]
    with pytest.raises(gr.SharedRunsError, match="cannot relaunch"):
        gr.claim_pod_job("toy-job", "3", origin=origin, clock=store.clock)
    with pytest.raises(gr.SharedRunsError, match="cannot be overwritten"):
        gr.settle_pod_job("toy-job", "1")


def test_legacy_unknown_origin_known_charge_and_stale_store_cannot_release(claimed):
    store, proof, _ = claimed
    gr.claim_pod_job("legacy-job", "3", clock=store.clock)
    with pytest.raises(gr.SharedRunsError, match="legacy.*unknown"):
        gr.release_pod_job_noncreation("legacy-job", proof)
    gr.settle_pod_job("toy-job", "1", pending_usd=0)
    with pytest.raises(gr.SharedRunsError, match="known charges"):
        gr.release_pod_job_noncreation("toy-job", proof)
    store.set_intent_state("pod-jobs", "toy-job", IntentState.NOT_FOUND)
    with pytest.raises(gr.SharedRunsError, match="REJECTED"):
        gr.release_pod_job_noncreation("toy-job", proof)
    assert gr.weekly_report(clock=store.clock)["spent_usd"] == "4.00"


def test_copied_proof_different_job_or_root_and_raw_record_refuse(claimed):
    store, proof, origin = claimed
    gr.claim_pod_job("different-job", "3", origin=origin, clock=store.clock)
    with pytest.raises(gr.SharedRunsError, match="intent audit"):
        gr.release_pod_job_noncreation("different-job", proof)
    with pytest.raises(gr.SharedRunsError, match="operator-issued"):
        gr.release_pod_job_noncreation("toy-job", proof.record())
    with pytest.raises(gr.SharedRunsError, match="origin differs"):
        gr.claim_pod_job(
            "toy-job",
            "3",
            origin={**origin, "store_digest": "sha256:" + "b" * 64},
            clock=store.clock,
        )


def test_concurrent_release_serializes_without_double_audit(claimed):
    import json
    import threading

    _, proof, _ = claimed
    results, errors = [], []
    start = threading.Barrier(2)

    def release():
        start.wait()
        try:
            results.append(gr.release_pod_job_noncreation("toy-job", proof))
        # Surface every worker failure in the main assertion.
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=release) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads)
    assert results == [True, True] and errors == []
    rows = [
        json.loads(line)
        for line in (gr.ledger_dir() / gr.WEEKLY_FILE).read_text().splitlines()
    ]
    assert sum("non_creation_release" in row for row in rows) == 1


def test_charge_committed_before_release_fence_is_not_waived(claimed):
    store, proof, _ = claimed
    gr.settle_pod_job("toy-job", "3", pending_usd="2")
    with pytest.raises(gr.SharedRunsError, match="known charges"):
        gr.release_pod_job_noncreation("toy-job", proof)
    assert gr.weekly_report(clock=store.clock)["spent_usd"] == "3.00"


def test_original_dispatched_request_must_match_the_rejected_intent(rejected):
    from dataclasses import replace

    store, request, error = rejected
    changed = replace(request, deadline_at=request.deadline_at + 1)
    with pytest.raises(nc.NonCreationRefused, match="request identity"):
        nc.reconcile_rejection(store, changed, SPEC, error)


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_ambiguous_http_outcome_cannot_issue_proof(rejected, status):
    store, request, error = rejected
    error.http_status = status
    with pytest.raises(nc.NonCreationRefused, match="ambiguous HTTP"):
        nc.reconcile_rejection(store, request, SPEC, error)


def test_duplicate_claim_row_cannot_erase_a_release(claimed):
    import json

    _, proof, _ = claimed
    gr.release_pod_job_noncreation("toy-job", proof)
    path = gr.ledger_dir() / gr.WEEKLY_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    original = json.loads(lines[0])
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(original) + "\n")
    with pytest.raises(gr.SharedRunsError, match="corrupt"):
        gr.weekly_report()
