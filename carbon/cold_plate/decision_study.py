"""Reproducible DEVELOPMENT decision study for accelerator cold-plate cooling.

The study stays inside the periodic straight-channel cell.  It freezes one
synthetic scenario, compares model and search-method value separately, and
uses a finite reference-backed comparison set for regret.  Analytical
reference callbacks are fixtures; counted evidence is accepted only through
the retained-artifact importer in this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

from carbon.design_search import experiment, methods

from . import analytic, domain, exam, openfoam, reference_campaign
from . import customer_decision as cd

CONFIG_SCHEMA = "carbon.cold-plate.decision-study-config.v2"
FREEZE_SCHEMA = "carbon.cold-plate.decision-study-freeze.v2"
CONSTRUCTION_SCHEMA = "carbon.cold-plate.decision-study-construction.v1"
RESULT_SCHEMA = "carbon.cold-plate.decision-study-result.v2"
PLAN_SCHEMA = "carbon.cold-plate.decision-reference-plan.v2"
CAMPAIGN_SCHEMA = reference_campaign.CAMPAIGN_SCHEMA
GROUPS = ("REPRESENTATIVE", "BOUNDARY_STRESS")
RETRY_ELIGIBLE_STATUSES = (
    "FAILED_INFRA",
    "REFERENCE_SOLVER_FAILED",
    "REFERENCE_TIMEOUT",
)
_REQUIRED_SOLVER_FILES = (
    "log.blockMesh",
    "log.checkMesh",
    "log.splitMeshRegions",
    "log.changeDictionary.fluid",
    "log.changeDictionary.solid",
    "log.chtMultiRegionSimpleFoam",
    "log.cellCentres.fluid",
    "log.cellCentres.solid",
    "log.cellVolumes.fluid",
    "log.cellVolumes.solid",
    "times",
)


class StudyError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _repository_text_sha256(path):
    """Hash canonical Git/LF bytes even from a CRLF Windows checkout."""

    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _exact(value, fields, code):
    if type(value) is not dict or set(value) != set(fields):
        raise StudyError(code)
    return value


def load_config(path, *, repository):
    """Load and validate the frozen study vocabulary and referenced inputs."""

    path = Path(path)
    repository = Path(repository)
    config = json.loads(path.read_text(encoding="utf-8"))
    _exact(
        config,
        {
            "schema",
            "study_id",
            "material",
            "scope",
            "scenario",
            "designs",
            "conditions",
            "models",
            "methods",
            "comparisons",
            "budgets",
            "compute_accounting",
            "analysis",
            "claims",
        },
        "config_fields",
    )
    if (
        config["schema"] != CONFIG_SCHEMA
        or config["material"] != cd.MATERIAL
        or config["scope"] != cd.SCOPE
    ):
        raise StudyError("config_identity")
    scenario = _exact(
        config["scenario"],
        {
            "description",
            "customer_requirement_ref",
            "die_limit_c",
            "hydraulic_limit_w",
            "control_policy",
        },
        "scenario_fields",
    )
    if not scenario["description"].startswith("Synthetic"):
        raise StudyError("synthetic_scenario_label_required")
    control = _exact(
        scenario["control_policy"],
        {"name", "equation", "assumption", "not_demonstrated", "required_limits"},
        "control_policy_fields",
    )
    if control["equation"] != "total_flow_lpm = flow_lpm_per_kw * heat_load_w / 1000":
        raise StudyError("flow_control_equation")
    _exact(
        config["comparisons"],
        {"model_value", "search_method_value", "reference_comparator"},
        "comparison_fields",
    )
    budgets = _exact(
        config["budgets"],
        {
            "model_query_points_per_arm",
            "verification_condition_evaluations_per_arm",
            "comparator_condition_evaluations",
            "reference_session_condition_evaluations",
            "initial_solver_executions",
            "retry_reserve",
            "max_retries_per_case",
            "hard_solver_execution_cap",
            "cpus_per_solver_execution",
            "solver_timeout_seconds",
            "parallel_solver_executions",
            "estimated_core_hours_per_case",
            "estimated_initial_core_hours",
            "estimated_hard_cap_core_hours",
            "configured_initial_allocated_core_hour_ceiling",
            "configured_hard_cap_allocated_core_hour_ceiling",
            "retry_eligible_statuses",
        },
        "budget_fields",
    )
    compute_accounting = _exact(
        config["compute_accounting"],
        {
            "estimate_basis",
            "configured_ceiling_basis",
            "actual_cpu_use_limitation",
            "overhead_limitation",
        },
        "compute_accounting_fields",
    )
    analysis = _exact(
        config["analysis"],
        {
            "statistical_interpretation",
            "group_policy",
            "combined_weighting",
            "regret_quantity",
            "regret_policy",
            "pass_threshold",
        },
        "analysis_fields",
    )
    _exact(
        analysis["regret_policy"],
        {
            "reference_feasible_selection",
            "reference_infeasible_selection",
            "unresolved_reference",
            "abstention",
        },
        "regret_policy_fields",
    )
    statistical = _exact(
        analysis["statistical_interpretation"],
        {
            "mode",
            "population_reliability_claim",
            "independent_observation_unit",
            "future_uncertainty_requirement",
        },
        "statistical_interpretation_fields",
    )
    if config["claims"] != {
        "synthetic_customer_requirement": True,
        "global_optimum": False,
        "customer_acceptance": False,
        "scientific_qualification": False,
        "production_qualification": False,
        "live_authority": False,
    }:
        raise StudyError("claims_are_fail_closed")
    if analysis["combined_weighting"] is not None:
        raise StudyError("combined_weighting_requires_approval")
    if analysis["pass_threshold"] is not None:
        raise StudyError("pass_threshold_requires_approval")
    if (
        statistical
        != {
            "mode": "DESCRIPTIVE_FIXED_PILOT",
            "population_reliability_claim": False,
            "independent_observation_unit": None,
            "future_uncertainty_requirement": (
                "approved sampling design and justified unit of independent observation"
            ),
        }
        or analysis["group_policy"]
        != "REPORT_REPRESENTATIVE_AND_BOUNDARY_STRESS_SEPARATELY"
        or analysis["regret_quantity"] != "worst-case reference hydraulic power in W"
    ):
        raise StudyError("analysis_policy_identity")

    designs = []
    design_ids = set()
    for entry in config["designs"]:
        _exact(entry, {"design_id", "values"}, "design_entry_fields")
        if entry["design_id"] in design_ids:
            raise StudyError("duplicate_design_id")
        design_ids.add(entry["design_id"])
        if type(entry["values"]) is not dict or set(entry["values"]) != set(
            cd.DESIGN_VARIABLES
        ):
            raise StudyError("design_variables")
        designs.append(entry["values"])
    cd._grid(designs, cd.DESIGN_VARIABLES)

    conditions = []
    scenario_ids = set()
    for entry in config["conditions"]:
        _exact(entry, {"scenario_id", "group", "values"}, "condition_entry_fields")
        if entry["scenario_id"] in scenario_ids:
            raise StudyError("duplicate_scenario_id")
        scenario_ids.add(entry["scenario_id"])
        if entry["group"] not in GROUPS:
            raise StudyError("condition_group")
        if type(entry["values"]) is not dict or set(entry["values"]) != set(
            cd.CONDITION_VARIABLES
        ):
            raise StudyError("condition_variables")
        conditions.append(entry["values"])
    cd._conditions(conditions)
    for design in designs:
        for condition in conditions:
            domain.check_inputs({**design, **condition})

    expected_points = len(designs) * len(conditions)
    if (
        budgets["model_query_points_per_arm"] != expected_points
        or budgets["verification_condition_evaluations_per_arm"] != len(conditions)
        or budgets["comparator_condition_evaluations"] != expected_points
        or budgets["initial_solver_executions"] != expected_points
        or budgets["hard_solver_execution_cap"]
        != budgets["initial_solver_executions"] + budgets["retry_reserve"]
    ):
        raise StudyError("budget_geometry_mismatch")
    expected_session = expected_points + len(config["models"]) * len(
        config["methods"]
    ) * len(conditions)
    if budgets["reference_session_condition_evaluations"] != expected_session:
        raise StudyError("reference_session_budget_mismatch")
    if budgets["max_retries_per_case"] != 1:
        raise StudyError("study_retry_policy_is_one")
    for name in (
        "model_query_points_per_arm",
        "verification_condition_evaluations_per_arm",
        "comparator_condition_evaluations",
        "reference_session_condition_evaluations",
        "initial_solver_executions",
        "retry_reserve",
        "hard_solver_execution_cap",
        "cpus_per_solver_execution",
        "solver_timeout_seconds",
        "parallel_solver_executions",
        "configured_initial_allocated_core_hour_ceiling",
        "configured_hard_cap_allocated_core_hour_ceiling",
    ):
        if type(budgets[name]) not in (int, float) or budgets[name] <= 0:
            raise StudyError("positive_integer_budget", name)
    for name in (
        "model_query_points_per_arm",
        "verification_condition_evaluations_per_arm",
        "comparator_condition_evaluations",
        "reference_session_condition_evaluations",
        "initial_solver_executions",
        "retry_reserve",
        "hard_solver_execution_cap",
        "cpus_per_solver_execution",
        "solver_timeout_seconds",
        "parallel_solver_executions",
    ):
        if type(budgets[name]) is not int:
            raise StudyError("integer_budget_required", name)
    if not math.isclose(
        budgets["estimated_initial_core_hours"],
        budgets["estimated_core_hours_per_case"] * budgets["initial_solver_executions"],
    ) or not math.isclose(
        budgets["estimated_hard_cap_core_hours"],
        budgets["estimated_core_hours_per_case"] * budgets["hard_solver_execution_cap"],
    ):
        raise StudyError("estimated_compute_arithmetic")
    if not math.isclose(
        budgets["configured_initial_allocated_core_hour_ceiling"],
        budgets["initial_solver_executions"]
        * budgets["cpus_per_solver_execution"]
        * budgets["solver_timeout_seconds"]
        / 3600.0,
    ) or not math.isclose(
        budgets["configured_hard_cap_allocated_core_hour_ceiling"],
        budgets["hard_solver_execution_cap"]
        * budgets["cpus_per_solver_execution"]
        * budgets["solver_timeout_seconds"]
        / 3600.0,
    ):
        raise StudyError("configured_compute_ceiling_arithmetic")
    if budgets["retry_eligible_statuses"] != list(RETRY_ELIGIBLE_STATUSES):
        raise StudyError("retry_eligibility_policy")
    if not all(
        isinstance(value, str) and value for value in compute_accounting.values()
    ):
        raise StudyError("compute_accounting_statement")

    if set(config["methods"]) != {"fixed_grid", "screen_then_confirm"}:
        raise StudyError("registered_method_panel")
    for name, spec in config["methods"].items():
        _exact(spec, {"method", "parameters"}, "method_fields")
        if spec["method"] != name:
            raise StudyError("method_name_mismatch")
    methods.check(
        "screen_then_confirm",
        config["methods"]["screen_then_confirm"]["parameters"],
        mode=cd.MODE,
        conditions=len(conditions),
    )
    learned = config["models"].get("learned-krr-v1")
    if set(config["models"]) != {"analytic-v1", "learned-krr-v1"}:
        raise StudyError("model_panel")
    _exact(config["models"]["analytic-v1"], {"kind", "seed"}, "analytic_model_fields")
    _exact(
        learned,
        {
            "kind",
            "seed",
            "training_records",
            "training_sha256",
            "calibration_report",
            "calibration_sha256",
            "length",
            "ridge",
        },
        "learned_model_fields",
    )
    if type(learned) is not dict or learned.get("kind") != "LEARNED_RECONSTRUCTION":
        raise StudyError("learned_model_required")
    for relative, field in (
        (learned["training_records"], "training_sha256"),
        (learned["calibration_report"], "calibration_sha256"),
    ):
        actual = _repository_text_sha256(repository / relative)
        if actual != learned[field]:
            raise StudyError("model_artifact_digest_mismatch", relative)
    calibration = json.loads(
        (repository / learned["calibration_report"]).read_text(encoding="utf-8")
    )
    if (
        calibration["learned"]["length"] != learned["length"]
        or calibration["learned"]["ridge"] != learned["ridge"]
    ):
        raise StudyError("learned_hyperparameters_not_calibrated")
    return config


def decision_contract(config):
    scenario = config["scenario"]
    return cd.contract(
        contract_id=config["study_id"],
        customer_requirement_ref=scenario["customer_requirement_ref"],
        die_limit_c=scenario["die_limit_c"],
        hydraulic_limit_w=scenario["hydraulic_limit_w"],
    )


def _designs(config):
    return [entry["values"] for entry in config["designs"]]


def _conditions(config):
    return [entry["values"] for entry in config["conditions"]]


def build_freeze(config, *, repository):
    """Freeze scenario, analysis and generic search contracts before evidence."""

    contract = decision_contract(config)
    adapter = cd.adapter(contract)
    model_panel = []
    for name, spec in config["models"].items():
        recipe = {key: value for key, value in spec.items() if key != "seed"}
        model_panel.append(
            {
                "member": name,
                "recipe_digest": experiment.digest(recipe),
                "seed": spec["seed"],
                "material": cd.MATERIAL,
            }
        )
    proposals = {
        name: spec for name, spec in config["methods"].items() if name != "fixed_grid"
    }
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
        seed_policy="deterministic frozen DEVELOPMENT models; no random draw",
        panel=model_panel,
        proposals=proposals,
    )
    body = {
        "schema": FREEZE_SCHEMA,
        "study_id": config["study_id"],
        "config_digest": experiment.digest(config),
        "decision_contract": contract,
        "search_freeze": search,
        "condition_groups": {
            entry["scenario_id"]: entry["group"] for entry in config["conditions"]
        },
        "case_roles": {
            "training_and_prior_tuning": config["models"]["learned-krr-v1"][
                "training_records"
            ],
            "prior_calibration_report": config["models"]["learned-krr-v1"][
                "calibration_report"
            ],
            "final_decision_evaluation": [
                entry["scenario_id"] for entry in config["conditions"]
            ],
            "final_cases_used_for_training_or_tuning": False,
        },
        "control_policy": config["scenario"]["control_policy"],
        "comparisons": config["comparisons"],
        "budgets": config["budgets"],
        "compute_accounting": config["compute_accounting"],
        "analysis": config["analysis"],
        "reference_scope": {
            "solver_image": openfoam.IMAGE,
            "physical_scope": cd.SCOPE,
            "comparison_set": "all declared design-condition pairs",
            "global_optimality_claim": False,
        },
        "claims": config["claims"],
    }
    return {**body, "freeze_digest": experiment.digest(body)}


def _learned_model(config, repository):
    """Reconstruct the already selected KRR baseline and measure that cost."""

    try:
        import numpy as np

        from carbon import learned_baseline
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
    x = learned_baseline.scale(
        [record["inputs"] for record in train], domain.INPUTS, domain.INPUT_BOUNDS
    )
    targets = []
    for record in train:
        inlet = record["inputs"]["inlet_c"]
        outputs = record["outputs"]
        targets.append(
            [math.log(outputs["peak_c"] - inlet)]
            + [math.log(value - inlet) for value in outputs["profile_c"]]
            + [math.log(outputs["pressure_drop_pa"])]
        )
    model = learned_baseline.KernelRidge(
        x,
        np.array(targets),
        length=spec["length"],
        ridge=spec["ridge"],
    )
    reconstruction = {
        "kind": "LEARNED_RECONSTRUCTION",
        "training_records": len(train),
        "wall_s": time.perf_counter() - started_wall,
        "cpu_s": time.process_time() - started_cpu,
        "historical_training_and_tuning_cost": None,
        "historical_cost_status": "NOT_RECORDED_IN_PINNED_BASELINE_ARTIFACT",
    }

    def predict_one(inputs):
        values = model.predict(
            learned_baseline.scale([inputs], domain.INPUTS, domain.INPUT_BOUNDS)
        )[0]
        inlet = inputs["inlet_c"]
        profile = [inlet + math.exp(value) for value in values[1:-1]]
        return {
            "peak_c": max(inlet + math.exp(values[0]), max(profile)),
            "profile_c": profile,
            "pressure_drop_pa": math.exp(values[-1]),
        }

    return predict_one, reconstruction


def reconstruct_models(config, *, repository):
    learned, reconstruction = _learned_model(config, repository)

    def analytical(inputs):
        values = analytic.predict(inputs)
        return {name: values[name] for name in exam.SHAPES}

    def batch(one):
        return lambda inputs: {key: one(case) for key, case in inputs.items()}

    return {
        "analytic-v1": batch(analytical),
        "learned-krr-v1": batch(learned),
    }, {
        "analytic-v1": {"kind": "ANALYTICAL_BASELINE"},
        "learned-krr-v1": reconstruction,
    }


def _campaign_policy(config, construction_identity_digest):
    if (
        type(construction_identity_digest) is not str
        or not construction_identity_digest.startswith("sha256:")
        or len(construction_identity_digest) != 71
    ):
        raise StudyError("construction_identity_digest_required")
    budgets = config["budgets"]
    resource_policy = {
        "cpus_per_execution": budgets["cpus_per_solver_execution"],
        "parallel_executions": budgets["parallel_solver_executions"],
        "timeout_seconds_per_execution": budgets["solver_timeout_seconds"],
        "artifact_retention": "all",
    }
    identity = {
        "study_id": config["study_id"],
        "construction_identity_digest": construction_identity_digest,
        "ledger_relative_path": (
            f".carbon-artifacts/{config['study_id']}-campaign.sqlite3"
        ),
        "initial_execution_limit": budgets["initial_solver_executions"],
        "retry_execution_limit": budgets["retry_reserve"],
        "total_execution_limit": budgets["hard_solver_execution_cap"],
        "max_retries_per_case": budgets["max_retries_per_case"],
        "retry_eligible_statuses": budgets["retry_eligible_statuses"],
        "resource_policy": resource_policy,
    }
    return {
        "schema": CAMPAIGN_SCHEMA,
        "campaign_id": experiment.digest(identity),
        **identity,
    }


def reference_plan(config, construction_identity_digest, *, case_ids=None, attempt=1):
    """Return the exact bounded run_batch plan; no solver is launched."""

    allowed = None if case_ids is None else set(case_ids)
    cases = []
    for design in config["designs"]:
        for condition in config["conditions"]:
            raw_id = f"decision-{design['design_id']}-{condition['scenario_id']}"
            if allowed is not None and raw_id not in allowed:
                continue
            cases.append(
                {
                    "case_id": raw_id,
                    "kind": "ordinary",
                    "inputs": domain.check_inputs(
                        {**design["values"], **condition["values"]}
                    ),
                    "options": {},
                }
            )
    if attempt not in (1, 2):
        raise StudyError("reference_attempt_outside_policy")
    campaign = _campaign_policy(config, construction_identity_digest)
    return {
        "schema": PLAN_SCHEMA,
        "batch": f"{config['study_id']}-cfd-attempt-{attempt}",
        "attempt": attempt,
        "solver_image": openfoam.IMAGE,
        "construction_identity_digest": construction_identity_digest,
        "campaign": campaign,
        "cases": cases,
    }


def reference_retry_plan(config, initial_directory):
    """Create the sole permitted retry plan from typed initial failures."""

    root = Path(initial_directory)
    actual = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    construction_identity_digest = actual.get("construction_identity_digest")
    expected = reference_plan(config, construction_identity_digest, attempt=1)
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
    failed = sorted(
        record["case_id"]
        for record in records
        if record.get("status") in RETRY_ELIGIBLE_STATUSES
    )
    if len(failed) > config["budgets"]["retry_reserve"]:
        raise StudyError(
            "retry_reserve_insufficient",
            f"{len(failed)} failures exceeds {config['budgets']['retry_reserve']}",
        )
    return reference_plan(
        config,
        construction_identity_digest,
        case_ids=failed,
        attempt=2,
    )


def fixture_reference(config):
    """Analytical pseudo-reference, structurally unable to count as CFD."""

    def source(jobs):
        return {
            job["case_id"]: {
                "status": "OK",
                "inputs": job["inputs"],
                "outputs": analytic.predict(job["inputs"]),
                "checks": {"fixture": True},
            }
            for job in jobs
        }

    return cd.analytical_fixture_reference(
        source,
        condition_budget=config["budgets"]["reference_session_condition_evaluations"],
        session_id=f"{config['study_id']}-analytical-fixture",
    )


def _artifact_manifest(case_directories, extra_files=()):
    rows = []
    total = 0
    for prefix, directory in case_directories:
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
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
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        rows.append({"path": relative, "bytes": size, "sha256": _sha256(path)})
    rows.sort(key=lambda row: row["path"])
    return rows, total


def _campaign_snapshot(root, plan, records):
    try:
        snapshot = json.loads(
            (Path(root) / "campaign-ledger.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise StudyError("campaign_ledger_snapshot_required", str(root)) from error
    campaign = plan["campaign"]
    if (
        snapshot.get("schema") != reference_campaign.SNAPSHOT_SCHEMA
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
    current = [row for row in executions if row.get("attempt") == attempt]
    by_case = {record["case_id"]: record for record in records}
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
    initial = sum(row.get("attempt") == 1 for row in executions)
    retries = sum(row.get("attempt") == 2 for row in executions)
    finished = sum(row.get("state") == "FINISHED" for row in executions)
    if accounting != {
        "attempted_executions": len(executions),
        "initial_attempts": initial,
        "retry_attempts": retries,
        "finished_executions": finished,
    }:
        raise StudyError("campaign_ledger_accounting", str(root))
    if (
        initial > campaign["initial_execution_limit"]
        or retries > campaign["retry_execution_limit"]
        or len(executions) > campaign["total_execution_limit"]
    ):
        raise StudyError("campaign_ledger_limit_exceeded", str(root))
    pairs = {(row.get("case_id"), row.get("attempt")) for row in executions}
    if len(pairs) != len(executions):
        raise StudyError("campaign_ledger_duplicate_execution", str(root))
    return snapshot


def import_counted_cfd(config, reference_directories):
    """Validate retained run_batch artifacts and return a counted session.

    Attempt 1 must contain the full frozen comparison set.  Attempt 2 may
    contain only cases that did not finish OK in attempt 1.  Every OK result
    requires its generated case, analysis, mesh, convergence/applicability
    checks, pinned image, run identity, and artifact manifest.
    """

    roots = [Path(path) for path in reference_directories]
    if not roots or len(roots) > 2:
        raise StudyError("one_initial_and_optional_retry_directory")
    first_plan = json.loads((roots[0] / "plan.json").read_text(encoding="utf-8"))
    construction_identity_digest = first_plan.get("construction_identity_digest")
    expected_initial = reference_plan(config, construction_identity_digest, attempt=1)
    expected_by_id = {case["case_id"]: case for case in expected_initial["cases"]}
    attempts = {case_id: [] for case_id in expected_by_id}
    total_records = 0
    campaign_wall_s = 0.0
    first_status = {}

    for index, root in enumerate(roots, start=1):
        plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
        host = json.loads((root / "host.json").read_text(encoding="utf-8"))
        completed = json.loads((root / "DONE.json").read_text(encoding="utf-8"))
        if plan.get("attempt") != index or plan.get("solver_image") != openfoam.IMAGE:
            raise StudyError("reference_plan_identity", str(root))
        if plan.get("campaign") != expected_initial["campaign"]:
            raise StudyError("reference_campaign_policy")
        ids = [case["case_id"] for case in plan.get("cases", [])]
        if index == 1 and plan != expected_initial:
            raise StudyError("initial_reference_plan_not_frozen")
        if index == 2:
            allowed = {
                case_id
                for case_id, status in first_status.items()
                if status in RETRY_ELIGIBLE_STATUSES
            }
            if not ids or not set(ids) <= allowed:
                raise StudyError("retry_plan_not_failed_subset")
            expected_retry = reference_plan(
                config,
                construction_identity_digest,
                case_ids=ids,
                attempt=2,
            )
            if plan != expected_retry:
                raise StudyError("retry_reference_plan_not_frozen")
        if host.get("cpus") != config["budgets"]["cpus_per_solver_execution"]:
            raise StudyError("reference_cpu_cap_mismatch")
        if host.get("parallel") != config["budgets"]["parallel_solver_executions"]:
            raise StudyError("reference_parallelism_mismatch")
        if host.get("timeout_s") != config["budgets"]["solver_timeout_seconds"]:
            raise StudyError("reference_timeout_mismatch")
        if host.get("keep") != "all" or host.get("solver_image") != openfoam.IMAGE:
            raise StudyError("reference_artifact_retention_required")
        if (
            completed.get("batch") != plan["batch"]
            or completed.get("cases") != len(ids)
            or type(completed.get("wall_s")) not in (int, float)
            or completed["wall_s"] < 0
        ):
            raise StudyError("reference_completion_record")
        campaign_wall_s += float(completed["wall_s"])
        records = [
            json.loads(line)
            for line in (root / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        if len(records) != len(ids) or {
            record.get("case_id") for record in records
        } != set(ids):
            raise StudyError("reference_records_not_exactly_plan")
        actual_counts = {}
        for record in records:
            status = record.get("status")
            actual_counts[status] = actual_counts.get(status, 0) + 1
        if completed.get("counts") != actual_counts:
            raise StudyError("reference_completion_counts")
        snapshot = _campaign_snapshot(root, plan, records)
        total_records += len(records)
        if total_records > config["budgets"]["hard_solver_execution_cap"]:
            raise StudyError("reference_execution_hard_cap_exceeded")
        for record in records:
            case_id = record["case_id"]
            expected = expected_by_id.get(case_id)
            if expected is None or record.get("inputs") != expected["inputs"]:
                raise StudyError("reference_inputs_not_frozen", case_id)
            if record.get("options", {}) != expected["options"]:
                raise StudyError("reference_options_not_frozen", case_id)
            attempts[case_id].append((index, root, host, record))
            if index == 1:
                first_status[case_id] = record.get("status")

    final_snapshot = snapshot
    if final_snapshot["accounting"]["attempted_executions"] != total_records:
        raise StudyError("campaign_ledger_final_attempt_count")

    normalized = {}
    for raw_id, expected in expected_by_id.items():
        history = attempts[raw_id]
        if not history:
            continue
        final_attempt, root, host, record = history[-1]
        if record.get("status") == "OK" and record.get("image") != openfoam.IMAGE:
            continue
        retained = []
        metadata_files = []
        artifacts_valid = True
        final_generated_mesh = None
        for attempt_number, attempt_root, _host, attempt_record in history:
            metadata_files.extend(
                (
                    f"attempt-{attempt_number}/batch/{name}",
                    attempt_root / name,
                )
                for name in ("plan.json", "host.json", "records.jsonl", "DONE.json")
            )
            metadata_files.append(
                (
                    f"attempt-{attempt_number}/batch/campaign-ledger.json",
                    attempt_root / "campaign-ledger.json",
                )
            )
            case_dir = attempt_root / "cases" / raw_id
            if not case_dir.is_dir():
                if attempt_record.get("status") == "FAILED_INFRA":
                    continue
                artifacts_valid = False
                break
            case_json = case_dir / "case.json"
            if not case_json.is_file():
                artifacts_valid = False
                break
            generated = json.loads(case_json.read_text(encoding="utf-8"))
            _files, expected_generated = openfoam.files(
                expected["inputs"], **expected["options"]
            )
            if generated != expected_generated or (
                attempt_record.get("mesh") is not None
                and generated.get("mesh") != attempt_record.get("mesh")
            ):
                artifacts_valid = False
                break
            if attempt_number == final_attempt:
                final_generated_mesh = generated.get("mesh")
            if attempt_record.get("status") == "OK":
                analysis_path = case_dir / "analysis.json"
                required = [case_dir / name for name in _REQUIRED_SOLVER_FILES]
                writes = (attempt_record.get("diagnostics") or {}).get("writes")
                if (
                    attempt_record.get("schema")
                    != "carbon.cold-plate.reference-record.v1"
                    or attempt_record.get("batch")
                    != f"{config['study_id']}-cfd-attempt-{attempt_number}"
                    or attempt_record.get("run") != "exit 0"
                    or not analysis_path.is_file()
                    or any(
                        not path.is_file() or path.stat().st_size == 0
                        for path in required
                    )
                    or type(writes) is not list
                    or not writes
                    or any(
                        not (case_dir / str(write) / region / "T").is_file()
                        for write in writes
                        for region in ("fluid", "solid")
                    )
                ):
                    artifacts_valid = False
                    break
                analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
                if (
                    analysis.get("outcome") != "OK"
                    or analysis.get("outputs") != attempt_record.get("outputs")
                    or analysis.get("checks") != attempt_record.get("checks")
                ):
                    artifacts_valid = False
                    break
            retained.append((f"attempt-{attempt_number}", case_dir))
        if not artifacts_valid:
            continue
        manifest, artifact_bytes = _artifact_manifest(retained, metadata_files)
        checks = record.get("checks") or {}
        convergence = {
            key: checks.get(key)
            for key in (
                "mass_imbalance_rel",
                "energy_balance_rel",
                "iteration_change_k",
                "iteration_change_pressure_rel",
            )
        }
        applicability = {
            key: checks.get(key) for key in ("fluid_min_c", "fluid_max_c", "re_outlet")
        }
        configuration = {
            "plan_entry": expected,
            "solver_image": openfoam.IMAGE,
            "commands": list(openfoam.COMMANDS),
            "hosts": [item[2] for item in history],
        }
        provenance = {
            "evidence_class": "COUNTED_CFD",
            "solver_image": openfoam.IMAGE,
            "configuration_digest": experiment.digest(configuration),
            "mesh_digest": experiment.digest(
                final_generated_mesh
                if final_generated_mesh is not None
                else record.get("mesh")
            ),
            "convergence_evidence_digest": experiment.digest(convergence),
            "applicability_evidence_digest": experiment.digest(applicability),
            "run_identity": f"{config['study_id']}:{raw_id}:attempt-{final_attempt}",
            "artifact_manifest_digest": experiment.digest(manifest),
            "artifact_count": len(manifest),
            "artifact_bytes": artifact_bytes,
            "execution_count": len(history),
            "retry_count": len(history) - 1,
            "wall_s": sum(float(item[3].get("wall_s", 0.0)) for item in history),
            "cpu_limit": int(host["cpus"]),
        }
        internal_id = cd._case_id(expected["inputs"])
        normalized[internal_id] = cd._seal_counted_record(
            cd._REFERENCE_SESSION_TOKEN,
            status=record.get("status", "REFERENCE_MISSING"),
            inputs=expected["inputs"],
            outputs=record.get("outputs"),
            checks=checks,
            provenance=provenance,
        )
    return cd.counted_cfd_reference(
        normalized,
        condition_budget=config["budgets"]["reference_session_condition_evaluations"],
        session_id=f"{config['study_id']}-counted-cfd",
        construction_identity_digest=construction_identity_digest,
        campaign_wall_s=campaign_wall_s,
    )


def _comparison_jobs(config):
    rows = []
    for design in config["designs"]:
        for condition in config["conditions"]:
            case = domain.check_inputs({**design["values"], **condition["values"]})
            rows.append(
                {
                    "case_id": cd._case_id(case),
                    "inputs": case,
                    "design_id": design["design_id"],
                    "scenario_id": condition["scenario_id"],
                    "group": condition["group"],
                }
            )
    return rows


def _reference_row(contract, job, record):
    verdict, quantities, status = cd._reference_verdict(contract, job, record)
    return {
        **job,
        "verdict": verdict,
        "reference_status": status,
        "reference": quantities,
    }


def _finite_comparator(config, freeze, contract, reference):
    jobs = _comparison_jobs(config)
    key = experiment.digest(
        {"freeze_digest": freeze["freeze_digest"], "purpose": "finite-comparator"}
    )
    records, accounting = reference.acquire(
        key, jobs, config["budgets"]["comparator_condition_evaluations"]
    )
    rows = [_reference_row(contract, job, records.get(job["case_id"])) for job in jobs]
    candidates = []
    designs = []
    for design in config["designs"]:
        evidence = [row for row in rows if row["design_id"] == design["design_id"]]
        verdict_counts = {
            verdict: sum(row["verdict"] == verdict for row in evidence)
            for verdict in cd.VERDICTS
        }
        if verdict_counts["INFEASIBLE"]:
            outcome = "CONFIRMED_INFEASIBLE"
        elif verdict_counts["FEASIBLE"] == len(evidence):
            outcome = "CONFIRMED_FEASIBLE"
        else:
            outcome = "UNRESOLVED"
        resolved = verdict_counts["REFERENCE_UNAVAILABLE"] == 0
        feasible = outcome == "CONFIRMED_FEASIBLE"
        worst = (
            max(row["reference"]["hydraulic_w"] for row in evidence)
            if feasible
            else None
        )
        item = {
            "design_id": design["design_id"],
            "geometry": design["values"],
            "proposal_outcome": outcome,
            "verdicts": verdict_counts,
            "resolved_all_conditions": resolved,
            "reference_feasible_all_conditions": feasible,
            "worst_reference_hydraulic_w": worst,
        }
        designs.append(item)
        if feasible:
            candidates.append((worst, design["design_id"], item))
    best_observed = min(candidates) if candidates else None
    unresolved = [item for item in designs if item["proposal_outcome"] == "UNRESOLVED"]
    if unresolved:
        comparator_status = "UNRESOLVED_COMPARISON_SET"
        best_complete = None
    elif best_observed is None:
        comparator_status = "COMPLETE_SET_NO_REFERENCE_FEASIBLE_DESIGN"
        best_complete = None
    else:
        comparator_status = "COMPLETE_FINITE_SET"
        best_complete = best_observed
    return {
        "definition": config["comparisons"]["reference_comparator"],
        "status": comparator_status,
        "coverage": {
            "designs": len(config["designs"]),
            "conditions_per_design": len(config["conditions"]),
            "condition_evidence": len(rows),
            "resolved_condition_evidence": sum(
                row["verdict"] != "REFERENCE_UNAVAILABLE" for row in rows
            ),
            "fully_resolved_designs": sum(
                item["resolved_all_conditions"] for item in designs
            ),
            "confirmed_infeasible_designs": sum(
                item["proposal_outcome"] == "CONFIRMED_INFEASIBLE" for item in designs
            ),
            "confirmed_feasible_designs": sum(
                item["proposal_outcome"] == "CONFIRMED_FEASIBLE" for item in designs
            ),
            "unresolved_designs": len(unresolved),
            "sufficiently_resolved_for_exact_finite_set_comparator": not unresolved,
        },
        "limitations": (
            "Best-known only within the declared finite eight-design, six-condition "
            "set and periodic-cell scope; it is not a global optimum."
        ),
        "accounting": accounting,
        "designs": designs,
        "best_observed_reference_feasible": (
            None if best_observed is None else best_observed[2]
        ),
        "best_reference_feasible_in_complete_set": (
            None if best_complete is None else best_complete[2]
        ),
        "rows": rows,
    }


def _construct_arm(
    config,
    freeze,
    adapter,
    model_name,
    infer,
    method_name,
    construction_root,
    out,
):
    identity = next(
        row for row in freeze["search_freeze"]["panel"] if row["member"] == model_name
    )
    method = freeze["search_freeze"]["methods"][method_name]
    neutral = experiment.neutral_request(
        adapter,
        mode=cd.MODE,
        model={key: identity[key] for key in ("member", "recipe_digest", "seed")},
        designs=_designs(config),
        conditions=_conditions(config),
        query_budget=config["budgets"]["model_query_points_per_arm"],
        verification_budget=config["budgets"][
            "verification_condition_evaluations_per_arm"
        ],
        method={
            "name": method_name,
            "code_digest": experiment.digest(freeze["search_freeze"]["code"]),
            "configuration_digest": method["configuration_digest"],
        },
        seed_policy=freeze["search_freeze"]["seed_policy"],
    )
    request, space = adapter.request(neutral)
    oracle = adapter.oracle(request, space, infer)
    started = time.perf_counter()
    if method_name == "fixed_grid":
        selections = adapter.baseline(oracle, request, space)
    else:
        selections = methods.run(
            method["method"], method["parameters"], adapter.view(request, space), oracle
        )
    search_s = time.perf_counter() - started
    commitment = adapter.commit(request, selections, oracle, out)
    elapsed = time.perf_counter() - started

    predicted = {
        tuple(row["point"]): row["quantities"]
        for row in oracle.log
        if row["status"] == "OK"
    }
    scenario_rows = []
    if selections:
        design = tuple(selections[0][name] for name in cd.DESIGN_VARIABLES)
        for entry in config["conditions"]:
            condition = tuple(entry["values"][name] for name in cd.CONDITION_VARIABLES)
            case = domain.check_inputs(
                {
                    **{name: selections[0][name] for name in cd.DESIGN_VARIABLES},
                    **entry["values"],
                }
            )
            scenario_rows.append(
                {
                    "case_id": cd._case_id(case),
                    "scenario_id": entry["scenario_id"],
                    "group": entry["group"],
                    "condition": entry["values"],
                    "selected_geometry": {
                        name: selections[0][name] for name in cd.DESIGN_VARIABLES
                    },
                    "operating_control": {
                        "policy": config["scenario"]["control_policy"]["name"],
                        "total_flow_lpm": selections[0]["flow_lpm_per_kw"]
                        * entry["values"]["heat_load_w"]
                        / 1000.0,
                    },
                    "prediction": predicted.get((*design, *condition)),
                    "engineering_cost": {
                        "quantity": "hydraulic_power",
                        "unit": "W",
                        "predicted": predicted.get((*design, *condition), {}).get(
                            "hydraulic_w"
                        ),
                    },
                }
            )
    commitment_document = commitment.document
    commitment_path = commitment.path
    return {
        "arm_id": f"{model_name}/{method_name}",
        "model": model_name,
        "method": method_name,
        "declared_query_budget": oracle.budget,
        "model_query_attempts": oracle.used,
        "model_query_successes": oracle.successful,
        "search_wall_s": search_s,
        "model_inference_wall_s": oracle.elapsed,
        "construction_wall_s": elapsed,
        "selection": selections[0] if selections else None,
        "commitment": {
            "relative_path": commitment_path.relative_to(construction_root).as_posix(),
            "commitment_digest": commitment_document["commitment_digest"],
            "file_sha256": "sha256:" + _sha256(commitment_path),
            "status": commitment_document["status"],
        },
        "predicted_scenarios": scenario_rows,
    }


def _construction_identity(freeze_digest, arms):
    return {
        "freeze_digest": freeze_digest,
        "commitments": [
            {
                "arm_id": arm["arm_id"],
                "commitment_digest": arm["commitment"]["commitment_digest"],
                "file_sha256": arm["commitment"]["file_sha256"],
                "status": arm["commitment"]["status"],
                "selection": arm["selection"],
            }
            for arm in sorted(arms, key=lambda item: item["arm_id"])
        ],
    }


def construct(config, *, repository, output):
    """Freeze, reconstruct, search, and commit without reference access."""

    repository = Path(repository)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    freeze = build_freeze(config, repository=repository)
    _write_json(output / "freeze.json", freeze)
    contract = freeze["decision_contract"]
    adapter = cd.adapter(contract)
    models, reconstruction = reconstruct_models(config, repository=repository)
    _write_json(output / "reconstruction.json", reconstruction)
    arms = []
    for model_name in config["models"]:
        for method_name in config["methods"]:
            arms.append(
                _construct_arm(
                    config,
                    freeze,
                    adapter,
                    model_name,
                    models[model_name],
                    method_name,
                    output,
                    output / "commitments" / model_name / method_name,
                )
            )
    expected_arm_ids = {
        f"{model_name}/{method_name}"
        for model_name in config["models"]
        for method_name in config["methods"]
    }
    if {arm["arm_id"] for arm in arms} != expected_arm_ids:
        raise StudyError("construction_arm_set")
    identity = _construction_identity(freeze["freeze_digest"], arms)
    body = {
        "schema": CONSTRUCTION_SCHEMA,
        "study_id": config["study_id"],
        "state": "ALL_ARMS_COMMITTED_BEFORE_REFERENCE",
        "freeze_digest": freeze["freeze_digest"],
        "construction_identity_digest": experiment.digest(identity),
        "reconstruction_file_sha256": "sha256:"
        + _sha256(output / "reconstruction.json"),
        "construction_wall_s": time.perf_counter() - started,
        "arms": arms,
    }
    document = {**body, "construction_digest": experiment.digest(body)}
    # This completion artifact is written last.  Evaluation refuses a partial
    # directory even if some individual commitments already exist.
    _write_json(output / "construction.json", document)
    return document


def load_construction(config, *, repository, directory):
    """Validate the complete construction artifact before any reference read."""

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
        or construction.get("state") != "ALL_ARMS_COMMITTED_BEFORE_REFERENCE"
        or construction.get("freeze_digest") != freeze["freeze_digest"]
        or construction.get("construction_digest") != experiment.digest(body)
        or construction.get("reconstruction_file_sha256")
        != "sha256:" + _sha256(directory / "reconstruction.json")
    ):
        raise StudyError("construction_manifest_invalid")
    arms = construction.get("arms")
    if type(arms) is not list:
        raise StudyError("construction_arms")
    expected_arm_ids = {
        f"{model_name}/{method_name}"
        for model_name in config["models"]
        for method_name in config["methods"]
    }
    if (
        len(arms) != len(expected_arm_ids)
        or {arm.get("arm_id") for arm in arms if type(arm) is dict} != expected_arm_ids
    ):
        raise StudyError("construction_arm_set")
    identity = _construction_identity(freeze["freeze_digest"], arms)
    if construction.get("construction_identity_digest") != experiment.digest(identity):
        raise StudyError("construction_identity_digest_mismatch")

    restored = []
    # Restore every commitment before returning any object that evaluation can
    # use.  A missing final arm therefore prevents the first reference acquire.
    for arm in sorted(arms, key=lambda item: item["arm_id"]):
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
                "complete_construction_artifact_required", arm["arm_id"]
            ) from error
        document = commitment.document
        if (
            document["status"] != manifest["status"]
            or (document["selections"][0] if document["selections"] else None)
            != arm["selection"]
        ):
            raise StudyError("construction_commitment_manifest_mismatch", arm["arm_id"])
        restored.append((arm, commitment))
    return freeze, construction, reconstruction, restored


def _evaluate_arm(config, adapter, construction_arm, commitment, reference):
    started = time.perf_counter()
    verification = adapter.verify(commitment, reference)
    by_case = {row["case_id"]: row for row in verification["rows"]}
    scenarios = []
    for predicted in construction_arm["predicted_scenarios"]:
        reference_row = by_case[predicted["case_id"]]
        scenarios.append(
            {
                **predicted,
                "reference": reference_row["reference"],
                "reference_verdict": reference_row["verdict"],
                "reference_status": reference_row["reference_status"],
                "engineering_cost": {
                    **predicted["engineering_cost"],
                    "reference": (
                        reference_row["reference"]["hydraulic_w"]
                        if reference_row["reference"] is not None
                        else None
                    ),
                },
            }
        )
    evaluation_wall_s = time.perf_counter() - started
    return {
        **construction_arm,
        "status": verification["status"],
        "proposal_outcome": verification["proposal_outcome"],
        "verification": verification,
        "scenarios": scenarios,
        "evaluation_wall_s": evaluation_wall_s,
        "end_to_end_wall_s": construction_arm["construction_wall_s"]
        + evaluation_wall_s,
    }


def _attach_regret(arm, comparator):
    outcome = arm["proposal_outcome"]
    if outcome == "ABSTAIN":
        arm["regret"] = {"status": "ABSTAIN", "value_w": None}
        return
    if outcome == "CONFIRMED_INFEASIBLE":
        arm["regret"] = {"status": "INFEASIBLE_SELECTION", "value_w": None}
        return
    if outcome == "UNRESOLVED":
        arm["regret"] = {"status": "REFERENCE_UNRESOLVED", "value_w": None}
        return
    worst = max(row["reference"]["hydraulic_w"] for row in arm["scenarios"])
    best_observed = comparator["best_observed_reference_feasible"]
    best_complete = comparator["best_reference_feasible_in_complete_set"]
    if comparator["status"] == "UNRESOLVED_COMPARISON_SET":
        arm["regret"] = {
            "status": "COMPARATOR_UNRESOLVED_BEST_OBSERVED_DIFFERENCE_ONLY",
            "value_w": None,
            "selected_worst_reference_hydraulic_w": worst,
            "difference_from_best_observed_w": (
                None
                if best_observed is None
                else worst - best_observed["worst_reference_hydraulic_w"]
            ),
            "best_observed_reference_feasible_design_id": (
                None if best_observed is None else best_observed["design_id"]
            ),
        }
        return
    if best_complete is None:
        arm["regret"] = {
            "status": "NO_REFERENCE_FEASIBLE_COMPARATOR",
            "value_w": None,
            "selected_worst_reference_hydraulic_w": worst,
        }
        return
    arm["regret"] = {
        "status": "DEFINED_FINITE_SET",
        "value_w": worst - best_complete["worst_reference_hydraulic_w"],
        "selected_worst_reference_hydraulic_w": worst,
        "comparator_worst_reference_hydraulic_w": best_complete[
            "worst_reference_hydraulic_w"
        ],
        "comparator_design_id": best_complete["design_id"],
    }


def _arm_metrics(arms):
    proposal_arms = [arm for arm in arms if arm["proposal_outcome"] != "ABSTAIN"]
    outcomes = {
        outcome: sum(arm["proposal_outcome"] == outcome for arm in arms)
        for outcome in cd.PROPOSAL_OUTCOMES
    }
    false_proposals = [
        arm
        for arm in proposal_arms
        if arm["proposal_outcome"] == "CONFIRMED_INFEASIBLE"
    ]
    all_rows = [row for arm in proposal_arms for row in arm["scenarios"]]
    unavailable = [
        row for row in all_rows if row["reference_verdict"] == "REFERENCE_UNAVAILABLE"
    ]
    unavailable_statuses = {}
    for row in unavailable:
        status = row["reference_status"]
        unavailable_statuses[status] = unavailable_statuses.get(status, 0) + 1
    unique_rows = {}
    for row in all_rows:
        evidence = {
            key: row[key]
            for key in (
                "case_id",
                "scenario_id",
                "group",
                "selected_geometry",
                "reference_verdict",
                "reference_status",
                "reference",
            )
        }
        previous = unique_rows.setdefault(row["case_id"], evidence)
        if previous != evidence:
            raise StudyError("reused_reference_case_disagrees", row["case_id"])

    groups = {}
    for group in GROUPS:
        rows = [row for row in all_rows if row["group"] == group]
        unique = [row for row in unique_rows.values() if row["group"] == group]
        groups[group] = {
            "arm_condition_uses": len(rows),
            "unique_design_condition_reference_cases": len(unique),
            "evidence_reuses": len(rows) - len(unique),
            "unique_reference_available": sum(
                row["reference_verdict"] != "REFERENCE_UNAVAILABLE" for row in unique
            ),
            "unique_reference_confirmed_feasible": sum(
                row["reference_verdict"] == "FEASIBLE" for row in unique
            ),
            "unique_reference_confirmed_infeasible": sum(
                row["reference_verdict"] == "INFEASIBLE" for row in unique
            ),
            "unique_reference_unavailable": sum(
                row["reference_verdict"] == "REFERENCE_UNAVAILABLE" for row in unique
            ),
        }
    return {
        "arms": len(arms),
        "proposal_outcomes": outcomes,
        "abstentions": outcomes["ABSTAIN"],
        "abstention_rate": outcomes["ABSTAIN"] / len(arms),
        "decision_coverage_count": outcomes["CONFIRMED_FEASIBLE"]
        + outcomes["CONFIRMED_INFEASIBLE"],
        "decision_coverage_denominator": len(arms),
        "decision_coverage": (
            outcomes["CONFIRMED_FEASIBLE"] + outcomes["CONFIRMED_INFEASIBLE"]
        )
        / len(arms),
        "false_feasible_proposals": len(false_proposals),
        "false_feasible_proposal_denominator": len(proposal_arms),
        "arm_condition_uses": len(all_rows),
        "unique_selected_design_condition_reference_cases": len(unique_rows),
        "selected_reference_evidence_reuses": len(all_rows) - len(unique_rows),
        "unique_selected_reference_verdicts": {
            verdict: sum(
                row["reference_verdict"] == verdict for row in unique_rows.values()
            )
            for verdict in cd.VERDICTS
        },
        "unavailable_or_invalid_reference_evidence": len(unavailable),
        "unavailable_reference_statuses": unavailable_statuses,
        "worst_case_reference_hydraulic_w_for_feasible_proposals": {
            arm["arm_id"]: (
                max(row["reference"]["hydraulic_w"] for row in arm["scenarios"])
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
                "design-condition evidence; arm and condition uses are not independent samples."
            ),
            "future_uncertainty_requirement": (
                "An approved sampling design and a justified unit of independent observation."
            ),
        },
        "groups": groups,
    }


def _contrast(arms_by_id, pair):
    left, right = (arms_by_id[name] for name in pair)
    return {
        "left": left["arm_id"],
        "right": right["arm_id"],
        "same_declared_query_budget": left["declared_query_budget"]
        == right["declared_query_budget"],
        "query_attempt_difference_right_minus_left": right["model_query_attempts"]
        - left["model_query_attempts"],
        "selected_geometry_same": (
            left["selection"] is not None
            and right["selection"] is not None
            and all(
                left["selection"][name] == right["selection"][name]
                for name in cd.DESIGN_VARIABLES
            )
        ),
        "left_regret": left["regret"],
        "right_regret": right["regret"],
    }


def _attach_baseline_comparisons(arms):
    baseline = next(arm for arm in arms if arm["arm_id"] == "analytic-v1/fixed_grid")
    baseline_rows = {row["scenario_id"]: row for row in baseline["scenarios"]}
    for arm in arms:
        same_geometry = (
            arm["selection"] is not None
            and baseline["selection"] is not None
            and all(
                arm["selection"][name] == baseline["selection"][name]
                for name in cd.DESIGN_VARIABLES
            )
        )
        arm["baseline_comparison"] = {
            "baseline_arm": baseline["arm_id"],
            "selected_geometry_same": same_geometry,
        }
        for row in arm["scenarios"]:
            baseline_row = baseline_rows.get(row["scenario_id"])
            row["baseline_comparison"] = {
                "baseline_arm": baseline["arm_id"],
                "selected_geometry_same": same_geometry,
                "predicted_die_margin_delta_c": (
                    row["prediction"]["die_margin_c"]
                    - baseline_row["prediction"]["die_margin_c"]
                    if baseline_row is not None
                    else None
                ),
                "predicted_hydraulic_margin_delta_w": (
                    row["prediction"]["hydraulic_margin_w"]
                    - baseline_row["prediction"]["hydraulic_margin_w"]
                    if baseline_row is not None
                    else None
                ),
            }


def _markdown(result):
    lines = [
        "# AI accelerator cooling decision study",
        "",
        f"Evidence class: **{result['evidence_class']}**. Material: **DEVELOPMENT**.",
        "",
        "This study is synthetic and remains inside the periodic straight-channel cell. It is not customer acceptance, scientific qualification, production qualification, or a global-optimality claim.",
        "",
        "## Arms",
        "",
        "| Arm | Selection | Queries | Proposal outcome | Reference verdicts | Regret status | Exact regret (W) | Best-observed difference (W) |",
        "|---|---|---:|---|---|---|---:|---:|",
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
        verdicts = arm["verification"]["verdicts"]
        regret = arm["regret"]
        lines.append(
            f"| {arm['arm_id']} | `{selection}` | {arm['model_query_attempts']} | {arm['proposal_outcome']} | `{verdicts}` | {regret['status']} | {regret['value_w'] if regret['value_w'] is not None else 'N/A'} | {regret.get('difference_from_best_observed_w', 'N/A')} |"
        )
    lines += [
        "",
        "## Finite-set comparator",
        "",
        result["comparator"]["limitations"],
        "",
        f"Comparator status: **{result['comparator']['status']}**.",
        "",
        "Best observed reference-feasible design: `"
        + json.dumps(
            result["comparator"]["best_observed_reference_feasible"],
            sort_keys=True,
        )
        + "`",
        "",
        "Best reference-feasible design in a sufficiently resolved complete set: `"
        + json.dumps(
            result["comparator"]["best_reference_feasible_in_complete_set"],
            sort_keys=True,
        )
        + "`",
        "",
        "## Decision metrics",
        "",
        "```json",
        json.dumps(result["metrics"], indent=2, sort_keys=True),
        "```",
        "",
        "## Cost and limits",
        "",
        "```json",
        json.dumps(result["cost"], indent=2, sort_keys=True),
        "```",
        "",
        "The fixed pilot is descriptive. The four arms share one decision problem and may reuse the same reference cases; no population-level reliability or generalisation confidence is claimed. A future uncertainty estimate requires an approved sampling design and a justified unit of independent observation.",
        "",
        "Representative and boundary-stress results remain separate; no combined weighting or pass threshold is asserted.",
        "",
        "## Interpretation",
        "",
        result["conclusion"]["observed_outcome"],
        "",
        "The pilot asks whether selected designs satisfy the registered constraints according to reference CFD, how they compare with the finite-set comparator, whether registered search methods reduce queries or cost, and whether the learned model changes or improves the decision in this particular study.",
        "",
        "This evidence does not establish: "
        + result["conclusion"]["does_not_establish"],
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
    """Evaluate a complete immutable construction artifact against references."""

    repository = Path(repository)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    freeze, construction, reconstruction, restored = load_construction(
        config, repository=repository, directory=construction_directory
    )
    if (
        reference.evidence_class == "COUNTED_CFD"
        and reference.construction_identity_digest
        != construction["construction_identity_digest"]
    ):
        raise StudyError("reference_construction_identity_mismatch")
    contract = freeze["decision_contract"]
    adapter = cd.adapter(contract)
    # load_construction restores every required commitment before the first
    # reference acquire.  Proposal evaluation precedes comparator evaluation.
    arms = [
        _evaluate_arm(config, adapter, arm, commitment, reference)
        for arm, commitment in restored
    ]
    comparator = _finite_comparator(config, freeze, contract, reference)
    for arm in arms:
        _attach_regret(arm, comparator)
    _attach_baseline_comparisons(arms)
    arms_by_id = {arm["arm_id"]: arm for arm in arms}
    evaluation_wall = time.perf_counter() - started
    metrics = _arm_metrics(arms)
    reference_metrics = reference.metrics()
    selection_keys = {
        (
            None
            if arm["selection"] is None
            else tuple(arm["selection"][name] for name in cd.DESIGN_VARIABLES)
        )
        for arm in arms
    }
    all_arms_agree = len(selection_keys) == 1
    observed_outcome = (
        "All four registered model/search arms selected the same geometry in this "
        "fixed pilot. This is agreement, not evidence of a learned-model "
        "design-quality advantage."
        if all_arms_agree
        else "The registered model/search arms selected different geometries in this fixed pilot."
    )
    budgets = config["budgets"]
    result = {
        "schema": RESULT_SCHEMA,
        "study_id": config["study_id"],
        "material": cd.MATERIAL,
        "scope": cd.SCOPE,
        "evidence_label": evidence_label,
        "evidence_class": reference.evidence_class,
        "freeze_digest": freeze["freeze_digest"],
        "construction_digest": construction["construction_digest"],
        "construction_identity_digest": construction["construction_identity_digest"],
        "construction_state": construction["state"],
        "control_policy": config["scenario"]["control_policy"],
        "arms": arms,
        "comparisons": {
            "model_value": _contrast(arms_by_id, config["comparisons"]["model_value"]),
            "search_method_value": _contrast(
                arms_by_id, config["comparisons"]["search_method_value"]
            ),
        },
        "comparator": comparator,
        "metrics": metrics,
        "cost": {
            "construction_wall_s": construction["construction_wall_s"],
            "evaluation_wall_s": evaluation_wall,
            "study_end_to_end_wall_s": construction["construction_wall_s"]
            + evaluation_wall,
            "model_query_attempts": sum(arm["model_query_attempts"] for arm in arms),
            "model_inference_wall_s": sum(
                arm["model_inference_wall_s"] for arm in arms
            ),
            "reference_condition_evaluations": reference_metrics[
                "condition_evaluations"
            ],
            "reference_executions": reference_metrics["solver_executions"],
            "reference_retries": reference_metrics["retries"],
            "reference_solver_wall_s": reference_metrics["solver_wall_s"],
            "reference_campaign_wall_s": reference_metrics["campaign_wall_s"],
            "reference_cpu_limit_per_execution": config["budgets"][
                "cpus_per_solver_execution"
            ],
            "compute_envelope": {
                "estimated_initial_core_hours": budgets["estimated_initial_core_hours"],
                "estimated_hard_cap_core_hours": budgets[
                    "estimated_hard_cap_core_hours"
                ],
                "configured_initial_allocated_core_hour_ceiling": budgets[
                    "configured_initial_allocated_core_hour_ceiling"
                ],
                "configured_hard_cap_allocated_core_hour_ceiling": budgets[
                    "configured_hard_cap_allocated_core_hour_ceiling"
                ],
                "initial_solver_executions": budgets["initial_solver_executions"],
                "retry_reserve": budgets["retry_reserve"],
                "hard_solver_execution_cap": budgets["hard_solver_execution_cap"],
                "accounting_description": config["compute_accounting"],
            },
            "monetary_cost_usd": None,
            "monetary_cost_status": "NO_OWNER_APPROVED_RESOURCE_RATE",
            "training_and_reconstruction": reconstruction,
            "per_decision_wall_s_by_arm": {
                arm["arm_id"]: arm["end_to_end_wall_s"] for arm in arms
            },
        },
        "analysis_policy": config["analysis"],
        "claims": config["claims"],
        "conclusion": {
            "pilot_questions": [
                "Do selected designs satisfy the registered constraints according to reference CFD?",
                "How do selected designs compare with the finite-set reference comparator?",
                "Do registered search methods reduce model queries or computational cost?",
                "Does the learned model change or improve the decision in this particular study?",
            ],
            "all_arms_selected_same_geometry": all_arms_agree,
            "observed_outcome": observed_outcome,
            "establishes": (
                "Only the observed DEVELOPMENT results for the frozen finite set, "
                "models, methods, budgets, and evidence class."
            ),
            "does_not_establish": (
                "Customer acceptance, global optimality, full cold-plate behavior, "
                "transient/controller performance, scientific qualification, or LIVE readiness."
            ),
            "next_expansion": (
                "Run the capped counted-CFD plan after owner compute authorization; "
                "expand physical scope only after reviewing finite-set failure modes."
            ),
        },
    }
    _write_json(output / "result.json", result)
    (output / "report.md").write_text(_markdown(result), encoding="utf-8")
    return result


def run(config, *, repository, reference, output, evidence_label):
    """Compatibility wrapper that preserves the construction/evaluation seam."""

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    construct(config, repository=repository, output=output / "construction")
    return evaluate(
        config,
        repository=repository,
        construction_directory=output / "construction",
        reference=reference,
        output=output / "evaluation",
        evidence_label=evidence_label,
    )
