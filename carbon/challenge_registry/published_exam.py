"""What each launch Challenge's exam tests, as structured public fields
(OWNER-PUBLISH-WHAT-IS-TESTED-01; the Validator's exam-safety ruling,
codex-queue/reports/VALIDATOR_PUBLISH_WHAT_IS_TESTED_RULING_20261024.md).

One rule: publish what is measured and what passes; withhold where the exam's
cases are and how they were chosen. Every value below is copied from the
registered constant named in its `source`; `tests/cpu/test_published_exam.py`
re-reads those constants in code and fails when one differs, and its door test
fails when a served section is not on `ALLOWED_FIELDS` or a withheld item
appears. A value that is not registered is the words "not yet registered",
never a blank or a placeholder number.

This module is data only (standard library, no scoring import), so the miner
door carries no exam code.
"""

from __future__ import annotations

import copy

from carbon.challenge_registry import speed_gate

SCHEMA = "carbon.published-exam.v1"
#: The block of a pool-graded version (design search over solved designs, no
#: solver at grade time). Older versions keep v1 byte for byte.
SCHEMA_POOL = "carbon.published-exam.v2"
NOT_REGISTERED = "not yet registered"

#: The Validator's allow-list: the only top-level sections the published block
#: may carry. A new section goes to the Validator before it is published
#: (default: withhold). The door test also scans every served value for the
#: withheld items (seeds, draw ids, ids of a particular exam, placement
#: internals).
ALLOWED_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "scoring_version",
        "score",
        "minimums",
        "gates",
        "physics_laws",
        "design_value_scales",
        "limits",
        "uncertainty",
        "exam_shape",
        "population",
        "koth",
        "grade_statuses",
        "practice_vs_exam",
        "rotation",
        "design_search",
        "how_you_are_tested",
        "speed_gate",
    }
)

_SHARED_SOURCE = "carbon/scoring/dual_score.py, physics_half.py, critical_fidelity.py"

_SCORE_LEGS = [
    {
        "id": "A_acc",
        "measures": "accuracy of the model's outputs on the exam's cases",
    },
    {
        "id": "A_robust",
        "measures": "the same accuracy on the worse of two strata: cases nearer "
        "the main limit and cases further from it",
    },
    {
        "id": "A_law",
        "measures": "how far the model's outputs break the measured physics "
        "laws, as an equivalent normalised output error (the units of A_acc)",
    },
    {
        "id": "A_response",
        "measures": "how far the model's sensitivity to each input departs "
        "from the log-log slope fitted on public TRAIN, as an equivalent "
        "normalised output error (the units of A_acc)",
    },
    {
        "id": "V_pair",
        "measures": "share of design pairs ordered correctly, misordered pairs "
        "costing their true objective gap",
    },
    {
        "id": "V_feas",
        "measures": "1 / (1 + mean cost) of wrongly accepting an infeasible "
        "design or rejecting a feasible one",
    },
    {
        "id": "V_var",
        "measures": "how good the model's pick is for the base limit and for "
        "the limit shifted down and up by the nearby-variant shift",
    },
    {
        "id": "C",
        "measures": "how well the model predicts the decision margins of every "
        "candidate design, selected or not (1 / (1 + worst normalised error))",
    },
]


def _score(a_acc, extra=None):
    legs = [dict(leg) for leg in _SCORE_LEGS]
    legs[0] = {"id": "A_acc", "measures": a_acc}
    return {
        "formula": "TOTAL = 0.5 * A + 0.5 * D",
        "weights": {"A": 0.5, "D": 0.5},
        "rule": {
            "A": "A = mean(A_acc, A_robust, A_law, A_response)",
            "D": "D = min(V, C), V = mean(V_pair, V_feas, V_var); V of 0 stays "
            "0, and any critical cell the model leaves unpredicted gives no D",
            "decision": "a pick that is not verified feasible by the references "
            "gets D = 0",
        },
        "legs": legs,
        "nearby_variant_shift": {
            "value": 0.05,
            "unit": "fraction of the main limit (plus and minus 5 %)",
            "source": "carbon/scoring/critical_fidelity.py SHIFT",
        },
        "source": _SHARED_SOURCE + (extra or ""),
    }


_MINIMUMS = {
    "A": None,
    "D": None,
    "note": "No leg minimum is registered in the sealed pack; each batch takes "
    "its minimums from the baseline's own run on that batch, and a submission "
    "below a minimum is not eligible (equality passes).",
    "source": "each *_sealed_dual_pack.py, `minimum`: None",
}

_LAW_MARGIN = {
    "gross_violation_margin": NOT_REGISTERED,
    "note": "Laws marked measured count in A_law but are not yet gate margins.",
}

_KOTH = {
    "rule": "The best total wins. A challenger must beat the king by the "
    "registered margin; a tie keeps the king; the first king must beat "
    "Carbon's baseline by the margin.",
    "margin": NOT_REGISTERED,
    "note": "While no margin is registered, takeovers are paused.",
    "ladder_step": {"value": 0.02, "unit": "total", "source": "grade_feedback.py ETA"},
    "source": "carbon/challenge_validator/koth_public.py, bank_promotion.py, "
    "koth_rebuild_noise.json",
}

_GRADE = {
    "statuses": ["IMPROVED", "NO_IMPROVEMENT", "GATE_FAILED", "NOT_SCORED"],
    "reasons": [
        "LEG_MINIMUM_FAILED",
        "CANDIDATE_INVALID",
        "DECISION_INELIGIBLE",
        "FAILED_INFRA",
        "INDETERMINATE",
    ],
    "source": "carbon/scoring/grade_feedback.py STATUSES, REASONS",
}

_PRACTICE = (
    "Practice runs on the public bank, with public-seeded probes; its totals "
    "are not exam totals. The exam uses private cases."
)
_ROTATION = "Exams rotate at most every 90 days, with a weekly overfit check."
_POPULATION = (
    "Cases are drawn near the design limit, inside the published validity "
    "region, so that some designs pass and some fail."
)
#: The pool-graded exam (Validator spec POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024,
#: OWNER-INVERSE-DESIGN-PROOF-01). Challenge-neutral
#: text only. Every constant the spec leaves to the owner (query budget, honesty
#: scale, A_gen scale and how A_gen enters A) is the words "not yet registered"
#: until the owner registers it with the grader module; nothing here is a number
#: the spec does not fix. The target and pool counts are the Validator-registered
#: ones (receipt on 3b2b3fcac).
_POOL_SOURCE = "codex-queue/reports/POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024.md"


def pool_score(a_acc):
    """The score section of a pool-graded version (legs A and D as the spec fixes them)."""
    legs = [dict(leg) for leg in _SCORE_LEGS[:4]]
    legs[0] = {"id": "A_acc", "measures": a_acc}
    legs.append(
        {
            "id": "A_gen",
            "measures": "the same accuracy on a fixed slice of the extended "
            "validity region, with its own scale; the design search is never "
            "allowed to ask your model about those points",
        }
    )
    legs.append(
        {
            "id": "D_opt",
            "measures": "how well Carbon's fixed search designs with your "
            "model on hidden targets: 0 for a target whose pick is not "
            "feasible, otherwise closeness to the best known design times "
            "honesty",
        }
    )
    legs.append(
        {
            "id": "C",
            "measures": "how well the model predicts the decision margins of "
            "every candidate design it is asked about",
        }
    )
    return {
        "formula": "TOTAL = 0.5 * A + 0.5 * D",
        "weights": {"A": 0.5, "D": 0.5},
        "rule": {
            "A": "A = mean(A_acc, A_robust, A_law, A_response); how A_gen "
            "enters A is " + NOT_REGISTERED,
            "D": "D = min(mean of the per-target scores of a set, C); see "
            "design_search",
            "decision": "a pick that is not feasible by the known true "
            "outputs gets 0 for that target",
        },
        "legs": legs,
        "source": _POOL_SOURCE,
    }


_DESIGN_SEARCH = {
    "what": "Design value is inverse design: Carbon's own fixed optimizer "
    "(CMA-ES, deterministic for a given model) uses your model to find a "
    "design that meets each hidden target's limits. A target is one design "
    "problem: an objective to maximise or minimise, the registered limits "
    "and fixed conditions. Some targets are the base problem and some are "
    "variants of it inside the extended validity region.",
    "search": {
        "optimizer": "CMA-ES in the target's normalised design box; you "
        "cannot choose or change the search",
        "query_budget": NOT_REGISTERED,
        "step": "each proposal snaps to the nearest unqueried design of a set "
        "of already-solved designs; your model predicts that design's outputs",
        "internal_objective": "your model's predicted objective, with a "
        "penalty for predicted limit violations",
        "final_pick": "the best predicted-feasible design among those queried",
    },
    "truth": "The pick's true outputs are looked up, not solved: nothing is "
    "solved at grade time. Solved designs whose true margin is within the "
    "registered measurement uncertainty of a limit are left out, so every "
    "remaining design is clearly feasible or clearly infeasible.",
    "per_target_score": {
        "infeasible": 0,
        "feasible": "closeness * honesty",
        "closeness": "(objective of your pick - the median feasible objective) "
        "/ (the best known objective - the median feasible objective), "
        "clipped to 0..1, so a typical feasible design scores 0 and only "
        "near-best designs score well",
        "honesty": "exp(-e / s), where e is your model's uncertainty-normalised "
        "error at its pick; a model that steers the search with optimistic "
        "predictions loses here",
        "honesty_scale": NOT_REGISTERED,
    },
    "set_score": "The design score of a set is the mean over its targets.",
    "targets_and_pools": "6 targets per set, 2 sets; 100 solved designs per " "target",
    "deterministic": "The same model gives the same score, so the paired "
    "repeat check holds.",
    "disclosure": "You see the rounded total and a closed reason code, as "
    "before. Per-target values, picks and the solved designs stay private.",
    "source": _POOL_SOURCE,
}

_PRACTICE_POOL = (
    "Practice runs on the public bank and shows what it can of A, the gates "
    "and the minimums. It never touches the exam's hidden targets or its "
    "out-of-range questions, and a practice total is not an exam total."
)

#: "How you are tested": the plain-words page for a pool-graded version (owner,
#: 2026-10-25: "for out of range, robustness, and inverse design we just tell
#: them how it will be tested"). One list feeds the describe tool, the Launchpad
#: page and docs/MINING.md ("How you're tested"); a test holds the three equal.
#: Nothing hidden is named: not the targets, the extended region's bounds, the
#: limit shifts, the optimizer's starting points or seeds, or the solved designs.
#: The speed gate's ceiling per design, per Challenge: one registered module
#: (`speed_gate`), read by the grader, this block and the scoring-rules tool.
_SPEED_CEILING_SECONDS = speed_gate.ceilings()
SPEED_LINE = (
    "Your model must answer each design in at most 1/500 of the time the "
    "reference solver needs for one design. The time is measured on the "
    "validator's machine, for the whole batch of exam designs with the model's "
    "loading included, divided by the number of designs. Failing it is a failed "
    "gate (speed), and no score."
)
HOW_TESTED_LINES = (
    (
        "score",
        "The grade",
        (
            "Your grade is 0.5 x A + 0.5 x D, from 0 to 1, higher is better. A is "
            "accuracy and physics. D is design value."
        ),
    ),
    (
        "inverse_design",
        "Inverse design",
        (
            "Design value is inverse design. Carbon's own fixed optimizer (CMA-ES) "
            "uses your model to search for designs that meet each hidden target's "
            "limits, within a fixed number of model queries, and picks one design "
            "from a set Carbon has already solved. A pick that does not meet the "
            "limits scores 0 for that target; otherwise it scores how close it is "
            "to the best known design, times how honest your model's prediction "
            "was at that pick. You cannot change the search. The query budget is "
            "not yet registered."
        ),
    ),
    (
        "optimizer",
        "The search, to copy",
        (
            "You may copy this search for your own practice; it never enters "
            "the grade. In each target, CMA-ES proposes points in the "
            "normalised design box and each proposal snaps to the nearest "
            "solved design not yet queried; your model predicts that design's "
            "outputs; designs are ranked first by whether they are predicted to "
            "meet the limits and then by the predicted objective. After the "
            "fixed number of queries the pick is the best predicted-feasible "
            "design among those queried, and its true outputs are looked up. A "
            "pick that is not feasible scores 0. Otherwise the target scores "
            "closeness times honesty, where closeness = (objective of the pick "
            "- median feasible objective) / (best known objective - median "
            "feasible objective), clipped to 0..1, and honesty = exp(-e / s), "
            "with e your model's uncertainty-normalised error at the pick. D is "
            "the mean over the targets, limited by C. The query budget, the "
            "step size and s are not yet registered."
        ),
    ),
    (
        "variants",
        "Tighter and looser limits",
        (
            "Some targets are tighter or looser versions of the base problem: the "
            "same design question with its limits moved. A model that only works "
            "for the base limits loses there. How far the limits move is not "
            "published."
        ),
    ),
    (
        "out_of_range",
        "Outside the training range",
        (
            "Some exam questions lie just outside the range your training data "
            "covers. They count: accuracy there, inverse-design picks there, and "
            "the physics gates there. How far that range extends, and where its "
            "questions are, is not published."
        ),
    ),
    (
        "gates",
        "Physics gates",
        (
            "The physics gates that check a single answer run on every answer "
            "your model gives, inside and outside the range. Failing any gate "
            "means no score at all, however good the rest. You are told which "
            "gate failed, never which design."
        ),
    ),
    ("speed", "Speed", SPEED_LINE),
    (
        "minimums",
        "Minimums",
        (
            "Each score part also has a minimum, set from Carbon's own baseline on "
            "the exam. A part below its minimum makes the submission not eligible, "
            "and the part is named. Until a version's minimums are registered, the "
            "page says minimums are not yet set."
        ),
    ),
    (
        "practice",
        "Practice",
        (
            "Practice runs on the public bank and shows what it can of A, the "
            "gates and the minimums. It never touches the exam's hidden targets or "
            "its out-of-range questions, and a practice total is not an exam total."
        ),
    ),
)


#: The owner constants a pool version has registered, copied from
#: `carbon/scoring/pool_constants.json` (a test holds the two equal). A version
#: absent here keeps the words "not yet registered". Motor 1.5:
#: OWNER-MOTOR-SHEET-AND-F02-EXPONENT-01 (owner "1 and a", 2026-10-26). The A_gen
#: scales are 0.03 x the TRAIN spread of each output, which is public TRAIN data;
#: no target, pool, region bound or seed is named.
_REGISTERED_POOL = {
    ("electric-motor-magnetics", "1.5"): {
        "query_budget": 60,
        "initial_step": 0.25,
        "honesty_scale": 1.0,
        "honesty_reduction": "max",
        "a_multiplier": 3.0,
        "a_gen_rule": "mean",
        "a_gen_scales": {
            "mean_torque_nm": 0.07433812816092869,
            "ripple_fraction": 0.08677790679238961,
        },
        "c_rule": "min",
        "source": "carbon/scoring/pool_constants.json (OWNER-MOTOR-SHEET-AND-F02-EXPONENT-01)",
    }
}


def registered_pool(challenge_id, version):
    """The registered owner constants of a pool version, or None."""
    own = _REGISTERED_POOL.get((challenge_id, version))
    return None if own is None else copy.deepcopy(own)


def _registered_text(own):
    scales = ", ".join(
        f"{name} {value:.4f}" for name, value in own["a_gen_scales"].items()
    )
    return (
        f"The search asks the model {own['query_budget']} times per target, from "
        f"a first step of {own['initial_step']:g} of the normalised design box. "
        f"Honesty is exp(-e / s) with s = {own['honesty_scale']:g}, and e is the "
        "largest uncertainty-normalised error over the outputs at the pick. Each "
        "of the four accuracy parts of A is tightened as 1 / (1 + "
        f"{own['a_multiplier']:g} x) of its normalised error x. A_gen is scored "
        "the same way on its own slice with a scale of 0.03 x the training "
        f"spread of each output ({scales}), and the final A is the mean of A and "
        "A_gen. D is limited by C: it is the smaller of the two."
    )


def _with_registered_design_search(base, own):
    search = copy.deepcopy(base)
    search["search"]["query_budget"] = own["query_budget"]
    search["search"]["initial_step"] = own["initial_step"]
    per_target = search["per_target_score"]
    per_target["honesty_scale"] = own["honesty_scale"]
    per_target["honesty"] += " (e is the largest of the per-output errors at the pick)"
    search["source"] = own["source"]
    return search


def _with_registered_score(score, own):
    score = copy.deepcopy(score)
    score["rule"]["A"] = (
        "A = mean(A_acc, A_robust, A_law, A_response), each tightened as "
        f"1 / (1 + {own['a_multiplier']:g} x); the final A is the mean of that A "
        "and A_gen"
    )
    return score


def how_you_are_tested(challenge_id, version=None):
    """The "How you are tested" lines of a pool-graded version of
    ``challenge_id``: id, title and text each; the speed line also names this
    Challenge's ceiling per design."""
    ceiling = _SPEED_CEILING_SECONDS[challenge_id]
    registered = registered_pool(challenge_id, version)
    lines = []
    for line_id, title, text in HOW_TESTED_LINES:
        if line_id == "speed":
            text = text + f" The ceiling for this Challenge is {ceiling} s per design."
        if registered is not None and line_id == "inverse_design":
            text = text.replace(
                "The query budget is not yet registered.",
                f"The query budget is {registered['query_budget']}.",
            )
        if registered is not None and line_id == "optimizer":
            text = text.replace(
                "The query budget, the step size and s are not yet registered.",
                f"The query budget is {registered['query_budget']}, the first step "
                f"{registered['initial_step']:g} and s {registered['honesty_scale']:g}.",
            )
        lines.append({"id": line_id, "title": title, "text": text})
    if registered is not None:
        lines.append(
            {
                "id": "registered_values",
                "title": "This version's registered values",
                "text": _registered_text(registered),
            }
        )
    return lines


_SPAN_STEP = {
    "step": {
        "value": "0.005 to 0.015",
        "unit": "fraction of each input's span",
        "source": "carbon/scoring/probe_design.py DELTA_RANGE",
    },
    "base_points": {"value": 4, "source": "each *_sealed_pack.py PROBE_BASES"},
    "note": "Probes are extra rows the model also predicts; they are random "
    "points inside the published validity region.",
}


def _probes(rows, rows_source):
    return {**_SPAN_STEP, "rows": {"value": rows, "source": rows_source}}


def _gate(gate_id, passes_when, value=None):
    return {"id": gate_id, "passes_when": passes_when, "value": value}


_F08 = {
    "scope": "f08-ribbed-bracket 1.5",
    "scoring_version": "f08-dual-sealed-grid-8x1-v2",
    "score": _score(
        "1 / (1 + loss) with loss the worst of the seven targets' mean "
        "normalised error over the 8 geometries and the worst geometry's mean "
        "error (normalised by the TRAIN population spread)",
        ", f08_dual_measurement.py",
    ),
    "minimums": _MINIMUMS,
    "gates": [
        _gate(
            "finite_native_summary",
            "the graded rows and both repeats are finite and non-negative, and "
            "the three peak frequencies lie in the band",
            {"frequency_band_hz": [80, 600]},
        ),
        _gate(
            "paired_repeat",
            "the graded run and the two fresh repeats are identical, per case",
            {"rule": "exact_equality"},
        ),
        _gate(
            "complete_accepted_reference",
            "the exam's references are complete and accepted",
        ),
        _gate(
            "verified_pick_feasible",
            "the model's pick is feasible by the references; otherwise D = 0",
            {
                "mass_kg_max": 0.45,
                "static_tip_mm_per_n_max": 0.03,
                "dynamic_tip_mm_per_n_max": 0.15,
            },
        ),
        _gate(
            "physics_laws",
            "no gated law is violated, no sign law fails, and the probe "
            "predictions are usable",
        ),
    ],
    "physics_laws": {
        "gated": [
            _gate(
                "peak_not_below_static",
                "the peak dynamic compliance is at least the static compliance "
                "at every damping level",
                {"unit": "mm/N"},
            ),
            _gate(
                "peaks_ordered_by_damping",
                "the peak at zeta 0.005 is at least the peak at 0.01, which is "
                "at least the peak at 0.02",
                {"unit": "mm/N"},
            ),
        ],
        "measured": [
            (
                "damping_scaling_005_010 (peak at 0.005 = 2 x peak at 0.01, the "
                "1/zeta peak scaling)"
            ),
            "damping_scaling_010_020 (peak at 0.01 = 2 x peak at 0.02)",
            "frequency_independence_005_010 (peak frequency at 0.005 = at 0.01)",
            "frequency_independence_010_020 (peak frequency at 0.01 = at 0.02)",
        ],
        "sign_laws": [
            (
                "static tip compliance rises with length and falls with width, "
                "thickness, rib height and rib thickness"
            ),
            "peak frequency falls with length and rises with rib height",
        ],
        **_LAW_MARGIN,
        "source": "carbon/scoring/f08_physics.py",
    },
    "design_value_scales": {
        "static_margin": {"value": 0.003, "unit": "mm/N"},
        "dynamic_margin": {"value": 0.015, "unit": "mm/N"},
        "resonance": {"value": 10.0, "unit": "Hz"},
        "objective_D_scale": {"value": 0.01, "unit": "mm/N"},
        "source": "carbon/scoring/f08_critical.py, f08_dual_pack.py",
    },
    "limits": {
        "mass_kg_max": 0.45,
        "static_tip_mm_per_n_max": 0.03,
        "dynamic_tip_mm_per_n_max": 0.15,
        "inputs_mm": {
            "length": [180, 260],
            "width": [60, 100],
            "thickness": [4, 8],
            "rib_height": [8, 16],
            "rib_thickness": [3, 5],
            "relief_length": [20, 60],
        },
        "damping_ratios": [0.005, 0.01, 0.02],
        "source": "carbon/challenge_kit/physical_pack.py, "
        "carbon/challenge_pipeline/structures_readiness.py",
    },
    "uncertainty": {
        "static_tip_mm_per_n": 6.7e-07,
        "worst_dynamic_mm_per_n": 3.9e-05,
        "mass": NOT_REGISTERED,
        "source": "f08-reference-uncertainty.json (physical_pack.py)",
    },
    "exam_shape": {
        "cells": 8,
        "designs": 8,
        "conditions": 1,
        "probes": _probes(52, "f08_sealed_pack.py"),
    },
}

_F02 = {
    "scope": "f02 2.4",
    "scoring_version": "f02-dual-sealed-grid-8x1-v2",
    "score": _score(
        "1 / (1 + loss) with loss the worst of the mean peak-temperature error "
        "over the 8 cases, the near-limit block's mean error and the maximum "
        "error (each error is |prediction - reference| / TRAIN peak spread, "
        "6.701 degC)",
        ", private_evaluation_source.py, f02_train.py",
    ),
    "minimums": _MINIMUMS,
    "gates": [
        _gate("finite_peak", "every predicted peak is a finite number"),
        _gate(
            "paired_repeat",
            "both fresh repeats equal the graded outputs exactly, per case",
            {"tolerance_ulp": 0},
        ),
        _gate(
            "reference_acceptance",
            "the exam holds only accepted references that were compared "
            "across solver rungs",
        ),
        _gate(
            "verified_pick",
            "the model's pick is feasible by the references",
            {"peak_top_c_max": 95.0},
        ),
        _gate(
            "physics_laws",
            "no gated law is violated, no sign law fails, and the probe "
            "predictions are usable",
        ),
    ],
    "physics_laws": {
        "gated": [
            _gate(
                "peak_not_below_initial",
                "every predicted peak is at least the initial temperature",
                {"initial_c": 40.0, "unit": "degC"},
            )
        ],
        "measured": ["affine_in_power (the peak is affine in power at fixed on-time)"],
        "sign_laws": [
            (
                "the temperature rise over the initial rises with peak power and "
                "with on-time"
            ),
        ],
        **_LAW_MARGIN,
        "source": "carbon/scoring/f02_physics.py",
    },
    "design_value_scales": {
        "value_scale": {"value": 100.0, "unit": "J"},
        "margin_scale": {"value": 1.0, "unit": "degC"},
        "source": "carbon/scoring/f02_dual_pack.py S_VALUE_J, MARGIN_SCALE_C",
    },
    "limits": {
        "peak_top_c_max": 95.0,
        "inputs": {"peak_w": [70.0, 100.0], "on_time_s": [4.0, 6.0]},
        "fixed_context": {
            "coolant_c": 30.0,
            "h_w_m2_k": 2500.0,
            "initial_c": 40.0,
            "left_source_fraction": 0.5,
            "waveform": "rectangular",
        },
        "source": "carbon/challenge_kit/f02_train.py, carbon/f02/domain.py",
    },
    "uncertainty": {
        "peak_top_c": 0.012,
        "source": "f02-reference-uncertainty.json (carbon/f02/decision_check.py)",
    },
    "exam_shape": {
        "cells": 8,
        "designs": 8,
        "conditions": 1,
        "probes": _probes(28, "f02_sealed_pack.py (7 rows per base point)"),
    },
}

_MOTOR = {
    "scope": "electric-motor-magnetics 1.4",
    "scoring_version": "motor-dual-sealed-batch-30-v2",
    "score": _score(
        "the smallest of three 1 / (1 + loss / scale) benefits: the mean "
        "torque-curve error over all 30 cells, the worst design's mean error, "
        "and the median signed margin error",
        ", motor_sealed_dual_pack.py",
    ),
    "minimums": _MINIMUMS,
    "gates": [
        _gate(
            "native_motor_valid",
            "no cell fails a native gate against either fresh repeat or "
            "between the repeats, and every cell is scorable",
        ),
        _gate("complete_fixed_coverage", "all 30 cells are scored", {"cells": 30}),
        _gate(
            "physics_laws",
            "no gated law is violated, no sign law fails, and the probe "
            "predictions are usable",
        ),
        _gate(
            "schema_finite",
            "the torque curve is present with 60 finite values",
            {"angle_steps": 60},
        ),
        _gate(
            "motoring_mean_nonnegative",
            "mean(torque) is at least -(1e-3 x max|torque| + 1e-3 N.m)",
            {"relative": 1e-3, "floor_nm": 1e-3},
        ),
        _gate(
            "paired_repeat",
            "a duplicate's prediction equals the original's within 32 float32 ulp",
            {"ulp": 32},
        ),
    ],
    "physics_laws": {
        "gated": [
            _gate(
                "mean_torque_positive",
                "the mean torque of the predicted curve is positive wherever "
                "the current density exceeds 1 A/mm^2",
                {"unit": "N.m"},
            )
        ],
        "measured": [
            "linear_in_current (mean torque scales with current density, K = 1.5)",
            (
                "zero_current_torque (mean torque tends to 0 as current density "
                "tends to 0)"
            ),
        ],
        "sign_laws": [
            "mean torque rises with current density and falls with current angle"
        ],
        **_LAW_MARGIN,
        "source": "carbon/scoring/motor_physics.py, carbon/motor/exam.py",
    },
    "design_value_scales": {
        "torque_margin": {"value": 0.10, "unit": "N.m"},
        "ripple_margin": {"value": 0.01, "unit": "ripple fraction"},
        "objective_D_scale": {"value": 0.01, "unit": "ripple fraction"},
        "source": "carbon/scoring/motor_sealed_dual_pack.py, "
        "motor-applied-score-definition-20261018.json",
    },
    "limits": {
        "min_mean_torque_nm": 4.0,
        "max_ripple_fraction": 0.3,
        "ripple_fraction": "(max torque - min torque) / mean torque",
        "inputs": {
            "magnet_mm": [1.5, 4.0],
            "embrace": [0.55, 0.95],
            "airgap_mm": [0.3, 1.0],
            "slot_open_deg": [1.0, 6.0],
            "tooth_mm": [2.5, 5.0],
            "slot_bottom_mm": [34.0, 42.0],
            "current_density_a_mm2": [0.0, 15.0],
            "current_angle_deg": [0.0, 60.0],
        },
        "source": "carbon/challenge_kit/data/motor-important-limit-definition-"
        "20261018.json, carbon/motor/domain.py",
    },
    "uncertainty": {
        "mean_torque_nm": 0.0052,
        "ripple_fraction": 0.026,
        "source": "motor-reference-uncertainty.json "
        "(carbon/motor_grid_exam/decision_check.py)",
    },
    "exam_shape": {
        "cells": 30,
        "designs": 5,
        "conditions": 6,
        "probes": _probes(76, "motor_sealed_pack.py (19 rows per base point)"),
    },
}

_COOLING = {
    "scope": "chip-cold-plate 1.4",
    "scoring_version": "cooling-dual-sealed-batch-16-v2",
    "score": _score(
        "the smallest of the peak, profile and pressure benefits "
        "1 / (1 + error / scale), each over all 16 cells and over the worst "
        "design (scales from public TRAIN)",
        ", cooling_dual_measurement.py",
    ),
    "minimums": _MINIMUMS,
    "gates": [
        _gate(
            "native_cold_plate",
            "every cell is scorable against both fresh repeats and the two "
            "repeats agree",
        ),
        _gate("complete_grid_common_mask", "the grid is a complete 4 x 4 cross"),
        _gate(
            "selected_design_verified_feasible",
            "the model's pick is feasible by the references at every condition",
            {"die_peak_c_max": 100.0, "hydraulic_power_w_max": 0.25},
        ),
        _gate(
            "physics_laws",
            "no gated law is violated, no sign law fails, and the probe "
            "predictions are usable",
        ),
        _gate(
            "schema_finite",
            "peak, the 30-value profile and the pressure drop are present and finite",
            {"profile_values": 30},
        ),
        _gate("face_above_inlet", "the lowest profile value is above the inlet"),
        _gate(
            "peak_bounds_profile",
            "the peak is at least the highest profile value less 32 float32 ulp",
            {"ulp": 32},
        ),
        _gate("pressure_drop_positive", "the pressure drop is above zero"),
        _gate(
            "paired_repeat",
            "a duplicate's prediction equals the original's within 32 float32 ulp",
            {"ulp": 32},
        ),
    ],
    "physics_laws": {
        "gated": [
            _gate(
                "peak_above_profile",
                "the peak is at least the highest profile value",
                {"unit": "degC"},
            ),
            _gate(
                "profile_above_inlet",
                "the lowest profile value is at least the inlet",
                {"unit": "degC"},
            ),
            _gate(
                "pressure_positive", "the pressure drop is above zero", {"unit": "Pa"}
            ),
        ],
        "measured": [
            (
                "inlet_shift_temperatures (moving only the inlet by 5 degC moves "
                "the peak and every profile segment by the same amount)"
            ),
            (
                "pressure_ignores_hotspot (mirroring only the hotspot inputs "
                "leaves the pressure drop unchanged)"
            ),
        ],
        "sign_laws": [
            (
                "the temperature rise falls with flow and rises with heat load and "
                "hotspot ratio"
            ),
            "the pressure drop rises with flow and falls with channel width and depth",
        ],
        **_LAW_MARGIN,
        "source": "carbon/scoring/cooling_physics.py, carbon/cold_plate/exam.py",
    },
    "design_value_scales": {
        "die_margin": {"value": 1.0, "unit": "degC"},
        "hydraulic_margin": {"value": 0.025, "unit": "W"},
        "objective_D_scale": {"value": 0.025, "unit": "W"},
        "source": "carbon/scoring/cooling_dual_measurement.py, cooling_dual_pack.py",
    },
    "limits": {
        "die_peak_c_max": 100.0,
        "hydraulic_power_w_max": 0.25,
        "inputs": {
            "channel_width_mm": [0.2, 0.5],
            "fin_width_mm": [0.2, 0.5],
            "channel_depth_mm": [1.0, 3.0],
            "flow_lpm_per_kw": [1.25, 2.0],
            "inlet_c": [30.0, 45.0],
            "heat_load_w": [500.0, 1500.0],
            "hotspot_ratio": [1.0, 3.0],
            "hotspot_center_mm": [3.0, 27.0],
            "hotspot_width_mm": [1.5, 3.5],
        },
        "source": "carbon/challenge_kit/data/cooling-important-limit-definition-"
        "20261018.json, carbon/cold_plate/domain.py",
    },
    "uncertainty": {
        "die_peak_c": 0.037,
        "hydraulic_w": {"relative": 0.03},
        "source": "cooling-reference-uncertainty.json "
        "(carbon/cold_plate_exam/decision_check.py)",
    },
    "exam_shape": {
        "cells": 16,
        "designs": 4,
        "conditions": 4,
        "probes": _probes(84, "cooling_sealed_pack.py (21 rows per base point)"),
    },
}

_POOL_GATES = [
    _gate(
        "physics_pool",
        "the Challenge's physics gates hold on every design your model answers in the "
        "exam, in range and out of range; a violation fails the whole submission and "
        "names only the gate",
    ),
    _gate(
        "speed",
        "the median seconds of single-design calls on 20 sealed designs is at most "
        "the ceiling",
    ),
]


def _pool_block(own, scope, scoring_version):
    """The pool-graded successor of a launch version: the same material and gates, the pool score and its gates."""
    return {
        **own,
        "scope": scope,
        "scoring_version": scoring_version,
        "score": pool_score(own["score"]["legs"][0]["measures"]),
        "gates": [*own["gates"], *_POOL_GATES],
    }


_F08_POOL = _pool_block(_F08, "f08-ribbed-bracket 1.6", "f08-pool-sealed-v1")
_F08_POOL_SANITY = {
    **_pool_block(_F08, "f08-ribbed-bracket 1.7", "f08-pool-sealed-v2"),
    "gates": [
        _gate(
            "finite_native_summary",
            "the graded rows and both repeats have the correct width and finite "
            "numbers, non-negative compliance and strictly positive peak frequencies; "
            "frequency error, including outside 80–600 Hz, is scored in A",
        ),
        *_F08["gates"][1:],
        *_POOL_GATES,
    ],
}
_F02_POOL = _pool_block(_F02, "f02 2.5", "f02-pool-sealed-v1")
_MOTOR_POOL = _pool_block(
    _MOTOR, "electric-motor-magnetics 1.5", "motor-pool-sealed-v1"
)
_COOLING_POOL = _pool_block(_COOLING, "chip-cold-plate 1.5", "cooling-pool-sealed-v1")
# OWNER-COOLING-HOTSPOT-GATE-DROP-01: a new version, never a rewrite of _COOLING.
_COOLING_POOL_16 = {
    **_pool_block(_COOLING, "chip-cold-plate 1.6", "cooling-pool-sealed-v2"),
    "physics_laws": {
        **_COOLING["physics_laws"],
        "sign_laws": [
            "the temperature rise falls with flow and rises with heat load",
            "the pressure drop rises with flow and falls with channel width and depth",
        ],
        "source": "carbon/scoring/cooling_hotspot_dual_pack.py, carbon/scoring/cooling_physics.py, carbon/cold_plate/exam.py",
    },
    "score": pool_score(
        _COOLING["score"]["legs"][0]["measures"]
        + "; the hotspot-ratio sensitivity has no registered response exponent"
    ),
}

#: Versions graded by the pool grader (their `_BY_VERSION` entry must carry a
#: `pool_score(...)` score); the block of every other version is unchanged.
_POOL_VERSIONS = frozenset(
    {
        ("f08-ribbed-bracket", "1.6"),
        ("f08-ribbed-bracket", "1.7"),
        ("f02", "2.5"),
        ("electric-motor-magnetics", "1.5"),
        ("chip-cold-plate", "1.5"),
        ("chip-cold-plate", "1.6"),
    }
)

_BY_VERSION = {
    ("f08-ribbed-bracket", "1.5"): _F08,
    ("f08-ribbed-bracket", "1.6"): _F08_POOL,
    ("f08-ribbed-bracket", "1.7"): _F08_POOL_SANITY,
    ("f02", "2.5"): _F02_POOL,
    ("electric-motor-magnetics", "1.5"): _MOTOR_POOL,
    ("chip-cold-plate", "1.5"): _COOLING_POOL,
    ("chip-cold-plate", "1.6"): _COOLING_POOL_16,
    ("f02", "2.4"): _F02,
    ("electric-motor-magnetics", "1.4"): _MOTOR,
    ("chip-cold-plate", "1.4"): _COOLING,
}


def for_version(challenge_id, version):
    """The published exam block for a launch Challenge version, or None."""
    own = _BY_VERSION.get((challenge_id, version))
    if own is None:
        return None
    pool = (challenge_id, version) in _POOL_VERSIONS
    block = {
        "schema": SCHEMA_POOL if pool else SCHEMA,
        **own,
        "population": _POPULATION,
        "koth": _KOTH,
        "grade_statuses": _GRADE,
        "practice_vs_exam": _PRACTICE_POOL if pool else _PRACTICE,
        "rotation": _ROTATION,
    }
    if pool:
        block["design_search"] = _DESIGN_SEARCH
        block["how_you_are_tested"] = how_you_are_tested(challenge_id, version)
        registered = registered_pool(challenge_id, version)
        if registered is not None:
            block["design_search"] = _with_registered_design_search(
                _DESIGN_SEARCH, registered
            )
            block["score"] = _with_registered_score(block["score"], registered)
        block["speed_gate"] = {
            "ratio": speed_gate.RATIO,
            "rule": "seconds per design <= the reference solver's seconds "
            "per design / ratio",
            "solver_seconds_per_design": speed_gate.SOLVER_SECONDS_PER_DESIGN[
                challenge_id
            ],
            "ceiling_seconds_per_design": speed_gate.ceiling_seconds(challenge_id),
            "failure": "GATE_FAILED (speed)",
            "source": "carbon/challenge_registry/speed_gate.py",
        }
    return block


def served():
    """The (challenge id, version) pairs that carry a block."""
    return sorted(_BY_VERSION)
