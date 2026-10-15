"""Owner-D2 DEVELOPMENT projection of authentic indexed decision primitives.

This is not a championship adapter or a solver. Input provenance/role and
commit-before-reference chronology belong to the producer. The interval input
is a registered numerical enclosure, never a physical confidence interval.
Historical indexed reductions and their results remain unchanged.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from decimal import Decimal

from carbon.design_search import indexed, reference_resolution, tasks

PROJECTION = "carbon.scorelab.battery-v3.band-deadzone-projection.v1"
JOB = "battery-v3-job-dev-v1"
BANDS = (5, 15, 25, 35, 40)
TOLERANCE = Decimal("0.5")


def _number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise tasks.TaskError("finite objective enclosure required")
    return Decimal(str(value))


def _validate(registered):
    indexed.validate_indexed(registered)
    identity = registered["identity"]
    if (
        tuple(row["index_value"] for row in registered["indices"]) != BANDS
        or identity["contract_version"] != JOB
        or identity["objective"]["quantity"] != "minutes"
        or identity["objective"]["unit"] != "min"
        or identity["objective"]["sense"] != "min"
        or identity["index_axis"] != "ambient_c"
        or any(row["task"]["secondary"] is not None for row in registered["indices"])
        or _number(identity["value_equivalence"]["tolerance"]) != TOLERANCE
    ):
        raise tasks.TaskError("owner-v3 job, five bands and minute tolerance required")


def reference_mask(registered, references, intervals):
    """Freeze all-action coverage and winner/deadzone resolution without a model.

    `references` has the existing judge's ordered {index_value, values} shape.
    `intervals` is an equally ordered list of {index_value, candidates}, mapping
    every candidate to {quantity: [lower, upper]} for all required quantities.
    The producer supplies method-bound enclosures, not raw point labels. A missing or
    undecided reference excludes the WHOLE question, including zero-weight bands.
    No member's abstention or unsafe pick can change this mask.
    """
    _validate(registered)
    if (
        type(references) is not list
        or type(intervals) is not list
        or len(references) != len(BANDS)
        or len(intervals) != len(BANDS)
    ):
        raise tasks.TaskError(
            "one reference/enclosure panel per mandatory band required"
        )
    reasons, per_index = [], []
    for row, panel, enclosure in zip(registered["indices"], references, intervals):
        band, subtask = row["index_value"], row["task"]
        if (
            type(panel) is not dict
            or set(panel) != {"index_value", "values"}
            or panel["index_value"] != band
            or type(enclosure) is not dict
            or set(enclosure) != {"index_value", "candidates"}
            or enclosure["index_value"] != band
            or type(panel["values"]) is not dict
            or type(enclosure["candidates"]) is not dict
        ):
            raise tasks.TaskError("reference/enclosure band order differs")
        quantities = {subtask["objective"]["quantity"]} | {
            limit["quantity"] for limit in subtask["limits"]
        }
        complete_rows = {}
        for candidate in subtask["candidates"]:
            for condition in subtask["conditions"]:
                key = (candidate, condition["id"])
                values = panel["values"].get(key)
                if type(values) is dict and all(
                    type(values.get(q)) in (int, float) and math.isfinite(values[q])
                    for q in quantities
                ):
                    complete_rows[key] = values
                else:
                    reasons.append(
                        [band, candidate, "MISSING_OR_INVALID_REFERENCE_ROW"]
                    )
        # Incomplete records are UNKNOWN, not fabricated complete quantities.
        truth = tasks.assess(subtask, complete_rows, reference=True)
        if set(enclosure["candidates"]) - set(subtask["candidates"]):
            raise tasks.TaskError("enclosure candidate outside registered bank")
        bounds = {}
        for candidate in subtask["candidates"]:
            quantity_intervals = enclosure["candidates"].get(candidate)
            if type(quantity_intervals) is not dict or not quantities <= set(
                quantity_intervals
            ):
                reasons.append([band, candidate, "MISSING_OBJECTIVE_ENCLOSURE"])
                truth[candidate]["feasible"] = None
                continue
            checked = {}
            for quantity in quantities:
                interval = quantity_intervals[quantity]
                if type(interval) is not list or len(interval) != 2:
                    raise tasks.TaskError("quantity enclosure needs two endpoints")
                low, high = map(_number, interval)
                for condition in subtask["conditions"]:
                    values = complete_rows.get((candidate, condition["id"]))
                    if (
                        values is not None
                        and not low <= _number(values[quantity]) <= high
                    ):
                        raise tasks.TaskError("reference point outside its enclosure")
                checked[quantity] = (low, high)
            bounds[candidate] = checked[subtask["objective"]["quantity"]]
            if all(
                (candidate, cond["id"]) in complete_rows
                for cond in subtask["conditions"]
            ):
                verdicts = []
                for limit in subtask["limits"]:
                    low, high = checked[limit["quantity"]]
                    threshold = _number(limit["value"])
                    if limit["op"] == "<=":
                        verdicts.append(
                            True
                            if high <= threshold
                            else False if low > threshold else None
                        )
                    else:
                        verdicts.append(
                            True
                            if low >= threshold
                            else False if high < threshold else None
                        )
                truth[candidate]["feasible"] = (
                    False if False in verdicts else None if None in verdicts else True
                )
        unknown = [c for c, value in truth.items() if value["feasible"] is None]
        feasible = [c for c, value in truth.items() if value["feasible"] is True]
        if unknown:
            reasons.extend([band, c, "UNRESOLVED_REFERENCE"] for c in unknown)
        best = tasks.select(subtask, truth)
        if best is not None and best in bounds and all(c in bounds for c in feasible):
            best_low, best_high = bounds[best]
            best_order = subtask["candidates"].index(best)
            for candidate in feasible:
                if candidate == best:
                    continue
                low, high = bounds[candidate]
                if best_high > low or (
                    best_high == low
                    and best_order > subtask["candidates"].index(candidate)
                ):
                    reasons.append([band, candidate, "WINNER_INTERVAL_AMBIGUOUS"])
                delta_low = max(Decimal(0), low - best_high)
                delta_high = max(Decimal(0), high - best_low)
                if delta_low <= TOLERANCE < delta_high:
                    reasons.append([band, candidate, "DEADZONE_INTERVAL_AMBIGUOUS"])
        per_index.append(
            {
                "index_value": band,
                "reference_best": best,
                "feasible_candidates": len(feasible),
                "verdicts": [
                    {"candidate": c, "feasible": value["feasible"]}
                    for c, value in truth.items()
                    if value["feasible"] is not None
                ],
                "reference_state": (
                    "UNRESOLVED"
                    if unknown
                    else "FEASIBLE_EXISTS" if feasible else "NONE_FEASIBLE"
                ),
            }
        )
    # Native reference dictionaries have tuple keys, so pin their ordered rows.
    reference_rows = [
        {
            "index_value": p["index_value"],
            "rows": [[*key, value] for key, value in sorted(p["values"].items())],
        }
        for p in references
    ]
    body = {
        "projection": PROJECTION,
        "task_digest": registered["task_digest"],
        "reference_digest": tasks.digest(reference_rows),
        "enclosure_digest": tasks.digest(intervals),
        "included": not reasons,
        "reference_state": (
            "UNRESOLVED"
            if reasons
            else (
                "NONE_FEASIBLE"
                if any(r["reference_state"] == "NONE_FEASIBLE" for r in per_index)
                else "FEASIBLE_EXISTS"
            )
        ),
        "reasons": reasons,
        "per_index": per_index,
    }
    return {**body, "mask_digest": tasks.digest(body)}


def judge(
    registered,
    commitment,
    references,
    intervals,
    *,
    scope,
    producer_evidence=None,
    producer_binding=None,
):
    """Reuse the canonical judge; reduce its band regrets with owner-D2 order.

    Unsafe/abstaining/unknown outcomes have NO finite minute penalty invented
    here. They remain typed and cannot qualify for a regret-only ranking.
    """
    if scope not in ("SYNTHETIC_FIXTURE", "PUBLIC_DEVELOPMENT"):
        raise tasks.TaskError("development-only projection")
    producer_proof = None
    if scope == "PUBLIC_DEVELOPMENT" and (
        producer_evidence is None or producer_binding is None
    ):
        raise tasks.TaskError(
            "PUBLIC projection requires the registered producer numerical-evidence bridge"
        )
    if producer_evidence is not None:
        from .owner_v3_panel_export import validate_for

        receipt = validate_for(
            producer_evidence, registered, references, intervals, scope=scope
        )
        if (
            type(producer_binding) is not dict
            or set(producer_binding)
            != {"plan_digest", "source_pins_digest", "manifest_digest"}
            or any(producer_binding[k] != receipt.get(k) for k in producer_binding)
            or receipt.get("scope") != scope
        ):
            raise tasks.TaskError("prebound producer registration or scope differs")
        producer_proof = {
            "registration": dict(producer_binding),
            "receipt_digest": tasks.digest(receipt),
        }
    mask = reference_mask(registered, references, intervals)
    body = {k: v for k, v in commitment.items() if k != "commitment_digest"}
    if (
        tasks.digest(body) != commitment.get("commitment_digest")
        or commitment.get("task_digest") != registered["task_digest"]
    ):
        raise tasks.TaskError("altered or foreign indexed commitment")
    if not mask["included"]:
        result = {
            "schema": PROJECTION,
            "scope": scope,
            "producer": producer_proof,
            "job": JOB,
            "task_digest": registered["task_digest"],
            "commitment_digest": commitment["commitment_digest"],
            "reference_mask": mask,
            "kind": "REFERENCE_UNRESOLVED",
            "per_index": mask["per_index"],
            "regret_min": None,
            "regret_ranking_eligible": False,
            "historical_aggregate_regret_unchanged": None,
            "qualification": False,
        }
        return {**result, "primitive_digest": tasks.digest(result)}
    historical = tasks.judge_indexed(registered, commitment, references)
    settled = [
        {"index_value": r["index_value"], "verdicts": r["verdicts"]}
        for r in mask["per_index"]
    ]
    base = reference_resolution.judge_indexed(
        registered, commitment, references, settled
    )
    per_index = base["per_index"]
    unavailable = any(
        commitment["execution"][key] > 0
        for key in ("model_failures", "invalid_queries")
    )
    comparable = base["kind"] == "SELECTED_FEASIBLE" and not unavailable
    weighted = []
    for row in per_index:
        regret = row["outcome"]["regret"]
        weighted.append(
            None
            if not comparable
            else float(_number(row["buyer_weight"]) * _number(regret))
        )
    regret = (
        float(sum((Decimal(str(x)) for x in weighted), Decimal(0)))
        if comparable
        else None
    )
    result = {
        "schema": PROJECTION,
        "scope": scope,
        "producer": producer_proof,
        "job": JOB,
        "task_digest": registered["task_digest"],
        "commitment_digest": commitment["commitment_digest"],
        "reference_mask": mask,
        "kind": "CANDIDATE_UNAVAILABLE" if unavailable else base["kind"],
        "per_index": [
            {**row, "weighted_regret_min": contribution}
            for row, contribution in zip(per_index, weighted)
        ],
        "regret_min": regret,
        "regret_ranking_eligible": comparable,
        "historical_aggregate_regret_unchanged": historical["regret"],
        "qualification": False,
    }
    return {**result, "primitive_digest": tasks.digest(result)}


def model_summary(outcomes, *, expected_masks):
    """Price a fixed reference-only F stratum, retaining all offered outcomes.

    Correct NONE abstention is not missing truth. Within the common reference
    FEASIBLE_EXISTS stratum, any unsafe/missed/unavailable pick withholds the
    whole member's mean. This is NOT a complete-P scalar or a new gate value.
    """
    rows = list(outcomes)
    if len({r["task_digest"] for r in rows}) != len(rows):
        raise tasks.TaskError("duplicate offered question")
    if set(expected_masks) != {r["task_digest"] for r in rows}:
        raise tasks.TaskError("missing or foreign offered question")
    for row in rows:
        expected = expected_masks[row["task_digest"]]
        body = {k: v for k, v in expected.items() if k != "mask_digest"}
        if (
            expected.get("task_digest") != row["task_digest"]
            or tasks.digest(body) != expected.get("mask_digest")
            or row["reference_mask"] != expected
        ):
            raise tasks.TaskError("offered reference mask differs")
    n = len(rows)
    priced = [
        r for r in rows if r["reference_mask"]["reference_state"] == "FEASIBLE_EXISTS"
    ]
    eligible = bool(priced) and all(r["regret_ranking_eligible"] for r in priced)
    return {
        "offered_questions": n,
        "kind_counts": dict(sorted(Counter(r["kind"] for r in rows).items())),
        "reference_FEASIBLE_EXISTS_questions": len(priced),
        "regret_estimand": "E[L | FEASIBLE_EXISTS, reference adequate, frozen bank]",
        "full_population_scalar_available": False,
        "regret_ranking_eligible": eligible,
        "mean_regret_min": (
            sum(r["regret_min"] for r in priced) / len(priced) if eligible else None
        ),
        "infeasible_pick_count": sum(
            any(
                b.get("outcome", {}).get("kind") == "SELECTED_INFEASIBLE"
                for b in r["per_index"]
            )
            for r in rows
        ),
        "missed_opportunity_count": sum(
            r["reference_mask"]["reference_state"] == "FEASIBLE_EXISTS"
            and any(
                b.get("outcome", {}).get("kind") == "MISSED_OPPORTUNITY"
                for b in r["per_index"]
            )
            for r in rows
        ),
        "correct_abstention_count": sum(
            r["kind"] == "CORRECT_ABSTENTION" for r in rows
        ),
        "unresolved_reference_count": sum(
            not r["reference_mask"]["included"] for r in rows
        ),
    }


def cohort_member(cohort, *, expected_digest, recipe_id, seed):
    """Arguments for the EXISTING arm, never a trainer or an execution route.

    The caller binds the registered digest and chronology before execution.
    Each recipe/seed has a distinct model ID. The same settings under a new
    kit/TRAIN are a new artifact, not a relabelled historical EV4 model.
    """
    from dataclasses import replace

    from carbon.development_comparison import battery_v3_kit, carbon_arm

    if (
        tasks.digest(cohort) != expected_digest
        or cohort.get("schema") != "carbon.scorelab.battery-v3.cohort.v1"
        or cohort.get("scope") != "PUBLIC_DEVELOPMENT"
        or cohort.get("base_settings") != carbon_arm.TRAINER_DEFAULTS
        or tasks.digest(cohort["base_settings"]) != cohort.get("base_settings_digest")
        or cohort.get("kit") != battery_v3_kit.KIT.kit_id
        or cohort.get("trainer") != carbon_arm.TRAINER
        or cohort.get("backend") not in ("jax", "pytorch")
    ):
        raise tasks.TaskError("registered cohort, trainer and base settings required")
    recipes = {row["id"]: row["overrides"] for row in cohort["recipes"]}
    if len(recipes) != len(cohort["recipes"]) or recipe_id not in recipes:
        raise tasks.TaskError("recipe outside registered cohort")
    if type(seed) is not int or seed not in cohort["seeds"]:
        raise tasks.TaskError("seed outside registered cohort")
    overrides = recipes[recipe_id]
    if set(overrides) - set(carbon_arm.TRAINER_DEFAULTS):
        raise tasks.TaskError("unknown trainer setting")
    settings = {**cohort["base_settings"], **overrides}
    model_id = f"{cohort['id']}:{recipe_id}:seed{seed}"
    return {
        "kit": replace(battery_v3_kit.KIT, model_id=model_id),
        "settings": settings,
        "seed": seed,
        "backend": cohort["backend"],
        "code": {
            "cohort_digest": expected_digest,
            "recipe_id": recipe_id,
            "recipe_settings_digest": tasks.digest(settings),
            "selection": "prospectively fixed cohort; producer binds merge chronology",
        },
    }


def acquisition_inputs(plan, *, expected_digest, stage):
    """Materialize registered inputs for feasibility02, never run the worker.

    Root may subtract only authenticated exact reuse and must retain the
    offered input manifest. Refinement is a separate conditional plan, not
    permission to launch it for every tuple.
    """
    if (
        tasks.digest(plan) != expected_digest
        or plan.get("schema") != "carbon.scorelab.acquisition-plan.v1"
        or plan.get("job") != JOB
        or plan.get("scope") != "DEVELOPMENT_ONLY"
        or plan.get("bands_c") != list(BANDS)
        or plan.get("cooling") != [1, 2, 4]
        or plan.get("soc0") != 0.1
        or plan.get("cycles") != 30
    ):
        raise tasks.TaskError("registered acquisition plan required")
    if stage not in (
        "calibration-pilot",
        "calibration-rest",
        "evaluation",
        "refinement",
    ):
        raise tasks.TaskError("unknown acquisition input stage")
    calibration = stage.startswith("calibration")
    profiles = plan["calibration" if calibration else "fallback_evaluation"]["profiles"]
    pilot = {tuple(pair) for pair in plan["calibration"]["first_wave_t_h"]}
    meshes = (
        (20, 40, 80) if calibration else (80,) if stage == "refinement" else (20, 40)
    )
    jobs = []
    for c1, c2, switch in profiles:
        for band in BANDS:
            for cooling in plan["cooling"]:
                if calibration and ((band, cooling) in pilot) != (
                    stage == "calibration-pilot"
                ):
                    continue
                for mesh in meshes:
                    jobs.append(
                        {
                            "case_id": f"scorelab-v3:{'cal' if calibration else 'eval'}:c1={c1:.2f}:c2={c2:.2f}:sv={switch:.2f}:T{band}:h{cooling}:mesh{mesh}",
                            "c1": c1,
                            "c2": c2,
                            "switch_voltage_v": switch,
                            "h_multiplier": cooling,
                            "t_amb_c": band,
                            "soc0": 0.1,
                            "refined": mesh != 20,
                            "rung": {20: 1, 40: 2, 80: 3}[mesh],
                        }
                    )
    return {"batch": f"scorelab-v3-{stage}-dev-v1", "jobs": jobs}


def population_tasks(plan, *, expected_plan_digest, count):
    """Input-only P tasks for the frozen fallback bank; no truth or models.

    Dirichlet draws use registered CPython Random.gammavariate. Largest-
    remainder quantization to 1e-12 gives exact unit-sum buyer weights and
    error below 1e-12 per band. Q requires its separate discovery support.
    """
    from .owner_v3_panel_export import OBSERVER

    jobs = acquisition_inputs(
        plan, expected_digest=expected_plan_digest, stage="evaluation"
    )["jobs"]
    initial, maximum = plan["questions"]["initial_P"], plan["questions"]["max_P"]
    if type(count) is not int or not 0 < count <= maximum:
        raise tasks.TaskError("bounded registered public P count required")
    actions = {}
    for row in jobs:
        action = {
            "c1": row["c1"],
            "c2": row["c2"],
            "switch_v": row["switch_voltage_v"],
            "cooling": row["h_multiplier"],
        }
        actions.setdefault(tasks.digest(action), action)
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": f"{JOB}.fallback60.actions.v1",
        "variables": [
            {"name": "c1", "type": "number", "min": 0.25, "max": 2, "step": 0.01},
            {"name": "c2", "type": "number", "min": 0.25, "max": 2, "step": 0.01},
            {"name": "switch_v", "type": "number", "min": 4, "max": 4.15, "step": 0.05},
            {"name": "cooling", "type": "integer", "min": 1, "max": 4, "step": 1},
        ],
        "rules": [
            {
                "kind": "linear",
                "coefficients": {"c2": 1, "c1": -1},
                "op": "<=",
                "value": 0,
            }
        ],
    }
    rng = random.Random(plan["questions"]["seed"])
    result = []
    for i in range(count):
        gamma = [Decimal(str(rng.gammavariate(a, 1))) for a in (2, 3, 8, 5, 2)]
        exact = [g / sum(gamma) * 10**12 for g in gamma]
        units = [int(v) for v in exact]
        remainder_order = sorted(range(5), key=lambda b: (-(exact[b] - units[b]), b))
        for b in remainder_order[: 10**12 - sum(units)]:
            units[b] += 1
        thermal_margin, plating_margin = rng.uniform(0, 2.5), rng.uniform(0, 0.002)
        indices = []
        qid = f"public-battery-v3-P{i:03d}"
        for band, weight in zip(BANDS, units):
            condition = f"T{band}"
            subtask = tasks.task(
                f"{qid}-{condition}",
                identity={
                    "challenge": "battery-fastcharge-ageing-development-v1",
                    "contract_version": JOB,
                    "action_grammar": grammar,
                    "optimizer": {"class": "exhaustive", "version": "v1"},
                    "query_budget": len(actions),
                    "seed": plan["questions"]["seed"],
                    "observer_version": OBSERVER,
                    "reference_bank": expected_plan_digest,
                },
                conditions=[{"id": condition, "stratum": "fresh-state"}],
                strata={"fresh-state": {"p": 1, "q": 1, "w": 1}},
                candidates=list(actions),
                actions=actions,
                objective={
                    "quantity": "minutes",
                    "unit": "min",
                    "sense": "min",
                    "aggregate": "worst",
                },
                limits=[
                    {
                        "quantity": "charging_t_max_c",
                        "unit": "C",
                        "op": "<=",
                        "value": 45 - thermal_margin,
                    },
                    {
                        "quantity": "plating_min_v",
                        "unit": "V",
                        "op": ">=",
                        "value": plating_margin,
                    },
                    {"quantity": "v_max_v", "unit": "V", "op": "<=", "value": 4.2},
                    {"quantity": "q30_over_q1", "unit": "1", "op": ">=", "value": 0.99},
                ],
            )
            indices.append(
                {"index_value": band, "buyer_weight": weight / 10**12, "task": subtask}
            )
        registered = indexed.indexed_task(
            qid,
            index_axis="ambient_c",
            indices=indices,
            query_budget=5 * len(actions),
            value_equivalence={
                "quantity": "minutes",
                "unit": "min",
                "tolerance": 0.5,
                "rule": indexed.EQUIVALENCE_RULE,
            },
        )
        result.append(
            {
                "population": "P",
                "role": "LEG" if i % initial < initial // 2 else "VALUE",
                "outer_weight": 1,
                "bank_cluster": expected_plan_digest,
                "buyer_mix_quantization_error_bound": 1e-12,
                "task": registered,
            }
        )
    return result
