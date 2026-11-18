"""One door, N grades at once, committed in claim order (`carbon.challenge_validator.grade_sequencer`; owner's order
16 Nov 2026 via the Lead). Threads and stand-in grade steps only: no containers, no ledger.
"""

from __future__ import annotations

import threading
import time

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.development_session import research_carrier

#: the real yield, kept before the autouse fixture replaces it
_REAL_YIELD = research_carrier.yield_grade_session


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
    assert (
        len(_no_session) == 1
    )  # only the grade that had to wait gave up its session container


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
    grader._prelude_due = lambda pending: False
    grader.pending = lambda: [sid for sid in pending if sid not in grader.marked]
    grader._settle_withdrawn = lambda sid: False
    grader._withdrawn_pending = lambda sid: False
    grader._allowance_group = lambda sid: "h:" + sid  # one hotkey per task
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
    grader._prelude_due = lambda pending: True
    grader.pending = list
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


def test_a_later_task_of_the_same_allowance_group_waits_for_the_earlier_one():
    """Two tasks of one hotkey: the second is not claimed while the first is in flight (its allowance is read after
    the first settles, as one at a time does); another hotkey's task is."""
    claimed, a_started, b_claimed, release = (
        [],
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )

    def steps(grader, sid, turn):
        claimed.append(sid)
        grade_sequencer.claimed()
        if sid == "a1":
            a_started.set()
            assert release.wait(5)
        else:
            b_claimed.set()
        turn()
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["a1", "a2", "b1"], steps)
    grader._allowance_group = lambda sid: "h:" + sid[0]
    rounds = [threading.Thread(target=grader._run_once) for _ in range(2)]
    rounds[0].start()
    assert a_started.wait(5)
    rounds[1].start()
    assert b_claimed.wait(5)
    assert claimed == ["a1", "b1"]  # a2 held back behind a1
    release.set()
    for thread in rounds:
        thread.join(5)
    assert grader._run_once() == ("a2", "GRADED")


def test_a_lone_task_of_an_unknown_group_is_still_graded():
    def steps(grader, sid, turn):
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["x"], steps)
    grader._allowance_group = lambda sid: None
    assert grader._run_once() == ("x", "GRADED")


def test_an_unknown_group_waiting_never_holds_the_tasks_behind_it():
    """Live 116 (17 Nov 2026): one pending task of an unknown allowance group, with any owner busy, held EVERY later
    task back. Now it waits alone; a later task of a known group is graded."""

    def steps(grader, sid, turn):
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["busy", "unknown", "later"], steps)
    grader._allowance_group = lambda sid: None if sid == "unknown" else "h:" + sid
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim("o:busy")  # that owner is in a build round
    grader.owner_claims = claims
    grader._owner_of = lambda sid: "o:" + sid
    assert grader._run_once() == ("later", "GRADED")


def test_a_withdrawal_is_settled_in_its_commit_turn():
    settled = []
    grader = _grader(["w"], lambda *a: None)
    grader._withdrawn_pending = lambda sid: True
    grader._settle_withdrawn = lambda sid: bool(settled.append(sid) or True)
    assert grader._run_once() == ("w", "WITHDRAWN_BY_MINER")
    assert settled == ["w"]


def test_a_failed_withdrawal_repair_falls_through_to_grading():
    def steps(grader, sid, turn):
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["w"], steps)
    grader._withdrawn_pending = lambda sid: True
    grader._settle_withdrawn = lambda sid: False
    assert grader._run_once() == ("w", "GRADED")


def test_a_failed_session_yield_marks_it_broken_and_keeps_going(monkeypatch):
    # never reload research_carrier: a fresh MinerProgramFailure class would break every later test that types it
    carrier = research_carrier
    session = carrier._GradeSession()
    session.live = True

    def close(cli=None):
        raise ValueError("grade session cleanup uncertain")

    session.close = close
    token = carrier._GRADE_SESSION.set(session)
    try:
        _REAL_YIELD()
    finally:
        carrier._GRADE_SESSION.reset(token)
    assert session.live is False and session.broken is True


def test_the_sequencer_is_a_grading_path():
    """It decides which king a crown is compared against: a change to it is an exam change (exam_identity)."""
    from carbon.challenge_validator import direct_receiver

    assert (
        "carbon/challenge_validator/grade_sequencer.py" in direct_receiver.GRADING_PATHS
    )


# -- A19: owners never in two rounds at once (advance + grade) ------------------------------------------------------------


def test_an_owner_is_held_by_one_round_at_a_time():
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim("5A") and not claims.try_claim("5A")
    assert claims.try_claim("5B")
    claims.release("5A")
    assert claims.try_claim("5A")
    assert claims.held() == {"5A", "5B"}


def test_the_incumbents_steps_take_every_owner_and_wait_for_the_held_ones():
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim("5A")
    entered, log = threading.Event(), []

    def king():
        with claims.exclusive():
            entered.set()
            log.append("king")

    thread = threading.Thread(target=king)
    thread.start()
    time.sleep(0.2)
    assert not entered.is_set()  # waits for 5A's round
    assert not claims.try_claim("5B")  # and no new owner is taken meanwhile
    claims.release("5A")
    thread.join(5)
    assert log == ["king"] and claims.try_claim("5B")


def test_a_parallel_grade_skips_a_task_whose_owner_another_round_holds():
    def steps(grader, sid, turn):
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["a", "b"], steps)
    grader._owner_of = lambda sid: "owner-" + sid
    grader.owner_claims = grade_sequencer.OwnerClaims()
    assert grader.owner_claims.try_claim(
        "owner-a"
    )  # an advance round builds owner a's next task now
    assert grader._run_once() == ("b", "GRADED")
    assert grader.owner_claims.held() == {
        "owner-a"
    }  # the grade round released its own owner
    grader.owner_claims.release("owner-a")
    assert grader._run_once() == ("a", "GRADED")


def test_a_copy_that_waits_gives_its_owner_back_for_the_rest_of_the_round():
    seen = []

    def steps(grader, sid, turn):
        seen.append(grader.owner_claims.held())
        grader.marked.add(sid)
        return sid, "GRADED"

    grader = _grader(["a", "b"], steps)
    grader._owner_of = lambda sid: "owner-" + sid
    grader.owner_claims = grade_sequencer.OwnerClaims()
    grader._copy_decision = lambda sid: ("wait", None) if sid == "a" else None
    grader._log_copy_waits = lambda: None
    assert grader._run_once() == ("b", "GRADED")
    assert seen == [{"owner-b"}]  # while b grades, a's owner is free for a build round
    assert grader.owner_claims.held() == set()


def test_a_hung_grade_is_ended_and_never_stalls_a_later_commit(monkeypatch):
    """Live 116 (17 Nov 2026): two grades parked 85 min and every later commit waited behind them. A grade in flight
    past `GRADE_HUNG_SECONDS` is ended as Carbon's (FAILED_INFRA via `_fail`); a later grade's turn no longer waits for
    it, and the hung thread, should it wake, raises `GradeAbandoned` at its turn instead of committing.
    """
    sequencer = grade_sequencer.Sequencer()
    hung_in, hung_go, raised = threading.Event(), threading.Event(), []

    def hung():
        with sequencer.task() as task:
            task.bind("rtsk_hung")
            task.release_claim()
            hung_in.set()
            assert hung_go.wait(5)
            try:
                task.turn()
            except grade_sequencer.GradeAbandoned:
                raised.append(True)

    thread = threading.Thread(target=hung, daemon=True)
    thread.start()
    assert hung_in.wait(5)
    failed = []
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader._fail = lambda sid, code: failed.append((sid, code))
    monkeypatch.setattr(auto_grade, "GRADE_HUNG_SECONDS", None)
    grader._end_hung_grades(sequencer)
    assert failed == []  # off while unset
    monkeypatch.setattr(auto_grade, "GRADE_HUNG_SECONDS", 0)
    grader._end_hung_grades(sequencer)
    assert failed == [("rtsk_hung", auto_grade.GRADE_HUNG)]
    assert sequencer.in_flight() == set()
    with sequencer.task() as later:
        later.bind("rtsk_later")
        later.turn()  # never waits for the hung ticket
    hung_go.set()
    thread.join(5)
    assert raised == [True]


def test_an_abandoned_grade_that_wakes_ends_its_round_quietly():
    """V2 (18 Nov 2026): the hung grade's thread, waking after `_end_hung_grades` gave its slot back, meets
    GradeAbandoned at its turn (inside `_grade_on_lane`'s own handlers too). Its round ends with None: no marker, no
    second `_fail`, no crash of the grader loop."""
    failed = []

    def steps(grader, sid, turn):
        raise grade_sequencer.GradeAbandoned(0)

    grader = _grader(["hung"], steps)
    grader._fail = lambda sid, code: failed.append((sid, code))
    assert grader._run_once() is None
    assert grader.marked == set() and failed == []
