"""Public DEVELOPMENT research provider for motor Level 0.

Construction sees only registered public TRAIN/PRACTICE material. Private
pools, decision-study references and future confirmation material are absent
by structure.
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
    MOTOR_CHALLENGE,
    contract,
    public_registry,
)

from . import exam, population, practice_safety
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
    digest,
    motor_contracts,
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
    "challenge_id": MOTOR_CHALLENGE,
    "backbone": "kernel_ridge",
    "parameters": {"length": "length_4", "ridge": "ridge_1e_4"},
}


def na(label):
    return A.not_applicable(semantic("applicability_reason", label))


def objective():
    interface = interface_document()
    return {
        "schema": "carbon.motor.research-objective.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "identity": IDENTITY,
        "task": (
            "Learn a fast surrogate for the registered two-dimensional motor "
            "cross-section from eight scalar inputs to the 60-angle torque curve."
        ),
        "intended_use": (
            "Public DEVELOPMENT construction and practice only; no three-"
            "dimensional end-effect, thermal, drive-transient, qualification "
            "or customer-acceptance claim."
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
        "reference": (
            "Gmsh mesh plus GetDP two-dimensional magnetostatic solve with "
            "Maxwell-stress torque over one rotor period"
        ),
        "image": "carbon-motor-reference:dev (pinned Dockerfile inputs)",
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
        object_id="motor_public_practice",
        supersedes=na("first_motor_research_population"),
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
            clause("physical_support", "eight_input_motor_bounds"),
            clause("representation_support", "sixty_angle_torque_curve"),
            clause("support_boundary", "closed_bounds_and_buildable_geometry"),
            clause("membership_decision", "domain_validity_has_no_reasons"),
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
        population_provenance=(clause("provenance", "motor_public_practice_v1"),),
    )
    plan = sample.SamplingPlan(
        **common,
        object_kind="sampling_plan",
        object_id="motor_public_practice_plan",
        supersedes=na("first_motor_research_plan"),
        sampling_role=SamplingRole.PRACTICE,
        primary_population_ref=practice_population.to_ref(),
        selection_population_ref=practice_population.to_ref(),
        target_population_binding=na("no_official_target"),
        official_proposal_binding=na("no_official_proposal"),
        evidence_weight_binding=na("no_official_weight"),
        query_population_binding=na("fixed_prediction_outputs"),
        observation_population_binding=na("public_getdp_records"),
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
        full_design_law_ref=clause("full_design_law", "thirty_public_cases"),
        stratified_allocation_binding=na("practice_is_not_stratified"),
        query_observation_allocation_binding=na("fixed_prediction_contract"),
        reference_fidelity_allocation_binding=A.bound(
            clause("reference_fidelity_allocation", "pinned_gmsh_getdp_records")
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
        plan_provenance_refs=(clause("provenance", "motor_public_practice_v1"),),
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
        "motor_development_error_vector",
        "1.0",
        definition(kind.SCIENTIFIC_PROPERTY, "mean_torque_and_ripple_shape_error"),
        (definition(kind.OBSERVABLE, "electromagnetic_torque_curve"),),
        definition(kind.COORDINATE_SYSTEM, "rotor_angle_over_period"),
        definition(kind.UNIT, "newton_metre"),
        definition(kind.NUMERICAL_OPERATOR, "exam_case_components"),
        definition(kind.DISCRETIZATION, "sixty_rotor_angles_over_fifteen_degrees"),
        definition(kind.SAMPLING_QUADRATURE, "equal_rotor_angle_samples"),
        definition(kind.NORMALIZATION, "train_scale_normalized_components"),
        definition(kind.AGGREGATION, "mean_case_error_not_official_score"),
        definition(kind.PRECISION, "binary64_scoring"),
        m.ReferencePolicyRef(
            CHALLENGE,
            digest(canonical({"reference": "carbon.motor.gmsh-getdp.v1"})),
        ),
        m.ScientificValueBinding(m.ScientificValueState.HUMAN_INPUT),
        definition(kind.APPLICABILITY_POLICY, "public_development_population_only"),
        m.UncertaintyPolicyBinding(m.ScientificValueState.HUMAN_INPUT),
        (),
        (
            definition(
                kind.KNOWN_LIMITATION,
                "two_dimensional_magnetostatic_not_end_effect_thermal_or_hardware",
            ),
        ),
        (definition(kind.IMPLEMENTATION, "carbon_motor_exam_v1"),),
        m.MeasurementRole.DIAGNOSTIC,
        False,
    )


class MotorPublicMaterial:
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
            workspace.put("motor-train-v1.jsonl", body)
            return {
                "files": {"motor-train-v1.jsonl": digest(body)},
                "cases": TRAIN_CASES,
                "format": "JSON lines: public GetDP reference records",
            }
        if name == "practice_data":
            body = canonical_text(
                self.root / PRACTICE_PATH, PRACTICE_SHA256, "practice"
            )
            workspace.put("motor-practice-v1.jsonl", body)
            return {
                "files": {"motor-practice-v1.jsonl": digest(body)},
                "cases": PRACTICE_CASES,
                "adaptively_seen": True,
            }
        if name == "objective":
            value = objective()
        elif name == "capabilities":
            value = public_registry(MOTOR_CHALLENGE)
        elif name == "reference_method":
            value = reference_method()
        else:
            raise ValueError("material outside public allowlist")
        body = canonical(value)
        workspace.put("motor-" + name + ".json", body)
        return {
            "document": value,
            "file": "motor-" + name + ".json",
            "digest": digest(body),
        }


class MotorPractice:
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
        """The backends this host serves when `strategy` compiles to a recipe
        it cannot practise, else None (`backend_not_served`, before anything
        starts or is charged). The practice worker is the numpy image, so a
        neural family (MOTOR-NEURAL-01) is refused until a JAX and PyTorch
        practice image is wired for Motor."""
        from carbon.development_session.research_catalog import RecipeRejected

        from .compile import NEURAL_FAMILIES

        try:
            _compiled, recipe = self.compile(strategy)
        except (RecipeRejected, ValueError, TypeError, KeyError):
            return None
        if recipe.family in NEURAL_FAMILIES:
            return tuple(self.backends)
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
            "trial-" + digest(identity.encode())[7:23] + "-motor-practice.json",
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

    contracts = motor_contracts()
    practice_population, sampling = population_and_sampling()
    catalog = public_registry(MOTOR_CHALLENGE)
    return ChallengeParts(
        key=CHALLENGE,
        contracts=contracts,
        recipe_compiler=compile_recipe,
        resources=lambda compiler: resources(
            contracts,
            compiler,
            key=CHALLENGE,
            clause=semantic,
            class_id="motor_research_linux_cpu",
            policy_id="motor_research_static_policy",
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
            "schema": "carbon.motor.scaffold-catalog.v1",
            "templates": [SCAFFOLD],
            "contract_digest": contract(MOTOR_CHALLENGE).digest,
        },
        scaffold_strategy=SCAFFOLD,
        implementation_files=implementation_files(),
        disclosure=b"carbon.motor.public-research-result.v1",
    )


def make_motor_research_service(
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
            MotorPublicMaterial(practice.root) if material is None else material
        ),
        practice=practice,
        julia_image=julia_image,
        cleanup_only=cleanup_only,
        demand=demand,
    )
    composition.executor.challenge = MOTOR_CHALLENGE
    return composition
