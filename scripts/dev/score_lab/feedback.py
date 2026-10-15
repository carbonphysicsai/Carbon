"""Synthetic disclosed-score hill climb; value is measured only afterward.

The search receives a public score callback, never references or value-side
questions. All parameter and feedback settings are diagnostic assumptions.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

from .core import LabRefused


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def climb(
    public_score: Callable[[Mapping[str, float], str], float],
    *,
    initial: Mapping[str, float],
    bounds: Mapping[str, tuple[float, float]],
    step: Mapping[str, float],
    grain: str,
    decimals: int,
    probes_per_epoch: int,
    epochs: int,
):
    """Maximise only the disclosed rounded score under a fixed probe budget.

    Ties retain the prior parameters. Coordinate proposals rotate so a narrow
    per-epoch probe budget does not permanently omit later parameters.
    """
    if (
        not isinstance(grain, str)
        or not grain
        or type(decimals) is not int
        or not 0 <= decimals <= 12
        or type(probes_per_epoch) is not int
        or probes_per_epoch < 1
        or type(epochs) is not int
        or epochs < 1
        or not isinstance(initial, Mapping)
        or not initial
        or not isinstance(bounds, Mapping)
        or not isinstance(step, Mapping)
        or any(not isinstance(name, str) or not name for name in initial)
        or set(initial) != set(bounds)
        or set(initial) != set(step)
    ):
        raise LabRefused("feedback_configuration")
    names = sorted(initial)
    for name in names:
        pair = bounds[name]
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise LabRefused("feedback_parameter_bounds")
        low, high = pair
        if (
            not all(_finite(x) for x in (initial[name], low, high, step[name]))
            or not low < high
            or not low <= initial[name] <= high
            or step[name] <= 0
        ):
            raise LabRefused("feedback_parameter_bounds")

    calls = 0

    def disclosed(parameters):
        nonlocal calls
        raw = public_score(dict(parameters), grain)
        if not _finite(raw):
            raise LabRefused("feedback_score_nonfinite")
        calls += 1
        return round(float(raw), decimals)

    current = dict(initial)
    first = disclosed(current)
    visible = first
    trace = []
    proposals = [(name, sign) for name in names for sign in (-1, 1)]
    for epoch in range(epochs):
        tested = 0
        # Rotate the fixed proposal list; each epoch sees at most the posted
        # number of probes, regardless of ties or boundary-clipped proposals.
        offset = (epoch * probes_per_epoch) % len(proposals)
        for i in range(probes_per_epoch):
            name, sign = proposals[(offset + i) % len(proposals)]
            low, high = bounds[name]
            candidate = dict(current)
            candidate[name] = min(high, max(low, current[name] + sign * step[name]))
            shown = disclosed(candidate)
            tested += 1
            if shown > visible:
                current, visible = candidate, shown
        trace.append({"epoch": epoch + 1, "probes": tested, "disclosed_score": visible})
    return {
        "schema": "carbon.dev.score-lab-feedback-gamer.v1",
        "grain": grain,
        "rounding_decimals": decimals,
        "probes_per_epoch": probes_per_epoch,
        "epochs": epochs,
        "calls": calls,
        "initial_score": first,
        "final_score": visible,
        "initial_parameters": dict(initial),
        "final_parameters": current,
        "trace": trace,
    }


def add_value_outcome(result, value_loss: Callable[[Mapping[str, float]], float]):
    """Measure value after search; this callable never enters `climb`."""
    start = value_loss(result["initial_parameters"])
    end = value_loss(result["final_parameters"])
    if not _finite(start) or not _finite(end):
        raise LabRefused("feedback_value_nonfinite")
    return {
        **result,
        "initial_value_loss": float(start),
        "final_value_loss": float(end),
        "score_gain": result["final_score"] - result["initial_score"],
        "value_gain": float(start) - float(end),
    }


def sweep(
    public_score,
    value_loss,
    *,
    initial,
    bounds,
    step,
    grains,
    roundings,
    probe_allowances,
    epochs,
):
    """Report score and later value gains at every declared disclosure setting."""
    if (
        not isinstance(grains, (tuple, list))
        or not grains
        or not isinstance(roundings, (tuple, list))
        or not roundings
        or not isinstance(probe_allowances, (tuple, list))
        or not probe_allowances
    ):
        raise LabRefused("feedback_sweep_empty")
    return [
        add_value_outcome(
            climb(
                public_score,
                initial=initial,
                bounds=bounds,
                step=step,
                grain=grain,
                decimals=decimals,
                probes_per_epoch=probes,
                epochs=epochs,
            ),
            value_loss,
        )
        for grain in grains
        for decimals in roundings
        for probes in probe_allowances
    ]
