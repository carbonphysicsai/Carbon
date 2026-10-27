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
        "delta_range": list(probe_design.DELTA_RANGE),
        "sign_gates": [{"output": o, "input": i, "sign": s} for o, i, s in SIGN_GATES],
    }


def block(train):
    return physics_half.block(LAWS, response_registration(train))


def local_slopes(probe_rows, peaks, input_name="on_time_s"):
    """``{str(probe base): the solver's local log-log slope of the rise over ``input_name``}`` per probe group.

    ``probe_rows`` are the bank's probe rows (inputs and ``record["probe"]``) and ``peaks`` the solver's peak at
    each; the slope is the one the response leg measures (finite difference over the +/- pair, normalised by the
    group's base rise and input), so a model equal to the solver scores zero error on that input. Custody-side:
    the peaks are truth at the sealed probes."""
    indexed = [(i, row["record"]["probe"]) for i, row in enumerate(probe_rows)]
    column = INPUTS.index(input_name)
    inputs = [[float(row["inputs"][n]) for n in INPUTS] for row in probe_rows]
    out = {}
    for group in probe_design.groups(indexed):
        plus, minus = group["dims"][column]
        base = group["base"]
        rise = float(peaks[base]) - INITIAL_C
        physics_half._require(rise > 0, "f02_local_slope_needs_a_positive_rise")
        dx = (inputs[plus][column] - inputs[minus][column]) / inputs[base][column]
        slope = ((float(peaks[plus]) - float(peaks[minus])) / rise) / dx
        out[str(indexed[base][1]["base"])] = slope
    return out


def _group_reference(definition, response, indexed):
    """The reference exponent override of a version that anchors one input's exponent on the solver's local
    slope per probe group (F02 2.5, OWNER-MOTOR-SHEET-AND-F02-EXPONENT-01), or None (the registered exponents).

    ``definition["group_response_reference"]`` is ``{"input": name, "by_base": {probe base: slope}}``, set by the
    pool material of the sealed batch (custody; never in a public file). A group with no reference is a gap of
    Carbon's, a refusal, never the registered exponent in its place."""
    reference = definition.get("group_response_reference")
    if reference is None:
        return None
    physics_half._require(
        type(reference) is dict
        and set(reference) == {"input", "by_base"}
        and reference["input"] in response["inputs"]
        and type(reference["by_base"]) is dict
        and all(
            type(k) is str and physics_half._number(v)
            for k, v in reference["by_base"].items()
        ),
        "f02_group_response_reference_malformed",
    )
    column = response["inputs"].index(reference["input"])
    base_of = {i: record["base"] for i, record in indexed}

    def override(group, _j, d, registered):
        if d != column:
            return registered
        key = str(base_of[group["base"]])
        physics_half._require(
            key in reference["by_base"], "f02_group_response_reference_missing"
        )
        return reference["by_base"][key]

    return override


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
        _group_reference(definition, response, indexed),
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
