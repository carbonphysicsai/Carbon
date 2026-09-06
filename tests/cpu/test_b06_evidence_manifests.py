from __future__ import annotations

import json
from dataclasses import replace

import pytest

from carbon import qualification
from carbon.authoring.refs import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    CandidateOutputContractRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.measurement.enums import MeasurementDefinitionKind
from carbon.measurement.refs import (
    MeasurementContractRef,
    MeasurementDefinitionRef,
    MeasurementQualificationEvidenceRef,
    UncertaintyPolicyRef,
)
from carbon.registry import ChallengeKey

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


def top_ref(
    expected: type, challenge: ChallengeKey, identity: str, *, version: str = "1.0"
):
    common = (
        challenge,
        identity,
        version,
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        DIGEST_A,
    )
    if expected is InstanceDistributionContractRef:
        return expected(*common, "TARGET_WORKLOAD_P")
    return expected(*common)


def owned(kind: str, challenge: ChallengeKey, identity: str, *, version: str = "1.0"):
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(challenge),
        object_id=identity,
        object_version=version,
        content_digest=DIGEST_B,
    )


def evidence_ref(
    challenge: ChallengeKey,
    evidence_class: qualification.DossierEvidenceClass,
    identity: str,
    *,
    origin: qualification.StructuralOrigin = qualification.StructuralOrigin.REGISTERED_REFERENCE,
):
    return qualification.DossierEvidenceRef(
        challenge, evidence_class, identity, "1.0", DIGEST_C, origin
    )


def definition(
    challenge: ChallengeKey,
    kind: MeasurementDefinitionKind,
    identity: str,
):
    return MeasurementDefinitionRef(challenge, kind, identity, "1.0", DIGEST_A)


def subjects(challenge: ChallengeKey, *, scope_version: str = "1.0"):
    return qualification.EvidenceSubjectBindings(
        challenge,
        owned("claim_scope", challenge, "registered-claim", version=scope_version),
        physical_system_ref=top_ref(
            PhysicalSystemSpecRef, challenge, "physical-system"
        ),
        candidate_output_ref=top_ref(
            CandidateOutputContractRef, challenge, "candidate-output"
        ),
        target_population_ref=top_ref(
            InstanceDistributionContractRef, challenge, "target-population"
        ),
        sampling_plan_ref=top_ref(SamplingPlanRef, challenge, "sampling-plan"),
        generator_ref=owned("generator", challenge, "generator"),
        generator_conformance_ref=owned(
            "distribution_conformance", challenge, "generator-conformance"
        ),
        reference_policy_ref=owned(
            "reference_qualification_policy", challenge, "reference-policy"
        ),
        representation_ref=owned("representation", challenge, "representation"),
        measurement_contract_ref=MeasurementContractRef(challenge, DIGEST_A),
        measurement_evidence_ref=MeasurementQualificationEvidenceRef(
            challenge, DIGEST_B
        ),
    )


def accounting(
    challenge: ChallengeKey,
    binding: qualification.EvidenceSubjectBindings,
    *,
    attempts: tuple[qualification.EvidenceAttemptBinding, ...] | None = None,
):
    attempts = attempts or (
        qualification.EvidenceAttemptBinding(
            challenge,
            evidence_ref(
                challenge,
                qualification.DossierEvidenceClass.CENSORING_LIMITATIONS_RESIDUAL_UNCERTAINTY,
                "attempt-reference-failure",
            ),
            qualification.AttemptDisposition.REFERENCE_FAILURE,
        ),
        qualification.EvidenceAttemptBinding(
            challenge,
            evidence_ref(
                challenge,
                qualification.DossierEvidenceClass.CENSORING_LIMITATIONS_RESIDUAL_UNCERTAINTY,
                "attempt-candidate-failure",
            ),
            qualification.AttemptDisposition.CANDIDATE_FAILURE,
        ),
    )
    return qualification.EvidenceAccountingManifest(
        challenge,
        binding.sampling_plan_ref,
        owned("protected_unit_manifest", challenge, "intended-units"),
        owned("realized_evidence_accounting", challenge, "realized-evidence"),
        owned("censoring_policy", challenge, "censoring-policy"),
        owned("missingness_adjustment", challenge, "missingness-policy"),
        owned("exclusion_assessment", challenge, "exclusion-assessment"),
        attempts,
    )


def secrecy(challenge: ChallengeKey):
    return qualification.SecrecyEvidenceManifest(
        challenge,
        owned("disclosure_policy", challenge, "disclosure-policy"),
        owned("blinding_policy", challenge, "blinding-policy"),
        owned("audit_evidence", challenge, "decontamination-audit"),
        owned("audit_evidence", challenge, "role-separation-audit"),
    )


def statistical(challenge: ChallengeKey, coverage):
    return qualification.StatisticalScopeManifest(
        challenge,
        qualification.DependencePolicyAuthorityStatus.OWNER_RATIFICATION_PENDING,
        UncertaintyPolicyRef(challenge, DIGEST_B),
        definition(challenge, MeasurementDefinitionKind.ESTIMAND, "estimand"),
        definition(challenge, MeasurementDefinitionKind.SAMPLING_UNIT, "sampling-unit"),
        definition(
            challenge, MeasurementDefinitionKind.RESAMPLING_UNIT, "resampling-unit"
        ),
        definition(
            challenge, MeasurementDefinitionKind.INDEPENDENCE_UNIT, "independence-unit"
        ),
        definition(challenge, MeasurementDefinitionKind.CASE_SCOPE, "case-scope"),
        definition(challenge, MeasurementDefinitionKind.STRATUM, "stress-stratum"),
        definition(
            challenge,
            MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL,
            "decision-interval-method",
        ),
        definition(
            challenge,
            MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
            "dependence-assumption",
        ),
        definition(
            challenge,
            MeasurementDefinitionKind.APPLICABILITY_TEST,
            "applicability-test",
        ),
        definition(
            challenge,
            MeasurementDefinitionKind.RECONSTRUCTION_CASE_INTERACTION,
            "reconstruction-case-interaction",
        ),
        definition(
            challenge,
            MeasurementDefinitionKind.RECONSTRUCTION_STRATUM_INTERACTION,
            "reconstruction-stratum-interaction",
        ),
        coverage,
        definition(challenge, MeasurementDefinitionKind.STOPPING_RULE, "stopping-rule"),
        definition(
            challenge,
            MeasurementDefinitionKind.CENSORING_ACCOUNTING,
            "missing-cell-policy",
        ),
        definition(challenge, MeasurementDefinitionKind.EVIDENCE_SET, "evidence-set"),
    )


def manifest(
    slot: qualification.DossierSlot,
    *,
    challenge: ChallengeKey | None = None,
    origin: qualification.StructuralOrigin = qualification.StructuralOrigin.REGISTERED_REFERENCE,
    extra_refs: tuple[qualification.DossierEvidenceRef, ...] = (),
    extra_claims: tuple[qualification.EvidenceClaimBinding, ...] = (),
    supersedes: qualification.DossierEvidenceManifestRef | None = None,
    version: str = "1.0",
):
    challenge = challenge or ChallengeKey("fixture-burgers", "1.0")
    binding = subjects(challenge)
    primary = evidence_ref(
        challenge,
        qualification.DOSSIER_PRIMARY_EVIDENCE_CLASS[slot],
        f"primary-{slot.value.lower()}",
        origin=origin,
    )
    refs = (primary, *extra_refs)
    claims = (
        qualification.EvidenceClaimBinding(
            challenge,
            primary,
            qualification.DOSSIER_PRIMARY_CLAIM_ROLE[slot],
            binding.claim_scope_ref,
        ),
        *extra_claims,
    )
    stat = None
    account = None
    secret = None
    if slot is qualification.DossierSlot.D10:
        coverage = evidence_ref(
            challenge,
            qualification.DossierEvidenceClass.DECISION_RESOLUTION_STUDY,
            "coverage-study",
            origin=origin,
        )
        refs = (*refs, coverage)
        claims = (
            *claims,
            qualification.EvidenceClaimBinding(
                challenge,
                coverage,
                qualification.DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC,
                binding.claim_scope_ref,
            ),
        )
        stat = statistical(challenge, coverage)
    if slot in (
        qualification.DossierSlot.D4,
        qualification.DossierSlot.D6,
        qualification.DossierSlot.D12,
    ):
        account = accounting(challenge, binding)
    if slot is qualification.DossierSlot.D11:
        secret = secrecy(challenge)
    return qualification.DossierEvidenceManifest(
        challenge,
        slot,
        f"manifest-{slot.value.lower()}",
        version,
        qualification.EvidenceCompleteness.COMPLETE_REFERENCED,
        origin,
        binding,
        refs,
        claims,
        stat,
        account,
        secret,
        (),
        supersedes,
    )


def test_all_d1_d12_primary_manifests_keep_exact_slot_identity() -> None:
    values = tuple(manifest(slot) for slot in qualification.DOSSIER_SLOT_ORDER)
    assert tuple(item.slot for item in values) == qualification.DOSSIER_SLOT_ORDER
    assert tuple(
        qualification.dossier_evidence_ref(item).evidence_class for item in values
    ) == tuple(qualification.DOSSIER_PRIMARY_EVIDENCE_CLASS.values())


@pytest.mark.parametrize(
    "completeness",
    (
        qualification.EvidenceCompleteness.INCOMPLETE_MISSING,
        qualification.EvidenceCompleteness.INCOMPLETE_PLACEHOLDER,
    ),
)
def test_incomplete_manifests_are_honest_and_carry_no_evidence(completeness) -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    value = qualification.DossierEvidenceManifest(
        challenge,
        qualification.DossierSlot.D10,
        "incomplete-statistical-manifest",
        "1.0",
        completeness,
        qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
    )
    assert (
        qualification.load_evidence_manifest(
            qualification.evidence_manifest_bytes(value)
        )
        == value
    )
    with pytest.raises(qualification.DossierValidationError):
        replace(
            value,
            evidence_refs=(
                evidence_ref(
                    challenge,
                    qualification.DossierEvidenceClass.STATISTICAL_SUFFICIENCY_ESTIMAND_CLARITY,
                    "false-complete",
                ),
            ),
        )


def test_subject_graph_requires_exact_population_plan_and_versions() -> None:
    value = manifest(qualification.DossierSlot.D4)
    with pytest.raises(qualification.DossierValidationError) as missing:
        replace(
            value,
            subject_bindings=replace(value.subject_bindings, sampling_plan_ref=None),
        )
    assert missing.value.code is qualification.DossierInputCode.MISSING_EVIDENCE

    wrong_version = top_ref(
        SamplingPlanRef, value.challenge_key, "sampling-plan", version="2.0"
    )
    with pytest.raises(qualification.DossierValidationError) as mismatch:
        replace(
            value,
            subject_bindings=replace(
                value.subject_bindings, sampling_plan_ref=wrong_version
            ),
        )
    assert mismatch.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_target_population_role_and_cross_challenge_reject() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    other = ChallengeKey("other-challenge", "1.0")
    wrong_role = InstanceDistributionContractRef(
        challenge,
        "practice-population",
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        DIGEST_A,
        "PRACTICE",
    )
    with pytest.raises(qualification.DossierValidationError) as role:
        replace(subjects(challenge), target_population_ref=wrong_role)
    assert role.value.code is qualification.DossierInputCode.ROLE_CONFUSION
    with pytest.raises(qualification.DossierValidationError) as crossed:
        replace(
            subjects(challenge),
            reference_policy_ref=owned(
                "reference_qualification_policy", other, "reference-policy"
            ),
        )
    assert crossed.value.code is qualification.DossierInputCode.CROSS_CHALLENGE


@pytest.mark.parametrize(
    "forbidden",
    (
        qualification.DossierClaimRole.PHYSICAL_SYSTEM_ADEQUACY,
        qualification.DossierClaimRole.TARGET_POPULATION_ADEQUACY,
        qualification.DossierClaimRole.SAMPLING_PLAN_ADEQUACY,
        qualification.DossierClaimRole.CUSTOMER_CONTEXT_OF_USE,
        qualification.DossierClaimRole.PRODUCT_QUALIFICATION,
        qualification.DossierClaimRole.LIVE_ACTIVATION,
    ),
)
def test_mms_cannot_substitute_for_broader_claims(forbidden) -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    mms = evidence_ref(
        challenge,
        qualification.DossierEvidenceClass.MMS_REFINEMENT_OBSERVED_ORDER,
        "mms-study",
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.EvidenceClaimBinding(
            challenge, mms, forbidden, subjects(challenge).claim_scope_ref
        )
    assert caught.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_explicit_artifact_reuse_is_allowed_only_for_mapped_narrow_claims() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    binding = subjects(challenge)
    mms = evidence_ref(
        challenge,
        qualification.DossierEvidenceClass.MMS_REFINEMENT_OBSERVED_ORDER,
        "mms-study",
    )
    mappings = tuple(
        qualification.EvidenceClaimBinding(
            challenge, mms, role, binding.claim_scope_ref
        )
        for role in (
            qualification.DossierClaimRole.IMPLEMENTATION_VERIFICATION,
            qualification.DossierClaimRole.DISCRETIZATION_CONVERGENCE,
            qualification.DossierClaimRole.REFERENCE_AGREEMENT,
        )
    )
    value = manifest(
        qualification.DossierSlot.D7, extra_refs=(mms,), extra_claims=mappings
    )
    assert sum(item.evidence_ref == mms for item in value.claim_bindings) == 3


def test_no_evidence_class_can_claim_customer_product_or_live_authority() -> None:
    forbidden = {
        qualification.DossierClaimRole.CUSTOMER_CONTEXT_OF_USE,
        qualification.DossierClaimRole.PRODUCT_QUALIFICATION,
        qualification.DossierClaimRole.LIVE_ACTIVATION,
    }
    assert all(
        allowed.isdisjoint(forbidden)
        for allowed in qualification.EVIDENCE_CLASS_ALLOWED_CLAIMS.values()
    )


def test_claim_mapping_must_pin_the_manifest_scope_version() -> None:
    value = manifest(qualification.DossierSlot.D3)
    primary = value.evidence_refs[0]
    wrong_scope = owned(
        "claim_scope", value.challenge_key, "registered-claim", version="2.0"
    )
    wrong_mapping = qualification.EvidenceClaimBinding(
        value.challenge_key,
        primary,
        qualification.DossierClaimRole.TARGET_POPULATION_ADEQUACY,
        wrong_scope,
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        replace(value, claim_bindings=(wrong_mapping,))
    assert caught.value.code is qualification.DossierInputCode.VERSION_MISMATCH


@pytest.mark.parametrize(
    ("slot", "wrong_class"),
    (
        (
            qualification.DossierSlot.D6,
            qualification.DossierEvidenceClass.REFERENCE_TRUTH_ADEQUACY,
        ),
        (
            qualification.DossierSlot.D7,
            qualification.DossierEvidenceClass.MEASUREMENT_ADEQUACY_APPLICABILITY,
        ),
        (
            qualification.DossierSlot.D9,
            qualification.DossierEvidenceClass.GENERATOR_DISTRIBUTION_CONFORMANCE,
        ),
    ),
)
def test_generator_reference_and_measurement_primary_roles_do_not_substitute(
    slot, wrong_class
) -> None:
    value = manifest(slot)
    wrong = evidence_ref(value.challenge_key, wrong_class, "wrong-layer")
    wrong_claim = qualification.EvidenceClaimBinding(
        value.challenge_key,
        wrong,
        next(iter(qualification.EVIDENCE_CLASS_ALLOWED_CLAIMS[wrong_class])),
        value.subject_bindings.claim_scope_ref,
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        replace(value, evidence_refs=(wrong,), claim_bindings=(wrong_claim,))
    assert caught.value.code is qualification.DossierInputCode.SLOT_MISMATCH


def test_statistical_manifest_is_structurally_complete_but_policy_pending() -> None:
    value = manifest(qualification.DossierSlot.D10)
    assert (
        value.statistical_scope.authority_status
        is qualification.DependencePolicyAuthorityStatus.OWNER_RATIFICATION_PENDING
    )
    with pytest.raises(qualification.DossierValidationError) as wrong_kind:
        replace(
            value.statistical_scope,
            independence_unit_ref=definition(
                value.challenge_key,
                MeasurementDefinitionKind.SAMPLING_UNIT,
                "different-seed-label",
            ),
        )
    assert wrong_kind.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_component_or_primary_evidence_cannot_substitute_for_coverage() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    component = evidence_ref(
        challenge,
        qualification.DossierEvidenceClass.STATISTICAL_SUFFICIENCY_ESTIMAND_CLARITY,
        "component-uncertainty-table",
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        statistical(challenge, component)
    assert caught.value.code is qualification.DossierInputCode.ROLE_CONFUSION


def test_accounting_preserves_reference_and_candidate_failure_separation() -> None:
    value = manifest(qualification.DossierSlot.D12)
    dispositions = tuple(item.disposition for item in value.accounting.attempts)
    assert qualification.AttemptDisposition.REFERENCE_FAILURE in dispositions
    assert qualification.AttemptDisposition.CANDIDATE_FAILURE in dispositions
    assert (
        qualification.AttemptDisposition.REFERENCE_FAILURE
        is not qualification.AttemptDisposition.CANDIDATE_FAILURE
    )
    duplicate = value.accounting.attempts[0]
    with pytest.raises(qualification.DossierValidationError) as caught:
        replace(value.accounting, attempts=(duplicate, duplicate))
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY


def test_limitations_bind_affected_evidence_claim_and_exact_scope() -> None:
    base = manifest(qualification.DossierSlot.D12)
    limitation = evidence_ref(
        base.challenge_key,
        qualification.DossierEvidenceClass.RESIDUAL_LIMITATION,
        "residual-dependence",
    )
    binding = qualification.LimitationBinding(
        base.challenge_key,
        limitation,
        (base.evidence_refs[0],),
        (qualification.DossierClaimRole.CENSORING_LIMITATIONS,),
        base.subject_bindings.claim_scope_ref,
    )
    value = replace(
        base,
        evidence_refs=(*base.evidence_refs, limitation),
        claim_bindings=(
            *base.claim_bindings,
            qualification.EvidenceClaimBinding(
                base.challenge_key,
                limitation,
                qualification.DossierClaimRole.RESIDUAL_LIMITATION_DISCLOSURE,
                base.subject_bindings.claim_scope_ref,
            ),
        ),
        limitations=(binding,),
    )
    assert value.limitations == (binding,)
    with pytest.raises(qualification.DossierValidationError) as dangling:
        replace(base, limitations=(binding,))
    assert dangling.value.code is qualification.DossierInputCode.MISSING_EVIDENCE
    with pytest.raises(qualification.DossierValidationError) as scope:
        replace(
            value,
            limitations=(
                replace(
                    binding,
                    claim_scope_ref=owned(
                        "claim_scope",
                        base.challenge_key,
                        "registered-claim",
                        version="2.0",
                    ),
                ),
            ),
        )
    assert scope.value.code is qualification.DossierInputCode.VERSION_MISMATCH


def test_canonical_round_trip_order_digest_and_tamper_fail_closed() -> None:
    value = manifest(qualification.DossierSlot.D10)
    reversed_value = replace(
        value,
        evidence_refs=tuple(reversed(value.evidence_refs)),
        claim_bindings=tuple(reversed(value.claim_bindings)),
    )
    encoded = qualification.evidence_manifest_bytes(value)
    assert encoded == qualification.evidence_manifest_bytes(reversed_value)
    assert qualification.load_evidence_manifest(encoded) == value
    assert qualification.evidence_manifest_ref(value).content_digest == (
        qualification.evidence_manifest_digest(value)
    )
    payload = json.loads(
        encoded[len(qualification.EVIDENCE_MANIFEST_DOCUMENT_HEADER) :]
    )
    noncanonical = (
        qualification.EVIDENCE_MANIFEST_DOCUMENT_HEADER + json.dumps(payload).encode()
    )
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_evidence_manifest(noncanonical)
    with pytest.raises(qualification.DossierCanonicalError):
        qualification.load_evidence_manifest(encoded + b"x")
    duplicate = (
        qualification.EVIDENCE_MANIFEST_DOCUMENT_HEADER
        + b'{"record_type":"dossier_evidence_manifest","record_type":"dossier_evidence_manifest"}'
    )
    with pytest.raises(qualification.DossierCanonicalError) as caught:
        qualification.load_evidence_manifest(duplicate)
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY


def test_fixture_propagation_and_supersession_cannot_cleanse_origin() -> None:
    value = manifest(
        qualification.DossierSlot.D11,
        origin=qualification.StructuralOrigin.FIXTURE_ONLY,
    )
    assert value.fixture_derived
    predecessor = qualification.evidence_manifest_ref(value)
    assert predecessor.origin is qualification.StructuralOrigin.FIXTURE_ONLY
    assert (
        qualification.dossier_evidence_ref(value).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )
    successor = manifest(
        qualification.DossierSlot.D11,
        origin=qualification.StructuralOrigin.REGISTERED_REFERENCE,
        supersedes=predecessor,
        version="2.0",
    )
    assert successor.supersedes == predecessor
    assert successor.fixture_derived
    encoded = qualification.evidence_manifest_bytes(successor)
    loaded = qualification.load_evidence_manifest(encoded)
    assert loaded == successor
    assert (
        qualification.evidence_manifest_ref(loaded).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )
    assert (
        qualification.dossier_evidence_ref(loaded).origin
        is qualification.StructuralOrigin.FIXTURE_ONLY
    )
    with pytest.raises(qualification.DossierValidationError):
        replace(successor, manifest_version="1.0")


def test_unresolved_evidence_graph_projects_monotonically() -> None:
    primary_value = manifest(qualification.DossierSlot.D1)
    primary = primary_value.evidence_refs[0]
    unresolved_primary = replace(
        primary, origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )
    primary_value = replace(
        primary_value,
        evidence_refs=(unresolved_primary,),
        claim_bindings=(
            replace(primary_value.claim_bindings[0], evidence_ref=unresolved_primary),
        ),
    )
    assert (
        primary_value.effective_origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )

    value = manifest(qualification.DossierSlot.D10)
    coverage = value.statistical_scope.coverage_evidence_ref
    unresolved_coverage = replace(
        coverage, origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )
    unresolved = replace(
        value,
        evidence_refs=tuple(
            unresolved_coverage if item == coverage else item
            for item in value.evidence_refs
        ),
        claim_bindings=tuple(
            (
                replace(item, evidence_ref=unresolved_coverage)
                if item.evidence_ref == coverage
                else item
            )
            for item in value.claim_bindings
        ),
        statistical_scope=replace(
            value.statistical_scope, coverage_evidence_ref=unresolved_coverage
        ),
    )
    assert (
        unresolved.effective_origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )
    assert (
        qualification.evidence_manifest_ref(unresolved).origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )
    assert (
        qualification.dossier_evidence_ref(unresolved).origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )
    loaded = qualification.load_evidence_manifest(
        qualification.evidence_manifest_bytes(unresolved)
    )
    assert loaded.effective_origin is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED

    accounting_value = manifest(qualification.DossierSlot.D4)
    first_attempt = accounting_value.accounting.attempts[0]
    unresolved_attempt = replace(
        first_attempt,
        attempt_ref=replace(
            first_attempt.attempt_ref,
            origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
        ),
    )
    accounting_value = replace(
        accounting_value,
        accounting=replace(
            accounting_value.accounting,
            attempts=(unresolved_attempt, *accounting_value.accounting.attempts[1:]),
        ),
    )
    assert (
        accounting_value.effective_origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )

    predecessor = replace(
        manifest(qualification.DossierSlot.D11),
        origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
    )
    successor = manifest(
        qualification.DossierSlot.D11,
        version="2.0",
        supersedes=qualification.evidence_manifest_ref(predecessor),
    )
    assert (
        successor.effective_origin is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )


def test_unresolved_limitation_and_affected_evidence_propagate() -> None:
    base = manifest(qualification.DossierSlot.D12)
    limitation_ref = evidence_ref(
        base.challenge_key,
        qualification.DossierEvidenceClass.RESIDUAL_LIMITATION,
        "residual-limitation",
        origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
    )
    limitation = qualification.LimitationBinding(
        base.challenge_key,
        limitation_ref,
        (base.evidence_refs[0],),
        (qualification.DossierClaimRole.CENSORING_LIMITATIONS,),
        base.subject_bindings.claim_scope_ref,
    )
    value = replace(
        base,
        evidence_refs=(*base.evidence_refs, limitation_ref),
        claim_bindings=(
            *base.claim_bindings,
            qualification.EvidenceClaimBinding(
                base.challenge_key,
                limitation_ref,
                qualification.DossierClaimRole.RESIDUAL_LIMITATION_DISCLOSURE,
                base.subject_bindings.claim_scope_ref,
            ),
        ),
        limitations=(limitation,),
    )
    assert (
        limitation.effective_origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )
    assert value.effective_origin is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED

    affected = replace(
        base.evidence_refs[0],
        origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
    )
    affected_limitation = replace(limitation, affected_evidence_refs=(affected,))
    assert (
        affected_limitation.effective_origin
        is qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED
    )


def test_nominal_evidence_conflicts_reject_before_canonical_ordering() -> None:
    value = manifest(qualification.DossierSlot.D1)
    primary = value.evidence_refs[0]
    for conflict in (
        replace(primary, content_digest=DIGEST_A),
        replace(primary, origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED),
        replace(
            primary,
            content_digest=DIGEST_A,
            origin=qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
        ),
    ):
        with pytest.raises(qualification.DossierValidationError) as caught:
            replace(value, evidence_refs=(primary, conflict))
        assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY

    accounting_value = manifest(qualification.DossierSlot.D4)
    attempt = accounting_value.accounting.attempts[0]
    conflicting_attempt = replace(
        attempt,
        attempt_ref=replace(attempt.attempt_ref, content_digest=DIGEST_A),
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        replace(
            accounting_value.accounting,
            attempts=(attempt, conflicting_attempt),
        )
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY

    affected = value.evidence_refs[0]
    limitation = evidence_ref(
        value.challenge_key,
        qualification.DossierEvidenceClass.RESIDUAL_LIMITATION,
        "limitation",
    )
    with pytest.raises(qualification.DossierValidationError) as caught:
        qualification.LimitationBinding(
            value.challenge_key,
            limitation,
            (affected, replace(affected, content_digest=DIGEST_A)),
            (qualification.DossierClaimRole.PHYSICAL_SYSTEM_ADEQUACY,),
            value.subject_bindings.claim_scope_ref,
        )
    assert caught.value.code is qualification.DossierInputCode.DUPLICATE_IDENTITY

    distinct = evidence_ref(
        value.challenge_key,
        qualification.DossierEvidenceClass.MMS_REFINEMENT_OBSERVED_ORDER,
        "distinct-evidence",
    )
    assert replace(value, evidence_refs=(primary, distinct)).evidence_refs


def test_serialized_surface_contains_no_secret_or_locator_fields() -> None:
    payload = qualification.evidence_manifest_payload(
        manifest(qualification.DossierSlot.D11)
    )

    def keys(value: object) -> set[str]:
        if type(value) is dict:
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if type(value) is list:
            return set().union(*(keys(item) for item in value), set())
        return set()

    serialized_keys = keys(payload)
    assert serialized_keys.isdisjoint(
        {
            "seed",
            "official_seed",
            "realization",
            "truth_payload",
            "filesystem_path",
            "network_url",
            "private_provenance",
        }
    )
