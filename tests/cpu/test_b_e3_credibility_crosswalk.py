from __future__ import annotations

from dataclasses import replace

import pytest

from carbon import qualification
from carbon.registry import ChallengeKey
from tests.cpu.test_b06_evidence_manifests import DIGEST_A, manifest


def use_ref(
    challenge: ChallengeKey,
    kind: qualification.CredibilityRefKind,
    identity: str,
    *,
    currentness: qualification.ArtifactCurrentness = qualification.ArtifactCurrentness.CURRENT,
):
    return qualification.CredibilityRef(
        challenge,
        kind,
        f"{identity}-{kind.value.lower().replace('_', '-')}",
        "1.0",
        DIGEST_A,
        currentness,
    )


def complete_use_refs(challenge: ChallengeKey, identity: str):
    return tuple(
        use_ref(challenge, kind, identity)
        for kind in qualification.REQUIRED_AVAILABLE_REF_KINDS
    )


def source_kind_for(role: qualification.DossierClaimRole):
    return {
        qualification.DossierClaimRole.PHYSICAL_SYSTEM_ADEQUACY: (
            qualification.EvidenceSourceKind.EXPERIMENTAL_VALIDATION
        ),
        qualification.DossierClaimRole.CLAIM_ENVELOPE_ADEQUACY: (
            qualification.EvidenceSourceKind.EXPERIMENTAL_VALIDATION
        ),
        qualification.DossierClaimRole.TARGET_POPULATION_ADEQUACY: (
            qualification.EvidenceSourceKind.POPULATION_EVIDENCE
        ),
        qualification.DossierClaimRole.SAMPLING_PLAN_ADEQUACY: (
            qualification.EvidenceSourceKind.POPULATION_EVIDENCE
        ),
        qualification.DossierClaimRole.GENERATOR_IMPLEMENTATION_INTEGRITY: (
            qualification.EvidenceSourceKind.GENERATOR_CONFORMANCE
        ),
        qualification.DossierClaimRole.GENERATOR_DISTRIBUTION_CONFORMANCE: (
            qualification.EvidenceSourceKind.GENERATOR_CONFORMANCE
        ),
        qualification.DossierClaimRole.REFERENCE_ADEQUACY: (
            qualification.EvidenceSourceKind.CONVERGED_NUMERICAL_PRIMARY
        ),
        qualification.DossierClaimRole.REPRESENTATION_FIDELITY: (
            qualification.EvidenceSourceKind.REPRESENTATION_EVIDENCE
        ),
        qualification.DossierClaimRole.MEASUREMENT_ADEQUACY: (
            qualification.EvidenceSourceKind.MEASUREMENT_EVIDENCE
        ),
        qualification.DossierClaimRole.STATISTICAL_SUFFICIENCY: (
            qualification.EvidenceSourceKind.UNCERTAINTY_EVIDENCE
        ),
        qualification.DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC: (
            qualification.EvidenceSourceKind.DECISION_RESOLUTION
        ),
        qualification.DossierClaimRole.SECRECY_ROLE_SEPARATION: (
            qualification.EvidenceSourceKind.SECURITY_ROLE_SEPARATION
        ),
        qualification.DossierClaimRole.CENSORING_LIMITATIONS: (
            qualification.EvidenceSourceKind.LIMITATION_DISCLOSURE
        ),
    }[role]


def owner_for(role: qualification.DossierClaimRole):
    if role in {
        qualification.DossierClaimRole.STATISTICAL_SUFFICIENCY,
        qualification.DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC,
        qualification.DossierClaimRole.CENSORING_LIMITATIONS,
    }:
        return qualification.EvidenceOwnerRole.STATISTICS
    if role is qualification.DossierClaimRole.SECRECY_ROLE_SEPARATION:
        return qualification.EvidenceOwnerRole.SECURITY
    return qualification.EvidenceOwnerRole.PHYSICS_SCIML


def unavailable_source(challenge: ChallengeKey, kind, index: int):
    unresolved = use_ref(
        challenge,
        qualification.CredibilityRefKind.UNRESOLVED_INPUT,
        f"unavailable-{index}",
    )
    return qualification.CredibilityEvidenceSource(
        challenge,
        f"unavailable-source-{index}",
        "1.0",
        kind,
        qualification.EvidenceCategory.PROPOSED_CARBON_EXPERIMENT,
        qualification.EvidenceMaturity.UNAVAILABLE,
        qualification.EvidenceAvailability.ABSENT,
        qualification.EvidenceOwnerRole.INDEPENDENT_REVIEW,
        qualification.EvidenceIndependence.UNRESOLVED,
        qualification.EvidenceDisclosure.CARBON_PRIVATE,
        None,
        qualification.ArtifactCurrentness.CURRENT,
        (),
        (),
        (
            qualification.HumanInputBinding(
                unresolved,
                qualification.HumanInputDisposition.PENDING_REQUIRED,
            ),
        ),
    )


def graph():
    challenge = ChallengeKey("fixture-burgers", "1.0")
    manifests = tuple(
        manifest(
            slot,
            challenge=challenge,
            origin=qualification.StructuralOrigin.FIXTURE_ONLY,
        )
        for slot in qualification.DOSSIER_SLOT_ORDER
    )
    sources = []
    links = []
    used_kinds = set()
    source_index = 0
    for evidence_manifest in manifests:
        manifest_ref = qualification.evidence_manifest_ref(evidence_manifest)
        for binding in evidence_manifest.claim_bindings:
            source_index += 1
            source_id = f"source-{source_index}"
            source_kind = source_kind_for(binding.claim_role)
            used_kinds.add(source_kind)
            human_inputs = ()
            if (
                binding.claim_role
                is qualification.DossierClaimRole.CENSORING_LIMITATIONS
            ):
                human_inputs = (
                    qualification.HumanInputBinding(
                        use_ref(
                            challenge,
                            qualification.CredibilityRefKind.UNRESOLVED_INPUT,
                            source_id,
                        ),
                        qualification.HumanInputDisposition.PENDING_NON_BLOCKING,
                    ),
                )
            source = qualification.CredibilityEvidenceSource(
                challenge,
                source_id,
                "1.0",
                source_kind,
                qualification.EvidenceCategory.CARBON_TEST_EVIDENCE,
                qualification.EvidenceMaturity.TESTED,
                qualification.EvidenceAvailability.AVAILABLE,
                owner_for(binding.claim_role),
                qualification.EvidenceIndependence.SELF_REPORTED,
                (
                    qualification.EvidenceDisclosure.CARBON_PRIVATE
                    if source_index == 1
                    else qualification.EvidenceDisclosure.PUBLIC
                ),
                binding.evidence_ref,
                qualification.ArtifactCurrentness.CURRENT,
                (binding.claim_role,),
                complete_use_refs(challenge, source_id),
                human_inputs,
            )
            sources.append(source)
            links.append(
                qualification.ClaimEvidenceLink(
                    challenge,
                    evidence_manifest.slot,
                    manifest_ref,
                    binding.claim_scope_ref,
                    binding.claim_role,
                    owner_for(binding.claim_role),
                    source_id,
                    "1.0",
                    binding.evidence_ref,
                )
            )
    missing_kinds = set(qualification.REQUIRED_SOURCE_KINDS) - used_kinds
    sources.extend(
        unavailable_source(challenge, kind, index)
        for index, kind in enumerate(
            sorted(missing_kinds, key=lambda item: item.value), 1
        )
    )
    dossier_ref = qualification.ValidationDossierRef(
        challenge,
        "fixture-dossier",
        "1.0",
        DIGEST_A,
        qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    crosswalk = qualification.CredibilityCrosswalk(
        challenge,
        "fixture-credibility-crosswalk",
        "1.0",
        dossier_ref,
        tuple(qualification.evidence_manifest_ref(item) for item in manifests),
        tuple(sources),
        tuple(links),
        qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    return crosswalk, manifests


def replace_source(crosswalk, source_id: str, **changes):
    sources = tuple(
        replace(item, **changes) if item.source_id == source_id else item
        for item in crosswalk.sources
    )
    return replace(crosswalk, sources=sources)


def test_complete_synthetic_non_live_crosswalk_is_deterministic_and_non_authorizing():
    crosswalk, manifests = graph()
    assessment = qualification.validate_credibility_crosswalk(crosswalk, manifests)
    assert assessment.all_required_claims_supported is True
    assert assessment.certifies_scientific_adequacy is False
    assert crosswalk.effective_origin is qualification.StructuralOrigin.FIXTURE_ONLY
    assert qualification.credibility_crosswalk_bytes(crosswalk).startswith(
        qualification.CREDIBILITY_DOCUMENT_HEADER
    )
    assert (
        qualification.load_credibility_crosswalk(
            qualification.credibility_crosswalk_bytes(crosswalk)
        )
        == crosswalk
    )
    assert qualification.credibility_crosswalk_digest(crosswalk) == (
        qualification.credibility_crosswalk_digest(
            replace(
                crosswalk,
                sources=tuple(reversed(crosswalk.sources)),
                links=tuple(reversed(crosswalk.links)),
            )
        )
    )
    assert (
        qualification.credibility_crosswalk_ref(crosswalk).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )


def test_missing_evidence_and_exact_manifest_identity_mismatch_fail_closed():
    crosswalk, manifests = graph()
    missing = replace(crosswalk, links=crosswalk.links[:-1])
    with pytest.raises(qualification.CredibilityValidationError) as caught:
        qualification.validate_credibility_crosswalk(missing, manifests)
    assert (
        caught.value.code
        is qualification.CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE
    )

    changed_ref = replace(
        crosswalk.evidence_manifest_refs[0], content_digest="sha256:" + "f" * 64
    )
    mismatched = replace(
        crosswalk,
        evidence_manifest_refs=(changed_ref, *crosswalk.evidence_manifest_refs[1:]),
        links=tuple(
            (
                replace(item, evidence_manifest_ref=changed_ref)
                if item.slot is changed_ref.slot
                else item
            )
            for item in crosswalk.links
        ),
    )
    assessment = qualification.assess_credibility_crosswalk(mismatched, manifests)
    assert qualification.CredibilityIssueCode.IDENTITY_MISMATCH in {
        item.code for item in assessment.issues
    }


def test_stale_reference_and_maturity_escalation_fail_closed():
    crosswalk, manifests = graph()
    source = next(item for item in crosswalk.sources if item.evidence_ref is not None)
    stale = replace_source(
        crosswalk,
        source.source_id,
        evidence_currentness=qualification.ArtifactCurrentness.SUPERSEDED,
    )
    with pytest.raises(qualification.CredibilityValidationError) as caught:
        qualification.validate_credibility_crosswalk(stale, manifests)
    assert caught.value.code is qualification.CredibilityIssueCode.STALE_REFERENCE

    overstated = replace_source(
        crosswalk,
        source.source_id,
        maturity=qualification.EvidenceMaturity.PRODUCTION_QUALIFIED,
    )
    assessment = qualification.assess_credibility_crosswalk(overstated, manifests)
    assert qualification.CredibilityIssueCode.MATURITY_OVERSTATEMENT in {
        item.code for item in assessment.issues
    }


def test_circular_self_certification_and_required_human_input_fail_closed():
    crosswalk, manifests = graph()
    link = crosswalk.links[0]
    circular = replace_source(
        crosswalk,
        link.source_id,
        category=qualification.EvidenceCategory.INDEPENDENT_REPLICATION,
        maturity=qualification.EvidenceMaturity.REPLICATED,
        independence=qualification.EvidenceIndependence.EXTERNAL_INDEPENDENT,
        owner=link.claim_owner,
    )
    assessment = qualification.assess_credibility_crosswalk(circular, manifests)
    assert qualification.CredibilityIssueCode.CIRCULAR_SELF_CERTIFICATION in {
        item.code for item in assessment.issues
    }

    source = next(
        item for item in crosswalk.sources if item.source_id == link.source_id
    )
    pending = replace_source(
        crosswalk,
        link.source_id,
        human_inputs=(
            qualification.HumanInputBinding(
                use_ref(
                    crosswalk.challenge_key,
                    qualification.CredibilityRefKind.UNRESOLVED_INPUT,
                    source.source_id,
                ),
                qualification.HumanInputDisposition.PENDING_REQUIRED,
            ),
        ),
    )
    with pytest.raises(qualification.CredibilityValidationError) as caught:
        qualification.validate_credibility_crosswalk(pending, manifests)
    assert (
        caught.value.code
        is qualification.CredibilityIssueCode.UNRESOLVED_REQUIRED_HUMAN_INPUT
    )


def test_mms_source_kind_cannot_substitute_for_target_population_or_product_claims():
    crosswalk, manifests = graph()
    link = next(
        item
        for item in crosswalk.links
        if item.claim_role is qualification.DossierClaimRole.TARGET_POPULATION_ADEQUACY
    )
    substituted = replace_source(
        crosswalk,
        link.source_id,
        source_kind=qualification.EvidenceSourceKind.MMS_CODE_VERIFICATION,
    )
    assessment = qualification.assess_credibility_crosswalk(substituted, manifests)
    assert qualification.CredibilityIssueCode.UNSUPPORTED_SUBSTITUTION in {
        item.code for item in assessment.issues
    }
    forbidden = qualification.SOURCE_KIND_ALLOWED_CLAIMS[
        qualification.EvidenceSourceKind.MMS_CODE_VERIFICATION
    ]
    assert qualification.DossierClaimRole.CUSTOMER_CONTEXT_OF_USE not in forbidden
    assert qualification.DossierClaimRole.PRODUCT_QUALIFICATION not in forbidden
    assert qualification.DossierClaimRole.LIVE_ACTIVATION not in forbidden


def test_report_integrity_and_disclosure_are_audience_allow_listed():
    crosswalk, manifests = graph()
    private_link = crosswalk.links[0]
    private_source = next(
        item for item in crosswalk.sources if item.source_id == private_link.source_id
    )
    renamed_source = replace(private_source, source_id="hidden-seed-identity")
    renamed_link = replace(private_link, source_id="hidden-seed-identity")
    protected = replace(
        crosswalk,
        sources=tuple(
            renamed_source if item.source_id == private_source.source_id else item
            for item in crosswalk.sources
        ),
        links=tuple(
            renamed_link if item is private_link else item for item in crosswalk.links
        ),
    )
    public = qualification.render_credibility_report(
        protected, manifests, qualification.CredibilityReportAudience.PUBLIC
    )
    private = qualification.render_credibility_report(
        protected, manifests, qualification.CredibilityReportAudience.CARBON_PRIVATE
    )
    assert "hidden-seed-identity" not in public
    assert "WITHHELD" in public
    assert "hidden-seed-identity" in private
    assert qualification.credibility_crosswalk_digest(protected) not in public
    assert qualification.credibility_crosswalk_digest(protected) in private
    assert "Scientific adequacy certified: `NO`" in public
    assert "## Evidence-source inventory" in public
    assert qualification.EvidenceAvailability.ABSENT.value in public
    assert all(kind.value in public for kind in qualification.REQUIRED_SOURCE_KINDS)
    assert public == qualification.render_credibility_report(
        protected, manifests, qualification.CredibilityReportAudience.PUBLIC
    )


def test_canonical_import_rejects_duplicate_trailing_tampered_and_oversized_input():
    crosswalk, _ = graph()
    document = qualification.credibility_crosswalk_bytes(crosswalk)
    duplicate = document.replace(
        b'{"canonicalization_profile":',
        b'{"crosswalk_id":"duplicate","canonicalization_profile":',
        1,
    )
    malformed = (
        duplicate,
        document + b"x",
        document.replace(b'"CARBON_TEST_EVIDENCE"', b'"NOT_A_CATEGORY"', 1),
    )
    for candidate in malformed:
        with pytest.raises(qualification.CredibilityCanonicalError):
            qualification.load_credibility_crosswalk(candidate)
    with pytest.raises(qualification.CredibilityCanonicalError) as caught:
        qualification.load_credibility_crosswalk(
            b"x" * (qualification.MAX_CREDIBILITY_CROSSWALK_DOCUMENT_BYTES + 1)
        )
    assert caught.value.code is qualification.CredibilityIssueCode.SIZE_LIMIT


def test_errors_and_representations_do_not_echo_hostile_values():
    crosswalk, manifests = graph()
    missing = replace(crosswalk, links=crosswalk.links[:-1])
    with pytest.raises(qualification.CredibilityValidationError) as caught:
        qualification.validate_credibility_crosswalk(missing, manifests)
    assert "hidden" not in str(caught.value)
    assert repr(crosswalk) == "CredibilityCrosswalk(<protected>)"
    assert repr(crosswalk.sources[0]) == "CredibilityEvidenceSource(<protected>)"
