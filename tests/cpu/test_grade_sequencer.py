"""One door, N grades at once, committed in claim order (`carbon.challenge_validator.grade_sequencer`; owner's order
16 Nov 2026 via the Lead). Threads and stand-in grade steps only: no containers, no ledger.
"""

from __future__ import annotations

import threading
import time

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.development_session import research_carrier


@pytest.fixture(autouse=True)
def _no_session(monkeypatch):
    yielded = []
    monkeypatch.setattr(
        research_carrier, "yield_grade_session", lambda: yielded.append(1)
    )
    return yielded


def test_outside_a_sequenced_grade_every_hook_is_a_no_op():
    assert grade_sequencer.current() is None
    grade_sequencer.claimed()
    grade_sequencer.turn()


def test_a_later_claim_commits_only_after_every_earlier_one(_no_session):
    sequencer = grade_sequencer.Sequencer()
    log, first_claimed, second_done_compute = [], threading.Event(), threading.Event()

    def first():
        with sequencer.task() as task:
            task.bind("a")
            grade_sequencer.claimed()
            first_claimed.set()
            assert second_done_compute.wait(5)  # a slow grade
            time.sleep(0.2)
            grade_sequencer.turn()
            log.append("commit a")

    def second():
        assert first_claimed.wait(5)
        with sequencer.task() as task:
            task.bind("b")
            grade_sequencer.claimed()
            second_done_compute.set()  # a fast grade, done first
            grade_sequencer.turn()
            log.append("commit b")

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert log == ["commit a", "commit b"]
    assert len(_no_session) == 2  # each gave up its session container before waiting


def test_the_next_claim_waits_for_the_reservation():
    sequencer = grade_sequencer.Sequencer()
    order, reserved = [], threading.Event()

    def first():
        with sequencer.task():
            time.sleep(0.2)
            order.append("reserve a")
            grade_sequencer.claimed()
            reserved.set()
            time.sleep(0.2)

    def second():
        time.sleep(0.05)
        with sequencer.task():
            order.append("claim b")

    threads = [threading.Thread(target=f) for f in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert order == ["reserve a", "claim b"]


def test_in_flight_names_the_claimed_tasks_until_they_finish():
    sequencer = grade_sequencer.Sequencer()
    with sequencer.task() as task:
        task.bind("a")
        grade_sequencer.claimed()
        assert sequencer.in_flight() == {"a"}
    assert sequencer.in_flight() == set()


def test_the_incumbents_steps_wait_for_every_grade_in_flight():
    sequencer = grade_sequencer.Sequencer()
    log, inside = [], threading.Event()

    def grade():
        with sequencer.task():
            grade_sequencer.claimed()
            inside.set()
            time.sleep(0.3)
            log.append("grade done")

    thread = threading.Thread(target=grade)
    thread.start()
    assert inside.wait(5)
    with sequencer.exclusive():
        log.append("king upkeep")
    thread.join(10)
    assert log == ["grade done", "king upkeep"]


def test_a_failed_grade_frees_its_ticket():
    sequencer = grade_sequencer.Sequencer()
    with pytest.raises(RuntimeError), sequencer.task():
        raise RuntimeError("compute failed")
    with sequencer.task():
        grade_sequencer.turn()  # nothing earlier is open: no wait
    assert sequencer.in_flight() == set()


# -- the AutoGrader's parallel round -------------------------------------------------------------------------------------


def _grader(pending, steps):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.sequencer = grade_sequencer.Sequencer()
    grader.marked = set()
    grader.chain_degraded = lambda: False
    grader._prelude_due = lambda: False
    grader.pending = lambda: [sid for sid in pending if sid not in grader.marked]
    grader._settle_withdrawn = lambda sid: False
    grader._copy_decision = lambda sid: None

    def grade_one(sid, turn=lambda: None):
        return steps(grader, sid, turn)

    grader._grade_one = grade_one
    return grader


def test_two_rounds_grade_different_tasks_and_commit_in_submission_order():
    log, a_started = [], threading.Event()

    def steps(grader, sid, turn):
        grade_sequencer.claimed()  # the exam-cap reservation
        if sid == "a":
            a_started.set()
            time.sleep(0.3)  # a slow graded pass
        log.append(f"computed {sid}")
        turn()
        log.append(f"commit {sid}")
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["a", "b"], steps)
    results = []

    def round_():
        results.append(grader._run_once())

    first = threading.Thread(target=round_)
    first.start()
    assert a_started.wait(5)
    second = threading.Thread(target=round_)
    second.start()
    first.join(10)
    second.join(10)
    assert sorted(results) == [("a", "GRADED"), ("b", "GRADED")]
    assert log.index("computed b") < log.index(
        "computed a"
    )  # b's compute ran beside a's
    assert log.index("commit a") < log.index("commit b")  # but a committed first


def test_a_task_not_gradable_now_lets_the_round_try_the_next(monkeypatch):
    def steps(grader, sid, turn):
        if sid == "a":
            return auto_grade._NEXT
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["a", "b"], steps)
    assert grader._run_once() == ("b", "GRADED")


def test_the_incumbents_steps_run_only_when_due_and_alone(monkeypatch):
    ran = []
    grader = _grader([], lambda *a: None)
    grader._prelude_due = lambda: True
    grader._settle_queue_places = lambda: ran.append("places")
    grader._upkeep_deferred = lambda: False
    grader._king_upkeep = lambda: ran.append("king")
    grader._resume_paused_crowns = lambda: ran.append("crowns")
    grader._apply_due_retries = lambda idle: ran.append("retries")
    assert grader._run_once() is None
    assert ran == ["places", "king", "crowns", "retries"]


def test_a_grader_without_a_sequencer_keeps_the_serial_round():
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    assert getattr(grader, "sequencer", None) is None
