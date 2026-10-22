"""Carbon's one generic pinned trainer for F08 and F02 public graph recipes.

The Validator's ruling of 2026-10-20 (LAUNCHPAD_F08_F02_GRAPH_ADAPTER_SPEC):
one generic trainer, pinned, its digest in the construction identity. Its
source sha256 is `physical_graph_adapter.TRAINER_SHA256`, which each served
version's construction limits carry; any change here is a new digest, so a new
Challenge version, never this one changed in place.

It trains a validated, prepared Level 4 graph on the Challenge's fixed TRAIN:

- the selected TRAIN rows: all rows at `train_fraction` 1.0, otherwise a
  seeded subset of `int(rows * train_fraction)` rows, drawn as Battery's
  `recipes.train_subset` draws it;
- per-column target standardisation, with mean and standard deviation from
  the selected rows only (plus Battery's 1e-9 on the deviation);
- unweighted mean squared error in standardised units;
- AdamW (optax) at the recipe's rate, betas, epsilon and decoupled decay, with
  an optional linear warmup and a constant rate after it;
- full-batch updates when `batch_size` equals the selected rows, otherwise
  `batch_size` rows per update, permuted from Carbon's seed
  (`carbon.level4.train.keys`).

Float32 only. It runs inside the isolated build worker with only its staged
modules; it never reads participant Python and grants no judge authority.
"""

from __future__ import annotations

import numpy as np

SCHEMA = "carbon.physical-graph-trainer.v1"
#: Battery's standard-deviation floor (`battery.direct_graph.DirectGraphModel`).
SD_FLOOR = 1e-9


def selected_rows(count: int, fraction: float, seed: int) -> np.ndarray:
    """The selected TRAIN row indices, in TRAIN order."""
    if fraction >= 1.0:
        return np.arange(count)
    take = int(count * fraction)
    return np.sort(np.random.default_rng(seed).permutation(count)[:take])


def standardisation(targets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-column mean and deviation of the selected TRAIN targets."""
    mu = targets.mean(axis=0).astype(np.float32)
    sd = (targets.std(axis=0) + np.float32(SD_FLOOR)).astype(np.float32)
    return mu, sd


def train(prepared, inputs: np.ndarray, targets: np.ndarray, settings: dict, *, seed):
    """Fit `prepared` on the selected rows; returns params and the decoder."""
    import jax
    import jax.numpy as jnp
    import optax

    from carbon.level4.train import keys

    init_key, train_key = keys(seed)
    params = list(prepared.init(init_key))
    rows = selected_rows(len(inputs), settings["train_fraction"], seed)
    x = np.asarray(inputs[rows], dtype=np.float32)
    y = np.asarray(targets[rows], dtype=np.float32)
    mu, sd = standardisation(y)
    z = ((y - mu) / sd).astype(np.float32)
    n, batch = len(rows), settings["batch_size"]
    rate = settings["learning_rate"]
    warmup = settings["warmup_steps"]
    schedule = rate if warmup == 0 else optax.linear_schedule(0.0, rate, warmup)
    transform = optax.adamw(
        schedule,
        b1=settings["beta1"],
        b2=settings["beta2"],
        eps=settings["adam_epsilon"],
        weight_decay=settings["weight_decay"],
    )
    fx, fz = jnp.asarray(x), jnp.asarray(z)
    everything = jnp.arange(n)

    def loss(values, idx):
        return jnp.mean((prepared.apply(values, fx[idx])[0] - fz[idx]) ** 2)

    def step(carry, _):
        values, state, key = carry
        key, sub = jax.random.split(key)
        idx = everything if batch >= n else jax.random.permutation(sub, n)[:batch]
        gradients = jax.grad(loss)(values, idx)
        updates, state = transform.update(gradients, state, values)
        return (optax.apply_updates(values, updates), state, key), None

    @jax.jit
    def run(values, key):
        carry = (values, transform.init(values), key)
        (values, _, _), _ = jax.lax.scan(step, carry, None, length=settings["steps"])
        return values

    params = jax.block_until_ready(run(params, train_key))
    predicted = np.asarray(prepared.predict(params, fx)[0])
    return {
        "params": [np.asarray(value) for value in params],
        "mu": mu,
        "sd": sd,
        "selected_rows": int(n),
        "train_loss": float(np.mean((predicted - z) ** 2)),
    }
