"""Produce C-W1 source associations through C-08/C-07/C-06 domain owners."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from carbon import audit
from carbon.development_testnet.execution import write_source_handoff
from carbon.execution import DurableExecutionBinding, ExecutionScope
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    SubmissionId,
)
from carbon.miner_mcp import BindMode
from carbon.orchestration import (
    DevelopmentOrchestrationRequest,
    ResultOwnerRefs,
    reconstruction_outcome_digest,
    write_report_bundle,
)
from carbon.reference_runtime.protocol import validate_reference_snapshot

from .data import write_once
from .profile import CHALLENGE, canonical, digest, profile_digest, profile_document


def finish_handoff(connection, transport_ref, requester, numerical):
    if numerical.get("execution_scope") is not ExecutionScope.REAL_PATH_NON_LIVE:
        raise ValueError(
            "engineering fixture results cannot become authenticated real-path sources"
        )
    scope_document = numerical.get("profile_document", profile_document())
    scope_digest = numerical.get("profile_digest", profile_digest())
    if digest(canonical(scope_document)) != scope_digest:
        raise ValueError("numerical profile identity differs")
    root = connection.root
    plan, profile = numerical["plan"], numerical["profile"]
    image, worker = numerical["image"], numerical["worker"]
    dossier, receipts = numerical["dossier"], numerical["receipts"]
    submission = dossier["submission_id"]
    (
        prediction,
        reference_request,
        reference_record,
        measurement_request,
        measurement,
    ) = numerical["anchor"]
    reference = validate_reference_snapshot(
        Path(reference_record["solution_path"]).parent, reference_request
    )
    if reference.artifact_digest != reference_record["artifact_digest"]:
        raise ValueError("reference changed since preparation")
    method = reference_request.document()["method"]
    manifest_bytes = (root / "case-manifest.json").read_bytes()
    sampling = canonical(scope_document["sampling"])
    population = canonical(scope_document["physics"])
    qualification = canonical(
        {
            "schema": "carbon.burgers-session.unqualified.v1",
            "qualified": False,
            "scientific_limits": None,
            "uncertainty_limits": None,
        }
    )
    evidence = audit.DevelopmentEvidenceBinding(
        submission_id=submission,
        strategy_digest=plan.strategy_hash.value,
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        generator_digest=numerical["context"].pin.generator_digest,
        target_population_digest=digest(population),
        sampling_plan_digest=digest(sampling),
        training_data_commitment=numerical["archive"].content_digest,
        reconstruction_plan_digest=plan.to_ref().content_digest,
        repeat_plan_digest=numerical["repeat"].plan_digest,
        resource_policy_digest=numerical["policy"].content_digest,
        reconstruction_outcome_digest=reconstruction_outcome_digest(
            numerical["repeat"], receipts
        ),
        reconstruction_attempt_digests=tuple(item.artifact_digest for item in receipts),
        inference_request_digest=prediction.request_digest,
        prediction_digest=prediction.output_digest,
        reference_policy_digest=measurement_request.reference_policy_digest,
        reference_implementation_digest=method["implementation_digest"],
        reference_environment_digest=reference_request.environment_digest,
        reference_artifact_digest=reference.artifact_digest,
        measurement_contract_digest=measurement_request.measurement_contract_digest,
        measurement_implementation_digest=measurement_request.implementation_digest,
        measurement_environment_digest=measurement_request.measurement_environment_digest,
        measurement_result_digest=measurement.result_digest,
        scoring_policy_digest=scope_digest,
        dossier_digest=digest(canonical(dossier)),
        qualification_manifest_digest=digest(qualification),
        source_tree_digest=image.source_tree_digest,
        worker_image_digest=image.image_id,
        execution_policy_digest=worker.digest,
    )
    binding = DurableExecutionBinding(
        ExecutionAttemptHandle(
            SubmissionId(submission),
            1,
            AdmissionKind.PRODUCTION,
            replace(numerical["context"].pin, scoring_digest=scope_digest),
            ExecutionEnvironmentPin(profile.profile_id, profile.environment_digest),
        ),
        requester,
        plan.strategy_hash,
        ExecutionScope.REAL_PATH_NON_LIVE,
        plan.to_ref().content_digest,
        profile.profile_digest,
        numerical["policy"].content_digest,
        scope_digest,
    )
    request = DevelopmentOrchestrationRequest(
        binding,
        evidence,
        digest(manifest_bytes),
        (reference_request.request_digest,),
        (measurement_request.request_digest,),
    )
    handle = connection.service.bind_orchestration(
        transport_ref,
        request,
        worker_id="burgers-session-controller",
        claim_id=f"session-{submission}",
        mode=BindMode.START,
    )
    owner = connection.orchestrator
    owner.record_generator_manifest(handle, request.case_manifest_digest)
    owner.record_reconstruction(handle, numerical["repeat"], receipts)
    owner.record_prediction(handle, prediction)
    owner.record_reference(handle, reference)
    owner.record_measurement(handle, measurement)
    owner.record_unresolved_score(handle)
    finished = time.time_ns() // 1000
    complete = owner.finalize_complete(
        handle,
        receipt_id=f"burgers-session-{submission}",
        signer=connection.signer,
        evidence_index=audit.FrozenEvidenceIndex(
            frozenset(evidence.required_evidence_digests())
        ),
        result_owners=ResultOwnerRefs(
            f"development-card-{submission}",
            f"development-dossier-{submission}",
            evidence.dossier_digest,
        ),
        started_at_micros=numerical["started_at_micros"],
        finished_at_micros=finished,
        verified_at_micros=finished,
    )
    connection.service.record_outcome(complete.account)
    export = root / "exports" / submission
    reports = write_report_bundle(export, complete)
    for name, payload in (
        ("population.json", population),
        ("sampling.json", sampling),
        ("qualification.json", qualification),
        ("case-manifest.json", manifest_bytes),
        ("profile.json", canonical(scope_document)),
        ("dossier.json", canonical(dossier)),
        ("feedback.json", canonical(numerical["feedback"])),
    ):
        write_once(export / name, payload)
    # Explicit bounded export members; never recurse over the private session
    # root, provider records, entropy, chain wallet or evidence signing key.
    attempt = numerical["attempt_root"]
    for source in (
        attempt / "strategy.json",
        attempt / "construction-plan.json",
        *sorted(attempt.glob("replica-*-measurement.json")),
    ):
        write_once(export / source.name, source.read_bytes())
    entries = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "digest": digest(path.read_bytes()),
        }
        for path in sorted(export.iterdir())
        if path.is_file() and path.name != "export-manifest.json"
    ]
    if len(entries) > 1024 or sum(item["bytes"] for item in entries) > 2 * 1024**3:
        raise ValueError("bounded export exceeded")
    export_manifest = export / "export-manifest.json"
    write_once(
        export_manifest,
        canonical(
            {
                "schema": "carbon.development-testnet.bounded-export-manifest.v1",
                "entries": entries,
            }
        ),
    )
    write_source_handoff(
        root / f"source-{submission}.json",
        intent_identity=f"burgers-session-{submission}",
        publication_journal=root / "publication.sqlite3",
        transport_journal=connection.transport,
        evidence_ledger=connection.ledger,
        verification_keys=(connection.signer.verification_key,),
        account_report=reports[0],
        ledger_reference=complete.ledger_reference,
        authenticated_request_receipt=transport_ref,
        export_manifest=export_manifest,
    )
    return complete
