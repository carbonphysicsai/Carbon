"""Docker-backed C-10 linked DEVELOPMENT re-execution evidence."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from c02_fixtures import compile_c02_plan

from carbon import audit
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionRelationKind,
    ExecutionScope,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.measurement_runtime.controller import (
    IsolatedBurgersMeasurementController,
    IsolatedMeasurementResult,
)
from carbon.measurement_runtime.model import (
    BurgersMeasurementRequest,
    FrozenFieldArtifact,
    MeasurementDisposition,
    measurement_contract_digest,
    measurement_environment_digest,
)
from carbon.orchestration import (
    CompletedDevelopmentOrchestration,
    DevelopmentEvaluationOrchestrator,
    DevelopmentOrchestrationRequest,
    OrchestrationHandle,
    ResultOwnerRefs,
    reconstruction_outcome_digest,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentRepeatPlan,
    DevelopmentReplica,
    development_replicate_digest,
    development_request_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.service import PredictionReceipt, predict
from carbon.reconstruction.worker.controller import (
    IsolatedReconstructionController,
    WorkerRunResult,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import (
    DevelopmentWorkerProfile,
    WorkerImageIdentity,
)
from carbon.reexecution.model import (
    ComparisonDisposition,
    ExecutionProvenance,
    ExecutionResourceObservation,
    LinkedReexecutionRequest,
    ReexecutionBudget,
    ReplicaAuditBinding,
    ResourceObservationState,
)
from carbon.reexecution.report import write_reexecution_report_bundle
from carbon.reexecution.service import DevelopmentReexecutionService
from carbon.reexecution.store import ReexecutionJournal
from carbon.reference_runtime.controller import (
    IsolatedBurgersReferenceController,
    IsolatedReferenceResult,
)
from carbon.reference_runtime.model import (
    POLICY_ID as REFERENCE_POLICY_ID,
)
from carbon.reference_runtime.model import (
    POLICY_VERSION as REFERENCE_POLICY_VERSION,
)
from carbon.reference_runtime.model import (
    BurgersReferenceArtifact,
    BurgersReferenceRequest,
    BurgersReferenceRole,
    reference_settings,
    runtime_environment_digest,
)
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)
from carbon.seeding import DerivedSeed, EvaluationBinding, SeedPin


def _sha(label: str) -> str:
    return audit.digest_bytes(label.encode("ascii"))


def _data() -> Trajectories:
    points = 64
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack(
        (
            np.sin(2 * np.pi * positions),
            np.cos(2 * np.pi * positions),
            np.sin(4 * np.pi * positions) * 0.5,
            np.cos(4 * np.pi * positions) * 0.5,
        )
    )
    times = np.broadcast_to(np.array([0.05, 0.1]), (4, 2)).copy()
    solution = np.stack((initial * 0.98, initial * 0.96), axis=1)
    return Trajectories(
        initial,
        np.array([0.01, 0.02, 0.015, 0.025]),
        times,
        solution,
        positions,
        "train",
        "carbon_c10_public_synthetic_fixture",
    )


def _policy_digest() -> str:
    return audit.digest_bytes(
        audit.canonical_json(
            {"id": REFERENCE_POLICY_ID, "version": REFERENCE_POLICY_VERSION}
        )
    )


@dataclass(frozen=True, slots=True)
class NumericalRun:
    repeat: DevelopmentRepeatPlan
    replicas: tuple[DevelopmentReplica, ...]
    reconstruction: tuple[WorkerRunResult, ...]
    prediction_receipt: PredictionReceipt
    reference: IsolatedReferenceResult
    measurement_request: BurgersMeasurementRequest
    measurement: IsolatedMeasurementResult


def _replicas(
    *,
    role_index: int,
    challenge: ChallengeKey,
    plan,
    policy: ResearchResourcePolicyRef,
    resource: ResourceClassRef,
    archive: PublicTrainingArchive,
    query_digest: str,
) -> tuple[
    tuple[DevelopmentReplica, ...], tuple[DerivedSeed, ...], DevelopmentRepeatPlan
]:
    seeds = tuple(DerivedSeed(bytes([index + 1]) * 32) for index in range(3))
    replicas: list[DevelopmentReplica] = []
    for index, seed in enumerate(seeds):
        execution = ExecutionAttemptRef(
            SubmissionId(f"00000000-0000-4000-8000-000000000{role_index}{index:02d}"),
            1,
        )
        randomness = "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()
        placeholder = BoundReconstructionReplicate(
            ReconstructionReplicateIdentity(
                challenge,
                plan.to_ref(),
                policy,
                resource,
                f"reconstruction-replica-{index}",
                _sha(f"c10-placeholder-{role_index}-{index}"),
            )
        )
        replicas.append(
            DevelopmentReplica(
                BoundReconstructionReplicate(
                    replace(
                        placeholder.replicate_identity,
                        replicate_digest=development_replicate_digest(
                            binding=placeholder,
                            execution_ref=execution,
                            randomness_digest=randomness,
                            training_data_digest=archive.content_digest,
                            request_digest=query_digest,
                        ),
                    )
                ),
                execution,
                randomness,
            )
        )
    frozen = freeze_development_repeat_plan(
        plan_id=f"c10-public-audit-role-{role_index}",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=query_digest,
        replicas=tuple(replicas),
    )
    return tuple(replicas), seeds, frozen


def _binding(
    *,
    replica: DevelopmentReplica,
    challenge: ChallengeKey,
    plan,
    profile,
    policy: ResearchResourcePolicyRef,
) -> DurableExecutionBinding:
    return DurableExecutionBinding(
        ExecutionAttemptHandle(
            replica.execution_ref.submission_id,
            1,
            AdmissionKind.FIXTURE,
            SeedPin(
                challenge,
                "development-generator-v1",
                _sha("generator"),
                "development-score-v1",
                _sha("score-policy"),
                EvaluationBinding(b"d" * 32),
            ),
            ExecutionEnvironmentPin(profile.profile_id, profile.environment_digest),
        ),
        RequesterIdentity("c10-public-audit"),
        plan.strategy_hash,
        ExecutionScope.FIXTURE_DEVELOPMENT,
        plan.to_ref().content_digest,
        profile.profile_digest,
        policy.content_digest,
        _sha("protected-disabled"),
    )


def _run_numerical(
    *,
    root: Path,
    role: str,
    image: WorkerImageIdentity,
    challenge: ChallengeKey,
    plan,
    profile,
    policy: ResearchResourcePolicyRef,
    resource: ResourceClassRef,
    archive: PublicTrainingArchive,
    data: Trajectories,
    query: dict[str, np.ndarray],
    reference_request: BurgersReferenceRequest,
    replicas: tuple[DevelopmentReplica, ...],
    seeds: tuple[DerivedSeed, ...],
    repeat: DevelopmentRepeatPlan,
) -> NumericalRun:
    queue = DurableExecutionQueue(root / role / "reconstruction.sqlite3")
    controller = IsolatedReconstructionController(
        state_root=(root / role / "reconstruction").resolve(),
        execution_queue=queue,
        image=image,
    )
    reconstruction: list[WorkerRunResult] = []
    for index, (replica, seed) in enumerate(zip(replicas, seeds, strict=True)):
        queue.admit(
            _binding(
                replica=replica,
                challenge=challenge,
                plan=plan,
                profile=profile,
                policy=policy,
            )
        )
        claimed = queue.claim(
            replica.execution_ref,
            "c10-reconstruction-pool",
            claim_id=f"c10-{role}-reconstruction-{index}",
        )
        reconstruction.append(
            controller.execute(
                claimed=claimed,
                repeat_plan=repeat,
                replica=replica,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
            )
        )
    receipts = tuple(value.receipt for value in reconstruction)
    prediction, prediction_receipt = predict(receipts[0], **query)
    worker_profile = DevelopmentWorkerProfile(
        policy.content_digest, resource.content_digest
    )
    reference = IsolatedBurgersReferenceController(
        state_root=(root / role / "reference").resolve(),
        image=image,
        worker_profile=worker_profile,
    ).execute(reference_request)
    reference_artifact = BurgersReferenceArtifact(
        reference_request.request_digest,
        (3, 64),
        (reference.snapshot_path / "solution.f64le").read_bytes(),
    )
    candidate = FrozenFieldArtifact(
        prediction_receipt.request_digest,
        (3, 64),
        np.asarray(prediction[0], dtype="<f8").tobytes(order="C"),
        "CANDIDATE_PREDICTION",
    )
    frozen_reference = FrozenFieldArtifact(
        reference_request.request_digest,
        (3, 64),
        reference_artifact.payload,
        "REFERENCE_PRIMARY",
    )
    measurement_request = BurgersMeasurementRequest(
        case_digest=reference_request.case_digest,
        candidate_artifact_digest=candidate.artifact_digest,
        candidate_binding_digest=candidate.binding_digest,
        candidate_source_digest=receipts[0].source_digest,
        candidate_environment_digest=receipts[0].environment_digest,
        candidate_plan_digest=plan.to_ref().content_digest,
        candidate_replica_id="reconstruction-replica-0",
        reference_artifact_digest=frozen_reference.artifact_digest,
        reference_request_digest=reference_request.request_digest,
        reference_policy_digest=_policy_digest(),
        reference_environment_digest=reference_request.environment_digest,
        measurement_contract_digest=measurement_contract_digest(),
        measurement_environment_digest=measurement_environment_digest(),
        spatial_points=reference_request.spatial_points,
        requested_times=reference_request.requested_times,
        initial_values=tuple(float(value) for value in data.initial[0]),
        domain_length=1.0,
        viscosity=float(data.viscosity[0]),
        characteristic_time=1.0,
        amplitude=1.0,
        k_rms=2.0 * np.pi,
    )
    measurement = IsolatedBurgersMeasurementController(
        state_root=(root / role / "measurement").resolve(),
        image=image,
        worker_profile=worker_profile,
    ).execute(measurement_request, candidate, frozen_reference)
    assert (
        measurement.result.disposition
        is MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
    )
    return NumericalRun(
        repeat,
        replicas,
        tuple(reconstruction),
        prediction_receipt,
        reference,
        measurement_request,
        measurement,
    )


def _evidence(
    *,
    image: WorkerImageIdentity,
    challenge: ChallengeKey,
    plan,
    profile,
    policy: ResearchResourcePolicyRef,
    resource: ResourceClassRef,
    archive: PublicTrainingArchive,
    run: NumericalRun,
    reference_request: BurgersReferenceRequest,
) -> audit.DevelopmentEvidenceBinding:
    method = reference_request.document()["method"]
    assert type(method) is dict
    receipts = tuple(value.receipt for value in run.reconstruction)
    return audit.DevelopmentEvidenceBinding(
        submission_id="00000000-0000-4000-8000-000000000c10",
        strategy_digest=plan.strategy_hash.value,
        challenge_id=challenge.challenge_id,
        challenge_version=challenge.version,
        generator_digest=_sha("generator"),
        target_population_digest=_sha("public-synthetic-population"),
        sampling_plan_digest=_sha("one-case-c10-service-smoke"),
        training_data_commitment=archive.content_digest,
        reconstruction_plan_digest=plan.to_ref().content_digest,
        repeat_plan_digest=run.repeat.plan_digest,
        resource_policy_digest=policy.content_digest,
        reconstruction_outcome_digest=reconstruction_outcome_digest(
            run.repeat, receipts
        ),
        reconstruction_attempt_digests=tuple(item.artifact_digest for item in receipts),
        inference_request_digest=run.prediction_receipt.request_digest,
        prediction_digest=run.prediction_receipt.output_digest,
        reference_policy_digest=_policy_digest(),
        reference_implementation_digest=method["implementation_digest"],
        reference_environment_digest=reference_request.environment_digest,
        reference_artifact_digest=run.reference.result.artifact_digest,
        measurement_contract_digest=measurement_contract_digest(),
        measurement_implementation_digest=run.measurement_request.implementation_digest,
        measurement_environment_digest=measurement_environment_digest(),
        measurement_result_digest=run.measurement.result.result_digest,
        scoring_policy_digest=_sha("score-policy"),
        dossier_digest=_sha("public-synthetic-development-dossier"),
        qualification_manifest_digest=_sha("unqualified-development-manifest"),
        source_tree_digest=image.source_tree_digest,
        worker_image_digest=image.image_id,
        execution_policy_digest=DevelopmentWorkerProfile(
            policy.content_digest, resource.content_digest
        ).digest,
    )


def _orchestration_request(
    *, evidence: audit.DevelopmentEvidenceBinding, attempt: int, plan, profile
) -> DevelopmentOrchestrationRequest:
    challenge = ChallengeKey(evidence.challenge_id, evidence.challenge_version)
    return DevelopmentOrchestrationRequest(
        DurableExecutionBinding(
            ExecutionAttemptHandle(
                SubmissionId(evidence.submission_id),
                attempt,
                AdmissionKind.FIXTURE,
                SeedPin(
                    challenge,
                    "development-generator-v1",
                    evidence.generator_digest,
                    "development-score-v1",
                    evidence.scoring_policy_digest,
                    EvaluationBinding(b"o" * 32),
                ),
                ExecutionEnvironmentPin(
                    "c10-development", evidence.worker_image_digest
                ),
            ),
            RequesterIdentity("c10-public-audit"),
            plan.strategy_hash,
            ExecutionScope.FIXTURE_DEVELOPMENT,
            plan.to_ref().content_digest,
            profile.profile_digest,
            evidence.resource_policy_digest,
            _sha("protected-disabled"),
        ),
        evidence,
        _sha("public-synthetic-sine-case"),
        (_sha("reference-request-placeholder"),),
        (_sha("measurement-request-placeholder"),),
    )


def _request_with_actual_inputs(
    request: DevelopmentOrchestrationRequest,
    reference_request: BurgersReferenceRequest,
    run: NumericalRun,
) -> DevelopmentOrchestrationRequest:
    return dataclasses.replace(
        request,
        case_manifest_digest=reference_request.case_digest,
        reference_request_digests=(reference_request.request_digest,),
        measurement_request_digests=(run.measurement.result.request_digest,),
    )


def _complete(
    *,
    orchestrator: DevelopmentEvaluationOrchestrator,
    request: DevelopmentOrchestrationRequest,
    run: NumericalRun,
    handle: OrchestrationHandle,
    signer: audit.DevelopmentReceiptSigner,
    receipt_id: str,
    attempt: int,
) -> CompletedDevelopmentOrchestration:
    receipts = tuple(value.receipt for value in run.reconstruction)
    orchestrator.record_generator_manifest(handle, request.case_manifest_digest)
    orchestrator.record_reconstruction(handle, run.repeat, receipts)
    orchestrator.record_prediction(handle, run.prediction_receipt)
    orchestrator.record_reference(handle, run.reference.result)
    orchestrator.record_measurement(handle, run.measurement.result)
    orchestrator.record_unresolved_score(handle)
    return orchestrator.finalize_complete(
        handle,
        receipt_id=receipt_id,
        signer=signer,
        evidence_index=audit.FrozenEvidenceIndex(
            frozenset(request.evidence.required_evidence_digests())
        ),
        result_owners=ResultOwnerRefs(
            f"c10-development-card-{attempt}",
            f"c10-development-transcript-{attempt}",
            _sha(f"c10-development-transcript-{attempt}"),
        ),
        started_at_micros=2_000 * attempt,
        finished_at_micros=2_000 * attempt + 1_000,
        verified_at_micros=10_000,
    )


def _launch_identity(launch_digest: str, scope: str) -> str:
    return audit.digest_bytes(
        audit.canonical_json({"launch": launch_digest, "scope": scope})
    )


def _provenance(
    *, role: str, image: WorkerImageIdentity, run: NumericalRun
) -> ExecutionProvenance:
    launches = tuple(
        [_launch_identity(item.launch_digest, role) for item in run.reconstruction]
        + [
            _launch_identity(run.reference.launch_digest, role),
            _launch_identity(run.measurement.launch_digest, role),
        ]
    )
    return ExecutionProvenance(
        execution_id=f"c10-{role}-execution",
        host_id=os.environ.get("CARBON_C10_HOST_ID", "c10-linux-service-host"),
        administrator_trust_domain="carbon-development-host-admins",
        hardware_identity_digest=_sha("linux-x86-64-cpu-service-host"),
        source_tree_digest=image.source_tree_digest,
        worker_image_digest=image.image_id,
        worker_launch_digests=launches,
        scratch_scope_digests=tuple(
            _sha(f"c10-{role}-scratch-{index}") for index in range(5)
        ),
    )


def _resources(run: NumericalRun) -> ExecutionResourceObservation:
    workers = (*run.reconstruction, run.reference, run.measurement)
    wall = sum(float(value.timings["total"]) for value in workers)
    cpu_usec = 0
    peak_memory = 0
    output_bytes = 0
    oom_events = 0
    complete = True
    for value in workers:
        observation = (
            value.resource_observation
            if isinstance(value, WorkerRunResult)
            else value.resources
        )
        cpu = observation.get("cpu")
        memory = observation.get("memory")
        output = observation.get("output_snapshot")
        if not isinstance(cpu, dict) or not isinstance(cpu.get("usage_usec"), int):
            complete = False
        else:
            cpu_usec += cpu["usage_usec"]
        if not isinstance(memory, dict) or not isinstance(
            memory.get("peak_bytes"), int
        ):
            complete = False
        else:
            peak_memory = max(peak_memory, memory["peak_bytes"])
        events = memory.get("events") if isinstance(memory, dict) else None
        if not isinstance(events, dict) or not isinstance(events.get("oom_kill"), int):
            complete = False
        else:
            oom_events += events["oom_kill"]
        if not isinstance(output, dict) or not isinstance(
            output.get("observed_bytes"), int
        ):
            complete = False
        else:
            output_bytes += output["observed_bytes"]
    return ExecutionResourceObservation(
        ResourceObservationState.PARTIAL,
        wall,
        cpu_usec / 1_000_000 if complete else None,
        peak_memory if complete else None,
        None,
        output_bytes if complete else None,
        oom_events if complete else None,
    )


def test_real_linked_primary_and_reexecution_are_fresh_and_non_official(
    tmp_path: Path,
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    report_root = os.environ.get("CARBON_C10_REPORT_ROOT")
    key_hex = os.environ.get("CARBON_C10_DEVELOPMENT_SIGNING_KEY_HEX")
    assert manifest, "required service lane must supply the exact image manifest"
    assert report_root, "required service lane must supply a report destination"
    assert key_hex, "required service lane must supply an external DEVELOPMENT key"
    image = load_image_identity(Path(manifest))
    private_key = bytes.fromhex(key_hex)
    assert len(private_key) == 32
    challenge = ChallengeKey("burgers-dynamics-v1", "1.0")
    plan = compile_c02_plan(tmp_path, challenge_key=challenge)
    profile = compile_development_profile(plan)
    data = _data()
    train_path = tmp_path / "public-train.npz"
    data.save(train_path)
    archive = PublicTrainingArchive.from_file(
        train_path, provenance="c10_public_synthetic_train"
    )
    query = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": np.array([[0.0, 0.05, 0.1]], dtype=np.float64),
        "positions": data.positions,
    }
    policy = ResearchResourcePolicyRef(
        challenge,
        "c10-development-policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("c03-resource-policy"),
    )
    resource = ResourceClassRef(
        challenge,
        "c10-linux-x86-64-cpu",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("c03-resource-class"),
    )
    reference_request = BurgersReferenceRequest(
        case_digest=_sha("public-synthetic-sine-case"),
        role=BurgersReferenceRole.CANDIDATE_PRIMARY,
        spatial_points=tuple(float(value) for value in data.positions),
        requested_times=(0.0, 0.05, 0.1),
        domain_length=1.0,
        viscosity=float(data.viscosity[0]),
        mean=0.0,
        cosine_coefficients=(0.0,) * 12,
        sine_coefficients=(1.0,) + (0.0,) * 11,
        environment_digest=runtime_environment_digest(),
        settings=reference_settings(BurgersReferenceRole.CANDIDATE_PRIMARY, 64),
    )
    primary_replicas, seeds, primary_repeat = _replicas(
        role_index=1,
        challenge=challenge,
        plan=plan,
        policy=policy,
        resource=resource,
        archive=archive,
        query_digest=development_request_digest(query),
    )
    reexecution_replicas, repeated_seeds, reexecution_repeat = _replicas(
        role_index=2,
        challenge=challenge,
        plan=plan,
        policy=policy,
        resource=resource,
        archive=archive,
        query_digest=development_request_digest(query),
    )
    primary_run = _run_numerical(
        root=tmp_path,
        role="primary",
        image=image,
        challenge=challenge,
        plan=plan,
        profile=profile,
        policy=policy,
        resource=resource,
        archive=archive,
        data=data,
        query=query,
        reference_request=reference_request,
        replicas=primary_replicas,
        seeds=seeds,
        repeat=primary_repeat,
    )
    primary_evidence = _evidence(
        image=image,
        challenge=challenge,
        plan=plan,
        profile=profile,
        policy=policy,
        resource=resource,
        archive=archive,
        run=primary_run,
        reference_request=reference_request,
    )
    primary_request = _request_with_actual_inputs(
        _orchestration_request(
            evidence=primary_evidence, attempt=1, plan=plan, profile=profile
        ),
        reference_request,
        primary_run,
    )
    signer = audit.DevelopmentReceiptSigner(
        key_id="c10-service-external-development-key",
        private_key=private_key,
        valid_from_micros=1_000,
        valid_until_micros=20_000,
    )
    queue = DurableExecutionQueue(tmp_path / "orchestration.sqlite3")
    ledger = audit.DevelopmentEvidenceLedger(
        tmp_path / "evidence.sqlite3", (signer.verification_key,)
    )
    orchestrator = DevelopmentEvaluationOrchestrator(queue, ledger)
    primary_handle = orchestrator.begin(
        primary_request,
        worker_id="c10-primary-orchestrator",
        claim_id="c10-primary-claim",
    )
    primary_result = _complete(
        orchestrator=orchestrator,
        request=primary_request,
        run=primary_run,
        handle=primary_handle,
        signer=signer,
        receipt_id="c10-primary-service-receipt",
        attempt=1,
    )

    expected_receipts = tuple(
        dataclasses.replace(
            item.receipt,
            execution_id=(
                f"{replica.execution_ref.submission_id.value}:"
                f"{replica.execution_ref.attempt_number}"
            ),
        )
        for item, replica in zip(
            primary_run.reconstruction, reexecution_replicas, strict=True
        )
    )
    expected_run = dataclasses.replace(
        primary_run,
        repeat=reexecution_repeat,
        replicas=reexecution_replicas,
        reconstruction=tuple(
            dataclasses.replace(item, receipt=receipt)
            for item, receipt in zip(
                primary_run.reconstruction, expected_receipts, strict=True
            )
        ),
    )
    reexecution_evidence = _evidence(
        image=image,
        challenge=challenge,
        plan=plan,
        profile=profile,
        policy=policy,
        resource=resource,
        archive=archive,
        run=expected_run,
        reference_request=reference_request,
    )
    reexecution_request = _request_with_actual_inputs(
        _orchestration_request(
            evidence=reexecution_evidence, attempt=2, plan=plan, profile=profile
        ),
        reference_request,
        expected_run,
    )
    linked = LinkedReexecutionRequest(
        request_id="c10-real-linked-reexecution",
        primary_request=primary_request,
        primary_result=primary_result,
        reexecution_request=reexecution_request,
        replicas=tuple(
            ReplicaAuditBinding(
                primary.binding.replicate_identity.replicate_id,
                primary.randomness_digest,
                primary.binding.replicate_identity.replicate_digest,
                repeated.binding.replicate_identity.replicate_digest,
            )
            for primary, repeated in zip(
                primary_replicas, reexecution_replicas, strict=True
            )
        ),
        budget=ReexecutionBudget(policy.content_digest),
        worker_id="c10-reexecution-orchestrator",
        claim_id="c10-reexecution-claim",
    )
    service = DevelopmentReexecutionService(
        orchestrator,
        ledger,
        ReexecutionJournal(tmp_path / "reexecution.sqlite3"),
    )
    reexecution_handle = service.launch(linked).handle
    reexecution_run = _run_numerical(
        root=tmp_path,
        role="reexecution",
        image=image,
        challenge=challenge,
        plan=plan,
        profile=profile,
        policy=policy,
        resource=resource,
        archive=archive,
        data=data,
        query=query,
        reference_request=reference_request,
        replicas=reexecution_replicas,
        seeds=repeated_seeds,
        repeat=reexecution_repeat,
    )
    assert (
        tuple(value.receipt.artifact_digest for value in reexecution_run.reconstruction)
        == reexecution_evidence.reconstruction_attempt_digests
    )
    assert (
        reexecution_run.prediction_receipt.output_digest
        == reexecution_evidence.prediction_digest
    )
    assert (
        reexecution_run.reference.result.artifact_digest
        == reexecution_evidence.reference_artifact_digest
    )
    assert (
        reexecution_run.measurement.result.result_digest
        == reexecution_evidence.measurement_result_digest
    )
    assert (
        reexecution_run.measurement.result.request_digest
        in reexecution_request.measurement_request_digests
    )
    reexecution_result = _complete(
        orchestrator=orchestrator,
        request=reexecution_request,
        run=reexecution_run,
        handle=reexecution_handle,
        signer=signer,
        receipt_id="c10-reexecution-service-receipt",
        attempt=2,
    )
    primary_provenance = _provenance(role="primary", image=image, run=primary_run)
    repeated_provenance = _provenance(
        role="reexecution", image=image, run=reexecution_run
    )
    outcome = service.associate_completed(
        linked,
        reexecution_result,
        primary_provenance=primary_provenance,
        reexecution_provenance=repeated_provenance,
        primary_resources=_resources(primary_run),
        reexecution_resources=_resources(reexecution_run),
        verified_at_micros=10_000,
    )
    assert outcome.disposition is ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT
    assert outcome.scientific_resolution is False
    assert outcome.official is False
    assert set(primary_provenance.worker_launch_digests).isdisjoint(
        repeated_provenance.worker_launch_digests
    )
    relation = queue.relation(reexecution_request.execution.ref)
    assert relation is not None
    assert relation.kind is ExecutionRelationKind.REEXECUTION_OF
    paths = write_reexecution_report_bundle(Path(report_root).resolve(), outcome)
    assert all(path.is_file() for path in paths)
    reviewer = json.loads(paths[1].read_text(encoding="ascii"))
    assert reviewer["independence"] == {
        "administratively_independent": False,
        "distinct_administrator_trust_domain_identities": False,
        "fresh_execution_identity": True,
        "fresh_worker_launches": True,
        "same_host": True,
        "separate_scratch": True,
    }
    assert set(
        json.loads(paths[2].read_text(encoding="ascii"))["authority"].values()
    ) == {False}
