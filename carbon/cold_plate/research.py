"""Public DEVELOPMENT research provider for cold-plate Level 0.

Construction sees only registered public TRAIN/PRACTICE material.  Counted
CFD, private pools and future confirmation material are absent by structure.
"""

from __future__ import annotations

import json
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
from carbon.reconstruction.capability_registry import (
    COLD_PLATE_CHALLENGE,
    contract,
    public_registry,
)

from . import exam, openfoam, population, practice_safety
from .challenge import (
    CHALLENGE,
    IDENTITY,
    PRACTICE_CASES,
    PRACTICE_PATH,
    PRACTICE_SHA256,
    TRAIN_CASES,
    TRAIN_PATH,
    TRAIN_SHA256,
    PublicMaterial,
    canonical_text,
    interface_document,
)
from .compile import compile_recipe
from .contracts import (
    authored_contracts,
    canonical,
    cold_plate_contracts,
    digest,
    semantic,
)
from .practice import (
    FEEDBACK_SCHEMA,
    PROGRAM,
    PROVENANCE,
    PracticeSet,
    feedback,
    score_practice,
    staged_files,
)

PRACTICE_SECONDS = 600
SCAFFOLD = {
    "schema_version": "1.0",
    "challenge_id": COLD_PLATE_CHALLENGE,
    "backbone": "kernel_ridge",
    "parameters": {"length": "length_8", "ridge": "ridge_1e_6"},
}


def na(label):
    return A.not_applicable(semantic("applicability_reason", label))


def objective():
    interface = interface_document()
    return {
        "schema": "carbon.cold-plate.research-objective.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "identity": IDENTITY,
        "task": (
            "Learn a fast surrogate for the registered steady periodic cold-plate "
            "cell from nine scalar inputs to peak temperature, the 30-segment "
            "heated-face profile and pressure drop."
        ),
        "intended_use": (
            "Public DEVELOPMENT construction and practice only; no manifold, "
            "transient, qualification or customer-acceptance claim."
        ),
        "inputs": interface["inputs"],
        "outputs": interface["outputs"],
        "sampling_law": {
            "population": population.POPULATION_VERSION,
            "draw": "uniform over the admitted input region",
            "meaning": "development coverage, not deployed-condition prevalence",
        },
        "gates": [
            {"gate": gate.gate_id, "formula": gate.formula, "basis": gate.basis}
            for gate in exam.GATES
        ],
        "score": {
            "components": list(exam.COMPONENTS),
            "direction": "lower is better",
            "comparability": "bound to this Challenge version only",
            "mandatory_failure": "never compensated by score",
        },
        "practice_feedback_schema": FEEDBACK_SCHEMA,
        "non_claims": [
            "not scientifically, security or production qualified",
            "no reward, frontier, settlement or chain authority",
            "public practice is adaptive research evidence, not confirmation",
        ],
    }


def reference_method():
    return {
        "reference": "steady OpenFOAM periodic-cell conjugate heat transfer",
        "image": openfoam.IMAGE,
        "population": population.POPULATION_VERSION,
        "research_access": "public TRAIN and PRACTICE records only",
        "evaluation_access": "not served by this construction ticket",
        "construction_access": False,
        "quality": "unqualified numerical DEVELOPMENT reference",
    }


def population_and_sampling():
    physical, candidate, _ = authored_contracts()
    common = {
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "challenge_key": CHALLENGE,
        "object_version": "1.0",
    }
    clause = semantic
    practice_population = pop.InstanceDistributionContract(
        **common,
        object_kind="instance_distribution_contract",
        object_id="cold_plate_public_practice",
        supersedes=na("first_cold_plate_research_population"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        population_role=PopulationRole.PRACTICE,
        owning_claim_scope_ref=clause(
            "claim_scope", "public_adaptive_development_practice"
        ),
        target_population_binding=na("no_official_population_authority"),
        proposal_population_binding=na("no_official_proposal"),
        support_contract=pop.SupportContract(
            clause("membership_rule", "development_population_v1_screen"),
            clause("physical_support", "nine_input_periodic_cell_bounds"),
            clause("representation_support", "three_output_prediction_contract"),
            clause("support_boundary", "closed_bounds_and_public_screen"),
            clause("membership_decision", "population_screen_passes"),
            "REJECT",
        ),
        law_semantics=pop.LawSemantics(
            pop.LawKind.PROBABILITY_LAW,
            pop.ProbabilityLaw(
                clause("base_measure", "uniform_over_input_box"),
                clause("probability_law", "uniform_conditioned_on_public_screen"),
                clause("normalization_claim", "development_not_field_prevalence"),
            ),
        ),
        weighting_semantics=pop.WeightingSemantics(
            pop.WeightingSemanticsKind.NOT_APPLICABLE,
            clause("applicability_reason", "practice_is_not_population_scoring"),
        ),
        stratification_binding=na("practice_is_not_stratified"),
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
        population_provenance=(clause("provenance", "cold_plate_public_practice_v1"),),
    )
    plan = sample.SamplingPlan(
        **common,
        object_kind="sampling_plan",
        object_id="cold_plate_public_practice_plan",
        supersedes=na("first_cold_plate_research_plan"),
        sampling_role=SamplingRole.PRACTICE,
        primary_population_ref=practice_population.to_ref(),
        selection_population_ref=practice_population.to_ref(),
        target_population_binding=na("no_official_target"),
        official_proposal_binding=na("no_official_proposal"),
        evidence_weight_binding=na("no_official_weight"),
        query_population_binding=na("fixed_prediction_outputs"),
        observation_population_binding=na("public_openfoam_records"),
        evidence_campaign_binding=na("practice_not_confirmation"),
        intended_estimand_or_reporting_ref=clause(
            "intended_estimand_or_reporting", "adaptive_practice_diagnostics"
        ),
        finite_evidence_design=sample.FiniteEvidenceDesign(
            clause("sampling_unit", "one_design_condition_case"),
            sample.FiniteDesignMode.FIXED,
            PRACTICE_CASES,
            clause("base_evidence_requirement", "all_public_practice_cases"),
            na("fixed_design"),
            na("no_case_extension"),
            "EVIDENCE_DEFERRED",
            "INDETERMINATE",
            "INSUFFICIENT_EVIDENCE",
            "NEW_VERSION_REQUIRED",
        ),
        full_design_law_ref=clause("full_design_law", "one_hundred_public_cases"),
        stratified_allocation_binding=na("practice_is_not_stratified"),
        query_observation_allocation_binding=na("fixed_prediction_contract"),
        reference_fidelity_allocation_binding=A.bound(
            clause("reference_fidelity_allocation", "pinned_openfoam_records")
        ),
        replication_dependence_policy_ref=clause(
            "replication_dependence_policy", "fixed_shared_public_cases"
        ),
        uncertainty_resolution_objectives_binding=na(
            "practice_has_no_population_confirmation"
        ),
        tail_resolution_objectives_binding=na("no_tail_population_claim"),
        minimum_subgroup_objectives_binding=na("descriptive_all_cases_only"),
        draw_order_semantics_ref=clause("draw_order_semantics", "case_id_order"),
        stopping_extension_policy=sample.ProspectiveStoppingExtensionPolicy(
            clause("stopping_rule", "all_fixed_cases"),
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
                    "practice_disjoint_from_train",
                    "exact_representation_disjoint_from_train",
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
        plan_provenance_refs=(clause("provenance", "cold_plate_public_practice_v1"),),
        insufficient_or_failure_policy="NON_SETTLING_FAIL_CLOSED",
    )
    return practice_population, plan


def measurement_contract():
    source = digest(Path(exam.__file__).read_bytes())

    def definition(kind, label):
        return m.MeasurementDefinitionRef(
            CHALLENGE,
            kind,
            label,
            "1.0",
            digest(canonical({"source": source, "definition": label})),
        )

    kind = m.MeasurementDefinitionKind
    return m.MeasurementContract(
        CHALLENGE,
        "cold_plate_development_error_vector",
        "1.0",
        definition(kind.SCIENTIFIC_PROPERTY, "temperature_profile_and_pressure_error"),
        (definition(kind.OBSERVABLE, "peak_profile_pressure"),),
        definition(kind.COORDINATE_SYSTEM, "axial_channel_position"),
        definition(kind.UNIT, "degc_and_pascal"),
        definition(kind.NUMERICAL_OPERATOR, "exam_case_components"),
        definition(kind.DISCRETIZATION, "thirty_axial_segments"),
        definition(kind.SAMPLING_QUADRATURE, "equal_profile_segments"),
        definition(kind.NORMALIZATION, "train_scale_normalized_components"),
        definition(kind.AGGREGATION, "mean_case_error_not_official_score"),
        definition(kind.PRECISION, "binary64_scoring"),
        m.ReferencePolicyRef(
            CHALLENGE,
            digest(canonical({"reference": "carbon.cold-plate.openfoam.v1"})),
        ),
        m.ScientificValueBinding(m.ScientificValueState.HUMAN_INPUT),
        definition(kind.APPLICABILITY_POLICY, "public_development_population_only"),
        m.UncertaintyPolicyBinding(m.ScientificValueState.HUMAN_INPUT),
        (),
        (
            definition(
                kind.KNOWN_LIMITATION,
                "periodic_cell_not_manifold_transient_or_hardware_validation",
            ),
        ),
        (definition(kind.IMPLEMENTATION, "carbon_cold_plate_exam_v1"),),
        m.MeasurementRole.DIAGNOSTIC,
        False,
    )


class ColdPlatePublicMaterial:
    NAMES = (
        "objective",
        "capabilities",
        "training_data",
        "practice_data",
        "reference_method",
    )

    def __init__(self, root="."):
        self.root = Path(root)

    def __call__(self, name, workspace):
        if name == "training_data":
            body = canonical_text(self.root / TRAIN_PATH, TRAIN_SHA256, "train")
            workspace.put("cold-plate-train-v1.jsonl", body)
            return {
                "files": {"cold-plate-train-v1.jsonl": digest(body)},
                "cases": TRAIN_CASES,
                "format": "JSON lines: public OpenFOAM reference records",
            }
        if name == "practice_data":
            body = canonical_text(
                self.root / PRACTICE_PATH, PRACTICE_SHA256, "practice"
            )
            workspace.put("cold-plate-practice-v1.jsonl", body)
            return {
                "files": {"cold-plate-practice-v1.jsonl": digest(body)},
                "cases": PRACTICE_CASES,
                "adaptively_seen": True,
            }
        if name == "objective":
            value = objective()
        elif name == "capabilities":
            value = public_registry(COLD_PLATE_CHALLENGE)
        elif name == "reference_method":
            value = reference_method()
        else:
            raise ValueError("material outside public allowlist")
        body = canonical(value)
        workspace.put("cold-plate-" + name + ".json", body)
        return {
            "document": value,
            "file": "cold-plate-" + name + ".json",
            "digest": digest(body),
        }


class ColdPlatePractice:
    def __init__(
        self,
        *,
        ledger,
        owner,
        image,
        root=".",
        seconds=PRACTICE_SECONDS,
        runner=None,
        backend=None,
    ):
        from carbon.development_session.research_carrier import _run

        self.ledger, self.owner, self.image = ledger, owner, image
        self.root, self.seconds = Path(root), seconds
        self.runner = _run if runner is None else runner
        self.backends = ("numpy",)
        self.gpu_image = None
        self.backend = backend or {
            "kind": "ISOLATED_CARRIER",
            "carrier": "carbon.development_session.research_carrier",
            "device": "cpu",
        }
        self.material = PublicMaterial.load(self.root)
        self.practice = PracticeSet.load(self.root)

    def compile(self, strategy):
        return compile_recipe(strategy)

    def backend_refusal(self, strategy):
        return None

    def __call__(self, identity, strategy):
        from carbon.development_session.research_carrier import PRECHARGED_TRIAL
        from carbon.development_session.research_workspace import ResearchWorkspace

        _compiled, recipe = self.compile(strategy)
        worker = self.runner(
            self.ledger,
            owner=self.owner,
            identity=identity,
            source=PROGRAM,
            files=staged_files(self.root, self.practice, recipe),
            image=self.image,
            seconds=self.seconds,
            provenance=PROVENANCE,
            extra_resources=(
                {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
            ),
        )
        snapshot = self.ledger.root / worker["operation"] / "snapshot"

        def checked(name, maximum):
            path = snapshot / name
            if path.is_symlink() or not 0 < path.stat().st_size <= maximum:
                raise ValueError("bounded practice result required")
            body = path.read_bytes()
            if digest(body) != worker["files"].get(name):
                raise ValueError("practice result changed")
            return json.loads(body)

        predictions = checked("predictions.json", 16 * 1024**2)
        fit = checked("fit.json", 65536)
        if type(predictions) is not dict or type(fit) is not dict:
            raise ValueError("practice result shape differs")
        _rows, summary = score_practice(predictions, self.practice, self.material)
        result = feedback(
            summary,
            fit,
            recipe=recipe,
            backend={**self.backend, "image": getattr(self.image, "image_id", None)},
            worker={
                "operation": worker["operation"],
                "output_digest": worker.get("output_digest"),
                "provenance": worker.get("provenance"),
            },
            # PRACTICE-SAFETY-01: feedback only, on the same public cases.
            safety=practice_safety.safety(predictions, self.practice),
        )
        result["recipe"] = strategy
        ResearchWorkspace(self.ledger, self.owner).put(
            "trial-" + digest(identity.encode())[7:23] + "-cold-plate-practice.json",
            canonical(result),
        )
        return result


def implementation_files():
    here = Path(__file__).parent
    challenge_files = tuple(
        here / name
        for name in (
            "challenge.py",
            "compile.py",
            "contracts.py",
            "domain.py",
            "exam.py",
            "practice.py",
            "practice_safety.py",
            "recipes.py",
            "research.py",
        )
    )
    return (
        *challenge_files,
        here.parent / "learned_baseline.py",
        here.parent / "practice_safety_feedback.py",
    )


def challenge_parts():
    from carbon.development_session.research_resources import resources
    from carbon.development_session.research_service import ChallengeParts

    contracts = cold_plate_contracts()
    practice_population, sampling = population_and_sampling()
    catalog = public_registry(COLD_PLATE_CHALLENGE)
    return ChallengeParts(
        key=CHALLENGE,
        contracts=contracts,
        recipe_compiler=compile_recipe,
        resources=lambda compiler: resources(
            contracts,
            compiler,
            key=CHALLENGE,
            clause=semantic,
            class_id="cold_plate_research_linux_cpu",
            policy_id="cold_plate_research_static_policy",
        ),
        population=practice_population,
        sampling=sampling,
        measurements=measurement_contract(),
        score_document={
            "components": list(exam.COMPONENTS),
            "direction": "lower_is_better",
            "qualification": False,
        },
        strategy_schema=catalog,
        practice_scope=objective(),
        scaffold_catalog={
            "schema": "carbon.cold-plate.scaffold-catalog.v1",
            "templates": [SCAFFOLD],
            "contract_digest": contract(COLD_PLATE_CHALLENGE).digest,
        },
        scaffold_strategy=SCAFFOLD,
        implementation_files=implementation_files(),
        disclosure=b"carbon.cold-plate.public-research-result.v1",
    )


def make_cold_plate_research_service(
    *,
    root,
    ledger,
    owner,
    image,
    practice,
    material=None,
    demand=None,
    cleanup_only=False,
    julia_image=None,
):
    from carbon.development_session.research_service import compose_research_service

    composition = compose_research_service(
        challenge_parts(),
        root=root,
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=(
            ColdPlatePublicMaterial(practice.root) if material is None else material
        ),
        practice=practice,
        julia_image=julia_image,
        cleanup_only=cleanup_only,
        demand=demand,
    )
    composition.executor.challenge = COLD_PLATE_CHALLENGE
    return composition
