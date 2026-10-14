"""Positive argument projections. No raw-input digest, path or text fallback."""

from __future__ import annotations

import json
import math

from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS

from .protected_material import protected

POLICY = "carbon.graphite.argument-events.v1"
REDACTED = "REDACTED"
UNKNOWN_TOOL = "UNKNOWN_TOOL"
MAX_BYTES = 16384
FIELDS = frozenset(
    {
        "kind",
        "action",
        "seconds",
        "count",
        "offset",
        "limit",
        "used_feedback",
        "hypothesis",
        "expected_effect",
        "strategy_json",
        "arguments_json",
        "source",
        "files",
        "name",
        "query",
        "card_id",
        "task_id",
        "path",
        "submission_json",
        "summary",
        "findings",
        "next_steps",
        "evidence_json",
        "reason",
    }
)
ENUMS = {
    "kind": frozenset({"practice", "workspace", "hypothesis", "decision", "notebook"}),
    "action": frozenset((*DEVELOPMENT_WORKSPACE_ACTIONS, "run_julia")),
}
NUMBERS = {
    "seconds": (1, 2**31 - 1),
    "count": (1, 4096),
    "offset": (0, 2**31 - 1),
    "limit": (1, 4096),
}
PUBLIC_MATERIAL = frozenset(
    {"objective", "capabilities", "training_data", "practice_data", "reference_method"}
)


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _decode(value):
    if type(value) is str:
        if len(value.encode("utf-8")) > MAX_BYTES:
            raise ValueError("argument size")
        value = json.loads(value, object_pairs_hook=_object)
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError("argument shape")
    if len(value) > 128:
        raise ValueError("argument fields")
    return value


def _forecast(value):
    """Optional logging-only structured forecast; plain text stays redacted."""
    try:
        value = _decode(value)
    except (ValueError, UnicodeError, RecursionError):
        return REDACTED
    if (
        type(value.get("metric")) is not str
        or type(value.get("direction")) is not str
        or set(value)
        not in ({"metric", "direction", "delta"}, {"metric", "direction", "target"})
        or value.get("metric")
        not in ("score", "latency_seconds", "memory_bytes", "error")
        or value.get("direction") not in ("increase", "decrease", "unchanged")
    ):
        return REDACTED
    number = "delta" if "delta" in value else "target"
    if (
        type(value[number]) not in (int, float)
        or abs(value[number]) > 10**12
        or not math.isfinite(value[number])
    ):
        return REDACTED
    return {
        "metric": value["metric"],
        "direction": value["direction"],
        number: value[number],
    }


def snapshot(raw, *, action=None, nested=False):
    if raw is None or (type(raw) is str and raw.strip() in ("", "null")):
        return {"schema": POLICY, "shape": "empty", "fields": {}, "unknown_fields": 0}
    try:
        arguments = _decode(raw)
        denied = protected(arguments)
    except (ValueError, UnicodeError, RecursionError):
        return {
            "schema": POLICY,
            "shape": "malformed",
            "fields": {},
            "unknown_fields": None,
        }
    fields = {}
    action = arguments.get("action", action)
    action = action if type(action) is str else None
    for name in sorted(FIELDS.intersection(arguments)):
        value = arguments[name]
        projected = REDACTED
        if not denied:
            if (
                name in ENUMS
                and type(value) is str
                and value in ENUMS[name]
                or (
                    name in NUMBERS
                    and type(value) is int
                    and NUMBERS[name][0] <= value <= NUMBERS[name][1]
                )
                or name == "used_feedback"
                and type(value) is bool
                or (
                    name == "name"
                    and action == "public_material"
                    and type(value) is str
                    and value in PUBLIC_MATERIAL
                )
            ):
                projected = value
            elif name == "arguments_json" and not nested:
                projected = snapshot(value, action=action, nested=True)
            elif name == "expected_effect":
                projected = _forecast(value)
        fields[name] = projected
    return {
        "schema": POLICY,
        "shape": "object",
        "fields": fields,
        "unknown_fields": len(arguments.keys() - FIELDS),
    }


def tool_name(name, offered):
    return name if type(name) is str and name in offered else UNKNOWN_TOOL


def status(value):
    allowed = {
        "OK",
        "NOT_FOUND",
        "UNAVAILABLE",
        "READY",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "FAILED_INFRA",
        "COMPLETED",
        "REJECTED_BEFORE_DISPATCH",
        "LEVEL4_STAGED",
        "PROPOSED",
        "REFUSED_INVALID_REQUEST",
        "completed",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    }
    return value if type(value) is str and value in allowed else REDACTED
