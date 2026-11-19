"""Live 116, 19 Nov 2026 ~09:48Z: grade-loop failures every round (``direct_grade_failure`` type Unavailable), nothing
graded. An owner the door cannot open now (set aside at this start, its registration changed, its provider bound
elsewhere) never ends the round from the claim scan's copy check or the incumbent's steps; its task goes to its grade,
which gives it back as Carbon's as before. Any other Unavailable is raised as before.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.challenge_validator.interface import Unavailable

A, B = ("rtsk_" + c * 64 for c in "ab")
SET_ASIDE = "direct_provider_owner_set_aside"


def _scan_grader(copy_raises):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=SimpleNamespace())
    grader.pending = lambda: [A, B]
    grader._allowance_group = lambda task: "g-" + task
    grader._owner_of = lambda task: "5Owner-" + task
    grader._withdrawn_pending = lambda task: False

    def copy_decision(task):
        if task == A:
            raise copy_raises

    grader._copy_decision = copy_decision
    grader._grade_one = lambda task, *, turn: (task, "GRADED")
    return grader


def _claim(grader, claims):
    sequencer = grade_sequencer.Sequencer()
    with sequencer.task() as task:
        taken = []
        try:
            return grader._claim_and_grade(sequencer, task, set(), claims, taken)
        finally:
            for owner in taken:
                claims.release(owner)


def test_an_unopenable_owner_in_the_copy_check_goes_on_to_its_grade():
    """No copy can be decided; its grade's owner open gives it back as Carbon's (`_grade_on_lane`), as before."""
    claims = grade_sequencer.OwnerClaims()
    grader = _scan_grader(Unavailable(SET_ASIDE))
    # the stand-in grade: the round never ended
    assert _claim(grader, claims) == (A, "GRADED")


def test_any_other_unavailable_in_the_claim_scan_is_raised_as_before():
    grader = _scan_grader(Unavailable("something_else"))
    with pytest.raises(Unavailable):
        _claim(grader, grade_sequencer.OwnerClaims())


def test_the_incumbents_steps_wait_for_an_unopenable_owner_and_the_round_goes_on(
    monkeypatch,
):
    lines = []
    monkeypatch.setattr(
        "carbon.battery.intake.log", lambda event, **f: lines.append((event, f))
    )
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader._settle_queue_places = lambda: None

    def crown_steps():
        raise Unavailable(SET_ASIDE)

    grader._crown_steps = crown_steps
    grader._run_prelude()  # never raises
    assert ("prelude_owner_unavailable", {"code": SET_ASIDE}) in lines

    def other_steps():
        raise Unavailable("other")

    grader._crown_steps = other_steps
    with pytest.raises(Unavailable):
        grader._run_prelude()
