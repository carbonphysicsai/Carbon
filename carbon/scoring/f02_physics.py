"""F02 physics-half plugin (``physics_half``), laws checked on TRAIN40 v2 by the
Validator (VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023, "Law data").

- **Gate:** the peak is at least the initial temperature (40 C), on every graded
  cell and probe (40/40 on TRAIN).
- **Measured (A_law):** linear superposition in the source, so the peak is affine
  in power at a fixed on-time. The probe second difference
  ``y(P+h) - 2 y(P) + y(P-h)`` (h = 10% of the power span) is the residual, in
  units of the TRAIN peak spread (6.701 C) so it sits with A_acc.
- **Measured (A_response):** the rise over the initial temperature, log-log, against
  power and on-time, fitted on TRAIN; **sign gates:** the peak rises with power and
  with on-time.

The gross-violation margins stay unregistered (None), so the measured law does not
gate. DEVELOPMENT only.
"""

from __future__ import annotations

from carbon.scoring import physics_half, probe_design

GATE = "physics_laws"
INITIAL_C = 40.0
INPUTS = ("peak_w", "on_time_s")
OUTPUT = "rise_c"
LAWS = (
    ("affine_in_power", "measured", "peak_top_c", None),
    ("peak_not_below_initial", "gate", "peak_top_c", None),
)
SIGN_GATES = ((OUTPUT, "peak_w", 1), (OUTPUT, "on_time_s", 1))
BOUNDS = ((70.0, 100.0), (4.0, 6.0))


def response_registration(train):
    """The registered sensitivities from the public TRAIN (``train``: the
    ``f02_train.load_public_train`` document)."""
    import numpy as np

    x = np.asarray(train["inputs"], dtype=float)
    y = np.asarray(train["targets"], dtype=float)[:, 0] - INITIAL_C
    if x.shape[1] != 2 or (y <= 0).any():
        raise ValueError("f02_response_train_shape")
    lx = np.log(x)
    design = np.column_stack([np.ones(len(lx)), lx])
    coefficients, *_ = np.linalg.lstsq(design, np.log(y), rcond=None)
    rmse = float(np.sqrt(np.mean((design @ coefficients - np.log(y)) ** 2)))
    spread = lx.std(axis=0)
    return {
        "inputs": list(INPUTS),
        "outputs": [OUTPUT],
        "exponent": [[round(float(coefficients[1 + i]), 6) for i in range(2)]],
        "band": [[round(rmse / float(spread[i]), 6) for i in range(2)]],
        "span": [float(hi - lo) for lo, hi in BOUNDS],
        "delta": probe_design.DELTA,
        "sign_gates": [{"output": o, "input": i, "sign": s} for o, i, s in SIGN_GATES],
    }


def block(train):
    return physics_half.block(LAWS, response_registration(train))


def apply(
    measured,
    *,
    bank_rows,
    outputs,
    definition,
    train_std,
    constraints,
    probe_rows=(),
    probe_outputs=(),
):
    """``measured`` (F02 native measurement) with the physics half A and its law
    gate. ``outputs``/``probe_outputs`` are rows of one value (the peak)."""
    if "physics" not in definition:
        return measured
    if measured["A"] is None:
        return {**measured, "gates": {**measured["gates"], GATE: False}}
    spec = physics_half.validate_block(definition["physics"])
    peaks = [float(row[0]) for row in outputs]
    references = [float(r["reference"][0]) for r in bank_rows]
    errors = [[abs(p - r) / train_std] for p, r in zip(peaks, references, strict=True)]
    nearness = [abs(constraints["maximum_c"] - r) for r in references]
    a_robust = physics_half.robust_benefit(
        errors, physics_half.split_by_nearness(nearness)
    )

    probes = [float(row[0]) for row in probe_outputs]
    indexed = [(i, row["record"]["probe"]) for i, row in enumerate(probe_rows)]
    up = dict(probe_design.law_pairs(indexed, "affine_up"))
    down = dict(probe_design.law_pairs(indexed, "affine_down"))
    residuals = {
        "affine_in_power": [
            abs(probes[up[b]] - 2 * probes[b] + probes[down[b]]) / train_std
            for b in sorted(up)
        ]
    }
    a_law, law_record = physics_half.law_benefit(residuals)

    response = spec["response"]
    inputs = [
        [float(row["inputs"][n]) for n in response["inputs"]] for row in probe_rows
    ]
    groups = probe_design.groups(indexed)
    a_response, response_record = physics_half.response_benefit(
        groups,
        lambda i: inputs[i],
        lambda i: [probes[i] - INITIAL_C],
        response,
        [train_std],
    )
    invalid = a_response is None
    a, legs = physics_half.combine(
        measured["A"], a_robust, a_law, 0.0 if invalid else a_response
    )
    failed = []
    if any(p < INITIAL_C for p in [*peaks, *probes]):
        failed.append("peak_not_below_initial")
    failed += response_record.get("sign_gate_failed", [])
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


__all__ = ["GATE", "apply", "block"]
