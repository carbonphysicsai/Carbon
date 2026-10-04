"""Cold-plate Level-0 reconstruction recipes.

This is the learned model already used by the frozen decision study, lifted
into a reusable construction path.  It is a deterministic closed-form fit on
public TRAIN; no seed, private record or reference callback affects it.
"""

from __future__ import annotations

import math

import numpy as np

from carbon import learned_baseline

from . import domain


def targets(records):
    """The decision study's log-rise/log-pressure target representation."""

    values = []
    for record in records:
        inlet = record["inputs"]["inlet_c"]
        outputs = record["outputs"]
        values.append(
            [math.log(outputs["peak_c"] - inlet)]
            + [math.log(value - inlet) for value in outputs["profile_c"]]
            + [math.log(outputs["pressure_drop_pa"])]
        )
    return np.asarray(values, dtype=float)


class KernelRidgeModel:
    def __init__(self, records, *, length, ridge):
        x = learned_baseline.scale(
            [record["inputs"] for record in records], domain.INPUTS, domain.INPUT_BOUNDS
        )
        self._model = learned_baseline.KernelRidge(
            x, targets(records), length=length, ridge=ridge
        )

    def predict(self, inputs):
        checked = domain.check_inputs(inputs)
        values = self._model.predict(
            learned_baseline.scale([checked], domain.INPUTS, domain.INPUT_BOUNDS)
        )[0]
        inlet = checked["inlet_c"]
        profile = [inlet + math.exp(value) for value in values[1:-1]]
        return {
            "peak_c": max(inlet + math.exp(values[0]), max(profile)),
            "profile_c": profile,
            "pressure_drop_pa": math.exp(values[-1]),
        }


def build(family, settings, records):
    if family != "kernel_ridge":
        raise ValueError("unknown cold-plate recipe family")
    if set(settings) != {"length", "ridge"}:
        raise ValueError("cold-plate kernel ridge requires length and ridge")
    return KernelRidgeModel(records, length=settings["length"], ridge=settings["ridge"])
