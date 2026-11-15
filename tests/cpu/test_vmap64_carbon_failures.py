"""A vmap-64 grade's Carbon failures go FAILED_INFRA through the REAL counted grade (review of 15 Nov, findings 1, 2, 5).

The counted bank grade of `test_graph_pool_counted_e2e` (real graph custody, regrade orchestration, ExamCap, dual
producer and score engine; synthetic worker outputs) runs under a receiver grader (`auto_grade.AutoGrader`) whose intake
calls the real `_counted_bank_grade`. Its Motor 1.5 pool fixture is registered as a vmap-64 version for the test only
(with a SYNTHETIC speed-match row), so the vmap-64 paths run exactly as for Motor 1.8:

- a timed answer beyond the speed-match tolerance (`speed_outputs_disagree`) ends FAILED (not a graded marker, not a
  candidate outcome, no speed FAIL): the slot released as FAILED_INFRA and the task's one automatic retry scheduled;
- graded bytes retained by another inference program (the switch: a retained regrade with no program record, or a
  different one) are refused as `graded_program_changed` before any pair, never compared, the slot released;
- an unset speed-match row stops the grade before any exam read or inference.

Synthetic fixtures only: no science, LIVE, crown or settlement claim.
"""

# ruff: noqa: F811 (the imported case fixture is received by tests)
from __future__ import annotations

import json

import pytest
import test_graph_pool_counted_e2e as e2e
from test_pool_dual_e2e import MOTOR, VERSION, case  # noqa: F401

from carbon.challenge_validator import auto_grade, auto_retry, speed_match
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import (
    bundle_construction_worker,
    direct_graph_construction_worker,
)

KEY = (MOTOR, VERSION)


def _as_vmap64(monkeypatch, tmp_path, row=None):
    """Register the fixture's version as a vmap-64 version, with a SYNTHETIC speed-match row (not the registered one)."""
    worker = direct_graph_construction_worker
    monkeypatch.setattr(worker, "JIT_INFERENCE_VERSIONS", frozenset({KEY}))
    monkeypatch.setattr(worker, "VMAP64_INFERENCE_VERSIONS", frozenset({KEY}))
    path = tmp_path / "speed_match_tolerance.json"
    path.write_text(
        json.dumps(
            {
                "schema": speed_match.SCHEMA,
                "rows": {f"{MOTOR} {VERSION}": row or {"rtol": 1e-9, "atol": 1e-9}},
            }
        )
    )
    monkeypatch.setattr(speed_match, "REGISTRY", path)


def _timed_off_by(monkeypatch, offset):
    """The fixture's timed single calls answer ``offset`` away from the graded rows."""
    inner = bundle_construction_worker._infer_state

    def shifted(ledger, **kwargs):
        result = inner(ledger, **kwargs)
        if "single_call" in kwargs:
            result.predictions = [
                [v + offset for v in row] for row in result.predictions
            ]
        return result

    monkeypatch.setattr(bundle_construction_worker, "_infer_state", shifted)


class _Intake:
    """The receiver intake's seam: `retain_result` is the real counted bank grade of the fixture's task."""

    def __init__(self, fixture):
        self.fixture = fixture
        real = fixture.adapter
        self.adapter = type(
            "GraderView",
            (),
            {
                "contract_digest": real.contract_digest,
                "ledger": real.ledger,
                "owner": staticmethod(real.owner),
                "discovery": real.discovery,
                "challenge_id": real.challenge_id,
                "challenge_version": real.challenge_version,
            },
        )()
        self.calls = 0

    def retain_result(self, submission_id, **_kwargs):
        self.calls += 1
        return retention._counted_bank_grade(
            self.fixture.adapter,
            submission_id,
            self.fixture.retained,
            artifact_directory=self.fixture.base,
            entry_directory=self.fixture.entries,
            pool_store=self.fixture.store,
            runner=object(),
        )


def _graded_by_the_grader(fixture, root):
    grader = auto_grade.AutoGrader(_Intake(fixture), root)
    outcome = grader.run_once()
    marker = json.loads(
        (root / "auto-grade" / "markers" / (e2e.TASK + ".json")).read_text()
    )
    return outcome, marker


def test_the_counted_vmap64_grade_records_its_program_and_grades(
    case, tmp_path, monkeypatch
):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    result = e2e._grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert fixture.calls == ["bank", "pair", "single"]
    (operations,) = fixture.base.glob("*.regrade-operation.json")
    recorded = json.loads(operations.read_bytes())["graded_program_sha256"]
    assert recorded == direct_graph_construction_worker.graded_program_sha256(*KEY)


def test_a_timed_disagreement_beyond_the_tolerance_is_failed_infra_never_a_grade(
    case, tmp_path, monkeypatch
):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    _timed_off_by(monkeypatch, 1e-6)  # far beyond 1e-9 + 1e-9 |b|
    outcome, marker = _graded_by_the_grader(fixture, tmp_path / "receiver")
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["state"] == "FAILED" and marker["code"] == speed_match.DISAGREE
    assert marker["entry_id"] is None
    # Carbon's: the slot is released (FAILED_INFRA), nothing graded or filed, and the task's one retry is scheduled
    assert e2e._cap_rows(fixture)[0][2] == "RELEASED"
    assert auto_retry.retryable(speed_match.DISAGREE) is True
    assert marker["next_step"] == "retry_scheduled"
    assert fixture.store.incumbent() is None
    assert not list(fixture.base.glob("*.evaluation/single-call.json"))
    assert not list(fixture.base.glob("*.evaluation/private-evaluation-binding.json"))


def test_within_the_tolerance_the_vmap64_grade_completes(case, tmp_path, monkeypatch):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    _timed_off_by(monkeypatch, 1e-12)  # not bit equal, well inside the tolerance
    result = e2e._grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert e2e._cap_rows(fixture)[0][2] == "COUNTED"


@pytest.mark.parametrize("before", ["unrecorded", "another_program"])
def test_graded_bytes_of_another_program_are_never_compared(
    case, tmp_path, monkeypatch, before
):
    """The switch: the graded pass was retained by one program; its retry runs under another."""
    if before == "another_program":
        _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    # the first attempt stops after the graded pass was retained (a Carbon fault in the pair): slot given back
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            retention,
            "_inference_pair_raw",
            lambda *a, **k: (_ for _ in ()).throw(
                retention.RetentionUnavailable("inference_pair_incomplete")
            ),
        )
        stopped = e2e._grade(fixture, counted=True)
    assert stopped["private_evaluation_reason"] == "inference_pair_incomplete"
    assert fixture.calls == ["bank"]
    # after the switch
    if before == "unrecorded":
        _as_vmap64(monkeypatch, tmp_path)  # retained before any program record existed
    else:
        monkeypatch.setattr(
            direct_graph_construction_worker,
            "graded_program_sha256",
            lambda *_key: "sha256:" + "f" * 64,
        )
    outcome, marker = _graded_by_the_grader(fixture, tmp_path / "receiver")
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["code"] == retention.GRADED_PROGRAM_CHANGED
    assert fixture.calls == [
        "bank"
    ]  # no pair, no single call, no new graded pass: nothing compared
    assert all(row[2] == "RELEASED" for row in e2e._cap_rows(fixture))
    assert fixture.store.incumbent() is None


def test_an_unset_tolerance_stops_the_grade_before_any_exam_read(
    case, tmp_path, monkeypatch
):
    _as_vmap64(monkeypatch, tmp_path, {"rtol": None, "atol": None})
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    read = []
    snapshot = fixture.adapter.discovery.evaluation_pack_snapshot

    class Watched:
        """The pack snapshot, recording every role read (the case bank is one)."""

        def __getattr__(self, name):
            return getattr(snapshot, name)

        def read_role(self, *args, **kwargs):
            read.append(args)
            return snapshot.read_role(*args, **kwargs)

    monkeypatch.setattr(
        fixture.adapter.discovery, "evaluation_pack_snapshot", Watched()
    )
    outcome, marker = _graded_by_the_grader(fixture, tmp_path / "receiver")
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["code"] == speed_match.UNREGISTERED
    assert read == [] and fixture.calls == []  # no case bank read, no inference
    assert all(row[2] == "RELEASED" for row in e2e._cap_rows(fixture))
    assert auto_retry.retryable(speed_match.UNREGISTERED) is False


def test_every_other_version_keeps_its_graded_marker_path(case, tmp_path, monkeypatch):
    """Not a vmap-64 version: no program record, no check; an ordinary Carbon gap stays an UNAVAILABLE evaluation."""
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    result = e2e._grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    (operations,) = fixture.base.glob("*.regrade-operation.json")
    assert "graded_program_sha256" not in json.loads(operations.read_bytes())
