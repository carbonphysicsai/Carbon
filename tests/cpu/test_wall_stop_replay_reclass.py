"""D2 and the re-class step (Lead, 13 Nov; testnet Motor wall stops #1-#4).

D2: a re-queued task whose first attempt already settled its inference child FAILED_MINER REPLAYS that operation (the worker
does not run). A replay is the record of an EARLIER observation, so a door must never count it as a new candidate wall
stop: it is typed ``replayed_not_rerun``, given back as infrastructure, and never counted.

Re-class: the owner path that gives back one COUNTED / WORKER_WALL_LIMIT_REACHED slot the Validator ruled was not the
candidate's (``infra_requeue reclass``): RELEASED / FAILED_INFRA with the ruling and the prior state logged, no
rescore, no regrade, no re-queue. SYNTHETIC ledgers and markers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from carbon.challenge_validator import (
    auto_grade,
    auto_retry,
    direct_intake,
    infra_requeue,
)
from carbon.challenge_validator.exam_cap import ExamCap, ExamCapRefused
from tests.cpu import test_auto_grade as ag
from tests.cpu.test_infra_requeue import A, B, _root, _row, _rows

RULING = "CVMOTORC-L9753"


# --- D2: a replay is not a new candidate wall stop ------------------------------------------------------------------------


def _wall(*, replayed):
    from carbon.reconstruction.worker.model import WorkerCode

    failure = ag._miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    failure.replayed = replayed
    return failure


def test_a_fresh_wall_stop_is_not_a_replay():
    assert _wall(replayed=False).replayed is False
    assert auto_grade._candidate_wall_stop(_wall(replayed=False)) is True


def test_a_replayed_wall_stop_is_not_a_candidate_wall_stop():
    assert auto_grade._candidate_wall_stop(_wall(replayed=True)) is False


def test_a_replayed_wall_stop_is_given_back_typed_and_never_counted(tmp_path):
    grader, cap, ident, ledger = ag._wall_setup(tmp_path, _wall(replayed=True))
    assert grader.run_once() == (ag.A, "FAILED")
    assert ag._row(ledger) == [("RELEASED", "FAILED_INFRA")]
    marker = ag._marker(tmp_path, ag.A)
    assert marker["state"] == "FAILED"
    assert marker["code"] == auto_grade.REPLAYED_NOT_RERUN == "replayed_not_rerun"
    assert cap.released_on_infra(**ident)  # the slot is the miner's again
    # nothing was counted, and the contention guard never ran (no row in the wall-stops log)
    assert not (tmp_path / "auto-grade" / "wall-stops.jsonl").exists()


def test_a_fresh_wall_stop_is_still_counted_as_before(tmp_path):
    grader, _cap, _ident, ledger = ag._wall_setup(tmp_path, _wall(replayed=False))
    assert grader.run_once() == (ag.A, "CANDIDATE_FAILED")
    assert ag._row(ledger) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]


def test_the_carrier_marks_only_a_replay(tmp_path):
    """The carrier sets the mark where it re-raises a settled FAILED_MINER operation, and nowhere else."""
    import inspect

    from carbon.development_session import research_carrier as carrier

    source = inspect.getsource(carrier)
    assert source.count("replay.replayed = True") == 1
    assert "self.replayed = False" in inspect.getsource(carrier.MinerProgramFailure)


# --- the re-class step ---------------------------------------------------------------------------------------------------------


def _marker_file(
    root, task, state="CANDIDATE_FAILED", code="WORKER_WALL_LIMIT_REACHED"
):
    markers = root / "auto-grade" / "markers"
    markers.mkdir(parents=True, exist_ok=True)
    path = markers / (task + ".json")
    path.write_text(
        json.dumps(
            {
                "schema": auto_grade.SCHEMA,
                "submission_id": task,
                "state": state,
                "code": code,
                "entry_id": None,
            }
        )
    )
    return path


def _wall_stop_log(root, task, **row):
    path = root / "auto-grade" / "wall-stops.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as log:
        log.write(
            json.dumps(
                {
                    "task": task,
                    "counted": True,
                    "uncontended": True,
                    "samples": 0,
                    **row,
                }
            )
            + "\n"
        )


def _counted_wall(tmp_path, task=A):
    root, ledger = _root(tmp_path)
    path = _marker_file(root, task)
    _row(ledger, task, "COUNTED", "WORKER_WALL_LIMIT_REACHED")
    return root, ledger, path


def test_a_dry_run_shows_the_row_and_the_wall_stop_and_changes_nothing(tmp_path):
    root, ledger, _path = _counted_wall(tmp_path)
    _wall_stop_log(root, A, samples=0)
    out = infra_requeue.reclass(root, A, ruling=RULING)
    assert out["reclassed"]["prior_state"] == "COUNTED"
    assert out["reclassed"]["prior_status"] == "WORKER_WALL_LIMIT_REACHED"
    assert out["wall_stop"] == {"counted": True, "uncontended": True, "samples": 0}
    assert "refused" not in out and out["apply"] is False
    assert _rows(ledger, A) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]
    assert not (root / "auto-grade" / "requeued" / "reclass.jsonl").exists()


def test_apply_gives_the_slot_back_keeps_the_history_and_logs_the_ruling(tmp_path):
    root, ledger, path = _counted_wall(tmp_path)
    before = path.read_bytes()
    out = infra_requeue.reclass(root, A, ruling=RULING, apply=True, clock=lambda: 7)
    assert "refused" not in out
    assert out["after"] == {"state": "RELEASED", "status": "FAILED_INFRA"}
    # the row stays as history, given back; nothing else of the door moves
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]
    kept = root / "auto-grade" / "requeued" / "reclass-kept" / (A + ".json")
    assert kept.read_bytes() == before  # the old marker, byte for byte
    sha = hashlib.sha256(before).hexdigest()
    assert out["marker"] == {"replaced": True, "kept_sha256": sha}
    lines = (
        (root / "auto-grade" / "requeued" / "reclass.jsonl").read_text().splitlines()
    )
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["task"] == A and record["ruling"] == RULING and record["at_ns"] == 7
    assert (record["prior_state"], record["prior_status"]) == (
        "COUNTED",
        "WORKER_WALL_LIMIT_REACHED",
    )
    assert (record["state"], record["status"]) == ("RELEASED", "FAILED_INFRA")
    assert record["reason"] == "counted_wall_stop_ruled_not_the_candidates"
    assert record["marker_kept_sha256"] == sha and record["marker_replaced"] is True
    assert not list(
        (root / "auto-grade" / "requeued").glob("*.attempt-*")
    )  # no requeue


def _read(path):
    return json.loads(path.read_text())


def test_the_marker_is_replaced_so_the_miner_stops_seeing_a_wall_stop(tmp_path):
    root, _ledger, path = _counted_wall(tmp_path)
    infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    marker = _read(path)
    assert marker["schema"] == auto_grade.SCHEMA and marker["submission_id"] == A
    assert marker["state"] == "FAILED"
    assert (
        marker["code"] == infra_requeue.RECLASSED_CODE == "reclassed_not_the_candidates"
    )
    assert marker["next_step"] == "slot_returned"
    assert marker["next_step"] in auto_retry.NEXT_STEPS
    # no temporary file is left in the markers directory
    assert sorted(p.name for p in path.parent.iterdir()) == [A + ".json"]


class _Intake:
    """What `DirectRecipeIntake._grade_state_v4` and `_grade_state` read: the task's marker, nothing else."""

    def __init__(self, path):
        self.path = path

    def grade_marker(self, submission_id):
        return json.loads(self.path.read_text())

    _grade_state_v4 = direct_intake.DirectRecipeIntake._grade_state_v4
    _grade_state = direct_intake.DirectRecipeIntake._grade_state
    failure_v4 = direct_intake.DirectRecipeIntake.failure_v4


def test_the_miner_reads_infrastructure_after_the_reclass_not_a_wall_stop(tmp_path):
    """Validator-2C: v4 grade_state FAILED_INFRA (no failure), v3 not CANDIDATE_FAILED, once the ledger says RELEASED."""
    root, _ledger, path = _counted_wall(tmp_path)
    intake = _Intake(path)
    state, failure = intake._grade_state_v4("hotkey", A)
    assert state == "CANDIDATE_FAILED" and failure is not None  # as it was
    assert intake._grade_state("hotkey", A) == "CANDIDATE_FAILED"
    infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert intake._grade_state_v4("hotkey", A) == ("FAILED_INFRA", None)
    assert intake._grade_state("hotkey", A) is None


def test_the_task_has_a_marker_at_every_instant(tmp_path, monkeypatch):
    """With no marker the grader's `pending()` would pick the task up and replay it: the replacement is one os.replace."""
    root, _ledger, path = _counted_wall(tmp_path)
    seen = []
    real = os.replace

    def replace(source, target):
        seen.append((Path(source).name, Path(target).name, path.exists()))
        real(source, target)
        seen.append(("after", path.name, path.exists()))

    monkeypatch.setattr(infra_requeue.os, "replace", replace)
    infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert seen == [
        (A + ".json.reclass-tmp", A + ".json", True),  # the old marker is still there
        ("after", A + ".json", True),
    ]
    # and the temporary name is never a marker name (`markers/*.json`)
    assert not (A + ".json.reclass-tmp").endswith(".json")


def test_a_dry_run_changes_nothing_not_even_the_marker(tmp_path):
    root, _ledger, path = _counted_wall(tmp_path)
    before, mtime = path.read_bytes(), path.stat().st_mtime_ns
    infra_requeue.reclass(root, A, ruling=RULING)
    assert path.read_bytes() == before and path.stat().st_mtime_ns == mtime
    assert not (root / "auto-grade" / "requeued").exists()


def test_a_conflicting_kept_copy_refuses_and_changes_nothing(tmp_path):
    root, ledger, path = _counted_wall(tmp_path)
    kept = root / "auto-grade" / "requeued" / "reclass-kept"
    kept.mkdir(parents=True, mode=0o700)
    (kept / (A + ".json")).write_text("something else")
    before = path.read_bytes()
    out = infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert out["refused"] == "reclass_kept_copy_unavailable"
    assert path.read_bytes() == before
    assert _rows(ledger, A) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]


def test_a_marker_that_cannot_be_replaced_is_said_in_the_record(tmp_path, monkeypatch):
    root, ledger, path = _counted_wall(tmp_path)
    before = path.read_bytes()

    def refuse(source, target):
        raise OSError("disk")

    monkeypatch.setattr(infra_requeue.os, "replace", refuse)
    out = infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert out["marker"]["replaced"] is False
    assert path.read_bytes() == before  # still the old marker: never left without one
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]
    record = json.loads(
        (root / "auto-grade" / "requeued" / "reclass.jsonl").read_text().splitlines()[0]
    )
    assert record["marker_replaced"] is False


def test_the_miners_slot_is_free_again(tmp_path):
    from tests.cpu.test_infra_requeue import EXAM, HOTKEY

    root, ledger, _path = _counted_wall(tmp_path)
    infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert ExamCap(ledger).released_on_infra(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=A,
    )


def test_a_second_reclass_and_a_requeue_are_refused(tmp_path):
    root, ledger, _path = _counted_wall(tmp_path)
    infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    again = infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert again["refused"] == "already_given_back"
    assert A in infra_requeue.requeue(root, [A], apply=True)["refused"]
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


@pytest.mark.parametrize(
    ("state", "code", "refused"),
    [
        ("FAILED", "replayed_not_rerun", "marker_is_not_a_counted_wall_stop"),
        ("GRADED", None, "marker_is_not_a_counted_wall_stop"),
        (
            "CANDIDATE_FAILED",
            "WORKER_MEMORY_LIMIT_REACHED",
            "marker_is_not_a_counted_wall_stop",
        ),
        ("CANDIDATE_FAILED", None, "marker_is_not_a_counted_wall_stop"),
    ],
)
def test_only_a_counted_wall_stop_marker_is_reclassed(tmp_path, state, code, refused):
    root, ledger = _root(tmp_path)
    _marker_file(root, A, state, code)
    _row(ledger, A, "COUNTED", "WORKER_WALL_LIMIT_REACHED")
    out = infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert out["refused"] == refused
    assert _rows(ledger, A) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]


def test_a_task_with_no_marker_is_refused(tmp_path):
    root, ledger = _root(tmp_path)
    _row(ledger, A, "COUNTED", "WORKER_WALL_LIMIT_REACHED")
    out = infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert out["refused"] == "marker_is_not_a_counted_wall_stop"


@pytest.mark.parametrize(
    "rows",
    [
        [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")],
        [("RELEASED", "UNAVAILABLE")],
        [("RELEASED", "FAILED_INFRA")],
        [("RESERVED", None)],
        [],
    ],
)
def test_only_a_counted_wall_row_is_reclassed(tmp_path, rows):
    """(The ledger holds one row per task and exam: a second row cannot exist, so only the row's own state is tested.)"""
    root, ledger = _root(tmp_path)
    _marker_file(root, A)
    for state, status in rows:
        _row(ledger, A, state, status)
    out = infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert out["refused"] == "reclass_no_single_counted_wall_row"
    assert sorted(_rows(ledger, A)) == sorted(rows)


@pytest.mark.parametrize(
    "ruling", [None, "", "x", "two words", "a" * 97, "-leading", "semi;colon", 7]
)
def test_a_closed_ruling_id_is_required(tmp_path, ruling):
    root, ledger, _path = _counted_wall(tmp_path)
    out = infra_requeue.reclass(root, A, ruling=ruling, apply=True)
    assert out["refused"] == "ruling_id_required"
    assert _rows(ledger, A) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]


@pytest.mark.parametrize("task", ["", "rtsk_short", "../rtsk_" + "a" * 64, None])
def test_a_task_id_must_be_a_task(tmp_path, task):
    root, _ledger = _root(tmp_path)
    assert (
        infra_requeue.reclass(root, task, ruling=RULING)["refused"] == "not_a_task_id"
    )


def test_a_task_release_gave_back_is_refused(tmp_path):
    root, _ledger, _path = _counted_wall(tmp_path)
    directory = root / "auto-grade" / "requeued"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "releases.jsonl").write_text(json.dumps({"task": A}) + "\n")
    assert (
        infra_requeue.reclass(root, A, ruling=RULING, apply=True)["refused"]
        == "already_given_back"
    )


def test_only_the_named_task_moves(tmp_path):
    root, ledger, _path = _counted_wall(tmp_path)
    _marker_file(root, B)
    _row(ledger, B, "COUNTED", "WORKER_WALL_LIMIT_REACHED")
    infra_requeue.reclass(root, A, ruling=RULING, apply=True)
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]
    assert _rows(ledger, B) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]


def test_exam_cap_moves_only_a_single_counted_wall_row(tmp_path):
    _root_dir, ledger = _root(tmp_path)
    cap = ExamCap(ledger)
    for state, status in (
        ("RESERVED", None),
        ("RELEASED", "FAILED_INFRA"),
        ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE"),
        ("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED"),
    ):
        _row(ledger, A, state, status)
        with pytest.raises(ExamCapRefused) as refused:
            cap.reclass_counted_wall(A)
        assert refused.value.code == "reclass_no_single_counted_wall_row"
        assert _rows(ledger, A) == [(state, status)]
        with ledger._db() as db:
            db.execute("DELETE FROM exam_graded")
    with pytest.raises(ExamCapRefused):
        cap.reclass_counted_wall("")
    row = _row(ledger, A, "COUNTED", "WORKER_WALL_LIMIT_REACHED", epoch=9)
    done = cap.reclass_counted_wall(A)
    assert done["row"] == row and done["epoch"] == 9
    assert (done["prior_state"], done["prior_status"]) == (
        "COUNTED",
        "WORKER_WALL_LIMIT_REACHED",
    )
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


def test_the_command_reclasses_and_refuses(tmp_path, capsys):
    root, ledger, _path = _counted_wall(tmp_path)
    argv = ["reclass", "--root", str(root), "--id", A, "--ruling", RULING]
    assert infra_requeue.main(argv) == 0  # a dry run
    assert json.loads(capsys.readouterr().out)["reclassed"]["prior_state"] == "COUNTED"
    assert _rows(ledger, A) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]
    assert infra_requeue.main([*argv, "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["after"]["status"] == "FAILED_INFRA"
    assert infra_requeue.main([*argv, "--apply"]) == 3
    assert json.loads(capsys.readouterr().out)["refused"] == "already_given_back"


def test_a_root_with_no_state_is_not_a_crash(tmp_path):
    root = tmp_path / "empty"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    out = infra_requeue.reclass(root, A, ruling=RULING)
    assert out["refused"] == "marker_is_not_a_counted_wall_stop"
