"""Motor's neural families: an MLP and a DeepONet over the torque curve.

MOTOR-NEURAL-01. A motor neural recipe trains through Carbon's shared trainers,
the same mechanism a battery recipe trains through:
`carbon.battery.training.train` (JAX) and `carbon.battery.torch_training.train`
(PyTorch). Only the network's inputs and outputs are motor's. Nothing here
executes anything a miner supplied, and all randomness is Carbon's
reconstruction seed.

**The model.**
- The eight registered inputs are scaled to [-1, 1] by their bounds (the
  kernel ridge's scaling).
- The output is the torque at the `ANGLE_STEPS` angles of one period,
  standardized per angle over TRAIN.
- The loss is the mean squared standardized error over the angles, with
  every case weighted equally.
- **The MLP** maps the inputs to the whole curve.
- **The DeepONet** pairs a branch over the inputs with a trunk over the angle,
  normalized to [0, 1) over the period. The trunk is shared by every angle.

**Fixed, declared constants** (engineering choices, not quality claims): every
trainer setting no motor surface sets (`TRAINER_FIXED`). These are the battery
trainer's defaults, copied here so a later battery change never moves motor
silently (consistency across Challenges is deliberate and recorded).

These are development recipes. They make no claim of physical validity, are
not qualified, and are no evidence of value over the kernel ridge.
"""

from __future__ import annotations

import hashlib
import time

import numpy as np

from carbon import learned_baseline

from . import domain

FAMILIES = ("mlp", "deeponet")
BACKENDS = ("jax", "pytorch")
TRAINER = "carbon.motor.neural-trainer.v1"

#: Every trainer setting no motor surface sets (`carbon.battery.training`'s
#: vocabulary, at the battery defaults). Full-batch: TRAIN is 150 cases.
TRAINER_FIXED = {
    "adam_epsilon": 1e-08,
    "batch_size": 150,
    "beta1": 0.9,
    "beta2": 0.999,
    "clip_norm": 0.0,
    "curriculum": "none",
    "ema_decay": 0.99,
    "ensemble_members": 1,
    "h1_weight": 0.0,
    "h2_weight": 0.0,
    "hard_example_weight": 0.0,
    "inference_weights": "params",
    "initialization": "he_normal",
    "learning_rate_curve": "cosine",
    "microbatches": 1,
    "min_learning_rate_ratio": 0.0,
    "normalization": "none",
    "optimizer_family": "adam",
    "polish_steps": 0,
    # The motor contract's envelope precision (float64, as the kernel ridge).
    "precision": "float64",
    "relative_loss": False,
    "spectral_weight": 0.0,
    "tail_averaging": 0.0,
    "time_weighting": "uniform",
    "warmup_steps": 0,
    "weight_decay": 0.0,
    "weight_decay_mask": "all",
}
#: The settings a motor neural recipe names (its surfaces).
SURFACED = {
    "mlp": frozenset(
        {"activation", "backend", "depth", "learning_rate", "steps", "width"}
    ),
    "deeponet": frozenset(
        {
            "activation",
            "backend",
            "basis_functions",
            "depth",
            "learning_rate",
            "steps",
            "width",
        }
    ),
}


def _angles():
    """The trunk's coordinate: the angle over one period, in [0, 1)."""
    return (np.arange(domain.ANGLE_STEPS) / domain.ANGLE_STEPS)[:, None]


class NeuralModel:
    """One motor neural recipe, trained by `fit(records, seed)`."""

    def __init__(self, family, settings):
        if family not in FAMILIES:
            raise ValueError("unknown Motor neural family")
        if set(settings) != SURFACED[family]:
            raise ValueError("Motor " + family + " settings are its surfaces")
        if settings["backend"] not in BACKENDS:
            raise ValueError("unknown Motor neural backend")
        self.family = family
        self.settings = {**TRAINER_FIXED, **settings}
        self.backend = settings["backend"]
        self.params = None

    # -- data --------------------------------------------------------------------
    @staticmethod
    def features(rows):
        return learned_baseline.scale(rows, domain.INPUTS, domain.INPUT_BOUNDS)

    def _arrays(self, records, dtype):
        f = self.features([r["inputs"] for r in records]).astype(dtype)
        y = np.asarray([r["outputs"]["torque_nm"] for r in records], dtype=float)
        if y.shape[1:] != (domain.ANGLE_STEPS,):
            raise ValueError("Motor TRAIN torque curves have the wrong length")
        self.mu, self.sd = y.mean(0), y.std(0) + 1e-9
        z = ((y - self.mu) / self.sd).astype(dtype)
        n, k = z.shape
        sw = np.ones(n, dtype)
        gw = np.full(k, 1.0 / k, dtype)
        return f, z, sw, gw, np.arange(n)

    # -- training ----------------------------------------------------------------
    def fit(self, records, seed):
        if type(seed) is not int or seed < 0:
            raise ValueError("a non-negative integer reconstruction seed is required")
        t0 = time.perf_counter()
        if self.backend == "pytorch":
            leaves, final = self._fit_torch(records, seed)
        else:
            leaves, final = self._fit_jax(records, seed)
        blob = b"".join(np.ascontiguousarray(a).tobytes() for a in leaves)
        self.stats = {
            "train_s": time.perf_counter() - t0,
            "final_loss": final,
            "params_sha256": hashlib.sha256(blob).hexdigest(),
            "n_params": int(sum(a.size for a in leaves)),
            "backend": self.backend,
            "trainer": TRAINER,
        }
        return self.stats

    def _jax_network(self, jax, dtype, n_in, n_out):
        from carbon.battery.training import apply_stack, dense_stack

        s = self.settings
        act, norm, init_name = s["activation"], s["normalization"], s["initialization"]
        width, depth = s["width"], s["depth"]
        if self.family == "mlp":

            def init(key):
                return dense_stack(
                    jax, key, [n_in] + [width] * depth + [n_out], init_name, dtype
                )

            def apply(p, f):
                return apply_stack(jax, p, f, act, norm)

            return init, apply
        jnp = jax.numpy
        basis = s["basis_functions"]
        angles = jnp.asarray(_angles(), dtype)

        def init(key):
            key, branch = dense_stack(
                jax, key, [n_in] + [width] * depth + [basis], init_name, dtype
            )
            key, trunk = dense_stack(
                jax, key, [1] + [width] * depth + [basis], init_name, dtype
            )
            bias = jnp.zeros((n_out,), dtype)
            return key, {"branch": branch, "trunk": trunk, "bias": bias}

        def apply(p, f):
            b = apply_stack(jax, p["branch"], f, act, norm)
            t = apply_stack(jax, p["trunk"], angles, act, norm)
            return b @ t.T + p["bias"]

        return init, apply

    def _fit_jax(self, records, seed):
        import jax

        from carbon.battery.training import train

        dtype = np.float64
        with jax.enable_x64(True):
            f, z, sw, gw, order = self._arrays(records, dtype)
            init, apply = self._jax_network(jax, dtype, f.shape[1], z.shape[1])
            params = train(
                init=init,
                apply=apply,
                f=f,
                z=z,
                sw=sw,
                gw=gw,
                trajectory=lambda out: (out,),
                settings=self.settings,
                seed=seed,
                order=order,
            )
            zhat = np.asarray(apply(params, f))
        self.params, self._apply = params, apply
        leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(params)]
        return leaves, float(np.mean((zhat - z) ** 2))

    def _torch_network(self, generator, dtype, n_in, n_out):
        import torch

        from carbon.battery import torch_training as tt

        s = self.settings
        act, norm, init_name = s["activation"], s["normalization"], s["initialization"]
        width, depth = s["width"], s["depth"]
        if self.family == "mlp":
            return tt.mlp_network(generator, s, width, depth, n_in, n_out, dtype)
        basis = s["basis_functions"]
        branch = tt.dense_stack(
            generator, [n_in] + [width] * depth + [basis], init_name, dtype
        )
        trunk = tt.dense_stack(
            generator, [1] + [width] * depth + [basis], init_name, dtype
        )
        bias = torch.zeros(n_out, dtype=dtype)
        angles = torch.tensor(_angles(), dtype=dtype)
        nb, nt = len(branch), len(trunk)

        def apply(params, f):
            b_layers = [params[2 * i : 2 * i + 2] for i in range(nb)]
            t_layers = [params[2 * (nb + i) : 2 * (nb + i) + 2] for i in range(nt)]
            b = tt.apply_stack(b_layers, f, act, norm)
            t = tt.apply_stack(t_layers, angles.to(f.device), act, norm)
            return b @ t.T + params[2 * (nb + nt)]

        return tt.Network(tt._flatten(branch) + tt._flatten(trunk) + [bias], apply)

    def _fit_torch(self, records, seed):
        import torch

        from carbon.battery import torch_training as tt

        dtype = tt.torch_dtype(self.settings["precision"])
        device = tt.rebuild_device()
        with tt._determinism(device):
            f, z, sw, gw, order = self._arrays(records, np.float64)
            generator = torch.Generator().manual_seed(seed)
            network = self._torch_network(generator, dtype, f.shape[1], z.shape[1])
            params = tt.train(
                network=network,
                f=f,
                z=z,
                sw=sw,
                gw=gw,
                trajectory=lambda out: (out,),
                settings=self.settings,
                seed=seed,
                order=order,
                dtype=dtype,
                device=device,
            )
            with torch.no_grad():
                x = torch.tensor(f, dtype=dtype, device=device)
                zhat = network(params, x).cpu().numpy()
        leaves = [p.detach().cpu().numpy() for p in params]
        self.params, self._network = leaves, network
        return leaves, float(np.mean((zhat - z) ** 2))

    # -- prediction --------------------------------------------------------------
    def _outputs(self, f):
        if self.params is None:
            raise ValueError("the Motor neural model is not trained")
        if self.backend == "pytorch":
            import torch

            from carbon.battery import torch_training as tt

            dtype = tt.torch_dtype(self.settings["precision"])
            with tt.deterministic(), torch.no_grad():
                params = [torch.tensor(a, dtype=dtype) for a in self.params]
                return self._network(params, torch.tensor(f, dtype=dtype)).numpy()
        import jax

        with jax.enable_x64(True):
            return np.asarray(self._apply(self.params, f.astype(np.float64)))

    def predict_many(self, cases):
        checked = [domain.check_inputs(case) for case in cases]
        z = self._outputs(self.features(checked).astype(np.float64))
        curves = z.astype(float) * self.sd + self.mu
        out = []
        for row in curves:
            curve = [float(v) for v in row]
            # The kernel ridge's output rule (`recipes.KernelRidgeModel`),
            # applied identically: a motoring curve's mean is not negative.
            mean = float(np.mean(curve))
            if mean < 0:
                curve = [v - mean for v in curve]
            out.append({"torque_nm": curve})
        return out

    def predict(self, inputs):
        return self.predict_many([inputs])[0]


def build(family, settings, records, seed):
    """A trained motor neural model and its training statistics."""
    model = NeuralModel(family, settings)
    stats = model.fit(records, seed)
    return model, stats
