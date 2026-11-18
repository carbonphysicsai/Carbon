"""Live 116 stacks (18 Nov 2026, 14:27Z): one grade thread held the sequencer's claim while its candidate scan ran
the owner check (`LeanRecipeAdapter.owner` → `_provider` → a full served-source hash) for every pending submission, built
or not; every other grade and the incumbent's steps waited on that claim. Now the scan skips the submissions the open
providers hold as still building, and the owner check re-hashes the served sources at most once per
`IDENTITY_RECHECK_SECONDS` (V2's option (a): a byte edit is still refused within that interval)."""

from __future__ import annotations

import time
from types import SimpleNamespace

from carbon.challenge_validator import auto_grade, grade_sequencer, lean_recipe
from carbon.research import DirectTaskStateV3

BUILT, QUEUED, RUNNING, UNKNOWN = ("rtsk_" + c * 64 for c in "abcd")


def _grader(views):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    provider = SimpleNamespace(
        _views={task: SimpleNamespace(state=state) for task, state in views.items()}
    )
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(provider_for=SimpleNamespace(_providers={"5O": provider}))
    )
    grader.pending = lambda: [QUEUED, RUNNING, BUILT, UNKNOWN]
    grader._allowance_group = lambda task: "g-" + task
    asked = []

    def owner_of(task):
        asked.append(task)
        return "5Owner-" + task

    grader._owner_of = owner_of
    grader._withdrawn_pending = lambda task: False
    grader._copy_decision = lambda task: None
    graded = []

    def grade_one(task, *, turn):
        graded.append(task)
        return task, "GRADED"

    grader._grade_one = grade_one
    return grader, asked, graded


def test_the_claim_scan_skips_submissions_still_building_before_the_owner_check():
    grader, asked, graded = _grader(
        {
            QUEUED: DirectTaskStateV3.QUEUED,
            RUNNING: DirectTaskStateV3.RUNNING,
            BUILT: DirectTaskStateV3.SUCCEEDED,
        }
    )
    sequencer = grade_sequencer.Sequencer()
    claims = grade_sequencer.OwnerClaims()
    with sequencer.task() as task:
        outcome = grader._claim_and_grade(sequencer, task, set(), claims, [])
    assert outcome == (BUILT, "GRADED")
    # the queued and running ones never reached the owner check
    assert asked == [BUILT]
    assert graded == [BUILT]


def test_without_open_providers_every_pending_submission_is_scanned_as_before():
    grader, asked, _graded = _grader({})
    grader.intake = SimpleNamespace(adapter=SimpleNamespace())  # no provider view at all
    sequencer = grade_sequencer.Sequencer()
    with sequencer.task() as task:
        grader._claim_and_grade(
            sequencer, task, set(), grade_sequencer.OwnerClaims(), []
        )
    assert asked == [QUEUED]  # the first candidate is taken, as before


def test_the_owner_check_re_hashes_the_served_sources_once_per_interval(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(lean_recipe, "_RECENT_IDENTITY", [None, 0.0])
    hashed = []
    identity = ["sha256:one"]

    def full():
        hashed.append(now[0])
        return identity[0]

    monkeypatch.setattr(lean_recipe, "_implementation_identity", full)
    assert lean_recipe._implementation_identity_recent() == "sha256:one"
    assert lean_recipe._implementation_identity_recent() == "sha256:one"
    assert hashed == [1000.0]  # once inside the interval
    # a served source edited: seen within one interval
    identity[0] = "sha256:edited"
    now[0] += lean_recipe.IDENTITY_RECHECK_SECONDS
    assert lean_recipe._implementation_identity_recent() == "sha256:edited"
    assert len(hashed) == 2
