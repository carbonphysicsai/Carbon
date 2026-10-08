"""Indexed design decisions assembled from registered runnable sub-tasks.

Each index is a mandatory choice. Buyer-mix weights aggregate objective
values only after every selected index passes its own hard limits. This is a
DEVELOPMENT contract, not a battery-v3 scientific registration.
"""

from __future__ import annotations

import json
from decimal import Decimal

from carbon.design_search import tasks

ALLOCATION_RULE = "fixed_registered_quotas_in_index_order.v1"
EQUIVALENCE_RULE = "zero_within_absolute_objective_delta.v1"


def indexed_task(task_id, *, index_axis, indices, query_budget, value_equivalence):
    """Register one decision with fixed per-index optimizer quotas."""
    if type(task_id) is not str or not task_id:
        raise tasks.TaskError("indexed task id required")
    if type(index_axis) is not str or not index_axis:
        raise tasks.TaskError("registered index axis required")
    if type(indices) is not list or len(indices) < 2:
        raise tasks.TaskError("indexed decision needs at least two indices")
    if type(query_budget) is not int or query_budget <= 0:
        raise tasks.TaskError("positive shared query budget required")
    if type(value_equivalence) is not dict or set(value_equivalence) != {
        "quantity",
        "unit",
        "tolerance",
        "rule",
    }:
        raise tasks.TaskError("registered objective value equivalence required")
    if (
        value_equivalence["rule"] != EQUIVALENCE_RULE
        or tasks._number(value_equivalence["tolerance"], "value-equivalence tolerance")
        < 0
    ):
        raise tasks.TaskError("nonnegative registered value tolerance required")
    seen = set()
    total_weight = Decimal(0)
    total_budget = 0
    common = None
    rows = []
    for row in indices:
        if type(row) is not dict or set(row) != {
            "index_value",
            "buyer_weight",
            "task",
        }:
            raise tasks.TaskError("index needs value, buyer weight and task")
        value = row["index_value"]
        if type(value) not in (str, int, float) or (type(value) is str and not value):
            raise tasks.TaskError("index value must be a scalar")
        if type(value) in (int, float):
            tasks._number(value, "index value")
        key = (
            ("number", tasks._number(value, "index value"))
            if type(value) in (int, float)
            else ("string", value)
        )
        if key in seen:
            raise tasks.TaskError("index values must be distinct")
        seen.add(key)
        weight = tasks._number(row["buyer_weight"], "buyer weight")
        if weight < 0:
            raise tasks.TaskError("buyer weights must be nonnegative")
        total_weight += weight
        subtask = row["task"]
        if type(subtask) is not dict or subtask.get("schema") != tasks.RUNNABLE_SCHEMA:
            raise tasks.TaskError("every index needs a runnable task")
        tasks._verify_task_digest(subtask)
        objective = subtask["objective"]
        identity = subtask["identity"]
        signature = (
            identity["challenge"],
            identity["contract_version"],
            objective["quantity"],
            objective["unit"],
            objective["sense"],
            tasks.digest(objective),
        )
        if common is None:
            common = signature
        elif signature != common:
            raise tasks.TaskError("indices must share an objective definition")
        total_budget += identity["query_budget"]
        rows.append(
            {
                "index_value": value,
                "buyer_weight": row["buyer_weight"],
                "task": subtask,
            }
        )
    if total_weight != 1:
        raise tasks.TaskError("buyer-mix weights must sum to one")
    if total_budget != query_budget:
        raise tasks.TaskError("shared budget must equal registered index quotas")
    if (
        value_equivalence["quantity"],
        value_equivalence["unit"],
    ) != common[2:4]:
        raise tasks.TaskError("value tolerance must match objective and unit")
    body = {
        "schema": tasks.INDEXED_SCHEMA,
        "task_id": task_id,
        "identity": {
            "challenge": common[0],
            "contract_version": common[1],
            "index_axis": index_axis,
            "query_budget": query_budget,
            "allocation_rule": ALLOCATION_RULE,
            "objective": {
                "quantity": common[2],
                "unit": common[3],
                "sense": common[4],
                "aggregate": "buyer_weighted_mean",
            },
            "value_equivalence": dict(value_equivalence),
        },
        "indices": rows,
    }
    body = json.loads(json.dumps(body, allow_nan=False))
    return {**body, "task_digest": tasks.digest(body)}


def validate_indexed(registered):
    if (
        type(registered) is not dict
        or set(registered)
        != {"schema", "task_id", "identity", "indices", "task_digest"}
        or registered.get("schema") != tasks.INDEXED_SCHEMA
    ):
        raise tasks.TaskError("registered indexed task required")
    tasks._verify_task_digest(registered)
    identity = registered["identity"]
    if (
        type(identity) is not dict
        or set(identity)
        != {
            "challenge",
            "contract_version",
            "index_axis",
            "query_budget",
            "allocation_rule",
            "objective",
            "value_equivalence",
        }
        or identity["allocation_rule"] != ALLOCATION_RULE
    ):
        raise tasks.TaskError("invalid indexed identity")
    rebuilt = indexed_task(
        registered["task_id"],
        index_axis=identity["index_axis"],
        indices=registered["indices"],
        query_budget=identity["query_budget"],
        value_equivalence=identity["value_equivalence"],
    )
    if rebuilt != registered:
        raise tasks.TaskError("indexed task identity was altered")


def _equivalent_regret(delta, tolerance):
    positive = max(Decimal(0), delta)
    return 0.0 if positive <= tolerance else float(positive)


def run_indexed_optimizer(registered, predictor, *, model_id):
    """Commit all indices from predictions before reference data is supplied."""
    validate_indexed(registered)
    if type(model_id) is not str or not model_id:
        raise tasks.TaskError("model id required")
    commitments = []
    accounting = []
    for row in registered["indices"]:
        value = row["index_value"]
        run = tasks.run_optimizer(
            row["task"],
            lambda action, condition, value=value: predictor(value, action, condition),
            model_id=model_id,
        )
        commitments.append(run["commitment"])
        accounting.append(run["accounting"])
    total = sum(row["attempted_queries"] for row in accounting)
    budget = registered["identity"]["query_budget"]
    if total > budget:
        raise tasks.TaskError("indexed optimizer exceeded shared budget")
    execution = {
        "attempted_queries": total,
        "query_budget": budget,
        "invalid_queries": sum(row["invalid_queries"] for row in accounting),
        "model_failures": sum(row["model_failures"] for row in accounting),
        "per_index": accounting,
        "exhaustive_coverage": all(row["exhaustive_coverage"] for row in accounting),
        "stopped_for_budget": any(row["stopped_for_budget"] for row in accounting),
    }
    body = {
        "schema": tasks.INDEXED_COMMIT_SCHEMA,
        "task_digest": registered["task_digest"],
        "model_id": model_id,
        "subcommitments": commitments,
        "execution": execution,
    }
    return {
        "commitment": {**body, "commitment_digest": tasks.digest(body)},
        "accounting": execution,
    }


def judge_indexed(registered, commitment, references):
    """Judge every mandatory band, then aggregate only a feasible full map."""
    validate_indexed(registered)
    if (
        type(commitment) is not dict
        or set(commitment)
        != {
            "schema",
            "task_digest",
            "model_id",
            "subcommitments",
            "execution",
            "commitment_digest",
        }
        or commitment.get("schema") != tasks.INDEXED_COMMIT_SCHEMA
        or type(commitment["model_id"]) is not str
        or not commitment["model_id"]
    ):
        raise tasks.TaskError("indexed commitment required")
    body = {k: v for k, v in commitment.items() if k != "commitment_digest"}
    if commitment.get("task_digest") != registered["task_digest"] or commitment.get(
        "commitment_digest"
    ) != tasks.digest(body):
        raise tasks.TaskError("indexed commitment was altered")
    rows = registered["indices"]
    if (
        type(references) is not list
        or len(references) != len(rows)
        or type(commitment.get("subcommitments")) is not list
        or len(commitment["subcommitments"]) != len(rows)
    ):
        raise tasks.TaskError("complete indexed reference panel required")
    if any(type(item) is not dict for item in commitment["subcommitments"]):
        raise tasks.TaskError("invalid indexed subcommitment")
    child_accounting = [
        subcommitment.get("execution") for subcommitment in commitment["subcommitments"]
    ]
    accounting_fields = {
        "attempted_queries",
        "query_budget",
        "invalid_queries",
        "model_failures",
        "complete_panels",
        "exhaustive_coverage",
        "stopped_for_budget",
    }
    if any(
        type(item) is not dict or set(item) != accounting_fields
        for item in child_accounting
    ):
        raise tasks.TaskError("invalid indexed query accounting")
    for item in child_accounting:
        if any(
            type(item[field]) is not int or item[field] < 0
            for field in (
                "attempted_queries",
                "query_budget",
                "invalid_queries",
                "model_failures",
                "complete_panels",
            )
        ) or any(
            type(item[field]) is not bool
            for field in ("exhaustive_coverage", "stopped_for_budget")
        ):
            raise tasks.TaskError("invalid indexed query accounting")
    expected_execution = {
        "attempted_queries": sum(
            item["attempted_queries"] for item in child_accounting
        ),
        "query_budget": registered["identity"]["query_budget"],
        "invalid_queries": sum(item["invalid_queries"] for item in child_accounting),
        "model_failures": sum(item["model_failures"] for item in child_accounting),
        "per_index": child_accounting,
        "exhaustive_coverage": all(
            item["exhaustive_coverage"] for item in child_accounting
        ),
        "stopped_for_budget": any(
            item["stopped_for_budget"] for item in child_accounting
        ),
    }
    if (
        commitment.get("execution") != expected_execution
        or expected_execution["attempted_queries"]
        > registered["identity"]["query_budget"]
        or any(
            item["query_budget"] != row["task"]["identity"]["query_budget"]
            or item["attempted_queries"] > item["query_budget"]
            for item, row in zip(child_accounting, rows)
        )
    ):
        raise tasks.TaskError("indexed query accounting differs from quotas")
    tolerance = tasks._number(
        registered["identity"]["value_equivalence"]["tolerance"], "tolerance"
    )
    per_index = []
    selected_sum = Decimal(0)
    best_sum = Decimal(0)
    full_values = True
    for row, subcommitment, reference in zip(
        rows, commitment["subcommitments"], references
    ):
        if (
            type(reference) is not dict
            or set(reference) != {"index_value", "values"}
            or reference["index_value"] != row["index_value"]
            or type(reference["values"]) is not dict
        ):
            raise tasks.TaskError("reference index does not match registration")
        subtask = row["task"]
        outcome = tasks.judge(subtask, subcommitment, reference["values"])
        if subcommitment["model_id"] != commitment["model_id"]:
            raise tasks.TaskError("indexed model identities differ")
        assessed = tasks.assess(subtask, reference["values"], reference=True)
        picked = outcome["selected"]
        best = outcome["best"]
        selected_objective = (
            assessed[picked]["objective"] if picked is not None else None
        )
        best_objective = assessed[best]["objective"] if best is not None else None
        if (
            outcome["kind"] == "SELECTED_FEASIBLE"
            and outcome["reference_resolved"]
            and best is not None
        ):
            sense = subtask["objective"]["sense"]
            delta = tasks._number(
                selected_objective, "selected objective"
            ) - tasks._number(best_objective, "reference-best objective")
            if sense == "max":
                delta = -delta
            outcome["regret"] = _equivalent_regret(delta, tolerance)
            outcome["value_equivalent"] = outcome["regret"] == 0
            weight = tasks._number(row["buyer_weight"], "buyer weight")
            selected_sum += weight * tasks._number(
                selected_objective, "selected objective"
            )
            best_sum += weight * tasks._number(
                best_objective, "reference-best objective"
            )
        else:
            full_values = False
            outcome["value_equivalent"] = None
        per_index.append(
            {
                "index_value": row["index_value"],
                "buyer_weight": row["buyer_weight"],
                "outcome": outcome,
                "selected_objective": selected_objective,
                "reference_best_objective": best_objective,
            }
        )
    states = [item["outcome"]["reference_state"] for item in per_index]
    state = (
        "NONE_FEASIBLE"
        if "NONE_FEASIBLE" in states
        else (
            "FEASIBLE_EXISTS"
            if all(s == "FEASIBLE_EXISTS" for s in states)
            else "UNRESOLVED"
        )
    )
    resolved = all(item["outcome"]["reference_resolved"] for item in per_index)
    kinds = [item["outcome"]["kind"] for item in per_index]
    if "SELECTED_INFEASIBLE" in kinds:
        kind = "SELECTED_INFEASIBLE"
    elif "SELECTED_UNRESOLVED" in kinds:
        kind = "SELECTED_UNRESOLVED"
    elif "ABSTENTION_UNRESOLVED" in kinds:
        kind = "ABSTENTION_UNRESOLVED"
    elif not resolved:
        kind = "SELECTED_UNRESOLVED"
    elif "MISSED_OPPORTUNITY" in kinds:
        kind = "MISSED_OPPORTUNITY"
    elif state == "NONE_FEASIBLE":
        kind = "CORRECT_ABSTENTION"
    else:
        kind = "SELECTED_FEASIBLE"
    aggregate = None
    if full_values and kind == "SELECTED_FEASIBLE":
        sense = registered["identity"]["objective"]["sense"]
        delta = selected_sum - best_sum if sense == "min" else best_sum - selected_sum
        aggregate = {
            "selected_objective": float(selected_sum),
            "reference_best_objective": float(best_sum),
            "regret": _equivalent_regret(delta, tolerance),
            "unit": registered["identity"]["objective"]["unit"],
        }
    return {
        "kind": kind,
        "task_digest": registered["task_digest"],
        "reference_state": state,
        "reference_resolved": resolved,
        "per_index": per_index,
        "aggregate": aggregate,
        "regret": aggregate["regret"] if aggregate is not None else None,
        "unit": registered["identity"]["objective"]["unit"],
    }
