"""Live 116, 19 Nov 2026 ~09:58Z: 190 grade-loop failures in a row (``direct_grade_failure`` type Unavailable), nothing
graded. An owner the door cannot open now (set aside at this start, or its registration unreadable) holds back only its
own task; the round, the claim scan and the incumbent's steps go on. Any other Unavailable is raised as before.
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
        return None

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


def test_an_unopenable_owner_in_the_claim_scan_skips_only_its_task():
    claims = grade_sequencer.OwnerClaims()
    grader = _scan_grader(Unavailable(SET_ASIDE))
    assert _claim(grader, claims) == (B, "GRADED")
    assert claims.held() == set()  # the skipped owner's claim was given back


def test_any_other_unavailable_in_the_claim_scan_is_raised_as_before():
    grader = _scan_grader(Unavailable("something_else"))
    with pytest.raises(Unavailable):
        _claim(grader, grade_sequencer.OwnerClaims())


def _lane_grader(raises):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)

    def retain_result(*args, **kwargs):
        raise raises

    grader.intake = SimpleNamespace(retain_result=retain_result)
    grader.containers = lambda: 0
    grader.sample_seconds = 3600
    grader.artifacts = grader.entries = None
    grader._pool = lambda: None
    grader._scan_local().codes = {}
    return grader


def test_an_unopenable_owner_at_the_retain_step_is_not_yet():
    grader = _lane_grader(Unavailable(SET_ASIDE))
    assert grader._grade_on_lane(A, turn=lambda: None) is auto_grade._NEXT
    assert A in grader.stalled
    assert grader._scan_local().codes == {SET_ASIDE: 1}


def test_any_other_unavailable_at_the_retain_step_is_raised_as_before():
    grader = _lane_grader(Unavailable("something_else"))
    with pytest.raises(Unavailable):
        grader._grade_on_lane(A, turn=lambda: None)


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
