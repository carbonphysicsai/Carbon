"""Focused tests for B-04's prospective reference-policy graph."""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import FrozenInstanceError, fields, replace

import pytest

from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.evaluation.enums import (
    DependencyCategory,
    DependencyRelation,
    ReferenceAuthorityFunction,
    ReferenceCompositionKind,
    ReferenceIdentityKind,
    ReferenceSourceClass,
    ResolutionReason,
)
from carbon.evaluation.errors import ReferenceInputCode, ReferenceValidationError
from carbon.evaluation.model import (
    DependencyDisclosure,
    OptionalBinding,
    PinnedReferenceIdentity,
    ReferenceAuthorityTarget,
    ReferenceAuthorityTargetBinding,
    ReferenceProvenance,
    ReferenceScopeBinding,
    ReferenceWitnessTarget,
)
from carbon.evaluation.policy import (
    PrecomputedReferenceSourceManifest,
    ReferenceComposition,
    ReferencePolicy,
    ReferencePolicyEntry,
    expand_authority_target,
    expand_witness_target,
    primary_target_for_composition,
    primary_target_for_entry,
    validate_reference_policy_graph,
    witness_target_for_composition,
    witness_target_for_entry,
)
from carbon.registry.model import ChallengeKey


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('ascii')).hexdigest()}"


def _challenge(name: str = "b04_policy_fixture") -> ChallengeKey:
    return ChallengeKey(name, "1.0")


def _owner(kind: str, label: str, challenge: ChallengeKey) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(challenge),
        object_id=f"b04_{label}_{kind}",
        object_version="1.0",
        content_digest=_digest(f"owner:{challenge}:{label}:{kind}"),
    )


def _top_ref(
    ref_type: type,
    label: str,
    challenge: ChallengeKey,
    *,
    population_role: str | None = None,
) -> object:
    common = (
        challenge,
        f"b04_{label}",
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        _digest(f"top:{challenge}:{label}"),
    )
    if ref_type is InstanceDistributionContractRef:
        assert population_role is not None
        return ref_type(*common, population_role)
    return ref_type(*common)


def _identity(
    kind: ReferenceIdentityKind,
    label: str,
    challenge: ChallengeKey,
) -> PinnedReferenceIdentity:
    return PinnedReferenceIdentity(
        challenge,
        _digest(f"identity:{challenge}:{label}:{kind.value}"),
        f"b04_{label}_{kind.value.lower()}",
        kind,
        "1.0",
    )


def _scope(challenge: ChallengeKey) -> ReferenceScopeBinding:
    return ReferenceScopeBinding(
        _top_ref(CandidateOutputContractRef, "candidate_output", challenge),
        _owner("claim_scope", "scope", challenge),
        _owner("evidence_campaign", "scope", challenge),
        (
            _top_ref(
                InstanceDistributionContractRef,
                "evidence_population",
                challenge,
                population_role="EVIDENCE_CAMPAIGN",
            ),
        ),
        _top_ref(PhysicalSystemSpecRef, "physical_system", challenge),
        _top_ref(
            InstanceDistributionContractRef,
            "proposal_population",
            challenge,
            population_role="OFFICIAL_PROPOSAL_Q",
        ),
        _owner("reference_fidelity_allocation", "scope", challenge),
        _top_ref(SamplingPlanRef, "sampling_plan", challenge),
        _top_ref(
            InstanceDistributionContractRef,
            "target_population",
            challenge,
            population_role="TARGET_WORKLOAD_P",
        ),
        _owner("intended_estimand_or_reporting", "scope", challenge),
    )


def _provenance(
    challenge: ChallengeKey,
    *,
    source_ref: PinnedReferenceIdentity,
    label: str,
) -> ReferenceProvenance:
    disclosures = tuple(
        DependencyDisclosure(
            category,
            (_owner("provenance", f"{label}_dependency_{index}", challenge),),
            DependencyRelation.UNDISCLOSED,
        )
        for index, category in enumerate(DependencyCategory)
    )
    return ReferenceProvenance(
        disclosures,
        _identity(ReferenceIdentityKind.ENVIRONMENT, f"{label}_environment", challenge),
        _owner("evidence_campaign", f"{label}_provenance", challenge),
        (_owner("provenance", f"{label}_generated_code", challenge),),
        _identity(
            ReferenceIdentityKind.IMPLEMENTATION,
            f"{label}_implementation",
            challenge,
        ),
        _identity(ReferenceIdentityKind.METHOD, f"{label}_method", challenge),
        (_owner("provenance", f"{label}_source_provenance", challenge),),
        (_owner("authority_evidence", f"{label}_reviewer", challenge),),
        _owner("rights_profile", f"{label}_rights", challenge),
        source_ref,
    )


def _entry(
    label: str,
    authority: ReferenceAuthorityFunction,
    *,
    challenge: ChallengeKey | None = None,
    scope: ReferenceScopeBinding | None = None,
    role: EvidenceRole = EvidenceRole.NUMERICAL,
    source_class: ReferenceSourceClass = ReferenceSourceClass.DIRECT_REGISTERED_SOURCE,
    source_ref: PinnedReferenceIdentity | None = None,
    representation_ref: PinnedReferenceIdentity | None = None,
    artifact_schema_ref: PinnedReferenceIdentity | None = None,
    precomputed_manifest_ref: OptionalBinding | None = None,
    policy_id: str = "b04_reference_policy",
    policy_version: str = "1.0",
) -> ReferencePolicyEntry:
    active_challenge = challenge or _challenge()
    active_scope = scope or _scope(active_challenge)
    return ReferencePolicyEntry(
        _owner("applicability", label, active_challenge),
        artifact_schema_ref
        or _identity(
            ReferenceIdentityKind.ARTIFACT_SCHEMA,
            "shared_artifact_schema",
            active_challenge,
        ),
        authority,
        active_challenge,
        _owner("sensitivity_analysis", label, active_challenge),
        _owner("replication_dependence_policy", label, active_challenge),
        _identity(
            ReferenceIdentityKind.DEPENDENCY_SET,
            f"{label}_dependencies",
            active_challenge,
        ),
        _owner("disclosure_policy", label, active_challenge),
        f"{label}_entry",
        "1.0",
        _identity(
            ReferenceIdentityKind.ENVIRONMENT,
            f"{label}_environment_constraints",
            active_challenge,
        ),
        EvidenceRoleBinding(role),
        representation_ref
        or _identity(
            ReferenceIdentityKind.REPRESENTATION,
            "shared_representation",
            active_challenge,
        ),
        _identity(
            ReferenceIdentityKind.IMPLEMENTATION,
            f"{label}_implementation_constraints",
            active_challenge,
        ),
        _identity(
            ReferenceIdentityKind.METHOD,
            f"{label}_method_constraints",
            active_challenge,
        ),
        policy_id,
        policy_version,
        (
            precomputed_manifest_ref
            if precomputed_manifest_ref is not None
            else OptionalBinding.absent()
        ),
        _owner("provenance", f"{label}_policy", active_challenge),
        _owner("reference_qualification_policy", label, active_challenge),
        _owner("reference_resource_limit", label, active_challenge),
        _owner("rights_profile", label, active_challenge),
        active_scope,
        source_class,
        source_ref
        or _identity(
            ReferenceIdentityKind.SOURCE,
            f"{label}_source",
            active_challenge,
        ),
        _owner("support_boundary", label, active_challenge),
        _owner("statistics_objective", label, active_challenge),
    )


def _composition(
    label: str,
    authority: ReferenceAuthorityFunction,
    members: tuple[ReferencePolicyEntry, ...],
    *,
    challenge: ChallengeKey | None = None,
    scope: ReferenceScopeBinding | None = None,
    policy_id: str = "b04_reference_policy",
    policy_version: str = "1.0",
) -> ReferenceComposition:
    active_challenge = challenge or _challenge()
    active_scope = scope or _scope(active_challenge)
    representation = members[0].expected_representation_ref
    artifact_schema = members[0].artifact_schema_ref
    return ReferenceComposition(
        _owner("applicability", f"{label}_composition", active_challenge),
        artifact_schema,
        authority,
        active_challenge,
        _identity(
            ReferenceIdentityKind.ENVIRONMENT,
            f"{label}_combination_environment",
            active_challenge,
        ),
        _identity(
            ReferenceIdentityKind.IMPLEMENTATION,
            f"{label}_combination_implementation",
            active_challenge,
        ),
        _identity(
            ReferenceIdentityKind.COMBINATION_METHOD,
            f"{label}_combination_method",
            active_challenge,
        ),
        f"{label}_composition",
        ReferenceCompositionKind.REGISTERED_HYBRID_POLICY,
        "1.0",
        _owner("sensitivity_analysis", f"{label}_composition", active_challenge),
        _owner(
            "replication_dependence_policy",
            f"{label}_composition",
            active_challenge,
        ),
        _owner("disclosure_policy", f"{label}_composition", active_challenge),
        representation,
        tuple(member.to_ref() for member in members),
        policy_id,
        policy_version,
        _owner("provenance", f"{label}_composition", active_challenge),
        _owner(
            "reference_qualification_policy",
            f"{label}_composition",
            active_challenge,
        ),
        _owner("reference_resource_limit", f"{label}_composition", active_challenge),
        _owner("rights_profile", f"{label}_composition", active_challenge),
        active_scope,
        _owner("statistics_objective", f"{label}_composition", active_challenge),
    )


def _policy(
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...] = (),
    *,
    primary: ReferenceAuthorityTarget | None,
    witnesses: tuple[ReferenceWitnessTarget, ...] = (),
    challenge: ChallengeKey | None = None,
    scope: ReferenceScopeBinding | None = None,
) -> ReferencePolicy:
    active_challenge = challenge or _challenge()
    active_scope = scope or _scope(active_challenge)
    primary_binding = (
        ReferenceAuthorityTargetBinding.bound(primary)
        if primary is not None
        else ReferenceAuthorityTargetBinding.absent(
            ResolutionReason.POLICY_PRIMARY_MISSING
        )
    )
    return ReferencePolicy(
        primary_binding,
        _owner("applicability", "policy", active_challenge),
        active_challenge,
        _owner("semantic_equivalence", "policy", active_challenge),
        tuple(item.to_ref() for item in compositions),
        _owner("disclosure_policy", "policy", active_challenge),
        tuple(item.to_ref() for item in entries),
        _owner("restriction", "no_fallback", active_challenge),
        _owner("authoring_registration", "policy", active_challenge),
        "b04_reference_policy",
        "1.0",
        _owner("provenance", "policy", active_challenge),
        _owner("reference_qualification_policy", "policy", active_challenge),
        witnesses,
        _owner("reference_resource_limit", "policy", active_challenge),
        OptionalBinding.absent(),
        _owner("rights_profile", "policy", active_challenge),
        active_scope,
        OptionalBinding.absent(),
        _owner("statistics_objective", "policy", active_challenge),
    )


def _manifest(
    label: str,
    *,
    scope: ReferenceScopeBinding,
    source_ref: PinnedReferenceIdentity,
    representation_ref: PinnedReferenceIdentity,
    artifact_schema_ref: PinnedReferenceIdentity,
    rights_profile_ref: object,
) -> PrecomputedReferenceSourceManifest:
    challenge = scope.challenge_key
    provenance = _provenance(challenge, source_ref=source_ref, label=label)
    provenance = replace(
        provenance,
        evidence_campaign_ref=scope.evidence_campaign_ref,
        rights_profile_ref=rights_profile_ref,
    )
    return PrecomputedReferenceSourceManifest(
        artifact_schema_ref,
        challenge,
        f"{label}_manifest",
        "1.0",
        provenance,
        representation_ref,
        rights_profile_ref,
        scope,
        ReferenceSourceClass.DIRECT_REGISTERED_SOURCE,
        _digest(f"precomputed:{label}"),
        source_ref,
        OptionalBinding.absent(),
    )


def test_policy_records_are_immutable_redacted_and_content_addressed() -> None:
    challenge = _challenge()
    scope = _scope(challenge)
    primary = _entry("primary", ReferenceAuthorityFunction.PRIMARY, scope=scope)
    witness = _entry(
        "witness", ReferenceAuthorityFunction.CORROBORATING_WITNESS, scope=scope
    )
    policy = _policy(
        (primary, witness),
        primary=primary_target_for_entry(primary),
        witnesses=(witness_target_for_entry(witness),),
        scope=scope,
    )

    validate_reference_policy_graph(
        policy,
        entries=(primary, witness),
        compositions=(),
    )
    assert primary.to_ref() == primary.to_ref()
    assert policy.to_ref() == policy.to_ref()
    assert primary.to_ref() != witness.to_ref()

    for record in (primary, witness, policy):
        assert repr(record) == f"{type(record).__name__}(<protected>)"
        assert str(record) == repr(record)
        with pytest.raises(TypeError):
            pickle.dumps(record)
    with pytest.raises(FrozenInstanceError):
        policy.policy_version = "2.0"  # type: ignore[misc]

    with pytest.raises(ReferenceValidationError) as duplicate:
        replace(policy, entry_refs=(primary.to_ref(), primary.to_ref()))
    assert duplicate.value.code == ReferenceInputCode.DUPLICATE_IDENTITY.value


def test_policy_record_field_order_is_exactly_d11() -> None:
    assert tuple(
        field.name for field in fields(PrecomputedReferenceSourceManifest)
    ) == (
        "artifact_schema_ref",
        "challenge_key",
        "manifest_id",
        "manifest_version",
        "provenance_binding",
        "representation_ref",
        "rights_profile_ref",
        "scope_binding",
        "source_class",
        "source_corpus_digest",
        "source_ref",
        "supersedes",
    )
    assert tuple(field.name for field in fields(ReferencePolicyEntry)) == (
        "applicability_policy_ref",
        "artifact_schema_ref",
        "authority_function",
        "challenge_key",
        "conditioning_policy_ref",
        "correlation_policy_ref",
        "dependency_constraints_ref",
        "disclosure_policy_ref",
        "entry_id",
        "entry_version",
        "environment_constraints_ref",
        "evidence_role_binding",
        "expected_representation_ref",
        "implementation_constraints_ref",
        "method_constraints_ref",
        "policy_id",
        "policy_version",
        "precomputed_source_manifest_ref",
        "provenance_policy_ref",
        "qualification_policy_ref",
        "resource_policy_ref",
        "rights_profile_ref",
        "scope_binding",
        "source_class",
        "source_ref",
        "support_boundary_ref",
        "uncertainty_policy_ref",
    )
    assert tuple(field.name for field in fields(ReferenceComposition)) == (
        "applicability_policy_ref",
        "artifact_schema_ref",
        "authority_function",
        "challenge_key",
        "combination_environment_ref",
        "combination_implementation_ref",
        "combination_method_ref",
        "composition_id",
        "composition_kind",
        "composition_version",
        "conditioning_policy_ref",
        "correlation_policy_ref",
        "disclosure_policy_ref",
        "expected_representation_ref",
        "member_entry_refs",
        "policy_id",
        "policy_version",
        "provenance_policy_ref",
        "qualification_policy_ref",
        "resource_policy_ref",
        "rights_profile_ref",
        "scope_binding",
        "uncertainty_policy_ref",
    )
    assert tuple(field.name for field in fields(ReferencePolicy)) == (
        "answer_key_authority_target",
        "applicability_policy_ref",
        "challenge_key",
        "comparison_policy_ref",
        "composition_refs",
        "disclosure_policy_ref",
        "entry_refs",
        "fallback_policy_ref",
        "history_binding_ref",
        "policy_id",
        "policy_version",
        "provenance_policy_ref",
        "qualification_policy_ref",
        "registered_witness_targets",
        "resource_policy_ref",
        "revocation_binding_ref",
        "rights_profile_ref",
        "scope_binding",
        "supersedes",
        "uncertainty_policy_ref",
    )


def test_policy_rejections_do_not_echo_or_pickle_hostile_values() -> None:
    secret = "protected-case-secret\nnot-canonical"
    entry = _entry("primary", ReferenceAuthorityFunction.PRIMARY)
    with pytest.raises(ReferenceValidationError) as caught:
        replace(entry, entry_id=secret)
    error = caught.value
    assert secret not in str(error)
    assert secret not in repr(error)
    assert error.__cause__ is None
    assert error.__context__ is None
    with pytest.raises(TypeError):
        pickle.dumps(error)


@pytest.mark.parametrize("source_class", tuple(ReferenceSourceClass))
def test_source_class_does_not_select_primary_authority(
    source_class: ReferenceSourceClass,
) -> None:
    primary = _entry(
        f"source_{source_class.name.lower()}",
        ReferenceAuthorityFunction.PRIMARY,
        source_class=source_class,
    )
    assert primary_target_for_entry(primary).entry_ref == primary.to_ref()


def test_mms_is_verification_only_and_cannot_transfer_authority() -> None:
    verification = _entry(
        "mms_verification",
        ReferenceAuthorityFunction.VERIFICATION_ANCHOR,
        role=EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION,
    )
    assert (
        verification.authority_function
        is ReferenceAuthorityFunction.VERIFICATION_ANCHOR
    )

    for forbidden in (
        ReferenceAuthorityFunction.PRIMARY,
        ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        ReferenceAuthorityFunction.VALIDATION_ANCHOR,
        ReferenceAuthorityFunction.REGISTERED_COMPONENT,
    ):
        with pytest.raises(ReferenceValidationError) as caught:
            _entry(
                f"mms_{forbidden.name.lower()}",
                forbidden,
                role=EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION,
            )
        assert caught.value.code == ReferenceInputCode.ROLE_MISMATCH.value

    with pytest.raises(ReferenceValidationError):
        primary_target_for_entry(verification)


def test_registered_composition_is_ordered_distinct_and_component_only() -> None:
    scope = _scope(_challenge())
    first = _entry(
        "component_first", ReferenceAuthorityFunction.REGISTERED_COMPONENT, scope=scope
    )
    second = _entry(
        "component_second", ReferenceAuthorityFunction.REGISTERED_COMPONENT, scope=scope
    )
    primary = _composition(
        "primary_hybrid",
        ReferenceAuthorityFunction.PRIMARY,
        (first, second),
        scope=scope,
    )
    reversed_primary = _composition(
        "primary_hybrid",
        ReferenceAuthorityFunction.PRIMARY,
        (second, first),
        scope=scope,
    )
    assert primary.to_ref() != reversed_primary.to_ref()
    assert expand_authority_target(
        primary_target_for_composition(primary),
        entries=(first, second),
        compositions=(primary,),
    ) == (first.to_ref(), second.to_ref())

    with pytest.raises(ReferenceValidationError):
        _composition(
            "single_member", ReferenceAuthorityFunction.PRIMARY, (first,), scope=scope
        )
    with pytest.raises(ReferenceValidationError) as duplicate:
        _composition(
            "duplicate_member",
            ReferenceAuthorityFunction.PRIMARY,
            (first, first),
            scope=scope,
        )
    assert duplicate.value.code == ReferenceInputCode.DUPLICATE_IDENTITY.value

    wrong_member = _entry(
        "wrong_member", ReferenceAuthorityFunction.PRIMARY, scope=scope
    )
    wrong_composition = _composition(
        "wrong_member_hybrid",
        ReferenceAuthorityFunction.PRIMARY,
        (wrong_member, second),
        scope=scope,
    )
    wrong_policy = _policy(
        (wrong_member, second),
        (wrong_composition,),
        primary=primary_target_for_composition(wrong_composition),
        scope=scope,
    )
    with pytest.raises(ReferenceValidationError) as caught:
        validate_reference_policy_graph(
            wrong_policy,
            entries=(wrong_member, second),
            compositions=(wrong_composition,),
        )
    assert caught.value.code == ReferenceInputCode.ROLE_MISMATCH.value

    stale_version = replace(first, policy_version="2.0")
    stale_version_composition = _composition(
        "stale_version_hybrid",
        ReferenceAuthorityFunction.PRIMARY,
        (stale_version, second),
        scope=scope,
    )
    with pytest.raises(ReferenceValidationError) as stale_version_error:
        expand_authority_target(
            primary_target_for_composition(stale_version_composition),
            entries=(stale_version, second),
            compositions=(stale_version_composition,),
        )
    assert stale_version_error.value.code == ReferenceInputCode.STALE_BINDING.value

    stale_scope = replace(
        scope,
        truth_target_ref=_owner(
            "intended_estimand_or_reporting", "other", _challenge()
        ),
    )
    stale_scope_member = replace(first, scope_binding=stale_scope)
    stale_scope_composition = _composition(
        "stale_scope_hybrid",
        ReferenceAuthorityFunction.PRIMARY,
        (stale_scope_member, second),
        scope=scope,
    )
    with pytest.raises(ReferenceValidationError) as stale_scope_error:
        expand_authority_target(
            primary_target_for_composition(stale_scope_composition),
            entries=(stale_scope_member, second),
            compositions=(stale_scope_composition,),
        )
    assert stale_scope_error.value.code == ReferenceInputCode.STALE_BINDING.value


def test_expanded_primary_and_witness_compositions_must_be_disjoint() -> None:
    scope = _scope(_challenge())
    shared = _entry(
        "shared", ReferenceAuthorityFunction.REGISTERED_COMPONENT, scope=scope
    )
    primary_only = _entry(
        "primary_only", ReferenceAuthorityFunction.REGISTERED_COMPONENT, scope=scope
    )
    witness_only = _entry(
        "witness_only", ReferenceAuthorityFunction.REGISTERED_COMPONENT, scope=scope
    )
    primary = _composition(
        "primary_composition",
        ReferenceAuthorityFunction.PRIMARY,
        (shared, primary_only),
        scope=scope,
    )
    witness = _composition(
        "witness_composition",
        ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        (shared, witness_only),
        scope=scope,
    )
    entries = (shared, primary_only, witness_only)
    compositions = (primary, witness)
    policy = _policy(
        entries,
        compositions,
        primary=primary_target_for_composition(primary),
        witnesses=(witness_target_for_composition(witness),),
        scope=scope,
    )

    with pytest.raises(ReferenceValidationError) as caught:
        validate_reference_policy_graph(
            policy,
            entries=entries,
            compositions=compositions,
        )
    assert caught.value.code == ReferenceInputCode.ROLE_MISMATCH.value


def test_exact_inventory_scope_and_policy_version_are_fail_closed() -> None:
    scope = _scope(_challenge())
    primary = _entry("primary", ReferenceAuthorityFunction.PRIMARY, scope=scope)
    witness = _entry(
        "witness", ReferenceAuthorityFunction.CORROBORATING_WITNESS, scope=scope
    )
    policy = _policy(
        (primary, witness),
        primary=primary_target_for_entry(primary),
        witnesses=(witness_target_for_entry(witness),),
        scope=scope,
    )

    with pytest.raises(ReferenceValidationError) as stale_order:
        validate_reference_policy_graph(
            policy,
            entries=(witness, primary),
            compositions=(),
        )
    assert stale_order.value.code == ReferenceInputCode.STALE_BINDING.value

    stale_version = replace(
        witness,
        policy_version="2.0",
    )
    stale_policy = replace(
        policy,
        entry_refs=(primary.to_ref(), stale_version.to_ref()),
        registered_witness_targets=(witness_target_for_entry(stale_version),),
    )
    with pytest.raises(ReferenceValidationError) as caught:
        validate_reference_policy_graph(
            stale_policy,
            entries=(primary, stale_version),
            compositions=(),
        )
    assert caught.value.code == ReferenceInputCode.STALE_BINDING.value

    other_challenge = _challenge("other_b04_policy_fixture")
    with pytest.raises(ReferenceValidationError) as cross_challenge:
        replace(policy, challenge_key=other_challenge)
    assert cross_challenge.value.code == ReferenceInputCode.CROSS_CHALLENGE.value


def test_representation_matching_is_target_local_not_anchor_authority() -> None:
    challenge = _challenge()
    scope = _scope(challenge)
    primary = _entry("primary", ReferenceAuthorityFunction.PRIMARY, scope=scope)
    witness = _entry(
        "witness", ReferenceAuthorityFunction.CORROBORATING_WITNESS, scope=scope
    )
    other_representation = _identity(
        ReferenceIdentityKind.REPRESENTATION,
        "anchor_representation",
        challenge,
    )
    anchor = _entry(
        "verification_anchor",
        ReferenceAuthorityFunction.VERIFICATION_ANCHOR,
        scope=scope,
        representation_ref=other_representation,
    )
    policy = _policy(
        (primary, witness, anchor),
        primary=primary_target_for_entry(primary),
        witnesses=(witness_target_for_entry(witness),),
        scope=scope,
    )
    validate_reference_policy_graph(
        policy,
        entries=(primary, witness, anchor),
        compositions=(),
    )

    mismatched_witness = replace(
        witness,
        expected_representation_ref=other_representation,
    )
    mismatched_policy = _policy(
        (primary, mismatched_witness),
        primary=primary_target_for_entry(primary),
        witnesses=(witness_target_for_entry(mismatched_witness),),
        scope=scope,
    )
    with pytest.raises(ReferenceValidationError) as mismatch:
        validate_reference_policy_graph(
            mismatched_policy,
            entries=(primary, mismatched_witness),
            compositions=(),
        )
    assert mismatch.value.code == ReferenceInputCode.STALE_BINDING.value


def test_precomputed_manifest_must_match_every_entry_binding() -> None:
    challenge = _challenge()
    scope = _scope(challenge)
    source = _identity(ReferenceIdentityKind.SOURCE, "precomputed_source", challenge)
    representation = _identity(
        ReferenceIdentityKind.REPRESENTATION, "shared_representation", challenge
    )
    artifact_schema = _identity(
        ReferenceIdentityKind.ARTIFACT_SCHEMA, "shared_artifact_schema", challenge
    )
    rights = _owner("rights_profile", "precomputed", challenge)
    manifest = _manifest(
        "precomputed",
        scope=scope,
        source_ref=source,
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        rights_profile_ref=rights,
    )
    primary = _entry(
        "precomputed",
        ReferenceAuthorityFunction.PRIMARY,
        scope=scope,
        source_ref=source,
        representation_ref=representation,
        artifact_schema_ref=artifact_schema,
        precomputed_manifest_ref=OptionalBinding.present(manifest.to_ref()),
    )
    primary = replace(primary, rights_profile_ref=rights)
    policy = _policy((primary,), primary=primary_target_for_entry(primary), scope=scope)
    validate_reference_policy_graph(
        policy,
        entries=(primary,),
        compositions=(),
        precomputed_manifests=(manifest,),
    )

    with pytest.raises(ReferenceValidationError) as stale_rights:
        replace(
            manifest,
            provenance_binding=replace(
                manifest.provenance_binding,
                rights_profile_ref=_owner("rights_profile", "wrong", challenge),
            ),
        )
    assert stale_rights.value.code == ReferenceInputCode.STALE_BINDING.value

    with pytest.raises(ReferenceValidationError) as stale_campaign:
        replace(
            manifest,
            provenance_binding=replace(
                manifest.provenance_binding,
                evidence_campaign_ref=_owner("evidence_campaign", "wrong", challenge),
            ),
        )
    assert stale_campaign.value.code == ReferenceInputCode.STALE_BINDING.value

    stale_manifest = replace(
        manifest,
        representation_ref=_identity(
            ReferenceIdentityKind.REPRESENTATION,
            "wrong_representation",
            challenge,
        ),
    )
    stale_primary = replace(
        primary,
        precomputed_source_manifest_ref=OptionalBinding.present(
            stale_manifest.to_ref()
        ),
    )
    stale_policy = _policy(
        (stale_primary,), primary=primary_target_for_entry(stale_primary), scope=scope
    )
    with pytest.raises(ReferenceValidationError) as caught:
        validate_reference_policy_graph(
            stale_policy,
            entries=(stale_primary,),
            compositions=(),
            precomputed_manifests=(stale_manifest,),
        )
    assert caught.value.code == ReferenceInputCode.STALE_BINDING.value


def test_unresolved_policy_has_no_default_primary_or_fallback_target() -> None:
    scope = _scope(_challenge())
    anchor = _entry(
        "verification_anchor",
        ReferenceAuthorityFunction.VERIFICATION_ANCHOR,
        scope=scope,
    )
    policy = _policy((anchor,), primary=None, scope=scope)
    validate_reference_policy_graph(
        policy,
        entries=(anchor,),
        compositions=(),
    )
    assert not policy.answer_key_authority_target.is_bound
    assert policy.registered_witness_targets == ()
    assert "fallback_target" not in {field.name for field in fields(ReferencePolicy)}

    with pytest.raises(ReferenceValidationError) as incompatible_absence:
        replace(
            policy,
            answer_key_authority_target=ReferenceAuthorityTargetBinding.absent(
                ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED
            ),
        )
    assert (
        incompatible_absence.value.code
        == ReferenceInputCode.OUTCOME_REASON_MISMATCH.value
    )


def test_policy_schema_has_no_solver_language_tolerance_or_agreement_authority() -> (
    None
):
    entry_fields = {field.name for field in fields(ReferencePolicyEntry)}
    composition_fields = {field.name for field in fields(ReferenceComposition)}
    policy_fields = {field.name for field in fields(ReferencePolicy)}
    forbidden = {
        "solver",
        "solver_name",
        "language",
        "tolerance",
        "agreement",
        "authority_by_agreement",
        "fallback_targets",
        "truth_mode",
    }
    assert entry_fields.isdisjoint(forbidden)
    assert composition_fields.isdisjoint(forbidden)
    assert policy_fields.isdisjoint(forbidden)

    scope = _scope(_challenge())
    primary = _entry("primary", ReferenceAuthorityFunction.PRIMARY, scope=scope)
    witness = _entry(
        "witness", ReferenceAuthorityFunction.CORROBORATING_WITNESS, scope=scope
    )
    with pytest.raises(ReferenceValidationError):
        witness_target_for_entry(primary)
    with pytest.raises(ReferenceValidationError):
        primary_target_for_entry(witness)

    raw_witness_target = ReferenceWitnessTarget.single_witness_entry(primary.to_ref())
    wrong_witness_policy = _policy(
        (primary,),
        primary=primary_target_for_entry(primary),
        witnesses=(raw_witness_target,),
        scope=scope,
    )
    with pytest.raises(ReferenceValidationError) as wrong_witness:
        validate_reference_policy_graph(
            wrong_witness_policy,
            entries=(primary,),
            compositions=(),
        )
    assert wrong_witness.value.code == ReferenceInputCode.ROLE_MISMATCH.value

    raw_primary_target = ReferenceAuthorityTarget.single_primary_entry(witness.to_ref())
    wrong_primary_policy = _policy(
        (witness,),
        primary=raw_primary_target,
        scope=scope,
    )
    with pytest.raises(ReferenceValidationError) as wrong_primary:
        validate_reference_policy_graph(
            wrong_primary_policy,
            entries=(witness,),
            compositions=(),
        )
    assert wrong_primary.value.code == ReferenceInputCode.ROLE_MISMATCH.value

    assert expand_witness_target(
        witness_target_for_entry(witness),
        entries=(primary, witness),
        compositions=(),
    ) == (witness.to_ref(),)
