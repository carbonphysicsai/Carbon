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


def block(components, objective):
    """The definition block: ``components`` is a list of ``(id, kind, quantity,
    unit, scale)`` and ``objective`` ``(unit, direction, scale)``."""
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
    }


def validate_block(value):
    _require(
        type(value) is dict
        and set(value)
        == {"schema", "rule", "components", "objective", "components_not_applied"}
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
    "validate_block",
]
