"""Cross-contract acceptance matrix for the complete B-02A surface.

These tests deliberately compose the public contracts instead of testing one
constructor at a time.  The small fixture builders are shared with the focused
model tests so this file can concentrate on matrix coverage and hostile
cross-binding substitutions.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import pytest
import test_b02a_contract_models as fixtures

from carbon.authoring.canonical import decode_document
from carbon.authoring.cases import (
    AnalyticCaseSource,
    CanonicalChallengeCase,
    CaseProjectionVerificationEcho,
    CaseSourceBinding,
    CaseSourceKind,
    ExperimentalCaseSource,
    GeneratedCaseSource,
    IndustrialCaseSource,
    ManufacturedSolutionCaseSource,
    ObservedCaseSource,
    PublicCaseFactBinding,
    PublicCaseIdentityProjection,
    _issue_case_projection_authority,
    issue_public_case_projection,
    require_public_case_projection,
)
from carbon.authoring.evidence import (
    CaseEvidenceBinding,
    CensoringRecord,
    CensoringTrigger,
    CensoringTriggerKind,
    EvidenceRoleBinding,
    EvidenceScopeBinding,
    InfrastructureCensoringTrigger,
    ReplacementDecision,
    ReplacementDecisionKind,
    ReplacementPolicyBinding,
    ReplacementPolicyBindingKind,
    reject_evidence_role_relabel,
    validate_case_evidence_binding,
    validate_censoring_against_plan,
)
from carbon.authoring.model import (
    AllowedConsumer,
    AllowedConsumerKind,
    ApplicabilityBinding,
    CasePopulationUse,
    CensoringReason,
    DisclosureClass,
    EvidenceRole,
    PopulationRole,
    PrecisionLiteral,
    PublicCaseFactKind,
    SamplingRole,
    authored_object_from_record,
    validate_loaded_authoring_graph,
)
from carbon.authoring.physical import (
    BoundaryConditionContract,
    BoundaryRegionClause,
    CandidateInputBinding,
    CandidateInputRelation,
    CandidateInputRelationKind,
    CandidateOutputContract,
    CandidateOutputRelation,
    CandidateOutputRelationKind,
    ConditionInputBinding,
    InitialConditionContract,
    InitialStateClause,
    PhysicalSystemSpec,
    TimeContract,
    TimeHorizonBinding,
    TimeMode,
    validate_candidate_against_physical,
)
from carbon.authoring.populations import (
    FiniteEnumeration,
    InstanceDistributionContract,
    LawKind,
    LawSemantics,
)
from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.sampling import SamplingPlan
from carbon.authoring.training_support import TrainingSupportContract

_COMMON_FIELDS = (
    "object_kind",
    "schema_version",
    "canonicalization_profile",
    "challenge_key",
    "object_id",
    "object_version",
    "supersedes",
)

_TOP_LEVEL_FIELDS = {
    PhysicalSystemSpec: _COMMON_FIELDS
    + (
        "governing_job_ref",
        "governing_law_refs",
        "assumptions",
        "causal_inputs",
        "required_physical_quantities",
        "geometry_domain_ref",
        "boundary_conditions",
        "initial_conditions",
        "time_contract",
        "operating_envelope_ref",
        "claim_scope_ref",
        "missing_input_policy",
    ),
    CandidateOutputContract: _COMMON_FIELDS
    + (
        "physical_system_ref",
        "candidate_inputs",
        "causal_input_bindings",
        "required_outputs",
        "physical_output_bindings",
        "candidate_representation_ref",
        "geometry_domain_ref",
        "boundary_input_bindings",
        "initial_input_bindings",
        "time_horizon_binding",
        "operating_envelope_ref",
        "claim_scope_ref",
        "missing_or_extra_policy",
        "malformed_output_policy",
    ),
    InstanceDistributionContract: _COMMON_FIELDS
    + (
        "physical_system_ref",
        "candidate_output_ref",
        "population_role",
        "owning_claim_scope_ref",
        "target_population_binding",
        "proposal_population_binding",
        "support_contract",
        "law_semantics",
        "weighting_semantics",
        "stratification_binding",
        "applicability_refs",
        "exclusions",
        "rights_profile_ref",
        "permitted_use_refs",
        "restrictions",
        "disclosure_contract",
        "allowed_consumers",
        "population_provenance",
    ),
    SamplingPlan: _COMMON_FIELDS
    + (
        "sampling_role",
        "primary_population_ref",
        "selection_population_ref",
        "target_population_binding",
        "official_proposal_binding",
        "evidence_weight_binding",
        "query_population_binding",
        "observation_population_binding",
        "evidence_campaign_binding",
        "intended_estimand_or_reporting_ref",
        "finite_evidence_design",
        "full_design_law_ref",
        "stratified_allocation_binding",
        "query_observation_allocation_binding",
        "reference_fidelity_allocation_binding",
        "replication_dependence_policy_ref",
        "uncertainty_resolution_objectives_binding",
        "tail_resolution_objectives_binding",
        "minimum_subgroup_objectives_binding",
        "draw_order_semantics_ref",
        "stopping_extension_policy",
        "replacement_policy",
        "duplicate_policy",
        "inclusion_policy_ref",
        "exclusion_policy_ref",
        "censoring_policy_ref",
        "public_authored_facts",
        "protected_realization_fields",
        "statistical_qualification_requirements_ref",
        "plan_provenance_refs",
        "insufficient_or_failure_policy",
    ),
    TrainingSupportContract: _COMMON_FIELDS
    + (
        "physical_system_ref",
        "candidate_output_ref",
        "membership_contract",
        "physical_invariant_refs",
        "representation_invariant_refs",
        "permitted_source_materials",
        "permitted_generators",
        "rights_profile_ref",
        "permitted_use_refs",
        "restrictions",
        "provenance_requirements",
        "disclosure_contract",
        "unknown_or_invalid_policy",
    ),
    CanonicalChallengeCase: _COMMON_FIELDS
    + (
        "physical_system_ref",
        "candidate_output_ref",
        "primary_population_ref",
        "related_population_bindings",
        "sampling_plan_binding",
        "case_source",
        "case_representation_ref",
        "physical_payload_ref",
        "query_population_binding",
        "observation_population_binding",
        "evidence_campaign_binding",
        "intended_slot_binding",
        "prospective_censoring_policy_binding",
        "applicability_bindings",
        "disclosure_class",
        "disclosure_contract",
        "case_provenance_refs",
    ),
}


def _analytic_case(
    physical: PhysicalSystemSpec,
    candidate: CandidateOutputContract,
    population: InstanceDistributionContract,
    *,
    plan: SamplingPlan | None = None,
    object_id: str = "matrix_case",
    source: CaseSourceBinding | None = None,
    campaign: ApplicabilityBinding[object] | None = None,
    query: ApplicabilityBinding[object] | None = None,
    observation: ApplicabilityBinding[object] | None = None,
) -> CanonicalChallengeCase:
    plan_binding = (
        ApplicabilityBinding.bound(plan.to_ref())
        if plan is not None
        else fixtures._na("matrix_case_no_plan")
    )
    query_binding = (
        query
        if query is not None
        else (
            plan.query_population_binding
            if plan is not None
            else fixtures._na(f"{object_id}_no_query")
        )
    )
    observation_binding = (
        observation
        if observation is not None
        else (
            plan.observation_population_binding
            if plan is not None
            else fixtures._na(f"{object_id}_no_observation")
        )
    )
    campaign_binding = (
        campaign
        if campaign is not None
        else (
            plan.evidence_campaign_binding
            if plan is not None
            else fixtures._na(f"{object_id}_no_campaign")
        )
    )
    return CanonicalChallengeCase(
        object_kind="canonical_challenge_case",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=physical.challenge_key,
        object_id=object_id,
        object_version="1.0",
        supersedes=fixtures._na(f"first_{object_id}"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        primary_population_ref=population.to_ref(),
        related_population_bindings=(),
        sampling_plan_binding=plan_binding,
        case_source=source
        or CaseSourceBinding(
            CaseSourceKind.ANALYTIC,
            AnalyticCaseSource(fixtures._owner("analytic_construction", object_id)),
        ),
        case_representation_ref=fixtures._owner(
            "representation", f"{object_id}_representation"
        ),
        physical_payload_ref=fixtures._owner(
            "protected_case_payload", f"{object_id}_payload"
        ),
        query_population_binding=query_binding,
        observation_population_binding=observation_binding,
        evidence_campaign_binding=campaign_binding,
        intended_slot_binding=(
            ApplicabilityBinding.bound(
                fixtures._owner("protected_intended_slot", f"{object_id}_slot")
            )
            if plan is not None
            else fixtures._na(f"{object_id}_no_slot")
        ),
        prospective_censoring_policy_binding=(
            ApplicabilityBinding.bound(plan.censoring_policy_ref)
            if plan is not None
            else fixtures._na(f"{object_id}_no_censoring")
        ),
        applicability_bindings=(
            fixtures._owner("applicability", f"{object_id}_applicability"),
        ),
        disclosure_class=DisclosureClass.PROTECTED,
        disclosure_contract=fixtures._disclosure(),
        case_provenance_refs=(
            fixtures._owner("provenance", f"{object_id}_provenance"),
        ),
    )


def _complete_objects() -> tuple[object, ...]:
    physical = fixtures._physical()
    candidate = fixtures._candidate(physical)
    target = fixtures._population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    proposal = fixtures._population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
    )
    estimand = fixtures._owner("intended_estimand_or_reporting", "matrix_estimand")
    weight = fixtures._population(
        PopulationRole.EVIDENCE_WEIGHT_W,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
        proposal_binding=ApplicabilityBinding.bound(proposal.to_ref()),
        estimand_ref=fixtures._owner("estimand_scope", "matrix_estimand"),
    )
    plan = fixtures._fixed_sampling_plan(
        target,
        proposal,
        w=weight,
        estimand_ref=estimand,
    )
    support = fixtures._training_support(physical, candidate)
    case = _analytic_case(physical, candidate, target, plan=plan)
    graph = {
        value.to_ref(): value
        for value in (
            physical,
            candidate,
            target,
            proposal,
            weight,
            plan,
            support,
            case,
        )
    }
    validate_loaded_authoring_graph(graph)
    return physical, candidate, target, plan, support, case


def _executable_population(
    role: PopulationRole,
    physical: PhysicalSystemSpec,
    candidate: CandidateOutputContract,
    *,
    target: InstanceDistributionContract | None,
    sampling_role: SamplingRole,
) -> InstanceDistributionContract:
    if role is PopulationRole.OFFICIAL_PROPOSAL_Q:
        value = fixtures._population(
            role,
            physical,
            candidate,
            target_binding=ApplicabilityBinding.bound(target.to_ref()),
        )
    else:
        value = fixtures._population(
            role,
            physical,
            candidate,
            target_binding=(
                ApplicabilityBinding.bound(target.to_ref())
                if target is not None and role is not PopulationRole.TARGET_WORKLOAD_P
                else None
            ),
        )
    return replace(
        value,
        law_semantics=LawSemantics(
            LawKind.FINITE_ENUMERATION,
            FiniteEnumeration(
                fixtures._owner("member_set", f"{role.value.lower()}_members"),
                fixtures._owner(
                    "multiplicity_semantics", f"{role.value.lower()}_multiplicity"
                ),
            ),
        ),
        allowed_consumers=(
            AllowedConsumer(AllowedConsumerKind.SAMPLING_PLAN, sampling_role),
        ),
    )


def _sampling_role_graph(
    role: SamplingRole,
) -> tuple[dict[object, object], SamplingPlan]:
    physical = fixtures._physical()
    candidate = fixtures._candidate(physical)
    target = _executable_population(
        PopulationRole.TARGET_WORKLOAD_P,
        physical,
        candidate,
        target=None,
        sampling_role=role,
    )
    primary_role = {
        SamplingRole.OFFICIAL_EVALUATION: PopulationRole.TARGET_WORKLOAD_P,
        SamplingRole.STRESS: PopulationRole.STRESS,
        SamplingRole.PRACTICE: PopulationRole.PRACTICE,
        SamplingRole.PRODUCT_QUALIFICATION: PopulationRole.PRODUCT_QUALIFICATION,
        SamplingRole.VERIFICATION: PopulationRole.EVIDENCE_CAMPAIGN,
        SamplingRole.EVIDENCE_CAMPAIGN: PopulationRole.EVIDENCE_CAMPAIGN,
    }[role]
    if role is SamplingRole.OFFICIAL_EVALUATION:
        primary = target
        selection = _executable_population(
            PopulationRole.OFFICIAL_PROPOSAL_Q,
            physical,
            candidate,
            target=target,
            sampling_role=role,
        )
    else:
        primary = _executable_population(
            primary_role,
            physical,
            candidate,
            target=None if role is SamplingRole.VERIFICATION else target,
            sampling_role=role,
        )
        selection = primary
    base_q = _executable_population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target=target,
        sampling_role=SamplingRole.OFFICIAL_EVALUATION,
    )
    plan = fixtures._fixed_sampling_plan(
        target,
        base_q,
        w=None,
        estimand_ref=fixtures._owner(
            "intended_estimand_or_reporting", f"{role.value.lower()}_reporting"
        ),
    )
    campaign_required = role in {
        SamplingRole.PRODUCT_QUALIFICATION,
        SamplingRole.VERIFICATION,
        SamplingRole.EVIDENCE_CAMPAIGN,
    }
    plan = replace(
        plan,
        object_id=f"plan_{role.value.lower()}",
        sampling_role=role,
        primary_population_ref=primary.to_ref(),
        selection_population_ref=selection.to_ref(),
        target_population_binding=(
            fixtures._na(f"{role.value.lower()}_no_target")
            if role is SamplingRole.VERIFICATION
            else ApplicabilityBinding.bound(target.to_ref())
        ),
        official_proposal_binding=(
            ApplicabilityBinding.bound(selection.to_ref())
            if role is SamplingRole.OFFICIAL_EVALUATION
            else fixtures._na(f"{role.value.lower()}_not_official_q")
        ),
        evidence_campaign_binding=(
            ApplicabilityBinding.bound(
                fixtures._owner("evidence_campaign", f"{role.value.lower()}_campaign")
            )
            if campaign_required
            else fixtures._na(f"{role.value.lower()}_no_campaign")
        ),
    )
    values = {physical.to_ref(): physical, candidate.to_ref(): candidate}
    for population in (target, primary, selection):
        values[population.to_ref()] = population
    values[plan.to_ref()] = plan
    return values, plan


def _replacement_decision(plan: SamplingPlan) -> ReplacementDecision:
    return ReplacementDecision(
        sampling_plan_ref=plan.to_ref(),
        policy_binding=ReplacementPolicyBinding(
            ReplacementPolicyBindingKind.PLAN_NEVER,
            None,
        ),
        decision=ReplacementDecisionKind.PROHIBITED,
        trigger_binding=fixtures._na("matrix_replacement_forbidden"),
        lineage_binding=fixtures._na("matrix_no_replacement_lineage"),
        accounting_evidence_ref=fixtures._owner(
            "replacement_accounting", "matrix_no_replacement"
        ),
    )


def test_all_six_top_level_schemas_round_trip_and_pin_exact_identity() -> None:
    values = _complete_objects()
    assert {type(value) for value in values} == set(_TOP_LEVEL_FIELDS)

    for value in values:
        expected_fields = _TOP_LEVEL_FIELDS[type(value)]
        assert tuple(field.name for field in fields(value)) == expected_fields
        document = decode_document(value.canonical_bytes())
        assert document.object_kind == value.object_kind
        assert {name for name, _ in document.record.fields} == set(expected_fields)
        assert len(document.record.fields) == len(expected_fields)
        reconstructed = authored_object_from_record(
            object_kind=document.object_kind,
            record=document.record,
        )
        assert type(reconstructed) is type(value)
        assert reconstructed == value
        assert reconstructed.to_ref() == value.to_ref()
        assert reconstructed.canonical_bytes() == value.canonical_bytes()


def test_all_six_top_level_objects_are_immutable_and_supersede_prospectively() -> None:
    for value in _complete_objects():
        with pytest.raises(FrozenInstanceError):
            value.object_version = "9.9"
        successor = replace(
            value,
            object_version="1.1",
            supersedes=ApplicabilityBinding.bound(value.to_ref()),
        )
        assert successor != value
        assert successor.to_ref() != value.to_ref()
        assert successor.canonical_bytes() != value.canonical_bytes()
        assert value.object_version == "1.0"
        assert not value.supersedes.is_bound


@pytest.mark.parametrize("role", tuple(PopulationRole))
def test_population_role_matrix_has_exact_nominal_ref_and_no_alias(
    role: PopulationRole,
) -> None:
    physical = fixtures._physical()
    candidate = fixtures._candidate(physical)
    target = fixtures._population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    proposal = fixtures._population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
    )
    if role is PopulationRole.TARGET_WORKLOAD_P:
        value = target
    elif role is PopulationRole.OFFICIAL_PROPOSAL_Q:
        value = proposal
    elif role is PopulationRole.EVIDENCE_WEIGHT_W:
        value = fixtures._population(
            role,
            physical,
            candidate,
            target_binding=ApplicabilityBinding.bound(target.to_ref()),
            proposal_binding=ApplicabilityBinding.bound(proposal.to_ref()),
        )
    else:
        value = fixtures._population(
            role,
            physical,
            candidate,
            target_binding=ApplicabilityBinding.bound(target.to_ref()),
        )

    assert value.to_ref().expected_population_role == role.value
    assert value.population_role is role
    assert len({value.to_ref(), target.to_ref(), proposal.to_ref()}) >= 2

    if role is not PopulationRole.EVIDENCE_WEIGHT_W:
        with pytest.raises(ValueError):
            replace(
                value,
                proposal_population_binding=ApplicabilityBinding.bound(
                    proposal.to_ref()
                ),
            )


@pytest.mark.parametrize("role", tuple(SamplingRole))
def test_sampling_role_matrix_resolves_exact_primary_selection_and_campaign(
    role: SamplingRole,
) -> None:
    graph, plan = _sampling_role_graph(role)
    validate_loaded_authoring_graph(graph)
    assert plan.sampling_role is role
    assert plan.evidence_campaign_binding.is_bound is (
        role
        in {
            SamplingRole.PRODUCT_QUALIFICATION,
            SamplingRole.VERIFICATION,
            SamplingRole.EVIDENCE_CAMPAIGN,
        }
    )
    assert plan.official_proposal_binding.is_bound is (
        role is SamplingRole.OFFICIAL_EVALUATION
    )
    assert plan.target_population_binding.is_bound is (
        role is not SamplingRole.VERIFICATION
    )


def _conditioned_pair(
    *, transient: bool
) -> tuple[PhysicalSystemSpec, CandidateOutputContract]:
    base = fixtures._physical()
    forcing = fixtures._value("forcing")
    boundary = fixtures._value("boundary_value")
    initial = fixtures._value("initial_value")
    time_value = fixtures._value("time_coordinate")
    physical = replace(
        base,
        causal_inputs=(forcing, boundary, initial),
        boundary_conditions=BoundaryConditionContract(
            (
                BoundaryRegionClause(
                    region_clause_id="boundary_clause",
                    geometry_region_ref=fixtures._owner(
                        "geometry_region", "matrix_boundary_region"
                    ),
                    condition_semantic_ref=fixtures._owner(
                        "semantic_clause", "matrix_boundary_semantic"
                    ),
                    causal_input_binding=ApplicabilityBinding.bound("boundary_value"),
                    unit_ref=boundary.unit_ref,
                    applicability=ApplicabilityBinding.bound(
                        fixtures._owner("applicability", "matrix_boundary_applies")
                    ),
                ),
            )
        ),
        initial_conditions=InitialConditionContract(
            (
                InitialStateClause(
                    state_clause_id="initial_clause",
                    state_semantic_ref=fixtures._owner(
                        "semantic_clause", "matrix_initial_semantic"
                    ),
                    causal_input_binding=ApplicabilityBinding.bound("initial_value"),
                    geometry_domain_ref=base.geometry_domain_ref,
                    time_origin_ref=fixtures._owner(
                        "semantic_clause", "matrix_time_origin"
                    ),
                    applicability=ApplicabilityBinding.bound(
                        fixtures._owner("applicability", "matrix_initial_applies")
                    ),
                ),
            )
        ),
        time_contract=(
            TimeContract(
                TimeMode.TRANSIENT,
                ApplicabilityBinding.bound(time_value),
                ApplicabilityBinding.bound(
                    fixtures._owner("semantic_clause", "matrix_horizon")
                ),
                fixtures._owner("semantic_clause", "matrix_endpoint"),
                time_value.unit_ref,
            )
            if transient
            else base.time_contract
        ),
    )
    candidate_inputs = (
        replace(forcing, field_id="candidate_forcing"),
        replace(boundary, field_id="candidate_boundary_causal"),
        replace(initial, field_id="candidate_initial_causal"),
        replace(boundary, field_id="candidate_boundary_condition"),
        replace(initial, field_id="candidate_initial_condition"),
    )
    time_ids: tuple[str, ...] = ()
    if transient:
        candidate_inputs += (replace(time_value, field_id="candidate_time"),)
        time_ids = ("candidate_time",)
    candidate = replace(
        fixtures._candidate(physical),
        candidate_inputs=candidate_inputs,
        causal_input_bindings=(
            CandidateInputBinding(
                "forcing",
                "candidate_forcing",
                CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
            CandidateInputBinding(
                "boundary_value",
                "candidate_boundary_causal",
                CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
            CandidateInputBinding(
                "initial_value",
                "candidate_initial_causal",
                CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
        ),
        boundary_input_bindings=(
            ConditionInputBinding(
                "boundary_clause",
                "candidate_boundary_condition",
                CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
        ),
        initial_input_bindings=(
            ConditionInputBinding(
                "initial_clause",
                "candidate_initial_condition",
                CandidateInputRelation(CandidateInputRelationKind.IDENTITY),
            ),
        ),
        time_horizon_binding=TimeHorizonBinding(
            time_ids,
            fixtures._owner("semantic_equivalence", "matrix_time_equivalence"),
            fixtures._owner("semantic_equivalence", "matrix_horizon_equivalence"),
            fixtures._owner("semantic_equivalence", "matrix_endpoint_equivalence"),
        ),
    )
    validate_candidate_against_physical(candidate, physical)
    return physical, candidate


@pytest.mark.parametrize(
    ("seam", "expected"),
    (
        ("causal_semantic", "causal input semantic_role_ref"),
        ("boundary_unit", "boundary input unit_ref"),
        ("initial_geometry", "initial input geometry_binding"),
        ("output_precision", "required output precision_contract"),
    ),
)
def test_physical_candidate_causal_matrix_rejects_semantic_substitution(
    seam: str,
    expected: str,
) -> None:
    physical, candidate = _conditioned_pair(transient=False)
    if seam == "causal_semantic":
        candidate = replace(
            candidate,
            candidate_inputs=(
                replace(
                    candidate.candidate_inputs[0],
                    semantic_role_ref=fixtures._owner(
                        "semantic_clause", "substituted_forcing"
                    ),
                ),
                *candidate.candidate_inputs[1:],
            ),
        )
    elif seam == "boundary_unit":
        candidate = replace(
            candidate,
            candidate_inputs=(
                *candidate.candidate_inputs[:3],
                replace(
                    candidate.candidate_inputs[3],
                    unit_ref=fixtures._owner("unit", "substituted_boundary_unit"),
                ),
                *candidate.candidate_inputs[4:],
            ),
        )
    elif seam == "initial_geometry":
        candidate = replace(
            candidate,
            candidate_inputs=(
                *candidate.candidate_inputs[:4],
                replace(
                    candidate.candidate_inputs[4],
                    geometry_binding=ApplicabilityBinding.bound(
                        fixtures._owner(
                            "geometry_domain", "substituted_initial_geometry"
                        )
                    ),
                ),
                *candidate.candidate_inputs[5:],
            ),
        )
    else:
        candidate = replace(
            candidate,
            required_outputs=(
                replace(
                    candidate.required_outputs[0],
                    precision_contract=(PrecisionLiteral.FLOAT32,),
                ),
            ),
            physical_output_bindings=(
                replace(
                    candidate.physical_output_bindings[0],
                    relation=CandidateOutputRelation(
                        CandidateOutputRelationKind.REPRESENTATION_ADAPTER,
                        fixtures._owner(
                            "representation_adapter", "matrix_output_adapter"
                        ),
                    ),
                ),
            ),
        )
    with pytest.raises(ValueError, match=expected):
        validate_candidate_against_physical(candidate, physical)


def test_transient_and_steady_time_bindings_fail_closed_on_substitution() -> None:
    transient_physical, transient_candidate = _conditioned_pair(transient=True)
    wrong_unit = replace(
        transient_candidate,
        candidate_inputs=(
            *transient_candidate.candidate_inputs[:-1],
            replace(
                transient_candidate.candidate_inputs[-1],
                unit_ref=fixtures._owner("unit", "substituted_time_unit"),
            ),
        ),
    )
    with pytest.raises(ValueError, match="physical time coordinate"):
        validate_candidate_against_physical(wrong_unit, transient_physical)

    steady_physical, steady_candidate = _conditioned_pair(transient=False)
    with pytest.raises(
        ValueError, match="candidate inputs must be targeted exactly once"
    ):
        replace(
            steady_candidate,
            candidate_inputs=(
                *steady_candidate.candidate_inputs,
                fixtures._value("undeclared_steady_time"),
            ),
        )
    validate_candidate_against_physical(steady_candidate, steady_physical)


def _query_observation_graph() -> tuple[
    dict[object, object],
    SamplingPlan,
    CanonicalChallengeCase,
    InstanceDistributionContract,
]:
    physical = fixtures._physical()
    candidate = fixtures._candidate(physical)
    target = fixtures._population(PopulationRole.TARGET_WORKLOAD_P, physical, candidate)
    proposal = fixtures._population(
        PopulationRole.OFFICIAL_PROPOSAL_Q,
        physical,
        candidate,
        target_binding=ApplicabilityBinding.bound(target.to_ref()),
    )
    query = replace(
        fixtures._population(
            PopulationRole.QUERY,
            physical,
            candidate,
            target_binding=ApplicabilityBinding.bound(target.to_ref()),
        ),
        allowed_consumers=(
            AllowedConsumer(
                AllowedConsumerKind.SAMPLING_PLAN,
                SamplingRole.OFFICIAL_EVALUATION,
            ),
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE, CasePopulationUse.QUERY
            ),
        ),
    )
    observation = replace(
        fixtures._population(
            PopulationRole.OBSERVATION,
            physical,
            candidate,
            target_binding=ApplicabilityBinding.bound(target.to_ref()),
        ),
        allowed_consumers=(
            AllowedConsumer(
                AllowedConsumerKind.SAMPLING_PLAN,
                SamplingRole.OFFICIAL_EVALUATION,
            ),
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE,
                CasePopulationUse.OBSERVATION,
            ),
        ),
    )
    campaign = ApplicabilityBinding.bound(
        fixtures._owner("evidence_campaign", "matrix_observation_campaign")
    )
    plan = replace(
        fixtures._fixed_sampling_plan(
            target,
            proposal,
            w=None,
            estimand_ref=fixtures._owner(
                "intended_estimand_or_reporting", "matrix_observation_reporting"
            ),
        ),
        query_population_binding=ApplicabilityBinding.bound(query.to_ref()),
        observation_population_binding=ApplicabilityBinding.bound(observation.to_ref()),
        evidence_campaign_binding=campaign,
        query_observation_allocation_binding=ApplicabilityBinding.bound(
            fixtures._owner(
                "query_observation_allocation", "matrix_query_observation_allocation"
            )
        ),
    )
    case = _analytic_case(
        physical,
        candidate,
        target,
        plan=plan,
        object_id="matrix_observation_case",
        campaign=campaign,
        query=ApplicabilityBinding.bound(query.to_ref()),
        observation=ApplicabilityBinding.bound(observation.to_ref()),
    )
    graph = {
        value.to_ref(): value
        for value in (
            physical,
            candidate,
            target,
            proposal,
            query,
            observation,
            plan,
            case,
        )
    }
    return graph, plan, case, observation


def test_query_observation_campaign_bindings_are_exact_across_plan_and_case() -> None:
    graph, plan, case, _ = _query_observation_graph()
    validate_loaded_authoring_graph(graph)
    assert case.query_population_binding == plan.query_population_binding
    assert case.observation_population_binding == plan.observation_population_binding
    assert case.evidence_campaign_binding == plan.evidence_campaign_binding

    physical = graph[case.physical_system_ref]
    candidate = graph[case.candidate_output_ref]
    target = graph[case.primary_population_ref]
    other_query = replace(
        graph[case.query_population_binding.value],
        object_id="other_query_population",
    )
    mismatched = replace(
        case,
        query_population_binding=ApplicabilityBinding.bound(other_query.to_ref()),
    )
    hostile = dict(graph)
    hostile[other_query.to_ref()] = other_query
    hostile.pop(case.to_ref())
    hostile[mismatched.to_ref()] = mismatched
    assert physical is not None and candidate is not None and target is not None
    with pytest.raises(ValueError, match="query binding mismatch"):
        validate_loaded_authoring_graph(hostile)


_CASE_SOURCE_FACTORIES = (
    (
        CaseSourceKind.GENERATED,
        lambda: GeneratedCaseSource(
            fixtures._owner("generation_event", "matrix_generation"),
            fixtures._owner("generator", "matrix_generator"),
        ),
    ),
    (
        CaseSourceKind.OBSERVED,
        lambda: ObservedCaseSource(
            fixtures._owner("observation_source", "matrix_observation")
        ),
    ),
    (
        CaseSourceKind.EXPERIMENTAL,
        lambda: ExperimentalCaseSource(
            fixtures._owner("experiment_source", "matrix_experiment")
        ),
    ),
    (
        CaseSourceKind.INDUSTRIAL,
        lambda: IndustrialCaseSource(
            fixtures._owner("industrial_source", "matrix_industrial")
        ),
    ),
    (
        CaseSourceKind.ANALYTIC,
        lambda: AnalyticCaseSource(
            fixtures._owner("analytic_construction", "matrix_analytic")
        ),
    ),
    (
        CaseSourceKind.MANUFACTURED_SOLUTION,
        lambda: ManufacturedSolutionCaseSource(
            fixtures._owner("evidence_campaign", "matrix_mms_campaign"),
            fixtures._owner("verification_construction", "matrix_mms_construction"),
        ),
    ),
)


@pytest.mark.parametrize(("kind", "source_factory"), _CASE_SOURCE_FACTORIES)
def test_all_six_case_sources_round_trip_without_role_transfer(
    kind: CaseSourceKind,
    source_factory: object,
) -> None:
    physical = fixtures._physical()
    candidate = fixtures._candidate(physical)
    campaign = fixtures._na(f"{kind.value.lower()}_no_campaign")
    population_role = PopulationRole.TARGET_WORKLOAD_P
    if kind is CaseSourceKind.MANUFACTURED_SOLUTION:
        population_role = PopulationRole.EVIDENCE_CAMPAIGN
        campaign = ApplicabilityBinding.bound(
            fixtures._owner("evidence_campaign", "matrix_mms_campaign")
        )
    population = fixtures._population(population_role, physical, candidate)
    source = source_factory()
    case = _analytic_case(
        physical,
        candidate,
        population,
        object_id=f"case_{kind.value.lower()}",
        source=CaseSourceBinding(kind, source),
        campaign=campaign,
    )
    validate_loaded_authoring_graph(
        {value.to_ref(): value for value in (physical, candidate, population, case)}
    )
    decoded = decode_document(case.canonical_bytes())
    reconstructed = authored_object_from_record(
        object_kind=decoded.object_kind,
        record=decoded.record,
    )
    assert reconstructed == case
    assert reconstructed.case_source.kind is kind


@pytest.mark.parametrize("reason", tuple(CensoringReason))
def test_all_censoring_reason_families_require_exact_typed_trigger(
    reason: CensoringReason,
) -> None:
    graph, plan, _, observation = _query_observation_graph()
    target = graph[plan.primary_population_ref]
    campaign = plan.evidence_campaign_binding
    measurement = fixtures._na("matrix_no_measurement")
    population_ref = target.to_ref()
    provenance: tuple[object, ...] = (
        fixtures._owner("query_observation_provenance", "matrix_acquisition"),
    )
    if reason in {
        CensoringReason.OBSERVATION_MISSING,
        CensoringReason.OBSERVATION_TIMEOUT,
    }:
        population_ref = observation.to_ref()
    if reason in {
        CensoringReason.MEASUREMENT_UNAVAILABLE,
        CensoringReason.MEASUREMENT_RESOURCE_LIMIT,
        CensoringReason.MEASUREMENT_TIMEOUT,
    }:
        measurement = ApplicabilityBinding.bound(
            fixtures._owner("measurement_applicability", "matrix_measurement")
        )
    trigger_kind, payload_kind = {
        CensoringReason.REFERENCE_UNAVAILABLE: (
            CensoringTriggerKind.REFERENCE,
            "reference_unavailable",
        ),
        CensoringReason.REFERENCE_DISPUTED: (
            CensoringTriggerKind.REFERENCE,
            "reference_disputed",
        ),
        CensoringReason.REFERENCE_NUMERICAL_FAILURE: (
            CensoringTriggerKind.REFERENCE,
            "reference_numerical_failure",
        ),
        CensoringReason.REFERENCE_RESOURCE_LIMIT: (
            CensoringTriggerKind.REFERENCE,
            "reference_resource_limit",
        ),
        CensoringReason.REFERENCE_TIMEOUT: (
            CensoringTriggerKind.REFERENCE,
            "reference_timeout",
        ),
        CensoringReason.OBSERVATION_MISSING: (
            CensoringTriggerKind.OBSERVATION,
            "observation_missing",
        ),
        CensoringReason.OBSERVATION_TIMEOUT: (
            CensoringTriggerKind.OBSERVATION,
            "observation_timeout",
        ),
        CensoringReason.MEASUREMENT_UNAVAILABLE: (
            CensoringTriggerKind.MEASUREMENT,
            "measurement_unavailable",
        ),
        CensoringReason.MEASUREMENT_RESOURCE_LIMIT: (
            CensoringTriggerKind.MEASUREMENT,
            "measurement_resource_limit",
        ),
        CensoringReason.MEASUREMENT_TIMEOUT: (
            CensoringTriggerKind.MEASUREMENT,
            "measurement_timeout",
        ),
        CensoringReason.EXPERIMENT_CORRUPTED: (
            CensoringTriggerKind.EXPERIMENT,
            "experiment_corrupted",
        ),
        CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER: (
            CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE,
            None,
        ),
    }[reason]
    payload = (
        InfrastructureCensoringTrigger(
            fixtures._owner(
                "evidence_acquisition_operation", "matrix_acquisition_operation"
            ),
            fixtures._owner("infrastructure_failure", "matrix_infrastructure"),
        )
        if payload_kind is None
        else fixtures._owner(payload_kind, f"matrix_{reason.value.lower()}")
    )
    scope = EvidenceScopeBinding(
        evidence_campaign_binding=campaign,
        query_population_binding=plan.query_population_binding,
        observation_population_binding=plan.observation_population_binding,
        intended_estimand_or_reporting_ref=plan.intended_estimand_or_reporting_ref,
        measurement_applicability_binding=measurement,
    )
    record = CensoringRecord(
        schema_version="1.0",
        canonicalization_profile=("carbon_scientific_authoring_derived_evidence_v1"),
        intended_evidence_unit_ref=fixtures._owner(
            "protected_intended_evidence_unit", f"matrix_{reason.value.lower()}_unit"
        ),
        evidence_scope=scope,
        censoring_reason=reason,
        trigger_failure_binding=CensoringTrigger(trigger_kind, payload),
        actor_authority_ref=fixtures._owner(
            "censoring_authority", "matrix_censoring_authority"
        ),
        population_ref=population_ref,
        sampling_plan_ref=plan.to_ref(),
        evidence_campaign_binding=campaign,
        query_observation_provenance=provenance,
        replacement_decision=_replacement_decision(plan),
        accounting_binding=fixtures._owner(
            "censoring_accounting", "matrix_censoring_accounting"
        ),
        missingness_adjustment_binding=fixtures._na("matrix_no_adjustment"),
        audit_evidence_refs=(
            fixtures._owner("audit_evidence", "matrix_censoring_audit"),
        ),
        downstream_use_restrictions=(
            fixtures._owner("restriction", "matrix_censoring_restriction"),
        ),
    )
    validate_censoring_against_plan(record, plan)
    assert record.trigger_failure_binding.kind is trigger_kind

    different_reason = next(item for item in CensoringReason if item is not reason)
    with pytest.raises(ValueError, match="reason/trigger|reason/trigger subtype"):
        replace(record, censoring_reason=different_reason)


@pytest.mark.parametrize("role", tuple(EvidenceRole))
def test_evidence_roles_are_exact_and_cannot_be_relabelled(
    role: EvidenceRole,
) -> None:
    physical = fixtures._physical()
    candidate = fixtures._candidate(physical)
    campaign_ref = fixtures._owner("evidence_campaign", "matrix_evidence_campaign")
    population = replace(
        fixtures._population(
            PopulationRole.EVIDENCE_CAMPAIGN,
            physical,
            candidate,
        ),
        allowed_consumers=(
            AllowedConsumer(
                AllowedConsumerKind.CANONICAL_CASE, CasePopulationUse.PRIMARY
            ),
            AllowedConsumer(AllowedConsumerKind.CASE_EVIDENCE, role),
        ),
    )
    source = (
        CaseSourceBinding(
            CaseSourceKind.MANUFACTURED_SOLUTION,
            ManufacturedSolutionCaseSource(
                campaign_ref,
                fixtures._owner("verification_construction", "matrix_evidence_mms"),
            ),
        )
        if role is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        else CaseSourceBinding(
            CaseSourceKind.ANALYTIC,
            AnalyticCaseSource(
                fixtures._owner("analytic_construction", "matrix_evidence_case")
            ),
        )
    )
    case = _analytic_case(
        physical,
        candidate,
        population,
        object_id=f"evidence_case_{role.value.lower()}",
        source=source,
        campaign=ApplicabilityBinding.bound(campaign_ref),
    )
    role_binding = EvidenceRoleBinding(
        role,
        (
            fixtures._owner("hybrid_evidence_role", "matrix_hybrid")
            if role is EvidenceRole.REGISTERED_HYBRID
            else None
        ),
    )
    binding = CaseEvidenceBinding(
        authoritative_case_ref=case.to_ref(),
        public_projection_binding=fixtures._na("matrix_no_public_projection"),
        evidence_role=role_binding,
        evidence_campaign_ref=campaign_ref,
        role_population_ref=population.to_ref(),
        evidence_artifact_ref=fixtures._owner(
            "evidence_artifact", f"matrix_{role.value.lower()}_artifact"
        ),
        claim_scope_ref=physical.claim_scope_ref,
        applicability_refs=(
            fixtures._owner("applicability", "matrix_evidence_applicability"),
        ),
        query_observation_provenance=(),
        policy_qualification_binding=fixtures._na("matrix_unqualified_reference"),
        provenance_refs=(fixtures._owner("provenance", "matrix_evidence_source"),),
        disclosure_contract=fixtures._disclosure(),
        downstream_use_restrictions=(
            fixtures._owner("restriction", "matrix_evidence_restriction"),
        ),
    )
    validate_case_evidence_binding(
        binding,
        case=case,
        role_population=population,
        physical_system=physical,
        candidate_output=candidate,
    )
    assert binding.evidence_role == role_binding
    other_role = next(item for item in EvidenceRole if item is not role)
    requested = EvidenceRoleBinding(
        other_role,
        (
            fixtures._owner("hybrid_evidence_role", "matrix_other_hybrid")
            if other_role is EvidenceRole.REGISTERED_HYBRID
            else None
        ),
    )
    with pytest.raises(ValueError, match="cannot be relabeled"):
        reject_evidence_role_relabel(binding, requested)


def test_public_projection_has_closed_allowlist_and_no_protected_identity() -> None:
    _, _, _, _, _, case = _complete_objects()
    issuance = fixtures._owner("projection_issuance", "matrix_public_projection")

    class ExactProjectionRegistry:
        def verify_case_projection(
            self,
            *,
            authority_ref: object,
            case_ref: object,
            projection: object,
        ) -> CaseProjectionVerificationEcho:
            return CaseProjectionVerificationEcho(
                authority_ref=authority_ref,
                case_ref=case_ref,
                projection=projection,
            )

    authority = _issue_case_projection_authority(
        authority_ref=issuance,
        authority=ExactProjectionRegistry(),
    )
    projection = issue_public_case_projection(
        authority,
        case,
        opaque_public_handle=fixtures._owner(
            "opaque_public_case_handle", "matrix_opaque_handle"
        ),
        disclosure_policy_ref=case.disclosure_contract.release_policy_ref,
        issuance_ref=issuance,
        public_fact_bindings=(
            PublicCaseFactBinding(
                PublicCaseFactKind.PRIMARY_POPULATION_ROLE,
                fixtures._owner("public_case_fact", "matrix_public_population_role"),
            ),
        ),
    )
    field_names = {field.name for field in fields(projection)}
    assert field_names == {
        "schema_version",
        "challenge_key",
        "opaque_public_handle",
        "disclosure_policy_ref",
        "issuance_ref",
        "public_fact_bindings",
    }
    assert not field_names & {
        "case_ref",
        "payload_ref",
        "intended_slot_ref",
        "realized_stratum_binding",
        "replacement_linkage",
        "seed",
        "entropy",
    }
    assert case.to_ref().content_digest not in repr(projection)
    assert require_public_case_projection(projection) is projection
    with pytest.raises(TypeError):
        require_public_case_projection(case.to_ref())
    with pytest.raises(PermissionError):
        PublicCaseIdentityProjection(
            _capability=object(),
            schema_version="1.0",
            challenge_key=case.challenge_key,
            opaque_public_handle=projection.opaque_public_handle,
            disclosure_policy_ref=projection.disclosure_policy_ref,
            issuance_ref=projection.issuance_ref,
            public_fact_bindings=projection.public_fact_bindings,
        )
