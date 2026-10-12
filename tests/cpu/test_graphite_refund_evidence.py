"""What the Graphite provider can prove for a run-slot refund (`Phase3Provider.refund_evidence`).

A refund needs the run to have ended `failed` with code `failed_infra` AND a readable pod
record that shows no pod created and none uncertain. A missing or corrupt pod record is
never read as "no pods".
"""

from __future__ import annotations

from graphite_phase3_fixtures import (
    ScriptedPods,
    propose,
    run_id,
    session,
    steps,
    text,
    variant,
)

from carbon.agent_campaign.graphite import experiment as ex


def finished(tmp_path):
    """A finished session (its baseline pod ran) and its provider."""
    _result, graphite, _control = session(
        tmp_path,
        [propose(variant(width=128)), text("done")],
        ScriptedPods(steps=steps(1.0, 0.4)),
    )
    return graphite, run_id()


def ledger_path(graphite, rid):
    return graphite._dir(rid) / "experiment" / "pod-ledger.jsonl"


def fail_as_infra(graphite, rid):
    graphite._set_state(rid, state="failed", failure={"code": "failed_infra"})


def test_a_completed_run_is_not_a_failed_infrastructure_run(tmp_path):
    graphite, rid = finished(tmp_path)
    evidence = graphite.refund_evidence(rid)
    assert evidence["failed_infra"] is False
    assert evidence["pod_record_readable"] is True and evidence["pods_created"] >= 1


def test_a_failed_infra_run_whose_pod_record_shows_a_created_pod_is_not_refundable(
    tmp_path,
):
    graphite, rid = finished(tmp_path)
    fail_as_infra(graphite, rid)
    evidence = graphite.refund_evidence(rid)
    assert evidence["failed_infra"] is True and evidence["pods_created"] >= 1


def test_a_failed_infra_run_with_an_empty_readable_pod_record_is_refundable(tmp_path):
    graphite, rid = finished(tmp_path)
    fail_as_infra(graphite, rid)
    ledger_path(graphite, rid).write_bytes(b"")
    assert graphite.refund_evidence(rid) == {
        "failed_infra": True,
        "pod_record_readable": True,
        "pods_created": 0,
        "pods_uncertain": 0,
    }


def test_a_missing_pod_record_is_not_read_as_no_pods(tmp_path):
    graphite, rid = finished(tmp_path)
    fail_as_infra(graphite, rid)
    ledger_path(graphite, rid).unlink()
    evidence = graphite.refund_evidence(rid)
    assert evidence["pod_record_readable"] is False
    assert not ledger_path(graphite, rid).exists()  # reading it created nothing


def test_a_corrupt_pod_record_is_not_readable(tmp_path):
    graphite, rid = finished(tmp_path)
    fail_as_infra(graphite, rid)
    ledger_path(graphite, rid).write_bytes(b"{not json\n")
    assert graphite.refund_evidence(rid)["pod_record_readable"] is False


def test_a_launch_requested_with_no_outcome_is_uncertain(tmp_path):
    graphite, rid = finished(tmp_path)
    fail_as_infra(graphite, rid)
    path = ledger_path(graphite, rid)
    path.write_bytes(b"")
    ledger = ex.PodLedger(path, clock=lambda: 0.0)
    ledger.append("pod_reserved", intent_id="i9", proposal="p", reserved_usd="0.25")
    ledger.append("pod_launch_requested", intent_id="i9", proposal="p")
    evidence = graphite.refund_evidence(rid)
    assert evidence["pods_created"] == 0 and evidence["pods_uncertain"] == 1


def test_a_reserved_pod_that_never_launched_or_was_refused_is_not_a_created_pod(
    tmp_path,
):
    graphite, rid = finished(tmp_path)
    fail_as_infra(graphite, rid)
    path = ledger_path(graphite, rid)
    path.write_bytes(b"")
    ledger = ex.PodLedger(path, clock=lambda: 0.0)
    ledger.append("pod_reserved", intent_id="i1", proposal="p", reserved_usd="0.25")
    ledger.append("pod_reserved", intent_id="i2", proposal="p", reserved_usd="0.25")
    ledger.append("pod_launch_requested", intent_id="i2", proposal="p")
    ledger.append("pod_launch_refused", intent_id="i2", proposal="p")
    evidence = graphite.refund_evidence(rid)
    assert (evidence["pods_created"], evidence["pods_uncertain"]) == (0, 0)


def test_an_ensured_pod_record_is_empty_private_and_never_overwritten(tmp_path):
    path = tmp_path / "pod-ledger.jsonl"
    ledger = ex.PodLedger(path, clock=lambda: 0.0)
    ledger.ensure()
    assert path.read_bytes() == b"" and (path.stat().st_mode & 0o777) == 0o600
    ledger.append("pod_reserved", intent_id="i1", proposal="p", reserved_usd="0.25")
    before = path.read_bytes()
    ledger.ensure()
    assert path.read_bytes() == before
