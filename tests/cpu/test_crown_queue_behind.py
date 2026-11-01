"""A later crown candidate is never decided ahead of an earlier one that is still undecided (admission order at the door).

Claims: while an earlier crown decision of the Challenge is UNRESOLVED (the host could not make it), `consider_private` queues a
later crown-worthy candidate (no decision, no repeat or rebuild spent) instead of crowning it; once the earlier one is decided,
the later one is decided against the incumbent as it stands at its turn; a stuck earlier record raises the alert naming the queued
candidates and nothing jumps it; with no unresolved record everything is as before; and the incumbent event is stamped with the
decision time, not the admission time. Synthetic grades and a stand-in rebuild."""

from __future__ import annotations

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import crown_pause_sweep as sweeper
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest
from tests.cpu.test_crown_average_wiring import (
    CHALLENGE,
    KEY,
    Repeat,
    _active,
    _body,
    _comparator,
    _pair,
    _Pairs,
)

EXAM = digest("exam")
PIN = digest("pin")
T0 = 1_000_000.0
FAIL_ALL = {i: bp.FAILED_INFRA for i in range(10)}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    clock = [T0]
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = PoolStore(state / "pool.sqlite3", clock=lambda: clock[0])
    for model in ("a", "b", "c"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge=CHALLENGE,
            strategy={},
            binding={"challenge": {"id": CHALLENGE}},
        )
    a, b, c = _body("a", 0.70), _body("b", 0.80), _body("c", 0.90)
    pairs = {"a": _pair(a, None), "b": _pair(b, None), "c": _pair(c, None)}
    monkeypatch.setattr(store, "private_evaluation_pair", _Pairs(pairs))
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    repeats = {
        "a": Repeat("a", [0.70] * 10, FAIL_ALL),  # the host cannot rebuild a
        "b": Repeat("b", [0.80] * 10),
        "c": Repeat("c", [0.90] * 10),
    }
    average = _active(tmp_path)

    def consider(sid):
        return flow.consider_private(
            sid, KEY, _comparator(), repeat=repeats[sid], average=average
        )

    def live(sid):
        """What the receiver does for a live grade: consider it and file it if it is paused, queued or to retry."""
        outcome = consider(sid)
        retention._file_if_paused(
            store,
            {**outcome, "evaluation_key": KEY},
            "pack",
            sid,
            EXAM,
            repeats[sid],
            PIN,
        )
        return outcome

    def reconsider(record):
        return consider(record["submission_id"])

    return store, clock, pairs, repeats, live, reconsider, (a, b, c)


def sweep(store, reconsider):
    return sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)


def test_a_later_crown_worthy_candidate_is_queued_behind_an_undecided_earlier_one(rig):
    store, _clock, _pairs, repeats, live, _reconsider, _bodies = rig
    first = live("a")  # the host cannot rebuild a: undecided
    assert (
        first["outcome"] == bp.UNAVAILABLE and first["reason"] == ca.REBUILD_UNAVAILABLE
    )
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a"]
    queued = live("b")  # b would be the first crown: it waits
    assert queued["outcome"] == bp.UNAVAILABLE and queued["reason"] == bp.CROWN_QUEUED
    assert store.incumbent() is None  # nothing jumped the queue
    assert repeats["b"].asked == []  # no rebuild or repeat was spent on it
    assert [r["submission_id"] for r in store.paused_crowns()] == [
        "a",
        "b",
    ]  # filed in admission order
    assert live("b")["reason"] == bp.CROWN_QUEUED  # considered again, still behind a


def test_once_the_earlier_one_is_decided_the_later_one_is_decided_against_the_incumbent_of_its_turn(
    rig,
):
    store, clock, pairs, repeats, live, reconsider, (a, b, _c) = rig
    live("a")
    live("b")
    repeats["a"] = Repeat("a", [0.70] * 10)  # the host recovers
    clock[0] += sweeper.EPOCH_SECONDS + 1
    pairs["b"] = _pair(b, a)  # b's grade will meet a, as the king then
    done = sweep(store, reconsider)
    assert [sid for sid, _ in done] == ["a", "b"]
    assert done[0][1].startswith(bp.FIRST_INCUMBENT)  # a is decided first ...
    assert done[1][1].startswith(bp.CHALLENGER)  # ... and b against a
    assert store.incumbent()["model_id"] == "b"
    assert store.paused_crowns() == []


def test_a_stuck_earlier_record_raises_the_alert_naming_the_queued_and_nothing_jumps(
    rig,
):
    store, clock, _pairs, repeats, live, reconsider, _bodies = rig
    live("a")
    live("b")
    live("c")
    for _ in range(sweeper.ALERT_AFTER):
        clock[0] += sweeper.EPOCH_SECONDS + 1
        assert sweep(store, reconsider) == []
    (alert,) = store.crown_pause_alerts()
    assert alert["code"] == "crown_pause_blocked_by_undecided"
    assert alert["submission_id"] == "a" and alert["waiting"] == 2
    assert alert["queued"] == ["b", "c"]
    assert store.incumbent() is None
    assert repeats["b"].asked == [] and repeats["c"].asked == []


def test_with_no_unresolved_record_the_plain_path_is_unchanged(rig):
    store, _clock, _pairs, repeats, live, _reconsider, _bodies = rig
    outcome = live("b")  # nothing is waiting
    assert (
        outcome["outcome"] == bp.FIRST_INCUMBENT
        and outcome["reason"] == ca.FIRST_BEATS_BASELINE
    )
    assert store.incumbent()["model_id"] == "b" and store.paused_crowns() == []
    assert (
        len(repeats["b"].asked) == 11
    )  # the N rebuilds and the host-fault second build, as before
    # a contender with its OWN record and nothing before it is decided (the oldest is never queued)
    assert (
        bp.BankPromotion(store, registered_source_receipt_sha256=PIN)._undecided_before(
            "b", KEY
        )
        == []
    )


def test_the_incumbent_event_is_stamped_with_the_decision_time_not_the_admission_time(
    rig,
):
    store, clock, pairs, repeats, live, reconsider, (a, b, _c) = rig
    admitted = clock[0]
    live("a")
    live("b")
    repeats["a"] = Repeat("a", [0.70] * 10)
    clock[0] += 3 * sweeper.EPOCH_SECONDS
    pairs["b"] = _pair(b, a)
    sweep(store, reconsider)
    events = store.events("incumbent")
    assert [e["body"]["model_id"] for e in events] == ["a", "b"]
    assert all(e["body"]["previous"] != "x" for e in events)
    assert store.clock() == clock[0] and clock[0] > admitted
    with store.db() as db:
        (since,) = db.execute("SELECT since FROM incumbent WHERE id=1").fetchone()
    assert since == clock[0]  # the weights ledger reads the time the crown was DECIDED


def test_only_unresolved_records_count_and_in_admission_order(rig):
    store, _clock, _pairs, _repeats, live, reconsider, _bodies = rig
    live("a")  # undecided: unresolved
    live("b")  # queued behind a
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a", "b"]
    store.resolve_crown_pause("a", KEY, "INCUMBENT_KEEPS:resolved_by_a_test")
    # a resolved earlier record queues nobody: b is now the oldest unresolved one and is decided
    assert [r["submission_id"] for r in store.paused_crowns()] == ["b"]
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    assert flow._undecided_before("b", KEY) == []
    assert [r["submission_id"] for r in flow._undecided_before("c", KEY)] == ["b"]
    assert reconsider({"submission_id": "b"})["outcome"] == bp.FIRST_INCUMBENT
