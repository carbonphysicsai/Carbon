"""A vmap-64 grade's Carbon failures go FAILED_INFRA through the REAL counted grade (review of 15 Nov, findings 1-3, 5).

The counted bank grade of `test_graph_pool_counted_e2e` (real graph custody, regrade orchestration, ExamCap, dual
producer and score engine; synthetic worker outputs) runs under a receiver grader (`auto_grade.AutoGrader`) whose intake
calls the real `_counted_bank_grade`. Its Motor 1.5 pool fixture is registered as a vmap-64 version for the test only
(with a SYNTHETIC speed-match row), so the vmap-64 paths run exactly as for Motor 1.8:

- a timed answer beyond the speed-match tolerance (`speed_outputs_disagree`) ends FAILED (not a graded marker, not a
  candidate outcome, no speed FAIL): the slot released as FAILED_INFRA and the task's one automatic retry scheduled;
  that retry REALLY times again (a fresh single-call identity, the graded bytes reused), and a second disagreement
  stays FAILED for the operator;
- graded bytes retained by another inference (no record, or a different program text, staged module or worker image)
  are refused as `graded_program_changed` before any pair, never compared, the slot released; its automatic retry
  (switch 5) takes a fresh regrade generation, so the graded pass runs again under the current program and grades; a
  same-everything retry grades;
- a vmap-64 grade off its sealed pack is refused, typed and never retried;
- an unset speed-match row stops the grade before any exam read or inference.

Synthetic fixtures only: no science, LIVE, crown or settlement claim.
"""

# ruff: noqa: F811 (the imported case fixture is received by tests)
from __future__ import annotations

import json
import os

import pytest
import test_graph_pool_counted_e2e as e2e
from test_pool_dual_e2e import MOTOR, VERSION, case  # noqa: F401

from carbon.challenge_validator import (
    auto_grade,
    auto_retry,
    exam_cap,
    infra_requeue,
    speed_match,
)
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import (
    bundle_construction_worker,
    direct_graph_construction_worker,
)
from carbon.reconstruction.worker.model import WorkerImageIdentity

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


def _timed(monkeypatch, offset, *, retried_offset=None):
    """The fixture's timed single calls answer ``offset`` away from the graded rows (``retried_offset`` on a re-queued
    attempt's own identity); returns the single-call identities seen."""
    inner = bundle_construction_worker._infer_state
    identities = []

    def shifted(ledger, **kwargs):
        result = inner(ledger, **kwargs)
        if "single_call" in kwargs:
            identities.append(kwargs["identity"])
            again = "-attempt" in kwargs["identity"]
            by = retried_offset if again and retried_offset is not None else offset
            result.predictions = [[v + by for v in row] for row in result.predictions]
        return result

    monkeypatch.setattr(bundle_construction_worker, "_infer_state", shifted)
    return identities


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

    def retain_result(self, submission_id, **_kwargs):
        return retention._counted_bank_grade(
            self.fixture.adapter,
            submission_id,
            self.fixture.retained,
            artifact_directory=self.fixture.base,
            entry_directory=self.fixture.entries,
            pool_store=self.fixture.store,
            runner=object(),
        )


def _marker_path(root):
    return root / "auto-grade" / "markers" / (e2e.TASK + ".json")


def _graded_by(grader, root):
    outcome = grader.run_once()
    return outcome, json.loads(_marker_path(root).read_text())


def _requeue(fixture, root):
    """What `infra_requeue.requeue` does for the task's one automatic retry: the ledger's re-queue row (attempt 2) and
    the marker moved aside, so the grader takes the task again."""
    assert exam_cap.ExamCap(fixture.adapter.ledger).mark_requeued(e2e.TASK) is True
    kept = root / "auto-grade" / "kept"
    kept.mkdir(exist_ok=True)
    os.replace(_marker_path(root), kept / (e2e.TASK + ".json"))


def test_the_counted_vmap64_grade_records_its_inference_and_grades(
    case, tmp_path, monkeypatch
):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    result = e2e._grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert fixture.calls == ["bank", "pair", "single"]
    (operations,) = fixture.base.glob("*.regrade-operation.json")
    recorded = json.loads(operations.read_bytes())["graded_inference_sha256"]
    provider = fixture.adapter._provider(e2e.OWNER)
    assert recorded == retention._graded_inference_digest(
        fixture.adapter,
        fixture.adapter.discovery._material,
        fixture.regrade.recipe,
        provider.inference_image,
    )


def test_a_timed_disagreement_is_failed_infra_and_its_one_retry_really_times_again(
    case, tmp_path, monkeypatch
):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    identities = _timed(
        monkeypatch, 1e-6, retried_offset=0.0
    )  # beyond 1e-9 + 1e-9 |b|, then agreeing
    root = tmp_path / "receiver"
    grader = auto_grade.AutoGrader(_Intake(fixture), root)
    outcome, marker = _graded_by(grader, root)
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["state"] == "FAILED" and marker["code"] == speed_match.DISAGREE
    assert marker["entry_id"] is None
    # Carbon's: the slot is released (FAILED_INFRA), nothing graded or filed, the task's one retry scheduled
    assert e2e._cap_rows(fixture)[0][2] == "RELEASED"
    assert marker["next_step"] == "retry_scheduled"
    assert fixture.store.incumbent() is None
    assert not list(fixture.base.glob("*.evaluation/single-call.json"))
    assert not list(fixture.base.glob("*.evaluation/private-evaluation-binding.json"))
    # the retry: the graded bytes and the pair are reused, the single calls run anew under their own identity
    _requeue(fixture, root)
    outcome, marker = _graded_by(grader, root)
    assert outcome == (e2e.TASK, "GRADED"), marker
    assert fixture.calls == ["bank", "pair", "single", "single"]
    # its own identity (A20's in-lane speed stage names each run `speed-lane-<name>[-attempt2]-r<k>`)
    assert len(identities) == 2 and identities[1] != identities[0]
    assert "-attempt2" in identities[1] and "-attempt2" not in identities[0]
    assert e2e._cap_rows(fixture)[-1][2] == "COUNTED"


def test_a_second_disagreement_stays_failed_for_the_operator(
    case, tmp_path, monkeypatch
):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    identities = _timed(monkeypatch, 1e-6)  # the retry disagrees too
    root = tmp_path / "receiver"
    grader = auto_grade.AutoGrader(_Intake(fixture), root)
    assert _graded_by(grader, root)[1]["next_step"] == "retry_scheduled"
    _requeue(fixture, root)
    outcome, marker = _graded_by(grader, root)
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["code"] == speed_match.DISAGREE
    assert (
        marker["next_step"] == "slot_returned"
    )  # the one retry is used: no second automatic one
    assert len(identities) == 2 and identities[0] != identities[1]
    assert e2e._cap_rows(fixture)[-1][2] == "RELEASED"
    assert fixture.store.incumbent() is None


def test_within_the_tolerance_the_vmap64_grade_completes(case, tmp_path, monkeypatch):
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    _timed(monkeypatch, 1e-12)  # not bit equal, well inside the tolerance
    result = e2e._grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert e2e._cap_rows(fixture)[0][2] == "COUNTED"


def _changed_query(monkeypatch, change):
    """After the switch: the door's inference query for the version differs in ``change``."""
    worker = direct_graph_construction_worker
    original = worker.v2_infer_query

    def switched(challenge_id, version):
        query = dict(original(challenge_id, version))
        if change == "program_text":
            query["program"] = query["program"] + "\n# the door's program changed\n"
        else:
            files = dict(query["staged_files"])
            name = min(files)
            files[name] = files[name] + b"\n# a staged module changed\n"
            query["staged_files"] = files
        return query

    monkeypatch.setattr(worker, "v2_infer_query", switched)


@pytest.mark.parametrize(
    "switch", ["unrecorded", "program_text", "staged_file", "image_id", "same"]
)
def test_graded_bytes_of_another_inference_are_never_compared(
    case, tmp_path, monkeypatch, switch
):
    """The switch: the graded pass was retained by one inference; its retry runs under another."""
    if switch != "unrecorded":
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
    if switch == "unrecorded":
        _as_vmap64(monkeypatch, tmp_path)  # retained before any record existed
    elif switch in ("program_text", "staged_file"):
        _changed_query(monkeypatch, switch)
    elif switch == "image_id":
        # (a provider image that moved is refused earlier, regrade_construction_parent_differs; here the regrade's
        # own chosen image differs, so only the inference digest can see it)
        moved = WorkerImageIdentity(*(("sha256:" + "e" * 64,) * 8))
        monkeypatch.setattr(retention, "_regrade_inference_image", lambda *a: moved)
    root = tmp_path / "receiver"
    outcome, marker = _graded_by(auto_grade.AutoGrader(_Intake(fixture), root), root)
    if switch == "same":
        assert outcome == (e2e.TASK, "GRADED"), marker
        assert fixture.calls == ["bank", "pair", "single"]
        return
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["code"] == retention.GRADED_PROGRAM_CHANGED
    assert marker["next_step"] == "retry_scheduled"
    assert auto_retry.retryable(retention.GRADED_PROGRAM_CHANGED) is True
    assert fixture.calls == [
        "bank"
    ]  # no pair, no single call, no new graded pass: nothing compared
    assert all(row[2] == "RELEASED" for row in e2e._cap_rows(fixture))
    assert fixture.store.incumbent() is None
    # the retry, as `infra_requeue.requeue` hands it back: the `.regenerate` mark beside the grader's artifacts, so the
    # regrade takes generation 1 and its graded pass runs afresh under the current program, then pair and single calls
    kept = fixture.base.parent / "requeued"
    assert infra_requeue._mark_regenerate(
        {"marker": _marker_path(root), "kept_marker": kept / "kept-marker.json"},
        e2e.TASK,
        1,
    )
    assert retention._regrade_generation(fixture.base, e2e.TASK) == 1
    _requeue(fixture, root)
    outcome, marker = _graded_by(auto_grade.AutoGrader(_Intake(fixture), root), root)
    assert fixture.calls == ["bank", "bank", "pair", "single"]
    rows = e2e._cap_rows(fixture)
    if switch == "image_id":
        # a moved worker image: the fresh graded pass runs, then the grade cannot be computed on that image: Carbon's
        # version-wide gap (V2-L2-RETENTION-20261120), raised to the grader as FAILED_INFRA (not retried), the slot
        # released: uncharged, as for any image move; never compared, never charged
        assert outcome == (e2e.TASK, "FAILED"), marker
        assert marker["code"] == "leg_minimum_platform_mismatch", marker
        assert marker["next_step"] == "resubmit_after_fix", marker
        assert auto_retry.retryable(marker["code"]) is False
        assert all(row[2] == "RELEASED" for row in rows), (marker, rows)
    else:
        assert outcome == (e2e.TASK, "GRADED"), marker
        assert rows[-1][2] == "COUNTED", (marker, rows)


def test_a_vmap64_grade_off_its_sealed_pack_is_refused_typed_and_not_retried(
    case, tmp_path, monkeypatch
):
    """Motor 1.8 is only graded on its sealed pool pack; the task's own inference (no regrade) is never compared."""
    _as_vmap64(monkeypatch, tmp_path)
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    with pytest.raises(
        retention.RetentionUnavailable, match=retention.VMAP64_NEEDS_SEALED_PACK
    ):
        retention._retain_selected_pack_evaluation(
            fixture.adapter,
            e2e.TASK,
            fixture.retained,
            fixture.artifacts,
            fixture.worker,
            None,
            pool_store=fixture.store,
        )
    assert fixture.calls == []
    assert all(row[2] == "RELEASED" for row in e2e._cap_rows(fixture))
    assert auto_retry.retryable(retention.VMAP64_NEEDS_SEALED_PACK) is False


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
    root = tmp_path / "receiver"
    outcome, marker = _graded_by(auto_grade.AutoGrader(_Intake(fixture), root), root)
    assert outcome == (e2e.TASK, "FAILED")
    assert marker["code"] == speed_match.UNREGISTERED
    assert read == [] and fixture.calls == []  # no case bank read, no inference
    assert all(row[2] == "RELEASED" for row in e2e._cap_rows(fixture))
    assert auto_retry.retryable(speed_match.UNREGISTERED) is False


def test_every_other_version_keeps_its_graded_marker_path(case, tmp_path, monkeypatch):
    """Not a vmap-64 version: no inference record, no check; it grades as before."""
    fixture = e2e._setup(case, tmp_path, monkeypatch)
    result = e2e._grade(fixture, counted=True)
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    (operations,) = fixture.base.glob("*.regrade-operation.json")
    assert "graded_inference_sha256" not in json.loads(operations.read_bytes())


@pytest.fixture(autouse=True)
def _vmap64_machinery_opted_in(monkeypatch):
    """Motor 1.8 is NOT a vmap-64 version since the owner's 116 rollback to A9 behaviour (Sun 15 Nov 2026; it grades
    with the per-case compiled program, tests/cpu/test_motor18_rollback_program.py). These tests exercise the dormant
    vmap-64 machinery with Motor 1.8 opted back in."""
    from carbon.development_session import direct_graph_construction_worker

    monkeypatch.setattr(
        direct_graph_construction_worker,
        "VMAP64_INFERENCE_VERSIONS",
        frozenset({("electric-motor-magnetics", "1.8")}),
    )
