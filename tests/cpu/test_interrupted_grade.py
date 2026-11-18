"""A grade stopped mid-way (a crash, a kill, an unplanned restart) is re-run cleanly on Carbon's side.

Switch-2 copy, 17 Nov 2026 (codex-queue/reports/SWITCH2_COPY_READS_20261117.md), two live bugs on any mid-grade stop:
- (b) the re-run met the stopped attempt's create-only evaluation-pack binding and failed FAILED_INFRA, burning the one
  automatic retry (rtsk_34ff589c, c276992f, ca1df3a8): the grader now sets the stopped attempt's evaluation aside;
- (c) the re-run met the stopped attempt's RESERVED inference op ("research operation ambiguous", rtsk_a6b1490a), and
  an op settled FAILED_INFRA was replayed as if it were a worker result: a re-run of a counted grade takes a fresh
  regrade generation, and the carrier types a settled FAILED_INFRA as a replayed infrastructure failure.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from types import SimpleNamespace

import pytest
from test_fixed_practice_failure_diagnostics import harness as _runner_harness

from carbon.challenge_validator import auto_grade, infra_requeue
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _runner_harness  # pytest discovers the existing fixture by this name
TASK = "rtsk_" + "a" * 64
OTHER = "rtsk_" + "b" * 64


#: when "this" grader process started in these tests: after every directory `_interrupted` writes
LATER = time.time() + 3600


def _interrupted(root, task=TASK, binding=b'{"entry_id": "e1"}', *, age=600):
    """What a grade stopped after its pack binding leaves (in an EARLIER process): the evaluation directory and no
    marker, written ``age`` seconds before now."""
    evaluation = root / "auto-grade" / "artifacts" / (task + ".evaluation")
    evaluation.mkdir(parents=True, exist_ok=True)
    sidecar = evaluation / "evaluation-pack-binding.json"
    sidecar.write_bytes(binding)
    then = time.time() - age
    for path in (sidecar, evaluation):
        os.utime(path, (then, then))
    return evaluation


def _marker(root, task, state="GRADED"):
    path = root / "auto-grade" / "markers" / (task + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": auto_grade.SCHEMA, "state": state}))


# ---------------------------------------------------------------- (b) the stopped attempt's evaluation is set aside


def test_a_stopped_attempts_evaluation_is_moved_aside_never_deleted(tmp_path):
    evaluation = _interrupted(tmp_path)
    kept = infra_requeue.set_aside_interrupted(
        tmp_path, TASK, started=LATER, clock=lambda: 7
    )
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
    assert infra_requeue.set_aside_interrupted(tmp_path, TASK, started=LATER) == (
        f"{TASK}.interrupted-2.evaluation"
    )
    assert (
        moved / "evaluation-pack-binding.json"
    ).read_bytes() == b'{"entry_id": "e1"}'


def test_a_task_with_a_marker_or_no_evaluation_is_never_touched(tmp_path):
    evaluation = _interrupted(tmp_path)
    _marker(tmp_path, TASK)
    assert infra_requeue.set_aside_interrupted(tmp_path, TASK, started=LATER) is None
    assert evaluation.is_dir()  # a finished grade's record stays where it is
    assert infra_requeue.set_aside_interrupted(tmp_path, OTHER, started=LATER) is None
    assert (
        infra_requeue.set_aside_interrupted(tmp_path, "not-a-task", started=LATER)
        is None
    )
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

    grader = SimpleNamespace(
        root=tmp_path, process_started=LATER, _grade_on_lane=grade_on_lane
    )
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


def test_a_directory_this_grader_process_wrote_is_left_alone(tmp_path):
    """door-code review: a tick that ended (not gradable now, a degraded chain) after the binding and before a marker
    leaves THIS process's directory; the next tick must not move it and bump the generation tick by tick. Only a
    directory older than the process (a crash or kill always means a new process) is an interrupted attempt.
    """
    started = time.time()
    evaluation = _interrupted(tmp_path, age=-5)  # written after this process started
    assert infra_requeue.set_aside_interrupted(tmp_path, TASK, started=started) is None
    assert evaluation.is_dir()
    # one file written since, in an otherwise old directory: still this process's
    old = _interrupted(tmp_path / "x", age=600)
    (old / "late.json").write_text("{}")
    assert (
        infra_requeue.set_aside_interrupted(tmp_path / "x", TASK, started=started)
        is None
    )
    # the kernel's coarse file clock can stamp a file this process wrote a hair BEFORE `time.time()` read the start
    # (Runner g8730): still this process's
    lagging = _interrupted(tmp_path / "z", age=600)
    late = lagging / "late.json"
    late.write_text("{}")
    os.utime(late, (started - 0.01, started - 0.01))
    os.utime(lagging, (started - 0.01, started - 0.01))
    assert (
        infra_requeue.set_aside_interrupted(tmp_path / "z", TASK, started=started)
        is None
    )
    # no start known: never moved
    _interrupted(tmp_path / "y", age=600)
    assert (
        infra_requeue.set_aside_interrupted(tmp_path / "y", TASK, started=None) is None
    )
    assert infra_requeue.set_aside_interrupted(tmp_path / "y", TASK, started=started)


def test_a_grade_ended_as_hung_has_its_evaluation_set_aside_for_a_fresh_retry(tmp_path):
    """V2 (18 Nov 2026): a grade ended as hung (`AutoGrader._end_hung_grades`) wrote its evaluation in THIS process, so
    the start-time rule alone would leave it. It is set aside before `_fail`, whatever its age: the automatic retry
    binds a fresh evaluation and takes a fresh regrade generation (never the hung thread's op identities).
    """
    from carbon.challenge_validator import grade_sequencer

    evaluation = tmp_path / "auto-grade" / "artifacts" / (TASK + ".evaluation")
    evaluation.mkdir(parents=True)
    (evaluation / "evaluation-pack-binding.json").write_bytes(b'{"entry_id": "e1"}')
    base = tmp_path / "auto-grade" / "artifacts"
    assert retention._regrade_generation(base, TASK) == 0
    sequencer = grade_sequencer.Sequencer()
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.root = tmp_path
    failed = []

    def fail(sid, code):
        assert not evaluation.exists()  # set aside BEFORE the retry is armed
        failed.append((sid, code))

    grader._fail = fail
    with sequencer.task() as task:
        task.bind(TASK, "h:x")
        old, auto_grade.GRADE_HUNG_SECONDS = auto_grade.GRADE_HUNG_SECONDS, -1
        try:
            grader._end_hung_grades(sequencer)
        finally:
            auto_grade.GRADE_HUNG_SECONDS = old
    assert failed == [(TASK, auto_grade.GRADE_HUNG)]
    kept = tmp_path / "auto-grade" / "requeued" / (TASK + ".interrupted-1.evaluation")
    assert (kept / "evaluation-pack-binding.json").read_bytes() == b'{"entry_id": "e1"}'
    # the retry's regrade id differs
    assert retention._regrade_generation(base, TASK) == 1


def test_an_uncounted_regrade_moves_past_a_generation_that_started_and_never_finished(
    tmp_path,
):
    """Validator-2 (17 Nov): a crown repeat / averaging rebuild / king upkeep regrade marks its own start and finish.
    A generation that started and never finished (ANY of its ops failed or was interrupted, whatever that op's id: the
    pair children, subset repeats, single-call names never name the regrade id) is passed; a finished one is kept (its
    retained bytes are read back); a first regrade is generation 0."""

    def regrade_id_at(generation):
        return f"rtsk_{generation:064d}"

    def mark(generation, done):
        started, finished = retention._uncounted_marks(
            tmp_path, regrade_id_at(generation)
        )
        started.write_text("{}")
        if done:
            finished.write_text("{}")

    assert retention._uncounted_generation(tmp_path, regrade_id_at) == 0
    mark(0, done=True)
    assert (
        retention._uncounted_generation(tmp_path, regrade_id_at) == 0
    )  # finished: reused
    for path in tmp_path.iterdir():
        path.unlink()
    mark(0, done=False)  # an interrupted pair child, say
    assert retention._uncounted_generation(tmp_path, regrade_id_at) == 1
    mark(1, done=False)
    mark(2, done=True)
    assert retention._uncounted_generation(tmp_path, regrade_id_at) == 2


def test_a_candidates_own_failure_finishes_the_regrade_a_carbon_failure_does_not(
    tmp_path, monkeypatch
):
    """door-code review (17 Nov): a regrade that ends in the CANDIDATE's own failure is finished (the next call reuses
    its id and replays that settled outcome: a failed king is never re-rolled until it passes). Only a Carbon-side
    ending (or a replay) leaves it unfinished, so the next call takes a fresh generation.
    """
    from carbon.development_session.research_carrier import (
        MINER_FAILURE_SCHEMA,
        MinerProgramFailure,
    )

    def candidate(replayed=False):
        failure = MinerProgramFailure(
            {
                "schema": MINER_FAILURE_SCHEMA,
                "failure_code": WorkerCode.RUNTIME.value,
                "observation": "nonzero_exit",
            }
        )
        failure.replayed = replayed
        return failure

    def wrapped_candidate():
        try:
            raise candidate()
        except MinerProgramFailure as cause:
            raise retention.RetentionUnavailable("inference_pair_incomplete") from cause

    endings = {
        "returned": lambda: {"ok": True},
        "candidate": lambda: (_ for _ in ()).throw(candidate()),
        "candidate-wrapped": wrapped_candidate,
        "carbon": lambda: (_ for _ in ()).throw(WorkerFailure(WorkerCode.UNAVAILABLE)),
        "replay": lambda: (_ for _ in ()).throw(candidate(replayed=True)),
        "unavailable": lambda: (_ for _ in ()).throw(
            retention.RetentionUnavailable("regrade_case_bank_unavailable")
        ),
    }
    finished = {}
    for name, end in endings.items():
        path = tmp_path / f"{name}.regrade-done.json"

        def body(*args, _marks=None, _end=end, _path=path, **kwargs):
            _marks["finished"], _marks["regrade_id"] = _path, "rtsk_x"
            return _end()

        monkeypatch.setattr(retention, "_regrade_retained_entry", body)
        with contextlib.suppress(
            Exception
        ):  # every ending re-raises; only the mark is read
            retention.regrade_retained_entry("adapter", "entry")
        finished[name] = (
            json.loads(path.read_text())["outcome"] if path.exists() else None
        )
    assert finished == {
        "returned": "returned",
        "candidate": "candidate",
        "candidate-wrapped": "candidate",
        "carbon": None,
        "replay": None,
        "unavailable": None,
    }
