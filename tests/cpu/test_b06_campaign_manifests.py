from __future__ import annotations

import json
from dataclasses import fields, replace

import pytest

from carbon import qualification
from carbon.authoring.refs import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.measurement.enums import MeasurementDefinitionKind
from carbon.measurement.refs import MeasurementContractRef, MeasurementDefinitionRef
from carbon.qualification import campaign_canonical
from carbon.registry import ChallengeKey

DIGESTS = tuple("sha256:" + char * 64 for char in "abcdefghijklmnop")
CHALLENGE = ChallengeKey("fixture-campaign", "1.0")


def owned(kind: str, identity: str, challenge: ChallengeKey = CHALLENGE):
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(challenge),
        object_id=identity,
        object_version="1.0",
        content_digest=DIGESTS[0],
    )


def top(expected: type, identity: str, challenge: ChallengeKey = CHALLENGE):
    args = (
        challenge,
        identity,
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        DIGESTS[1],
    )
    if expected is InstanceDistributionContractRef:
        return expected(*args, "TARGET_WORKLOAD_P")
    return expected(*args)


def definition(
    kind: MeasurementDefinitionKind,
    identity: str | None = None,
    challenge: ChallengeKey = CHALLENGE,
):
    return MeasurementDefinitionRef(
        challenge,
        kind,
        identity or kind.value.lower().replace("_", "-"),
        "1.0",
        DIGESTS[2],
    )


def artifact(
    role: qualification.CampaignArtifactRole,
    *,
    suffix: str = "one",
    challenge: ChallengeKey = CHALLENGE,
    origin: qualification.StructuralOrigin = qualification.StructuralOrigin.REGISTERED_REFERENCE,
    currentness: qualification.ArtifactCurrentness = qualification.ArtifactCurrentness.CURRENT,
):
    return qualification.CampaignArtifactRef(
        challenge,
        role,
        f"{role.value.lower().replace('_', '-')}-{suffix}",
        "1.0",
        DIGESTS[3],
        origin,
        currentness,
    )


def subject(
    role: qualification.CampaignSubjectRole, challenge: ChallengeKey = CHALLENGE
):
    if role is qualification.CampaignSubjectRole.CLAIM_SCOPE:
        value = owned("claim_scope", "campaign-claim", challenge)
    elif role is qualification.CampaignSubjectRole.PHYSICAL_SYSTEM:
        value = top(PhysicalSystemSpecRef, "physical-system", challenge)
    elif role is qualification.CampaignSubjectRole.TARGET_POPULATION:
        value = top(InstanceDistributionContractRef, "target-population", challenge)
    elif role is qualification.CampaignSubjectRole.SAMPLING_PLAN:
        value = top(SamplingPlanRef, "sampling-plan", challenge)
    elif role is qualification.CampaignSubjectRole.GENERATOR:
        value = owned("generator", "generator", challenge)
    elif role is qualification.CampaignSubjectRole.REFERENCE_POLICY:
        value = owned("reference_qualification_policy", "reference-policy", challenge)
    elif role is qualification.CampaignSubjectRole.REPRESENTATION:
        value = owned("representation", "representation", challenge)
    else:
        value = MeasurementContractRef(challenge, DIGESTS[4])
    return qualification.CampaignSubjectBinding(challenge, role, value)


def acquisition(family: qualification.CampaignFamily):
    roles = qualification.CAMPAIGN_REQUIRED_ACQUISITION_ARTIFACT_ROLES[family]
    artifacts = [artifact(role) for role in roles]
    if family is qualification.CampaignFamily.DECISION_RESOLUTION:
        artifacts.append(
            artifact(qualification.CampaignArtifactRole.COMPARED_OBJECT, suffix="two")
        )
    return qualification.CampaignAcquisitionManifest(
        CHALLENGE,
        family,
        f"{family.value.lower().replace('_', '-')}-acquisition",
        "1.0",
        qualification.CampaignAcquisitionState.ACQUISITION_COMPLETED,
        (
            qualification.CampaignAuthorityStatus.OWNER_RATIFICATION_PENDING
            if family is qualification.CampaignFamily.DECISION_RESOLUTION
            else qualification.CampaignAuthorityStatus.RATIFIED_V2_0_STRUCTURE
        ),
        tuple(
            subject(role)
            for role in qualification.CAMPAIGN_REQUIRED_SUBJECT_ROLES[family]
        ),
        tuple(
            definition(kind)
            for kind in qualification.CAMPAIGN_REQUIRED_DEFINITION_KINDS[family]
        ),
        tuple(reversed(artifacts)),
    )


_SUCCESS_STATUS = {
    qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: qualification.CampaignResultStatus.MMS_OBSERVED_ORDER_RECORDED,
    qualification.CampaignFamily.PLANTED_DEFECT_MUTATION: qualification.CampaignResultStatus.MUTATION_DETECTED,
    qualification.CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: qualification.CampaignResultStatus.ANALYTIC_COMPARISON_RECORDED,
    qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: qualification.CampaignResultStatus.REFERENCE_AGREEMENT_OBSERVED,
    qualification.CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: qualification.CampaignResultStatus.ADVERSARIAL_VIOLATION_OBSERVED,
    qualification.CampaignFamily.MEASUREMENT_FLOOR: qualification.CampaignResultStatus.MEASUREMENT_FLOOR_RECORDED,
    qualification.CampaignFamily.DECISION_RESOLUTION: qualification.CampaignResultStatus.INDETERMINATE,
    qualification.CampaignFamily.RESIDUAL_LIMITATION: qualification.CampaignResultStatus.RESIDUAL_LIMITATION_RECORDED,
}


def result(
    value: qualification.CampaignAcquisitionManifest,
    *,
    status: qualification.CampaignResultStatus | None = None,
    attempts: tuple[qualification.EvidenceAttemptBinding, ...] = (),
):
    selected_status = status or _SUCCESS_STATUS[value.campaign_family]
    roles = qualification.CAMPAIGN_REQUIRED_RESULT_ARTIFACT_ROLES[value.campaign_family]
    artifacts = [artifact(role) for role in roles]
    if selected_status in {
        qualification.CampaignResultStatus.REFERENCE_FAILURE,
        qualification.CampaignResultStatus.GENERATOR_FAILURE,
        qualification.CampaignResultStatus.BLOCKED,
        qualification.CampaignResultStatus.INVALID,
    }:
        artifacts.append(artifact(qualification.CampaignArtifactRole.FAILURE))
    if selected_status is qualification.CampaignResultStatus.NOT_APPLICABLE:
        artifacts.append(artifact(qualification.CampaignArtifactRole.EXCLUSION))
    if (
        value.campaign_family
        is qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER
    ):
        artifacts.append(
            artifact(qualification.CampaignArtifactRole.PER_LEVEL_RESULT, suffix="two")
        )
    return qualification.CampaignResultManifest(
        CHALLENGE,
        value.campaign_family,
        f"{value.campaign_family.value.lower().replace('_', '-')}-result",
        "1.0",
        value.acquisition_id,
        value.acquisition_version,
        qualification.campaign_acquisition_digest(value),
        selected_status,
        tuple(reversed(value.scope_refs)),
        tuple(reversed(artifacts)),
        attempts,
    )


def manifest(
    family: qualification.CampaignFamily,
    *,
    origin: qualification.StructuralOrigin = qualification.StructuralOrigin.REGISTERED_REFERENCE,
    currentness: qualification.ArtifactCurrentness = qualification.ArtifactCurrentness.CURRENT,
):
    acquired = acquisition(family)
    return qualification.CampaignEvidenceManifest(
        CHALLENGE,
        family,
        qualification.CAMPAIGN_FAMILY_EVIDENCE_CLASS[family],
        f"{family.value.lower().replace('_', '-')}-manifest",
        "1.0",
        origin,
        currentness,
        acquired,
        result(acquired),
    )


@pytest.mark.parametrize("family", tuple(qualification.CampaignFamily))
def test_every_campaign_family_has_exact_acquisition_result_and_round_trip(
    family,
) -> None:
    value = manifest(family)
    document = qualification.campaign_manifest_bytes(value)
    assert qualification.load_campaign_manifest(document) == value
    assert (
        qualification.campaign_manifest_bytes(
            qualification.load_campaign_manifest(document)
        )
        == document
    )
    assert qualification.campaign_manifest_digest(value).startswith("sha256:")
    assert (
        qualification.campaign_evidence_ref(value).evidence_class
        is qualification.CAMPAIGN_FAMILY_EVIDENCE_CLASS[family]
    )
    assert {
        item.subject_role for item in value.acquisition.subject_bindings
    } >= qualification.CAMPAIGN_REQUIRED_SUBJECT_ROLES[family]
    assert {
        item.artifact_role for item in value.result.artifact_refs
    } >= qualification.CAMPAIGN_REQUIRED_RESULT_ARTIFACT_ROLES[family]


def test_reference_disagreement_is_an_explicit_evidence_class() -> None:
    original = manifest(
        qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
    )
    value = replace(
        original,
        evidence_class=qualification.DossierEvidenceClass.REFERENCE_DISAGREEMENT,
        result=replace(
            original.result,
            result_status=qualification.CampaignResultStatus.REFERENCE_DISAGREEMENT_OBSERVED,
        ),
    )
    loaded = qualification.load_campaign_manifest(
        qualification.campaign_manifest_bytes(value)
    )
    assert (
        loaded.evidence_class
        is qualification.DossierEvidenceClass.REFERENCE_DISAGREEMENT
    )
    assert (
        qualification.campaign_evidence_ref(loaded).evidence_class
        is qualification.DossierEvidenceClass.REFERENCE_DISAGREEMENT
    )
    with pytest.raises(qualification.DossierValidationError) as wrong:
        replace(
            value,
            evidence_class=qualification.DossierEvidenceClass.MEASUREMENT_FLOOR,
        )
    assert wrong.value.code is qualification.DossierInputCode.ROLE_CONFUSION
    with pytest.raises(qualification.DossierValidationError) as confused_status:
        replace(value, result=original.result)
    assert confused_status.value.code is qualification.DossierInputCode.ROLE_CONFUSION


@pytest.mark.parametrize(
    "state",
    (
        qualification.CampaignAcquisitionState.CAMPAIGN_SPECIFIED,
        qualification.CampaignAcquisitionState.ACQUISITION_ATTEMPTED,
        qualification.CampaignAcquisitionState.ACQUISITION_PARTIALLY_COMPLETED,
    ),
)
def test_honest_pre_result_campaign_states_are_representable_but_not_evidence(
    state,
) -> None:
    acquired = replace(
        acquisition(qualification.CampaignFamily.MEASUREMENT_FLOOR),
        acquisition_state=state,
    )
    value = qualification.CampaignEvidenceManifest(
        CHALLENGE,
        qualification.CampaignFamily.MEASUREMENT_FLOOR,
        qualification.DossierEvidenceClass.MEASUREMENT_FLOOR,
        "floor-pending",
        "1.0",
        qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
        qualification.ArtifactCurrentness.CURRENT,
        acquired,
    )
    assert (
        qualification.load_campaign_manifest(
            qualification.campaign_manifest_bytes(value)
        )
        == value
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.campaign_evidence_ref(value)
    assert caught.value.code is qualification.DossierInputCode.MISSING_EVIDENCE


def test_mms_wrong_implementation_and_malformed_refinement_reject() -> None:
    value = acquisition(qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER)
    wrong = tuple(
        (
            artifact(
                qualification.CampaignArtifactRole.IMPLEMENTATION_UNDER_TEST,
                challenge=ChallengeKey("other", "1.0"),
            )
            if item.artifact_role
            is qualification.CampaignArtifactRole.IMPLEMENTATION_UNDER_TEST
            else item
        )
        for item in value.artifact_refs
    )
    with pytest.raises(qualification.DossierValidationError) as crossed:
        replace(value, artifact_refs=wrong)
    assert crossed.value.code is qualification.DossierInputCode.CROSS_CHALLENGE
    with pytest.raises(qualification.DossierValidationError):
        artifact(
            qualification.CampaignArtifactRole.REFINEMENT_FAMILY, suffix="https://bad"
        )


def test_mutation_duplicates_and_wrong_measurement_binding_reject() -> None:
    value = acquisition(qualification.CampaignFamily.PLANTED_DEFECT_MUTATION)
    mutation = next(
        item
        for item in value.artifact_refs
        if item.artifact_role is qualification.CampaignArtifactRole.MUTATION_OPERATOR
    )
    with pytest.raises(qualification.DossierValidationError) as duplicate:
        replace(value, artifact_refs=(*value.artifact_refs, mutation))
    assert duplicate.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY
    with pytest.raises(qualification.DossierValidationError) as wrong:
        tuple(
            (
                qualification.CampaignSubjectBinding(
                    CHALLENGE,
                    item.subject_role,
                    MeasurementContractRef(ChallengeKey("other", "1.0"), DIGESTS[4]),
                )
                if item.subject_role
                is qualification.CampaignSubjectRole.MEASUREMENT_CONTRACT
                else item
            )
            for item in value.subject_bindings
        )
    assert wrong.value.code is qualification.DossierInputCode.CROSS_CHALLENGE


def test_analytic_result_scope_and_reference_binding_are_exact() -> None:
    acquired = acquisition(qualification.CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR)
    produced = result(acquired)
    wrong_scope = (definition(MeasurementDefinitionKind.CASE_SCOPE, "other-scope"),)
    with pytest.raises(qualification.DossierValidationError) as mismatch:
        qualification.CampaignEvidenceManifest(
            CHALLENGE,
            acquired.campaign_family,
            qualification.DossierEvidenceClass.ANALYTIC_LIMITING_CASE_ANCHOR,
            "analytic-manifest",
            "1.0",
            qualification.StructuralOrigin.REGISTERED_REFERENCE,
            qualification.ArtifactCurrentness.CURRENT,
            acquired,
            replace(produced, scope_refs=wrong_scope),
        )
    assert mismatch.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_primary_and_witness_are_nominally_distinct_and_failure_stays_reference_failure() -> (
    None
):
    acquired = acquisition(
        qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
    )
    primary = next(
        item
        for item in acquired.artifact_refs
        if item.artifact_role is qualification.CampaignArtifactRole.PRIMARY_REFERENCE
    )
    confused = tuple(
        (
            replace(
                primary,
                artifact_role=qualification.CampaignArtifactRole.WITNESS_REFERENCE,
            )
            if item.artifact_role
            is qualification.CampaignArtifactRole.WITNESS_REFERENCE
            else item
        )
        for item in acquired.artifact_refs
    )
    with pytest.raises(qualification.DossierValidationError) as role:
        replace(acquired, artifact_refs=confused)
    assert role.value.code is qualification.DossierInputCode.ROLE_CONFUSION

    attempt_ref = qualification.DossierEvidenceRef(
        CHALLENGE,
        qualification.DossierEvidenceClass.REFERENCE_DISAGREEMENT,
        "reference-failure-attempt",
        "1.0",
        DIGESTS[5],
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
    )
    failure = qualification.EvidenceAttemptBinding(
        CHALLENGE, attempt_ref, qualification.AttemptDisposition.REFERENCE_FAILURE
    )
    produced = result(
        acquired,
        status=qualification.CampaignResultStatus.REFERENCE_FAILURE,
        attempts=(failure,),
    )
    assert (
        produced.attempts[0].disposition
        is qualification.AttemptDisposition.REFERENCE_FAILURE
    )
    assert (
        produced.attempts[0].disposition
        is not qualification.AttemptDisposition.CANDIDATE_FAILURE
    )
    failed_campaign = replace(
        manifest(qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT),
        acquisition=acquired,
        result=produced,
    )
    with pytest.raises(qualification.DossierValidationError) as not_evidence:
        qualification.campaign_evidence_ref(failed_campaign)
    assert not_evidence.value.code is qualification.DossierInputCode.MISSING_EVIDENCE


def test_generator_campaign_requires_exact_population_plan_and_generator() -> None:
    acquired = acquisition(qualification.CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL)
    wrong_population = InstanceDistributionContractRef(
        CHALLENGE,
        "practice-population",
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        DIGESTS[1],
        "PRACTICE",
    )
    with pytest.raises(qualification.DossierValidationError) as role:
        tuple(
            (
                qualification.CampaignSubjectBinding(
                    CHALLENGE, item.subject_role, wrong_population
                )
                if item.subject_role
                is qualification.CampaignSubjectRole.TARGET_POPULATION
                else item
            )
            for item in acquired.subject_bindings
        )
    assert role.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_measurement_floor_scope_and_contract_are_exact_but_not_score_eligibility() -> (
    None
):
    value = manifest(qualification.CampaignFamily.MEASUREMENT_FLOOR)
    evidence = qualification.campaign_evidence_ref(value)
    with pytest.raises(qualification.DossierValidationError) as substitution:
        qualification.EvidenceClaimBinding(
            CHALLENGE,
            evidence,
            qualification.DossierClaimRole.MEASUREMENT_ADEQUACY,
            owned("claim_scope", "campaign-claim"),
        )
    assert substitution.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_decision_resolution_is_pending_only_and_has_no_computation() -> None:
    acquired = acquisition(qualification.CampaignFamily.DECISION_RESOLUTION)
    assert (
        acquired.authority_status
        is qualification.CampaignAuthorityStatus.OWNER_RATIFICATION_PENDING
    )
    with pytest.raises(qualification.DossierValidationError) as authority:
        replace(
            acquired,
            authority_status=qualification.CampaignAuthorityStatus.RATIFIED_V2_0_STRUCTURE,
        )
    assert authority.value.code is qualification.DossierInputCode.ROLE_CONFUSION
    missing_method = tuple(
        item
        for item in acquired.definition_refs
        if item.definition_kind is not MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL
    )
    with pytest.raises(qualification.DossierValidationError) as missing:
        replace(acquired, definition_refs=missing_method)
    assert missing.value.code is qualification.DossierInputCode.MISSING_EVIDENCE
    forbidden = {
        "compute_interval",
        "select_winner",
        "promote",
        "bootstrap",
        "calculate_power",
    }
    assert forbidden.isdisjoint(qualification.__all__)


@pytest.mark.parametrize(
    ("family", "forbidden_role"),
    (
        (
            qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER,
            qualification.DossierClaimRole.PHYSICAL_SYSTEM_ADEQUACY,
        ),
        (
            qualification.CampaignFamily.PLANTED_DEFECT_MUTATION,
            qualification.DossierClaimRole.PRODUCT_QUALIFICATION,
        ),
        (
            qualification.CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL,
            qualification.DossierClaimRole.SAMPLING_PLAN_ADEQUACY,
        ),
        (
            qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT,
            qualification.DossierClaimRole.REFERENCE_ADEQUACY,
        ),
        (
            qualification.CampaignFamily.DECISION_RESOLUTION,
            qualification.DossierClaimRole.LIVE_ACTIVATION,
        ),
    ),
)
def test_campaign_evidence_cannot_substitute_for_unrelated_claims(
    family, forbidden_role
) -> None:
    evidence = qualification.campaign_evidence_ref(manifest(family))
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.EvidenceClaimBinding(
            CHALLENGE,
            evidence,
            forbidden_role,
            owned("claim_scope", "campaign-claim"),
        )
    assert caught.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_fixture_and_currentness_propagate_and_stale_cannot_supply_evidence() -> None:
    fixture = manifest(
        qualification.CampaignFamily.PLANTED_DEFECT_MUTATION,
        origin=qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    assert fixture.fixture_derived
    assert (
        qualification.campaign_manifest_ref(fixture).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )
    assert (
        qualification.campaign_evidence_ref(fixture).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )
    stale = manifest(
        qualification.CampaignFamily.MEASUREMENT_FLOOR,
        currentness=qualification.ArtifactCurrentness.SUPERSEDED,
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.campaign_evidence_ref(stale)
    assert caught.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_campaign_canonical_ordering_tamper_trailing_duplicate_and_oversize_reject() -> (
    None
):
    value = manifest(qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER)
    permuted = replace(
        value,
        acquisition=replace(
            value.acquisition,
            subject_bindings=tuple(reversed(value.acquisition.subject_bindings)),
            definition_refs=tuple(reversed(value.acquisition.definition_refs)),
            artifact_refs=tuple(reversed(value.acquisition.artifact_refs)),
        ),
    )
    assert qualification.campaign_manifest_bytes(
        permuted
    ) == qualification.campaign_manifest_bytes(value)
    document = qualification.campaign_manifest_bytes(value)
    payload = json.loads(
        document[len(qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER) :]
    )
    payload["manifest_id"] = "tampered-manifest"
    tampered = (
        qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER
        + json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )
    assert (
        qualification.campaign_manifest_digest(value)
        != "sha256:" + __import__("hashlib").sha256(tampered).hexdigest()
    )
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_campaign_manifest(document + b" ")
    body = document[len(qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER) :]
    duplicate = qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER + body.replace(
        b'{"acquisition":', b'{"manifest_id":"duplicate","acquisition":', 1
    )
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_campaign_manifest(duplicate)
    with pytest.raises(qualification.DossierCanonicalError) as oversized:
        qualification.load_campaign_manifest(
            qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER
            + b" " * qualification.MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES
        )
    assert oversized.value.code is qualification.DossierInputCode.SIZE_LIMIT


def test_campaign_encoders_and_digest_ref_helpers_enforce_exact_size_bound(
    monkeypatch,
) -> None:
    value = manifest(qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER)
    acquisition_document = qualification.campaign_acquisition_bytes(value.acquisition)
    manifest_document = qualification.campaign_manifest_bytes(value)

    monkeypatch.setattr(
        campaign_canonical,
        "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
        len(acquisition_document) + 1,
    )
    assert qualification.campaign_acquisition_bytes(value.acquisition) == (
        acquisition_document
    )
    monkeypatch.setattr(
        campaign_canonical,
        "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
        len(acquisition_document),
    )
    assert qualification.campaign_acquisition_digest(value.acquisition).startswith(
        "sha256:"
    )
    monkeypatch.setattr(
        campaign_canonical,
        "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
        len(acquisition_document) - 1,
    )
    for operation in (
        lambda: qualification.campaign_acquisition_bytes(value.acquisition),
        lambda: qualification.campaign_acquisition_digest(value.acquisition),
    ):
        with pytest.raises(qualification.DossierCanonicalError) as oversized:
            operation()
        assert oversized.value.code is qualification.DossierInputCode.SIZE_LIMIT

    monkeypatch.setattr(
        campaign_canonical,
        "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
        len(manifest_document) + 1,
    )
    assert qualification.campaign_manifest_bytes(value) == manifest_document
    monkeypatch.setattr(
        campaign_canonical,
        "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
        len(manifest_document),
    )
    assert qualification.campaign_manifest_digest(value).startswith("sha256:")
    assert qualification.campaign_manifest_ref(value).content_digest.startswith(
        "sha256:"
    )
    assert qualification.campaign_evidence_ref(value).content_digest.startswith(
        "sha256:"
    )
    monkeypatch.setattr(
        campaign_canonical,
        "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
        len(manifest_document) - 1,
    )
    for operation in (
        lambda: qualification.campaign_manifest_bytes(value),
        lambda: qualification.campaign_manifest_digest(value),
        lambda: qualification.campaign_manifest_ref(value),
        lambda: qualification.campaign_evidence_ref(value),
    ):
        with pytest.raises(qualification.DossierCanonicalError) as oversized:
            operation()
        assert oversized.value.code is qualification.DossierInputCode.SIZE_LIMIT


def test_wrong_family_result_status_and_wrong_acquisition_digest_reject() -> None:
    acquired = acquisition(qualification.CampaignFamily.MEASUREMENT_FLOOR)
    with pytest.raises(qualification.DossierValidationError) as status:
        result(acquired, status=qualification.CampaignResultStatus.MUTATION_DETECTED)
    assert status.value.code is qualification.DossierInputCode.ROLE_CONFUSION
    produced = result(acquired)
    with pytest.raises(qualification.DossierValidationError) as digest:
        qualification.CampaignEvidenceManifest(
            CHALLENGE,
            acquired.campaign_family,
            qualification.DossierEvidenceClass.MEASUREMENT_FLOOR,
            "floor-digest-mismatch",
            "1.0",
            qualification.StructuralOrigin.REGISTERED_REFERENCE,
            qualification.ArtifactCurrentness.CURRENT,
            acquired,
            replace(produced, acquisition_digest=DIGESTS[5]),
        )
    assert digest.value.code is qualification.DossierInputCode.DIGEST_MISMATCH


def test_campaign_surface_has_no_protected_material_or_runtime_locator_fields() -> None:
    names = set(qualification.CampaignArtifactRef.__dataclass_fields__)
    names |= set(qualification.CampaignAcquisitionManifest.__dataclass_fields__)
    names |= set(qualification.CampaignResultManifest.__dataclass_fields__)
    forbidden = {
        "seed",
        "official_seed",
        "realization",
        "truth_payload",
        "path",
        "url",
        "locator",
        "payload",
        "credential",
        "token",
        "signer_secret",
    }
    assert forbidden.isdisjoint(names)
    value = manifest(qualification.CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL)
    assert "fixture-campaign" not in repr(value)
    assert b"official_seed" not in qualification.campaign_manifest_bytes(value)


@pytest.mark.parametrize(
    ("family", "allowed_role"),
    (
        (
            qualification.CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER,
            qualification.DossierClaimRole.DISCRETIZATION_CONVERGENCE,
        ),
        (
            qualification.CampaignFamily.PLANTED_DEFECT_MUTATION,
            qualification.DossierClaimRole.IMPLEMENTATION_VERIFICATION,
        ),
        (
            qualification.CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR,
            qualification.DossierClaimRole.LIMITING_CASE_BEHAVIOR,
        ),
        (
            qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT,
            qualification.DossierClaimRole.REFERENCE_AGREEMENT,
        ),
        (
            qualification.CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL,
            qualification.DossierClaimRole.GENERATOR_CONFORMANCE_DIAGNOSTIC,
        ),
        (
            qualification.CampaignFamily.MEASUREMENT_FLOOR,
            qualification.DossierClaimRole.MEASUREMENT_FLOOR_DIAGNOSTIC,
        ),
        (
            qualification.CampaignFamily.DECISION_RESOLUTION,
            qualification.DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC,
        ),
        (
            qualification.CampaignFamily.RESIDUAL_LIMITATION,
            qualification.DossierClaimRole.RESIDUAL_LIMITATION_DISCLOSURE,
        ),
    ),
)
def test_each_campaign_integrates_through_existing_claim_matrix(
    family, allowed_role
) -> None:
    evidence = qualification.campaign_evidence_ref(manifest(family))
    binding = qualification.EvidenceClaimBinding(
        CHALLENGE,
        evidence,
        allowed_role,
        owned("claim_scope", "campaign-claim"),
    )
    assert binding.evidence_ref == evidence
    assert binding.claim_role is allowed_role


def test_campaign_digest_integrates_into_d7_without_replacing_primary_evidence() -> (
    None
):
    original = manifest(
        qualification.CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
    )
    campaign = replace(
        original,
        evidence_class=qualification.DossierEvidenceClass.REFERENCE_DISAGREEMENT,
        result=replace(
            original.result,
            result_status=qualification.CampaignResultStatus.REFERENCE_DISAGREEMENT_OBSERVED,
        ),
    )
    campaign_ref = qualification.campaign_evidence_ref(campaign)
    claim_scope = owned("claim_scope", "campaign-claim")
    primary = qualification.DossierEvidenceRef(
        CHALLENGE,
        qualification.DossierEvidenceClass.REFERENCE_TRUTH_ADEQUACY,
        "primary-reference-adequacy",
        "1.0",
        DIGESTS[5],
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
    )
    value = qualification.DossierEvidenceManifest(
        CHALLENGE,
        qualification.DossierSlot.D7,
        "d7-with-campaign",
        "1.0",
        qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
        qualification.StructuralOrigin.REGISTERED_REFERENCE,
        qualification.EvidenceSubjectBindings(
            CHALLENGE,
            claim_scope,
            reference_policy_ref=owned(
                "reference_qualification_policy", "reference-policy"
            ),
        ),
        (primary, campaign_ref),
        (
            qualification.EvidenceClaimBinding(
                CHALLENGE,
                primary,
                qualification.DossierClaimRole.REFERENCE_ADEQUACY,
                claim_scope,
            ),
            qualification.EvidenceClaimBinding(
                CHALLENGE,
                campaign_ref,
                qualification.DossierClaimRole.REFERENCE_AGREEMENT,
                claim_scope,
            ),
        ),
    )
    document = qualification.evidence_manifest_bytes(value)
    assert qualification.load_evidence_manifest(document) == value
    assert campaign_ref in value.evidence_refs
    assert primary in value.evidence_refs


@pytest.mark.parametrize(
    "status",
    (
        qualification.CampaignResultStatus.BLOCKED,
        qualification.CampaignResultStatus.INVALID,
        qualification.CampaignResultStatus.NOT_APPLICABLE,
    ),
)
def test_blocked_invalid_and_inapplicable_results_need_no_fabricated_floor(
    status,
) -> None:
    acquired = acquisition(qualification.CampaignFamily.MEASUREMENT_FLOOR)
    artifacts = [artifact(qualification.CampaignArtifactRole.LIMITATION)]
    if status is qualification.CampaignResultStatus.NOT_APPLICABLE:
        artifacts.append(artifact(qualification.CampaignArtifactRole.EXCLUSION))
    else:
        artifacts.append(artifact(qualification.CampaignArtifactRole.FAILURE))
    value = qualification.CampaignResultManifest(
        CHALLENGE,
        acquired.campaign_family,
        "measurement-floor-result",
        "1.0",
        acquired.acquisition_id,
        acquired.acquisition_version,
        qualification.campaign_acquisition_digest(acquired),
        status,
        acquired.scope_refs,
        tuple(artifacts),
    )
    assert not any(
        item.artifact_role is qualification.CampaignArtifactRole.FLOOR_RESULT
        for item in value.artifact_refs
    )
    campaign = replace(
        manifest(qualification.CampaignFamily.MEASUREMENT_FLOOR), result=value
    )
    with pytest.raises(qualification.DossierValidationError) as not_evidence:
        qualification.campaign_evidence_ref(campaign)
    assert not_evidence.value.code is qualification.DossierInputCode.MISSING_EVIDENCE


def test_measurement_floor_result_rejects_stratum_and_contract_drift() -> None:
    acquired = acquisition(qualification.CampaignFamily.MEASUREMENT_FLOOR)
    with_stratum = replace(
        acquired,
        definition_refs=(
            *acquired.definition_refs,
            definition(MeasurementDefinitionKind.STRATUM, "floor-stratum"),
        ),
    )
    produced = result(with_stratum)
    wrong_scope = tuple(
        (
            definition(MeasurementDefinitionKind.STRATUM, "other-stratum")
            if item.definition_kind is MeasurementDefinitionKind.STRATUM
            else item
        )
        for item in produced.scope_refs
    )
    with pytest.raises(qualification.DossierValidationError) as mismatch:
        qualification.CampaignEvidenceManifest(
            CHALLENGE,
            acquired.campaign_family,
            qualification.DossierEvidenceClass.MEASUREMENT_FLOOR,
            "floor-scope-drift",
            "1.0",
            qualification.StructuralOrigin.REGISTERED_REFERENCE,
            qualification.ArtifactCurrentness.CURRENT,
            with_stratum,
            replace(produced, scope_refs=wrong_scope),
        )
    assert mismatch.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_decision_resolution_requires_censoring_and_stopping_audit_identity() -> None:
    acquired = acquisition(qualification.CampaignFamily.DECISION_RESOLUTION)
    for missing_kind in (
        MeasurementDefinitionKind.CENSORING_ACCOUNTING,
        MeasurementDefinitionKind.STOPPING_RULE,
    ):
        with pytest.raises(qualification.DossierValidationError) as missing:
            replace(
                acquired,
                definition_refs=tuple(
                    item
                    for item in acquired.definition_refs
                    if item.definition_kind is not missing_kind
                ),
            )
        assert missing.value.code is qualification.DossierInputCode.MISSING_EVIDENCE


def test_residual_limitation_only_maps_to_limitation_disclosure() -> None:
    evidence = qualification.campaign_evidence_ref(
        manifest(qualification.CampaignFamily.RESIDUAL_LIMITATION)
    )
    with pytest.raises(qualification.DossierValidationError) as wrong:
        qualification.EvidenceClaimBinding(
            CHALLENGE,
            evidence,
            qualification.DossierClaimRole.CLAIM_ENVELOPE_ADEQUACY,
            owned("claim_scope", "campaign-claim"),
        )
    assert wrong.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_nested_fixture_and_stale_artifacts_cannot_be_laundered() -> None:
    value = manifest(qualification.CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL)
    fixture_result = replace(
        value.result,
        artifact_refs=tuple(
            (
                replace(item, origin=qualification.StructuralOrigin.FIXTURE_ONLY)
                if item.artifact_role
                is qualification.CampaignArtifactRole.ADVERSARIAL_RESULT
                else item
            )
            for item in value.result.artifact_refs
        ),
    )
    fixture = replace(value, result=fixture_result)
    assert fixture.fixture_derived
    assert (
        qualification.campaign_evidence_ref(fixture).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )

    stale_result = replace(
        value.result,
        artifact_refs=tuple(
            (
                replace(item, currentness=qualification.ArtifactCurrentness.SUPERSEDED)
                if item.artifact_role
                is qualification.CampaignArtifactRole.ADVERSARIAL_RESULT
                else item
            )
            for item in value.result.artifact_refs
        ),
    )
    with pytest.raises(qualification.DossierValidationError) as stale:
        qualification.campaign_evidence_ref(replace(value, result=stale_result))
    assert stale.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_supersession_is_exact_and_preserves_fixture_origin() -> None:
    predecessor = manifest(
        qualification.CampaignFamily.PLANTED_DEFECT_MUTATION,
        origin=qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    successor = replace(
        manifest(qualification.CampaignFamily.PLANTED_DEFECT_MUTATION),
        manifest_version="2.0",
        supersedes=qualification.campaign_manifest_ref(predecessor),
    )
    assert successor.fixture_derived
    with pytest.raises(qualification.DossierValidationError) as same_version:
        replace(successor, manifest_version="1.0")
    assert same_version.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_strict_decoder_rejects_numeric_unknown_and_corrupt_input() -> None:
    document = qualification.campaign_manifest_bytes(
        manifest(qualification.CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR)
    )
    body = document[len(qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER) :]
    payload = json.loads(body)
    payload["unknown"] = "field"
    unknown = (
        qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER
        + json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_campaign_manifest(unknown)
    numeric = qualification.CAMPAIGN_MANIFEST_DOCUMENT_HEADER + body.replace(
        b'"manifest_version":"1.0"', b'"manifest_version":1', 1
    )
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_campaign_manifest(numeric)
    corrupt = bytearray(document)
    corrupt[-2] = 0xFF
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_campaign_manifest(bytes(corrupt))


def test_every_campaign_field_has_an_explicit_authority_classification() -> None:
    expected = {
        f"{record.__name__}.{item.name}"
        for record in (
            qualification.CampaignSubjectBinding,
            qualification.CampaignArtifactRef,
            qualification.CampaignAcquisitionManifest,
            qualification.CampaignResultManifest,
            qualification.CampaignEvidenceManifest,
        )
        for item in fields(record)
    }
    assert set(qualification.CAMPAIGN_FIELD_AUTHORITY) == expected
    assert qualification.CAMPAIGN_UNREPRESENTED_HUMAN_JUDGMENTS == {
        "evidence_adequacy",
        "scientific_acceptance",
        "signer_authorization",
        "security_acceptance",
        "production_qualification",
        "live_activation",
    }
