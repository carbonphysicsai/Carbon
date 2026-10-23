"""Motor physics-half plugin (``physics_half``), laws checked on TRAIN v1 (150
references) by the Validator (VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023, "Law data").

Everything is read from the mean torque of a predicted 60-angle curve, in units of
the TRAIN spread of the mean torque so it sits with A_acc.

- **Gate:** mean torque is positive when the current density exceeds 1 A/mm^2
  (139/139 on TRAIN), on every graded cell and probe.
- **Measured (A_law), linearity in the current:** at fixed geometry and angle,
  mean(kJ) = k mean(J) with k = 1.5; the probe residual is
  ``|mean(kJ) - k mean(J)|``.
- **Measured (A_law), zero-current limit:** mean torque tends to 0 as J tends to 0;
  the probe at J = 0 gives ``|mean|``.
- **Measured (A_response):** the log-log exponent of mean torque against current
  density (fitted on TRAIN, 1.01), with its allowance band.
- **Sign gates:** torque rises with current density and falls with current angle.
  The angle fit is too loose for a size, so it has no registered exponent.

Gross-violation margins stay unregistered (None): the measured laws do not gate.
DEVELOPMENT only.
"""

from __future__ import annotations

import io
from statistics import fmean, pstdev

from carbon.motor import domain
from carbon.scoring import physics_half, probe_design

GATE = "physics_laws"
K = 1.5
OUTPUT = "mean_torque_nm"
LAWS = (
    ("linear_in_current", "measured", OUTPUT, None),
    ("zero_current_torque", "measured", OUTPUT, None),
    ("mean_torque_positive", "gate", OUTPUT, None),
)
SIGN_GATES = (
    (OUTPUT, "current_density_a_mm2", 1),
    (OUTPUT, "current_angle_deg", -1),
)
#: The probe region: the registered input bounds, except that the base current
#: density runs from 1 A/mm^2 (the positivity law and the TRAIN fits hold above it)
#: to 13, leaving room for the scaled-current law row to stay inside the 15 A/mm^2
#: range (its factor is then at least 15/13).
PROBE_BOUNDS = tuple(
    (1.0, 13.0) if name == "current_density_a_mm2" else domain.INPUT_BOUNDS[name]
    for name in domain.INPUTS
)
J_MAX = domain.INPUT_BOUNDS["current_density_a_mm2"][1]
_J = domain.INPUTS.index("current_density_a_mm2")
_ANGLE = domain.INPUTS.index("current_angle_deg")


def probe_extra():
    """The law-probe rows: the current scaled by k, and zero."""

    def scaled(x):
        moved = list(x)
        moved[_J] = min(K * x[_J], J_MAX)
        return moved

    def zero(x):
        moved = list(x)
        moved[_J] = 0.0
        return moved

    return (("j_up", scaled), ("j_zero", zero))


def valid_geometry(x) -> bool:
    return not domain.validity(dict(zip(domain.INPUTS, x, strict=True)))


def _train(train_raw):
    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        return (
            np.asarray(data["inputs"], dtype=float),
            np.asarray(data["targets"], dtype=float),
        )


def mean_torque(curve):
    return fmean(float(v) for v in curve)


def response_registration(train_raw):
    """The reference sensitivity of mean torque to the current density: the log-log
    exponent from a fit on TRAIN rows with J > 1 and positive mean torque."""
    import numpy as np

    x, curves = _train(train_raw)
    mean = curves.mean(axis=1)
    keep = (x[:, _J] > 1.0) & (mean > 0)
    names = domain.INPUTS
    geometry = [i for i, n in enumerate(names) if i not in (_J, _ANGLE)]
    design = np.column_stack(
        [
            np.ones(int(keep.sum())),
            np.log(x[keep][:, geometry]),
            np.log(x[keep][:, _J]),
            np.cos(np.radians(x[keep][:, _ANGLE])),
        ]
    )
    target = np.log(mean[keep])
    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
    rmse = float(np.sqrt(np.mean((design @ coefficients - target) ** 2)))
    j_column = 1 + len(geometry)
    spread = float(np.log(x[keep][:, _J]).std())
    exponent = [None] * len(names)
    band = [None] * len(names)
    exponent[_J] = round(float(coefficients[j_column]), 6)
    band[_J] = round(rmse / spread, 6)
    low, high = zip(*PROBE_BOUNDS, strict=True)
    return {
        "inputs": list(names),
        "outputs": [OUTPUT],
        "exponent": [exponent],
        "band": [band],
        "span": [float(h - lo) for lo, h in zip(low, high, strict=True)],
        "delta_range": list(probe_design.DELTA_RANGE),
        "sign_gates": [{"output": o, "input": i, "sign": s} for o, i, s in SIGN_GATES],
    }


def registered_model(train_raw):
    """A stand-in predictor with exactly the registered sensitivities: the TRAIN
    log-log mean-torque fit (geometry logs, log J, cos angle). Returns
    ``predict(point) -> mean torque``; zero at zero current. For tests and
    controls only; it is not a submitted model."""
    import numpy as np

    x, curves = _train(train_raw)
    mean = curves.mean(axis=1)
    keep = (x[:, _J] > 1.0) & (mean > 0)
    geometry = [i for i, n in enumerate(domain.INPUTS) if i not in (_J, _ANGLE)]
    design = np.column_stack(
        [
            np.ones(int(keep.sum())),
            np.log(x[keep][:, geometry]),
            np.log(x[keep][:, _J]),
            np.cos(np.radians(x[keep][:, _ANGLE])),
        ]
    )
    coefficients, *_ = np.linalg.lstsq(design, np.log(mean[keep]), rcond=None)

    def predict(point):
        if point[_J] <= 0:
            return 0.0
        row = np.concatenate(
            [
                [1.0],
                np.log([point[i] for i in geometry]),
                [np.log(point[_J]), np.cos(np.radians(point[_ANGLE]))],
            ]
        )
        return float(np.exp(row @ coefficients))

    return predict


def block(train_raw):
    return physics_half.block(LAWS, response_registration(train_raw))


def train_spread(train_raw):
    """The TRAIN spread of the mean torque (population standard deviation)."""
    _, curves = _train(train_raw)
    return float(pstdev(float(v) for v in curves.mean(axis=1)))


def apply(
    measured,
    *,
    f0,
    nearness,
    condition_cells,
    f0_scale,
    cell_curves,
    cell_density,
    definition,
    spread,
    probe_rows=(),
    probe_curves=(),
):
    """``measured`` (Motor sealed native measurement) with the physics half A and its
    law gate. ``f0`` and ``nearness`` map each cell id to its f0 loss and to its
    reference distance from the limits (critical-scale units); ``condition_cells``
    lists the cell ids of each condition; ``cell_curves`` the model curve of each
    cell id."""
    if "physics" not in definition:
        return measured
    if measured["A"] is None or not f0:
        return {**measured, "gates": {**measured["gates"], GATE: False}}
    spec = physics_half.validate_block(definition["physics"])

    def benefit(ids):
        return 1.0 / (1.0 + fmean(f0[i] for i in ids) / f0_scale)

    ids = sorted(f0)
    order = sorted(ids, key=lambda i: (nearness[i], i))
    half = max(1, len(order) // 2)
    strata = [order[:half], *([order[half:]] if order[half:] else [])]
    strata += [list(cells) for cells in condition_cells]
    a_robust = min(benefit(stratum) for stratum in strata)

    means = [mean_torque(row) for row in probe_curves]
    indexed = [(i, row["record"]["probe"]) for i, row in enumerate(probe_rows)]
    up = dict(probe_design.law_pairs(indexed, "j_up"))
    zero = dict(probe_design.law_pairs(indexed, "j_zero"))

    def ratio(base, other):
        """The actual current ratio of the law row (K, or less near the range top)."""
        return float(probe_rows[other]["inputs"]["current_density_a_mm2"]) / float(
            probe_rows[base]["inputs"]["current_density_a_mm2"]
        )

    residuals = {
        "linear_in_current": [
            abs(means[up[b]] - ratio(b, up[b]) * means[b]) / spread for b in sorted(up)
        ],
        "zero_current_torque": [abs(means[zero[b]]) / spread for b in sorted(zero)],
    }
    a_law, law_record = physics_half.law_benefit(residuals)

    response = spec["response"]
    inputs = [
        [float(row["inputs"][n]) for n in response["inputs"]] for row in probe_rows
    ]
    a_response, response_record = physics_half.response_benefit(
        probe_design.groups(indexed),
        lambda i: inputs[i],
        lambda i: [means[i]],
        response,
        [spread],
    )
    invalid = a_response is None
    a, legs = physics_half.combine(
        measured["A"], a_robust, a_law, 0.0 if invalid else a_response
    )
    failed = list(response_record.get("sign_gate_failed", []))
    base_ids = {b for b, _ in probe_design.law_pairs(indexed, "j_up")}
    # Mean torque is positive wherever the current density exceeds 1 A/mm^2.
    positive = [
        mean_torque(c) > 0 for k, c in cell_curves.items() if cell_density[k] > 1.0
    ] + [means[i] > 0 for i in base_ids]
    if not all(positive):
        failed.append("mean_torque_positive")
    if invalid:
        failed.append("probe_prediction_invalid")
    return {
        **measured,
        "A": a,
        "A_legs": legs,
        "gates": {**measured["gates"], GATE: not failed},
        "physics_half": {
            **law_record,
            **response_record,
            "gate_failed_laws": sorted(failed),
        },
    }
