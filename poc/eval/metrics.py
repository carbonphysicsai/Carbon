"""Evaluation metrics for Burgers PoC."""

from __future__ import annotations

from typing import Dict

import numpy as np

from poc.models.fno1d import FNO1dConfig, forward
from poc.train.losses import conservation_error, residual_diagnostic
from poc.generators.burgers1d import BurgersBatch


def relative_l2(pred: np.ndarray, target: np.ndarray) -> float:
    num = np.linalg.norm(pred - target)
    den = np.linalg.norm(target) + 1e-12
    return float(num / den)


def evaluate(
    params: dict,
    cfg: FNO1dConfig,
    batch: BurgersBatch,
) -> Dict[str, float]:
    pred = forward(params, batch.u0, cfg)
    return {
        "rel_l2": relative_l2(pred, batch.uT),
        "mse": float(np.mean((pred - batch.uT) ** 2)),
        "residual_mean": residual_diagnostic(pred, batch.u0, batch.nu),
        "conservation_error": conservation_error(pred, batch.u0),
        "finite_ok": float(np.isfinite(pred).all()),
        "pred": pred,  # caller may drop
    }
