"""Live 116 stacks (18 Nov 2026, 14:27Z): one grade thread held the sequencer's claim while its candidate scan ran
the owner check (`LeanRecipeAdapter.owner` → `_provider` → a full served-source hash) for every pending submission, built
or not; every other grade and the incumbent's steps waited on that claim. Now the scan skips the submissions the open
providers hold as still building, and the served sources are hashed only where work starts (V2's ruling): a build
or a grade start, never a lookup.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer, lean_recipe
from carbon.research import DirectTaskStateV3

BUILT, QUEUED, RUNNING, UNKNOWN = ("rtsk_" + c * 64 for c in "abcd")


def _grader(views):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    provider = SimpleNamespace(
        _views={task: SimpleNamespace(state=state) for task, state in views.items()}
    )
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            provider_for=SimpleNamespace(_providers={"5O": provider})
        )
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
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace()
    )  # no provider view at all
    sequencer = grade_sequencer.Sequencer()
    with sequencer.task() as task:
        grader._claim_and_grade(
            sequencer, task, set(), grade_sequencer.OwnerClaims(), []
        )
    assert asked == [QUEUED]  # the first candidate is taken, as before


def _counted_identity(monkeypatch, value="sha256:started"):
    calls = []

    def identity():
        calls.append(1)
        return value

    monkeypatch.setattr(lean_recipe, "_implementation_identity", identity)
    return calls


def _adapter():
    adapter = lean_recipe.LeanRecipeAdapter.__new__(lean_recipe.LeanRecipeAdapter)
    adapter._identities = {"implementation_digest": "sha256:started"}
    return adapter


def test_a_lookup_never_hashes_the_served_sources(monkeypatch):
    """V2's ruling: `_provider` (behind every `owner()`, claim scan, advance scan and status read) runs no hash."""
    calls = _counted_identity(monkeypatch)
    adapter = _adapter()
    adapter.provider_for = (
        lambda hotkey: object()
    )  # not a provider: refused after the lookup
    for _ in range(25):
        # the double is refused; only the hash count matters
        with pytest.raises(Exception):  # noqa: B017
            adapter._provider("5Owner")
    assert calls == []


def test_a_byte_edit_after_start_is_refused_at_the_next_build_start(monkeypatch):
    _counted_identity(monkeypatch, "sha256:edited")
    adapter = _adapter()
    adapter.discovery = SimpleNamespace(info=SimpleNamespace(challenge_key="key"))
    ran = []
    provider = SimpleNamespace(
        get_research_result=lambda request: SimpleNamespace(
            task=SimpleNamespace(state=DirectTaskStateV3.QUEUED)
        ),
        run_queued_task=lambda task_id: ran.append(task_id),
    )
    adapter._provider = lambda owner: provider
    from carbon import research

    # the read request is the provider double's; only the check before the run matters here
    monkeypatch.setattr(research, "DirectGetTaskRequestV3", lambda *args: None)
    from carbon.challenge_validator.interface import Unavailable

    with pytest.raises(Unavailable, match="served_recipe_source_changed"):
        adapter._advance_one("5Owner", BUILT)
    assert ran == []  # refused before the build runs


@pytest.mark.parametrize(
    "entry",
    [
        "retain_served_result",
        "retain_served_bundle_result",
        "regrade_retained_entry",
        "remeasure_incumbent_pack",
        "reconsider_paused_pack",
        "rebuild_king",
        "repeat_grade",
        "rebuild_at_seed",
    ],
)
def test_a_byte_edit_after_start_is_refused_at_the_next_grade_start(monkeypatch, entry):
    """Every grade entry checks the served sources first, before any of its work."""
    import inspect

    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.challenge_validator.interface import Unavailable

    _counted_identity(monkeypatch, "sha256:edited")
    adapter = _adapter()
    function = getattr(retention, entry)
    params = inspect.signature(function).parameters.values()
    args = [
        adapter if p.name == "adapter" else None
        for p in params
        if p.kind is p.POSITIONAL_OR_KEYWORD and p.default is p.empty
    ]
    kwargs = {
        p.name: None
        for p in params
        if p.kind is p.KEYWORD_ONLY and p.default is p.empty
    }
    with pytest.raises(Unavailable, match="served_recipe_source_changed"):
        function(*args, **kwargs)
