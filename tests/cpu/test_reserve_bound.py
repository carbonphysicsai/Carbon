"""V2's two design-A additions (19 Nov 2026): (1) an early claim that retains past `RETAIN_BEFORE_RESERVE_SECONDS`
no longer holds later reservations or commits, and ends "not yet" at its own turn; (2) two same-recipe tasks picked by
two rounds never both reserve. Threads and stand-in grade steps only.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.development_session import research_carrier

T1, T2 = ("rtsk_" + c * 64 for c in "ab")


@pytest.fixture(autouse=True)
def _no_session(monkeypatch):
    monkeypatch.setattr(research_carrier, "yield_grade_session", lambda: None)


def test_a_claim_stuck_before_its_reservation_stops_holding_the_order(monkeypatch):
    monkeypatch.setattr(grade_sequencer, "RETAIN_BEFORE_RESERVE_SECONDS", 0.2)
    sequencer = grade_sequencer.Sequencer()
    order, a_bound, a_free = [], threading.Event(), threading.Event()
    outcome = {}

    def first():
        with sequencer.task() as task:
            task.bind("a")
            task.release_claim()
            a_bound.set()
            assert a_free.wait(5)  # a stuck retain step
            try:
                grade_sequencer.reserve_turn()
                outcome["a"] = "reserved"
            except grade_sequencer.ReserveTurnExpired:
                outcome["a"] = "not yet"

    def second():
        assert a_bound.wait(5)
        with sequencer.task() as task:
            task.bind("b")
            task.release_claim()
            # past the bound the stuck claim no longer holds it
            grade_sequencer.reserve_turn()
            order.append("reserve b")
            grade_sequencer.claimed()
            grade_sequencer.turn()  # nor the commit order
            order.append("commit b")

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    threads[1].join(5)
    assert order == ["reserve b", "commit b"]
    a_free.set()
    threads[0].join(5)
    # nothing reserved for it: back to pending, uncharged
    assert outcome == {"a": "not yet"}


def test_within_the_bound_the_order_holds(monkeypatch):
    monkeypatch.setattr(grade_sequencer, "RETAIN_BEFORE_RESERVE_SECONDS", 30)
    sequencer = grade_sequencer.Sequencer()
    order, a_bound, a_go = [], threading.Event(), threading.Event()

    def first():
        with sequencer.task() as task:
            task.bind("a")
            task.release_claim()
            a_bound.set()
            assert a_go.wait(5)
            grade_sequencer.reserve_turn()
            order.append("reserve a")
            grade_sequencer.claimed()

    def second():
        assert a_bound.wait(5)
        with sequencer.task() as task:
            task.bind("b")
            task.release_claim()
            grade_sequencer.reserve_turn()
            order.append("reserve b")
            grade_sequencer.claimed()

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    time.sleep(0.3)
    assert order == []
    a_go.set()
    for thread in threads:
        thread.join(5)
    assert order == ["reserve a", "reserve b"]


def test_two_same_recipe_tasks_picked_by_two_rounds_never_both_reserve():
    """The copy decision runs at PICK under the claim lock: the later same-recipe task meets the earlier one still
    unsettled (no marker) and WAITS; only the earlier one reaches its reservation."""
    settled, reserved = set(), []
    grading, release = threading.Event(), threading.Event()
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=SimpleNamespace())
    grader.pending = lambda: [t for t in (T1, T2) if t not in settled]
    grader._allowance_group = lambda task: "g-" + task
    grader._owner_of = lambda task: "5Owner-" + task
    grader._withdrawn_pending = lambda task: False

    def copy_decision(task):
        # the same recipe: T2 is a copy of T1 while T1 has no verdict
        if task == T2 and T1 not in settled:
            return "wait", T1
        return None

    grader._copy_decision = copy_decision

    def grade_one(task, *, turn):
        grade_sequencer.reserve_turn()
        reserved.append(task)
        grade_sequencer.claimed()
        grading.set()
        assert release.wait(5)
        return task, "GRADED"

    grader._grade_one = grade_one
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()

    def round_():
        with sequencer.task() as task:
            taken = []
            try:
                return grader._claim_and_grade(sequencer, task, set(), claims, taken)
            finally:
                for owner in taken:
                    claims.release(owner)

    results = {}
    first = threading.Thread(target=lambda: results.setdefault("1", round_()))
    first.start()
    assert grading.wait(5)
    results["2"] = round_()  # T1 in flight: T2 is a copy waiting for it
    release.set()
    first.join(5)
    assert reserved == [T1]
    assert results == {"1": (T1, "GRADED"), "2": None}
