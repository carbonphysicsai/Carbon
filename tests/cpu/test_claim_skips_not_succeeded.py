"""Live 116, 19 Nov 2026 08:23Z (``grade_claim_scan``: 123 tasks retried as ``task_not_succeeded``, 24-34 min per pass):
the claim scan skips every task whose build has not SUCCEEDED, from the open views and the lazy owners' index, before
the owner check: a terminal REFUSED / FAILED / CANCELLED task never gets a marker and stayed pending forever.
"""

from __future__ import annotations

from types import SimpleNamespace

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.research import DirectTaskStateV3

REFUSED, FAILED, CANCELLED, LAZY_DEAD, LAZY_BUILT, BUILT = (
    "rtsk_" + c * 64 for c in "abcdef"
)


def _grader(views, lazy):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    provider = SimpleNamespace(
        _views={task: SimpleNamespace(state=state) for task, state in views.items()}
    )
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            provider_for=SimpleNamespace(
                _providers={"5Open": provider}, lazy_index=lambda: dict(lazy)
            )
        )
    )
    grader._allowance_group = lambda task: "g-" + task
    asked = []

    def owner_of(task):
        asked.append(task)
        return "5Owner-" + task

    grader._owner_of = owner_of
    grader._withdrawn_pending = lambda task: False
    grader._copy_decision = lambda task: None
    grader._grade_one = lambda task, *, turn: (task, "GRADED")
    return grader, asked


def test_terminal_and_lazy_unbuilt_tasks_never_reach_the_owner_check():
    views = {
        REFUSED: DirectTaskStateV3.REFUSED,
        FAILED: DirectTaskStateV3.FAILED_INFRA,
        CANCELLED: DirectTaskStateV3.CANCELLED,
        BUILT: DirectTaskStateV3.SUCCEEDED,
    }
    lazy = {LAZY_DEAD: ("REFUSED", 1.0), LAZY_BUILT: ("SUCCEEDED", 2.0)}
    grader, asked = _grader(views, lazy)
    order = [REFUSED, FAILED, CANCELLED, LAZY_DEAD, LAZY_BUILT, BUILT]
    grader.pending = lambda: list(order)
    assert grader._building_views() == {REFUSED, FAILED, CANCELLED, LAZY_DEAD}
    sequencer, claims = grade_sequencer.Sequencer(), grade_sequencer.OwnerClaims()
    with sequencer.task() as task:
        outcome = grader._claim_and_grade(sequencer, task, set(), claims, [])
    # the first gradable task is claimed at once; no dead task was asked about
    assert outcome == (LAZY_BUILT, "GRADED") and asked == [LAZY_BUILT]


def test_an_unreadable_lazy_index_scans_those_tasks_as_before():
    grader, _asked = _grader({}, {})

    def broken():
        raise RuntimeError("changed while read")

    grader.intake.adapter.provider_for.lazy_index = broken
    assert grader._building_views() == frozenset()
