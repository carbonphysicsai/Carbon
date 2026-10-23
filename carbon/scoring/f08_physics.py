"""F08 physics-half plugin (``physics_half``): laws checked on TRAIN v2 (287
references) by the Validator, VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023.

Measured on the predicted row of every geometry, normalised by the TRAIN spread of
the output the law constrains (the units of A_acc):

- **damping scaling**: peak(zeta) x zeta is constant, so peak(0.005) = 2 peak(0.01)
  and peak(0.01) = 2 peak(0.02) (reference ratios 1.99987-1.99991 / 1.99948-1.99965);
- **resonance frequency independent of damping**: f(0.005) = f(0.01) = f(0.02)
  (reference spread 0.046%).

Gated (logical, no tolerance needed; 287/287 on TRAIN): peak dynamic compliance is
at least the static compliance at every damping level, and the peaks are ordered
zeta 0.005 >= 0.01 >= 0.02. Positivity and the registered band are already F08
native ``finite_native_summary`` gate.

The gross-violation gate on the two measured laws takes ``reference residual
quantile + a registered margin``; that margin is for the Validator to register, so
it is None here and those laws are measured but do not gate (HUMAN_INPUT).

The sensitivity leg (A_response) and the trend-sign gates need model queries at
perturbed inputs; see ``physics_half``. DEVELOPMENT only.
"""

from __future__ import annotations

from statistics import pstdev

from carbon.scoring import f08_critical, physics_half

GATE = "physics_laws"
LAWS = (
    ("damping_scaling_005_010", "measured", "peak_tip_z005_mm_per_n", None),
    ("damping_scaling_010_020", "measured", "peak_tip_z010_mm_per_n", None),
    ("frequency_independence_005_010", "measured", "peak_frequency_z005_hz", None),
    ("frequency_independence_010_020", "measured", "peak_frequency_z010_hz", None),
    ("peak_not_below_static", "gate", "static_tip_mm_per_n", None),
    ("peaks_ordered_by_damping", "gate", "peak_tip_z005_mm_per_n", None),
)


def block():
    return physics_half.block(LAWS)


def _spread(train_rows, targets):
    spread = [pstdev(float(row[j]) for row in train_rows) for j in range(len(targets))]
    return dict(zip(targets, spread, strict=True))


def _row(targets, values):
    return dict(zip(targets, values, strict=True))


def _residuals(z, spread):
    return {
        "damping_scaling_005_010": abs(
            z["peak_tip_z005_mm_per_n"] - 2 * z["peak_tip_z010_mm_per_n"]
        )
        / spread["peak_tip_z005_mm_per_n"],
        "damping_scaling_010_020": abs(
            z["peak_tip_z010_mm_per_n"] - 2 * z["peak_tip_z020_mm_per_n"]
        )
        / spread["peak_tip_z010_mm_per_n"],
        "frequency_independence_005_010": abs(
            z["peak_frequency_z005_hz"] - z["peak_frequency_z010_hz"]
        )
        / spread["peak_frequency_z005_hz"],
        "frequency_independence_010_020": abs(
            z["peak_frequency_z010_hz"] - z["peak_frequency_z020_hz"]
        )
        / spread["peak_frequency_z010_hz"],
    }


def _logical(row):
    """The gated laws: dynamic peaks above the static compliance, ordered by damping."""
    peaks = [
        row["peak_tip_z005_mm_per_n"],
        row["peak_tip_z010_mm_per_n"],
        row["peak_tip_z020_mm_per_n"],
    ]
    return {
        "peak_not_below_static": all(p >= row["static_tip_mm_per_n"] for p in peaks),
        "peaks_ordered_by_damping": peaks[0] >= peaks[1] >= peaks[2],
    }


def apply(measured, *, bank_rows, outputs, definition, train_rows, constraints):
    """``measured`` (F08 native measurement, with D already min(V, C)) with the
    physics half A and its law gate, when the definition registers the rule."""
    if "physics" not in definition:
        return measured
    if measured["A"] is None:
        # Non-finite predictions: no law can be read, and the gate fails.
        return {**measured, "gates": {**measured["gates"], GATE: False}}
    physics_half.validate_block(definition["physics"])
    targets = definition["targets"]
    spread = _spread(train_rows, targets)
    predictions = [_row(targets, [float(v) for v in row]) for row in outputs]
    references = [_row(targets, [float(v) for v in r["reference"]]) for r in bank_rows]
    errors = [
        [abs(p[t] - r[t]) / spread[t] for t in targets]
        for p, r in zip(predictions, references, strict=True)
    ]
    # Strata: how close each geometry reference sits to its limits, in the
    # critical scales of the Design half.
    nearness = [
        min(
            abs(constraints["static_tip_mm_per_n_max"] - r[definition["static_target"]])
            / f08_critical.STATIC_MARGIN_SCALE,
            *(
                abs(constraints["dynamic_tip_mm_per_n_max"] - r[t])
                / f08_critical.DYNAMIC_MARGIN_SCALE
                for t in definition["tip_targets"]
            ),
        )
        for r in references
    ]
    a_robust = physics_half.robust_benefit(
        errors, physics_half.split_by_nearness(nearness)
    )
    residuals = {name: [] for name, *_ in LAWS[:4]}
    for p in predictions:
        for name, value in _residuals(p, spread).items():
            residuals[name].append(value)
    a_law, law_record = physics_half.law_benefit(residuals)
    a, legs = physics_half.combine(measured["A"], a_robust, a_law)
    holds = [_logical(p) for p in predictions]
    failed = sorted({name for row in holds for name, ok in row.items() if not ok})
    gates = {**measured["gates"], GATE: not failed}
    return {
        **measured,
        "A": a,
        "A_legs": legs,
        "gates": gates,
        "physics_half": {**law_record, "gate_failed_laws": failed},
    }
