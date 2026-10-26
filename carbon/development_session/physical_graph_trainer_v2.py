"""Carbon's graph trainer v2 for public graph recipes, every Challenge (graph
route v2; owner: "No carbon limits please!", Launchpad sweep rows L9-L12).

It sits beside the pinned v1 trainer (`physical_graph_trainer`), which F08
1.4 and F02 2.3 keep byte for byte. Its source sha256 is
`physical_graph_adapter_v2.TRAINER_SHA256`, carried by each graph route v2
version's construction limits; any change here is a new digest, so a new
Challenge version, never this one changed in place.

One call trains one ensemble member of a validated, prepared Level 4 graph on
the Challenge's fixed TRAIN:

- the selected TRAIN rows: all rows at `train_fraction` 1.0, otherwise a
  seeded subset of `int(rows * train_fraction)` rows, drawn exactly as v1
  draws them, shared by every member;
- per-column target standardisation from the selected rows (v1's);
- the member's loss on its own output subset, each output weighted by the
  recipe's per-output weight: `mse`, `mae` or `huber` per case and output in
  standardised units, averaged over cases, then the weighted mean over the
  member's outputs (weights renormalised over them); or, when the recipe
  carries a loss graph, that graph over the training batch (the model's outputs
  and the targets in standardised units, the batch's inputs, the parameters),
  which replaces the menu loss, its loss kind and output weights;
- the member's optimizer (`adamw`, `adam`, `sgd` with momentum, `lion`), its
  rate, an optional linear warmup and a `constant`, `cosine` or `linear`
  curve down to `min_learning_rate_ratio` of the rate, and optional global
  gradient clipping;
- full-batch updates when `batch_size` is at least the selected rows,
  otherwise `batch_size` rows per update, permuted from the member's key.

Member `m`'s keys are Carbon's seed keys (`carbon.level4.train.keys`) folded
with `m`, so member 0 of a one-member recipe is not v1's draw: v2 is its own
trainer. TRAIN and the decoder are in the interface's dtype (float32 or
float64); the graph's own computation precision is the graph's (Validator:
only the output dtype is kept). It runs inside the isolated build worker with only its
staged modules; it never reads participant Python and grants no judge
authority.
"""

from __future__ import annotations

import numpy as np

SCHEMA = "carbon.physical-graph-trainer.v2"
#: v1's standard-deviation floor, kept so the decoder is v1's.
SD_FLOOR = 1e-9
LOSSES = ("mse", "mae", "huber")
OPTIMIZERS = ("adamw", "adam", "sgd", "lion")
CURVES = ("constant", "cosine", "linear")


def selected_rows(count: int, fraction: float, seed: int) -> np.ndarray:
    """The selected TRAIN row indices, in TRAIN order (v1's draw)."""
    if fraction >= 1.0:
        return np.arange(count)
    take = int(count * fraction)
    return np.sort(np.random.default_rng(seed).permutation(count)[:take])


def standardisation(targets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-column mean and deviation of the selected TRAIN targets, in their
    own dtype."""
    dtype = targets.dtype
    mu = targets.mean(axis=0).astype(dtype)
    sd = (targets.std(axis=0) + dtype.type(SD_FLOOR)).astype(dtype)
    return mu, sd


def member_weights(output_weights, outputs, width: int) -> np.ndarray:
    """The member's per-output loss weights: the recipe's weight on each of
    the member's outputs, zero elsewhere, renormalised to sum to one."""
    weights = np.zeros(width, dtype=np.float64)
    for index in outputs:
        weights[index] = output_weights[index]
    total = float(weights.sum())
    if not total > 0:
        raise ValueError("a member's outputs carry no loss weight")
    return weights / total


def _schedule(settings: dict):
    import optax

    rate, warmup = settings["learning_rate"], settings["warmup_steps"]
    floor = rate * settings["min_learning_rate_ratio"]
    decay = max(settings["steps"] - warmup, 1)
    curve = settings["learning_rate_curve"]
    if curve == "constant":
        after = optax.constant_schedule(rate)
    elif curve == "cosine":
        after = optax.cosine_decay_schedule(
            rate, decay, alpha=settings["min_learning_rate_ratio"]
        )
    else:
        after = optax.linear_schedule(rate, floor, decay)
    if warmup == 0:
        return after
    return optax.join_schedules(
        [optax.linear_schedule(0.0, rate, warmup), after], [warmup]
    )


def _optimizer(settings: dict):
    import optax

    schedule = _schedule(settings)
    family = settings["optimizer_family"]
    if family == "adamw":
        transform = optax.adamw(
            schedule,
            b1=settings["beta1"],
            b2=settings["beta2"],
            eps=settings["adam_epsilon"],
            weight_decay=settings["weight_decay"],
        )
    elif family == "adam":
        transform = optax.adam(
            schedule,
            b1=settings["beta1"],
            b2=settings["beta2"],
            eps=settings["adam_epsilon"],
        )
    elif family == "sgd":
        transform = optax.sgd(schedule, momentum=settings["beta1"] or None)
    else:
        transform = optax.lion(
            schedule,
            b1=settings["beta1"],
            b2=settings["beta2"],
            weight_decay=settings["weight_decay"],
        )
    if settings["clip_norm"] > 0:
        transform = optax.chain(
            optax.clip_by_global_norm(settings["clip_norm"]), transform
        )
    return transform


def train_member(
    prepared,
    x: np.ndarray,
    z: np.ndarray,
    settings: dict,
    weights: np.ndarray,
    *,
    seed: int,
    member: int,
):
    """Fit one member on the selected, standardised rows `x`, `z`."""
    import jax
    import jax.numpy as jnp
    import optax

    from carbon.level4.train import keys

    init_key, train_key = (jax.random.fold_in(k, member) for k in keys(seed))
    params = list(prepared.init(init_key))
    n, batch = len(x), settings["batch_size"]
    transform = _optimizer(settings)
    fx, fz = jnp.asarray(x), jnp.asarray(z)
    fw = jnp.asarray(weights, dtype=z.dtype)
    everything = jnp.arange(n)
    kind, delta = settings["loss"], settings["huber_delta"]

    def per_output(error):
        if kind == "mse":
            return error**2
        if kind == "mae":
            return jnp.abs(error)
        magnitude = jnp.abs(error)
        return jnp.where(
            magnitude <= delta,
            0.5 * error**2,
            delta * (magnitude - 0.5 * delta),
        )

    custom = getattr(prepared, "loss", None)

    def loss(values, idx):
        if custom is not None:
            # The miner's loss graph over this batch (standardised units), with
            # the model's parameters as inputs: it replaces the menu loss.
            batch_x = fx[idx]
            return custom(
                [prepared.apply(values, batch_x)[0]], [fz[idx]], [batch_x], values
            )
        error = prepared.apply(values, fx[idx])[0] - fz[idx]
        return jnp.sum(jnp.mean(per_output(error), axis=0) * fw)

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
    error = predicted - z
    return {
        "params": [np.asarray(value) for value in params],
        "train_loss": float(np.sum(np.mean(error**2, axis=0) * weights)),
    }


def combination(members: list, width: int) -> np.ndarray:
    """Per-output combination weights, (members, outputs): each
    output is the weighted mean of the members that train on it, by their
    `weight`; a member's row is zero on outputs it does not train."""
    rows = np.zeros((len(members), width), dtype=np.float64)
    for index, member in enumerate(members):
        for output in member["outputs"]:
            rows[index, output] = member["weight"]
    totals = rows.sum(axis=0)
    if not np.all(totals > 0):
        raise ValueError("an output no member trains")
    return rows / totals


def train(prepared, inputs: np.ndarray, targets: np.ndarray, settings: dict, *, seed):
    """Fit every member of `settings["ensemble"]` on the selected rows;
    returns each member's params, the decoder and the combination."""
    rows = selected_rows(len(inputs), settings["train_fraction"], seed)
    x = np.asarray(inputs[rows], dtype=inputs.dtype)
    y = np.asarray(targets[rows], dtype=targets.dtype)
    mu, sd = standardisation(y)
    z = ((y - mu) / sd).astype(targets.dtype)
    width = z.shape[1]
    members = settings["ensemble"]
    fitted = [
        train_member(
            prepared,
            x,
            z,
            member["training"],
            member_weights(settings["output_weights"], member["outputs"], width),
            seed=seed,
            member=index,
        )
        for index, member in enumerate(members)
    ]
    combine = combination(members, width).astype(targets.dtype)
    import jax.numpy as jnp

    fx = jnp.asarray(x)
    combined = sum(
        np.asarray(prepared.predict(member["params"], fx)[0]) * combine[index]
        for index, member in enumerate(fitted)
    )
    return {
        "members": [member["params"] for member in fitted],
        "member_losses": [member["train_loss"] for member in fitted],
        "combine": combine,
        "mu": mu,
        "sd": sd,
        "selected_rows": len(rows),
        "train_loss": float(np.mean((combined - z) ** 2)),
    }
