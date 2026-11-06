"""Physics scoring for a pool-graded version: the in-range accuracy gate, the full accuracy record, and the family layer.

Basis: the owner's 5 Nov exam-design decisions (EQ's EXAM_DESIGN_PRINCIPLES_20261105.md items 1-3) and EQ's 17:45 record
rule:

1. "Score only classes/outputs where the fit loses. Outside the training data." A version registers, in a sealed
   scoring-cell map, which (family, class, output) cells are SCORED; every other cell is report-only.
2. "In-range accuracy is a gate, threshold from the curves." In-range accuracy is pass/fail, never points. The threshold
   and the statistic it gates (median, p90 or max of |err|/U) are the owner's: registered per version, no default; a
   rule without them refuses to grade (fail closed).
3. The generalization battery: each family is scored only on its registered cells, and the surviving families (those with
   a scored cell) are weighted equally.
4. "As long as we can still get all the data we need through the gates": every grade RECORDS, for every class (in range
   and out of range, scored or report-only) and every output, the median / p90 / max |err|/U over the class's reserved
   cases, the count and (in range) the gate verdict. The record is custody material: it is never scored and never leaves
   custody through `pool_exam.public` (scores-only rule; per-case values never appear in it).

Cases: a class's cases are the reserved accuracy slices (`TargetSpec.agen`) of its targets: points the optimiser never
queries. In-range classes are the coverage-plan classes whose targets are all inside the TRAIN range (not EXTENDED);
out-of-range classes have only EXTENDED targets; a class mixing both is refused.

How the family value enters the score is the rule's ``enters``: ``"a_gen"`` replaces A_gen inside the owner's
`pool_grader.combine_a` rule (A = combine_a(A_bank, family value, a_rule)). Every other composition refuses until the
owner registers it.

Off by default: `pool_proof_suite.Policies.physics` is None for every registered version, and every path that reads it
is then unchanged, bit for bit. Nothing here names a Challenge.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, replace

from carbon.scoring import pool_grader
from carbon.scoring.design_fidelity import benefit

SCORING_CELLS_SCHEMA = "carbon.pool.scoring-cells.v1"
RECORD_SCHEMA = "carbon.pool.accuracy-record.v1"
ACCURACY_GATE = "in_range_accuracy"
STATISTICS = ("median", "p90", "max")
ENTERS = ("a_gen",)
IN_RANGE, OUT_OF_RANGE = "in", "out"


class PhysicsRefused(pool_grader.PoolRefused):
    """The version's physics-scoring material or rule cannot give a sound grade: the Challenge's, never a candidate's."""


def _require(condition, reason):
    if not condition:
        raise PhysicsRefused(reason)


def _is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class CellMap:
    """A version's registered scoring cells. Built only by `cell_map` from the custody document whose sha256 the rule
    registers (class names stay in custody)."""

    families: tuple  # ((family, (class, ...)), ...), sorted by family name
    scored: tuple  # ((family, class, output), ...), sorted
    sha256: str

    def family_of(self, name):
        for family, classes in self.families:
            if name in classes:
                return family
        return None


@dataclass(frozen=True)
class PhysicsRule:
    """A NEW version's physics scoring (all the owner's; None of these has a default).

    ``cells_sha256``: the sha256 of the sealed scoring-cell document. ``gate_statistic``: which of `STATISTICS` gates.
    ``gate_threshold``: the largest passing value of that statistic of |err|/U, one number for every output or
    ``{output: number}`` covering each gated output. Either left None (HUMAN_INPUT) refuses to grade. ``enters``: how the
    family value enters the score (`ENTERS`). ``cells``: the attached `CellMap` (`attach_cells`), or None.
    """

    cells_sha256: str
    gate_statistic: str | None
    gate_threshold: object
    enters: str
    cells: object = None


def check_rule(rule):
    """`PhysicsRefused` unless the rule is complete. HUMAN_INPUT (None) in the gate is never defaulted."""
    _require(isinstance(rule, PhysicsRule), "physics_rule_malformed")
    _require(pool_grader._is_sha256(rule.cells_sha256), "cells_sha256_must_be_64_hex")
    _require(rule.gate_statistic is not None, "accuracy_gate_statistic_is_human_input")
    _require(
        rule.gate_statistic in STATISTICS,
        "accuracy_gate_statistic_must_be_median_p90_or_max",
    )
    threshold = rule.gate_threshold
    _require(threshold is not None, "accuracy_gate_threshold_is_human_input")
    _require(
        (_is_number(threshold) and threshold >= 0)
        or (
            type(threshold) is dict
            and threshold
            and all(type(k) is str and k for k in threshold)
            and all(_is_number(v) and v >= 0 for v in threshold.values())
        ),
        "accuracy_gate_threshold_must_be_a_non_negative_number_or_one_per_output",
    )
    _require(rule.enters in ENTERS, "physics_enters_must_be_a_gen")
    _require(
        rule.cells is None
        or (isinstance(rule.cells, CellMap) and rule.cells.sha256 == rule.cells_sha256),
        "scoring_cells_are_not_the_registered_ones",
    )


def cell_map_bytes(document):
    """The canonical bytes of a scoring-cell document (its sha256 is `CellMap.sha256`)."""
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def cell_map(document):
    """The `CellMap` of ``{"schema": SCORING_CELLS_SCHEMA, "families": {family: [class, ...]}, "scored": [[family, class,
    output], ...]}``, or `PhysicsRefused`. A class sits in at most one family; every scored cell names a family and one of
    its classes; at least one cell is scored; no duplicates."""
    _require(
        type(document) is dict
        and set(document) == {"schema", "families", "scored"}
        and document["schema"] == SCORING_CELLS_SCHEMA,
        "scoring_cells_malformed",
    )
    families, scored = document["families"], document["scored"]
    _require(
        type(families) is dict
        and families
        and all(type(f) is str and f for f in families)
        and all(
            type(classes) is list
            and classes
            and all(type(c) is str and c for c in classes)
            for classes in families.values()
        ),
        "scoring_cells_families_must_name_classes",
    )
    every = [c for classes in families.values() for c in classes]
    _require(len(set(every)) == len(every), "scoring_cells_class_in_two_families")
    _require(
        type(scored) is list
        and scored
        and all(
            type(cell) is list
            and len(cell) == 3
            and all(type(x) is str and x for x in cell)
            and cell[0] in families
            and cell[1] in families[cell[0]]
            for cell in scored
        ),
        "scoring_cells_scored_cell_invalid",
    )
    cells = sorted(tuple(cell) for cell in scored)
    _require(len(set(cells)) == len(cells), "scoring_cells_duplicate_cell")
    return CellMap(
        families=tuple(sorted((f, tuple(c)) for f, c in families.items())),
        scored=tuple(cells),
        sha256=hashlib.sha256(cell_map_bytes(document)).hexdigest(),
    )


def class_ranges(specs, plan):
    """``{class: IN_RANGE | OUT_OF_RANGE}`` over the plan's classes present in `specs`; a class mixing in-range and
    EXTENDED targets is refused (the record and the gate never compare a mix)."""
    kinds = {}
    for spec in specs:
        kinds.setdefault(plan.class_of(spec.target_id), set()).add(spec.extended)
    _require(
        all(len(k) == 1 for k in kinds.values()),
        "physics_class_mixes_in_range_and_out_of_range_targets",
    )
    return {
        name: (OUT_OF_RANGE if kind == {True} else IN_RANGE)
        for name, kind in kinds.items()
    }


def _gate_threshold(rule, output):
    threshold = rule.gate_threshold
    return threshold if _is_number(threshold) else threshold.get(output)


def attach_cells(rule, document, plan, sets):
    """``rule`` with its sealed scoring cells attached, or `PhysicsRefused`: the EXAM's structure, checked once before any
    submission is graded, so a structural fault is never a candidate's result.

    Refused: a document that is not the registered one; a family class that is not an out-of-range plan class (in-range
    accuracy is a gate, never points); a scored output that is not an output of its class's targets; a scored cell with
    no reserved case in some set; an in-range class with no reserved case in some set (the gate would have nothing to
    judge); an in-range gated output whose U is zero on a case (|err|/U undefined); a threshold that does not cover an
    in-range output.
    """
    check_rule(rule)
    _require(
        isinstance(plan, pool_grader.CoveragePlan),
        "physics_rule_needs_a_registered_coverage_plan",
    )
    _require(document is not None, "scoring_cells_missing_from_the_sealed_pack")
    cells = cell_map(document)
    _require(cells.sha256 == rule.cells_sha256, "scoring_cells_sha256_mismatch")
    all_specs = [spec for group in sets for spec in group]
    ranges = class_ranges(all_specs, plan)
    for _family, classes in cells.families:
        _require(
            all(ranges.get(name) == OUT_OF_RANGE for name in classes),
            "scoring_cells_family_class_must_be_out_of_range",
        )
    for group in sets:
        cases = {}
        for spec in group:
            cases.setdefault(plan.class_of(spec.target_id), []).append(spec)
        for _family, name, output in cells.scored:
            members = cases.get(name, [])
            _require(
                all(output in spec.outputs for spec in members),
                "scoring_cells_output_not_an_output_of_its_class",
            )
            _require(
                any(spec.agen for spec in members),
                "scoring_cell_without_cases_in_a_set",
            )
        for name, kind in ranges.items():
            if kind != IN_RANGE:
                continue
            members = cases.get(name, [])
            _require(
                any(spec.agen for spec in members),
                "in_range_class_without_gate_cases_in_a_set",
            )
            for spec in members:
                for output in spec.outputs:
                    threshold = _gate_threshold(rule, output)
                    _require(
                        _is_number(threshold),
                        "accuracy_gate_threshold_missing_for_an_output",
                    )
                    _require(
                        all(spec.u_at(i, output) > 0 for i in spec.agen),
                        "accuracy_gate_output_with_zero_u",
                    )
    return replace(rule, cells=cells)


def _quantile(values, q):
    """The linear-interpolation quantile (the inclusive method) of a non-empty list."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _summary(values):
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p90": _quantile(values, 0.9),
        "max": max(values),
    }


def _ratios(specs, predict):
    """``{(class, output): [|err|/U, ...]}`` over every reserved case; also ``{(class, output): [|err|, ...]}`` for cases
    whose U is zero (an exact output: reported raw, never divided)."""
    ratios, raw = {}, {}
    for spec, name in specs:
        if not spec.agen:
            continue
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in spec.agen])
        _require(
            type(batch) is list and len(batch) == len(spec.agen),
            "accuracy_prediction_invalid",
        )
        for index, prediction in zip(spec.agen, batch):
            _require(
                pool_grader._valid_prediction(prediction, spec.outputs),
                "accuracy_prediction_invalid",
            )
            for output in spec.outputs:
                error = abs(prediction[output] - spec.truths[index][output])
                u = spec.u_at(index, output)
                if u > 0:
                    ratios.setdefault((name, output), []).append(error / u)
                else:
                    raw.setdefault((name, output), []).append(error)
    return ratios, raw


def accuracy_record(specs, predict, plan, rule):
    """The custody accuracy record of one graded model (see the module docstring) and the gate verdict.

    ``{"schema", "rows": [{"class", "range", "family", "output", "scored", "n", "median", "p90", "max", "n_exact",
    "max_abs_exact", "verdict"}], "gate": {"statistic", "passed"}}`` in the plan's class order, then output name order.
    ``verdict`` is "PASS" / "FAIL" for in-range rows and None otherwise; the gate passes only when every in-range row
    passes (a row without a number fails: fail closed). The thresholds themselves are the rule's, not repeated here.
    """
    check_rule(rule)
    _require(rule.cells is not None, "scoring_cells_not_attached")
    ranges = class_ranges(specs, plan)
    ratios, raw = _ratios(
        [(spec, plan.class_of(spec.target_id)) for spec in specs], predict
    )
    scored = {(c, o) for _f, c, o in rule.cells.scored}
    outputs = {}
    for spec in specs:
        outputs.setdefault(plan.class_of(spec.target_id), set()).update(spec.outputs)
    rows, passed = [], True
    for name in plan.classes:
        if name not in ranges:
            continue
        for output in sorted(outputs[name]):
            summary = _summary(ratios.get((name, output), []))
            exact = raw.get((name, output), [])
            verdict = None
            if ranges[name] == IN_RANGE:
                value, threshold = summary[rule.gate_statistic], _gate_threshold(
                    rule, output
                )
                ok = (
                    not exact
                    and value is not None
                    and _is_number(threshold)
                    and value <= threshold
                )
                verdict = "PASS" if ok else "FAIL"
                passed = passed and ok
            rows.append(
                {
                    "class": name,
                    "range": ranges[name],
                    "family": rule.cells.family_of(name),
                    "output": output,
                    "scored": (name, output) in scored,
                    **summary,
                    "n_exact": len(exact),
                    "max_abs_exact": max(exact) if exact else None,
                    "verdict": verdict,
                }
            )
    return {
        "schema": RECORD_SCHEMA,
        "rows": rows,
        "gate": {"statistic": rule.gate_statistic, "passed": passed},
    }


def family_value(specs, predict, scales, plan, rule):
    """One set's physics accuracy value: for each scored (family, class, output) cell, the mean over the class's reserved
    cases in `specs` of the A_gen atom benefit(|err| / scales[output]); each family the mean of its scored cells; the value
    the equal-weight mean over the surviving families (a family with a scored cell). Report-only cells never enter.
    """
    check_rule(rule)
    _require(rule.cells is not None, "scoring_cells_not_attached")
    cells_by_class = {}
    for family, name, output in rule.cells.scored:
        _require(
            _is_number(scales.get(output)) and scales[output] > 0,
            "agen_scales_must_cover_the_scored_outputs",
        )
        cells_by_class.setdefault(name, []).append((family, output))
    atoms = {}
    for spec in specs:
        name = plan.class_of(spec.target_id)
        if name not in cells_by_class or not spec.agen:
            continue
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in spec.agen])
        _require(
            type(batch) is list and len(batch) == len(spec.agen),
            "agen_prediction_invalid",
        )
        for index, prediction in zip(spec.agen, batch):
            _require(
                pool_grader._valid_prediction(prediction, spec.outputs),
                "agen_prediction_invalid",
            )
            for family, output in cells_by_class[name]:
                atoms.setdefault((family, name, output), []).append(
                    benefit(
                        abs(prediction[output] - spec.truths[index][output])
                        / scales[output]
                    )
                )
    _require(
        set(atoms) == set(rule.cells.scored), "scoring_cell_without_cases_in_a_set"
    )
    families = {}
    for (family, _name, _output), values in sorted(atoms.items()):
        families.setdefault(family, []).append(statistics.fmean(values))
    return statistics.fmean(
        statistics.fmean(cells) for _family, cells in sorted(families.items())
    )


__all__ = [
    "ACCURACY_GATE",
    "ENTERS",
    "RECORD_SCHEMA",
    "SCORING_CELLS_SCHEMA",
    "STATISTICS",
    "CellMap",
    "PhysicsRefused",
    "PhysicsRule",
    "accuracy_record",
    "attach_cells",
    "cell_map",
    "cell_map_bytes",
    "check_rule",
    "class_ranges",
    "family_value",
]
