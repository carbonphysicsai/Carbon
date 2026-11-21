"""A crown sweep whose `reconsider` RAISES is no longer silent (14 Nov 2026).

`crown_pause_sweep.sweep` used to end the tick on any exception with no journal line, no attempt and no alert, every tick, at the
oldest record (so every later record waited with it). Now: one journal line (record id, exception type, closed code), a failed
attempt counted so the retry is spaced, and the typed alert after ALERT_AFTER attempts. The record stays unresolved in its place
and the sweep goes on to the later records (over-broad rules audit #14; a later crown change is queued behind it by
`consider_private`, which these doubles stand in for). Synthetic fixtures only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crown_fixtures import KEY, _store

from carbon.battery.pool_store import StateError
from carbon.challenge_validator import crown_hold
from carbon.challenge_validator import crown_pause_sweep as sweep
from carbon.challenge_validator.interface import digest

EXAM = digest("exam")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    first, changed = dict(sweep._FIRST_SEEN), dict(sweep._KING_CHANGED)
    monkeypatch.setattr(crown_hold, "ACTIVE", False)
    yield
    sweep._FIRST_SEEN.clear()
    sweep._FIRST_SEEN.update(first)
    sweep._KING_CHANGED.clear()
    sweep._KING_CHANGED.update(changed)


@pytest.fixture
def world(tmp_path, monkeypatch):
    store = _store(tmp_path)
    now = [1000.0]
    store.clock = lambda: now[0]
    for model in ("b", "c"):  # b is the oldest unresolved record, c waits behind it
        store.record_crown_paused(
            model,
            KEY,
            kind="pack",
            exam=EXAM,
            entry_id=digest("entry"),
            pin=digest("pin"),
        )
    lines = []
    monkeypatch.setattr(
        sweep.koth_journal,
        "note",
        lambda event, **fields: lines.append((event, fields)),
    )
    return store, now, lines


def _tick(store, reconsider):
    return sweep.sweep(store, reconsider, kind="pack", current_exam=EXAM)


def _alerts(store):
    with store.db() as db:
        return [
            json.loads(row[0])
            for row in db.execute(
                "SELECT body FROM operations WHERE kind='crown_pause_alert.v1'"
            )
        ]


def test_a_raising_reconsider_journals_once_counts_an_attempt_and_the_sweep_goes_on(
    world,
):
    store, _now, lines = world
    asked = []

    def reconsider(record):
        asked.append(record["submission_id"])
        if record["submission_id"] == "c":
            # what `consider_private` answers a later crown change while b is unresolved
            return {"outcome": "UNAVAILABLE", "reason": "queued_behind_undecided_crown"}
        raise StateError("evaluation_source_changed")

    assert _tick(store, reconsider) == []
    assert asked == ["b", "c"]  # b keeps its place; c is asked and queues behind it
    # c's queued contention is journaled as every reconsider is (`koth_contention`); the failure line is b's alone
    assert [line for line in lines if line[0] == "crown_sweep_reconsider_failed"] == [
        (
            "crown_sweep_reconsider_failed",
            {
                "submission_id": "b",
                "error": "StateError",
                "code": "evaluation_source_changed",
            },
        )
    ]
    attempts, last = store.crown_pause_attempts("b", KEY)
    assert attempts == 1 and last == 1000.0
    assert store.crown_pause_attempts("c", KEY) == (
        0,
        None,
    )  # queued is not a failed attempt
    assert [r["submission_id"] for r in store.paused_crowns("pack")] == [
        "b",
        "c",
    ]  # nothing resolved or skipped


def test_the_next_tick_is_spaced_and_a_later_one_tries_again(world):
    store, now, lines = world
    asked = []

    def reconsider(record):
        asked.append(record["submission_id"])
        raise StateError("evaluation_source_changed")

    _tick(store, reconsider)
    now[0] += 60.0  # the next tick: inside the retry spacing of both
    _tick(store, reconsider)
    assert asked == ["b", "c"] and len(lines) == 2  # not tried again, no new line
    now[0] += sweep.RETRY_SECONDS  # past the spacing
    _tick(store, reconsider)
    assert asked == ["b", "c", "b", "c"] and len(lines) == 4
    assert store.crown_pause_attempts("b", KEY)[0] == 2


def test_the_typed_alert_follows_after_three_attempts_and_names_the_records_behind_it(
    world,
):
    store, now, lines = world

    def reconsider(record):
        if record["submission_id"] == "c":
            return {"outcome": "UNAVAILABLE", "reason": "queued_behind_undecided_crown"}
        raise StateError("evaluation_source_changed")

    for _ in range(sweep.ALERT_AFTER):
        _tick(store, reconsider)
        now[0] += sweep.RETRY_SECONDS + 1
    (alert,) = _alerts(store)  # b's only: c queued behind it is not a failed decision
    assert alert["code"] == "crown_pause_blocked_by_undecided"  # c may wait behind b
    assert alert["attempts"] == sweep.ALERT_AFTER and alert["queued"] == ["c"]
    assert alert["last_code"] == "EXCEPTION:StateError:evaluation_source_changed"
    failed = [line for line in lines if line[0] == "crown_sweep_reconsider_failed"]
    assert len(failed) == sweep.ALERT_AFTER  # b's; c's lines are its queued contentions
    assert [f["candidate"] for e, f in lines if e == "koth_contention"] == [
        "c"
    ] * sweep.ALERT_AFTER


def test_an_exception_without_a_code_and_a_hostile_code_never_leak_text(world):
    store, _now, lines = world

    class Plain(Exception):
        code = "x" * 500  # not a closed code

    def reconsider(record):
        raise Plain("private path /srv/secret/x")

    _tick(store, reconsider)
    _event, fields = lines[0]
    assert fields == {"submission_id": "b", "error": "Plain", "code": ""}
    assert "secret" not in json.dumps(lines)


def test_a_reconsider_that_returns_is_unchanged_and_a_failing_store_write_never_ends_the_tick(
    world, monkeypatch
):
    store, _now, lines = world
    ok = {
        "outcome": "INCUMBENT_KEEPS",
        "reason": "mean_within_margin_or_tie",
        "evaluation_key": KEY,
    }
    resolved = _tick(store, lambda record: ok)
    assert [sid for sid, _ in resolved][:1] == ["b"]
    failures = [e for e, _ in lines if e == "crown_sweep_reconsider_failed"]
    assert failures == []  # the ordinary path: no failure line
    # a store that cannot write the attempt: the journal line is the record, nothing raises
    monkeypatch.setattr(
        store,
        "note_crown_pause_attempt",
        lambda *a: (_ for _ in ()).throw(OSError("disk")),
    )

    def boom(record):
        raise StateError("x")

    store.record_crown_paused(  # b and c were resolved above: a new record for the failing decision
        "d", KEY, kind="pack", exam=EXAM, entry_id=digest("entry"), pin=digest("pin")
    )
    _tick(store, boom)
    assert [e for e, _ in lines if e == "crown_sweep_reconsider_failed"]
