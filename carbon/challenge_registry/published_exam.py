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

SCHEMA = "carbon.published-exam.v1"
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

_BY_VERSION = {
    ("f08-ribbed-bracket", "1.5"): _F08,
    ("f02", "2.4"): _F02,
    ("electric-motor-magnetics", "1.4"): _MOTOR,
    ("chip-cold-plate", "1.4"): _COOLING,
}


def for_version(challenge_id, version):
    """The published exam block for a launch Challenge version, or None."""
    own = _BY_VERSION.get((challenge_id, version))
    if own is None:
        return None
    return {
        "schema": SCHEMA,
        **own,
        "population": _POPULATION,
        "koth": _KOTH,
        "grade_statuses": _GRADE,
        "practice_vs_exam": _PRACTICE,
        "rotation": _ROTATION,
    }


def served():
    """The (challenge id, version) pairs that carry a block."""
    return sorted(_BY_VERSION)
