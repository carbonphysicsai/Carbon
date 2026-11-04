"""REG-UNAVAILABLE A2 (TL 4 Nov 03:14-03:44; Validator 03:15, 05:17): the one-shot operator tools of
`challenge_validator.infra_requeue` and the receiver's own `ExamCap.release_undelivered`.

Claims:
- ``list`` regenerates the stuck list from the door's own markers and ledger (never a frozen file), split by arrival.
- ``requeue`` hands only FAILED, registration-caused, never-charged tasks back to the receiver's REAL auto-grader, once
  (attempt 2, same task identity, its own row reused: no new slot); a graded task is NEVER re-queued; a dry run changes
  nothing; a task already given back as FAILED_INFRA is left to the door's fresh-rerun path.
- ``release`` frees one COUNTED slot only through `ExamCap.release_undelivered`, keeps the row and its prior state as
  history, never regrades, and refuses when the grade was delivered (marker or Ladder).
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

A, B, C, D, E, F = ("rtsk_" + c * 64 for c in "abcdef")
HOTKEY = "5" + "1" * 47
EXAM = "sha256:" + "e" * 64
#: 3 Nov 2026 00:00Z, the default split, in ns.
SPLIT_NS = 1_793_664_000 * 10**9
CAUSE = "direct_provider_registration_unavailable"


def _root(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ledger import AttemptLedger

    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    ledger = AttemptLedger(root / "attempts.sqlite3")
    ExamCap(ledger)  # the exam tables
    return root, ledger


def _arrived(ledger, task, *, at_ns=SPLIT_NS + 10**9, block=7_200):
    with ledger._db() as db:
        db.execute(
            "INSERT INTO attempts(at_ns, kind, hotkey, contract_digest, receipt, submission_sha256, "
            "submission_id) VALUES(?, 'OUTCOME', ?, 'sha256:c', ?, 'sha256:s', ?)",
            (at_ns, HOTKEY, json.dumps({"block": block}), task),
        )


def _row(ledger, task, state, status=None, *, epoch=20):
    with ledger._db() as db:
        return db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, "
            "submission_id, state, status, reserved_ns) VALUES(?,'f02','2.5',?,'GRADED',?,?,?,?,1)",
            (HOTKEY, EXAM, epoch, task, state, status),
        ).lastrowid


def _rows(ledger, task):
    with ledger._db() as db:
        return db.execute(
            "SELECT state, status FROM exam_graded WHERE submission_id=?", (task,)
        ).fetchall()


def _failed(root, ledger, task, *, cause=CAUSE, state="FAILED", arrived=True, **when):
    from carbon.challenge_validator.auto_grade import SCHEMA

    markers = root / "auto-grade" / "markers"
    failures = root / "auto-grade" / "failures"
    markers.mkdir(parents=True, exist_ok=True)
    failures.mkdir(parents=True, exist_ok=True)
    (markers / (task + ".json")).write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "submission_id": task,
                "state": state,
                "code": "Unavailable:unrecorded",
                "entry_id": None,
            }
        )
    )
    (failures / (task + ".txt")).write_text(f"Traceback ...\nUnavailable: {cause}\n")
    if arrived:
        _arrived(ledger, task, **when)


def _kept(root, task, suffix):
    return root / "auto-grade" / "requeued" / f"{task}.attempt-1.{suffix}"


# ---------------------------------------------------------------- list: the regenerated task list


def test_list_regenerates_the_stuck_list_from_the_door_split_at_3_nov(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)  # since 3 Nov
    _failed(root, ledger, B, at_ns=SPLIT_NS - 10**9)  # before 3 Nov
    _failed(root, ledger, C, state="GRADED")  # not FAILED: not listed at all
    _failed(root, ledger, D, cause="WorkerFailure")
    _failed(root, ledger, E)
    _row(ledger, E, "RELEASED", "FAILED_INFRA")  # given back: the fresh-rerun path
    _failed(root, ledger, F)
    _row(ledger, F, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    out = infra_requeue.scan(root)
    assert out["eligible"] == {"before_split": [B], "since_split": [A]}
    assert out["eligible_counts"] == {"before_split": 1, "since_split": 1}
    assert out["failed_markers"] == 5
    assert out["refused_counts"] == {
        "cause_not_registration_unavailable": 1,
        "given_back_resubmit_runs_fresh": 1,
        "exam_row_counted_or_reserved": 1,
    }
    assert out["arrived"][A] == "2026-11-03T00:00:01Z"
    # the read changes nothing
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()
    assert not (root / "auto-grade" / "requeued").exists()


def test_list_previews_the_round_limit_a_regrade_would_meet(tmp_path):
    """`ExamCap.reserve` still applies the slot rule to a re-queued task (TE audit risk; Validator ruling pending):
    the list says which tasks would meet it, before anything is applied."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, block=20 * 360)  # epoch 20
    _failed(root, ledger, B, block=40 * 360)  # epoch 40
    _row(
        ledger, C, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE", epoch=20
    )  # the miner's later grade, same round
    out = infra_requeue.scan(root)
    assert out["limit_preview"] == {A: "epoch_limit_reached"}


# ---------------------------------------------------------------- requeue


def test_requeue_hands_back_once_and_the_real_auto_grader_takes_it(tmp_path):
    from carbon.challenge_validator import auto_grade, infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _failed(root, ledger, C, state="GRADED")
    graded = []

    class Intake:
        adapter = SimpleNamespace(
            contract_digest="sha256:c",
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: (A, C)),
            owner=lambda submission_id: HOTKEY,
        )

        def retain_result(self, submission_id, **kwargs):
            graded.append(submission_id)
            return {"entry_id": "sha256:" + "1" * 64}

    grader = auto_grade.AutoGrader(Intake(), root)
    assert grader.pending() == []  # before: both have markers, nothing is graded
    dry = infra_requeue.requeue(root, [A, C])
    assert dry["requeued"] == [A] and dry["refused"] == {C: "marker_graded"}
    assert grader.pending() == []  # a dry run changes nothing
    out = infra_requeue.requeue(root, [A, C], apply=True)
    assert out["requeued"] == [A] and out["refused"] == {C: "marker_graded"}
    assert json.loads(_kept(root, A, "marker.json").read_text())["state"] == "FAILED"
    assert CAUSE in _kept(root, A, "failure.txt").read_text()
    log = (root / "auto-grade" / "requeued" / "requeues.jsonl").read_text().splitlines()
    assert [json.loads(line)["attempt"] for line in log] == [2]
    assert grader.pending() == [A]  # the graded task stays out
    assert grader.run_once() == (A, "GRADED")
    assert graded == [A]
    # one-shot: the same task is never handed back again, graded or not
    again = infra_requeue.requeue(root, [A], apply=True)
    assert again["refused"] == {A: "already_requeued"}


@pytest.mark.parametrize(
    "marker, row, code",
    [
        ("GRADED", None, "marker_graded"),
        ("CANDIDATE_FAILED", None, "marker_candidate_failed"),
        (
            "FAILED",
            ("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED"),
            "exam_row_counted_or_reserved",
        ),
        ("FAILED", ("RESERVED", None), "exam_row_counted_or_reserved"),
    ],
)
def test_a_graded_or_charged_task_is_never_requeued(tmp_path, marker, row, code):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, state=marker)
    if row is not None:
        _row(ledger, A, *row)
    out = infra_requeue.requeue(root, [A], apply=True)
    assert out["requeued"] == [] and out["refused"] == {A: code}
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()
    assert not _kept(root, A, "marker.json").exists()


def test_requeue_refuses_other_causes_strangers_and_given_back_tasks(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause="WorkerFailure")
    _failed(
        root, ledger, B, arrived=False
    )  # never submitted at this door: the grader would never take it
    _failed(root, ledger, D)
    _row(ledger, D, "RELEASED", "FAILED_INFRA")
    out = infra_requeue.requeue(root, [A, B, D, E, "x"], apply=True)
    assert out["requeued"] == []
    assert out["refused"] == {
        A: "cause_not_registration_unavailable",
        B: "not_submitted_at_this_door",
        D: "given_back_resubmit_runs_fresh",
        E: "no_marker",
        "x": "not_a_task_id",
    }


def test_a_requeued_task_reuses_its_own_row_so_no_new_slot_is_taken(tmp_path):
    from carbon.challenge_validator import infra_requeue
    from carbon.challenge_validator.exam_cap import ExamCap

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    row = _row(ledger, A, "RELEASED", "UNAVAILABLE")
    assert infra_requeue.requeue(root, [A], apply=True)["requeued"] == [A]
    assert _rows(ledger, A) == [("RELEASED", "UNAVAILABLE")]  # untouched by the tool
    cap = ExamCap(
        ledger,
        cadence={
            "capacity_gpu_lane_hours_per_day": 270.0,
            "rebuild_gpu_lane_hours": {"f02": 1.0},
            "lanes": 1,
            "measurement_digest": "sha256:" + "a" * 64,
            "class_record_digest": "sha256:" + "b" * 64,
        },
    )
    again = cap.reserve(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=A,
        block=7_200,
    )
    assert again == row
    with ledger._db() as db:
        assert db.execute("SELECT COUNT(*) FROM exam_graded").fetchone()[0] == 1


# ---------------------------------------------------------------- release


def test_release_frees_an_undelivered_counted_slot_through_exam_cap_and_keeps_history(
    tmp_path,
):
    from carbon.challenge_validator import exam_cap, infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    row = _row(ledger, A, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    dry = infra_requeue.release(root, A)
    assert dry["released"] == {
        "row": row,
        "prior_state": "COUNTED",
        "prior_status": "REQUIRED_LEG_MINIMUM_FAILED",
    }
    assert _rows(ledger, A) == [
        ("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    ]  # dry: unchanged
    out = infra_requeue.release(root, A, apply=True)
    assert "refused" not in out and out["after"] == {
        "state": "RELEASED",
        "status": "FAILED_INFRA",
    }
    assert _rows(ledger, A) == [
        ("RELEASED", "FAILED_INFRA")
    ]  # the row stays, as history
    assert exam_cap.ExamCap(ledger).released_on_infra(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=A,
    )  # so the door runs the miner's resubmit as a fresh task
    log = (root / "auto-grade" / "requeued" / "releases.jsonl").read_text().splitlines()
    record = json.loads(log[0])
    assert (
        record["prior_state"] == "COUNTED"
        and record["reason"] == "result_not_delivered"
    )
    # no regrade: the marker stays, and the task can never be re-queued afterwards
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "given_back_resubmit_runs_fresh"
    }
    # and a second release finds nothing to release
    assert infra_requeue.release(root, A, apply=True)["refused"] == (
        "release_no_single_counted_row"
    )


@pytest.mark.parametrize(
    "marker, code",
    [
        ("GRADED", "grade_delivered_or_unreadable"),
        ("CANDIDATE_FAILED", "grade_delivered_or_unreadable"),
        (None, "grade_not_finished"),
    ],
)
def test_release_refuses_when_the_grade_was_delivered_or_is_not_finished(
    tmp_path, marker, code
):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    if marker is not None:
        _failed(root, ledger, A, state=marker)
    _row(ledger, A, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    out = infra_requeue.release(root, A, apply=True)
    assert out["refused"] == code
    assert _rows(ledger, A) == [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")]


@pytest.mark.parametrize(
    "shown_epoch, refused", [(20, True), (19, False), (None, True)]
)
def test_release_refuses_when_the_miners_ladder_shows_that_round(
    tmp_path, shown_epoch, refused
):
    """A Ladder document of the row's round is a delivered grade (the miner reads best/latest); one with no epoch
    written since the slot was reserved cannot be told apart, so it refuses too (fail closed).
    """
    from carbon.challenge_validator import infra_requeue
    from carbon.challenge_validator.ladder_store import LadderStore

    root, ledger = _root(tmp_path)
    LadderStore(ledger)  # its tables
    _failed(root, ledger, A)
    _row(ledger, A, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED", epoch=20)
    document = {"status": "NOT_SCORED"}
    if shown_epoch is not None:
        document["epoch"] = shown_epoch
    with ledger._db() as db:
        db.execute(
            "INSERT INTO ladder_feedback_v2(hotkey, challenge_id, evaluation_version, exam_key, "
            "challenge_version, best, latest, updated_ns) VALUES(?,'f02','2.5',?,'2.5',NULL,?,5)",
            (HOTKEY, EXAM, json.dumps(document)),
        )
    out = infra_requeue.release(root, A, apply=True)
    if refused:
        assert out["refused"] == "ladder_shows_this_round"
        assert _rows(ledger, A) == [("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")]
    else:
        assert "refused" not in out
        assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


def test_exam_cap_release_undelivered_gives_back_only_a_single_counted_row(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap, ExamCapRefused

    _root_dir, ledger = _root(tmp_path)
    cap = ExamCap(ledger)
    for state, status in (
        ("RESERVED", None),
        ("RELEASED", "FAILED_INFRA"),
        ("RELEASED", "UNAVAILABLE"),
    ):
        _row(ledger, A, state, status)
        with pytest.raises(ExamCapRefused) as refused:
            cap.release_undelivered(A)
        assert refused.value.code == "release_no_single_counted_row"
        assert _rows(ledger, A) == [(state, status)]
        with ledger._db() as db:
            db.execute("DELETE FROM exam_graded")
    with pytest.raises(ExamCapRefused):
        cap.release_undelivered("")
    row = _row(ledger, A, "COUNTED", "MANDATORY_GATE_FAILED", epoch=9)
    done = cap.release_undelivered(A)
    assert done["row"] == row and done["epoch"] == 9
    assert (done["prior_state"], done["prior_status"]) == (
        "COUNTED",
        "MANDATORY_GATE_FAILED",
    )
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


# ---------------------------------------------------------------- the operator command


def test_the_command_lists_requeues_and_releases(tmp_path, capsys):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _failed(root, ledger, B)
    _row(ledger, B, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    ids = tmp_path / "ids.txt"
    assert infra_requeue.main(["list", "--root", str(root), "--out", str(ids)]) == 0
    assert ids.read_text() == A + "\n"
    assert json.loads(capsys.readouterr().out)["eligible_counts"]["since_split"] == 1
    assert infra_requeue.main(["requeue", "--root", str(root), "--ids", str(ids)]) == 0
    assert json.loads(capsys.readouterr().out)["apply"] is False
    assert (
        infra_requeue.main(
            ["requeue", "--root", str(root), "--ids", str(ids), "--apply"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["requeued"] == [A]
    assert infra_requeue.main(["release", "--root", str(root), "--id", A]) == 3
    assert json.loads(capsys.readouterr().out)["refused"] == "grade_not_finished"
    assert (
        infra_requeue.main(["release", "--root", str(root), "--id", B, "--apply"]) == 0
    )
    assert json.loads(capsys.readouterr().out)["after"]["status"] == "FAILED_INFRA"
