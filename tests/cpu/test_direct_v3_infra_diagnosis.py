"""A FAILED_INFRA direct task always says where and why (Lead, 2026-10-24: a
FAILED_INFRA with no evidence is itself a bug): the failed stage, a closed
reason code and a sanitized tail, retained for the operator beside the task and
never returned on a public surface. Every path that settles FAILED_INFRA must
supply one: `_transition` refuses the state without it."""

from __future__ import annotations

import json

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.development_session import bundle_construction_worker, infra_diagnosis
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

FAILED = research.DirectTaskStateV3.FAILED_INFRA


BUILD_FAILED = ("FAILED_INFRA", None)


def _run_failing(tmp_path, monkeypatch, error, *, child_states=BUILD_FAILED):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    started = tasks.start_research_task(request)
    if child_states is not None:
        build, inference = tasks._children(started.task.task_id)
        states = {build: child_states[0], inference: child_states[1]}
        monkeypatch.setattr(
            tasks.ledger,
            "operation_state",
            lambda identity, *, owner: (
                states.get(identity) if owner == tasks.owner else None
            ),
        )

    def failing(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        bundle_construction_worker, "reconstruct_and_infer_public", failing
    )
    view = tasks.run_queued_task(started.task.task_id)
    return tasks, started.task.task_id, view, provider


def test_a_worker_failure_records_its_code_and_a_sanitized_tail(tmp_path, monkeypatch):
    digest_like = "ab" * 32
    error = WorkerFailure(
        WorkerCode.RUNTIME,
        private_diagnostic=(
            f"Traceback\nModuleNotFoundError: no module 'x'\nstate {digest_like}\x00\x1b[31m"
        ).encode(),
    )
    tasks, task_id, view, _provider = _run_failing(tmp_path, monkeypatch, error)
    try:
        assert view.state is FAILED
        record = tasks.private_infra_diagnosis(task_id)
        assert record["schema"] == infra_diagnosis.SCHEMA
        assert record["failed_stage"] == "build"
        assert record["reason_code"] == WorkerCode.RUNTIME.value
        assert "ModuleNotFoundError" in record["tail"]
        assert digest_like not in record["tail"] and "<hex>" in record["tail"]
        assert "\x00" not in record["tail"] and "\x1b" not in record["tail"]
        assert record["official_eligible"] is False
        # The public receipt keeps its closed class, and no public surface
        # returns the tail.
        assert (
            view.terminal_receipt.infrastructure_failure_class
            is research.InfrastructureFailureClass.INTERNAL
        )
        assert tasks.public_result(view) is None
        assert "ModuleNotFoundError" not in json.dumps(
            tasks.public_result(view), default=str
        )
    finally:
        tasks.close()


def test_an_unresolved_task_records_where_the_exception_was_raised(
    tmp_path, monkeypatch
):
    """The proof-run failure: an exception outside any worker settles the task
    UNRESOLVED (shown to a miner like infrastructure) with nothing to read.
    It now names the class, the step and the traceback tail."""

    def culprit():
        raise AttributeError("'NoneType' object has no attribute 'bundle'")

    try:
        culprit()
    except AttributeError as raised:
        error = raised
    tasks, task_id, view, _provider = _run_failing(
        tmp_path, monkeypatch, error, child_states=(None, None)
    )
    try:
        assert view.state is research.DirectTaskStateV3.UNRESOLVED
        record = tasks.private_infra_diagnosis(task_id)
        assert record["failed_stage"] == "orchestration"
        assert record["reason_code"] == "unclassified_internal"
        assert record["raised_at"].endswith(":culprit")
        assert "test_direct_v3_infra_diagnosis.py" in record["raised_at"]
        assert "AttributeError" in record["traceback"]
        assert "culprit" in record["traceback"]
        assert "AttributeError" in record["tail"]
        assert tasks.public_result(view) is None
    finally:
        tasks.close()


def test_a_refused_resource_policy_check_is_diagnosed_not_blank(tmp_path, monkeypatch):
    """The 2026-10-24 proof-run branch exactly: `RecipeRefused` from the
    resource-policy check, no failed child, not provisioning."""
    from carbon.development_session.construction_recipe import RecipeRefused

    try:
        raise RecipeRefused("construction_resource_policy_unserved")
    except RecipeRefused as raised:
        error = raised
    tasks, task_id, view, _provider = _run_failing(
        tmp_path, monkeypatch, error, child_states=(None, None)
    )
    try:
        assert view.state is research.DirectTaskStateV3.UNRESOLVED
        record = tasks.private_infra_diagnosis(task_id)
        assert record is not None
        assert record["failed_stage"] == "orchestration"
        assert record["child_states"] == [None, None]
        assert "RecipeRefused" in record["tail"]
        assert "construction_resource_policy_unserved" in record["traceback"]
        assert record["raised_at"].endswith(
            ":test_a_refused_resource_policy_check_is_diagnosed_not_blank"
        )
    finally:
        tasks.close()


def test_a_failed_build_child_names_the_build_stage(tmp_path, monkeypatch):
    tasks, task_id, view, _provider = _run_failing(
        tmp_path, monkeypatch, OSError("host doctor failed")
    )
    try:
        assert view.state is FAILED
        record = tasks.private_infra_diagnosis(task_id)
        assert record["failed_stage"] == "build"
        assert record["reason_code"] == "host_io_error"
        assert record["child_states"] == ["FAILED_INFRA", None]
        assert "OSError" in record["tail"] and "OSError" in record["traceback"]
        assert record["raised_at"].endswith(":failing")
    finally:
        tasks.close()


def test_every_infrastructure_failure_has_a_stage_and_a_reason(tmp_path, monkeypatch):
    for index, (error, reason) in enumerate(
        (
            (WorkerFailure(WorkerCode.UNAVAILABLE), WorkerCode.UNAVAILABLE.value),
            (TimeoutError("late"), "timeout"),
            (ValueError("x"), "custody_or_state_invalid"),
            (RuntimeError("y"), "unclassified_internal"),
        )
    ):
        directory = tmp_path / f"case{index}"
        directory.mkdir()
        tasks, task_id, view, _provider = _run_failing(directory, monkeypatch, error)
        try:
            assert view.state is FAILED
            record = tasks.private_infra_diagnosis(task_id)
            assert record["reason_code"] == reason
            assert record["failed_stage"] in infra_diagnosis.STAGES
            assert record["reason_code"] in infra_diagnosis.REASONS or (
                record["reason_code"].startswith("reconstruction.worker.")
            )
        finally:
            tasks.close()


def test_infrastructure_failure_cannot_be_settled_without_a_diagnosis(
    tmp_path, monkeypatch
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        view = tasks._views[started.task.task_id.value]
        receipt = tasks._receipt(
            view,
            FAILED,
            failure=research.InfrastructureFailureClass.INTERNAL,
        )
        with pytest.raises(ValueError, match="requires a diagnosis"):
            tasks._transition(view, FAILED, receipt=receipt)
        with pytest.raises(ValueError, match="malformed"):
            tasks._transition(
                view,
                FAILED,
                receipt=receipt,
                infra={"failed_stage": "nowhere", "reason_code": "x", "tail": ""},
            )
        with pytest.raises(ValueError, match="belongs to an infrastructure"):
            tasks._transition(
                view,
                research.DirectTaskStateV3.RUNNING,
                infra={"failed_stage": "build", "reason_code": "timeout"},
            )
    finally:
        tasks.close()


def test_the_diagnosis_survives_a_restart_and_checks_its_receipt(tmp_path, monkeypatch):
    tasks, task_id, _view, provider = _run_failing(
        tmp_path, monkeypatch, OSError("disk gone")
    )
    tasks.close()
    reopened = provider()
    try:
        record = reopened.private_infra_diagnosis(task_id)
        assert record["reason_code"] == "host_io_error"
        with reopened._db() as db:
            db.execute(
                "UPDATE direct_infra_diagnosis SET body=?",
                (
                    json.dumps(
                        {**record, "receipt_digest": "sha256:" + "0" * 64}
                    ).encode(),
                ),
            )
        with pytest.raises(ValueError, match="custody differs"):
            reopened.private_infra_diagnosis(task_id)
    finally:
        reopened.close()


def test_the_sanitizer_bounds_masks_and_cleans():
    assert infra_diagnosis.sanitize_tail(b"a\x00b\x1b[0mc\xff") == "a?b?[0mc?"
    long = "ab " * 2000
    assert len(infra_diagnosis.sanitize_tail(long)) == infra_diagnosis.TAIL_CHARS
    assert infra_diagnosis.sanitize_tail("k=" + "f" * 64) == "k=<hex>"
    assert "<b64>" in infra_diagnosis.sanitize_tail("tok " + "Ab1+" * 12)
    assert infra_diagnosis.sanitize_tail("line1\nline2") == "line1\nline2"


def test_stage_and_diagnosis_are_closed():
    assert infra_diagnosis.stage_of(["FAILED_INFRA", None]) == "build"
    assert infra_diagnosis.stage_of([None, "FAILED_INFRA"]) == "inference"
    assert infra_diagnosis.stage_of([None, None, "FAILED_INFRA"]) == "prep"
    assert infra_diagnosis.stage_of([None, None]) == "orchestration"
    assert infra_diagnosis.stage_of(["FAILED_INFRA", None], True) == "provision"
    infra_diagnosis.diagnosis("build", "timeout", "t", ["FAILED_INFRA", None])
    for bad in (
        ("nowhere", "timeout"),
        ("build", "free text reason"),
        ("build", ""),
    ):
        with pytest.raises(ValueError):
            infra_diagnosis.diagnosis(*bad)
    with pytest.raises(ValueError):
        infra_diagnosis.diagnosis("build", "timeout", "x" * 2049)
