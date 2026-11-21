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


def test_ended_builds_are_kept_once_and_never_pending_again(tmp_path):
    """EFFICIENCY_LEDGER row 6 (smallest slice; live 116 20 Nov: 606 ended, unmarked tasks re-read by every scan, idle
    `has_work` and the host's waiting list): a build seen ENDED without success (REFUSED / FAILED_INFRA / UNRESOLVED /
    CANCELLED) by the scan's own views is kept once in ``auto-grade/ended``; `pending` skips it from then on, across a
    restart. A built task, a still-running one and a withdrawal awaiting its marker are never kept.
    """
    running, withdrawn = "rtsk_" + "1" * 64, "rtsk_" + "2" * 64
    views = {
        REFUSED: DirectTaskStateV3.REFUSED,
        FAILED: DirectTaskStateV3.FAILED_INFRA,
        CANCELLED: DirectTaskStateV3.CANCELLED,
        BUILT: DirectTaskStateV3.SUCCEEDED,
        running: DirectTaskStateV3.RUNNING,
        withdrawn: DirectTaskStateV3.CANCELLED,
    }
    lazy = {LAZY_DEAD: ("UNRESOLVED", 1.0), LAZY_BUILT: ("SUCCEEDED", 2.0)}
    grader, _asked = _grader(views, lazy)
    grader._withdrawn_pending = lambda task: task == withdrawn
    grader.ended = tmp_path / "auto-grade" / "ended"
    grader.markers = tmp_path / "auto-grade" / "markers"
    order = [
        REFUSED,
        FAILED,
        CANCELLED,
        LAZY_DEAD,
        LAZY_BUILT,
        BUILT,
        running,
        withdrawn,
    ]
    grader.intake.adapter.contract_digest = "sha256:c"
    grader.intake.adapter.ledger = SimpleNamespace(
        submitted_outcomes=lambda contract: list(order)
    )
    assert grader.pending() == order  # nothing kept yet
    grader._building_views()
    assert auto_grade.ended_tasks(grader.ended) == {
        REFUSED,
        FAILED,
        CANCELLED,
        LAZY_DEAD,
    }
    assert grader.pending() == [LAZY_BUILT, BUILT, running, withdrawn]
    # a fresh grader (a restart) reads the kept set: no scan needed first
    fresh, _ = _grader({}, {})
    fresh.ended, fresh.markers = grader.ended, grader.markers
    fresh.intake.adapter.contract_digest = "sha256:c"
    fresh.intake.adapter.ledger = grader.intake.adapter.ledger
    assert fresh.pending() == [LAZY_BUILT, BUILT, running, withdrawn]
    # idempotent, and nothing is ever removed from the views' own answer
    assert grader._building_views() == {
        REFUSED,
        FAILED,
        CANCELLED,
        LAZY_DEAD,
        running,
        withdrawn,
    }
    assert auto_grade.note_ended(grader.ended, REFUSED) is True
    assert auto_grade.note_ended(grader.ended, "not-a-task") is False


def test_a_grader_without_an_ended_directory_behaves_as_before():
    grader, _asked = _grader({REFUSED: DirectTaskStateV3.REFUSED}, {})
    assert grader._building_views() == {
        REFUSED
    }  # no `ended` attribute: nothing kept, no error


def test_a_kept_task_seen_alive_again_is_taken_out(tmp_path):
    """V2 23:2xZ condition: no path may leave a task skipped for ever under the SAME id. Every build re-run is a new
    generation id (`_request` INFRA_RERUN; the ledger refuses ``same_task``, test_build_requeue); as a backstop, a kept
    task the views show SUCCEEDED or not ended again is removed from ``ended`` and is pending again.
    """
    grader, _asked = _grader({FAILED: DirectTaskStateV3.FAILED_INFRA}, {})
    grader.ended = tmp_path / "auto-grade" / "ended"
    grader.markers = tmp_path / "auto-grade" / "markers"
    grader.intake.adapter.contract_digest = "sha256:c"
    grader.intake.adapter.ledger = SimpleNamespace(
        submitted_outcomes=lambda contract: [FAILED, LAZY_DEAD]
    )
    grader._building_views()
    assert grader.pending() == [LAZY_DEAD]
    # the same id now shows built (the views of an open provider), then not ended (lazy index)
    provider = grader.intake.adapter.provider_for._providers["5Open"]
    provider._views[FAILED] = SimpleNamespace(state=DirectTaskStateV3.SUCCEEDED)
    grader._building_views()
    assert auto_grade.ended_tasks(grader.ended) == set()
    assert grader.pending() == [FAILED, LAZY_DEAD]
    # kept again when it ends again; a lazy owner's QUEUED entry also brings it back
    provider._views[FAILED] = SimpleNamespace(state=DirectTaskStateV3.FAILED_INFRA)
    grader._building_views()
    assert grader.pending() == [LAZY_DEAD]
    del provider._views[FAILED]
    grader.intake.adapter.provider_for.lazy_index = lambda: {FAILED: ("QUEUED", 1.0)}
    grader._building_views()
    assert FAILED in grader.pending()


def test_every_build_rerun_is_a_new_task_id():
    """The code map behind the condition: a build re-run (the door's requeue, a stop-cancel re-run, an operator
    rebuild, a crown rebuild) always binds a different task id; grade re-runs (auto retry, rearm, regrade, restore,
    reclass) only hand back SUCCEEDED builds, which are never kept as ended."""
    import inspect

    from carbon.challenge_validator import lean_recipe

    source = inspect.getsource(lean_recipe.LeanRecipeAdapter._request)
    assert "INFRA_RERUN" in source and "+ str(rerun)" in source
    assert "CROWN_REBUILD" in source and "+ rebuild" in source
    requeue = inspect.getsource(lean_recipe.LeanRecipeAdapter._requeue_failed_build)
    assert "requests[rerun + 1]" in requeue
    assert "SUCCEEDED" not in auto_grade.ENDED_STATES


def test_an_unreadable_owner_is_asked_once_per_recheck_window(monkeypatch):
    """case-procs 21 Nov 08:14Z (row 6 leftovers): a task in no open view and no lazy index whose owner read answers
    None costs ONE adapter.owner read per window, not one per scan; once its owner is readable it is answered.
    """
    grader, _asked = _grader({}, {})
    del grader._owner_of  # the real method, not the fixture's stand-in
    grader._hotkey_of = lambda task: None
    reads = []
    answer = {"value": None}

    def owner(task):
        reads.append(task)
        return answer["value"]

    grader.intake.adapter.owner = owner
    clock = {"now": 1000.0}
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: clock["now"])
    assert grader._owner_of(REFUSED) is None
    assert grader._owner_of(REFUSED) is None  # within the window: not asked again
    assert reads == [REFUSED]
    clock["now"] += grader.OWNER_UNREADABLE_RECHECK_SECONDS
    answer["value"] = "5Owner"
    assert (
        grader._owner_of(REFUSED) == "5Owner"
    )  # asked again after the window, and readable now
    assert reads == [REFUSED, REFUSED]
    # an owner found in memory is answered at once, whatever the window
    grader._hotkey_of = lambda task: "5Open"
    assert grader._owner_of(FAILED) == "5Open"


def test_is_pending_answers_for_one_task_exactly_as_the_pending_list(tmp_path):
    """Submit latency (21 Nov 2026): `AutoGrader.is_pending(task)` == ``task in pending()`` (marker, ended, submitted),
    read for one task (the coldkey place's check) instead of every marker and every submission.
    """
    from types import SimpleNamespace

    from carbon.challenge_validator import auto_grade

    submitted = ["rtsk_" + c * 64 for c in "abcd"]
    ledger = SimpleNamespace(
        submitted_outcomes=lambda contract: list(submitted),
        is_submitted_outcome=lambda contract, task: task in submitted,
    )
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(ledger=ledger, contract_digest="sha256:" + "0" * 64)
    )
    grader.markers = tmp_path / "markers"
    grader.ended = tmp_path / "ended"
    grader.markers.mkdir()
    (grader.markers / (submitted[0] + ".json")).write_text("{}")
    auto_grade.note_ended(grader.ended, submitted[1])
    listed = set(grader.pending())
    for task in [*submitted, "rtsk_" + "e" * 64, "not-a-task"]:
        assert grader.is_pending(task) == (task in listed), task
    assert listed == {submitted[2], submitted[3]}
