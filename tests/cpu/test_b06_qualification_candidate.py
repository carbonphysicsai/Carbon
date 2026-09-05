from __future__ import annotations

import json
import pickle
from dataclasses import replace

import pytest

from carbon import qualification
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    QualificationEvidence,
    QualificationManifest,
)
from tests.cpu.test_b06_dossier_foundation import complete_sections
from tests.cpu.test_b06_evidence_manifests import manifest

DIGESTS = tuple(f"sha256:{character * 64}" for character in "abcdef0123456789")


def signer_ref(challenge, role, kind, suffix):
    return qualification.SignerArtifactRef(
        challenge,
        role,
        kind,
        f"{role.value.lower().replace('_', '-')}-{suffix}",
        "1.0",
        DIGESTS[1],
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
    )


def populated_signers(challenge):
    return tuple(
        qualification.SignerBinding(
            challenge,
            role,
            qualification.SignerBindingState.POPULATED_UNVERIFIED,
            signer_ref(
                challenge,
                role,
                qualification.SignerArtifactKind.SIGNER_IDENTITY,
                "identity",
            ),
            signer_ref(
                challenge,
                role,
                qualification.SignerArtifactKind.SIGNATURE,
                "signature",
            ),
            signer_ref(
                challenge,
                role,
                qualification.SignerArtifactKind.AUTHORIZATION_EVIDENCE,
                "authorization",
            ),
        )
        for role in qualification.REQUIRED_SIGNER_ROLE_ORDER
    )


def artifact(challenge, artifact_id, kind, ref=None, *, digest=None):
    if ref is None:
        object_id = artifact_id
        object_version = "1.0"
        content_digest = digest or DIGESTS[2]
    elif type(ref) is MeasurementContractRef:
        object_id = artifact_id
        object_version = ref.schema_version
        content_digest = ref.content_digest
    elif type(ref) is qualification.ValidationDossierRef:
        object_id = ref.dossier_id
        object_version = ref.dossier_version
        content_digest = ref.content_digest
    elif type(ref) is qualification.DossierEvidenceManifestRef:
        object_id = ref.manifest_id
        object_version = ref.manifest_version
        content_digest = ref.content_digest
    elif type(ref) is qualification.SignerArtifactRef:
        object_id = ref.artifact_id
        object_version = ref.artifact_version
        content_digest = ref.content_digest
    else:
        object_id = ref.object_id
        object_version = ref.object_version
        content_digest = ref.content_digest
    return qualification.QualificationArtifactRef(
        challenge,
        artifact_id,
        kind,
        object_id,
        object_version,
        content_digest,
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
    )


def candidate_fixture(*, include_inputs=False):
    challenge = ChallengeKey("qualification-candidate", "1.0")
    signers = populated_signers(challenge)
    dossier = qualification.ValidationDossier(
        challenge,
        "validation-dossier",
        "1.0",
        complete_sections(challenge),
        signers,
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
    )
    manifests = tuple(
        manifest(slot, challenge=challenge) for slot in qualification.DOSSIER_SLOT_ORDER
    )
    subjects = manifests[0].subject_bindings
    assert subjects is not None
    dossier_ref = qualification.dossier_ref(dossier)
    artifacts = [
        artifact(
            challenge,
            "physical-system",
            qualification.QualificationArtifactKind.PHYSICAL_SYSTEM_SPEC,
            subjects.physical_system_ref,
        ),
        artifact(
            challenge,
            "claim-scope",
            qualification.QualificationArtifactKind.CLAIM_SCOPE,
            subjects.claim_scope_ref,
        ),
        artifact(
            challenge,
            "target-population",
            qualification.QualificationArtifactKind.TARGET_POPULATION,
            subjects.target_population_ref,
        ),
        artifact(
            challenge,
            "sampling-plan",
            qualification.QualificationArtifactKind.SAMPLING_PLAN,
            subjects.sampling_plan_ref,
        ),
        artifact(
            challenge,
            "generator",
            qualification.QualificationArtifactKind.GENERATOR,
            subjects.generator_ref,
        ),
        artifact(
            challenge,
            "reference-policy",
            qualification.QualificationArtifactKind.REFERENCE_POLICY,
            subjects.reference_policy_ref,
        ),
        artifact(
            challenge,
            "candidate-output",
            qualification.QualificationArtifactKind.CANDIDATE_OUTPUT_CONTRACT,
            subjects.candidate_output_ref,
        ),
        artifact(
            challenge,
            "representation",
            qualification.QualificationArtifactKind.REPRESENTATION_ADAPTER,
            subjects.representation_ref,
        ),
        artifact(
            challenge,
            "measurement-contract",
            qualification.QualificationArtifactKind.MEASUREMENT_CONTRACT,
            subjects.measurement_contract_ref,
        ),
        artifact(
            challenge,
            "validation-dossier",
            qualification.QualificationArtifactKind.VALIDATION_DOSSIER,
            dossier_ref,
        ),
    ]
    artifacts.extend(
        artifact(
            challenge,
            f"evidence-manifest-{item.slot.value.lower()}",
            qualification.QualificationArtifactKind.EVIDENCE_MANIFEST,
            qualification.evidence_manifest_ref(item),
        )
        for item in manifests
    )
    signer_kinds = {
        qualification.SignerArtifactKind.SIGNER_IDENTITY: qualification.QualificationArtifactKind.SIGNER_IDENTITY,
        qualification.SignerArtifactKind.SIGNATURE: qualification.QualificationArtifactKind.SIGNER_SIGNATURE,
        qualification.SignerArtifactKind.AUTHORIZATION_EVIDENCE: qualification.QualificationArtifactKind.SIGNER_AUTHORIZATION_EVIDENCE,
    }
    for binding in signers:
        for ref in (
            binding.identity_ref,
            binding.signature_ref,
            binding.authorization_evidence_ref,
        ):
            assert ref is not None
            artifacts.append(
                artifact(
                    challenge, ref.artifact_id, signer_kinds[ref.artifact_kind], ref
                )
            )
    slot_bindings = tuple(
        qualification.RegistryQualificationSlotBinding(
            slot, f"a3-{slot.replace('_', '-')}"
        )
        for slot, _ in REQUIRED_QUALIFICATION_STATES
    )
    artifacts.extend(
        artifact(
            challenge,
            item.registry_artifact_id,
            qualification.QualificationArtifactKind.A3_QUALIFICATION_ARTIFACT,
            digest=DIGESTS[3],
        )
        for item in slot_bindings
    )
    artifact_set = qualification.QualificationArtifactSet(
        challenge, "qualification-artifacts", "1.0", tuple(reversed(artifacts))
    )
    a3_manifest = QualificationManifest(
        challenge.challenge_id,
        challenge.version,
        "production",
        {
            slot: QualificationEvidence(
                state,
                slot_bindings[index].registry_artifact_id,
                "human-owned-assertion",
            )
            for index, (slot, state) in enumerate(REQUIRED_QUALIFICATION_STATES)
        },
        DIGESTS[4],
    )
    candidate = qualification.build_qualification_manifest_candidate(
        candidate_id="qualification-candidate",
        candidate_version="1.0",
        dossier=dossier,
        evidence_manifests=manifests,
        artifact_set=artifact_set,
        registry_slot_bindings=slot_bindings,
        expected_registry_qualification_digest=qualification.a3_qualification_snapshot_digest(
            a3_manifest
        ),
    )
    record = ChallengeRecord(
        challenge.challenge_id,
        challenge.version,
        fixture_origin=False,
        artifacts={
            item.registry_artifact_id: ArtifactBinding(digest=item.content_digest)
            for item in artifact_set.artifacts
        },
        qualification=a3_manifest,
        scientific_authoring_graph_fingerprint=DIGESTS[4],
    )
    authorizations = tuple(
        qualification.SignerAuthorizationResult(
            challenge,
            binding.signer_role,
            binding.identity_ref,
            binding.signature_ref,
            binding.authorization_evidence_ref,
            qualification.SignerIdentityValidation.STRUCTURALLY_VALID,
            qualification.SignerRoleAuthorization.AUTHORIZED_FOR_ROLE,
            qualification.SignatureVerification.CRYPTOGRAPHICALLY_VERIFIED,
        )
        for binding in signers
    )
    if include_inputs:
        return (
            candidate,
            record,
            authorizations,
            dossier,
            manifests,
            artifact_set,
            slot_bindings,
        )
    return candidate, record, authorizations


def compare(candidate, record, authorizations):
    return qualification.compare_qualification_candidate(
        candidate, record, authorizations
    )


def test_matching_candidate_is_only_machine_ready_and_does_not_mutate_a3() -> None:
    candidate, record, authorizations = candidate_fixture()
    before = (record.status, dict(record.artifacts), record.qualification)
    result = compare(candidate, record, authorizations)
    assert result.machine_prerequisites_satisfied
    assert result.reasons == ()
    assert (record.status, dict(record.artifacts), record.qualification) == before
    assert record.status == "draft"
    assert not hasattr(result, "scientifically_qualified")
    assert not hasattr(result, "live")


def test_candidate_canonical_round_trip_order_digest_and_reference() -> None:
    candidate, _, _ = candidate_fixture()
    encoded = qualification.qualification_candidate_bytes(candidate)
    assert qualification.load_qualification_candidate(encoded) == candidate
    assert (
        qualification.qualification_candidate_bytes(
            qualification.load_qualification_candidate(encoded)
        )
        == encoded
    )
    assert qualification.qualification_candidate_ref(
        candidate
    ).content_digest == qualification.qualification_candidate_digest(candidate)
    assert tuple(
        item.registry_artifact_id for item in candidate.artifact_set.artifacts
    ) == tuple(
        sorted(item.registry_artifact_id for item in candidate.artifact_set.artifacts)
    )
    assert "qualification-candidate" not in repr(candidate)
    with pytest.raises(TypeError):
        pickle.dumps(candidate)


def test_tampered_noncanonical_duplicate_and_trailing_documents_fail_closed() -> None:
    candidate, _, _ = candidate_fixture()
    encoded = qualification.qualification_candidate_bytes(candidate)
    payload = json.loads(
        encoded[len(qualification.QUALIFICATION_CANDIDATE_DOCUMENT_HEADER) :]
    )
    payload["candidate_version"] = "2.0"
    tampered = (
        qualification.QUALIFICATION_CANDIDATE_DOCUMENT_HEADER
        + json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )
    loaded = qualification.load_qualification_candidate(tampered)
    assert qualification.qualification_candidate_digest(
        loaded
    ) != qualification.qualification_candidate_digest(candidate)
    damaged = encoded.replace(
        b'"artifact_set_digest":"sha256:',
        b'"artifact_set_digest":"sha256:0',
        1,
    )
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_qualification_candidate(damaged)
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_qualification_candidate(encoded + b"\n")
    duplicate = (
        qualification.QUALIFICATION_CANDIDATE_DOCUMENT_HEADER
        + b'{"record_type":"qualification_manifest_candidate","record_type":"qualification_manifest_candidate"}'
    )
    with pytest.raises(qualification.DossierCanonicalError) as caught:
        qualification.load_qualification_candidate(duplicate)
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY


def test_wrong_challenge_and_lifecycle_are_distinct() -> None:
    candidate, record, authorizations = candidate_fixture()
    wrong = replace(record, challenge_id="other-challenge")
    result = compare(candidate, wrong, authorizations)
    assert result.reasons == (
        qualification.QualificationMismatchReason.CHALLENGE_KEY_MISMATCH,
    )
    wrong_version = replace(record, version="2.0")
    assert compare(candidate, wrong_version, authorizations).reasons == (
        qualification.QualificationMismatchReason.CHALLENGE_KEY_MISMATCH,
    )
    live = replace(record, status="live")
    assert compare(candidate, live, authorizations).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_LIFECYCLE_INCOMPATIBLE,
    )
    fixture = replace(
        record,
        fixture_origin=True,
        status="fixture",
        qualification=replace(record.qualification, mode="fixture"),
    )
    assert compare(candidate, fixture, authorizations).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_LIFECYCLE_INCOMPATIBLE,
        qualification.QualificationMismatchReason.REGISTRY_FIXTURE_ORIGIN,
        qualification.QualificationMismatchReason.REGISTRY_QUALIFICATION_MODE_MISMATCH,
        qualification.QualificationMismatchReason.REGISTRY_QUALIFICATION_DIGEST_MISMATCH,
    )


def test_exact_registry_snapshot_slot_and_artifact_set_mismatches() -> None:
    candidate, record, authorizations = candidate_fixture()
    wrong_snapshot = replace(
        candidate, expected_registry_qualification_digest=DIGESTS[5]
    )
    assert compare(wrong_snapshot, record, authorizations).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_QUALIFICATION_DIGEST_MISMATCH,
    )
    wrong_manifest = replace(record.qualification, challenge_version="2.0")
    wrong_manifest_record = replace(record, qualification=wrong_manifest)
    wrong_manifest_candidate = replace(
        candidate,
        expected_registry_qualification_digest=qualification.a3_qualification_snapshot_digest(
            wrong_manifest
        ),
    )
    assert compare(
        wrong_manifest_candidate, wrong_manifest_record, authorizations
    ).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_QUALIFICATION_CHALLENGE_MISMATCH,
    )
    slots = dict(record.qualification.slots)
    slots["generator_envelope"] = replace(
        slots["generator_envelope"],
        state="WRONG",
        artifact_id="a3-generator-validation",
    )
    wrong_slot_record = replace(
        record, qualification=replace(record.qualification, slots=slots)
    )
    wrong_slot = replace(
        candidate,
        expected_registry_qualification_digest=qualification.a3_qualification_snapshot_digest(
            wrong_slot_record.qualification
        ),
    )
    assert compare(wrong_slot, wrong_slot_record, authorizations).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_SLOT_STATE_MISMATCH,
        qualification.QualificationMismatchReason.REGISTRY_SLOT_ARTIFACT_MISMATCH,
    )
    missing_slots = dict(record.qualification.slots)
    missing_slots.pop("generator_envelope")
    missing_slot_manifest = replace(record.qualification, slots=missing_slots)
    missing_slot_record = replace(record, qualification=missing_slot_manifest)
    missing_slot_candidate = replace(
        candidate,
        expected_registry_qualification_digest=qualification.a3_qualification_snapshot_digest(
            missing_slot_manifest
        ),
    )
    assert compare(
        missing_slot_candidate, missing_slot_record, authorizations
    ).reasons == (qualification.QualificationMismatchReason.REGISTRY_SLOT_MISSING,)
    assert compare(
        candidate,
        replace(record, scientific_authoring_graph_fingerprint=None),
        authorizations,
    ).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_AUTHORING_GRAPH_FINGERPRINT_MISSING,
    )
    assert compare(
        candidate,
        replace(record, scientific_authoring_graph_fingerprint=DIGESTS[12]),
        authorizations,
    ).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_AUTHORING_GRAPH_FINGERPRINT_MISMATCH,
    )
    missing = dict(record.artifacts)
    missing.pop("validation-dossier")
    assert compare(
        candidate, replace(record, artifacts=missing), authorizations
    ).reasons == (qualification.QualificationMismatchReason.REGISTRY_ARTIFACT_MISSING,)
    extra = dict(record.artifacts)
    extra["unexpected-artifact"] = ArtifactBinding(digest=DIGESTS[6])
    assert compare(
        candidate, replace(record, artifacts=extra), authorizations
    ).reasons == (
        qualification.QualificationMismatchReason.REGISTRY_ARTIFACT_UNEXPECTED,
    )


def test_dossier_measurement_and_generic_digest_mismatches_remain_distinct() -> None:
    candidate, record, authorizations = candidate_fixture()
    changed = dict(record.artifacts)
    changed["validation-dossier"] = ArtifactBinding(digest=DIGESTS[7])
    changed["measurement-contract"] = ArtifactBinding(digest=DIGESTS[8])
    changed["physical-system"] = ArtifactBinding(digest=DIGESTS[9])
    assert compare(
        candidate, replace(record, artifacts=changed), authorizations
    ).reasons == (
        qualification.QualificationMismatchReason.DOSSIER_DIGEST_MISMATCH,
        qualification.QualificationMismatchReason.MEASUREMENT_SET_MISMATCH,
        qualification.QualificationMismatchReason.REGISTRY_ARTIFACT_DIGEST_MISMATCH,
    )


def test_duplicate_and_uncovered_artifacts_are_rejected_at_construction() -> None:
    candidate, _, _ = candidate_fixture()
    first = candidate.artifact_set.artifacts[0]
    with pytest.raises(qualification.DossierValidationError) as duplicate:
        replace(
            candidate.artifact_set, artifacts=(*candidate.artifact_set.artifacts, first)
        )
    assert duplicate.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY
    conflicting = replace(
        first,
        registry_artifact_id="conflicting-artifact",
        content_digest=DIGESTS[10],
    )
    with pytest.raises(qualification.DossierValidationError) as conflict:
        replace(
            candidate.artifact_set,
            artifacts=(*candidate.artifact_set.artifacts, conflicting),
        )
    assert conflict.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY
    extra = artifact(
        candidate.challenge_key,
        "orphan-artifact",
        qualification.QualificationArtifactKind.A3_QUALIFICATION_ARTIFACT,
    )
    with pytest.raises(qualification.DossierValidationError):
        replace(
            candidate,
            artifact_set=replace(
                candidate.artifact_set,
                artifacts=(*candidate.artifact_set.artifacts, extra),
            ),
        )


def test_builder_rejects_cross_section_object_version_drift() -> None:
    (
        candidate,
        _,
        _,
        dossier,
        manifests,
        artifact_set,
        slot_bindings,
    ) = candidate_fixture(include_inputs=True)
    first = manifests[0]
    subjects = first.subject_bindings
    assert subjects is not None
    drifted_physical = replace(
        subjects.physical_system_ref,
        object_version="2.0",
        content_digest=DIGESTS[11],
    )
    drifted = replace(
        first,
        subject_bindings=replace(subjects, physical_system_ref=drifted_physical),
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.build_qualification_manifest_candidate(
            candidate_id=candidate.candidate_id,
            candidate_version=candidate.candidate_version,
            dossier=dossier,
            evidence_manifests=(drifted, *manifests[1:]),
            artifact_set=artifact_set,
            registry_slot_bindings=slot_bindings,
            expected_registry_qualification_digest=candidate.expected_registry_qualification_digest,
        )
    assert caught.value.code is qualification.DossierInputCode.VERSION_MISMATCH


@pytest.mark.parametrize(
    ("field", "reason"),
    (
        ("dossier", qualification.QualificationMismatchReason.DOSSIER_FIXTURE_DERIVED),
        (
            "evidence",
            qualification.QualificationMismatchReason.EVIDENCE_FIXTURE_DERIVED,
        ),
        (
            "artifact",
            qualification.QualificationMismatchReason.ARTIFACT_FIXTURE_DERIVED,
        ),
    ),
)
def test_fixture_propagation_fails_closed(field, reason) -> None:
    candidate, record, authorizations = candidate_fixture()
    if field == "dossier":
        candidate = replace(
            candidate, dossier_origin=qualification.StructuralOrigin.FIXTURE_ONLY
        )
    elif field == "evidence":
        binding = candidate.evidence_manifest_bindings[0]
        ref = replace(
            binding.manifest_ref, origin=qualification.StructuralOrigin.FIXTURE_ONLY
        )
        candidate = replace(
            candidate,
            evidence_manifest_bindings=(
                replace(binding, manifest_ref=ref),
                *candidate.evidence_manifest_bindings[1:],
            ),
        )
    else:
        changed = replace(
            candidate.artifact_set.artifacts[0],
            origin=qualification.StructuralOrigin.FIXTURE_ONLY,
        )
        candidate = replace(
            candidate,
            artifact_set=replace(
                candidate.artifact_set,
                artifacts=(changed, *candidate.artifact_set.artifacts[1:]),
            ),
        )
    assert reason in compare(candidate, record, authorizations).reasons


def test_placeholder_stale_and_superseded_evidence_fail_closed() -> None:
    candidate, record, authorizations = candidate_fixture()
    binding = replace(
        candidate.evidence_manifest_bindings[0],
        completeness=qualification.EvidenceCompleteness.INCOMPLETE_PLACEHOLDER,
        currentness=qualification.ArtifactCurrentness.SUPERSEDED,
    )
    artifact_value = replace(
        candidate.artifact_set.artifacts[0],
        currentness=qualification.ArtifactCurrentness.REVOKED,
    )
    candidate = replace(
        candidate,
        state=qualification.QualificationCandidateState.INCOMPLETE,
        dossier_currentness=qualification.ArtifactCurrentness.SUPERSEDED,
        evidence_manifest_bindings=(binding, *candidate.evidence_manifest_bindings[1:]),
        artifact_set=replace(
            candidate.artifact_set,
            artifacts=(artifact_value, *candidate.artifact_set.artifacts[1:]),
        ),
    )
    assert compare(candidate, record, authorizations).reasons[:5] == (
        qualification.QualificationMismatchReason.CANDIDATE_INCOMPLETE,
        qualification.QualificationMismatchReason.DOSSIER_STALE_OR_SUPERSEDED,
        qualification.QualificationMismatchReason.EVIDENCE_PLACEHOLDER,
        qualification.QualificationMismatchReason.EVIDENCE_STALE_OR_SUPERSEDED,
        qualification.QualificationMismatchReason.ARTIFACT_STALE_OR_SUPERSEDED,
    )


def test_signer_authorization_states_are_external_exact_and_fail_closed() -> None:
    candidate, record, authorizations = candidate_fixture()
    assert compare(candidate, record, ()).reasons == (
        qualification.QualificationMismatchReason.SIGNER_AUTHORIZATION_MISSING,
    )
    first = authorizations[0]
    unverified = replace(
        first,
        identity_validation=qualification.SignerIdentityValidation.UNVERIFIED,
        role_authorization=qualification.SignerRoleAuthorization.UNVERIFIED,
        signature_verification=qualification.SignatureVerification.UNVERIFIED,
    )
    assert compare(candidate, record, (unverified, *authorizations[1:])).reasons == (
        qualification.QualificationMismatchReason.SIGNER_IDENTITY_UNVERIFIED,
        qualification.QualificationMismatchReason.SIGNER_ROLE_UNAUTHORIZED,
        qualification.QualificationMismatchReason.SIGNATURE_UNVERIFIED,
    )
    with pytest.raises(qualification.DossierValidationError):
        replace(first, signer_role=qualification.REQUIRED_SIGNER_ROLE_ORDER[1])


def test_incomplete_candidates_remain_representable_but_cannot_be_ready() -> None:
    candidate, record, authorizations = candidate_fixture()
    binding = replace(
        candidate.evidence_manifest_bindings[0],
        completeness=qualification.EvidenceCompleteness.INCOMPLETE_MISSING,
    )
    incomplete = replace(
        candidate,
        state=qualification.QualificationCandidateState.INCOMPLETE,
        dossier_completeness=qualification.EvidenceCompleteness.INCOMPLETE_MISSING,
        evidence_manifest_bindings=(binding, *candidate.evidence_manifest_bindings[1:]),
    )
    assert compare(incomplete, record, authorizations).reasons[:3] == (
        qualification.QualificationMismatchReason.CANDIDATE_INCOMPLETE,
        qualification.QualificationMismatchReason.DOSSIER_INCOMPLETE,
        qualification.QualificationMismatchReason.EVIDENCE_MISSING,
    )
    with pytest.raises(qualification.DossierValidationError):
        replace(candidate, state=qualification.QualificationCandidateState.INCOMPLETE)


def test_multi_mismatch_order_is_enum_order_and_stable() -> None:
    candidate, record, _ = candidate_fixture()
    broken = replace(
        record,
        challenge_id="other-challenge",
        status="live",
        qualification=None,
        artifacts={},
    )
    first = compare(candidate, broken, ())
    second = compare(candidate, broken, ())
    assert first == second
    assert first.reasons == tuple(
        reason
        for reason in qualification.QualificationMismatchReason
        if reason in set(first.reasons)
    )
    assert (
        first.reasons[0]
        is qualification.QualificationMismatchReason.CHALLENGE_KEY_MISMATCH
    )
    assert (
        qualification.QualificationMismatchReason.REGISTRY_QUALIFICATION_MISSING
        in first.reasons
    )
    assert (
        qualification.QualificationMismatchReason.REGISTRY_ARTIFACT_MISSING
        in first.reasons
    )
