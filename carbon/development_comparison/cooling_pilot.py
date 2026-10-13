"""Cooling retained-public-evidence worker; no solver or provider calls.

Reuses the solenoid worker's load/prepare/train/replay pattern with main's
shared trainers, task assessments and OPT-12. Maps and native references are
producer inputs. The separate dry-run uses a deterministic trainer stand-in.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path

from carbon.challenge_pipeline import cooling_readiness as cr
from carbon.design_search import cooling_budget as budget
from carbon.design_search import equal_budget as eb
from carbon.design_search import tasks
from carbon.design_search import winnability_pilot as wp
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import cooling_kit as ck
from carbon.development_comparison import evidence_pipeline as ep

SCHEMA = "carbon.cooling-cell.winnability-bundle.v1"
EXPORT = "carbon.cooling-cell.tim2-pilot-export.v1"
RESULT = "carbon.cooling-cell.winnability-run.v1"
ROLES = {"registration", "train", "export", "policy", "reference", "cheap", "costs"}
SEEDS = (0, 1, 2)


class PilotHold(ValueError):
    """Missing/malformed evidence is a hold, never a candidate failure."""


def shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise PilotHold("CLOSED_DATA_CONTRACT_REQUIRED")


def pin(value):
    if type(value) is not str or cr.SHA.fullmatch(value) is None:
        raise PilotHold("IMMUTABLE_SOURCE_OR_OWNER_INPUT_MISSING")
    return value


def cost(value):
    shape(value, {"wall_s", "core_s"})
    if any(not cr._finite(v) or v < 0 for v in value.values()):
        raise PilotHold("COMPLETE_MEASURED_COST_REQUIRED")
    return value.copy()


def load(path, expected_sha256):
    from carbon.agent_campaign.pod_jobs import _sealed, _upload_path

    path = Path(path)
    if (
        _sealed(path)
        or _sealed(path.resolve())
        or any(p.is_symlink() for p in (path, *path.parents))
        or str(path).startswith(("\\\\", "//"))
    ):
        raise PilotHold("PUBLIC_LOCAL_BUNDLE_REQUIRED")
    manifest = ep._read(path, pin(expected_sha256))
    shape(manifest, {"schema", "scope", "sources"})
    if manifest["schema"] != SCHEMA or manifest["scope"] != "PUBLIC_DEVELOPMENT":
        raise PilotHold("PUBLIC_BUNDLE_REQUIRED")
    shape(manifest["sources"], ROLES)
    docs, pins, seen = {}, {}, set()
    base = path.parent.resolve()
    for role, desc in manifest["sources"].items():
        shape(desc, {"path", "sha256"})
        pin(desc["sha256"])
        relative = desc["path"]
        if not _upload_path(relative) or relative in seen or relative == path.name:
            raise PilotHold("DISTINCT_PUBLIC_RELATIVE_FILES_REQUIRED")
        target = base / relative
        if (
            not target.resolve().is_relative_to(base)
            or _sealed(target)
            or any(
                p.is_symlink()
                for p in (target, *target.parents)
                if p.is_relative_to(base)
            )
        ):
            raise PilotHold("PUBLIC_LOCAL_PATH_REQUIRED")
        seen.add(relative)
        if role == "train":
            with target.open("rb") as stream:
                raw = stream.read(ep.MAX_BYTES + 1)
            if len(raw) > ep.MAX_BYTES or ca.sha256(raw) != desc["sha256"]:
                raise PilotHold("TRAIN_PIN_OR_SIZE_MISMATCH")
            docs[role] = raw
        else:
            docs[role] = ep._read(target, desc["sha256"])
        pins[role] = desc["sha256"]
    return docs, pins


def _document(doc, name, scope, export, registration):
    if (
        doc["schema"] != "carbon.cooling-cell." + name + ".v1"
        or doc["scope"] != scope
        or doc["export_digest"] != export["export_digest"]
        or doc["registration_digest"] != registration["digest"]
    ):
        raise PilotHold("SOURCE_SCOPE_OR_IDENTITY_MISMATCH")


def _source_list(values):
    if type(values) is not list or not values:
        raise PilotHold("RETAINED_SOURCE_PROOFS_REQUIRED")
    for value in values:
        pin(value)


def prepare(docs, pins, *, fixture=False):
    shape(docs, ROLES)
    shape(pins, ROLES)
    for value in pins.values():
        pin(value)
    scope = "SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT"
    registration = cr.validate(docs["registration"])
    if registration["scope"] != scope:
        raise PilotHold("FIXTURE_PROMOTION_REFUSED")
    services = {s["id"]: s for s in registration["services"]}
    if len(services) != 3 or any(
        (s["inlet_c"], s["heat_load_w"], s["cell_pressure_limit_pa"])
        != (40, 1000, 25000)
        for s in services.values()
    ):
        raise PilotHold("THREE_FROZEN_POINT_B_MAPS_REQUIRED")
    flow_rule = registration["grammar"]["flow_lpm_per_kw"]
    if (flow_rule["min"], flow_rule["max"]) != (1.5, 1.5):
        raise PilotHold("POINT_B_FIXED_FLOW_REQUIRED")
    objectives = {s["objective"] for s in services.values()}
    if len(objectives) != 1 or None in objectives:
        raise PilotHold("OWNER_CELL_OBJECTIVE_REQUIRED")
    kit = ck.kit_from_bytes(ca.canonical(registration))
    train = ca.load_train(kit, docs["train"], pins["train"])
    if train.fixture != fixture or train.excluded:
        raise PilotHold("FIXTURE_PROMOTION_OR_NONFINITE_TRAIN_REFUSED")
    for record in train.records:
        if (
            record.get("registration_digest") != registration["digest"]
            or record.get("observer_version")
            != cr.OBSERVER + ":" + registration["digest"]
        ):
            raise PilotHold("TRAIN_TIM2_PROVENANCE_REQUIRED")
        observed = cr.observe(
            registration,
            {n: record["inputs"][n] for n in cr.ACTION},
            record["inputs"]["service"],
            **record["observation"],
        )
        if observed["status"] != "OBSERVED_NOT_QUALIFIED" or any(
            not math.isclose(
                record["outputs"][k], observed[k], rel_tol=1e-10, abs_tol=1e-10
            )
            for k in ck.OUTPUTS
        ):
            raise PilotHold("TRAIN_TIM2_OBSERVER_MISMATCH")
    export = docs["export"]
    shape(export, {"schema", "scope", "family", "questions", "export_digest"})
    if (
        export["schema"] != EXPORT
        or export["scope"] != scope
        or export["family"] != ck.FAMILY
        or export["export_digest"]
        != ca.sha256(
            ca.canonical({k: v for k, v in export.items() if k != "export_digest"})
        )
        or type(export["questions"]) is not list
        or not 1 <= len(export["questions"]) <= 64
    ):
        raise PilotHold("COOLING_EXPORT_IDENTITY_OR_SIZE_MISMATCH")
    seen = set()
    for entry in export["questions"]:
        shape(entry, {"case", "task", "reference"})
        if type(entry["case"]) is not str or not entry["case"] or entry["case"] in seen:
            raise PilotHold("UNIQUE_QUESTIONS_REQUIRED")
        seen.add(entry["case"])
        task = entry["task"]
        tasks._verify_task_digest(task)
        tasks._validate_runnable(task["identity"], task["candidates"], task["actions"])
        expected_conditions = {s["id"]: s["stratum"] for s in services.values()}
        expected_strata = {
            s["stratum"]: {
                name.lower(): registration[name][s["id"]] for name in ("P", "Q", "w")
            }
            for s in services.values()
        }
        if (
            task["schema"] != tasks.RUNNABLE_SCHEMA
            or task["identity"]["challenge"] != ck.FAMILY
            or task["identity"]["observer_version"]
            != cr.OBSERVER + ":" + registration["digest"]
            or {c["id"] for c in task["conditions"]} != set(services)
            or len(task["conditions"]) != 3
            or any(
                c["stratum"] != expected_conditions[c["id"]] for c in task["conditions"]
            )
            or task["strata"] != expected_strata
            or task["objective"]
            != {
                "quantity": (
                    "cell_pressure_drop_pa"
                    if next(iter(objectives)) == "min_cell_pressure_pa"
                    else "half_cell_hydraulic_power_w"
                ),
                "unit": (
                    "Pa" if next(iter(objectives)) == "min_cell_pressure_pa" else "W"
                ),
                "sense": "min",
                "aggregate": "worst",
            }
        ):
            raise PilotHold("COMPLETE_TIM2_SERVICE_TASK_REQUIRED")
        for action in task["actions"].values():
            for service in services:
                cr.case(registration, action, service, resolution=2)
        expected = {(c, s) for c in task["candidates"] for s in services}
        actual = [(r["candidate"], r["condition"]) for r in entry["reference"]]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise PilotHold("COMPLETE_REFERENCE_PANEL_REQUIRED")
        if any(
            type(r["values"]) is not dict
            or set(r["values"]) != set(ck.OBSERVABLES)
            or any(not cr._finite(v) for v in r["values"].values())
            for r in entry["reference"]
        ):
            raise PilotHold("FINITE_TIM2_REFERENCE_INVENTORY_REQUIRED")
        limits = task["limits"]
        if len(limits) != 3 or {(r["quantity"], r["op"]) for r in limits} != {
            ("peak_case_c", "<="),
            ("cell_pressure_drop_pa", "<="),
            ("cell_pressure_drop_pa", ">="),
        }:
            raise PilotHold("MANDATORY_THERMAL_HYDRAULIC_LIMITS_REQUIRED")
        for limit in limits:
            if (
                not cr._finite(limit["value"])
                or not cr._finite(limit.get("band", 0))
                or limit.get("band", 0) < 0
            ):
                raise PilotHold("FINITE_REGISTERED_LIMITS_REQUIRED")
            if limit["quantity"] == "peak_case_c" and (
                limit["unit"] != "degC" or not 0 < limit["value"] <= 85
            ):
                raise PilotHold("TIM2_HARD_LIMIT_RELAXED")
            if limit["quantity"] == "cell_pressure_drop_pa" and (
                limit["unit"] != "Pa"
                or (
                    not 0 < limit["value"] <= 25000
                    if limit["op"] == "<="
                    else limit["value"] != 0
                )
            ):
                raise PilotHold("CELL_PRESSURE_HARD_LIMIT_RELAXED")
    physical = cb._physical_rows(export)
    if any(
        set(r["values"]) != set(ck.OBSERVABLES)
        or any(not cr._finite(v) for v in r["values"].values())
        for r in physical
    ):
        raise PilotHold("FINITE_TIM2_REFERENCE_INVENTORY_REQUIRED")
    train_actions = {
        ca.canonical({n: row["inputs"][n] for n in cr.ACTION}) for row in train.records
    }
    held_actions = {ca.canonical(row["action"]) for row in physical}
    if train_actions & held_actions:
        raise PilotHold("WHOLE_GEOMETRY_TRAIN_HELDOUT_OVERLAP")
    training_keys = {ca.canonical(row["inputs"]) for row in train.records}
    if (
        len(training_keys) != len(train.records)
        or len(train.records) != len(train_actions) * 3
    ):
        raise PilotHold("COMPLETE_UNIQUE_TRAIN_SERVICE_PANELS_REQUIRED")
    if not fixture and (
        len(train.records),
        len(train_actions),
        len(held_actions),
        len(physical),
        len(seen),
    ) != (48, 16, 12, 36, 8):
        raise PilotHold("REGISTERED_48_TRAIN_36_HELDOUT_8_QUESTIONS_REQUIRED")
    policy, reference, cheap, costs = (
        docs[k] for k in ("policy", "reference", "cheap", "costs")
    )
    shape(
        policy,
        {
            "schema",
            "scope",
            "export_digest",
            "registration_digest",
            "precommit_receipt",
            "question_law",
            "solver_orders",
            "served_decisions",
            "seed_policy",
        },
    )
    _document(policy, "pilot-policy", scope, export, registration)
    pin(policy["precommit_receipt"])
    shape(policy["question_law"], {"P", "Q", "w", "panel_use"})
    if (
        policy["question_law"]["panel_use"] != "PUBLIC_HELDOUT"
        or any(
            type(policy["question_law"][k]) is not str
            or policy["question_law"][k] in ("", "HUMAN_INPUT", "OPEN")
            for k in ("P", "Q", "w")
        )
        or policy["seed_policy"] != list(SEEDS)
    ):
        raise PilotHold("PREDECLARED_P_Q_W_AND_SEEDS_REQUIRED")
    shape(policy["solver_orders"], seen)
    for entry in export["questions"]:
        order = policy["solver_orders"][entry["case"]]
        if (
            type(order) is not list
            or len(order) != len(entry["task"]["candidates"])
            or set(order) != set(entry["task"]["candidates"])
        ):
            raise PilotHold("COMPLETE_REGISTERED_SOLVER_ORDER_REQUIRED")
    shape(
        reference,
        {
            "schema",
            "scope",
            "export_digest",
            "registration_digest",
            "native_acceptance_receipt",
            "source_digests",
            "observations",
        },
    )
    _document(reference, "pilot-reference", scope, export, registration)
    pin(reference["native_acceptance_receipt"])
    _source_list(reference["source_digests"])
    observations = {}
    for row in reference["observations"]:
        shape(
            row,
            {
                "candidate",
                "condition",
                "faces",
                "numerical_uncertainty_k",
                "pressure_uncertainty_pa",
                "pressure_drop_pa",
                "fluid_min_c",
                "fluid_max_c",
            },
        )
        key = (row["candidate"], row["condition"])
        if (
            key in observations
            or not cr._finite(row["pressure_uncertainty_pa"])
            or row["pressure_uncertainty_pa"] < 0
        ):
            raise PilotHold("UNIQUE_OBSERVER_UNCERTAINTY_REQUIRED")
        observations[key] = row
    if set(observations) != {(r["candidate"], r["condition"]) for r in physical}:
        raise PilotHold("COMPLETE_COLOCATED_NATIVE_OBSERVATIONS_REQUIRED")
    for row in physical:
        witness = observations[(row["candidate"], row["condition"])]
        observed = cr.observe(
            registration,
            row["action"],
            row["condition"],
            witness["faces"],
            **{
                k: witness[k]
                for k in (
                    "numerical_uncertainty_k",
                    "pressure_drop_pa",
                    "fluid_min_c",
                    "fluid_max_c",
                )
            },
        )
        if observed["status"] != "OBSERVED_NOT_QUALIFIED" or any(
            not math.isclose(
                observed[k], row["values"][k], rel_tol=1e-10, abs_tol=1e-10
            )
            for k in ck.OBSERVABLES
        ):
            raise PilotHold("TIM2_REFERENCE_OBSERVER_MISMATCH_OR_INVALID")
        thermal_band = (
            services[row["condition"]]["map_uncertainty_k"]
            + witness["numerical_uncertainty_k"]
        )
        for entry in export["questions"]:
            for limit in entry["task"]["limits"]:
                needed = (
                    thermal_band
                    if limit["quantity"] == "peak_case_c"
                    else witness["pressure_uncertainty_pa"]
                )
                if limit.get("band", 0) < needed:
                    raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")
    shape(
        cheap,
        {
            "schema",
            "scope",
            "export_digest",
            "registration_digest",
            "train_sha256",
            "precommit_receipt",
            "method",
            "calibration_role",
            "predictions",
            "query_costs",
            "source_digests",
        },
    )
    _document(cheap, "strongest-cheap-screen", scope, export, registration)
    if (
        cheap["train_sha256"] != pins["train"]
        or cheap["precommit_receipt"] != policy["precommit_receipt"]
        or cheap["calibration_role"] != "TRAIN_WHOLE_GEOMETRY_ONLY"
        or cheap["method"]
        not in ("same-map-rbf-kriging", "calibrated-channel-thermal-response-map")
        or cheap["predictions"]["scope"] != scope
    ):
        raise PilotHold("STRONGEST_TRAIN_ONLY_CHEAP_REQUIRED")
    _source_list(cheap["source_digests"])
    baseline = ep._predictions(export, cheap["predictions"])
    for row in physical:
        key = (None, row["candidate"], row["condition"])
        if key in baseline:
            reduced = kit.row_values(row, [{k: baseline[key][k] for k in ck.OUTPUTS}])
            if any(
                not math.isclose(
                    reduced[k], baseline[key][k], rel_tol=1e-10, abs_tol=1e-10
                )
                for k in ck.OBSERVABLES
            ):
                raise PilotHold("CHEAP_HYDRAULIC_ARITHMETIC_MISMATCH")
    shape(cheap["query_costs"], seen)
    for value in cheap["query_costs"].values():
        cost(value)
    shape(
        costs,
        {
            "schema",
            "scope",
            "export_digest",
            "registration_digest",
            "preparation",
            "failed_control_cost",
            "reference",
            "source_digests",
            "new_attempts",
        },
    )
    _document(costs, "pilot-costs", scope, export, registration)
    shape(costs["preparation"], {"model", "baseline"})
    for value in costs["preparation"].values():
        cost(value)
    cost(costs["failed_control_cost"])
    _source_list(costs["source_digests"])
    if type(costs["new_attempts"]) is not int or not 0 <= costs["new_attempts"] <= 12:
        raise PilotHold("PROSPECTIVE_ATTEMPT_CAP_EXCEEDED")
    indexed = {}
    for row in costs["reference"]:
        shape(
            row, {"candidate", "condition", "cost", "planning_bound", "source_digests"}
        )
        key = (row["candidate"], row["condition"])
        actual, bound = cost(row["cost"]), cost(row["planning_bound"])
        if key in indexed or any(
            actual[k] <= 0 or bound[k] < actual[k] for k in actual
        ):
            raise PilotHold("COMPLETE_REFERENCE_COST_BOUND_REQUIRED")
        _source_list(row["source_digests"])
        indexed[key] = (actual, bound)
    if set(indexed) != set(observations):
        raise PilotHold("REFERENCE_COST_INVENTORY_INCOMPLETE")
    return kit, export, train, policy, costs, indexed, baseline, cheap


def replay(export, predictions, receipt, policy, costs, indexed, baseline, cheap):
    model = ep._predictions(export, predictions)
    timings = {
        r["query"]: {"wall_s": r["wall_s"], "core_s": r["cpu_s"]}
        for r in receipt["cost"]["inference"]["decision_queries"]
    }
    jobs, learning = [], []
    # Shared physical evidence is one cluster, regardless of question labels.
    cluster = ca.sha256(
        ca.canonical(
            sorted(
                {ca.canonical(r["action"]).decode() for r in cb._physical_rows(export)}
            )
        )
    )
    for entry in export["questions"]:
        task, truth = ep._assess(entry, {}, reference=True)["plain"]
        learned = ep._assess(entry, model)["plain"][1]
        mapped = ep._assess(entry, baseline)["plain"][1]
        orders = {
            "model": ep._order(learned, task),
            "baseline": ep._order(mapped, task),
        }
        candidates = []
        for candidate in task["candidates"]:
            actual, bound = ({"wall_s": 0, "core_s": 0} for _ in range(2))
            for condition in task["conditions"]:
                a, b = indexed[(candidate, condition["id"])]
                for unit in actual:
                    actual[unit] += a[unit]
                    bound[unit] += b[unit]
            state = truth[candidate]["feasible"]
            candidates.append(
                {
                    "design_id": candidate,
                    "reference": {
                        "status": (
                            "UNRESOLVED"
                            if state is None
                            else "FEASIBLE" if state else "INFEASIBLE"
                        ),
                        "value": (
                            truth[candidate]["objective"] if state is True else None
                        ),
                    },
                    "solve_cost": actual,
                    "planning_bound": bound,
                    "screen_rank": {
                        arm: order.index(candidate) for arm, order in orders.items()
                    },
                }
            )
        jobs.append(
            {
                "job_id": entry["case"],
                "cluster_id": cluster,
                "candidates": candidates,
                "solver_order": policy["solver_orders"][entry["case"]],
                "screen_cost": {
                    "model": cost(timings[entry["case"]]),
                    "baseline": cheap["query_costs"][entry["case"]],
                },
            }
        )
        unresolved = any(r["feasible"] is None for r in truth.values())
        pick, best = tasks.select(task, learned), tasks.select(task, truth)
        errors = [
            abs(
                model[(None, r["candidate"], r["condition"])]["peak_case_c"]
                - r["values"]["peak_case_c"]
            )
            for r in entry["reference"]
            if (None, r["candidate"], r["condition"]) in model
        ]
        learning.append(
            {
                "job_id": entry["case"],
                "cluster_id": cluster,
                "stratum": "three-frozen-point-B-maps",
                "reference_status": (
                    "UNRESOLVED"
                    if unresolved
                    else "FEASIBLE_EXISTS" if best is not None else "NONE_FEASIBLE"
                ),
                "pointwise_error": None if unresolved or not errors else max(errors),
                "decision_agreement": None if unresolved else pick == best,
                "false_feasible": (
                    None
                    if unresolved
                    else pick is not None and truth[pick]["feasible"] is False
                ),
                "missed_feasible": (
                    None if unresolved else pick is None and best is not None
                ),
                "abstained": None if unresolved else pick is None,
            }
        )
    objective = export["questions"][0]["task"]["objective"]
    registration = budget.proposal()
    registered = budget.validate(registration)
    panel = eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": ck.FAMILY,
            "source_digest": export["export_digest"],
            "decision_rule_id": policy["precommit_receipt"],
            "objective": {"direction": objective["sense"], "unit": objective["unit"]},
            "cost_basis": (
                "ASSUMPTION" if export["scope"] == "SYNTHETIC_FIXTURE" else "MEASURED"
            ),
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [
                registered.cap(ck.FAMILY, tier).time_compute
                for tier in ("half", "base", "double")
            ],
            "jobs": jobs,
            "registrations": {
                "solver_search": policy["precommit_receipt"],
                "model_screen": receipt["model_id"],
                "baseline_screen": cheap["method"],
                "cost_plan": budget.ID,
            },
        }
    )
    prep = copy.deepcopy(costs["preparation"])
    fit, query = receipt["cost"]["fit"], receipt["cost"]["inference"]
    for unit, suffix in (("wall_s", "wall_s"), ("core_s", "cpu_s")):
        prep["model"][unit] += (
            fit["fit_" + suffix]
            + query["cold_" + suffix]
            + query[suffix]
            + sum(r["cold_" + suffix] for r in query["decision_queries"])
        )
        for arm in prep:
            prep[arm][unit] += costs["failed_control_cost"][unit]
    return {
        "schema": wp.SCHEMA,
        "evidence_class": "DEVELOPMENT_PUBLIC",
        "panel": panel,
        "registration": registration,
        "methods": {
            "model": "PLAIN_L0_MLP",
            "cheap": "STRONGEST_APPLICABLE_CHEAP",
            "solver": "REGISTERED_ADAPTIVE_SOLVER",
        },
        "question_law": policy["question_law"],
        "preparation_cost": prep,
        "served_decisions": policy["served_decisions"],
        "learning": learning,
        "learning_unit": "K",
        "cost_record_digest": ca.sha256(ca.canonical(costs)),
    }


def pointwise_by_service(export, predictions):
    predicted = ep._predictions(export, predictions)
    near = set()
    for entry in export["questions"]:
        for row in entry["reference"]:
            if any(
                abs(row["values"][lim["quantity"]] - lim["value"]) <= lim.get("band", 0)
                for lim in entry["task"]["limits"]
            ):
                near.add((row["candidate"], row["condition"]))
    groups = {}
    for service in sorted({row["condition"] for row in cb._physical_rows(export)}):
        rows = [row for row in cb._physical_rows(export) if row["condition"] == service]
        covered = [
            row for row in rows if (None, row["candidate"], service) in predicted
        ]
        groups[service] = {
            "reference_rows": len(rows),
            "predicted_rows": len(covered),
            "abstained_rows": len(rows) - len(covered),
            "near_boundary_reference_rows": sum(
                (row["candidate"], service) in near for row in rows
            ),
            "max_absolute_error": {
                name: max(
                    (
                        abs(
                            predicted[(None, row["candidate"], service)][name]
                            - row["values"][name]
                        )
                        for row in covered
                    ),
                    default=None,
                )
                for name in ck.OBSERVABLES
            },
        }
    return groups


def execute(docs, pins, *, fixture=False, trainer=None):
    if trainer is not None and not fixture:
        raise PilotHold("STAND_IN_TRAINER_PUBLIC_PROMOTION_REFUSED")
    kit, export, train, policy, costs, indexed, baseline, cheap = prepare(
        docs, pins, fixture=fixture
    )
    view = copy.deepcopy(export)
    for entry in view["questions"]:
        for row in entry["reference"]:
            row["values"] = {key: 0.0 for key in ck.OBSERVABLES}
    results, fit_cpu = [], 0.0
    for seed in SEEDS:
        previous_limit = None
        if os.name == "posix" and not fixture:
            import resource

            used = resource.getrusage(resource.RUSAGE_SELF)
            previous_limit = resource.getrlimit(resource.RLIMIT_CPU)
            remaining = max(1, math.ceil(14400 - fit_cpu))
            soft = math.ceil(used.ru_utime + used.ru_stime) + remaining
            if previous_limit[0] != resource.RLIM_INFINITY:
                soft = min(soft, previous_limit[0])
            resource.setrlimit(resource.RLIMIT_CPU, (soft, previous_limit[1]))
        pred, receipt = (trainer or ca.run)(
            kit,
            view,
            train,
            scope=export["scope"],
            seed=seed,
            backend="jax",
            code={
                **ca._code_identity(),
                "cooling_kit_sha256": ca.sha256(Path(ck.__file__).read_bytes()),
                "cooling_pilot_sha256": ca.sha256(Path(__file__).read_bytes()),
            },
        )
        if previous_limit is not None:
            resource.setrlimit(resource.RLIMIT_CPU, previous_limit)
        fit_cpu += receipt["cost"]["fit"]["fit_cpu_s"]
        if fit_cpu > 14400:
            raise PilotHold("AGGREGATE_FIT_CPU_CAP_EXCEEDED")
        source = replay(export, pred, receipt, policy, costs, indexed, baseline, cheap)
        report = wp.evaluate(
            source,
            bootstrap_replicates=100 if fixture else 2000,
            confidence=0.95,
            seed=0,
        )
        results.append(
            {
                "seed": seed,
                "receipt": receipt,
                "input": source,
                "report": report,
                "pointwise": cb.pointwise_errors(export, ep._predictions(export, pred)),
                "pointwise_by_service": pointwise_by_service(export, pred),
            }
        )
    return {
        "schema": RESULT,
        "scope": export["scope"],
        "family": ck.FAMILY,
        "source_pins": pins,
        "reports": results,
        "aggregate_fit_cpu_s": fit_cpu,
        "real_training_executed": not fixture,
        "reference_solves": 0,
        "customer_result": False,
        "qualification": "UNDECIDED",
        "thresholds": "HUMAN_INPUT",
    }


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "check", "dry-run", "data-plan"):
        command = commands.add_parser(name)
        if name in ("run", "check"):
            command.add_argument("bundle", type=Path)
            command.add_argument("--bundle-sha256", required=True)
        if name != "check":
            command.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "dry-run":
            from .cooling_pilot_fixture import dry_run

            write(args.out, dry_run())
        elif args.command == "data-plan":
            path = (
                Path(__file__).resolve().parents[2]
                / "docs/development/challenge_pipeline/cooling-winnability-run/reference-jobs.json"
            )
            write(args.out, ep._json(path.read_bytes()))
        else:
            docs, pins = load(args.bundle, args.bundle_sha256)
            if args.command == "check":
                prepare(docs, pins)
            else:
                if os.name != "posix":
                    raise PilotHold("BOUNDED_LINUX_CPU_WORKER_REQUIRED")
                import resource

                used = resource.getrusage(resource.RUSAGE_SELF)
                cap = math.ceil(used.ru_utime + used.ru_stime + 32 * 3600)
                resource.setrlimit(resource.RLIMIT_CPU, (cap, cap))
                os.environ["JAX_PLATFORMS"] = "cpu"
                write(args.out, execute(docs, pins))
        print(
            json.dumps(
                {
                    "status": (
                        "FIXTURE_WIRING_ONLY"
                        if args.command == "dry-run"
                        else (
                            "PROPOSED_HOLD"
                            if args.command == "data-plan"
                            else "PUBLIC_DIAGNOSTIC_CONTRACT_ONLY"
                        )
                    ),
                    "reference_solves": 0,
                }
            )
        )
        return 0
    except (
        PilotHold,
        ca.ArmRefused,
        ep.Refusal,
        eb.EqualBudgetError,
        wp.WinnabilityError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OSError,
    ):
        print(
            json.dumps(
                {
                    "status": "HOLD",
                    "reason": "INVALID_OR_INCOMPLETE_PUBLIC_EVIDENCE",
                    "candidate_failure": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
