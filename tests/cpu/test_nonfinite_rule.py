"""A proven non-finite answer on the new exams (owner G-LEAD-75, 24 Nov 2026).

Claims: only a version under the rule runs the split program, and every other version's text is unchanged; the second sentence
means a finite query with a non-finite answer, never a shape, dtype or kind error and never a non-finite input; the first one of
an allowance group's day is given back, every further one is COUNTED; nothing else changes its path; the miner's reply names the
closed code and never Carbon's fault.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_registry import exam_build
from carbon.challenge_validator import auto_grade, auto_retry, direct_intake, exam_cap
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import (
    bundle_construction_worker,
    case_procs,
    nonfinite_infer,
    physical_graph_adapter_v2,
    single_call_timing,
    trust_infer,
)
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

MOTOR = "electric-motor-magnetics"
KEY = (MOTOR, "1.9")
HOTKEY, OTHER = "5" + "1" * 47, "5" + "2" * 47
EXAM = "sha256:" + "e" * 64
DAY = exam_cap.DAY_EPOCHS


def _task(n):
    return "rtsk_" + f"{n:064x}"


def _failure(text=nonfinite_infer.RAISE):
    return WorkerFailure(
        WorkerCode.POLICY,
        private_diagnostic=b"Traceback (most recent call last):\nValueError: "
        + text.encode()
        + b"\n",
    )


# -- the program -------------------------------------------------------------------------------------------------------------------


def test_only_a_version_under_the_rule_runs_the_split_program():
    assert nonfinite_infer.applies(*KEY)
    for key in (
        (MOTOR, "1.8"),
        ("f02", "1.0"),
        ("f08-ribbed-bracket", "1.7"),
        ("x", "1.9"),
    ):
        assert not nonfinite_infer.applies(*key)
    for base in (
        bundle_construction_worker.INFER_PROGRAM,
        worker.PHYSICAL_V2_INFER_PROGRAM,
        worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM,
    ):
        assert nonfinite_infer.RAISE not in base
        assert nonfinite_infer.for_version(MOTOR, "1.8", base) == base
    for key in physical_graph_adapter_v2.SPECS:
        program = worker.v2_infer_query(*key)["program"]
        assert (nonfinite_infer.RAISE in program) is nonfinite_infer.applies(*key)


def test_the_split_form_derives_everywhere_the_program_does():
    for base in (
        worker.PHYSICAL_V2_INFER_PROGRAM,
        worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM,
    ):
        split = nonfinite_infer.program(base)
        compile(split, "program", "exec")
        assert split.count(nonfinite_infer.RAISE) == 1
        both = nonfinite_infer.trust(trust_infer.trust_program(split))
        compile(both, "program", "exec")
        assert both.count(nonfinite_infer.RAISE) == 2
        compile(single_call_timing.program(split), "program", "exec")
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    split = nonfinite_infer.program(case_procs.procs_program(compiled, 10**10, 648))
    assert case_procs.serial_program(split) == nonfinite_infer.program(compiled)
    for moved in ("", None, nonfinite_infer.program(compiled)):
        with pytest.raises(RuntimeError, match="anchor moved"):
            nonfinite_infer.program(moved)


def _run(result, inputs=None, shape=(2, 2), dtype="float64", width=None):
    """The program's own output check (both forms), run on ``result``."""
    inputs = np.zeros((2, 3)) if inputs is None else inputs
    control = {"expected_output_shape": list(shape), "expected_output_dtype": dtype}
    text = nonfinite_infer.program(bundle_construction_worker.INFER_PROGRAM)
    start = text.index("if (list(result.shape) != control")
    end = text.index("body = json.dumps(result.tolist()")
    exec(  # noqa: S102 - the program's own text
        text[start:end],
        {"result": result, "control": control, "np": np, "inputs": inputs},
    )


def test_the_second_sentence_means_a_finite_query_with_a_non_finite_answer():
    good = np.ones((2, 2))
    _run(good)
    for value in (np.nan, np.inf, -np.inf):
        bad = good.copy()
        bad[1, 0] = value
        with pytest.raises(ValueError) as caught:
            _run(bad)
        assert str(caught.value) == nonfinite_infer.RAISE
        # a non-finite input is Carbon's: today's sentence
        with pytest.raises(ValueError) as caught:
            _run(bad, inputs=np.full((2, 3), np.nan))
        assert str(caught.value) == nonfinite_infer.CONTRACT
        # a wrong shape, dtype or kind is today's sentence, non-finite or not
        for other in (
            bad[:1],
            bad.astype("float32"),
            bad.astype("complex128"),
            good[:1],
        ):
            with pytest.raises(ValueError) as caught:
                _run(other)
            assert str(caught.value) == nonfinite_infer.CONTRACT


def test_the_trust_split_is_cut_the_same_way():
    split = nonfinite_infer.trust(
        trust_infer.trust_program(
            nonfinite_infer.program(worker.PHYSICAL_V2_INFER_PROGRAM)
        )
    )
    start = split.index('trust_k = control.get("trust_outputs", 0)')
    end = split.index("result = result * decoder_sd + decoder_mu")
    control = {"trust_outputs": 1, "expected_output_shape": [2, 2]}

    def run(result, inputs):
        exec(  # noqa: S102 - the program's own text
            split[start:end],
            {"result": result, "control": control, "np": np, "inputs": inputs},
        )

    finite, nan = np.zeros((2, 3)), np.full((2, 3), np.nan)
    run(np.ones((2, 3)), finite)
    for result, inputs, words in (
        (nan, finite, nonfinite_infer.RAISE),
        (nan, nan, nonfinite_infer.CONTRACT),
        (np.ones((2, 2)), finite, nonfinite_infer.CONTRACT),
    ):
        with pytest.raises(ValueError) as caught:
            run(result, inputs)
        assert str(caught.value) == words


def test_every_existing_reader_still_matches_the_second_sentence():
    assert nonfinite_infer.RAISE.startswith(nonfinite_infer.CONTRACT)
    assert nonfinite_infer.CONTRACT.encode() == auto_retry._OUTPUT_CONTRACT_RAISE
    assert auto_retry.failure_code(_failure()) == auto_retry.OUTPUT_CONTRACT_DIFFERS


def test_only_the_workers_own_sentence_proves_it():
    assert nonfinite_infer.proven(_failure())
    replay = _failure()
    replay.replayed = True
    for other in (
        _failure(nonfinite_infer.CONTRACT),
        WorkerFailure(WorkerCode.POLICY),
        ValueError(nonfinite_infer.RAISE),
        replay,
    ):
        assert not nonfinite_infer.proven(other)


# -- the registered row --------------------------------------------------------------------------------------------------------


def test_a_build_row_may_name_the_rule_and_nothing_else(monkeypatch):
    assert exam_build.NONFINITE_RULES == (nonfinite_infer.RULE,)
    assert "nonfinite_rule" in exam_build._OPTIONAL
    rows = {("zz", "0.1"): {"nonfinite_rule": nonfinite_infer.RULE}, ("zz", "0.2"): {}}
    monkeypatch.setattr(exam_build, "block", lambda c, v: rows.get((c, v)))
    assert nonfinite_infer.applies("zz", "0.1")
    assert not nonfinite_infer.applies("zz", "0.2")
    assert not nonfinite_infer.applies("zz", "0.3")


# -- the count -------------------------------------------------------------------------------------------------------------------


def _cap(tmp_path):
    tmp_path.chmod(0o700)
    return exam_cap.ExamCap(AttemptLedger(tmp_path / "attempts.sqlite3"))


def _row(cap, n, *, hotkey=HOTKEY, epoch=100, state="RELEASED", status="UNAVAILABLE"):
    with cap.ledger._db() as db:
        db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, submission_id, "
            "state, status, reserved_ns, group_id) VALUES(?,?,?,?,'GRADED',?,?,?,?,?,?)",
            (
                hotkey,
                MOTOR,
                "1.9",
                EXAM,
                epoch,
                _task(n),
                state,
                status,
                10,
                exam_cap.group_of(hotkey),
            ),
        )


def _state(cap, n):
    with cap.ledger._db() as db:
        return db.execute(
            "SELECT state, status FROM exam_graded WHERE submission_id=?", (_task(n),)
        ).fetchone()


def _settle(cap, n, *, hotkey=HOTKEY, returned=(), since=0):
    return cap.settle_nonfinite(
        hotkey=hotkey,
        challenge_id=MOTOR,
        challenge_version="1.9",
        exam_key=EXAM,
        submission_id=_task(n),
        since_ns=since,
        returned=lambda other: other in {_task(i) for i in returned},
    )


def test_the_first_of_a_day_is_left_released_and_every_further_one_is_counted(tmp_path):
    cap = _cap(tmp_path)
    _row(cap, 1)
    assert _settle(cap, 1) == "FIRST"
    assert _state(cap, 1) == ("RELEASED", "UNAVAILABLE")
    with cap.ledger._db() as db:
        db.execute("UPDATE exam_graded SET status='FAILED_INFRA'")
    for n, epoch in ((2, 101), (3, 102)):
        _row(cap, n, epoch=epoch)
        assert _settle(cap, n, returned=(1,)) == "COUNTED"
        assert _state(cap, n) == ("COUNTED", "NONFINITE_OUTPUT")
    assert "NONFINITE_OUTPUT" in exam_cap.COUNTED


def test_a_carbon_failure_of_the_day_is_not_a_non_finite_one(tmp_path):
    cap = _cap(tmp_path)
    _row(cap, 1, status="FAILED_INFRA")
    _row(cap, 2, epoch=101)
    assert _settle(cap, 2, returned=()) == "FIRST"


@pytest.mark.parametrize(
    "gap, expected",
    [(DAY - 1, "COUNTED"), (DAY, "FIRST"), (1 - DAY, "COUNTED"), (-DAY, "FIRST")],
)
def test_the_day_is_the_daily_allowances_either_side(tmp_path, gap, expected):
    cap = _cap(tmp_path)
    _row(cap, 1, epoch=100 + gap, state="COUNTED", status="NONFINITE_OUTPUT")
    _row(cap, 2, epoch=100)
    assert _settle(cap, 2) == expected


def test_it_counts_per_hotkey_until_a_grouping_is_installed_then_per_group(tmp_path):
    cap = _cap(tmp_path)
    _row(cap, 1, state="COUNTED", status="NONFINITE_OUTPUT")
    _row(cap, 2, hotkey=OTHER, epoch=101)
    assert _settle(cap, 2, hotkey=OTHER) == "FIRST"
    exam_cap.install_grouping(lambda hotkey: "g:one")
    try:
        _row(cap, 3, epoch=102, state="COUNTED", status="NONFINITE_OUTPUT")
        _row(cap, 4, hotkey=OTHER, epoch=103)
        assert _settle(cap, 4, hotkey=OTHER) == "COUNTED"
    finally:
        exam_cap.install_grouping(None)


def test_only_this_attempts_own_unavailable_row_moves(tmp_path):
    cap = _cap(tmp_path)
    _row(cap, 9, state="COUNTED", status="NONFINITE_OUTPUT")
    for n, (state, status) in enumerate(
        (
            ("RELEASED", "FAILED_INFRA"),
            ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE"),
            ("RESERVED", None),
        ),
        start=1,
    ):
        _row(cap, n, state=state, status=status)
        assert _settle(cap, n) is None
        assert _state(cap, n) == (state, status)
    _row(cap, 5)
    assert _settle(cap, 5, since=11) is None  # reserved before this attempt
    assert _settle(cap, 6) is None  # no row
    assert _settle(cap, 5, since=10) == "COUNTED"


# -- the grader ------------------------------------------------------------------------------------------------------------------


def _grader(tmp_path, failure, version="1.9"):
    cap = _cap(tmp_path)
    tasks = [_task(1), _task(2)]
    adapter = SimpleNamespace(
        challenge_id=MOTOR,
        challenge_version=version,
        ledger=cap.ledger,
        owner=lambda submission_id: HOTKEY,
        discovery=SimpleNamespace(evaluation_pack_digest=EXAM),
    )
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=adapter)
    grader.root = tmp_path
    grader.markers = tmp_path / "auto-grade" / "markers"
    grader.markers.mkdir(parents=True)
    grader.pool_store = None
    del tasks
    return grader, cap


def test_the_first_is_given_back_with_no_retry_and_the_second_is_counted(
    tmp_path, monkeypatch
):
    logged = []
    from carbon.battery import intake as battery_intake

    monkeypatch.setattr(
        battery_intake, "log", lambda event, **facts: logged.append((event, facts))
    )
    grader, cap = _grader(tmp_path, _failure())
    _row(cap, 1)
    assert grader._nonfinite(_task(1), _failure(), 0) == "FAILED"
    marker = grader.marker(_task(1))
    assert (marker["state"], marker["code"], marker["next_step"]) == (
        "FAILED",
        auto_retry.NONFINITE_OUTPUT,
        "nonfinite_first_returned",
    )
    assert _state(cap, 1) == ("RELEASED", "FAILED_INFRA")
    assert not auto_retry._pending(tmp_path)  # never retried, never owed
    assert not (tmp_path / "auto-grade" / "requeued" / auto_retry.ALERT_NAME).exists()
    assert auto_retry.sweep_carbon_cut(tmp_path) == []
    _row(cap, 2, epoch=101)
    assert grader._nonfinite(_task(2), _failure(), 0) == "CANDIDATE_FAILED"
    marker = grader.marker(_task(2))
    assert (marker["state"], marker["code"]) == (
        "CANDIDATE_FAILED",
        auto_retry.NONFINITE_OUTPUT,
    )
    assert _state(cap, 2) == ("COUNTED", "NONFINITE_OUTPUT")
    assert [facts["settled"] for _, facts in logged] == ["FIRST", "COUNTED"]
    assert {facts["counted_per"] for _, facts in logged} == {
        "hotkey_no_grouping_installed"
    }


@pytest.mark.parametrize(
    "version, failure",
    [
        ("1.8", _failure()),
        ("1.9", _failure(nonfinite_infer.CONTRACT)),
        ("1.9", WorkerFailure(WorkerCode.DEADLINE)),
        ("1.9", ValueError("x")),
    ],
)
def test_anything_else_takes_its_usual_path(tmp_path, version, failure):
    grader, cap = _grader(tmp_path, failure, version)
    _row(cap, 1)
    assert grader._nonfinite(_task(1), failure, 0) is None
    assert grader.marker(_task(1)) is None
    assert _state(cap, 1) == ("RELEASED", "UNAVAILABLE")


def test_an_unreadable_registry_row_or_ledger_never_charges(tmp_path, monkeypatch):
    grader, cap = _grader(tmp_path, _failure())
    _row(cap, 1)

    def refused(*key):
        raise exam_build.ExamBuildRefused("x")

    with monkeypatch.context() as patch:
        patch.setattr(nonfinite_infer, "applies", refused)
        assert grader._nonfinite(_task(1), _failure(), 0) is None
    _row(cap, 2, epoch=101, state="COUNTED", status="NONFINITE_OUTPUT")

    def broken(self, **kwargs):
        raise OSError("x")

    with monkeypatch.context() as patch:
        patch.setattr(exam_cap.ExamCap, "settle_nonfinite", broken)
        assert grader._nonfinite(_task(1), _failure(), 0) == "FAILED"
    assert _state(cap, 1) == ("RELEASED", "FAILED_INFRA")


def test_the_grader_asks_after_the_wall_stop_and_before_the_usual_failure():
    from pathlib import Path

    text = Path(auto_grade.__file__).read_text(encoding="utf-8")
    ask = text.index("outcome = self._nonfinite(submission_id, failure, started_ns)")
    assert text.index("if _candidate_wall_stop(failure) and self._wall_counted(") < ask
    assert ask < text.index("else auto_retry.failure_code(failure)")


# -- the miner's reply -----------------------------------------------------------------------------------------------------------


def _reply(marker):
    intake = SimpleNamespace(
        grade_marker=lambda submission_id: marker,
        failure_v4=lambda *values: direct_intake.DirectRecipeIntake.failure_v4(
            None, *values
        ),
    )
    return direct_intake.DirectRecipeIntake._grade_state_v4(intake, HOTKEY, _task(1))


def test_the_miner_reads_the_closed_code_and_never_carbons_fault():
    assert direct_intake.NONFINITE_OUTPUT == auto_retry.NONFINITE_OUTPUT
    failure = {
        "child": "inference",
        "observation": None,
        "limit": None,
        "code": "nonfinite_output",
    }
    for state, expected in (
        ("FAILED", "NOT_GRADED"),
        ("CANDIDATE_FAILED", "CANDIDATE_FAILED"),
    ):
        marker = {"state": state, "code": auto_retry.NONFINITE_OUTPUT}
        assert _reply(marker) == (expected, failure)
    # a kit in the field reads it: the reply's shape does not change
    from carbon.development_session import direct_submission

    assert direct_submission._failure_v4(failure)
    assert direct_submission._failure_v8({**failure, "pass": None})
    # every other FAILED marker is Carbon's, as before
    assert _reply({"state": "FAILED", "code": auto_retry.OUTPUT_CONTRACT_DIFFERS}) == (
        "FAILED_INFRA",
        None,
    )
    assert json.dumps(failure)
    for words in auto_retry.NEXT_STEPS["nonfinite_first_returned"].split():
        assert "Carbon" not in words
