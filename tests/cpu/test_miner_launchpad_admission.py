"""Non-spending admission/control diagnostics; no campaign evidence."""

import concurrent.futures
import threading
import time

import pytest
from test_cw1_research_ledger import ledger as old_ledger

from carbon.development_session.profile import canonical
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_control import CampaignControl, DispatchStopped
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    CampaignLedger,
)


def managed(tmp_path):
    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    path = tmp_path / "grant.json"
    document = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "fixture-grant",
        "campaign_id": "fixture-campaign",
        "root": str(root),
        "principal": "alice",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": {"implementation": "fixture", "images": ["fixture"]},
        "provider": "openai-responses",
        "account_ref": "fixture-no-credential",
        "campaign_count": 1,
        "ceilings": dict(CEILINGS),
        "elapsed_seconds": ELAPSED_SECONDS,
        "expires_unix": 50000,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    admission = Admission.load(path)
    value = CampaignLedger(root, clock=lambda: 1000, admission=admission)
    control = CampaignControl(value)
    value.generation = control.acquire()
    manifest = {
        "schema": MANIFEST,
        "campaign_id": document["campaign_id"],
        "authority": document["authority"],
        "principal": "alice",
        "owner": "miner-requester",
        "runtime": document["runtime"],
        "grant": admission.binding(),
        "ceilings": document["ceilings"],
        "elapsed_seconds": ELAPSED_SECONDS,
        "implementation": "fixture",
        "objective": "fixture",
        "sampling": "fixture",
        "control": "fixture",
        "selection": "fixture",
        "replica_policy": "three",
        "provider": "fixture",
    }
    value.freeze(manifest)
    return value, control, manifest


def reserve(value, identity="op", resources=None):
    return value.reserve(
        identity,
        owner="miner-requester",
        phase="research",
        request={"test": 1},
        resources=resources or {"research_trials": 1},
    )


def test_d4_original_manifest_and_limits_preserved(tmp_path):
    value = old_ledger(tmp_path)
    assert value.status(owner="alice")["ceilings"] == CEILINGS
    assert value.reserve(
        "old",
        owner="alice",
        phase="research",
        request={},
        resources={"research_trials": 1},
    )["dispatch"]


@pytest.mark.parametrize(
    "field,invalid",
    [
        ("status", "REQUESTED_NOT_GRANTED"),
        ("expires_unix", 999),
        ("principal", "bob"),
        ("profile", "other"),
        ("campaign_count", 2),
        ("runtime", {"implementation": "wrong"}),
        ("authority", "OWNER-C-W1-D4-AUTORESEARCH-01"),
        ("provider", "arbitrary-endpoint"),
        ("retry_allowance", 1),
    ],
)
def test_changed_revoked_or_wrong_grant_blocks_dispatch(tmp_path, field, invalid):
    value, _, _ = managed(tmp_path)
    doc = dict(value.admission.document)
    doc[field] = invalid
    value.admission.path.write_bytes(canonical(doc))
    with pytest.raises(ValueError):
        reserve(value)
    assert value.status(owner="miner-requester")["operations"] == []


def test_shared_grant_cannot_multiply_by_new_root_or_campaign(tmp_path):
    value, _, manifest = managed(tmp_path)
    other = CampaignLedger(
        tmp_path / "second", clock=lambda: 1000, admission=value.admission
    )
    with pytest.raises(ValueError, match="binding"):
        other.freeze(manifest)
    changed = dict(manifest, campaign_id="second")
    with pytest.raises(ValueError, match="differs"):
        value.freeze(changed)


def test_concurrent_launch_retry_reserves_once_and_restart_keeps_usage(tmp_path):
    value, _, _ = managed(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda _: reserve(value), range(4)))
    assert sum(answer["dispatch"] for answer in answers) == 1
    restarted = CampaignLedger(
        value.root,
        clock=lambda: 1001,
        admission=value.admission,
        generation=value.generation,
    )
    assert reserve(restarted)["dispatch"] is False
    assert restarted.status(owner="miner-requester")["used"]["research_trials"] == 1
    assert restarted.status(owner="miner-requester")["started_unix"] == 1000


def test_missing_grant_and_stale_generation_cannot_dispatch(tmp_path):
    value, control, _ = managed(tmp_path)
    reopened = CampaignLedger(value.root)
    with pytest.raises(ValueError, match="admission"):
        reserve(reopened)
    control.acquire()
    with pytest.raises(DispatchStopped):
        reserve(value)


def test_ambiguous_billable_outcome_keeps_reservation_blocks_new_call(tmp_path):
    value, control, _ = managed(tmp_path)
    resources = {"provider_attempts": 1, "provider_nanodollars": 20480000}
    reserve(value, resources=resources)
    with pytest.raises(ValueError, match="unknown provider"):
        reserve(value, "next", resources)
    control.request("stop")
    assert (
        control.settled(value.generation, cleanup_verified=True)
        == "RECONCILIATION_REQUIRED"
    )
    assert (
        value.status(owner="miner-requester")["used"]["provider_nanodollars"]
        == 20480000
    )


def test_pause_waits_for_current_operation_and_resume_keeps_deadline(tmp_path):
    value, control, _ = managed(tmp_path)
    reserve(value)
    control.request("pause")
    thread = threading.Thread(target=value.checkpoint)
    thread.start()
    try:
        time.sleep(0.15)
        assert control.status()["state"] == "PAUSE_REQUESTED"
        value.finish(
            "op",
            owner="miner-requester",
            state="SUCCEEDED",
            actual={"research_trials": 1},
            result={},
        )
        time.sleep(0.15)
        assert control.status()["state"] == "PAUSED"
        control.request("resume")
        thread.join(2)
        assert not thread.is_alive()
        assert reserve(value, "next")["dispatch"]
        assert value.status(owner="miner-requester")["started_unix"] == 1000
    finally:
        control.request("resume")
        thread.join(2)


def test_stop_before_dispatch_and_cleanup_failure_never_claim_stopped(tmp_path):
    value, control, _ = managed(tmp_path)
    control.request("stop")
    with pytest.raises(DispatchStopped):
        reserve(value)
    assert (
        control.settled(value.generation, cleanup_verified=False)
        == "RECONCILIATION_REQUIRED"
    )
    assert control.settled(value.generation, cleanup_verified=True) == "STOPPED"
    with pytest.raises(DispatchStopped):
        control.acquire()


def test_final_reserve_and_exhaustion(tmp_path):
    value, _, _ = managed(tmp_path)
    with pytest.raises(ValueError, match="resource admission"):
        reserve(
            value, resources={"provider_nanodollars": CEILINGS["provider_nanodollars"]}
        )
    reserve(value, resources={"research_trials": 16})
    with pytest.raises(ValueError, match="resource admission"):
        reserve(value, "extra")


def test_fresh_unapproved_grant_is_not_authority(tmp_path):
    value, _, manifest = managed(tmp_path)
    doc = dict(value.admission.document, status="REQUESTED_NOT_GRANTED")
    value.admission.path.write_bytes(canonical(doc))
    fresh = Admission.load(value.admission.path)
    with pytest.raises(ValueError, match="explicit Launchpad grant"):
        fresh.verify(
            root=value.root, principal="alice", runtime=manifest["runtime"], now=1000
        )


def test_pause_race_retries_admission_without_consumption(tmp_path, monkeypatch):
    value, control, _ = managed(tmp_path)
    original = value._reserve
    seen = threading.Event()

    def race(*args, **kwargs):
        if not seen.is_set():
            control.request("pause")
            seen.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(value, "_reserve", race)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(reserve, value)
        assert seen.wait(2)
        time.sleep(0.15)
        assert value.status(owner="miner-requester")["used"]["research_trials"] == 0
        control.request("resume")
        assert future.result(2)["dispatch"]
    assert value.status(owner="miner-requester")["used"]["research_trials"] == 1


def test_expired_original_deadline_cannot_resume(tmp_path):
    value, control, _ = managed(tmp_path)
    reserve(value)
    value.clock = lambda: 1000 + ELAPSED_SECONDS
    control.request("pause")
    with pytest.raises(DispatchStopped, match="deadline"):
        value.checkpoint()


@pytest.mark.parametrize("phase", ["research", "final"])
def test_stop_during_admitted_work_preserves_settlement_until_cleanup(tmp_path, phase):
    value, control, _ = managed(tmp_path)
    resources = {"numerical_milliseconds": 720000}
    assert value.reserve(
        "inflight",
        owner="miner-requester",
        phase=phase,
        request={},
        resources=resources,
    )["dispatch"]
    control.request("stop")
    assert control.status()["state"] == "STOPPING"
    with pytest.raises(DispatchStopped):
        value.reserve(
            "late",
            owner="miner-requester",
            phase=phase,
            request={},
            resources=resources,
        )
    value.finish(
        "inflight",
        owner="miner-requester",
        state="SUCCEEDED",
        actual={"numerical_milliseconds": 1234},
        result={"engineering_fixture": True},
    )
    assert (
        control.settled(value.generation, cleanup_verified=False)
        == "RECONCILIATION_REQUIRED"
    )
    assert control.settled(value.generation, cleanup_verified=True) == "STOPPED"
    assert (
        value.status(owner="miner-requester")["used"]["numerical_milliseconds"] == 1234
    )


def test_stop_before_final_dispatch_does_not_create_submission(tmp_path):
    import asyncio

    from carbon.development_session.research_campaign import final_epoch

    value, control, _ = managed(tmp_path)
    control.request("stop")
    with pytest.raises(DispatchStopped):
        asyncio.run(
            final_epoch(
                None,
                value,
                "miner-requester",
                1,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )
    assert not (value.root / "epoch-1").exists()


def test_completed_controller_does_not_imply_scientific_improvement(tmp_path):
    value, control, _ = managed(tmp_path)
    assert (
        control.settled(value.generation, completed=True, cleanup_verified=True)
        == "COMPLETED"
    )
    assert value.status(owner="miner-requester")["operations"] == []
    with pytest.raises(DispatchStopped):
        reserve(value)
