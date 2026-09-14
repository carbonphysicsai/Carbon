"""C-07 durable non-official orchestration tests."""

from __future__ import annotations

import dataclasses

import pytest

from carbon import audit
from carbon.construction import ResolvedConstructionPlanRef
from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionScope,
    ExecutionStage,
    ExecutionState,
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
from carbon.measurement_runtime.model import (
    MEASUREMENT_IDS,
    PHYSICS_IDS,
    BurgersMeasurementResult,
    MeasurementDisposition,
    MeasurementObservation,
    PhysicsObservation,
)
from carbon.orchestration import (
    DevelopmentEvaluationOrchestrator,
    DevelopmentOrchestrationRequest,
    OperationalDisposition,
    OrchestrationCode,
    OrchestrationFailure,
    ResultOwnerRefs,
    StageDisposition,
    public_projection,
    reconstruction_outcome_digest,
    reviewer_projection,
    write_report_bundle,
)
from carbon.reconstruction.model import (
    PredictionReceipt,
    ReconstructionReceipt,
    ReconstructionStatus,
)
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reference_runtime.model import BurgersReferenceRole
from carbon.reference_runtime.protocol import ValidatedReferenceResult
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)
from carbon.seeding import EvaluationBinding, SeedPin


def _sha(label: str) -> str:
    return audit.digest_bytes(label.encode("ascii"))


def _repeat_and_receipts(tmp_path):
    challenge = ChallengeKey("burgers-dynamics-v1", "1.0")
    plan_ref = ResolvedConstructionPlanRef(
        challenge, content_digest=_sha("construction-plan")
    )
    policy = ResearchResourcePolicyRef(
        challenge,
        "c07-development-policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("resource-policy"),
    )
    resource = ResourceClassRef(
        challenge,
        "c07-linux-cpu",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("resource-class"),
    )
    replicas = []
    receipts = []
    for index in range(3):
        execution = ExecutionAttemptRef(
            SubmissionId(f"00000000-0000-4000-8000-00000000001{index}"), 1
        )
        randomness = _sha(f"randomness-{index}")
        placeholder = BoundReconstructionReplicate(
            ReconstructionReplicateIdentity(
                challenge,
                plan_ref,
                policy,
                resource,
                f"replica-{index}",
                _sha(f"placeholder-{index}"),
            )
        )
        replicate_digest = development_replicate_digest(
            binding=placeholder,
            execution_ref=execution,
            randomness_digest=randomness,
            training_data_digest=_sha("train"),
            request_digest=_sha("inference-request"),
        )
        replica = DevelopmentReplica(
            BoundReconstructionReplicate(
                dataclasses.replace(
                    placeholder.replicate_identity,
                    replicate_digest=replicate_digest,
                )
            ),
            execution,
            randomness,
        )
        replicas.append(replica)
        receipts.append(
            ReconstructionReceipt(
                artifact_path=(tmp_path / f"artifact-{index}").resolve(),
                artifact_digest=_sha(f"artifact-{index}"),
                execution_id=f"reconstruction-{index}",
                plan_digest=plan_ref.content_digest,
                profile_digest=_sha("profile"),
                training_data_digest=_sha("train"),
                randomness_digest=randomness,
                checkpoint_digest=_sha(f"checkpoint-{index}"),
                status=ReconstructionStatus.COMPLETE,
                completed_steps=4,
                compile_seconds=0.1,
                train_execution_seconds=0.2,
            )
        )
    repeat = freeze_development_repeat_plan(
        plan_id="c07-three-replica-development",
        construction_plan_digest=plan_ref.content_digest,
        training_data_digest=_sha("train"),
        request_digest=_sha("inference-request"),
        replicas=tuple(replicas),
    )
    return repeat, tuple(receipts)


def _measurement() -> BurgersMeasurementResult:
    return BurgersMeasurementResult(
        request_digest=_sha("measurement-request"),
        disposition=MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY,
        measurements=tuple(
            MeasurementObservation(item, 1.0, 1.0, 0.0, 1.0, 0.0)
            for item in MEASUREMENT_IDS
        ),
        physics=tuple(PhysicsObservation(item, 0.0, 1.0, 0.0) for item in PHYSICS_IDS),
        diagnostics=(),
    )


def _values(tmp_path):
    repeat, receipts = _repeat_and_receipts(tmp_path)
    measurement = _measurement()
    reference = ValidatedReferenceResult(
        request_digest=_sha("reference-request"),
        role=BurgersReferenceRole.CANDIDATE_PRIMARY,
        outcome=ReferenceRunOutcome.SUPPORTED,
        failure_reason=None,
        artifact_digest=_sha("reference-artifact"),
        artifact_bytes=512,
        shape=(4, 16),
        diagnostics=(),
    )
    evidence = audit.DevelopmentEvidenceBinding(
        submission_id="00000000-0000-4000-8000-000000000007",
        strategy_digest=_sha("strategy"),
        challenge_id="burgers-dynamics-v1",
        challenge_version="1.0",
        generator_digest=_sha("generator"),
        target_population_digest=_sha("population"),
        sampling_plan_digest=_sha("sampling"),
        training_data_commitment=_sha("train"),
        reconstruction_plan_digest=_sha("construction-plan"),
        repeat_plan_digest=repeat.plan_digest,
        resource_policy_digest=_sha("resource-policy"),
        reconstruction_outcome_digest=reconstruction_outcome_digest(repeat, receipts),
        reconstruction_attempt_digests=tuple(item.artifact_digest for item in receipts),
        inference_request_digest=_sha("inference-request"),
        prediction_digest=_sha("prediction"),
        reference_policy_digest=_sha("reference-policy"),
        reference_implementation_digest=_sha("reference-implementation"),
        reference_environment_digest=_sha("reference-environment"),
        reference_artifact_digest=reference.artifact_digest,
        measurement_contract_digest=_sha("measurement-contract"),
        measurement_implementation_digest=_sha("measurement-implementation"),
        measurement_environment_digest=_sha("measurement-environment"),
        measurement_result_digest=measurement.result_digest,
        scoring_policy_digest=_sha("score-policy"),
        dossier_digest=_sha("dossier"),
        qualification_manifest_digest=_sha("qualification-manifest"),
        source_tree_digest=_sha("source-tree"),
        worker_image_digest=_sha("worker-image"),
        execution_policy_digest=_sha("execution-policy"),
    )
    execution = DurableExecutionBinding(
        handle=ExecutionAttemptHandle(
            submission_id=SubmissionId(evidence.submission_id),
            attempt_number=1,
            admission_kind=AdmissionKind.FIXTURE,
            seed_pin=SeedPin(
                ChallengeKey(evidence.challenge_id, evidence.challenge_version),
                "generator-v1",
                evidence.generator_digest,
                "score-v1",
                evidence.scoring_policy_digest,
                EvaluationBinding(b"e" * 32),
            ),
            environment_pin=ExecutionEnvironmentPin(
                "c07-development", evidence.worker_image_digest
            ),
        ),
        requester_identity=RequesterIdentity("c07-development-owner"),
        strategy_hash=StrategyHash(evidence.strategy_digest),
        scope=ExecutionScope.FIXTURE_DEVELOPMENT,
        resolved_plan_digest=evidence.reconstruction_plan_digest,
        reconstruction_policy_digest=_sha("reconstruction-policy"),
        resource_policy_digest=evidence.resource_policy_digest,
        protected_evaluation_policy_digest=_sha("protected-disabled"),
    )
    prediction = PredictionReceipt(
        artifact_digest=receipts[0].artifact_digest,
        request_digest=evidence.inference_request_digest,
        output_digest=evidence.prediction_digest,
        cases=1,
        times=4,
        points=16,
        execution_seconds=0.1,
    )
    return (
        DevelopmentOrchestrationRequest(
            execution,
            evidence,
            _sha("case-manifest"),
            (reference.request_digest,),
            (measurement.request_digest,),
        ),
        repeat,
        receipts,
        prediction,
        reference,
        measurement,
    )


def _signer() -> audit.DevelopmentReceiptSigner:
    return audit.DevelopmentReceiptSigner(
        key_id="c07-external-development-key",
        private_key=bytes(range(32)),
        valid_from_micros=1_000,
        valid_until_micros=10_000,
    )


def _owners() -> ResultOwnerRefs:
    return ResultOwnerRefs(
        "development-card-1", "development-transcript-1", _sha("transcript")
    )


def _orchestrator(tmp_path, signer):
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    ledger = audit.DevelopmentEvidenceLedger(
        tmp_path / "audit.sqlite3", (signer.verification_key,)
    )
    return queue, ledger, DevelopmentEvaluationOrchestrator(queue, ledger)


def _run_stages(
    orchestrator, handle, repeat, receipts, prediction, reference, measurement
):
    assert (
        orchestrator.record_generator_manifest(
            handle, handle.request.case_manifest_digest
        )
        is WriteDisposition.INSERTED
    )
    assert (
        orchestrator.record_reconstruction(handle, repeat, receipts)
        is WriteDisposition.INSERTED
    )
    assert (
        orchestrator.record_prediction(handle, prediction) is WriteDisposition.INSERTED
    )
    assert orchestrator.record_reference(handle, reference) is WriteDisposition.INSERTED
    assert (
        orchestrator.record_measurement(handle, measurement)
        is WriteDisposition.INSERTED
    )
    assert orchestrator.record_unresolved_score(handle) is WriteDisposition.INSERTED


def test_complete_path_signs_once_records_result_and_stays_non_official(
    tmp_path,
) -> None:
    signer = _signer()
    request, repeat, receipts, prediction, reference, measurement = _values(tmp_path)
    queue, ledger, orchestrator = _orchestrator(tmp_path, signer)
    handle = orchestrator.begin(request, worker_id="c07-worker", claim_id="claim-1")
    _run_stages(
        orchestrator, handle, repeat, receipts, prediction, reference, measurement
    )
    evidence = audit.FrozenEvidenceIndex(
        frozenset(request.evidence.required_evidence_digests())
    )
    complete = orchestrator.finalize_complete(
        handle,
        receipt_id="c07-development-receipt-1",
        signer=signer,
        evidence_index=evidence,
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=3_000,
        verified_at_micros=3_100,
    )
    assert complete.account.disposition is OperationalDisposition.COMPLETE_UNRESOLVED
    assert complete.account.missing_stages == (ExecutionStage.ARCHIVE,)
    assert complete.account.stages[5].disposition is (
        StageDisposition.UNRESOLVED_NO_QUALIFIED_SCORE
    )
    assert ledger.checkpoint().receipt_count == 1
    assert (
        queue.status(request.execution.ref, request.execution.requester_identity).state
        is ExecutionState.RESULT_RECORDED
    )
    assert set(public_projection(complete.account)["eligibility"].values()) == {False}
    assert (
        reviewer_projection(complete.account)["receipt_digest"]
        == complete.account.receipt_digest
    )
    paths = write_report_bundle((tmp_path / "report").resolve(), complete)
    assert all(path.is_file() for path in paths)
    assert write_report_bundle((tmp_path / "report").resolve(), complete) == paths

    replay = orchestrator.finalize_complete(
        handle,
        receipt_id="c07-development-receipt-1",
        signer=signer,
        evidence_index=evidence,
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=3_000,
        verified_at_micros=3_100,
    )
    assert replay == complete
    assert ledger.checkpoint().receipt_count == 1

    reopened_queue = DurableExecutionQueue(queue.path)
    reopened_ledger = audit.DevelopmentEvidenceLedger(
        ledger.path, (signer.verification_key,)
    )
    reopened = DevelopmentEvaluationOrchestrator(reopened_queue, reopened_ledger)
    attached = reopened.attach_completed(
        request, worker_id="c07-worker", claim_id="claim-1"
    )
    assert (
        reopened.finalize_complete(
            attached,
            receipt_id="c07-development-receipt-1",
            signer=signer,
            evidence_index=evidence,
            result_owners=_owners(),
            started_at_micros=2_000,
            finished_at_micros=3_000,
            verified_at_micros=3_100,
        )
        == complete
    )


def test_restart_requires_explicit_same_attempt_reconciliation(tmp_path) -> None:
    signer = _signer()
    request, repeat, receipts, *_ = _values(tmp_path)
    queue, ledger, orchestrator = _orchestrator(tmp_path, signer)
    handle = orchestrator.begin(request, worker_id="c07-worker", claim_id="claim-1")
    orchestrator.record_generator_manifest(handle, request.case_manifest_digest)
    orchestrator.record_reconstruction(handle, repeat, receipts)

    restarted_queue = DurableExecutionQueue(queue.path)
    restarted = DevelopmentEvaluationOrchestrator(restarted_queue, ledger)
    with pytest.raises(OrchestrationFailure) as blocked:
        restarted.begin(request, worker_id="c07-worker", claim_id="claim-1")
    assert blocked.value.code is OrchestrationCode.RECONCILIATION_REQUIRED
    resumed = restarted.resume_existing(
        request, worker_id="c07-worker", claim_id="claim-1"
    )
    assert (
        restarted.record_generator_manifest(resumed, request.case_manifest_digest)
        is WriteDisposition.ALREADY_PRESENT
    )
    assert (
        restarted.record_reconstruction(resumed, repeat, receipts)
        is WriteDisposition.ALREADY_PRESENT
    )
    assert (
        restarted_queue.status(
            request.execution.ref, request.execution.requester_identity
        ).attempt_number
        == 1
    )


@pytest.mark.parametrize(
    ("disposition", "stage"),
    (
        (OperationalDisposition.FAILED_GENERATOR, ExecutionStage.GENERATOR),
        (OperationalDisposition.FAILED_RECONSTRUCTION, ExecutionStage.RECONSTRUCTION),
        (OperationalDisposition.FAILED_REFERENCE, ExecutionStage.REFERENCE),
        (OperationalDisposition.FAILED_MEASUREMENT, ExecutionStage.MEASUREMENT),
        (OperationalDisposition.FAILED_INFRASTRUCTURE, ExecutionStage.RECONSTRUCTION),
        (OperationalDisposition.CANCELLED, ExecutionStage.RECONSTRUCTION),
        (OperationalDisposition.INDETERMINATE, ExecutionStage.RECONSTRUCTION),
        (OperationalDisposition.CONTESTED, ExecutionStage.SCORE),
    ),
)
def test_every_terminal_account_retains_failure_without_receipt_or_score(
    tmp_path, disposition, stage
) -> None:
    signer = _signer()
    request, repeat, receipts, prediction, reference, measurement = _values(tmp_path)
    queue, ledger, orchestrator = _orchestrator(tmp_path, signer)
    handle = orchestrator.begin(request, worker_id="c07-worker", claim_id="claim-1")
    if stage is not ExecutionStage.GENERATOR:
        orchestrator.record_generator_manifest(handle, request.case_manifest_digest)
    if stage in {
        ExecutionStage.PREDICTION,
        ExecutionStage.REFERENCE,
        ExecutionStage.MEASUREMENT,
        ExecutionStage.SCORE,
    }:
        orchestrator.record_reconstruction(handle, repeat, receipts)
    if stage in {
        ExecutionStage.REFERENCE,
        ExecutionStage.MEASUREMENT,
        ExecutionStage.SCORE,
    }:
        orchestrator.record_prediction(handle, prediction)
    if stage in {ExecutionStage.MEASUREMENT, ExecutionStage.SCORE}:
        orchestrator.record_reference(handle, reference)
    if stage is ExecutionStage.SCORE:
        orchestrator.record_measurement(handle, measurement)
    account = orchestrator.conclude_without_receipt(
        handle,
        disposition=disposition,
        failed_stage=stage,
        failure_evidence_ref="typed-terminal-evidence",
        failure_evidence_digest=_sha(disposition.value),
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=2_500,
    )
    assert account.receipt_id is None
    assert account.score_eligible is False
    assert ledger.checkpoint().receipt_count == 0
    assert queue.status(
        request.execution.ref, request.execution.requester_identity
    ).result_recorded
    replay = orchestrator.conclude_without_receipt(
        handle,
        disposition=disposition,
        failed_stage=stage,
        failure_evidence_ref="typed-terminal-evidence",
        failure_evidence_digest=_sha(disposition.value),
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=2_500,
    )
    assert replay == account


def test_receipt_append_then_association_interruption_replays_without_new_science(
    tmp_path, monkeypatch
) -> None:
    signer = _signer()
    request, repeat, receipts, prediction, reference, measurement = _values(tmp_path)
    queue, ledger, orchestrator = _orchestrator(tmp_path, signer)
    handle = orchestrator.begin(request, worker_id="c07-worker", claim_id="claim-1")
    _run_stages(
        orchestrator, handle, repeat, receipts, prediction, reference, measurement
    )
    evidence = audit.FrozenEvidenceIndex(
        frozenset(request.evidence.required_evidence_digests())
    )
    original = queue.record_partial
    interrupted = False

    def fail_receipt_once(claim, partial):
        nonlocal interrupted
        if partial.stage is ExecutionStage.RECEIPT and not interrupted:
            interrupted = True
            raise RuntimeError("simulated controller interruption")
        return original(claim, partial)

    monkeypatch.setattr(queue, "record_partial", fail_receipt_once)
    with pytest.raises(RuntimeError, match="simulated controller interruption"):
        orchestrator.finalize_complete(
            handle,
            receipt_id="c07-development-receipt-1",
            signer=signer,
            evidence_index=evidence,
            result_owners=_owners(),
            started_at_micros=2_000,
            finished_at_micros=3_000,
            verified_at_micros=3_100,
        )
    assert ledger.checkpoint().receipt_count == 1
    complete = orchestrator.finalize_complete(
        handle,
        receipt_id="c07-development-receipt-1",
        signer=signer,
        evidence_index=evidence,
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=3_000,
        verified_at_micros=3_100,
    )
    assert complete.account.disposition is OperationalDisposition.COMPLETE_UNRESOLVED
    assert ledger.checkpoint().receipt_count == 1


def test_cross_binding_stage_order_and_authority_upgrade_fail_closed(tmp_path) -> None:
    signer = _signer()
    request, repeat, receipts, prediction, *_ = _values(tmp_path)
    _, _, orchestrator = _orchestrator(tmp_path, signer)
    handle = orchestrator.begin(request, worker_id="c07-worker", claim_id="claim-1")
    with pytest.raises(OrchestrationFailure) as generator_mismatch:
        orchestrator.record_generator_manifest(handle, _sha("changed-manifest"))
    assert generator_mismatch.value.code is OrchestrationCode.CONFLICT
    with pytest.raises(OrchestrationFailure) as order:
        orchestrator.record_prediction(handle, prediction)
    assert order.value.code is OrchestrationCode.STATE
    orchestrator.record_generator_manifest(handle, request.case_manifest_digest)
    changed = dataclasses.replace(receipts[0], artifact_digest=_sha("changed"))
    with pytest.raises(OrchestrationFailure) as mismatch:
        orchestrator.record_reconstruction(
            handle, repeat, (changed, receipts[1], receipts[2])
        )
    assert mismatch.value.code is OrchestrationCode.CONFLICT
    with pytest.raises(OrchestrationFailure) as denied:
        dataclasses.replace(
            orchestrator.conclude_without_receipt(
                handle,
                disposition=OperationalDisposition.CANCELLED,
                failed_stage=ExecutionStage.RECONSTRUCTION,
                failure_evidence_ref="cancelled-evidence",
                failure_evidence_digest=_sha("cancelled"),
                result_owners=_owners(),
                started_at_micros=2_000,
                finished_at_micros=2_500,
            ),
            archive_acknowledged=True,
        )
    assert denied.value.code is OrchestrationCode.DENIED
