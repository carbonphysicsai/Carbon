"""Complete transient B-03 service fixtures and nominal authority doubles."""

from __future__ import annotations

from dataclasses import dataclass, replace

from carbon.authoring.evidence import (
    CensoringTrigger,
    CensoringTriggerKind,
    EvidenceScopeBinding,
    InfrastructureCensoringTrigger,
    ReplacementDecision,
    ReplacementDecisionKind,
    ReplacementPolicyBinding,
    ReplacementPolicyBindingKind,
)
from carbon.authoring.loading import FixtureAuthoringCapability, load_authoring_bytes
from carbon.authoring.model import (
    AllowedConsumer,
    AllowedConsumerKind,
    ApplicabilityBinding,
    CasePopulationUse,
    CensoringReason,
    DisclosureClass,
    DisclosureContract,
    PopulationRole,
    PrecisionLiteral,
    SamplingRole,
)
from carbon.authoring.physical import (
    AssumptionClause,
    AxisContract,
    AxisExtent,
    AxisExtentKind,
    BoundaryConditionContract,
    CandidateInputBinding,
    CandidateInputRelation,
    CandidateInputRelationKind,
    CandidateOutputBinding,
    CandidateOutputContract,
    CandidateOutputRelation,
    CandidateOutputRelationKind,
    InitialConditionContract,
    PhysicalSystemSpec,
    Presence,
    PresenceKind,
    TimeContract,
    TimeHorizonBinding,
    TimeMode,
    ValueFieldContract,
)
from carbon.authoring.populations import (
    ExclusionContract,
    FiniteEnumeration,
    InstanceDistributionContract,
    LawKind,
    LawSemantics,
    SupportContract,
    WeightingSemantics,
    WeightingSemanticsKind,
)
from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.authoring.sampling import (
    CandidateOutcomeAccessBinding,
    CandidateOutcomeAccessKind,
    DuplicatePolicy,
    FiniteDesignMode,
    FiniteEvidenceDesign,
    ProspectiveStoppingExtensionPolicy,
    RegisteredReplacementPolicy,
    ReplacementPolicy,
    ReplacementPolicyKind,
    ReplacementTrigger,
    ReplacementTriggerKind,
    SamplingPlan,
)
from carbon.generators.accounting import (
    AttemptAccountingDirective,
    AttemptAccountingDirectiveKind,
)
from carbon.generators.authorities import (
    CensoringRecordBasis,
    CensoringVerdict,
    CensoringVerdictKind,
    FixtureGenerationAuthority,
    IntendedUnitLinkDecision,
    IntendedUnitLinkRequest,
    PopulationAssessmentRole,
    PopulationSupportAssessment,
    PopulationSupportDecisionKind,
    SupportExclusionDecision,
    SupportExclusionDecisionKind,
)
from carbon.generators.burgers import (
    BURGERS_FIXTURE_GRID_POINTS,
    burgers_fixture_configuration,
    burgers_fixture_configuration_ref,
)
from carbon.generators.canonical import canonical_content_digest
from carbon.generators.conformance import CONFORMANCE_FALLBACK_SCHEMA
from carbon.generators.model import (
    ApplicabilityReasonKind,
    AttemptAccountingFallback,
    CaseConstructionBinding,
    DispositionConstructionBinding,
    FailureOccurrenceEvidenceCategory,
    FixtureLoadingBinding,
    GenerationRoleBinding,
    GeneratorDescriptor,
    GeneratorEnvironmentClass,
    GeneratorEnvironmentDescriptor,
    GeneratorFailureCatalogEntry,
    GeneratorFailureReason,
    GeneratorOutcomeKind,
    GeneratorRequest,
    GeneratorTerminalStage,
    NamedApplicabilityReason,
    NamedConformanceFallback,
    ResolvedGeneratorAuthoringBundle,
)
from carbon.generators.service import burgers_fixture_implementation_manifest
from carbon.registry.model import ChallengeKey
from carbon.seeding.model import (
    EvaluationBinding,
    FixtureOfficialEntropy,
    RoleKey,
    SeedDomain,
    SeedPin,
)
from carbon.seeding.provider import DeterministicFixtureProvider

_DIGEST = "sha256:" + "0" * 64
_KEY = ChallengeKey("b03_generator_fixture", "1.0")

_FAILURE_CATALOG_SCHEMA = (
    (
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.MATERIALIZATION,
        "b03_sampler_contract_violation",
        "sampler_contract_violation",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        "b03_outside_registered_support",
        "outside_registered_support",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY,
        "b03_construction_compatibility_failed",
        "construction_compatibility_failed",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        "b03_case_construction_failed",
        "case_construction_failed",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INVALID_CONSTRUCTION,
        GeneratorTerminalStage.GRAPH_VALIDATION,
        "b03_authoring_graph_invalid",
        "authoring_graph_invalid",
        FailureOccurrenceEvidenceCategory.AUDIT_EVIDENCE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CONTEXT_ACQUISITION,
        "b03_context_acquisition_unavailable",
        "context_acquisition_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.DERIVATION,
        "b03_seed_derivation_unavailable",
        "seed_derivation_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.MATERIALIZATION,
        "b03_materialization_infrastructure_failure",
        "materialization_infrastructure_failure",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.SUPPORT_AUTHORITY,
        "b03_support_authority_unavailable",
        "support_authority_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CASE_CONSTRUCTION,
        "b03_case_construction_infrastructure_failure",
        "case_construction_infrastructure_failure",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.CENSORING_AUTHORITY,
        "b03_censoring_authority_unavailable",
        "censoring_authority_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
        "b03_attempt_accounting_authority_unavailable",
        "attempt_accounting_authority_unavailable",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
    (
        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        GeneratorTerminalStage.GRAPH_VALIDATION,
        "b03_graph_validation_infrastructure_failure",
        "graph_validation_infrastructure_failure",
        FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE,
    ),
)


def challenge_owner(
    ref_kind: str,
    object_id: str,
    *,
    content_digest: str = _DIGEST,
    challenge_key: ChallengeKey = _KEY,
) -> object:
    return owner_ref(
        ref_kind,
        scope_binding=ChallengeScope(challenge_key),
        object_id=object_id,
        object_version="1.0",
        content_digest=content_digest,
    )


def _na(object_id: str) -> ApplicabilityBinding[object]:
    return ApplicabilityBinding.not_applicable(
        challenge_owner("applicability_reason", object_id)
    )


def _disclosure() -> DisclosureContract:
    return DisclosureContract(
        public_field_ids=(),
        internal_field_ids=(),
        protected_field_ids=("physical_payload",),
        aggregation_policy_ref=challenge_owner(
            "aggregation_policy", "fixture_aggregation"
        ),
        release_policy_ref=challenge_owner("release_policy", "fixture_release"),
    )


def _spatial_field(field_id: str, semantic_id: str) -> ValueFieldContract:
    return ValueFieldContract(
        field_id=field_id,
        semantic_role_ref=challenge_owner("semantic_clause", semantic_id),
        representation_ref=challenge_owner("representation", "dense_float64_vector"),
        unit_ref=challenge_owner("unit", "dimensionless"),
        shape_contract=(
            AxisContract(
                axis_id="space",
                semantic_role_ref=challenge_owner(
                    "semantic_clause", "periodic_space_axis"
                ),
                unit_ref=challenge_owner("unit", "dimensionless"),
                extent=AxisExtent(
                    AxisExtentKind.FIXED,
                    fixed_extent=BURGERS_FIXTURE_GRID_POINTS,
                ),
            ),
        ),
        precision_contract=(PrecisionLiteral.FLOAT64,),
        geometry_binding=ApplicabilityBinding.bound(
            challenge_owner("geometry_domain", "periodic_unit_interval")
        ),
        presence=Presence(PresenceKind.REQUIRED),
        admissibility_refs=(
            challenge_owner("semantic_clause", "finite_float64_values"),
        ),
        nonfinite_policy="REJECT",
    )


def _time_field(field_id: str) -> ValueFieldContract:
    return ValueFieldContract(
        field_id=field_id,
        semantic_role_ref=challenge_owner("semantic_clause", "time_coordinate"),
        representation_ref=challenge_owner("representation", "scalar_float64"),
        unit_ref=challenge_owner("unit", "fixture_time"),
        shape_contract=(),
        precision_contract=(PrecisionLiteral.FLOAT64,),
        geometry_binding=_na("time_has_no_geometry"),
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
        object_id="burgers_transient_physical",
        object_version="1.0",
        supersedes=_na("first_physical_version"),
        governing_job_ref=challenge_owner(
            "semantic_clause", "burgers_fixture_question"
        ),
        governing_law_refs=(challenge_owner("semantic_clause", "viscous_burgers_law"),),
        assumptions=(
            AssumptionClause(
                assumption_id="fixture_periodic_fixed_viscosity",
                semantic_ref=challenge_owner(
                    "semantic_clause", "periodic_fixed_viscosity_fixture_only"
                ),
                applicability=ApplicabilityBinding.bound(
                    challenge_owner("applicability", "fixture_only")
                ),
                authority_ref=challenge_owner(
                    "scientific_authority", "fixture_contract_only"
                ),
            ),
        ),
        causal_inputs=(_spatial_field("initial_state", "initial_state_semantics"),),
        required_physical_quantities=(_spatial_field("state", "state_semantics"),),
        geometry_domain_ref=challenge_owner(
            "geometry_domain", "periodic_unit_interval"
        ),
        boundary_conditions=BoundaryConditionContract(()),
        initial_conditions=InitialConditionContract(()),
        time_contract=TimeContract(
            mode=TimeMode.TRANSIENT,
            time_coordinate_binding=ApplicabilityBinding.bound(_time_field("time")),
            horizon_binding=ApplicabilityBinding.bound(
                challenge_owner("semantic_clause", "fixture_time_horizon")
            ),
            endpoint_inclusion_semantic_ref=challenge_owner(
                "semantic_clause", "closed_time_horizon"
            ),
            time_unit_ref=challenge_owner("unit", "fixture_time"),
        ),
        operating_envelope_ref=challenge_owner(
            "operating_envelope", "fixture_only_envelope"
        ),
        claim_scope_ref=challenge_owner("claim_scope", "fixture_only_claim"),
        missing_input_policy="REJECT",
    )


def _candidate(physical: PhysicalSystemSpec) -> CandidateOutputContract:
    initial = replace(physical.causal_inputs[0], field_id="candidate_initial_state")
    time = replace(
        physical.time_contract.time_coordinate_binding.value,
        field_id="candidate_time",
    )
    state = replace(
        physical.required_physical_quantities[0],
        field_id="candidate_state",
    )
    return CandidateOutputContract(
        object_kind="candidate_output_contract",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="burgers_candidate_contract",
        object_version="1.0",
        supersedes=_na("first_candidate_version"),
        physical_system_ref=physical.to_ref(),
        candidate_inputs=(initial, time),
        causal_input_bindings=(
            CandidateInputBinding(
                physical_field_id="initial_state",
                candidate_field_id="candidate_initial_state",
                relation=CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
        ),
        required_outputs=(state,),
        physical_output_bindings=(
            CandidateOutputBinding(
                physical_quantity_id="state",
                candidate_field_id="candidate_state",
                relation=CandidateOutputRelation(CandidateOutputRelationKind.IDENTITY),
                semantic_equivalence_ref=challenge_owner(
                    "semantic_equivalence", "state_identity"
                ),
            ),
        ),
        candidate_representation_ref=challenge_owner(
            "representation", "burgers_candidate_io"
        ),
        geometry_domain_ref=physical.geometry_domain_ref,
        boundary_input_bindings=(),
        initial_input_bindings=(),
        time_horizon_binding=TimeHorizonBinding(
            candidate_field_ids=("candidate_time",),
            time_coordinate_equivalence_ref=challenge_owner(
                "semantic_equivalence", "time_coordinate_identity"
            ),
            horizon_equivalence_ref=challenge_owner(
                "semantic_equivalence", "time_horizon_identity"
            ),
            endpoint_equivalence_ref=challenge_owner(
                "semantic_equivalence", "time_endpoint_identity"
            ),
        ),
        operating_envelope_ref=physical.operating_envelope_ref,
        claim_scope_ref=physical.claim_scope_ref,
        missing_or_extra_policy="REJECT",
        malformed_output_policy="CANDIDATE_FORMAT_FAILURE",
    )


def _support(object_id: str) -> SupportContract:
    return SupportContract(
        membership_rule_ref=challenge_owner("membership_rule", f"{object_id}_rule"),
        physical_support_ref=challenge_owner(
            "physical_support", f"{object_id}_physical"
        ),
        representation_support_ref=challenge_owner(
            "representation_support", f"{object_id}_representation"
        ),
        boundary_semantics_ref=challenge_owner(
            "support_boundary", f"{object_id}_closed_boundary"
        ),
        membership_decision_ref=challenge_owner(
            "membership_decision", f"{object_id}_membership_decision"
        ),
        failure_outcome="REJECT",
    )


def _population(
    role: PopulationRole,
    physical: PhysicalSystemSpec,
    candidate: CandidateOutputContract,
    *,
    target_binding: ApplicabilityBinding[object] | None = None,
    exclusions: tuple[ExclusionContract, ...] = (),
) -> InstanceDistributionContract:
    object_id = (
        "burgers_primary_p"
        if role is PopulationRole.TARGET_WORKLOAD_P
        else "burgers_selection_q"
    )
    law = (
        LawSemantics(
            LawKind.FINITE_ENUMERATION,
            FiniteEnumeration(
                challenge_owner("member_set", "fixture_latent_lattice"),
                challenge_owner("multiplicity_semantics", "uniform_fixture_members"),
            ),
        )
        if role is PopulationRole.OFFICIAL_PROPOSAL_Q
        else LawSemantics(
            LawKind.SET_MEMBERSHIP_ONLY,
            challenge_owner("no_prevalence_claim", "fixture_membership_only"),
        )
    )
    return InstanceDistributionContract(
        object_kind="instance_distribution_contract",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id=object_id,
        object_version="1.0",
        supersedes=_na(f"first_{object_id}"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        population_role=role,
        owning_claim_scope_ref=physical.claim_scope_ref,
        target_population_binding=target_binding or _na(f"{object_id}_no_target"),
        proposal_population_binding=_na(f"{object_id}_no_proposal"),
        support_contract=_support(object_id),
        law_semantics=law,
        weighting_semantics=WeightingSemantics(
            WeightingSemanticsKind.NOT_APPLICABLE,
            challenge_owner(
                "applicability_reason", f"{object_id}_no_weighting_semantics"
            ),
        ),
        stratification_binding=_na(f"{object_id}_unstratified"),
        applicability_refs=(
            challenge_owner("applicability", f"{object_id}_fixture_applicability"),
        ),
        exclusions=exclusions,
        rights_profile_ref=challenge_owner(
            "rights_profile", f"{object_id}_fixture_rights"
        ),
        permitted_use_refs=(
            challenge_owner("permitted_use", f"{object_id}_fixture_use"),
        ),
        restrictions=(challenge_owner("restriction", "fixture_only"),),
        disclosure_contract=_disclosure(),
        allowed_consumers=(
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE,
                CasePopulationUse.PRIMARY,
            ),
            AllowedConsumer(
                AllowedConsumerKind.SAMPLING_PLAN,
                SamplingRole.OFFICIAL_EVALUATION,
            ),
        ),
        population_provenance=(
            challenge_owner("provenance", f"{object_id}_provenance"),
        ),
    )


def _failure_catalog() -> tuple[GeneratorFailureCatalogEntry, ...]:
    entries = []
    for outcome, stage, reason_id, reason_code, category in _FAILURE_CATALOG_SCHEMA:
        reason = GeneratorFailureReason(
            challenge_key=_KEY,
            reason_id=reason_id,
            reason_version="1.0",
            outcome_kind=outcome,
            terminal_stage=stage,
            reason_code=reason_code,
            occurrence_evidence_category=category,
        )
        if outcome is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE:
            digest = canonical_content_digest(reason)
            generation_alias = ApplicabilityBinding.bound(
                challenge_owner(
                    "generation_failure",
                    reason_id,
                    content_digest=digest,
                )
            )
            replacement_alias = ApplicabilityBinding.bound(
                challenge_owner(
                    "replacement_eligible_generation_failure_reason",
                    reason_id,
                    content_digest=digest,
                )
            )
        else:
            not_applicable = challenge_owner(
                "applicability_reason", f"{reason_id}_alias_inapplicable"
            )
            generation_alias = ApplicabilityBinding.not_applicable(not_applicable)
            replacement_alias = ApplicabilityBinding.not_applicable(not_applicable)
        fallback_kind = (
            "infrastructure_failure"
            if category is FailureOccurrenceEvidenceCategory.INFRASTRUCTURE_FAILURE
            else "audit_evidence"
        )
        entries.append(
            GeneratorFailureCatalogEntry(
                reason=reason,
                reason_ref=reason.to_ref(),
                generation_failure_alias_binding=generation_alias,
                replacement_eligible_generation_failure_alias_binding=(
                    replacement_alias
                ),
                occurrence_evidence_fallback=challenge_owner(
                    fallback_kind, f"{reason_id}_occurrence"
                ),
            )
        )
    return tuple(entries)


def _sampling_plan(
    primary: InstanceDistributionContract,
    selection: InstanceDistributionContract,
    failure_catalog: tuple[GeneratorFailureCatalogEntry, ...],
    prospective_exclusion_ref: object,
) -> SamplingPlan:
    replacement_triggers = (
        ReplacementTrigger(
            ReplacementTriggerKind.CENSORED,
            CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER,
        ),
        ReplacementTrigger(
            ReplacementTriggerKind.EXCLUDED,
            prospective_exclusion_ref,
        ),
        *tuple(
            ReplacementTrigger(
                ReplacementTriggerKind.GENERATION_FAILURE,
                entry.replacement_eligible_generation_failure_alias_binding.value,
            )
            for entry in failure_catalog
            if entry.reason.outcome_kind
            is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE
        ),
    )
    registered_policy = RegisteredReplacementPolicy(
        policy_ref=challenge_owner("replacement_policy", "fixture_replacement"),
        triggers=replacement_triggers,
        replacement_selection_law_ref=challenge_owner(
            "replacement_selection_law", "fixture_same_selection_law"
        ),
        stratum_treatment_ref=challenge_owner(
            "replacement_stratum_treatment", "fixture_preserve_stratum"
        ),
        maximum_attempt_rule_ref=challenge_owner(
            "maximum_attempt_rule", "fixture_bounded_attempt_rule"
        ),
        accounting_rule_ref=challenge_owner(
            "replacement_accounting", "fixture_replacement_rule"
        ),
        denominator_effect_ref=challenge_owner(
            "denominator_effect", "fixture_attempt_remains_visible"
        ),
        weight_effect_ref=challenge_owner(
            "weight_effect", "fixture_no_silent_reweighting"
        ),
    )
    return SamplingPlan(
        object_kind="sampling_plan",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=_KEY,
        object_id="burgers_fixture_sampling_plan",
        object_version="1.0",
        supersedes=_na("first_sampling_plan"),
        sampling_role=SamplingRole.OFFICIAL_EVALUATION,
        primary_population_ref=primary.to_ref(),
        selection_population_ref=selection.to_ref(),
        target_population_binding=ApplicabilityBinding.bound(primary.to_ref()),
        official_proposal_binding=ApplicabilityBinding.bound(selection.to_ref()),
        evidence_weight_binding=_na("fixture_nonaggregating_evidence"),
        query_population_binding=_na("fixture_no_query_population"),
        observation_population_binding=_na("fixture_no_observation_population"),
        evidence_campaign_binding=_na("fixture_no_evidence_campaign"),
        intended_estimand_or_reporting_ref=challenge_owner(
            "intended_estimand_or_reporting", "fixture_structural_reporting"
        ),
        finite_evidence_design=FiniteEvidenceDesign(
            count_unit_ref=challenge_owner("sampling_unit", "case"),
            design_mode=FiniteDesignMode.FIXED,
            base_intended_count=1,
            base_evidence_requirement_ref=challenge_owner(
                "base_evidence_requirement", "one_fixture_case"
            ),
            budget_binding=_na("fixture_fixed_no_budget"),
            extension_ceiling_binding=_na("fixture_fixed_no_extension"),
            heuristic_stop_outcome="EVIDENCE_DEFERRED",
            insufficiency_state="INDETERMINATE",
            insufficiency_reason="INSUFFICIENT_EVIDENCE",
            plan_change_rule="NEW_VERSION_REQUIRED",
        ),
        full_design_law_ref=challenge_owner(
            "full_design_law", "fixture_finite_enumeration"
        ),
        stratified_allocation_binding=_na("fixture_unstratified"),
        query_observation_allocation_binding=_na("fixture_no_query_allocation"),
        reference_fidelity_allocation_binding=_na("fixture_no_reference_allocation"),
        replication_dependence_policy_ref=challenge_owner(
            "replication_dependence_policy", "fixture_deterministic_dependence"
        ),
        uncertainty_resolution_objectives_binding=_na(
            "fixture_no_uncertainty_objective"
        ),
        tail_resolution_objectives_binding=_na("fixture_no_tail_objective"),
        minimum_subgroup_objectives_binding=_na("fixture_no_subgroup_objective"),
        draw_order_semantics_ref=challenge_owner(
            "draw_order_semantics", "fixture_monotone_draw_index"
        ),
        stopping_extension_policy=ProspectiveStoppingExtensionPolicy(
            stopping_rule_ref=challenge_owner("stopping_rule", "fixture_fixed_count"),
            extension_rule_binding=_na("fixture_no_extension_rule"),
            interim_look_binding=_na("fixture_no_interim_look"),
            sequential_allocation_binding=_na("fixture_no_sequential_allocation"),
            candidate_outcome_access_binding=CandidateOutcomeAccessBinding(
                CandidateOutcomeAccessKind.CANDIDATE_OUTCOMES_PROHIBITED,
                challenge_owner("blinding_policy", "fixture_blinded"),
            ),
            coverage_qualification_binding=_na("fixture_no_coverage_qualification"),
            modification_authority_ref=challenge_owner(
                "modification_authority", "fixture_no_runtime_modification"
            ),
        ),
        replacement_policy=ReplacementPolicy(
            ReplacementPolicyKind.ON_REGISTERED_TRIGGERS,
            registered_policy,
        ),
        duplicate_policy=DuplicatePolicy(
            physical_duplicate_rule_ref=challenge_owner(
                "duplicate_rule", "fixture_physical_exact"
            ),
            representation_duplicate_rule_ref=challenge_owner(
                "duplicate_rule", "fixture_representation_exact"
            ),
            near_duplicate_rule_ref=challenge_owner(
                "duplicate_rule", "fixture_near_duplicate_external"
            ),
            repeated_observation_rule_ref=challenge_owner(
                "duplicate_rule", "fixture_no_observation"
            ),
            replacement_duplicate_rule_ref=challenge_owner(
                "duplicate_rule", "fixture_replacement_duplicate"
            ),
        ),
        inclusion_policy_ref=challenge_owner(
            "inclusion_policy", "fixture_registered_support"
        ),
        exclusion_policy_ref=challenge_owner(
            "exclusion_policy", "fixture_registered_exclusions"
        ),
        censoring_policy_ref=challenge_owner(
            "censoring_policy", "fixture_prospective_censoring"
        ),
        public_authored_facts=(),
        protected_realization_fields=(),
        statistical_qualification_requirements_ref=challenge_owner(
            "statistical_qualification_requirement", "fixture_unqualified"
        ),
        plan_provenance_refs=(challenge_owner("provenance", "fixture_plan"),),
        insufficient_or_failure_policy="NON_SETTLING_FAIL_CLOSED",
    )


def _loaded_bundle(
    physical: PhysicalSystemSpec,
    candidate: CandidateOutputContract,
    primary: InstanceDistributionContract,
    selection: InstanceDistributionContract,
    plan: SamplingPlan,
    *,
    fixture_registration_ref: object,
    source_provenance_refs: tuple[object, ...],
) -> ResolvedGeneratorAuthoringBundle:
    origin = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=fixture_registration_ref,
        source_provenance_refs=source_provenance_refs,
    )
    objects = (physical, candidate, primary, selection, plan)
    pairs = tuple(
        sorted(
            ((value.to_ref(), value) for value in objects),
            key=lambda pair: (
                pair[0].object_kind,
                pair[0].challenge_key.challenge_id,
                pair[0].challenge_key.version,
                pair[0].object_id,
                pair[0].object_version,
                pair[0].schema_version,
                pair[0].canonicalization_profile,
                pair[0].content_digest,
                getattr(pair[0], "expected_population_role", ""),
            ),
        )
    )
    loaded = tuple(
        load_authoring_bytes(
            ref,
            value.canonical_bytes(),
            origin=origin,
            origin_evidence_ref=challenge_owner(
                "authoring_origin_evidence", f"fixture_origin_{value.object_id}"
            ),
            source_provenance_refs=source_provenance_refs,
            audit_evidence_refs=(
                challenge_owner("audit_evidence", "fixture_authoring_load"),
            ),
            qualification_evidence=_na("fixture_not_scientifically_qualified"),
        )
        for ref, value in pairs
    )
    return ResolvedGeneratorAuthoringBundle(
        physical_system=physical,
        physical_system_ref=physical.to_ref(),
        candidate_output=candidate,
        candidate_output_ref=candidate.to_ref(),
        primary_population=primary,
        primary_population_ref=primary.to_ref(),
        selection_population=selection,
        selection_population_ref=selection.to_ref(),
        sampling_plan=plan,
        sampling_plan_ref=plan.to_ref(),
        resolved_dependencies=pairs,
        loaded_dependencies=loaded,
    )


def _reason_catalogs(
    failure_catalog: tuple[GeneratorFailureCatalogEntry, ...],
) -> tuple[
    tuple[NamedApplicabilityReason, ...],
    tuple[NamedApplicabilityReason, ...],
    tuple[NamedConformanceFallback, ...],
]:
    reasons = tuple(
        NamedApplicabilityReason(
            kind,
            challenge_owner("applicability_reason", f"runtime_{kind.value.lower()}"),
        )
        for kind in ApplicabilityReasonKind
    )
    support_fallback = next(
        entry.occurrence_evidence_fallback
        for entry in failure_catalog
        if entry.reason.outcome_kind is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
        and entry.reason.terminal_stage is GeneratorTerminalStage.SUPPORT_AUTHORITY
    )
    conformance = tuple(
        NamedConformanceFallback(
            fallback_id,
            (
                support_fallback
                if fallback_id == "support_decision_owner_unavailable"
                else challenge_owner(
                    "applicability_reason", f"conformance_{fallback_id}"
                )
            ),
        )
        for fallback_id in CONFORMANCE_FALLBACK_SCHEMA
    )
    return reasons[:7], reasons[7:], conformance


class NominalSupportAuthority:
    """Exact support owner double with one externally selected resolution."""

    def __init__(
        self,
        bundle: ResolvedGeneratorAuthoringBundle,
        prospective_exclusion_ref: object,
        mode: str = "within",
    ) -> None:
        self.bundle = bundle
        self.prospective_exclusion_ref = prospective_exclusion_ref
        self.mode = mode
        self.calls = 0

    @staticmethod
    def _not_applicable(prefix: str, name: str) -> ApplicabilityBinding[object]:
        return _na(f"{prefix}_{name}_inapplicable")

    def _assessment(
        self,
        request: object,
        role: PopulationAssessmentRole,
        population: InstanceDistributionContract,
        decision: PopulationSupportDecisionKind,
    ) -> PopulationSupportAssessment:
        prefix = f"{role.value.lower()}_{decision.value.lower()}"
        na = self._not_applicable
        if decision is PopulationSupportDecisionKind.REGISTERED_EXCLUSION:
            exclusion = population.exclusions[0]
            exclusion_binding = ApplicabilityBinding.bound(exclusion)
            applicability = na(prefix, "applicability")
            membership = na(prefix, "membership")
            exclusion_contract = ApplicabilityBinding.bound(
                challenge_owner("exclusion_contract", exclusion.exclusion_id)
            )
            prospective = ApplicabilityBinding.bound(self.prospective_exclusion_ref)
            assessment = ApplicabilityBinding.bound(
                challenge_owner("exclusion_assessment", "fixture_exclusion")
            )
            screening = ApplicabilityBinding.bound(
                challenge_owner("screening_design", "fixture_exclusion_screen")
            )
            inclusion = ApplicabilityBinding.bound(
                challenge_owner(
                    "inclusion_probability_accounting",
                    "fixture_exclusion_probability",
                )
            )
        else:
            exclusion_binding = na(prefix, "exclusion_contract_object")
            applicability = ApplicabilityBinding.bound(
                challenge_owner("applicability_evidence", f"{prefix}_applicability")
            )
            membership = ApplicabilityBinding.bound(
                challenge_owner("membership_evidence", f"{prefix}_membership")
            )
            exclusion_contract = na(prefix, "exclusion_contract")
            prospective = na(prefix, "prospective_exclusion")
            assessment = na(prefix, "exclusion_assessment")
            screening = na(prefix, "screening")
            inclusion = na(prefix, "inclusion")
        return PopulationSupportAssessment(
            assessment_role=role,
            population_ref=population.to_ref(),
            support_contract=population.support_contract,
            exclusion_contract_binding=exclusion_binding,
            decision_kind=decision,
            applicability_evidence_binding=applicability,
            membership_evidence_binding=membership,
            exclusion_contract_ref_binding=exclusion_contract,
            prospective_exclusion_contract_ref_binding=prospective,
            exclusion_assessment_ref_binding=assessment,
            screening_design_ref_binding=screening,
            inclusion_probability_accounting_ref_binding=inclusion,
            infrastructure_failure_binding=na(prefix, "infrastructure"),
        )

    def assess_support_exclusion(self, request: object) -> SupportExclusionDecision:
        self.calls += 1
        if self.mode == "unavailable":
            raise RuntimeError("fixture support owner unavailable")
        bundle = self.bundle
        selection = self._assessment(
            request,
            PopulationAssessmentRole.SELECTION_MATERIALIZATION,
            bundle.selection_population,
            PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT,
        )
        primary_kind = {
            "within": PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT,
            "excluded": PopulationSupportDecisionKind.REGISTERED_EXCLUSION,
            "outside": PopulationSupportDecisionKind.OUTSIDE_REGISTERED_SUPPORT,
        }[self.mode]
        primary = self._assessment(
            request,
            PopulationAssessmentRole.PRIMARY_CASE,
            bundle.primary_population,
            primary_kind,
        )
        within = primary_kind is PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT
        return SupportExclusionDecision(
            challenge_key=_KEY,
            request=request,
            decision_kind=SupportExclusionDecisionKind.ASSESSED,
            assessments=(selection, primary),
            terminal_resolution=primary_kind,
            effective_assessment_role=(
                None if within else PopulationAssessmentRole.PRIMARY_CASE
            ),
            resolution_policy_ref=(
                None
                if within
                else challenge_owner("policy_authority", "fixture_support_resolution")
            ),
            resolution_evidence_ref=(
                None
                if within
                else challenge_owner(
                    "membership_decision", "fixture_support_resolution"
                )
            ),
            infrastructure_failure_ref=None,
        )


class NominalCensoringAuthority:
    """Exact censor owner double; its policy choice stays outside B-03."""

    def __init__(self, mode: str = "not_censored") -> None:
        self.mode = mode
        self.calls = 0

    def decide_censoring(self, request: object) -> CensoringVerdict:
        self.calls += 1
        if self.mode == "unavailable":
            raise RuntimeError("fixture censor owner unavailable")
        if self.mode == "not_censored":
            return CensoringVerdict(
                challenge_key=_KEY,
                request=request,
                verdict_kind=CensoringVerdictKind.NOT_CENSORED,
                basis=None,
                infrastructure_failure_ref=None,
            )
        basis = CensoringRecordBasis(
            intended_evidence_unit_ref=request.intended_evidence_unit_ref,
            evidence_scope=request.evidence_scope,
            censoring_reason=(
                CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER
            ),
            trigger_failure_binding=CensoringTrigger(
                CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE,
                InfrastructureCensoringTrigger(
                    acquisition_operation_ref=challenge_owner(
                        "evidence_acquisition_operation", "fixture_acquisition"
                    ),
                    infrastructure_failure_ref=challenge_owner(
                        "infrastructure_failure", "fixture_acquisition_failure"
                    ),
                ),
            ),
            actor_authority_ref=challenge_owner(
                "censoring_authority", "fixture_censor_owner"
            ),
            population_ref=request.primary_population_ref,
            sampling_plan_ref=request.sampling_plan_ref,
            evidence_campaign_binding=request.evidence_scope.evidence_campaign_binding,
            query_observation_provenance=(),
            accounting_binding=challenge_owner(
                "censoring_accounting", "fixture_censor_accounting"
            ),
            missingness_adjustment_binding=_na(
                "fixture_missingness_adjustment_inapplicable"
            ),
            audit_evidence_refs=(
                challenge_owner("audit_evidence", "fixture_censor_audit"),
            ),
            downstream_use_restrictions=(
                challenge_owner("restriction", "fixture_only"),
            ),
        )
        return CensoringVerdict(
            challenge_key=_KEY,
            request=request,
            verdict_kind=CensoringVerdictKind.CENSORED,
            basis=basis,
            infrastructure_failure_ref=None,
        )


class NominalAccountingAuthority:
    """Final-only accounting owner double: it never schedules a hidden retry."""

    def __init__(self, *, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.calls = 0
        self.requests: list[object] = []

    @staticmethod
    def _reason(request: object, kind: ApplicabilityReasonKind) -> object:
        return next(
            item.reason_ref
            for item in (
                request.request_identity.attempt_accounting_applicability_reasons
                + request.request_identity.result_applicability_reasons
            )
            if item.kind is kind
        )

    def decide_attempt_accounting(self, request: object) -> AttemptAccountingDirective:
        self.calls += 1
        self.requests.append(request)
        if self.unavailable:
            raise RuntimeError("fixture accounting owner unavailable")
        mapped = request.provisional_outcome in {
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.REGISTERED_EXCLUSION,
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.CENSORED_CASE,
        }
        if mapped:
            trigger = request.replacement_trigger_binding
            decision_kind = (
                ReplacementDecisionKind.PERMITTED
                if trigger.is_bound
                else ReplacementDecisionKind.PROHIBITED
            )
            replacement = ReplacementDecision(
                sampling_plan_ref=request.request_identity.sampling_plan_ref,
                policy_binding=ReplacementPolicyBinding(
                    ReplacementPolicyBindingKind.REGISTERED_POLICY,
                    request.replacement_policy.payload.policy_ref,
                ),
                decision=decision_kind,
                trigger_binding=trigger,
                lineage_binding=ApplicabilityBinding.not_applicable(
                    self._reason(
                        request,
                        ApplicabilityReasonKind.REPLACEMENT_LINEAGE_NOT_EXECUTED,
                    )
                ),
                accounting_evidence_ref=challenge_owner(
                    "replacement_accounting", "fixture_attempt_accounted"
                ),
            )
            replacement_binding = ApplicabilityBinding.bound(replacement)
        else:
            replacement_binding = ApplicabilityBinding.not_applicable(
                request.outcome_replacement_inapplicable_reason_ref
            )
        denominator_binding = (
            ApplicabilityBinding.bound(
                request.replacement_policy.payload.denominator_effect_ref
            )
            if request.replacement_trigger_binding.is_bound
            else ApplicabilityBinding.not_applicable(
                request.denominator_effect_inapplicable_reason_ref
            )
        )
        return AttemptAccountingDirective(
            challenge_key=request.challenge_key,
            request=request,
            directive_kind=AttemptAccountingDirectiveKind.FINAL,
            provisional_outcome=request.provisional_outcome,
            provisional_stage=request.provisional_stage,
            final_outcome=request.provisional_outcome,
            final_stage=request.provisional_stage,
            outcome_replacement_binding=replacement_binding,
            successor_authorization_binding=ApplicabilityBinding.not_applicable(
                request.successor_authorization_inapplicable_reason_ref
            ),
            denominator_effect_binding=denominator_binding,
            accounting_authority_failure_ref=None,
        )


@dataclass(slots=True)
class B03Fixture:
    request: GeneratorRequest
    fixture_authority: FixtureGenerationAuthority
    support_authority: NominalSupportAuthority
    censoring_authority: NominalCensoringAuthority
    accounting_authority: NominalAccountingAuthority

    bundle: ResolvedGeneratorAuthoringBundle
    prospective_exclusion_ref: object


def make_b03_fixture(
    *,
    support_mode: str = "within",
    censoring_mode: str = "not_censored",
    accounting_unavailable: bool = False,
) -> B03Fixture:
    """Build one admitted request around the full transient eight-point graph."""

    failure_catalog = _failure_catalog()
    prospective_exclusion_ref = challenge_owner(
        "prospective_exclusion_contract", "fixture_registered_exclusion"
    )
    physical = _physical()
    candidate = _candidate(physical)
    exclusion = ExclusionContract(
        exclusion_id="fixture_registered_exclusion",
        membership_rule_ref=challenge_owner(
            "membership_rule", "fixture_registered_exclusion"
        ),
        scientific_authority_ref=challenge_owner(
            "scientific_authority", "fixture_exclusion_contract"
        ),
        applicable_claim_ref=physical.claim_scope_ref,
        audit_semantics_ref=challenge_owner(
            "audit_semantics", "fixture_exclusion_audit"
        ),
    )
    primary = _population(
        PopulationRole.TARGET_WORKLOAD_P,
        physical,
        candidate,
        exclusions=(exclusion,),
    )
    selection = _population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(primary.to_ref()),
    )
    plan = _sampling_plan(
        primary,
        selection,
        failure_catalog,
        prospective_exclusion_ref,
    )
    fixture_registration_ref = challenge_owner(
        "fixture_registration", "b03_burgers_fixture"
    )
    source_provenance_refs = (
        challenge_owner("provenance", "b03_burgers_fixture_source"),
    )
    bundle = _loaded_bundle(
        physical,
        candidate,
        primary,
        selection,
        plan,
        fixture_registration_ref=fixture_registration_ref,
        source_provenance_refs=source_provenance_refs,
    )
    manifest = burgers_fixture_implementation_manifest(_KEY)
    environment = GeneratorEnvironmentDescriptor(
        challenge_key=_KEY,
        environment_id="b03_fixture_environment",
        environment_version="1.0",
        python_implementation="CPython",
        python_version="3.11.16",
        platform_tag="fixture_any",
        dependency_lock_digest=_DIGEST,
        environment_class=GeneratorEnvironmentClass.FIXTURE_ONLY,
    )
    generator = GeneratorDescriptor(
        challenge_key=_KEY,
        generator_id="b03_burgers_fixture_generator",
        generator_version="1.0",
        implementation_digest=manifest.implementation_digest,
        environment_ref=environment.to_ref(),
        fixture_registration_ref=fixture_registration_ref,
        source_provenance_refs=source_provenance_refs,
        fixture_configuration_ref=burgers_fixture_configuration_ref(_KEY),
        supported_physical_system_ref=physical.to_ref(),
        supported_candidate_output_ref=candidate.to_ref(),
        supported_primary_population_ref=primary.to_ref(),
        supported_selection_population_ref=selection.to_ref(),
    )
    pin = SeedPin(
        challenge_key=_KEY,
        generator_version=generator.generator_version,
        generator_digest=generator.implementation_digest,
        scoring_version="1.0",
        scoring_digest=_DIGEST,
        evaluation_binding=EvaluationBinding(bytes(range(32))),
    )
    fixture_authority = FixtureGenerationAuthority(
        provider=DeterministicFixtureProvider(
            FixtureOfficialEntropy(bytes(reversed(range(32))))
        ),
        pin=pin,
        generator=generator,
        generator_ref=generator.to_ref(),
        reservation_issuer_ref=challenge_owner(
            "authority_evidence", "fixture_replay_issuer"
        ),
        fixture_registration_ref=fixture_registration_ref,
        source_provenance_refs=source_provenance_refs,
    )
    replay_ref = fixture_authority.reserve_replay()
    role_binding = GenerationRoleBinding(
        sampling_role=SamplingRole.OFFICIAL_EVALUATION,
        seed_domain=SeedDomain.OFFICIAL_EVAL,
        role_key=RoleKey("generator_sampling"),
        sampling_plan_ref=plan.to_ref(),
    )
    intended_slot_ref = challenge_owner(
        "protected_intended_slot", "fixture_intended_slot"
    )
    intended_unit_ref = challenge_owner(
        "protected_intended_evidence_unit", "fixture_intended_unit"
    )
    attempt_ref = challenge_owner(
        "protected_attempt_commitment", "fixture_attempt_zero"
    )
    link_request = IntendedUnitLinkRequest(
        challenge_key=_KEY,
        sampling_plan_ref=plan.to_ref(),
        selection_population_ref=selection.to_ref(),
        role_binding=role_binding,
        replay_ref=replay_ref,
        intended_slot_ref=intended_slot_ref,
        intended_evidence_unit_ref=intended_unit_ref,
        attempt_ref=attempt_ref,
    )
    link_decision = IntendedUnitLinkDecision(
        challenge_key=_KEY,
        request=link_request,
        link_evidence_ref=challenge_owner(
            "authority_evidence", "fixture_intended_unit_link"
        ),
    )
    accounting_reasons, result_reasons, conformance = _reason_catalogs(failure_catalog)
    evidence_scope = EvidenceScopeBinding(
        evidence_campaign_binding=plan.evidence_campaign_binding,
        query_population_binding=plan.query_population_binding,
        observation_population_binding=plan.observation_population_binding,
        intended_estimand_or_reporting_ref=plan.intended_estimand_or_reporting_ref,
        measurement_applicability_binding=_na("fixture_no_measurement"),
    )
    request = GeneratorRequest(
        challenge_key=_KEY,
        authoring_bundle=bundle,
        generator=generator,
        generator_ref=generator.to_ref(),
        environment=environment,
        environment_ref=environment.to_ref(),
        fixture_configuration=burgers_fixture_configuration(),
        fixture_configuration_ref=burgers_fixture_configuration_ref(_KEY),
        role_binding=role_binding,
        replay_ref=replay_ref,
        intended_slot_ref=intended_slot_ref,
        intended_evidence_unit_ref=intended_unit_ref,
        intended_unit_link_decision=link_decision,
        intended_unit_link_decision_ref=link_decision.to_ref(),
        attempt_ref=attempt_ref,
        attempt_ordinal=0,
        current_attempt_predecessor_binding=None,
        current_attempt_lineage_binding=None,
        attempt_accounting_fallback=AttemptAccountingFallback(
            authority_failure_ref=challenge_owner(
                "infrastructure_failure", "fixture_accounting_unavailable"
            ),
            denominator_unavailable_reason_ref=challenge_owner(
                "applicability_reason", "fixture_denominator_owner_unavailable"
            ),
        ),
        attempt_accounting_applicability_reasons=accounting_reasons,
        result_applicability_reasons=result_reasons,
        conformance_fallbacks=conformance,
        source_payload_inapplicable_reason_ref=challenge_owner(
            "applicability_reason", "fixture_source_payload_inapplicable"
        ),
        failure_reason_catalog=failure_catalog,
        disposition_construction=DispositionConstructionBinding(
            evidence_scope=evidence_scope,
            policy_authority_ref=challenge_owner(
                "policy_authority", "fixture_disposition_policy"
            ),
            audit_evidence_refs=(
                challenge_owner("audit_evidence", "fixture_disposition_audit"),
            ),
            downstream_use_restrictions=(
                challenge_owner("restriction", "fixture_only"),
            ),
            disclosure_contract=_disclosure(),
            case_inapplicable_reason_ref=challenge_owner(
                "applicability_reason", "fixture_case_inapplicable"
            ),
            attempt_inapplicable_reason_ref=challenge_owner(
                "applicability_reason", "fixture_attempt_inapplicable"
            ),
        ),
        case_construction=CaseConstructionBinding(
            object_id="burgers_generated_case",
            object_version="1.0",
            supersedes=_na("first_generated_case"),
            related_population_bindings=(),
            case_representation_ref=challenge_owner(
                "representation", "burgers_protected_fixture_payload"
            ),
            query_population_binding=plan.query_population_binding,
            observation_population_binding=plan.observation_population_binding,
            evidence_campaign_binding=plan.evidence_campaign_binding,
            intended_slot_binding=ApplicabilityBinding.bound(intended_slot_ref),
            prospective_censoring_policy_binding=ApplicabilityBinding.bound(
                plan.censoring_policy_ref
            ),
            applicability_bindings=(
                challenge_owner("applicability", "fixture_generated_case_applies"),
            ),
            disclosure_class=DisclosureClass.PROTECTED,
            disclosure_contract=_disclosure(),
            case_provenance_refs=(
                *source_provenance_refs,
                challenge_owner("provenance", "fixture_generated_case"),
            ),
        ),
        fixture_loading=FixtureLoadingBinding(
            origin_evidence_ref=challenge_owner(
                "authoring_origin_evidence", "fixture_generated_case_origin"
            ),
            audit_evidence_refs=(
                challenge_owner("audit_evidence", "fixture_generated_case_load"),
            ),
            composition_audit_ref=challenge_owner(
                "origin_composition_audit", "fixture_graph_composition"
            ),
            fixture_unqualified_reason_ref=challenge_owner(
                "applicability_reason", "fixture_not_scientifically_qualified"
            ),
        ),
    )
    fixture = B03Fixture(
        request=request,
        fixture_authority=fixture_authority,
        support_authority=NominalSupportAuthority(
            bundle,
            prospective_exclusion_ref,
            support_mode,
        ),
        censoring_authority=NominalCensoringAuthority(censoring_mode),
        accounting_authority=NominalAccountingAuthority(
            unavailable=accounting_unavailable
        ),
        bundle=bundle,
        prospective_exclusion_ref=prospective_exclusion_ref,
    )
    return fixture


__all__ = [
    "B03Fixture",
    "NominalAccountingAuthority",
    "NominalCensoringAuthority",
    "NominalSupportAuthority",
    "challenge_owner",
    "make_b03_fixture",
]
