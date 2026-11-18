"""V2 (18 Nov 2026): a busy owner holds back only its OWN tasks, never its allowance group's other owners; an in-flight
grade whose group cannot be read holds nothing. A cap refusal of a task that went ahead of a passed-over earlier
group-mate (or while an unknown-group grade is in flight) is "not yet": no final GRADED marker, it stays pending.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from carbon.challenge_validator import auto_grade, grade_sequencer

EARLY, LATE, OTHER = ("rtsk_" + c * 64 for c in "abc")
OWNERS = {EARLY: "5Busy", LATE: "5Mate", OTHER: "5Else"}
GROUPS = {EARLY: "c:same", LATE: "c:same", OTHER: "c:else"}


def _grader(pending, refuse=()):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=SimpleNamespace())
    grader.pending = lambda: list(pending)
    grader._allowance_group = GROUPS.get
    grader._owner_of = OWNERS.get
    grader._withdrawn_pending = lambda task: False
    grader._copy_decision = lambda task: None
    graded, soft, markers = [], {}, []
    grader._write = lambda task, state, **kw: markers.append((task, state))

    def grade_one(task, *, turn):
        # the real path: a cap refusal of a soft claim is "not yet" (`_grade_on_lane`), else a GRADED marker
        if task in refuse:
            soft[task] = grader._cap_soft(task)
            if soft[task]:
                return auto_grade._NEXT
            grader._write(task, "GRADED")
            return task, "GRADED"
        graded.append(task)
        return task, "GRADED"

    grader._grade_one = grade_one
    return grader, graded, soft, markers


def _round(grader, sequencer, claims, skipped=None):
    skipped = set() if skipped is None else skipped
    while True:
        with sequencer.task() as task:
            taken = []
            try:
                return grader._claim_and_grade(sequencer, task, skipped, claims, taken)
            except auto_grade._NextTask:
                continue
            finally:
                for owner in taken:
                    claims.release(owner)


def test_a_busy_owner_holds_only_its_own_tasks_and_the_passed_one_grades_next_round():
    grader, graded, _soft, markers = _grader([EARLY, LATE])
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    assert claims.try_claim(OWNERS[EARLY])  # EARLY's miner builds its next task
    # its group-mate goes ahead (it used to wait behind EARLY)
    assert _round(grader, sequencer, claims) == (LATE, "GRADED")
    claims.release(OWNERS[EARLY])
    grader.pending = lambda: [EARLY]
    assert _round(grader, sequencer, claims) == (EARLY, "GRADED")
    assert graded == [LATE, EARLY] and markers == []


def test_a_cap_refusal_after_passing_an_earlier_group_mate_is_not_yet_never_final():
    grader, _graded, soft, markers = _grader([EARLY, LATE], refuse={LATE})
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    assert claims.try_claim(OWNERS[EARLY])
    assert (
        _round(grader, sequencer, claims) is None
    )  # LATE refused "not yet"; nothing else to grade
    assert soft == {LATE: True}
    assert markers == []  # no final GRADED cap-refusal marker
    # the passed-over earlier task gets the slot next round and grades
    claims.release(OWNERS[EARLY])
    grader.pending = lambda: [EARLY, LATE]
    assert _round(grader, sequencer, claims) == (EARLY, "GRADED")


def test_an_unknown_group_in_flight_holds_nothing_and_makes_a_refusal_not_yet():
    grader, _graded, soft, markers = _grader([OTHER], refuse={OTHER})
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    started, finish = threading.Event(), threading.Event()

    def in_flight():
        with sequencer.task() as task:
            task.bind("rtsk_" + "u" * 64, None)  # its group could not be read
            task.release_claim()
            started.set()
            finish.wait(5)

    thread = threading.Thread(target=in_flight, daemon=True)
    thread.start()
    assert started.wait(5)
    assert (
        _round(grader, sequencer, claims) is None
    )  # claimed (not held), refused "not yet"
    assert soft == {OTHER: True} and markers == []
    # once it RELEASES (no unknown group in flight) the same refusal is final, as before
    finish.set()
    thread.join(5)
    soft.clear()
    assert _round(grader, sequencer, claims) == (OTHER, "GRADED")
    assert soft == {OTHER: False} and markers == [(OTHER, "GRADED")]


def test_with_nothing_passed_and_nothing_unknown_a_cap_refusal_stays_final():
    grader, _graded, soft, markers = _grader([LATE], refuse={LATE})
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    assert _round(grader, sequencer, claims) == (LATE, "GRADED")
    assert soft == {LATE: False} and markers == [(LATE, "GRADED")]
