"""A grade stopped mid-way (a crash, a kill, an unplanned restart) is re-run cleanly on Carbon's side.

Switch-2 copy, 17 Nov 2026 (codex-queue/reports/SWITCH2_COPY_READS_20261117.md), two live bugs on any mid-grade stop:
- (b) the re-run met the stopped attempt's create-only evaluation-pack binding and failed FAILED_INFRA, burning the one
  automatic retry (rtsk_34ff589c, c276992f, ca1df3a8): the grader now sets the stopped attempt's evaluation aside;
- (c) the re-run met the stopped attempt's RESERVED inference op ("research operation ambiguous", rtsk_a6b1490a), and
  an op settled FAILED_INFRA was replayed as if it were a worker result: a re-run of a counted grade takes a fresh
  regrade generation, and the carrier types a settled FAILED_INFRA as a replayed infrastructure failure.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_fixed_practice_failure_diagnostics import harness as _runner_harness

from carbon.challenge_validator import auto_grade, infra_requeue
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _runner_harness  # pytest discovers the existing fixture by this name
TASK = "rtsk_" + "a" * 64
OTHER = "rtsk_" + "b" * 64


def _interrupted(root, task=TASK, binding=b'{"entry_id": "e1"}'):
    """What a grade stopped after its pack binding leaves: the evaluation directory and no marker."""
    evaluation = root / "auto-grade" / "artifacts" / (task + ".evaluation")
    evaluation.mkdir(parents=True)
    (evaluation / "evaluation-pack-binding.json").write_bytes(binding)
    return evaluation


def _marker(root, task, state="GRADED"):
    path = root / "auto-grade" / "markers" / (task + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": auto_grade.SCHEMA, "state": state}))


# ---------------------------------------------------------------- (b) the stopped attempt's evaluation is set aside


def test_a_stopped_attempts_evaluation_is_moved_aside_never_deleted(tmp_path):
    evaluation = _interrupted(tmp_path)
    kept = infra_requeue.set_aside_interrupted(tmp_path, TASK, clock=lambda: 7)
    assert kept == f"{TASK}.interrupted-1.evaluation"
    assert not evaluation.exists()
    moved = tmp_path / "auto-grade" / "requeued" / kept
    assert (
        moved / "evaluation-pack-binding.json"
    ).read_bytes() == b'{"entry_id": "e1"}'
    log = (tmp_path / "auto-grade/requeued/interrupted.jsonl").read_text().splitlines()
    assert [json.loads(line) for line in log] == [
        {"task": TASK, "kept": kept, "files": 1, "at_ns": 7}
    ]
    # a second stop of the same task: its own name, nothing overwritten
    _interrupted(tmp_path, binding=b'{"entry_id": "e2"}')
    assert infra_requeue.set_aside_interrupted(tmp_path, TASK) == (
        f"{TASK}.interrupted-2.evaluation"
    )
    assert (
        moved / "evaluation-pack-binding.json"
    ).read_bytes() == b'{"entry_id": "e1"}'


def test_a_task_with_a_marker_or_no_evaluation_is_never_touched(tmp_path):
    evaluation = _interrupted(tmp_path)
    _marker(tmp_path, TASK)
    assert infra_requeue.set_aside_interrupted(tmp_path, TASK) is None
    assert evaluation.is_dir()  # a finished grade's record stays where it is
    assert infra_requeue.set_aside_interrupted(tmp_path, OTHER) is None
    assert infra_requeue.set_aside_interrupted(tmp_path, "not-a-task") is None
    assert not (tmp_path / "auto-grade/requeued/interrupted.jsonl").exists()


def test_the_grader_sets_it_aside_before_it_grades_the_task(tmp_path):
    """`AutoGrader._grade_one` (both the serial round and a parallel claim): the grade never sees the stopped attempt's
    create-only files."""
    _interrupted(tmp_path)
    seen = []

    def grade_on_lane(submission_id, turn):
        seen.append(
            (
                tmp_path / "auto-grade/artifacts" / (submission_id + ".evaluation")
            ).exists()
        )
        return auto_grade._NEXT

    grader = SimpleNamespace(root=tmp_path, _grade_on_lane=grade_on_lane)
    assert auto_grade.AutoGrader._grade_one(grader, TASK) is auto_grade._NEXT
    assert seen == [False]
    assert (
        tmp_path / "auto-grade/requeued" / f"{TASK}.interrupted-1.evaluation"
    ).is_dir()


# ---------------------------------------------------------------- (c) a re-run takes fresh identities


def test_a_rerun_of_a_counted_grade_counts_its_earlier_attempts(tmp_path):
    base = tmp_path / "auto-grade" / "artifacts"
    base.mkdir(parents=True)
    assert (
        retention._regrade_generation(base, TASK) == 0
    )  # a first attempt: its id is unchanged
    kept = tmp_path / "auto-grade" / "requeued"
    kept.mkdir()
    for name in (
        f"{TASK}.attempt-1.evaluation",  # handed back once (requeue / auto retry)
        f"{TASK}.interrupted-1.evaluation",  # then stopped mid-grade
        f"{OTHER}.attempt-1.evaluation",  # another task's
        f"{TASK}.attempt-1.marker.json",  # not an evaluation
    ):
        (
            (kept / name).mkdir()
            if name.endswith(".evaluation")
            else (kept / name).write_text("{}")
        )
    assert retention._regrade_generation(base, TASK) == 2
    assert retention._regrade_generation(base, OTHER) == 1


def test_a_settled_infrastructure_failure_is_never_returned_as_a_worker_result(
    harness,
):
    """An op settled FAILED_INFRA (here by an interruption's reconcile) replays as Carbon's typed failure, marked a
    replay (the grader writes REPLAYED_NOT_RERUN), never as the reconciliation document posing as output.
    """
    harness.fail_stage, harness.error = "PROGRAM", WorkerFailure(WorkerCode.RUNTIME)
    with pytest.raises(WorkerFailure):
        harness.run(
            provenance="BATTERY_PUBLIC_PRACTICE"
        )  # Carbon's own program: left RESERVED
    ops = harness.ledger.status(owner="alice")["operations"]
    (op,) = [o for o in ops if o["state"] == "RESERVED"]
    harness.ledger.finish(
        op["id"],
        owner="alice",
        state="FAILED_INFRA",
        actual=op["reservation"],
        result={
            "schema": "carbon.autoresearch.worker-reconciliation.v1",
            "state": "FAILED_INFRA",
        },
    )
    harness.fail_stage = None
    with pytest.raises(WorkerFailure) as again:
        harness.run(provenance="BATTERY_PUBLIC_PRACTICE")
    assert again.value.code is WorkerCode.UNAVAILABLE
    assert again.value.replayed is True
