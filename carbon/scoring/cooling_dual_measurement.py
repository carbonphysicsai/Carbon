"""Cooling's dual A/D measurement from one retained model's bank predictions.

DEVELOPMENT only. This is the counted-dual Cooling measurement
(OPTIMIZER_COUNTED_DUAL_PACKETS_20261018, ``cooling``, sha256 b6a1ce3e...)
computed from one model's predictions on the exposed 48-cell development bank,
using Cooling's own exam (``carbon/cold_plate/exam.py``) and customer-decision
code. Every scale and budget comes from the registered accuracy definition
document; nothing here chooses a value. The scales are that script's
PROSPECTIVE_EXPERIMENT_NOT_ADOPTED values: a development candidate, not an
adopted score.

A is the minimum of nine reciprocal benefits ``1/(1+e/A_scale)``: three
dimensionless errors (peak, profile, pressure) over three cohorts (all 48,
worst geometry, boundary-stress conditions). D is ``1/(1+regret_W/D_scale_W)``
for a predicted-feasible pick that the references verify feasible, else 0.
The native gate is every row SCORABLE under Cooling's exam gates, with its
paired repeat checked against two fresh repeat queries (three runs agree).
"""

from __future__ import annotations

import math
from statistics import fmean

from carbon.cold_plate import customer_decision as cd
from carbon.cold_plate import exam

DEFINITION_SCHEMA = "carbon.scoring.cooling-dual-accuracy.v1"
METHOD = "cooling-counted-dual-from-predictions.v1"
COHORT_COUNTS = {"decision_representative": 32, "decision_boundary_stress": 16}
_REDUCTIONS = ("all48", "worst_geometry", "boundary")
GATES = (
    "native_cold_plate",
    "complete48_common_mask",
    "selected_design_verified_feasible",
)


class CoolingMeasurementRefused(ValueError):
    """The bank, definition or references cannot support the measurement."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise CoolingMeasurementRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_definition(definition):
    """The registered A/D definition document, checked for every field used."""
    _require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("components") == list(exam.COMPONENTS)
        and definition.get("reductions") == list(_REDUCTIONS)
        and definition.get("A_reducer") == "minimum"
        and all(
            _number(definition.get(k)) and definition[k] > 0
            for k in ("A_scale", "D_scale_W")
        )
        and type(definition.get("verification_condition_budget")) is int
        and definition["verification_condition_budget"] >= 1
        and definition.get("cohort_counts") == COHORT_COUNTS
        and definition.get("target_slices")
        == {"peak_c": [0, 1], "profile_c": [1, 31], "pressure_drop_pa": [31, 32]},
        "cooling_definition",
    )
    return definition


def _outputs(values, slices):
    """One flat 32-value row as Cooling's native output document."""
    peak, profile, dp = (slices[k] for k in ("peak_c", "profile_c", "pressure_drop_pa"))
    return {
        "peak_c": float(values[peak[0]]),
        "profile_c": [float(v) for v in values[profile[0] : profile[1]]],
        "pressure_drop_pa": float(values[dp[0]]),
    }


def _benefit(error, scale):
    return 1.0 / (1.0 + error / scale)


def measure(*, bank, outputs, repeats, definition, contract, train):
    """A, D, native gates and the decision outcome for one model.

    ``bank`` rows are ``{case_id, cohort, inputs, record, design_id,
    condition_id}`` in the scored query's order; ``outputs`` and each of the two
    ``repeats`` are that many 32-value rows. ``contract`` is the pack's
    registered decision contract; ``train`` the Challenge TRAIN as reference
    records.
    """
    validate_definition(definition)
    n = len(bank)
    _require(
        type(outputs) is list
        and len(outputs) == n
        and type(repeats) in (list, tuple)
        and len(repeats) == 2
        and all(type(r) is list and len(r) == n for r in repeats),
        "cooling_prediction_roster",
    )
    counts = {c: 0 for c in COHORT_COUNTS}
    for row in bank:
        _require(row.get("cohort") in counts, "cooling_bank_cohort")
        counts[row["cohort"]] += 1
    _require(counts == COHORT_COUNTS, "cooling_bank_cohorts")
    designs = sorted({row["design_id"] for row in bank})
    conditions = sorted({row["condition_id"] for row in bank})
    keys = [(row["design_id"], row["condition_id"]) for row in bank]
    _require(
        len(set(keys)) == n == len(designs) * len(conditions),
        "cooling_complete_grid",
    )
    index = {key: i for i, key in enumerate(keys)}
    boundary = {
        row["condition_id"]
        for row in bank
        if row["cohort"] == "decision_boundary_stress"
    }
    references = [
        {
            "case_id": row["case_id"],
            "status": row["record"].get("status"),
            "inputs": row["inputs"],
            "outputs": row["record"]["outputs"],
        }
        for row in bank
    ]
    _require(
        all(r["status"] == "OK" for r in references), "cooling_reference_unresolved"
    )
    try:
        exam.calibrate(references)
    except ValueError as exc:
        raise CoolingMeasurementRefused("cooling_reference_gate") from exc
    scales = exam.scales_from_train(train)
    _require(
        all(
            _number(scales[k]) and scales[k] > 0
            for k in ("s_peak", "s_profile", "s_log_dp")
        ),
        "cooling_train_normalization",
    )
    slices = definition["target_slices"]
    first = [_outputs(v, slices) for v in outputs]
    twins = [[_outputs(v, slices) for v in repeat] for repeat in repeats]

    # Native validity: every row SCORABLE against both fresh repeats, and the
    # two repeats agree with each other (three runs agree).
    gate_failed = []
    for i, ref in enumerate(references):
        states = [
            exam.score_case(first[i], ref, scales, twin=twins[0][i])["state"],
            exam.score_case(first[i], ref, scales, twin=twins[1][i])["state"],
        ]
        repeat_pair = exam.gates(twins[0][i], ref["inputs"], twin=twins[1][i])
        if any(s != exam.SCORABLE for s in states) or exam.FAIL in repeat_pair.values():
            gate_failed.append(bank[i]["case_id"])
    native_pass = not gate_failed

    # A: finite errors stay measurable after a physical gate failure.
    components, errors = {}, {}
    try:
        if any(
            exam.gates(first[i], references[i]["inputs"])["schema_finite"] != exam.PASS
            or first[i]["pressure_drop_pa"] <= 0
            for i in range(n)
        ):
            raise ValueError("invalid native shape or logarithmic pressure")
        errors = {
            keys[i]: exam.case_components(first[i], references[i], scales)
            for i in range(n)
        }
    except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError):
        errors = {}
    if errors and all(
        math.isfinite(value) and value >= 0
        for error in errors.values()
        for value in error.values()
    ):
        for component in exam.COMPONENTS:
            components[component + "_all48"] = fmean(
                error[component] for error in errors.values()
            )
            components[component + "_worst_geometry"] = max(
                fmean(errors[(d, c)][component] for c in conditions) for d in designs
            )
            components[component + "_boundary"] = fmean(
                errors[(d, c)][component] for d in designs for c in boundary
            )
    a = (
        min(_benefit(e, definition["A_scale"]) for e in components.values())
        if components
        else None
    )

    # D: the predicted-feasible pick (worst-case hydraulic power, then design
    # variables), verified against the references at every condition.
    def objectives(rows_out):
        quantities = {}
        for key, i in index.items():
            try:
                quantities[key] = cd.quantities(
                    contract, bank[i]["inputs"], rows_out[i]
                )
            except (ValueError, TypeError, KeyError, OverflowError):
                quantities[key] = None
        return {
            d: max(quantities[(d, c)]["hydraulic_w"] for c in conditions)
            for d in designs
            if all(
                quantities[(d, c)] is not None and quantities[(d, c)]["feasible"]
                for c in conditions
            )
        }

    design_values = {d: bank[index[(d, conditions[0])]]["inputs"] for d in designs}
    predicted = objectives(first)
    picked = (
        min(
            predicted,
            key=lambda d: (
                predicted[d],
                *(design_values[d][k] for k in cd.DESIGN_VARIABLES),
            ),
        )
        if predicted
        else None
    )
    reference_objectives = objectives([r["outputs"] for r in references])
    _require(bool(reference_objectives), "cooling_no_feasible_reference")
    _require(
        len(conditions) <= definition["verification_condition_budget"],
        "cooling_verification_budget",
    )
    best = min(reference_objectives.values())
    verified = picked is not None and picked in reference_objectives
    regret = max(0.0, reference_objectives[picked] - best) if verified else None
    d_benefit = _benefit(regret, definition["D_scale_W"]) if verified else 0.0
    return {
        "gates": {
            "native_cold_plate": native_pass,
            "complete48_common_mask": True,
            "selected_design_verified_feasible": verified,
        },
        "gate_failed_cases": gate_failed,
        "components": components,
        "A": a,
        "D": d_benefit,
        "pick": picked,
        "regret_w": regret,
        "decision_outcome": "VERIFIED_FEASIBLE" if verified else "MISSED_OPPORTUNITY",
    }
