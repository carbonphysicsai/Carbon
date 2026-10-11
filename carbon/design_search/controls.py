"""Producer-side synthetic design controls; no Challenge truth authority.

Task controls alter reference quantities by signed hard-limit margin. The
legacy-output adapter is kept here so historical battery bytes stay frozen.
"""

from __future__ import annotations

import copy
import math
from decimal import Decimal

from carbon.design_search import tasks

CONTROL_SCHEMA = "carbon.design-search.control.v2"
CONTROL_SET_SCHEMA = "carbon.design-search.controls.v2"
KINDS = (
    "edge_optimist",
    "over_cautious",
    "localized_sign_error",
    "optimizer_or_lattice_aware",
)


def register_controls(controls):
    """Integrity-bind producer-supplied control definitions."""
    body = {"schema": CONTROL_SET_SCHEMA, "controls": copy.deepcopy(controls)}
    validate_controls({**body, "registration_digest": tasks.digest(body)}, task=None)
    return {**body, "registration_digest": tasks.digest(body)}


def validate_controls(registration, *, task):
    if (
        type(registration) is not dict
        or set(registration) != {"schema", "controls", "registration_digest"}
        or registration["schema"] != CONTROL_SET_SCHEMA
        or registration["registration_digest"]
        != tasks.digest(
            {k: v for k, v in registration.items() if k != "registration_digest"}
        )
        or type(registration["controls"]) is not list
        or not registration["controls"]
    ):
        raise tasks.TaskError("registered controls required")
    names = set()
    for spec in registration["controls"]:
        _validate_control(spec, task)
        if spec["name"] in names:
            raise tasks.TaskError("control names must be distinct")
        names.add(spec["name"])


def _finite_positive(value, where):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise tasks.TaskError(f"{where} must be finite and positive")
    return Decimal(str(value))


def _validate_region(region, task):
    if (
        type(region) is not dict
        or set(region) != {"action", "strata"}
        or type(region["action"]) is not dict
        or type(region["strata"]) is not list
        or not (region["action"] or region["strata"])
        or any(type(s) is not str or not s for s in region["strata"])
        or len(set(region["strata"])) != len(region["strata"])
    ):
        raise tasks.TaskError("localized control needs a predeclared region")
    for selector in region["action"].values():
        if type(selector) is not dict or not (
            set(selector) == {"min", "max"} or set(selector) == {"values"}
        ):
            raise tasks.TaskError("invalid region action selector")
        if "values" in selector:
            if (
                type(selector["values"]) is not list
                or not selector["values"]
                or any(type(x) is not str for x in selector["values"])
                or len(set(selector["values"])) != len(selector["values"])
            ):
                raise tasks.TaskError("invalid enum region selector")
        else:
            lo = tasks._number(selector["min"], "region min")
            hi = tasks._number(selector["max"], "region max")
            if lo > hi:
                raise tasks.TaskError("region bounds reversed")
    if task is None:
        return
    variables = {v["name"]: v for v in task["identity"]["action_grammar"]["variables"]}
    if not set(region["action"]) <= set(variables):
        raise tasks.TaskError("region uses unregistered action variable")
    if not set(region["strata"]) <= set(task["strata"]):
        raise tasks.TaskError("region uses unregistered stratum")
    for name, selector in region["action"].items():
        variable = variables[name]
        if variable["type"] == "enum":
            if set(selector) != {"values"} or not set(selector["values"]) <= set(
                variable["values"]
            ):
                raise tasks.TaskError("region enum does not match grammar")
        elif set(selector) != {"min", "max"} or not (
            tasks._number(variable["min"], "min")
            <= tasks._number(selector["min"], "region min")
            <= tasks._number(selector["max"], "region max")
            <= tasks._number(variable["max"], "max")
        ):
            raise tasks.TaskError("region bounds do not match grammar")


def _validate_control(spec, task):
    if type(spec) is not dict or spec.get("schema") != CONTROL_SCHEMA:
        raise tasks.TaskError("registered control schema required")
    kind = spec.get("kind")
    extras = (
        {"region"}
        if kind == "localized_sign_error"
        else {"scope"} if kind == "optimizer_or_lattice_aware" else set()
    )
    if (
        kind not in KINDS
        or set(spec)
        != {"schema", "name", "kind", "severity", "limit_quantities"} | extras
        or type(spec.get("name")) is not str
        or not spec["name"]
        or type(spec.get("limit_quantities")) is not list
        or not spec["limit_quantities"]
        or any(type(q) is not str or not q for q in spec["limit_quantities"])
        or len(set(spec["limit_quantities"])) != len(spec["limit_quantities"])
    ):
        raise tasks.TaskError("invalid behaviour-defined control")
    severity = spec["severity"]
    if type(severity) is not dict or set(severity) != set(spec["limit_quantities"]):
        raise tasks.TaskError("one severity per controlled quantity required")
    for quantity, entry in severity.items():
        if (
            type(entry) is not dict
            or set(entry) != {"value", "unit"}
            or type(entry["unit"]) is not str
            or not entry["unit"]
        ):
            raise tasks.TaskError("control severity needs a value and unit")
        _finite_positive(entry["value"], f"{quantity} severity")
    if kind == "localized_sign_error":
        _validate_region(spec["region"], task)
    if kind == "optimizer_or_lattice_aware" and spec["scope"] not in (
        "registered_search_path",
        "registered_lattice",
    ):
        raise tasks.TaskError("unregistered awareness scope")
    if task is not None:
        limits = [limit["quantity"] for limit in task["limits"]]
        if len(set(limits)) != len(limits):
            raise tasks.TaskError("control requires unique hard-limit quantities")
        if not set(spec["limit_quantities"]) <= set(limits):
            raise tasks.TaskError("control uses unregistered hard limit")
        units = {limit["quantity"]: limit["unit"] for limit in task["limits"]}
        if any(
            severity[quantity]["unit"] != units[quantity]
            for quantity in spec["limit_quantities"]
        ):
            raise tasks.TaskError("control severity unit does not match hard limit")


def _inside_region(region, action, condition):
    if region["strata"] and condition["stratum"] not in region["strata"]:
        return False
    for name, selector in region["action"].items():
        value = action[name]
        if "values" in selector:
            if value not in selector["values"]:
                return False
        elif not selector["min"] <= value <= selector["max"]:
            return False
    return True


def task_control_prediction(
    task, spec, action, condition, reference_values, *, accurate_actions=frozenset()
):
    """Return a synthetic query response from a reference row.

    The optimizer supplies canonical actions. `accurate_actions` is derived
    from the frozen optimizer's known-good path, not miner input.
    """
    _validate_control(spec, task)
    tasks._verify_task_digest(task)
    result = dict(reference_values)
    kind = spec["kind"]
    if kind == "localized_sign_error" and not _inside_region(
        spec["region"], action, condition
    ):
        return result
    if kind == "optimizer_or_lattice_aware":
        if (
            spec["scope"] == "registered_search_path"
            and tasks.digest(action) in accurate_actions
        ):
            return result
        if (
            spec["scope"] == "registered_lattice"
            and tasks.snap_action(task["identity"]["action_grammar"], action) == action
        ):
            return result
    limits = {limit["quantity"]: limit for limit in task["limits"]}
    for quantity in spec["limit_quantities"]:
        severity = _finite_positive(
            spec["severity"][quantity]["value"], f"{quantity} severity"
        )
        if quantity not in result:
            raise tasks.TaskError("reference row lacks controlled quantity")
        limit = limits[quantity]
        value = tasks._number(result[quantity], quantity)
        threshold = tasks._number(limit["value"], "limit")
        margin = value - threshold if limit["op"] == ">=" else threshold - value
        changed = None
        flip = (
            (kind == "edge_optimist" and -severity <= margin < 0)
            or (kind == "over_cautious" and 0 < margin <= severity)
            or (kind == "localized_sign_error" and 0 < abs(margin) <= severity)
        )
        if flip:
            changed = -margin
        elif kind == "optimizer_or_lattice_aware":
            changed = margin + severity
        if changed is not None:
            result[quantity] = float(
                threshold + changed if limit["op"] == ">=" else threshold - changed
            )
    return result


def apply_output_operations(outputs, operations):
    """Challenge-neutral scalar/trajectory operations on copied reference data."""
    out = copy.deepcopy(outputs)
    for rule in operations:
        when = rule.get("when")
        if when is not None:
            value = out[when["field"]]
            mode = when["kind"]
            if mode == "scalar_open_interval":
                active = when["lower"] < value < when["upper"]
            elif mode == "series_max_open_interval":
                active = when["lower"] < max(value) < when["upper"]
            elif mode == "scalar_abs_at_most":
                active = abs(value) <= when["maximum"]
            else:
                raise tasks.TaskError("unknown reference-output selector")
            if not active:
                continue
        field = rule["field"]
        mode = rule["kind"]
        if mode == "scalar_shift":
            out[field] += rule["delta"]
        elif mode == "scalar_negate":
            out[field] = -out[field]
        elif mode == "series_after_first_shift":
            values = out[field]
            out[field] = [values[0]] + [value + rule["delta"] for value in values[1:]]
        elif mode == "series_delay":
            values = list(out[field])
            steps = rule["steps"]
            if type(steps) is not int or not 1 <= steps < len(values):
                raise tasks.TaskError("invalid series delay")
            out[field] = [values[0]] * steps + values[:-steps]
        else:
            raise tasks.TaskError("unknown reference-output operation")
    return out


_BATTERY_OPERATIONS = {
    "oracle": (),
    "conservative": (
        {"kind": "scalar_shift", "field": "plating_margin_v", "delta": -0.010},
        {"kind": "series_after_first_shift", "field": "temperature_c", "delta": 2.0},
    ),
    "boundary_optimist": (
        {
            "kind": "scalar_shift",
            "field": "plating_margin_v",
            "delta": 0.012,
            "when": {
                "kind": "scalar_open_interval",
                "field": "plating_margin_v",
                "lower": -0.012,
                "upper": 0.003,
            },
        },
        {
            "kind": "series_after_first_shift",
            "field": "temperature_c",
            "delta": -3.5,
            "when": {
                "kind": "series_max_open_interval",
                "field": "temperature_c",
                "lower": 44.0,
                "upper": 48.5,
            },
        },
    ),
    "rank_preserving_delay": (
        {"kind": "series_delay", "field": "voltage_v", "steps": 1},
    ),
    "localized_sign_error": (
        {
            "kind": "scalar_negate",
            "field": "plating_margin_v",
            "when": {
                "kind": "scalar_abs_at_most",
                "field": "plating_margin_v",
                "maximum": 0.005,
            },
        },
    ),
}


def battery_control_predictions(kind, references):
    """Reproduce the historical battery controls without changing panel.py."""
    if kind not in _BATTERY_OPERATIONS:
        raise ValueError("unknown control")
    return {
        case_id: apply_output_operations(record["outputs"], _BATTERY_OPERATIONS[kind])
        for case_id, record in references.items()
        if record.get("status") == "OK"
    }
