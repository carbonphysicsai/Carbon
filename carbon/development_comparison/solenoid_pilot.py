"""Solenoid retained-evidence worker. No reference solver or provider calls.

The native axisymmetric package and buyer/material inputs are data holds.
The separate dry-run mode is an explicit trainer stand-in, never evidence.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
from pathlib import Path

from carbon.design_search import equal_budget as eb
from carbon.design_search import solenoid_budget as budget
from carbon.design_search import tasks
from carbon.design_search import winnability_pilot as wp
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_pipeline as ep
from carbon.development_comparison import solenoid_kit as sk

SCHEMA = "carbon.solenoid-pole.winnability-bundle.v1"
EXPORT = "carbon.solenoid-pole.pilot-export.v1"
RESULT = "carbon.solenoid-pole.winnability-run.v1"
FIXTURE = "carbon.solenoid-pole.winnability-dry-run.v1"
FIELDS = {"schema", "scope", "sources"}
ROLES = {"export", "train", "domain", "cheap", "costs", "policy", "reference"}
SEEDS = (0, 1, 2)


class PilotHold(ValueError):
    """A missing producer/reference contract, not a candidate failure."""


def shape(doc, fields):
    if type(doc) is not dict or set(doc) != set(fields):
        raise PilotHold("CLOSED_DATA_CONTRACT_REQUIRED")


def pin(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise PilotHold("PIN_OR_OWNER_INPUT_MISSING")
    return value


def cost(row):
    shape(row, {"wall_s", "core_s"})
    if any(
        type(v) not in (int, float) or not math.isfinite(v) or v < 0
        for v in row.values()
    ):
        raise PilotHold("MEASURED_COMPLETE_COST_REQUIRED")
    return row.copy()


def load(path):
    from carbon.agent_campaign.pod_jobs import _sealed, _upload_path

    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    shape(raw, FIELDS)
    if raw["schema"] != SCHEMA or raw["scope"] != "PUBLIC_DEVELOPMENT":
        raise PilotHold("PUBLIC_BUNDLE_REQUIRED")
    shape(raw["sources"], ROLES)
    docs, pins, seen = {}, {}, set()
    base = path.parent.resolve()
    for role, desc in raw["sources"].items():
        shape(desc, {"path", "sha256"})
        pin(desc["sha256"])
        if (
            not _upload_path(desc["path"])
            or desc["path"] in seen
            or desc["path"] == path.name
        ):
            raise PilotHold("DISTINCT_PUBLIC_RELATIVE_FILES_REQUIRED")
        target = base / desc["path"]
        if (
            _sealed(target)
            or not target.resolve().is_relative_to(base)
            or any(
                p.is_symlink()
                for p in (target, *target.parents)
                if p.is_relative_to(base)
            )
        ):
            raise PilotHold("PUBLIC_LOCAL_PATH_REQUIRED")
        seen.add(desc["path"])
        data = target.read_bytes()
        if len(data) > 95 * 1024 * 1024 or ca.sha256(data) != desc["sha256"]:
            raise PilotHold("SOURCE_PIN_OR_SIZE_MISMATCH")
        docs[role] = data if role == "train" else json.loads(data)
        pins[role] = desc["sha256"]
    return docs, pins


def prepare(docs, pins, *, fixture=False):
    shape(docs, ROLES)
    kit = sk.kit_from_bytes(ca.canonical(docs["domain"]))
    train = ca.load_train(kit, docs["train"], pins["train"])
    if train.fixture != fixture or train.excluded:
        raise PilotHold("FIXTURE_PROMOTION_OR_NONFINITE_TRAIN_REFUSED")
    export = docs["export"]
    shape(export, {"schema", "family", "questions", "export_digest"})
    if (
        export["schema"] != EXPORT
        or export["family"] != sk.FAMILY
        or export["export_digest"]
        != ca.sha256(
            ca.canonical({k: v for k, v in export.items() if k != "export_digest"})
        )
    ):
        raise PilotHold("SOLENOID_EXPORT_IDENTITY_MISMATCH")
    if type(export["questions"]) is not list or not export["questions"]:
        raise PilotHold("BUYER_QUESTIONS_REQUIRED")
    seen = set()
    for e in export["questions"]:
        shape(e, {"case", "support_case", "task", "reference"})
        if (
            e["case"] in seen
            or not isinstance(e["support_case"], str)
            or not e["support_case"]
        ):
            raise PilotHold("UNIQUE_QUESTIONS_AND_PHYSICAL_CLUSTERS_REQUIRED")
        seen.add(e["case"])
        task = e["task"]
        tasks._verify_task_digest(task)
        if task["identity"]["challenge"] != sk.FAMILY or {
            c["id"] for c in task["conditions"]
        } != set(docs["domain"]["conditions"]):
            raise PilotHold("COMPLETE_THREE_STRATUM_TASK_REQUIRED")
        if task["objective"] != {
            "quantity": "force_envelope_error_n",
            "unit": "N",
            "sense": "min",
            "aggregate": "worst",
        }:
            raise PilotHold("OWNER_MINIMAX_FORCE_ENVELOPE_OBJECTIVE_REQUIRED")
        if not {f"force_closing_n_{j:02d}" for j in range(27)} <= {
            lim["quantity"] for lim in task["limits"]
        }:
            raise PilotHold("COMPLETE_FORCE_ENVELOPE_REQUIRED")
        expected = {
            (c, condition["id"])
            for c in task["candidates"]
            for condition in task["conditions"]
        }
        actual = [(r["candidate"], r["condition"]) for r in e["reference"]]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise PilotHold("COMPLETE_CURVE_REFERENCE_REQUIRED")
    physical = cb._physical_rows(export)
    if any(set(r["values"]) != set(sk.OBSERVABLES) for r in physical):
        raise PilotHold("FULL_27_STATE_OBSERVER_INVENTORY_REQUIRED")
    if any(not math.isfinite(v) for r in physical for v in r["values"].values()):
        raise PilotHold("REFERENCE_NONFINITE_NOT_CANDIDATE_FAILURE")
    for row in physical:
        reduced = kit.row_values(row, [{key: row["values"][key] for key in sk.OUTPUTS}])
        if not math.isclose(
            reduced["force_envelope_error_n"],
            row["values"]["force_envelope_error_n"],
            abs_tol=1e-10,
            rel_tol=1e-10,
        ):
            raise PilotHold("BUYER_FORCE_OBSERVER_MISMATCH")
    training = [
        ca.canonical({n: r["inputs"][n] for n, _b in sk.COORDS}) for r in train.records
    ]
    held = {ca.canonical(r["action"]) for r in physical}
    if held.intersection(training):
        raise PilotHold("WHOLE_GEOMETRY_TRAIN_HELDOUT_OVERLAP")
    if len(train.records) != len({ca.canonical(r["inputs"]) for r in train.records}):
        raise PilotHold("DUPLICATE_TRAIN_CURVES")
    if not fixture and (
        len(train.records) != 48
        or len(set(training)) != 16
        or len(held) != 12
        or len(physical) != 36
    ):
        raise PilotHold("REGISTERED_16_TRAIN_12_HELDOUT_GEOMETRIES_REQUIRED")
    if not fixture:
        plan = acquisition_plan()
        wanted_train = {
            ca.canonical(d["coordinates"])
            for d in plan["designs"]
            if d["role"] == "TRAIN"
        }
        wanted_held = {
            ca.canonical(d["coordinates"])
            for d in plan["designs"]
            if d["role"] == "PUBLIC_HELDOUT"
        }
        if set(training) != wanted_train or held != wanted_held:
            raise PilotHold("PREDECLARED_GEOMETRY_PLAN_REQUIRED")
    policy, reference, costs, cheap = (
        docs[k] for k in ("policy", "reference", "costs", "cheap")
    )
    shape(
        policy,
        {
            "schema",
            "scope",
            "export_digest",
            "domain_digest",
            "owner_requirements_digest",
            "question_law",
            "solver_orders",
            "served_decisions",
            "seed_policy",
            "precommit_receipt",
        },
    )
    if (
        policy["schema"] != "carbon.solenoid-pole.pilot-policy.v1"
        or policy["scope"] != ("SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT")
        or policy["export_digest"] != export["export_digest"]
        or policy["domain_digest"] != pins["domain"]
        or policy["seed_policy"] != list(SEEDS)
    ):
        raise PilotHold("PREDECLARED_FAMILY_POLICY_REQUIRED")
    for key in ("owner_requirements_digest", "precommit_receipt"):
        pin(policy[key])
    shape(policy["question_law"], {"P", "Q", "w", "panel_use"})
    if (
        any(
            type(policy["question_law"][k]) is not str
            or policy["question_law"][k] in ("", "HUMAN_INPUT", "OPEN")
            for k in ("P", "Q", "w")
        )
        or policy["question_law"]["panel_use"] != "PUBLIC_HELDOUT"
    ):
        raise PilotHold("DIAGNOSTIC_P_Q_W_IDENTITIES_REQUIRED")
    shape(policy["solver_orders"], seen)
    for e in export["questions"]:
        order = policy["solver_orders"][e["case"]]
        if (
            type(order) is not list
            or len(order) != len(e["task"]["candidates"])
            or set(order) != set(e["task"]["candidates"])
        ):
            raise PilotHold("COMPLETE_ADAPTIVE_ORDER_REQUIRED")
    shape(
        reference,
        {
            "schema",
            "scope",
            "export_digest",
            "domain_digest",
            "image_digest",
            "formulation",
            "observer_scope",
            "source_digests",
            "native_acceptance_receipt",
        },
    )
    if (
        reference["schema"] != "carbon.solenoid-pole.pilot-reference-return.v1"
        or reference["scope"] != policy["scope"]
        or reference["export_digest"] != export["export_digest"]
        or reference["domain_digest"] != pins["domain"]
        or reference["formulation"] != "AXISYMMETRIC_APHI"
        or reference["observer_scope"]
        != "MAXWELL_FORCE_NONLINEAR_COENERGY_VIRTUAL_WORK"
    ):
        raise PilotHold("AXISYMMETRIC_REFERENCE_HOLD")
    pin(reference["image_digest"])
    pin(reference["native_acceptance_receipt"])
    if not reference["source_digests"]:
        raise PilotHold("REFERENCE_SOURCE_HOLD")
    for p in reference["source_digests"]:
        pin(p)
    shape(
        cheap,
        {
            "schema",
            "scope",
            "method",
            "export_digest",
            "train_sha256",
            "domain_digest",
            "precommit_receipt",
            "calibration_role",
            "predictions",
            "query_costs",
            "source_digests",
        },
    )
    if (
        cheap["schema"] != "carbon.solenoid-pole.strongest-cheap-screen.v1"
        or cheap["scope"] != policy["scope"]
        or cheap["export_digest"] != export["export_digest"]
        or cheap["train_sha256"] != pins["train"]
        or cheap["domain_digest"] != pins["domain"]
        or cheap["precommit_receipt"] != policy["precommit_receipt"]
        or cheap["calibration_role"] != "TRAIN_WHOLE_GEOMETRY_ONLY"
        or cheap["method"]
        not in (
            "nonlinear-reluctance-fringing-calibrated",
            "manufacturer-cached-fe-rbf-kriging",
        )
    ):
        raise PilotHold("STRONGEST_TRAIN_ONLY_CHEAP_HOLD")
    if not cheap["source_digests"]:
        raise PilotHold("CHEAP_SOURCE_HOLD")
    for p in cheap["source_digests"]:
        pin(p)
    if cheap["predictions"].get("scope") != policy["scope"]:
        raise PilotHold("CHEAP_FIXTURE_PROMOTION")
    baseline = ep._predictions(export, cheap["predictions"])
    for row in physical:
        key = (None, row["candidate"], row["condition"])
        if key in baseline:
            reduced = kit.row_values(row, [{k: baseline[key][k] for k in sk.OUTPUTS}])
            if not math.isclose(
                reduced["force_envelope_error_n"],
                baseline[key]["force_envelope_error_n"],
                rel_tol=1e-10,
                abs_tol=1e-10,
            ):
                raise PilotHold("CHEAP_FORCE_OBSERVER_MISMATCH")
    shape(cheap["query_costs"], seen)
    for c in cheap["query_costs"].values():
        cost(c)
    shape(
        costs,
        {
            "schema",
            "scope",
            "export_digest",
            "preparation",
            "reference",
            "failed_control_cost",
            "source_digests",
            "new_curve_attempts",
            "new_field_attempts",
        },
    )
    if (
        costs["schema"] != "carbon.solenoid-pole.pilot-costs.v1"
        or costs["scope"] != policy["scope"]
        or costs["export_digest"] != export["export_digest"]
    ):
        raise PilotHold("COMPLETE_COST_IDENTITY_REQUIRED")
    if (
        type(costs["new_curve_attempts"]) is not int
        or not 0 <= costs["new_curve_attempts"] <= 104
        or type(costs["new_field_attempts"]) is not int
        or not 0 <= costs["new_field_attempts"] <= 2952
    ):
        raise PilotHold("REGISTERED_ATTEMPT_CAP_EXCEEDED")
    shape(costs["preparation"], {"model", "baseline"})
    for c in costs["preparation"].values():
        cost(c)
    cost(costs["failed_control_cost"])
    if not costs["source_digests"]:
        raise PilotHold("COST_SOURCE_HOLD")
    for p in costs["source_digests"]:
        pin(p)
    indexed = {}
    for r in costs["reference"]:
        shape(
            r,
            {
                "candidate",
                "condition",
                "cost",
                "planning_bound",
                "field_states",
                "source_digests",
            },
        )
        key = (r["candidate"], r["condition"])
        if (
            key in indexed
            or type(r["field_states"]) is not int
            or r["field_states"] < 27
            or not r["source_digests"]
        ):
            raise PilotHold("COMPLETE_27_STATE_COST_REQUIRED")
        for p in r["source_digests"]:
            pin(p)
        actual, bound = cost(r["cost"]), cost(r["planning_bound"])
        if any(actual[k] <= 0 or bound[k] < actual[k] for k in actual):
            raise PilotHold("COMPLETE_COST_BOUND_REQUIRED")
        indexed[key] = (actual, bound)
    if set(indexed) != {(r["candidate"], r["condition"]) for r in physical}:
        raise PilotHold("REFERENCE_COST_INVENTORY_INCOMPLETE")
    return kit, export, train, policy, costs, indexed, baseline, cheap


def replay(export, model, receipt, policy, costs, indexed, baseline, cheap):
    model = ep._predictions(export, model)
    jobs, learning = [], []
    timings = {
        r["query"]: {"wall_s": r["wall_s"], "core_s": r["cpu_s"]}
        for r in receipt["cost"]["inference"]["decision_queries"]
    }
    for e in export["questions"]:
        task, truth = ep._assess(e, {}, reference=True)["plain"]
        learned = ep._assess(e, model)["plain"][1]
        mapped = ep._assess(e, baseline)["plain"][1]
        orders = {
            "model": ep._order(learned, task),
            "baseline": ep._order(mapped, task),
        }
        candidates = []
        for c in task["candidates"]:
            measured, bound = {"wall_s": 0, "core_s": 0}, {"wall_s": 0, "core_s": 0}
            for condition in task["conditions"]:
                a, b = indexed[(c, condition["id"])]
                for unit in measured:
                    measured[unit] += a[unit]
                    bound[unit] += b[unit]
            status = truth[c]["feasible"]
            candidates.append(
                {
                    "design_id": c,
                    "reference": {
                        "status": (
                            "UNRESOLVED"
                            if status is None
                            else "FEASIBLE" if status else "INFEASIBLE"
                        ),
                        "value": truth[c]["objective"] if status is True else None,
                    },
                    "solve_cost": measured,
                    "planning_bound": bound,
                    "screen_rank": {
                        arm: order.index(c) for arm, order in orders.items()
                    },
                }
            )
        jobs.append(
            {
                "job_id": e["case"],
                "cluster_id": e["support_case"],
                "candidates": candidates,
                "solver_order": policy["solver_orders"][e["case"]],
                "screen_cost": {
                    "model": timings[e["case"]],
                    "baseline": cheap["query_costs"][e["case"]],
                },
            }
        )
        unresolved = any(t["feasible"] is None for t in truth.values())
        pick, best = tasks.select(task, learned), tasks.select(task, truth)
        errors = [
            abs(
                model[(None, r["candidate"], r["condition"])][
                    f"force_closing_n_{j:02d}"
                ]
                - r["values"][f"force_closing_n_{j:02d}"]
            )
            for r in e["reference"]
            if (None, r["candidate"], r["condition"]) in model
            for j in range(27)
        ]
        learning.append(
            {
                "job_id": e["case"],
                "cluster_id": e["support_case"],
                "stratum": "all_mandatory_strata",
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
    first = export["questions"][0]["task"]["objective"]
    if any(e["task"]["objective"] != first for e in export["questions"]):
        raise PilotHold("ONE_BUYER_OBJECTIVE_REQUIRED")
    registered = budget.validate(budget.proposal())
    panel = eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "evidence_scope": "REPRESENTATIVE",
            "customer_result": False,
            "challenge": sk.FAMILY,
            "source_digest": export["export_digest"],
            "decision_rule_id": policy["owner_requirements_digest"],
            "objective": {"direction": first["sense"], "unit": first["unit"]},
            "cost_basis": "MEASURED",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [
                registered.cap(sk.FAMILY, tier).time_compute
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
    query, fit = receipt["cost"]["inference"], receipt["cost"]["fit"]
    prep["model"]["wall_s"] += (
        fit["fit_wall_s"]
        + query["cold_wall_s"]
        + query["wall_s"]
        + sum(r["cold_wall_s"] for r in query["decision_queries"])
    )
    prep["model"]["core_s"] += (
        fit["fit_cpu_s"]
        + query["cold_cpu_s"]
        + query["cpu_s"]
        + sum(r["cold_cpu_s"] for r in query["decision_queries"])
    )
    for arm in prep:
        for unit in prep[arm]:
            prep[arm][unit] += costs["failed_control_cost"][unit]
    return {
        "schema": wp.SCHEMA,
        "evidence_class": "DEVELOPMENT_PUBLIC",
        "panel": panel,
        "registration": budget.proposal(),
        "methods": {
            "model": "PLAIN_L0_MLP",
            "cheap": "STRONGEST_APPLICABLE_CHEAP",
            "solver": "REGISTERED_ADAPTIVE_SOLVER",
        },
        "question_law": policy["question_law"],
        "preparation_cost": prep,
        "served_decisions": policy["served_decisions"],
        "learning": learning,
        "learning_unit": "N",
        "cost_record_digest": ca.sha256(ca.canonical(costs)),
    }


def execute(docs, pins, *, fixture=False, trainer=None):
    kit, export, train, policy, costs, indexed, baseline, cheap = prepare(
        docs, pins, fixture=fixture
    )
    view = copy.deepcopy(export)
    for e in view["questions"]:
        for r in e["reference"]:
            r["values"] = {key: 0.0 for key in sk.OBSERVABLES}
    results, fit_cpu = [], 0.0
    for seed in SEEDS:
        if fit_cpu >= 14400:
            raise PilotHold("AGGREGATE_FIT_CAP_EXHAUSTED")
        if os.name == "posix" and not fixture:
            import resource

            used = resource.getrusage(resource.RUSAGE_SELF)
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (
                    min(
                        math.ceil(used.ru_utime + used.ru_stime + 14400 - fit_cpu),
                        24 * 3600,
                    ),
                    24 * 3600,
                ),
            )
        pred, receipt = (trainer or ca.run)(
            kit,
            view,
            train,
            scope="SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT",
            seed=seed,
            backend="jax",
            code={
                **ca._code_identity(),
                "pilot_module_sha256": ca.sha256(Path(__file__).read_bytes()),
                "launcher_code_ref": os.environ.get("CODE_REF"),
            },
        )
        fit_cpu += receipt["cost"]["fit"]["fit_cpu_s"]
        if fit_cpu > 14400:
            raise PilotHold("AGGREGATE_FIT_CAP_EXCEEDED")
        if os.name == "posix" and not fixture:
            resource.setrlimit(resource.RLIMIT_CPU, (24 * 3600, 24 * 3600))
        source = replay(export, pred, receipt, policy, costs, indexed, baseline, cheap)
        results.append(
            {
                "seed": seed,
                "receipt": receipt,
                "input": source,
                "report": wp.evaluate(
                    source,
                    bootstrap_replicates=100 if fixture else 2000,
                    confidence=0.95,
                    seed=0,
                ),
            }
        )
    return {
        "schema": FIXTURE if fixture else RESULT,
        "scope": "SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT",
        "source_pins": pins,
        "family": sk.FAMILY,
        "reports": results,
        "aggregate_fit_cpu_s": fit_cpu,
        "real_pilot_executed": not fixture,
        "reference_solves": 0,
        "customer_result": False,
        "qualification": "UNDECIDED",
        "thresholds": "HUMAN_INPUT",
    }


def pod_spec(bundle, code_ref):
    from carbon.agent_campaign.pod_jobs import load_spec

    load(bundle)  # source and public-path checks, not scientific adequacy
    manifest = json.loads(Path(bundle).read_text(encoding="utf-8"))
    files = {Path(bundle).name: Path(bundle)}
    files.update(
        {
            r["path"]: Path(bundle).parent / r["path"]
            for r in manifest["sources"].values()
        }
    )
    spec = {
        "schema": "carbon.pod-job.spec.v1",
        "job_id": "solenoid-winnability-pilot",
        "code_ref": code_ref,
        "module": "carbon.development_comparison.solenoid_pilot",
        "args": ["run", "{inputs}/" + Path(bundle).name, "--out", "{out}/pilot.json"],
        "inputs": [
            "docs/development/challenge_pipeline/magnetics-first-panels/panels.json"
        ],
        "image": "study",
        "overlays": {},
        "compute": {"kind": "cpu", "flavor": "cpu5c", "vcpus": 32},
        "minutes": 1790,
        "rate_ceiling_usd_per_hr": 1.20,
        "cap_usd": 36.40,
        "disk_gb": 20,
        "uploads": {
            name: {"sha256": ca.sha256(p.read_bytes())[7:], "bytes": p.stat().st_size}
            for name, p in files.items()
        },
        "collect": [],
    }
    load_spec(spec)
    return spec


def acquisition_plan():
    """Dimensionless proposals only; every absolute/reference binding is HOLD."""
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "docs/development/challenge_pipeline/magnetics-first-panels/panels.json"
    )
    original = json.loads(source.read_text(encoding="utf-8"))["families"][
        "solenoid_pole"
    ]["designs"]

    def radical_inverse(index, base):
        result, factor = 0.0, 1.0 / base
        while index:
            result += (index % base) * factor
            index //= base
            factor /= base
        return result

    def interior(index):
        return {
            name: lo + (hi - lo) * radical_inverse(index, base)
            for (name, (lo, hi)), base in zip(sk.COORDS, (2, 3, 5, 7))
        }

    designs = [
        {"id": f"T{i:02d}", "role": "TRAIN", "coordinates": interior(i)}
        for i in range(1, 17)
    ]
    designs += [
        {
            "id": d["id"],
            "role": "PUBLIC_HELDOUT",
            "coordinates": dict(zip((n for n, _b in sk.COORDS), d["parameters"])),
        }
        for d in original
    ]
    designs += [
        {"id": f"H{i:02d}", "role": "PUBLIC_HELDOUT", "coordinates": interior(16 + i)}
        for i in (1, 2)
    ]
    tuples = [
        {
            "design": d["id"],
            "role": d["role"],
            "stratum": stratum,
            "rung": "primary",
            "field_states": 27,
        }
        for d in designs
        for stratum in sk.STRATA
    ]
    tuples += [
        {
            "design": d,
            "role": "PUBLIC_HELDOUT",
            "stratum": stratum,
            "rung": "refined-plus-virtual-work",
            "field_states": 39,
        }
        for d in ("S01", "S04", "H01", "H02")
        for stratum in sk.STRATA
    ]
    tuples += [
        {
            "design": d,
            "role": "CONTROL",
            "stratum": "CONTROL_HUMAN_INPUT",
            "rung": "control",
            "field_states": 27,
        }
        for d in (
            "zero-current",
            "weak-field-current-reversal",
            "exterior-growth",
            "air-contour-invariance",
        )
    ]
    return {
        "schema": "carbon.solenoid-pole.pilot-acquisition-plan.v1",
        "status": "PROPOSED_HOLD",
        "source_sha256": ca.sha256(source.read_bytes()),
        "designs": designs,
        "tuples": tuples,
        "current_fractions": list(sk.CURRENTS),
        "stroke_fractions": list(sk.STROKES),
        "failed_curve_allowance": 4,
        "max_curve_attempts": 104,
        "max_field_attempts": 2952,
        "probe": {
            "design": "S01",
            "stratum": "nominal",
            "included_in_primary": True,
            "lifecycle_minutes_cap": 30,
            "usd_cap": 1.0,
        },
        "holds": {
            field: "HUMAN_INPUT"
            for field in (
                "absolute_anchor_and_geometry_validity",
                "coherent_material_coil_rights",
                "force_envelope_and_minimax_objective",
                "P_Q_w",
                "axisymmetric_deck_and_observer",
                "native_reference_adequacy",
                "exact_grant_quote_capacity",
                "refinement_widths",
            )
        },
        "automatic_redraws": False,
        "runtime_id_activated": False,
    }


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for command in ("run", "check", "pod-spec", "dry-run", "data-plan"):
        s = sub.add_parser(command)
        if command not in ("dry-run", "data-plan"):
            s.add_argument("bundle", type=Path)
        if command != "check":
            s.add_argument("--out", type=Path, required=True)
        if command == "pod-spec":
            s.add_argument("--code-ref", required=True)
    args = p.parse_args(argv)
    try:
        if args.cmd == "data-plan":
            write(args.out, acquisition_plan())
        elif args.cmd == "dry-run":
            from carbon.development_comparison.solenoid_pilot_fixture import dry_run

            write(args.out, dry_run())
        elif args.cmd == "pod-spec":
            write(args.out, pod_spec(args.bundle, args.code_ref))
        else:
            docs, pins = load(args.bundle)
            if args.cmd == "check":
                prepare(docs, pins)
            else:
                if os.name == "posix":
                    import resource

                    resource.setrlimit(resource.RLIMIT_CPU, (24 * 3600, 24 * 3600))
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
        tasks.TaskError,
        ep.Refusal,
        eb.EqualBudgetError,
        wp.WinnabilityError,
        OSError,
    ) as hold:
        print(
            json.dumps(
                {"status": "HOLD", "reason": str(hold), "candidate_failure": False}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
