"""Design A (Lead, 19 Nov 2026; live 116 lost 20-30 min of grading after every start): the grade claim lock covers only
the PICK; the retain step and the owner's open (a lazy owner's restore) run outside it, and `reserve_turn` keeps the
exam-cap reservations in claim order. Threads and stand-in grade steps only: no containers, no ledger.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from carbon.challenge_validator import auto_grade, grade_sequencer

A, B = ("rtsk_" + c * 64 for c in "ab")


def test_a_slow_retain_never_blocks_the_next_claim_and_reserves_keep_order():
    sequencer = grade_sequencer.Sequencer()
    order, retaining, b_claimed = [], threading.Event(), threading.Event()
    lazy_open_done = threading.Event()

    def first():
        with sequencer.task() as task:
            task.bind("a")
            task.release_claim()  # the pick is made
            retaining.set()
            assert lazy_open_done.wait(5)  # a lazy owner's open, outside the lock
            grade_sequencer.reserve_turn()
            order.append("reserve a")
            grade_sequencer.claimed()

    def second():
        assert retaining.wait(5)
        with sequencer.task() as task:  # claims WHILE the first still retains
            b_claimed.set()
            task.bind("b")
            task.release_claim()
            grade_sequencer.reserve_turn()  # waits for the earlier reservation
            order.append("reserve b")
            grade_sequencer.claimed()

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    assert b_claimed.wait(2)  # within seconds, while the first retains
    assert order == []  # but the later reservation waits
    lazy_open_done.set()
    for thread in threads:
        thread.join(10)
    assert order == ["reserve a", "reserve b"]


def test_an_earlier_grade_that_ends_without_reserving_frees_the_turn():
    sequencer = grade_sequencer.Sequencer()
    order, a_bound, a_end = [], threading.Event(), threading.Event()

    def first():
        with sequencer.task() as task:
            task.bind("a")
            task.release_claim()
            a_bound.set()
            assert a_end.wait(5)  # "not yet": ends, no reservation

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
    time.sleep(0.2)
    assert order == []
    a_end.set()
    for thread in threads:
        thread.join(10)
    assert order == ["reserve b"]


def test_an_abandoned_earlier_grade_frees_the_turn_and_a_waiter_is_not_hung():
    sequencer = grade_sequencer.Sequencer()
    order, a_bound, release = [], threading.Event(), threading.Event()
    tickets = {}

    def first():
        with sequencer.task() as task:
            tickets["a"] = task.ticket
            task.bind("a")
            task.release_claim()
            a_bound.set()
            assert release.wait(5)  # hung

    def second():
        assert a_bound.wait(5)
        with sequencer.task() as task:
            tickets["b"] = task.ticket
            task.bind("b")
            task.release_claim()
            grade_sequencer.reserve_turn()
            order.append("reserve b")
            grade_sequencer.claimed()

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    time.sleep(0.2)
    # the waiting reservation is a wait on an EARLIER grade: never ended as hung
    overdue = {ticket for ticket, _sid in sequencer.overdue(0.0)}
    assert tickets["b"] not in overdue and tickets["a"] in overdue
    sequencer.abandon(tickets["a"])
    threads[1].join(5)
    assert order == ["reserve b"]
    release.set()
    threads[0].join(5)


def test_the_claim_scan_lets_the_claim_lock_go_before_the_retain_step():
    """The lazy owner's open runs inside `_grade_one` (retain_result -> adapter.owner): another round claims at once."""
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=SimpleNamespace())
    grader.pending = lambda: [A]
    grader._allowance_group = lambda task: "c:one"
    grader._owner_of = lambda task: "5Owner"
    grader._withdrawn_pending = lambda task: False
    grader._copy_decision = lambda task: None
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    free = []

    def grade_one(task, *, turn):
        # inside the retain step: the claim lock is free for other rounds
        free.append(sequencer._claim.acquire(blocking=False))
        if free[-1]:
            sequencer._claim.release()
        return task, "GRADED"

    grader._grade_one = grade_one
    with sequencer.task() as task:
        taken = []
        try:
            outcome = grader._claim_and_grade(sequencer, task, set(), claims, taken)
        finally:
            for owner in taken:
                claims.release(owner)
    assert outcome == (A, "GRADED") and free == [True]


def test_outside_a_sequenced_grade_the_reservation_turn_is_a_no_op():
    assert grade_sequencer.current() is None
    grade_sequencer.reserve_turn()
    grade_sequencer.claimed()


def test_pending_is_one_marker_listing(tmp_path):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.markers = tmp_path / "markers"
    grader.markers.mkdir()
    (grader.markers / (A + ".json")).write_text("{}")
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            contract_digest="c",
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: [A, B, "x"]),
        )
    )
    assert grader.pending() == [B]
    grader.markers = tmp_path / "absent"
    assert grader.pending() == [A, B]
