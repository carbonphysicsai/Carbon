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

from . import analytic, domain, exam, openfoam
from . import customer_decision as cd

CONFIG_SCHEMA = "carbon.cold-plate.decision-study-config.v1"
FREEZE_SCHEMA = "carbon.cold-plate.decision-study-freeze.v1"
RESULT_SCHEMA = "carbon.cold-plate.decision-study-result.v1"
PLAN_SCHEMA = "carbon.cold-plate.decision-reference-plan.v1"
GROUPS = ("REPRESENTATIVE", "BOUNDARY_STRESS")
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
        },
        "budget_fields",
    )
    analysis = _exact(
        config["analysis"],
        {
            "confidence_interval",
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
        analysis["confidence_interval"] != "Wilson 95% binomial interval"
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
    ):
        if type(budgets[name]) is not int or budgets[name] <= 0:
            raise StudyError("positive_integer_budget", name)
    if not math.isclose(
        budgets["estimated_initial_core_hours"],
        budgets["estimated_core_hours_per_case"] * budgets["initial_solver_executions"],
    ) or not math.isclose(
        budgets["estimated_hard_cap_core_hours"],
        budgets["estimated_core_hours_per_case"] * budgets["hard_solver_execution_cap"],
    ):
        raise StudyError("estimated_compute_arithmetic")

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


def reference_plan(config, *, case_ids=None, attempt=1):
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
    return {
        "schema": PLAN_SCHEMA,
        "batch": f"{config['study_id']}-cfd-attempt-{attempt}",
        "attempt": attempt,
        "solver_image": openfoam.IMAGE,
        "hard_solver_execution_cap": config["budgets"]["hard_solver_execution_cap"],
        "cases": cases,
    }


def reference_retry_plan(config, initial_directory):
    """Create the sole permitted retry plan from typed initial failures."""

    root = Path(initial_directory)
    expected = reference_plan(config, attempt=1)
    actual = json.loads((root / "plan.json").read_text(encoding="utf-8"))
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
    failed = sorted(
        record["case_id"] for record in records if record.get("status") != "OK"
    )
    if len(failed) > config["budgets"]["retry_reserve"]:
        raise StudyError(
            "retry_reserve_insufficient",
            f"{len(failed)} failures exceeds {config['budgets']['retry_reserve']}",
        )
    return reference_plan(config, case_ids=failed, attempt=2)


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
    expected_initial = reference_plan(config, attempt=1)
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
        if (
            plan.get("hard_solver_execution_cap")
            != config["budgets"]["hard_solver_execution_cap"]
        ):
            raise StudyError("reference_plan_cap")
        ids = [case["case_id"] for case in plan.get("cases", [])]
        if index == 1 and plan != expected_initial:
            raise StudyError("initial_reference_plan_not_frozen")
        if index == 2:
            allowed = {
                case_id for case_id, status in first_status.items() if status != "OK"
            }
            if not ids or not set(ids) <= allowed:
                raise StudyError("retry_plan_not_failed_subset")
            expected_retry = reference_plan(config, case_ids=ids, attempt=2)
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
        resolved = all(row["verdict"] != "REFERENCE_UNAVAILABLE" for row in evidence)
        feasible = resolved and all(row["verdict"] == "FEASIBLE" for row in evidence)
        worst = (
            max(row["reference"]["hydraulic_w"] for row in evidence)
            if feasible
            else None
        )
        item = {
            "design_id": design["design_id"],
            "geometry": design["values"],
            "resolved_all_conditions": resolved,
            "reference_feasible_all_conditions": feasible,
            "worst_reference_hydraulic_w": worst,
        }
        designs.append(item)
        if feasible:
            candidates.append((worst, design["design_id"], item))
    best = min(candidates) if candidates else None
    return {
        "definition": config["comparisons"]["reference_comparator"],
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
        },
        "limitations": (
            "Best-known only within the declared finite eight-design, six-condition "
            "set and periodic-cell scope; it is not a global optimum."
        ),
        "accounting": accounting,
        "designs": designs,
        "best": None if best is None else best[2],
        "rows": rows,
    }


def _arm(
    config, freeze, contract, adapter, model_name, infer, method_name, reference, out
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
    result = adapter.verify(commitment, reference)
    elapsed = time.perf_counter() - started

    predicted = {
        tuple(row["point"]): row["quantities"]
        for row in oracle.log
        if row["status"] == "OK"
    }
    scenario_rows = []
    if selections:
        design = tuple(selections[0][name] for name in cd.DESIGN_VARIABLES)
        by_case = {row["case_id"]: row for row in result["rows"]}
        for entry in config["conditions"]:
            condition = tuple(entry["values"][name] for name in cd.CONDITION_VARIABLES)
            case = domain.check_inputs(
                {
                    **{name: selections[0][name] for name in cd.DESIGN_VARIABLES},
                    **entry["values"],
                }
            )
            reference_row = by_case[cd._case_id(case)]
            scenario_rows.append(
                {
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
                    "reference": reference_row["reference"],
                    "reference_verdict": reference_row["verdict"],
                    "reference_status": reference_row["reference_status"],
                    "engineering_cost": {
                        "quantity": "hydraulic_power",
                        "unit": "W",
                        "predicted": predicted.get((*design, *condition), {}).get(
                            "hydraulic_w"
                        ),
                        "reference": (
                            reference_row["reference"]["hydraulic_w"]
                            if reference_row["reference"] is not None
                            else None
                        ),
                    },
                }
            )
    return {
        "arm_id": f"{model_name}/{method_name}",
        "model": model_name,
        "method": method_name,
        "declared_query_budget": oracle.budget,
        "model_query_attempts": oracle.used,
        "model_query_successes": oracle.successful,
        "search_wall_s": search_s,
        "model_inference_wall_s": oracle.elapsed,
        "end_to_end_wall_s": elapsed,
        "selection": selections[0] if selections else None,
        "status": result["status"],
        "verification": result,
        "scenarios": scenario_rows,
    }


def _wilson(successes, trials):
    if trials == 0:
        return None
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = (
        z
        * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    low = max(0.0, center - half)
    return {
        "low": 0.0 if low < 1e-15 else low,
        "high": min(1.0, center + half),
    }


def _attach_regret(arm, comparator):
    best = comparator["best"]
    if arm["selection"] is None:
        arm["regret"] = {"status": "ABSTAIN", "value_w": None}
        return
    verdicts = arm["verification"]["verdicts"]
    if verdicts["REFERENCE_UNAVAILABLE"]:
        arm["regret"] = {"status": "REFERENCE_UNRESOLVED", "value_w": None}
        return
    if verdicts["INFEASIBLE"]:
        arm["regret"] = {"status": "INFEASIBLE_SELECTION", "value_w": None}
        return
    if best is None:
        arm["regret"] = {"status": "COMPARATOR_UNRESOLVED", "value_w": None}
        return
    worst = max(row["reference"]["hydraulic_w"] for row in arm["scenarios"])
    arm["regret"] = {
        "status": "DEFINED_FINITE_SET",
        "value_w": worst - best["worst_reference_hydraulic_w"],
        "selected_worst_reference_hydraulic_w": worst,
        "comparator_worst_reference_hydraulic_w": best["worst_reference_hydraulic_w"],
    }


def _arm_metrics(arms):
    proposal_trials = [arm for arm in arms if arm["selection"] is not None]
    resolved_proposals = [
        arm
        for arm in proposal_trials
        if arm["verification"]["verdicts"]["REFERENCE_UNAVAILABLE"] == 0
    ]
    false_proposals = [
        arm
        for arm in resolved_proposals
        if arm["verification"]["verdicts"]["INFEASIBLE"] > 0
    ]
    condition_trials = [
        row
        for arm in proposal_trials
        for row in arm["scenarios"]
        if row["reference_verdict"] != "REFERENCE_UNAVAILABLE"
    ]
    false_conditions = [
        row for row in condition_trials if row["reference_verdict"] == "INFEASIBLE"
    ]
    unavailable = [
        row
        for arm in proposal_trials
        for row in arm["scenarios"]
        if row["reference_verdict"] == "REFERENCE_UNAVAILABLE"
    ]
    unavailable_statuses = {}
    for row in unavailable:
        status = row["reference_status"]
        unavailable_statuses[status] = unavailable_statuses.get(status, 0) + 1
    groups = {}
    for group in GROUPS:
        rows = [
            row
            for arm in proposal_trials
            for row in arm["scenarios"]
            if row["group"] == group
        ]
        available = [
            row for row in rows if row["reference_verdict"] != "REFERENCE_UNAVAILABLE"
        ]
        false = [row for row in available if row["reference_verdict"] == "INFEASIBLE"]
        groups[group] = {
            "proposed_condition_decisions": len(rows),
            "reference_available": len(available),
            "reference_confirmed_feasible": sum(
                row["reference_verdict"] == "FEASIBLE" for row in available
            ),
            "false_feasible": len(false),
            "false_feasible_denominator": len(available),
            "false_feasible_wilson_95": _wilson(len(false), len(available)),
        }
    return {
        "arms": len(arms),
        "abstentions": len(arms) - len(proposal_trials),
        "abstention_rate": (len(arms) - len(proposal_trials)) / len(arms),
        "decision_coverage": len(resolved_proposals) / len(arms),
        "resolved_proposals": len(resolved_proposals),
        "false_feasible_proposals": len(false_proposals),
        "false_feasible_proposal_denominator": len(resolved_proposals),
        "false_feasible_proposal_wilson_95": _wilson(
            len(false_proposals), len(resolved_proposals)
        ),
        "false_feasible_condition_decisions": len(false_conditions),
        "false_feasible_condition_denominator": len(condition_trials),
        "false_feasible_condition_wilson_95": _wilson(
            len(false_conditions), len(condition_trials)
        ),
        "unavailable_or_invalid_reference_evidence": len(unavailable),
        "unavailable_reference_statuses": unavailable_statuses,
        "worst_case_reference_hydraulic_w_for_feasible_proposals": {
            arm["arm_id"]: (
                max(row["reference"]["hydraulic_w"] for row in arm["scenarios"])
                if arm["selection"] is not None
                and arm["verification"]["verdicts"]["FEASIBLE"] == len(arm["scenarios"])
                else None
            )
            for arm in arms
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
        "| Arm | Selection | Queries | Reference verdicts | Regret status | Regret (W) |",
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
        verdicts = arm["verification"]["verdicts"]
        regret = arm["regret"]
        lines.append(
            f"| {arm['arm_id']} | `{selection}` | {arm['model_query_attempts']} | `{verdicts}` | {regret['status']} | {regret['value_w'] if regret['value_w'] is not None else 'N/A'} |"
        )
    lines += [
        "",
        "## Finite-set comparator",
        "",
        result["comparator"]["limitations"],
        "",
        "Best comparator: `"
        + json.dumps(result["comparator"]["best"], sort_keys=True)
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
        "Representative and boundary-stress results remain separate; no combined weighting or pass threshold is asserted.",
        "",
    ]
    return "\n".join(lines)


def run(config, *, repository, reference, output, evidence_label):
    """Run the frozen comparison and persist inspectable evidence."""

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
    comparator = _finite_comparator(config, freeze, contract, reference)
    arms = []
    for model_name in config["models"]:
        for method_name in config["methods"]:
            arms.append(
                _arm(
                    config,
                    freeze,
                    contract,
                    adapter,
                    model_name,
                    models[model_name],
                    method_name,
                    reference,
                    output / "commitments" / model_name / method_name,
                )
            )
    for arm in arms:
        _attach_regret(arm, comparator)
    _attach_baseline_comparisons(arms)
    arms_by_id = {arm["arm_id"]: arm for arm in arms}
    total_wall = time.perf_counter() - started
    metrics = _arm_metrics(arms)
    reference_metrics = reference.metrics()
    result = {
        "schema": RESULT_SCHEMA,
        "study_id": config["study_id"],
        "material": cd.MATERIAL,
        "scope": cd.SCOPE,
        "evidence_label": evidence_label,
        "evidence_class": reference.evidence_class,
        "freeze_digest": freeze["freeze_digest"],
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
            "study_end_to_end_wall_s": total_wall,
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
