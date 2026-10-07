"""Allow-listed miner view of a registered design task (DEVELOPMENT only).

The registration and its digest stay producer-side. This object is deliberately
not an input to commitment verification. All nested fields are copied through
positive field lists so a future private registration field cannot leak by
default.
"""

from __future__ import annotations

import json
import math

from carbon.design_search import tasks

SCHEMA = "carbon.design-task.miner-projection.v1"
QUANTITY_FIELDS = ("quantity", "unit", "sense", "aggregate")
LIMIT_FIELDS = ("quantity", "unit", "op", "value")


def _pick(row, fields):
    return {key: row[key] for key in fields if key in row}


def _public_quantity(row):
    if any(type(row.get(key)) is not str for key in QUANTITY_FIELDS):
        raise tasks.TaskError("public quantity fields must be strings")
    return _pick(row, QUANTITY_FIELDS)


def _public_limit(row):
    if any(type(row.get(key)) is not str for key in LIMIT_FIELDS[:-1]):
        raise tasks.TaskError("public limit fields must be strings")
    value = row.get("value")
    if type(value) not in (int, float) or not math.isfinite(value):
        raise tasks.TaskError("public limit value must be finite numeric")
    return _pick(row, LIMIT_FIELDS)


def _public_grammar(grammar):
    if type(grammar) is str:
        return grammar, None
    if (
        type(grammar) is not dict
        or set(grammar) != {"schema", "version", "variables", "rules"}
        or type(grammar["schema"]) is not str
        or type(grammar["version"]) is not str
        or type(grammar["variables"]) is not list
        or type(grammar["rules"]) is not list
    ):
        raise tasks.TaskError("public action grammar invalid")
    variables = []
    for var in grammar["variables"]:
        if type(var) is not dict or type(var.get("name")) is not str:
            raise tasks.TaskError("public action variable invalid")
        if var.get("type") in ("number", "integer"):
            if set(var) != {"name", "type", "min", "max", "step"} or any(
                type(var[key]) not in (int, float) or not math.isfinite(var[key])
                for key in ("min", "max", "step")
            ):
                raise tasks.TaskError("public numeric variable invalid")
            variables.append(_pick(var, ("name", "type", "min", "max", "step")))
        elif var.get("type") == "enum":
            if (
                set(var) != {"name", "type", "values"}
                or type(var["values"]) is not list
                or any(type(value) is not str for value in var["values"])
            ):
                raise tasks.TaskError("public enum variable invalid")
            variables.append(
                {"name": var["name"], "type": "enum", "values": sorted(var["values"])}
            )
        else:
            raise tasks.TaskError("public action type invalid")
    rules = []
    for rule in grammar["rules"]:
        if (
            type(rule) is not dict
            or set(rule) != {"kind", "coefficients", "op", "value"}
            or rule["kind"] != "linear"
            or rule["op"] not in ("<=", ">=")
            or type(rule["coefficients"]) is not dict
            or any(
                type(name) is not str
                or type(value) not in (int, float)
                or not math.isfinite(value)
                for name, value in rule["coefficients"].items()
            )
            or type(rule["value"]) not in (int, float)
            or not math.isfinite(rule["value"])
        ):
            raise tasks.TaskError("public validity rule invalid")
        rules.append(
            {
                "kind": "linear",
                "coefficients": dict(sorted(rule["coefficients"].items())),
                "op": rule["op"],
                "value": rule["value"],
            }
        )
    rules.sort(key=lambda rule: json.dumps(rule, sort_keys=True))
    return grammar["version"], {
        "schema": grammar["schema"],
        "variables": sorted(variables, key=lambda var: var["name"]),
        "rules": rules,
    }


def miner_projection(registered_task):
    """Return only public decision semantics, without a reversible task ID.

    Condition/candidate IDs and bank contents stay private. A Challenge can
    separately publish its approved public condition and action-space contract;
    this projection never accepts caller-supplied disclosure fields.
    """
    if registered_task.get("schema") not in (
        tasks.SCHEMA,
        getattr(tasks, "RUNNABLE_SCHEMA", ""),
    ):
        raise tasks.TaskError("registered design task required")
    if tasks.digest(
        {k: v for k, v in registered_task.items() if k != "task_digest"}
    ) != registered_task.get("task_digest"):
        raise tasks.TaskError("registered task was altered")
    identity = registered_task["identity"]
    grammar_version, public_action_space = _public_grammar(identity["action_grammar"])
    if any(
        type(value) is not str
        for value in (
            identity["challenge"],
            identity["contract_version"],
            grammar_version,
        )
    ):
        raise tasks.TaskError("public identity versions must be strings")
    return {
        "schema": SCHEMA,
        "challenge": identity["challenge"],
        "contract_version": identity["contract_version"],
        "action_grammar_version": grammar_version,
        "action_space": public_action_space,
        "condition_count": len(registered_task["conditions"]),
        "objective": _public_quantity(registered_task["objective"]),
        "limits": [_public_limit(limit) for limit in registered_task["limits"]],
        "secondary": (
            None
            if registered_task["secondary"] is None
            else _public_quantity(registered_task["secondary"])
        ),
    }
