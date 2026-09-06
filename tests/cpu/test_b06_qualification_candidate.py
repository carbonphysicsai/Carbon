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
from tests.cpu.test_b06_evidence_manifests import manifest

DIGESTS = tuple(f"sha256:{character * 64}" for character in "abcdef0123456789")
CANDIDATE_CHALLENGE = ChallengeKey("qualification-candidate", "1.0")


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
    origin = qualification.StructuralOrigin.REGISTERED_REFERENCE
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
        origin = ref.origin
    elif type(ref) is qualification.DossierEvidenceManifestRef:
        object_id = ref.manifest_id
        object_version = ref.manifest_version
        content_digest = ref.content_digest
        origin = ref.origin
    elif type(ref) is qualification.SignerArtifactRef:
        object_id = ref.artifact_id
        object_version = ref.artifact_version
        content_digest = ref.content_digest
        origin = ref.origin
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
        origin,
    )


def candidate_fixture(
    *,
    include_inputs=False,
    manifests_override=None,
    signers_override=None,
    dossier_supersedes=None,
):
    challenge = CANDIDATE_CHALLENGE
    signers = signers_override or populated_signers(challenge)
    manifests = manifests_override or tuple(
        manifest(slot, challenge=challenge) for slot in qualification.DOSSIER_SLOT_ORDER
    )
    dossier = qualification.ValidationDossier(
        challenge,
        "validation-dossier",
        "2.0" if dossier_supersedes is not None else "1.0",
        tuple(
            qualification.DossierSection(
                challenge,
                item.slot,
                qualification.EvidenceRequirement.REQUIRED,
                qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
                qualification.EvidenceSectionStatus.PASS,
                (qualification.dossier_evidence_ref(item),),
            )
            for item in manifests
        ),
        signers,
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
        dossier_supersedes,
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


def rebuild_candidate(candidate, dossier, manifests, artifact_set, slot_bindings):
    return qualification.build_qualification_manifest_candidate(
        candidate_id=candidate.candidate_id,
        candidate_version=candidate.candidate_version,
        dossier=dossier,
        evidence_manifests=manifests,
        artifact_set=artifact_set,
        registry_slot_bindings=slot_bindings,
        expected_registry_qualification_digest=candidate.expected_registry_qualification_digest,
    )


def fixture_derived_manifest(path):
    slot = (
        qualification.DossierSlot.D4
        if path == "accounting_attempt"
        else qualification.DossierSlot.D1
    )
    value = manifest(slot, challenge=CANDIDATE_CHALLENGE)
    if path == "outer_origin":
        return replace(value, origin=qualification.StructuralOrigin.FIXTURE_ONLY)
    if path == "evidence_ref":
        fixture_ref = replace(
            value.evidence_refs[0],
            origin=qualification.StructuralOrigin.FIXTURE_ONLY,
        )
        return replace(
            value,
            evidence_refs=(fixture_ref,),
            claim_bindings=(
                replace(value.claim_bindings[0], evidence_ref=fixture_ref),
            ),
        )
    if path == "accounting_attempt":
        assert value.accounting is not None
        first = value.accounting.attempts[0]
        fixture_attempt = replace(
            first,
            attempt_ref=replace(
                first.attempt_ref,
                origin=qualification.StructuralOrigin.FIXTURE_ONLY,
            ),
        )
        return replace(
            value,
            accounting=replace(
                value.accounting,
                attempts=(fixture_attempt, *value.accounting.attempts[1:]),
            ),
        )
    if path == "limitation":
        primary = value.evidence_refs[0]
        limitation_ref = qualification.DossierEvidenceRef(
            CANDIDATE_CHALLENGE,
            qualification.DossierEvidenceClass.RESIDUAL_LIMITATION,
            "fixture-limitation",
            "1.0",
            DIGESTS[14],
            qualification.StructuralOrigin.FIXTURE_ONLY,
        )
        assert value.subject_bindings is not None
        limitation = qualification.LimitationBinding(
            CANDIDATE_CHALLENGE,
            limitation_ref,
            (primary,),
            (qualification.DOSSIER_PRIMARY_CLAIM_ROLE[value.slot],),
            value.subject_bindings.claim_scope_ref,
        )
        return replace(
            value,
            evidence_refs=(*value.evidence_refs, limitation_ref),
            limitations=(limitation,),
        )
    if path == "predecessor":
        predecessor = replace(value, origin=qualification.StructuralOrigin.FIXTURE_ONLY)
        return manifest(
            slot,
            challenge=CANDIDATE_CHALLENGE,
            version="2.0",
            supersedes=qualification.evidence_manifest_ref(predecessor),
        )
    raise AssertionError(path)


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
    assert (
        candidate.dossier_ref.origin
        is qualification.StructuralOrigin.REGISTERED_REFERENCE
    )
    assert all(
        item.manifest_ref.origin is qualification.StructuralOrigin.REGISTERED_REFERENCE
        for item in candidate.evidence_manifest_bindings
    )


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
    assert caught.value.code is qualification.DossierInputCode.MISSING_EVIDENCE


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("evidence_id", "unrelated-d1-manifest"),
        ("evidence_version", "2.0"),
        ("content_digest", DIGESTS[13]),
        ("origin", qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED),
    ),
)
def test_builder_requires_each_complete_section_to_link_its_exact_manifest(
    field, replacement
) -> None:
    (
        candidate,
        _,
        _,
        dossier,
        manifests,
        artifact_set,
        slot_bindings,
    ) = candidate_fixture(include_inputs=True)
    section = dossier.sections[0]
    wrong_ref = replace(section.evidence_refs[0], **{field: replacement})
    wrong_section = replace(section, evidence_refs=(wrong_ref,))
    wrong_dossier = replace(dossier, sections=(wrong_section, *dossier.sections[1:]))
    with pytest.raises(qualification.DossierValidationError) as caught:
        rebuild_candidate(
            candidate, wrong_dossier, manifests, artifact_set, slot_bindings
        )
    assert caught.value.code is qualification.DossierInputCode.MISSING_EVIDENCE


def test_section_rejects_wrong_slot_class_and_supplemental_only_substitution() -> None:
    _, _, _, dossier, _, _, _ = candidate_fixture(include_inputs=True)
    d1 = dossier.sections[0]
    d2 = dossier.sections[1]
    with pytest.raises(qualification.DossierValidationError) as wrong_class:
        replace(d1, evidence_refs=d2.evidence_refs)
    assert wrong_class.value.code is qualification.DossierInputCode.SLOT_MISMATCH
    supplemental = replace(
        d1.evidence_refs[0],
        evidence_class=qualification.DossierEvidenceClass.RESIDUAL_LIMITATION,
    )
    with pytest.raises(qualification.DossierValidationError) as supplemental_only:
        replace(d1, evidence_refs=(supplemental,))
    assert supplemental_only.value.code is qualification.DossierInputCode.SLOT_MISMATCH


def test_builder_rejects_wrong_slot_and_cross_challenge_manifest_graphs() -> None:
    (
        candidate,
        _,
        _,
        dossier,
        manifests,
        artifact_set,
        slot_bindings,
    ) = candidate_fixture(include_inputs=True)
    with pytest.raises(qualification.DossierValidationError) as wrong_slot:
        rebuild_candidate(
            candidate,
            dossier,
            (manifests[1], manifests[0], *manifests[2:]),
            artifact_set,
            slot_bindings,
        )
    assert wrong_slot.value.code is qualification.DossierInputCode.SLOT_MISMATCH

    crossed = manifest(
        qualification.DossierSlot.D1,
        challenge=ChallengeKey("other-challenge", "1.0"),
    )
    with pytest.raises(qualification.DossierValidationError) as cross_challenge:
        rebuild_candidate(
            candidate,
            dossier,
            (crossed, *manifests[1:]),
            artifact_set,
            slot_bindings,
        )
    assert cross_challenge.value.code is qualification.DossierInputCode.CROSS_CHALLENGE


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
    if field in {"dossier", "evidence"}:
        manifests = tuple(
            manifest(
                slot,
                challenge=CANDIDATE_CHALLENGE,
                origin=(
                    qualification.StructuralOrigin.FIXTURE_ONLY
                    if slot is qualification.DossierSlot.D1
                    else qualification.StructuralOrigin.REGISTERED_REFERENCE
                ),
            )
            for slot in qualification.DOSSIER_SLOT_ORDER
        )
        candidate, record, authorizations = candidate_fixture(
            manifests_override=manifests
        )
    else:
        candidate, record, authorizations = candidate_fixture()
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
    result = compare(candidate, record, authorizations)
    assert not result.machine_prerequisites_satisfied
    assert reason in result.reasons


@pytest.mark.parametrize(
    "path",
    (
        "outer_origin",
        "evidence_ref",
        "accounting_attempt",
        "limitation",
        "predecessor",
    ),
)
def test_every_evidence_fixture_path_reaches_refs_candidate_and_comparison(
    path,
) -> None:
    fixture_manifest = fixture_derived_manifest(path)
    manifests = tuple(
        (
            fixture_manifest
            if slot is fixture_manifest.slot
            else manifest(slot, challenge=CANDIDATE_CHALLENGE)
        )
        for slot in qualification.DOSSIER_SLOT_ORDER
    )
    candidate, record, authorizations = candidate_fixture(manifests_override=manifests)
    manifest_ref = qualification.evidence_manifest_ref(fixture_manifest)
    section_ref = qualification.dossier_evidence_ref(fixture_manifest)
    assert manifest_ref.origin is qualification.StructuralOrigin.FIXTURE_ONLY
    assert section_ref.origin is qualification.StructuralOrigin.FIXTURE_ONLY
    assert candidate.dossier_ref.origin is qualification.StructuralOrigin.FIXTURE_ONLY
    loaded = qualification.load_qualification_candidate(
        qualification.qualification_candidate_bytes(candidate)
    )
    assert loaded.dossier_ref.origin is qualification.StructuralOrigin.FIXTURE_ONLY
    result = compare(loaded, record, authorizations)
    assert qualification.QualificationMismatchReason.DOSSIER_FIXTURE_DERIVED in (
        result.reasons
    )
    assert qualification.QualificationMismatchReason.EVIDENCE_FIXTURE_DERIVED in (
        result.reasons
    )
    assert qualification.QualificationMismatchReason.ARTIFACT_FIXTURE_DERIVED in (
        result.reasons
    )
    assert not result.machine_prerequisites_satisfied


def test_fixture_signer_and_dossier_predecessor_are_preserved_end_to_end() -> None:
    base_signers = populated_signers(CANDIDATE_CHALLENGE)
    fixture_identity = replace(
        base_signers[0].identity_ref,
        origin=qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    fixture_signature = replace(
        base_signers[0].signature_ref,
        origin=qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    fixture_authorization = replace(
        base_signers[0].authorization_evidence_ref,
        origin=qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    fixture_signers = (
        replace(
            base_signers[0],
            identity_ref=fixture_identity,
            signature_ref=fixture_signature,
            authorization_evidence_ref=fixture_authorization,
        ),
        *base_signers[1:],
    )
    signer_candidate, signer_record, signer_authorizations = candidate_fixture(
        signers_override=fixture_signers
    )
    signer_round_trip = qualification.load_qualification_candidate(
        qualification.qualification_candidate_bytes(signer_candidate)
    )
    signer_result = compare(signer_round_trip, signer_record, signer_authorizations)
    assert qualification.QualificationMismatchReason.DOSSIER_FIXTURE_DERIVED in (
        signer_result.reasons
    )
    assert qualification.QualificationMismatchReason.SIGNER_FIXTURE_DERIVED in (
        signer_result.reasons
    )
    assert qualification.QualificationMismatchReason.ARTIFACT_FIXTURE_DERIVED in (
        signer_result.reasons
    )
    assert not signer_result.machine_prerequisites_satisfied

    _, _, _, predecessor, _, _, _ = candidate_fixture(include_inputs=True)
    fixture_section = replace(
        predecessor.sections[0],
        evidence_refs=(
            replace(
                predecessor.sections[0].evidence_refs[0],
                origin=qualification.StructuralOrigin.FIXTURE_ONLY,
            ),
        ),
    )
    predecessor = replace(
        predecessor,
        sections=(fixture_section, *predecessor.sections[1:]),
    )
    successor_candidate, successor_record, successor_authorizations = candidate_fixture(
        dossier_supersedes=qualification.dossier_ref(predecessor)
    )
    assert (
        successor_candidate.dossier_ref.origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )
    successor_result = compare(
        successor_candidate, successor_record, successor_authorizations
    )
    assert qualification.QualificationMismatchReason.DOSSIER_FIXTURE_DERIVED in (
        successor_result.reasons
    )
    assert not successor_result.machine_prerequisites_satisfied


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
