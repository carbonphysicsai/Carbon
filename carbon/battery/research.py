"""The battery research environment behind Carbon's shared MCP operations.

A miner reaches battery through the same twelve B-07 research operations as
any Challenge (`research_service.compose_research_service`). This module
supplies only what is battery's own:
- the authored practice population, sampling plan and measurement contract;
- the public objective;
- the public material: TRAIN v1, PRACTICE, the OCV table and the reference
  method;
- the practice callback;
- the unexecuted scaffold.

Research access is not evaluation authority. Nothing here reads a private
pool, a seed or a hidden case: those belong to the evaluation deployment
(`carbon.battery.evaluation`), which picks its own reference and never takes
a miner's artifact as the grading reference.

Every authored record is unqualified DEVELOPMENT metadata. Where the schema
asks for a scientific value (acceptance, uncertainty, strata) it is
``HUMAN_INPUT``.
"""

from __future__ import annotations

import json
import os
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
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    contract,
    public_registry,
)

from . import exam, practice_safety
from .challenge import (
    CAPACITY_CYCLES,
    CHALLENGE,
    GRID_POINTS,
    GRID_STEP_S,
    IDENTITY,
    INPUT_BOUNDS,
    INPUTS,
    OCV_TABLE_PATH,
    OCV_TABLE_SHA256,
    OUTPUTS,
    TRAIN_V1_CASES,
    TRAIN_V1_PATH,
    TRAIN_V1_SHA256,
    V_MAX,
    V_MIN,
    WINDOW_S,
)
from .contracts import authored_contracts, canonical, digest, semantic
from .practice import (
    FEEDBACK_SCHEMA,
    PRACTICE_CASES,
    PRACTICE_SOURCE_SHA256,
    PROGRAM,
    PROVENANCE,
    PracticeSet,
    feedback,
    score_practice,
    staged_files,
)
from .public_model_retention import record_trial
from .scaffold import SCAFFOLD

OBJECTIVE_SCHEMA = "carbon.battery.research-objective.v1"
#: The allow-listed fields of a validator outcome a miner may receive
#: (`daemon.BatteryValidator.outcome`), and of its screening summary. Named
#: here so discovery states them exactly; the daemon refuses to emit any other.
EVALUATION_FEEDBACK_FIELDS = (
    "schema",
    "submission_id",
    "challenge",
    "state",
    "evidence",
    "rule",
    "qualification",
    "reward",
    "failure",
    "recipe_digest",
    "contract_digest",
    "reconstruction",
    "screening",
    "nominated",
    "waiting",
    "finals",
    # The coverage rule that typed the outcome (GRAPHITE-COVERAGE-PARITY-01),
    # on outcomes recorded from that ruling on; absent on older ones.
    "coverage_rule",
)
SCREENING_FEEDBACK_FIELDS = (
    "pool_version",
    "eligible",
    "score",
    "important_score",
    "gates_failed",
    "cases",
)
PRACTICE_SECONDS = 600


def na(label):
    return A.not_applicable(semantic("applicability_reason", label))


def sampling_law():
    """The declared practice sampling law, read from the authored population
    contract so the disclosure cannot differ from it
    (OWNER-BATTERY-V2-DISCLOSURE-01, item 7)."""
    population, _ = population_and_sampling()
    support = population.support_contract
    law = population.law_semantics.payload
    return {
        "support": support.membership_rule_ref.object_id,
        "support_bounds": {name: list(INPUT_BOUNDS[name]) for name in INPUTS},
        "support_boundary": support.boundary_semantics_ref.object_id,
        "base_measure": law.base_measure_ref.object_id,
        "normalization": law.normalization_claim_ref.object_id,
        "draw": (
            "each input independently uniform over its bounds, rounded to 4 "
            "decimal places"
        ),
        "drawn_from_it": ["TRAIN v1", "PRACTICE"],
        "meaning": (
            "uniform coverage of the input box, not the prevalence of any real "
            "charging protocol or climate"
        ),
    }


def objective():
    """The public task statement, derived from the executable registrations."""
    rule = exam.DEVELOPMENT_RULE
    return {
        "schema": OBJECTIVE_SCHEMA,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "identity": IDENTITY,
        "task": (
            "Learn a fast surrogate for a pinned PyBaMM DFN (OKane2022) cell under "
            "a two-stage fast charge followed by ageing cycles: from four scalar "
            "inputs predict the first hour's voltage and temperature, the "
            "cycle-1 minimum plating margin, and capacity at four checkpoints."
        ),
        "intended_use": (
            "DEVELOPMENT research on reconstructable surrogate recipes. The "
            "reference is a simulator, not a real cell: agreement says nothing "
            "about real-cell lifetime or safety."
        ),
        "inputs": {
            name: {"bounds": list(INPUT_BOUNDS[name]), "unit": unit}
            for name, unit in zip(
                INPUTS, ("C-rate", "C-rate", "degC", "fraction"), strict=True
            )
        },
        "outputs": {
            "voltage_v": {
                "shape": [GRID_POINTS],
                "unit": "V",
                "grid": f"0..{WINDOW_S} s every {GRID_STEP_S} s",
            },
            "temperature_c": {
                "shape": [GRID_POINTS],
                "unit": "degC",
                "grid": f"0..{WINDOW_S} s every {GRID_STEP_S} s",
            },
            "plating_margin_v": {
                "shape": [],
                "unit": "V",
                "meaning": "minimum cycle-1 charge plating overpotential",
            },
            "capacity_ah": {
                "shape": [len(CAPACITY_CYCLES)],
                "unit": "Ah",
                "cycles": list(CAPACITY_CYCLES),
            },
        },
        "sampling_law": sampling_law(),
        "conventions": {
            "cycler_window_v": [V_MIN, V_MAX],
            "initial_state": "equilibrium at soc0 and ambient temperature",
            "prediction_order": list(OUTPUTS),
        },
        "gates": [
            {"gate": g.gate_id, "formula": g.formula, "applies": g.applicability}
            for g in exam.GATES
        ],
        "score": {
            "case_error": (
                "mean of four TRAIN-scale-normalized components: "
                + ", ".join(exam.COMPONENTS)
            ),
            "direction": "lower is better",
            "comparability": "bound to this Challenge version only",
            "mandatory_failure": "never compensated by score",
        },
        "rule": {
            "status": rule["status"],
            "authority": rule["authority"],
            "screening_batch_size": rule["screening_batch_size"],
            "active_batches": rule["active_batches"],
            "rotate_after_admitted": rule["rotate_after_admitted"],
            "equivalence_margin_rel": rule["equivalence_margin_rel"],
            "important_region": rule["important_region"],
            "promotable": rule["promotable"],
        },
        "evaluation_feedback_fields": list(EVALUATION_FEEDBACK_FIELDS),
        "practice_feedback_schema": FEEDBACK_SCHEMA,
        "non_claims": [
            "not scientifically, security or production qualified",
            "no reward, frontier, settlement or chain authority",
            "practice feedback is adaptively seen public evidence, not the exam",
        ],
    }


def reference_method():
    """How references are made, and who may make them."""
    from .truth import CHECKPOINTS, MAIN_CYCLES, TRUTH_IMAGE

    return {
        "reference": "PyBaMM 26.8.0.0 DFN, OKane2022 parameter set, unmodified",
        "protocol": "two-stage constant-current fast charge, CV hold, rest, discharge",
        "cycles": MAIN_CYCLES,
        "capacity_checkpoints": list(CHECKPOINTS),
        "truth_image": dict(TRUTH_IMAGE),
        "research_access": (
            "public TRAIN v1 and PRACTICE references only; no reference solve "
            "is offered to miners in this version"
        ),
        "evaluation_authority": (
            "the evaluation deployment solves its own references in the pinned "
            "truth image; a miner artifact is never a grading reference"
        ),
        "failure_typing": [
            "REFERENCE_SOLVER_FAILED",
            "REFERENCE_TIMEOUT",
            "FAILED_INFRA (never a scientific result; retried)",
        ],
        "quality": "unqualified numerical reference",
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
    population = pop.InstanceDistributionContract(
        **common,
        object_kind="instance_distribution_contract",
        object_id="battery_research_practice",
        supersedes=na("first_battery_research_population"),
        physical_system_ref=physical.to_ref(),
        candidate_output_ref=candidate.to_ref(),
        population_role=PopulationRole.PRACTICE,
        owning_claim_scope_ref=clause(
            "claim_scope", "public_adaptive_development_practice"
        ),
        target_population_binding=na("no_official_population_authority"),
        proposal_population_binding=na("no_official_proposal"),
        support_contract=pop.SupportContract(
            clause("membership_rule", "four_input_box"),
            clause("physical_support", "c1_c2_ambient_soc0_bounds"),
            clause("representation_support", "thirty_second_grid_121_points"),
            clause("support_boundary", "closed_input_box"),
            clause("membership_decision", "inputs_within_bounds"),
            "REJECT",
        ),
        law_semantics=pop.LawSemantics(
            pop.LawKind.PROBABILITY_LAW,
            pop.ProbabilityLaw(
                clause("base_measure", "uniform_over_input_box"),
                clause("probability_law", "campaign_practice_role_draws"),
                clause(
                    "normalization_claim",
                    "uniform_draws_not_industrial_prevalence",
                ),
            ),
        ),
        weighting_semantics=pop.WeightingSemantics(
            pop.WeightingSemanticsKind.NOT_APPLICABLE,
            clause("applicability_reason", "practice_population_is_not_score_weight"),
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
        population_provenance=(
            clause("provenance", "exam_design_campaign_practice_role"),
        ),
    )
    plan = sample.SamplingPlan(
        **common,
        object_kind="sampling_plan",
        object_id="battery_research_practice_plan",
        supersedes=na("first_battery_research_plan"),
        sampling_role=SamplingRole.PRACTICE,
        primary_population_ref=population.to_ref(),
        selection_population_ref=population.to_ref(),
        target_population_binding=na("no_official_target"),
        official_proposal_binding=na("no_official_proposal"),
        evidence_weight_binding=na("no_official_weight"),
        query_population_binding=na("fixed_output_grid"),
        observation_population_binding=na("synthetic_public_reference"),
        evidence_campaign_binding=na("practice_not_confirmation"),
        intended_estimand_or_reporting_ref=clause(
            "intended_estimand_or_reporting", "adaptive_practice_diagnostics"
        ),
        finite_evidence_design=sample.FiniteEvidenceDesign(
            clause("sampling_unit", "one_input_case"),
            sample.FiniteDesignMode.FIXED,
            PRACTICE_CASES,
            clause("base_evidence_requirement", "all_public_practice_cases"),
            na("fixed_design_with_external_campaign_admission"),
            na("no_case_extension"),
            "EVIDENCE_DEFERRED",
            "INDETERMINATE",
            "INSUFFICIENT_EVIDENCE",
            "NEW_VERSION_REQUIRED",
        ),
        full_design_law_ref=clause("full_design_law", "two_hundred_practice_cases"),
        stratified_allocation_binding=na("practice_is_not_stratified"),
        query_observation_allocation_binding=na("fixed_121_point_grid"),
        reference_fidelity_allocation_binding=A.bound(
            clause("reference_fidelity_allocation", "pinned_dfn_primary_solve")
        ),
        replication_dependence_policy_ref=clause(
            "replication_dependence_policy",
            "cases_and_constructions_are_separate_dimensions",
        ),
        uncertainty_resolution_objectives_binding=na(
            "practice_has_no_population_confirmation"
        ),
        tail_resolution_objectives_binding=na("no_tail_population_claim"),
        minimum_subgroup_objectives_binding=na("descriptive_all_cases_only"),
        draw_order_semantics_ref=clause("draw_order_semantics", "case_id_order"),
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
                    "exact_input_case_disjoint_from_train",
                    "exact_representation_disjoint_from_train",
                    "common_reference_dependence_declared",
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
        plan_provenance_refs=(
            clause("provenance", "exam_design_campaign_practice_role"),
        ),
        insufficient_or_failure_policy="NON_SETTLING_FAIL_CLOSED",
    )
    return population, plan


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

    k = m.MeasurementDefinitionKind
    return m.MeasurementContract(
        CHALLENGE,
        "battery_development_exam_vector",
        "1.0",
        definition(k.SCIENTIFIC_PROPERTY, "trajectory_plating_and_capacity_error"),
        (definition(k.OBSERVABLE, "voltage_temperature_plating_capacity"),),
        definition(k.COORDINATE_SYSTEM, "time_from_protocol_start"),
        definition(k.UNIT, "volt_degc_ampere_hour"),
        definition(k.NUMERICAL_OPERATOR, "exam_case_components"),
        definition(k.DISCRETIZATION, "thirty_second_grid_121_points"),
        definition(k.SAMPLING_QUADRATURE, "equal_weight_grid_points"),
        definition(k.NORMALIZATION, "train_scale_normalized_components"),
        definition(k.AGGREGATION, "mean_case_error_not_official_score"),
        definition(k.PRECISION, "binary64_scoring"),
        ReferencePolicyRef(
            CHALLENGE,
            digest(canonical({"reference": "carbon.battery.reference.v1"})),
        ),
        m.ScientificValueBinding(m.ScientificValueState.HUMAN_INPUT),
        definition(k.APPLICABILITY_POLICY, "public_development_arrays_only"),
        m.UncertaintyPolicyBinding(m.ScientificValueState.HUMAN_INPUT),
        tuple(
            m.StratumApplicabilityBinding(
                definition(k.STRATUM, label),
                m.StratumApplicabilityStatus.HUMAN_INPUT,
            )
            for label in ("important_region", "ordinary_region")
        ),
        (definition(k.KNOWN_LIMITATION, "simulator_reference_not_real_cell"),),
        (definition(k.IMPLEMENTATION, "carbon_battery_exam_v1"),),
        m.MeasurementRole.DIAGNOSTIC,
        False,
    )


class BatteryPublicMaterial:
    """The battery public-material allow-list for the workspace action.

    No path, case selector, URL, evaluator query or hidden role is accepted:
    a name selects one fixed public document.
    """

    NAMES = (
        "objective",
        "capabilities",
        "training_data",
        "practice_data",
        "reference_method",
        "scaffold_recipe",
    )

    def __init__(self, root="."):
        self.root = Path(root)

    def __call__(self, name, workspace):
        from .practice import _pinned

        if name == "training_data":
            body = _pinned(self.root / TRAIN_V1_PATH, TRAIN_V1_SHA256, "train_v1")
            workspace.put("battery-train-v1.jsonl.gz", body)
            table = _pinned(self.root / OCV_TABLE_PATH, OCV_TABLE_SHA256, "ocv_table")
            workspace.put("battery-ocv-table.json", table)
            return {
                "files": {
                    "battery-train-v1.jsonl.gz": digest(body),
                    "battery-ocv-table.json": digest(table),
                },
                "cases": TRAIN_V1_CASES,
                "format": "gzip JSON lines: case_id, inputs, outputs, diagnostics",
            }
        if name == "practice_data":
            practice = PracticeSet.load(self.root)
            body = practice.public_bytes()
            workspace.put("battery-practice-v1.jsonl.gz", body)
            return {
                "files": {"battery-practice-v1.jsonl.gz": digest(body)},
                "cases": PRACTICE_CASES,
                "source_sha256": PRACTICE_SOURCE_SHA256,
                "format": "gzip JSON lines: case_id, inputs, outputs, t_max_c",
                "adaptively_seen": True,
            }
        if name == "scaffold_recipe":
            # The published scaffold as a ready direct recipe: its graph is
            # staged where practice reads a workspace graph, so editing the
            # recipe's training block and practising it needs no lowering.
            from carbon.level4 import staging

            from . import public_scaffold

            manifest, files = public_scaffold.graph()
            workspace.put(staging.WORKSPACE_MANIFEST, manifest)
            staged = {staging.WORKSPACE_MANIFEST: digest(manifest)}
            for document, body in files.items():
                name_in_workspace = staging.WORKSPACE_PREFIX + document[7:] + ".json"
                workspace.put(name_in_workspace, body)
                staged[name_in_workspace] = digest(body)
            value = public_scaffold.recipe()
            payload = canonical(value)
            workspace.put("battery-scaffold-recipe.json", payload)
            return {
                "document": value,
                "file": "battery-scaffold-recipe.json",
                "digest": digest(payload),
                "files": staged,
                "use": (
                    "Practise it as strategy_json (kind=practice). Edit "
                    "procedure.configuration.training with any registered "
                    "training field; the scaffold graph is staged in your "
                    "workspace, and a new graph needs its own staged files."
                ),
                # Validator, 2026-10-20: served with the scaffold, not only in
                # a docstring the agent never reads.
                "anchors": (
                    "The scaffold's initial-state anchors assume "
                    "procedure.train_use.train_fraction 1.0; changing it breaks "
                    "the initial_temperature and initial_voltage gates."
                ),
            }
        if name == "objective":
            value = objective()
        elif name == "capabilities":
            value = public_registry(BATTERY_CHALLENGE)
        elif name == "reference_method":
            value = reference_method()
        else:
            raise ValueError("material outside public allowlist")
        payload = canonical(value)
        workspace.put("battery-" + name + ".json", payload)
        return {
            "document": value,
            "file": "battery-" + name + ".json",
            "digest": digest(payload),
        }


class BatteryPractice:
    """The practice callback: compile, run in the carrier, score on the host.

    `runner` is the carrier (`research_carrier._run`) unless the operator
    composes another. Whatever runs is recorded in the feedback as `backend`,
    so a result never claims an isolation it did not have.
    """

    #: The campaign's construction-level binding (LAUNCHPAD-LEVELS-01 S2), or
    #: None at Level 0: also for a practice built without `__init__`.
    level = None

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
        gpu_image=None,
        device=None,
        remote=None,
        level=None,
        model_retention=None,
        construction_mode=None,
    ):
        from carbon.development_session.battery_gpu import (
            image_backends as gpu_image_backends,
        )
        from carbon.development_session.battery_gpu import is_gpu_image
        from carbon.development_session.research_carrier import _run

        from .challenge import PublicMaterial

        self.ledger, self.owner, self.image = ledger, owner, image
        self.root, self.seconds = Path(root), seconds
        # GPU practice (C-MLP-03 slice 3): the campaign's verified GPU worker,
        # on the host's installed device. `device` is for tests; a campaign
        # reads the installed record on every trial.
        if gpu_image is not None and not is_gpu_image(gpu_image):
            raise ValueError("exact pinned GPU worker image required")
        self.gpu_image, self.device = gpu_image, device
        # The miner's own remote GPU machine (OWNER-MINER-COMPUTE-LINK-ONLY-01):
        # the same GPU program, run by `RemoteRunner` over SSH. It needs the
        # campaign's GPU worker identity and has no local device record.
        if remote is not None and gpu_image is None:
            raise ValueError("remote GPU practice runs the pinned GPU worker")
        self.remote = remote
        self.backends = (
            gpu_image_backends(gpu_image)
            if gpu_image is not None
            else image_backends(image, self.root)
        )
        self.runner = remote or (_run if runner is None else runner)
        self.backend = backend or {
            "kind": "ISOLATED_CARRIER",
            "carrier": "carbon.development_session.research_carrier",
        }
        self.material = PublicMaterial.load(self.root)
        self.practice = PracticeSet.load(self.root)
        #: The campaign's construction-level binding (LAUNCHPAD-LEVELS-01
        #: S2), or None at Level 0.
        self.level = level
        if construction_mode not in (None, "direct") or (construction_mode and level):
            raise ValueError(
                "battery direct construction conflicts with a legacy level"
            )
        self.construction_mode = construction_mode
        # The graph DEVELOPMENT path is the pinned C-03 CPU carrier even when
        # the campaign also offers a miner-owned remote GPU for other tasks.
        self.direct_runner = runner
        # Explicit local public Graphite test opt-in, frozen by campaign.py.
        # Ordinary/private campaigns retain their existing program and outputs.
        self.model_retention = model_retention

    def compile(self, strategy):
        from .compile import compile_recipe

        if self.level is None:
            return compile_recipe(strategy)
        # At a construction level: the level's compile
        # (`compile_development`, in its own process), then the recipe's
        # Level 0 base, which is what practice trains. A level refusal is a
        # `LevelRefused` (a ValueError) by its closed code; the Launchpad's
        # doors ask the same compile before a trial starts.
        from carbon.development_session import construction_level as cl

        if self.level.get("kind") == cl.COMPOSITION:
            value = cl.compile_strategy(self.level, strategy)
            self._construction_compile = value
            return compile_recipe(cl.base_strategy(strategy, value["widened_fields"]))
        return cl.level_compiler(self.level, compile_recipe)(strategy)

    def backend_refusal(self, strategy):
        """The backends this host serves, when `strategy` names another; None
        when it names a served one or does not compile.

        The request path reads this before dispatch, so a recipe this host
        cannot practise starts nothing and charges no trial slot
        (`backend_not_served`, LP-PROD-D). A recipe that does not compile is
        not refused here: the compiler names its issues.
        """
        from carbon.development_session.research_catalog import RecipeRejected

        if getattr(self, "construction_mode", None) == "direct":
            return None  # The direct callback binds the kit and source at use.

        try:
            _compiled, recipe = self.compile(strategy)
        except (RecipeRejected, ValueError, TypeError, KeyError):
            return None
        if recipe.settings.get("backend", "jax") in self.backends:
            return None
        return tuple(self.backends)

    def _seed(self, identity):
        """Carbon's per-trial randomness, retained so a replay is identical."""
        from carbon.development_session.data import write_once

        key = self.ledger.root / (
            "battery-practice-randomness-"
            + digest(canonical([self.owner, identity]))[7:]
            + ".bin"
        )
        if not key.exists():
            write_once(key, os.urandom(32))
        if key.is_symlink() or key.stat().st_size != 32:
            raise ValueError("invalid retained practice randomness")
        return int.from_bytes(key.read_bytes()[:4], "big")

    @record_trial
    def __call__(self, identity, strategy, *, retention_trial=None):
        from carbon.development_session.research_carrier import PRECHARGED_TRIAL
        from carbon.development_session.research_workspace import ResearchWorkspace

        if self.construction_mode == "direct":
            return self._direct_practice(identity, strategy, retention_trial)

        _compiled, recipe = self.compile(strategy)
        backend = recipe.settings.get("backend", "jax")
        if backend not in self.backends:
            # Refused before any run: this host's worker image cannot rebuild
            # the recipe's backend, and saying so is not a practice result.
            if self.gpu_image is not None:
                served = "JAX" if self.backends == ("jax",) else "PyTorch"
                raise ValueError(
                    f"backend_not_served: GPU practice serves {served} recipes only"
                )
            raise ValueError(
                f"backend_not_served: {backend} recipes practise in the PyTorch "
                "worker image (scripts/dev/torch_worker_image.sh)"
            )
        seed = self._seed(identity)
        # PRACTICE-SAFETY-01 B4: the public practice decision set, verified
        # against its pins (or refused, staging nothing), predicted beside
        # PRACTICE for feedback only.
        decision = practice_safety.decision_set(self.root)
        run = {
            "source": PROGRAM,
            "image": self.image,
        }
        if self.gpu_image is not None:
            from carbon.development_session.battery_gpu import (
                GPU_PROGRAM,
                TORCH_GPU_PROGRAM,
            )
            from carbon.development_session.research_carrier import MINER_GPU

            run = {
                "source": TORCH_GPU_PROGRAM if backend == "pytorch" else GPU_PROGRAM,
                "image": self.gpu_image,
                "accelerator": MINER_GPU,
            }
            device = None if self.remote else (self.device or _installed_device())
        files = staged_files(self.root, self.practice, recipe, seed, decision.cases())
        retained = None
        if retention_trial is not None:
            from .public_model_retention import retained_program

            run["source"], files, retained = retained_program(
                run["source"],
                files,
                opt_in=self.model_retention,
                identity=identity,
                image=getattr(run["image"], "image_id", None),
            )
            retention_trial.dispatch(
                retained,
                {
                    **recipe.document(),
                    "recipe_digest": recipe.recipe_digest,
                    "seed": seed,
                },
            )
        worker = self.runner(
            self.ledger,
            owner=self.owner,
            identity=identity,
            files=files,
            seconds=self.seconds,
            provenance=PROVENANCE,
            extra_resources=(
                {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
            ),
            **run,
        )
        snapshot = self.ledger.root / worker["operation"] / "snapshot"
        if retention_trial is not None:
            retention_trial.collect(worker, retained)

        def checked(name, maximum):
            path = snapshot / name
            if path.is_symlink() or not 0 < path.stat().st_size <= maximum:
                raise ValueError("bounded practice result required")
            body = path.read_bytes()
            if digest(body) != worker["files"].get(name):
                from carbon.development_session.research_carrier import (
                    record_output_tamper,
                )

                record_output_tamper(
                    self.ledger,
                    owner=self.owner,
                    operation=worker["operation"],
                    name=name,
                    expected=worker["files"].get(name),
                    observed=digest(body),
                )
            return json.loads(body)

        predictions = checked("predictions.json", 16 * 1024**2)
        fit = checked("fit.json", 65536)
        if type(predictions) is not dict or type(fit) is not dict:
            raise ValueError("practice result shape differs")
        # Only the cases Carbon asked for are scored; nothing else is read.
        asked = {c: predictions.get(c) for c in self.practice.case_ids}
        _rows, summary = score_practice(asked, self.practice, self.material, self.root)
        if self.gpu_image is None:
            ran = {**self.backend, "image": getattr(self.image, "image_id", None)}
        else:
            from carbon.development_session.battery_gpu import (
                backend_record,
                remote_backend_record,
            )

            observed = checked("runtime.json", 65536)
            if type(observed) is not dict:
                raise ValueError("practice result shape differs")
            ran = {
                **(
                    remote_backend_record(worker["remote"], observed)
                    if self.remote
                    else backend_record(device, observed, backend=backend)
                ),
                "image": self.gpu_image.image_id,
            }
        result = feedback(
            summary,
            fit,
            recipe=recipe,
            backend=ran,
            worker={
                "operation": worker["operation"],
                "output_digest": worker.get("output_digest"),
                "provenance": worker.get("provenance"),
            },
            # PRACTICE-SAFETY-01: feedback only, on the same public cases and
            # the decision set's; the score above saw PRACTICE alone.
            safety=practice_safety.safety(
                {**asked, **{c: predictions.get(c) for c in decision.case_ids}},
                self.practice,
                decision,
            ),
        )
        result["recipe"] = strategy
        result["seed_source"] = "carbon_retained_randomness"
        if self.level is not None:
            # What this practice trained at a construction level: the base.
            from carbon.development_session.construction_level import practice_label

            result["construction_level"] = practice_label(
                self.level, getattr(self, "_construction_compile", None)
            )
        ResearchWorkspace(self.ledger, self.owner).put(
            "trial-" + digest(identity.encode())[7:23] + "-battery-practice.json",
            canonical(result),
        )
        return result

    def _direct_practice(self, identity, strategy, retention_trial):
        """Rebuild a direct graph on pinned TRAIN and score public PRACTICE.

        The mode is frozen by the campaign. No legacy recipe compiler, family
        catalogue or level/base projection is called on this route.
        """
        from carbon.development_session.construction_recipe import (
            bind_recipe,
            graph_envelope_from_workspace,
        )
        from carbon.development_session.research_workspace import ResearchWorkspace

        from . import construction_kit, direct_graph_inference, direct_graph_worker
        from .practice import _summary, score_practice

        kit = construction_kit.construction_kit()
        recipe = bind_recipe(
            strategy,
            challenge_id=kit["id"],
            challenge_version=kit["version"],
            train_digest=kit["train_digest"],
            interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"],
        )
        source = recipe.to_dict()["source"]
        if source["kind"] != "graph":
            raise ValueError("battery_direct_bundle_execution_unserved")
        envelope = graph_envelope_from_workspace(self.ledger, self.owner, recipe)
        seed = self._seed(identity)
        decision = practice_safety.decision_set(self.root)
        # C13: the exam's dual measurement needs the public development bank's
        # decision and probe rows (the practice rows are queried already), so
        # the one inference below also covers them. Public, run on this host.
        from carbon.scoring import battery_public_adapter, practice_dual

        # The direct graph route serves the 1.0 construction kit, whose public
        # practice rows are the first rows of the 2.0 development bank (the bank
        # that adds the decision grid and the probe pairs). The block names the
        # measurement version it ran (`practice_dual.challenge.version`).
        dual_version = {"1.0": "2.0"}.get(kit["version"], kit["version"])
        dual_adapter = practice_dual.versioned(battery_public_adapter, dual_version)
        bank_cases = (
            [] if dual_adapter is None else practice_dual.bank_cases(dual_adapter)
        )
        practice_ids = set(self.practice.case_ids)
        bank_extra = [
            {"case_id": case_id, "inputs": inputs}
            for case_id, cohort, inputs in bank_cases
            if case_id not in practice_ids
        ]
        cases = self.practice.inputs_document(extra=[*decision.cases(), *bank_extra])[
            "cases"
        ]
        worker = direct_graph_worker.reconstruct_public(
            self.ledger,
            owner=self.owner,
            identity=identity,
            image=self.image,
            root=self.root,
            recipe=recipe,
            source_envelope=envelope,
            seed=seed,
            test_inputs={"cases": cases},
            runner=self.direct_runner,
        )
        if (
            worker.recipe_digest != recipe.digest
            or worker.graph_digest != source["submission_digest"]
            or worker.interface_digest != kit["interface_digest"]
            or worker.train_digest != kit["train_digest"]
        ):
            raise ValueError("direct practice reconstruction identity differs")
        inference = direct_graph_inference.infer_public(
            self.ledger,
            owner=self.owner,
            identity="direct-infer-"
            + digest(canonical([self.owner, identity, recipe.digest]))[7:],
            image=self.image,
            recipe=recipe,
            build=worker,
            test_inputs={"cases": cases},
            runner=self.direct_runner,
        )
        if (
            inference.recipe_digest != recipe.digest
            or inference.state_digest != worker.state_digest
        ):
            raise ValueError("direct practice inference identity differs")
        asked = {
            case: inference.predictions.get(case) for case in self.practice.case_ids
        }
        _rows, summary = score_practice(asked, self.practice, self.material, self.root)
        result = {
            # v2 (C13) adds the shared `practice_dual` block; v1 had none.
            "schema": "carbon.battery.direct-practice-feedback.v2",
            "provenance": "BATTERY_PUBLIC_PRACTICE",
            "challenge": recipe.to_dict()["challenge"],
            "recipe_digest": recipe.digest,
            "source": source,
            "summary": _summary(summary),
            "fit": _summary(
                {
                    key: worker.fit[key]
                    for key in ("n_params", "params_sha256", "train_loss")
                    if key in worker.fit
                }
            ),
            "backend": {
                "kind": "ISOLATED_C03_DIRECT_GRAPH",
                "image": getattr(self.image, "image_id", None),
            },
            "worker": {
                "operation": worker.worker_operation,
                "provenance": direct_graph_worker.PROVENANCE,
                "state_sha256": worker.state_digest,
                "build_predictions_sha256": worker.predictions_digest,
                "inference_operation": inference.worker_operation,
                "predictions_sha256": inference.predictions_digest,
            },
            "safety": practice_safety.safety(
                {
                    **asked,
                    **{
                        case: inference.predictions.get(case)
                        for case in decision.case_ids
                    },
                },
                self.practice,
                decision,
            ),
            "adaptively_seen": True,
            "final_exam": False,
            "official_eligible": False,
            "scientific_qualification": False,
            "recipe": strategy,
            "seed_source": "carbon_retained_randomness",
            "practice_dual": _battery_dual_feedback(
                dual_adapter, bank_cases, inference.predictions
            ),
        }
        workspace = ResearchWorkspace(self.ledger, self.owner)
        state_name = (
            "trial-" + digest(identity.encode())[7:23] + "-battery-direct-state.npz"
        )
        if worker.state_path.is_symlink() or not worker.state_path.is_file():
            raise ValueError("direct graph state unavailable")
        state = worker.state_path.read_bytes()
        if digest(state) != worker.state_digest:
            raise ValueError("direct graph state digest differs")
        workspace.put(state_name, state)
        result["model"] = {"workspace_name": state_name, "sha256": worker.state_digest}
        if retention_trial is not None:
            retention_trial.dispatch(
                {
                    "schema": "carbon.battery.direct-model-provenance.v1",
                    "recipe_digest": recipe.digest,
                    "train_digest": kit["train_digest"],
                    "graph_digest": source["submission_digest"],
                    "interface_digest": kit["interface_digest"],
                    "image": getattr(self.image, "image_id", None),
                },
                {"recipe_digest": recipe.digest, "seed": seed},
            )
            retention_trial.collect_direct(worker, state_name)
        workspace.put(
            "trial-" + digest(identity.encode())[7:23] + "-battery-practice.json",
            canonical(result),
        )
        return result


def _battery_dual_feedback(adapter, bank_cases, predictions):
    """The shared practice dual block for the model's predictions on the public
    development bank, or an explicit "unavailable" (never a silent omission)."""
    from carbon.scoring import battery_public_adapter, practice_dual

    if adapter is None:
        return practice_dual.unavailable(
            battery_public_adapter, "practice_version_not_registered"
        )
    rows = []
    for case_id, _cohort, _inputs in bank_cases:
        prediction = predictions.get(case_id)
        try:
            rows.append(
                [
                    *prediction["voltage_v"],
                    *prediction["temperature_c"],
                    prediction["plating_margin_v"],
                    *prediction["capacity_ah"],
                ]
            )
        except (KeyError, TypeError):
            return practice_dual.unavailable(adapter, "practice_prediction_missing")
    return practice_dual.from_rows(adapter, rows)


def _installed_device():
    """The host's installed GPU device record, read for this trial."""
    from carbon.reconstruction.worker.accelerator_runtime import host_device
    from carbon.reconstruction.worker.model import WorkerFailure

    try:
        return host_device()
    except WorkerFailure:
        raise ValueError(
            "no GPU device record is installed on this host; run setup's GPU check"
        ) from None


def image_backends(image, root):
    """The reconstruction backends a pinned worker image rebuilds.

    Every C-03 worker carries JAX. The PyTorch worker is the one whose lock
    digest is this checkout's exact-hashed `science-torch` export.
    """
    from carbon.reconstruction.torch_profile import requirements_digest

    if getattr(image, "lock_digest", None) == requirements_digest(root):
        return ("jax", "pytorch")
    return ("jax",)


def implementation_files():
    here = Path(__file__).parent
    return tuple(
        here / name
        for name in (
            "compile.py",
            "contracts.py",
            "domain.py",
            "exam.py",
            "practice.py",
            "practice_safety.py",
            "recipes.py",
            "research.py",
            "training.py",
            "torch_training.py",
            "torch_families.py",
            "value/decision.py",
        )
    ) + (here.parent / "practice_safety_feedback.py",)


def challenge_parts():
    """Battery's contribution to the shared research composition."""
    from carbon.development_session.research_resources import resources
    from carbon.development_session.research_service import ChallengeParts

    from .compile import compile_recipe
    from .contracts import battery_contracts

    contracts = battery_contracts()
    population, sampling = population_and_sampling()
    catalog = public_registry(BATTERY_CHALLENGE)
    return ChallengeParts(
        key=CHALLENGE,
        contracts=contracts,
        recipe_compiler=compile_recipe,
        resources=lambda compiler: resources(
            contracts,
            compiler,
            key=CHALLENGE,
            clause=semantic,
            class_id="battery_research_linux_cpu",
            policy_id="battery_research_static_policy",
        ),
        population=population,
        sampling=sampling,
        measurements=measurement_contract(),
        score_document={
            "score": objective()["score"],
            "gates": [g.gate_id for g in exam.GATES],
            "rule": exam.DEVELOPMENT_RULE,
        },
        strategy_schema=catalog,
        practice_scope=objective(),
        scaffold_catalog={
            "schema": "carbon.battery.scaffold-catalog.v1",
            "templates": [SCAFFOLD],
            "contract_digest": contract(BATTERY_CHALLENGE).digest,
        },
        scaffold_strategy=SCAFFOLD,
        implementation_files=implementation_files(),
        disclosure=b"carbon.battery.public-research-result.v1",
    )


def make_battery_research_service(
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
    """The battery composition of the shared B-07 research service.

    `julia_image` gives the research executor authored Julia (`run_julia`), as
    it does in the Burgers composition. It is a research tool only: the parts
    below - contracts, recipe compiler, strategy schema, scoring document and
    practice - are the same with or without it.
    """
    from dataclasses import replace

    from carbon.development_session.research_service import compose_research_service

    parts = challenge_parts()
    if getattr(practice, "level", None) is not None:
        # A campaign at a construction level compiles every recipe at it,
        # wherever the service compiles one (LAUNCHPAD-LEVELS-01 S2).
        parts = replace(parts, recipe_compiler=practice.compile)
    if julia_image is not None:
        from carbon.development_session import julia_analysis

        parts = replace(
            parts,
            implementation_files=(
                *parts.implementation_files,
                Path(julia_analysis.__file__),
            ),
        )
    composition = compose_research_service(
        parts,
        root=root,
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=(
            BatteryPublicMaterial(practice.root) if material is None else material
        ),
        practice=practice,
        julia_image=julia_image,
        cleanup_only=cleanup_only,
        demand=demand,
    )
    # Battery's own registry answers capability requests, the roadmap and
    # demand (OD-8), never Burgers' default.
    composition.executor.challenge = BATTERY_CHALLENGE
    return composition
