"""Synthetic current-source coherence; no real key, chain or host execution."""

import asyncio
import dataclasses
import traceback

import pytest
from test_battery_od4a_dispatch import chain, snapshot
from test_reward_testnet_winner_publication import BATTERY, POLICY, composed, promotion

from carbon.rewards import testnet_winner_publication as twp
from carbon.rewards.core import Q12
from carbon.rewards.winner_decay import DAY_MS


def stored(issuer, ref):
    with issuer.receipts.transaction() as db:
        return db.execute(
            "SELECT digest,body FROM testnet_winner_intent_v1 WHERE identity=?",
            (ref.identity,),
        ).fetchone()


def record(issuer, state, value=None, *, coldkeys=None):
    return issuer.ledger.observe(
        POLICY,
        BATTERY,
        promotion() if value is None else value,
        {"miner-hotkey": "miner-coldkey"} if coldkeys is None else coldkeys,
        state.timestamp_ms,
    )


@pytest.mark.parametrize("configured", [False, True])
def test_absent_current_source_keeps_burn_consistent_without_erasing_history(
    tmp_path, configured
):
    issuer, backend, _ = composed(
        tmp_path, source=(lambda: None) if configured else None
    )
    first = snapshot(chain(), block=925)
    record(issuer, first)
    history = issuer.ledger.path.read_bytes()
    for block in (925, 1085, 1445):
        state = snapshot(chain(), block=block)
        shown = twp.preview(issuer, state)
        assert shown["records"][BATTERY] is None
        ref = issuer.issue(state)
        before = stored(issuer, ref)
        result = issuer.resolve(ref, state)
        assert result["intent"]["targets"] == shown["targets"]
        assert result["intent"]["targets"]["burn"] == Q12
        assert result["intent"]["targets"]["winners"] == []
        assert result["intent"]["ledger"][BATTERY] is None
        assert issuer.issue(state) == ref and stored(issuer, ref) == before
        assert issuer.ledger.path.read_bytes() == history
    assert backend.executions == backend.signed == 0


def test_same_snapshot_burn_reaches_existing_checked_fixture_publisher(tmp_path):
    issuer, backend, publisher = composed(tmp_path, source=lambda: None)
    record(issuer, backend.state)
    before = issuer.ledger.path.read_bytes()
    ref = issuer.issue(backend.state)
    result = asyncio.run(publisher.publish(ref))
    assert result["state"] == "ROW_VERIFIED"
    assert result["document"]["plan"]["q12"] == [[0, Q12]]
    assert issuer.ledger.path.read_bytes() == before
    assert asyncio.run(publisher.publish(ref)) == result
    assert backend.executions == backend.signed == 1  # Scripted counters only.


def test_current_model_selects_matching_older_record_and_original_clock(tmp_path):
    issuer, backend, _ = composed(tmp_path)
    state = backend.state
    original = record(issuer, state)
    later = dataclasses.replace(state, timestamp_ms=state.timestamp_ms + 1000)
    # The unrelated miner had a known identity when its historical record was
    # observed; it is absent from the current publication snapshot.
    record(
        issuer,
        later,
        promotion("unregistered", "unrelated-later-model"),
        coldkeys={
            "miner-hotkey": "miner-coldkey",
            "unregistered": "unrelated-coldkey",
        },
    )
    before = issuer.ledger.path.read_bytes()
    ref = issuer.issue(later)
    result = issuer.resolve(ref, later)
    assert result["intent"]["targets"]["winners"][0][0]["hotkey"] == "miner-hotkey"
    assert (
        twp.preview(issuer, later)["records"][BATTERY]["clock_ms"]
        == original["clock_ms"]
    )
    assert issuer.ledger.path.read_bytes() == before
    assert backend.executions == backend.signed == 0


@pytest.mark.parametrize("observed", [False, True])
def test_real_current_promotion_change_refuses_even_when_numeric_targets_match(
    tmp_path, observed
):
    current = {"value": promotion()}
    issuer, backend, publisher = composed(tmp_path, source=lambda: current["value"])
    state = backend.state
    ref = issuer.issue(state)
    original = stored(issuer, ref)
    current["value"] = promotion(model="new-current-model")
    if observed:
        record(issuer, state, current["value"])
    history = issuer.ledger.path.read_bytes()
    with pytest.raises(
        twp.WinnerPublicationRefused, match="TARGETS_CHANGED_REISSUE_NEXT_EPOCH"
    ):
        asyncio.run(publisher.publish(ref))
    assert issuer.issue(state) == ref and stored(issuer, ref) == original
    assert issuer.ledger.path.read_bytes() == history
    assert backend.executions == backend.signed == 0


def test_current_promotion_disappearing_after_issue_is_real_drift(tmp_path):
    current = {"value": promotion()}
    issuer, backend, publisher = composed(tmp_path, source=lambda: current["value"])
    ref = issuer.issue(backend.state)
    original = stored(issuer, ref)
    history = issuer.ledger.path.read_bytes()
    current["value"] = None
    with pytest.raises(
        twp.WinnerPublicationRefused, match="TARGETS_CHANGED_REISSUE_NEXT_EPOCH"
    ):
        asyncio.run(publisher.publish(ref))
    assert issuer.issue(backend.state) == ref and stored(issuer, ref) == original
    assert issuer.ledger.path.read_bytes() == history
    assert backend.executions == backend.signed == 0


def test_halving_drift_still_refuses_and_never_resets_clock(tmp_path):
    issuer, backend, publisher = composed(tmp_path)
    start = backend.state.timestamp_ms
    record(issuer, backend.state)
    before_boundary = dataclasses.replace(
        backend.state, timestamp_ms=start + DAY_MS - 1
    )
    ref = issuer.issue(before_boundary)
    original = stored(issuer, ref)
    history = issuer.ledger.path.read_bytes()
    backend.state = dataclasses.replace(
        snapshot(chain(), block=before_boundary.finalized_block + 1),
        timestamp_ms=start + DAY_MS,
    )
    with pytest.raises(
        twp.WinnerPublicationRefused, match="TARGETS_CHANGED_REISSUE_NEXT_EPOCH"
    ):
        asyncio.run(publisher.publish(ref))
    assert issuer.ledger.records(BATTERY)[0]["clock_ms"] == start
    assert (
        issuer.ledger.path.read_bytes() == history and stored(issuer, ref) == original
    )
    assert backend.executions == backend.signed == 0


@pytest.mark.parametrize("mode", ["issue", "preview", "resolve"])
@pytest.mark.parametrize("bad", ["raised", {}, {"model_id": "m1"}, False])
def test_unavailable_or_malformed_source_never_becomes_burn_or_history(
    tmp_path, mode, bad
):
    current = {"value": promotion()}

    def source():
        if current["value"] == "raised":
            raise RuntimeError("synthetic-private-provider-marker")
        return current["value"]

    issuer, backend, publisher = composed(tmp_path, source=source)
    state = backend.state
    ref = issuer.issue(state)
    history = issuer.ledger.path.read_bytes()
    current["value"] = bad
    newer = snapshot(chain(), block=1085)
    with pytest.raises(
        twp.WinnerPublicationRefused, match="WINNER_SOURCE_UNAVAILABLE"
    ) as refused:
        if mode == "issue":
            issuer.issue(newer)
        elif mode == "preview":
            twp.preview(issuer, state)
        else:
            asyncio.run(publisher.publish(ref))
    assert str(refused.value) == "WINNER_SOURCE_UNAVAILABLE"
    assert "synthetic-private-provider-marker" not in "".join(
        traceback.format_exception(refused.value)
    )
    assert issuer.ledger.path.read_bytes() == history
    assert backend.executions == backend.signed == 0
