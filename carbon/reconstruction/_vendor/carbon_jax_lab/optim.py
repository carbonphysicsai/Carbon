"""Small JAX AdamW implementation; tested against PyTorch AdamW.

No dependency is silently substituted at runtime. This fallback exists because
Flax/Optax could not be installed in the execution environment. It uses standard
bias-corrected Adam and decoupled decay, not a claimed novel optimizer.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp


class AdamState(NamedTuple):
    count: jax.Array
    m: object
    v: object


def init_adam(params):
    z = jax.tree.map(jnp.zeros_like, params)
    return AdamState(jnp.array(0, dtype=jnp.int32), z, z)


def global_norm(tree):
    return jnp.sqrt(sum(jnp.sum(jnp.square(x)) for x in jax.tree.leaves(tree)))


def all_finite(tree):
    return jnp.all(jnp.stack([jnp.all(jnp.isfinite(x)) for x in jax.tree.leaves(tree)]))


def learning_rate(step, cfg):
    s = jnp.asarray(step, dtype=jnp.float32)
    progress = jnp.clip(
        (s - cfg.warmup_steps) / max(1, cfg.steps - cfg.warmup_steps - 1), 0, 1
    )
    cosine = 0.5 * (1 + jnp.cos(jnp.pi * progress))
    lr = cfg.learning_rate * (
        cfg.min_learning_rate_ratio + (1 - cfg.min_learning_rate_ratio) * cosine
    )
    if cfg.warmup_steps:
        lr = jnp.where(
            s < cfg.warmup_steps, cfg.learning_rate * (s + 1) / cfg.warmup_steps, lr
        )
    return lr


def adamw(
    params,
    grads,
    state,
    lr,
    *,
    beta1=0.9,
    beta2=0.999,
    epsilon=1e-8,
    weight_decay=0.0,
    clip_norm=1.0,
    decay_mask=None,
):
    norm = global_norm(grads)
    factor = jnp.minimum(1.0, clip_norm / jnp.maximum(norm, 1e-12))
    grads = jax.tree.map(lambda g: g * factor, grads)
    m = jax.tree.map(lambda a, g: beta1 * a + (1 - beta1) * g, state.m, grads)
    v = jax.tree.map(lambda a, g: beta2 * a + (1 - beta2) * g * g, state.v, grads)
    count = state.count + 1
    if decay_mask is None:
        decay_mask = jax.tree.map(lambda p: p.ndim > 1, params)

    def update(p, m, v, mask):
        mh = m / (1 - jnp.asarray(beta1) ** count)
        vh = v / (1 - jnp.asarray(beta2) ** count)
        return p - lr * (mh / (jnp.sqrt(vh) + epsilon) + weight_decay * p * mask)

    p = jax.tree.map(update, params, m, v, decay_mask)
    return p, AdamState(count, m, v), norm
