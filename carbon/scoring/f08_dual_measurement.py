"""F08's dual A/D measurement from one retained model's bank predictions.

DEVELOPMENT only. This is the summary dual F08 measurement
(OPTIMIZER_F08_SUMMARY_DUAL_PACKET_20261018, sha256 4e07322f...) computed from
one model's predictions on the exposed accepted-reference geometries. Every
scale, band and limit comes from the registered accuracy definition and the
pack's important-limit document; nothing here chooses a value.

A is the minimum of reciprocal benefits ``1/(1+loss)`` over the seven learned
summary targets' mean TRAIN-normalised absolute errors and the worst
geometry's mean error. Mass is not learned and earns no accuracy credit: each
geometry's CAD mass is a registered property of the geometry, used only for
feasibility. D is ``1/(1+regret/D_scale)`` for a predicted-feasible pick
(least worst tip peak) that the references verify feasible, 0 for an
infeasible pick. Gates: a finite native summary in the registered frequency
band on every geometry, the paired repeat (the graded run and two fresh
repeats equal under the packet's rule), complete accepted references, and
the verified-feasible pick.
"""

from __future__ import annotations

import math
from statistics import fmean, pstdev

DEFINITION_SCHEMA = "carbon.scoring.f08-dual-accuracy.v1"
METHOD = "f08-summary-dual-from-predictions.v1"
# OWNER-F08-FREQUENCY-BAND-DROP-01: prospective 1.7 only. Older definitions
# omit this field and retain their registered band check.
SANITY_RULE = "nonnegative_compliance_positive_frequency.v1"
GATES = (
    "finite_native_summary",
    "paired_repeat",
    "complete_accepted_reference",
    "verified_pick_feasible",
)


class F08MeasurementRefused(ValueError):
    """The bank, definition or references cannot support the measurement."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise F08MeasurementRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_definition(definition):
    """The registered A/D definition document, checked for every field used."""
    targets = definition.get("targets") if type(definition) is dict else None
    _require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and type(targets) is list
        and len(targets) == 7
        and definition.get("tip_targets") is not None
        and set(definition["tip_targets"]) <= set(targets)
        and set(definition.get("frequency_targets", ())) <= set(targets)
        and definition.get("static_target") in targets
        and definition.get("A_reducer") == "minimum"
        and _number(definition.get("D_scale_mm_per_n"))
        and definition["D_scale_mm_per_n"] > 0
        and type(definition.get("frequency_band_hz")) is list
        and len(definition["frequency_band_hz"]) == 2
        and all(_number(v) for v in definition["frequency_band_hz"])
        and definition.get("native_summary_rule") in (None, SANITY_RULE)
        and definition.get("paired_repeat_rule") == "exact_equality"
        and type(definition.get("geometry_count")) is int,
        "f08_definition",
    )
    return definition


def native_summary(row, *, targets, frequency_targets, frequency_band_hz, rule=None):
    """One per-answer check for native grading and the pool hook.

    The historical rule retains the band. The owner's prospective rule treats
    frequencies as predictions: positive and finite, with their error scored in A.
    Damping ordering remains the registered physics-law gate.
    """
    if len(row) != len(targets) or not all(_number(v) and v >= 0 for v in row):
        return False
    frequencies = [targets.index(name) for name in frequency_targets]
    if rule == SANITY_RULE:
        return all(row[j] > 0 for j in frequencies)
    low, high = frequency_band_hz
    return all(low <= row[j] <= high for j in frequencies)


def _limits(limits):
    constraints = (limits or {}).get("constraints") if type(limits) is dict else None
    _require(
        type(constraints) is dict
        and all(
            _number(constraints.get(k)) and constraints[k] > 0
            for k in (
                "mass_kg_max",
                "static_tip_mm_per_n_max",
                "dynamic_tip_mm_per_n_max",
            )
        ),
        "f08_limits",
    )
    return constraints


def measure(*, bank, outputs, repeats, definition, limits, train):
    """A, D, native gates and the decision outcome for one model.

    ``bank`` rows carry ``case_id``, ``inputs``, ``reference`` (the seven
    targets in definition order) and ``record`` (with ``status`` and
    ``cad_mass_kg``); ``outputs`` and the two ``repeats`` are that many
    seven-value rows. ``train`` is TRAIN's target rows in the same order.
    """
    validate_definition(definition)
    constraints = _limits(limits)
    targets = definition["targets"]
    n = len(bank)
    _require(n == definition["geometry_count"], "f08_bank_geometries")
    _require(
        type(outputs) is list
        and len(outputs) == n
        and type(repeats) in (list, tuple)
        and len(repeats) == 2
        and all(type(r) is list and len(r) == n for r in repeats),
        "f08_prediction_roster",
    )
    _require(
        all(r["record"].get("status") == "OK" for r in bank),
        "f08_reference_unresolved",
    )
    _require(all(_number(r["record"].get("cad_mass_kg")) for r in bank), "f08_cad_mass")
    references = [[float(v) for v in r["reference"]] for r in bank]
    width = len(targets)
    _require(
        all(len(r) == width and all(map(_number, r)) for r in references),
        "f08_reference_values",
    )
    spread = [pstdev(float(row[j]) for row in train) for j in range(width)]
    _require(all(_number(s) and s > 0 for s in spread), "f08_train_normalization")
    index = {name: j for j, name in enumerate(targets)}
    tips = [index[name] for name in definition["tip_targets"]]
    static = index[definition["static_target"]]

    rule = definition.get("native_summary_rule")
    if rule == SANITY_RULE:
        # Malformed new-version answers fail the native gate, rather than
        # escaping as a float-conversion exception. Historical readers stay exact.
        def rows(values):
            return [list(r) if type(r) in (list, tuple) else [] for r in values]

        graded = rows(outputs)
        runs = [graded, *[rows(r) for r in repeats]]
    else:
        graded = [[float(v) for v in row] for row in outputs]
        runs = [graded, *[[list(map(float, row)) for row in r] for r in repeats]]
    finite = all(
        native_summary(
            row,
            targets=targets,
            frequency_targets=definition["frequency_targets"],
            frequency_band_hz=definition["frequency_band_hz"],
            rule=rule,
        )
        for run in runs
        for row in run
    )
    repeat_equal = runs[0] == runs[1] == runs[2]

    def feasible(row, mass):
        return (
            mass <= constraints["mass_kg_max"]
            and row[static] <= constraints["static_tip_mm_per_n_max"]
            and max(row[j] for j in tips) <= constraints["dynamic_tip_mm_per_n_max"]
        )

    def pick(rows):
        candidates = [
            (max(row[j] for j in tips), bank[i]["case_id"])
            for i, row in enumerate(rows)
            if feasible(row, bank[i]["record"]["cad_mass_kg"])
        ]
        return min(candidates)[1] if candidates else None

    a = None
    if finite:
        errors = [
            [abs(p - r) / spread[j] for j, (p, r) in enumerate(zip(prow, rrow))]
            for prow, rrow in zip(graded, references, strict=True)
        ]
        losses = [fmean(row[j] for row in errors) for j in range(width)]
        losses.append(max(fmean(row) for row in errors))
        a = min(1.0 / (1.0 + loss) for loss in losses)
    picked = pick(graded) if finite else None
    feasible_refs = {
        bank[i]["case_id"]: max(row[j] for j in tips)
        for i, row in enumerate(references)
        if feasible(row, bank[i]["record"]["cad_mass_kg"])
    }
    best = min(feasible_refs.values(), default=None)
    verified = picked is not None and picked in feasible_refs
    if verified:
        regret = max(0.0, feasible_refs[picked] - best)
        d, outcome = 1.0 / (1.0 + regret / definition["D_scale_mm_per_n"]), (
            "VERIFIED_FEASIBLE"
        )
    else:
        regret, d = None, 0.0
        outcome = "MISSED_OPPORTUNITY" if best is not None else "NONE_FEASIBLE"
    return {
        "gates": {
            "finite_native_summary": finite,
            "paired_repeat": repeat_equal,
            "complete_accepted_reference": True,
            "verified_pick_feasible": verified,
        },
        "A": a,
        "D": d,
        "pick": picked,
        "regret_mm_per_n": regret,
        "decision_outcome": outcome,
    }
