"""Carbon's battery recipe implementations (KEEP the campaign math, WRAP it).

Promoted from `scripts/dev/exam_design/recipes.py`. The campaign's recipes
(kNN, MLP, the PCA-headed, raw, localized, half-TRAIN and ensemble variants)
are bit-identical to the research recipes on the same backend and seed; a
test holds that. Every other setting of the battery vocabulary - optax
optimizers and curves, minibatches, extra losses, averaging, the L-BFGS polish,
float64, curriculum, and the battery DeepONet - trains through
`training.train`. Only a compiled `BatteryRecipe` configures a model here, and
the seed is Carbon's reconstruction randomness, never a miner's.

Declared construction choices (not physics evidence; passing a gate because of
one establishes nothing beyond the choice itself):

* ``T(0) = T_amb``, which the reference satisfies exactly (always on);
* ``ocv_initial_voltage``: ``V(0)`` from the published OCV table. The
  reference's first sample is a zero-current rest voltage 0.003-0.44 mV below
  OCV, so the choice carries that error rather than removing it;
* ``bounded_voltage_head``: the network predicts ``z`` in volts and the head
  returns ``V = V_max - softplus(k (V_max - z)) / k`` with ``k = 200 /V``. It
  can never exceed 4.2 V, and it is trained end to end on the exact inverse,
  so it is an architecture choice, not a post-hoc clamp. Off, the head is
  unconstrained: the raw control the ``voltage_ceiling`` gate is meant to see;
* ``capacity_fade_head``: targets are ``Q_1`` and ``Q_1 - Q_k``. Off, each
  checkpoint capacity is predicted directly.

No output is clamped after the fact: the gates see raw predictions.
"""

from __future__ import annotations

import hashlib
import itertools
import time

import numpy as np

from .domain import INPUT_BOUNDS, INPUTS, V_MAX

BOUNDS = np.array([INPUT_BOUNDS[k] for k in INPUTS], dtype=float)
V_GAP_FLOOR = 1e-6  # V; training targets are clipped this far inside V_max
SOFT_K = 200.0  # 1/V; sharpness of the bounded head (width about 5 mV)


def unit(x):
    return (x - BOUNDS[:, 0]) / (BOUNDS[:, 1] - BOUNDS[:, 0])


def features(x, rich):
    u = unit(x)
    if not rich:
        return u
    tk = x[:, 2] + 273.15
    arr = (1000.0 / tk - 1000.0 / 313.15) / (1000.0 / 278.15 - 1000.0 / 313.15)
    lc1 = (np.log(x[:, 0]) - np.log(0.5)) / (np.log(2.0) - np.log(0.5))
    lc2 = (np.log(x[:, 1]) - np.log(0.2)) / (np.log(1.0) - np.log(0.2))
    return np.column_stack([u, arr, lc1, lc2, u[:, 0] * arr, u[:, 3] * u[:, 0]])


def _to_logit(v):
    """Inverse of the bounded head: z with V_max - softplus(k (V_max - z)) / k = v."""
    a = SOFT_K * np.maximum(V_MAX - v, V_GAP_FLOOR)
    log_expm1 = np.where(
        a > 30.0,
        a + np.log1p(-np.exp(-np.minimum(a, 700.0))),
        np.log(np.expm1(np.minimum(a, 30.0))),
    )
    return V_MAX - log_expm1 / SOFT_K


def _from_logit(z):
    return V_MAX - np.logaddexp(0.0, SOFT_K * (V_MAX - z)) / SOFT_K


class Layout:
    """Target layout: which columns the network predicts, and their inverse."""

    def __init__(self, g, k, *, bounded_v, predict_v0, fade):
        self.g, self.k = g, k
        self.bounded_v, self.predict_v0, self.fade = bounded_v, predict_v0, fade
        self.nv = g if predict_v0 else g - 1
        self.nt = g - 1

    def targets(self, d):
        v = d.v if self.predict_v0 else d.v[:, 1:]
        v = _to_logit(v) if self.bounded_v else v
        if self.fade:
            q = np.column_stack([d.q[:, :1], d.q[:, :1] - d.q[:, 1:]])
        else:
            q = d.q
        return np.column_stack([v, d.t[:, 1:] - d.x[:, 2:3], d.eta[:, None], q])

    def split(self, y):
        nv, nt = self.nv, self.nt
        v = _from_logit(y[:, :nv]) if self.bounded_v else y[:, :nv]
        qf = y[:, nv + nt + 1 :]
        q = np.column_stack([qf[:, :1], qf[:, :1] - qf[:, 1:]]) if self.fade else qf
        return v, y[:, nv : nv + nt], y[:, nv + nt], q


class Structure:
    """Initial values from declared construction choices; never clamps."""

    def __init__(self, ocv_soc, ocv_v):
        self.ocv_soc = np.asarray(ocv_soc, float)
        self.ocv_v = np.asarray(ocv_v, float)

    def apply(self, x, v, t_rest, eta, q, *, predict_v0=False):
        if not predict_v0:
            v0 = np.interp(x[:, 3], self.ocv_soc, self.ocv_v)
            v = np.column_stack([v0, v])
        t = np.column_stack([x[:, 2], x[:, 2][:, None] + t_rest])
        return {"v": v, "t": t, "eta": eta, "q": q}


def to_predictions(out, case_ids):
    return {
        c: {
            "voltage_v": out["v"][i].tolist(),
            "temperature_c": out["t"][i].tolist(),
            "plating_margin_v": float(out["eta"][i]),
            "capacity_ah": out["q"][i].tolist(),
        }
        for i, c in enumerate(case_ids)
    }


class KNN:
    def __init__(self, neighbours, train_fraction=1.0):
        self.k, self.fraction = neighbours, train_fraction

    def fit(self, d, structure, seed):
        d = train_subset(d, self.fraction, seed)
        self.layout = Layout(
            d.v.shape[1], d.q.shape[1], bounded_v=False, predict_v0=False, fade=True
        )
        self.u, self.y, self.s = unit(d.x), self.layout.targets(d), structure
        return {
            "seconds": 0.0,
            "params_sha256": hashlib.sha256(self.y.tobytes()).hexdigest(),
        }

    def predict(self, x):
        dist = np.linalg.norm(unit(x)[:, None, :] - self.u[None], axis=2)
        idx = np.argsort(dist, axis=1)[:, : self.k]
        w = 1.0 / (np.take_along_axis(dist, idx, 1) + 1e-9)
        w /= w.sum(1, keepdims=True)
        y = np.einsum("nk,nkd->nd", w, self.y[idx])
        return self.s.apply(x, *self.layout.split(y))


#: The general surfaces at the values the campaign's written-out loop implements.
CLASSIC = {
    "optimizer_family": "adam",
    "learning_rate_curve": "cosine",
    "warmup_steps": 0,
    "min_learning_rate_ratio": 0.0,
    "weight_decay_mask": "all",
    "clip_norm": 0.0,
    "beta1": 0.9,
    "beta2": 0.999,
    "adam_epsilon": 1e-8,
    "microbatches": 1,
    "relative_loss": False,
    "time_weighting": "uniform",
    "h1_weight": 0.0,
    "h2_weight": 0.0,
    "spectral_weight": 0.0,
    "polish_steps": 0,
    "tail_averaging": 0.0,
    "inference_weights": "params",
    "precision": "float32",
    "curriculum": "none",
    "hard_example_weight": 0.0,
    "activation": "gelu",
    "normalization": "none",
    "initialization": "he_normal",
}


def train_subset(d, fraction, seed):
    """A seeded subset of TRAIN, exactly as the campaign's recipes drew it."""
    if fraction >= 1.0:
        return d
    count = int(len(d.case_ids) * fraction)
    return d.take(
        np.sort(np.random.default_rng(seed).permutation(len(d.case_ids))[:count])
    )


class MLP:
    """A learned battery recipe: the MLP or the battery DeepONet.

    With every general surface at its `CLASSIC` value, the MLP trains with the
    campaign's written-out full-batch Adam(W) and cosine decay, bit-identical to
    the research recipe; any other setting trains through `training.train`.
    """

    def __init__(self, family, settings):
        s = dict(settings)
        self.family, self.settings = family, s
        self.width, self.steps = s["width"], s["steps"]
        self.depth = s["depth"] if family == "mlp" else s["deeponet_depth"]
        self.lr, self.wd = s["learning_rate"], s["weight_decay"]
        self.rich = s["arrhenius_features"]
        self.pca = s.get("trajectory_components", 0)
        self.bounded_v = s["bounded_voltage_head"]
        self.predict_v0 = not s["ocv_initial_voltage"]
        self.fade = s["capacity_fade_head"]
        self.important_weight = s["important_region_weight"]
        self.fraction = s["train_fraction"]

    def _classic(self, cases):
        s = self.settings
        return (
            self.family == "mlp"
            and all(s[k] == v for k, v in CLASSIC.items())
            and s["batch_size"] >= cases
        )

    def _encode(self, y):
        if not self.pca:
            return (y - self.mu) / self.sd
        nv, nt = self.layout.nv, self.layout.nt
        v, t = y[:, :nv], y[:, nv : nv + nt]
        eta, q = y[:, nv + nt], y[:, nv + nt + 1 :]
        cv = (v - self.vm) @ self.pv.T
        ct = (t - self.tm) @ self.pt.T
        z = np.column_stack([cv, ct, eta[:, None], q])
        return (z - self.zmu) / self.zsd

    def _decode(self, z):
        if not self.pca:
            return z * self.sd + self.mu
        z = z * self.zsd + self.zmu
        p = self.pca
        v = z[:, :p] @ self.pv + self.vm
        t = z[:, p : 2 * p] @ self.pt + self.tm
        return np.column_stack([v, t, z[:, 2 * p], z[:, 2 * p + 1 :]])

    def _group_weights(self, dims):
        # Each score component carries equal total weight in the loss.
        k = self.layout.k
        nv = self.pca if self.pca else self.layout.nv
        nt = self.pca if self.pca else self.layout.nt
        w = np.concatenate(
            [np.full(nv, 1 / nv), np.full(nt, 1 / nt), [1.0], np.full(k, 1 / k)]
        )
        if w.size != dims:
            raise ValueError("target layout and loss weights disagree")
        return w

    def fit(self, d, structure, seed):
        d = train_subset(d, self.fraction, seed)
        self.s = structure
        self.layout = Layout(
            d.v.shape[1],
            d.q.shape[1],
            bounded_v=self.bounded_v,
            predict_v0=self.predict_v0,
            fade=self.fade,
        )
        y = self.layout.targets(d)
        self.mu, self.sd = y.mean(0), y.std(0) + 1e-9
        if self.pca:
            nv, nt = self.layout.nv, self.layout.nt
            v, t = y[:, :nv], y[:, nv : nv + nt]
            self.vm, self.tm = v.mean(0), t.mean(0)
            self.pv = np.linalg.svd(v - self.vm, full_matrices=False)[2][: self.pca]
            self.pt = np.linalg.svd(t - self.tm, full_matrices=False)[2][: self.pca]
            eta, q = y[:, nv + nt], y[:, nv + nt + 1 :]
            z = np.column_stack(
                [(v - self.vm) @ self.pv.T, (t - self.tm) @ self.pt.T, eta[:, None], q]
            )
            self.zmu, self.zsd = z.mean(0), z.std(0) + 1e-9
        self.classic = self._classic(len(d.case_ids))
        if self.classic:
            return self._fit_classic(d, y, seed)
        return self._fit_general(d, y, seed)

    def _fit_classic(self, d, y, seed):
        import jax
        import jax.numpy as jnp

        z = self._encode(y).astype(np.float32)
        f = features(d.x, self.rich).astype(np.float32)
        sw = np.where(d.important, self.important_weight, 1.0).astype(np.float32)
        gw = self._group_weights(z.shape[1]).astype(np.float32)
        key = jax.random.PRNGKey(seed)
        sizes = [f.shape[1]] + [self.width] * self.depth + [z.shape[1]]
        params = []
        for a, b in itertools.pairwise(sizes):
            key, k1 = jax.random.split(key)
            params.append(
                (
                    jax.random.normal(k1, (a, b), jnp.float32) * jnp.sqrt(2.0 / a),
                    jnp.zeros((b,), jnp.float32),
                )
            )

        def net(p, xx):
            h = xx
            for w, bb in p[:-1]:
                h = jax.nn.gelu(h @ w + bb)
            w, bb = p[-1]
            return h @ w + bb

        def loss(p, xx, yy):
            r = (net(p, xx) - yy) ** 2
            return jnp.sum(sw[:, None] * r * gw[None, :]) / jnp.sum(sw)

        steps, lr0, wd = self.steps, self.lr, self.wd
        b1, b2, eps = 0.9, 0.999, 1e-8

        @jax.jit
        def train(p, xx, yy):
            m = jax.tree_util.tree_map(jnp.zeros_like, p)
            v = jax.tree_util.tree_map(jnp.zeros_like, p)

            def step(c, i):
                p, m, v = c
                g = jax.grad(loss)(p, xx, yy)
                lr = lr0 * 0.5 * (1 + jnp.cos(jnp.pi * i / steps))
                m = jax.tree_util.tree_map(lambda a, b: b1 * a + (1 - b1) * b, m, g)
                v = jax.tree_util.tree_map(lambda a, b: b2 * a + (1 - b2) * b * b, v, g)
                t = i + 1.0
                p = jax.tree_util.tree_map(
                    lambda w, a, b: (
                        w
                        - lr
                        * (
                            (a / (1 - b1**t)) / (jnp.sqrt(b / (1 - b2**t)) + eps)
                            + wd * w
                        )
                    ),
                    p,
                    m,
                    v,
                )
                return (p, m, v), None

            (p, m, v), _ = jax.lax.scan(
                step, (p, m, v), jnp.arange(steps, dtype=jnp.float32)
            )
            return p, loss(p, xx, yy)

        t0 = time.perf_counter()
        compiled = train.lower(params, f, z).compile()
        t1 = time.perf_counter()
        p, final = compiled(params, f, z)
        p = jax.block_until_ready(p)
        t2 = time.perf_counter()
        self.params = [(np.asarray(w), np.asarray(b)) for w, b in p]
        self._net = net
        blob = b"".join(w.tobytes() + b.tobytes() for w, b in self.params)
        return {
            "compile_s": t1 - t0,
            "train_s": t2 - t1,
            "final_loss": float(final),
            "params_sha256": hashlib.sha256(blob).hexdigest(),
            "n_params": int(sum(w.size + b.size for w, b in self.params)),
        }

    def _network(self, jax, dtype, n_in, n_out):
        """(init, apply) for this family, in the requested precision."""
        from .domain import GRID_STEP_S
        from .training import apply_stack, dense_stack

        s = self.settings
        act, norm, init_name = s["activation"], s["normalization"], s["initialization"]
        width, depth = self.width, self.depth
        if self.family == "mlp":

            def init(key):
                return dense_stack(
                    jax, key, [n_in] + [width] * depth + [n_out], init_name, dtype
                )

            def apply(p, f):
                return apply_stack(jax, p, f, act, norm)

            return init, apply
        jnp = jax.numpy
        basis, lay = s["basis_functions"], self.layout
        times = np.arange(lay.g) * GRID_STEP_S / (GRID_STEP_S * (lay.g - 1))
        tv = jnp.asarray((times if lay.predict_v0 else times[1:])[:, None], dtype)
        tt = jnp.asarray(times[1:][:, None], dtype)
        heads = 2 * basis + 1 + lay.k

        def init(key):
            key, branch = dense_stack(
                jax, key, [n_in] + [width] * depth + [heads], init_name, dtype
            )
            key, trunk = dense_stack(
                jax, key, [1] + [width] * depth + [2 * basis], init_name, dtype
            )
            bias = jnp.zeros((lay.nv + lay.nt,), dtype)
            return key, {"branch": branch, "trunk": trunk, "bias": bias}

        def apply(p, f):
            b = apply_stack(jax, p["branch"], f, act, norm)
            v = b[:, :basis] @ apply_stack(jax, p["trunk"], tv, act, norm)[:, :basis].T
            t = (
                b[:, basis : 2 * basis]
                @ apply_stack(jax, p["trunk"], tt, act, norm)[:, basis:].T
            )
            traj = jnp.concatenate([v, t], axis=1) + p["bias"]
            return jnp.concatenate([traj, b[:, 2 * basis :]], axis=1)

        return init, apply

    def _trajectory(self, jnp):
        """Normalized voltage and temperature trajectories from outputs z."""
        nv, nt = self.layout.nv, self.layout.nt
        if not self.pca:
            return lambda z: (z[:, :nv], z[:, nv : nv + nt])
        zsd, zmu = jnp.asarray(self.zsd), jnp.asarray(self.zmu)
        pv, pt = jnp.asarray(self.pv), jnp.asarray(self.pt)
        vm, tm = jnp.asarray(self.vm), jnp.asarray(self.tm)
        mu, sd, p = jnp.asarray(self.mu), jnp.asarray(self.sd), self.pca

        def trajectory(z):
            c = z * zsd + zmu
            v = (c[:, :p] @ pv + vm - mu[:nv]) / sd[:nv]
            t = (c[:, p : 2 * p] @ pt + tm - mu[nv : nv + nt]) / sd[nv : nv + nt]
            return v, t

        return trajectory

    def _fit_general(self, d, y, seed):
        import jax

        from .training import train

        self.x64 = self.settings["precision"] == "float64"
        dtype = np.float64 if self.x64 else np.float32
        t0 = time.perf_counter()
        with jax.enable_x64(self.x64):
            z = self._encode(y).astype(dtype)
            f = features(d.x, self.rich).astype(dtype)
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
            )
            leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(params)]
            final = float(
                np.mean((np.asarray(apply(params, f)) - z) ** 2 * gw[None, :]) * gw.size
            )
        self.params, self._apply = params, apply
        blob = b"".join(a.tobytes() for a in leaves)
        return {
            "compile_s": 0.0,
            "train_s": time.perf_counter() - t0,
            "final_loss": final,
            "params_sha256": hashlib.sha256(blob).hexdigest(),
            "n_params": int(sum(a.size for a in leaves)),
        }

    def predict(self, x):
        import jax
        import jax.numpy as jnp

        if self.classic:
            f = features(x, self.rich).astype(np.float32)
            z = np.asarray(
                self._net(
                    [(jnp.asarray(w), jnp.asarray(b)) for w, b in self.params],
                    jnp.asarray(f),
                ),
                float,
            )
        else:
            with jax.enable_x64(self.x64):
                dtype = np.float64 if self.x64 else np.float32
                f = features(x, self.rich).astype(dtype)
                z = np.asarray(self._apply(self.params, jnp.asarray(f)), float)
        return self.s.apply(
            x, *self.layout.split(self._decode(z)), predict_v0=self.predict_v0
        )


class Ensemble:
    """Members splitting the step budget equally; predictions averaged."""

    def __init__(self, members, family, settings):
        self.k, self.family, self.settings = members, family, dict(settings)

    def fit(self, d, structure, seed):
        self.members, stats = [], []
        for i in range(self.k):
            member = dict(self.settings)
            member["steps"] = member["steps"] // self.k
            m = MLP(self.family, member)
            stats.append(m.fit(d, structure, seed=seed * 1000 + i))
            self.members.append(m)
        blob = "".join(s["params_sha256"] for s in stats).encode()
        return {
            "compile_s": sum(s["compile_s"] for s in stats),
            "train_s": sum(s["train_s"] for s in stats),
            "final_loss": float(np.mean([s["final_loss"] for s in stats])),
            "params_sha256": hashlib.sha256(blob).hexdigest(),
            "n_params": sum(s["n_params"] for s in stats),
        }

    def predict(self, x):
        outs = [m.predict(x) for m in self.members]
        return {k: np.mean([o[k] for o in outs], axis=0) for k in outs[0]}


def build(family, settings):
    """The untrained model a compiled recipe names. `compile.build_model` and
    the isolated practice worker both construct through this one function."""
    if family == "knn":
        return KNN(settings["neighbours"], settings["train_fraction"])
    if settings["ensemble_members"] == 1:
        return MLP(family, settings)
    return Ensemble(settings["ensemble_members"], family, settings)
