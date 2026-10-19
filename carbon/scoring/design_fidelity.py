"""Pure DEVELOPMENT D=min(verified value, critical prediction fidelity).

Adapters own physical reductions, frozen cohorts/pairs, reference acceptance,
native gates and the shared ScoreEngine. This file reads/writes nothing, runs
no model and selects no cohort from candidate errors. Input acceptance receipts
are source assertions, not scientific authority conferred by this reducer.
The adapter pins every settled reference-feasible action pair from accepted
truth before inspecting candidate errors, then supplies that common pair list.
This does not claim pre-truth custody for exposed data.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from statistics import fmean


class ReductionRefused(ValueError):
    """Malformed policy or identities, not a model's physical failure."""


def require(value, reason):
    if not value:
        raise ReductionRefused(reason)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def typed_identity(value):
    """Hash rejected nonfinite reference values as types, never JSON NaN."""
    if type(value) is float and not math.isfinite(value):
        return {
            "rejected_numeric": (
                "NaN" if math.isnan(value) else "+Inf" if value > 0 else "-Inf"
            )
        }
    if type(value) is dict:
        return {key: typed_identity(item) for key, item in value.items()}
    if type(value) is list:
        return [typed_identity(item) for item in value]
    return value


def shape(value, names, reason):
    require(type(value) is dict and set(value) == set(names), reason)


def scale(value, unit, *, zero=False):
    shape(value, ("value", "unit"), "explicit_unit_scale_required")
    require(value["unit"] == unit, "scale_unit_mismatch")
    require(
        finite(value["value"])
        and (value["value"] >= 0 if zero else value["value"] > 0),
        "invalid_scale",
    )
    return float(value["value"])


def benefit(loss):
    return 1 / (1 + loss)


def validate_policy(policy):
    shape(
        policy,
        (
            "id",
            "case_ids",
            "action_ids",
            "quantities",
            "objective",
            "components",
            "coverage_slots",
        ),
        "policy_shape",
    )
    require(type(policy["id"]) is str and bool(policy["id"]), "policy_identity")
    for name in ("case_ids", "action_ids"):
        values = policy[name]
        require(
            type(values) is list
            and bool(values)
            and all(type(v) is str and v for v in values)
            and len(values) == len(set(values)),
            "common_identity_mask:" + name,
        )
    require(
        type(policy["quantities"]) is dict and bool(policy["quantities"]),
        "quantities_required",
    )
    for quantity in policy["quantities"].values():
        shape(quantity, ("unit", "learned"), "quantity_shape")
        require(
            type(quantity["unit"]) is str
            and bool(quantity["unit"])
            and type(quantity["learned"]) is bool,
            "quantity_unit_or_credit",
        )
    objective = policy["objective"]
    shape(
        objective,
        ("quantity", "unit", "direction", "scale", "learned", "equivalence"),
        "objective_shape",
    )
    require(
        objective["quantity"] in policy["quantities"]
        and policy["quantities"][objective["quantity"]]
        == {"unit": objective["unit"], "learned": objective["learned"]},
        "objective_quantity_binding",
    )
    require(objective["direction"] in ("MINIMIZE", "MAXIMIZE"), "objective_direction")
    scale(objective["scale"], objective["unit"])
    scale(objective["equivalence"], objective["unit"], zero=True)
    ids = set()
    require(
        type(policy["components"]) is list and bool(policy["components"]),
        "components_required",
    )
    for component in policy["components"]:
        shape(
            component,
            ("id", "kind", "quantity", "unit", "scale", "cases", "pairs"),
            "component_shape",
        )
        require(
            type(component["id"]) is str
            and component["id"]
            and component["id"] not in ids,
            "component_identity",
        )
        ids.add(component["id"])
        require(
            component["kind"] in ("margin", "response", "gap", "resonance"),
            "component_kind",
        )
        require(
            component["quantity"] in policy["quantities"]
            and policy["quantities"][component["quantity"]]["unit"]
            == component["unit"],
            "component_quantity_unit",
        )
        scale(component["scale"], component["unit"])
        require(
            type(component["cases"]) is list and type(component["pairs"]) is list,
            "fixed_component_panel",
        )
        if component["kind"] in ("margin", "resonance"):
            require(
                not component["pairs"]
                and len(component["cases"]) == len(set(component["cases"]))
                and set(component["cases"]) <= set(policy["case_ids"]),
                "level_case_mask",
            )
        else:
            require(not component["cases"], "pair_component_cases")
            endpoints = (
                policy["action_ids"]
                if component["kind"] == "gap"
                else policy["case_ids"]
            )
            require(
                all(
                    type(pair) is list
                    and len(pair) == 2
                    and pair[0] != pair[1]
                    and set(pair) <= set(endpoints)
                    for pair in component["pairs"]
                ),
                "pair_endpoints",
            )
            require(
                len({tuple(pair) for pair in component["pairs"]})
                == len(component["pairs"]),
                "duplicate_pair",
            )
            if component["kind"] == "gap":
                require(
                    component["quantity"] == objective["quantity"],
                    "gap_uses_registered_objective",
                )
    coverage_ids = set()
    require(type(policy["coverage_slots"]) is list, "coverage_slots_required")
    components = {c["id"]: c for c in policy["components"]}
    for slot in policy["coverage_slots"]:
        shape(
            slot,
            (
                "id",
                "component",
                "case_id",
                "side",
                "max_distance",
                "structural_na_receipt",
            ),
            "coverage_slot_shape",
        )
        require(
            type(slot["id"]) is str and slot["id"] and slot["id"] not in coverage_ids,
            "coverage_slot_identity",
        )
        coverage_ids.add(slot["id"])
        require(
            slot["component"] in components
            and components[slot["component"]]["kind"] == "margin",
            "coverage_margin_component",
        )
        component = components[slot["component"]]
        require(
            slot["case_id"] is None or slot["case_id"] in component["cases"],
            "coverage_case_binding",
        )
        require(slot["side"] in ("nonnegative", "negative"), "coverage_side")
        scale(slot["max_distance"], component["unit"])
        receipt = slot["structural_na_receipt"]
        require(
            receipt is None
            or (type(receipt) is str and bool(receipt) and slot["case_id"] is None),
            "structural_applicability_receipt",
        )
    digest(policy)


def reference_atom(value, unit):
    """Return typed source point/accepted interval, never a candidate verdict."""
    if type(value) is not dict or set(value) != {"status", "value", "unit", "interval"}:
        return {"point": None, "interval": None, "reason": "REFERENCE_MISSING_OR_SHAPE"}
    if value["unit"] != unit:
        return {"point": None, "interval": None, "reason": "REFERENCE_UNIT_MISMATCH"}
    if value["status"] != "RESOLVED":
        reason = (
            "REFERENCE_INFRA"
            if value["status"] == "FAILED_INFRA"
            else "REFERENCE_UNRESOLVED"
        )
        return {"point": None, "interval": None, "reason": reason}
    if not finite(value["value"]):
        return {"point": None, "interval": None, "reason": "REFERENCE_NONFINITE"}
    interval = value["interval"]
    if interval is None:
        return {
            "point": float(value["value"]),
            "interval": None,
            "reason": "NO_ACCEPTED_REFERENCE_INTERVAL",
        }
    if (
        type(interval) is not dict
        or set(interval) != {"lower", "upper", "unit", "receipt"}
        or interval["unit"] != unit
        or not finite(interval["lower"])
        or not finite(interval["upper"])
        or not interval["lower"] <= value["value"] <= interval["upper"]
        or type(interval["receipt"]) is not str
        or not interval["receipt"]
    ):
        return {
            "point": float(value["value"]),
            "interval": None,
            "reason": "REFERENCE_INTERVAL_INVALID_OR_UNACCEPTED",
        }
    return {
        "point": float(value["value"]),
        "interval": [float(interval["lower"]), float(interval["upper"])],
        "reason": None,
    }


def prediction_atom(value, unit):
    if type(value) is not dict or set(value) != {"value", "unit"}:
        return None, "CANDIDATE_MISSING_PREDICTION"
    if value["unit"] != unit:
        return None, "CANDIDATE_UNIT_MISMATCH"
    if not finite(value["value"]):
        return None, "CANDIDATE_NONFINITE"
    return float(value["value"]), None


def difference(second, first):
    if first["point"] is None or second["point"] is None:
        return {
            "point": None,
            "interval": None,
            "reason": "REFERENCE_DIFFERENCE_UNRESOLVED",
        }
    point = second["point"] - first["point"]
    if not finite(point):
        return {
            "point": None,
            "interval": None,
            "reason": "REFERENCE_DIFFERENCE_OVERFLOW",
        }
    interval = None
    if first["interval"] is not None and second["interval"] is not None:
        lo = second["interval"][0] - first["interval"][1]
        hi = second["interval"][1] - first["interval"][0]
        if finite(lo) and finite(hi):
            interval = [lo, hi]
    return {
        "point": point,
        "interval": interval,
        "reason": None if interval is not None else "NO_ACCEPTED_REFERENCE_INTERVAL",
    }


def error_row(label, predicted, reference, unit, normalizer, candidate_reason=None):
    row = {
        "id": label,
        "unit": unit,
        "scale": normalizer,
        "prediction": predicted,
        "reference_point": reference["point"],
        "reference_interval": reference["interval"],
        "reference_limitation": reference["reason"],
        "candidate_issue": candidate_reason,
        "signed_error": None,
        "absolute_point_error": None,
        "effective_error": None,
        "normalized_error": None,
        "normalized_error_bounds": None,
    }
    if predicted is None or reference["point"] is None:
        return row
    signed = predicted - reference["point"]
    if not finite(signed):
        row["candidate_issue"] = "CANDIDATE_ERROR_OVERFLOW"
        return row
    absolute = abs(signed)
    if reference["interval"] is None:
        effective = upper = absolute
    else:
        lo, hi = reference["interval"]
        effective = max(lo - predicted, 0.0, predicted - hi)
        upper = max(abs(lo - predicted), abs(hi - predicted))
    ratio, upper_ratio = effective / normalizer, upper / normalizer
    if not finite(ratio) or not finite(upper_ratio):
        row["candidate_issue"] = "CANDIDATE_NORMALIZED_ERROR_OVERFLOW"
        return row
    row.update(
        signed_error=signed,
        absolute_point_error=absolute,
        effective_error=effective,
        normalized_error=ratio,
        normalized_error_bounds=[ratio, upper_ratio],
    )
    return row


def summarize_component(component, rows, status):
    available = [r for r in rows if r["normalized_error"] is not None]
    loss = max((r["normalized_error"] for r in available), default=None)
    upper = max((r["normalized_error_bounds"][1] for r in available), default=None)
    return {
        "kind": component["kind"],
        "quantity": component["quantity"],
        "unit": component["unit"],
        "status": status,
        "rows": rows,
        "required_rows": len(rows),
        "measured_rows": len(available),
        "mean_absolute_point_error": (
            fmean(r["absolute_point_error"] for r in available) if available else None
        ),
        "worst_absolute_point_error": max(
            (r["absolute_point_error"] for r in available), default=None
        ),
        "mean_effective_error": (
            fmean(r["effective_error"] for r in available) if available else None
        ),
        "worst_effective_error": max(
            (r["effective_error"] for r in available), default=None
        ),
        "normalized_worst_loss": loss,
        "benefit": benefit(loss) if loss is not None else None,
        "benefit_bounds": [benefit(upper), benefit(loss)] if loss is not None else None,
    }


def value_result(policy, action_reference, feasible, unresolved, selected):
    objective = policy["objective"]
    result = {
        "unit": objective["unit"],
        "selected_action": selected,
        "status": None,
        "regret": None,
        "regret_bounds": None,
        "V": None,
        "V_bounds": None,
        "selected_objective": None,
        "best_objective": None,
        "reference_best_scope": "DECLARED_FINITE_ACTION_SET",
        "reference_feasible_set_is_settled": not unresolved,
        "reference_best_objective_interval": None,
        "possible_best_actions": None,
        "winner_order_is_settled": False,
        "value_equivalence_status": "NOT_MEASURED",
        "dependence_limitation": "Self-comparison is exactly zero; bounds over other actions are enclosing and do not assume probabilistic independence.",
    }
    if not feasible:
        result["status"] = (
            "REFERENCE_UNRESOLVED" if unresolved else "NONE_FEASIBLE_VALUE_NOT_MEASURED"
        )
        return result
    if selected is None:
        result.update(
            status="ABSTENTION_WITH_FEASIBLE_OPPORTUNITY",
            regret=None,
            V=0.0,
            V_bounds=[0.0, 0.0],
        )
        return result
    if selected in unresolved:
        result["status"] = "SELECTED_REFERENCE_UNRESOLVED"
        return result
    if selected not in feasible:
        result["status"] = "SELECTED_PROVEN_INFEASIBLE"
        return result
    candidates = [action_reference[a] for a in feasible]
    require(
        all(atom["point"] is not None for atom in candidates),
        "internal_feasible_reference",
    )
    minimizing = objective["direction"] == "MINIMIZE"
    best = (min if minimizing else max)(atom["point"] for atom in candidates)
    actual = action_reference[selected]
    raw = max(0.0, actual["point"] - best if minimizing else best - actual["point"])
    if not finite(raw):
        result["status"] = "REFERENCE_OBJECTIVE_RANGE_OVERFLOW"
        return result
    delta = objective["equivalence"]["value"]
    regret = 0.0 if raw <= delta else raw
    result.update(
        status="POINT_ESTIMATE_ONLY" if unresolved else "VERIFIED_FEASIBLE",
        regret=regret,
        selected_objective=actual["point"],
        best_objective=best,
        V=benefit(regret / objective["scale"]["value"]),
    )
    if not unresolved and all(atom["interval"] is not None for atom in candidates):
        choose = min if minimizing else max
        best_lo, best_hi = (
            choose(atom["interval"][i] for atom in candidates) for i in (0, 1)
        )
        possible = (
            [key for key in feasible if action_reference[key]["interval"][0] <= best_hi]
            if minimizing
            else [
                key
                for key in feasible
                if action_reference[key]["interval"][1] >= best_lo
            ]
        )
        result.update(
            reference_best_objective_interval=[best_lo, best_hi],
            possible_best_actions=possible,
            winner_order_is_settled=len(possible) == 1,
        )
        sel_lo, sel_hi = actual["interval"]
        # r = max(0, selected - every OTHER action) for minimization.
        # The selected action is itself in the bank; its difference with itself
        # is exactly zero, not [sel_lo-sel_hi, sel_hi-sel_lo].
        others = [
            action_reference[key]["interval"] for key in feasible if key != selected
        ]
        lo = max(
            [0.0] + [sel_lo - hi if minimizing else low - sel_hi for low, hi in others]
        )
        hi = max(
            [0.0]
            + [sel_hi - low if minimizing else upper - sel_lo for low, upper in others]
        )
        bounds = [0.0 if x <= delta else x for x in (lo, hi)]
        result["regret_bounds"] = bounds
        result["value_equivalence_status"] = (
            "VERIFIED_EQUIVALENT"
            if bounds[1] == 0
            else "VERIFIED_NOT_EQUIVALENT" if bounds[0] > 0 else "UNRESOLVED"
        )
        result["V_bounds"] = [
            benefit(bounds[1] / objective["scale"]["value"]),
            benefit(bounds[0] / objective["scale"]["value"]),
        ]
    return result


def reduce_design(policy, reference, models):
    """Pure finite-bank reduction. No gate/Physics/final TOP or policy adoption.

    `full_credit_eligible` describes common panel coverage/resolution, not a
    promise the model earns 1. `earns_full_credit` additionally checks its D.
    A complete panel can register a low model D; missing truth never does so.
    """
    validate_policy(policy)
    require(
        type(reference) is dict and set(reference) == {"cases", "actions"},
        "reference_container",
    )
    require(
        type(reference["cases"]) is dict and type(reference["actions"]) is dict,
        "reference_masks",
    )
    require(type(models) is list and bool(models), "model_records_required")
    objective = policy["objective"]
    unit = objective["unit"]
    limits = []
    for missing in sorted(set(policy["case_ids"]) - set(reference["cases"])):
        limits.append("REFERENCE_CASE_MISSING:" + missing)
    for extra in sorted(set(reference["cases"]) - set(policy["case_ids"])):
        limits.append("REFERENCE_CASE_OUTSIDE_COMMON_MASK:" + extra)
    action_reference, feasible, unresolved = {}, [], []
    for key in policy["action_ids"]:
        row = reference["actions"].get(key)
        if (
            type(row) is not dict
            or set(row) != {"feasibility", "objective"}
            or row["feasibility"]
            not in ("FEASIBLE", "INFEASIBLE", "UNRESOLVED", "FAILED_INFRA")
        ):
            unresolved.append(key)
            limits.append("REFERENCE_ACTION_MISSING_OR_INVALID:" + key)
            continue
        if row["feasibility"] in ("UNRESOLVED", "FAILED_INFRA"):
            unresolved.append(key)
            limits.append("REFERENCE_ACTION_" + row["feasibility"] + ":" + key)
        elif row["feasibility"] == "FEASIBLE":
            atom = reference_atom(row["objective"], unit)
            action_reference[key] = atom
            if atom["point"] is None:
                unresolved.append(key)
            else:
                feasible.append(key)
            if atom["reason"]:
                limits.append(atom["reason"] + ":objective:" + key)
    feasible.sort()
    prepared = {}
    for component in policy["components"]:
        learned = policy["quantities"][component["quantity"]]["learned"]
        if not learned:
            prepared[component["id"]] = ("STRUCTURAL_NA_ANALYTIC_NO_CREDIT", [])
            continue
        kind, quantity, target_unit = (
            component["kind"],
            component["quantity"],
            component["unit"],
        )
        refs = []
        if kind == "gap":
            expected_pairs = set(itertools.combinations(feasible, 2))
            require(
                {tuple(sorted(pair)) for pair in component["pairs"]} == expected_pairs
                and len(component["pairs"]) == len(expected_pairs),
                "gap_requires_every_settled_feasible_pair",
            )
            if unresolved:
                status = "REFERENCE_UNRESOLVED_COMPETITIVE_ACTION"
                limits.append(status + ":" + component["id"])
            elif len(feasible) < 2:
                prepared[component["id"]] = (
                    "STRUCTURAL_NA_FEWER_THAN_TWO_SETTLED_FEASIBLE",
                    [],
                )
                continue
            else:
                status = "APPLICABLE"
            for first, second in component["pairs"]:
                refs.append(
                    (
                        first + "->" + second,
                        [first, second],
                        difference(action_reference[second], action_reference[first]),
                    )
                )
        else:
            status = "APPLICABLE"
            for key in component["cases"]:
                row = reference["cases"].get(key)
                atom = reference_atom(
                    row.get(quantity) if type(row) is dict else None, target_unit
                )
                refs.append((key, [key], atom))
            for first, second in component["pairs"]:
                atoms = []
                for key in (first, second):
                    row = reference["cases"].get(key)
                    atoms.append(
                        reference_atom(
                            row.get(quantity) if type(row) is dict else None,
                            target_unit,
                        )
                    )
                refs.append(
                    (
                        first + "->" + second,
                        [first, second],
                        difference(atoms[1], atoms[0]),
                    )
                )
            if not refs:
                limits.append("EMPTY_REQUIRED_COMPONENT:" + component["id"])
        for label, _, atom in refs:
            if atom["reason"]:
                limits.append(atom["reason"] + ":" + component["id"] + ":" + label)
        prepared[component["id"]] = (status, refs)
    coverage = []
    components_by_id = {c["id"]: c for c in policy["components"]}
    for slot in policy["coverage_slots"]:
        component = components_by_id[slot["component"]]
        result = {
            **slot,
            "max_distance": dict(slot["max_distance"]),
            "status": None,
            "reference_margin": None,
            "distance": None,
        }
        if not policy["quantities"][component["quantity"]]["learned"]:
            result["status"] = "STRUCTURAL_NA_ANALYTIC_NO_CREDIT"
        elif slot["structural_na_receipt"] is not None:
            result["status"] = "STRUCTURAL_NA_SOURCE_APPLICABILITY"
        else:
            key = slot["case_id"]
            row = reference["cases"].get(key)
            atom = reference_atom(
                row.get(component["quantity"]) if type(row) is dict else None,
                component["unit"],
            )
            if key is None or atom["point"] is None:
                result["status"] = "REQUIRED_SIDE_MISSING_OR_UNRESOLVED"
            else:
                point = atom["point"]
                result.update(reference_margin=point, distance=abs(point))
                correct = (point >= 0) == (slot["side"] == "nonnegative")
                interval_side_resolved = atom["interval"] is None or (
                    atom["interval"][0] >= 0
                    if slot["side"] == "nonnegative"
                    else atom["interval"][1] < 0
                )
                interval_proximity_resolved = (
                    atom["interval"] is None
                    or max(abs(endpoint) for endpoint in atom["interval"])
                    <= slot["max_distance"]["value"]
                )
                result["status"] = (
                    "COVERED"
                    if correct
                    and interval_side_resolved
                    and abs(point) <= slot["max_distance"]["value"]
                    else "WRONG_SIDE" if not correct else "OUTSIDE_DECLARED_PROXIMITY"
                )
                if correct and abs(point) <= slot["max_distance"]["value"]:
                    if not interval_side_resolved:
                        result["status"] = "INTERVAL_SIDE_UNRESOLVED"
                    elif not interval_proximity_resolved:
                        result["status"] = "INTERVAL_PROXIMITY_UNRESOLVED"
            if result["status"] != "COVERED":
                limits.append(result["status"] + ":" + slot["id"])
        coverage.append(result)
    for component in policy["components"]:
        if (
            component["kind"] == "margin"
            and policy["quantities"][component["quantity"]]["learned"]
        ):
            sides = {
                s["side"]
                for s in policy["coverage_slots"]
                if s["component"] == component["id"]
            }
            for missing in sorted({"nonnegative", "negative"} - sides):
                limits.append(
                    "MARGIN_SIDE_COVERAGE_UNDECLARED:" + component["id"] + ":" + missing
                )
    if not feasible:
        limits.append(
            "REFERENCE_FEASIBLE_SET_UNRESOLVED"
            if unresolved
            else "NONE_FEASIBLE_VALUE_NOT_MEASURED"
        )
    limits = sorted(set(limits))
    panel_eligible = not limits
    identities, results = set(), []
    for model in models:
        shape(
            model,
            ("artifact_digest", "selected_action", "cases", "actions"),
            "model_shape",
        )
        identity = model["artifact_digest"]
        require(
            type(identity) is str and identity and identity not in identities,
            "model_identity",
        )
        identities.add(identity)
        require(
            model["selected_action"] is None
            or model["selected_action"] in policy["action_ids"],
            "selected_action_identity",
        )
        require(
            type(model["cases"]) is dict and type(model["actions"]) is dict,
            "candidate_container",
        )
        candidate_issues = []
        if set(model["cases"]) != set(policy["case_ids"]):
            candidate_issues.append("CANDIDATE_COMMON_CASE_MASK_MISMATCH")
        scored = {}
        for component in policy["components"]:
            status, refs = prepared[component["id"]]
            rows = []
            for label, endpoints, atom in refs:
                forecasts, issue = [], None
                for key in endpoints:
                    source = (
                        model["actions"]
                        if component["kind"] == "gap"
                        else model["cases"]
                    )
                    point = source.get(key)
                    value = (
                        point.get("objective")
                        if component["kind"] == "gap" and type(point) is dict
                        else (
                            point.get(component["quantity"])
                            if type(point) is dict
                            else None
                        )
                    )
                    forecast, reason = prediction_atom(value, component["unit"])
                    forecasts.append(forecast)
                    if reason:
                        issue = reason
                forecast = (
                    None
                    if any(v is None for v in forecasts)
                    else (
                        forecasts[0]
                        if len(forecasts) == 1
                        else forecasts[1] - forecasts[0]
                    )
                )
                if forecast is not None and not finite(forecast):
                    forecast, issue = None, "CANDIDATE_RESPONSE_OVERFLOW"
                error = error_row(
                    label,
                    forecast,
                    atom,
                    component["unit"],
                    component["scale"]["value"],
                    issue,
                )
                rows.append(error)
                if error["candidate_issue"]:
                    candidate_issues.append(
                        error["candidate_issue"] + ":" + component["id"] + ":" + label
                    )
            scored[component["id"]] = summarize_component(component, rows, status)
        applicable = {
            key: value
            for key, value in scored.items()
            if not value["status"].startswith("STRUCTURAL_NA")
        }
        available = {
            key: value["benefit"]
            for key, value in applicable.items()
            if value["benefit"] is not None
        }
        c = min(available.values()) if available else None
        if not applicable:
            local_limits = limits + ["NO_LEARNED_CRITICAL_COMPONENTS"]
        else:
            local_limits = limits + [
                "UNMEASURED_COMPONENT:" + key
                for key, value in applicable.items()
                if value["benefit"] is None
                and not any(row["candidate_issue"] for row in value["rows"])
            ]
        value = value_result(
            policy, action_reference, feasible, unresolved, model["selected_action"]
        )
        if value["value_equivalence_status"] == "UNRESOLVED":
            local_limits.append("VALUE_EQUIVALENCE_UNRESOLVED")
        selected_reference = reference["actions"].get(model["selected_action"])
        unsafe = (
            type(selected_reference) is dict
            and selected_reference.get("feasibility") == "INFEASIBLE"
        )
        candidate_issues = sorted(set(candidate_issues))
        point_d = (
            min(value["V"], c)
            if value["V"] is not None
            and c is not None
            and not candidate_issues
            and not unsafe
            else None
        )
        c_bounds = (
            [
                min(
                    v["benefit_bounds"][i]
                    for v in applicable.values()
                    if v["benefit_bounds"] is not None
                )
                for i in (0, 1)
            ]
            if available
            else None
        )
        d_bounds = (
            [min(value["V_bounds"][i], c_bounds[i]) for i in (0, 1)]
            if value["V_bounds"] is not None
            and c_bounds is not None
            and point_d is not None
            else None
        )
        registered = (
            point_d
            if panel_eligible
            and not local_limits
            and not candidate_issues
            and not unsafe
            else None
        )
        if candidate_issues:
            status = "CANDIDATE_INVALID"
        elif unsafe:
            status = "CANDIDATE_UNSAFE_SELECTION"
        elif local_limits:
            status = "PARTIAL_DIAGNOSTIC"
        else:
            status = "REGISTERED_DEVELOPMENT_MEASUREMENT"
        limiting = []
        if point_d is not None:
            if value["V"] == point_d:
                limiting.append("VALUE")
            if c == point_d:
                limiting.extend(
                    "CRITICAL:" + key for key, b in available.items() if b == c
                )
        slot_errors = {}
        for slot in policy["coverage_slots"]:
            component = scored[slot["component"]]
            error = next(
                (r for r in component["rows"] if r["id"] == slot["case_id"]), None
            )
            slot_errors[slot["id"]] = {
                "side": slot["side"],
                "case_id": slot["case_id"],
                "error": error,
            }
        earns_full = (
            registered == 1.0
            and value["regret_bounds"] is not None
            and value["regret_bounds"][1] == 0
        )
        results.append(
            {
                "artifact_digest": identity,
                "prediction_digest": digest(typed_identity(model)),
                "status": status,
                "candidate_status": (
                    "INVALID"
                    if candidate_issues
                    else (
                        "PROVEN_UNSAFE_SELECTION"
                        if unsafe
                        else (
                            "ABSTAIN"
                            if model["selected_action"] is None
                            else "VALID_PREDICTIONS"
                        )
                    )
                ),
                "reference_status": (
                    "PARTIAL_OR_UNRESOLVED"
                    if local_limits
                    else "COMPLETE_ACCEPTED_PANEL"
                ),
                "candidate_issues": candidate_issues,
                "candidate_selection_outcome": value["status"],
                "reference_limitations": sorted(set(local_limits)),
                "full_credit_eligible": panel_eligible and not local_limits,
                "earns_full_credit": earns_full,
                "registered_D": registered,
                "point_estimate_D": point_d,
                "D_bounds": d_bounds,
                "V": value,
                "C": c,
                "C_bounds": c_bounds,
                "critical_components": scored,
                "coverage_slot_errors": slot_errors,
                "limiting_components": limiting,
                "no_scientific_candidate_penalty_from_reference_gap": True,
            }
        )
    return {
        "policy_digest": digest(policy),
        "common_mask_digest": digest(
            {"case_ids": policy["case_ids"], "action_ids": policy["action_ids"]}
        ),
        "reference_coverage_digest": digest(typed_identity(reference)),
        "reference_coverage_digest_basis": "CANONICAL_TYPED_REFERENCE_NOT_RAW_BYTES",
        "full_credit_panel_eligible": panel_eligible,
        "reference_limitations": limits,
        "coverage": coverage,
        "settled_feasible_actions": feasible,
        "unresolved_potentially_competitive_actions": unresolved,
        "models": results,
        "official_score": False,
        "score_adopted": False,
    }
