"""Docker-backed C-07 public synthetic DEVELOPMENT vertical."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
from c02_fixtures import compile_c02_plan

from carbon import audit
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionScope,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.measurement_runtime.controller import IsolatedBurgersMeasurementController
from carbon.measurement_runtime.model import (
    BurgersMeasurementRequest,
    FrozenFieldArtifact,
    MeasurementDisposition,
    measurement_contract_digest,
    measurement_environment_digest,
)
from carbon.orchestration import (
    DevelopmentEvaluationOrchestrator,
    DevelopmentOrchestrationRequest,
    ResultOwnerRefs,
    reconstruction_outcome_digest,
    write_report_bundle,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionStatus
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    development_request_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.service import predict
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reference_runtime.controller import IsolatedBurgersReferenceController
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


def _data(points: int) -> Trajectories:
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
        "carbon_c07_public_synthetic_fixture",
    )


def _policy_digest() -> str:
    return audit.digest_bytes(
        audit.canonical_json(
            {"id": REFERENCE_POLICY_ID, "version": REFERENCE_POLICY_VERSION}
        )
    )


def test_real_numerical_vertical_produces_non_official_projection_bundle(
    tmp_path: Path,
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    report_root = os.environ.get("CARBON_C07_REPORT_ROOT")
    private_key_hex = os.environ.get("CARBON_C07_DEVELOPMENT_SIGNING_KEY_HEX")
    assert manifest, "required service lane must supply the exact image manifest"
    assert report_root, "required service lane must supply a report destination"
    assert (
        private_key_hex
    ), "required service lane must supply an external DEVELOPMENT key"
    private_key = bytes.fromhex(private_key_hex)
    assert len(private_key) == 32

    image = load_image_identity(Path(manifest))
    challenge = ChallengeKey("burgers-dynamics-v1", "1.0")
    plan = compile_c02_plan(tmp_path, challenge_key=challenge)
    profile = compile_development_profile(plan)
    data = _data(64)
    train_path = tmp_path / "public-train.npz"
    data.save(train_path)
    archive = PublicTrainingArchive.from_file(
        train_path, provenance="c07_public_synthetic_train"
    )
    query = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": np.array([[0.0, 0.05, 0.1]], dtype=np.float64),
        "positions": data.positions,
    }
    query_digest = development_request_digest(query)
    policy = ResearchResourcePolicyRef(
        challenge,
        "c07-development-policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("c03-resource-policy"),
    )
    resource = ResourceClassRef(
        challenge,
        "c07-linux-x86-64-cpu",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("c03-resource-class"),
    )
    seeds = tuple(DerivedSeed(bytes([index + 1]) * 32) for index in range(3))
    replicas = []
    for index, seed in enumerate(seeds):
        execution = ExecutionAttemptRef(
            SubmissionId(f"00000000-0000-4000-8000-00000000008{index}"), 1
        )
        randomness = "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()
        placeholder = BoundReconstructionReplicate(
            ReconstructionReplicateIdentity(
                challenge,
                plan.to_ref(),
                policy,
                resource,
                f"reconstruction-replica-{index}",
                _sha(f"placeholder-{index}"),
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
    repeat = freeze_development_repeat_plan(
        plan_id="c07-public-synthetic-three-replica",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=query_digest,
        replicas=tuple(replicas),
    )
    reconstruction_queue = DurableExecutionQueue(
        tmp_path / "reconstruction-execution.sqlite3"
    )
    reconstruction_controller = IsolatedReconstructionController(
        state_root=(tmp_path / "reconstruction-state").resolve(),
        execution_queue=reconstruction_queue,
        image=image,
    )
    receipts = []
    for index, (replica, seed) in enumerate(zip(replicas, seeds, strict=True)):
        execution_binding = DurableExecutionBinding(
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
            RequesterIdentity("c07-public-synthetic"),
            plan.strategy_hash,
            ExecutionScope.FIXTURE_DEVELOPMENT,
            plan.to_ref().content_digest,
            profile.profile_digest,
            policy.content_digest,
            _sha("protected-disabled"),
        )
        reconstruction_queue.admit(execution_binding)
        claimed = reconstruction_queue.claim(
            replica.execution_ref,
            "c07-reconstruction-pool",
            claim_id=f"c07-reconstruction-claim-{index}",
        )
        result = reconstruction_controller.execute(
            claimed=claimed,
            repeat_plan=repeat,
            replica=replica,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
        )
        assert result.receipt.status is ReconstructionStatus.COMPLETE
        receipts.append(result.receipt)

    prediction, prediction_receipt = predict(receipts[0], **query)
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
    worker_profile = DevelopmentWorkerProfile(
        policy.content_digest, resource.content_digest
    )
    reference_run = IsolatedBurgersReferenceController(
        state_root=(tmp_path / "reference-state").resolve(),
        image=image,
        worker_profile=worker_profile,
    ).execute(reference_request)
    reference_artifact = BurgersReferenceArtifact(
        reference_request.request_digest,
        (3, 64),
        (reference_run.snapshot_path / "solution.f64le").read_bytes(),
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
    measurement_run = IsolatedBurgersMeasurementController(
        state_root=(tmp_path / "measurement-state").resolve(),
        image=image,
        worker_profile=worker_profile,
    ).execute(measurement_request, candidate, frozen_reference)
    assert (
        measurement_run.result.disposition
        is MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
    )

    method = reference_request.document()["method"]
    assert type(method) is dict
    evidence = audit.DevelopmentEvidenceBinding(
        submission_id="00000000-0000-4000-8000-000000000090",
        strategy_digest=plan.strategy_hash.value,
        challenge_id=challenge.challenge_id,
        challenge_version=challenge.version,
        generator_digest=_sha("generator"),
        target_population_digest=_sha("public-synthetic-population"),
        sampling_plan_digest=_sha("one-case-service-smoke"),
        training_data_commitment=archive.content_digest,
        reconstruction_plan_digest=plan.to_ref().content_digest,
        repeat_plan_digest=repeat.plan_digest,
        resource_policy_digest=policy.content_digest,
        reconstruction_outcome_digest=reconstruction_outcome_digest(
            repeat, tuple(receipts)
        ),
        reconstruction_attempt_digests=tuple(item.artifact_digest for item in receipts),
        inference_request_digest=prediction_receipt.request_digest,
        prediction_digest=prediction_receipt.output_digest,
        reference_policy_digest=_policy_digest(),
        reference_implementation_digest=method["implementation_digest"],
        reference_environment_digest=reference_request.environment_digest,
        reference_artifact_digest=reference_run.result.artifact_digest,
        measurement_contract_digest=measurement_request.measurement_contract_digest,
        measurement_implementation_digest=measurement_request.implementation_digest,
        measurement_environment_digest=measurement_request.measurement_environment_digest,
        measurement_result_digest=measurement_run.result.result_digest,
        scoring_policy_digest=_sha("score-policy"),
        dossier_digest=_sha("public-synthetic-development-dossier"),
        qualification_manifest_digest=_sha("unqualified-development-manifest"),
        source_tree_digest=image.source_tree_digest,
        worker_image_digest=image.image_id,
        execution_policy_digest=worker_profile.digest,
    )
    orchestration_binding = DurableExecutionBinding(
        ExecutionAttemptHandle(
            SubmissionId(evidence.submission_id),
            1,
            AdmissionKind.FIXTURE,
            SeedPin(
                challenge,
                "development-generator-v1",
                evidence.generator_digest,
                "development-score-v1",
                evidence.scoring_policy_digest,
                EvaluationBinding(b"o" * 32),
            ),
            ExecutionEnvironmentPin("c07-development", image.image_id),
        ),
        RequesterIdentity("c07-public-synthetic"),
        plan.strategy_hash,
        ExecutionScope.FIXTURE_DEVELOPMENT,
        plan.to_ref().content_digest,
        profile.profile_digest,
        policy.content_digest,
        _sha("protected-disabled"),
    )
    signer = audit.DevelopmentReceiptSigner(
        key_id="c07-service-external-development-key",
        private_key=private_key,
        valid_from_micros=1_000,
        valid_until_micros=10_000,
    )
    queue = DurableExecutionQueue(tmp_path / "orchestration.sqlite3")
    ledger = audit.DevelopmentEvidenceLedger(
        tmp_path / "evidence.sqlite3", (signer.verification_key,)
    )
    orchestrator = DevelopmentEvaluationOrchestrator(queue, ledger)
    request = DevelopmentOrchestrationRequest(
        orchestration_binding,
        evidence,
        reference_request.case_digest,
        (reference_request.request_digest,),
        (measurement_request.request_digest,),
    )
    handle = orchestrator.begin(
        request, worker_id="c07-orchestrator", claim_id="c07-orchestration-claim"
    )
    orchestrator.record_generator_manifest(handle, request.case_manifest_digest)
    orchestrator.record_reconstruction(handle, repeat, tuple(receipts))
    orchestrator.record_prediction(handle, prediction_receipt)
    orchestrator.record_reference(handle, reference_run.result)
    orchestrator.record_measurement(handle, measurement_run.result)
    orchestrator.record_unresolved_score(handle)
    complete = orchestrator.finalize_complete(
        handle,
        receipt_id="c07-public-synthetic-service-receipt",
        signer=signer,
        evidence_index=audit.FrozenEvidenceIndex(
            frozenset(evidence.required_evidence_digests())
        ),
        result_owners=ResultOwnerRefs(
            "c07-development-card",
            "c07-development-transcript",
            _sha("c07-development-transcript"),
        ),
        started_at_micros=2_000,
        finished_at_micros=3_000,
        verified_at_micros=3_100,
    )
    paths = write_report_bundle(Path(report_root).resolve(), complete)
    assert all(path.is_file() for path in paths)
    public = json.loads(paths[2].read_text(encoding="ascii"))
    assert set(public["eligibility"].values()) == {False}
    assert public["disposition"] == "COMPLETE_UNRESOLVED"
