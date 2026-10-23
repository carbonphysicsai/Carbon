"""Public DEVELOPMENT research parts for a direct-recipe-only version.

Mirrors Motor's research parts (objective, population and sampling,
measurement contract, public material) for the shared research composition.
Each part names only registered facts and the owner-approved ones (`facts`:
task, intended use, sampling law, reference method and quality, and the
population's support, membership, law, rights, fidelity and limitation
clauses); what is neither (gates, score, per-case disclosure, practice labels)
is `HUMAN_INPUT`, so it fails closed where it is read. The practice error scale
and aggregation are each Challenge's registered ones
(`practice.error_scale`; Validator, 2026-10-21).
Construction sees only registered public TRAIN and the exposed DEVELOPMENT
bank's inputs; no reference label, private pool or hidden role is served.
"""

from __future__ import annotations

import functools
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
from carbon.authoring.model import ApplicabilityBinding as A
from carbon.authoring.primitives import CANONICALIZATION_PROFILE

from . import facts
from . import practice as direct_practice
from .contracts import (
    PRECISION,
    authored_contracts,
    canonical,
    compile_refused,
    construction_kit,
    digest,
    direct_contracts,
    fact,
    interface_document,
    limits_document,
    semantic,
    train_facts,
)
from .spec import HUMAN_INPUT, key_for, keyed, research_key

#: Public material a direct campaign serves: the shared closed list plus the
#: catalog and the construction kit.
NAMES = (
    "objective",
    "capabilities",
    "training_data",
    "practice_data",
    "reference_method",
    "catalog",
    "construction_kit",
)


def na(spec, label):
    return A.not_applicable(semantic(spec, "applicability_reason", label))


def bank(spec):
    """The exposed DEVELOPMENT bank's registered identity: its case count and
    input array digest (never its labels)."""
    from carbon.challenge_kit import physical_material

    key = research_key(spec)
    material = physical_material.bundle_material(key.challenge_id, key.version)
    inputs = material["practice_inputs"]
    return {
        "cases": int(inputs.shape[0]),
        "inputs_dtype": inputs.dtype.str,
        "inputs_shape": list(inputs.shape),
        "inputs_sha256": digest(inputs.tobytes(order="C")),
        "role": material["disclosure"]["practice_role"],
    }


def objective(spec):
    key = research_key(spec)
    interface = interface_document(spec)
    return {
        "schema": "carbon." + spec.prefix + ".research-objective.v1",
        "challenge": {"id": key.challenge_id, "version": key.version},
        "title": spec.title,
        "task": facts.value(spec, key.version, "task"),
        "intended_use": facts.value(spec, key.version, "intended_use"),
        "inputs": interface["input"],
        "outputs": interface["output"],
        "scope": limits_document(spec)["scope"],
        "sampling_law": facts.value(spec, key.version, "sampling_law"),
        "gates": HUMAN_INPUT,
        "score": HUMAN_INPUT,
        "practice_feedback_schema": spec.practice_schema,
        "practice_error_scale": direct_practice.error_scale(spec, key.version),
        "non_claims": [
            "not scientifically, security or production qualified",
            "no reward, frontier, settlement or chain authority",
            "public practice is adaptive research evidence, not confirmation",
        ],
    }


def reference_method(spec):
    version = research_key(spec).version
    train = train_facts(spec)
    return {
        "reference": facts.value(spec, version, "reference_method"),
        "train_provenance_sha256": train["train_provenance_sha256"],
        "train_cases": train["train_cases"],
        "quality": facts.value(spec, version, "reference_quality"),
    }


def capabilities(spec):
    """What this version can construct: the direct sources its limits bind."""
    from carbon.backbone_catalog import served

    key = research_key(spec)
    limits = limits_document(spec)
    return {
        "schema": "carbon." + spec.prefix + ".direct-capabilities.v1",
        "challenge": {"id": key.challenge_id, "version": key.version},
        "sources": {
            # Battery's catalog version binds no graph adapter: its graph
            # recipes stay on its base version's own graph worker.
            "graph": limits.get("graph_training_adapter", "not served on this version"),
            "catalog": {
                **limits["backbone_catalog"],
                "entries": sorted(
                    served.document(key.challenge_id, key.version)["entries"]
                ),
            },
            "bundle": "closed: miner source bundles are not served",
        },
    }


def population_and_sampling(spec):
    physical, candidate, _ = authored_contracts(spec)
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "challenge_key": research_key(spec),
        "object_version": "1.0",
    }
    clause = functools.partial(semantic, spec)
    stated = functools.partial(fact, spec)
    cases = bank(spec)["cases"]
    practice_population = pop.InstanceDistributionContract(
        **common,
        object_kind="instance_distribution_contract",
        object_id=spec.prefix + "_public_practice",
        supersedes=na(spec, "first_" + spec.prefix + "_research_population"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        population_role=PopulationRole.PRACTICE,
        owning_claim_scope_ref=clause(
            "claim_scope", "public_adaptive_development_practice"
        ),
        target_population_binding=na(spec, "no_official_population_authority"),
        proposal_population_binding=na(spec, "no_official_proposal"),
        support_contract=pop.SupportContract(
            clause("membership_rule", "exposed_development_bank_rows"),
            stated(
                "physical_support", "physical_support", "human_input_physical_support"
            ),
            clause(
                "representation_support",
                PRECISION[interface_document(spec)["train_dtype"]][1],
            ),
            stated(
                "support_boundary", "support_boundary", "human_input_support_boundary"
            ),
            stated(
                "membership_decision",
                "membership_decision",
                "human_input_membership_decision",
            ),
            "REJECT",
        ),
        law_semantics=pop.LawSemantics(
            pop.LawKind.PROBABILITY_LAW,
            pop.ProbabilityLaw(
                stated("base_measure", "base_measure", "human_input_base_measure"),
                stated(
                    "probability_law",
                    "probability_law",
                    "human_input_probability_law",
                ),
                clause("normalization_claim", "development_not_field_prevalence"),
            ),
        ),
        weighting_semantics=pop.WeightingSemantics(
            pop.WeightingSemanticsKind.NOT_APPLICABLE,
            clause("applicability_reason", "practice_is_not_population_scoring"),
        ),
        stratification_binding=na(spec, "practice_is_not_stratified"),
        applicability_refs=(clause("applicability", "public_practice_only"),),
        exclusions=(),
        rights_profile_ref=stated(
            "rights_profile", "rights_profile.research", "human_input_rights_profile"
        ),
        permitted_use_refs=(clause("permitted_use", "adaptive_miner_research"),),
        restrictions=(clause("restriction", "not_final_evidence_or_qualification"),),
        # Validator ruling (2026-10-20): no per-case labels in practice, so the
        # labels are not public fields here and per-case detail fails closed.
        disclosure_contract=DisclosureContract(
            (),
            (),
            (),
            clause("aggregation_policy", "human_input_practice_aggregation"),
            clause("release_policy", "public_research_only"),
        ),
        allowed_consumers=(
            AllowedConsumer(AllowedConsumerKind.SAMPLING_PLAN, SamplingRole.PRACTICE),
        ),
        population_provenance=(
            clause("provenance", spec.prefix + "_exposed_development_bank"),
        ),
    )
    plan = sample.SamplingPlan(
        **common,
        object_kind="sampling_plan",
        object_id=spec.prefix + "_public_practice_plan",
        supersedes=na(spec, "first_" + spec.prefix + "_research_plan"),
        sampling_role=SamplingRole.PRACTICE,
        primary_population_ref=practice_population.to_ref(),
        selection_population_ref=practice_population.to_ref(),
        target_population_binding=na(spec, "no_official_target"),
        official_proposal_binding=na(spec, "no_official_proposal"),
        evidence_weight_binding=na(spec, "no_official_weight"),
        query_population_binding=na(spec, "fixed_prediction_outputs"),
        observation_population_binding=na(spec, "fixed_exposed_bank"),
        evidence_campaign_binding=na(spec, "practice_not_confirmation"),
        intended_estimand_or_reporting_ref=stated(
            "intended_estimand_or_reporting",
            "practice_reporting",
            "human_input_practice_reporting",
        ),
        finite_evidence_design=sample.FiniteEvidenceDesign(
            clause("sampling_unit", "one_bank_row"),
            sample.FiniteDesignMode.FIXED,
            cases,
            clause("base_evidence_requirement", "all_exposed_bank_rows"),
            na(spec, "fixed_design"),
            na(spec, "no_case_extension"),
            "EVIDENCE_DEFERRED",
            "INDETERMINATE",
            "INSUFFICIENT_EVIDENCE",
            "NEW_VERSION_REQUIRED",
        ),
        full_design_law_ref=clause("full_design_law", "exposed_bank_rows"),
        stratified_allocation_binding=na(spec, "practice_is_not_stratified"),
        query_observation_allocation_binding=na(spec, "fixed_prediction_contract"),
        reference_fidelity_allocation_binding=A.bound(
            stated(
                "reference_fidelity_allocation",
                "reference_fidelity",
                "human_input_reference_fidelity",
            )
        ),
        replication_dependence_policy_ref=clause(
            "replication_dependence_policy", "fixed_shared_public_cases"
        ),
        uncertainty_resolution_objectives_binding=na(
            spec, "practice_has_no_population_confirmation"
        ),
        tail_resolution_objectives_binding=na(spec, "no_tail_population_claim"),
        minimum_subgroup_objectives_binding=na(spec, "descriptive_all_cases_only"),
        draw_order_semantics_ref=clause("draw_order_semantics", "case_id_order"),
        stopping_extension_policy=sample.ProspectiveStoppingExtensionPolicy(
            clause("stopping_rule", "all_fixed_cases"),
            na(spec, "no_extension"),
            na(spec, "no_sampling_interim_look"),
            na(spec, "fixed_public_cases_despite_adaptive_recipes"),
            sample.CandidateOutcomeAccessBinding(
                sample.CandidateOutcomeAccessKind.CANDIDATE_OUTCOMES_PROHIBITED,
                clause("blinding_policy", "sampling_never_reads_candidate_results"),
            ),
            na(spec, "no_coverage_qualification"),
            clause("modification_authority", "new_version_for_design_change"),
        ),
        replacement_policy=sample.ReplacementPolicy(
            sample.ReplacementPolicyKind.NEVER, None
        ),
        duplicate_policy=sample.DuplicatePolicy(
            *(
                clause("duplicate_rule", label)
                for label in (
                    "human_input_practice_train_overlap",
                    "human_input_representation_overlap",
                    "shared_reference_dependence_declared",
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
            "statistical_qualification_requirement", "not_qualified"
        ),
        plan_provenance_refs=(
            clause("provenance", spec.prefix + "_exposed_development_bank"),
        ),
        insufficient_or_failure_policy="NON_SETTLING_FAIL_CLOSED",
    )
    return practice_population, plan


#: The practice measurement's registered normalisation and aggregation,
#: by Challenge (`practice.error_scale` names their records).
_NORMALIZATION = {
    "f02": "train40_v2_train_peak_std_c",
    "f08": "dev1_section7_f08_critical_scales",
    "battery_catalog": "battery_exam_train_scales",
}
_AGGREGATION = {
    "f02": "max_of_mean_near_block_mean_and_worst",
    "f08": "dev1_worst_over_quantity_and_case_mean_recorded",
    "battery_catalog": "battery_exam_aggregate_over_public_practice",
}


def measurement_contract(spec):
    source = digest(Path(direct_practice.__file__).read_bytes())
    key = research_key(spec)

    def definition(kind, label, statement=None):
        value = {"source": source, "definition": label}
        if statement is not None:
            value["statement"] = statement
        return m.MeasurementDefinitionRef(
            key, kind, label, "1.0", digest(canonical(value))
        )

    kind = m.MeasurementDefinitionKind
    # The approved known limitation (`facts`), its text bound by the digest;
    # its human_input_* label while unset.
    text = facts.value(spec, key.version, "known_limitation")
    limitation = (
        definition(kind.KNOWN_LIMITATION, "human_input_known_limitation")
        if text == HUMAN_INPUT
        else definition(
            kind.KNOWN_LIMITATION,
            facts.label(spec, key.version, "known_limitation"),
            text,
        )
    )
    return m.MeasurementContract(
        key,
        spec.prefix + "_development_practice",
        "1.0",
        definition(kind.SCIENTIFIC_PROPERTY, "human_input_scientific_property"),
        (definition(kind.OBSERVABLE, "interface_outputs"),),
        definition(kind.COORDINATE_SYSTEM, "human_input_coordinate_system"),
        definition(kind.UNIT, "interface_units"),
        definition(kind.NUMERICAL_OPERATOR, "absolute_error_over_registered_scale"),
        definition(kind.DISCRETIZATION, "one_row_per_case"),
        definition(kind.SAMPLING_QUADRATURE, "human_input_sampling_quadrature"),
        # The registered scale and its record's aggregation (practice.py).
        definition(kind.NORMALIZATION, _NORMALIZATION[spec.prefix]),
        definition(kind.AGGREGATION, _AGGREGATION[spec.prefix]),
        definition(
            kind.PRECISION,
            PRECISION[interface_document(spec)["train_dtype"]][1].replace(
                "rows", "outputs"
            ),
        ),
        m.ReferencePolicyRef(key, digest(canonical({"reference": HUMAN_INPUT}))),
        m.ScientificValueBinding(m.ScientificValueState.HUMAN_INPUT),
        definition(kind.APPLICABILITY_POLICY, "public_development_population_only"),
        m.UncertaintyPolicyBinding(m.ScientificValueState.HUMAN_INPUT),
        # The measurement layer requires one stratum binding; its
        # applicability is unresolved (HUMAN_INPUT), as Motor's and Battery's.
        (
            m.StratumApplicabilityBinding(
                definition(kind.STRATUM, "public_development_population"),
                m.StratumApplicabilityStatus.HUMAN_INPUT,
            ),
        ),
        (limitation,),
        (
            definition(
                kind.IMPLEMENTATION, "carbon_" + spec.prefix + "_direct_practice"
            ),
        ),
        m.MeasurementRole.DIAGNOSTIC,
        False,
    )


class DirectPublicMaterial:
    """The direct version's public material, by closed name. Each document is
    built under the version's research key; nothing per-case is served."""

    NAMES = NAMES

    def __init__(self, spec, version, root="."):
        self.spec = spec
        self.key = key_for(spec, version)
        self.root = Path(root)

    def __call__(self, name, workspace):
        with keyed(self.spec, self.key):
            return self._serve(name, workspace)

    def _serve(self, name, workspace):
        from carbon.backbone_catalog import served

        prefix = self.spec.challenge_id + "-"
        if name == "training_data":
            from carbon.challenge_kit import physical_material

            material = physical_material.bundle_material(
                self.key.challenge_id, self.key.version
            )
            body = material["train"]
            train = train_facts(self.spec)
            workspace.put(prefix + train["file"], body)
            return {
                "files": {prefix + train["file"]: digest(body)},
                "cases": train["train_cases"],
                "dtype": train["train_dtype"],
                "format": train["format"],
            }
        if name == "practice_data":
            value = {**bank(self.spec), "labels": HUMAN_INPUT, "adaptively_seen": True}
        elif name == "objective":
            value = objective(self.spec)
        elif name == "capabilities":
            value = capabilities(self.spec)
        elif name == "reference_method":
            value = reference_method(self.spec)
        elif name == "catalog":
            from carbon.challenge_registry.direct import catalog_recipe

            value = {
                **served.document(self.key.challenge_id, self.key.version),
                "catalog_digest": served.digest(
                    self.key.challenge_id, self.key.version
                ),
                "ready_recipe": catalog_recipe(self.spec, version=self.key.version),
                "use": facts.value(self.spec, self.key.version, "catalog_usage_text"),
            }
        elif name == "construction_kit":
            value = construction_kit(self.spec)
        else:
            raise ValueError("material outside public allowlist")
        body = canonical(value)
        workspace.put(prefix + name + ".json", body)
        return {
            "document": value,
            "file": prefix + name + ".json",
            "digest": digest(body),
        }


def implementation_files():
    from .contracts import IMPLEMENTATION_SOURCES, REPOSITORY

    return tuple(REPOSITORY / name for name in IMPLEMENTATION_SOURCES)


def _bound(spec, key, function):
    """`function` run under research key `key`, however late it is called."""

    def call(*args, **kwargs):
        with keyed(spec, key):
            return function(*args, **kwargs)

    return call


def challenge_parts(spec, version):
    """The research parts for exactly `version` (no default), keyed by it."""
    key = key_for(spec, version)
    with keyed(spec, key):
        return _challenge_parts(spec, key)


def _challenge_parts(spec, key):
    from carbon.backbone_catalog import served
    from carbon.challenge_registry.direct import catalog_recipe
    from carbon.development_session.research_resources import resources
    from carbon.development_session.research_service import ChallengeParts

    contracts = direct_contracts(spec, key.version)
    practice_population, sampling = population_and_sampling(spec)
    scaffold = catalog_recipe(spec, version=key.version)
    return ChallengeParts(
        key=key,
        contracts=contracts,
        recipe_compiler=compile_refused,
        resources=_bound(
            spec,
            key,
            lambda compiler: resources(
                contracts,
                compiler,
                key=key,
                clause=_bound(spec, key, functools.partial(semantic, spec)),
                class_id=spec.prefix + "_research_linux_cpu",
                policy_id=spec.prefix + "_research_static_policy",
            ),
        ),
        population=practice_population,
        sampling=sampling,
        measurements=measurement_contract(spec),
        score_document={"score": HUMAN_INPUT, "qualification": False},
        strategy_schema=served.document(key.challenge_id, key.version),
        practice_scope=objective(spec),
        scaffold_catalog={
            "schema": "carbon." + spec.prefix + ".scaffold-catalog.v1",
            "templates": [scaffold],
            "contract_digest": served.digest(key.challenge_id, key.version),
        },
        scaffold_strategy=scaffold,
        implementation_files=implementation_files(),
        disclosure=("carbon." + spec.prefix + ".public-research-result.v1").encode(),
    )


def make_research_service(
    spec,
    *,
    root,
    ledger,
    owner,
    image,
    practice,
    version,
    material=None,
    demand=None,
    cleanup_only=False,
    julia_image=None,
):
    from carbon.development_session.research_service import compose_research_service

    composition = compose_research_service(
        challenge_parts(spec, version),
        root=root,
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=(
            DirectPublicMaterial(spec, version, practice.root)
            if material is None
            else material
        ),
        practice=practice,
        julia_image=julia_image,
        cleanup_only=cleanup_only,
        demand=demand,
    )
    # The campaign's own Challenge: a roadmap or design check names no other
    # Challenge's registry (this one has none, so those refuse).
    composition.executor.challenge = spec.challenge_id
    return composition
