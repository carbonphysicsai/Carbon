"""Cooling physics-half plugin (``physics_half``), laws checked on TRAIN v1 (400
references) by the Validator (VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023, "Law data").

Gates, on every graded cell and probe base: the peak is at least every profile
segment, every profile segment is at least the inlet temperature, and the
pressure drop is positive (400/400 on TRAIN).

Measured (A_law), read from private probes in units of the TRAIN spread of the
output (the units of A_acc):

- **temperatures shift with the inlet:** moving only ``inlet_c`` by ``+5 C`` moves
  the peak and every profile segment by the same 5 C;
- **pressure drop ignores the hotspot:** mirroring only the three hotspot inputs
  leaves the pressure drop unchanged.

Measured (A_response): the rise over the inlet and the pressure drop, log-log
against all nine inputs, fitted on TRAIN, with the allowance band of the fit.
Sign gates: the rise falls with flow and rises with heat load and hotspot ratio;
the pressure drop rises with flow and falls with channel width and depth.

Gross-violation margins stay unregistered (None). DEVELOPMENT only.
"""

from __future__ import annotations

import io
from statistics import fmean, pstdev

from carbon.cold_plate import domain
from carbon.scoring import physics_half, probe_design

GATE = "physics_laws"
INLET_SHIFT_C = 5.0
RISE, PRESSURE = "rise_c", "pressure_drop_pa"
LAWS = (
    ("inlet_shift_temperatures", "measured", "peak_c", None),
    ("pressure_ignores_hotspot", "measured", "pressure_drop_pa", None),
    ("peak_above_profile", "gate", "peak_c", None),
    ("profile_above_inlet", "gate", "profile_c", None),
    ("pressure_positive", "gate", "pressure_drop_pa", None),
)
SIGN_GATES = (
    (RISE, "flow_lpm_per_kw", -1),
    (RISE, "heat_load_w", 1),
    (RISE, "hotspot_ratio", 1),
    (PRESSURE, "flow_lpm_per_kw", 1),
    (PRESSURE, "channel_width_mm", -1),
    (PRESSURE, "channel_depth_mm", -1),
)
_INLET = domain.INPUTS.index("inlet_c")
_HOT = tuple(
    domain.INPUTS.index(n)
    for n in ("hotspot_ratio", "hotspot_center_mm", "hotspot_width_mm")
)
#: The probe region: the registered bounds, with the inlet low enough that the
#: shifted row stays in range.
PROBE_BOUNDS = tuple(
    (30.0, 45.0 - INLET_SHIFT_C) if n == "inlet_c" else domain.INPUT_BOUNDS[n]
    for n in domain.INPUTS
)


def probe_extra():
    def shifted(x):
        moved = list(x)
        moved[_INLET] = x[_INLET] + INLET_SHIFT_C
        return moved

    def mirrored(x):
        # Each hotspot input reflected inside its own range: unchanged flow,
        # heat load and geometry, a different hot spot.
        moved = list(x)
        for index in _HOT:
            low, high = PROBE_BOUNDS[index]
            moved[index] = low + high - x[index]
        return moved

    return (("inlet_shift", shifted), ("hotspot_mirror", mirrored))


def _train(train_raw):
    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        return (
            np.asarray(data["inputs"], dtype=float),
            np.asarray(data["targets"], dtype=float),
        )


def _responses(x, y):
    """The two responses of TRAIN rows: rise over the inlet and pressure drop."""
    return y[:, 0] - x[:, _INLET], y[:, 31]


def response_registration(train_raw):
    import numpy as np

    x, y = _train(train_raw)
    rise, pressure = _responses(x, y)
    if x.shape[1] != len(domain.INPUTS) or (rise <= 0).any() or (pressure <= 0).any():
        raise ValueError("cooling_response_train_shape")
    lx = np.log(x)
    design = np.column_stack([np.ones(len(lx)), lx])
    exponent, band = [], []
    for target in (rise, pressure):
        ly = np.log(target)
        coefficients, *_ = np.linalg.lstsq(design, ly, rcond=None)
        rmse = float(np.sqrt(np.mean((design @ coefficients - ly) ** 2)))
        exponent.append([round(float(c), 6) for c in coefficients[1:]])
        band.append([round(rmse / float(s), 6) for s in lx.std(axis=0)])
    return {
        "inputs": list(domain.INPUTS),
        "outputs": [RISE, PRESSURE],
        "exponent": exponent,
        "band": band,
        "span": [float(hi - lo) for lo, hi in PROBE_BOUNDS],
        "delta": probe_design.DELTA,
        "sign_gates": [{"output": o, "input": i, "sign": s} for o, i, s in SIGN_GATES],
    }


def registered_model(train_raw):
    """A stand-in predictor with exactly the registered sensitivities: the TRAIN
    log-log fits of the rise over the inlet and of the pressure drop, with a
    profile rising linearly to the peak. For tests and controls only; it is not a
    submitted model."""
    import numpy as np

    x, y = _train(train_raw)
    rise, pressure = _responses(x, y)
    design = np.column_stack([np.ones(len(x)), np.log(x)])
    rise_fit, *_ = np.linalg.lstsq(design, np.log(rise), rcond=None)
    pressure_fit, *_ = np.linalg.lstsq(design, np.log(pressure), rcond=None)

    def predict(point):
        row = np.concatenate([[1.0], np.log(np.asarray(point, float))])
        inlet = float(point[_INLET])
        top = float(np.exp(row @ rise_fit))
        profile = [inlet + top * (0.5 + 0.5 * k / 29.0) for k in range(30)]
        return [profile[-1], *profile, float(np.exp(row @ pressure_fit))]

    return predict


def block(train_raw):
    return physics_half.block(LAWS, response_registration(train_raw))


def spreads(train_raw):
    """TRAIN spreads of the peak temperature and the pressure drop."""
    _, y = _train(train_raw)
    return float(pstdev(y[:, 0])), float(pstdev(y[:, 31]))


def _legal(row, inlet):
    peak, profile, pressure = row[0], row[1:31], row[31]
    return {
        "peak_above_profile": peak >= max(profile),
        "profile_above_inlet": min(profile) >= inlet,
        "pressure_positive": pressure > 0,
    }


def apply(
    measured,
    *,
    cell_errors,
    nearness,
    condition_cells,
    a_scale,
    cell_rows,
    cell_outputs,
    definition,
    train_raw,
    probe_rows=(),
    probe_outputs=(),
):
    """``measured`` (Cooling sealed native measurement) with the physics half A and
    its law gate. ``cell_errors`` maps a cell id to its normalised error per
    component; ``nearness`` to its reference distance from the limits;
    ``condition_cells`` lists the cell ids of each condition."""
    if "physics" not in definition:
        return measured
    if measured["A"] is None or not cell_errors:
        return {**measured, "gates": {**measured["gates"], GATE: False}}
    spec = physics_half.validate_block(definition["physics"])

    def benefit(ids):
        return min(
            1.0 / (1.0 + fmean(cell_errors[i][c] for i in ids) / a_scale)
            for c in next(iter(cell_errors.values()))
        )

    order = sorted(cell_errors, key=lambda i: (nearness[i], i))
    half = max(1, len(order) // 2)
    strata = [order[:half], *([order[half:]] if order[half:] else [])]
    strata += [list(cells) for cells in condition_cells]
    a_robust = min(benefit(stratum) for stratum in strata)

    peak_spread, pressure_spread = spreads(train_raw)
    indexed = [(i, row["record"]["probe"]) for i, row in enumerate(probe_rows)]
    shift = dict(probe_design.law_pairs(indexed, "inlet_shift"))
    mirror = dict(probe_design.law_pairs(indexed, "hotspot_mirror"))
    outs = [[float(v) for v in row] for row in probe_outputs]
    residuals = {
        "inlet_shift_temperatures": [
            fmean(
                abs((a - b) - INLET_SHIFT_C) / peak_spread
                for a, b in zip(outs[shift[base]][:31], outs[base][:31], strict=True)
            )
            for base in sorted(shift)
        ],
        "pressure_ignores_hotspot": [
            abs(outs[mirror[base]][31] - outs[base][31]) / pressure_spread
            for base in sorted(mirror)
        ],
    }
    a_law, law_record = physics_half.law_benefit(residuals)

    response = spec["response"]
    inputs = [
        [float(row["inputs"][n]) for n in response["inputs"]] for row in probe_rows
    ]
    a_response, response_record = physics_half.response_benefit(
        probe_design.groups(indexed),
        lambda i: inputs[i],
        lambda i: [outs[i][0] - inputs[i][_INLET], outs[i][31]],
        response,
        [peak_spread, pressure_spread],
    )
    invalid = a_response is None
    a, legs = physics_half.combine(
        measured["A"], a_robust, a_law, 0.0 if invalid else a_response
    )
    failed = list(response_record.get("sign_gate_failed", []))
    rows = [
        (r["inputs"]["inlet_c"], list(map(float, o)))
        for r, o in zip(cell_rows, cell_outputs, strict=True)
    ]
    rows += [(inputs[base][_INLET], outs[base]) for base in sorted(shift)]
    for inlet, row in rows:
        failed += [name for name, ok in _legal(row, inlet).items() if not ok]
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
            "gate_failed_laws": sorted(set(failed)),
        },
    }
