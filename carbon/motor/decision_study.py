"""Frozen construction, counted-reference custody and evaluation for Motor.

The synthetic limits are supplied by OWNER-GRAPHITE-TEST-WAVE-01 section 6.
Construction persists every proposal before a reference plan can be made.
Counted GetDP evidence requires the registered Docker campaign and durable
ledger; solver dispatch remains blocked until its compute/spend approval.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from statistics import fmean

from carbon import learned_baseline
from carbon.design_search import aggregate_methods, experiment, reference_comparison

from . import analytic, domain, reference_campaign
from . import customer_decision as cd

CONFIG_SCHEMA = "carbon.motor.decision-study-config.v1"
FREEZE_SCHEMA = "carbon.motor.decision-study-freeze.v1"
CONSTRUCTION_SCHEMA = "carbon.motor.decision-study-construction.v1"
PLAN_SCHEMA = "carbon.motor.decision-reference-plan.v1"
CAMPAIGN_SCHEMA = "carbon.motor.reference-campaign.v1"
SNAPSHOT_SCHEMA = "carbon.motor.reference-campaign-snapshot.v1"
RESULT_SCHEMA = "carbon.motor.decision-study-result.v1"
RETRY_ELIGIBLE_STATUSES = (
    "FAILED_INFRA",
    "REFERENCE_SOLVER_FAILED",
    "REFERENCE_TIMEOUT",
)

REGISTERED_SCENARIO = {
    "requirement_ref": "OWNER_GRAPHITE_TEST_WAVE_01_SECTION_6",
    "min_mean_torque_nm": 4.0,
    "max_ripple_fraction": 0.30,
    "approval_status": (
        "APPROVED_SYNTHETIC_DEVELOPMENT_ASSUMPTIONS_" "OWNER_GRAPHITE_TEST_WAVE_01"
    ),
    "operating_control": (
        "A fixed geometry is evaluated at six commanded peak-current-density "
        "and current-angle pairs. The command is assumed settled before each "
        "magnetostatic sweep; controller dynamics, voltage limits, speed, "
        "thermal limits and inverter feasibility are outside this study."
    ),
}
REGISTERED_DESIGNS = [
    {
        "design_id": f"d{index:02d}",
        "values": {
            "magnet_mm": magnet,
            "embrace": embrace,
            "airgap_mm": airgap,
            "slot_open_deg": 3.7,
            "tooth_mm": 3.5,
            "slot_bottom_mm": 38.16,
        },
    }
    for index, (magnet, embrace, airgap) in enumerate(
        (
            (magnet, embrace, airgap)
            for magnet in (2.0, 3.5)
            for embrace in (0.65, 0.85)
            for airgap in (0.4, 0.8)
        ),
        start=1,
    )
]
REGISTERED_CONDITIONS = [
    {
        "condition_id": condition_id,
        "group": group,
        "values": {
            "current_density_a_mm2": current,
            "current_angle_deg": angle,
        },
    }
    for condition_id, group, current, angle in (
        ("r01", "REPRESENTATIVE", 8.0, 0.0),
        ("r02", "REPRESENTATIVE", 10.0, 0.0),
        ("r03", "REPRESENTATIVE", 12.0, 0.0),
        ("r04", "REPRESENTATIVE", 10.0, 15.0),
        ("b01", "BOUNDARY_STRESS", 15.0, 0.0),
        ("b02", "BOUNDARY_STRESS", 12.0, 30.0),
    )
]
REGISTERED_ANALYSIS = {
    "proposal_classification": [
        "CONFIRMED_INFEASIBLE",
        "CONFIRMED_FEASIBLE",
        "UNRESOLVED",
        "ABSTAIN",
    ],
    "missing_evidence_policy": (
        "A confirmed violation remains CONFIRMED_INFEASIBLE even if another "
        "required condition is unavailable; no violation plus missing evidence "
        "is UNRESOLVED."
    ),
    "comparator_policy": (
        "Exact finite-set regret is allowed only after all potentially "
        "competitive designs are sufficiently resolved; otherwise report only "
        "a difference from the best observed feasible design."
    ),
    "group_reporting": (
        "REPRESENTATIVE and BOUNDARY_STRESS are reported separately; no combined "
        "weighting is approved."
    ),
    "reliability_policy": (
        "Descriptive fixed-pilot counts only; no population reliability or "
        "generalisation interval."
    ),
    "budget_views": {
        "deciding": "equal measured compute cost priced on recorded hardware",
        "diagnostic": "equal attempted model-query count",
        "amortised": (
            "measured break-even decision count including one-time training cost"
        ),
    },
}
REGISTERED_CLAIMS = {
    "customer_acceptance": False,
    "global_optimum": False,
    "population_reliability": False,
    "scientific_qualification": False,
    "production_qualification": False,
    "launch_readiness": False,
}


class StudyError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _sha256(path):
    # Git stores tracked text with LF. Normalize a Windows checkout's CRLF so
    # construction manifests remain portable across canonical Linux and local
    # diagnostic execution.
    content = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _write(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def load_config(path, *, repository):
    path = Path(path)
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema",
        "study_id",
        "material",
        "scope",
        "scenario",
        "designs",
        "conditions",
        "models",
        "methods",
        "budgets",
        "analysis",
        "claims",
    }
    if type(config) is not dict or set(config) != required:
        raise StudyError("config_fields")
    if (
        config["schema"] != CONFIG_SCHEMA
        or config["material"] != cd.MATERIAL
        or config["scope"] != cd.SCOPE
    ):
        raise StudyError("config_identity")
    if set(config["models"]) != {"analytic-v1", "learned-krr-v1"}:
        raise StudyError("model_panel")
    if config["models"]["analytic-v1"] != {
        "kind": "TEXTBOOK_SURFACE_PM_ANALYTICAL_BASELINE",
        "seed": 0,
    }:
        raise StudyError("analytical_model_identity")
    learned = config["models"]["learned-krr-v1"]
    if learned != {
        "kind": "GAUSSIAN_KERNEL_RIDGE",
        "training_records": "docs/development/evidence/motor-pools-v1/train.jsonl",
        "calibration_report": "docs/development/evidence/motor-pools-v1/baselines.json",
        "length": 4.0,
        "ridge": 0.0001,
        "seed": 0,
    }:
        raise StudyError("learned_hyperparameters_not_registered")
    for name in ("training_records", "calibration_report"):
        candidate = Path(repository) / learned[name]
        if not candidate.is_file():
            raise StudyError("model_evidence_missing", str(candidate))
    if set(config["methods"]) != {"fixed_grid", "screen_then_confirm"}:
        raise StudyError("method_panel")
    if config["methods"]["fixed_grid"] != {
        "method": "fixed_grid",
        "parameters": {},
    }:
        raise StudyError("fixed_grid_configuration")
    if config["methods"]["screen_then_confirm"] != {
        "method": "screen_then_confirm",
        "parameters": {"screen_condition": 5},
    }:
        raise StudyError("search_method_configuration")
    budgets = config["budgets"]
    if budgets != {
        "model_query_points_per_arm": 48,
        "verification_condition_evaluations_per_arm": 6,
        "reference_session_condition_evaluations": 72,
        "comparator_condition_evaluations": 48,
        "initial_solver_executions": 48,
        "retry_reserve": 12,
        "hard_solver_execution_cap": 60,
        "max_retries_per_case": 1,
        "retry_eligible_statuses": list(RETRY_ELIGIBLE_STATUSES),
        "cpus_per_solver_execution": 2,
        "parallel_solver_executions": 6,
        "solver_timeout_seconds": 3600,
        "artifact_retention": "all",
        "planning_initial_core_hours": 96.0,
        "planning_hard_cap_core_hours": 120.0,
        "configured_initial_allocated_core_hour_ceiling": 96.0,
        "configured_hard_cap_allocated_core_hour_ceiling": 120.0,
    }:
        raise StudyError("registered_budgets")
    if config["scenario"] != REGISTERED_SCENARIO:
        raise StudyError("registered_scenario")
    if config["designs"] != REGISTERED_DESIGNS:
        raise StudyError("registered_design_rule")
    if config["conditions"] != REGISTERED_CONDITIONS:
        raise StudyError("registered_conditions")
    if config["analysis"] != REGISTERED_ANALYSIS:
        raise StudyError("registered_analysis_policy")
    if config["claims"] != REGISTERED_CLAIMS:
        raise StudyError("registered_claim_ceiling")
    return config


def decision_contract(config):
    scenario = config["scenario"]
    return cd.contract(
        contract_id=config["study_id"],
        requirement_ref=scenario["requirement_ref"],
        min_mean_torque_nm=scenario["min_mean_torque_nm"],
        max_ripple_fraction=scenario["max_ripple_fraction"],
    )


def _designs(config):
    return [row["values"] for row in config["designs"]]


def _conditions(config):
    return [row["values"] for row in config["conditions"]]


def build_freeze(config, *, repository):
    contract = decision_contract(config)
    adapter = cd.adapter(contract)
    panel = []
    for name, spec in config["models"].items():
        recipe = {key: value for key, value in spec.items() if key != "seed"}
        panel.append(
            {
                "member": name,
                "recipe_digest": experiment.digest(recipe),
                "seed": spec["seed"],
                "material": cd.MATERIAL,
            }
        )
    proposals = {"screen_then_confirm": config["methods"]["screen_then_confirm"]}
    search = experiment.freeze(
        adapter,
        repository=repository,
        mode=cd.MODE,
        designs=_designs(config),
        conditions=_conditions(config),
        query_budget=config["budgets"]["model_query_points_per_arm"],
        verification_budget=config["budgets"][
            "verification_condition_evaluations_per_arm"
        ],
        seed_policy="deterministic registered DEVELOPMENT baselines; no random draw",
        panel=panel,
        proposals=proposals,
    )
    body = {
        "schema": FREEZE_SCHEMA,
        "study_id": config["study_id"],
        "config_digest": experiment.digest(config),
        "config_file_sha256": _sha256(
            Path(repository)
            / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V1.json"
        ),
        "decision_contract": contract,
        "search_freeze": search,
        "condition_groups": {
            row["condition_id"]: row["group"] for row in config["conditions"]
        },
        "comparisons": {
            "model_value": "same fixed-grid search, candidate set, conditions and budget",
            "search_value": (
                "same model and same 48-point maximum; measured compute cost is "
                "the deciding view and query count is diagnostic"
            ),
            "reference_comparator": (
                "best reference-feasible design in the registered finite "
                "eight-design by six-condition set when sufficiently resolved"
            ),
        },
        "analysis": config["analysis"],
        "claims": config["claims"],
    }
    return {**body, "freeze_digest": experiment.digest(body)}


def _learned_model(config, repository):
    try:
        import numpy as np
    except ImportError as error:
        raise StudyError("numpy_required_for_learned_reconstruction") from error

    spec = config["models"]["learned-krr-v1"]
    records = [
        json.loads(line)
        for line in (Path(repository) / spec["training_records"])
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    train = [record for record in records if record.get("status") == "OK"]
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    model = learned_baseline.KernelRidge(
        learned_baseline.scale(
            [record["inputs"] for record in train], domain.INPUTS, domain.INPUT_BOUNDS
        ),
        np.array([record["outputs"]["torque_nm"] for record in train]),
        length=spec["length"],
        ridge=spec["ridge"],
    )
    reconstruction = {
        "kind": "LEARNED_RECONSTRUCTION",
        "training_records": len(train),
        "length": spec["length"],
        "ridge": spec["ridge"],
        "wall_s": time.perf_counter() - started_wall,
        "cpu_s": time.process_time() - started_cpu,
        "historical_training_and_tuning_cost": None,
        "historical_cost_status": "NOT_RECORDED_IN_PINNED_BASELINE_ARTIFACT",
    }

    def predict(inputs):
        curve = [
            float(value)
            for value in model.predict(
                learned_baseline.scale([inputs], domain.INPUTS, domain.INPUT_BOUNDS)
            )[0]
        ]
        mean = fmean(curve)
        if mean < 0:
            curve = [value - mean for value in curve]
        return {"torque_nm": curve}

    return predict, reconstruction


def reconstruct_models(config, *, repository):
    learned, reconstruction = _learned_model(config, repository)

    def analytical(inputs):
        return {"torque_nm": analytic.predict(inputs)["torque_nm"]}

    def batch(one):
        return lambda inputs: {key: one(row) for key, row in inputs.items()}

    return {
        "analytic-v1": batch(analytical),
        "learned-krr-v1": batch(learned),
    }, {
        "analytic-v1": {"kind": "ANALYTICAL_BASELINE"},
        "learned-krr-v1": reconstruction,
    }


def _construction_identity(freeze_digest, arms):
    return experiment.digest(
        {
            "freeze_digest": freeze_digest,
            "commitments": [
                {
                    "arm_id": arm["arm_id"],
                    "commitment_digest": arm["commitment"]["commitment_digest"],
                    "file_sha256": arm["commitment"]["file_sha256"],
                    "status": arm["commitment"]["status"],
                }
                for arm in arms
            ],
        }
    )


def construct(config, *, repository, output):
    """Persist all four proposals without constructing any reference object."""

    construction_started = time.perf_counter()
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise StudyError("construction_output_not_empty", str(output))
    output.mkdir(parents=True, exist_ok=True)
    freeze = build_freeze(config, repository=repository)
    _write(output / "freeze.json", freeze)
    models, reconstruction = reconstruct_models(config, repository=repository)
    _write(output / "reconstruction.json", reconstruction)
    adapter = cd.adapter(freeze["decision_contract"])
    search_freeze = freeze["search_freeze"]
    code_digest = experiment.digest(search_freeze["code"])
    identities = {row["member"]: row for row in search_freeze["panel"]}
    arms = []
    for model_name in sorted(models):
        identity = identities[model_name]
        for method_name in sorted(search_freeze["methods"]):
            spec = search_freeze["methods"][method_name]
            neutral = experiment.neutral_request(
                adapter,
                mode=cd.MODE,
                model={
                    key: identity[key] for key in ("member", "recipe_digest", "seed")
                },
                designs=search_freeze["designs"],
                conditions=search_freeze["conditions"],
                query_budget=search_freeze["query_budget"],
                verification_budget=search_freeze["verification_budget"],
                method={
                    "name": method_name,
                    "code_digest": code_digest,
                    "configuration_digest": spec["configuration_digest"],
                },
                seed_policy=search_freeze["seed_policy"],
            )
            request_document, space = adapter.request(neutral)
            oracle = adapter.oracle(request_document, space, models[model_name])
            started = time.perf_counter()
            if spec["method"] == "fixed_grid":
                selections = adapter.baseline(oracle, request_document, space)
            else:
                selections = aggregate_methods.screen_then_confirm(
                    adapter.view(request_document, space),
                    oracle,
                    screen_condition=spec["parameters"]["screen_condition"],
                    aggregate_objective=lambda rows: (
                        max(row["ripple_fraction"] for row in rows),
                        -min(row["mean_nm"] for row in rows),
                    ),
                )
            search_wall_s = time.perf_counter() - started
            commitment = adapter.commit(
                request_document,
                selections,
                oracle,
                output / "commitments" / model_name / method_name,
            )
            document = commitment.document
            selection = document["selections"][0] if document["selections"] else None
            predicted_conditions = []
            if selection is not None:
                design = tuple(selection[name] for name in cd.DESIGN_VARIABLES)
                by_point = {
                    tuple(row["point"]): row["quantities"]
                    for row in oracle.log
                    if row["status"] == "OK"
                }
                for condition in config["conditions"]:
                    point = (
                        *design,
                        *(condition["values"][name] for name in cd.CONDITION_VARIABLES),
                    )
                    values = by_point.get(point)
                    if values is None:
                        raise StudyError(
                            "selected_design_prediction_missing",
                            f"{model_name}:{method_name}:{condition['condition_id']}",
                        )
                    predicted_conditions.append(
                        {
                            "case_id": cd._case_id(
                                domain.check_inputs(
                                    {
                                        **{
                                            name: selection[name]
                                            for name in cd.DESIGN_VARIABLES
                                        },
                                        **condition["values"],
                                    }
                                )
                            ),
                            "condition_id": condition["condition_id"],
                            "group": condition["group"],
                            "predicted": values,
                        }
                    )
            arms.append(
                {
                    "arm_id": f"{model_name}:{method_name}",
                    "model": model_name,
                    "method": method_name,
                    "declared_query_budget": search_freeze["query_budget"],
                    "queries_attempted": oracle.used,
                    "queries_successful": oracle.successful,
                    "search_wall_s": search_wall_s,
                    "model_wall_s": oracle.elapsed,
                    "selections": document["selections"],
                    "selection": selection,
                    "predicted_conditions": predicted_conditions,
                    "commitment": {
                        "relative_path": commitment.path.relative_to(output).as_posix(),
                        "commitment_digest": document["commitment_digest"],
                        "file_sha256": _sha256(commitment.path),
                        "status": document["status"],
                    },
                }
            )
    if len(arms) != 4:
        raise StudyError("all_four_commitments_required")
    body = {
        "schema": CONSTRUCTION_SCHEMA,
        "study_id": config["study_id"],
        "freeze_digest": freeze["freeze_digest"],
        "state": "ALL_PROPOSALS_COMMITTED_NO_REFERENCE_ACCESSED",
        "reconstruction_file_sha256": _sha256(output / "reconstruction.json"),
        "construction_wall_s": time.perf_counter() - construction_started,
        "arms": arms,
        "construction_identity_digest": _construction_identity(
            freeze["freeze_digest"], arms
        ),
        "next_stage": (
            "pin the built Docker image, generate the exact campaign plan, "
            "and obtain compute/spend approval before solver dispatch"
        ),
    }
    construction = {**body, "construction_digest": experiment.digest(body)}
    _write(output / "construction.json", construction)
    return construction


def load_construction(config, *, repository, directory):
    """Validate every commitment before returning an evaluation surface."""

    directory = Path(directory)
    try:
        freeze = json.loads((directory / "freeze.json").read_text(encoding="utf-8"))
        construction = json.loads(
            (directory / "construction.json").read_text(encoding="utf-8")
        )
        reconstruction = json.loads(
            (directory / "reconstruction.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise StudyError("complete_construction_artifact_required") from error
    if freeze != build_freeze(config, repository=repository):
        raise StudyError("construction_freeze_not_current")
    body = {
        key: value
        for key, value in construction.items()
        if key != "construction_digest"
    }
    if (
        construction.get("schema") != CONSTRUCTION_SCHEMA
        or construction.get("study_id") != config["study_id"]
        or construction.get("state") != "ALL_PROPOSALS_COMMITTED_NO_REFERENCE_ACCESSED"
        or construction.get("freeze_digest") != freeze["freeze_digest"]
        or construction.get("construction_digest") != experiment.digest(body)
        or construction.get("reconstruction_file_sha256")
        != _sha256(directory / "reconstruction.json")
    ):
        raise StudyError("construction_manifest_invalid")
    arms = construction.get("arms")
    expected = {
        f"{model}:{method}"
        for model in config["models"]
        for method in config["methods"]
    }
    if (
        type(arms) is not list
        or len(arms) != len(expected)
        or {arm.get("arm_id") for arm in arms if type(arm) is dict} != expected
        or construction.get("construction_identity_digest")
        != _construction_identity(freeze["freeze_digest"], arms)
    ):
        raise StudyError("construction_arm_set_or_identity")
    restored = []
    for arm in sorted(arms, key=lambda row: row["arm_id"]):
        manifest = arm.get("commitment")
        if type(manifest) is not dict:
            raise StudyError("construction_commitment_manifest")
        try:
            commitment = cd._restore_commitment(
                directory / manifest["relative_path"],
                expected_digest=manifest["commitment_digest"],
                expected_file_sha256=manifest["file_sha256"],
            )
        except (cd.DecisionError, KeyError, TypeError) as error:
            raise StudyError(
                "complete_construction_artifact_required", arm.get("arm_id", "")
            ) from error
        document = commitment.document
        selection = document["selections"][0] if document["selections"] else None
        if (
            document["status"] != manifest["status"]
            or document["selections"] != arm.get("selections")
            or selection != arm.get("selection")
        ):
            raise StudyError("construction_commitment_manifest_mismatch", arm["arm_id"])
        restored.append((arm, commitment))
    return freeze, construction, reconstruction, restored


def _pinned_image(image):
    if type(image) is not str or "@sha256:" not in image:
        raise StudyError("pinned_solver_image_required")
    digest_value = image.rsplit("@sha256:", 1)[1]
    if len(digest_value) != 64 or any(
        character not in "0123456789abcdef" for character in digest_value
    ):
        raise StudyError("pinned_solver_image_required")
    return image


def _comparison_jobs(config):
    jobs = []
    for design in config["designs"]:
        for condition in config["conditions"]:
            inputs = domain.check_inputs({**design["values"], **condition["values"]})
            jobs.append(
                {
                    "case_id": cd._case_id(inputs),
                    "raw_case_id": (
                        f"decision-{design['design_id']}-{condition['condition_id']}"
                    ),
                    "inputs": inputs,
                    "design_id": design["design_id"],
                    "condition_id": condition["condition_id"],
                    "group": condition["group"],
                }
            )
    return jobs


def _campaign_policy(config, construction_identity_digest, solver_image):
    cd._tagged_digest(construction_identity_digest, "construction_identity_digest")
    solver_image = _pinned_image(solver_image)
    budgets = config["budgets"]
    identity = {
        "study_id": config["study_id"],
        "construction_identity_digest": construction_identity_digest,
        "execution_backend": "DOCKER",
        "solver_image": solver_image,
        "ledger_relative_path": (
            f".carbon-artifacts/{config['study_id']}-campaign.sqlite3"
        ),
        "initial_execution_limit": budgets["initial_solver_executions"],
        "retry_execution_limit": budgets["retry_reserve"],
        "total_execution_limit": budgets["hard_solver_execution_cap"],
        "max_retries_per_case": budgets["max_retries_per_case"],
        "retry_eligible_statuses": budgets["retry_eligible_statuses"],
        "resource_policy": {
            "cpus_per_execution": budgets["cpus_per_solver_execution"],
            "parallel_executions": budgets["parallel_solver_executions"],
            "timeout_seconds_per_execution": budgets["solver_timeout_seconds"],
            "artifact_retention": budgets["artifact_retention"],
        },
    }
    return {
        "schema": CAMPAIGN_SCHEMA,
        "campaign_id": experiment.digest(identity),
        **identity,
    }


def reference_plan(
    config,
    construction_identity_digest,
    *,
    solver_image,
    case_ids=None,
    attempt=1,
):
    """Return an exact, bounded GetDP plan without launching a solver."""

    if attempt not in (1, 2):
        raise StudyError("reference_attempt_outside_policy")
    allowed = None if case_ids is None else set(case_ids)
    cases = []
    for job in _comparison_jobs(config):
        if allowed is not None and job["raw_case_id"] not in allowed:
            continue
        cases.append(
            {
                "case_id": job["raw_case_id"],
                "kind": "ordinary",
                "inputs": job["inputs"],
                "options": {},
            }
        )
    campaign = _campaign_policy(
        config, construction_identity_digest, solver_image=solver_image
    )
    plan = {
        "schema": PLAN_SCHEMA,
        "batch": f"{config['study_id']}-getdp-attempt-{attempt}",
        "attempt": attempt,
        "solver_image": campaign["solver_image"],
        "construction_identity_digest": construction_identity_digest,
        "campaign": campaign,
        "cases": cases,
    }
    reference_campaign._policy(plan)
    return plan


def reference_retry_plan(config, initial_directory):
    """Create the sole permitted retry plan from retained typed failures."""

    root = Path(initial_directory)
    actual = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    expected = reference_plan(
        config,
        actual.get("construction_identity_digest"),
        solver_image=actual.get("solver_image"),
        attempt=1,
    )
    if actual != expected:
        raise StudyError("retry_source_is_not_frozen_initial_plan")
    records = [
        json.loads(line)
        for line in (root / "records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    planned = {case["case_id"] for case in expected["cases"]}
    if (
        len(records) != len(planned)
        or {record.get("case_id") for record in records} != planned
    ):
        raise StudyError("retry_source_records_not_exactly_plan")
    _campaign_snapshot(root, actual, records)
    retry_ids = sorted(
        record["case_id"]
        for record in records
        if record.get("status") in RETRY_ELIGIBLE_STATUSES
    )
    if not retry_ids:
        raise StudyError("no_retry_eligible_cases")
    if len(retry_ids) > config["budgets"]["retry_reserve"]:
        raise StudyError("retry_reserve_insufficient", str(len(retry_ids)))
    return reference_plan(
        config,
        actual["construction_identity_digest"],
        solver_image=actual["solver_image"],
        case_ids=retry_ids,
        attempt=2,
    )


def fixture_reference(config):
    return cd.analytical_fixture_reference(
        condition_budget=config["budgets"]["reference_session_condition_evaluations"],
        session_id=f"{config['study_id']}-analytical-fixture",
    )


def _campaign_snapshot(root, plan, records):
    try:
        snapshot = json.loads(
            (Path(root) / "campaign-ledger.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise StudyError("campaign_ledger_snapshot_required", str(root)) from error
    campaign = plan["campaign"]
    if (
        snapshot.get("schema") != SNAPSHOT_SCHEMA
        or snapshot.get("campaign_id") != campaign["campaign_id"]
        or snapshot.get("construction_identity_digest")
        != plan["construction_identity_digest"]
        or snapshot.get("policy") != campaign
    ):
        raise StudyError("campaign_ledger_identity", str(root))
    batches = snapshot.get("batches")
    executions = snapshot.get("executions")
    if type(batches) is not list or type(executions) is not list:
        raise StudyError("campaign_ledger_rows", str(root))
    attempt = plan["attempt"]
    batch = [row for row in batches if row.get("attempt") == attempt]
    if (
        len(batch) != 1
        or batch[0].get("batch") != plan["batch"]
        or batch[0].get("state") != "FINISHED"
    ):
        raise StudyError("campaign_ledger_batch", str(root))
    by_case = {record["case_id"]: record for record in records}
    current = [row for row in executions if row.get("attempt") == attempt]
    if (
        len(current) != len(by_case)
        or {row.get("case_id") for row in current} != set(by_case)
        or any(
            row.get("state") != "FINISHED"
            or row.get("status") != by_case[row["case_id"]].get("status")
            for row in current
        )
    ):
        raise StudyError("campaign_ledger_execution_records", str(root))
    accounting = snapshot.get("accounting")
    expected_accounting = {
        "attempted_executions": len(executions),
        "initial_attempts": sum(row.get("attempt") == 1 for row in executions),
        "retry_attempts": sum(row.get("attempt") == 2 for row in executions),
        "finished_executions": sum(
            row.get("state") == "FINISHED" for row in executions
        ),
    }
    if accounting != expected_accounting:
        raise StudyError("campaign_ledger_accounting", str(root))
    if (
        expected_accounting["initial_attempts"] > campaign["initial_execution_limit"]
        or expected_accounting["retry_attempts"] > campaign["retry_execution_limit"]
        or expected_accounting["attempted_executions"]
        > campaign["total_execution_limit"]
    ):
        raise StudyError("campaign_ledger_limit_exceeded", str(root))
    return snapshot


def _artifact_manifest(case_directories, extra_files):
    rows = []
    total = 0
    for prefix, directory in case_directories:
        for path in sorted(
            candidate for candidate in directory.rglob("*") if candidate.is_file()
        ):
            size = path.stat().st_size
            total += size
            rows.append(
                {
                    "path": f"{prefix}/{path.relative_to(directory).as_posix()}",
                    "bytes": size,
                    "sha256": _sha256(path),
                }
            )
    for relative, path in extra_files:
        path = Path(path)
        if path.is_file():
            size = path.stat().st_size
            total += size
            rows.append({"path": relative, "bytes": size, "sha256": _sha256(path)})
    rows.sort(key=lambda row: row["path"])
    return rows, total


def import_counted_getdp(config, reference_directories):
    """Validate the registered campaign artifacts and return counted evidence."""

    roots = [Path(path) for path in reference_directories]
    if not roots or len(roots) > 2:
        raise StudyError("one_initial_and_optional_retry_directory")
    first = json.loads((roots[0] / "plan.json").read_text(encoding="utf-8"))
    construction_identity = first.get("construction_identity_digest")
    image = first.get("solver_image")
    expected_initial = reference_plan(
        config,
        construction_identity,
        solver_image=image,
        attempt=1,
    )
    expected_by_raw = {case["case_id"]: case for case in expected_initial["cases"]}
    job_by_raw = {job["raw_case_id"]: job for job in _comparison_jobs(config)}
    attempts = {case_id: [] for case_id in expected_by_raw}
    first_status = {}
    total_records = 0
    campaign_wall_s = 0.0
    final_snapshot = None
    for attempt_number, root in enumerate(roots, start=1):
        plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
        host = json.loads((root / "host.json").read_text(encoding="utf-8"))
        done = json.loads((root / "DONE.json").read_text(encoding="utf-8"))
        if plan.get("attempt") != attempt_number or plan.get("solver_image") != image:
            raise StudyError("reference_plan_identity", str(root))
        if plan.get("campaign") != expected_initial["campaign"]:
            raise StudyError("reference_campaign_policy", str(root))
        case_ids = [case["case_id"] for case in plan.get("cases", [])]
        if attempt_number == 1 and plan != expected_initial:
            raise StudyError("initial_reference_plan_not_frozen")
        if attempt_number == 2:
            allowed = {
                case_id
                for case_id, status in first_status.items()
                if status in RETRY_ELIGIBLE_STATUSES
            }
            if not case_ids or not set(case_ids) <= allowed:
                raise StudyError("retry_plan_not_failed_subset")
            if plan != reference_plan(
                config,
                construction_identity,
                solver_image=image,
                case_ids=case_ids,
                attempt=2,
            ):
                raise StudyError("retry_reference_plan_not_frozen")
        resources = expected_initial["campaign"]["resource_policy"]
        if (
            host.get("execution_backend") != "DOCKER"
            or host.get("solver_image") != image
            or host.get("cpus") != resources["cpus_per_execution"]
            or host.get("parallel") != resources["parallel_executions"]
            or host.get("timeout_s") != resources["timeout_seconds_per_execution"]
            or host.get("keep") != resources["artifact_retention"]
        ):
            raise StudyError("reference_resource_policy", str(root))
        if (
            done.get("batch") != plan["batch"]
            or done.get("cases") != len(case_ids)
            or type(done.get("wall_s")) not in (int, float)
            or done["wall_s"] < 0
        ):
            raise StudyError("reference_completion_record", str(root))
        campaign_wall_s += float(done["wall_s"])
        records = [
            json.loads(line)
            for line in (root / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        if len(records) != len(case_ids) or {
            record.get("case_id") for record in records
        } != set(case_ids):
            raise StudyError("reference_records_not_exactly_plan", str(root))
        counts = {}
        for record in records:
            counts[record.get("status")] = counts.get(record.get("status"), 0) + 1
        if done.get("counts") != counts:
            raise StudyError("reference_completion_counts", str(root))
        final_snapshot = _campaign_snapshot(root, plan, records)
        total_records += len(records)
        for record in records:
            raw_id = record["case_id"]
            expected = expected_by_raw.get(raw_id)
            if (
                expected is None
                or record.get("schema") != "carbon.motor.reference-record.v1"
                or record.get("batch") != plan["batch"]
                or record.get("inputs") != expected["inputs"]
                or record.get("options", {}) != expected["options"]
                or record.get("image") != image
            ):
                raise StudyError("reference_record_identity", raw_id)
            attempts[raw_id].append((attempt_number, root, host, record))
            if attempt_number == 1:
                first_status[raw_id] = record.get("status")
    if (
        final_snapshot is None
        or final_snapshot["accounting"]["attempted_executions"] != total_records
    ):
        raise StudyError("campaign_ledger_final_attempt_count")

    normalized = {}
    for raw_id, expected in expected_by_raw.items():
        history = attempts[raw_id]
        if not history:
            continue
        final_attempt, root, host, record = history[-1]
        retained = []
        metadata = []
        artifacts_valid = True
        final_mesh = record.get("mesh")
        for number, attempt_root, _attempt_host, attempt_record in history:
            metadata.extend(
                (
                    f"attempt-{number}/batch/{name}",
                    attempt_root / name,
                )
                for name in (
                    "plan.json",
                    "host.json",
                    "records.jsonl",
                    "DONE.json",
                    "campaign-ledger.json",
                )
            )
            case_dir = attempt_root / "cases" / raw_id
            if not case_dir.is_dir():
                if attempt_record.get("status") == "FAILED_INFRA":
                    continue
                artifacts_valid = False
                break
            if attempt_record.get("status") == "OK":
                required = [
                    case_dir / "params.json",
                    case_dir / "machine.pro",
                    case_dir / "mesh.py",
                    case_dir / "mesh.json",
                    case_dir / "log.mesh",
                    case_dir / "log.getdp",
                ]
                result_files = list((case_dir / "res").glob("torque_*.txt"))
                if (
                    attempt_record.get("run") != "exit 0"
                    or any(
                        not path.is_file() or path.stat().st_size == 0
                        for path in required
                    )
                    or len(result_files) != domain.ANGLE_STEPS + 1
                    or attempt_record.get("checks", {}).get("not_converged") != 0
                ):
                    artifacts_valid = False
                    break
                mesh = json.loads((case_dir / "mesh.json").read_text(encoding="utf-8"))
                if mesh.get("steps", {}).get("0") != attempt_record.get("mesh"):
                    artifacts_valid = False
                    break
                if number == final_attempt:
                    final_mesh = attempt_record.get("mesh")
            retained.append((f"attempt-{number}", case_dir))
        if not artifacts_valid:
            continue
        manifest, artifact_bytes = _artifact_manifest(retained, metadata)
        checks = record.get("checks") or {}
        params_path = root / "cases" / raw_id / "params.json"
        params = (
            json.loads(params_path.read_text(encoding="utf-8"))
            if params_path.is_file()
            else None
        )
        provenance = {
            "evidence_class": "COUNTED_GETDP",
            "solver_image": image,
            "configuration_digest": experiment.digest(
                {
                    "plan_entry": expected,
                    "params": params,
                    "hosts": [item[2] for item in history],
                }
            ),
            "mesh_digest": experiment.digest(final_mesh),
            "convergence_evidence_digest": experiment.digest(
                {"not_converged": checks.get("not_converged")}
            ),
            "applicability_evidence_digest": experiment.digest(
                {"periodicity_rel": checks.get("periodicity_rel"), "iron": "brauer"}
            ),
            "run_identity": f"{config['study_id']}:{raw_id}:attempt-{final_attempt}",
            "artifact_manifest_digest": experiment.digest(manifest),
            "artifact_count": len(manifest),
            "artifact_bytes": artifact_bytes,
            "execution_count": len(history),
            "retry_count": len(history) - 1,
            "wall_s": sum(float(item[3].get("wall_s", 0.0)) for item in history),
            "cpu_limit": host["cpus"],
        }
        job = job_by_raw[raw_id]
        normalized[job["case_id"]] = cd._seal_counted_record(
            cd._REFERENCE_TOKEN,
            status=record.get("status", "REFERENCE_MISSING"),
            inputs=expected["inputs"],
            outputs=record.get("outputs"),
            checks=checks,
            provenance=provenance,
        )
    return cd.counted_getdp_reference(
        normalized,
        condition_budget=config["budgets"]["reference_session_condition_evaluations"],
        session_id=f"{config['study_id']}-counted-getdp",
        construction_identity_digest=construction_identity,
        campaign_wall_s=campaign_wall_s,
    )


def _reference_row(contract, job, record):
    verdict, values, status = cd._reference_verdict(contract, job, record)
    return {
        **job,
        "verdict": verdict,
        "reference_status": status,
        "reference": values,
    }


def _finite_comparator(config, freeze, contract, reference):
    jobs = _comparison_jobs(config)
    key = experiment.digest(
        {"freeze_digest": freeze["freeze_digest"], "purpose": "finite-comparator"}
    )
    records, accounting = reference.acquire(
        key,
        jobs,
        config["budgets"]["comparator_condition_evaluations"],
    )
    rows = [_reference_row(contract, job, records.get(job["case_id"])) for job in jobs]
    return reference_comparison.finite_comparator(
        designs=config["designs"],
        rows=rows,
        conditions_per_design=len(config["conditions"]),
        objective=lambda evidence: max(
            row["reference"]["ripple_fraction"] for row in evidence
        ),
        objective_field="worst_reference_ripple_fraction",
        definition=freeze["comparisons"]["reference_comparator"],
        limitations=(
            "Best-known only within the registered eight geometries, six current "
            "commands and 2D magnetostatic scope; it is not a global optimum."
        ),
        accounting=accounting,
    )


def _evaluate_arm(adapter, arm, commitment, reference):
    started = time.perf_counter()
    verification = adapter.verify(commitment, reference)
    by_case = {row["case_id"]: row for row in verification["rows"]}
    conditions = []
    for predicted in arm["predicted_conditions"]:
        reference_row = by_case[predicted["case_id"]]
        conditions.append(
            {
                **predicted,
                "reference": reference_row["reference"],
                "reference_verdict": reference_row["verdict"],
                "reference_status": reference_row["reference_status"],
            }
        )
    evaluation_wall_s = time.perf_counter() - started
    return {
        **arm,
        "proposal_outcome": verification["proposal_outcome"],
        "verification": verification,
        "conditions": conditions,
        "evaluation_wall_s": evaluation_wall_s,
        "end_to_end_wall_s": arm["search_wall_s"] + evaluation_wall_s,
    }


def _metrics(arms):
    outcomes = {
        outcome: sum(arm["proposal_outcome"] == outcome for arm in arms)
        for outcome in cd.PROPOSAL_OUTCOMES
    }
    proposals = [arm for arm in arms if arm["proposal_outcome"] != "ABSTAIN"]
    all_rows = [row for arm in proposals for row in arm["conditions"]]
    unique = {}
    for row in all_rows:
        evidence = {
            key: row[key]
            for key in (
                "case_id",
                "condition_id",
                "group",
                "reference_verdict",
                "reference_status",
                "reference",
            )
        }
        previous = unique.setdefault(row["case_id"], evidence)
        if previous != evidence:
            raise StudyError("reused_reference_case_disagrees", row["case_id"])
    groups = {}
    for group in ("REPRESENTATIVE", "BOUNDARY_STRESS"):
        used = [row for row in all_rows if row["group"] == group]
        distinct = [row for row in unique.values() if row["group"] == group]
        groups[group] = {
            "arm_condition_uses": len(used),
            "unique_design_condition_reference_cases": len(distinct),
            "evidence_reuses": len(used) - len(distinct),
            "unique_reference_verdicts": {
                verdict: sum(row["reference_verdict"] == verdict for row in distinct)
                for verdict in cd.VERDICTS
            },
        }
    return {
        "arms": len(arms),
        "proposal_outcomes": outcomes,
        "abstention_rate": outcomes["ABSTAIN"] / len(arms),
        "decision_coverage_count": outcomes["CONFIRMED_FEASIBLE"]
        + outcomes["CONFIRMED_INFEASIBLE"],
        "decision_coverage_denominator": len(arms),
        "false_feasible_proposals": outcomes["CONFIRMED_INFEASIBLE"],
        "false_feasible_proposal_denominator": len(proposals),
        "arm_condition_uses": len(all_rows),
        "unique_selected_design_condition_reference_cases": len(unique),
        "selected_reference_evidence_reuses": len(all_rows) - len(unique),
        "unique_selected_reference_verdicts": {
            verdict: sum(row["reference_verdict"] == verdict for row in unique.values())
            for verdict in cd.VERDICTS
        },
        "unavailable_or_invalid_reference_evidence_uses": sum(
            row["reference_verdict"] == "REFERENCE_UNAVAILABLE" for row in all_rows
        ),
        "worst_case_reference_ripple_fraction_for_feasible_proposals": {
            arm["arm_id"]: (
                max(row["reference"]["ripple_fraction"] for row in arm["conditions"])
                if arm["proposal_outcome"] == "CONFIRMED_FEASIBLE"
                else None
            )
            for arm in arms
        },
        "statistical_interpretation": {
            "mode": "DESCRIPTIVE_FIXED_PILOT",
            "population_reliability_or_generalisation_confidence": False,
            "reason": (
                "The four arms share one decision problem and may reuse the same "
                "design-condition evidence; uses are not independent samples."
            ),
            "future_uncertainty_requirement": (
                "An approved sampling design and a justified independent-observation unit."
            ),
        },
        "groups": groups,
    }


def _contrast(left, right):
    return {
        "left": left["arm_id"],
        "right": right["arm_id"],
        "same_declared_query_budget": (
            left["declared_query_budget"] == right["declared_query_budget"]
        ),
        "query_attempt_difference_right_minus_left": (
            right["queries_attempted"] - left["queries_attempted"]
        ),
        "selected_geometry_same": left["selection"] == right["selection"],
        "left_outcome": left["proposal_outcome"],
        "right_outcome": right["proposal_outcome"],
        "left_regret": left["regret"],
        "right_regret": right["regret"],
    }


def _markdown(result):
    lines = [
        "# Motor synthetic decision pilot",
        "",
        f"Evidence class: **{result['evidence_class']}**.",
        "",
        "## Arms",
        "",
        "| Arm | Selection | Queries | Outcome | Regret status | Exact regret |",
        "|---|---|---:|---|---|---:|",
    ]
    for arm in result["arms"]:
        selection = (
            "ABSTAIN"
            if arm["selection"] is None
            else json.dumps(
                {name: arm["selection"][name] for name in cd.DESIGN_VARIABLES},
                sort_keys=True,
            )
        )
        lines.append(
            f"| {arm['arm_id']} | `{selection}` | {arm['queries_attempted']} | "
            f"{arm['proposal_outcome']} | {arm['regret']['status']} | "
            f"{arm['regret']['value_fraction'] if arm['regret']['value_fraction'] is not None else 'N/A'} |"
        )
    lines += [
        "",
        "## Comparator",
        "",
        result["comparator"]["limitations"],
        "",
        f"Status: **{result['comparator']['status']}**.",
        "",
        "## Controlled comparisons",
        "",
        "```json",
        json.dumps(result["comparisons"], indent=2, sort_keys=True),
        "```",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(result["metrics"], indent=2, sort_keys=True),
        "```",
        "",
        "## Cost and resource accounting",
        "",
        "```json",
        json.dumps(result["cost"], indent=2, sort_keys=True),
        "```",
        "",
        (
            "Representative and boundary-stress groups are reported separately. "
            "This fixed pilot supports no population reliability claim."
        ),
        "",
        "## Interpretation",
        "",
        result["conclusion"]["observed_outcome"],
        "",
        result["conclusion"]["does_not_establish"],
        "",
    ]
    return "\n".join(lines)


def evaluate(
    config,
    *,
    repository,
    construction_directory,
    reference,
    output,
    evidence_label,
):
    """Evaluate immutable proposals and the complete finite comparison set."""

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    freeze, construction, reconstruction, restored = load_construction(
        config, repository=repository, directory=construction_directory
    )
    if (
        reference.evidence_class == "COUNTED_GETDP"
        and reference.construction_identity_digest
        != construction["construction_identity_digest"]
    ):
        raise StudyError("reference_construction_identity_mismatch")
    adapter = cd.adapter(freeze["decision_contract"])
    arms = [
        _evaluate_arm(adapter, arm, commitment, reference)
        for arm, commitment in restored
    ]
    comparator = _finite_comparator(
        config, freeze, freeze["decision_contract"], reference
    )
    for arm in arms:
        selected = (
            None
            if arm["proposal_outcome"] != "CONFIRMED_FEASIBLE"
            else max(row["reference"]["ripple_fraction"] for row in arm["conditions"])
        )
        arm["regret"] = reference_comparison.regret(
            proposal_outcome=arm["proposal_outcome"],
            selected_objective=selected,
            comparator=comparator,
            objective_field="worst_reference_ripple_fraction",
            value_field="value_fraction",
            selected_field="selected_worst_reference_ripple_fraction",
            comparator_field="comparator_worst_reference_ripple_fraction",
            difference_field="difference_from_best_observed_fraction",
        )
    metrics = _metrics(arms)
    reference_metrics = reference.metrics()
    by_id = {arm["arm_id"]: arm for arm in arms}
    selections = {
        (
            None
            if arm["selection"] is None
            else tuple(arm["selection"][name] for name in cd.DESIGN_VARIABLES)
        )
        for arm in arms
    }
    all_agree = len(selections) == 1
    evaluation_wall_s = time.perf_counter() - started
    result = {
        "schema": RESULT_SCHEMA,
        "study_id": config["study_id"],
        "evidence_label": evidence_label,
        "evidence_class": reference.evidence_class,
        "freeze_digest": freeze["freeze_digest"],
        "construction_digest": construction["construction_digest"],
        "construction_identity_digest": construction["construction_identity_digest"],
        "operating_control": config["scenario"]["operating_control"],
        "arms": arms,
        "comparisons": {
            "model_value_same_fixed_grid": _contrast(
                by_id["analytic-v1:fixed_grid"],
                by_id["learned-krr-v1:fixed_grid"],
            ),
            "search_value_analytic_model": _contrast(
                by_id["analytic-v1:fixed_grid"],
                by_id["analytic-v1:screen_then_confirm"],
            ),
            "search_value_learned_model": _contrast(
                by_id["learned-krr-v1:fixed_grid"],
                by_id["learned-krr-v1:screen_then_confirm"],
            ),
        },
        "comparator": comparator,
        "metrics": metrics,
        "cost": {
            "construction_wall_s": construction["construction_wall_s"],
            "construction_search_wall_s": sum(arm["search_wall_s"] for arm in arms),
            "evaluation_wall_s": evaluation_wall_s,
            "study_end_to_end_wall_s": (
                construction["construction_wall_s"] + evaluation_wall_s
            ),
            "model_query_attempts": sum(arm["queries_attempted"] for arm in arms),
            "model_inference_wall_s": sum(arm["model_wall_s"] for arm in arms),
            "reference_condition_evaluations": reference_metrics[
                "condition_evaluations"
            ],
            "reference_executions": reference_metrics["solver_executions"],
            "reference_retries": reference_metrics["retries"],
            "reference_solver_wall_s": reference_metrics["solver_wall_s"],
            "reference_campaign_wall_s": reference_metrics["campaign_wall_s"],
            "training_and_reconstruction": reconstruction,
            "per_arm_search_plus_evaluation_wall_s": {
                arm["arm_id"]: arm["end_to_end_wall_s"] for arm in arms
            },
            "compute_envelope": {
                key: config["budgets"][key]
                for key in (
                    "initial_solver_executions",
                    "retry_reserve",
                    "hard_solver_execution_cap",
                    "cpus_per_solver_execution",
                    "parallel_solver_executions",
                    "solver_timeout_seconds",
                    "planning_initial_core_hours",
                    "planning_hard_cap_core_hours",
                    "configured_initial_allocated_core_hour_ceiling",
                    "configured_hard_cap_allocated_core_hour_ceiling",
                )
            },
            "monetary_cost_usd": None,
            "monetary_cost_status": "NO_APPROVED_OR_RECORDED_RESOURCE_RATE",
        },
        "analysis_policy": config["analysis"],
        "claims": config["claims"],
        "conclusion": {
            "all_arms_selected_same_geometry": all_agree,
            "observed_outcome": (
                "All four arms selected the same geometry; this is agreement, not "
                "a learned-model design-quality advantage."
                if all_agree
                else "The registered model/search arms selected different geometries."
            ),
            "establishes": (
                "Only the observed DEVELOPMENT outcomes for the frozen finite set, "
                "models, methods, budgets and admitted evidence class."
            ),
            "does_not_establish": (
                "No customer acceptance, global optimality, population reliability, "
                "3D/thermal/dynamic performance, scientific qualification or LIVE readiness."
            ),
        },
    }
    _write(output / "result.json", result)
    (output / "report.md").write_text(_markdown(result), encoding="utf-8")
    return result
