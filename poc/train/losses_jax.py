"""JAX boolean-masked unified loss for Burgers PoC.

Boolean enables are closed over as Python bools (static) so the loss
graph does not recompile when weights change — only when the strategy
flags change (new jit). SPEC invariant: no weight-threshold masking.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

try:
    import jax.numpy as jnp

    JAX_AVAILABLE = True
except ImportError:  # pragma: no cover
    JAX_AVAILABLE = False
    jnp = None  # type: ignore

from poc.models.fno1d import FNO1dConfig
from poc.models.fno1d_jax import forward_jax


def _mse(pred, target):
    return jnp.mean((pred - target) ** 2)


def _conservation(pred, u0):
    return jnp.mean(jnp.abs(pred.mean(axis=-1) - u0.mean(axis=-1)))


def _residual_diagnostic(pred, nu):
    """Final-time Burgers residual proxy |u u_x - nu u_xx|."""
    nx = pred.shape[-1]
    k = 2 * jnp.pi * jnp.fft.fftfreq(nx, d=1.0 / nx)
    u_hat = jnp.fft.fft(pred, axis=-1)
    ux = jnp.fft.ifft(1j * k * u_hat, axis=-1).real
    uxx = jnp.fft.ifft(-(k**2) * u_hat, axis=-1).real
    nu_b = nu.reshape(-1, 1)
    r = pred * ux - nu_b * uxx
    return jnp.mean(jnp.abs(r))


def make_loss_fn(cfg: FNO1dConfig, loss_cfg: Dict[str, Any]) -> Callable:
    """Build a scalar loss_fn(params, u0, uT, nu) closed over strategy flags."""
    if not JAX_AVAILABLE:
        raise ImportError("jax required for make_loss_fn")

    en_data = bool(loss_cfg.get("data_mse", True))
    en_phys = bool(loss_cfg.get("physics_residual", False))
    en_cons = bool(loss_cfg.get("conservation_penalty", False))
    w_data = float(loss_cfg.get("data_mse_weight", 1.0))
    w_phys = float(loss_cfg.get("physics_residual_weight", 0.1))
    w_cons = float(loss_cfg.get("conservation_penalty_weight", 0.05))

    def loss_fn(params, u0, uT, nu):
        pred = forward_jax(params, u0, cfg)
        total = 0.0
        if en_data:
            total = total + w_data * _mse(pred, uT)
        if en_phys:
            total = total + w_phys * _residual_diagnostic(pred, nu)
        if en_cons:
            total = total + w_cons * _conservation(pred, u0)
        # If all disabled (broken fixture), still return a constant so grads are 0
        if not (en_data or en_phys or en_cons):
            total = total + 0.0 * jnp.mean(pred)
        return total

    return loss_fn
