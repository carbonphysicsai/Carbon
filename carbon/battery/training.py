"""Carbon's general battery training loop (JAX and optax, the pinned stack).

The campaign recipe at its defaults keeps its own written-out loop in
`recipes.MLP` (bit-identical to the research recipe). Every other combination
of the battery vocabulary trains here: optax optimizers and learning-rate
curves, minibatches and gradient accumulation, extra trajectory losses, TRAIN
case weighting and curriculum, EMA and tail averaging, an L-BFGS polish, and
float64. Each is a Carbon implementation of a registered surface; nothing here
executes anything a miner supplied, and all randomness is Carbon's
reconstruction seed.

Fixed, declared constants (engineering choices, not quality claims):
- piecewise curve: the peak until 50 % of the updates, 0.1x until 75 %, then
  0.01x;
- exponential curve: decays to `min_learning_rate_ratio` of the peak (0.01 if
  that is zero);
- SGDR: four equal warm restarts;
- polynomial curve: power 2 to `min_learning_rate_ratio` of the peak;
- plateau curve: halve the rate after `max(10, steps // 20)` updates without a
  TRAIN-loss improvement;
- Prodigy: the curve, divided by its peak, multiplies Prodigy's own step;
- SAM: normalized-SGD adversary with rho 0.05, alternating updates;
- curriculum: TRAIN cases ordered by c1 + c2, a quarter admitted at the start
  and all by half of the updates;
- time weighting: a linear 2-to-0 (early) or 0-to-2 (late) ramp over time.
"""

from __future__ import annotations

import itertools

import numpy as np

ACTIVATIONS = ("gelu", "relu", "tanh", "silu", "softplus")
SAM_RHO = 0.05


def _activation(jax, name):
    return {
        "gelu": jax.nn.gelu,
        "relu": jax.nn.relu,
        "tanh": jax.numpy.tanh,
        "silu": jax.nn.silu,
        "softplus": jax.nn.softplus,
    }[name]


def _scale(name, a, b):
    if name == "he_normal":
        return np.sqrt(2.0 / a)
    if name == "glorot_normal":
        return np.sqrt(2.0 / (a + b))
    return np.sqrt(1.0 / a)  # lecun_normal


def dense_stack(jax, key, sizes, initialization, dtype):
    params = []
    for a, b in itertools.pairwise(sizes):
        key, k1 = jax.random.split(key)
        params.append(
            (
                jax.random.normal(k1, (a, b), dtype) * _scale(initialization, a, b),
                jax.numpy.zeros((b,), dtype),
            )
        )
    return key, params


def apply_stack(jax, params, h, activation, normalization):
    act = _activation(jax, activation)
    for w, b in params[:-1]:
        h = h @ w + b
        if normalization == "layer_norm":
            mean = h.mean(-1, keepdims=True)
            h = (h - mean) / jax.numpy.sqrt(h.var(-1, keepdims=True) + 1e-6)
        h = act(h)
    w, b = params[-1]
    return h @ w + b


def curve(optax, settings, steps):
    """The learning-rate curve over `steps` updates, warmup included."""
    peak = settings["learning_rate"]
    ratio = settings["min_learning_rate_ratio"]
    warmup = settings["warmup_steps"]
    name = settings["learning_rate_curve"]
    decay = max(steps - warmup, 1)
    if name == "cosine":
        main = optax.cosine_decay_schedule(peak, decay, alpha=ratio)
    elif name in ("constant", "train_loss_plateau"):
        main = optax.constant_schedule(peak)
    elif name == "piecewise":
        main = optax.piecewise_constant_schedule(
            peak, {decay // 2: 0.1, (3 * decay) // 4: 0.1}
        )
    elif name == "exponential":
        main = optax.exponential_decay(peak, decay, ratio if ratio > 0 else 0.01)
    elif name == "one_cycle":
        return optax.cosine_onecycle_schedule(steps, peak)
    elif name == "sgdr":
        cycle = max(decay // 4, 1)
        main = optax.sgdr_schedule(
            [
                {
                    "init_value": peak,
                    "peak_value": peak,
                    "warmup_steps": 0,
                    "decay_steps": cycle,
                    "end_value": 0.0,
                }
            ]
            * 4
        )
    elif name == "polynomial":
        main = optax.polynomial_schedule(peak, peak * ratio, 2, decay)
    else:  # pragma: no cover - the registry's closed choice
        raise ValueError("unregistered learning-rate curve")
    if warmup == 0:
        return main
    return optax.join_schedules(
        [optax.linear_schedule(0.0, peak, warmup), main], [warmup]
    )


def optimizer(jax, optax, settings, steps):
    """The optax transform for a registered optimizer family."""
    from optax import contrib

    lr = curve(optax, settings, steps)
    b1, b2 = settings["beta1"], settings["beta2"]
    eps, wd = settings["adam_epsilon"], settings["weight_decay"]
    mask = None
    if settings["weight_decay_mask"] == "matrices":

        def mask(params):
            return jax.tree_util.tree_map(lambda x: x.ndim >= 2, params)

    def decoupled(scale):
        return optax.chain(
            scale, optax.add_decayed_weights(wd, mask), optax.scale_by_learning_rate(lr)
        )

    name = settings["optimizer_family"]
    if name == "adam":
        tx = decoupled(optax.scale_by_adam(b1, b2, eps))
    elif name == "lion":
        tx = optax.lion(lr, b1, b2, weight_decay=wd, mask=mask)
    elif name == "lamb":
        tx = optax.lamb(lr, b1, b2, eps, weight_decay=wd, mask=mask)
    elif name == "adafactor":
        tx = optax.adafactor(lr, weight_decay_rate=wd or None, weight_decay_mask=mask)
    elif name == "radam":
        tx = decoupled(optax.scale_by_radam(b1, b2, eps))
    elif name == "nadamw":
        tx = optax.nadamw(lr, b1, b2, eps, weight_decay=wd, mask=mask)
    elif name == "sgd_momentum":
        tx = decoupled(optax.trace(decay=b1))
    elif name == "muon":
        tx = contrib.muon(lr, beta=b1, eps=eps, weight_decay=wd, weight_decay_mask=mask)
    elif name == "prodigy":
        peak = settings["learning_rate"]
        tx = contrib.prodigy(
            lambda step: lr(step) / peak, betas=(b1, b2), eps=eps, weight_decay=wd
        )
    elif name == "free_adamw":
        tx = contrib.schedule_free_adamw(
            settings["learning_rate"],
            warmup_steps=settings["warmup_steps"] or None,
            b1=b1,
            b2=b2,
            eps=eps,
            weight_decay=wd,
        )
    elif name == "sam":
        tx = contrib.sam(
            decoupled(optax.scale_by_adam(b1, b2, eps)),
            optax.chain(contrib.normalize(), optax.sgd(SAM_RHO)),
            sync_period=2,
        )
    else:  # pragma: no cover - the registry's closed choice
        raise ValueError("unregistered optimizer")
    if settings["learning_rate_curve"] == "train_loss_plateau":
        tx = optax.chain(
            tx, contrib.reduce_on_plateau(factor=0.5, patience=max(10, steps // 20))
        )
    if settings["clip_norm"] > 0:
        tx = optax.chain(optax.clip_by_global_norm(settings["clip_norm"]), tx)
    return tx


def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order):
    """Train from `init(key)`; returns the parameters Carbon predicts from.

    `trajectory(z)` maps network outputs to normalized voltage and temperature
    trajectories (cases x times) for the trajectory losses. `order` ranks TRAIN
    cases for the curriculum. All arrays are in the requested precision.
    """
    import jax
    import jax.numpy as jnp
    import optax

    s = settings
    n = f.shape[0]
    steps = s["steps"] - s["polish_steps"]
    batch = min(s["batch_size"], n)
    micro = s["microbatches"]
    key = jax.random.PRNGKey(seed)
    key, params = init(key)
    f, z, sw, gw = (jnp.asarray(a) for a in (f, z, sw, gw))
    rank = jnp.asarray(order)
    tx = optimizer(jax, optax, s, steps)

    def ramp(length):
        if s["time_weighting"] == "early":
            return jnp.linspace(2.0, 0.0, length)
        return jnp.linspace(0.0, 2.0, length)

    def case_loss(p, idx):
        zhat = apply(p, f[idx])
        zt = z[idx]
        base = jnp.sum((zhat - zt) ** 2 * gw[None, :], axis=1)
        if s["relative_loss"]:
            base = base / (jnp.sum(zt**2 * gw[None, :], axis=1) + 1e-6)
        extra = 0.0
        if (
            s["time_weighting"] != "uniform"
            or s["h1_weight"]
            or s["h2_weight"]
            or s["spectral_weight"]
        ):
            for a, b in zip(trajectory(zhat), trajectory(zt)):
                e = a - b
                if s["time_weighting"] != "uniform":
                    extra = extra + jnp.mean(ramp(e.shape[1]) * e**2, axis=1)
                if s["h1_weight"]:
                    d = jnp.diff(e, axis=1)
                    extra = extra + s["h1_weight"] * jnp.mean(d**2, axis=1)
                if s["h2_weight"]:
                    d = jnp.diff(e, n=2, axis=1)
                    extra = extra + s["h2_weight"] * jnp.mean(d**2, axis=1)
                if s["spectral_weight"]:
                    spectrum = jnp.abs(jnp.fft.rfft(e, axis=1)) ** 2
                    k = jnp.linspace(0.0, 1.0, spectrum.shape[1])
                    extra = (
                        extra
                        + s["spectral_weight"]
                        * jnp.mean(k * spectrum, axis=1)
                        / e.shape[1]
                    )
        return base + extra

    def weights(p, idx, step):
        w = sw[idx]
        if s["curriculum"] != "none":
            admitted = jnp.minimum(1.0, 0.25 + 1.5 * step / steps)
            w = w * (rank[idx] < jnp.ceil(admitted * n))
        if s["hard_example_weight"]:
            current = jax.lax.stop_gradient(case_loss(p, idx))
            w = w * (current / (jnp.mean(current) + 1e-12)) ** s["hard_example_weight"]
        return w

    def loss(p, idx, step):
        w = jax.lax.stop_gradient(weights(p, idx, step))
        return jnp.sum(w * case_loss(p, idx)) / (jnp.sum(w) + 1e-12)

    def gradient(p, idx, step):
        if micro == 1:
            return jax.value_and_grad(loss)(p, idx, step)
        chunks = idx.reshape(micro, -1)
        total = None
        for c in range(micro):
            v, g = jax.value_and_grad(loss)(p, chunks[c], step)
            if total is None:
                total = (v, g)
            else:
                total = (
                    total[0] + v,
                    jax.tree_util.tree_map(jnp.add, total[1], g),
                )
        return total[0] / micro, jax.tree_util.tree_map(lambda g: g / micro, total[1])

    tail = int(steps * (1.0 - s["tail_averaging"])) if s["tail_averaging"] else steps
    decay = s["ema_decay"]
    use_ema = s["inference_weights"] == "ema"
    plateau = s["learning_rate_curve"] == "train_loss_plateau"
    everything = jnp.arange(n)

    def step_fn(carry, i):
        p, state, ema, avg, k = carry
        k, sub = jax.random.split(k)
        idx = everything if batch >= n else jax.random.permutation(sub, n)[:batch]
        value, g = gradient(p, idx, i)
        if plateau:
            updates, state = tx.update(g, state, p, value=value)
        else:
            updates, state = tx.update(g, state, p)
        p = optax.apply_updates(p, updates)
        if use_ema:
            ema = jax.tree_util.tree_map(
                lambda e, x: decay * e + (1 - decay) * x, ema, p
            )
        if s["tail_averaging"]:
            count = jnp.maximum(i - tail + 1, 1).astype(f.dtype)
            avg = jax.tree_util.tree_map(
                lambda a, x: jnp.where(i >= tail, a + (x - a) / count, a), avg, p
            )
        return (p, state, ema, avg, k), None

    @jax.jit
    def run(params, key):
        carry = (params, tx.init(params), params, params, key)
        (p, state, ema, avg, _), _ = jax.lax.scan(
            step_fn, carry, jnp.arange(steps, dtype=f.dtype)
        )
        return p, state, ema, avg

    p, state, ema, avg = run(params, key)
    if s["optimizer_family"] == "free_adamw":
        from optax.contrib import schedule_free_eval_params

        p = schedule_free_eval_params(state, p)
    if use_ema:
        p = ema
    elif s["tail_averaging"]:
        p = avg
    if s["polish_steps"]:
        p = polish(
            jax, optax, p, lambda q: loss(q, everything, steps), s["polish_steps"]
        )
    return jax.block_until_ready(p)


def polish(jax, optax, params, objective, count):
    """Full-batch L-BFGS steps with optax's zoom line search."""
    tx = optax.lbfgs()
    value_and_grad = optax.value_and_grad_from_state(objective)

    @jax.jit
    def run(p):
        def body(carry, _):
            p, state = carry
            value, g = value_and_grad(p, state=state)
            updates, state = tx.update(
                g, state, p, value=value, grad=g, value_fn=objective
            )
            return (optax.apply_updates(p, updates), state), None

        (p, _), _ = jax.lax.scan(body, (p, tx.init(p)), None, length=count)
        return p

    return run(params)
