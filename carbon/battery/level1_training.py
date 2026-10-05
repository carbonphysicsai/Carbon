"""Battery's Level-1 trainer: Carbon's general loop with a compiled loss expression.

GRAPHITE-L1-BUILD-01. Level 1 trains exactly as `training.train` and
`recipes.MLP` do, except that the per-case loss is a compiled loss expression
(`carbon.battery.loss_terms.factory`) instead of the objective menu.

**Why a separate module.** `recipes.py` and `training.py` are battery's
implementation modules (`contracts.IMPLEMENTATION_MODULES`): their bytes are
part of every Level-0 recipe's construction profile, so every Level-0 recipe
digest, staged file and rebuild digest depends on them. They are left byte for
byte as they are on main, and Level 1 lives here instead: staged only into a
Level-1 trial (`carbon.battery.level1_worker`), never into a Level-0 one.

**No drift.** `train` below is `training.train` line for line except for its
signature, its docstring and its per-case loss; a test rebuilds it from
`training.train`'s source with that one edit and compares
(`tests/cpu/test_battery_level1.py`). `LossMLP` and `LossEnsemble` subclass
`recipes.MLP` and `recipes.Ensemble` and override only what reads the loss.

Relative imports only: this file is also staged into the isolated practice
worker's `carbon_battery_lab` package beside `recipes.py` and `training.py`.
"""

from __future__ import annotations

import hashlib
import time

import numpy as np

from . import recipes
from .training import keep_history, optimizer, polish, recording_history


def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order, case_loss):
    """Train from `init(key)`; returns the parameters Carbon predicts from.

    `trajectory(z)` maps network outputs to normalized voltage and temperature
    trajectories (cases x times) for the trajectory losses. `order` ranks TRAIN
    cases for the curriculum. All arrays are in the requested precision.

    Level 1: `case_loss(zhat, zt, gw)` is the compiled loss expression's
    per-case loss, which replaces the objective menu's. Everything else is
    `training.train`, line for line.
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

    expression = case_loss

    def case_loss(p, idx):
        # The Level-1 loss replaces the objective menu's per-case loss.
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
    # Fixed at trace time: off, the traced program is the one before trainer v2.
    recording = recording_history()

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
        p = polish(
            jax, optax, p, lambda q: loss(q, everything, steps), s["polish_steps"]
        )
    return jax.block_until_ready(p)


class LossMLP(recipes.MLP):
    """`recipes.MLP` trained with a Level-1 loss: never the written-out
    classic loop, never the PyTorch backend."""

    def __init__(self, family, settings, loss):
        super().__init__(family, settings)
        #: `loss(jnp, trajectory, groups) -> (zhat, zt, gw) -> per-case loss`.
        self.loss = loss

    def _classic(self, cases):
        return False

    def _groups(self):
        """The output groups' columns in the network's output space, in the
        order `_group_weights` weights them."""
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
            raise ValueError("a loss expression trains on the JAX backend only")
        return super().fit(d, structure, seed)

    def _fit_general(self, d, y, seed):
        """`recipes.MLP._fit_general` with the Level-1 trainer and loss."""
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
                case_loss=self.loss(
                    jax.numpy, self._trajectory(jax.numpy), self._groups()
                ),
            )
            leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(params)]
            final = float(
                np.mean((np.asarray(apply(params, f)) - z) ** 2 * gw[None, :]) * gw.size
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


class LossEnsemble(recipes.Ensemble):
    """`recipes.Ensemble` whose members are `LossMLP`s."""

    def __init__(self, members, family, settings, loss):
        super().__init__(members, family, settings)
        self.loss = loss

    def fit(self, d, structure, seed):
        self.members, stats = [], []
        for i in range(self.k):
            member = dict(self.settings)
            member["steps"] = member["steps"] // self.k
            m = LossMLP(self.family, member, self.loss)
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


def build(family, settings, loss):
    """The untrained Level-1 model a compiled recipe and a loss name: the MLP
    and DeepONet families only (`recipes.build` for everything else)."""
    if family not in ("mlp", "deeponet"):
        raise ValueError("only the mlp and deeponet families train a loss expression")
    if settings["ensemble_members"] == 1:
        return LossMLP(family, settings, loss)
    return LossEnsemble(settings["ensemble_members"], family, settings, loss)
