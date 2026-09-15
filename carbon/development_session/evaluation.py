"""Real isolated reconstruction and evaluator-owned measurement of a frozen cohort."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np

from carbon.construction import CompileAccepted
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
    SubmissionId,
)
from carbon.generators.burgers_dynamics import (
    DOMAIN_LENGTH,
    PublicDevelopmentRole,
    candidate_query,
)
from carbon.measurement_runtime.controller import IsolatedBurgersMeasurementController
from carbon.measurement_runtime.model import (
    FrozenFieldArtifact,
    MeasurementDisposition,
    build_measurement_request,
)
from carbon.orchestration.development_feedback import aggregate_development_feedback
from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionStatus
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    development_request_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reference_runtime.model import (
    BurgersReferenceArtifact,
    decode_reference_request,
)
from carbon.resource_policy import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)
from carbon.seeding import DerivedSeed

from .budget import SessionBudget
from .contracts import build_contracts
from .data import context, frozen_cases, write_once
from .prediction import isolated_predict
from .profile import CHALLENGE, canonical, digest, profile_digest, profile_document


def evaluate(
    root: Path,
    image_manifest: Path,
    strategy: dict[str, object],
    submission_id: str,
    requester,
    *,
    resume_completed_reconstruction: bool = False,
    execution_scope: ExecutionScope = ExecutionScope.FIXTURE_DEVELOPMENT,
):
    """Called only after the authenticated service admits the miner submission.

    Return domain-owned objects to the trusted C-07 handoff builder. They are
    never sent to the model. This method does not call a provider or chain signer.
    """
    started_at_micros = time.time_ns() // 1000
    if type(execution_scope) is not ExecutionScope:
        raise ValueError("exact trusted execution scope required")
    attempt = root / "evaluations" / submission_id
    attempt.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_once(attempt / "strategy.json", canonical(strategy))
    retained = None
    if (attempt / "dispatch.json").exists() and not resume_completed_reconstruction:
        raise ValueError(
            "evaluation already dispatched; reconcile retained worker journals"
        )
    if resume_completed_reconstruction:
        retained = json.loads((attempt / "dispatch.json").read_bytes())
        started_at_micros = int((attempt / "dispatch.json").stat().st_mtime_ns // 1000)
    compiled = build_contracts().compile(strategy)
    if type(compiled) is not CompileAccepted:
        raise ValueError("strategy rejected by B-02B")
    preparation = json.loads((root / "preparation.json").read_bytes())
    train = root / "public-train.npz"
    if (
        preparation["profile_digest"] != profile_digest()
        or digest(train.read_bytes()) != preparation["train_archive_digest"]
    ):
        raise ValueError("frozen session identity changed")
    plan = compiled.construction_plan
    profile = compile_development_profile(plan)
    image = load_image_identity(image_manifest)
    manifest = json.loads((root / "case-manifest.json").read_bytes())
    if image.image_id != manifest["worker_image"]:
        raise ValueError("worker image differs from frozen session")
    write_once(attempt / "construction-plan.json", plan.canonical_bytes())
    archive = PublicTrainingArchive.from_file(
        train, provenance="c_auth1_c04_train_only"
    )
    cases = tuple(
        case
        for case in frozen_cases(root)
        if case.coordinates.role is not PublicDevelopmentRole.TRAIN
    )
    queries = [
        candidate_query(case, grid_points=64, intervals_per_phase=4) for case in cases
    ]
    query = {
        "initial": np.array([q.initial_field for q in queries]),
        "viscosity": np.array([q.viscosity for q in queries]),
        "requested_times": np.array([q.requested_times for q in queries]),
        "positions": np.arange(64, dtype=np.float64) * DOMAIN_LENGTH / 64,
    }
    query_digest = development_request_digest(query)
    policy = ResearchResourcePolicyRef(
        CHALLENGE,
        "burgers-session-policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        profile_digest(),
    )
    resource = ResourceClassRef(
        CHALLENGE,
        "burgers-session-linux-cpu",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        digest(canonical(profile_document()["budget"])),
    )
    worker = DevelopmentWorkerProfile(policy.content_digest, resource.content_digest)
    seeds = tuple(
        (
            DerivedSeed(
                (attempt / f"replica-{index}-private-randomness.bin").read_bytes()
            )
            if retained
            else DerivedSeed(os.urandom(32))
        )
        for index in range(3)
    )
    replicas = []
    for index, seed in enumerate(seeds):
        execution = ExecutionAttemptRef(
            SubmissionId(
                retained["replicas"][index]["submission_id"]
                if retained
                else str(uuid.uuid4())
            ),
            1,
        )
        randomness = digest(seed.as_backend_bytes())
        write_once(
            attempt / f"replica-{index}-private-randomness.bin", seed.as_backend_bytes()
        )
        # The placeholder is used only while computing the self-independent
        # replicate digest; only the replaced, exact identity enters execution.
        bound = BoundReconstructionReplicate(
            ReconstructionReplicateIdentity(
                CHALLENGE,
                plan.to_ref(),
                policy,
                resource,
                f"replica-{index}",
                profile_digest(),
            )
        )
        identity = development_replicate_digest(
            binding=bound,
            execution_ref=execution,
            randomness_digest=randomness,
            training_data_digest=archive.content_digest,
            request_digest=query_digest,
        )
        replicas.append(
            DevelopmentReplica(
                BoundReconstructionReplicate(
                    replace(bound.replicate_identity, replicate_digest=identity)
                ),
                execution,
                randomness,
            )
        )
    repeat = freeze_development_repeat_plan(
        plan_id=f"session-{submission_id}",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=query_digest,
        replicas=tuple(replicas),
    )
    write_once(
        attempt / "dispatch.json",
        canonical(
            {
                "profile_digest": profile_digest(),
                "strategy_digest": plan.strategy_hash.value,
                "repeat_plan_digest": repeat.plan_digest,
                "request_digest": query_digest,
                "replicas": [
                    {
                        "submission_id": item.execution_ref.submission_id.value,
                        "replica_id": item.binding.replicate_identity.replicate_id,
                    }
                    for item in replicas
                ],
            }
        ),
    )
    queue = DurableExecutionQueue(attempt / "reconstruction.sqlite3")
    controller = IsolatedReconstructionController(
        state_root=attempt / "reconstruction", execution_queue=queue, image=image
    )
    budget = SessionBudget(root / "budget.sqlite3")
    receipts, runs = [], []
    for index, (replica, seed) in enumerate(zip(replicas, seeds, strict=True)):
        binding = DurableExecutionBinding(
            ExecutionAttemptHandle(
                replica.execution_ref.submission_id,
                1,
                (
                    AdmissionKind.FIXTURE
                    if execution_scope is ExecutionScope.FIXTURE_DEVELOPMENT
                    else AdmissionKind.PRODUCTION
                ),
                context(root).pin,
                ExecutionEnvironmentPin(profile.profile_id, profile.environment_digest),
            ),
            requester,
            plan.strategy_hash,
            execution_scope,
            plan.to_ref().content_digest,
            profile.profile_digest,
            policy.content_digest,
            profile_digest(),
        )
        queue.admit(binding)
        claimed = queue.claim(
            replica.execution_ref, "session-reconstruction", claim_id=f"replica-{index}"
        )
        if retained:
            status = controller.store.raw_status(
                f"{replica.execution_ref.submission_id.value}:1"
            )
            if not status or status["state"] != "ASSOCIATED":
                raise ValueError(
                    "resume requires every reconstruction already associated; no rerun authority"
                )
        run = budget.run_worker(
            (
                f"{submission_id}-train-{index}"
                if not retained
                else f"{submission_id}-verify-retained-{index}-{uuid.uuid4().hex}"
            ),
            lambda claimed=claimed, replica=replica, seed=seed: controller.execute(
                claimed=claimed,
                repeat_plan=repeat,
                replica=replica,
                plan=plan,
                training_archive=archive,
                derived_seed=seed,
            ),
        )
        runs.append(run)
        receipts.append(run.receipt)
        if run.receipt.status is not ReconstructionStatus.COMPLETE:
            raise ValueError(
                "reconstruction did not complete; retain all replicas and stop"
            )
    measurement_controller = IsolatedBurgersMeasurementController(
        state_root=attempt / "measurement", image=image, worker_profile=worker
    )
    cohorts = {"EVAL": [], "STRESS": []}
    evidence_rows = []
    predictions = []
    anchor = None
    for index, receipt in enumerate(receipts):
        replay_prediction = (
            retained is not None and (attempt / f"prediction-{index}").exists()
        )
        prediction, prediction_receipt = budget.run_worker(
            (
                f"{submission_id}-predict-{index}"
                if not replay_prediction
                else f"{submission_id}-verify-prediction-{index}-{uuid.uuid4().hex}"
            ),
            lambda receipt=receipt, index=index, replay_prediction=replay_prediction: (
                isolated_predict(
                    receipt,
                    query,
                    root=attempt / f"prediction-{index}",
                    image=image,
                    worker=worker,
                    replay_only=replay_prediction,
                )
            ),
        )
        predictions.append(prediction_receipt)
        for position, case in enumerate(cases):
            name = f"{case.coordinates.role.value.lower()}-{case.coordinates.cell:02d}"
            reference_request = decode_reference_request(
                json.loads((root / f"{name}-reference-request.json").read_bytes())
            )
            record = json.loads((root / f"{name}-reference-result.json").read_bytes())
            payload = Path(record["solution_path"]).read_bytes()
            if digest(payload) != record["payload_digest"]:
                raise ValueError("reference artifact changed")
            reference = BurgersReferenceArtifact(
                reference_request.request_digest, (13, 64), payload
            )
            candidate = FrozenFieldArtifact(
                prediction_receipt.request_digest,
                (13, 64),
                np.asarray(prediction[position], dtype="<f8").tobytes(order="C"),
                "CANDIDATE_PREDICTION",
            )
            frozen_reference = FrozenFieldArtifact(
                reference_request.request_digest, (13, 64), payload, "REFERENCE_PRIMARY"
            )
            request = build_measurement_request(
                case,
                reference_request,
                reference,
                candidate,
                candidate_source_digest=receipt.source_digest,
                candidate_environment_digest=receipt.environment_digest,
                candidate_plan_digest=plan.to_ref().content_digest,
                candidate_replica_id=f"reconstruction-replica-{index}",
            )
            result = budget.run_worker(
                f"{submission_id}-measure-{index}-{name}",
                lambda request=request, candidate=candidate, frozen_reference=frozen_reference: (
                    measurement_controller.execute(request, candidate, frozen_reference)
                ),
            )
            write_once(
                attempt / f"replica-{index}-{name}-measurement.json",
                canonical(result.result.document()),
            )
            write_once(
                attempt / f"replica-{index}-{name}-measurement-request.json",
                canonical(request.document()),
            )
            if (
                result.result.disposition
                is not MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
            ):
                raise ValueError("measurement incomplete; retain and stop")
            cohorts[case.coordinates.role.value].append((request, result.result))
            evidence_rows.append(
                {
                    "replica": index,
                    "role": case.coordinates.role.value,
                    "case_digest": reference_request.case_digest,
                    "measurement_request_digest": request.request_digest,
                    "measurement_result_digest": result.result.result_digest,
                    "candidate_artifact_digest": candidate.artifact_digest,
                    "reference_artifact_digest": reference.artifact_digest,
                }
            )
            if index == 0 and position == 0:
                anchor = (
                    prediction_receipt,
                    reference_request,
                    record,
                    request,
                    result.result,
                )
    feedback = aggregate_development_feedback(
        tuple((role, tuple(cohorts[role])) for role in ("EVAL", "STRESS")),
        expected_cases={
            role: frozenset(
                decode_reference_request(
                    json.loads(
                        (
                            root / f"{role.lower()}-{cell:02d}-reference-request.json"
                        ).read_bytes()
                    )
                ).case_digest
                for cell in range(12)
            )
            for role in ("EVAL", "STRESS")
        },
    )
    write_once(attempt / "feedback.json", canonical(feedback))
    dossier = {
        "schema": "carbon.burgers-session.evaluation-dossier.v1",
        "submission_id": submission_id,
        "profile_digest": profile_digest(),
        "case_manifest_digest": preparation["case_manifest_digest"],
        "strategy_digest": plan.strategy_hash.value,
        "repeat_plan_digest": repeat.plan_digest,
        "training_runs": 3,
        "training_steps": sum(item.completed_steps for item in receipts),
        "reconstruction_observations": [
            {"timings": item.timings, "resources": item.resource_observation}
            for item in runs
        ],
        "prediction_observations": [
            json.loads(
                (
                    attempt / f"prediction-{index}" / "controls-and-resources.json"
                ).read_bytes()
            )
            for index in range(3)
        ],
        "measurements": evidence_rows,
        "feedback_digest": digest(canonical(feedback)),
        "c07_anchor": "prospectively fixed replica-0 / EVAL cell-0; whole-cohort evidence bound by dossier",
        "accepted_improvement": None,
        "scientific_uncertainty": None,
    }
    write_once(attempt / "dossier.json", canonical(dossier))
    return {
        "plan": plan,
        "profile": profile,
        "archive": archive,
        "repeat": repeat,
        "receipts": tuple(receipts),
        "runs": tuple(runs),
        "anchor": anchor,
        "image": image,
        "worker": worker,
        "policy": policy,
        "dossier": dossier,
        "feedback": feedback,
        "attempt_root": attempt,
        "context": context(root),
        "started_at_micros": started_at_micros,
        "execution_scope": execution_scope,
    }
