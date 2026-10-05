"""Motor Level-0 reconstruction recipes.

This is the learned model already registered by the public Motor baseline and
used by the frozen decision study. It is a deterministic closed-form fit on
public TRAIN; no seed, private record or reference callback affects it.
"""

from __future__ import annotations

from statistics import fmean

import numpy as np

from carbon import learned_baseline

from . import domain


class KernelRidgeModel:
    def __init__(self, records, *, length, ridge):
        x = learned_baseline.scale(
            [record["inputs"] for record in records], domain.INPUTS, domain.INPUT_BOUNDS
        )
        targets = np.asarray(
            [record["outputs"]["torque_nm"] for record in records], dtype=float
        )
        self._model = learned_baseline.KernelRidge(
            x, targets, length=length, ridge=ridge
        )

    def predict(self, inputs):
        checked = domain.check_inputs(inputs)
        curve = [
            float(value)
            for value in self._model.predict(
                learned_baseline.scale([checked], domain.INPUTS, domain.INPUT_BOUNDS)
            )[0]
        ]
        mean = fmean(curve)
        if mean < 0:
            curve = [value - mean for value in curve]
        return {"torque_nm": curve}


def build(family, settings, records):
    if family != "kernel_ridge":
        raise ValueError("unknown Motor recipe family")
    if set(settings) != {"length", "ridge"}:
        raise ValueError("Motor kernel ridge requires length and ridge")
    return KernelRidgeModel(records, length=settings["length"], ridge=settings["ridge"])
