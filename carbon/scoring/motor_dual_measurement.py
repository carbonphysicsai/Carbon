"""Motor's dual A/D measurement from one retained model's bank predictions.

DEVELOPMENT only. This is the committed applied Motor definition
(MOTOR_APPLIED_SCORE_DEFINITION_20261018, G1_BALANCED_BASELINE) computed from
one model's predictions on the exposed development bank, instead of from saved
workflow summaries. The math is the frozen analysis's (``_old_features`` in
OPTIMIZER_MOTOR_DUAL_TRANSFER_ANALYSIS_20261018 and the decision workflow of
OPTIMIZER_MOTOR_WORKFLOW_AUDIT_20261018), using Motor's own exam, score
candidate and customer-decision code. Every scale and count comes from the
registered accuracy definition document; nothing here chooses a value.

A is the minimum of eight unit benefits over three cohorts (practice 30,
pilot 8 + 4, old V2 48). D is the verified-value benefit of the top predicted
feasible design after the registered verification budget. The native gates
are Motor's exam gates (``carbon/motor/exam.py``) on every row, with the
paired repeat checked against two fresh repeat queries under Motor's own
registered 32 float32 ulp rule; coverage is the fixed cohort counts.
"""

from __future__ import annotations

import math
import statistics
from statistics import fmean

from carbon.motor import customer_decision as decision
from carbon.motor import exam
from carbon.motor import score_candidates as candidates

DEFINITION_SCHEMA = "carbon.scoring.motor-dual-accuracy.v1"
METHOD = "motor-applied-g1-dual-from-predictions.v1"
_PILOT = ("pilot_ordinary", "pilot_difficult")
_DECISION = ("decision_representative", "decision_boundary_stress")
_LOSSES = (
    "practice30_mean_f0",
    "pilot_ordinary8_mean_f0",
    "pilot_difficult4_mean_f0",
    "old_v2_48_mean_f0",
    "old_v2_worst_geometry_mean_f0",
    "old_v2_representative32_mean_f0",
    "old_v2_boundary16_mean_f0",
    "old_v2_median_dimensionless_signed_margin_error",
)


class MotorMeasurementRefused(ValueError):
    """The bank, definition or predictions cannot support the measurement."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise MotorMeasurementRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_definition(definition):
    """The registered A/D definition document, checked for every field used."""
    _require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("losses") == list(_LOSSES)
        and definition.get("A_reducer") == "minimum"
        and all(
            _number(definition.get(k)) and definition[k] > 0
            for k in ("f0_scale", "signed_margin_scale", "D_scale")
        )
        and type(definition.get("signed_margin_cell")) is dict
        and all(
            _number(definition["signed_margin_cell"].get(k))
            and definition["signed_margin_cell"][k] > 0
            for k in ("mean_torque_nm", "ripple_fraction")
        )
        and type(definition.get("verification_budget")) is int
        and definition["verification_budget"] >= 1
        and definition.get("cohort_counts")
        == {
            "practice": 30,
            "pilot_ordinary": 8,
            "pilot_difficult": 4,
            "decision_representative": 32,
            "decision_boundary_stress": 16,
        },
        "motor_definition",
    )
    return definition


def _curve(values):
    return {"torque_nm": [float(v) for v in values]}


def _benefit(loss, scale):
    _require(_number(loss) and loss >= 0, "motor_derived_nonfinite")
    return 1.0 / (1.0 + loss / scale)


def measure(*, bank, outputs, repeats, definition, limits, objective, train):
    """A, D, native gates and the decision outcome for one model.

    ``bank`` rows are ``{case_id, cohort, inputs, record}`` in the scored
    query's order; ``outputs`` and each of the two ``repeats`` are that many
    60-angle torque curves. ``limits`` and ``objective`` are the pack's
    registered important-limit and design-objective documents; ``train`` is
    the Challenge TRAIN as reference records.
    """
    validate_definition(definition)
    n = len(bank)
    _require(
        type(outputs) is list
        and len(outputs) == n
        and type(repeats) in (list, tuple)
        and len(repeats) == 2
        and all(type(r) is list and len(r) == n for r in repeats),
        "motor_prediction_roster",
    )
    counts = {c: 0 for c in definition["cohort_counts"]}
    for row in bank:
        _require(row.get("cohort") in counts, "motor_bank_cohort")
        counts[row["cohort"]] += 1
    _require(counts == definition["cohort_counts"], "motor_bank_cohorts")
    constraints = limits.get("constraints") if type(limits) is dict else None
    contract = (objective or {}).get("decision_contract")
    _require(
        type(constraints) is dict
        and type(contract) is dict
        and contract.get("constraints") == constraints
        and objective.get("condition_ids") is not None
        and objective.get("design_ids") is not None,
        "motor_limit_or_objective",
    )
    exam_scales = exam.scales_from_train(train)
    component_scales = candidates.scales(train)
    predictions = [_curve(v) for v in outputs]
    twins = [[_curve(v) for v in repeat] for repeat in repeats]
    references = [{**row["record"], "inputs": row["inputs"]} for row in bank]

    # Native validity on every row: Motor's gates against both fresh repeats,
    # and the two repeats against each other (three runs agree).
    gate_failed = []
    for i, prediction in enumerate(predictions):
        verdicts = [
            exam.gates(prediction, twins[0][i]),
            exam.gates(prediction, twins[1][i]),
            exam.gates(twins[0][i], twins[1][i]),
        ]
        if any(exam.FAIL in v.values() for v in verdicts):
            gate_failed.append(bank[i]["case_id"])

    scored = {
        i: exam.score_case(predictions[i], references[i], exam_scales, twin=twins[0][i])
        for i, row in enumerate(bank)
        if not row["cohort"].startswith("decision_")
    }
    practice_rows = [scored[i] for i, r in enumerate(bank) if r["cohort"] == "practice"]
    practice = exam.aggregate(practice_rows)
    pilot = {
        cohort: [scored[i] for i, r in enumerate(bank) if r["cohort"] == cohort]
        for cohort in _PILOT
    }
    decision_index = [
        i for i, r in enumerate(bank) if r["cohort"].startswith("decision_")
    ]
    grid_rows = [
        exam.score_case(predictions[i], references[i], exam_scales, twin=twins[0][i])
        for i in decision_index
    ]
    grid = exam.aggregate(grid_rows)
    coverage_ok = (
        practice["n_scored"] == practice["n_cases"] == 30
        and grid["n_scored"] == 48
        and all(
            sum(r["state"] == exam.SCORABLE for r in pilot[c])
            == definition["cohort_counts"][c]
            for c in _PILOT
        )
    )
    native_ok = (
        not gate_failed
        and practice["eligible"] is True
        and practice["n_gate_failed"] == 0
        and grid["eligible"] is True
        and all(r["state"] == exam.SCORABLE for c in _PILOT for r in pilot[c])
    )
    gates = {"native_motor_valid": native_ok, "complete_fixed_coverage": coverage_ok}

    # A: eight unit benefits, minimum (A1 robust fidelity).
    a = None
    losses = None
    if coverage_ok and all(r["state"] == exam.SCORABLE for r in grid_rows):
        f0 = {}
        design_of, condition_of = {}, {}
        for i in decision_index:
            parts = candidates.components(
                predictions[i], references[i], component_scales
            )
            key = bank[i]["case_id"]
            f0[key] = (parts["mean"] + parts["shape"]) / 2
            design_of[key] = bank[i]["design_id"]
            condition_of[key] = bank[i]["cohort"]
        per_design = [
            fmean(f0[k] for k in f0 if design_of[k] == design)
            for design in objective["design_ids"]
        ]
        losses = {
            "practice30_mean_f0": practice["score"],
            "pilot_ordinary8_mean_f0": fmean(
                r["error"] for r in pilot["pilot_ordinary"]
            ),
            "pilot_difficult4_mean_f0": fmean(
                r["error"] for r in pilot["pilot_difficult"]
            ),
            "old_v2_48_mean_f0": fmean(f0.values()),
            "old_v2_worst_geometry_mean_f0": max(per_design),
            "old_v2_representative32_mean_f0": fmean(
                v for k, v in f0.items() if condition_of[k] == "decision_representative"
            ),
            "old_v2_boundary16_mean_f0": fmean(
                v
                for k, v in f0.items()
                if condition_of[k] == "decision_boundary_stress"
            ),
        }
    # D: quantities on every decision row (also the signed-margin A loss).
    try:
        reference_quantities = {
            bank[i]["case_id"]: decision.quantities(contract, references[i]["outputs"])
            for i in decision_index
        }
    except decision.DecisionError as exc:
        raise MotorMeasurementRefused("motor_reference_quantities") from exc
    try:
        quantities = {
            bank[i]["case_id"]: decision.quantities(contract, predictions[i])
            for i in decision_index
        }
    except decision.DecisionError:
        # The model's own curve failed Motor's validity gates.
        quantities = None
    if losses is not None and quantities is not None:
        cell = definition["signed_margin_cell"]
        losses["old_v2_median_dimensionless_signed_margin_error"] = statistics.median(
            max(
                abs(
                    quantities[k]["mean_torque_margin_nm"]
                    - reference_quantities[k]["mean_torque_margin_nm"]
                )
                / cell["mean_torque_nm"],
                abs(
                    quantities[k]["ripple_fraction_margin"]
                    - reference_quantities[k]["ripple_fraction_margin"]
                )
                / cell["ripple_fraction"],
            )
            for k in quantities
        )
        benefits = {
            name: _benefit(
                loss,
                (
                    definition["signed_margin_scale"]
                    if name.endswith("margin_error")
                    else definition["f0_scale"]
                ),
            )
            for name, loss in losses.items()
        }
        _require(set(benefits) == set(_LOSSES), "motor_eight_benefits")
        a = min(benefits.values())
    outcome, d, regret, selected = _decision(
        bank, decision_index, quantities, reference_quantities, objective, definition
    )
    return {
        "A": a,
        "D": d,
        "losses": losses,
        "gates": gates,
        "gate_failed_cases": gate_failed,
        "decision_outcome": outcome,
        "verified_regret": regret,
        "selected_design": selected,
    }


def _summary(rows_by_design):
    return {
        design: {
            "feasible": all(r["feasible"] for r in rows),
            "worst_ripple_fraction": max(r["ripple_fraction"] for r in rows),
            "min_mean_torque_nm": min(r["mean_nm"] for r in rows),
        }
        for design, rows in rows_by_design.items()
    }


def _decision(
    bank, decision_index, quantities, reference_quantities, objective, definition
):
    """The native fixed-grid workflow at the registered verification budget."""
    designs = list(objective["design_ids"])
    by_design = {d: [] for d in designs}
    coordinates = {}
    for i in decision_index:
        design = bank[i]["design_id"]
        _require(design in by_design, "motor_design_roster")
        by_design[design].append(bank[i]["case_id"])
        coordinates.setdefault(
            design, tuple(bank[i]["inputs"][k] for k in decision.DESIGN_VARIABLES)
        )
    _require(
        all(
            len(keys) == len(objective["condition_ids"]) for keys in by_design.values()
        ),
        "motor_design_condition_count",
    )
    truth = _summary(
        {d: [reference_quantities[k] for k in keys] for d, keys in by_design.items()}
    )

    def key(table, design):
        # customer_decision.fixed_grid's native tie rule (worst ripple, then
        # higher worst mean torque, then the frozen design coordinates).
        return (
            table[design]["worst_ripple_fraction"],
            -table[design]["min_mean_torque_nm"],
            *coordinates[design],
        )

    feasible_truth = sorted(
        (d for d in designs if truth[d]["feasible"]), key=lambda d: key(truth, d)
    )
    if not feasible_truth:
        return "NONE_FEASIBLE", 0.0, None, None
    if quantities is None:
        # Outputs failed Motor's validity gates: no design can be recommended.
        return "MISSED_OPPORTUNITY", None, None, None
    predicted = _summary(
        {d: [quantities[k] for k in keys] for d, keys in by_design.items()}
    )
    order = sorted(
        (d for d in designs if predicted[d]["feasible"]),
        key=lambda d: key(predicted, d),
    )
    verified = order[: definition["verification_budget"]]
    safe = sorted(
        (d for d in verified if truth[d]["feasible"]), key=lambda d: key(truth, d)
    )
    if not safe:
        return "MISSED_OPPORTUNITY", 0.0, None, None
    selected = safe[0]
    regret = (
        truth[selected]["worst_ripple_fraction"]
        - truth[feasible_truth[0]]["worst_ripple_fraction"]
    )
    return (
        "VERIFIED_FEASIBLE",
        _benefit(regret, definition["D_scale"]),
        regret,
        selected,
    )
