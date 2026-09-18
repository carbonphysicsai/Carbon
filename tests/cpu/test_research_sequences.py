"""Non-spending two-child admission, generation and cleanup regressions."""

import concurrent.futures
import json
import threading
import time

import pytest

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_carrier import reconcile_worker
from carbon.development_session.research_control import (
    CampaignControl,
    DispatchPaused,
    DispatchStopped,
)
from carbon.development_session.research_ledger import (
    CEILINGS,
    FINAL_RESERVE,
    CampaignLedger,
)
from carbon.development_session.research_report import render_status
from carbon.development_session.research_sequences import SCOPE

OWNER = "envelope-fixture"
SCOPE_DOCUMENT = {
    "schema": SCOPE,
    "case_digests": [digest(b"first"), digest(b"second")],
}
RESOURCES = {
    "numerical_milliseconds": 720000,
    "reference_trajectories": 2,
    "reference_invocations": 2,
    "retained_bytes": 402653184,
}
CHILDREN = [
    {
        "request": {"request_digest": pin, "image": "sha256:" + "a" * 64},
        "resources": RESOURCES,
    }
    for pin in SCOPE_DOCUMENT["case_digests"]
]


def prepared(tmp_path, *, ceilings=None, scope=SCOPE_DOCUMENT):
    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    runtime = {"implementation": "fixture", "scientific_tasks": [scope]}
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "envelope-fixture",
        "campaign_id": "envelope-fixture",
        "root": str(root),
        "principal": "alice",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": runtime,
        "provider": "openai-responses",
        "account_ref": "no-credentials",
        "campaign_count": 1,
        "ceilings": dict(CEILINGS if ceilings is None else ceilings),
        "elapsed_seconds": 28800,
        "expires_unix": 50000,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    path = tmp_path / "grant.json"
    path.write_bytes(canonical(grant))
    path.chmod(0o600)
    admission = Admission.load(path)
    ledger = CampaignLedger(root, clock=lambda: 1000, admission=admission)
    ledger.generation = CampaignControl(ledger).acquire()
    manifest = {
        "schema": MANIFEST,
        "campaign_id": grant["campaign_id"],
        "authority": grant["authority"],
        "principal": "alice",
        "owner": OWNER,
        "runtime": runtime,
        "grant": admission.binding(),
        "ceilings": grant["ceilings"],
        "elapsed_seconds": grant["elapsed_seconds"],
        **dict.fromkeys(
            (
                "implementation",
                "objective",
                "sampling",
                "control",
                "selection",
                "replica_policy",
                "provider",
            ),
            "fixture",
        ),
    }
    ledger.freeze(manifest)
    return ledger


def reserve(ledger, parent="sequence", *, owner=OWNER, children=CHILDREN):
    return ledger.reserve_sequence(
        parent, owner=owner, scope=SCOPE_DOCUMENT, children=children
    )


def finish(ledger, child, *, receipt=True):
    result = {}
    if receipt:
        relative = "controller/" + child["id"] + ".json"
        path = ledger.root / relative
        path.parent.mkdir(exist_ok=True)
        body = canonical(
            {
                "schema": "carbon.c04.reference-launch.v1",
                "request_digest": child["request"]["request_digest"],
                "image_id": child["request"]["image"],
                "state": "ASSOCIATED_DEVELOPMENT_ONLY",
            }
        )
        path.write_bytes(body)
        result["cleanup_receipt"] = {"path": relative, "digest": digest(body)}
    actual = {**RESOURCES, "numerical_milliseconds": 1000, "retained_bytes": 10000}
    ledger.finish(
        child["id"], owner=OWNER, state="SUCCEEDED", actual=actual, result=result
    )


def test_atomic_aggregate_final_reserve_and_replay(tmp_path):
    ledger = prepared(tmp_path)
    first = reserve(ledger)
    assert first["dispatch"]
    assert reserve(ledger) == {**first, "dispatch": False}
    status = ledger.status(owner=OWNER)
    assert len(status["operations"]) == 3
    assert status["used"]["numerical_milliseconds"] == 1440000
    assert (
        ledger.sequence_status("sequence", owner=OWNER)["children"][0]["state"]
        == "HELD"
    )
    with pytest.raises(ValueError, match="replay conflict"):
        reserve(ledger, children=CHILDREN[::-1])
    with pytest.raises(ValueError, match="prospective"):
        reserve(ledger, owner="bob")


def test_no_partial_rows_when_only_one_child_fits(tmp_path):
    caps = {
        **CEILINGS,
        "numerical_milliseconds": FINAL_RESERVE["numerical_milliseconds"] + 720000,
    }
    ledger = prepared(tmp_path, ceilings=caps)
    with pytest.raises(ValueError, match="aggregate"):
        reserve(ledger)
    assert ledger.status(owner=OWNER)["operations"] == []
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operation_sequences").fetchone()[0] == 0


def test_claim_once_order_cleanup_and_parent_settlement(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    with pytest.raises(ValueError, match="previous child"):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=1)
    child = ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    with pytest.raises(ValueError, match="no redispatch"):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    with pytest.raises(ValueError, match="child-derived"):
        ledger.finish("sequence", owner=OWNER, state="SUCCEEDED", actual={}, result={})
    finish(ledger, child)
    second = ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=1)
    finish(ledger, second)
    ledger.settle_sequence("sequence", owner=OWNER)
    ledger.settle_sequence("sequence", owner=OWNER)
    assert {op["state"] for op in ledger.status(owner=OWNER)["operations"]} == {
        "SUCCEEDED"
    }
    assert ledger.status(owner=OWNER)["used"]["numerical_milliseconds"] == 2000


def test_success_code_without_cleanup_does_not_claim_second(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    child = ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    finish(ledger, child, receipt=False)
    with pytest.raises(ValueError, match="cleanup receipt"):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=1)


def test_held_is_not_worker_cannot_finish_and_releases_after_expiry(tmp_path):
    ledger = prepared(tmp_path)
    ids = reserve(ledger)["children"]
    with pytest.raises(ValueError, match="terminal conflict"):
        ledger.finish(
            ids[0],
            owner=OWNER,
            state="CANCELLED",
            actual=dict.fromkeys(RESOURCES, 0),
            result={},
        )
    with pytest.raises(ValueError, match="never-claimed"):
        reconcile_worker(ledger, owner=OWNER, identity=ids[0])
    ledger.clock = lambda: 50001
    with pytest.raises(ValueError, match="expired"):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    ledger.cancel_sequence_held("sequence", owner=OWNER)
    ledger.settle_sequence("sequence", owner=OWNER)
    report = render_status(ledger, owner=OWNER)
    assert report["used"]["numerical_milliseconds"] == 0
    assert report["phase_accounting"]["research"]["numerical_milliseconds"] == 0


def test_expired_cancel_retains_claimed_unknown_and_partial_capacity(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    ledger.clock = lambda: 50001
    ledger.cancel_sequence_held("sequence", owner=OWNER)
    states = ledger.sequence_status("sequence", owner=OWNER)["children"]
    assert [c["state"] for c in states] == ["RESERVED", "CANCELLED"]
    assert ledger.status(owner=OWNER)["used"]["numerical_milliseconds"] == 720000
    with pytest.raises(ValueError, match="unresolved"):
        ledger.settle_sequence("sequence", owner=OWNER)


def test_parallel_claim_one_worker_and_restart_generation(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    reserve(ledger, "other-sequence")

    def claim(parent):
        try:
            return ledger.claim_sequence_child(parent, owner=OWNER, ordinal=0)
        except ValueError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert (
            sum(x is not None for x in pool.map(claim, ["sequence", "other-sequence"]))
            == 1
        )
    restarted = CampaignLedger(
        ledger.root, clock=ledger.clock, admission=ledger.admission
    )
    restarted.generation = CampaignControl(restarted).acquire()
    with pytest.raises(DispatchStopped):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=1)
    assert restarted.status(owner=OWNER)["used"]["numerical_milliseconds"] == 2880000
    assert (
        CampaignControl(restarted).settled(
            restarted.generation, completed=True, cleanup_verified=True
        )
        == "RECONCILIATION_REQUIRED"
    )


def test_pause_and_stop_fence_claim_without_spending_held(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    control = CampaignControl(ledger)
    control.request("pause")
    with pytest.raises(DispatchPaused):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    control.request("stop")
    with pytest.raises(DispatchStopped):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    ledger.cancel_sequence_held("sequence", owner=OWNER)
    ledger.settle_sequence("sequence", owner=OWNER)
    assert control.settled(ledger.generation, cleanup_verified=True) == "STOPPED"


def test_v1_scope_does_not_authorize_sequence(tmp_path):
    ledger = prepared(tmp_path, scope={"schema": "carbon.public-julia-study.scope.v1"})
    with pytest.raises(ValueError, match="prospective"):
        reserve(ledger)


def test_changed_cleanup_artifact_blocks_next_child(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    first = ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    finish(ledger, first)
    receipt_path = ledger.root / ("controller/" + first["id"] + ".json")
    doc = json.loads(receipt_path.read_bytes())
    doc["image_id"] = "sha256:" + "b" * 64
    receipt_path.write_bytes(canonical(doc))
    with pytest.raises(ValueError, match="not confirmed"):
        ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=1)


def test_pause_observes_held_as_capacity_not_running_worker(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    control = CampaignControl(ledger)
    control.request("pause")
    thread = threading.Thread(target=lambda: control.checkpoint(ledger.generation))
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while control.status()["state"] != "PAUSED" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert control.status()["state"] == "PAUSED"
        assert {
            c["state"]
            for c in ledger.sequence_status("sequence", owner=OWNER)["children"]
        } == {"HELD"}
    finally:
        control.request("resume")
        thread.join(timeout=3)
    assert not thread.is_alive()


def test_existing_cleanup_releases_held_without_worker_journal(tmp_path):
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    ledger = prepared(tmp_path)
    reserve(ledger)
    assert RunnerAdapter._cleanup(ledger)
    assert ledger.status(owner=OWNER)["used"]["numerical_milliseconds"] == 0
    assert {
        c["state"] for c in ledger.sequence_status("sequence", owner=OWNER)["children"]
    } == {"CANCELLED"}


def test_restart_partial_requires_previous_cleanup_and_original_allowance(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    first = ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    finish(ledger, first)
    before = ledger.status(owner=OWNER)["used"]
    restarted = CampaignLedger(
        ledger.root, clock=ledger.clock, admission=ledger.admission
    )
    restarted.generation = CampaignControl(restarted).acquire()
    assert reserve(restarted)["dispatch"] is False
    second = restarted.claim_sequence_child("sequence", owner=OWNER, ordinal=1)
    assert second["id"] != first["id"]
    assert restarted.status(owner=OWNER)["used"] == before
    with pytest.raises(ValueError, match="no redispatch"):
        restarted.claim_sequence_child("sequence", owner=OWNER, ordinal=0)


def test_claimed_state_cannot_be_relabelled_held_to_refund(tmp_path):
    ledger = prepared(tmp_path)
    reserve(ledger)
    first = ledger.claim_sequence_child("sequence", owner=OWNER, ordinal=0)
    with ledger.db() as db:
        db.execute("UPDATE operations SET state='HELD' WHERE id=?", (first["id"],))
    with pytest.raises(ValueError, match="cannot regain"):
        ledger.cancel_sequence_held("sequence", owner=OWNER)
    assert ledger.status(owner=OWNER)["used"]["numerical_milliseconds"] == 1440000
