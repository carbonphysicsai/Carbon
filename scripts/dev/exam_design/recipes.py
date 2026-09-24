"""Surrogate recipes for the battery exam-design challenge (JAX, CPU or GPU).

Every recipe trains on TRAIN v1 only and returns predictions in the challenge's
output schema.

**Construction choices** (declared, not physics evidence). Two structural
choices are applied after the network, and passing a gate because of them
establishes nothing beyond the choice itself:

* ``V(0)`` is set from the **published OCV table**. The reference's first sample
  is a zero-current rest voltage that sits 0.003-0.44 mV *below* OCV (small
  internal side-reaction currents; measured), so this choice carries that
  error rather than removing it;
* ``T(0) = T_amb``, which the reference satisfies exactly.

No output is clamped after the fact. Clamping voltage to the cycler window
would hide a model that predicts an impossible voltage; the gates see raw
predictions.

Two *representation* choices, also declared, are made inside training:

* **Soft voltage ceiling** (all MLP recipes except ``mlp_raw``): the network
  predicts ``z`` in volts and the head returns
  ``V = V_max - softplus(k (V_max - z)) / k`` with ``k = 200 /V`` (a ~5 mV
  transition). Well below 4.2 V it is the identity; it can never exceed 4.2 V.
  It is trained end to end on the exact inverse of the reference, so it is an
  architecture choice rather than a post-hoc clamp. The protocol's cycler holds
  V <= 4.2 V; passing ``voltage_ceiling`` because of this head is not physics
  evidence. ``mlp_raw`` keeps an unconstrained head so the study measures what
  the gate rejects. Tried first on 44 cases and rejected: a log-gap head and a
  logistic window head both generalized badly (predictions collapsing to the
  2.5 V floor, voltage error 2-4x worse), because most training cases sit on the
  4.2 V hold and the representation made that a huge target range.
* **Capacity as cycle-1 capacity plus fade**: targets are ``Q_1`` and
  ``Q_1 - Q_k``; predicting each ``Q_k`` independently put errors of the size
  of the whole 30-cycle fade signal into the outputs.

Recipes (the role each plays in the study is fixed in the specification):

* ``knn``        simple baseline - inverse-distance k-nearest-neighbour.
* ``mlp``        competent learned baseline - MLP on normalized inputs.
* ``mlp_plus``   candidate intended to improve - Arrhenius and log-rate features,
                 PCA trajectory heads, weight decay, longer cosine schedule.
* ``mlp_plus_localized`` localized-regression control - ``mlp_plus`` with
                 important-region training cases down-weighted to 0.1.

The optimizer is plain Adam(W) written here: the pinned image carries JAX and
no optimizer library, and adding one would widen the overlay for no gain.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import numpy as np

from scripts.dev.exam_design.battery_reference import SPEC

BOUNDS = np.array([SPEC["input_bounds"][k] for k in ("c1", "c2", "t_amb_c", "soc0")], dtype=float)
V_MIN, V_MAX = SPEC["v_min"], SPEC["v_max"]


@dataclass
class Data:
    x: np.ndarray        # (n, 4) raw inputs c1, c2, t_amb_c, soc0
    v: np.ndarray        # (n, G)
    t: np.ndarray        # (n, G)
    eta: np.ndarray      # (n,)
    q: np.ndarray        # (n, K)
    important: np.ndarray  # (n,) bool
    case_ids: list

    @staticmethod
    def from_records(recs: list[dict], important_fn=None) -> "Data":
        x = np.array([[r["inputs"][k] for k in ("c1", "c2", "t_amb_c", "soc0")] for r in recs], float)
        o = [r["outputs"] for r in recs]
        imp = np.array([bool(important_fn(r)) if important_fn else False for r in recs])
        return Data(x, np.array([a["voltage_v"] for a in o]), np.array([a["temperature_c"] for a in o]),
                    np.array([a["plating_margin_v"] for a in o]), np.array([a["capacity_ah"] for a in o]), imp,
                    [r["case_id"] for r in recs])


def unit(x: np.ndarray) -> np.ndarray:
    return (x - BOUNDS[:, 0]) / (BOUNDS[:, 1] - BOUNDS[:, 0])


def features(x: np.ndarray, rich: bool) -> np.ndarray:
    u = unit(x)
    if not rich:
        return u
    tk = x[:, 2] + 273.15
    arr = (1000.0 / tk - 1000.0 / 313.15) / (1000.0 / 278.15 - 1000.0 / 313.15)
    lc1 = (np.log(x[:, 0]) - np.log(0.5)) / (np.log(2.0) - np.log(0.5))
    lc2 = (np.log(x[:, 1]) - np.log(0.2)) / (np.log(1.0) - np.log(0.2))
    return np.column_stack([u, arr, lc1, lc2, u[:, 0] * arr, u[:, 3] * u[:, 0]])


class Structure:
    """Declared construction choices shared by every recipe (initial values only; no clamping)."""

    def __init__(self, ocv_soc: np.ndarray, ocv_v: np.ndarray):
        self.ocv_soc, self.ocv_v = np.asarray(ocv_soc, float), np.asarray(ocv_v, float)

    def apply(self, x, v_rest, t_rest, eta, q) -> dict:
        # Construction choices only (see module docstring): no clamping of any output.
        v0 = np.interp(x[:, 3], self.ocv_soc, self.ocv_v)
        v = np.column_stack([v0, v_rest])
        t = np.column_stack([x[:, 2], x[:, 2][:, None] + t_rest])
        return {"v": v, "t": t, "eta": eta, "q": q}


def to_preds(out: dict, case_ids: list) -> dict:
    return {c: {"voltage_v": out["v"][i].tolist(), "temperature_c": out["t"][i].tolist(),
                "plating_margin_v": float(out["eta"][i]), "capacity_ah": out["q"][i].tolist()}
            for i, c in enumerate(case_ids)}


V_GAP_FLOOR = 1e-6  # V; training targets are clipped this far inside the [V_min, V_max] window


SOFT_K = 200.0  # 1/V; sharpness of the soft ceiling (width ~5 mV)


def _to_logit(v: np.ndarray) -> np.ndarray:
    """Inverse of the soft-ceiling head: z such that V_max - softplus(k (V_max - z)) / k = v."""
    a = SOFT_K * np.maximum(V_MAX - v, V_GAP_FLOOR)
    log_expm1 = np.where(a > 30.0, a + np.log1p(-np.exp(-np.minimum(a, 700.0))), np.log(np.expm1(np.minimum(a, 30.0))))
    return V_MAX - log_expm1 / SOFT_K


def _from_logit(z: np.ndarray) -> np.ndarray:
    return V_MAX - np.logaddexp(0.0, SOFT_K * (V_MAX - z)) / SOFT_K


def _targets(d: Data, bounded_v: bool = False) -> np.ndarray:
    v = _to_logit(d.v[:, 1:]) if bounded_v else d.v[:, 1:]
    q = np.column_stack([d.q[:, :1], d.q[:, :1] - d.q[:, 1:]])  # Q_1, then fade Q_1 - Q_k
    return np.column_stack([v, d.t[:, 1:] - d.x[:, 2:3], d.eta[:, None], q])


def _split(y: np.ndarray, g: int, bounded_v: bool = False):
    n1 = g - 1
    v = _from_logit(y[:, :n1]) if bounded_v else y[:, :n1]
    qf = y[:, 2 * n1 + 1:]
    q = np.column_stack([qf[:, :1], qf[:, :1] - qf[:, 1:]])
    return v, y[:, n1:2 * n1], y[:, 2 * n1], q


class KNN:
    name = "knn"

    def __init__(self, k: int = 5):
        self.k = k

    def fit(self, d: Data, structure: Structure, seed: int = 0) -> dict:
        self.u, self.y, self.g, self.s = unit(d.x), _targets(d), d.v.shape[1], structure
        return {"seconds": 0.0, "params_sha256": hashlib.sha256(self.y.tobytes()).hexdigest()}

    def predict(self, x: np.ndarray) -> dict:
        dist = np.linalg.norm(unit(x)[:, None, :] - self.u[None], axis=2)
        idx = np.argsort(dist, axis=1)[:, : self.k]
        w = 1.0 / (np.take_along_axis(dist, idx, 1) + 1e-9)
        w /= w.sum(1, keepdims=True)
        y = np.einsum("nk,nkd->nd", w, self.y[idx])
        return self.s.apply(x, *_split(y, self.g))


class MLP:
    """``mlp`` and ``mlp_plus`` share this class; the config distinguishes them."""

    def __init__(self, name="mlp", width=128, depth=3, steps=3000, lr=3e-3, wd=0.0, rich=False, pca=0,
                 important_weight=1.0, bounded_v=True):
        self.name, self.width, self.depth, self.steps, self.lr, self.wd = name, width, depth, steps, lr, wd
        self.rich, self.pca, self.important_weight, self.bounded_v = rich, pca, important_weight, bounded_v

    def config(self) -> dict:
        return {k: getattr(self, k) for k in ("name", "width", "depth", "steps", "lr", "wd", "rich", "pca",
                                               "important_weight", "bounded_v")}

    def _encode(self, y: np.ndarray) -> np.ndarray:
        if not self.pca:
            return (y - self.mu) / self.sd
        v, t, eta, q = y[:, :self.g - 1], y[:, self.g - 1:2 * (self.g - 1)], y[:, 2 * (self.g - 1)], y[:, 2 * (self.g - 1) + 1:]
        cv = (v - self.vm) @ self.pv.T
        ct = (t - self.tm) @ self.pt.T
        z = np.column_stack([cv, ct, eta[:, None], q])
        return (z - self.zmu) / self.zsd

    def _decode(self, z: np.ndarray) -> np.ndarray:
        if not self.pca:
            return z * self.sd + self.mu
        z = z * self.zsd + self.zmu
        p = self.pca
        v = z[:, :p] @ self.pv + self.vm
        t = z[:, p:2 * p] @ self.pt + self.tm
        return np.column_stack([v, t, z[:, 2 * p], z[:, 2 * p + 1:]])

    def _group_weights(self, dims: int) -> np.ndarray:
        # Each score component carries equal total weight in the loss, as in the score.
        k = self.q_dim
        n_traj = self.pca if self.pca else self.g - 1
        w = np.concatenate([np.full(n_traj, 1 / n_traj), np.full(n_traj, 1 / n_traj), [1.0], np.full(k, 1 / k)])
        assert w.size == dims
        return w

    def fit(self, d: Data, structure: Structure, seed: int) -> dict:
        import jax
        import jax.numpy as jnp

        self.s, self.g, self.q_dim = structure, d.v.shape[1], d.q.shape[1]
        y = _targets(d, self.bounded_v)
        self.mu, self.sd = y.mean(0), y.std(0) + 1e-9
        if self.pca:
            n1 = self.g - 1
            v, t = y[:, :n1], y[:, n1:2 * n1]
            self.vm, self.tm = v.mean(0), t.mean(0)
            self.pv = np.linalg.svd(v - self.vm, full_matrices=False)[2][: self.pca]
            self.pt = np.linalg.svd(t - self.tm, full_matrices=False)[2][: self.pca]
            v2, t2, eta, q = v, t, y[:, 2 * n1], y[:, 2 * n1 + 1:]
            z = np.column_stack([(v2 - self.vm) @ self.pv.T, (t2 - self.tm) @ self.pt.T, eta[:, None], q])
            self.zmu, self.zsd = z.mean(0), z.std(0) + 1e-9
        z = self._encode(y).astype(np.float32)
        f = features(d.x, self.rich).astype(np.float32)
        sw = np.where(d.important, self.important_weight, 1.0).astype(np.float32)
        gw = self._group_weights(z.shape[1]).astype(np.float32)
        key = jax.random.PRNGKey(seed)
        sizes = [f.shape[1]] + [self.width] * self.depth + [z.shape[1]]
        params = []
        for a, b in zip(sizes[:-1], sizes[1:]):
            key, k1 = jax.random.split(key)
            params.append((jax.random.normal(k1, (a, b), jnp.float32) * jnp.sqrt(2.0 / a), jnp.zeros((b,), jnp.float32)))

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
                    lambda w, a, b: w - lr * ((a / (1 - b1 ** t)) / (jnp.sqrt(b / (1 - b2 ** t)) + eps) + wd * w),
                    p, m, v)
                return (p, m, v), None

            (p, m, v), _ = jax.lax.scan(step, (p, m, v), jnp.arange(steps, dtype=jnp.float32))
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
        return {"compile_s": t1 - t0, "train_s": t2 - t1, "final_loss": float(final),
                "params_sha256": hashlib.sha256(blob).hexdigest(), "n_params": int(sum(w.size + b.size for w, b in self.params))}

    def predict(self, x: np.ndarray) -> dict:
        import jax.numpy as jnp

        f = features(x, self.rich).astype(np.float32)
        z = np.asarray(self._net([(jnp.asarray(w), jnp.asarray(b)) for w, b in self.params], jnp.asarray(f)), float)
        return self.s.apply(x, *_split(self._decode(z), self.g, self.bounded_v))


def make(name: str):
    if name == "knn":
        return KNN(5)
    if name == "mlp":
        # Matched budget with the candidate: same width, depth, optimizer steps and learning rate.
        return MLP("mlp", width=256, depth=3, steps=6000, lr=2e-3)
    if name == "mlp_plus":
        return MLP("mlp_plus", width=256, depth=3, steps=6000, lr=2e-3, wd=1e-4, rich=True, pca=16)
    if name == "mlp_raw":
        # Unconstrained voltage head: kept to measure what the voltage_ceiling gate rejects.
        return MLP("mlp_raw", width=256, depth=3, steps=6000, lr=2e-3, bounded_v=False)
    if name == "mlp_plus_localized":
        return MLP("mlp_plus_localized", width=256, depth=3, steps=6000, lr=2e-3, wd=1e-4, rich=True, pca=16,
                   important_weight=0.1)
    raise KeyError(name)


RECIPES = ("knn", "mlp", "mlp_raw", "mlp_plus", "mlp_plus_localized")
