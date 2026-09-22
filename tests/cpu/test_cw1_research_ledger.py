"""Finite campaign authority survives replay and uncertain billing."""

import pytest

from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    NO_BUDGET,
    SERVICE_LIMITS,
    VERSION,
    CampaignLedger,
)


def ledger(
    tmp_path,
    clock=lambda: 1000,
    final_reserve=None,
    ceilings=DEVELOPMENT_CEILINGS,
    elapsed_seconds=DEVELOPMENT_ELAPSED_SECONDS,
):
    """A campaign. `ceilings=None` is a miner who set no budget at all."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    value = CampaignLedger(tmp_path, clock=clock)
    manifest = {
        "schema": VERSION,
        "ceilings": ceilings,
        **({} if final_reserve is None else {"final_reserve": final_reserve}),
        "elapsed_seconds": elapsed_seconds,
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
    # Over the budget itself, rather than over a reserve the miner never asked
    # for: 800M spent plus 250M wanted exceeds the 1B cap.
    with pytest.raises(ValueError, match="miner budget: provider_nanodollars"):
        reserve(
            value,
            "second",
            resources={"provider_attempts": 1, "provider_nanodollars": 250000000},
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
    # Carbon's own reference service, so the counter still cannot reset - but it
    # binds at Carbon's service capacity rather than at a miner budget, and no
    # part of it is held back for a final phase the miner never asked for.
    reserve(value, "under-service-capacity", resources={"reference_invocations": 1905})
    with pytest.raises(ValueError, match="carbon service capacity"):
        reserve(value, "references", resources={"reference_invocations": 2049})


def test_failures_consume_attempts_and_exploration_may_spend_it_all(tmp_path):
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
    # No reserve was asked for, so exploration may spend the whole budget. The
    # budget itself still binds exactly where it was set.
    reserve(value, "spends-what-was-not-reserved", resources={"provider_attempts": 89})
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        reserve(value, "over-budget", resources={"provider_attempts": 8})


def test_elapsed_clock_starts_on_first_operation_and_expiry_blocks_new_dispatch(
    tmp_path,
):
    now = [1000]
    value = ledger(tmp_path, clock=lambda: now[0])
    assert value.status(owner="alice")["started_unix"] is None
    now[0] = 2000
    reserve(value, resources={"provider_attempts": 1})
    assert value.status(owner="alice")["started_unix"] == 2000
    now[0] += DEVELOPMENT_ELAPSED_SECONDS
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
    assert restarted.status(owner="alice")["budget"] == DEVELOPMENT_CEILINGS
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


def test_a_final_reserve_binds_only_when_the_miner_asks_for_one(tmp_path):
    """The replacement for the compulsory reserve.

    Holding back part of a final phase is useful, and it is the miner's to
    decline: deciding it for them would be Carbon allocating their money. So it
    is offered, and it binds exactly when taken up.
    """
    asked = ledger(tmp_path, final_reserve=True)
    with pytest.raises(ValueError, match="miner budget: provider_attempts"):
        reserve(asked, "held-back", resources={"provider_attempts": 89})

    declined = ledger(tmp_path / "other", final_reserve=False)
    reserve(declined, "all-of-it", resources={"provider_attempts": 89})


def test_a_campaign_with_no_budget_is_a_supported_state(tmp_path):
    """The decision this module exists to implement.

    A miner who set no budget has no budget. Asserted as work being admitted
    far beyond every former development ceiling, so a reinstated cap - or a
    large stand-in number posing as one - fails here.
    """
    value = ledger(tmp_path / "unbounded", ceilings=None, elapsed_seconds=None)

    reserve(
        value,
        "far-beyond-the-old-ceiling",
        resources={
            "research_trials": DEVELOPMENT_CEILINGS["research_trials"] * 100,
            "provider_nanodollars": DEVELOPMENT_CEILINGS["provider_nanodollars"] * 100,
        },
    )
    status = value.status(owner="alice")
    assert status["budget"] is None
    assert status["elapsed_limit_seconds"] is None
    assert status["carbon_service_limits"] == SERVICE_LIMITS


def test_carbon_service_capacity_applies_even_with_no_miner_budget(tmp_path):
    """Carbon's infrastructure is not the miner's money, and is named apart."""
    value = ledger(tmp_path / "service", ceilings=None, elapsed_seconds=None)
    with pytest.raises(ValueError, match="carbon service capacity"):
        reserve(value, "over", resources={"reference_invocations": 2049})


def test_no_budget_is_a_state_and_not_a_very_large_number(tmp_path):
    """A stand-in number would read as a limit to the next person.

    NO_BUDGET supports no ordering and no truth value, so a code path that
    forgets to skip the headroom check raises at the mistake instead of
    silently admitting work against a limit nobody set.
    """
    assert NO_BUDGET is not None
    with pytest.raises(TypeError):
        _ = 5 > NO_BUDGET
    with pytest.raises(TypeError):
        bool(NO_BUDGET)
    assert repr(NO_BUDGET) == "NO_BUDGET"
