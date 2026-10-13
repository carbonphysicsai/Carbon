"""Pinned public motor pilot worker; no reference or provider execution.

Reference acquisition is a separate HOLD plan. The dry-run uses an explicit
synthetic trainer stand-in and cannot be promoted to a physical pilot.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
from contextlib import contextmanager, nullcontext
from pathlib import Path

from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget as eb
from carbon.design_search import tasks
from carbon.design_search import winnability_pilot as wp
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_pipeline as ep
from carbon.development_comparison import motor_10p12s_kit as mk
from carbon.development_comparison import motor_pilot_kit as pk
from scripts.dev.evidence_runs.motor_10p12s import IMAGE_DIGEST

SCHEMA = "carbon.motor.pilot-bundle.v2"
UNCERTAINTY = "carbon.motor.reference-uncertainty.v1"
EXPORT = "carbon.motor.complete-panel-export.v1"
ROLES = {"export", "train", "domain", "cheap", "costs", "policy", "reference"}
SEEDS = (0, 1, 2)
ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = (
    "docs/development/challenge_pipeline/equal-budget-registration-v2-f02-menu.json"
)


class PilotHold(ValueError):
    """An unavailable input or reference contract, never a candidate failure."""


def shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise PilotHold("CLOSED_DATA_CONTRACT_REQUIRED")


def pin(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise PilotHold("PIN_OR_OWNER_INPUT_MISSING")
    return value


def cost(value):
    shape(value, {"wall_s", "core_s"})
    if any(
        type(v) not in (int, float) or not math.isfinite(v) or v < 0
        for v in value.values()
    ):
        raise PilotHold("COMPLETE_COST_REQUIRED")
    return value.copy()


def sources(values):
    if type(values) is not list or not values:
        raise PilotHold("SOURCE_RECEIPTS_REQUIRED")
    for value in values:
        pin(value)


def geometry_key(coordinates):
    """Exact numeric identity: JSON integer/float spelling is not a new design."""
    return tuple(float(coordinates[name]) for name in mk.GRAMMAR)


def load(path):
    from carbon.agent_campaign.pod_jobs import _sealed, _upload_path

    path = Path(path)
    if _sealed(path) or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise PilotHold("PUBLIC_LOCAL_PATH_REQUIRED")
    if path.stat().st_size > 1024 * 1024:
        raise PilotHold("BUNDLE_SIZE_EXCEEDED")
    raw = ep._json(path.read_bytes())
    shape(raw, {"schema", "scope", "sources"})
    if raw["schema"] != SCHEMA or raw["scope"] != "PUBLIC_DEVELOPMENT":
        raise PilotHold("PUBLIC_BUNDLE_REQUIRED")
    shape(raw["sources"], ROLES)
    docs, pins, seen = {}, {}, {path.name}
    base = path.parent.resolve()
    for role, desc in raw["sources"].items():
        shape(desc, {"path", "sha256"})
        pin(desc["sha256"])
        if not _upload_path(desc["path"]) or desc["path"] in seen:
            raise PilotHold("DISTINCT_PUBLIC_RELATIVE_FILES_REQUIRED")
        target = base / desc["path"]
        if (
            _sealed(target)
            or not target.resolve().is_relative_to(base)
            or any(p.is_symlink() for p in (target, *target.parents))
        ):
            raise PilotHold("PUBLIC_LOCAL_PATH_REQUIRED")
        seen.add(desc["path"])
        if target.stat().st_size > 95 * 1024 * 1024:
            raise PilotHold("SOURCE_SIZE_EXCEEDED")
        data = target.read_bytes()
        if ca.sha256(data) != desc["sha256"]:
            raise PilotHold("SOURCE_PIN_MISMATCH")
        docs[role] = data if role == "train" else ep._json(data)
        pins[role] = desc["sha256"]
    return docs, pins


def _domain(doc, scope):
    shape(doc, {"schema", "scope", "topology", "geometry", "curves"})
    if (
        doc["schema"] != "carbon.motor.pilot-domain.v1"
        or doc["scope"] != scope
        or doc["topology"] != "10p12s-double-layer"
    ):
        raise PilotHold("REVISED_10P12S_DOMAIN_REQUIRED")
    geometry = {}
    if type(doc["geometry"]) is not dict or not doc["geometry"]:
        raise PilotHold("PHYSICAL_COORDINATES_REQUIRED")
    shape(doc["curves"], doc["geometry"])
    curves = {}
    for index, coordinates in doc["geometry"].items():
        if not re.fullmatch(r"0|[1-9][0-9]*", index):
            raise PilotHold("CANONICAL_GEOMETRY_INDEX_REQUIRED")
        shape(coordinates, mk.GRAMMAR)
        if not pk.valid({**coordinates, "j_a_mm2": 0, "gamma_deg": 0}):
            raise PilotHold("INVALID_PHYSICAL_GEOMETRY")
        geometry[int(index)] = coordinates
        commands = {}
        for curve in doc["curves"][index]:
            shape(curve, {"j_a_mm2", "gamma_deg", "outputs", "source_digest"})
            shape(curve["outputs"], mk.OUTPUTS)
            pin(curve["source_digest"])
            key = (curve["j_a_mm2"], curve["gamma_deg"])
            if (
                any(type(v) not in (int, float) or not math.isfinite(v) for v in key)
                or key not in pk.COMMANDS
                or key in commands
                or any(
                    type(v) not in (int, float) or not math.isfinite(v)
                    for v in curve["outputs"].values()
                )
            ):
                raise PilotHold("FULL_SIGNED_REFERENCE_CURVES_REQUIRED")
            commands[key] = curve["outputs"]
        if set(commands) != set(pk.COMMANDS):
            raise PilotHold("ELEVEN_HOLDING_PEAK_COGGING_SWEEPS_REQUIRED")
        curves[int(index)] = commands
    if len({geometry_key(g) for g in geometry.values()}) != len(geometry):
        raise PilotHold("DUPLICATE_PHYSICAL_GEOMETRY")
    return geometry, curves


def _task(task):
    tasks._verify_task_digest(task)
    rebuilt = tasks.task(
        task["task_id"],
        identity=task["identity"],
        conditions=task["conditions"],
        strata=task["strata"],
        candidates=task["candidates"],
        actions=task["actions"],
        objective=task["objective"],
        limits=task["limits"],
        secondary=task["secondary"],
        tie_rule=task["tie_rule"],
    )
    if task != rebuilt:
        raise PilotHold("CANONICAL_RUNNABLE_TASK_REQUIRED")
    expected_objective = {
        "quantity": "holding_ripple_fraction",
        "unit": "1",
        "sense": "min",
        "aggregate": "worst",
    }
    if (
        task["identity"]["challenge"] != "motor"
        or task["objective"] != expected_objective
        or task["secondary"] is not None
        or task["conditions"]
        != [{"id": pk.CONDITION, "stratum": "complete_buyer_panel"}]
    ):
        raise PilotHold("COMPLETE_BUYER_TASK_REQUIRED")
    # Fixed J10 is tied for all actions, so lower-current secondary adds no order.
    limits = {r["quantity"]: r for r in task["limits"]}
    requirements = {
        "holding_mean_nm": (">=", 6, 7, "N m"),
        "peak_mean_nm": (">=", 12, 14, "N m"),
        "holding_pk_pk_nm": ("<=", 0.24, 0.30, "N m"),
        "peak_pk_pk_nm": ("<=", 0.48, 0.60, "N m"),
        "holding_ripple_fraction": ("<=", 0.04, 0.05, "1"),
        "peak_ripple_fraction": ("<=", 0.04, 0.05, "1"),
        "cogging_nm": ("<=", 0.03, 0.05, "N m"),
    }
    if len(limits) != len(task["limits"]) or set(limits) != set(requirements):
        raise PilotHold("ALL_HARD_BUYER_LIMITS_REQUIRED")
    for name, (op, lo, hi, unit) in requirements.items():
        lim = limits[name]
        if (
            lim["op"] != op
            or lim["unit"] != unit
            or type(lim["value"]) not in (int, float)
            or not lo <= lim["value"] <= hi
            or type(lim.get("band")) not in (int, float)
            or not math.isfinite(lim["band"])
            or lim["band"] < 0
        ):
            raise PilotHold("BUYER_LIMIT_RELAXATION_OR_UNCERTAINTY_HOLD")
    if (
        limits["peak_pk_pk_nm"]["value"] != 2 * limits["holding_pk_pk_nm"]["value"]
        or limits["peak_ripple_fraction"]["value"]
        != limits["holding_ripple_fraction"]["value"]
    ):
        raise PilotHold("COHERENT_HOLDING_PEAK_REQUIREMENTS_REQUIRED")


def _reference_uncertainty(reference, export, domain_digest, scope):
    """Bind supplied uncertainty content and cover it; never choose a value."""
    record = reference.get("uncertainty_record")
    keys = {
        "schema",
        "scope",
        "export_digest",
        "domain_digest",
        "image_digest",
        "observer",
        "bounds",
    }
    if type(record) is not dict or set(record) != keys:
        raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")
    if (
        record["schema"] != UNCERTAINTY
        or record["scope"] != scope
        or record["export_digest"] != export["export_digest"]
        or record["domain_digest"] != domain_digest
        or record["image_digest"] != reference["image_digest"]
        or record["observer"] != reference["observer"]
    ):
        raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")
    limits = export["questions"][0]["task"]["limits"]
    units = {r["quantity"]: r["unit"] for r in limits}
    bounds = record["bounds"]
    if type(bounds) is not dict or set(bounds) != set(units):
        raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")
    for name, unit in units.items():
        bound = bounds[name]
        if (
            type(bound) is not dict
            or set(bound) != {"value", "unit"}
            or bound["unit"] != unit
            or type(bound["value"]) not in (int, float)
            or not math.isfinite(bound["value"])
            or bound["value"] < 0
        ):
            raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")
    if ca.sha256(ca.canonical(record)) != reference["uncertainty_receipt"]:
        raise PilotHold("REFERENCE_UNCERTAINTY_PIN_MISMATCH")
    for entry in export["questions"]:
        for limit in entry["task"]["limits"]:
            if limit["band"] < bounds[limit["quantity"]]["value"]:
                raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")


def prepare(docs, pins, *, fixture=False):
    shape(docs, ROLES)
    shape(pins, ROLES)
    for role in ROLES:
        data = docs[role] if role == "train" else ca.canonical(docs[role])
        # JSON byte pins are checked by load; canonical pins supplied in tests.
        pin(pins[role])
        if role == "train" and ca.sha256(data) != pins[role]:
            raise PilotHold("TRAIN_PIN_MISMATCH")
    scope = "SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT"
    geometry, curves = _domain(docs["domain"], scope)
    kit = pk.kit(geometry)
    train = ca.load_train(kit, docs["train"], pins["train"])
    if train.fixture != fixture or train.excluded:
        raise PilotHold("FIXTURE_PROMOTION_OR_INVALID_TRAIN")
    training = {}
    for r in train.records:
        if not pk.valid(r["inputs"]):
            raise PilotHold("TRAIN_OUTSIDE_REGISTERED_GEOMETRY_OR_COMMANDS")
        key = geometry_key(r["inputs"])
        command = (r["inputs"]["j_a_mm2"], r["inputs"]["gamma_deg"])
        if command in training.setdefault(key, set()):
            raise PilotHold("DUPLICATE_TRAIN_CURVE")
        training[key].add(command)
    if any(v != set(pk.COMMANDS) for v in training.values()):
        raise PilotHold("COMPLETE_TRAIN_ROLES_REQUIRED")
    if set(training) & {geometry_key(g) for g in geometry.values()}:
        raise PilotHold("WHOLE_GEOMETRY_TRAIN_HELDOUT_OVERLAP")
    export = docs["export"]
    shape(export, {"schema", "scope", "family", "questions", "export_digest"})
    if (
        export["schema"] != EXPORT
        or export["scope"] != scope
        or export["family"] != "motor"
        or export["export_digest"]
        != ca.sha256(
            ca.canonical({k: v for k, v in export.items() if k != "export_digest"})
        )
    ):
        raise PilotHold("COMPLETE_EXPORT_IDENTITY_REQUIRED")
    if type(export["questions"]) is not list or not export["questions"]:
        raise PilotHold("BUYER_QUESTIONS_REQUIRED")
    seen = set()
    for e in export["questions"]:
        shape(e, {"case", "support_case", "task", "reference"})
        _task(e["task"])
        if (
            not isinstance(e["case"], str)
            or not e["case"]
            or e["case"] in seen
            or e["support_case"] != e["task"]["identity"]["reference_bank"]
        ):
            raise PilotHold("UNIQUE_QUESTIONS_AND_BANK_CLUSTERS_REQUIRED")
        seen.add(e["case"])
        actions = e["task"]["actions"]
        wanted = {(i, s) for i in geometry for s in (0, 2, 4)}
        if (
            set(actions) != set(e["task"]["candidates"])
            or len(actions) != len(wanted)
            or {(a["design"], a["skew_deg"]) for a in actions.values()} != wanted
        ):
            raise PilotHold("ALL_GEOMETRY_SKEW_ACTIONS_REQUIRED")
        rows = {}
        for r in e["reference"]:
            shape(r, {"candidate", "condition", "values"})
            if r["candidate"] in rows or r["condition"] != pk.CONDITION:
                raise PilotHold("COMPLETE_REFERENCE_INVENTORY_REQUIRED")
            shape(r["values"], pk.OBSERVABLES)
            rows[r["candidate"]] = r
        if set(rows) != set(actions):
            raise PilotHold("COMPLETE_REFERENCE_INVENTORY_REQUIRED")
        for c, r in rows.items():
            physical = {**r, "action": actions[c]}
            predicted = [
                curves[actions[c]["design"]][(q["j_a_mm2"], q["gamma_deg"])]
                for q in kit.row_queries(physical)
            ]
            reduced = kit.row_values(physical, predicted)
            if any(
                type(r["values"][k]) not in (int, float)
                or not math.isclose(
                    r["values"][k], reduced[k], rel_tol=1e-10, abs_tol=1e-10
                )
                for k in reduced
            ):
                raise PilotHold("SIGNED_REFERENCE_OBSERVER_MISMATCH")
    if len({e["support_case"] for e in export["questions"]}) != 1:
        raise PilotHold("SHARED_PHYSICAL_BANK_CLUSTER_REQUIRED")
    cb._physical_rows(export)  # also rejects inconsistent truth between questions
    if not fixture and (
        len(training) != 16
        or len(train.records) != 176
        or len(geometry) != 12
        or len(seen) != 12
    ):
        raise PilotHold("REGISTERED_16_TRAIN_12_HELDOUT_12_QUESTIONS_REQUIRED")
    policy, reference, cheap, costs = (
        docs[k] for k in ("policy", "reference", "cheap", "costs")
    )
    shape(
        policy,
        {
            "scope",
            "export_digest",
            "domain_digest",
            "owner_requirements_digest",
            "precommit_receipt",
            "question_law",
            "solver_orders",
            "served_decisions",
            "seeds",
        },
    )
    if (
        policy["scope"] != scope
        or policy["export_digest"] != export["export_digest"]
        or policy["domain_digest"] != pins["domain"]
        or policy["seeds"] != list(SEEDS)
    ):
        raise PilotHold("PREDECLARED_POLICY_IDENTITY_REQUIRED")
    pin(policy["owner_requirements_digest"])
    pin(policy["precommit_receipt"])
    shape(policy["question_law"], {"P", "Q", "w", "panel_use"})
    if policy["question_law"]["panel_use"] != "PUBLIC_HELDOUT" or any(
        type(policy["question_law"][k]) is not str
        or policy["question_law"][k] in ("", "HUMAN_INPUT", "OPEN")
        for k in ("P", "Q", "w")
    ):
        raise PilotHold("P_Q_W_HOLD")
    shape(policy["solver_orders"], seen)
    served = policy["served_decisions"]
    if (
        type(served) is not list
        or not served
        or any(type(n) is not int or n < 1 for n in served)
        or len(set(served)) != len(served)
    ):
        raise PilotHold("AMORTISATION_COUNTS_REQUIRED")
    for e in export["questions"]:
        order = policy["solver_orders"][e["case"]]
        if (
            type(order) is not list
            or len(order) != len(geometry)
            or any(type(i) is not int for i in order)
            or set(order) != set(geometry)
        ):
            raise PilotHold("COMPLETE_PRECOMMITTED_SOLVER_ORDER_REQUIRED")
    if type(reference) is not dict or "uncertainty_record" not in reference:
        raise PilotHold("REFERENCE_UNCERTAINTY_NOT_COVERED")
    shape(
        reference,
        {
            "scope",
            "export_digest",
            "domain_digest",
            "image_digest",
            "observer",
            "adequacy_receipt",
            "uncertainty_receipt",
            "uncertainty_record",
            "source_digests",
        },
    )
    if (
        reference["scope"] != scope
        or reference["export_digest"] != export["export_digest"]
        or reference["domain_digest"] != pins["domain"]
        or reference["image_digest"] != IMAGE_DIGEST
        or reference["observer"] != "10p12s-gamma-5d-theta+d-three-equal-slices-v1"
    ):
        raise PilotHold("MOTOR_REFERENCE_APPLICABILITY_HOLD")
    pin(reference["adequacy_receipt"])
    pin(reference["uncertainty_receipt"])
    sources(reference["source_digests"])
    _reference_uncertainty(reference, export, pins["domain"], scope)
    shape(
        cheap,
        {
            "scope",
            "export_digest",
            "method",
            "strongest_method_receipt",
            "train_digest",
            "predictions",
            "query_costs",
        },
    )
    if (
        cheap["scope"] != scope
        or cheap["export_digest"] != export["export_digest"]
        or cheap["train_digest"] != pins["train"]
        or not isinstance(cheap["method"], str)
        or not cheap["method"]
    ):
        raise PilotHold("STRONGEST_FULL_CURVE_CHEAP_REQUIRED")
    pin(cheap["strongest_method_receipt"])
    baseline = ep._predictions(export, cheap["predictions"])
    if cheap["predictions"]["scope"] != scope:
        raise PilotHold("FIXTURE_CHEAP_CANNOT_BE_PUBLIC")
    for values in baseline.values():
        for role in ("holding", "peak"):
            metrics = cb.curve_observables(
                [values[f"{role}_t{i:02d}"] for i in range(48)],
                [values[f"cogging_t{i:02d}"] for i in range(48)],
            )
            for name, value in metrics.items():
                key = "cogging_nm" if name == "cogging_nm" else f"{role}_{name}"
                if not math.isclose(values[key], value, rel_tol=1e-10, abs_tol=1e-10):
                    raise PilotHold("CHEAP_SIGNED_CURVE_OBSERVER_MISMATCH")
    shape(cheap["query_costs"], seen)
    for c in cheap["query_costs"].values():
        cost(c)
    shape(
        costs,
        {
            "scope",
            "export_digest",
            "preparation",
            "reference",
            "failed_control_cost",
            "source_digests",
            "new_sweep_attempts",
            "new_field_attempts",
        },
    )
    if costs["scope"] != scope or costs["export_digest"] != export["export_digest"]:
        raise PilotHold("COMPLETE_COST_IDENTITY_REQUIRED")
    if (
        type(costs["new_sweep_attempts"]) is not int
        or not 0 <= costs["new_sweep_attempts"] <= 6
        or type(costs["new_field_attempts"]) is not int
        or not 0 <= costs["new_field_attempts"] <= 384
    ):
        raise PilotHold("REGISTERED_ATTEMPT_CAP_EXCEEDED")
    sources(costs["source_digests"])
    shape(costs["preparation"], {"model", "baseline"})
    for c in costs["preparation"].values():
        cost(c)
    cost(costs["failed_control_cost"])
    indexed = {}
    for r in costs["reference"]:
        shape(
            r,
            {
                "design",
                "cost",
                "planning_bound",
                "raw_sweeps",
                "field_systems",
                "source_digests",
            },
        )
        if (
            type(r["design"]) is not int
            or r["design"] in indexed
            or type(r["raw_sweeps"]) is not int
            or r["raw_sweeps"] != 11
            or type(r["field_systems"]) is not int
            or r["field_systems"] < 528
        ):
            raise PilotHold("COMPLETE_ELEVEN_SWEEP_COST_REQUIRED")
        sources(r["source_digests"])
        actual, bound = cost(r["cost"]), cost(r["planning_bound"])
        if any(actual[k] <= 0 or bound[k] < actual[k] for k in actual):
            raise PilotHold("COMPLETE_COST_BOUND_REQUIRED")
        indexed[r["design"]] = (actual, bound)
    if set(indexed) != set(geometry):
        raise PilotHold("REFERENCE_COST_INVENTORY_INCOMPLETE")
    return kit, export, train, policy, costs, indexed, baseline, cheap


def replay(export, predictions, receipt, policy, costs, indexed, baseline, cheap):
    model = ep._predictions(export, predictions)
    timing = {
        r["query"]: {"wall_s": r["wall_s"], "core_s": r["cpu_s"]}
        for r in receipt["cost"]["inference"]["decision_queries"]
    }
    jobs, learning = [], []
    for e in export["questions"]:
        task, truth = ep._assess(e, {}, reference=True)["plain"]
        learned = ep._assess(e, model)["plain"][1]
        mapped = ep._assess(e, baseline)["plain"][1]
        orders = {
            arm: list(
                dict.fromkeys(
                    task["actions"][c]["design"] for c in ep._order(values, task)
                )
            )
            for arm, values in (("model", learned), ("baseline", mapped))
        }
        candidates = []
        geometry_order = list(
            dict.fromkeys(task["actions"][c]["design"] for c in task["candidates"])
        )
        for design in geometry_order:
            siblings = [
                truth[c]
                for c in task["candidates"]
                if task["actions"][c]["design"] == design
            ]
            status = (
                None
                if any(v["feasible"] is None for v in siblings)
                else any(v["feasible"] for v in siblings)
            )
            value = (
                min(v["objective"] for v in siblings if v["feasible"] is True)
                if status is True
                else None
            )
            actual, bound = indexed[design]
            candidates.append(
                {
                    "design_id": f"geometry-{design}",
                    "reference": {
                        "status": (
                            "UNRESOLVED"
                            if status is None
                            else "FEASIBLE" if status else "INFEASIBLE"
                        ),
                        "value": value,
                    },
                    "solve_cost": actual,
                    "planning_bound": bound,
                    "screen_rank": {
                        arm: order.index(design) for arm, order in orders.items()
                    },
                }
            )
        jobs.append(
            {
                "job_id": e["case"],
                "cluster_id": e["support_case"],
                "candidates": candidates,
                "solver_order": [
                    f"geometry-{i}" for i in policy["solver_orders"][e["case"]]
                ],
                "screen_cost": {
                    "model": timing[e["case"]],
                    "baseline": cheap["query_costs"][e["case"]],
                },
            }
        )
        unresolved = any(t["feasible"] is None for t in truth.values())
        pick, best = tasks.select(task, learned), tasks.select(task, truth)
        errors = [
            abs(model[(None, r["candidate"], pk.CONDITION)][k] - r["values"][k])
            for r in e["reference"]
            if (None, r["candidate"], pk.CONDITION) in model
            for k in pk.CURVES
        ]
        learning.append(
            {
                "job_id": e["case"],
                "cluster_id": e["support_case"],
                "stratum": "holding_peak_cogging",
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
    registration = json.loads((ROOT / REGISTRATION).read_text(encoding="utf-8"))
    registered = br.validate(registration)
    panel = eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": "motor",
            "source_digest": export["export_digest"],
            "decision_rule_id": policy["owner_requirements_digest"],
            "objective": {"direction": "min", "unit": "1"},
            "cost_basis": "MEASURED",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [
                registered.cap("motor", tier).time_compute for tier in br.TIERS
            ],
            "jobs": jobs,
            "registrations": {
                "solver_search": policy["precommit_receipt"],
                "model_screen": receipt["model_id"],
                "baseline_screen": cheap["method"],
                "cost_plan": registered.registration_id,
            },
        }
    )
    prep = copy.deepcopy(costs["preparation"])
    query, fit = receipt["cost"]["inference"], receipt["cost"]["fit"]
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
        "learning_unit": "N m signed stack curves",
        "cost_record_digest": ca.sha256(ca.canonical(costs)),
    }


def cpu_trainer(kit, export, train, *, scope, seed, backend, code):
    """Place the fixed shared recipe and its query arrays on the CPU explicitly."""
    import jax

    device = jax.devices("cpu")[0]
    with jax.default_device(device):
        return ca.run(
            kit,
            export,
            train,
            scope=scope,
            seed=seed,
            backend=backend,
            code={**code, "execution_platform": device.platform},
        )


def _cpu_api():
    if os.name != "posix":
        return None
    import resource
    import signal

    return resource, signal


def _process_limit(resource, kind, ceiling):
    """Apply the existing ceiling without relaxing a lower inherited limit."""
    before = resource.getrlimit(kind)
    selected = tuple(
        ceiling if value == resource.RLIM_INFINITY else min(value, ceiling)
        for value in before
    )
    resource.setrlimit(kind, selected)


@contextmanager
def _fit_cpu_limit(fit_cpu):
    """A caught soft fit cap; keep the existing hard cap and restore handler."""
    if fit_cpu >= 14400:
        raise PilotHold("AGGREGATE_FIT_CAP_EXCEEDED")
    api = _cpu_api()
    if api is None:
        yield
        return
    resource, signal = api
    inherited_soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    hard = 56 * 3600 if hard == resource.RLIM_INFINITY else min(hard, 56 * 3600)
    restored_soft = (
        hard if inherited_soft == resource.RLIM_INFINITY else min(inherited_soft, hard)
    )
    used = resource.getrusage(resource.RUSAGE_SELF)
    soft = min(
        math.ceil(used.ru_utime + used.ru_stime + 14400 - fit_cpu), restored_soft
    )
    previous = signal.getsignal(signal.SIGXCPU)

    def exceeded(_signum, _frame):
        raise PilotHold("AGGREGATE_FIT_CAP_EXCEEDED")

    signal.signal(signal.SIGXCPU, exceeded)
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
        yield
    finally:
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (restored_soft, hard))
        finally:
            signal.signal(signal.SIGXCPU, previous)


def execute(docs, pins, *, fixture=False, trainer=None):
    if not fixture and trainer is not None:
        raise PilotHold("PUBLIC_RUN_REQUIRES_FIXED_CPU_TRAINER")
    kit, export, train, policy, costs, indexed, baseline, cheap = prepare(
        docs, pins, fixture=fixture
    )
    view = copy.deepcopy(export)
    for e in view["questions"]:
        for r in e["reference"]:
            r["values"] = {k: 0.0 for k in pk.OBSERVABLES}
    results, fit_cpu = [], 0.0
    for seed in SEEDS:
        with nullcontext() if fixture else _fit_cpu_limit(fit_cpu):
            pred, receipt = (trainer or cpu_trainer)(
                kit,
                view,
                train,
                scope="SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT",
                seed=seed,
                backend="jax",
                code={
                    **ca._code_identity(),
                    "pilot_module_sha256": ca.sha256(Path(__file__).read_bytes()),
                    "pilot_kit_sha256": ca.sha256(Path(pk.__file__).read_bytes()),
                    "launcher_code_ref": os.environ.get("CODE_REF"),
                },
            )
        fit_cpu += receipt["cost"]["fit"]["fit_cpu_s"]
        if fit_cpu > 14400:
            raise PilotHold("AGGREGATE_FIT_CAP_EXCEEDED")
        source = replay(export, pred, receipt, policy, costs, indexed, baseline, cheap)
        results.append(
            {
                "seed": seed,
                "receipt": receipt,
                "input": source,
                "curve_diagnostics": curve_diagnostics(export, pred),
                "report": wp.evaluate(
                    source,
                    bootstrap_replicates=100 if fixture else 2000,
                    confidence=0.95,
                    seed=0,
                ),
            }
        )
    return {
        "schema": (
            "carbon.motor.pilot-dry-run.v1" if fixture else "carbon.motor.pilot-run.v1"
        ),
        "scope": "SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT",
        "source_pins": pins,
        "reports": results,
        "aggregate_fit_cpu_s": fit_cpu,
        "real_pilot_executed": not fixture,
        "reference_solves": 0,
        "customer_result": False,
        "qualification": "UNDECIDED",
        "thresholds": "HUMAN_INPUT",
    }


def curve_diagnostics(export, predictions):
    """Raw role maxima/coverage; missing predictions do not become zero error."""
    model = ep._predictions(export, predictions)
    physical = cb._physical_rows(export)
    out = {}
    for role in pk.ROLES:
        errors = [
            abs(
                model[(None, r["candidate"], pk.CONDITION)][f"{role}_t{i:02d}"]
                - r["values"][f"{role}_t{i:02d}"]
            )
            for r in physical
            if (None, r["candidate"], pk.CONDITION) in model
            for i in range(48)
        ]
        out[role] = {
            "covered_signed_samples": len(errors),
            "required_signed_samples": len(physical) * 48,
            "max_abs_error_nm": max(errors) if errors else None,
        }
    out["reference_bands"] = [
        {
            "question": e["case"],
            "quantity": lim["quantity"],
            "band": lim["band"],
            "within_two_registered_bands": sum(
                abs(r["values"][lim["quantity"]] - lim["value"]) <= 2 * lim["band"]
                for r in e["reference"]
            ),
        }
        for e in export["questions"]
        for lim in e["task"]["limits"]
    ]
    out["interpretation"] = (
        "sampled-curve diagnostics; no between-angle, 3D, confidence or physical qualification claim"
    )
    return out


def acquisition_plan():
    """Unexecuted counts, not a new bank or a sealed acquisition manifest."""
    law = ROOT / "docs/development/challenge_pipeline/question-laws/motor-round2.json"
    return {
        "schema": "carbon.motor.pilot-acquisition-plan.v1",
        "status": "PROPOSED_HOLD",
        "law_source_digest": ca.sha256(law.read_bytes()),
        "image_digest": IMAGE_DIGEST,
        "topology": "10p12s-double-layer",
        "geometry_ranges": dict(pk.topology.GRAMMAR),
        "commands": [{"j_a_mm2": j, "gamma_deg": g} for j, g in pk.COMMANDS],
        "skew_deg": [0, 2, 4],
        "public_jobs": [
            {
                "role": "TRAIN",
                "geometry_count": 16,
                "raw_sweep_jobs": 176,
                "field_systems": 8448,
            },
            {
                "role": "PUBLIC_HELDOUT",
                "geometry_count": 12,
                "raw_sweep_jobs": 132,
                "field_systems": 6336,
            },
        ],
        "raw_sweep_definition": "one signed 48-angle curve at one geometry/J/gamma; skew composites share slice curves",
        "total_reusable_raw_sweeps": 308,
        "total_field_systems": 14784,
        "cost_basis": "historical shared-host elapsed x2 allocated cores, not measured process CPU or portable p95",
        "standard_sweep": {
            "planning_allocated_cpu_s": 4320,
            "historical_p50_allocated_s": 4164,
            "historical_p95_allocated_s": 6648,
            "field_systems": 48,
        },
        "rung2_sweep": {
            "planning_allocated_cpu_s": 28800,
            "historical_p50_allocated_s": 28997,
            "historical_p95_allocated_s": 56500,
            "field_systems": 96,
        },
        "memory": {
            "working_rss_hypothesis_gib": 16,
            "measured_peak_rss_bytes": None,
            "host_profile_gb": 64,
            "dispatch": "HOLD_UNTIL_COMPLETE_CASE_PROBE",
        },
        "new_attempt_prefix": {
            "standard_sweeps": 4,
            "rung2_sweeps": 2,
            "total_attempts": 6,
            "field_systems": 384,
            "failures_counted": True,
            "retries": 0,
            "probe_included": True,
        },
        "corpus_standard_only_allocated_cpu_h": 308 * 1.2,
        "fresh_corpus_fits_56_cpu_h_pilot_cap": False,
        "sealed_half": {
            "status": "SEPARATE_OWNER_VALIDATOR_PLAN_REQUIRED",
            "jobs": None,
            "cpu_s": None,
            "memory_bytes": None,
            "material_read_or_generated": False,
            "mount_in_public_worker": False,
        },
        "holds": [
            "physical geometry/command acquisition manifest before truth",
            "16 complete TRAIN/12 heldout reuse rights and disjointness",
            "full J15/phase/cogging reference and signed observer uncertainty",
            "native applicability beyond linear MMS",
            "strongest full-curve cheap method",
            "owner law/objective/P/Q/w/k adoption",
            "actual CPU/RSS probe and exact compute grant",
        ],
        "spend_authorized": False,
        "runtime_bank_created": False,
    }


def pod_spec(bundle, code_ref, *, minutes, rate_ceiling, cap_usd, flavor, vcpus):
    from carbon.agent_campaign.pod_jobs import EXPORT_MINUTES, load_spec

    docs, pins = load(bundle)
    prepare(docs, pins)
    if (
        type(minutes) is not int
        or not 0 < minutes <= 3840 - EXPORT_MINUTES
        or type(rate_ceiling) not in (int, float)
        or not 0 < rate_ceiling <= 1.20
        or type(cap_usd) not in (int, float)
        or not 0 < cap_usd <= 77.20
    ):
        raise PilotHold("OPERATOR_SPEC_EXCEEDS_REGISTERED_LIFECYCLE_BOUNDS")
    manifest = ep._json(Path(bundle).read_bytes())
    files = {Path(bundle).name: Path(bundle)}
    files.update(
        {
            d["path"]: Path(bundle).parent / d["path"]
            for d in manifest["sources"].values()
        }
    )
    spec = {
        "schema": "carbon.pod-job.spec.v1",
        "job_id": "motor-winnability-pilot",
        "code_ref": code_ref,
        "module": "carbon.development_comparison.motor_pilot",
        "args": ["run", "{inputs}/" + Path(bundle).name, "--out", "{out}/pilot.json"],
        "inputs": [REGISTRATION],
        "image": "study",
        "overlays": {},
        "compute": {"kind": "cpu", "flavor": flavor, "vcpus": vcpus},
        "minutes": minutes,
        "rate_ceiling_usd_per_hr": rate_ceiling,
        "cap_usd": cap_usd,
        "disk_gb": 20,
        "uploads": {
            name: {"sha256": ca.sha256(p.read_bytes())[7:], "bytes": p.stat().st_size}
            for name, p in files.items()
        },
        "collect": [],
    }
    load_spec(spec)
    return spec


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for command in ("run", "check", "pod-spec", "dry-run", "data-plan"):
        p = sub.add_parser(command)
        if command not in ("dry-run", "data-plan"):
            p.add_argument("bundle", type=Path)
        if command != "check":
            p.add_argument("--out", type=Path, required=True)
        if command == "pod-spec":
            p.add_argument("--code-ref", required=True)
            p.add_argument("--minutes", required=True, type=int)
            p.add_argument("--rate-ceiling-usd-per-hr", required=True, type=float)
            p.add_argument("--cap-usd", required=True, type=float)
            p.add_argument("--cpu-flavor", required=True)
            p.add_argument("--vcpus", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "dry-run":
            from .motor_pilot_fixture import dry_run

            write(args.out, dry_run())
        elif args.cmd == "data-plan":
            write(args.out, acquisition_plan())
        elif args.cmd == "pod-spec":
            write(
                args.out,
                pod_spec(
                    args.bundle,
                    args.code_ref,
                    minutes=args.minutes,
                    rate_ceiling=args.rate_ceiling_usd_per_hr,
                    cap_usd=args.cap_usd,
                    flavor=args.cpu_flavor,
                    vcpus=args.vcpus,
                ),
            )
        else:
            docs, pins = load(args.bundle)
            if args.cmd == "check":
                prepare(docs, pins)
            else:
                if os.name != "posix":
                    raise PilotHold("LINUX_CPU_MEMORY_ENFORCEMENT_REQUIRED")
                import resource

                _process_limit(resource, resource.RLIMIT_CPU, 56 * 3600)
                _process_limit(resource, resource.RLIMIT_AS, 16 * 1024**3)
                write(args.out, execute(docs, pins))
        print(
            json.dumps(
                {
                    "status": (
                        "FIXTURE_WIRING_ONLY"
                        if args.cmd == "dry-run"
                        else (
                            "PROPOSED_HOLD"
                            if args.cmd == "data-plan"
                            else "PUBLIC_CONTRACT_ONLY"
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
        tasks.TaskError,
        ep.Refusal,
        eb.EqualBudgetError,
        br.BudgetRegistrationError,
        wp.WinnabilityError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as hold:
        print(
            json.dumps(
                {
                    "status": "HOLD",
                    "reason": (
                        str(hold)
                        if isinstance(hold, (PilotHold, ca.ArmRefused))
                        else "INPUT_OR_REFERENCE_CONTRACT_UNAVAILABLE"
                    ),
                    "candidate_failure": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
