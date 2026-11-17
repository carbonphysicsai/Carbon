"""17 Nov (Lead; owner D11): the live requeue tools for the custody failures and the second re-arm.

Each case is the shape of a real 116 task (markers read from live by Live ops, codex-queue/reports/REARM_20261117):
- rtsk_15ba1fe3 / 45c6b2ff / 79964ef7 / a0bdb655: FAILED ``operator_bank_custody_unavailable``, given back
  (RELEASED / FAILED_INFRA), its only same-recipe twin WITHDRAWN by the miner -> requeued once, uncharged;
- rtsk_43abaf0c: the same, but its twin is a built resubmit not yet graded -> refused (it grades fresh; never twice);
- rtsk_3b776db9: custody, auto re-run, then FAILED again (a contended wall stop the grader wrote FAILED) -> ``rearm``;
- rtsk_89de9489: FAILED, auto re-run (evaluation kept), then FAILED ``admitted_image_changed`` -> ``rearm``.
"""

from __future__ import annotations

import json
import sqlite3

from test_infra_requeue import (  # noqa: F401 (the autouse served-contract fixture)
    EXAM,
    HOTKEY,
    A,
    B,
    C,
    D,
    _recipe,
    _root,
    _row,
    _rows,
    _store,
    served,
)

CUSTODY = "operator_bank_custody_unavailable"
RULING = "V2-REARM-20261117"


def _marker(root, task, state, code, next_step):
    from carbon.challenge_validator.auto_grade import SCHEMA

    path = root / "auto-grade" / "markers" / (task + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "submission_id": task,
                "state": state,
                "code": code,
                "next_step": next_step,
                "entry_id": None,
            }
        )
    )
    return path


def _failure(root, task, cause):
    path = root / "auto-grade" / "failures" / (task + ".txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"Traceback ...\nRetentionUnavailable: {cause}\n\ncode: {cause}\n")


def _arrive(ledger, task):
    from test_infra_requeue import _arrived

    _arrived(ledger, task)


def _custody_task(root, ledger, task, recipe):
    """A first grade that FAILED on the bank custody write and was given back (the real 15ba1fe3 shape)."""
    _marker(root, task, "FAILED", CUSTODY, "retry_scheduled")
    _failure(root, task, CUSTODY)
    _arrive(ledger, task)
    _store(root, task, recipe)
    _row(ledger, task, "RELEASED", "FAILED_INFRA")


def _withdrawn(root, task, recipe):
    _store(root, task, recipe)
    _marker(root, task, "WITHDRAWN_BY_MINER", "withdrawn_by_miner", None)


def test_the_withdrawn_state_is_the_graders_own():
    from carbon.challenge_validator import auto_grade, infra_requeue

    assert infra_requeue.WITHDRAWN == auto_grade.WITHDRAWN_STATE


def test_a_custody_failure_with_only_a_withdrawn_twin_is_requeued_once_uncharged(
    tmp_path,
):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("custody")
    _custody_task(root, ledger, A, recipe)
    _withdrawn(root, B, recipe)
    dry = infra_requeue.requeue(root, [A])
    assert dry["requeued"] == [A] and dry["refused"] == {}
    assert _rows(ledger, A) == [
        ("RELEASED", "FAILED_INFRA")
    ]  # a dry run changes nothing
    out = infra_requeue.requeue(root, [A], apply=True)
    assert out["requeued"] == [A]
    assert _rows(ledger, A) == [("RELEASED", "REQUEUED")]  # no slot held, its own row
    assert not (
        root / "auto-grade/markers" / (A + ".json")
    ).exists()  # the grader takes it next
    assert (root / "auto-grade/requeued" / f"{A}.attempt-1.marker.json").exists()
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "already_requeued"
    }


def test_a_custody_failure_whose_resubmit_waits_to_grade_is_left_to_it(tmp_path):
    """rtsk_43abaf0c: its twin of the same recipe is built and not graded yet; re-queueing would grade the recipe twice."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("resubmitted")
    _custody_task(root, ledger, A, recipe)
    _store(root, B, recipe)  # built, no marker: the grader takes it fresh
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "given_back_rerun_exists"
    }
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


def _rerun_failed_again(root, ledger, task, *, code, next_step="slot_returned"):
    """Attempt 2 (the automatic re-run) FAILED on Carbon's side and the grader gave its row back."""
    _marker(root, task, "FAILED", code, next_step)
    _failure(root, task, code)
    with ledger._db() as db:
        db.execute(
            "UPDATE exam_graded SET status='FAILED_INFRA', state='RELEASED' WHERE submission_id=?",
            (task,),
        )


def _requeue_ns(root):
    return [
        json.loads(line)
        for line in (root / "auto-grade/requeued/requeues.jsonl")
        .read_text()
        .splitlines()
    ]


def test_a_task_whose_rerun_also_failed_on_our_side_is_rearmed_once(tmp_path):
    """rtsk_3b776db9: custody, re-run, then FAILED again. ``requeue`` refuses it; ``rearm`` takes it once, uncharged,
    on its own row and original epoch; a second ``rearm`` refuses."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("twice"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)  # the automatic re-run
    _rerun_failed_again(root, ledger, A, code="MinerProgramFailure")
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "already_requeued"
    }
    assert infra_requeue.rearm(root, [A], ruling="")["refused"] == {
        "*": "ruling_id_required"
    }
    dry = infra_requeue.rearm(root, [A], ruling=RULING)
    assert dry["rearmed"] == [A] and _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]
    out = infra_requeue.rearm(root, [A], ruling=RULING, apply=True)
    assert out["rearmed"] == [A] and out["refused"] == {}
    assert _rows(ledger, A) == [("RELEASED", "REQUEUED")]
    kept = root / "auto-grade/requeued"
    assert (kept / f"{A}.attempt-2.marker.json").exists()
    assert (kept / f"{A}.attempt-2.failure.txt").exists()
    assert not (root / "auto-grade/markers" / (A + ".json")).exists()
    line = _requeue_ns(root)[-1]
    assert (line["kind"], line["attempt"], line["cause"], line["ruling"]) == (
        "rearm",
        3,
        "MinerProgramFailure",
        RULING,
    )
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchone() == (3, None)
    assert infra_requeue.rearm(root, [A], ruling=RULING, apply=True)["refused"] == {
        A: "already_rearmed"
    }


def test_a_rerun_that_failed_on_an_image_change_keeps_its_evaluation_files_aside(
    tmp_path,
):
    """rtsk_89de9489: attempt 1 FAILED (its evaluation kept by the re-run), attempt 2 FAILED admitted_image_changed
    after writing evaluation files of its own: they are kept as attempt 2's, so attempt 3 binds its own.
    """
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _marker(root, A, "FAILED", "MinerProgramFailure", "retry_scheduled")
    _failure(root, A, "MinerProgramFailure")
    _arrive(ledger, A)
    _store(root, A, _recipe("image"))
    _row(ledger, A, "RELEASED", "FAILED_INFRA")
    evaluation = root / "auto-grade/artifacts" / (A + ".evaluation")
    evaluation.mkdir(parents=True)
    (evaluation / "evaluation-pack-binding.json").write_text("{}")
    assert infra_requeue.requeue(root, [A], apply=True, auto=True)["requeued"] == [A]
    evaluation.mkdir(parents=True)
    (evaluation / "evaluation-pack-binding.json").write_text('{"attempt": 2}')
    _rerun_failed_again(root, ledger, A, code="admitted_image_changed")
    out = infra_requeue.rearm(root, [A], ruling=RULING, apply=True)
    assert out["rearmed"] == [A]
    kept = root / "auto-grade/requeued"
    assert (kept / f"{A}.attempt-1.evaluation").is_dir()
    assert json.loads(
        (kept / f"{A}.attempt-2.evaluation/evaluation-pack-binding.json").read_text()
    ) == {"attempt": 2}
    assert not evaluation.exists()


def test_rearm_refuses_what_is_not_a_second_failure_on_our_side(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    # never handed back: the automatic retry or `requeue` is its path
    _custody_task(root, ledger, A, _recipe("a"))
    # re-run, then a candidate outcome: never re-armed (a contested wall stop is `reclass`'s)
    _custody_task(root, ledger, B, _recipe("b"))
    infra_requeue.requeue(root, [B], apply=True, auto=True)
    _marker(root, B, "CANDIDATE_FAILED", "WORKER_WALL_LIMIT_REACHED", None)
    # re-run, failed again, but the round was graded meanwhile: never
    _custody_task(root, ledger, C, _recipe("c"))
    infra_requeue.requeue(root, [C], apply=True, auto=True)
    _rerun_failed_again(root, ledger, C, code="admitted_image_changed")
    with ledger._db() as db:
        db.execute("UPDATE exam_graded SET state='COUNTED' WHERE submission_id=?", (C,))
    # an earlier attempt that was the candidate's own outcome
    _marker(root, D, "CANDIDATE_FAILED", "WORKER_WALL_LIMIT_REACHED", None)
    _arrive(ledger, D)
    _store(root, D, _recipe("d"))
    kept = root / "auto-grade/requeued"
    kept.mkdir(parents=True, exist_ok=True)
    (root / "auto-grade/markers" / (D + ".json")).rename(
        kept / f"{D}.attempt-1.marker.json"
    )
    _rerun_failed_again(root, ledger, D, code="admitted_image_changed")
    out = infra_requeue.rearm(root, [A, B, C, D], ruling=RULING, apply=True)
    assert out["rearmed"] == []
    assert out["refused"] == {
        A: "not_rearmed_before",
        B: "marker_candidate_failed",
        C: "exam_row_counted_or_reserved",
        D: "earlier_attempt_not_carbons",
    }


def test_the_rearm_command(tmp_path, capsys):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("cli"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)
    _rerun_failed_again(root, ledger, A, code="admitted_image_changed")
    ids = tmp_path / "ids.txt"
    ids.write_text(A + "\n")
    args = ["rearm", "--root", str(root), "--ids", str(ids), "--ruling", RULING]
    assert infra_requeue.main(args) == 0
    assert json.loads(capsys.readouterr().out)["rearmed"] == [A]
    assert (root / "auto-grade/markers" / (A + ".json")).exists()  # dry run
    assert infra_requeue.main([*args, "--apply"]) == 0
    assert not (root / "auto-grade/markers" / (A + ".json")).exists()
    assert sqlite3.connect(root / "attempts.sqlite3").execute(
        "SELECT status FROM exam_graded WHERE submission_id=?", (A,)
    ).fetchone() == ("REQUEUED",)
    assert (
        EXAM and HOTKEY
    )  # the shared fixture's identity (imported for the row helpers)
