"""Prospective public reply authority; no nominal protocol or task-store change."""

from __future__ import annotations

import json

RULE = "carbon.autoresearch.research-reply.v2"
LEGACY_FIELDS = frozenset(
    {
        "protocol",
        "operation",
        "reply",
        "terminal_task",
        "public_result",
        "requires_reconciliation",
    }
)
FIELDS = LEGACY_FIELDS | {"schema", "current_task"}
_TASK_FIELDS = {
    "task_id",
    "challenge_key",
    "state",
    "revision",
    "created_at_micros",
    "updated_at_micros",
    "immutable_bindings",
    "progress",
    "terminal_receipt",
}
_STATES = {
    "QUEUED",
    "RUNNING",
    "CANCEL_REQUESTED",
    "SUCCEEDED",
    "FAILED_INFRA",
    "CANCELLED",
}
_BINDINGS = ("task_id", "challenge_key", "created_at_micros", "immutable_bindings")


def frozen_rule(manifest):
    plan = manifest.get("provider") if type(manifest) is dict else None
    value = plan.get("research_reply") if type(plan) is dict else None
    if value is not None and value != RULE:
        raise ValueError("unknown research reply rule: provider.research_reply")
    return value


def campaign_rule(ledger):
    if not callable(getattr(ledger, "db", None)):
        return None
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    return None if row is None else frozen_rule(json.loads(row[0]))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _task(value):
    if (
        type(value) is not dict
        or set(value) != _TASK_FIELDS
        or type(value["state"]) is not str
        or value["state"] not in _STATES
        or type(value["revision"]) is not int
        or not 0 <= value["revision"] < 2**64
    ):
        raise ValueError("invalid public task observation")
    return value


def current_task(value):
    """Select only an already-public, same-task, non-regressing observation.

    This describes the response's observation, not a live query or settlement.
    Legacy poll-sequence replay may intentionally return a historical view.
    """
    reply = value["reply"]
    if type(reply) is not dict:
        raise ValueError("invalid public reply")
    result = reply.get("result")
    receipt = result.get("task") if type(result) is dict else None
    observed = value["terminal_task"]
    if receipt is None:
        if observed is not None:
            raise ValueError("unbound task observation")
        return None
    receipt = _task(receipt)
    selected, source = receipt, "reply.result.task"
    if observed is not None:
        observed = _task(observed)
        if (
            any(_canonical(observed[k]) != _canonical(receipt[k]) for k in _BINDINGS)
            or observed["revision"] < receipt["revision"]
            or (
                observed["revision"] == receipt["revision"]
                and _canonical(observed) != _canonical(receipt)
            )
        ):
            raise ValueError("inconsistent task observation")
        selected, source = observed, "terminal_task"
    return {
        "state": selected["state"],
        "revision": selected["revision"],
        "source": source,
        "reply_task_revision": receipt["revision"],
        "reply_task_role": "RETAINED_PROTOCOL_OBSERVATION",
    }


def project(value, rule):
    """Wrap only newly frozen campaigns; old payloads/receipts stay untouched."""
    if rule is None or "protocol" not in value:
        return value
    if rule != RULE:
        raise ValueError("unknown research reply rule: provider.research_reply")
    # Compact authority precedes bulk data, including with sorted JSON keys.
    return {"current_task": current_task(value), "schema": RULE, **value}


def validate(value, rule):
    expected = LEGACY_FIELDS if rule is None else FIELDS
    if rule not in (None, RULE) or set(value) != expected:
        raise ValueError("invalid selected research reply schema")
    if rule == RULE and (
        value["schema"] != RULE
        or _canonical(value["current_task"]) != _canonical(current_task(value))
    ):
        raise ValueError("invalid research task authority")
