"""Budget-capped training loop for FNO-1d PoC.

Preferred path: JAX + Adam over *all* FNO parameters (real training).
Fallback: NumPy finite-difference on lift/proj only — PROTOCOL ONLY.
  numpy_fd must never be used as evidence of train quality.

Batch sampling is seeded so fixed init_seed → reproducible trajectories (T5).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

import numpy as np

from poc.models.fno1d import FNO1dConfig, forward, init_params
from poc.train.losses import unified_loss
from poc.generators.burgers1d import BurgersBatch

try:
    import jax
    import jax.numpy as jnp

    from poc.models.fno1d_jax import init_params_jax, params_to_numpy
    from poc.train.losses_jax import make_loss_fn

    JAX_AVAILABLE = True
except ImportError:  # pragma: no cover
    JAX_AVAILABLE = False


def _clamp_strategy(strategy: dict, limits: dict) -> dict:
    cfg = strategy["backbone_cfg"]
    cfg["modes"] = int(min(cfg["modes"], limits["max_modes"]))
    cfg["width"] = int(min(cfg["width"], limits["max_width"]))
    cfg["layers"] = int(min(cfg["layers"], limits["max_layers"]))
    strategy["backbone_cfg"] = cfg

    lr = float(strategy["optim"]["lr"])
    lr = max(limits["lr_min"], min(limits["lr_max"], lr))
    strategy["optim"]["lr"] = lr

    steps = int(min(strategy["budget"]["max_steps"], limits["max_steps"]))
    bs = int(min(strategy["budget"]["batch_size"], limits["max_batch_size"]))
    strategy["budget"]["max_steps"] = steps
    strategy["budget"]["batch_size"] = bs
    return strategy


def _clip_grads_numpy(grads: Dict[str, np.ndarray], max_norm: float = 1.0) -> Dict[str, np.ndarray]:
    total = 0.0
    for g in grads.values():
        total += float(np.sum(g.astype(np.float64) ** 2))
    norm = np.sqrt(total) + 1e-12
    scale = min(1.0, max_norm / norm)
    return {k: (v * scale).astype(v.dtype) for k, v in grads.items()}


def _train_jax(
    strategy: dict,
    train_batch: BurgersBatch,
    limits: dict,
    init_seed: int,
    cfg: FNO1dConfig,
) -> Tuple[Dict[str, np.ndarray], FNO1dConfig, Dict[str, Any]]:
    """Full-parameter Adam via jax.grad. This is the only train-quality path."""
    try:
        jax.config.update("jax_default_prng_impl", "threefry")
    except Exception:
        pass

    params = init_params_jax(cfg, seed=init_seed)
    loss_fn = make_loss_fn(cfg, strategy["loss"])
    grad_fn = jax.jit(jax.grad(loss_fn))
    value_fn = jax.jit(loss_fn)

    lr = float(strategy["optim"]["lr"])
    # Adam is more reliable than SGD for short FNO budgets
    beta1 = 0.9
    beta2 = 0.999
    eps = 1e-8
    max_steps = int(strategy["budget"]["max_steps"])
    batch_size = int(strategy["budget"]["batch_size"])
    n = train_batch.u0.shape[0]
    clip = float(limits.get("grad_clip", 1.0))

    u0_all = jnp.asarray(train_batch.u0)
    uT_all = jnp.asarray(train_batch.uT)
    nu_all = jnp.asarray(train_batch.nu)

    # Adam state
    m = jax.tree_util.tree_map(jnp.zeros_like, params)
    v = jax.tree_util.tree_map(jnp.zeros_like, params)

    rng = np.random.default_rng(int(init_seed) % (2**32))
    t0 = time.time()
    first_loss = None
    last_loss = 0.0
    steps_run = 0
    use_full = n <= batch_size

    for step in range(max_steps):
        steps_run = step + 1
        t = step + 1  # Adam timestep (1-indexed)

        if use_full:
            idx = np.arange(n)
        else:
            idx = rng.integers(0, n, size=batch_size)
        u0 = u0_all[idx]
        uT = uT_all[idx]
        nu = nu_all[idx]

        if first_loss is None:
            first_loss = float(value_fn(params, u0, uT, nu))

        grads = grad_fn(params, u0, uT, nu)
        grads = jax.tree_util.tree_map(
            lambda g: jnp.nan_to_num(g, nan=0.0, posinf=0.0, neginf=0.0), grads
        )

        # Global norm clip
        leaves = jax.tree_util.tree_leaves(grads)
        sq = sum(jnp.sum(g**2) for g in leaves)
        norm = jnp.sqrt(sq) + 1e-12
        scale = jnp.minimum(1.0, clip / norm)
        grads = jax.tree_util.tree_map(lambda g: g * scale, grads)

        # Adam update
        m = jax.tree_util.tree_map(lambda mi, g: beta1 * mi + (1.0 - beta1) * g, m, grads)
        v = jax.tree_util.tree_map(
            lambda vi, g: beta2 * vi + (1.0 - beta2) * (g * g), v, grads
        )
        mhat = jax.tree_util.tree_map(lambda mi: mi / (1.0 - beta1**t), m)
        vhat = jax.tree_util.tree_map(lambda vi: vi / (1.0 - beta2**t), v)
        params = jax.tree_util.tree_map(
            lambda p, mh, vh: p - lr * mh / (jnp.sqrt(vh) + eps), params, mhat, vhat
        )

        last_loss = float(value_fn(params, u0, uT, nu))

        if time.time() - t0 > limits.get("max_wall_s", 600):
            break

    if first_loss is None:
        first_loss = last_loss

    # Real learning signal: loss must drop materially
    loss_ratio = (last_loss / first_loss) if first_loss > 1e-12 else 1.0
    loss_improved = bool(last_loss < first_loss * 0.95)  # ≥5% drop

    wall_s = time.time() - t0
    device = "gpu" if any("gpu" in str(d).lower() for d in jax.devices()) else "cpu"
    info = {
        "steps": steps_run,
        "wall_s": wall_s,
        "first_loss": float(first_loss),
        "last_loss": float(last_loss),
        "loss_ratio": float(loss_ratio),
        "loss_improved": loss_improved,
        "train_quality_claimable": loss_improved,  # only jax path can set True
        "device": device,
        "init_seed": int(init_seed),
        "backend": "jax",
        "optimizer": "adam",
        "full_batch": use_full,
    }
    return params_to_numpy(params), cfg, info


def _train_numpy_fd(
    strategy: dict,
    train_batch: BurgersBatch,
    limits: dict,
    init_seed: int,
    cfg: FNO1dConfig,
) -> Tuple[Dict[str, np.ndarray], FNO1dConfig, Dict[str, Any]]:
    """PROTOCOL-ONLY fallback. Does NOT claim train quality.

    FD on lift/proj only — insufficient for Burgers FNO learning.
    Use for schema/gates/card wiring tests when jax is absent.
    """
    params = init_params(cfg, seed=init_seed)
    rng = np.random.default_rng(int(init_seed) % (2**32))

    lr = float(strategy["optim"]["lr"])
    max_steps = int(strategy["budget"]["max_steps"])
    batch_size = int(strategy["budget"]["batch_size"])
    loss_cfg = strategy["loss"]
    n = train_batch.u0.shape[0]
    t0 = time.time()
    first_loss = None
    last_loss = 0.0
    eps = 1e-4
    train_keys = ["lift_w", "lift_b", "proj_w", "proj_b"]
    use_full = n <= batch_size

    steps_run = 0
    for step in range(max_steps):
        steps_run = step + 1
        if use_full:
            idx = np.arange(n)
        else:
            idx = rng.integers(0, n, size=min(batch_size, n))
        u0 = train_batch.u0[idx]
        uT = train_batch.uT[idx]
        nu = train_batch.nu[idx]

        pred = forward(params, u0, cfg)
        loss, _ = unified_loss(pred, uT, u0, nu, loss_cfg)
        if first_loss is None:
            first_loss = loss
        last_loss = loss

        grads: Dict[str, np.ndarray] = {}
        for key in train_keys:
            g = np.zeros_like(params[key])
            flat = params[key].ravel()
            g_flat = g.ravel()
            n_coords = min(16, flat.size)
            coords = np.linspace(0, flat.size - 1, n_coords, dtype=int)
            for c in coords:
                orig = flat[c]
                flat[c] = orig + eps
                params[key] = flat.reshape(params[key].shape)
                pred_p = forward(params, u0, cfg)
                loss_p, _ = unified_loss(pred_p, uT, u0, nu, loss_cfg)
                flat[c] = orig - eps
                params[key] = flat.reshape(params[key].shape)
                pred_m = forward(params, u0, cfg)
                loss_m, _ = unified_loss(pred_m, uT, u0, nu, loss_cfg)
                g_flat[c] = (loss_p - loss_m) / (2 * eps)
                flat[c] = orig
                params[key] = flat.reshape(params[key].shape)
            grads[key] = g

        grads = _clip_grads_numpy(grads, max_norm=1.0)
        for key in train_keys:
            params[key] = params[key] - lr * grads[key]

        if time.time() - t0 > limits.get("max_wall_s", 600):
            break

    if first_loss is None:
        first_loss = last_loss

    wall_s = time.time() - t0
    info = {
        "steps": steps_run,
        "wall_s": wall_s,
        "first_loss": float(first_loss),
        "last_loss": float(last_loss),
        "loss_ratio": float(last_loss / first_loss) if first_loss > 1e-12 else 1.0,
        "loss_improved": False,  # never claim on FD path
        "train_quality_claimable": False,  # HARD RULE
        "device": "cpu",
        "init_seed": int(init_seed),
        "backend": "numpy_fd",
        "optimizer": "fd_sgd_lift_proj_only",
        "full_batch": use_full,
        "note": "PROTOCOL_ONLY — not train-quality evidence",
    }
    return params, cfg, info


def train(
    strategy: dict,
    train_batch: BurgersBatch,
    limits: dict,
    init_seed: int = 0,
    prefer_jax: bool = True,
) -> Tuple[Dict[str, np.ndarray], FNO1dConfig, Dict[str, Any]]:
    """Train under strategy budget. JAX Adam if available, else NumPy FD protocol-only."""
    strategy = _clamp_strategy(dict(strategy), limits)
    cfg = FNO1dConfig(
        modes=int(strategy["backbone_cfg"]["modes"]),
        width=int(strategy["backbone_cfg"]["width"]),
        layers=int(strategy["backbone_cfg"]["layers"]),
    )

    if prefer_jax and JAX_AVAILABLE:
        return _train_jax(strategy, train_batch, limits, init_seed, cfg)
    return _train_numpy_fd(strategy, train_batch, limits, init_seed, cfg)
