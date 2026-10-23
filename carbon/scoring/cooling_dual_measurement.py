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
from carbon.scoring import critical_fidelity as critical

DEFINITION_SCHEMA = "carbon.scoring.cooling-dual-accuracy.v1"
METHOD = "cooling-counted-dual-from-predictions.v1"
COHORT_COUNTS = {"decision_representative": 32, "decision_boundary_stress": 16}
_REDUCTIONS = ("all48", "worst_geometry", "boundary")
GATES = (
    "native_cold_plate",
    "complete48_common_mask",
    "selected_design_verified_feasible",
)
#: A sealed exam batch (Validator, 2026-10-20, cooling-dual-sealed-batch-16-v1):
#: one 4 x 4 grid in one cohort, so no boundary reduction (A is the minimum
#: over all 16 and the worst geometry), its own grid gate key, and its
#: reference evidence pinned by sha256.
SEALED_COHORT = "decision_sealed_grid"
SEALED_COHORT_COUNTS = {SEALED_COHORT: 16}
#: The practice grid of the full exposed public bank: 8 designs x 6 conditions
#: (labelled "practice (public bank)", never comparable with a sealed grade).
PRACTICE_COHORT_COUNTS = {SEALED_COHORT: 48}
GRID_COHORT_COUNTS = (SEALED_COHORT_COUNTS, PRACTICE_COHORT_COUNTS)
_SEALED_REDUCTIONS = ("all16", "worst_geometry")
SEALED_GATES = (
    "native_cold_plate",
    "complete_grid_common_mask",
    "selected_design_verified_feasible",
)
#: dev1 section 4 / section 7 DEVELOPMENT normalisation scales (not physical
#: thresholds): die margin 1 C, hydraulic margin 0.025 W. A sealed definition
#: registers them in its ``critical`` block (D = min(V, C)); a definition
#: without the block grades V alone, as the earlier evaluation version did.
DIE_MARGIN_SCALE_C = 1.0
HYDRAULIC_MARGIN_SCALE_W = 0.025


def critical_block(d_scale_w):
    return critical.block(
        [
            ("die_margin", "margin", "die_margin_c", "C", DIE_MARGIN_SCALE_C),
            (
                "hydraulic_margin",
                "margin",
                "hydraulic_margin_w",
                "W",
                HYDRAULIC_MARGIN_SCALE_W,
            ),
        ],
        ("W", "MINIMIZE", d_scale_w),
        [("die_margin", 1)],
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


def sealed(definition):
    """Whether ``definition`` grades a sealed exam batch (development banks'
    definitions carry no ``bank_kind``, as before)."""
    return type(definition) is dict and definition.get("bank_kind") == "sealed_batch"


def gates_for(definition):
    return SEALED_GATES if sealed(definition) else GATES


def validate_definition(definition):
    """The registered A/D definition document, checked for every field used."""
    is_sealed = sealed(definition)
    _require(
        type(definition) is dict
        and definition.get("bank_kind", "development")
        in ("development", "sealed_batch")
        and (
            not is_sealed
            or (
                type(definition.get("reference_evidence_sha256")) is str
                and len(definition["reference_evidence_sha256"]) == 71
                and definition["reference_evidence_sha256"].startswith("sha256:")
            )
        )
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("components") == list(exam.COMPONENTS)
        and definition.get("reductions")
        == list(_SEALED_REDUCTIONS if is_sealed else _REDUCTIONS)
        and definition.get("A_reducer") == "minimum"
        and all(
            _number(definition.get(k)) and definition[k] > 0
            for k in ("A_scale", "D_scale_W")
        )
        and type(definition.get("verification_condition_budget")) is int
        and definition["verification_condition_budget"] >= 1
        and (
            definition.get("cohort_counts") in GRID_COHORT_COUNTS
            if is_sealed
            else definition.get("cohort_counts") == COHORT_COUNTS
        )
        and definition.get("target_slices")
        == {"peak_c": [0, 1], "profile_c": [1, 31], "pressure_drop_pa": [31, 32]},
        "cooling_definition",
    )
    if "critical" in definition:
        _require(is_sealed, "cooling_definition")
        try:
            critical.validate_block(definition["critical"])
        except critical.CriticalFidelityRefused as exc:
            raise CoolingMeasurementRefused("cooling_definition") from exc
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
    is_sealed = sealed(definition)
    expected = definition["cohort_counts"] if is_sealed else COHORT_COUNTS
    counts = {c: 0 for c in expected}
    for row in bank:
        _require(row.get("cohort") in counts, "cooling_bank_cohort")
        counts[row["cohort"]] += 1
    _require(counts == expected, "cooling_bank_cohorts")
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
            # Cooling's native outputs only: a sealed batch's runner records
            # also carry diagnostics (mean_c, outlet_c), which the decision
            # code refuses as inexact; a development record has no others.
            "outputs": {k: row["record"]["outputs"][k] for k in exam.SHAPES},
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
        everything = "_all16" if is_sealed else "_all48"
        for component in exam.COMPONENTS:
            components[component + everything] = fmean(
                error[component] for error in errors.values()
            )
            components[component + "_worst_geometry"] = max(
                fmean(errors[(d, c)][component] for c in conditions) for d in designs
            )
            if not is_sealed:
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
    fidelity = critical_inputs = None
    if "critical" in definition:
        # D = min(V, C): C is the worst signed die/hydraulic margin error over
        # every design x condition cell, the unselected designs included; V is
        # the mean of the pair-ordering, accept/reject and nearby-variant measures.
        critical_inputs = _critical_inputs(
            definition,
            bank,
            keys,
            designs,
            conditions,
            references,
            first,
            contract,
            picked,
        )
        d_benefit, fidelity = _critical_design(d_benefit, critical_inputs, definition)
    cells = {}
    if "physics" in definition and critical_inputs is not None:
        # What the physics half needs of the exam cells (no extra solves).
        margins = critical_inputs[3]["cases"]
        cells = {
            "_cells": {
                "cell_errors": (
                    {bank[index[key]]["case_id"]: errors[key] for key in keys}
                    if errors
                    else {}
                ),
                "nearness": {
                    cid: min(
                        abs(m["die_margin_c"]) / DIE_MARGIN_SCALE_C,
                        abs(m["hydraulic_margin_w"]) / HYDRAULIC_MARGIN_SCALE_W,
                    )
                    for cid, m in margins.items()
                },
                "condition_cells": [
                    [bank[index[(d, c)]]["case_id"] for d in designs]
                    for c in conditions
                ],
            }
        }
    return {
        **cells,
        **({"design_fidelity": fidelity} if "critical" in definition else {}),
        "gates": dict(
            zip(gates_for(definition), (native_pass, True, verified), strict=True)
        ),
        "gate_failed_cases": gate_failed,
        "components": components,
        "A": a,
        "D": d_benefit,
        "pick": picked,
        "regret_w": regret,
        "decision_outcome": "VERIFIED_FEASIBLE" if verified else "MISSED_OPPORTUNITY",
    }


_MARGINS = ("die_margin_c", "hydraulic_margin_w")


def _critical_inputs(
    definition, bank, keys, designs, conditions, references, predictions, contract, pick
):
    """Cooling's cells for ``critical_fidelity``: the reference's and the
    model's signed die and hydraulic margins at every design x condition, and
    each design's worst-condition hydraulic power."""
    ids = [row["case_id"] for row in bank]

    def cells(outputs):
        found = {}
        for i, key in enumerate(keys):
            try:
                row = cd.quantities(contract, bank[i]["inputs"], outputs[i])
            except (ValueError, TypeError, KeyError, OverflowError):
                found[ids[i]] = {}
                continue
            found[ids[i]] = {name: row[name] for name in _MARGINS} | {
                "feasible": row["feasible"],
                "hydraulic_w": row["hydraulic_w"],
            }
        return found

    truth = cells([r["outputs"] for r in references])
    _require(all(truth[cid] for cid in ids), "cooling_reference_quantities")
    cells_of = {d: [ids[keys.index((d, c))] for c in conditions] for d in designs}
    predicted = cells(predictions)
    reference = {
        "cases": {cid: {n: row[n] for n in _MARGINS} for cid, row in truth.items()},
        "actions": {
            d: {
                "feasible": all(truth[cid]["feasible"] for cid in members),
                "objective": max(truth[cid]["hydraulic_w"] for cid in members),
            }
            for d, members in cells_of.items()
        },
    }
    prediction = {
        "cases": {
            cid: {n: row[n] for n in _MARGINS if n in row}
            for cid, row in predicted.items()
        },
        "selected": pick,
        "objective": {
            d: max(predicted[cid]["hydraulic_w"] for cid in members)
            for d, members in cells_of.items()
            if all("hydraulic_w" in predicted[cid] for cid in members)
        },
    }
    limits = {"die_margin": contract["constraints"]["die_peak_c_max"]}
    return ids, list(designs), cells_of, reference, prediction, limits


def _critical_design(base_v, inputs, definition):
    ids, actions, cells_of, reference, prediction, limits = inputs
    v, v_record = critical.value(
        definition["critical"],
        cells_of=cells_of,
        reference=reference,
        prediction=prediction,
        base_v=base_v,
        limits=limits,
    )
    d, record = critical.design(
        v,
        critical.reduce(
            definition["critical"],
            case_ids=ids,
            action_ids=actions,
            reference=reference,
            prediction=prediction,
        ),
    )
    record["value"] = v_record
    return d, record
