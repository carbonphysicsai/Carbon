"""Slow-tail F0 + F1a (Graphite-B's plan, TE-B's amendments, Lead 8 Nov): an older submission is never jumped.

F0: the ledger walks a door's tasks OLDEST SUBMISSION FIRST (first OUTCOME row), never by id (random hex), so the grader
(and the rebuild pass, which walks the same order) takes the oldest ungraded task first. F1a: each door's lock rounds,
its rebuilds and its grades alike, queue in the host's one waiting list by the acceptance time of its oldest ungraded
submission, so the door holding the oldest submission on the host goes next. A round without one behaves as before.
Fixture ids and times only."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest
from test_recipe_graded_once import CONTRACT, HOTKEYS, Door, _recipe

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.direct_intake import _WorkLock
from carbon.challenge_validator.ledger import AttemptLedger

POLL = 0.05
# ids whose sort order is the REVERSE of their submission order: the old order would grade the newest first
NEWEST_FIRST_BY_ID = ["rtsk_" + c * 64 for c in "fedcb"]


def _outcome(ledger, sid, hotkey=HOTKEYS[0], contract=CONTRACT):
    ledger.record(
        SimpleNamespace(
            hotkey=hotkey,
            receipt={"sequence": 1, "digest": "d", "block": 1},
            contract_digest=contract,
        ),
        kind="OUTCOME",
        submission_id=sid,
    )


# --- F0: the ledger order ----------------------------------------------------------------------------------------------


def test_the_ledger_walks_tasks_oldest_submission_first(tmp_path):
    clock = iter(range(1000, 2000, 10))
    ledger = AttemptLedger(tmp_path / "a.sqlite3", clock=lambda: next(clock))
    for sid in NEWEST_FIRST_BY_ID[:3]:
        _outcome(ledger, sid)
    _outcome(
        ledger, NEWEST_FIRST_BY_ID[0]
    )  # a later OUTCOME row of the oldest task keeps its first place
    # an intent with no OUTCOME yet (an interrupted start) comes after, by id
    ledger.record_recipe_task_intent(CONTRACT, NEWEST_FIRST_BY_ID[4], HOTKEYS[1], "r")
    ledger.record_recipe_task_intent(CONTRACT, NEWEST_FIRST_BY_ID[3], HOTKEYS[1], "r")
    assert ledger.submitted_outcomes(CONTRACT) == (
        *NEWEST_FIRST_BY_ID[:3],
        NEWEST_FIRST_BY_ID[4],
        NEWEST_FIRST_BY_ID[3],
    )
    assert ledger.first_outcome_ns(CONTRACT, NEWEST_FIRST_BY_ID[0]) == 1000
    assert ledger.first_outcome_ns(CONTRACT, NEWEST_FIRST_BY_ID[2]) == 1020
    assert ledger.first_outcome_ns(CONTRACT, NEWEST_FIRST_BY_ID[4]) is None
    # another contract's rows are not this one's
    _outcome(ledger, "rtsk_" + "a" * 64, contract="sha256:" + "9" * 64)
    assert "rtsk_" + "a" * 64 not in ledger.submitted_outcomes(CONTRACT)


@pytest.fixture
def door(tmp_path):
    return Door(tmp_path)


def test_an_old_task_is_graded_before_every_newer_one_on_its_door(door):
    """The grader's round takes the oldest ready task: newer submissions with lower ids never jump it."""
    for n, sid in enumerate(NEWEST_FIRST_BY_ID[:4]):
        door.submit(sid, HOTKEYS[n], _recipe(n + 1))
    door.ready |= set(NEWEST_FIRST_BY_ID[:4])
    assert door.grader.pending() == NEWEST_FIRST_BY_ID[:4]
    for _ in range(4):
        door.grader.run_once()
    assert door.graded == NEWEST_FIRST_BY_ID[:4]


def test_a_newer_arrival_never_jumps_the_oldest_waiting_task(door):
    """Arrivals between rounds (the busy-door shape): the oldest ready task still goes first every round."""
    old = NEWEST_FIRST_BY_ID[0]
    door.submit(old, HOTKEYS[0], _recipe(1))
    newer = NEWEST_FIRST_BY_ID[1:4]
    for n, sid in enumerate(newer):
        door.submit(sid, HOTKEYS[n + 1], _recipe(n + 2))
    door.ready |= {old, *newer}
    door.grader.run_once()
    assert door.graded == [old]


def test_the_doors_place_is_its_oldest_ungraded_submission(door):
    assert door.grader.oldest_pending_ns() is None
    door.submit(NEWEST_FIRST_BY_ID[0], HOTKEYS[0], _recipe(1))
    first = door.ledger.first_outcome_ns(CONTRACT, NEWEST_FIRST_BY_ID[0])
    door.submit(NEWEST_FIRST_BY_ID[1], HOTKEYS[1], _recipe(2))
    assert door.grader.oldest_pending_ns() == first
    door.ready.add(NEWEST_FIRST_BY_ID[0])
    door.grader.run_once()
    assert door.grader.oldest_pending_ns() == door.ledger.first_outcome_ns(
        CONTRACT, NEWEST_FIRST_BY_ID[1]
    )


# --- F1a: the host's one waiting list ----------------------------------------------------------------------------------


@pytest.fixture
def host(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    (host / direct_intake.WAITING_DIR).mkdir(mode=0o700)
    live = {4001: 11}  # another door's live process
    real = direct_intake._process_start
    monkeypatch.setattr(
        direct_intake,
        "_process_start",
        lambda pid: live[pid] if pid in live else real(pid),
    )
    return host


def _other_door_waits_since(host, since):
    (host / direct_intake.WAITING_DIR / "4001-11").write_text(str(since))


def _try(work, kind, **kw):
    """Enter one round in a thread; returns (entered event, release event, thread)."""
    entered, release = threading.Event(), threading.Event()

    def run():
        try:
            with work.taking(kind, **kw):
                entered.set()
                release.wait(5)
        except direct_intake.WorkDeclined:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return entered, release, thread


@pytest.mark.parametrize("kind", ["grade", "advance"])
def test_a_round_holding_the_older_submission_goes_first(host, kind):
    _other_door_waits_since(host, 2000)
    work = _WorkLock(host, poll_s=POLL)
    has = (lambda: True) if kind == "grade" else None
    entered, release, thread = _try(work, kind, has_work=has, since=lambda: 1000)
    assert entered.wait(2)
    release.set()
    thread.join(2)


@pytest.mark.parametrize("kind", ["grade", "advance"])
def test_a_round_holding_a_newer_submission_waits_for_the_older_door(host, kind):
    """Even an advance (rebuild) round: it may not take the free lock ahead of an older submission's door."""
    _other_door_waits_since(host, 1000)
    stop = threading.Event()
    work = _WorkLock(host, poll_s=POLL, stop=stop)
    has = (lambda: True) if kind == "grade" else None
    entered, release, thread = _try(work, kind, has_work=has, since=lambda: 2000)
    time.sleep(8 * POLL)
    assert not entered.is_set()
    # its own place in the list is its oldest submission's time, not the moment it began to wait
    mine = [
        p for p in (host / direct_intake.WAITING_DIR).iterdir() if p.name != "4001-11"
    ]
    assert [p.read_text() for p in mine] == ["2000"]
    (
        host / direct_intake.WAITING_DIR / "4001-11"
    ).unlink()  # the older door got its turn
    assert entered.wait(2)
    release.set()
    thread.join(2)
    assert not [
        p for p in (host / direct_intake.WAITING_DIR).iterdir()
    ]  # its entry is gone once it holds the lock


def test_an_advance_round_without_a_place_never_queues_as_before(host):
    _other_door_waits_since(host, 1000)
    work = _WorkLock(host, poll_s=POLL)
    entered, release, thread = _try(work, "advance")
    assert entered.wait(2)
    release.set()
    thread.join(2)


def test_a_failing_place_reader_only_loses_the_place(host):
    _other_door_waits_since(host, 1000)
    work = _WorkLock(host, poll_s=POLL)

    def broken():
        raise RuntimeError("ledger busy")

    entered, release, thread = _try(work, "advance", since=broken)
    assert entered.wait(2)  # as before: an advance round without a place does not queue
    release.set()
    thread.join(2)
    for odd in (-1, 1.5, "1000", True):
        assert (
            direct_intake._Taking(work, "advance", None, lambda v=odd: v)._place()
            is None
        )


def test_the_loops_pass_the_graders_place(monkeypatch):
    seen = []

    class Work:
        def taking(self, kind, *, has_work=None, since=None):
            seen.append((kind, since))
            raise direct_intake.WorkDeclined("idle")

    stop = threading.Event()
    grader = SimpleNamespace(
        has_work=lambda: True, oldest_pending_ns=lambda: 5, run_once=lambda: None
    )
    original = stop.wait

    def once(seconds):
        stop.set()
        return original(0)

    monkeypatch.setattr(stop, "wait", once)
    direct_intake._grade_loop(grader, stop, Work())
    stop.clear()
    direct_intake._advance_loop(None, stop, Work(), grader.oldest_pending_ns)
    assert seen == [
        ("grade", grader.oldest_pending_ns),
        ("advance", grader.oldest_pending_ns),
    ]


# --- a frozen place never keeps the head (10 Nov 06:15: RB + Motor starved BT + Cooling) -------------------------------


def _held(work, kind, since, has=None):
    """One round that takes the host lock at once (no other waiter) and releases it."""
    entered, release, thread = _try(work, kind, has_work=has, since=since)
    assert entered.wait(2)
    release.set()
    thread.join(2)


@pytest.mark.parametrize("kind", ["grade", "advance"])
def test_a_place_that_did_not_move_after_its_round_no_longer_goes_first(host, kind):
    """The door's oldest unmarked item never gets a marker (cancelled, orphaned): after one round held with that
    place, its next rounds of the same kind do not take the head again, so a younger door waiting gets its turn.
    """
    stop = threading.Event()
    work = _WorkLock(host, poll_s=POLL, stop=stop)
    has = (lambda: True) if kind == "grade" else None
    _held(work, kind, lambda: 1000, has)  # its turn at the head, with the frozen place
    _other_door_waits_since(host, 2000)  # a younger door now waits
    entered, release, thread = _try(work, kind, has_work=has, since=lambda: 1000)
    time.sleep(8 * POLL)
    if kind == "grade":
        assert (
            not entered.is_set()
        )  # queued as arriving now: behind the younger door's 2000
        (
            host / direct_intake.WAITING_DIR / "4001-11"
        ).unlink()  # the younger door got its turn
        assert entered.wait(2)
    else:
        # an advance round without a place never queues (as before F1a): it takes a free lock, and the post-round
        # stand-back (`_release_host`) is what lets the waiting door in
        assert entered.wait(2)
    release.set()
    thread.join(2)


def test_a_place_that_moved_keeps_its_age_place(host):
    """The oldest item settled: the door's next oldest is a NEW place, so it queues by age again (F1a kept)."""
    work = _WorkLock(host, poll_s=POLL)
    has = lambda: True
    _held(work, "grade", lambda: 1000, has)
    _other_door_waits_since(host, 2000)
    _held(
        work, "grade", lambda: 1500, has
    )  # 1500 < 2000: still ahead of the younger door


def test_a_frozen_place_is_per_kind(host):
    """A rebuild round held with the place does not take the grade round's turn (each step gets one)."""
    work = _WorkLock(host, poll_s=POLL)
    _held(work, "advance", lambda: 1000)
    _other_door_waits_since(host, 2000)
    _held(
        work, "grade", lambda: 1000, lambda: True
    )  # the grade's first turn with it: ahead of 2000
