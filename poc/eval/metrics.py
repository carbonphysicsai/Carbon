"""Evaluation metrics for Burgers PoC — physics diagnostics in fp32."""

from __future__ import annotations

from typing import Dict

import numpy as np

from poc.models.fno1d import FNO1dConfig, forward
from poc.train.losses import conservation_error, residual_diagnostic
from poc.generators.burgers1d import BurgersBatch
from poc.eval.fp32_context import physics_fp32_context, as_fp32


def relative_l2(pred: np.ndarray, target: np.ndarray) -> float:
    num = np.linalg.norm(pred - target)
    den = np.linalg.norm(target) + 1e-12
    return float(num / den)


def evaluate(
    params: dict,
    cfg: FNO1dConfig,
    batch: BurgersBatch,
) -> Dict[str, float]:
    """Forward + physics metrics under fp32 gate context."""
    with physics_fp32_context():
        pred = forward(params, batch.u0, cfg)
        pred32, u0_32, uT_32, nu_32 = as_fp32(pred, batch.u0, batch.uT, batch.nu)
        return {
            "rel_l2": relative_l2(pred32, uT_32),
            "mse": float(np.mean((pred32 - uT_32) ** 2)),
            "residual_mean": residual_diagnostic(pred32, u0_32, nu_32),
            "conservation_error": conservation_error(pred32, u0_32),
            "finite_ok": float(np.isfinite(pred32).all()),
            "pred": pred32,
            "precision": "fp32",
        }
