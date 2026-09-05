from __future__ import annotations

import json

import pytest

from carbon import qualification
from carbon.registry import ChallengeKey

DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64


def evidence(
    challenge: ChallengeKey,
    evidence_class: qualification.DossierEvidenceClass,
    *,
    identity: str,
    origin: qualification.StructuralOrigin = qualification.StructuralOrigin.REGISTERED_REFERENCE,
) -> qualification.DossierEvidenceRef:
    return qualification.DossierEvidenceRef(
        challenge, evidence_class, identity, "1.0", DIGEST, origin
    )


def complete_sections(
    challenge: ChallengeKey,
    *,
    fixture_slot: qualification.DossierSlot | None = None,
) -> tuple[qualification.DossierSection, ...]:
    return tuple(
        qualification.DossierSection(
            challenge,
            slot,
            qualification.EvidenceRequirement.REQUIRED,
            qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
            qualification.EvidenceSectionStatus.PASS,
            (
                evidence(
                    challenge,
                    qualification.DOSSIER_PRIMARY_EVIDENCE_CLASS[slot],
                    identity=f"evidence-{slot.value.lower()}",
                    origin=(
                        qualification.StructuralOrigin.FIXTURE_ONLY
                        if slot is fixture_slot
                        else qualification.StructuralOrigin.REGISTERED_REFERENCE
                    ),
                ),
            ),
        )
        for slot in qualification.DOSSIER_SLOT_ORDER
    )


def missing_signers(
    challenge: ChallengeKey,
) -> tuple[qualification.SignerBinding, ...]:
    return tuple(
        qualification.SignerBinding(
            challenge,
            role,
            qualification.SignerBindingState.REQUIRED_MISSING,
        )
        for role in qualification.REQUIRED_SIGNER_ROLE_ORDER
    )


def dossier(
    challenge: ChallengeKey | None = None,
    *,
    fixture_slot: qualification.DossierSlot | None = None,
    supersedes: qualification.ValidationDossierRef | None = None,
    version: str = "1.0",
) -> qualification.ValidationDossier:
    challenge = challenge or ChallengeKey("fixture-burgers", "1.0")
    return qualification.ValidationDossier(
        challenge,
        "validation-dossier",
        version,
        complete_sections(challenge, fixture_slot=fixture_slot),
        missing_signers(challenge),
        qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
        supersedes,
    )


def test_exact_slot_order_titles_and_primary_classes() -> None:
    assert tuple(slot.value for slot in qualification.DOSSIER_SLOT_ORDER) == tuple(
        f"D{index}" for index in range(1, 13)
    )
    assert tuple(qualification.DOSSIER_SLOT_TITLES.values()) == (
        "Physical-system adequacy",
        "Claim / envelope adequacy",
        "Target-population adequacy",
        "SamplingPlan / finite-evidence adequacy",
        "Generator implementation integrity",
        "Generator distribution conformance",
        "Reference / truth adequacy",
        "Representation fidelity",
        "Measurement adequacy and applicability",
        "Statistical sufficiency and estimand clarity",
        "Evaluation secrecy, decontamination, and role separation",
        "Censoring, limitations, and residual uncertainty",
    )
    assert len(set(qualification.DOSSIER_PRIMARY_EVIDENCE_CLASS.values())) == 12


def test_canonical_round_trip_digest_and_ref_are_deterministic() -> None:
    value = dossier()
    encoded = qualification.canonical_bytes(value)
    assert encoded.startswith(qualification.DOSSIER_DOCUMENT_HEADER)
    assert qualification.load_canonical_document(encoded) == value
    assert (
        qualification.canonical_bytes(qualification.load_canonical_document(encoded))
        == encoded
    )
    assert qualification.canonical_digest(value) == qualification.canonical_digest(
        value
    )
    assert qualification.dossier_ref(
        value
    ).content_digest == qualification.canonical_digest(value)


def test_noncanonical_and_duplicate_or_tampered_documents_fail_closed() -> None:
    value = dossier()
    encoded = qualification.canonical_bytes(value)
    payload = json.loads(encoded[len(qualification.DOSSIER_DOCUMENT_HEADER) :])
    noncanonical = qualification.DOSSIER_DOCUMENT_HEADER + json.dumps(payload).encode()
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_canonical_document(noncanonical)
    duplicate = (
        qualification.DOSSIER_DOCUMENT_HEADER
        + b'{"record_type":"validation_dossier","record_type":"validation_dossier"}'
    )
    with pytest.raises(qualification.DossierCanonicalError) as caught:
        qualification.load_canonical_document(duplicate)
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_canonical_document(encoded[:-1] + b"x")


@pytest.mark.parametrize(
    "completeness",
    (
        qualification.EvidenceCompleteness.INCOMPLETE_MISSING,
        qualification.EvidenceCompleteness.INCOMPLETE_PLACEHOLDER,
    ),
)
def test_missing_and_placeholder_states_are_explicitly_blocked(completeness) -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    section = qualification.DossierSection(
        challenge,
        qualification.DossierSlot.D1,
        qualification.EvidenceRequirement.REQUIRED,
        completeness,
        qualification.EvidenceSectionStatus.BLOCKED,
    )
    assert section.evidence_refs == ()
    with pytest.raises(qualification.DossierValidationError):
        qualification.DossierSection(
            challenge,
            qualification.DossierSlot.D1,
            qualification.EvidenceRequirement.REQUIRED,
            completeness,
            qualification.EvidenceSectionStatus.PASS,
        )


def test_placeholder_reference_identity_is_rejected() -> None:
    with pytest.raises(qualification.DossierValidationError) as caught:
        evidence(
            ChallengeKey("fixture-burgers", "1.0"),
            qualification.DossierEvidenceClass.PHYSICAL_SYSTEM_ADEQUACY,
            identity="placeholder",
        )
    assert caught.value.code is qualification.DossierInputCode.PLACEHOLDER_EVIDENCE


def test_supplemental_or_wrong_slot_evidence_cannot_substitute() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    for evidence_class in (
        qualification.DossierEvidenceClass.MMS_REFINEMENT_OBSERVED_ORDER,
        qualification.DossierEvidenceClass.TARGET_POPULATION_ADEQUACY,
    ):
        with pytest.raises(qualification.DossierValidationError) as caught:
            qualification.DossierSection(
                challenge,
                qualification.DossierSlot.D1,
                qualification.EvidenceRequirement.REQUIRED,
                qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
                qualification.EvidenceSectionStatus.PASS,
                (evidence(challenge, evidence_class, identity="wrong-evidence"),),
            )
        assert caught.value.code is qualification.DossierInputCode.SLOT_MISMATCH


def test_evidence_order_is_canonical_and_duplicate_identity_rejects() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    primary = evidence(
        challenge,
        qualification.DossierEvidenceClass.PHYSICAL_SYSTEM_ADEQUACY,
        identity="primary",
    )
    supplemental = evidence(
        challenge,
        qualification.DossierEvidenceClass.MMS_REFINEMENT_OBSERVED_ORDER,
        identity="supplemental",
    )
    forward = qualification.DossierSection(
        challenge,
        qualification.DossierSlot.D1,
        qualification.EvidenceRequirement.REQUIRED,
        qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
        qualification.EvidenceSectionStatus.PASS,
        (primary, supplemental),
    )
    reverse = qualification.DossierSection(
        challenge,
        qualification.DossierSlot.D1,
        qualification.EvidenceRequirement.REQUIRED,
        qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
        qualification.EvidenceSectionStatus.PASS,
        (supplemental, primary),
    )
    assert forward == reverse
    changed_digest = qualification.DossierEvidenceRef(
        challenge,
        primary.evidence_class,
        primary.evidence_id,
        primary.evidence_version,
        OTHER_DIGEST,
        primary.origin,
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.DossierSection(
            challenge,
            qualification.DossierSlot.D1,
            qualification.EvidenceRequirement.REQUIRED,
            qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
            qualification.EvidenceSectionStatus.PASS,
            (primary, changed_digest),
        )
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY


def test_requirement_rationale_rules_are_fail_closed() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    rationale = evidence(
        challenge,
        qualification.DossierEvidenceClass.RESIDUAL_LIMITATION,
        identity="rationale",
    )
    section = qualification.DossierSection(
        challenge,
        qualification.DossierSlot.D12,
        qualification.EvidenceRequirement.NOT_APPLICABLE_WITH_RATIONALE,
        qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
        qualification.EvidenceSectionStatus.NOT_APPLICABLE,
        rationale_ref=rationale,
    )
    assert section.rationale_ref == rationale
    with pytest.raises(qualification.DossierValidationError):
        qualification.DossierSection(
            challenge,
            qualification.DossierSlot.D12,
            qualification.EvidenceRequirement.NOT_APPLICABLE_WITH_RATIONALE,
            qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
            qualification.EvidenceSectionStatus.NOT_APPLICABLE,
        )


def signer_artifact(
    challenge: ChallengeKey,
    role: qualification.SignerRole,
    kind: qualification.SignerArtifactKind,
    identity: str,
    *,
    origin: qualification.StructuralOrigin = qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
) -> qualification.SignerArtifactRef:
    return qualification.SignerArtifactRef(
        challenge, role, kind, identity, "1.0", OTHER_DIGEST, origin
    )


def test_populated_signer_remains_unverified_and_role_bound() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    role = qualification.SignerRole.SECURITY
    binding = qualification.SignerBinding(
        challenge,
        role,
        qualification.SignerBindingState.POPULATED_UNVERIFIED,
        signer_artifact(
            challenge,
            role,
            qualification.SignerArtifactKind.SIGNER_IDENTITY,
            "identity",
        ),
        signer_artifact(
            challenge, role, qualification.SignerArtifactKind.SIGNATURE, "signature"
        ),
    )
    assert binding.state is qualification.SignerBindingState.POPULATED_UNVERIFIED
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.SignerBinding(
            challenge,
            role,
            qualification.SignerBindingState.POPULATED_UNVERIFIED,
            signer_artifact(
                challenge,
                role,
                qualification.SignerArtifactKind.SIGNATURE,
                "wrong-kind",
            ),
            signer_artifact(
                challenge, role, qualification.SignerArtifactKind.SIGNATURE, "signature"
            ),
        )
    assert caught.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_cross_challenge_section_and_wrong_signer_order_reject() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    other = ChallengeKey("other-challenge", "1.0")
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.ValidationDossier(
            challenge,
            "validation-dossier",
            "1.0",
            complete_sections(other),
            missing_signers(challenge),
            qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
        )
    assert caught.value.code is qualification.DossierInputCode.CROSS_CHALLENGE
    with pytest.raises(qualification.DossierValidationError):
        qualification.ValidationDossier(
            challenge,
            "validation-dossier",
            "1.0",
            complete_sections(challenge),
            tuple(reversed(missing_signers(challenge))),
            qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
        )


def test_supersession_is_same_challenge_dossier_and_different_version() -> None:
    prior = qualification.dossier_ref(dossier(version="1.0"))
    assert dossier(version="1.1", supersedes=prior).supersedes == prior
    with pytest.raises(qualification.DossierValidationError) as caught:
        dossier(version="1.0", supersedes=prior)
    assert caught.value.code is qualification.DossierInputCode.VERSION_MISMATCH
    wrong_challenge = qualification.ValidationDossierRef(
        ChallengeKey("other-challenge", "1.0"),
        prior.dossier_id,
        prior.dossier_version,
        prior.content_digest,
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        dossier(version="1.1", supersedes=wrong_challenge)
    assert caught.value.code is qualification.DossierInputCode.CROSS_CHALLENGE


def test_fixture_origin_propagates_without_qualification() -> None:
    value = dossier(fixture_slot=qualification.DossierSlot.D6)
    assert value.fixture_derived is True
    assert not any(
        name in qualification.__all__
        for name in (
            "activate",
            "qualify",
            "QualificationManifestCandidate",
            "ActiveRegistryComparator",
        )
    )
