from __future__ import annotations

import dataclasses
import sqlite3
import threading
import uuid

import pytest

from carbon.execution import (
    ArchiveRequirement,
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionCode,
    ExecutionFailure,
    ExecutionResultRefs,
    ExecutionScope,
    ExecutionStage,
    ExecutionState,
    PartialWorkRef,
    ReconciliationDisposition,
    WriteDisposition,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, SeedPin


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _binding(
    *,
    submission: str = "00000000-0000-4000-8000-000000000001",
    attempt: int = 1,
    kind: AdmissionKind = AdmissionKind.PRODUCTION,
    plan: str = "a",
) -> DurableExecutionBinding:
    handle = ExecutionAttemptHandle(
        submission_id=SubmissionId(submission),
        attempt_number=attempt,
        admission_kind=kind,
        seed_pin=SeedPin(
            challenge_key=ChallengeKey("burgers", "1.0"),
            generator_version="burgers-generator-v1",
            generator_digest=_sha("1"),
            scoring_version="burgers-score-v2",
            scoring_digest=_sha("2"),
            evaluation_binding=EvaluationBinding(b"e" * 32),
        ),
        environment_pin=ExecutionEnvironmentPin("jax-cpu-v1", _sha("3")),
    )
    return DurableExecutionBinding(
        handle=handle,
        requester_identity=RequesterIdentity("requester-1"),
        strategy_hash=StrategyHash(_sha("4")),
        scope=(
            ExecutionScope.FIXTURE_DEVELOPMENT
            if kind is AdmissionKind.FIXTURE
            else ExecutionScope.REAL_PATH_NON_LIVE
        ),
        resolved_plan_digest=_sha(plan),
        reconstruction_policy_digest=_sha("5"),
        resource_policy_digest=_sha("6"),
        protected_evaluation_policy_digest=_sha("7"),
    )


def _result() -> ExecutionResultRefs:
    return ExecutionResultRefs(
        private_result_ref="private-result-1",
        private_result_digest=_sha("8"),
        card_record_ref="card-record-1",
        transcript_ref="private-transcript-1",
        transcript_digest=_sha("9"),
    )


def test_binding_scope_is_structural() -> None:
    source = _binding(kind=AdmissionKind.FIXTURE)
    with pytest.raises(ExecutionFailure) as captured:
        DurableExecutionBinding(
            handle=source.handle,
            requester_identity=source.requester_identity,
            strategy_hash=source.strategy_hash,
            scope=ExecutionScope.REAL_PATH_NON_LIVE,
            resolved_plan_digest=source.resolved_plan_digest,
            reconstruction_policy_digest=source.reconstruction_policy_digest,
            resource_policy_digest=source.resource_policy_digest,
            protected_evaluation_policy_digest=source.protected_evaluation_policy_digest,
        )
    assert captured.value.code is ExecutionCode.INVALID


def test_admission_is_durable_idempotent_and_conflicts_fail_closed(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    first = DurableExecutionQueue(path)
    binding = _binding()
    assert first.admit(binding) is WriteDisposition.INSERTED
    assert (
        DurableExecutionQueue(path).admit(binding) is WriteDisposition.ALREADY_PRESENT
    )
    with pytest.raises(ExecutionFailure) as captured:
        first.admit(_binding(plan="b"))
    assert captured.value.code is ExecutionCode.CONFLICT


def test_claim_is_atomic_across_queue_instances(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    DurableExecutionQueue(path).admit(_binding())
    barrier = threading.Barrier(3)
    claims = []

    def run(worker: str) -> None:
        queue = DurableExecutionQueue(path)
        barrier.wait()
        claims.append(queue.claim_next(worker))

    threads = [
        threading.Thread(target=run, args=(f"worker-{index}",)) for index in range(2)
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert sum(claim is not None for claim in claims) == 1


def test_claim_replay_converges_without_second_dispatch(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    queue.admit(_binding())
    first = queue.claim_next("worker-1", claim_id="claim-1")
    second = queue.claim_next("worker-1", claim_id="claim-1")
    assert first == second
    with pytest.raises(ExecutionFailure) as captured:
        queue.claim_next("worker-2", claim_id="claim-1")
    assert captured.value.code is ExecutionCode.CONFLICT


def test_pre_dispatch_restart_requires_reconciliation_then_requeues(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path)
    queue.admit(_binding())
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None

    restarted = DurableExecutionQueue(path)
    status = restarted.status(claimed.claim.ref, RequesterIdentity("requester-1"))
    assert status.state is ExecutionState.RECONCILIATION_REQUIRED
    assert restarted.claim_next("worker-2") is None
    assert (
        restarted.reconcile(claimed.claim, ReconciliationDisposition.NOT_DISPATCHED)
        is ExecutionState.QUEUED
    )
    assert restarted.claim_next("worker-2", claim_id="claim-2") is not None


def test_running_restart_resumes_same_attempt_and_preserves_partial_work(
    tmp_path,
) -> None:
    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path)
    binding = _binding()
    queue.admit(binding)
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    partial = PartialWorkRef(ExecutionStage.RECONSTRUCTION, "artifact-1", _sha("a"))
    queue.record_partial(claimed.claim, partial)

    restarted = DurableExecutionQueue(path)
    assert (
        restarted.reconcile(claimed.claim, ReconciliationDisposition.RESUME_EXISTING)
        is ExecutionState.RUNNING
    )
    assert restarted.partials(claimed.claim) == (partial,)
    assert (
        restarted.record_partial(claimed.claim, partial)
        is WriteDisposition.ALREADY_PRESENT
    )
    status = restarted.status(binding.ref, RequesterIdentity("requester-1"))
    assert status.attempt_number == 1
    assert status.partial_stage_count == 1


def test_partial_stage_conflict_does_not_overwrite(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    queue.admit(_binding())
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    queue.record_partial(
        claimed.claim,
        PartialWorkRef(ExecutionStage.PREDICTION, "prediction-1", _sha("a")),
    )
    with pytest.raises(ExecutionFailure) as captured:
        queue.record_partial(
            claimed.claim,
            PartialWorkRef(ExecutionStage.PREDICTION, "prediction-2", _sha("b")),
        )
    assert captured.value.code is ExecutionCode.CONFLICT


def test_result_is_recorded_but_cannot_claim_archive_finalization(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path)
    binding = _binding()
    queue.admit(binding)
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    result = _result()
    assert (
        result.archive_requirement is ArchiveRequirement.C_EA2_ACKNOWLEDGEMENT_REQUIRED
    )
    assert queue.record_result(claimed.claim, result) is WriteDisposition.INSERTED
    assert (
        queue.record_result(claimed.claim, result) is WriteDisposition.ALREADY_PRESENT
    )

    restarted = DurableExecutionQueue(path)
    status = restarted.status(binding.ref, RequesterIdentity("requester-1"))
    assert status.state is ExecutionState.RESULT_RECORDED
    assert status.result_recorded is True
    assert status.archive_acknowledged is False
    assert "private-result" not in repr(status)
    assert "transcript" not in repr(status)


def test_result_conflict_does_not_overwrite(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    queue.admit(_binding())
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    queue.record_result(claimed.claim, _result())
    changed = dataclasses.replace(_result(), private_result_digest=_sha("b"))
    with pytest.raises(ExecutionFailure) as captured:
        queue.record_result(claimed.claim, changed)
    assert captured.value.code is ExecutionCode.CONFLICT


def test_retry_requires_source_attempt_continuity_and_same_bindings(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    first = _binding()
    queue.admit(first)
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    queue.retryable_infrastructure(claimed.claim)
    second = _binding(attempt=2)
    assert queue.admit(second) is WriteDisposition.INSERTED
    assert (
        queue.status(first.ref, RequesterIdentity("requester-1")).state
        is ExecutionState.RETRYABLE_INFRA
    )
    assert (
        queue.status(second.ref, RequesterIdentity("requester-1")).state
        is ExecutionState.QUEUED
    )

    with pytest.raises(ExecutionFailure) as captured:
        queue.admit(_binding(attempt=3, plan="b"))
    assert captured.value.code is ExecutionCode.CONFLICT


def test_retry_attempt_cannot_appear_without_prior_attempt(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    with pytest.raises(ExecutionFailure) as captured:
        queue.admit(_binding(attempt=2))
    assert captured.value.code is ExecutionCode.CONFLICT


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("retryable_infrastructure", ExecutionState.RETRYABLE_INFRA),
        ("fail_infrastructure", ExecutionState.FAILED_INFRA),
        ("fail_strategy", ExecutionState.FAILED_STRATEGY),
    ],
)
def test_failure_classes_remain_distinct(tmp_path, method, expected) -> None:
    queue = DurableExecutionQueue(tmp_path / f"{method}.sqlite3")
    binding = _binding()
    queue.admit(binding)
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    getattr(queue, method)(claimed.claim)
    assert queue.status(binding.ref, RequesterIdentity("requester-1")).state is expected


@pytest.mark.parametrize(
    "method", ("retryable_infrastructure", "fail_infrastructure", "fail_strategy")
)
def test_ambiguous_dispatch_cannot_be_turned_into_a_terminal_outcome(
    tmp_path, method
) -> None:
    path = tmp_path / f"{method}.sqlite3"
    queue = DurableExecutionQueue(path)
    queue.admit(_binding())
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    with pytest.raises(ExecutionFailure) as captured:
        getattr(queue, method)(claimed.claim)
    assert captured.value.code is ExecutionCode.STATE

    restarted = DurableExecutionQueue(path)
    with pytest.raises(ExecutionFailure) as captured:
        getattr(restarted, method)(claimed.claim)
    assert captured.value.code is ExecutionCode.STATE
    assert (
        restarted.status(claimed.claim.ref, RequesterIdentity("requester-1")).state
        is ExecutionState.RECONCILIATION_REQUIRED
    )


def test_cancel_is_requester_bound_and_only_pre_dispatch(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    binding = _binding()
    queue.admit(binding)
    with pytest.raises(ExecutionFailure) as captured:
        queue.cancel(binding.ref, RequesterIdentity("requester-2"))
    assert captured.value.code is ExecutionCode.DENIED
    assert (
        queue.cancel(binding.ref, RequesterIdentity("requester-1"))
        is WriteDisposition.INSERTED
    )
    assert (
        queue.cancel(binding.ref, RequesterIdentity("requester-1"))
        is WriteDisposition.ALREADY_PRESENT
    )


def test_status_is_requester_bound_and_positive_allow_list(tmp_path) -> None:
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    binding = _binding()
    queue.admit(binding)
    status = queue.status(binding.ref, RequesterIdentity("requester-1"))
    assert tuple(field.name for field in dataclasses.fields(status)) == (
        "schema_version",
        "submission_id",
        "attempt_number",
        "state",
        "partial_stage_count",
        "result_recorded",
        "archive_acknowledged",
    )
    with pytest.raises(ExecutionFailure) as captured:
        queue.status(binding.ref, RequesterIdentity("requester-2"))
    assert captured.value.code is ExecutionCode.DENIED


def test_corrupt_binding_digest_fails_closed(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path)
    binding = _binding()
    queue.admit(binding)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE execution_attempt_v1 SET binding_digest='bad'")
    with pytest.raises(ExecutionFailure) as captured:
        queue.status(binding.ref, RequesterIdentity("requester-1"))
    assert captured.value.code is ExecutionCode.STORE


def test_corrupt_partial_work_fails_closed_on_resume(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path)
    queue.admit(_binding())
    claimed = queue.claim_next("worker-1", claim_id="claim-1")
    assert claimed is not None
    queue.mark_running(claimed.claim)
    queue.record_partial(
        claimed.claim,
        PartialWorkRef(ExecutionStage.PREDICTION, "prediction-1", _sha("a")),
    )
    with sqlite3.connect(path) as db:
        db.execute("UPDATE execution_partial_v1 SET artifact_digest='bad'")
    with pytest.raises(ExecutionFailure) as captured:
        queue.partials(claimed.claim)
    assert captured.value.code is ExecutionCode.STORE
    with pytest.raises(ExecutionFailure) as captured:
        queue.status(claimed.claim.ref, RequesterIdentity("requester-1"))
    assert captured.value.code is ExecutionCode.STORE


def test_corrupt_result_state_and_event_log_fail_closed(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path)
    binding = _binding()
    queue.admit(binding)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE execution_attempt_v1 SET state='RESULT_RECORDED'")
    with pytest.raises(ExecutionFailure) as captured:
        queue.status(binding.ref, RequesterIdentity("requester-1"))
    assert captured.value.code is ExecutionCode.STORE

    with sqlite3.connect(path) as db:
        db.execute("UPDATE execution_attempt_v1 SET state='QUEUED'")
        db.execute("UPDATE execution_event_v1 SET body_digest='bad'")
    with pytest.raises(ExecutionFailure) as captured:
        DurableExecutionQueue(path)
    assert captured.value.code is ExecutionCode.STORE


def test_failed_claim_id_factory_leaves_attempt_queued(tmp_path) -> None:
    def fail() -> uuid.UUID:
        raise RuntimeError("boom")

    path = tmp_path / "execution.sqlite3"
    queue = DurableExecutionQueue(path, id_factory=fail)
    binding = _binding()
    queue.admit(binding)
    with pytest.raises(ExecutionFailure) as captured:
        queue.claim_next("worker-1")
    assert captured.value.code is ExecutionCode.INVALID
    assert (
        queue.status(binding.ref, RequesterIdentity("requester-1")).state
        is ExecutionState.QUEUED
    )
