"""Finite campaign authority survives replay and uncertain billing."""

import pytest

from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)


def ledger(tmp_path, clock=lambda: 1000):
    value = CampaignLedger(tmp_path, clock=clock)
    manifest = {
        "schema": VERSION,
        "ceilings": CEILINGS,
        "elapsed_seconds": ELAPSED_SECONDS,
        "campaign_id": "test-only",
        "implementation": "fixture",
        "objective": "balanced-v2",
        "sampling": "test-only",
        "control": "test-only",
        "selection": "test-only",
        "replica_policy": "three",
        "provider": "test-only",
        "owner": "alice",
    }
    value.freeze(manifest)
    return value


def reserve(
    value,
    identity="operation-1",
    owner="alice",
    resources=None,
    phase="research",
    request=None,
):
    return value.reserve(
        identity,
        owner=owner,
        phase=phase,
        request=request or {"hypothesis": "test"},
        resources=resources or {"research_trials": 1, "numerical_milliseconds": 600000},
    )


def test_restart_never_reexecutes_reserved_or_completed_work(tmp_path):
    value = ledger(tmp_path)
    assert reserve(value)["dispatch"]
    restarted = CampaignLedger(tmp_path, clock=lambda: 1001)
    assert reserve(restarted) == {
        "dispatch": False,
        "state": "RESERVED",
        "result": None,
    }
    restarted.finish(
        "operation-1",
        owner="alice",
        state="SUCCEEDED",
        actual={"research_trials": 1, "numerical_milliseconds": 2000},
        result={"loss": 0.2},
    )
    assert reserve(value) == {
        "dispatch": False,
        "state": "SUCCEEDED",
        "result": {"loss": 0.2},
    }
    assert value.status(owner="alice")["used"]["research_trials"] == 1


def test_conflicting_request_or_owner_cannot_replay(tmp_path):
    value = ledger(tmp_path)
    reserve(value)
    for kwargs in (
        {"owner": "bob"},
        {"request": {"different": True}},
        {"resources": {"research_trials": 2}},
    ):
        with pytest.raises(ValueError, match="conflict"):
            reserve(value, **kwargs)
    assert value.status(owner="bob")["operations"] == []
    with pytest.raises(ValueError, match="unavailable"):
        value.finish(
            "operation-1",
            owner="bob",
            state="CANCELLED",
            actual={"research_trials": 1, "numerical_milliseconds": 0},
            result={},
        )


def test_ambiguous_provider_billing_stays_reserved(tmp_path):
    value = ledger(tmp_path)
    reserve(
        value, resources={"provider_attempts": 1, "provider_nanodollars": 800000000}
    )
    used = value.status(owner="alice")["used"]
    assert used["provider_nanodollars"] == 800000000
    with pytest.raises(ValueError, match="resource admission"):
        reserve(
            value,
            "second",
            resources={"provider_attempts": 1, "provider_nanodollars": 100000000},
        )
    with pytest.raises(ValueError, match="every reserved"):
        value.finish(
            "operation-1",
            owner="alice",
            state="FAILED_INFRA",
            actual={"provider_attempts": 1},
            result={},
        )
    assert value.status(owner="alice")["used"] == used


def test_global_worker_and_reference_counters_cannot_reset(tmp_path):
    value = ledger(tmp_path)
    reserve(value)
    with pytest.raises(ValueError, match="one numerical worker"):
        reserve(value, "second", owner="bob")
    with pytest.raises(ValueError, match="reference_invocations"):
        reserve(value, "references", resources={"reference_invocations": 1905})


def test_failures_consume_attempts_and_final_capacity_is_reserved(tmp_path):
    value = ledger(tmp_path)
    reserve(value, resources={"research_trials": 1, "numerical_milliseconds": 600000})
    with pytest.raises(ValueError, match="cannot be refunded"):
        value.finish(
            "operation-1",
            owner="alice",
            state="FAILED_INFRA",
            actual={"research_trials": 0, "numerical_milliseconds": 10},
            result={},
        )
    value.finish(
        "operation-1",
        owner="alice",
        state="FAILED_INFRA",
        actual={"research_trials": 1, "numerical_milliseconds": 10},
        result={},
    )
    with pytest.raises(ValueError, match="provider_attempts"):
        reserve(value, "too-many", resources={"provider_attempts": 89})


def test_elapsed_clock_starts_on_first_operation_and_expiry_blocks_new_dispatch(
    tmp_path,
):
    now = [1000]
    value = ledger(tmp_path, clock=lambda: now[0])
    assert value.status(owner="alice")["started_unix"] is None
    now[0] = 2000
    reserve(value, resources={"provider_attempts": 1})
    assert value.status(owner="alice")["started_unix"] == 2000
    now[0] += ELAPSED_SECONDS
    with pytest.raises(ValueError, match="elapsed-time"):
        reserve(value, "late", resources={"provider_attempts": 1})
    assert not reserve(value, resources={"provider_attempts": 1})["dispatch"]


def test_notebook_and_capability_request_do_not_grant_resources(tmp_path):
    value = ledger(tmp_path)
    value.note(
        owner="alice",
        kind="capability_request",
        body={"request": "more compute", "disposition": "investigate"},
    )
    restarted = CampaignLedger(tmp_path)
    assert restarted.status(owner="alice")["notes"][0]["kind"] == "capability_request"
    assert restarted.status(owner="bob")["notes"] == []
    assert restarted.status(owner="alice")["ceilings"] == CEILINGS
    assert restarted.status(owner="alice")["started_unix"] is None


@pytest.mark.parametrize(
    "resources",
    [
        {"provider_attempts": True},
        {"provider_nanodollars": -1},
        {"numerical_milliseconds": float("nan")},
        {"unknown": 1},
    ],
)
def test_invalid_accounting_cannot_poison_budget(tmp_path, resources):
    with pytest.raises(ValueError):
        reserve(ledger(tmp_path), resources=resources)
