"""Deterministic public DEVELOPMENT fixtures for C-10 tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from carbon import audit
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionScope,
    ExecutionStage,
    PartialWorkRef,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
)
from carbon.orchestration import (
    CompletedDevelopmentOrchestration,
    DevelopmentEvaluationOrchestrator,
    DevelopmentOrchestrationRequest,
    OrchestrationHandle,
    ResultOwnerRefs,
)
from carbon.reexecution.model import (
    ExecutionProvenance,
    ExecutionResourceObservation,
    LinkedReexecutionRequest,
    ReexecutionBudget,
    ReexecutionLaunchIntent,
    ReplicaAuditBinding,
    ResourceObservationState,
    ScientificStateBinding,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, SeedPin


def sha(label: str) -> str:
    return audit.digest_bytes(label.encode("ascii"))


@dataclass(slots=True)
class C10Fixture:
    root: Path
    signer: audit.DevelopmentReceiptSigner
    queue: DurableExecutionQueue
    ledger: audit.DevelopmentEvidenceLedger
    orchestrator: DevelopmentEvaluationOrchestrator
    primary_request: DevelopmentOrchestrationRequest
    primary_result: CompletedDevelopmentOrchestration
    reexecution_request: DevelopmentOrchestrationRequest
    launch_intent: ReexecutionLaunchIntent
    linked_request: LinkedReexecutionRequest


def _evidence(
    *, repeat: str, output_suffix: str = ""
) -> audit.DevelopmentEvidenceBinding:
    suffix = f"-{output_suffix}" if output_suffix else ""
    return audit.DevelopmentEvidenceBinding(
        submission_id="00000000-0000-4000-8000-000000000710",
        strategy_digest=sha("strategy"),
        challenge_id="burgers-dynamics-v1",
        challenge_version="1.0",
        generator_digest=sha("generator"),
        target_population_digest=sha("population"),
        sampling_plan_digest=sha("sampling"),
        training_data_commitment=sha("train"),
        reconstruction_plan_digest=sha("construction-plan"),
        repeat_plan_digest=sha(repeat),
        resource_policy_digest=sha("resource-policy"),
        reconstruction_outcome_digest=sha(f"outcome-{repeat}{suffix}"),
        reconstruction_attempt_digests=tuple(
            sha(f"artifact-{index}{suffix}") for index in range(3)
        ),
        inference_request_digest=sha("inference-request"),
        prediction_digest=sha(f"prediction{suffix}"),
        reference_policy_digest=sha("reference-policy"),
        reference_implementation_digest=sha("reference-implementation"),
        reference_environment_digest=sha("reference-environment"),
        reference_artifact_digest=sha(f"reference-artifact{suffix}"),
        measurement_contract_digest=sha("measurement-contract"),
        measurement_implementation_digest=sha("measurement-implementation"),
        measurement_environment_digest=sha("measurement-environment"),
        measurement_result_digest=sha(f"measurement-result{suffix}"),
        scoring_policy_digest=sha("score-policy"),
        dossier_digest=sha("dossier"),
        qualification_manifest_digest=sha("qualification-manifest"),
        source_tree_digest=sha("source-tree"),
        worker_image_digest=sha("worker-image"),
        execution_policy_digest=sha("execution-policy"),
    )


def _request(
    evidence: audit.DevelopmentEvidenceBinding, attempt: int
) -> DevelopmentOrchestrationRequest:
    challenge = ChallengeKey(evidence.challenge_id, evidence.challenge_version)
    execution = DurableExecutionBinding(
        ExecutionAttemptHandle(
            SubmissionId(evidence.submission_id),
            attempt,
            AdmissionKind.FIXTURE,
            SeedPin(
                challenge,
                "generator-v1",
                evidence.generator_digest,
                "score-v1",
                evidence.scoring_policy_digest,
                EvaluationBinding(b"c" * 32),
            ),
            ExecutionEnvironmentPin("c10-development", evidence.worker_image_digest),
        ),
        RequesterIdentity("c10-development-owner"),
        StrategyHash(evidence.strategy_digest),
        ExecutionScope.FIXTURE_DEVELOPMENT,
        evidence.reconstruction_plan_digest,
        sha("reconstruction-policy"),
        evidence.resource_policy_digest,
        sha("protected-disabled"),
    )
    return DevelopmentOrchestrationRequest(
        execution,
        evidence,
        sha("case-manifest"),
        (sha("reference-request"),),
        (sha(f"measurement-request-{attempt}"),),
    )


def _owners(attempt: int) -> ResultOwnerRefs:
    return ResultOwnerRefs(
        f"development-card-{attempt}",
        f"development-transcript-{attempt}",
        sha(f"transcript-{attempt}"),
    )


def complete_c07(
    fixture: C10Fixture,
    request: DevelopmentOrchestrationRequest,
    *,
    receipt_id: str,
    handle: OrchestrationHandle | None = None,
) -> CompletedDevelopmentOrchestration:
    if handle is None:
        handle = fixture.orchestrator.begin(
            request,
            worker_id=f"c07-worker-{request.execution.handle.attempt_number}",
            claim_id=f"c07-claim-{request.execution.handle.attempt_number}",
        )
    evidence = request.evidence
    partials = (
        PartialWorkRef(
            ExecutionStage.GENERATOR,
            "case-manifest-" + request.case_manifest_digest[7:39],
            request.case_manifest_digest,
        ),
        PartialWorkRef(
            ExecutionStage.RECONSTRUCTION,
            "reconstruction-trio-" + evidence.reconstruction_outcome_digest[7:39],
            evidence.reconstruction_outcome_digest,
        ),
        PartialWorkRef(
            ExecutionStage.PREDICTION,
            "prediction-" + evidence.prediction_digest[7:39],
            evidence.prediction_digest,
        ),
        PartialWorkRef(
            ExecutionStage.REFERENCE,
            "reference-" + evidence.reference_artifact_digest[7:39],
            evidence.reference_artifact_digest,
        ),
        PartialWorkRef(
            ExecutionStage.MEASUREMENT,
            "measurement-" + evidence.measurement_result_digest[7:39],
            evidence.measurement_result_digest,
        ),
        PartialWorkRef(
            ExecutionStage.SCORE,
            "score-unresolved-" + evidence.scoring_policy_digest[7:39],
            evidence.scoring_policy_digest,
        ),
    )
    for partial in partials:
        fixture.queue.record_partial(handle.claimed.claim, partial)
    return fixture.orchestrator.finalize_complete(
        handle,
        receipt_id=receipt_id,
        signer=fixture.signer,
        evidence_index=audit.FrozenEvidenceIndex(
            frozenset(evidence.required_evidence_digests())
        ),
        result_owners=_owners(request.execution.handle.attempt_number),
        started_at_micros=2_000 * request.execution.handle.attempt_number,
        finished_at_micros=2_000 * request.execution.handle.attempt_number + 500,
        verified_at_micros=8_000,
    )


def make_fixture(tmp_path: Path, *, output_suffix: str = "") -> C10Fixture:
    signer = audit.DevelopmentReceiptSigner(
        key_id="c10-external-development-key",
        private_key=bytes(range(32)),
        valid_from_micros=1_000,
        valid_until_micros=20_000,
    )
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    ledger = audit.DevelopmentEvidenceLedger(
        tmp_path / "audit.sqlite3", (signer.verification_key,)
    )
    orchestrator = DevelopmentEvaluationOrchestrator(queue, ledger)
    primary_request = _request(_evidence(repeat="primary-repeat"), 1)
    placeholder = C10Fixture(
        tmp_path,
        signer,
        queue,
        ledger,
        orchestrator,
        primary_request,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
    )
    primary_result = complete_c07(
        placeholder, primary_request, receipt_id="c10-primary-receipt"
    )
    reexecution_evidence = _evidence(
        repeat="reexecution-repeat",
        output_suffix=output_suffix or "reexecution-envelope",
    )
    if not output_suffix:
        reexecution_evidence = replace(
            reexecution_evidence,
            prediction_digest=primary_request.evidence.prediction_digest,
            reference_artifact_digest=primary_request.evidence.reference_artifact_digest,
            measurement_result_digest=primary_request.evidence.measurement_result_digest,
        )
    reexecution_request = _request(reexecution_evidence, 2)
    replicas = tuple(
        ReplicaAuditBinding(
            f"reconstruction-replica-{index}",
            sha(f"randomness-{index}"),
            sha(f"primary-replicate-{index}"),
            sha(f"reexecution-replicate-{index}"),
        )
        for index in range(3)
    )
    linked = LinkedReexecutionRequest(
        request_id="c10-linked-reexecution-1",
        primary_request=primary_request,
        primary_result=primary_result,
        reexecution_request=reexecution_request,
        replicas=replicas,
        budget=ReexecutionBudget(reexecution_evidence.resource_policy_digest),
        worker_id="c10-audit-worker",
        claim_id="c10-audit-claim",
        primary_scientific_state=ScientificStateBinding(
            primary_request.evidence.reconstruction_attempt_digests,
            tuple(sha(f"checkpoint-{index}") for index in range(3)),
            primary_request.evidence.prediction_digest,
            primary_request.evidence.reference_artifact_digest,
            primary_request.evidence.measurement_result_digest,
        ),
        reexecution_scientific_state=ScientificStateBinding(
            reexecution_request.evidence.reconstruction_attempt_digests,
            tuple(
                sha(f"checkpoint-{index}{'-different' if output_suffix else ''}")
                for index in range(3)
            ),
            reexecution_request.evidence.prediction_digest,
            reexecution_request.evidence.reference_artifact_digest,
            reexecution_request.evidence.measurement_result_digest,
        ),
    )
    return C10Fixture(
        tmp_path,
        signer,
        queue,
        ledger,
        orchestrator,
        primary_request,
        primary_result,
        reexecution_request,
        linked.launch_intent,
        linked,
    )


def provenance(role: str, *, launches: int = 5) -> ExecutionProvenance:
    return ExecutionProvenance(
        execution_id=f"c10-{role}-execution",
        host_id="c10-linux-host",
        administrator_trust_domain="carbon-development-admins",
        hardware_identity_digest=sha("linux-x86-64-cpu"),
        source_tree_digest=sha("source-tree"),
        worker_image_digest=sha("worker-image"),
        worker_launch_digests=tuple(
            sha(f"{role}-launch-{index}") for index in range(launches)
        ),
        scratch_scope_digests=tuple(
            sha(f"{role}-scratch-{index}") for index in range(launches)
        ),
    )


def resources(
    state: ResourceObservationState = ResourceObservationState.MEASURED,
) -> ExecutionResourceObservation:
    if state is ResourceObservationState.UNAVAILABLE:
        return ExecutionResourceObservation(state, 0.0, None, None, None, None, None)
    return ExecutionResourceObservation(
        state,
        2.5,
        3.0 if state is ResourceObservationState.MEASURED else None,
        128 * 1024**2,
        16 * 1024**2,
        4096,
        0,
    )
