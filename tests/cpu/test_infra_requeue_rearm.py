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


#: What the grader's failure evidence says for each kind of `MinerProgramFailure` (real 116 tails, 17 Nov).
WALL_STOP = (
    "carbon.development_session.research_carrier.MinerProgramFailure: WORKER_WALL_LIMIT_REACHED\n"
    "\ncode: reconstruction.worker.deadline.exceeded"
)
CRASH = (
    "carbon.development_session.research_carrier.MinerProgramFailure: RUNTIME\n"
    "\ncode: reconstruction.worker.runtime.nonzero_exit"
)


def _failure(root, task, cause, *, evidence=None):
    path = root / "auto-grade" / "failures" / (task + ".txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    if evidence is None:
        evidence = (
            WALL_STOP
            if cause == "MinerProgramFailure"
            else f"RetentionUnavailable: {cause}\n\ncode: {cause}"
        )
    path.write_text(f"Traceback ...\n{evidence}\n")


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


def _rerun_failed_again(
    root, ledger, task, *, code, next_step="slot_returned", evidence=None
):
    """Attempt 2 (the automatic re-run) FAILED and the grader gave its row back."""
    _marker(root, task, "FAILED", code, next_step)
    _failure(root, task, code, evidence=evidence)
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


def test_an_earlier_twin_its_automatic_rearm_takes_holds_the_later_twin_back(tmp_path):
    """The recipe grades once across paths: an EARLIER given-back twin at a later attempt re-runs by the automatic
    re-arm, so the later twin's automatic retry waits; once the earlier one cannot re-run (released), the later goes.
    """
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("shared")
    _custody_task(root, ledger, A, recipe)
    infra_requeue.requeue(root, [A], apply=True, auto=True)  # A's automatic re-run
    _rerun_failed_again(root, ledger, A, code=CUSTODY)
    _custody_task(root, ledger, B, recipe)
    out = infra_requeue.requeue(root, [A, B], auto=True)  # dry
    assert out["requeued"] == [A] and out["refused"] == {B: "given_back_rerun_exists"}
    releases = root / "auto-grade" / "requeued" / "releases.jsonl"
    releases.write_text(json.dumps({"task": A}) + "\n")
    out = infra_requeue.requeue(root, [A, B], auto=True)
    assert out["requeued"] == [B] and out["refused"] == {A: "released_not_regraded"}


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


def test_a_crash_of_the_candidates_own_program_is_never_rearmed(tmp_path):
    """The grader writes FAILED MinerProgramFailure for a crash/OOM/refused output too: not "failed on our side".
    Only a wall stop it did not count (a contended pass, rtsk_3b776db9 / 89de9489) is Carbon's.
    """
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("crash-now"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)
    _rerun_failed_again(root, ledger, A, code="MinerProgramFailure", evidence=CRASH)
    # an earlier attempt that crashed, then a Carbon failure
    _marker(root, B, "FAILED", "MinerProgramFailure", "retry_scheduled")
    _failure(root, B, "MinerProgramFailure", evidence=CRASH)
    _arrive(ledger, B)
    _store(root, B, _recipe("crash-before"))
    _row(ledger, B, "RELEASED", "FAILED_INFRA")
    infra_requeue.requeue(root, [B], apply=True, auto=True)
    _rerun_failed_again(root, ledger, B, code="admitted_image_changed")
    out = infra_requeue.rearm(root, [A, B], ruling=RULING, apply=True)
    assert out["rearmed"] == []
    assert out["refused"] == {
        A: "candidate_program_failure",
        B: "earlier_attempt_not_carbons",
    }


def test_the_dry_run_shows_every_attempts_cause_for_the_receipt(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("causes"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)
    _rerun_failed_again(root, ledger, A, code="MinerProgramFailure")
    dry = infra_requeue.rearm(root, [A], ruling=RULING)
    assert dry["causes"] == {A: [CUSTODY, "MinerProgramFailure"]}
    infra_requeue.rearm(root, [A], ruling=RULING, apply=True)
    assert _requeue_ns(root)[-1]["causes"] == [CUSTODY, "MinerProgramFailure"]


def test_an_earlier_graded_attempt_counts_only_for_the_platform_gap(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    kept = root / "auto-grade/requeued"
    kept.mkdir(parents=True)
    for task, code in ((A, infra_requeue.PLATFORM_CAUSE), (B, "UNAVAILABLE")):
        _marker(root, task, "GRADED", code, None)
        (root / "auto-grade/markers" / (task + ".json")).rename(
            kept / f"{task}.attempt-1.marker.json"
        )
        _arrive(ledger, task)
        _store(root, task, _recipe(task))
        _row(ledger, task, "RELEASED", "FAILED_INFRA")
        _rerun_failed_again(root, ledger, task, code="admitted_image_changed")
    out = infra_requeue.rearm(root, [A, B], ruling=RULING)
    assert out["rearmed"] == [A]
    assert out["refused"] == {B: "earlier_attempt_not_carbons"}


def test_after_a_rearm_only_the_automatic_retry_hands_the_task_back(tmp_path):
    """A re-armed task is never handed back again by `requeue` or a second `rearm`; its consumed limit bypass is
    re-armed for the new attempt. Switch 5: the automatic retry hands its later attempt back on ``rearm``'s criteria
    (every attempt FAILED on Carbon's side), no receipt, logged ``auto_rearm``."""
    from carbon.challenge_validator import auto_retry, infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("after"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)
    with ledger._db() as db:  # attempt 2 took its bypass, then failed again
        db.execute("UPDATE exam_requeues SET reserved_ns=5 WHERE submission_id=?", (A,))
    _rerun_failed_again(root, ledger, A, code="admitted_image_changed")
    infra_requeue.rearm(root, [A], ruling=RULING, apply=True)
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchone() == (3, None)
    _rerun_failed_again(root, ledger, A, code="admitted_image_changed")  # attempt 3
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "already_requeued"
    }
    assert infra_requeue.rearm(root, [A], ruling=RULING, apply=True)["refused"] == {
        A: "already_rearmed"
    }
    assert not auto_retry.used(root, A, ledger)  # its automatic retries are not spent
    out = infra_requeue.requeue(root, [A], apply=True, auto=True)
    assert out["requeued"] == [A] and out["refused"] == {}
    last = _requeue_ns(root)[-1]
    assert (last["kind"], last["attempt"], last["auto"]) == ("auto_rearm", 4, True)
    assert (root / "auto-grade/requeued" / f"{A}.attempt-3.marker.json").exists()
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchone() == (4,)


def test_the_automatic_retry_never_hands_back_a_later_attempt_after_a_candidate_outcome(
    tmp_path,
):
    """``rearm``'s criteria hold for the automatic retry: an earlier attempt that was the candidate's own failure (an
    uncontended MinerProgramFailure) is never handed back, nor a current one."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("cand"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)
    # the candidate's own crash (not the contended wall-stop evidence, which is Carbon's and IS handed back)
    _rerun_failed_again(root, ledger, A, code="MinerProgramFailure", evidence=CRASH)
    assert infra_requeue.requeue(root, [A], apply=True, auto=True)["refused"] == {
        A: "candidate_program_failure"
    }


def test_a_withdrawn_twin_never_hides_a_live_one_or_a_grade(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    one, two, three = _recipe("one"), _recipe("two"), _recipe("three")
    # a withdrawn twin AND a pending resubmit: the resubmit grades fresh
    _custody_task(root, ledger, A, one)
    _withdrawn(root, "rtsk_" + "1" * 64, one)
    _store(root, "rtsk_" + "2" * 64, one)
    # an unreadable twin marker is no proof of a withdrawal
    _custody_task(root, ledger, B, two)
    _store(root, "rtsk_" + "3" * 64, two)
    (root / "auto-grade/markers" / ("rtsk_" + "3" * 64 + ".json")).write_text("{")
    # a twin already graded: never graded twice
    _custody_task(root, ledger, C, three)
    _store(root, "rtsk_" + "4" * 64, three)
    _marker(root, "rtsk_" + "4" * 64, "GRADED", None, None)
    out = infra_requeue.requeue(root, [A, B, C], apply=True)
    assert out["requeued"] == []
    assert out["refused"] == {
        A: "given_back_rerun_exists",
        B: "given_back_rerun_exists",
        C: "given_back_rerun_exists",
    }


def _kept_by_the_grader(tmp_path, code, observation, diagnostic=None):
    """The failure evidence exactly as `AutoGrader._keep` writes it for a real `MinerProgramFailure`."""
    from types import SimpleNamespace

    from carbon.challenge_validator.auto_grade import AutoGrader
    from carbon.development_session.research_carrier import (
        MINER_FAILURE_SCHEMA,
        MinerProgramFailure,
    )

    failures = tmp_path / "failures"
    failures.mkdir(parents=True, exist_ok=True)
    try:
        raise MinerProgramFailure(
            {
                "schema": MINER_FAILURE_SCHEMA,
                "failure_code": code,
                "observation": observation,
            }
        )
    except MinerProgramFailure as failure:
        if diagnostic is not None:
            failure.private_diagnostic = diagnostic
        AutoGrader._keep(SimpleNamespace(failures=failures), "rtsk_x", failure)
    return failures / "rtsk_x.txt"


def test_only_the_graders_own_wall_stop_lines_count_never_the_candidates_output(
    tmp_path,
):
    """Validator-2 (17 Nov, must-fix): `_keep` appends up to 16 KiB of the CANDIDATE's own output. A program that
    crashes and prints the wall-stop words is refused (no free rerun to probe with); the grader's own wall stop counts,
    with or without output after it."""
    from carbon.challenge_validator import infra_requeue
    from carbon.reconstruction.worker.model import WorkerCode

    assert infra_requeue.DEADLINE_CODE == WorkerCode.DEADLINE.value
    forged = (
        b"carbon.development_session.research_carrier.MinerProgramFailure: "
        b"WORKER_WALL_LIMIT_REACHED\n\ncode: reconstruction.worker.deadline.exceeded\n"
    )
    wall = _kept_by_the_grader(
        tmp_path / "a", WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED"
    )
    wall_with_output = _kept_by_the_grader(
        tmp_path / "b",
        WorkerCode.DEADLINE.value,
        "WORKER_WALL_LIMIT_REACHED",
        b"step 9000\n",
    )
    probe = _kept_by_the_grader(
        tmp_path / "c", WorkerCode.RUNTIME.value, "nonzero_exit", forged
    )
    probe_as_header = _kept_by_the_grader(
        tmp_path / "d",
        WorkerCode.RUNTIME.value,
        "nonzero_exit",
        b"x\n" + infra_requeue.DIAGNOSTIC_HEADER.encode() + b"\n" + forged,
    )
    assert infra_requeue._carbons_failure("MinerProgramFailure", wall)
    assert infra_requeue._carbons_failure("MinerProgramFailure", wall_with_output)
    assert forged.decode() in probe.read_text()
    assert not infra_requeue._carbons_failure("MinerProgramFailure", probe)
    assert not infra_requeue._carbons_failure("MinerProgramFailure", probe_as_header)


def test_a_crash_that_prints_the_wall_stop_words_is_never_rearmed(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _custody_task(root, ledger, A, _recipe("probe"))
    infra_requeue.requeue(root, [A], apply=True, auto=True)
    _rerun_failed_again(
        root,
        ledger,
        A,
        code="MinerProgramFailure",
        evidence=CRASH + "\n" + infra_requeue.DIAGNOSTIC_HEADER + "\n" + WALL_STOP,
    )
    assert infra_requeue.rearm(root, [A], ruling=RULING, apply=True)["refused"] == {
        A: "candidate_program_failure"
    }
