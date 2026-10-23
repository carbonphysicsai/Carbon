"""Catalog trainer v2 for the JAX (jNO / foundax) backbones, with Carbon's own limits removed
(backbone-catalog lane, "No Carbon limits", step 3, 2026-10-23).

The JAX twin of the Torch trainer v2 (`build.py`): the same lever names and meanings on the packet's unchanged foundax
registry (`jax_backbones_dc.build_backbone`). It trains fresh from the fixed TRAIN in the TRAIN's own float dtype
(float64 where the worker enables x64, which it does only for a float64 TRAIN; float32 otherwise), deterministically, so
a second rebuild gives the same bytes. The product is the parameters form (trained arrays as graph inputs). A lever
this file cannot express raises.

configuration: {"backbone", "learning_rate"}  (the foundax constructors take no architecture settings)
train_use (every key optional; `steps` default 300):
  loss        {"kind": mse|l1|huber|relative_l2|log_cosh, "delta", "smoothness", "output_weights": [w, ...]}
  optimizer   {"name": adam|adamw|sgd|rmsprop|lbfgs|adagrad|nadam|radam, "weight_decay", "momentum"}
  schedule    {"name": none|cosine|step|onecycle|warmup_cosine|exponential|polynomial|cosine_restarts, "gamma", "every",
              "warmup", "power"}
  data, stages, early_stopping, averaging, search, seeds, distill, prune, as the Torch trainer
  ensemble    {"members": k | [{"outputs": [indices]}, ...], "combine": mean|stacking|stacking_per_output|
              best_per_output|weights, "weights", "validation"}: a member trains with its loss restricted to its outputs
              and is combined only on them; every output must be covered by at least one member
  quantize    {"bits"}: bits >= 2
  precision   bfloat16|float16|float32 (float32 compute against the master weights; JAX's FFT refuses bfloat16)
The build seed and the seed candidates stay uint32 (numpy and PRNGKey seed from them).
"""

from __future__ import annotations

import math

TRAIN_LEVERS = {
    "loss",
    "optimizer",
    "schedule",
    "data",
    "stages",
    "averaging",
    "precision",
}
LEVERS = TRAIN_LEVERS | {
    "steps",
    "early_stopping",
    "search",
    "seeds",
    "ensemble",
    "distill",
    "prune",
    "quantize",
}
CONFIG_KEYS = ("learning_rate", "backbone")
COMBINES = ("mean", "stacking", "stacking_per_output", "best_per_output", "weights")


def output_weights(spec, n_out, mask=None):
    """The per-output loss weights of a run (loss.output_weights times a member's output mask), or None when neither
    narrows the loss (then the loss is the plain mean over outputs, as in v1)."""
    import numpy as np

    given = spec.get("output_weights")
    if given is None and mask is None:
        return None
    if given is None:
        w = np.ones(n_out)
    else:
        if type(given) is not list or len(given) != n_out:
            raise ValueError(
                f"loss.output_weights must list one weight per output ({n_out})"
            )
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in given
        ):
            raise ValueError("loss.output_weights must be finite and not negative")
        w = np.asarray([float(v) for v in given])
    if mask is not None:
        w = w * np.asarray(mask, dtype=np.float64)
    if not (w > 0).any():
        raise ValueError("loss.output_weights leave no output with a positive weight")
    return w / w.sum()


def members_cover(spec, n_out):
    """The (members, outputs) 0/1 coverage matrix from `ensemble.members`."""
    import numpy as np

    members = spec.get("members", 3)
    if type(members) is int:
        return np.ones((_positive(members, "members", 3), n_out))
    if type(members) is not list or not members:
        raise ValueError(
            "ensemble.members must be a whole number or a non-empty list of member specs"
        )
    cover = np.zeros((len(members), n_out))
    for i, member in enumerate(members):
        _only(member, {"outputs"}, f"ensemble.members[{i}]")
        outputs = member.get("outputs")
        if outputs is None:
            cover[i] = 1.0
            continue
        if (
            type(outputs) is not list
            or not outputs
            or any(type(o) is not int or not 0 <= o < n_out for o in outputs)
        ):
            raise ValueError(
                f"ensemble.members[{i}].outputs must list output indices from 0 to {n_out - 1}"
            )
        cover[i, outputs] = 1.0
    uncovered = [j for j in range(n_out) if not (cover[:, j] > 0).any()]
    if uncovered:
        raise ValueError(f"output {uncovered[0]} is covered by no ensemble member")
    return cover


def combination(combine, spec, cover, preds, target):
    """The (members, outputs) weight matrix for `combine` (numpy); only covering members weigh on an output.
    `preds` is (members, n, outputs) on held-out rows, `target` (n, outputs); both None for mean and weights.
    """
    import numpy as np

    k, n_out = cover.shape
    if combine == "mean":
        return cover / cover.sum(0, keepdims=True)
    if combine == "weights":
        given = spec.get("weights")
        if type(given) is not list or len(given) != k:
            raise ValueError("ensemble.weights must list one entry per member")
        rows = []
        for entry in given:
            if type(entry) is list:
                if len(entry) != n_out:
                    raise ValueError(
                        "a per-output member weight list must have one weight per output"
                    )
                rows.append(np.asarray([float(v) for v in entry]))
            else:
                rows.append(np.full(n_out, float(entry)))
        w = np.stack(rows)
        if not np.isfinite(w).all():
            raise ValueError("ensemble.weights must be finite")
        return w * cover
    if combine == "stacking":
        flat_p = (preds * cover[:, None, :]).reshape(k, -1)
        gram = flat_p @ flat_p.T + 1e-6 * np.eye(k)
        w = np.linalg.solve(gram, flat_p @ target.reshape(-1))
        return w[:, None] * cover
    out = np.zeros((k, n_out))
    for j in range(n_out):
        idx = [i for i in range(k) if cover[i, j] > 0]
        if combine == "stacking_per_output":
            p = preds[idx, :, j]
            out[idx, j] = np.linalg.solve(
                p @ p.T + 1e-6 * np.eye(len(idx)), p @ target[:, j]
            )
        else:  # best_per_output
            errors = [float(np.mean((preds[i, :, j] - target[:, j]) ** 2)) for i in idx]
            out[idx[min(range(len(idx)), key=errors.__getitem__)], j] = 1.0
    return out


def _only(mapping, allowed, name):
    if type(mapping) is not dict or set(mapping) - set(allowed):
        raise ValueError(
            f"unsupported {name}: {sorted(set(mapping or {}) - set(allowed))}"
        )


def _positive(value, name, default):
    value = default if value is None else value
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _rate(value, default):
    value = default if value is None else value
    if type(value) not in (int, float) or not 0 < value <= 1:
        raise ValueError("learning_rate must be in (0, 1]")
    return float(value)


def build(train_inputs, train_targets, *, seed, configuration, train_use):
    import equinox as eqx
    import jax
    import jax.numpy as jnp
    import numpy as np
    import optax

    try:
        from .jax_backbones_dc import build_backbone
    except ImportError:  # pragma: no cover - flat test layout
        from jax_backbones_dc import build_backbone

    # The worker enables x64 only for a float64 TRAIN (bundle_construction_worker.requires_x64). The guard follows the
    # TRAIN's own dtype: a float64 TRAIN without x64 refuses; a float32 TRAIN (F08, F02) trains in float32.
    x64 = bool(jax.config.jax_enable_x64)
    if not x64 and np.asarray(train_inputs).dtype == np.float64:
        raise RuntimeError("JAX x64 must be enabled for a float64 TRAIN")
    FLOAT = jnp.float64 if x64 else jnp.float32
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a uint32 integer")
    _only(configuration, {"backbone", "learning_rate"}, "configuration")
    _only(train_use, LEVERS, "train_use")
    x = np.asarray(train_inputs, dtype=np.float64)
    y = np.asarray(train_targets, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or len(x) < 2:
        raise ValueError("expected paired 2-D TRAIN inputs and targets")
    n_in = x.shape[1]
    mx, sx = x.mean(0), x.std(0) + 1e-9
    my, sy = y.mean(0), y.std(0) + 1e-9
    z, t = jnp.asarray((x - mx) / sx), jnp.asarray((y - my) / sy)
    lr = _rate(configuration.get("learning_rate"), 1e-3)
    steps = _positive(train_use.get("steps"), "steps", 300)
    rng = np.random.default_rng(seed)

    # --- one training run ------------------------------------------------
    def loss_of(pred, target, spec, weights, out_w=None):
        _only(spec, {"kind", "delta", "smoothness", "output_weights"}, "loss")
        kind = spec.get("kind", "mse")
        w_out = None if out_w is None else jnp.asarray(out_w, dtype=pred.dtype)

        def across(e):
            return jnp.mean(e, 1) if w_out is None else jnp.sum(e * w_out, 1)

        if kind == "mse":
            per = across((pred - target) ** 2)
        elif kind == "l1":
            per = across(jnp.abs(pred - target))
        elif kind == "huber":
            per = across(
                optax.huber_loss(pred, target, delta=float(spec.get("delta", 1.0)))
            )
        elif kind == "log_cosh":
            d = jnp.abs(pred - target)
            per = across(d + jax.nn.softplus(-2 * d) - math.log(2.0))
        elif kind == "relative_l2":
            if w_out is None:
                per = jnp.sum((pred - target) ** 2, 1) / (jnp.sum(target**2, 1) + 1e-6)
            else:
                per = jnp.sum(((pred - target) ** 2) * w_out, 1) / (
                    jnp.sum((target**2) * w_out, 1) + 1e-6
                )
        else:
            raise ValueError(f"loss kind {kind!r} is not supported")
        total = jnp.sum(per * weights) / jnp.sum(weights)
        w = float(spec.get("smoothness", 0.0))
        if w:
            total = total + w * jnp.mean(
                (pred[:, 2:] - 2 * pred[:, 1:-1] + pred[:, :-2]) ** 2
            )
        return total

    def optimizer_of(spec, rate):
        _only(spec, {"name", "weight_decay", "momentum"}, "optimizer")
        name, wd = spec.get("name", "adam"), float(spec.get("weight_decay", 0.0))
        if name == "adam":
            return (
                optax.chain(optax.add_decayed_weights(wd), optax.adam(rate))
                if wd
                else optax.adam(rate)
            )
        if name == "adamw":
            return optax.adamw(rate, weight_decay=wd or 1e-2)
        if name == "sgd":
            return optax.sgd(
                rate, momentum=float(spec.get("momentum", 0.9)), nesterov=True
            )
        if name == "rmsprop":
            return optax.rmsprop(rate)
        if name == "adagrad":
            return (
                optax.chain(optax.add_decayed_weights(wd), optax.adagrad(rate))
                if wd
                else optax.adagrad(rate)
            )
        if name == "nadam":
            return (
                optax.chain(optax.add_decayed_weights(wd), optax.nadam(rate))
                if wd
                else optax.nadam(rate)
            )
        if name == "radam":
            return (
                optax.chain(optax.add_decayed_weights(wd), optax.radam(rate))
                if wd
                else optax.radam(rate)
            )
        if name == "lbfgs":
            return optax.lbfgs(learning_rate=rate)
        raise ValueError(f"optimizer {name!r} is not supported")

    def schedule_of(spec, n, rate):
        _only(spec, {"name", "gamma", "every", "warmup", "power"}, "schedule")
        name = spec.get("name", "none")
        if name == "none":
            return rate
        if name == "cosine":
            return optax.cosine_decay_schedule(rate, n)
        if name == "step":
            every = int(spec.get("every", max(1, n // 3)))
            gamma = float(spec.get("gamma", 0.5))
            return optax.piecewise_constant_schedule(
                rate, {k: gamma for k in range(every, n, every)}
            )
        if name == "onecycle":
            return optax.cosine_onecycle_schedule(n, rate)
        if name == "warmup_cosine":
            warm = int(spec.get("warmup", max(1, n // 10)))
            return optax.warmup_cosine_decay_schedule(0.0, rate, warm, max(n, warm + 1))
        if name == "exponential":
            return optax.exponential_decay(rate, 1, float(spec.get("gamma", 0.99)))
        if name == "polynomial":
            return optax.polynomial_schedule(
                rate, 0.0, float(spec.get("power", 2.0)), n
            )
        if name == "cosine_restarts":
            period = max(1, int(spec.get("every", max(1, n // 3))))
            parts = -(-n // period)
            return optax.sgdr_schedule(
                [
                    {
                        "init_value": rate,
                        "peak_value": rate,
                        "decay_steps": period,
                        "warmup_steps": 0,
                        "end_value": 0.0,
                    }
                ]
                * parts
            )
        raise ValueError(f"schedule {name!r} is not supported")

    def train(
        backbone,
        use,
        run_seed,
        xs,
        ys,
        *,
        run_steps,
        rate,
        val=None,
        teacher=None,
        masks=None,
        start=None,
        out_mask=None,
    ):
        data = dict(use.get("data") or {})
        _only(
            data,
            {"subset", "batch", "order", "curriculum", "reweight", "mixup", "noise"},
            "data",
        )
        gen = np.random.default_rng(run_seed)
        order = gen.permutation(len(xs))
        subset = float(data.get("subset", 1.0))
        if not 0 < subset <= 1:
            raise ValueError("data.subset must be in (0, 1]")
        keep = order[: max(2, round(subset * len(xs)))]
        xs, ys = xs[keep], ys[keep]
        if data.get("order", "random") == "easy_first":
            rank = np.argsort(np.asarray(jnp.mean(ys**2, 1)), kind="stable")
            xs, ys = xs[rank], ys[rank]
        elif data.get("order", "random") != "random":
            raise ValueError("data.order must be random or easy_first")
        curriculum = dict(data.get("curriculum") or {})
        _only(curriculum, {"start", "ramp"}, "data.curriculum")
        reweight = data.get("reweight", "none")
        if reweight not in ("none", "hard_mining"):
            raise ValueError("data.reweight must be none or hard_mining")
        mixup, noise = float(data.get("mixup", 0.0)), float(data.get("noise", 0.0))
        precision = use.get("precision")
        # float32 compute against float64 master weights is the mixed precision
        # spectral models can use: JAX's FFT refuses bfloat16 and float16.
        if precision not in (None, "bfloat16", "float16", "float32"):
            raise ValueError("precision must be bfloat16, float16 or float32")
        compute = {
            "bfloat16": jnp.bfloat16,
            "float16": jnp.float16,
            "float32": jnp.float32,
        }.get(precision)
        loss_spec = dict(use.get("loss") or {})
        out_w = output_weights(loss_spec, ys.shape[1], out_mask)
        if start is None:
            model, forward = build_backbone(
                backbone, jax.random.PRNGKey(run_seed), n_in
            )
            params, static = eqx.partition(model, eqx.is_inexact_array)
        else:
            params, static, forward = start
        stages = use.get("stages") or [
            {
                "steps": run_steps,
                "optimizer": use.get("optimizer") or {},
                "schedule": use.get("schedule") or {},
            }
        ]
        averaging = dict(use.get("averaging") or {})
        if averaging:
            _only(averaging, {"kind", "decay", "start"}, "averaging")
            if averaging.get("kind", "ema") not in ("ema", "swa"):
                raise ValueError("averaging kind must be ema or swa")
        early = dict(use.get("early_stopping") or {}) if val is not None else {}
        total = sum(_positive(s.get("steps"), "stage steps", run_steps) for s in stages)
        weights = jnp.ones(len(xs))
        avg, count, best, best_loss, stale, done = None, 0, None, math.inf, 0, 0
        n = len(xs)

        def forward_at(p, inputs):
            if compute is None:
                return forward(eqx.combine(p, static), inputs)
            low = jax.tree_util.tree_map(lambda a: a.astype(compute), p)
            return forward(eqx.combine(low, static), inputs.astype(compute)).astype(
                FLOAT
            )

        def loss_fn(p, xb, yb, wb):
            pred = forward_at(p, xb).astype(FLOAT)
            value = loss_of(pred, yb, loss_spec, wb, out_w)
            if teacher is not None:
                target = jax.lax.stop_gradient(teacher(xb))
                alpha = float((use.get("distill") or {}).get("alpha", 0.5))
                value = alpha * value + (1 - alpha) * jnp.mean((pred - target) ** 2)
            return value

        stopped = False
        for stage in stages:
            _only(stage, {"steps", "optimizer", "schedule", "learning_rate"}, "stage")
            n_steps = _positive(stage.get("steps"), "stage steps", run_steps)
            stage_rate = _rate(stage.get("learning_rate"), rate)
            spec = dict(stage.get("optimizer") or {})
            opt = optimizer_of(
                spec,
                schedule_of(dict(stage.get("schedule") or {}), n_steps, stage_rate),
            )
            state = opt.init(params)
            lbfgs = spec.get("name") == "lbfgs"

            @jax.jit
            def step(p, s, xb, yb, wb):
                value, grads = jax.value_and_grad(loss_fn)(p, xb, yb, wb)
                if lbfgs:
                    updates, s = opt.update(
                        grads,
                        s,
                        p,
                        value=value,
                        grad=grads,
                        value_fn=lambda q: loss_fn(q, xb, yb, wb),
                    )
                else:
                    updates, s = opt.update(grads, s, p)
                return optax.apply_updates(p, updates), s, value

            for _ in range(n_steps):
                seen = n
                if curriculum:
                    begin, ramp = float(curriculum.get("start", 0.3)), float(
                        curriculum.get("ramp", 0.5)
                    )
                    seen = max(
                        2,
                        round(
                            n
                            * min(
                                1.0, begin + (1 - begin) * done / max(1, ramp * total)
                            )
                        ),
                    )
                idx = np.arange(seen)
                if data.get("batch"):
                    idx = idx[
                        gen.permutation(seen)[: _positive(data["batch"], "batch", 1)]
                    ]
                xb, yb, wb = xs[idx], ys[idx], weights[idx]
                if mixup:
                    lam = float(gen.beta(mixup, mixup))
                    perm = gen.permutation(len(idx))
                    xb, yb = (
                        lam * xb + (1 - lam) * xb[perm],
                        lam * yb + (1 - lam) * yb[perm],
                    )
                if noise:
                    xb = xb + noise * jnp.asarray(gen.standard_normal(xb.shape))
                params, state, value = step(params, state, xb, yb, wb)
                if not bool(jnp.isfinite(value)):
                    raise RuntimeError("nonfinite TRAIN loss")
                if masks is not None:
                    params = jax.tree_util.tree_map(
                        lambda a, m: a if m is None else a * m,
                        params,
                        masks,
                        is_leaf=lambda v: v is None,
                    )
                done += 1
                if averaging:
                    kind = averaging.get("kind", "ema")
                    if kind == "ema":
                        decay = float(averaging.get("decay", 0.99))
                        avg = (
                            params
                            if avg is None
                            else jax.tree_util.tree_map(
                                lambda a, b: decay * a + (1 - decay) * b, avg, params
                            )
                        )
                    elif done >= int(float(averaging.get("start", 0.75)) * total):
                        count += 1
                        avg = (
                            params
                            if avg is None
                            else jax.tree_util.tree_map(
                                lambda a, b: a + (b - a) / count, avg, params
                            )
                        )
                if reweight == "hard_mining" and done % 25 == 0:
                    per = jnp.mean((forward_at(params, xs).astype(FLOAT) - ys) ** 2, 1)
                    weights = 1.0 + per / (jnp.mean(per) + 1e-12)
                if early and done % int(early.get("every", 10)) == 0:
                    score = float(
                        jnp.mean(
                            (forward_at(params, val[0]).astype(FLOAT) - val[1]) ** 2
                        )
                    )
                    if score < best_loss:
                        best_loss, best, stale = score, params, 0
                    else:
                        stale += 1
                        if stale >= int(early.get("patience", 5)):
                            stopped = True
                            break
            if stopped:
                break
        if avg is not None:
            params = avg
        if best is not None:
            params = best
        return params, static, forward

    def predict(trained, inputs):
        params, static, forward = trained
        return forward(eqx.combine(params, static), inputs).astype(FLOAT)

    def evaluate(trained, xs, ys):
        return float(jnp.mean((predict(trained, xs) - ys) ** 2))

    def split(fraction):
        fraction = float(fraction)
        if not 0 < fraction < 1:
            raise ValueError("validation must be in (0, 1)")
        order = rng.permutation(len(z))
        k = max(1, round(fraction * len(z)))
        return (z[order[k:]], t[order[k:]]), (z[order[:k]], t[order[:k]])

    def with_(config, candidate):
        return {**config, **{k: v for k, v in candidate.items() if k in CONFIG_KEYS}}

    base = {
        k: v
        for k, v in train_use.items()
        if k not in ("search", "seeds", "ensemble", "distill", "prune", "quantize")
    }
    config, use, run_seed = dict(configuration), dict(base), seed
    for lever in ("search", "seeds"):
        spec = train_use.get(lever)
        if not spec:
            continue
        _only(spec, {"candidates", "trial_steps", "validation"}, lever)
        (fx, fy), (vx, vy) = split(spec.get("validation", 0.2))
        trial = _positive(spec.get("trial_steps"), "trial_steps", max(1, steps // 4))
        scores = []
        for candidate in spec["candidates"]:
            if lever == "seeds":
                if type(candidate) is not int or not 0 <= candidate < 2**32:
                    raise ValueError("seed candidates must be uint32 integers")
                c_config, c_use, c_seed = config, use, candidate
            else:
                _only(candidate, set(CONFIG_KEYS) | TRAIN_LEVERS, "candidate")
                c_config, c_seed = with_(config, candidate), run_seed
                c_use = {
                    **use,
                    **{k: v for k, v in candidate.items() if k not in CONFIG_KEYS},
                }
            trained = train(
                c_config["backbone"],
                c_use,
                c_seed,
                fx,
                fy,
                run_steps=trial,
                rate=_rate(c_config.get("learning_rate"), lr),
            )
            scores.append(evaluate(trained, vx, vy))
        winner = spec["candidates"][min(range(len(scores)), key=scores.__getitem__)]
        if lever == "seeds":
            run_seed = winner
        else:
            config = with_(config, winner)
            use = {**use, **{k: v for k, v in winner.items() if k not in CONFIG_KEYS}}

    early = train_use.get("early_stopping")
    (fit_x, fit_y), val = (
        split(dict(early).get("validation", 0.2)) if early else ((z, t), None)
    )
    rate = _rate(config.get("learning_rate"), lr)

    teacher = None
    if train_use.get("distill"):
        spec = dict(train_use["distill"])
        _only(spec, {"teacher", "teacher_steps", "alpha"}, "distill")
        teacher_spec = dict(spec.get("teacher") or {})
        _only(teacher_spec, {"backbone"}, "distill.teacher")
        trained = train(
            teacher_spec.get("backbone", config["backbone"]),
            use,
            run_seed + 1,
            fit_x,
            fit_y,
            run_steps=_positive(spec.get("teacher_steps"), "teacher_steps", steps),
            rate=rate,
        )
        teacher = jax.jit(lambda inputs, _t=trained: predict(_t, inputs))

    members, member_matrix = [], np.ones((1, y.shape[1]))
    if train_use.get("ensemble"):
        spec = dict(train_use["ensemble"])
        _only(spec, {"members", "combine", "weights", "validation"}, "ensemble")
        cover = members_cover(spec, y.shape[1])
        k = cover.shape[0]
        combine = spec.get("combine", "mean")
        if combine not in COMBINES:
            raise ValueError(
                "ensemble.combine must be mean, stacking, stacking_per_output, best_per_output or weights"
            )

        def row_mask(i):
            return None if (cover[i] > 0).all() else cover[i]

        if combine in ("stacking", "stacking_per_output", "best_per_output"):
            (sx_, sy_), (vx, vy) = split(spec.get("validation", 0.2))
            members = [
                train(
                    config["backbone"],
                    use,
                    run_seed + 10 + i,
                    sx_,
                    sy_,
                    run_steps=steps,
                    rate=rate,
                    teacher=teacher,
                    out_mask=row_mask(i),
                )
                for i in range(k)
            ]
            preds = np.stack([np.asarray(predict(m, vx)) for m in members])
            member_matrix = combination(combine, spec, cover, preds, np.asarray(vy))
        else:
            members = [
                train(
                    config["backbone"],
                    use,
                    run_seed + 10 + i,
                    fit_x,
                    fit_y,
                    run_steps=steps,
                    rate=rate,
                    val=val,
                    teacher=teacher,
                    out_mask=row_mask(i),
                )
                for i in range(k)
            ]
            member_matrix = combination(combine, spec, cover, None, None)
    else:
        members = [
            train(
                config["backbone"],
                use,
                run_seed,
                fit_x,
                fit_y,
                run_steps=steps,
                rate=rate,
                val=val,
                teacher=teacher,
            )
        ]

    if train_use.get("prune"):
        spec = dict(train_use["prune"])
        _only(spec, {"fraction", "finetune_steps"}, "prune")
        fraction = float(spec.get("fraction", 0.5))
        if not 0 < fraction < 1:
            raise ValueError("prune.fraction must be in (0, 1)")
        pruned = []
        for i, (params, static, forward) in enumerate(members):
            leaves = jax.tree_util.tree_leaves(params)
            magnitudes = jnp.concatenate(
                [jnp.abs(a).reshape(-1) for a in leaves if a.ndim >= 2]
            )
            threshold = jnp.quantile(magnitudes, fraction)
            masks = jax.tree_util.tree_map(
                lambda a: (
                    (jnp.abs(a) > threshold).astype(a.real.dtype)
                    if a.ndim >= 2
                    else None
                ),
                params,
            )
            params = jax.tree_util.tree_map(
                lambda a, m: a if m is None else a * m,
                params,
                masks,
                is_leaf=lambda v: v is None,
            )
            finetune = int(spec.get("finetune_steps", 100))
            if finetune:
                params, static, forward = train(
                    config["backbone"],
                    use,
                    run_seed + 99 + i,
                    fit_x,
                    fit_y,
                    run_steps=finetune,
                    rate=rate * 0.1,
                    masks=masks,
                    start=(params, static, forward),
                )
            pruned.append((params, static, forward))
        members = pruned

    if train_use.get("quantize"):
        spec = dict(train_use["quantize"])
        _only(spec, {"bits"}, "quantize")
        bits = _positive(spec.get("bits"), "bits", 8)
        if bits < 2:
            raise ValueError("quantize.bits must be at least 2")
        levels = float(2 ** (bits - 1) - 1)

        def snap(a):
            if jnp.iscomplexobj(a):
                return snap(a.real) + 1j * snap(a.imag)
            scale = jnp.max(jnp.abs(a)) / levels
            return jnp.where(
                scale > 0, jnp.round(a / jnp.where(scale > 0, scale, 1)) * scale, a
            )

        members = [(jax.tree_util.tree_map(snap, p), s, f) for p, s, f in members]

    # --- the product: every member's trained arrays as graph parameters --------
    flat, treedefs, counts = [], [], []
    for params, _, _ in members:
        leaves, treedef = jax.tree_util.tree_flatten(params)
        flat += leaves
        treedefs.append(treedef)
        counts.append(len(leaves))
    if not all(bool(jnp.all(jnp.isfinite(a))) for a in flat):
        raise RuntimeError("nonfinite trained state")
    mx_j, sx_j, my_j, sy_j = (jnp.asarray(v) for v in (mx, sx, my, sy))
    weights_j = [jnp.asarray(row, dtype=FLOAT) for row in member_matrix]

    def apply(params, inputs):
        if len(params) != len(flat):
            raise ValueError("parameter count differs")
        q = (jnp.asarray(inputs, dtype=FLOAT) - mx_j) / sx_j
        out, at = None, 0
        for (_, static, forward), treedef, count, w in zip(
            members, treedefs, counts, weights_j
        ):
            trained = jax.tree_util.tree_unflatten(
                treedef, list(params[at : at + count])
            )
            at += count
            part = forward(eqx.combine(trained, static), q).astype(FLOAT) * w
            out = part if out is None else out + part
        return out * sy_j + my_j

    direct = np.asarray(apply(flat, x))
    if (
        direct.shape != y.shape
        or direct.dtype != np.dtype(FLOAT)
        or not np.isfinite(direct).all()
    ):
        raise RuntimeError("trained prediction invalid")
    return {"framework": "jax", "apply": apply, "parameters": flat}
