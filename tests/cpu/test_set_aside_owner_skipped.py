"""Live 116, 18 Nov 2026 21:0xZ: owners set aside at a start (`OwnerProviders.restore`: their requests refused
``direct_provider_owner_set_aside``) ended every advance pass at their first task (no build at all) and, in the grade
scan, held every later task (no grade at all). Now each skips only its own task."""

from __future__ import annotations

from types import SimpleNamespace

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.challenge_validator.interface import Unavailable
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

ASIDE, LIVE = ("rtsk_" + c * 64 for c in "ab")


def test_an_advance_pass_skips_a_set_aside_owners_task_and_builds_the_next():
    adapter = LeanRecipeAdapter.__new__(LeanRecipeAdapter)
    adapter.contract_digest = "sha256:" + "c" * 64
    adapter.ledger = SimpleNamespace(submitted_outcomes=lambda contract: [ASIDE, LIVE])
    adapter.provider_for = SimpleNamespace(_providers={})

    def owner(task):
        if task == ASIDE:
            raise Unavailable("direct_provider_owner_set_aside")
        return "5Live"

    adapter.owner = owner
    built = []
    adapter._advance_one = lambda owner, task: built.append(task) or 1
    assert adapter.advance() == 1 and built == [LIVE]


def test_any_other_owner_refusal_still_raises():
    adapter = LeanRecipeAdapter.__new__(LeanRecipeAdapter)
    adapter.owner = lambda task: (_ for _ in ()).throw(
        Unavailable("direct_receiver_stopping")
    )
    try:
        adapter._active_owner(ASIDE)
    except Unavailable as raised:
        assert raised.code == "direct_receiver_stopping"
    else:
        raise AssertionError("expected the refusal")


def test_an_unreadable_owner_holds_only_its_own_task_in_the_grade_scan():
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=SimpleNamespace())
    grader.pending = lambda: [ASIDE, LIVE]
    grader._allowance_group = lambda task: None if task == ASIDE else "c:live"
    grader._owner_of = lambda task: None if task == ASIDE else "5Live"
    grader._withdrawn_pending = lambda task: False
    grader._copy_decision = lambda task: None
    graded = []
    grader._grade_one = lambda task, *, turn: graded.append(task) or (task, "GRADED")
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    with sequencer.task() as task:
        assert grader._claim_and_grade(sequencer, task, set(), claims, []) == (
            LIVE,
            "GRADED",
        )
    assert graded == [LIVE]
