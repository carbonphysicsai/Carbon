"""JAX FNO-1d — preferred train path when jax is installed.

All spectral + local weights are trainable (unlike the NumPy FD subset).
Params are plain pytrees (dicts of arrays) for optax/jax.grad.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from poc.models.fno1d import FNO1dConfig, init_params as init_params_numpy

try:
    import jax
    import jax.numpy as jnp

    JAX_AVAILABLE = True
except ImportError:  # pragma: no cover
    JAX_AVAILABLE = False
    jax = None  # type: ignore
    jnp = None  # type: ignore


def init_params_jax(cfg: FNO1dConfig, seed: int = 0) -> Dict[str, Any]:
    """Initialize as NumPy then device_put for a stable seed path."""
    if not JAX_AVAILABLE:
        raise ImportError("jax is required for init_params_jax")
    np_params = init_params_numpy(cfg, seed=seed)
    return {k: jnp.asarray(v) for k, v in np_params.items()}


def params_to_numpy(params: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Convert JAX pytree → NumPy for shared eval path."""
    out = {}
    for k, v in params.items():
        if hasattr(v, "__array__"):
            out[k] = np.asarray(v)
        else:
            out[k] = v
    return out


def _spectral_conv_jax(x, wr, wi, modes: int):
    """x: (B, nx, width); wr/wi: (width, width, modes)."""
    B, nx, width = x.shape
    x_ft = jnp.fft.rfft(x, axis=1)  # (B, nfreq, width)
    m = min(modes, x_ft.shape[1])

    xk = x_ft[:, :m, :]  # (B, m, width)
    # wk: (width, width, m) → contract over in-channels
    # out[b, k, o] = sum_i xk[b, k, i] * wk[o, i, k]
    wr_m = wr[:, :, :m]  # (width_out, width_in, m)
    wi_m = wi[:, :, :m]
    # einsum: b m i, o i m -> b m o
    out_r = jnp.einsum("bmi,oim->bmo", xk.real, wr_m) - jnp.einsum(
        "bmi,oim->bmo", xk.imag, wi_m
    )
    out_i = jnp.einsum("bmi,oim->bmo", xk.real, wi_m) + jnp.einsum(
        "bmi,oim->bmo", xk.imag, wr_m
    )
    out_modes = out_r + 1j * out_i

    nfreq = x_ft.shape[1]
    out_ft = jnp.zeros((B, nfreq, width), dtype=x_ft.dtype)
    out_ft = out_ft.at[:, :m, :].set(out_modes)
    return jnp.fft.irfft(out_ft, n=nx, axis=1).real


def forward_jax(params: Dict[str, Any], u0, cfg: FNO1dConfig):
    """u0: (B, nx) → pred (B, nx)."""
    x = u0[..., None]
    x = x @ params["lift_w"] + params["lift_b"]
    for i in range(cfg.layers):
        s = _spectral_conv_jax(
            x,
            params[f"spec_real_{i}"],
            params[f"spec_imag_{i}"],
            cfg.modes,
        )
        local = x @ params[f"w_{i}"] + params[f"b_{i}"]
        x = jnp.tanh(s + local)
    y = x @ params["proj_w"] + params["proj_b"]
    return y[..., 0]
