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

OBJECTIVE_SCHEMA = "carbon.battery.research-objective.v1"
#: The unexecuted template a miner starts from: the campaign MLP, shortened.
SCAFFOLD = {
    "schema_version": "1.0",
    "challenge_id": BATTERY_CHALLENGE,
    "backbone": "mlp",
    "parameters": {"steps": 2000, "width": 64, "depth": 3},
}
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
    ):
        from carbon.development_session.battery_gpu import BACKENDS, is_gpu_image
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
            BACKENDS if gpu_image is not None else image_backends(image, self.root)
        )
        self.runner = remote or (_run if runner is None else runner)
        self.backend = backend or {
            "kind": "ISOLATED_CARRIER",
            "carrier": "carbon.development_session.research_carrier",
        }
        self.material = PublicMaterial.load(self.root)
        self.practice = PracticeSet.load(self.root)

    def compile(self, strategy):
        from .compile import compile_recipe

        return compile_recipe(strategy)

    def backend_refusal(self, strategy):
        """The backends this host serves, when `strategy` names another; None
        when it names a served one or does not compile.

        The request path reads this before dispatch, so a recipe this host
        cannot practise starts nothing and charges no trial slot
        (`backend_not_served`, LP-PROD-D). A recipe that does not compile is
        not refused here: the compiler names its issues.
        """
        from carbon.development_session.research_catalog import RecipeRejected

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

    def __call__(self, identity, strategy):
        from carbon.development_session.research_carrier import PRECHARGED_TRIAL
        from carbon.development_session.research_workspace import ResearchWorkspace

        _compiled, recipe = self.compile(strategy)
        backend = recipe.settings.get("backend", "jax")
        if backend not in self.backends:
            # Refused before any run: this host's worker image cannot rebuild
            # the recipe's backend, and saying so is not a practice result.
            raise ValueError(
                f"backend_not_served: {backend} recipes practise in the PyTorch "
                "worker image (scripts/dev/torch_worker_image.sh)"
                + (
                    "; GPU practice serves JAX recipes only"
                    if self.gpu_image is not None
                    else ""
                )
            )
        seed = self._seed(identity)
        run = {
            "source": PROGRAM,
            "image": self.image,
        }
        if self.gpu_image is not None:
            from carbon.development_session.battery_gpu import GPU_PROGRAM
            from carbon.development_session.research_carrier import MINER_GPU

            run = {
                "source": GPU_PROGRAM,
                "image": self.gpu_image,
                "accelerator": MINER_GPU,
            }
            device = None if self.remote else (self.device or _installed_device())
        worker = self.runner(
            self.ledger,
            owner=self.owner,
            identity=identity,
            files=staged_files(self.root, self.practice, recipe, seed),
            seconds=self.seconds,
            provenance=PROVENANCE,
            extra_resources=(
                {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
            ),
            **run,
        )
        snapshot = self.ledger.root / worker["operation"] / "snapshot"

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
                    else backend_record(device, observed)
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
            # PRACTICE-SAFETY-01: feedback only, on the same public cases.
            safety=practice_safety.safety(asked, self.practice),
        )
        result["recipe"] = strategy
        result["seed_source"] = "carbon_retained_randomness"
        ResearchWorkspace(self.ledger, self.owner).put(
            "trial-" + digest(identity.encode())[7:23] + "-battery-practice.json",
            canonical(result),
        )
        return result


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
