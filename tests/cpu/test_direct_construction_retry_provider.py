"""Normal retries preserve failed originals and admit one fresh bounded task.

Real provider/SQLite admission is exercised here. Image verification and the
read-only auxiliary-helper observation use trusted infrastructure fixtures;
these tests execute no participant model or Docker workload.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.development_session.research_tasks import DIRECT_RETRY_KEY_PREFIX
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure


@pytest.fixture
def uv_observation(monkeypatch):
    calls = []
    response = {"stdout": b"", "failure": None}

    class Docker:
        def run(self, arguments, *, timeout):
            assert arguments == [
                "ps",
                "-aq",
                "--filter",
                "label=org.carbonphysicsai.overlay-uv-intent",
            ]
            assert timeout == 10
            calls.append(tuple(arguments))
            if response["failure"] is not None:
                raise response["failure"]
            return SimpleNamespace(stdout=response["stdout"])

    monkeypatch.setattr("carbon.reconstruction.worker.docker_runtime.DockerCLI", Docker)
    return calls, response


def _failed(tasks, request, monkeypatch, *, measure_query=False):
    started = tasks.start_research_task(request, measure_query=measure_query).task

    def absent(_request):
        raise FileNotFoundError("synthetic infrastructure dependency unavailable")

    # Exercise the maintained pre-child failure path and its real receipt.
    with monkeypatch.context() as changed:
        changed.setattr(tasks, "_resolved_image", absent)
        failed = tasks.run_queued_task(started.task_id)
    assert failed.state is research.DirectTaskStateV3.FAILED_INFRA
    assert failed.terminal_receipt.infrastructure_failure_class is (
        research.InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE
    )
    return failed


def _request(request, predecessor):
    return replace(
        request,
        idempotency_key=DIRECT_RETRY_KEY_PREFIX + predecessor.task_id.value,
    )


def _row(tasks, identity):
    with tasks._db() as db:
        return db.execute(
            "SELECT request,view,cancellation FROM direct_tasks WHERE id=?",
            (identity.value,),
        ).fetchone()


def _refused(code, operation):
    with pytest.raises(research.ResearchTaskProviderError) as caught:
        operation()
    assert caught.value.code is code


@pytest.mark.parametrize("measure_query", [False, True])
def test_retry_is_one_durable_fresh_child_and_preserves_failed_bytes(
    tmp_path, monkeypatch, uv_observation, measure_query
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch, measure_query=measure_query)
        original = _row(tasks, parent.task_id)
        retry = _request(request, parent)
        first = tasks.retry_research_task(
            retry, predecessor_id=parent.task_id, measure_query=measure_query
        )
        assert first.created
        assert first.task.task_id != parent.task_id
        assert first.task.state is research.DirectTaskStateV3.QUEUED
        assert first.task.immutable_bindings == parent.immutable_bindings
        assert tasks._requests[first.task.task_id.value] == retry
        assert (first.task.task_id.value in tasks._measured_tasks) is measure_query
        assert _row(tasks, parent.task_id) == original
        assert (
            tasks.get_research_result(
                research.DirectGetTaskRequestV3(request.challenge_key, parent.task_id)
            ).task
            == parent
        )
        # Replays need neither an empty helper observation nor live images.
        uv_observation[1]["stdout"] = b"synthetic-current-helper\n"
        monkeypatch.setattr(
            tasks, "_verify_images", lambda: pytest.fail("replay verified images")
        )
        again = tasks.retry_research_task(
            retry, predecessor_id=parent.task_id, measure_query=measure_query
        )
        assert not again.created and again.task == first.task
        assert len(uv_observation[0]) == 1
    finally:
        tasks.close()
    reopened = provider()
    try:
        resumed = reopened.retry_research_task(
            retry, predecessor_id=parent.task_id, measure_query=measure_query
        )
        assert not resumed.created
        assert resumed.task.task_id == first.task.task_id
        assert (resumed.task.task_id.value in reopened._measured_tasks) is measure_query
        assert _row(reopened, parent.task_id) == original
        assert len(reopened._views) == 2
        assert len(uv_observation[0]) == 1
    finally:
        reopened.close()


def test_concurrent_retry_calls_share_one_child(tmp_path, monkeypatch, uv_observation):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        original = _row(tasks, parent.task_id)
        retry = _request(request, parent)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    tasks.retry_research_task, retry, predecessor_id=parent.task_id
                )
                for _ in range(2)
            ]
            outcomes = [future.result() for future in futures]
        assert sum(outcome.created for outcome in outcomes) == 1
        assert outcomes[0].task.task_id == outcomes[1].task.task_id
        assert len(tasks._views) == 2 and len(uv_observation[0]) == 1
        assert _row(tasks, parent.task_id) == original
    finally:
        tasks.close()


def test_reserved_retry_key_cannot_bypass_predecessor_validation(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        queued = tasks.start_research_task(request).task
        original = _row(tasks, queued.task_id)
        _refused(
            research.ResearchServiceErrorCode.INVALID_TASK_TRANSITION,
            lambda: tasks.start_research_task(_request(request, queued)),
        )
        assert _row(tasks, queued.task_id) == original
        assert len(tasks._views) == 1 and uv_observation[0] == []
    finally:
        tasks.close()


def test_retry_requires_a_task_retained_by_this_owner(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, _ = _fixture(tmp_path / "first", monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
    finally:
        tasks.close()
    _, other_provider, _ = _fixture(tmp_path / "other", monkeypatch)
    other = other_provider("another-owner")
    try:
        _refused(
            research.ResearchServiceErrorCode.TASK_NOT_FOUND,
            lambda: other.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert not other._views and uv_observation[0] == []
    finally:
        other.close()


@pytest.mark.parametrize(
    "state",
    [
        research.DirectTaskStateV3.QUEUED,
        research.DirectTaskStateV3.RUNNING,
        research.DirectTaskStateV3.CANCEL_REQUESTED,
        research.DirectTaskStateV3.SUCCEEDED,
        research.DirectTaskStateV3.REFUSED,
        research.DirectTaskStateV3.UNRESOLVED,
        research.DirectTaskStateV3.CANCELLED,
    ],
)
def test_only_infrastructure_terminal_state_can_be_retried(
    tmp_path, monkeypatch, uv_observation, state
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = tasks.start_research_task(request).task
        if state in (
            research.DirectTaskStateV3.RUNNING,
            research.DirectTaskStateV3.CANCEL_REQUESTED,
        ):
            parent = tasks._transition(parent, state)
        elif state is not research.DirectTaskStateV3.QUEUED:
            receipt = research.DirectTaskReceiptV3(
                parent.task_id,
                state,
                parent.immutable_bindings,
                (
                    "sha256:" + "a" * 64
                    if state is research.DirectTaskStateV3.SUCCEEDED
                    else None
                ),
                (
                    "sha256:" + "b" * 64
                    if state is research.DirectTaskStateV3.SUCCEEDED
                    else None
                ),
                None,
                (
                    "synthetic-non-infra"
                    if state
                    in (
                        research.DirectTaskStateV3.REFUSED,
                        research.DirectTaskStateV3.UNRESOLVED,
                    )
                    else None
                ),
                parent.updated_at_micros,
                tasks._LIMITATIONS,
            )
            parent = tasks._transition(parent, state, receipt=receipt)
        original = _row(tasks, parent.task_id)
        _refused(
            research.ResearchServiceErrorCode.INVALID_TASK_TRANSITION,
            lambda: tasks.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert len(tasks._views) == 1 and uv_observation[0] == []
        assert _row(tasks, parent.task_id) == original
    finally:
        tasks.close()


@pytest.mark.parametrize(
    "field",
    [
        "public_train_digest",
        "interface_digest",
        "resource_policy_digest",
        "manifest_digest",
    ],
)
def test_retry_refuses_changed_registered_material(
    tmp_path, monkeypatch, uv_observation, field
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        retry = replace(_request(request, parent), **{field: "sha256:" + "0" * 64})
        _refused(
            research.ResearchServiceErrorCode.REFERENCE_MISMATCH,
            lambda: tasks.retry_research_task(retry, predecessor_id=parent.task_id),
        )
        assert len(tasks._views) == 1 and uv_observation[0] == []
    finally:
        tasks.close()


def test_retry_refuses_changed_recipe_measurement_pack_or_derived_key(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        retry = _request(request, parent)
        recipe = deepcopy(retry.recipe)
        recipe["procedure"]["configuration"]["different"] = True
        _refused(
            research.ResearchServiceErrorCode.REFERENCE_MISMATCH,
            lambda: tasks.retry_research_task(
                replace(retry, recipe=recipe), predecessor_id=parent.task_id
            ),
        )
        _refused(
            research.ResearchServiceErrorCode.REFERENCE_MISMATCH,
            lambda: tasks.retry_research_task(
                retry, predecessor_id=parent.task_id, measure_query=True
            ),
        )
        _refused(
            research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT,
            lambda: tasks.retry_research_task(
                replace(retry, idempotency_key="arbitrary-new-attempt"),
                predecessor_id=parent.task_id,
            ),
        )
        monkeypatch.setattr(discovery, "evaluation_pack_digest", "sha256:" + "1" * 64)
        _refused(
            research.ResearchServiceErrorCode.REFERENCE_MISMATCH,
            lambda: tasks.retry_research_task(retry, predecessor_id=parent.task_id),
        )
        assert len(tasks._views) == 1 and uv_observation[0] == []
    finally:
        tasks.close()


@pytest.mark.parametrize("state", ["RESERVED", "HELD", "UNKNOWN"])
def test_retry_refuses_unsettled_main_child_without_reconciliation(
    tmp_path, monkeypatch, uv_observation, state
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        build = tasks._children(parent.task_id)[0]
        monkeypatch.setattr(
            tasks.ledger,
            "operation_state",
            lambda identity, *, owner: state if identity == build else None,
        )
        _refused(
            research.ResearchServiceErrorCode.INVALID_TASK_TRANSITION,
            lambda: tasks.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert len(tasks._views) == 1 and uv_observation[0] == []
    finally:
        tasks.close()


@pytest.mark.parametrize(
    "state", ["SUCCEEDED", "FAILED_INFRA", "FAILED_MINER", "CANCELLED"]
)
def test_retry_accepts_closed_main_child_after_infrastructure_failure(
    tmp_path, monkeypatch, uv_observation, state
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        original = _row(tasks, parent.task_id)
        build = tasks._children(parent.task_id)[0]
        monkeypatch.setattr(
            tasks.ledger,
            "operation_state",
            lambda identity, *, owner: state if identity == build else None,
        )
        result = tasks.retry_research_task(
            _request(request, parent), predecessor_id=parent.task_id
        )
        assert result.created and result.task.state is research.DirectTaskStateV3.QUEUED
        assert _row(tasks, parent.task_id) == original
        assert len(tasks._views) == 2 and len(uv_observation[0]) == 1
    finally:
        tasks.close()


def test_fresh_retry_still_requires_normal_image_verification(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        original = _row(tasks, parent.task_id)

        def unavailable():
            raise WorkerFailure(WorkerCode.UNAVAILABLE)

        monkeypatch.setattr(tasks, "_verify_images", unavailable)
        _refused(
            research.ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE,
            lambda: tasks.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert _row(tasks, parent.task_id) == original
        assert len(tasks._views) == 1 and len(uv_observation[0]) == 1
    finally:
        tasks.close()


@pytest.mark.parametrize("stdout", [None, "", {}, []])
def test_unknown_auxiliary_observation_is_not_absence(
    tmp_path, monkeypatch, uv_observation, stdout
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        uv_observation[1]["stdout"] = stdout
        _refused(
            research.ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE,
            lambda: tasks.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert len(tasks._views) == 1 and len(uv_observation[0]) == 1
    finally:
        tasks.close()


@pytest.mark.parametrize(
    "failure",
    [
        None,
        OSError("synthetic-daemon"),
        TimeoutError("synthetic-timeout"),
        WorkerFailure(WorkerCode.UNAVAILABLE),
    ],
)
def test_bundle_retry_requires_observed_auxiliary_uv_absence(
    tmp_path, monkeypatch, uv_observation, failure
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        uv_observation[1].update(stdout=b"synthetic-stopped-helper\n", failure=failure)
        code = (
            research.ResearchServiceErrorCode.INVALID_TASK_TRANSITION
            if failure is None
            else research.ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
        )
        _refused(
            code,
            lambda: tasks.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert len(tasks._views) == 1 and len(uv_observation[0]) == 1
    finally:
        tasks.close()


def test_retry_chains_only_failed_children_and_preserves_ancestors(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        original = _row(tasks, parent.task_id)
        retry = _request(request, parent)
        child = tasks.retry_research_task(retry, predecessor_id=parent.task_id).task
        _refused(
            research.ResearchServiceErrorCode.INVALID_TASK_TRANSITION,
            lambda: tasks.retry_research_task(
                _request(retry, child), predecessor_id=child.task_id
            ),
        )
        child = _failed(tasks, retry, monkeypatch)
        failed_child = _row(tasks, child.task_id)
        grandchild = tasks.retry_research_task(
            _request(retry, child), predecessor_id=child.task_id
        ).task
        assert len({parent.task_id, child.task_id, grandchild.task_id}) == 3
        assert _row(tasks, parent.task_id) == original
        assert _row(tasks, child.task_id) == failed_child
        # Missing/corrupt retained ancestors cannot become a fresh branch.
        tasks._views.pop(parent.task_id.value)
        _refused(
            research.ResearchServiceErrorCode.TASK_NOT_FOUND,
            lambda: tasks.retry_research_task(
                _request(retry, child), predecessor_id=child.task_id
            ),
        )
        assert len(uv_observation[0]) == 2
    finally:
        tasks.close()


def test_retry_reuses_existing_child_at_capacity_but_new_child_keeps_normal_bound(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        retry = _request(request, parent)
        child = tasks.retry_research_task(retry, predecessor_id=parent.task_id).task
        for number in range(254):
            tasks.start_research_task(
                replace(request, idempotency_key=f"capacity-{number}")
            )
        assert len(tasks._views) == 256
        repeated = tasks.retry_research_task(retry, predecessor_id=parent.task_id)
        assert not repeated.created and repeated.task == child
        child = _failed(tasks, retry, monkeypatch)
        _refused(
            research.ResearchServiceErrorCode.BOUND_EXCEEDED,
            lambda: tasks.retry_research_task(
                _request(retry, child), predecessor_id=child.task_id
            ),
        )
        assert len(tasks._views) == 256 and len(uv_observation[0]) == 1
    finally:
        tasks.close()


def test_retry_requires_exact_nominals_and_a_genuine_failed_receipt(
    tmp_path, monkeypatch, uv_observation
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        retry = _request(request, parent)
        for malformed in (
            parent.task_id.value,
            SimpleNamespace(value=parent.task_id.value),
            None,
        ):
            _refused(
                research.ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
                lambda malformed=malformed: tasks.retry_research_task(
                    retry, predecessor_id=malformed
                ),
            )
        _refused(
            research.ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
            lambda: tasks.retry_research_task(
                retry, predecessor_id=parent.task_id, measure_query=1
            ),
        )
        original = _row(tasks, parent.task_id)
        object.__setattr__(
            parent.terminal_receipt, "infrastructure_failure_class", None
        )
        _refused(
            research.ResearchServiceErrorCode.REFERENCE_MISMATCH,
            lambda: tasks.retry_research_task(retry, predecessor_id=parent.task_id),
        )
        assert _row(tasks, parent.task_id) == original
        assert len(tasks._views) == 1 and uv_observation[0] == []
    finally:
        tasks.close()


@pytest.mark.parametrize("changed", ["receipt_task", "receipt_binding", "idempotency"])
def test_retry_refuses_forged_retained_identity(
    tmp_path, monkeypatch, uv_observation, changed
):
    request, provider, _ = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        parent = _failed(tasks, request, monkeypatch)
        original = _row(tasks, parent.task_id)
        if changed == "receipt_task":
            object.__setattr__(
                parent.terminal_receipt,
                "task_id",
                research.ResearchTaskId("rtsk_" + "0" * 64),
            )
        elif changed == "receipt_binding":
            object.__setattr__(
                parent.terminal_receipt,
                "immutable_bindings",
                replace(
                    parent.immutable_bindings, public_train_digest="sha256:" + "0" * 64
                ),
            )
        else:
            tasks._idempotency[request.idempotency_key] = "rtsk_" + "0" * 64
        _refused(
            research.ResearchServiceErrorCode.REFERENCE_MISMATCH,
            lambda: tasks.retry_research_task(
                _request(request, parent), predecessor_id=parent.task_id
            ),
        )
        assert _row(tasks, parent.task_id) == original
        assert len(tasks._views) == 1 and uv_observation[0] == []
    finally:
        tasks.close()
