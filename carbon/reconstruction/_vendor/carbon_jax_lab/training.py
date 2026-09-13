"""Fixed-plan, trajectory-split training. No official scoring or model selection.

The trainer never receives evaluation labels. Reporting happens through a
separate audit method and cannot alter the training plan or select a checkpoint.
This logical API separation is not an OS sandbox or a hostile-host guarantee.
"""

from __future__ import annotations

import hashlib
import math
import time
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from .config import ModelConfig, TaskConfig, TrainConfig, identity
from .data import Trajectories, assert_case_disjoint
from .models import Operator, parameter_count
from .optim import adamw, all_finite, init_adam, learning_rate


class NonFiniteTrainingError(FloatingPointError):
    pass


class CancelledTraining(RuntimeError):
    pass


def _root_key(runtime_key_material):
    """Consume every bit of an opaque 32-byte Carbon backend seed."""
    if type(runtime_key_material) is not bytes or len(runtime_key_material) != 32:
        raise ValueError("runtime_key_material must be exactly 32 bytes")
    key = jax.random.PRNGKey(0)
    for offset in range(0, 32, 4):
        word = int.from_bytes(runtime_key_material[offset : offset + 4], "big")
        key = jax.random.fold_in(key, word)
    return key


class TrainState(NamedTuple):
    params: object
    optimizer: object
    ema: object
    rng: jax.Array
    step: jax.Array


def spectral_derivative(u, L, order=1):
    n = u.shape[-1]
    k = 2 * jnp.pi * jnp.fft.rfftfreq(n, d=L / n)
    factor = (1j * k) ** order
    return jnp.fft.irfft(jnp.fft.rfft(u, axis=-1) * factor, n=n, axis=-1)


def conservative_advection(u, L):
    n = u.shape[-1]
    k = jnp.arange(n // 2 + 1)
    mask = k < n / 3
    v = jnp.fft.irfft(jnp.fft.rfft(u) * mask, n=n)
    flux_hat = jnp.fft.rfft(0.5 * v * v) * mask
    freq = 2 * jnp.pi * jnp.fft.rfftfreq(n, d=L / n)
    return jnp.fft.irfft(1j * freq * flux_hat, n=n)


class Predictor:
    def __init__(self, model_config, task_config, u_scale):
        self.model = Operator(model_config)
        self.task = task_config
        if not np.isfinite(u_scale) or u_scale <= 0:
            raise ValueError("normalization scale")
        self.u_scale = float(u_scale)

    def __call__(self, params, u0, nu, t, positions):
        b, n = u0.shape
        if nu.shape != (b,) or t.shape != (b,):
            raise ValueError("nu and t must have shape [B]")
        features = jnp.stack(
            (
                u0 / self.u_scale,
                jnp.broadcast_to(nu[:, None] / self.task.nu_scale, (b, n)),
                jnp.broadcast_to(t[:, None] / self.task.time_scale, (b, n)),
            ),
            axis=-1,
        )
        raw = self.model.apply(
            params, features, positions[:, None] / self.task.domain_length
        )[..., 0]
        pred = self.u_scale * raw
        if self.task.hard_initial_condition:
            pred = u0 + (t[:, None] / self.task.time_scale) * pred
        if self.task.enforce_mean:
            pred = (
                pred
                - jnp.mean(pred, axis=-1, keepdims=True)
                + jnp.mean(u0, axis=-1, keepdims=True)
            )
        return pred


class Trainer:
    def __init__(
        self,
        model_config: ModelConfig,
        task_config: TaskConfig,
        train_config: TrainConfig,
        data: Trajectories,
        *,
        runtime_key_material=None,
    ):
        if type(data) is not Trajectories or data.role != "train":
            raise ValueError("Trainer requires declared TRAIN trajectories only")
        if data.domain_length != task_config.domain_length:
            raise ValueError("domain mismatch")
        if data.times.max() > task_config.time_scale + 1e-12:
            raise ValueError("declared time range does not cover training times")
        if (
            model_config.kind == "haar_operator1d"
            and data.initial.shape[1] % 2**model_config.wavelet_levels
        ):
            raise ValueError("Haar resolution must be divisible by 2**wavelet_levels")
        self.model_config = model_config
        self.task_config = task_config
        self.config = train_config
        self.data = data
        self.contract_id = identity(model_config, task_config, train_config)
        self.u_scale = max(
            float(np.sqrt(np.mean(data.initial.astype(np.float64) ** 2))), 1e-8
        )
        self.predictor = Predictor(model_config, task_config, self.u_scale)
        if runtime_key_material is None:
            root = jax.random.PRNGKey(train_config.seed)
            self.runtime_key_digest = None
        else:
            root = _root_key(runtime_key_material)
            self.runtime_key_digest = hashlib.sha256(runtime_key_material).hexdigest()
        init_key, batch_key = jax.random.split(root)
        params = self.predictor.model.init(init_key)
        self.state = TrainState(
            params, init_adam(params), params, batch_key, jnp.array(0, dtype=jnp.int32)
        )
        self.arrays = tuple(
            jnp.asarray(a, dtype=jnp.float32)
            for a in (
                data.initial,
                data.viscosity,
                data.times,
                data.solution,
                data.positions,
            )
        )
        self.cast_max_abs = max(
            float(
                np.max(
                    np.abs(
                        a.astype(np.float64) - a.astype(np.float32).astype(np.float64)
                    )
                )
            )
            for a in data.arrays().values()
        )
        self.history = []
        self.timing = {
            "compile_seconds": 0.0,
            "train_execution_seconds": 0.0,
            "audit_seconds": 0.0,
        }
        self._compiled = None
        self._step_fn = jax.jit(self._make_step())

    def _loss(self, params, batch, positions, step):
        u0, nu, t, target = batch
        cfg = self.config
        task = self.task_config
        scale = self.u_scale
        pred = self.predictor(params, u0, nu, t, positions)
        difference = (pred - target) / scale
        per_sample = jnp.mean(difference * difference, axis=-1)
        if cfg.relative_loss:
            per_sample = per_sample / jnp.maximum(
                jnp.mean((target / scale) ** 2, axis=-1), 1e-6
            )
        data_loss = jnp.mean(per_sample)
        h1 = jnp.array(0.0, jnp.float32)
        pde = jnp.array(0.0, jnp.float32)
        if cfg.h1_weight:
            dx = spectral_derivative(pred - target, task.domain_length) * (
                task.domain_length / (2 * jnp.pi * scale)
            )
            h1 = jnp.mean(dx * dx)
        if cfg.pde_weight:
            _, ut = jax.jvp(
                lambda tt: self.predictor(params, u0, nu, tt, positions),
                (t,),
                (jnp.ones_like(t),),
            )
            residual = (
                ut
                + conservative_advection(pred, task.domain_length)
                - nu[:, None] * spectral_derivative(pred, task.domain_length, 2)
            )
            pde = jnp.mean((residual * task.time_scale / scale) ** 2)
        ramp = jnp.minimum(1.0, (step + 1) / max(1, cfg.physics_warmup_steps))
        total = data_loss + cfg.h1_weight * h1 + cfg.pde_weight * ramp * pde
        return total, jnp.stack((data_loss, h1, pde))

    def _make_step(self):
        cfg = self.config

        def step(state, arrays):
            u0, nu, t, y, x = arrays
            rng, casekey, timekey = jax.random.split(state.rng, 3)
            shape = (cfg.microbatches, cfg.batch_size)
            # Uniform trajectories, then uniform supplied times within trajectory.
            ci = jax.random.randint(casekey, shape, 0, u0.shape[0])
            ti = jax.random.randint(timekey, shape, 0, t.shape[1])
            batches = (u0[ci], nu[ci], t[ci, ti], y[ci, ti])
            zgrad = jax.tree.map(jnp.zeros_like, state.params)

            def accumulate(carry, batch):
                grad_sum, loss_sum, term_sum = carry
                (loss, terms), grad = jax.value_and_grad(self._loss, has_aux=True)(
                    state.params, batch, x, state.step
                )
                return (
                    jax.tree.map(jnp.add, grad_sum, grad),
                    loss_sum + loss,
                    term_sum + terms,
                ), None

            (grad, loss, terms), _ = jax.lax.scan(
                accumulate,
                (zgrad, jnp.array(0.0, jnp.float32), jnp.zeros((3,), jnp.float32)),
                batches,
            )
            grad = jax.tree.map(lambda g: g / cfg.microbatches, grad)
            loss = loss / cfg.microbatches
            terms = terms / cfg.microbatches
            lr = learning_rate(state.step, cfg)
            p, o, norm = adamw(
                state.params,
                grad,
                state.optimizer,
                lr,
                beta1=cfg.beta1,
                beta2=cfg.beta2,
                epsilon=cfg.adam_epsilon,
                weight_decay=cfg.weight_decay,
                clip_norm=cfg.clip_norm,
            )
            ema = jax.tree.map(
                lambda a, b: cfg.ema_decay * a + (1 - cfg.ema_decay) * b, state.ema, p
            )
            proposed = TrainState(p, o, ema, rng, state.step + 1)
            valid = (
                all_finite(proposed)
                & all_finite(grad)
                & jnp.isfinite(loss)
                & jnp.isfinite(norm)
            )
            # A failed step must not advance RNG, optimizer count, or parameter state.
            accepted = jax.tree.map(
                lambda new, old: jnp.where(valid, new, old), proposed, state
            )
            return accepted, {
                "loss": loss,
                "data_loss": terms[0],
                "h1_loss": terms[1],
                "pde_loss": terms[2],
                "grad_norm": norm,
                "learning_rate": lr,
                "finite": valid,
            }

        return step

    def compile(self):
        if self._compiled is None:
            start = time.perf_counter()
            self._compiled = self._step_fn.lower(self.state, self.arrays).compile()
            self.timing["compile_seconds"] += time.perf_counter() - start

    def fit(self, until_step=None, cancel=None, wall_budget_seconds=None):
        stop = self.config.steps if until_step is None else until_step
        if (
            type(stop) is not int
            or not int(self.state.step) <= stop <= self.config.steps
        ):
            raise ValueError("invalid stop step")
        if wall_budget_seconds is not None and (
            not math.isfinite(wall_budget_seconds) or wall_budget_seconds <= 0
        ):
            raise ValueError("wall budget")
        budget_started = time.perf_counter()
        self.compile()
        started = time.perf_counter()
        try:
            while int(self.state.step) < stop:
                if cancel is not None and cancel():
                    raise CancelledTraining("cancelled at an optimizer-step boundary")
                if (
                    wall_budget_seconds is not None
                    and time.perf_counter() - budget_started > wall_budget_seconds
                ):
                    raise CancelledTraining(
                        "research wall budget exhausted between steps"
                    )
                proposed, metrics = self._compiled(self.state, self.arrays)
                jax.block_until_ready((proposed, metrics))
                m = {k: float(v) for k, v in metrics.items() if k != "finite"}
                if not bool(metrics["finite"]):
                    raise NonFiniteTrainingError(
                        "nonfinite training step rejected; previous state retained"
                    )
                self.state = proposed
                self.history.append({"step": int(self.state.step), **m})
        finally:
            self.timing["train_execution_seconds"] += time.perf_counter() - started
        return self.state

    def audit(self, data: Trajectories, batch_size=32):
        if data.role not in ("audit", "validation"):
            raise ValueError("audit requires separately declared held-out data")
        assert_case_disjoint(self.data, data)
        if data.domain_length != self.task_config.domain_length:
            raise ValueError("audit domain mismatch")
        p = (
            self.state.params
            if self.config.inference_weights == "params"
            else self.state.ema
        )
        started = time.perf_counter()
        preds = predict_trajectories(self.predictor, p, data, batch_size)
        elapsed = time.perf_counter() - started
        self.timing["audit_seconds"] += elapsed
        diff = preds - data.solution
        denom = np.sqrt(np.sum(data.solution**2, axis=(1, 2)))
        rel = np.sqrt(np.sum(diff**2, axis=(1, 2))) / np.maximum(denom, 1e-12)
        mean_err = np.max(
            np.abs(preds.mean(-1) - data.initial.mean(-1)[:, None]), axis=1
        )
        overshoot = np.maximum(
            np.max(preds, axis=(1, 2)) - np.max(data.initial, axis=1), 0
        )
        undershoot = np.maximum(
            np.min(data.initial, axis=1) - np.min(preds, axis=(1, 2)), 0
        )
        return {
            "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
            "weights": self.config.inference_weights,
            "cases": len(data.initial),
            "mean_relative_l2": float(rel.mean()),
            "max_relative_l2": float(rel.max()),
            "mean_drift_max": float(mean_err.max()),
            "extrema_violation_max": float(np.maximum(overshoot, undershoot).max()),
            "parameter_count": parameter_count(p),
            "audit_total_seconds_including_compile": elapsed,
            "per_case_relative_l2": rel.tolist(),
        }, preds


def predict_trajectories(predictor, params, data, batch_size=32):
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size")
    s, t = data.times.shape
    out = []
    apply = jax.jit(predictor.__call__)
    x = jnp.asarray(data.positions, jnp.float32)
    for start in range(0, s * t, batch_size):
        ids = np.arange(start, min(start + batch_size, s * t))
        ci = ids // t
        ti = ids % t
        pred = apply(
            params,
            jnp.asarray(data.initial[ci], jnp.float32),
            jnp.asarray(data.viscosity[ci], jnp.float32),
            jnp.asarray(data.times[ci, ti], jnp.float32),
            x,
        )
        out.append(np.asarray(jax.block_until_ready(pred)))
    result = np.concatenate(out).reshape(s, t, data.initial.shape[1])
    if not np.isfinite(result).all():
        raise FloatingPointError("nonfinite inference")
    return result
