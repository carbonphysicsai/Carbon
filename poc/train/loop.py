"""Budget-capped training loop for FNO-1d PoC.

Uses finite-difference parameter gradients for portability (CPU CI).
Batch sampling is driven by a seeded Generator so fixed init_seed →
reproducible trajectories (acceptance test T5).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

import numpy as np

from poc.models.fno1d import FNO1dConfig, forward, init_params
from poc.train.losses import unified_loss
from poc.generators.burgers1d import BurgersBatch


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


def train(
    strategy: dict,
    train_batch: BurgersBatch,
    limits: dict,
    init_seed: int = 0,
) -> Tuple[Dict[str, np.ndarray], FNO1dConfig, Dict[str, Any]]:
    strategy = _clamp_strategy(dict(strategy), limits)
    cfg = FNO1dConfig(
        modes=int(strategy["backbone_cfg"]["modes"]),
        width=int(strategy["backbone_cfg"]["width"]),
        layers=int(strategy["backbone_cfg"]["layers"]),
    )
    params = init_params(cfg, seed=init_seed)
    rng = np.random.default_rng(int(init_seed) % (2**32))

    lr = float(strategy["optim"]["lr"])
    max_steps = int(strategy["budget"]["max_steps"])
    batch_size = int(strategy["budget"]["batch_size"])
    loss_cfg = strategy["loss"]

    n = train_batch.u0.shape[0]
    t0 = time.time()
    last_loss = 0.0
    eps = 1e-4  # FD step for param groups (lift/proj only for speed)

    # Optimize only lift/proj for FD tractability in PoC; spectral stays random init.
    # This still learns a usable mapping under data_mse for discrimination tests.
    train_keys = ["lift_w", "lift_b", "proj_w", "proj_b"]

    steps_run = 0
    for step in range(max_steps):
        steps_run = step + 1
        idx = rng.integers(0, n, size=min(batch_size, n))
        u0 = train_batch.u0[idx]
        uT = train_batch.uT[idx]
        nu = train_batch.nu[idx]

        pred = forward(params, u0, cfg)
        loss, _ = unified_loss(pred, uT, u0, nu, loss_cfg)
        last_loss = loss

        # Finite-difference grads on lift/proj
        for key in train_keys:
            g = np.zeros_like(params[key])
            flat = params[key].ravel()
            g_flat = g.ravel()
            # subsample coordinates for speed (deterministic linspace)
            n_coords = min(8, flat.size)
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
            params[key] = params[key] - lr * g

        if time.time() - t0 > limits.get("max_wall_s", 600):
            break

    wall_s = time.time() - t0
    info = {
        "steps": steps_run,
        "wall_s": wall_s,
        "last_loss": last_loss,
        "device": "cpu",
        "init_seed": int(init_seed),
    }
    return params, cfg, info
