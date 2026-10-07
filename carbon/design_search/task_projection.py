"""Allow-listed miner view of a registered design task (DEVELOPMENT only).

The registration and its digest stay producer-side. This object is deliberately
not an input to commitment verification. All nested fields are copied through
positive field lists so a future private registration field cannot leak by
default.
"""

from __future__ import annotations

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
    grammar = identity["action_grammar"]
    grammar_version = grammar.get("schema") if type(grammar) is dict else grammar
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
        "condition_count": len(registered_task["conditions"]),
        "objective": _public_quantity(registered_task["objective"]),
        "limits": [_public_limit(limit) for limit in registered_task["limits"]],
        "secondary": (
            None
            if registered_task["secondary"] is None
            else _public_quantity(registered_task["secondary"])
        ),
    }
