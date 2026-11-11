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

Cases: an out-of-range class's cases are the reserved accuracy slices (`TargetSpec.agen`) of its targets: points the
optimiser never queries. An in-range class's gate cases are the rule's ``gate_cases``: ``"agen"`` (its reserved slices)
or ``"pool"`` (every kept pool point of its targets, whose truths are hidden; record + gate only, never scored; EQ 5 Nov
Q1: R15-disjointness from TRAIN is the pack's, checked where the pack is built). A version may also register a sealed
in-range CASE SET (``in_range_cases_sha256``; `in_range_cases`): hidden in-range truths outside the pool targets (e.g.
in-box non-TRAIN primaries, step-1 in-span records), each case a class, the model's full input row, its truths and U.
Its rows must be exam rows the model answered (the grade reads them from the model's one table); record + gate only. In-range classes are the coverage-plan classes whose targets are all inside the TRAIN range (not EXTENDED);
out-of-range classes have only EXTENDED targets; a class mixing both is refused.

How the family value enters the score is the rule's ``enters``: ``"a"``: A IS the family value (EQ 5 Nov Q2, from the
owner's words: in-range accuracy is a gate, so the in-range A_bank leaves the score). The A/D split ``ad_split`` is
owner-set at 0.5 (owner 17:50, "50/50"), the dual pack's 0.5 A + 0.5 D; any other value refuses until he changes it and
that composition is built. The TOTAL is the rule's ``total_rule``, picked by the owner per version at registration
(no default; unset refuses): ``"half_a_half_d"`` (0.5 A + 0.5 D) or ``"a_only"`` (the physics score alone, for a version
whose D does not separate: the grade reports D := A so the dual pack's 0.5 A + 0.5 D is exactly A).

A cell's score maps |err| to [0, 1] with the version's registered accuracy function (EQ Q3): the A_gen atom
benefit(|err| / agen_scales), or with the registered A multiplier applied (``cell_scale``). Which one is the
Validator's ruling, so ``cell_scale`` has no default and refuses until registered.

Off by default: `pool_proof_suite.Policies.physics` is None for every registered version, and every path that reads it
is then unchanged, bit for bit. Nothing here names a Challenge.
"""

from __future__ import annotations

import collections
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
ENTERS = ("a",)
GATE_CASES = ("agen", "pool")
#: The A/D split: owner-set 0.5 (17:50), the only split the dual pack's total composes (0.5 A + 0.5 D).
AD_SPLIT_BUILT = 0.5
CELL_SCALES = ("agen_scales", "agen_scales_x_a_multiplier")
TOTAL_RULES = ("half_a_half_d", "a_only")
#: How a version scores its battery cells (owner 6 Nov via EQ: headroom scoring adopted, provisional). "cells": the 5 Nov
#: fit-loses scoring-cell map (cell atom benefit(|err| / scale)). "headroom": HEADROOM_SCORING_PLAN rev 2 (f3f47127):
#: per admitted (class, output) the log (or linear) skill against the oracle classical anchor A_c, on the geometric mean
#: of the floored errors |err| / U (floor 1 U).
SCORINGS = ("cells", "headroom")
#: A version's registered target kind (`PhysicsRule.target_kind`): "accuracy_only" (R1: every target carries scored cases
#: only; `pool_grader.build_accuracy_target`). Absent (None) = today's multi-design targets.
TARGET_KINDS = ("accuracy_only",)
SKILL_FORMS = ("log", "linear")
HEADROOM_SCHEMA = "carbon.pool.headroom-admission.v1"
ADMISSION_TESTS = ("H", "C", "O", "R", "V")
VERDICTS = ("PASS", "FAIL")
IN_RANGE_CASES_SCHEMA = "carbon.pool.in-range-cases.v1"
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
class HeadroomAdmission(CellMap):
    """A version's sealed headroom admission (`headroom_admission`): the same families / scored-cell interface as
    `CellMap` (``scored`` = the ADMITTED cells: all five tests PASS, the numeric ones re-checked here), plus each admitted
    cell's anchor A_c (the oracle best of the classical panel's geometric-mean floored error, in U) and the closed list
    of cells that were not admitted (report-only)."""

    anchors: tuple = ()  # (((family, class, output), A_c), ...)
    not_admitted: tuple = ()  # ((family, class, output), ...)

    def anchor(self, key):
        for cell, value in self.anchors:
            if cell == key:
                return value
        raise PhysicsRefused("headroom_anchor_missing")


@dataclass(frozen=True)
class PhysicsRule:
    """A NEW version's physics scoring (all the owner's; None of these has a default).

    ``cells_sha256``: the sha256 of the sealed scoring-cell document. ``gate_statistic``: which of `STATISTICS` gates.
    ``gate_threshold``: the largest passing value of that statistic of |err|/U, one number for every output or
    ``{output: number}`` covering each gated output. Either left None (HUMAN_INPUT) refuses to grade. ``gate_cases``: the
    in-range gate's cases (`GATE_CASES`). ``enters``: how the family value enters the score (`ENTERS`). ``ad_split``: the
    owner's weight of A in the total (owner-set `AD_SPLIT_BUILT`; any other value refuses). ``total_rule``: the version's
    TOTAL (`TOTAL_RULES`; the owner's pick per version, no default).
    ``cell_scale``: the cell atom's scale (`CELL_SCALES`, the Validator's ruling; no default). ``cells``: the attached
    `CellMap` (`attach_cells`); ``a_multiplier``: the registered A multiplier, attached at grade time; both None until.
    """

    cells_sha256: str
    gate_statistic: str | None
    gate_threshold: object
    gate_cases: str | None
    enters: str
    ad_split: object
    total_rule: str | None
    cell_scale: str | None
    cells: object = None
    a_multiplier: object = None
    #: The sha256 of the version's sealed in-range case set, or None (no case set; registered, optional).
    in_range_cases_sha256: str | None = None
    #: The attached `InRangeCases`, or None.
    in_range: object = None
    #: `SCORINGS`. "cells" (the 5 Nov form, ``cells_sha256`` = the scoring-cell map) or "headroom" (``cells_sha256`` = the
    #: sealed headroom admission document; ``cell_scale`` unused and None).
    scoring: str = "cells"
    #: Headroom only, each the owner's (registered per version, no default; None refuses): the skill form
    #: (`SKILL_FORMS`), the headroom thresholds H_min / H_lo (U, > 1) and the resolution floor n_min (cases per class).
    skill_form: str | None = None
    h_min: object = None
    h_lo: object = None
    n_min: object = None
    #: The version's registered target kind (`TARGET_KINDS`, Validator-2B M-1): the registration, never the pack material,
    #: decides it; the grade requires the material's targets to be of exactly this kind. None = today's kind.
    target_kind: str | None = None
    #: The canonical sha256 of the version's SIGNED region document (B5, CV-B W1-W3): the official derive then grades
    #: inputs inside its extended bounds (`cooling_region`). None = the TRAIN box, as before.
    region_sha256: str | None = None


def check_rule(rule):
    """`PhysicsRefused` unless the rule is complete. HUMAN_INPUT (None) in the gate is never defaulted."""
    _require(isinstance(rule, PhysicsRule), "physics_rule_malformed")
    _require(
        rule.target_kind is None or rule.target_kind in TARGET_KINDS,
        "physics_target_kind_unknown",
    )
    _require(
        rule.region_sha256 is None or pool_grader._is_sha256(rule.region_sha256),
        "region_sha256_must_be_64_hex",
    )
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
    _require(rule.gate_cases is not None, "accuracy_gate_cases_not_registered")
    _require(rule.gate_cases in GATE_CASES, "accuracy_gate_cases_must_be_agen_or_pool")
    _require(rule.enters in ENTERS, "physics_enters_must_be_a")
    _require(
        _is_number(rule.ad_split) and rule.ad_split == AD_SPLIT_BUILT,
        "ad_split_must_be_the_owner_set_half",
    )
    _require(rule.total_rule is not None, "physics_total_rule_not_registered")
    _require(
        rule.total_rule in TOTAL_RULES,
        "physics_total_rule_must_be_half_a_half_d_or_a_only",
    )
    _require(rule.scoring in SCORINGS, "physics_scoring_must_be_cells_or_headroom")
    if rule.scoring == "headroom":
        _require(rule.cell_scale is None, "headroom_has_no_cell_scale")
        _require(rule.skill_form is not None, "headroom_skill_form_is_human_input")
        _require(
            rule.skill_form in SKILL_FORMS, "headroom_skill_form_must_be_log_or_linear"
        )
        for name in ("h_min", "h_lo"):
            value = getattr(rule, name)
            _require(value is not None, f"headroom_{name}_is_human_input")
            _require(_is_number(value) and value > 1, f"headroom_{name}_must_exceed_1")
        _require(rule.h_lo <= rule.h_min, "headroom_h_lo_must_not_exceed_h_min")
        _require(rule.n_min is not None, "headroom_n_min_is_human_input")
        _require(
            type(rule.n_min) is int and rule.n_min >= 1,
            "headroom_n_min_must_be_a_positive_int",
        )
        _require(
            rule.cells is None
            or (
                isinstance(rule.cells, HeadroomAdmission)
                and rule.cells.sha256 == rule.cells_sha256
            ),
            "headroom_admission_is_not_the_registered_one",
        )
    else:
        _require(
            all(
                getattr(rule, n) is None
                for n in ("skill_form", "h_min", "h_lo", "n_min")
            ),
            "headroom_values_need_headroom_scoring",
        )
        _require(rule.cell_scale is not None, "cell_scale_not_registered")
        _require(
            rule.cell_scale in CELL_SCALES,
            "cell_scale_must_be_agen_scales_or_x_a_multiplier",
        )
        _require(
            rule.cells is None
            or (type(rule.cells) is CellMap and rule.cells.sha256 == rule.cells_sha256),
            "scoring_cells_are_not_the_registered_ones",
        )
    _require(
        rule.in_range_cases_sha256 is None
        or pool_grader._is_sha256(rule.in_range_cases_sha256),
        "in_range_cases_sha256_must_be_64_hex",
    )
    _require(
        rule.in_range is None
        or (
            isinstance(rule.in_range, InRangeCases)
            and rule.in_range.sha256 == rule.in_range_cases_sha256
        ),
        "in_range_cases_are_not_the_registered_ones",
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


@dataclass(frozen=True)
class InRangeCases:
    """A version's sealed in-range case set (custody: hidden truths). Built only by `in_range_cases`."""

    cases: tuple  # ((class, {input: value}, {output: truth}, {output: U}), ...), in document order
    sha256: str

    def classes(self):
        return sorted({case[0] for case in self.cases})


def _truth_ok(name, value):
    """A case truth: a number, or for an output registered as a waveform (`pool_grader.register_waveform_output`, B6) a
    list of numbers. Whether a waveform truth has a SHAPE is checked separately (`_reference_has_shape`).
    """
    if name in pool_grader._WAVEFORMS:
        return type(value) is list and bool(value) and all(_is_number(v) for v in value)
    return _is_number(value)


def _reference_has_shape(name, value):
    return name not in pool_grader._WAVEFORMS or pool_grader._value_ok(name, value)


def in_range_cases(document):
    """The `InRangeCases` of ``{"schema": IN_RANGE_CASES_SCHEMA, "cases": [{"class", "inputs": {input: number},
    "truths": {output: number}, "u": {output: number > 0}}]}``, or `PhysicsRefused`. Truths and U name the same outputs.
    A truth of an output registered as a WAVEFORM (B6: Motor 1.8's open-circuit back-EMF, k_e,ll) is its reference
    waveform (a list of numbers) with an absolute U > 0; a reference waveform with no shape is the exam's typed reference
    fault (``in_range_case_reference_has_no_shape``), never a candidate's failure.
    """
    _require(
        type(document) is dict
        and set(document) == {"schema", "cases"}
        and document["schema"] == IN_RANGE_CASES_SCHEMA
        and type(document["cases"]) is list
        and document["cases"],
        "in_range_cases_malformed",
    )
    cases = []
    for case in document["cases"]:
        _require(
            type(case) is dict
            and set(case) == {"class", "inputs", "truths", "u"}
            and type(case["class"]) is str
            and case["class"]
            and all(
                type(case[k]) is dict
                and case[k]
                and all(type(n) is str and _is_number(v) for n, v in case[k].items())
                for k in ("inputs", "u")
            )
            and type(case["truths"]) is dict
            and case["truths"]
            and all(
                type(n) is str and _truth_ok(n, v) for n, v in case["truths"].items()
            )
            and set(case["truths"]) == set(case["u"])
            and all(v > 0 for v in case["u"].values()),
            "in_range_case_malformed",
        )
        _require(
            all(_reference_has_shape(n, v) for n, v in case["truths"].items()),
            "in_range_case_reference_has_no_shape",
        )
        cases.append(
            (
                case["class"],
                dict(case["inputs"]),
                # a scalar truth exactly as given (as before); a waveform truth as its tuple of floats
                {
                    n: (pool_grader._keep(n, v) if n in pool_grader._WAVEFORMS else v)
                    for n, v in case["truths"].items()
                },
                dict(case["u"]),
            )
        )
    return InRangeCases(
        cases=tuple(cases),
        sha256=hashlib.sha256(cell_map_bytes(document)).hexdigest(),
    )


def headroom_admission(document, rule):
    """The `HeadroomAdmission` of ``{"schema": HEADROOM_SCHEMA, "families": {family: [class, ...]}, "cells": [{"family",
    "class", "output", "anchor_u", "anchor_lo_u", "n", "tests": {H, C, O, R, V: "PASS" | "FAIL"}}, ...]}`` under the
    rule's registered thresholds, or `PhysicsRefused`.

    A cell is ADMITTED when all five tests read PASS; then the numbers the grader can check are re-checked here: A_c ≥
    H_min, its 90 % lower bound ≥ H_lo, n ≥ n_min, A_c > 1. A PASS that these numbers contradict refuses
    (``headroom_verdict_contradicts_the_thresholds``): a structural fault, never a candidate's. FAIL cells are
    report-only. (C), (O) and (V) are the Validator's verdicts and are taken as written.
    """
    _require(
        type(document) is dict
        and set(document) == {"schema", "families", "cells"}
        and document["schema"] == HEADROOM_SCHEMA,
        "headroom_admission_malformed",
    )
    families = document["families"]
    _require(
        type(families) is dict
        and families
        and all(type(f) is str and f for f in families)
        and all(
            type(c) is list and c and all(type(x) is str and x for x in c)
            for c in families.values()
        ),
        "headroom_admission_families_must_name_classes",
    )
    every = [c for classes in families.values() for c in classes]
    _require(len(set(every)) == len(every), "headroom_admission_class_in_two_families")
    cells = document["cells"]
    _require(type(cells) is list and cells, "headroom_admission_has_no_cell")
    fields = {"family", "class", "output", "anchor_u", "anchor_lo_u", "n", "tests"}
    admitted, anchors, refused, seen = [], [], [], set()
    for cell in cells:
        _require(
            type(cell) is dict
            and set(cell) == fields
            and cell["family"] in families
            and cell["class"] in families[cell["family"]]
            and type(cell["output"]) is str
            and cell["output"]
            and _is_number(cell["anchor_u"])
            and _is_number(cell["anchor_lo_u"])
            and cell["anchor_lo_u"] <= cell["anchor_u"]
            and type(cell["n"]) is int
            and cell["n"] >= 1
            and type(cell["tests"]) is dict
            and set(cell["tests"]) == set(ADMISSION_TESTS)
            and all(v in VERDICTS for v in cell["tests"].values()),
            "headroom_admission_cell_malformed",
        )
        key = (cell["family"], cell["class"], cell["output"])
        _require(key not in seen, "headroom_admission_duplicate_cell")
        seen.add(key)
        if all(cell["tests"][t] == "PASS" for t in ADMISSION_TESTS):
            _require(
                cell["anchor_u"] > 1
                and cell["anchor_u"] >= rule.h_min
                and cell["anchor_lo_u"] >= rule.h_lo
                and cell["n"] >= rule.n_min,
                "headroom_verdict_contradicts_the_thresholds",
            )
            admitted.append(key)
            anchors.append((key, float(cell["anchor_u"])))
        else:
            refused.append(key)
    _require(admitted, "headroom_admission_admits_no_cell")
    return HeadroomAdmission(
        families=tuple(sorted((f, tuple(c)) for f, c in families.items())),
        scored=tuple(sorted(admitted)),
        sha256=hashlib.sha256(cell_map_bytes(document)).hexdigest(),
        anchors=tuple(sorted(anchors)),
        not_admitted=tuple(sorted(refused)),
    )


def skill(rule, anchor, error):
    """S_c of a class error ``error`` (the geometric mean of the floored |err| / U) against its anchor A_c, in [0, 1]:
    log: ln(A / E) / ln(A); linear: (A − E) / (A − 1). 0 = the best classical method, 1 = reference accuracy (E = 1 U).
    """
    if rule.skill_form == "log":
        value = math.log(anchor / error) / math.log(anchor)
    else:
        value = (anchor - error) / (anchor - 1.0)
    return min(1.0, max(0.0, value))


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


def _cases(spec, in_range, rule):
    """The case indices of a target: its reserved slice, or (in range, ``gate_cases == "pool"``) every kept pool point."""
    if in_range and rule.gate_cases == "pool":
        return tuple(range(len(spec.designs)))
    return tuple(spec.agen)


def _gate_threshold(rule, output):
    threshold = rule.gate_threshold
    return threshold if _is_number(threshold) else threshold.get(output)


def attach_cells(rule, document, plan, sets, in_range_document=None):
    """``rule`` with its sealed scoring cells attached, or `PhysicsRefused`: the EXAM's structure, checked once before any
    submission is graded, so a structural fault is never a candidate's result.

    Refused: a document that is not the registered one; a family class that is not an out-of-range plan class (in-range
    accuracy is a gate, never points); a scored output that is not an output of its class's targets; a scored cell with
    no reserved case in some set; an in-range class with no reserved case in some set (the gate would have nothing to
    judge); an in-range gated output whose U is zero on a case (|err|/U undefined); a threshold that does not cover an
    in-range output; an in-range case set that is not the registered one, or whose case names an out-of-range plan
    class or an output the threshold does not cover; and a version with no in-range gate case at all (the gate would
    pass on nothing).
    """
    check_rule(rule)
    _require(
        isinstance(plan, pool_grader.CoveragePlan),
        "physics_rule_needs_a_registered_coverage_plan",
    )
    _require(document is not None, "scoring_cells_missing_from_the_sealed_pack")
    headroom = rule.scoring == "headroom"
    cells = headroom_admission(document, rule) if headroom else cell_map(document)
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
            if headroom:
                # the log skill divides by U: every admitted case needs one
                _require(
                    all(
                        spec.u_at(i, output) > 0 for spec in members for i in spec.agen
                    ),
                    "headroom_output_with_zero_u",
                )
        for name, kind in ranges.items():
            if kind != IN_RANGE:
                continue
            members = cases.get(name, [])
            _require(
                any(_cases(spec, True, rule) for spec in members),
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
                        all(spec.u_at(i, output) > 0 for i in _cases(spec, True, rule)),
                        "accuracy_gate_output_with_zero_u",
                    )
    extra = None
    if rule.in_range_cases_sha256 is None:
        _require(in_range_document is None, "in_range_cases_not_registered")
    else:
        _require(
            in_range_document is not None, "in_range_cases_missing_from_the_sealed_pack"
        )
        extra = in_range_cases(in_range_document)
        _require(
            extra.sha256 == rule.in_range_cases_sha256, "in_range_cases_sha256_mismatch"
        )
        for name, _inputs, truths, _u in extra.cases:
            _require(
                ranges.get(name) != OUT_OF_RANGE, "in_range_case_class_is_out_of_range"
            )
            _require(
                all(_is_number(_gate_threshold(rule, o)) for o in truths),
                "accuracy_gate_threshold_missing_for_an_output",
            )
    _require(
        IN_RANGE in ranges.values() or extra is not None,
        "accuracy_gate_without_in_range_cases",
    )
    if headroom:
        # the admission's n is the class's reserved case count over the whole exam (a mismatch is a different exam)
        counts = collections.Counter()
        for spec in all_specs:
            counts[plan.class_of(spec.target_id)] += len(spec.agen)
        for cell in document["cells"]:
            if (cell["family"], cell["class"], cell["output"]) in cells.scored:
                _require(
                    counts[cell["class"]] == cell["n"],
                    "headroom_admission_n_is_not_the_exams_case_count",
                )
    return replace(rule, cells=cells, in_range=extra)


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


def _ratios(specs, predict, ranges, rule):
    """``{(class, output): [|err|/U, ...]}`` over every reserved case; also ``{(class, output): [|err|, ...]}`` for cases
    whose U is zero (an exact output: reported raw, never divided)."""
    ratios, raw, invalid = {}, {}, {}
    for spec, name in specs:
        indices = _cases(spec, ranges[name] == IN_RANGE, rule)
        if not indices:
            continue
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in indices])
        _require(
            type(batch) is list and len(batch) == len(indices),
            "accuracy_prediction_invalid",
        )
        for index, prediction in zip(indices, batch):
            if not pool_grader._valid_prediction(prediction, spec.outputs):
                # the candidate's invalid answer: counted, and an in-range class holding one fails the gate
                invalid[name] = invalid.get(name, 0) + 1
                continue
            for output in spec.outputs:
                error = pool_grader.difference(
                    output, prediction[output], spec.truths[index][output]
                )
                u = spec.u_at(index, output)
                if u > 0:
                    ratios.setdefault((name, output), []).append(error / u)
                else:
                    raw.setdefault((name, output), []).append(error)
    return ratios, raw, invalid


def _case_ratios(extra, case_predict, ratios, invalid, outputs):
    # Adds the in-range case set's |err|/U into ``ratios`` (by its class), counting invalid answers.
    rows = [dict(inputs) for _name, inputs, _t, _u in extra.cases]
    answers = case_predict(rows)
    _require(
        type(answers) is list and len(answers) == len(rows),
        "accuracy_prediction_invalid",
    )
    for (name, _inputs, truths, u), answer in zip(extra.cases, answers):
        outputs.setdefault(name, set()).update(truths)
        if not _case_answer_valid(answer, truths):
            invalid[name] = invalid.get(name, 0) + 1
            continue
        for output, truth in truths.items():
            # a scalar: |a - t| / U exactly as before; a registered waveform: its registered error (shape_error) / U (B6)
            ratios.setdefault((name, output), []).append(
                pool_grader.difference(output, answer[output], truth) / u[output]
            )


def _case_answer_valid(answer, truths):
    """Whether a model's answer can be graded on a case. A case with only scalar truths: exactly the target check
    (`pool_grader._valid_prediction`). A case naming a registered WAVEFORM output (B6): each truth output is present and
    valid (a waveform with a shape), and the derive's other keys are not graded here, so an OC case is not refused for the
    torque scalars the same derive also returns."""
    if not any(output in pool_grader._WAVEFORMS for output in truths):
        return pool_grader._valid_prediction(answer, tuple(truths))
    return type(answer) is dict and all(
        output in answer and pool_grader._value_ok(output, answer[output])
        for output in truths
    )


def _headroom_row(rule, name, output, values):
    """A headroom version's record columns for one (class, output): admitted or not, and for an admitted cell its class
    error E_c (geometric mean of the floored |err| / U over every case of the exam) and skill S_c. Custody only.
    """
    if rule.scoring != "headroom":
        return {}
    family = rule.cells.family_of(name)
    key = (family, name, output)
    if key not in rule.cells.scored:
        return {"admitted": False, "class_error_u": None, "skill": None}
    if not values:
        return {"admitted": True, "class_error_u": None, "skill": None}
    error = math.exp(statistics.fmean(math.log(max(v, 1.0)) for v in values))
    return {
        "admitted": True,
        "class_error_u": error,
        "skill": skill(rule, rule.cells.anchor(key), error),
    }


def accuracy_record(specs, predict, plan, rule, case_predict=None):
    """The custody accuracy record of one graded model (see the module docstring) and the gate verdict.

    ``{"schema", "rows": [{"class", "range", "family", "output", "scored", "n", "median", "p90", "max", "n_exact",
    "max_abs_exact", "verdict"}], "gate": {"statistic", "passed"}}`` in the plan's class order, then output name order.
    ``verdict`` is "PASS" / "FAIL" for in-range rows and None otherwise; the gate passes only when every in-range row
    passes (a row without a number, or a class holding an invalid answer, fails: fail closed). ``n_invalid`` counts a
    class's invalid answers. The thresholds themselves are the rule's, not repeated here.

    ``case_predict(rows)`` answers the registered in-range case set's input rows (derived outputs per row, or None for an
    invalid answer); its classes follow the plan's, in name order (a class the plan also holds merges with it).
    """
    check_rule(rule)
    _require(rule.cells is not None, "scoring_cells_not_attached")
    ranges = class_ranges(specs, plan)
    ratios, raw, invalid = _ratios(
        [(spec, plan.class_of(spec.target_id)) for spec in specs], predict, ranges, rule
    )
    scored = {(c, o) for _f, c, o in rule.cells.scored}
    outputs = {}
    for spec in specs:
        outputs.setdefault(plan.class_of(spec.target_id), set()).update(spec.outputs)
    order = [name for name in plan.classes if name in ranges]
    if rule.in_range is not None:
        _require(case_predict is not None, "in_range_cases_need_the_exam_table")
        _case_ratios(rule.in_range, case_predict, ratios, invalid, outputs)
        for name in rule.in_range.classes():
            ranges.setdefault(name, IN_RANGE)
            if name not in order:
                order.append(name)
    rows, passed = [], True
    for name in order:
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
                    and not invalid.get(name)
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
                    "n_invalid": invalid.get(name, 0),
                    "verdict": verdict,
                    **_headroom_row(rule, name, output, ratios.get((name, output), [])),
                }
            )
    return {
        "schema": RECORD_SCHEMA,
        "rows": rows,
        "gate": {"statistic": rule.gate_statistic, "passed": passed},
    }


def _atom(rule, error, scale):
    """A cell's case score: the registered A_gen atom benefit(|err| / scale), with the scale tightened by the registered
    A multiplier when ``cell_scale`` says so (`pool_proof_grid.tighten`: 1 / (1 + m x)).
    """
    if rule.cell_scale == "agen_scales_x_a_multiplier":
        return benefit(rule.a_multiplier * error / scale)
    return benefit(error / scale)


def target_cells(spec, predict, scales, plan, rule):
    """One target's contribution to its set's scored cells: ``{(family, class, output): (sum of case atoms, cases)}``
    over its reserved slice (empty when its class holds no scored cell). Sums, so a set's cell mean is the pooled mean
    over its targets' cases, and a target bootstrap recomposes it exactly (`compose`).
    """
    check_rule(rule)
    _require(rule.cells is not None, "scoring_cells_not_attached")
    headroom = rule.scoring == "headroom"
    _require(
        headroom
        or rule.cell_scale != "agen_scales_x_a_multiplier"
        or (_is_number(rule.a_multiplier) and rule.a_multiplier > 0),
        "cell_scale_needs_the_registered_a_multiplier",
    )
    name = plan.class_of(spec.target_id)
    cells = [(f, o) for f, c, o in rule.cells.scored if c == name]
    if not cells or not spec.agen:
        return {}
    for _family, output in cells:
        _require(
            headroom or (_is_number(scales.get(output)) and scales[output] > 0),
            "agen_scales_must_cover_the_scored_outputs",
        )
    batch = predict(spec.conditions, [list(spec.designs[i]) for i in spec.agen])
    _require(
        type(batch) is list and len(batch) == len(spec.agen),
        "agen_prediction_invalid",
    )
    sums = {(family, name, output): [0.0, 0] for family, output in cells}
    for index, prediction in zip(spec.agen, batch):
        _require(
            pool_grader._valid_prediction(prediction, spec.outputs),
            "agen_prediction_invalid",
        )
        for family, output in cells:
            error = pool_grader.difference(
                output, prediction[output], spec.truths[index][output]
            )
            entry = sums[(family, name, output)]
            if headroom:
                # ln of the error in U, floored at 1 U (the reference resolves nothing finer)
                entry[0] += math.log(max(error / spec.u_at(index, output), 1.0))
            else:
                entry[0] += _atom(rule, error, scales[output])
            entry[1] += 1
    return {key: (total, n) for key, (total, n) in sums.items()}


def compose(contributions, rule=None):
    """A set's family value from its targets' `target_cells`: each cell the pooled mean of its case atoms (headroom: the
    skill S_c of the geometric mean exp(mean ln e) against the cell's anchor), each family the mean of its cells with a
    case, the value the equal-weight mean over the families with a cell. None when no cell has a case (only a resample
    can draw that; the grade's structure check refuses it for a set).
    """
    headroom = rule is not None and rule.scoring == "headroom"
    pooled = {}
    for contribution in contributions:
        for key, (total, n) in contribution.items():
            entry = pooled.setdefault(key, [0.0, 0])
            entry[0] += total
            entry[1] += n
    families = {}
    for key, (total, n) in sorted(pooled.items()):
        if n:
            value = (
                skill(rule, rule.cells.anchor(key), math.exp(total / n))
                if headroom
                else total / n
            )
            families.setdefault(key[0], []).append(value)
    if not families:
        return None
    return statistics.fmean(
        statistics.fmean(cells) for _family, cells in sorted(families.items())
    )


def family_value(specs, predict, scales, plan, rule):
    """One set's physics accuracy value, which IS its A (``enters == "a"``): for each scored (family, class, output)
    cell, the mean over the class's reserved cases in `specs` of the cell atom (`_atom`); each family the mean of its
    scored cells; the value the equal-weight mean over the surviving families (a family with a scored cell). Report-only
    cells never enter."""
    contributions = [target_cells(spec, predict, scales, plan, rule) for spec in specs]
    present = {key for c in contributions for key, (_t, n) in c.items() if n}
    _require(present == set(rule.cells.scored), "scoring_cell_without_cases_in_a_set")
    return compose(contributions, rule)


__all__ = [
    "ACCURACY_GATE",
    "AD_SPLIT_BUILT",
    "CELL_SCALES",
    "ENTERS",
    "GATE_CASES",
    "HEADROOM_SCHEMA",
    "IN_RANGE_CASES_SCHEMA",
    "RECORD_SCHEMA",
    "SCORINGS",
    "SCORING_CELLS_SCHEMA",
    "SKILL_FORMS",
    "STATISTICS",
    "TOTAL_RULES",
    "CellMap",
    "HeadroomAdmission",
    "InRangeCases",
    "PhysicsRefused",
    "PhysicsRule",
    "accuracy_record",
    "attach_cells",
    "cell_map",
    "cell_map_bytes",
    "check_rule",
    "class_ranges",
    "compose",
    "family_value",
    "headroom_admission",
    "in_range_cases",
    "skill",
    "target_cells",
]
