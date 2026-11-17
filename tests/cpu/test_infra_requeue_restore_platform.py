"""`infra_requeue restore-platform` (Lead 17 Nov, 116 after the img21 migration): grades refused with
``leg_minimum_platform_mismatch`` (the pack's leg minimums bound to the pre-migration judge image) after their one
automatic retry are handed back ONCE more, uncharged, on their original epoch, with every ``requeue`` door check.
"""

from __future__ import annotations

import json

from test_infra_requeue import (  # noqa: F401 - `served` is this module's autouse fixture too
    BINDING,
    CAUSE,
    _DoorIntake,
    _evaluation,
    _failed,
    _root,
    _row,
    _rows,
    served,
)

from carbon.challenge_validator import auto_grade, infra_requeue

A, B, C = ("rtsk_" + c * 64 for c in "abc")
PLATFORM = infra_requeue.PLATFORM_CAUSE
RULING = "V2-receipt-17nov-restore"
KEPT = ("auto-grade", "requeued")


class _RefusingIntake(_DoorIntake):
    """The door's grade as far as the pack binding, then produce refuses on the leg-minimum platform (as on 116)."""

    def retain_result(self, submission_id, **kwargs):
        from carbon.challenge_validator.lean_recipe_retention import (
            RetentionUnavailable,
        )

        super().retain_result(submission_id, **kwargs)
        self.graded.remove(submission_id)
        raise RetentionUnavailable(PLATFORM)


def _after_auto_retry(root, ledger, task):
    """Attempt 1 refused on the platform, its one automatic retry (attempt 2) refused the same way and given back."""
    _failed(root, ledger, task, cause=PLATFORM)
    assert infra_requeue.requeue(root, [task], apply=True, auto=True)["requeued"] == [
        task
    ]
    (root / "auto-grade" / "artifacts" / task).mkdir(mode=0o700, parents=True)
    intake = _RefusingIntake(root, ledger, "sha256:" + "2" * 64)
    assert auto_grade.AutoGrader(intake, root).run_once() == (task, "FAILED")
    assert _rows(ledger, task) == [("RELEASED", "FAILED_INFRA")]


def test_a_task_refused_on_the_platform_after_its_retry_is_restored_once_and_grades(
    tmp_path,
):
    root, ledger = _root(tmp_path)
    _after_auto_retry(root, ledger, A)
    # before: neither the automatic retry nor the operator requeue may hand it back again
    assert infra_requeue.requeue(root, [A], auto=True)["refused"] == {
        A: "already_requeued"
    }
    assert infra_requeue.requeue(root, [A])["refused"] == {A: "already_requeued"}
    dry = infra_requeue.restore_platform(root, [A], ruling=RULING)
    assert dry["refused"] == {} and dry["restored"] == [A]
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()  # a dry run
    out = infra_requeue.restore_platform(root, [A], ruling=RULING, apply=True)
    assert out["restored"] == [A]
    kept = root.joinpath(*KEPT)
    assert PLATFORM in (kept / f"{A}.attempt-2.failure.txt").read_text()
    assert json.loads((kept / f"{A}.attempt-2.marker.json").read_text())["state"] == (
        "FAILED"
    )
    # attempt 2's evaluation files are kept, so attempt 3 binds its own
    assert json.loads((kept / f"{A}.attempt-2.evaluation" / BINDING).read_text()) == {
        "entry_id": "sha256:" + "2" * 64
    }
    restores = [
        json.loads(x) for x in (kept / "restores.jsonl").read_text().splitlines()
    ]
    assert [(x["attempt"], x["cause"], x["ruling"]) for x in restores] == [
        (3, PLATFORM, RULING)
    ]
    requeues = [
        json.loads(x) for x in (kept / "requeues.jsonl").read_text().splitlines()
    ]
    assert [(x["attempt"], x["kind"]) for x in requeues] == [
        (2, "requeue"),
        (3, "restore"),
    ]
    # uncharged on its own row: no fresh resubmit runs, the limit bypass is armed for attempt 3
    assert _rows(ledger, A) == [("RELEASED", "REQUEUED")]
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchall() == [(3, None)]
    intake = _DoorIntake(root, ledger, "sha256:" + "3" * 64)
    assert auto_grade.AutoGrader(intake, root).run_once() == (A, "GRADED")
    assert json.loads((_evaluation(root, A) / BINDING).read_text())["entry_id"] == (
        "sha256:" + "3" * 64
    )
    # once per task, and the ordinary requeue still never takes it
    again = infra_requeue.restore_platform(root, [A], ruling=RULING, apply=True)
    assert again["refused"] == {A: "already_restored"}
    assert infra_requeue.requeue(root, [A])["refused"] == {A: "already_requeued"}


def test_a_restore_takes_only_the_platform_cause_and_never_a_charged_or_graded_task(
    tmp_path,
):
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause=CAUSE)
    _failed(root, ledger, B, cause=PLATFORM, state="GRADED")
    _failed(root, ledger, C, cause=PLATFORM)
    _row(ledger, C, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    out = infra_requeue.restore_platform(root, [A, B, C, "nope"], ruling=RULING)
    assert out["restored"] == []
    assert out["refused"] == {
        A: "cause_not_platform",
        B: "cause_not_platform",  # a GRADED marker: only its own code counts
        C: "exam_row_counted_or_reserved",
        "nope": "not_a_task_id",
    }


def test_the_marker_code_alone_names_the_cause(tmp_path):
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause="something else")
    marker = root / "auto-grade" / "markers" / (A + ".json")
    body = json.loads(marker.read_text())
    marker.write_text(json.dumps({**body, "code": "regrade_unbound:" + PLATFORM}))
    assert infra_requeue.restore_platform(root, [A], ruling=RULING)["restored"] == [A]


def test_a_restore_needs_a_ruling_id_and_changes_nothing_without_one(tmp_path):
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause=PLATFORM)
    out = infra_requeue.restore_platform(root, [A], ruling="", apply=True)
    assert out["refused"] == {"*": "ruling_id_required"} and out["restored"] == []
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()


def test_the_command_dry_runs_every_failed_marker_and_applies_only_listed_ids(
    tmp_path, capsys
):
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause=PLATFORM)
    _failed(root, ledger, B, cause=CAUSE)
    args = ["restore-platform", "--root", str(root), "--ruling", RULING]
    assert infra_requeue.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["apply"] is False
    assert out["restored"] == [A] and out["refused"] == {B: "cause_not_platform"}
    ids = tmp_path / "ids.txt"
    ids.write_text(A + "\n")
    assert infra_requeue.main([*args, "--ids", str(ids), "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["restored"] == [A]
    assert not (root / "auto-grade" / "markers" / (A + ".json")).exists()


def test_a_task_restored_at_attempt_one_gets_its_one_bypass_and_no_auto_retry_after(
    tmp_path,
):
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause=PLATFORM)
    out = infra_requeue.restore_platform(root, [A], ruling=RULING, apply=True)
    assert out["restored"] == [A]
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchall() == [(2, None)]
    # the automatic retry can no longer hand it back too
    assert infra_requeue.requeue(root, [A], auto=True)["refused"] == {
        A: "already_requeued"
    }


def test_a_restore_line_alone_blocks_a_second_restore(tmp_path):
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause=PLATFORM)
    kept = root.joinpath(*KEPT)
    kept.mkdir(parents=True)
    (kept / "requeues.jsonl").write_text(
        json.dumps({"task": A, "kind": "restore", "attempt": 2}) + "\n"
    )
    assert infra_requeue.restore_platform(root, [A], ruling=RULING)["refused"] == {
        A: "already_restored"
    }


def test_the_command_refuses_apply_without_ids(tmp_path):
    import pytest

    root, _ledger = _root(tmp_path)
    args = ["restore-platform", "--root", str(root), "--ruling", RULING, "--apply"]
    with pytest.raises(SystemExit):
        infra_requeue.main(args)


class _UnavailableIntake(_DoorIntake):
    """The door's grade as 116 met it: the pack evaluation could not be computed (the platform check refused), so the
    retention returns UNAVAILABLE with that reason and its slot goes back (RELEASED / UNAVAILABLE).
    """

    def retain_result(self, submission_id, **kwargs):
        from carbon.challenge_validator.exam_cap import ExamCap

        cap = ExamCap(self.adapter.ledger)
        with self.adapter.ledger._db() as db:
            db.execute(
                "UPDATE exam_graded SET state='RELEASED', status='UNAVAILABLE' WHERE submission_id=?",
                (submission_id,),
            )
        assert cap is not None
        return {
            "entry_id": "sha256:" + "4" * 64,
            "private_evaluation_state": "UNAVAILABLE",
            "private_evaluation_reason": "regrade_unbound:" + PLATFORM,
        }


def test_a_graded_marker_keeping_the_platform_code_is_restored_and_grades(tmp_path):
    """The real grader's record of tonight's refusals: a GRADED marker with the platform code, the slot released."""
    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause=PLATFORM)
    (root / "auto-grade" / "markers" / (A + ".json")).unlink()
    _row(ledger, A, "RELEASED", "UNAVAILABLE")
    assert auto_grade.AutoGrader(
        _UnavailableIntake(root, ledger, "x"), root
    ).run_once() == (
        A,
        "GRADED",
    )
    marker = json.loads((root / "auto-grade" / "markers" / (A + ".json")).read_text())
    assert marker["state"] == "GRADED" and PLATFORM in marker["code"]
    assert infra_requeue.requeue(root, [A])["refused"] == {A: "marker_graded"}
    out = infra_requeue.restore_platform(root, [A], ruling=RULING, apply=True)
    assert out["restored"] == [A], out
    kept = root.joinpath(*KEPT)
    assert (
        json.loads((kept / f"{A}.attempt-1.marker.json").read_text())["state"]
        == "GRADED"
    )
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchall() == [(2, None)]
    (root / "auto-grade" / "artifacts" / A).mkdir(mode=0o700, parents=True)
    intake = _DoorIntake(root, ledger, "sha256:" + "3" * 64)
    assert auto_grade.AutoGrader(intake, root).run_once() == (A, "GRADED")
    assert intake.graded == [A]


def test_a_graded_marker_of_another_reason_or_a_scored_grade_is_never_restored(
    tmp_path,
):
    root, ledger = _root(tmp_path)
    for task, code in ((A, "dual_native_inference_binding"), (B, None)):
        _failed(root, ledger, task, cause=PLATFORM)
        marker = root / "auto-grade" / "markers" / (task + ".json")
        body = json.loads(marker.read_text())
        marker.write_text(json.dumps({**body, "state": "GRADED", "code": code}))
    _failed(root, ledger, C, cause=PLATFORM)
    marker = root / "auto-grade" / "markers" / (C + ".json")
    body = json.loads(marker.read_text())
    marker.write_text(json.dumps({**body, "state": "GRADED", "code": PLATFORM}))
    _row(ledger, C, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    out = infra_requeue.restore_platform(root, [A, B, C], ruling=RULING)
    assert out["refused"] == {
        A: "cause_not_platform",
        B: "cause_not_platform",
        C: "exam_row_counted_or_reserved",
    }
