"""V2 (18 Nov 2026): while an owner the crown steps need is set aside at the start (`OwnerProviders.restore`), the
incumbent's crown steps (the stranded filing, the king's upkeep, the paused-crown sweep) hold: a crown is never decided
on an incomplete set. Grading goes on."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from carbon.challenge_validator import auto_grade

KING_OWNER = "5" + "3" * 47
OTHER = "5" + "4" * 47


def _sha(hotkey):
    return hashlib.sha256(hotkey.encode()).hexdigest()


def _grader(set_aside, owners):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            provider_for=SimpleNamespace(set_aside=lambda: dict(set_aside))
        )
    )
    grader._prelude_owners = lambda: owners
    calls = []
    grader._upkeep_deferred = lambda: False
    grader._king_upkeep = lambda: calls.append("upkeep")
    grader._file_stranded = lambda: calls.append("stranded")
    grader._resume_paused_crowns = lambda: calls.append("sweep")
    return grader, calls


def test_the_crown_steps_hold_while_an_owner_they_need_is_set_aside():
    grader, calls = _grader({_sha(KING_OWNER): "ValueError"}, {KING_OWNER, OTHER})
    grader._crown_steps()
    assert calls == []


def test_the_crown_steps_run_when_the_set_aside_owner_is_not_one_they_need():
    grader, calls = _grader({_sha("5" + "9" * 47): "ValueError"}, {KING_OWNER})
    grader._crown_steps()
    assert calls == ["upkeep", "sweep"]


def test_owners_that_cannot_be_read_hold_the_steps_while_any_owner_is_set_aside():
    grader, calls = _grader({_sha("5" + "9" * 47): "ValueError"}, None)
    grader._crown_steps()
    assert calls == []


def test_nothing_set_aside_runs_the_steps_as_before():
    grader, calls = _grader({}, None)
    grader._crown_steps()
    assert calls == ["upkeep", "sweep"]
    bare, calls = _grader({}, None)
    bare.intake = SimpleNamespace(adapter=SimpleNamespace())  # no set-aside view at all
    bare._crown_steps()
    assert calls == ["upkeep", "sweep"]
