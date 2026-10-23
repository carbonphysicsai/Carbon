"""The shared Design half for the sealed graders: D = min(V, C).

Owner decision OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01 section 1: Design is
the lesser of the verified achieved-value credit V and the decision-critical
prediction credit C, and "a correct action ID alone cannot earn full Design
credit". The spec is ``docs/development/scorelab/four_challenge_design_fidelity_dev1.md``
(section 1 rule, sections 3, 4 and 6 per-Challenge components, section 7 scales).
F02 already grades this way through ``design_fidelity``; this module gives Motor,
Cooling and F08 the same rule through the same reducer, once.

One Challenge-neutral module. What differs per Challenge is plugin data, passed in
by the Challenge's own grader and written into its accuracy definition so the
signed pack binds it: the critical quantities with their units and scales, and
the objective that defines V. Nothing here chooses a physical value; the scales
are dev1 section 7's registered DEVELOPMENT normalisations.

C is the worst normalised signed-margin (or resonance) error over **every**
candidate cell of the batch, including the ones the model did not select
(dev1 sections 1-2: "Include unselected alternatives"); one badly predicted
near-limit candidate caps D. A cell the model failed to predict is a candidate
fault, never a smaller worst error. Analytic quantities (F08's mass) earn no
credit. Reference points carry no accepted interval in these banks, so errors
are absolute point errors and the reduction is a POINT_ESTIMATE_DIAGNOSTIC
(dev1 section 1): coverage limits are reported, never charged to a model.

Response (finite-difference) and learned-gap components need a registered pair
panel the sealed batches do not carry; they are not computed here and the
definition says so (``components_not_applied``).

This file is part of each grader's producer identity (listed in their ``FILES``).
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import math

from carbon.scoring import design_fidelity as fidelity

RULE = "D=min(V,C)"
SCHEMA = "carbon.scoring.critical-fidelity.v1"
KINDS = ("margin", "resonance")
NOT_APPLIED = ("response", "gap")
_OBJECTIVE_QUANTITY = "objective_value"


class CriticalFidelityRefused(ValueError):
    """The registered block or inputs cannot support the reduction."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise CriticalFidelityRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


#: OWNER-DESIGN-DECISION-FIDELITY-01 starting values: the main limit is shifted
#: by +-5% and the three decision measures are equally weighted.
SHIFT = 0.05


def block(components, objective, main_limits):
    """The definition block: ``components`` is a list of ``(id, kind, quantity,
    unit, scale)``, ``objective`` ``(unit, direction, scale)`` and
    ``main_limits`` a list of ``(component id, sigma)`` naming the main limit's
    margin components (sigma +1 when the margin is ``limit - value``, -1 when it
    is ``value - limit``), shifted together in the nearby-variant questions."""
    return {
        "schema": SCHEMA,
        "rule": RULE,
        "components": [
            {"id": i, "kind": k, "quantity": q, "unit": u, "scale": s}
            for i, k, q, u, s in components
        ],
        "objective": {
            "unit": objective[0],
            "direction": objective[1],
            "scale": objective[2],
        },
        "components_not_applied": list(NOT_APPLIED),
        "value": {
            "rule": "V=mean(V_pair,V_feas,V_var)",
            "shift": SHIFT,
            "resolution": 0.0,
            "main_limit": [{"component": c, "sigma": sg} for c, sg in main_limits],
        },
    }


def validate_block(value):
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "rule",
            "components",
            "objective",
            "components_not_applied",
            "value",
        }
        and value["schema"] == SCHEMA
        and value["rule"] == RULE
        and value["components_not_applied"] == list(NOT_APPLIED)
        and type(value["components"]) is list
        and bool(value["components"])
        and type(value["objective"]) is dict
        and set(value["objective"]) == {"unit", "direction", "scale"}
        and type(value["objective"]["unit"]) is str
        and value["objective"]["direction"] in ("MINIMIZE", "MAXIMIZE")
        and _number(value["objective"]["scale"])
        and value["objective"]["scale"] > 0,
        "critical_block",
    )
    seen = set()
    for component in value["components"]:
        _require(
            type(component) is dict
            and set(component) == {"id", "kind", "quantity", "unit", "scale"}
            and component["kind"] in KINDS
            and all(type(component[k]) is str and component[k] for k in ("id", "unit"))
            and type(component["quantity"]) is str
            and component["quantity"] != _OBJECTIVE_QUANTITY
            and _number(component["scale"])
            and component["scale"] > 0
            and component["id"] not in seen,
            "critical_component",
        )
        seen.add(component["id"])
    spec = value["value"]
    _require(
        type(spec) is dict
        and set(spec) == {"rule", "shift", "resolution", "main_limit"}
        and spec["rule"] == "V=mean(V_pair,V_feas,V_var)"
        and _number(spec["shift"])
        and 0 < spec["shift"] < 1
        and _number(spec["resolution"])
        and spec["resolution"] >= 0
        and type(spec["main_limit"]) is list
        and bool(spec["main_limit"])
        and all(
            type(m) is dict
            and set(m) == {"component", "sigma"}
            and m["sigma"] in (1, -1)
            and m["component"] in seen
            for m in spec["main_limit"]
        ),
        "critical_value_block",
    )
    return value


def _atom(value, unit):
    return {"status": "RESOLVED", "value": float(value), "unit": unit, "interval": None}


def _policy(spec, case_ids, action_ids, reference_cases):
    components, slots = [], []
    for component in spec["components"]:
        unit = component["unit"]
        components.append(
            {
                "id": component["id"],
                "kind": component["kind"],
                "quantity": component["quantity"],
                "unit": unit,
                "scale": {"value": component["scale"], "unit": unit},
                "cases": list(case_ids),
                "pairs": [],
            }
        )
        if component["kind"] != "margin":
            continue
        # dev1 section 2.3: the closest resolved nonnegative and negative margin
        # case, from the references alone (stable id tie break). A side with no
        # case is a coverage limitation, reported and never charged to a model.
        for side, keep in (
            ("nonnegative", lambda m: m >= 0),
            ("negative", lambda m: m < 0),
        ):
            pool = sorted(
                (abs(row[component["quantity"]]), cid)
                for cid, row in reference_cases.items()
                if keep(row[component["quantity"]])
            )
            if pool:
                slots.append(
                    {
                        "id": f"{component['id']}-{side}",
                        "component": component["id"],
                        "case_id": pool[0][1],
                        "side": side,
                        "max_distance": {"value": component["scale"], "unit": unit},
                        "structural_na_receipt": None,
                    }
                )
    quantities = {
        c["quantity"]: {"unit": c["unit"], "learned": True} for c in spec["components"]
    }
    quantities[_OBJECTIVE_QUANTITY] = {
        "unit": spec["objective"]["unit"],
        "learned": False,
    }
    return {
        "id": "critical-margin-dev1-v1",
        "case_ids": list(case_ids),
        "action_ids": list(action_ids),
        "quantities": quantities,
        "objective": {
            "quantity": _OBJECTIVE_QUANTITY,
            "unit": spec["objective"]["unit"],
            "direction": spec["objective"]["direction"],
            "scale": {
                "value": spec["objective"]["scale"],
                "unit": spec["objective"]["unit"],
            },
            "learned": False,
            # The objective is the Challenge's native verified value: no
            # equivalence width is invented.
            "equivalence": {"value": 0.0, "unit": spec["objective"]["unit"]},
        },
        "components": components,
        "coverage_slots": slots,
    }


def reduce(spec, *, case_ids, action_ids, reference, prediction):
    """Reduce one model with ``design_fidelity`` over the batch's every cell.

    ``reference``: ``{"cases": {cell: {quantity: float}}, "actions":
    {action: {"feasible": bool, "objective": float}}}`` (finite floats).
    ``prediction``: ``{"cases": {cell: {quantity: float}}`` (an unpredicted cell
    maps to ``{}`` or omits a quantity), ``"selected": action | None}``.
    Returns the reducer's result for that one model."""
    validate_block(spec)
    _require(
        type(reference) is dict
        and set(reference) == {"cases", "actions"}
        and set(reference["cases"]) == set(case_ids)
        and set(reference["actions"]) == set(action_ids)
        and all(
            _number(row.get(c["quantity"]))
            for row in reference["cases"].values()
            for c in spec["components"]
        ),
        "critical_reference",
    )
    policy = _policy(spec, case_ids, action_ids, reference["cases"])
    unit = {c["quantity"]: c["unit"] for c in spec["components"]}
    ref = {
        "cases": {
            cid: {q: _atom(row[q], unit[q]) for q in unit}
            for cid, row in reference["cases"].items()
        },
        "actions": {
            aid: {
                "feasibility": "FEASIBLE" if row["feasible"] else "INFEASIBLE",
                "objective": _atom(row["objective"], spec["objective"]["unit"]),
            }
            for aid, row in reference["actions"].items()
        },
    }
    model = {
        "artifact_digest": "model",
        "selected_action": prediction["selected"],
        "cases": {
            cid: {
                q: {"value": row[q], "unit": unit[q]}
                for q in unit
                if q in row and _number(row[q])
            }
            for cid, row in prediction["cases"].items()
        },
        "actions": {},
    }
    try:
        result = fidelity.reduce_design(policy, ref, [model])
    except fidelity.ReductionRefused as exc:
        raise CriticalFidelityRefused("critical_policy:" + str(exc)) from exc
    return result["models"][0]


def summary(model_result):
    """The compact record a grade carries: C, the limiting component and the
    per-component worst, plus the reference limits (never a model verdict)."""
    components = model_result["critical_components"]
    return {
        "rule": RULE,
        "C": model_result["C"],
        "components": {
            key: {
                "benefit": value["benefit"],
                "worst_effective_error": value["worst_effective_error"],
                "mean_effective_error": value["mean_effective_error"],
                "measured_rows": value["measured_rows"],
                "required_rows": value["required_rows"],
            }
            for key, value in components.items()
        },
        "candidate_issues": model_result["candidate_issues"],
        "reference_limitations": model_result["reference_limitations"],
        "full_credit_eligible": model_result["full_credit_eligible"],
        "reference_kind": "POINT_ESTIMATE_DIAGNOSTIC",
    }


def _worst_margins(spec, cells_of, cases):
    """Per action, per margin component: the worst (smallest) margin over the
    action's cells, in that component's scale units."""
    scale = {c["id"]: c["scale"] for c in spec["components"] if c["kind"] == "margin"}
    quantity = {
        c["id"]: c["quantity"] for c in spec["components"] if c["kind"] == "margin"
    }
    return {
        action: {
            cid: min(cases[cell][quantity[cid]] for cell in cells) / scale[cid]
            for cid in scale
        }
        for action, cells in cells_of.items()
    }


def value(spec, *, cells_of, reference, prediction, base_v, limits, exact_ok=None):
    """V = the equal-weight mean of V_pair, V_feas and V_var
    (OWNER-DESIGN-DECISION-FIDELITY-01), from the references already held.

    ``cells_of``: ``{action: [cell ids]}``. ``reference`` and ``prediction`` as
    in `reduce`, the prediction also carrying ``objective``: ``{action: float}``.
    ``base_v`` is the Challenge's native pick value on the base question.
    ``limits`` maps each main-limit component id to its registered limit value.
    ``exact_ok`` maps an action to False when an exactly known limit (F08's
    mass) already rules it out, for model and reference alike.

    Returns ``(V, record)``; V is None when the model left any needed
    prediction out (a candidate fault, never a smaller error)."""
    validate_block(spec)
    actions = list(cells_of)
    exact = {a: (exact_ok or {}).get(a, True) for a in actions}
    objective = spec["objective"]
    record = {"rule": spec["value"]["rule"], "V_pair": None, "V_feas": None}
    ref_obj = {a: reference["actions"][a]["objective"] for a in actions}
    pred_obj = prediction.get("objective") or {}
    pred_cases = prediction["cases"]
    needed = [c["quantity"] for c in spec["components"] if c["kind"] == "margin"]
    if (
        base_v is None
        or not all(_number(pred_obj.get(a)) for a in actions)
        or not all(
            _number(pred_cases.get(cell, {}).get(q))
            for cells in cells_of.values()
            for cell in cells
            for q in needed
        )
    ):
        return None, record
    ref_w = _worst_margins(spec, cells_of, reference["cases"])
    pred_w = _worst_margins(spec, cells_of, pred_cases)

    # V_pair: misordered pairs cost their true objective gap.
    resolution = spec["value"]["resolution"]
    total = wrong = 0.0
    for i, first in enumerate(actions):
        for second in actions[i + 1 :]:
            gap = abs(ref_obj[first] - ref_obj[second])
            if gap <= resolution:
                continue
            total += gap
            if (ref_obj[first] - ref_obj[second]) * (
                pred_obj[first] - pred_obj[second]
            ) <= 0:
                wrong += gap
    v_pair = 1.0 if total == 0 else 1.0 - wrong / total

    # V_feas: a wrong accept costs the true violation, a wrong reject the true
    # margin given up, both in the limit's own scale units.
    costs = []
    for a in actions:
        s_ref, s_pred = min(ref_w[a].values()), min(pred_w[a].values())
        if exact[a] and s_ref < 0 <= s_pred:
            costs.append(-s_ref)
        elif exact[a] and s_pred < 0 <= s_ref:
            costs.append(s_ref)
        else:
            costs.append(0.0)
    v_feas = 1.0 / (1.0 + sum(costs) / len(costs))

    # V_var: the pick question under the main limit shifted +-shift; the base
    # question is the Challenge's own.
    shift = spec["value"]["shift"]
    minimise = objective["direction"] == "MINIMIZE"

    def feasible(w, delta):
        for cid, value_ in w.items():
            for entry in spec["value"]["main_limit"]:
                if entry["component"] == cid:
                    scale = next(
                        c["scale"] for c in spec["components"] if c["id"] == cid
                    )
                    value_ = value_ + entry["sigma"] * delta * limits[cid] / scale
            if value_ < 0:
                return False
        return True

    questions = [base_v]
    for delta in (-shift, shift):
        truth = [a for a in actions if exact[a] and feasible(ref_w[a], delta)]
        if not truth:
            continue  # nothing is feasible: the variant measures nothing
        offered = [a for a in actions if exact[a] and feasible(pred_w[a], delta)]
        if not offered:
            questions.append(0.0)
            continue
        choose = min if minimise else max
        pick = choose(offered, key=lambda a: pred_obj[a])
        if pick not in truth:
            questions.append(0.0)
            continue
        best = choose(ref_obj[a] for a in truth)
        regret = abs(ref_obj[pick] - best)
        questions.append(1.0 / (1.0 + regret / objective["scale"]))
    v_var = sum(questions) / len(questions)
    record.update(
        V_pair=v_pair,
        V_feas=v_feas,
        V_var=v_var,
        variant_questions=len(questions) - 1,
    )
    return (v_pair + v_feas + v_var) / 3.0, record


def design(value_benefit, model_result):
    """``(D, summary)``: D = min(V, C). ``value_benefit`` is the Challenge's own
    native V (unchanged): None stays None, and a V of 0 stays 0 (an unsafe or
    missed pick earns no Design). A model with any unpredicted critical cell
    (a candidate fault) has no C and so no D."""
    record = summary(model_result)
    if value_benefit is None or value_benefit == 0:
        return value_benefit, record
    if model_result["candidate_issues"] or model_result["C"] is None:
        return None, record
    return min(value_benefit, model_result["C"]), record


__all__ = [
    "KINDS",
    "NOT_APPLIED",
    "RULE",
    "CriticalFidelityRefused",
    "block",
    "design",
    "reduce",
    "summary",
    "value",
    "validate_block",
]
