"""Minimal FNO-1d for Burgers PoC.

Primary path: pure NumPy forward + finite-difference parameter updates via
a tiny autograd-free training loop (see train/loop.py) using analytic
gradients approximated by a simple spectral MLP-style FNO.

When JAX is available, a JAX implementation is preferred (train/loop.py).
This module provides a portable NumPy FNO used for CPU CI and as reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


@dataclass
class FNO1dConfig:
    modes: int = 16
    width: int = 32
    layers: int = 4


def _glorot(rng: np.random.Generator, shape: Tuple[int, ...]) -> np.ndarray:
    fan_in = shape[0] if len(shape) > 1 else 1
    scale = np.sqrt(2.0 / max(fan_in, 1))
    return (rng.standard_normal(shape) * scale).astype(np.float32)


def init_params(cfg: FNO1dConfig, seed: int = 0) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    p: Dict[str, np.ndarray] = {}
    # Lift: 1 → width
    p["lift_w"] = _glorot(rng, (1, cfg.width))
    p["lift_b"] = np.zeros((cfg.width,), dtype=np.float32)
    for i in range(cfg.layers):
        # Spectral weights for positive modes: (width, width, modes)
        p[f"spec_real_{i}"] = _glorot(rng, (cfg.width, cfg.width, cfg.modes))
        p[f"spec_imag_{i}"] = _glorot(rng, (cfg.width, cfg.width, cfg.modes))
        p[f"w_{i}"] = _glorot(rng, (cfg.width, cfg.width))
        p[f"b_{i}"] = np.zeros((cfg.width,), dtype=np.float32)
    # Project: width → 1
    p["proj_w"] = _glorot(rng, (cfg.width, 1))
    p["proj_b"] = np.zeros((1,), dtype=np.float32)
    return p


def _spectral_conv(x: np.ndarray, wr: np.ndarray, wi: np.ndarray, modes: int) -> np.ndarray:
    """x: (B, nx, width) → (B, nx, width)."""
    B, nx, width = x.shape
    x_ft = np.fft.rfft(x, axis=1)  # (B, nx//2+1, width)
    out_ft = np.zeros_like(x_ft)
    m = min(modes, x_ft.shape[1])
    # Complex multiply over channels for retained modes
    for k in range(m):
        # (B, width) @ (width, width) complex
        xk = x_ft[:, k, :]  # (B, width)
        wk = wr[:, :, k] + 1j * wi[:, :, k]  # (width, width)
        out_ft[:, k, :] = xk @ wk.T
    return np.fft.irfft(out_ft, n=nx, axis=1).real.astype(np.float32)


def forward(params: Dict[str, np.ndarray], u0: np.ndarray, cfg: FNO1dConfig) -> np.ndarray:
    """u0: (B, nx) → pred uT: (B, nx)."""
    B, nx = u0.shape
    x = u0[..., None]  # (B, nx, 1)
    x = x @ params["lift_w"] + params["lift_b"]  # (B, nx, width)
    for i in range(cfg.layers):
        s = _spectral_conv(
            x,
            params[f"spec_real_{i}"],
            params[f"spec_imag_{i}"],
            cfg.modes,
        )
        # Local linear + residual + GELU-ish (tanh approx for portability)
        local = x @ params[f"w_{i}"] + params[f"b_{i}"]
        x = np.tanh(s + local)
    y = x @ params["proj_w"] + params["proj_b"]  # (B, nx, 1)
    return y[..., 0].astype(np.float32)
