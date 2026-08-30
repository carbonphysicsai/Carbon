"""Focused B-02A model, role, and canonical identity tests."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, replace
from dataclasses import fields as dataclass_fields

import pytest

from carbon.authoring.canonical import decode_document
from carbon.authoring.cases import (
    AnalyticCaseSource,
    CanonicalChallengeCase,
    CaseProjectionVerificationEcho,
    CaseSourceBinding,
    CaseSourceKind,
    ManufacturedSolutionCaseSource,
    PublicCaseFactBinding,
    RelatedPopulationBinding,
    _issue_case_projection_authority,
    issue_public_case_projection,
    require_public_case_projection,
)
from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.evidence import (
    CanonicalCaseDisposition,
    CaseEvidenceBinding,
    CaseEvidenceBindingAuthorization,
    CaseStatePayload,
    CensoringRecord,
    CensoringTrigger,
    CensoringTriggerKind,
    EvidenceAccountingCapability,
    EvidenceAccountingFinalizationEcho,
    EvidenceAccountingVerificationEcho,
    EvidenceRoleBinding,
    EvidenceScopeBinding,
    ExcludedCasePayload,
    FinalizedEvidenceAccountingCapability,
    GenerationFailurePayload,
    RealizedEvidenceLoadVerificationEcho,
    ReplacementDecision,
    ReplacementDecisionKind,
    ReplacementPolicyBinding,
    ReplacementPolicyBindingKind,
    ValidCasePayload,
    _finalize_evidence_accounting,
    _issue_case_evidence_binding_authority,
    _issue_evidence_accounting_capability,
    _issue_realized_evidence_load_authority,
    construct_realized_valid_evidence,
    load_derived_evidence,
    reject_evidence_role_relabel,
    validate_censoring_against_plan,
)
from carbon.authoring.model import (
    AllowedConsumer,
    AllowedConsumerKind,
    ApplicabilityBinding,
    CasePopulationUse,
    CaseState,
    CensoringReason,
    DisclosureClass,
    DisclosureContract,
    EvidenceRole,
    PopulationRole,
    PrecisionLiteral,
    PublicCaseFactKind,
    SamplingRole,
    WeightingRole,
    authored_object_from_record,
    canonical_set_tuple,
    validate_loaded_authoring_graph,
)
from carbon.authoring.physical import (
    AxisContract,
    AxisExtent,
    AxisExtentKind,
    BoundaryConditionContract,
    BoundaryRegionClause,
    CandidateInputBinding,
    CandidateInputRelation,
    CandidateInputRelationKind,
    CandidateOutputBinding,
    CandidateOutputContract,
    CandidateOutputRelation,
    CandidateOutputRelationKind,
    InitialConditionContract,
    InitialStateClause,
    PhysicalSystemSpec,
    Presence,
    PresenceKind,
    TimeContract,
    TimeHorizonBinding,
    TimeMode,
    ValueFieldContract,
    validate_candidate_against_physical,
)
from carbon.authoring.populations import (
    ExclusionContract,
    FiniteEnumeration,
    InstanceDistributionContract,
    LawKind,
    LawSemantics,
    SupportContract,
    WeightingPayload,
    WeightingSemantics,
    WeightingSemanticsKind,
)
from carbon.authoring.primitives import (
    CANONICALIZATION_PROFILE,
    DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    GlobalScope,
    InstanceDistributionContractRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.authoring.sampling import (
    CandidateOutcomeAccessBinding,
    CandidateOutcomeAccessKind,
    DuplicatePolicy,
    FiniteDesignMode,
    FiniteEvidenceDesign,
    ProspectiveStoppingExtensionPolicy,
    ReplacementPolicy,
    ReplacementPolicyKind,
    ReplacementTrigger,
    ReplacementTriggerKind,
    SamplingPlan,
)
from carbon.authoring.training_support import (
    PermittedGeneratorBinding,
    PermittedGeneratorKind,
    TrainingMembershipContract,
    TrainingSupportContract,
)
from carbon.registry import ChallengeKey

_DIGEST = "sha256:" + "0" * 64
_KEY = ChallengeKey("fixture_authoring", "1.0")
_SCOPE = GlobalScope()


def _owner(kind: str, object_id: str) -> object:
    return owner_ref(
        kind,
        scope_binding=_SCOPE,
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _na(object_id: str = "not_applicable") -> ApplicabilityBinding[object]:
    return ApplicabilityBinding.not_applicable(
        _owner("applicability_reason", object_id)
    )


def _sampling_ref() -> SamplingPlanRef:
    return SamplingPlanRef(
        _KEY,
        "official_sampling_plan",
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _population_ref(
    role: PopulationRole, object_id: str
) -> InstanceDistributionContractRef:
    return InstanceDistributionContractRef(
        _KEY,
        object_id,
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _DIGEST,
        role.value,
    )


def _case_ref() -> CanonicalChallengeCaseRef:
    return CanonicalChallengeCaseRef(
        _KEY,
        "canonical_case",
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _DIGEST,
        DisclosureClass.PROTECTED.value,
    )


def _disclosure() -> DisclosureContract:
    return DisclosureContract(
        public_field_ids=(),
        internal_field_ids=(),
        protected_field_ids=(),
        aggregation_policy_ref=_owner("aggregation_policy", "aggregate"),
        release_policy_ref=_owner("release_policy", "release"),
    )


def _value(field_id: str) -> ValueFieldContract:
    return ValueFieldContract(
        field_id=field_id,
        semantic_role_ref=_owner("semantic_clause", f"{field_id}_semantic"),
        representation_ref=_owner("representation", "dense_array"),
        unit_ref=_owner("unit", "dimensionless"),
        shape_contract=(
            AxisContract(
                axis_id="space",
                semantic_role_ref=_owner("semantic_clause", "space_axis"),
                unit_ref=_owner("unit", "dimensionless"),
                extent=AxisExtent(AxisExtentKind.FIXED, fixed_extent=2),
            ),
        ),
        precision_contract=(PrecisionLiteral.FLOAT64,),
        geometry_binding=ApplicabilityBinding.bound(
            _owner("geometry_domain", "line_domain")
        ),
        presence=Presence(PresenceKind.REQUIRED),
        admissibility_refs=(),
        nonfinite_policy="REJECT",
    )


def _physical() -> PhysicalSystemSpec:
    return PhysicalSystemSpec(
        object_kind="physical_system_spec",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="physical_job",
        object_version="1.0",
        supersedes=_na("first_physical_version"),
        governing_job_ref=_owner("semantic_clause", "physical_job_semantics"),
        governing_law_refs=(_owner("semantic_clause", "governing_law"),),
        assumptions=(),
        causal_inputs=(_value("forcing"),),
        required_physical_quantities=(_value("state"),),
        geometry_domain_ref=_owner("geometry_domain", "line_domain"),
        boundary_conditions=BoundaryConditionContract(()),
        initial_conditions=InitialConditionContract(()),
        time_contract=TimeContract(
            mode=TimeMode.STEADY,
            time_coordinate_binding=_na("steady_time"),
            horizon_binding=_na("steady_horizon"),
            endpoint_inclusion_semantic_ref=_owner(
                "semantic_clause", "steady_endpoint"
            ),
            time_unit_ref=_owner("unit", "dimensionless"),
        ),
        operating_envelope_ref=_owner("operating_envelope", "fixture_envelope"),
        claim_scope_ref=_owner("claim_scope", "fixture_claim"),
        missing_input_policy="REJECT",
    )


def _candidate(physical: PhysicalSystemSpec) -> CandidateOutputContract:
    return CandidateOutputContract(
        object_kind="candidate_output_contract",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="candidate_contract",
        object_version="1.0",
        supersedes=_na("first_candidate_version"),
        physical_system_ref=physical.to_ref(),
        candidate_inputs=(
            replace(physical.causal_inputs[0], field_id="candidate_forcing"),
        ),
        causal_input_bindings=(
            CandidateInputBinding(
                physical_field_id="forcing",
                candidate_field_id="candidate_forcing",
                relation=CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
        ),
        required_outputs=(
            replace(
                physical.required_physical_quantities[0],
                field_id="candidate_state",
            ),
        ),
        physical_output_bindings=(
            CandidateOutputBinding(
                physical_quantity_id="state",
                candidate_field_id="candidate_state",
                relation=CandidateOutputRelation(CandidateOutputRelationKind.IDENTITY),
                semantic_equivalence_ref=_owner(
                    "semantic_equivalence", "state_equivalence"
                ),
            ),
        ),
        candidate_representation_ref=_owner("representation", "candidate_io"),
        geometry_domain_ref=physical.geometry_domain_ref,
        boundary_input_bindings=(),
        initial_input_bindings=(),
        time_horizon_binding=TimeHorizonBinding(
            candidate_field_ids=(),
            time_coordinate_equivalence_ref=_owner(
                "semantic_equivalence", "steady_time_equivalence"
            ),
            horizon_equivalence_ref=_owner(
                "semantic_equivalence", "steady_horizon_equivalence"
            ),
            endpoint_equivalence_ref=_owner(
                "semantic_equivalence", "steady_endpoint_equivalence"
            ),
        ),
        operating_envelope_ref=physical.operating_envelope_ref,
        claim_scope_ref=physical.claim_scope_ref,
        missing_or_extra_policy="REJECT",
        malformed_output_policy="CANDIDATE_FORMAT_FAILURE",
    )


def _support() -> SupportContract:
    return SupportContract(
        membership_rule_ref=_owner("membership_rule", "fixture_membership"),
        physical_support_ref=_owner("physical_support", "fixture_physical_support"),
        representation_support_ref=_owner(
            "representation_support", "fixture_representation_support"
        ),
        boundary_semantics_ref=_owner("support_boundary", "closed_boundary"),
        membership_decision_ref=_owner(
            "membership_decision", "fixture_membership_decision"
        ),
        failure_outcome="REJECT",
    )


def _population(
    role: PopulationRole,
    physical: PhysicalSystemSpec,
    candidate: CandidateOutputContract,
    *,
    target_binding: ApplicabilityBinding[object] | None = None,
    proposal_binding: ApplicabilityBinding[object] | None = None,
    estimand_ref: object | None = None,
) -> InstanceDistributionContract:
    law = (
        LawSemantics(
            LawKind.FINITE_ENUMERATION,
            FiniteEnumeration(
                _owner("member_set", "fixture_members"),
                _owner("multiplicity_semantics", "fixture_multiplicity"),
            ),
        )
        if role is PopulationRole.OFFICIAL_PROPOSAL_Q
        else (
            LawSemantics(
                LawKind.NOT_A_PROBABILITY_LAW,
                _owner("non_probability_reason", "weighting_is_not_probability"),
            )
            if role is PopulationRole.EVIDENCE_WEIGHT_W
            else LawSemantics(
                LawKind.SET_MEMBERSHIP_ONLY,
                _owner("no_prevalence_claim", "membership_only"),
            )
        )
    )
    weighting = (
        WeightingSemantics(
            WeightingSemanticsKind.WEIGHTING,
            WeightingPayload(
                weighting_role=WeightingRole.SCIENTIFIC_EVIDENCE_WEIGHT,
                estimand_scope_ref=estimand_ref
                or _owner("estimand_scope", "fixture_estimand"),
                weighting_rule_ref=_owner("weighting_rule", "fixture_weight"),
                normalization_semantics_ref=_owner(
                    "weight_normalization", "fixture_normalization"
                ),
                target_population_ref=target_binding.value,
                proposal_population_binding=proposal_binding
                or _na("no_weighting_proposal"),
            ),
        )
        if role is PopulationRole.EVIDENCE_WEIGHT_W
        else WeightingSemantics(
            WeightingSemanticsKind.NOT_APPLICABLE,
            _owner("applicability_reason", "no_weighting_semantics"),
        )
    )
    return InstanceDistributionContract(
        object_kind="instance_distribution_contract",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id=f"population_{role.value.lower()}",
        object_version="1.0",
        supersedes=_na(f"first_{role.value.lower()}"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        population_role=role,
        owning_claim_scope_ref=physical.claim_scope_ref,
        target_population_binding=target_binding or _na("no_target_binding"),
        proposal_population_binding=proposal_binding or _na("no_proposal_binding"),
        support_contract=_support(),
        law_semantics=law,
        weighting_semantics=weighting,
        stratification_binding=_na("no_stratification"),
        applicability_refs=(_owner("applicability", "fixture_applicability"),),
        exclusions=(),
        rights_profile_ref=_owner("rights_profile", "fixture_rights"),
        permitted_use_refs=(_owner("permitted_use", "fixture_use"),),
        restrictions=(),
        disclosure_contract=_disclosure(),
        allowed_consumers=(
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE, CasePopulationUse.PRIMARY
            ),
            AllowedConsumer(
                AllowedConsumerKind.SAMPLING_PLAN,
                SamplingRole.OFFICIAL_EVALUATION,
            ),
        ),
        population_provenance=(_owner("provenance", "fixture_provenance"),),
    )


def _fixed_sampling_plan(
    p: InstanceDistributionContract,
    q: InstanceDistributionContract,
    *,
    w: InstanceDistributionContract | None,
    estimand_ref: object,
) -> SamplingPlan:
    return SamplingPlan(
        object_kind="sampling_plan",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="official_sampling_plan",
        object_version="1.0",
        supersedes=_na("first_sampling_plan"),
        sampling_role=SamplingRole.OFFICIAL_EVALUATION,
        primary_population_ref=p.to_ref(),
        selection_population_ref=q.to_ref(),
        target_population_binding=ApplicabilityBinding.bound(p.to_ref()),
        official_proposal_binding=ApplicabilityBinding.bound(q.to_ref()),
        evidence_weight_binding=(
            ApplicabilityBinding.bound(w.to_ref())
            if w is not None
            else _na("nonaggregating_evidence_use")
        ),
        query_population_binding=_na("no_query_population"),
        observation_population_binding=_na("no_observation_population"),
        evidence_campaign_binding=_na("no_official_campaign"),
        intended_estimand_or_reporting_ref=estimand_ref,
        finite_evidence_design=FiniteEvidenceDesign(
            count_unit_ref=_owner("sampling_unit", "case"),
            design_mode=FiniteDesignMode.FIXED,
            base_intended_count=2,
            base_evidence_requirement_ref=_owner(
                "base_evidence_requirement", "fixture_base_requirement"
            ),
            budget_binding=_na("fixed_no_budget"),
            extension_ceiling_binding=_na("fixed_no_extension"),
            heuristic_stop_outcome="EVIDENCE_DEFERRED",
            insufficiency_state="INDETERMINATE",
            insufficiency_reason="INSUFFICIENT_EVIDENCE",
            plan_change_rule="NEW_VERSION_REQUIRED",
        ),
        full_design_law_ref=_owner("full_design_law", "fixture_design"),
        stratified_allocation_binding=_na("unstratified"),
        query_observation_allocation_binding=_na("no_query_allocation"),
        reference_fidelity_allocation_binding=_na("no_reference_allocation"),
        replication_dependence_policy_ref=_owner(
            "replication_dependence_policy", "fixture_dependence"
        ),
        uncertainty_resolution_objectives_binding=_na("no_uncertainty_objective"),
        tail_resolution_objectives_binding=_na("no_tail_objective"),
        minimum_subgroup_objectives_binding=_na("no_subgroup_objective"),
        draw_order_semantics_ref=_owner("draw_order_semantics", "fixture_order"),
        stopping_extension_policy=ProspectiveStoppingExtensionPolicy(
            stopping_rule_ref=_owner("stopping_rule", "fixed_completion"),
            extension_rule_binding=_na("fixed_no_extension_rule"),
            interim_look_binding=_na("fixed_no_interim"),
            sequential_allocation_binding=_na("fixed_no_sequential_allocation"),
            candidate_outcome_access_binding=CandidateOutcomeAccessBinding(
                CandidateOutcomeAccessKind.CANDIDATE_OUTCOMES_PROHIBITED,
                _owner("blinding_policy", "fixture_blinding"),
            ),
            coverage_qualification_binding=_na("fixed_no_coverage"),
            modification_authority_ref=_owner(
                "modification_authority", "fixture_modification"
            ),
        ),
        replacement_policy=ReplacementPolicy(ReplacementPolicyKind.NEVER, None),
        duplicate_policy=DuplicatePolicy(
            physical_duplicate_rule_ref=_owner("duplicate_rule", "physical"),
            representation_duplicate_rule_ref=_owner(
                "duplicate_rule", "representation"
            ),
            near_duplicate_rule_ref=_owner("duplicate_rule", "near"),
            repeated_observation_rule_ref=_owner("duplicate_rule", "observation"),
            replacement_duplicate_rule_ref=_owner("duplicate_rule", "replacement"),
        ),
        inclusion_policy_ref=_owner("inclusion_policy", "fixture_inclusion"),
        exclusion_policy_ref=_owner("exclusion_policy", "fixture_exclusion"),
        censoring_policy_ref=_owner("censoring_policy", "fixture_censoring"),
        public_authored_facts=(),
        protected_realization_fields=(),
        statistical_qualification_requirements_ref=_owner(
            "statistical_qualification_requirement", "fixture_qualification"
        ),
        plan_provenance_refs=(_owner("provenance", "fixture_plan"),),
        insufficient_or_failure_policy="NON_SETTLING_FAIL_CLOSED",
    )


def _evidence_scope() -> EvidenceScopeBinding:
    return EvidenceScopeBinding(
        evidence_campaign_binding=_na("no_campaign"),
        query_population_binding=_na("no_query"),
        observation_population_binding=_na("no_observation"),
        intended_estimand_or_reporting_ref=_owner(
            "intended_estimand_or_reporting", "nonaggregating_fixture"
        ),
        measurement_applicability_binding=_na("no_measurement"),
    )


def _replacement_decision() -> ReplacementDecision:
    return ReplacementDecision(
        sampling_plan_ref=_sampling_ref(),
        policy_binding=ReplacementPolicyBinding(
            ReplacementPolicyBindingKind.PLAN_NEVER,
            None,
        ),
        decision=ReplacementDecisionKind.PROHIBITED,
        trigger_binding=_na("replacement_forbidden"),
        lineage_binding=_na("no_replacement_lineage"),
        accounting_evidence_ref=_owner("replacement_accounting", "no_replacement"),
    )


def _valid_disposition() -> CanonicalCaseDisposition:
    return CanonicalCaseDisposition(
        schema_version="1.0",
        canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
        intended_evidence_unit_ref=_owner("protected_intended_evidence_unit", "slot_1"),
        sampling_plan_ref=_sampling_ref(),
        primary_population_ref=_population_ref(
            PopulationRole.TARGET_WORKLOAD_P, "population_p"
        ),
        evidence_scope=_evidence_scope(),
        case_state=CaseState.VALID,
        case_ref_binding=ApplicabilityBinding.bound(_case_ref()),
        attempt_commitment_binding=_na("valid_has_no_attempt_only_ref"),
        state_payload=CaseStatePayload(
            CaseState.VALID,
            ValidCasePayload(
                applicability_evidence_ref=_owner(
                    "applicability_evidence", "valid_applicability"
                ),
                membership_evidence_ref=_owner(
                    "membership_evidence", "valid_membership"
                ),
            ),
        ),
        actor_policy_authority_ref=_owner("policy_authority", "case_policy"),
        replacement_decision=_replacement_decision(),
        audit_evidence_refs=(_owner("audit_evidence", "case_audit"),),
        downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
        disclosure_contract=_disclosure(),
    )


def _accounting_echo(
    candidate: EvidenceAccountingCapability,
) -> EvidenceAccountingVerificationEcho:
    return EvidenceAccountingVerificationEcho(
        sampling_plan_ref=candidate.sampling_plan_ref,
        complete_unit_manifest_ref=candidate.complete_unit_manifest_ref,
        intended_evidence_unit_refs=candidate.intended_evidence_unit_refs,
        primary_population_ref=candidate.primary_population_ref,
        selection_population_ref=candidate.selection_population_ref,
        target_population_binding=candidate.target_population_binding,
        official_proposal_binding=candidate.official_proposal_binding,
        evidence_weight_binding=candidate.evidence_weight_binding,
        intended_estimand_or_reporting_ref=(
            candidate.intended_estimand_or_reporting_ref
        ),
        accounting_evidence_ref=candidate.accounting_evidence_ref,
        denominator_policy_ref=candidate.denominator_policy_ref,
        censoring_policy_ref=candidate.censoring_policy_ref,
        missingness_adjustment_binding=candidate.missingness_adjustment_binding,
        sensitivity_analysis_binding=candidate.sensitivity_analysis_binding,
        construction_authority_ref=candidate.construction_authority_ref,
        construction_audit_refs=candidate.construction_audit_refs,
    )


def _echo_subclass_copy(subclass: type[object], value: object) -> object:
    return subclass(
        **{field.name: getattr(value, field.name) for field in dataclass_fields(value)}
    )


def _training_support(
    physical: PhysicalSystemSpec, candidate: CandidateOutputContract
) -> TrainingSupportContract:
    return TrainingSupportContract(
        object_kind="training_support_contract",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="training_support",
        object_version="1.0",
        supersedes=_na("first_training_support"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        membership_contract=TrainingMembershipContract(
            admission_rule_ref=_owner("membership_rule", "training_admission"),
            physical_support_ref=_owner("physical_support", "training_physical"),
            representation_support_ref=_owner(
                "representation_support", "training_representation"
            ),
            failure_outcome="REJECT",
        ),
        physical_invariant_refs=(_owner("semantic_clause", "training_physics"),),
        representation_invariant_refs=(
            _owner("semantic_clause", "training_representation_invariant"),
        ),
        permitted_source_materials=(),
        permitted_generators=PermittedGeneratorBinding(
            PermittedGeneratorKind.NONE,
            _owner("no_generator_reason", "no_training_generator"),
        ),
        rights_profile_ref=_owner("rights_profile", "fixture_training_rights"),
        permitted_use_refs=(_owner("permitted_use", "fixture_training_use"),),
        restrictions=(_owner("restriction", "fixture_only"),),
        provenance_requirements=(_owner("provenance", "fixture_training_provenance"),),
        disclosure_contract=_disclosure(),
        unknown_or_invalid_policy="REJECT",
    )


def test_top_level_canonical_round_trip_is_exact() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    values = (physical, candidate, _training_support(physical, candidate))

    for value in values:
        payload = value.canonical_bytes()
        decoded = decode_document(payload)
        reconstructed = authored_object_from_record(
            object_kind=decoded.object_kind, record=decoded.record
        )

        assert type(reconstructed) is type(value)
        assert reconstructed == value
        assert reconstructed.to_ref() == value.to_ref()
        assert payload == value.canonical_bytes()


def test_candidate_contract_binds_every_physical_input_and_output() -> None:
    physical = _physical()
    candidate = _candidate(physical)

    validate_candidate_against_physical(candidate, physical)

    mutated = object.__new__(CandidateOutputContract)
    for field in CandidateOutputContract.__dataclass_fields__:
        object.__setattr__(mutated, field, getattr(candidate, field))
    object.__setattr__(
        mutated, "geometry_domain_ref", _owner("geometry_domain", "other")
    )
    with pytest.raises(ValueError, match="geometry_domain_ref"):
        validate_candidate_against_physical(mutated, physical)


def test_exact_numeric_and_enum_types_reject_bool_coercion_and_nonfinite() -> None:
    with pytest.raises(AuthoringValidationError):
        AxisExtent(AxisExtentKind.FIXED, fixed_extent=True)

    from carbon.authoring.sampling import FractionAllocation

    with pytest.raises(AuthoringValidationError):
        FractionAllocation(
            fraction=math.inf,
            exact_sum_semantics_ref=_owner("allocation_sum_semantics", "sum_semantics"),
            zero_allocation_binding=_na("positive_fraction"),
        )


def test_p_and_q_are_nominally_separate_and_q_must_bind_p() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    p = _population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    q = _population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(p.to_ref()),
    )

    assert p.to_ref().expected_population_role == "TARGET_WORKLOAD_P"
    assert q.to_ref().expected_population_role == "OFFICIAL_PROPOSAL_Q"
    assert p.to_ref() != q.to_ref()

    with pytest.raises(ValueError, match="Q must bind exact P"):
        _population(PopulationRole.OFFICIAL_PROPOSAL_Q, physical, candidate)


def test_population_exclusions_bind_the_exact_owning_claim_scope() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    population = _population(
        PopulationRole.TARGET_WORKLOAD_P,
        physical,
        candidate,
    )
    exclusion = ExclusionContract(
        exclusion_id="fixture_exclusion",
        membership_rule_ref=_owner("membership_rule", "excluded_member"),
        scientific_authority_ref=_owner(
            "scientific_authority",
            "fixture_exclusion_authority",
        ),
        applicable_claim_ref=population.owning_claim_scope_ref,
        audit_semantics_ref=_owner("audit_semantics", "exclusion_audit"),
    )
    assert replace(population, exclusions=(exclusion,)).exclusions == (exclusion,)

    with pytest.raises(ValueError, match="applicable_claim_ref"):
        replace(
            population,
            exclusions=(
                replace(
                    exclusion,
                    applicable_claim_ref=_owner(
                        "claim_scope",
                        "another_scientific_claim",
                    ),
                ),
            ),
        )


def test_representation_adapters_cannot_drop_input_or_output_admissibility() -> None:
    admissibility = (_owner("semantic_clause", "physical_admissibility_constraint"),)
    input_physical = replace(
        _physical(),
        causal_inputs=(
            replace(_physical().causal_inputs[0], admissibility_refs=admissibility),
        ),
    )
    input_candidate = _candidate(input_physical)
    input_candidate = replace(
        input_candidate,
        candidate_inputs=(
            replace(input_candidate.candidate_inputs[0], admissibility_refs=()),
        ),
        causal_input_bindings=(
            replace(
                input_candidate.causal_input_bindings[0],
                relation=CandidateInputRelation(
                    CandidateInputRelationKind.REPRESENTATION_ADAPTER,
                    _owner("representation_adapter", "input_encoding_adapter"),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="causal input admissibility_refs"):
        validate_candidate_against_physical(input_candidate, input_physical)

    output_physical = replace(
        _physical(),
        required_physical_quantities=(
            replace(
                _physical().required_physical_quantities[0],
                admissibility_refs=admissibility,
            ),
        ),
    )
    output_candidate = _candidate(output_physical)
    output_candidate = replace(
        output_candidate,
        required_outputs=(
            replace(output_candidate.required_outputs[0], admissibility_refs=()),
        ),
        physical_output_bindings=(
            replace(
                output_candidate.physical_output_bindings[0],
                relation=CandidateOutputRelation(
                    CandidateOutputRelationKind.REPRESENTATION_ADAPTER,
                    _owner("representation_adapter", "output_encoding_adapter"),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="required output admissibility_refs"):
        validate_candidate_against_physical(output_candidate, output_physical)

    precision_candidate = _candidate(output_physical)
    precision_candidate = replace(
        precision_candidate,
        required_outputs=(
            replace(
                precision_candidate.required_outputs[0],
                precision_contract=(PrecisionLiteral.FLOAT32,),
            ),
        ),
        physical_output_bindings=(
            replace(
                precision_candidate.physical_output_bindings[0],
                relation=CandidateOutputRelation(
                    CandidateOutputRelationKind.REPRESENTATION_ADAPTER,
                    _owner("representation_adapter", "output_precision_adapter"),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="required output precision_contract"):
        validate_candidate_against_physical(precision_candidate, output_physical)


def test_physical_conditions_bind_exact_geometry_and_units() -> None:
    physical = _physical()
    with pytest.raises(ValueError, match="boundary clause unit"):
        replace(
            physical,
            boundary_conditions=BoundaryConditionContract(
                (
                    BoundaryRegionClause(
                        region_clause_id="boundary_region",
                        geometry_region_ref=_owner(
                            "geometry_region",
                            "fixture_boundary_region",
                        ),
                        condition_semantic_ref=_owner(
                            "semantic_clause",
                            "fixture_boundary_condition",
                        ),
                        causal_input_binding=ApplicabilityBinding.bound("forcing"),
                        unit_ref=_owner("unit", "wrong_boundary_unit"),
                        applicability=ApplicabilityBinding.bound(
                            _owner("applicability", "boundary_applies")
                        ),
                    ),
                )
            ),
        )

    with pytest.raises(ValueError, match="initial clause geometry"):
        replace(
            physical,
            initial_conditions=InitialConditionContract(
                (
                    InitialStateClause(
                        state_clause_id="initial_state",
                        state_semantic_ref=_owner(
                            "semantic_clause",
                            "fixture_initial_state",
                        ),
                        causal_input_binding=ApplicabilityBinding.bound("forcing"),
                        geometry_domain_ref=_owner(
                            "geometry_domain",
                            "wrong_initial_domain",
                        ),
                        time_origin_ref=_owner(
                            "semantic_clause",
                            "fixture_time_origin",
                        ),
                        applicability=ApplicabilityBinding.bound(
                            _owner("applicability", "initial_state_applies")
                        ),
                    ),
                )
            ),
        )


def test_official_sampling_plan_uses_exact_p_q_and_optional_explicit_w() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    p = _population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    q = _population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(p.to_ref()),
    )
    plan_estimand = _owner("intended_estimand_or_reporting", "fixture_estimand")
    w = _population(
        PopulationRole.EVIDENCE_WEIGHT_W,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(p.to_ref()),
        proposal_binding=ApplicabilityBinding.bound(q.to_ref()),
        estimand_ref=_owner("estimand_scope", "fixture_estimand"),
    )
    plan = _fixed_sampling_plan(p, q, w=w, estimand_ref=plan_estimand)

    graph = {
        physical.to_ref(): physical,
        candidate.to_ref(): candidate,
        p.to_ref(): p,
        q.to_ref(): q,
        w.to_ref(): w,
        plan.to_ref(): plan,
    }
    validate_loaded_authoring_graph(graph)

    nonaggregating = _fixed_sampling_plan(
        p,
        q,
        w=None,
        estimand_ref=_owner("intended_estimand_or_reporting", "nonaggregating_fixture"),
    )
    assert not nonaggregating.evidence_weight_binding.is_bound

    with pytest.raises(ValueError, match="selection_population_ref"):
        replace(plan, selection_population_ref=p.to_ref())


def test_case_public_projection_contains_no_raw_case_reference() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    population = _population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    case = CanonicalChallengeCase(
        object_kind="canonical_challenge_case",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="canonical_case",
        object_version="1.0",
        supersedes=_na("first_case_version"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        primary_population_ref=population.to_ref(),
        related_population_bindings=(),
        sampling_plan_binding=_na("case_without_plan"),
        case_source=CaseSourceBinding(
            CaseSourceKind.ANALYTIC,
            AnalyticCaseSource(_owner("analytic_construction", "analytic_fixture")),
        ),
        case_representation_ref=_owner("representation", "case_representation"),
        physical_payload_ref=_owner("protected_case_payload", "case_payload"),
        query_population_binding=_na("no_query_population"),
        observation_population_binding=_na("no_observation_population"),
        evidence_campaign_binding=_na("no_evidence_campaign"),
        intended_slot_binding=_na("no_intended_slot"),
        prospective_censoring_policy_binding=_na("no_censoring_policy"),
        applicability_bindings=(_owner("applicability", "case_applicability"),),
        disclosure_class=DisclosureClass.PROTECTED,
        disclosure_contract=_disclosure(),
        case_provenance_refs=(_owner("provenance", "case_provenance"),),
    )
    issuance_ref = _owner("projection_issuance", "public_projection")
    expected_case_ref = case.to_ref()

    class ExactProjectionRegistry:
        def __init__(self) -> None:
            self.revoked = False

        def verify_case_projection(
            self,
            *,
            authority_ref: object,
            case_ref: object,
            projection: object,
        ) -> CaseProjectionVerificationEcho:
            if self.revoked:
                raise ValueError("projection issuance is revoked")
            return CaseProjectionVerificationEcho(
                authority_ref=authority_ref,
                case_ref=case_ref,
                projection=projection,
            )

    registry = ExactProjectionRegistry()

    authority = _issue_case_projection_authority(
        authority_ref=issuance_ref,
        authority=registry,
    )
    projection = issue_public_case_projection(
        authority,
        case,
        opaque_public_handle=_owner("opaque_public_case_handle", "opaque_case"),
        disclosure_policy_ref=case.disclosure_contract.release_policy_ref,
        issuance_ref=issuance_ref,
        public_fact_bindings=(
            PublicCaseFactBinding(
                PublicCaseFactKind.PRIMARY_POPULATION_ROLE,
                _owner("public_case_fact", "target_role"),
            ),
        ),
    )

    assert not hasattr(projection, "case_ref")
    assert case.to_ref().content_digest not in repr(projection)
    with pytest.raises(TypeError):
        require_public_case_projection(case.to_ref())

    for raw in (None, False, {}, lambda candidate: candidate):
        with pytest.raises(TypeError):
            _issue_case_projection_authority(
                authority_ref=issuance_ref,
                authority=raw,
            )

    class FixedProjectionRegistry:
        def __init__(self, result: object) -> None:
            self.result = result

        def verify_case_projection(self, **kwargs: object) -> object:
            del kwargs
            return self.result

    exact_projection_echo = CaseProjectionVerificationEcho(
        authority_ref=issuance_ref,
        case_ref=expected_case_ref,
        projection=projection,
    )
    for wrong_result in (None, False, {}, (projection,)):
        wrong = _issue_case_projection_authority(
            authority_ref=issuance_ref,
            authority=FixedProjectionRegistry(wrong_result),
        )
        with pytest.raises(TypeError):
            wrong.require_pairing(projection, expected_case_ref)

    stale_case = _issue_case_projection_authority(
        authority_ref=issuance_ref,
        authority=FixedProjectionRegistry(
            replace(
                exact_projection_echo,
                case_ref=replace(expected_case_ref, object_version="1.1"),
            )
        ),
    )
    with pytest.raises(ValueError, match="case mismatch"):
        stale_case.require_pairing(projection, expected_case_ref)

    class ProjectionEchoSubclass(CaseProjectionVerificationEcho):
        pass

    subclass_registry = _issue_case_projection_authority(
        authority_ref=issuance_ref,
        authority=FixedProjectionRegistry(
            _echo_subclass_copy(ProjectionEchoSubclass, exact_projection_echo)
        ),
    )
    with pytest.raises(TypeError):
        subclass_registry.require_pairing(projection, expected_case_ref)
    with pytest.raises(ValueError, match="wrong exact nominal kind"):
        CaseProjectionVerificationEcho(
            authority_ref=_owner("accounting_authority", "wrong_authority_kind"),
            case_ref=expected_case_ref,
            projection=projection,
        )

    registry.revoked = True
    with pytest.raises(ValueError, match="revoked"):
        authority.require_pairing(projection, expected_case_ref)
    with pytest.raises(PermissionError):
        type(authority)(
            _capability=object(),
            authority_ref=issuance_ref,
            authority=registry,
        )


def test_evidence_weight_cannot_be_a_plan_free_case_population() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    target = _population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    proposal = _population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
    )
    weight = _population(
        PopulationRole.EVIDENCE_WEIGHT_W,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
        proposal_binding=ApplicabilityBinding.bound(proposal.to_ref()),
    )

    def plan_free_case(
        *,
        object_id: str,
        primary_ref: InstanceDistributionContractRef,
        related: tuple[RelatedPopulationBinding, ...] = (),
    ) -> CanonicalChallengeCase:
        return CanonicalChallengeCase(
            object_kind="canonical_challenge_case",
            schema_version="1.0",
            canonicalization_profile=CANONICALIZATION_PROFILE,
            challenge_key=_KEY,
            object_id=object_id,
            object_version="1.0",
            supersedes=_na(f"first_{object_id}"),
            physical_system_ref=physical.to_ref(),
            candidate_output_ref=candidate.to_ref(),
            primary_population_ref=primary_ref,
            related_population_bindings=related,
            sampling_plan_binding=_na("plan_free_case"),
            case_source=CaseSourceBinding(
                CaseSourceKind.ANALYTIC,
                AnalyticCaseSource(
                    _owner("analytic_construction", f"{object_id}_construction")
                ),
            ),
            case_representation_ref=_owner("representation", "case_representation"),
            physical_payload_ref=_owner(
                "protected_case_payload",
                f"{object_id}_payload",
            ),
            query_population_binding=_na("no_query_population"),
            observation_population_binding=_na("no_observation_population"),
            evidence_campaign_binding=_na("no_evidence_campaign"),
            intended_slot_binding=_na("no_intended_slot"),
            prospective_censoring_policy_binding=_na("no_censoring_policy"),
            applicability_bindings=(_owner("applicability", "case_applicability"),),
            disclosure_class=DisclosureClass.PROTECTED,
            disclosure_contract=_disclosure(),
            case_provenance_refs=(_owner("provenance", "case_provenance"),),
        )

    primary_weight_case = plan_free_case(
        object_id="weight_primary_case",
        primary_ref=weight.to_ref(),
    )
    primary_graph = {
        value.to_ref(): value
        for value in (
            physical,
            candidate,
            target,
            proposal,
            weight,
            primary_weight_case,
        )
    }
    with pytest.raises(ValueError, match="case primary population"):
        validate_loaded_authoring_graph(primary_graph)

    related_weight = replace(
        weight,
        allowed_consumers=(
            *weight.allowed_consumers,
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE,
                CasePopulationUse.RELATED,
            ),
        ),
    )
    related_weight_case = plan_free_case(
        object_id="weight_related_case",
        primary_ref=target.to_ref(),
        related=(
            RelatedPopulationBinding(
                related_weight.to_ref(),
                _owner("population_relationship", "weight_is_not_related"),
            ),
        ),
    )
    related_graph = {
        value.to_ref(): value
        for value in (
            physical,
            candidate,
            target,
            proposal,
            related_weight,
            related_weight_case,
        )
    }
    with pytest.raises(ValueError, match="case related population"):
        validate_loaded_authoring_graph(related_graph)


def test_mms_role_is_nominally_distinct() -> None:
    mms = EvidenceRoleBinding(EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION)
    numerical = EvidenceRoleBinding(EvidenceRole.NUMERICAL)
    assert mms != numerical


def test_case_evidence_consumption_requires_exact_external_authority_echo() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    campaign_ref = _owner("evidence_campaign", "mms_verification_campaign")
    role_population = replace(
        _population(
            PopulationRole.EVIDENCE_CAMPAIGN,
            physical,
            candidate,
        ),
        allowed_consumers=(
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE,
                CasePopulationUse.PRIMARY,
            ),
            AllowedConsumer(
                AllowedConsumerKind.CASE_EVIDENCE,
                EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION,
            ),
            AllowedConsumer(
                AllowedConsumerKind.CASE_EVIDENCE,
                EvidenceRole.NUMERICAL,
            ),
        ),
    )
    case = CanonicalChallengeCase(
        object_kind="canonical_challenge_case",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="mms_case",
        object_version="1.0",
        supersedes=_na("first_mms_case_version"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        primary_population_ref=role_population.to_ref(),
        related_population_bindings=(),
        sampling_plan_binding=_na("mms_case_without_plan"),
        case_source=CaseSourceBinding(
            CaseSourceKind.MANUFACTURED_SOLUTION,
            ManufacturedSolutionCaseSource(
                verification_campaign_ref=campaign_ref,
                verification_construction_ref=_owner(
                    "verification_construction", "mms_construction"
                ),
            ),
        ),
        case_representation_ref=_owner("representation", "mms_case_representation"),
        physical_payload_ref=_owner("protected_case_payload", "mms_payload"),
        query_population_binding=_na("no_query_population"),
        observation_population_binding=_na("no_observation_population"),
        evidence_campaign_binding=ApplicabilityBinding.bound(campaign_ref),
        intended_slot_binding=_na("no_intended_slot"),
        prospective_censoring_policy_binding=_na("no_censoring_policy"),
        applicability_bindings=(_owner("applicability", "mms_applicability"),),
        disclosure_class=DisclosureClass.PROTECTED,
        disclosure_contract=_disclosure(),
        case_provenance_refs=(_owner("provenance", "mms_case_provenance"),),
    )
    binding = CaseEvidenceBinding(
        authoritative_case_ref=case.to_ref(),
        public_projection_binding=_na("protected_binding_has_no_public_projection"),
        evidence_role=EvidenceRoleBinding(
            EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        ),
        evidence_campaign_ref=campaign_ref,
        role_population_ref=role_population.to_ref(),
        evidence_artifact_ref=_owner("evidence_artifact", "mms_residuals"),
        claim_scope_ref=physical.claim_scope_ref,
        applicability_refs=(_owner("applicability", "verification_only"),),
        query_observation_provenance=(),
        policy_qualification_binding=_na("not_reference_qualified"),
        provenance_refs=(_owner("provenance", "mms_evidence_provenance"),),
        disclosure_contract=_disclosure(),
        downstream_use_restrictions=(_owner("restriction", "verification_only"),),
    )
    authority_ref = _owner("evidence_binding_authority", "b04_history_registry")

    def exact_echo(
        candidate: CaseEvidenceBinding,
    ) -> CaseEvidenceBindingAuthorization:
        return CaseEvidenceBindingAuthorization(
            authority_ref=authority_ref,
            authoritative_case_ref=candidate.authoritative_case_ref,
            public_projection_binding=candidate.public_projection_binding,
            evidence_role=candidate.evidence_role,
            evidence_campaign_ref=candidate.evidence_campaign_ref,
            role_population_ref=candidate.role_population_ref,
            evidence_artifact_ref=candidate.evidence_artifact_ref,
            claim_scope_ref=candidate.claim_scope_ref,
            applicability_refs=candidate.applicability_refs,
            query_observation_provenance=(candidate.query_observation_provenance),
            policy_qualification_binding=(candidate.policy_qualification_binding),
            provenance_refs=candidate.provenance_refs,
            disclosure_contract=candidate.disclosure_contract,
            downstream_use_restrictions=(candidate.downstream_use_restrictions),
        )

    class ExactEvidenceBindingRegistry:
        def __init__(
            self,
            field: str | None = None,
            replacement_value: object | None = None,
            result: object | None = None,
        ) -> None:
            self.field = field
            self.replacement_value = replacement_value
            self.result = result

        def authorize_case_evidence_binding(
            self,
            *,
            authority_ref: object,
            binding: CaseEvidenceBinding,
        ) -> object:
            del authority_ref
            if self.result is not None:
                return self.result
            echo = exact_echo(binding)
            if self.field is None:
                return echo
            return replace(echo, **{self.field: self.replacement_value})

    authority = _issue_case_evidence_binding_authority(
        authority_ref=authority_ref,
        authority=ExactEvidenceBindingRegistry(),
    )
    authorization = authority.authorize(
        binding,
        case=case,
        role_population=role_population,
        physical_system=physical,
        candidate_output=candidate,
    )
    assert type(authorization) is CaseEvidenceBindingAuthorization
    assert authorization.evidence_artifact_ref == binding.evidence_artifact_ref
    assert not hasattr(binding, "authorization")

    for raw in (None, False, {}, lambda candidate: candidate):
        with pytest.raises(TypeError):
            _issue_case_evidence_binding_authority(
                authority_ref=authority_ref,
                authority=raw,
            )

    class WrongEvidenceBindingRegistry:
        def __init__(self, result: object) -> None:
            self.result = result

        def authorize_case_evidence_binding(self, **kwargs: object) -> object:
            del kwargs
            return self.result

    for wrong_result in (None, False, {}, (binding,)):
        wrong = _issue_case_evidence_binding_authority(
            authority_ref=authority_ref,
            authority=WrongEvidenceBindingRegistry(wrong_result),
        )
        with pytest.raises(TypeError):
            wrong.authorize(
                binding,
                case=case,
                role_population=role_population,
                physical_system=physical,
                candidate_output=candidate,
            )

    stale_values = (
        (
            "authority_ref",
            _owner("accounting_authority", "wrong_nominal_authority"),
        ),
        (
            "authoritative_case_ref",
            replace(case.to_ref(), object_version="1.1"),
        ),
        ("evidence_role", EvidenceRoleBinding(EvidenceRole.NUMERICAL)),
        (
            "evidence_campaign_ref",
            _owner("evidence_campaign", "substituted_campaign"),
        ),
        (
            "role_population_ref",
            _population_ref(PopulationRole.TARGET_WORKLOAD_P, "substituted_target"),
        ),
        (
            "role_population_ref",
            _population_ref(
                PopulationRole.PRODUCT_QUALIFICATION,
                "substituted_product_qualification",
            ),
        ),
        (
            "evidence_artifact_ref",
            _owner("evidence_artifact", "substituted_artifact"),
        ),
        ("claim_scope_ref", _owner("claim_scope", "substituted_claim")),
        (
            "applicability_refs",
            (_owner("applicability", "substituted_applicability"),),
        ),
        (
            "query_observation_provenance",
            (
                _owner(
                    "query_observation_provenance",
                    "substituted_observation",
                ),
            ),
        ),
        (
            "policy_qualification_binding",
            ApplicabilityBinding.bound(
                _owner(
                    "reference_qualification_policy",
                    "substituted_live_exam_claim",
                )
            ),
        ),
        (
            "provenance_refs",
            (_owner("provenance", "substituted_provenance"),),
        ),
    )
    for field, stale_value in stale_values:
        stale = _issue_case_evidence_binding_authority(
            authority_ref=authority_ref,
            authority=ExactEvidenceBindingRegistry(field, stale_value),
        )
        with pytest.raises(ValueError, match=field):
            stale.authorize(
                binding,
                case=case,
                role_population=role_population,
                physical_system=physical,
                candidate_output=candidate,
            )

    class EvidenceBindingEchoSubclass(CaseEvidenceBindingAuthorization):
        pass

    subclass_authority = _issue_case_evidence_binding_authority(
        authority_ref=authority_ref,
        authority=ExactEvidenceBindingRegistry(
            result=_echo_subclass_copy(
                EvidenceBindingEchoSubclass,
                exact_echo(binding),
            )
        ),
    )
    with pytest.raises(TypeError):
        subclass_authority.authorize(
            binding,
            case=case,
            role_population=role_population,
            physical_system=physical,
            candidate_output=candidate,
        )

    with pytest.raises(ValueError, match="relabeled"):
        reject_evidence_role_relabel(
            binding,
            EvidenceRoleBinding(EvidenceRole.NUMERICAL),
        )

    # A separately authored artifact with a distinct role can be registered;
    # exact-binding authorization prevents relabeling without banning it.
    numerical_binding = replace(
        binding,
        evidence_role=EvidenceRoleBinding(EvidenceRole.NUMERICAL),
        evidence_artifact_ref=_owner(
            "evidence_artifact", "separate_numerical_evidence"
        ),
    )
    numerical_authorization = authority.authorize(
        numerical_binding,
        case=case,
        role_population=role_population,
        physical_system=physical,
        candidate_output=candidate,
    )
    assert numerical_authorization.evidence_role.role is EvidenceRole.NUMERICAL


def test_derived_disposition_round_trip_is_digest_pinned() -> None:
    disposition = _valid_disposition()
    payload = disposition.canonical_bytes()

    loaded = load_derived_evidence(disposition.to_ref(), payload)

    assert type(loaded) is CanonicalCaseDisposition
    assert loaded == disposition
    assert loaded.to_ref() == disposition.to_ref()
    with pytest.raises(ValueError, match="digest"):
        load_derived_evidence(
            replace(disposition.to_ref(), content_digest=_DIGEST),
            payload,
        )


def test_censoring_record_round_trip_preserves_exact_reason_subtype() -> None:
    record = CensoringRecord(
        schema_version="1.0",
        canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
        intended_evidence_unit_ref=_owner("protected_intended_evidence_unit", "slot_1"),
        evidence_scope=_evidence_scope(),
        censoring_reason=CensoringReason.REFERENCE_TIMEOUT,
        trigger_failure_binding=CensoringTrigger(
            CensoringTriggerKind.REFERENCE,
            _owner("reference_timeout", "reference_timeout_event"),
        ),
        actor_authority_ref=_owner("censoring_authority", "reference_policy"),
        population_ref=_population_ref(
            PopulationRole.TARGET_WORKLOAD_P, "population_p"
        ),
        sampling_plan_ref=_sampling_ref(),
        evidence_campaign_binding=_na("no_campaign"),
        query_observation_provenance=(),
        replacement_decision=_replacement_decision(),
        accounting_binding=_owner("censoring_accounting", "intended_unit_retained"),
        missingness_adjustment_binding=_na("no_missingness_adjustment"),
        audit_evidence_refs=(_owner("audit_evidence", "censoring_audit"),),
        downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
    )

    loaded = load_derived_evidence(record.to_ref(), record.canonical_bytes())
    assert type(loaded) is CensoringRecord
    assert loaded == record

    with pytest.raises(ValueError, match="subtype"):
        replace(
            record,
            trigger_failure_binding=CensoringTrigger(
                CensoringTriggerKind.REFERENCE,
                _owner("reference_unavailable", "reference_timeout_event"),
            ),
        )


def test_censoring_plan_validation_closes_population_and_applicability_seams() -> None:
    physical = _physical()
    candidate = _candidate(physical)
    primary = _population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    proposal = _population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(primary.to_ref()),
    )
    estimand_ref = _owner("intended_estimand_or_reporting", "plan_estimand")
    base_plan = _fixed_sampling_plan(
        primary,
        proposal,
        w=None,
        estimand_ref=estimand_ref,
    )

    def record_for(
        plan: SamplingPlan,
        *,
        reason: CensoringReason,
        trigger_kind: CensoringTriggerKind,
        trigger_ref_kind: str,
        population_ref: object,
        provenance: tuple[object, ...] = (),
        measurement: ApplicabilityBinding[object] | None = None,
    ) -> CensoringRecord:
        scope = EvidenceScopeBinding(
            evidence_campaign_binding=plan.evidence_campaign_binding,
            query_population_binding=plan.query_population_binding,
            observation_population_binding=plan.observation_population_binding,
            intended_estimand_or_reporting_ref=(
                plan.intended_estimand_or_reporting_ref
            ),
            measurement_applicability_binding=(
                measurement or _na("no_measurement_applicability")
            ),
        )
        replacement = ReplacementDecision(
            sampling_plan_ref=plan.to_ref(),
            policy_binding=ReplacementPolicyBinding(
                ReplacementPolicyBindingKind.PLAN_NEVER,
                None,
            ),
            decision=ReplacementDecisionKind.PROHIBITED,
            trigger_binding=_na("replacement_forbidden"),
            lineage_binding=_na("no_replacement_lineage"),
            accounting_evidence_ref=_owner("replacement_accounting", "no_replacement"),
        )
        return CensoringRecord(
            schema_version="1.0",
            canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
            intended_evidence_unit_ref=_owner(
                "protected_intended_evidence_unit", "slot_1"
            ),
            evidence_scope=scope,
            censoring_reason=reason,
            trigger_failure_binding=CensoringTrigger(
                trigger_kind,
                _owner(trigger_ref_kind, "registered_trigger"),
            ),
            actor_authority_ref=_owner(
                "censoring_authority", "registered_censoring_policy"
            ),
            population_ref=population_ref,
            sampling_plan_ref=plan.to_ref(),
            evidence_campaign_binding=plan.evidence_campaign_binding,
            query_observation_provenance=provenance,
            replacement_decision=replacement,
            accounting_binding=_owner("censoring_accounting", "intended_unit_retained"),
            missingness_adjustment_binding=_na("no_missingness_adjustment"),
            audit_evidence_refs=(_owner("audit_evidence", "censoring_audit"),),
            downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
        )

    reference = record_for(
        base_plan,
        reason=CensoringReason.REFERENCE_TIMEOUT,
        trigger_kind=CensoringTriggerKind.REFERENCE,
        trigger_ref_kind="reference_timeout",
        population_ref=primary.to_ref(),
    )
    validate_censoring_against_plan(reference, base_plan)
    with pytest.raises(ValueError, match="requires a bound query or observation"):
        validate_censoring_against_plan(
            replace(
                reference,
                query_observation_provenance=(
                    _owner(
                        "query_observation_provenance",
                        "unbound_query_attempt",
                    ),
                ),
            ),
            base_plan,
        )
    with pytest.raises(ValueError, match="outside"):
        validate_censoring_against_plan(
            replace(
                reference,
                population_ref=_population_ref(
                    PopulationRole.STRESS,
                    "unbound_stress_population",
                ),
            ),
            base_plan,
        )

    observation_ref = _population_ref(
        PopulationRole.OBSERVATION,
        "observation_population",
    )
    observation_plan = replace(
        base_plan,
        object_id="observation_sampling_plan",
        observation_population_binding=ApplicabilityBinding.bound(observation_ref),
    )
    observation_provenance = (
        _owner("query_observation_provenance", "observation_attempt"),
    )
    query_ref = _population_ref(PopulationRole.QUERY, "query_population")
    query_plan = replace(
        base_plan,
        object_id="query_sampling_plan",
        query_population_binding=ApplicabilityBinding.bound(query_ref),
    )
    query_scoped_reference = record_for(
        query_plan,
        reason=CensoringReason.REFERENCE_TIMEOUT,
        trigger_kind=CensoringTriggerKind.REFERENCE,
        trigger_ref_kind="reference_timeout",
        population_ref=primary.to_ref(),
    )
    with pytest.raises(ValueError, match="requires acquisition provenance"):
        validate_censoring_against_plan(query_scoped_reference, query_plan)
    validate_censoring_against_plan(
        replace(
            query_scoped_reference,
            query_observation_provenance=(
                _owner("query_observation_provenance", "query_attempt"),
            ),
        ),
        query_plan,
    )
    observation = record_for(
        observation_plan,
        reason=CensoringReason.OBSERVATION_MISSING,
        trigger_kind=CensoringTriggerKind.OBSERVATION,
        trigger_ref_kind="observation_missing",
        population_ref=observation_ref,
        provenance=observation_provenance,
    )
    validate_censoring_against_plan(observation, observation_plan)
    with pytest.raises(ValueError, match="provenance"):
        validate_censoring_against_plan(
            replace(observation, query_observation_provenance=()),
            observation_plan,
        )
    with pytest.raises(ValueError, match="observation population"):
        validate_censoring_against_plan(
            replace(observation, population_ref=primary.to_ref()),
            observation_plan,
        )
    no_observation_plan_record = record_for(
        base_plan,
        reason=CensoringReason.OBSERVATION_TIMEOUT,
        trigger_kind=CensoringTriggerKind.OBSERVATION,
        trigger_ref_kind="observation_timeout",
        population_ref=primary.to_ref(),
    )
    with pytest.raises(ValueError, match="bound observation"):
        validate_censoring_against_plan(
            no_observation_plan_record,
            base_plan,
        )

    measurement = record_for(
        base_plan,
        reason=CensoringReason.MEASUREMENT_UNAVAILABLE,
        trigger_kind=CensoringTriggerKind.MEASUREMENT,
        trigger_ref_kind="measurement_unavailable",
        population_ref=primary.to_ref(),
        measurement=ApplicabilityBinding.bound(
            _owner("measurement_applicability", "registered_measurement")
        ),
    )
    validate_censoring_against_plan(measurement, base_plan)
    with pytest.raises(ValueError, match="measurement applicability"):
        validate_censoring_against_plan(
            replace(
                measurement,
                evidence_scope=replace(
                    measurement.evidence_scope,
                    measurement_applicability_binding=_na("measurement_not_applicable"),
                ),
            ),
            base_plan,
        )

    campaign_ref = _owner("evidence_campaign", "experiment_campaign")
    campaign_plan = replace(
        base_plan,
        object_id="experiment_sampling_plan",
        evidence_campaign_binding=ApplicabilityBinding.bound(campaign_ref),
    )
    experiment = record_for(
        campaign_plan,
        reason=CensoringReason.EXPERIMENT_CORRUPTED,
        trigger_kind=CensoringTriggerKind.EXPERIMENT,
        trigger_ref_kind="experiment_corrupted",
        population_ref=primary.to_ref(),
    )
    validate_censoring_against_plan(experiment, campaign_plan)
    no_campaign_experiment = record_for(
        base_plan,
        reason=CensoringReason.EXPERIMENT_CORRUPTED,
        trigger_kind=CensoringTriggerKind.EXPERIMENT,
        trigger_ref_kind="experiment_corrupted",
        population_ref=primary.to_ref(),
    )
    with pytest.raises(ValueError, match="evidence campaign"):
        validate_censoring_against_plan(no_campaign_experiment, base_plan)


def test_disposition_replacement_state_and_lineage_matrix_is_closed() -> None:
    valid = _valid_disposition()
    registered_binding = ReplacementPolicyBinding(
        ReplacementPolicyBindingKind.REGISTERED_POLICY,
        _owner("replacement_policy", "registered_replacement"),
    )
    censored_trigger = ReplacementTrigger(
        ReplacementTriggerKind.CENSORED,
        CensoringReason.REFERENCE_TIMEOUT,
    )
    with pytest.raises(ValueError, match="valid disposition trigger"):
        replace(
            valid,
            replacement_decision=ReplacementDecision(
                sampling_plan_ref=valid.sampling_plan_ref,
                policy_binding=registered_binding,
                decision=ReplacementDecisionKind.PERMITTED,
                trigger_binding=ApplicabilityBinding.bound(censored_trigger),
                lineage_binding=_na("replacement_not_executed"),
                accounting_evidence_ref=_owner(
                    "replacement_accounting", "registered_accounting"
                ),
            ),
        )

    with pytest.raises(ValueError, match="prohibited disposition lineage"):
        replace(
            valid,
            replacement_decision=ReplacementDecision(
                sampling_plan_ref=valid.sampling_plan_ref,
                policy_binding=registered_binding,
                decision=ReplacementDecisionKind.PROHIBITED,
                trigger_binding=_na("replacement_prohibited"),
                lineage_binding=ApplicabilityBinding.bound(
                    _owner("protected_replacement_lineage", "forged_lineage")
                ),
                accounting_evidence_ref=_owner(
                    "replacement_accounting", "prohibited_accounting"
                ),
            ),
        )

    generation_payload = GenerationFailurePayload(
        source_ref=_owner("case_source", "fixture_source"),
        failure_evidence_ref=_owner("generation_failure", "generation_reason"),
        distribution_conformance_ref=_owner(
            "distribution_conformance", "generation_conformance"
        ),
        accounting_ref=_owner("generation_failure_accounting", "generation_accounting"),
    )
    generation_decision = ReplacementDecision(
        sampling_plan_ref=valid.sampling_plan_ref,
        policy_binding=registered_binding,
        decision=ReplacementDecisionKind.PERMITTED,
        trigger_binding=ApplicabilityBinding.bound(
            ReplacementTrigger(
                ReplacementTriggerKind.GENERATION_FAILURE,
                _owner(
                    "replacement_eligible_generation_failure_reason",
                    "generation_reason",
                ),
            )
        ),
        lineage_binding=_na("generation_replacement_not_executed"),
        accounting_evidence_ref=_owner(
            "replacement_accounting", "generation_replacement"
        ),
    )
    generated_failure = replace(
        valid,
        case_state=CaseState.GENERATION_FAILURE,
        case_ref_binding=_na("generation_has_no_case"),
        attempt_commitment_binding=ApplicabilityBinding.bound(
            _owner("protected_attempt_commitment", "generation_attempt")
        ),
        state_payload=CaseStatePayload(
            CaseState.GENERATION_FAILURE,
            generation_payload,
        ),
        replacement_decision=generation_decision,
    )
    assert generated_failure.case_state is CaseState.GENERATION_FAILURE
    with pytest.raises(ValueError, match="generation replacement trigger"):
        replace(
            generated_failure,
            replacement_decision=replace(
                generation_decision,
                trigger_binding=ApplicabilityBinding.bound(
                    ReplacementTrigger(
                        ReplacementTriggerKind.GENERATION_FAILURE,
                        _owner(
                            "replacement_eligible_generation_failure_reason",
                            "different_generation_reason",
                        ),
                    )
                ),
            ),
        )

    excluded_payload = ExcludedCasePayload(
        exclusion_contract_ref=_owner("exclusion_contract", "excluded_contract"),
        assessment_ref=_owner("exclusion_assessment", "excluded_assessment"),
        prospective_screening_design_ref=_owner(
            "screening_design", "prospective_screen"
        ),
        inclusion_probability_accounting_ref=_owner(
            "inclusion_probability_accounting", "excluded_accounting"
        ),
    )
    excluded = replace(
        valid,
        case_state=CaseState.EXCLUDED,
        state_payload=CaseStatePayload(CaseState.EXCLUDED, excluded_payload),
        replacement_decision=ReplacementDecision(
            sampling_plan_ref=valid.sampling_plan_ref,
            policy_binding=registered_binding,
            decision=ReplacementDecisionKind.PERMITTED,
            trigger_binding=ApplicabilityBinding.bound(
                ReplacementTrigger(
                    ReplacementTriggerKind.EXCLUDED,
                    _owner("prospective_exclusion_contract", "excluded_contract"),
                )
            ),
            lineage_binding=_na("excluded_replacement_not_executed"),
            accounting_evidence_ref=_owner(
                "replacement_accounting", "excluded_replacement"
            ),
        ),
    )
    assert excluded.case_state is CaseState.EXCLUDED


def test_realized_evidence_requires_external_accounting_authority_to_load() -> None:
    disposition = _valid_disposition()
    primary = disposition.primary_population_ref
    selection = _population_ref(PopulationRole.OFFICIAL_PROPOSAL_Q, "population_q")
    target_binding = ApplicabilityBinding.bound(primary)
    proposal_binding = ApplicabilityBinding.bound(selection)
    weight_binding = _na("nonaggregating_evidence_use")
    estimand_ref = disposition.evidence_scope.intended_estimand_or_reporting_ref
    accounting_ref = _owner("realized_evidence_accounting", "realized_accounting")
    denominator_ref = _owner("denominator_policy", "intended_denominator")
    censoring_ref = _owner("censoring_policy", "fixture_censoring")
    missingness = _na("no_missingness_adjustment")
    sensitivity = _na("no_sensitivity_analysis")
    manifest_ref = _owner("protected_unit_manifest", "complete_manifest")
    authority_ref = _owner("accounting_authority", "fixture_accounting")
    audit_refs = (_owner("audit_evidence", "accounting_audit"),)

    class ExactAccountingRegistry:
        def verify_evidence_accounting(
            self, *, candidate: object
        ) -> EvidenceAccountingVerificationEcho:
            return EvidenceAccountingVerificationEcho(
                sampling_plan_ref=candidate.sampling_plan_ref,
                complete_unit_manifest_ref=candidate.complete_unit_manifest_ref,
                intended_evidence_unit_refs=candidate.intended_evidence_unit_refs,
                primary_population_ref=candidate.primary_population_ref,
                selection_population_ref=candidate.selection_population_ref,
                target_population_binding=candidate.target_population_binding,
                official_proposal_binding=candidate.official_proposal_binding,
                evidence_weight_binding=candidate.evidence_weight_binding,
                intended_estimand_or_reporting_ref=(
                    candidate.intended_estimand_or_reporting_ref
                ),
                accounting_evidence_ref=candidate.accounting_evidence_ref,
                denominator_policy_ref=candidate.denominator_policy_ref,
                censoring_policy_ref=candidate.censoring_policy_ref,
                missingness_adjustment_binding=(
                    candidate.missingness_adjustment_binding
                ),
                sensitivity_analysis_binding=(candidate.sensitivity_analysis_binding),
                construction_authority_ref=candidate.construction_authority_ref,
                construction_audit_refs=candidate.construction_audit_refs,
            )

    capability = _issue_evidence_accounting_capability(
        sampling_plan_ref=disposition.sampling_plan_ref,
        complete_unit_manifest_ref=manifest_ref,
        intended_evidence_unit_refs=(disposition.intended_evidence_unit_ref,),
        primary_population_ref=primary,
        selection_population_ref=selection,
        target_population_binding=target_binding,
        official_proposal_binding=proposal_binding,
        evidence_weight_binding=weight_binding,
        intended_estimand_or_reporting_ref=estimand_ref,
        accounting_evidence_ref=accounting_ref,
        denominator_policy_ref=denominator_ref,
        censoring_policy_ref=censoring_ref,
        missingness_adjustment_binding=missingness,
        sensitivity_analysis_binding=sensitivity,
        construction_authority_ref=authority_ref,
        construction_audit_refs=audit_refs,
        authority=ExactAccountingRegistry(),
    )

    class ExactAccountingFinalizer:
        def finalize_evidence_accounting(
            self,
            *,
            authority_ref: object,
            capability: EvidenceAccountingCapability,
            disposition_refs: tuple[object, ...],
            dispositions: tuple[CanonicalCaseDisposition, ...],
            censoring_record_refs: tuple[object, ...],
            censoring_records: tuple[CensoringRecord, ...],
        ) -> EvidenceAccountingFinalizationEcho:
            return EvidenceAccountingFinalizationEcho(
                authority_ref=authority_ref,
                accounting_verification=_accounting_echo(capability),
                capability=capability,
                disposition_refs=disposition_refs,
                dispositions=dispositions,
                censoring_record_refs=censoring_record_refs,
                censoring_records=censoring_records,
            )

    finalization = _finalize_evidence_accounting(
        capability,
        (disposition,),
        (),
        authority=ExactAccountingFinalizer(),
    )
    realized = construct_realized_valid_evidence(
        finalization,
        (disposition,),
        schema_version="1.0",
        canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        sampling_plan_ref=disposition.sampling_plan_ref,
        primary_population_ref=primary,
        selection_population_ref=selection,
        target_population_binding=target_binding,
        official_proposal_binding=proposal_binding,
        evidence_weight_binding=weight_binding,
        intended_estimand_or_reporting_ref=estimand_ref,
        evidence_scope=disposition.evidence_scope,
        accounting_evidence_ref=accounting_ref,
        denominator_policy_ref=denominator_ref,
        censoring_policy_ref=censoring_ref,
        missingness_adjustment_binding=missingness,
        sensitivity_analysis_binding=sensitivity,
        distribution_conformance_evidence_ref=_owner(
            "distribution_conformance", "fixture_conformance"
        ),
        disclosure_contract=_disclosure(),
        downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
    )
    payload = realized.canonical_bytes()
    expected_ref = realized.to_ref()

    with pytest.raises(PermissionError, match="authority"):
        load_derived_evidence(expected_ref, payload)

    class ExactRealizedHistory:
        def verify_realized_evidence_load(
            self,
            *,
            authority_ref: object,
            expected_ref: object,
            content_digest: str,
            decoded_record: object,
        ) -> RealizedEvidenceLoadVerificationEcho:
            del decoded_record
            return RealizedEvidenceLoadVerificationEcho(
                authority_ref=authority_ref,
                expected_ref=expected_ref,
                content_digest=content_digest,
                finalization=EvidenceAccountingFinalizationEcho(
                    authority_ref=authority_ref,
                    accounting_verification=_accounting_echo(capability),
                    capability=capability,
                    disposition_refs=(disposition.to_ref(),),
                    dispositions=(disposition,),
                    censoring_record_refs=(),
                    censoring_records=(),
                ),
            )

    load_authority = _issue_realized_evidence_load_authority(
        authority_ref=authority_ref,
        authority=ExactRealizedHistory(),
    )
    loaded = load_derived_evidence(
        expected_ref,
        payload,
        realized_authority=load_authority,
    )
    assert loaded == realized

    for raw in (None, False, {}, lambda candidate: candidate):
        with pytest.raises(TypeError):
            _issue_realized_evidence_load_authority(
                authority_ref=authority_ref,
                authority=raw,
            )

    class FixedRealizedHistory:
        def __init__(self, result: object) -> None:
            self.result = result

        def verify_realized_evidence_load(self, **kwargs: object) -> object:
            del kwargs
            return self.result

    exact_load_echo = ExactRealizedHistory().verify_realized_evidence_load(
        authority_ref=authority_ref,
        expected_ref=expected_ref,
        content_digest=expected_ref.content_digest,
        decoded_record=object(),
    )
    for wrong_result in (None, False, {}, (capability,)):
        wrong_authority = _issue_realized_evidence_load_authority(
            authority_ref=authority_ref,
            authority=FixedRealizedHistory(wrong_result),
        )
        with pytest.raises(TypeError):
            load_derived_evidence(
                expected_ref,
                payload,
                realized_authority=wrong_authority,
            )

    class RealizedLoadEchoSubclass(RealizedEvidenceLoadVerificationEcho):
        pass

    subclass_authority = _issue_realized_evidence_load_authority(
        authority_ref=authority_ref,
        authority=FixedRealizedHistory(
            _echo_subclass_copy(RealizedLoadEchoSubclass, exact_load_echo)
        ),
    )
    with pytest.raises(TypeError):
        load_derived_evidence(
            expected_ref,
            payload,
            realized_authority=subclass_authority,
        )

    stale_echoes = (
        replace(
            exact_load_echo,
            authority_ref=_owner("policy_authority", "wrong_nominal_authority"),
        ),
        replace(
            exact_load_echo,
            expected_ref=replace(
                expected_ref,
                content_digest="sha256:" + "b" * 64,
            ),
        ),
        replace(
            exact_load_echo,
            content_digest="sha256:" + "b" * 64,
        ),
        replace(
            exact_load_echo,
            finalization=replace(
                exact_load_echo.finalization,
                accounting_verification=replace(
                    exact_load_echo.finalization.accounting_verification,
                    complete_unit_manifest_ref=_owner(
                        "protected_unit_manifest", "stale_manifest"
                    ),
                ),
            ),
        ),
        replace(
            exact_load_echo,
            finalization=replace(
                exact_load_echo.finalization,
                disposition_refs=(
                    replace(
                        disposition.to_ref(),
                        content_digest="sha256:" + "b" * 64,
                    ),
                ),
            ),
        ),
    )
    for stale_echo in stale_echoes:
        stale_authority = _issue_realized_evidence_load_authority(
            authority_ref=authority_ref,
            authority=FixedRealizedHistory(stale_echo),
        )
        with pytest.raises(ValueError):
            load_derived_evidence(
                expected_ref,
                payload,
                realized_authority=stale_authority,
            )


def test_accounting_capability_requires_exact_nominal_external_echo() -> None:
    disposition = _valid_disposition()
    primary = disposition.primary_population_ref
    selection = _population_ref(PopulationRole.OFFICIAL_PROPOSAL_Q, "population_q")
    authority_ref = _owner("accounting_authority", "fixture_accounting")
    arguments = {
        "sampling_plan_ref": disposition.sampling_plan_ref,
        "complete_unit_manifest_ref": _owner(
            "protected_unit_manifest", "complete_manifest"
        ),
        "intended_evidence_unit_refs": (disposition.intended_evidence_unit_ref,),
        "primary_population_ref": primary,
        "selection_population_ref": selection,
        "target_population_binding": ApplicabilityBinding.bound(primary),
        "official_proposal_binding": ApplicabilityBinding.bound(selection),
        "evidence_weight_binding": _na("nonaggregating_evidence_use"),
        "intended_estimand_or_reporting_ref": (
            disposition.evidence_scope.intended_estimand_or_reporting_ref
        ),
        "accounting_evidence_ref": _owner(
            "realized_evidence_accounting", "realized_accounting"
        ),
        "denominator_policy_ref": _owner("denominator_policy", "intended_denominator"),
        "censoring_policy_ref": _owner("censoring_policy", "fixture_censoring"),
        "missingness_adjustment_binding": _na("no_missingness_adjustment"),
        "sensitivity_analysis_binding": _na("no_sensitivity_analysis"),
        "construction_authority_ref": authority_ref,
        "construction_audit_refs": (_owner("audit_evidence", "accounting_audit"),),
    }

    class ExactAccountingRegistry:
        def __init__(
            self,
            field: str | None = None,
            replacement_value: object | None = None,
        ) -> None:
            self.field = field
            self.replacement_value = replacement_value

        def verify_evidence_accounting(
            self, *, candidate: EvidenceAccountingCapability
        ) -> EvidenceAccountingVerificationEcho:
            echo = _accounting_echo(candidate)
            if self.field is None:
                return echo
            return replace(
                echo,
                **{self.field: self.replacement_value},
            )

    capability = _issue_evidence_accounting_capability(
        **arguments,
        authority=ExactAccountingRegistry(),
    )
    assert (
        capability.complete_unit_manifest_ref == arguments["complete_unit_manifest_ref"]
    )

    class WrongReturnAccountingRegistry:
        def __init__(self, result: object) -> None:
            self.result = result

        def verify_evidence_accounting(
            self, *, candidate: EvidenceAccountingCapability
        ) -> object:
            del candidate
            return self.result

    for raw in (None, False, {}, lambda candidate: candidate):
        with pytest.raises(TypeError):
            _issue_evidence_accounting_capability(
                **arguments,
                authority=raw,
            )
    for result in (None, False, {}, (capability,)):
        with pytest.raises(TypeError):
            _issue_evidence_accounting_capability(
                **arguments,
                authority=WrongReturnAccountingRegistry(result),
            )

    class AccountingEchoSubclass(EvidenceAccountingVerificationEcho):
        pass

    with pytest.raises(TypeError):
        _issue_evidence_accounting_capability(
            **arguments,
            authority=WrongReturnAccountingRegistry(
                _echo_subclass_copy(
                    AccountingEchoSubclass,
                    _accounting_echo(capability),
                )
            ),
        )

    stale_values = {
        "sampling_plan_ref": replace(
            disposition.sampling_plan_ref, object_id="stale_sampling_plan"
        ),
        "complete_unit_manifest_ref": _owner(
            "protected_unit_manifest", "stale_manifest"
        ),
        "intended_evidence_unit_refs": (
            _owner("protected_intended_evidence_unit", "stale_slot"),
        ),
        "primary_population_ref": _population_ref(
            PopulationRole.TARGET_WORKLOAD_P, "stale_population_p"
        ),
        "selection_population_ref": _population_ref(
            PopulationRole.OFFICIAL_PROPOSAL_Q, "stale_population_q"
        ),
        "target_population_binding": ApplicabilityBinding.bound(
            _population_ref(PopulationRole.TARGET_WORKLOAD_P, "stale_target_p")
        ),
        "official_proposal_binding": ApplicabilityBinding.bound(
            _population_ref(PopulationRole.OFFICIAL_PROPOSAL_Q, "stale_proposal_q")
        ),
        "evidence_weight_binding": ApplicabilityBinding.bound(
            _population_ref(PopulationRole.EVIDENCE_WEIGHT_W, "stale_weight_w")
        ),
        "intended_estimand_or_reporting_ref": _owner(
            "intended_estimand_or_reporting", "stale_estimand"
        ),
        "accounting_evidence_ref": _owner(
            "realized_evidence_accounting", "stale_accounting"
        ),
        "denominator_policy_ref": _owner("denominator_policy", "stale_denominator"),
        "censoring_policy_ref": _owner("censoring_policy", "stale_censoring"),
        "missingness_adjustment_binding": ApplicabilityBinding.bound(
            _owner("missingness_adjustment", "stale_missingness")
        ),
        "sensitivity_analysis_binding": ApplicabilityBinding.bound(
            _owner("sensitivity_analysis", "stale_sensitivity")
        ),
        "construction_authority_ref": _owner("accounting_authority", "stale_authority"),
        "construction_audit_refs": (_owner("audit_evidence", "stale_audit"),),
    }
    for field, stale_value in stale_values.items():
        with pytest.raises(ValueError, match=field):
            _issue_evidence_accounting_capability(
                **arguments,
                authority=ExactAccountingRegistry(field, stale_value),
            )
    with pytest.raises(ValueError, match="construction_authority_ref"):
        _issue_evidence_accounting_capability(
            **arguments,
            authority=ExactAccountingRegistry(
                "construction_authority_ref",
                _owner("policy_authority", "wrong_nominal_authority"),
            ),
        )


def test_final_accounting_pins_dispositions_and_loaded_censoring_history() -> None:
    valid = _valid_disposition()
    primary = valid.primary_population_ref
    selection = _population_ref(PopulationRole.OFFICIAL_PROPOSAL_Q, "population_q")
    authority_ref = _owner("accounting_authority", "fixture_accounting")

    class ExactAccountingRegistry:
        def verify_evidence_accounting(
            self, *, candidate: EvidenceAccountingCapability
        ) -> EvidenceAccountingVerificationEcho:
            return _accounting_echo(candidate)

    capability = _issue_evidence_accounting_capability(
        sampling_plan_ref=valid.sampling_plan_ref,
        complete_unit_manifest_ref=_owner(
            "protected_unit_manifest", "complete_manifest"
        ),
        intended_evidence_unit_refs=(valid.intended_evidence_unit_ref,),
        primary_population_ref=primary,
        selection_population_ref=selection,
        target_population_binding=ApplicabilityBinding.bound(primary),
        official_proposal_binding=ApplicabilityBinding.bound(selection),
        evidence_weight_binding=_na("nonaggregating_evidence_use"),
        intended_estimand_or_reporting_ref=(
            valid.evidence_scope.intended_estimand_or_reporting_ref
        ),
        accounting_evidence_ref=_owner(
            "realized_evidence_accounting", "realized_accounting"
        ),
        denominator_policy_ref=_owner("denominator_policy", "intended_denominator"),
        censoring_policy_ref=_owner("censoring_policy", "fixture_censoring"),
        missingness_adjustment_binding=_na("no_missingness_adjustment"),
        sensitivity_analysis_binding=_na("no_sensitivity_analysis"),
        construction_authority_ref=authority_ref,
        construction_audit_refs=(_owner("audit_evidence", "accounting_audit"),),
        authority=ExactAccountingRegistry(),
    )

    class ExactFinalizationRegistry:
        def __init__(
            self,
            field: str | None = None,
            replacement_value: object | None = None,
            result: object | None = None,
        ) -> None:
            self.field = field
            self.replacement_value = replacement_value
            self.result = result

        def finalize_evidence_accounting(
            self,
            *,
            authority_ref: object,
            capability: EvidenceAccountingCapability,
            disposition_refs: tuple[object, ...],
            dispositions: tuple[CanonicalCaseDisposition, ...],
            censoring_record_refs: tuple[object, ...],
            censoring_records: tuple[CensoringRecord, ...],
        ) -> object:
            if self.result is not None:
                return self.result
            echo = EvidenceAccountingFinalizationEcho(
                authority_ref=authority_ref,
                accounting_verification=_accounting_echo(capability),
                capability=capability,
                disposition_refs=disposition_refs,
                dispositions=dispositions,
                censoring_record_refs=censoring_record_refs,
                censoring_records=censoring_records,
            )
            if self.field is None:
                return echo
            return replace(echo, **{self.field: self.replacement_value})

    finalization = _finalize_evidence_accounting(
        capability,
        (valid,),
        (),
        authority=ExactFinalizationRegistry(),
    )
    assert type(finalization) is FinalizedEvidenceAccountingCapability
    assert finalization.disposition_refs == (valid.to_ref(),)

    with pytest.raises(TypeError, match="finalized accounting"):
        construct_realized_valid_evidence(capability, (valid,))
    altered = replace(
        valid,
        audit_evidence_refs=(_owner("audit_evidence", "altered_case_audit"),),
    )
    with pytest.raises(ValueError, match="finalized accounting composition"):
        construct_realized_valid_evidence(finalization, (altered,))

    for raw in (None, False, {}, lambda candidate: candidate):
        with pytest.raises(TypeError):
            _finalize_evidence_accounting(
                capability,
                (valid,),
                (),
                authority=raw,
            )

    class WrongFinalizationRegistry:
        def __init__(self, result: object) -> None:
            self.result = result

        def finalize_evidence_accounting(self, **kwargs: object) -> object:
            del kwargs
            return self.result

    for wrong_result in (None, False, {}, (valid,)):
        with pytest.raises(TypeError):
            _finalize_evidence_accounting(
                capability,
                (valid,),
                (),
                authority=WrongFinalizationRegistry(wrong_result),
            )
    exact_finalization_echo = EvidenceAccountingFinalizationEcho(
        authority_ref=authority_ref,
        accounting_verification=_accounting_echo(capability),
        capability=capability,
        disposition_refs=finalization.disposition_refs,
        dispositions=finalization.dispositions,
        censoring_record_refs=(),
        censoring_records=(),
    )

    class FinalizationEchoSubclass(EvidenceAccountingFinalizationEcho):
        pass

    with pytest.raises(TypeError):
        _finalize_evidence_accounting(
            capability,
            (valid,),
            (),
            authority=WrongFinalizationRegistry(
                _echo_subclass_copy(
                    FinalizationEchoSubclass,
                    exact_finalization_echo,
                )
            ),
        )
    with pytest.raises(ValueError, match="authority mismatch"):
        _finalize_evidence_accounting(
            capability,
            (valid,),
            (),
            authority=WrongFinalizationRegistry(
                replace(
                    exact_finalization_echo,
                    authority_ref=_owner("policy_authority", "wrong_nominal_authority"),
                )
            ),
        )
    with pytest.raises(ValueError, match="disposition_refs"):
        _finalize_evidence_accounting(
            capability,
            (valid,),
            (),
            authority=ExactFinalizationRegistry(
                "disposition_refs",
                (
                    replace(
                        valid.to_ref(),
                        content_digest="sha256:" + "b" * 64,
                    ),
                ),
            ),
        )

    censoring = CensoringRecord(
        schema_version="1.0",
        canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
        intended_evidence_unit_ref=valid.intended_evidence_unit_ref,
        evidence_scope=valid.evidence_scope,
        censoring_reason=CensoringReason.REFERENCE_TIMEOUT,
        trigger_failure_binding=CensoringTrigger(
            CensoringTriggerKind.REFERENCE,
            _owner("reference_timeout", "reference_timeout_event"),
        ),
        actor_authority_ref=_owner("censoring_authority", "reference_policy"),
        population_ref=primary,
        sampling_plan_ref=valid.sampling_plan_ref,
        evidence_campaign_binding=valid.evidence_scope.evidence_campaign_binding,
        query_observation_provenance=(),
        replacement_decision=valid.replacement_decision,
        accounting_binding=_owner("censoring_accounting", "intended_unit_retained"),
        missingness_adjustment_binding=_na("no_missingness_adjustment"),
        audit_evidence_refs=(_owner("audit_evidence", "censoring_audit"),),
        downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
    )
    censored = replace(
        valid,
        case_state=CaseState.CENSORED,
        state_payload=CaseStatePayload(CaseState.CENSORED, censoring.to_ref()),
    )
    finalized_censored = _finalize_evidence_accounting(
        capability,
        (censored,),
        (censoring,),
        authority=ExactFinalizationRegistry(),
    )
    assert finalized_censored.censoring_record_refs == (censoring.to_ref(),)

    with pytest.raises(ValueError, match="exact loaded censoring record"):
        _finalize_evidence_accounting(
            capability,
            (censored,),
            (),
            authority=ExactFinalizationRegistry(),
        )
    fabricated_ref = replace(
        censoring.to_ref(),
        content_digest="sha256:" + "b" * 64,
    )
    fabricated_link = replace(
        censored,
        state_payload=CaseStatePayload(CaseState.CENSORED, fabricated_ref),
    )
    with pytest.raises(ValueError, match="exact loaded censoring record"):
        _finalize_evidence_accounting(
            capability,
            (fabricated_link,),
            (censoring,),
            authority=ExactFinalizationRegistry(),
        )
    tampered_censoring = replace(
        censoring,
        audit_evidence_refs=(_owner("audit_evidence", "tampered_censoring"),),
    )
    with pytest.raises(ValueError, match="exact loaded censoring record"):
        _finalize_evidence_accounting(
            capability,
            (censored,),
            (tampered_censoring,),
            authority=ExactFinalizationRegistry(),
        )


def test_multi_disposition_finalization_and_reload_use_one_canonical_order() -> None:
    template = _valid_disposition()
    candidates = tuple(
        replace(
            template,
            intended_evidence_unit_ref=_owner(
                "protected_intended_evidence_unit", f"slot_{index}"
            ),
        )
        for index in range(1, 9)
    )
    selected: tuple[CanonicalCaseDisposition, CanonicalCaseDisposition] | None = None
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            pair = (left, right)
            canonical_order = canonical_set_tuple(pair)
            digest_order = tuple(
                sorted(pair, key=lambda item: item.to_ref().content_digest)
            )
            if canonical_order != digest_order:
                selected = pair
                break
        if selected is not None:
            break
    assert selected is not None
    first, second = selected
    canonical_dispositions = canonical_set_tuple((second, first))
    assert canonical_dispositions != tuple(
        sorted((first, second), key=lambda item: item.to_ref().content_digest)
    )

    primary = template.primary_population_ref
    selection = _population_ref(PopulationRole.OFFICIAL_PROPOSAL_Q, "population_q")
    authority_ref = _owner("accounting_authority", "fixture_accounting")

    class ExactAccountingRegistry:
        def verify_evidence_accounting(
            self, *, candidate: EvidenceAccountingCapability
        ) -> EvidenceAccountingVerificationEcho:
            return _accounting_echo(candidate)

    capability = _issue_evidence_accounting_capability(
        sampling_plan_ref=template.sampling_plan_ref,
        complete_unit_manifest_ref=_owner(
            "protected_unit_manifest", "two_unit_manifest"
        ),
        intended_evidence_unit_refs=(
            first.intended_evidence_unit_ref,
            second.intended_evidence_unit_ref,
        ),
        primary_population_ref=primary,
        selection_population_ref=selection,
        target_population_binding=ApplicabilityBinding.bound(primary),
        official_proposal_binding=ApplicabilityBinding.bound(selection),
        evidence_weight_binding=_na("nonaggregating_evidence_use"),
        intended_estimand_or_reporting_ref=(
            template.evidence_scope.intended_estimand_or_reporting_ref
        ),
        accounting_evidence_ref=_owner(
            "realized_evidence_accounting", "two_unit_accounting"
        ),
        denominator_policy_ref=_owner("denominator_policy", "two_unit_denominator"),
        censoring_policy_ref=_owner("censoring_policy", "two_unit_censoring"),
        missingness_adjustment_binding=_na("no_missingness_adjustment"),
        sensitivity_analysis_binding=_na("no_sensitivity_analysis"),
        construction_authority_ref=authority_ref,
        construction_audit_refs=(
            _owner("audit_evidence", "two_unit_accounting_audit"),
        ),
        authority=ExactAccountingRegistry(),
    )

    class ExactFinalizer:
        def finalize_evidence_accounting(
            self,
            *,
            authority_ref: object,
            capability: EvidenceAccountingCapability,
            disposition_refs: tuple[object, ...],
            dispositions: tuple[CanonicalCaseDisposition, ...],
            censoring_record_refs: tuple[object, ...],
            censoring_records: tuple[CensoringRecord, ...],
        ) -> EvidenceAccountingFinalizationEcho:
            return EvidenceAccountingFinalizationEcho(
                authority_ref=authority_ref,
                accounting_verification=_accounting_echo(capability),
                capability=capability,
                disposition_refs=disposition_refs,
                dispositions=dispositions,
                censoring_record_refs=censoring_record_refs,
                censoring_records=censoring_records,
            )

    finalization = _finalize_evidence_accounting(
        capability,
        (second, first),
        (),
        authority=ExactFinalizer(),
    )
    assert finalization.dispositions == canonical_dispositions
    realized = construct_realized_valid_evidence(
        finalization,
        (first, second),
        schema_version="1.0",
        canonicalization_profile=DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        sampling_plan_ref=capability.sampling_plan_ref,
        primary_population_ref=capability.primary_population_ref,
        selection_population_ref=capability.selection_population_ref,
        target_population_binding=capability.target_population_binding,
        official_proposal_binding=capability.official_proposal_binding,
        evidence_weight_binding=capability.evidence_weight_binding,
        intended_estimand_or_reporting_ref=(
            capability.intended_estimand_or_reporting_ref
        ),
        evidence_scope=template.evidence_scope,
        accounting_evidence_ref=capability.accounting_evidence_ref,
        denominator_policy_ref=capability.denominator_policy_ref,
        censoring_policy_ref=capability.censoring_policy_ref,
        missingness_adjustment_binding=(capability.missingness_adjustment_binding),
        sensitivity_analysis_binding=capability.sensitivity_analysis_binding,
        distribution_conformance_evidence_ref=_owner(
            "distribution_conformance", "two_unit_conformance"
        ),
        disclosure_contract=_disclosure(),
        downstream_use_restrictions=(_owner("restriction", "fixture_only"),),
    )

    class ExactHistory:
        def verify_realized_evidence_load(
            self,
            *,
            authority_ref: object,
            expected_ref: object,
            content_digest: str,
            decoded_record: object,
        ) -> RealizedEvidenceLoadVerificationEcho:
            del decoded_record
            return RealizedEvidenceLoadVerificationEcho(
                authority_ref=authority_ref,
                expected_ref=expected_ref,
                content_digest=content_digest,
                finalization=EvidenceAccountingFinalizationEcho(
                    authority_ref=authority_ref,
                    accounting_verification=_accounting_echo(capability),
                    capability=capability,
                    disposition_refs=finalization.disposition_refs,
                    dispositions=finalization.dispositions,
                    censoring_record_refs=(),
                    censoring_records=(),
                ),
            )

    loaded = load_derived_evidence(
        realized.to_ref(),
        realized.canonical_bytes(),
        realized_authority=_issue_realized_evidence_load_authority(
            authority_ref=authority_ref,
            authority=ExactHistory(),
        ),
    )
    assert loaded == realized
    assert loaded.disposition_refs == finalization.disposition_refs


def test_authored_objects_are_frozen() -> None:
    value = _physical()
    with pytest.raises(FrozenInstanceError):
        value.object_id = "changed"
