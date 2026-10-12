"""Build a development comparison design from registered producer evidence.

This is an arithmetic replay. It never invokes a model or reference solver.
The adaptive competitor still needs an independent pre-experiment policy receipt.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from carbon.design_search import budget_registration, equal_budget, tasks
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_pipeline as ep
from carbon.development_comparison import value_bar as vb

ROOT = Path(__file__).resolve().parents[3]
METHODS = {"battery-v3": "protocol", "motor": "gaussian", "f02": "impulse-response"}


class DesignRefused(ValueError):
    """The producer has not supplied a complete registered comparison design."""


def registration(family):
    name = (
        "equal-budget-registration-v2-f02-menu.json"
        if family == "f02"
        else "equal-budget-registration-v1.json"
    )
    raw = json.loads((ROOT / "docs/development/challenge_pipeline" / name).read_text())
    registered = budget_registration.validate(raw)
    if family not in registered.challenges:
        raise DesignRefused("BUDGET_FAMILY_NOT_REGISTERED")
    return registered


def _battery_choices(entry, model, baseline, envelopes):
    """Build cross-band maps from actions and committed screens, before truth."""
    parts = cb._panels(entry)
    bands = [str(band) for band, _, _ in parts]
    groups = {}
    for band, task, _ in parts:
        for candidate in task["candidates"]:
            action = task["actions"][candidate]
            protocol = (action["c1"], action["c2"], action["switch_v"])
            groups.setdefault(protocol, {}).setdefault(str(band), []).append(candidate)
    assessments = {
        "model": ep._assess(entry, model),
        "baseline": ep._assess(entry, baseline, envelopes=envelopes),
    }
    maps = []
    for protocol in sorted(groups):
        by_band = groups[protocol]
        if set(by_band) != set(bands):
            continue
        # Uniform cooling maps preserve the registered protocol and permit
        # a per-band cooling decision. Arm-specific maps use predictions only.
        common_cooling = set.intersection(
            *(
                {task["actions"][c]["cooling"] for c in by_band[str(band)]}
                for band, task, _ in parts
            )
        )
        for cooling in sorted(common_cooling):
            maps.append(
                {
                    str(band): next(
                        c
                        for c in by_band[str(band)]
                        if task["actions"][c]["cooling"] == cooling
                    )
                    for band, task, _ in parts
                }
            )
        for arm in ("model", "baseline"):
            maps.append(
                {
                    str(band): next(
                        c
                        for c in ep._order(assessments[arm][str(band)][1], task)
                        if c in by_band[str(band)]
                    )
                    for band, task, _ in parts
                }
            )
    unique = {}
    for choices in maps:
        unique.setdefault(tasks.digest(choices), choices)
    if not unique or len(unique) > 512:
        raise DesignRefused("BATTERY_MAP_BANK_ABSENT_OR_TOO_LARGE")
    return {f"map-{i:04d}": choices for i, choices in enumerate(unique.values())}


def _ledger_cost(ledger, entry, choices):
    by_key = {(r["band"], r["candidate"], r["condition"]): r for r in ledger["rows"]}
    wall = core = 0.0
    for band, task, _ in cb._panels(entry):
        name = "plain" if band is None else str(band)
        candidate = choices[name]
        for condition in task["conditions"]:
            row = by_key.get((band, candidate, condition["id"]))
            if row is None:
                raise DesignRefused("CANDIDATE_COMPLETE_CONDITION_COST_MISSING")
            wall += row["wall_s"]
            # The battery solver has a one-core cap and the producer records
            # wall time only. This is a conservative upper bound, not CPU metering.
            core += row["wall_s"] if row["core_s"] is None else row["core_s"]
    if not math.isfinite(wall) or not math.isfinite(core) or min(wall, core) <= 0:
        raise DesignRefused("POSITIVE_COMPLETE_PANEL_COST_REQUIRED")
    return {"wall_s": wall, "core_s": core}


def _screen_costs(receipt, baseline_cost):
    fit = receipt["cost"]["fit"]
    query = receipt["cost"]["inference"]
    model = {
        "wall_s": fit["fit_wall_s"] + query["wall_s"],
        "core_s": fit["fit_cpu_s"] + query["cpu_s"],
    }
    if "fit_reduction_query_cost" in baseline_cost:
        cost = baseline_cost["fit_reduction_query_cost"]
        baseline = {"wall_s": cost["wall_s"], "core_s": cost["cpu_s"]}
    else:
        baseline = {
            "wall_s": baseline_cost["fit"]["wall_s"]
            + baseline_cost["queries"]["wall_s"],
            "core_s": baseline_cost["fit"]["cpu_s"] + baseline_cost["queries"]["cpu_s"],
        }
    for arm, cost in (("model", model), ("baseline", baseline)):
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0
            for v in cost.values()
        ):
            raise DesignRefused(f"{arm.upper()}_SCREEN_COST_INVALID")
    # Every job is charged the complete observed fit and screen workflow.
    # No amortization across requirements is silently assumed.
    return {"model": model, "baseline": baseline}


def build(export, ledger, predictions, receipt, comparator, bindings=None):
    """Return a sealed replay and action bindings; all picks precede truth."""
    family = export["family"]
    registered = registration(family)
    method = METHODS[family]
    baseline, envelopes, baseline_cost = ep._baseline(
        export, comparator, method, require_fine_witness=family == "f02"
    )
    model = ep._predictions(export, predictions)
    screen_cost = _screen_costs(receipt, baseline_cost)
    bound_by_case = {}
    if family != "battery-v3":
        if (
            type(bindings) is not dict
            or bindings.get("schema") != ep.BINDINGS
            or bindings.get("export_digest") != export["export_digest"]
        ):
            raise DesignRefused("PRODUCER_BINDINGS_MISSING_OR_MISMATCHED")
        bound_by_case = {r["case"]: r["candidates"] for r in bindings["jobs"]}
    jobs, bound_jobs = [], []
    objective = None
    for entry in export["questions"]:
        parts = ep._assess(entry, {}, reference=True)
        task = next(iter(parts.values()))[0]
        weights = (
            {
                str(row["index_value"]): row["buyer_weight"]
                for row in entry["task"]["indices"]
            }
            if family == "battery-v3"
            else None
        )
        current_objective = {
            "unit": task["objective"]["unit"],
            "direction": task["objective"]["sense"],
            **({"index_weights": weights} if weights is not None else {}),
        }
        if objective is not None and current_objective != objective:
            raise DesignRefused("INCONSISTENT_OBJECTIVE_ACROSS_QUESTIONS")
        objective = current_objective
        choices = (
            _battery_choices(entry, model, baseline, envelopes)
            if family == "battery-v3"
            else bound_by_case.get(entry["case"])
        )
        if type(choices) is not dict or not choices:
            raise DesignRefused("BOUND_CANDIDATE_BANK_MISSING")
        ranks = {}
        for arm, values, bounds in (
            ("model", model, None),
            ("baseline", baseline, envelopes),
        ):
            assessed = ep._assess(entry, values, envelopes=bounds)
            ranks[arm] = {
                candidate: i
                for i, candidate in enumerate(
                    ep._rank_bound_choices(parts, assessed, choices, weights)
                )
            }
        candidates = []
        for candidate, action_map in choices.items():
            reference = ep._reference(parts, action_map, weights)
            if family != "battery-v3":
                reference = {
                    key: value for key, value in reference.items() if key != "per_index"
                }
            candidates.append(
                {
                    "design_id": candidate,
                    "reference": reference,
                    "solve_cost": _ledger_cost(ledger, entry, action_map),
                    "planning_bound": None,
                    "screen_rank": {arm: ranks[arm][candidate] for arm in ranks},
                }
            )
        planning = {
            unit: max(row["solve_cost"][unit] for row in candidates)
            for unit in ("wall_s", "core_s")
        }
        for row in candidates:
            row["planning_bound"] = planning.copy()
        jobs.append(
            {
                "job_id": entry["case"],
                "cluster_id": entry["support_case"],
                "candidates": candidates,
                "solver_order": list(choices),
                "screen_cost": screen_cost,
            }
        )
        bound_jobs.append(
            {"job_id": entry["case"], "case": entry["case"], "candidates": choices}
        )
    replay = equal_budget.seal(
        {
            "schema": equal_budget.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": family,
            "source_digest": export["export_digest"],
            "decision_rule_id": f"{family}:{export['challenge_id']}:{registered.registration_id}",
            "objective": objective,
            "cost_basis": "ASSUMPTION" if family == "battery-v3" else "MEASURED",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [
                registered.cap(family, tier).time_compute
                for tier in budget_registration.TIERS
            ],
            "jobs": jobs,
            "registrations": {
                "solver_search": "registered-order-v1",
                "model_screen": receipt["model_id"],
                "baseline_screen": method,
                "cost_plan": registered.registration_id,
            },
        }
    )
    bound = {
        "schema": ep.BINDINGS,
        "export_digest": export["export_digest"],
        "jobs": bound_jobs,
    }
    ep._verify_replay(export, replay, bound, baseline, model, envelopes)
    return replay, bound


def _measured_speed(export, ledger, receipt):
    """Pair warm full-question inference with serial reference panel wall time.

    The result is a wall-time receipt only. A stage CPU total cannot establish
    the CPU time of one reference solve for the flagship allowance.
    """
    if ledger is None or receipt is None:
        return None
    measured = receipt.get("cost", {}).get("inference", {}).get("decision_queries")
    if measured is None:
        return None  # older batched receipts cannot be divided into questions
    if (
        type(measured) is not list
        or ledger.get("export_digest") != export["export_digest"]
        or receipt.get("export_digest") != export["export_digest"]
    ):
        raise DesignRefused("DECISION_QUERY_METER_IDENTITY_INVALID")
    timing = {}
    for row in measured:
        if (
            type(row) is not dict
            or set(row)
            != {
                "query",
                "physical_rows",
                "model_queries",
                "cold_wall_s",
                "cold_cpu_s",
                "wall_s",
                "cpu_s",
            }
            or not isinstance(row["query"], str)
            or not row["query"]
            or row["query"] in timing
        ):
            raise DesignRefused("DECISION_QUERY_METER_INVALID")
        if (
            type(row["physical_rows"]) is not int
            or type(row["model_queries"]) is not int
            or row["physical_rows"] <= 0
            or row["model_queries"] < row["physical_rows"]
            or any(
                type(row[name]) not in (int, float)
                or not math.isfinite(row[name])
                or row[name] < 0
                for name in ("cold_wall_s", "cold_cpu_s", "wall_s", "cpu_s")
            )
            or row["wall_s"] <= 0
        ):
            raise DesignRefused("DECISION_QUERY_METER_INVALID")
        timing[row["query"]] = row
    if set(timing) != {q["case"] for q in export["questions"]}:
        raise DesignRefused("DECISION_QUERY_METER_INVENTORY_MISMATCH")
    costs = {(r["band"], r["candidate"], r["condition"]): r for r in ledger["rows"]}
    if len(costs) != len(ledger["rows"]):
        raise DesignRefused("DECISION_QUERY_REFERENCE_INVENTORY_MISMATCH")
    pairs = []
    for question in export["questions"]:
        keys = [
            (band, row["candidate"], row["condition"])
            for band, _task, panel in cb._panels(question)
            for row in panel
        ]
        if (
            not keys
            or len(keys) != len(set(keys))
            or len(keys) != timing[question["case"]]["physical_rows"]
            or any(key not in costs for key in keys)
        ):
            raise DesignRefused("DECISION_QUERY_REFERENCE_INVENTORY_MISMATCH")
        walls = [costs[key]["wall_s"] for key in keys]
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in walls
        ):
            raise DesignRefused("DECISION_QUERY_REFERENCE_COST_INVALID")
        pairs.append(
            {
                "query": question["case"],
                "reference_wall_s": sum(walls),
                "carbon_wall_s": timing[question["case"]]["wall_s"],
            }
        )
    return {
        "schema": vb.SPEED_SCHEMA,
        "export_digest": export["export_digest"],
        "status": "MEASURED",
        "query_unit": "full_registered_decision_query",
        "route": "serial-complete-panel-vs-warm-carbon-question-v1",
        "pairs": pairs,
        "reference_solve_core_s": None,
        "reference_solve_source_digest": None,
    }


def value_context(export, predictions, ledger=None, receipt=None):
    """Bind selection, independent support clusters and paired query speed."""
    groups = {}
    for question in export["questions"]:
        groups.setdefault(question["support_case"], []).append(question["case"])
    folds = None
    if len(groups) >= 2:
        ordered = sorted(groups)
        halves = (ordered[::2], ordered[1::2])
        folds = {
            "schema": "carbon.challenge-value-heldout-folds.v1",
            "export_digest": export["export_digest"],
            "folds": [
                {
                    "fold_id": f"fold-{i + 1}",
                    "source_digest": tasks.digest(
                        {
                            "support_cases": subset,
                            "export_digest": export["export_digest"],
                        }
                    ),
                    "questions": [
                        case for support in subset for case in groups[support]
                    ],
                }
                for i, subset in enumerate(halves)
            ],
        }
    return {
        "schema": ep.CONTEXT,
        "export_digest": export["export_digest"],
        "selection": {
            "carbon_model_id": predictions["model_id"],
            "baseline_id": export["family"],
            "selection_role": "TRAIN",
            "selection_receipt_digest": predictions["source_receipt_digest"],
        },
        "folds": folds,
        "speed": _measured_speed(export, ledger, receipt),
        "item_1": None,
        "item_4": None,
    }
