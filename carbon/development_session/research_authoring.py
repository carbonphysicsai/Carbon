"""Typed public practice discovery contracts over existing C-AUTH1/C-05 owners.

These documents register a DEVELOPMENT research surface. They do not qualify
the numerical reference, measurements, final population or scientific score.
"""

from __future__ import annotations

from pathlib import Path

from carbon import measurement as m
from carbon.authoring import populations as pop
from carbon.authoring import sampling as sample
from carbon.authoring.model import (
    AllowedConsumer,
    AllowedConsumerKind,
    DisclosureContract,
    PopulationRole,
    PublicPlanFactKind,
    SamplingRole,
)
from carbon.authoring.model import (
    ApplicabilityBinding as A,
)
from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.generators import burgers_dynamics
from carbon.measurement_runtime import development as measures
from carbon.reference_runtime import model as references

from .contracts import authored_contracts
from .profile import CHALLENGE, canonical, digest
from .research_profile import document


def clause(kind, label):
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(CHALLENGE),
        object_id=label,
        object_version="1.0",
        content_digest=digest(
            canonical(
                {
                    "clause": label,
                    "profile": document(),
                    "generator_source": digest(
                        Path(burgers_dynamics.__file__).read_bytes()
                    ),
                }
            )
        ),
    )


def na(label):
    return A.not_applicable(clause("applicability_reason", label))


def population_and_sampling():
    physical, candidate, _ = authored_contracts()
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "challenge_key": CHALLENGE,
        "object_version": "1.0",
    }
    population = pop.InstanceDistributionContract(
        **common,
        object_kind="instance_distribution_contract",
        object_id="burgers_autoresearch_practice",
        supersedes=na("first_public_research_population"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        population_role=PopulationRole.PRACTICE,
        owning_claim_scope_ref=clause(
            "claim_scope", "public_adaptive_development_practice"
        ),
        target_population_binding=na("no_official_population_authority"),
        proposal_population_binding=na("no_official_proposal"),
        support_contract=pop.SupportContract(
            clause("membership_rule", "registered_c_auth1_support"),
            clause("physical_support", "twelve_shape_reynolds_cells"),
            clause("representation_support", "periodic_64_points_13_times"),
            clause("support_boundary", "registered_generator_edges"),
            clause("membership_decision", "generator_closed_support_checks"),
            "REJECT",
        ),
        law_semantics=pop.LawSemantics(
            pop.LawKind.PROBABILITY_LAW,
            pop.ProbabilityLaw(
                clause("base_measure", "uniform_cell_and_c_auth1_continuous_draws"),
                clause("probability_law", "c_auth1_role_specific_laws_unchanged"),
                clause(
                    "normalization_claim",
                    "generator_probability_draws_not_industrial_prevalence",
                ),
            ),
        ),
        weighting_semantics=pop.WeightingSemantics(
            pop.WeightingSemanticsKind.NOT_APPLICABLE,
            clause("applicability_reason", "practice_population_is_not_score_weight"),
        ),
        stratification_binding=na("allocation_is_fixed_in_full_design_law"),
        applicability_refs=(clause("applicability", "public_practice_only"),),
        exclusions=(),
        rights_profile_ref=clause("rights_profile", "public_synthetic_cases"),
        permitted_use_refs=(clause("permitted_use", "adaptive_miner_research"),),
        restrictions=(clause("restriction", "not_final_evidence_or_qualification"),),
        disclosure_contract=DisclosureContract(
            ("laws", "public_practice_cases", "public_practice_labels"),
            (),
            (),
            clause("aggregation_policy", "detailed_own_public_practice"),
            clause("release_policy", "public_research_only"),
        ),
        allowed_consumers=(
            AllowedConsumer(AllowedConsumerKind.SAMPLING_PLAN, SamplingRole.PRACTICE),
        ),
        population_provenance=(
            clause("provenance", "c_auth1_generator_and_d4_owner_direction"),
        ),
    )
    plan = sample.SamplingPlan(
        **common,
        object_kind="sampling_plan",
        object_id="burgers_autoresearch_practice_plan",
        supersedes=na("first_public_research_plan"),
        sampling_role=SamplingRole.PRACTICE,
        primary_population_ref=population.to_ref(),
        selection_population_ref=population.to_ref(),
        target_population_binding=na("no_official_target"),
        official_proposal_binding=na("no_official_proposal"),
        evidence_weight_binding=na("no_official_weight"),
        query_population_binding=na("fixed_query_grid"),
        observation_population_binding=na("synthetic_public_reference"),
        evidence_campaign_binding=na("practice_not_confirmation"),
        intended_estimand_or_reporting_ref=clause(
            "intended_estimand_or_reporting", "adaptive_practice_diagnostics"
        ),
        finite_evidence_design=sample.FiniteEvidenceDesign(
            clause("sampling_unit", "physical_parent_case"),
            sample.FiniteDesignMode.FIXED,
            24,
            clause(
                "base_evidence_requirement", "one_parent_per_cell_per_practice_role"
            ),
            na("fixed_design_with_external_campaign_admission"),
            na("no_case_extension"),
            "EVIDENCE_DEFERRED",
            "INDETERMINATE",
            "INSUFFICIENT_EVIDENCE",
            "NEW_VERSION_REQUIRED",
        ),
        full_design_law_ref=clause(
            "full_design_law", "twelve_eval_and_twelve_stress_practice_parents"
        ),
        stratified_allocation_binding=na("fixed_cell_allocation_in_full_design_law"),
        query_observation_allocation_binding=na("fixed_64_by_13_grid"),
        reference_fidelity_allocation_binding=A.bound(
            clause("reference_fidelity_allocation", "fixed_c04_primary_and_refinement")
        ),
        replication_dependence_policy_ref=clause(
            "replication_dependence_policy",
            "cases_and_constructions_are_separate_dimensions",
        ),
        uncertainty_resolution_objectives_binding=na(
            "practice_has_no_population_confirmation"
        ),
        tail_resolution_objectives_binding=na("no_tail_population_claim"),
        minimum_subgroup_objectives_binding=na("descriptive_all_cells_only"),
        draw_order_semantics_ref=clause("draw_order_semantics", "role_then_cell_order"),
        stopping_extension_policy=sample.ProspectiveStoppingExtensionPolicy(
            clause("stopping_rule", "retain_every_draw_no_outcome_selection"),
            na("no_extension"),
            na("no_sampling_interim_look"),
            na("fixed_public_cases_despite_adaptive_recipes"),
            sample.CandidateOutcomeAccessBinding(
                sample.CandidateOutcomeAccessKind.CANDIDATE_OUTCOMES_PROHIBITED,
                clause("blinding_policy", "sampling_never_reads_candidate_results"),
            ),
            na("no_coverage_qualification"),
            clause("modification_authority", "new_version_for_design_change"),
        ),
        replacement_policy=sample.ReplacementPolicy(
            sample.ReplacementPolicyKind.NEVER, None
        ),
        duplicate_policy=sample.DuplicatePolicy(
            *(
                clause("duplicate_rule", label)
                for label in (
                    "exact_physical_parent_disjoint",
                    "exact_representation_parent_disjoint",
                    "common_generator_dependence_declared",
                    "repeat_research_observations_adaptively_seen",
                    "duplicates_stop_without_replacement",
                )
            )
        ),
        inclusion_policy_ref=clause("inclusion_policy", "all_frozen_cases"),
        exclusion_policy_ref=clause("exclusion_policy", "none_outcome_selected"),
        censoring_policy_ref=clause(
            "censoring_policy", "retain_missing_failed_censored_observations"
        ),
        public_authored_facts=tuple(PublicPlanFactKind),
        protected_realization_fields=(),
        statistical_qualification_requirements_ref=clause(
            "statistical_qualification_requirement",
            "not_qualified_by_development_authority",
        ),
        plan_provenance_refs=(clause("provenance", "prospective_d4_practice_design"),),
        insufficient_or_failure_policy="NON_SETTLING_FAIL_CLOSED",
    )
    return population, plan


def measurement_contract():
    source = digest(Path(measures.__file__).read_bytes())

    def definition(kind, label):
        return m.MeasurementDefinitionRef(
            CHALLENGE,
            kind,
            label,
            "3.0",
            digest(
                canonical(
                    {"source": source, "version": measures.VERSION, "definition": label}
                )
            ),
        )

    k = m.MeasurementDefinitionKind
    return m.MeasurementContract(
        CHALLENGE,
        "burgers_development_metric_vector",
        "3.0",
        definition(k.SCIENTIFIC_PROPERTY, "sampled_field_and_physics_diagnostics"),
        (definition(k.OBSERVABLE, "candidate_reference_and_initial_fields"),),
        definition(k.COORDINATE_SYSTEM, "periodic_space_physical_time"),
        definition(k.UNIT, "physical_and_dimensionless_as_v3"),
        definition(k.NUMERICAL_OPERATOR, "exact_measurement_v3_source"),
        definition(k.DISCRETIZATION, "grid_64_periodic_space_13_time_samples"),
        definition(k.SAMPLING_QUADRATURE, "equal_space_trapezoidal_time"),
        definition(k.NORMALIZATION, "v3_fixed_physical_amplitude_and_energy"),
        definition(k.AGGREGATION, "v3_per_case_diagnostics_not_official_score"),
        definition(k.PRECISION, "binary64"),
        ReferencePolicyRef(
            CHALLENGE,
            digest(
                canonical(
                    {
                        "policy": references.POLICY_ID,
                        "version": references.POLICY_VERSION,
                    }
                )
            ),
        ),
        m.ScientificValueBinding(m.ScientificValueState.HUMAN_INPUT),
        definition(k.APPLICABILITY_POLICY, "public_development_arrays_only"),
        m.UncertaintyPolicyBinding(m.ScientificValueState.HUMAN_INPUT),
        tuple(
            m.StratumApplicabilityBinding(
                definition(k.STRATUM, "cell_" + str(i)),
                m.StratumApplicabilityStatus.HUMAN_INPUT,
            )
            for i in range(12)
        ),
        (
            definition(
                k.KNOWN_LIMITATION, "sampled_unqualified_finite_development_cohort"
            ),
        ),
        (definition(k.IMPLEMENTATION, "carbon_measurement_runtime_development_v3"),),
        m.MeasurementRole.DIAGNOSTIC,
        False,
    )
