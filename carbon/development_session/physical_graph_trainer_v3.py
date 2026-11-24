"""Carbon's graph trainer v3: trainer v2 plus the construction-only training knobs
(Lead call 16 Nov 2026, CV-Motor L12281 (2)(a) and L12299 group (b)). It sits
beside the pinned v1 and v2 trainers, which keep their bytes; its source sha256
is `physical_graph_adapter_v2.TRAINER_V3_SHA256`, carried only by the versions
whose Spec names trainer "v3" (Motor 1.8). EVERY knob's default reproduces v2
bit for bit (tests/cpu/test_graph_trainer_v3.py): with the defaults, the
default code path below is v2's, op for op.

New knobs (all training procedure; grading unchanged, nothing is rescored):
`microbatches`, `weight_decay_mask`, `relative_loss`, `hard_example_weight`,
`ema_decay` + `inference_weights`, `tail_averaging`, `polish_steps`; and the
Motor 1.8 group (b) terms on the 4 x 60 row layout: `h1_weight`, `h2_weight`,
`spectral_weight`, `time_weighting`, `important_region_weight` (+ its
`important_region_band`). Conventions (Lead 16 Nov; CV-Motor may amend) are
stated on each helper below.

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

SCHEMA = "carbon.physical-graph-trainer.v3"
#: v1's standard-deviation floor, kept so the decoder is v1's.
SD_FLOOR = 1e-9
LOSSES = ("mse", "mae", "huber")
OPTIMIZERS = ("adamw", "adam", "sgd", "lion")
CURVES = ("constant", "cosine", "linear")
#: The training curve each fit records (DATA D2): the loss value every optimiser step already computes (the scan's
#: output, from `value_and_grad` of the same loss whose gradient the step applies), per member, on public TRAIN only.
#: At most `CURVE_POINTS` points per member (every `stride`-th step, the last step always kept), 7 significant
#: digits, and the whole block within `CURVE_BYTES_MAX` canonical JSON bytes (the stride doubles until it fits), so
#: the build receipt stays inside its cap. A record of the fit, never a score input.
CURVE_SCHEMA = "carbon.graph-training-curve.v1"
CURVE_POINTS = 256
CURVE_BYTES_MAX = 32 * 1024


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


def _decay_mask(settings: dict):
    """`weight_decay_mask`: "all" decays every parameter (v2's behaviour, the
    default, so the defaults stay bit-identical); "matrices" decays only the
    parameters with two or more axes (biases and norm scales excluded)."""
    if settings.get("weight_decay_mask", "all") == "all":
        return None
    return lambda params: [getattr(value, "ndim", 0) >= 2 for value in params]


def _optimizer(settings: dict):
    import optax

    schedule = _schedule(settings)
    family = settings["optimizer_family"]
    mask = _decay_mask(settings)
    if family == "adamw":
        transform = optax.adamw(
            schedule,
            b1=settings["beta1"],
            b2=settings["beta2"],
            eps=settings["adam_epsilon"],
            weight_decay=settings["weight_decay"],
            **({} if mask is None else {"mask": mask}),
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
            **({} if mask is None else {"mask": mask}),
        )
    if settings["clip_norm"] > 0:
        transform = optax.chain(
            optax.clip_by_global_norm(settings["clip_norm"]), transform
        )
    return transform


#: `relative_loss`: each case's loss is divided by the same loss of the TRAIN-mean
#: predictor on that case (all standardised outputs zero), plus this floor.
RELATIVE_FLOOR = 1e-3
#: The defaults every knob has in a v2-equivalent member.
KNOB_DEFAULTS = {
    "microbatches": 1,
    "weight_decay_mask": "all",
    "relative_loss": False,
    "hard_example_weight": 0.0,
    "ema_decay": 0.99,
    "inference_weights": "params",
    "tail_averaging": 0.0,
    "polish_steps": 0,
    "h1_weight": 0.0,
    "h2_weight": 0.0,
    "spectral_weight": 0.0,
    "time_weighting": None,
    "important_region_weight": 0.0,
    "important_region_band": 0.1,
}


def important_mask(targets: np.ndarray, layout: dict, band: float) -> np.ndarray:
    """1.0 on the TRAIN rows whose public limit quantities lie within the
    relative `band` of a public limit (`layout["limits"]`: the mean torque
    minimum and the ripple-fraction maximum of the Challenge's public
    important-limit definition), else 0.0; read from the raw (unstandardised)
    selected targets' torque slice."""
    steps = layout["steps"]
    torque = np.asarray(targets, dtype=np.float64)[:, :steps]
    mean = torque.mean(axis=1)
    ripple = torque.max(axis=1) - torque.min(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        fraction = np.where(mean > 0, ripple / mean, np.inf)
    floor = layout["limits"]["min_mean_torque_nm"]
    cap = layout["limits"]["max_ripple_fraction"]
    near_mean = np.abs(mean - floor) <= band * floor
    near_ripple = np.isfinite(fraction) & (np.abs(fraction - cap) <= band * cap)
    return (near_mean | near_ripple).astype(np.float64)


def _differences(x, periodic: bool, order: int):
    """The `order`-th angle-axis difference along the last axis: wrap-around
    when `periodic`, one-sided (shorter) at the window ends otherwise."""
    import jax.numpy as jnp

    if periodic:
        if order == 1:
            return jnp.roll(x, -1, axis=-1) - x
        return jnp.roll(x, -1, axis=-1) - 2 * x + jnp.roll(x, 1, axis=-1)
    if order == 1:
        return x[..., 1:] - x[..., :-1]
    return x[..., 2:] - 2 * x[..., 1:-1] + x[..., :-2]


def train_member(
    prepared,
    x: np.ndarray,
    z: np.ndarray,
    settings: dict,
    weights: np.ndarray,
    *,
    seed: int,
    member: int,
    layout: dict | None = None,
    important: np.ndarray | None = None,
):
    """Fit one member on the selected, standardised rows `x`, `z`."""
    import jax
    import jax.numpy as jnp
    import optax

    from carbon.level4.train import keys

    knobs = {name: settings.get(name, value) for name, value in KNOB_DEFAULTS.items()}
    polish = knobs["polish_steps"]
    steps = settings["steps"] - polish
    micro = knobs["microbatches"]
    use_ema = knobs["inference_weights"] == "ema"
    tail = knobs["tail_averaging"]
    terms = (knobs["h1_weight"], knobs["h2_weight"], knobs["spectral_weight"])
    tw = knobs["time_weighting"]
    extended = bool(
        knobs["relative_loss"]
        or knobs["hard_example_weight"]
        or any(terms)
        or tw is not None
        or knobs["important_region_weight"]
    )
    if (any(terms) or tw is not None) and layout is None:
        raise ValueError("a row-layout term needs the Challenge's layout")
    if knobs["important_region_weight"] and (layout is None or important is None):
        raise ValueError("important_region_weight needs the layout and the region")
    if polish and (use_ema or tail):
        raise ValueError("polish_steps with EMA or tail averaging is not defined")
    if steps < 1:
        raise ValueError("polish_steps leaves no main steps")

    init_key, train_key = (jax.random.fold_in(k, member) for k in keys(seed))
    params = list(prepared.init(init_key))
    n, batch = len(x), settings["batch_size"]
    transform = _optimizer({**settings, "steps": steps})
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
    if custom is not None and extended:
        raise ValueError("the menu-loss knobs do not apply to a recipe loss graph")
    slices = length = 0
    periodic = set()
    if layout is not None:
        slices, length = layout["slices"], layout["steps"]
        periodic = set(layout["periodic"])
    # The layout's curve block is the first slices x steps columns; a version may carry SCALAR columns after it (Motor
    # 1.9: 240 curve columns + magnet_min_b_t, audit row 5): the curve terms read the curve block only, and the time
    # weighting weights the curve block and leaves every tail column at 1.0.
    span = slices * length
    scalars = z.shape[1] - span
    if layout is not None and scalars < 0:
        raise ValueError("the layout's curve block is wider than the targets")
    column_weights = None
    if tw is not None:
        row = jnp.asarray(tw, dtype=z.dtype)
        column_weights = jnp.concatenate(
            [jnp.tile(row / jnp.mean(row), slices), jnp.ones(scalars, dtype=z.dtype)]
        )
    region = None if important is None else jnp.asarray(important, dtype=z.dtype)

    def extended_loss(values, idx):
        predicted = prepared.apply(values, fx[idx])[0]
        target = fz[idx]
        columns = per_output(predicted - target)
        zero = per_output(target)
        if column_weights is not None:
            columns, zero = columns * column_weights, zero * column_weights
        sample = jnp.sum(columns * fw, axis=1)
        if knobs["relative_loss"]:
            sample = sample / (jnp.sum(zero * fw, axis=1) + RELATIVE_FLOOR)
        if knobs["hard_example_weight"]:
            size = sample.shape[0]
            rank = jnp.argsort(jnp.argsort(jax.lax.stop_gradient(sample)))
            share = rank / max(size - 1, 1)
            blend = 1.0 + knobs["hard_example_weight"] * share
            sample = sample * (blend / jnp.mean(blend))
        if knobs["important_region_weight"]:
            sample = sample * (1.0 + knobs["important_region_weight"] * region[idx])
        total = jnp.mean(sample)
        if any(terms):
            shape = (predicted.shape[0], slices, length)
            p = predicted[:, :span].reshape(shape)
            t = target[:, :span].reshape(shape)
            for order, weight in ((1, terms[0]), (2, terms[1])):
                if not weight:
                    continue
                parts = []
                for s in range(slices):
                    diff = _differences(p[:, s], s in periodic, order) - _differences(
                        t[:, s], s in periodic, order
                    )
                    parts.append(jnp.mean(diff**2))
                total = total + weight * jnp.mean(jnp.stack(parts))
            if terms[2]:
                s0 = layout["spectral_slice"]

                def amplitude(v):
                    spectrum = jnp.fft.rfft(v, axis=-1)
                    return jnp.sqrt(spectrum.real**2 + spectrum.imag**2 + 1e-12)

                total = total + terms[2] * jnp.mean(
                    (amplitude(p[:, s0]) - amplitude(t[:, s0])) ** 2
                )
        return total

    def loss(values, idx):
        if custom is not None:
            # The miner's loss graph over this batch (standardised units), with
            # the model's parameters as inputs: it replaces the menu loss.
            batch_x = fx[idx]
            return custom(
                [prepared.apply(values, batch_x)[0]], [fz[idx]], [batch_x], values
            )
        if extended:
            return extended_loss(values, idx)
        error = prepared.apply(values, fx[idx])[0] - fz[idx]
        return jnp.sum(jnp.mean(per_output(error), axis=0) * fw)

    # `value_and_grad` gives the same gradient `jax.grad` gave (grad IS value_and_grad's second output) and keeps
    # the loss value the step already computed: the training curve (`CURVE_SCHEMA`).
    def gradient(values, key):
        key, sub = jax.random.split(key)
        total = value_total = None
        for part in jax.random.split(sub, micro):
            idx = everything if batch >= n else jax.random.permutation(part, n)[:batch]
            value, grads = jax.value_and_grad(loss)(values, idx)
            total = (
                grads
                if total is None
                else jax.tree_util.tree_map(lambda a, b: a + b, total, grads)
            )
            value_total = value if value_total is None else value_total + value
        return (
            jax.tree_util.tree_map(lambda g: g / micro, total),
            key,
            value_total / micro,
        )

    tail_count = max(1, round(tail * steps)) if tail else 0
    decay = knobs["ema_decay"]
    averaged = use_ema or bool(tail)

    def step(carry, index):
        values, state, key = carry[:3]
        gradients, key, value = gradient(values, key)
        updates, state = transform.update(gradients, state, values)
        values = optax.apply_updates(values, updates)
        mean = carry[3]
        if use_ema:
            mean = jax.tree_util.tree_map(
                lambda m, v: decay * m + (1.0 - decay) * v, mean, values
            )
        else:
            take = (index >= steps - tail_count).astype(z.dtype)
            mean = jax.tree_util.tree_map(lambda m, v: m + take * v, mean, values)
        return (values, state, key, mean), value

    def plain(carry, _):
        # v2's step, op for op (the default path).
        values, state, key = carry
        key, sub = jax.random.split(key)
        idx = everything if batch >= n else jax.random.permutation(sub, n)[:batch]
        value, gradients = jax.value_and_grad(loss)(values, idx)
        updates, state = transform.update(gradients, state, values)
        return (optax.apply_updates(values, updates), state, key), value

    def accumulate(carry, _):
        values, state, key = carry
        gradients, key, value = gradient(values, key)
        updates, state = transform.update(gradients, state, values)
        return (optax.apply_updates(values, updates), state, key), value

    @jax.jit
    def run(values, key):
        carry = (values, transform.init(values), key)
        if averaged:
            start = (
                values if use_ema else jax.tree_util.tree_map(jnp.zeros_like, values)
            )
            (values, _, _, mean), losses = jax.lax.scan(
                step, (*carry, start), jnp.arange(steps), length=steps
            )
            values = (
                mean
                if use_ema
                else jax.tree_util.tree_map(lambda m: m / tail_count, mean)
            )
        else:
            body = plain if micro == 1 else accumulate
            (values, _, _), losses = jax.lax.scan(body, carry, None, length=steps)
        polish_losses = None
        if polish:

            # The graph is validated and run at one declared batch, so the
            # full-TRAIN objective is the mean over fixed chunks of `batch`
            # rows in TRAIN order (the last chunk wraps to the first rows).
            count = -(-n // batch)
            chunks = (jnp.arange(count * batch) % n).reshape(count, batch)

            def objective(v):
                return jnp.mean(jax.lax.map(lambda idx: loss(v, idx), chunks))

            solver = optax.lbfgs()
            value_and_grad = optax.value_and_grad_from_state(objective)

            def refine(state_carry, _):
                current, state = state_carry
                value, grads = value_and_grad(current, state=state)
                updates, state = solver.update(
                    grads, state, current, value=value, grad=grads, value_fn=objective
                )
                return (optax.apply_updates(current, updates), state), value

            (values, _), polish_losses = jax.lax.scan(
                refine, (values, solver.init(values)), None, length=polish
            )
        return values, losses, polish_losses

    params, losses, polish_losses = jax.block_until_ready(run(params, train_key))
    predicted = np.asarray(prepared.predict(params, fx)[0])
    error = predicted - z
    return {
        "params": [np.asarray(value) for value in params],
        "train_loss": float(np.sum(np.mean(error**2, axis=0) * weights)),
        "curve": [float(v) for v in np.asarray(losses)],
        "polish_curve": (
            None
            if polish_losses is None
            else [float(v) for v in np.asarray(polish_losses)]
        ),
    }


def _sampled(values: list, stride: int) -> list:
    """Every `stride`-th value from the first, the last always kept; 7 significant digits; a non-finite value as None
    (JSON holds no NaN; a diverged step stays visible as a gap)."""
    picked = values[::stride]
    if values and (len(values) - 1) % stride:
        picked = [*picked, values[-1]]
    return [float(f"{v:.7g}") if np.isfinite(v) else None for v in picked]


def curve_block(fitted: list) -> dict:
    """The fit's training-curve record from each member's per-step losses (`CURVE_SCHEMA`): per member its main curve
    and, with `polish_steps`, its polish curve, sampled at the stride that keeps at most `CURVE_POINTS` points per
    curve and the whole block within `CURVE_BYTES_MAX` (doubled until it fits)."""
    import json

    longest = max(
        [len(m["curve"]) for m in fitted]
        + [len(m["polish_curve"] or ()) for m in fitted]
    )
    stride = max(1, -(-longest // CURVE_POINTS))
    while True:
        block = {
            "schema": CURVE_SCHEMA,
            "stride": stride,
            "members": [_sampled(m["curve"], stride) for m in fitted],
            "polish": [
                (
                    None
                    if m["polish_curve"] is None
                    else _sampled(m["polish_curve"], stride)
                )
                for m in fitted
            ],
        }
        size = len(json.dumps(block, sort_keys=True, separators=(",", ":")))
        if size <= CURVE_BYTES_MAX or stride >= longest:
            return block
        stride *= 2


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
    layout = settings.get("layout")
    fitted = [
        train_member(
            prepared,
            x,
            z,
            member["training"],
            member_weights(settings["output_weights"], member["outputs"], width),
            seed=seed,
            member=index,
            layout=layout,
            important=(
                important_mask(
                    y, layout, member["training"].get("important_region_band", 0.1)
                )
                if layout is not None
                and member["training"].get("important_region_weight", 0.0)
                else None
            ),
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
        "curve": curve_block(fitted),
    }
