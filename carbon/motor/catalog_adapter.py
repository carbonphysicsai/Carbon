"""Motor's interface as the backbone catalog sees it (OWNER-BACKBONE-CATALOG-01).

The eight registered inputs are scaled to [-1, 1] by their bounds (the kernel
ridge's scaling) and the output is the torque at the `ANGLE_STEPS` angles of
one period. 2-D-only backbones read the 60 angles as a 6 x 10 grid. The
catalog's loop standardizes the curve per angle over TRAIN.

Nothing here chooses a measurement or a threshold: predictions are returned
as they are, for Motor's own practice and exam scoring.
"""

from __future__ import annotations

import numpy as np

from carbon import learned_baseline

from . import domain

GRID_2D = (6, 10)


def shape():
    from carbon.backbone_catalog.torch_backbones import Shape

    return Shape(len(domain.INPUTS), domain.ANGLE_STEPS, GRID_2D)


def scaled(cases):
    return np.asarray(
        learned_baseline.scale(
            [domain.check_inputs(case) for case in cases],
            domain.INPUTS,
            domain.INPUT_BOUNDS,
        ),
        dtype=np.float64,
    )


class CatalogModel:
    """A trained catalog entry answering Motor's `predict(inputs)`."""

    def __init__(self, fitted, record):
        self.fitted, self.record = fitted, record

    def predict(self, inputs):
        curve = self.fitted.predict(scaled([inputs]))[0]
        return {"torque_nm": [float(value) for value in curve]}

    def predict_many(self, cases):
        return [
            {"torque_nm": [float(v) for v in row]}
            for row in self.fitted.predict(scaled(cases))
        ]


def fit(catalog_id, settings, records, *, seed):
    """Train `catalog_id` on Motor's public TRAIN `records` with Carbon's seed."""
    from carbon.backbone_catalog import torch_loop

    x = scaled([record["inputs"] for record in records])
    y = np.asarray(
        [record["outputs"]["torque_nm"] for record in records], dtype=np.float64
    )
    fitted, record = torch_loop.fit(
        catalog_id, settings, x, y, seed=seed, shape=shape()
    )
    return CatalogModel(fitted, record)
