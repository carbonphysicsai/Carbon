"""Boolean-masked unified loss for Burgers PoC (SPEC invariant)."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np


def mse(pred: np.ndarray, target: np.ndarray) -> float:
    return float(np.mean((pred - target) ** 2))


def conservation_error(pred: np.ndarray, u0: np.ndarray) -> float:
    """Periodic mass proxy: |mean(u_T) - mean(u_0)| averaged over batch."""
    return float(np.mean(np.abs(pred.mean(axis=-1) - u0.mean(axis=-1))))


def residual_diagnostic(pred: np.ndarray, u0: np.ndarray, nu: np.ndarray) -> float:
    """Cheap Burgers residual proxy at final time using spatial operators on pred.

    residual ≈ mean | u * u_x - nu * u_xx | evaluated on predicted field.
    Not a full spacetime residual; documented PoC diagnostic (appendix §7).
    """
    # spectral derivatives
    nx = pred.shape[-1]
    k = 2 * np.pi * np.fft.fftfreq(nx, d=1.0 / nx)
    u_hat = np.fft.fft(pred, axis=-1)
    ux = np.fft.ifft(1j * k * u_hat, axis=-1).real
    uxx = np.fft.ifft(-(k**2) * u_hat, axis=-1).real
    nu_b = nu.reshape(-1, 1)
    r = pred * ux - nu_b * uxx
    return float(np.mean(np.abs(r)))


def unified_loss(
    pred: np.ndarray,
    target: np.ndarray,
    u0: np.ndarray,
    nu: np.ndarray,
    loss_cfg: Dict,
) -> Tuple[float, Dict[str, float]]:
    """L = Σ 1_term * w_term * term_loss  with explicit boolean enables."""
    parts: Dict[str, float] = {}
    total = 0.0

    if loss_cfg.get("data_mse", True):
        w = float(loss_cfg.get("data_mse_weight", 1.0))
        v = mse(pred, target)
        parts["data_mse"] = v
        total += w * v

    if loss_cfg.get("physics_residual", False):
        w = float(loss_cfg.get("physics_residual_weight", 0.1))
        v = residual_diagnostic(pred, u0, nu)
        parts["physics_residual"] = v
        total += w * v

    if loss_cfg.get("conservation_penalty", False):
        w = float(loss_cfg.get("conservation_penalty_weight", 0.05))
        v = conservation_error(pred, u0)
        parts["conservation_penalty"] = v
        total += w * v

    parts["total"] = total
    return total, parts
