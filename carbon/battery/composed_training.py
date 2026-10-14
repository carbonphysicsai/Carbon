"""Battery's composed development trainer: Levels 1-3 in one fit (CONSTRUCTION-CONTRACT-01).

The owner, 2026-10-13: a construction contract that rebuilds anything on the 0-4
plan, combinations included. Each level's trainer is `training.train` with its own
edits, and the edits touch separate parts of the loop:

- Level 1 (`level1_training`): a compiled loss expression is the per-case loss;
- Level 2 (`level2_training`): SpecMuon wraps battery's Muon and takes the
  step's loss;
- Level 3 (`level3_training`): the polish stage runs the menu's quasi-Newton
  routine and line search.

`train` below is `training.train` with all three, each applied only when its
part is present. With exactly one part present it is that level's trainer, and
`tests/cpu/test_battery_composed_training.py` checks every level bit for bit
against its own trainer. With none it is `training.train`.

**Why a separate module.** `recipes.py` and `training.py` are battery's
implementation modules (`implementation_versions.MODULES`), so they are left
byte for byte, as every level's trainer leaves them. The single-level trainers
are not changed either: a single-level record still rebuilds with its own
trainer. This module trains only a construction with two or more parts.

Relative imports only: this file is staged into the isolated worker's
`carbon_battery_lab` package beside `recipes.py` and `training.py`.
"""

from __future__ import annotations

import hashlib
import time

import numpy as np

from . import level2_specmuon, level3_numerics, recipes
from .training import keep_history, optimizer, polish, recording_history


def loss_program(
    *,
    jax,
    apply,
    f,
    z,
    sw,
    gw,
    trajectory,
    settings,
    order,
    case_loss=None,
    objective=None,
):
    """The composed loop's exact objective, also used by its isolated profiler."""
    jnp = jax.numpy
    s = settings
    f, z, sw, gw = (jnp.asarray(a) for a in (f, z, sw, gw))
    rank = jnp.asarray(order)
    n = f.shape[0]
    steps = s["steps"] - s["polish_steps"]
    expression = case_loss

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

    if expression is not None:

        def case_loss(p, idx):
            return expression(apply(p, f[idx]), z[idx], gw)

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
        if objective is not None:
            # The validated graph objective already owns Carbon's per-case mean.
            # GraphModel enforces neutral case/loss-term settings for this slot.
            return objective([apply(p, f[idx])], [z[idx]], [f[idx]])
        w = jax.lax.stop_gradient(weights(p, idx, step))
        return jnp.sum(w * case_loss(p, idx)) / (jnp.sum(w) + 1e-12)

    return loss


def train(
    *,
    init,
    apply,
    f,
    z,
    sw,
    gw,
    trajectory,
    settings,
    seed,
    order,
    case_loss=None,
    spectral=False,
    numerics=None,
    objective=None,
):
    """Train from `init(key)`; returns the parameters Carbon predicts from.

    `trajectory(z)` maps network outputs to normalized voltage and temperature
    trajectories (cases x times) for the trajectory losses. `order` ranks TRAIN
    cases for the curriculum. All arrays are in the requested precision.

    Composed: `case_loss(zhat, zt, gw)` (Level 1) replaces the objective menu's
    per-case loss; with `spectral` (Level 2) battery's Muon is wrapped by
    `level2_specmuon.spectral`; `numerics` (Level 3) runs the polish stage's
    routine and line search. Everything else is `training.train`, line for line.
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
    tx = optimizer(jax, optax, s, steps)
    if spectral:
        tx = level2_specmuon.spectral(jax, optax, tx)
    loss = loss_program(
        jax=jax,
        apply=apply,
        f=f,
        z=z,
        sw=sw,
        gw=gw,
        trajectory=trajectory,
        settings=settings,
        order=order,
        case_loss=case_loss,
        objective=objective,
    )

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
    # Fixed at trace time: off, the traced program is the one before trainer v2.
    recording = recording_history()

    def step_fn(carry, i):
        p, state, ema, avg, k = carry
        k, sub = jax.random.split(k)
        idx = everything if batch >= n else jax.random.permutation(sub, n)[:batch]
        value, g = gradient(p, idx, i)
        if spectral:
            updates, state = tx.update(
                g, state, p, value=value, value_fn=lambda q: loss(q, idx, i)
            )
        elif plateau:
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
        return (p, state, ema, avg, k), (value if recording else None)

    @jax.jit
    def run(params, key):
        carry = (params, tx.init(params), params, params, key)
        (p, state, ema, avg, _), values = jax.lax.scan(
            step_fn, carry, jnp.arange(steps, dtype=f.dtype)
        )
        return p, state, ema, avg, values

    p, state, ema, avg, values = run(params, key)
    if recording:
        keep_history(enumerate(np.asarray(values).tolist()), steps)
    if s["optimizer_family"] == "free_adamw":
        from optax.contrib import schedule_free_eval_params

        p = schedule_free_eval_params(state, p)
    if use_ema:
        p = ema
    elif s["tail_averaging"]:
        p = avg
    if s["polish_steps"]:
        if numerics is None:
            p = polish(
                jax, optax, p, lambda q: loss(q, everything, steps), s["polish_steps"]
            )
        else:
            p = level3_numerics.polish(
                jax,
                optax,
                p,
                lambda q: loss(q, everything, steps),
                s["polish_steps"],
                numerics,
            )
    return jax.block_until_ready(p)


class ComposedMLP(recipes.MLP):
    """`recipes.MLP` trained with the composed trainer: never the written-out
    classic loop, never the PyTorch backend (JAX only, as every development
    trainer). `loss` is Level 1's factory (`loss_terms.factory`) or None;
    `spectral` is Level 2's SpecMuon; `numerics` is Level 3's menu or None."""

    def __init__(self, family, settings, *, loss=None, spectral=False, numerics=None):
        super().__init__(family, settings)
        self.loss = loss
        self.spectral = bool(spectral)
        self.numerics = None if numerics is None else dict(numerics)

    def _classic(self, cases):
        return False

    def _groups(self):
        """`level1_training.LossMLP._groups`: the output groups' columns in the
        network's output space, in the order `_group_weights` weights them."""
        nv = self.pca if self.pca else self.layout.nv
        nt = self.pca if self.pca else self.layout.nt
        return (
            ("voltage", 0, nv),
            ("temperature", nv, nv + nt),
            ("plating", nv + nt, nv + nt + 1),
            ("capacity", nv + nt + 1, None),
        )

    def fit(self, d, structure, seed):
        if self.backend != "jax":
            raise ValueError("a composed construction trains on the JAX backend only")
        return super().fit(d, structure, seed)

    def parameter_count(self, d, structure):
        """`level3_training.NumericsMLP.parameter_count`: the trained network's
        parameter count without training, for the dense routine's memory bound."""
        from .level3_training import NumericsMLP

        return NumericsMLP.parameter_count(self, d, structure)

    def _objective(self):
        return None

    def _fit_general(self, d, y, seed):
        """`recipes.MLP._fit_general` with the composed trainer."""
        import jax

        from .training import take_history

        self.x64 = self.settings["precision"] == "float64"
        dtype = np.float64 if self.x64 else np.float32
        t0 = time.perf_counter()
        with jax.enable_x64(self.x64):
            z = self._encode(y).astype(dtype)
            f = recipes.features(d.x, self.rich).astype(dtype)
            sw = np.where(d.important, self.important_weight, 1.0).astype(dtype)
            gw = self._group_weights(z.shape[1]).astype(dtype)
            init, apply = self._network(jax, dtype, f.shape[1], z.shape[1])
            order = np.argsort(np.argsort(d.x[:, 0] + d.x[:, 1], kind="stable"))
            if self.settings["curriculum"] == "high_rate_first":
                order = len(order) - 1 - order
            params = train(
                init=init,
                apply=apply,
                f=f,
                z=z,
                sw=sw,
                gw=gw,
                trajectory=self._trajectory(jax.numpy),
                settings=self.settings,
                seed=seed,
                order=order,
                case_loss=(
                    None
                    if self.loss is None
                    else self.loss(
                        jax.numpy, self._trajectory(jax.numpy), self._groups()
                    )
                ),
                spectral=self.spectral,
                numerics=self.numerics,
                objective=self._objective(),
            )
            leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(params)]
            objective = self._objective()
            final = (
                float(
                    np.mean((np.asarray(apply(params, f)) - z) ** 2 * gw[None, :])
                    * gw.size
                )
                if objective is None
                else float(
                    objective(
                        [apply(params, jax.numpy.asarray(f))],
                        [jax.numpy.asarray(z)],
                        [jax.numpy.asarray(f)],
                    )
                )
            )
        self.params, self._apply = params, apply
        blob = b"".join(a.tobytes() for a in leaves)
        return recipes._with_history(
            {
                "compile_s": 0.0,
                "train_s": time.perf_counter() - t0,
                "final_loss": final,
                "params_sha256": hashlib.sha256(blob).hexdigest(),
                "n_params": int(sum(a.size for a in leaves)),
            },
            take_history(),
        )


class ComposedEnsemble(recipes.Ensemble):
    """`recipes.Ensemble` whose members are `ComposedMLP`s."""

    def __init__(self, members, family, settings, **parts):
        super().__init__(members, family, settings)
        self.parts = parts

    def fit(self, d, structure, seed):
        self.members, stats = [], []
        for i in range(self.k):
            member = dict(self.settings)
            member["steps"] = member["steps"] // self.k
            m = ComposedMLP(self.family, member, **self.parts)
            stats.append(m.fit(d, structure, seed=seed * 1000 + i))
            self.members.append(m)
        blob = "".join(s["params_sha256"] for s in stats).encode()
        history = stats[0].get("loss_history")
        return recipes._with_history(
            {
                "compile_s": sum(s["compile_s"] for s in stats),
                "train_s": sum(s["train_s"] for s in stats),
                "final_loss": float(np.mean([s["final_loss"] for s in stats])),
                "params_sha256": hashlib.sha256(blob).hexdigest(),
                "n_params": sum(s["n_params"] for s in stats),
            },
            None if history is None else {**history, "member": f"1 of {self.k}"},
        )


def build(family, settings, *, loss=None, spectral=False, numerics=None):
    """The untrained composed model a compiled recipe and its parts name: the
    MLP and DeepONet families only, as every development trainer."""
    if family not in ("mlp", "deeponet"):
        raise ValueError(
            "only the mlp and deeponet families take a composed construction"
        )
    parts = {"loss": loss, "spectral": spectral, "numerics": numerics}
    if settings["ensemble_members"] == 1:
        return ComposedMLP(family, settings, **parts)
    return ComposedEnsemble(settings["ensemble_members"], family, settings, **parts)
