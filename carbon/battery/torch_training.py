"""Carbon's battery training loop in PyTorch (OWNER-PYTORCH-BACKEND-01).

The PyTorch sibling of `training`: a recipe whose `backend` setting is
`pytorch` is rebuilt here, in the pinned PyTorch worker image, with Carbon's
own code. Everything that is not numerical stays shared with the JAX backend
in `recipes.MLP`: the target layout, normalization, PCA heads, loss group
weights, the bounded voltage head, the declared initial values and the
prediction format. Only the network and the training engine differ, so a
PyTorch-built model is scored exactly like a JAX-built one.

Each registered surface means the same thing in both backends. The numbers are
not bit-identical across backends, and nothing requires that: each recipe is
rebuilt in the backend it names, and each backend must reproduce itself.

Optimizers: PyTorch's own implementation where it has one (Adam(W), RAdam,
NAdamW, Adafactor, Muon, and L-BFGS for the polish). Carbon implements the
others from their published algorithms: Lion, LAMB, Prodigy, schedule-free
AdamW and SAM, plus SGD with momentum and decoupled weight decay, which is how
the JAX backend defines it. The learning-rate curves are exact ports of the
optax schedules the JAX backend uses, with the same fixed constants (see
`training`).

Device (implementation 2.0, TORCH-GPU-01): a recipe rebuilds on the CPU, or
on a CUDA device when the validator's PyTorch GPU worker says so
(`CARBON_TORCH_DEVICE=cuda`); the recipe never chooses. Initialization, the
minibatch order and the stored state stay on the CPU, so a recipe starts from
the same weights and visits cases in the same order on either device. A CUDA
rebuild runs under the pinned GPU determinism profile
(`carbon.reconstruction.torch_gpu`); CPU and CUDA rebuilds are separate
evidence and are not required to match. On the CPU every change from
implementation 1.0 is the identity.

Determinism: all randomness comes from Carbon's reconstruction seed through an
explicit `torch.Generator`. Training runs with
`torch.use_deterministic_algorithms(True)` and a fixed CPU thread count
(`THREADS`); both are restored afterwards. Whether two hosts reproduce each
other within a tolerance is established by the backend's determinism study,
not asserted here.

Importing this module imports torch. Nothing outside the PyTorch backend
imports it.
"""

from __future__ import annotations

import contextlib
import itertools
import math
import os

import numpy as np
import torch

from .training import ACTIVATIONS, SAM_RHO

#: CPU threads for every PyTorch rebuild: the worker envelope's CPU count.
#: A declared engineering constant; reduction order depends on it.
THREADS = 2
TORCH_BACKEND = "pytorch"
#: The environment variable the validator's worker sets to choose the device.
DEVICE_ENV = "CARBON_TORCH_DEVICE"
DEVICES = ("cpu", "cuda")


class DeviceUnavailable(ImportError):
    """The rebuild device this worker was given is absent: Carbon's own
    environment, never the candidate's (the fixed worker programs report an
    ImportError as `stage: environment`)."""


def rebuild_device():
    """The device this process rebuilds on, from the worker environment."""
    name = os.environ.get(DEVICE_ENV, "cpu")
    if name not in DEVICES:
        raise DeviceUnavailable("unknown PyTorch rebuild device " + name)
    if name == "cuda" and not torch.cuda.is_available():
        raise DeviceUnavailable("the PyTorch GPU rebuild needs a CUDA device")
    return torch.device(name)


def _determinism(device):
    """The pinned determinism configuration for `device`."""
    if device.type == "cuda":
        from carbon.reconstruction import torch_gpu

        # The worker's environment, checked before anything changes: a
        # missing or different pinned value is Carbon's, never the candidate's.
        required = torch_gpu.worker_environment()
        if any(os.environ.get(k) != v for k, v in required.items()):
            raise DeviceUnavailable("the GPU determinism environment is not pinned")
        return torch_gpu.deterministic_cuda(torch)
    return deterministic()


@contextlib.contextmanager
def deterministic():
    """Deterministic algorithms and a fixed thread count, restored on exit."""
    algorithms = torch.are_deterministic_algorithms_enabled()
    threads = torch.get_num_threads()
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(THREADS)
    try:
        yield
    finally:
        torch.use_deterministic_algorithms(algorithms)
        torch.set_num_threads(threads)


def torch_dtype(precision):
    return torch.float64 if precision == "float64" else torch.float32


# --- Networks ------------------------------------------------------------------


def _activation(name):
    if name not in ACTIVATIONS:  # pragma: no cover - the registry's closed choice
        raise ValueError("unregistered activation")
    return {
        "gelu": torch.nn.functional.gelu,
        "relu": torch.relu,
        "tanh": torch.tanh,
        "silu": torch.nn.functional.silu,
        "softplus": torch.nn.functional.softplus,
    }[name]


def _scale(name, a, b):
    if name == "he_normal":
        return math.sqrt(2.0 / a)
    if name == "glorot_normal":
        return math.sqrt(2.0 / (a + b))
    return math.sqrt(1.0 / a)  # lecun_normal


def dense_stack(generator, sizes, initialization, dtype):
    """Weights (a, b) drawn N(0, 1) times the initialization's scale; zero
    biases. The same parameterization as the JAX backend's `dense_stack`."""
    params = []
    for a, b in itertools.pairwise(sizes):
        w = torch.randn((a, b), generator=generator, dtype=dtype)
        params.append([w * _scale(initialization, a, b), torch.zeros(b, dtype=dtype)])
    return params


def apply_stack(params, h, activation, normalization):
    act = _activation(activation)
    for w, b in params[:-1]:
        h = h @ w + b
        if normalization == "layer_norm":
            mean = h.mean(-1, keepdim=True)
            var = h.var(-1, keepdim=True, unbiased=False)
            h = (h - mean) / torch.sqrt(var + 1e-6)
        h = act(h)
    w, b = params[-1]
    return h @ w + b


class Network:
    """A battery network as a flat, ordered list of tensors and an `apply`.

    The parameter order is fixed by construction, so a model state is the
    list itself: no module tree, no pickle.
    """

    def __init__(self, params, apply):
        self.params, self._apply = params, apply

    def __call__(self, params, f):
        return self._apply(params, f)


def _flatten(nested):
    out = []
    for item in nested:
        if isinstance(item, (list, tuple)):
            out.extend(_flatten(item))
        else:
            out.append(item)
    return out


def mlp_network(generator, settings, width, depth, n_in, n_out, dtype):
    s = settings
    stack = dense_stack(
        generator, [n_in] + [width] * depth + [n_out], s["initialization"], dtype
    )
    count = len(stack)

    def apply(params, f):
        layers = [params[2 * i : 2 * i + 2] for i in range(count)]
        return apply_stack(layers, f, s["activation"], s["normalization"])

    return Network(_flatten(stack), apply)


def deeponet_network(generator, settings, width, depth, layout, n_in, dtype):
    """Branch over the inputs, trunk over the 30 s grid: the battery DeepONet,
    parameterized as in the JAX backend."""
    from .domain import GRID_STEP_S

    s = settings
    basis = s["basis_functions"]
    heads = 2 * basis + 1 + layout.k
    branch = dense_stack(
        generator, [n_in] + [width] * depth + [heads], s["initialization"], dtype
    )
    trunk = dense_stack(
        generator, [1] + [width] * depth + [2 * basis], s["initialization"], dtype
    )
    bias = torch.zeros(layout.nv + layout.nt, dtype=dtype)
    times = np.arange(layout.g) * GRID_STEP_S / (GRID_STEP_S * (layout.g - 1))
    tv = torch.tensor((times if layout.predict_v0 else times[1:])[:, None], dtype=dtype)
    tt = torch.tensor(times[1:][:, None], dtype=dtype)
    nb, nt = len(branch), len(trunk)
    act, norm = s["activation"], s["normalization"]

    def apply(params, f):
        b_layers = [params[2 * i : 2 * i + 2] for i in range(nb)]
        t_layers = [params[2 * (nb + i) : 2 * (nb + i) + 2] for i in range(nt)]
        bias_ = params[2 * (nb + nt)]
        b = apply_stack(b_layers, f, act, norm)
        tv_, tt_ = tv.to(f.device), tt.to(f.device)
        v = b[:, :basis] @ apply_stack(t_layers, tv_, act, norm)[:, :basis].T
        t = b[:, basis : 2 * basis] @ apply_stack(t_layers, tt_, act, norm)[:, basis:].T
        traj = torch.cat([v, t], dim=1) + bias_
        return torch.cat([traj, b[:, 2 * basis :]], dim=1)

    return Network(_flatten(branch) + _flatten(trunk) + [bias], apply)


def build_network(model, generator, n_in, n_out, dtype):
    """The network a PyTorch recipe names, for `recipes.MLP` `model`."""
    from .torch_families import TORCH_FAMILIES

    if model.family == "mlp":
        return mlp_network(
            generator, model.settings, model.width, model.depth, n_in, n_out, dtype
        )
    if model.family == "deeponet":
        return deeponet_network(
            generator,
            model.settings,
            model.width,
            model.depth,
            model.layout,
            n_in,
            dtype,
        )
    if model.family in TORCH_FAMILIES:
        return TORCH_FAMILIES[model.family](model, generator, n_in, n_out, dtype)
    raise ValueError("no PyTorch network for family " + model.family)


# --- Learning-rate curves: exact ports of the optax schedules -------------------


def curve(settings, steps):
    """The learning rate at update `i` (0-based), warmup included."""
    peak = settings["learning_rate"]
    ratio = settings["min_learning_rate_ratio"]
    warmup = settings["warmup_steps"]
    name = settings["learning_rate_curve"]
    decay = max(steps - warmup, 1)

    if name == "cosine":

        def main(i):
            t = min(i, decay) / decay
            return peak * ((1 - ratio) * 0.5 * (1 + math.cos(math.pi * t)) + ratio)

    elif name in ("constant", "train_loss_plateau"):

        def main(i):
            return peak

    elif name == "piecewise":
        bounds = (decay // 2, (3 * decay) // 4)

        def main(i):
            return peak * (0.1 ** sum(1 for b in bounds if i >= b))

    elif name == "exponential":
        rate = ratio if ratio > 0 else 0.01

        def main(i):
            return peak * rate ** (i / decay)

    elif name == "one_cycle":
        return _one_cycle(steps, peak)
    elif name == "sgdr":
        cycle = max(decay // 4, 1)

        def main(i):
            k = min(i // cycle, 3)
            j = min(i - k * cycle, cycle)
            return peak * 0.5 * (1 + math.cos(math.pi * j / cycle))

    elif name == "polynomial":
        end = peak * ratio

        def main(i):
            t = min(i, decay) / decay
            return (peak - end) * (1 - t) ** 2 + end

    else:  # pragma: no cover - the registry's closed choice
        raise ValueError("unregistered learning-rate curve")
    if warmup == 0:
        return main

    def warmed(i):
        if i < warmup:
            return peak * i / warmup
        return main(i - warmup)

    return warmed


def _one_cycle(steps, peak, pct_start=0.3, div_factor=25.0, final_div=1e4):
    """optax.cosine_onecycle_schedule: cosine up to the peak over 30 % of the
    updates, then cosine down to peak / 25 / 1e4."""
    start = peak / div_factor
    end = start / final_div
    up = int(pct_start * steps)

    def cosine(a, b, t):
        return b + (a - b) * 0.5 * (1 + math.cos(math.pi * t))

    def schedule(i):
        if i < up:
            return cosine(start, peak, i / max(up, 1))
        return cosine(peak, end, min((i - up) / max(steps - up, 1), 1.0))

    return schedule


# --- Optimizers -----------------------------------------------------------------


def _decayed(params, settings):
    """Which parameters weight decay applies to: all, or matrices only."""
    if settings["weight_decay_mask"] == "matrices":
        return [p.ndim >= 2 for p in params]
    return [True] * len(params)


class _Carbon:
    """A Carbon-implemented optimizer: `step(grads, lr)` updates in place."""

    def __init__(self, params, settings):
        self.params, self.s = params, settings
        self.decay = _decayed(params, settings)
        self.count = 0

    def _decoupled(self, p, i, lr):
        wd = self.s["weight_decay"]
        if wd and self.decay[i]:
            p.sub_(lr * wd * p)


class SGDMomentum(_Carbon):
    """optax.trace(decay=beta1), decoupled weight decay, then the rate."""

    def __init__(self, params, settings):
        super().__init__(params, settings)
        self.m = [torch.zeros_like(p) for p in params]

    def step(self, grads, lr):
        b1 = self.s["beta1"]
        for i, (p, g) in enumerate(zip(self.params, grads)):
            self.m[i].mul_(b1).add_(g)
            update = self.m[i].clone()
            if self.s["weight_decay"] and self.decay[i]:
                update.add_(self.s["weight_decay"] * p)
            p.sub_(lr * update)


class Lion(_Carbon):
    """Lion (Chen et al., 2023), as optax.lion."""

    def __init__(self, params, settings):
        super().__init__(params, settings)
        self.m = [torch.zeros_like(p) for p in params]

    def step(self, grads, lr):
        b1, b2 = self.s["beta1"], self.s["beta2"]
        for i, (p, g) in enumerate(zip(self.params, grads)):
            update = torch.sign(b1 * self.m[i] + (1 - b1) * g)
            if self.s["weight_decay"] and self.decay[i]:
                update = update + self.s["weight_decay"] * p
            p.sub_(lr * update)
            self.m[i].mul_(b2).add_((1 - b2) * g)


class Lamb(_Carbon):
    """LAMB (You et al., 2020), as optax.lamb: bias-corrected Adam, decayed
    weights, then the layer-wise trust ratio."""

    def __init__(self, params, settings):
        super().__init__(params, settings)
        self.m = [torch.zeros_like(p) for p in params]
        self.v = [torch.zeros_like(p) for p in params]

    def step(self, grads, lr):
        b1, b2, eps = self.s["beta1"], self.s["beta2"], self.s["adam_epsilon"]
        self.count += 1
        t = self.count
        for i, (p, g) in enumerate(zip(self.params, grads)):
            self.m[i].mul_(b1).add_((1 - b1) * g)
            self.v[i].mul_(b2).add_((1 - b2) * g * g)
            update = (self.m[i] / (1 - b1**t)) / (
                torch.sqrt(self.v[i] / (1 - b2**t)) + eps
            )
            if self.s["weight_decay"] and self.decay[i]:
                update = update + self.s["weight_decay"] * p
            pn, un = torch.linalg.vector_norm(p), torch.linalg.vector_norm(update)
            ratio = torch.where(
                (pn > 0) & (un > 0),
                pn / un,
                torch.ones((), dtype=p.dtype, device=p.device),
            )
            p.sub_(lr * ratio * update)


class Prodigy(_Carbon):
    """Prodigy (Mishchenko and Defazio, 2024), as optax.contrib.prodigy with
    the curve divided by its peak as its step multiplier."""

    def __init__(self, params, settings):
        super().__init__(params, settings)
        self.m = [torch.zeros_like(p) for p in params]
        self.v = [torch.zeros_like(p) for p in params]
        self.s_ = [torch.zeros_like(p) for p in params]
        self.p0 = [p.detach().clone() for p in params]
        dtype, device = params[0].dtype, params[0].device
        self.d = torch.tensor(1e-6, dtype=dtype, device=device)
        self.num = torch.tensor(0.0, dtype=dtype, device=device)

    def step(self, grads, lr):
        b1, b2, eps = self.s["beta1"], self.s["beta2"], self.s["adam_epsilon"]
        scale = lr / self.s["learning_rate"]  # the curve, divided by its peak
        b3 = math.sqrt(b2)
        d = self.d
        dlr = d * scale
        self.num = b3 * self.num + dlr * sum(
            torch.sum(g * (p0 - p)) for g, p, p0 in zip(grads, self.params, self.p0)
        )
        denom = 0.0
        for i, g in enumerate(grads):
            self.s_[i].mul_(b3).add_(dlr * g)
            denom = denom + torch.sum(torch.abs(self.s_[i]))
        d_hat = self.num / torch.clamp(torch.as_tensor(denom), min=1e-30)
        self.d = torch.maximum(d, d_hat)
        d = self.d
        for i, (p, g) in enumerate(zip(self.params, grads)):
            self.m[i].mul_(b1).add_(d * (1 - b1) * g)
            self.v[i].mul_(b2).add_(d * d * (1 - b2) * g * g)
            update = self.m[i] / (torch.sqrt(self.v[i]) + d * eps)
            if self.s["weight_decay"] and self.decay[i]:
                update = update + self.s["weight_decay"] * d * p
            p.sub_(scale * d * update)


class ScheduleFreeAdamW(_Carbon):
    """Schedule-free AdamW (Defazio et al., 2024), as
    optax.contrib.schedule_free_adamw: gradients at the interpolation y,
    updates to z, and x, the evaluation point, an average of z."""

    def __init__(self, params, settings):
        super().__init__(params, settings)
        self.z = [p.detach().clone() for p in params]
        self.x = [p.detach().clone() for p in params]
        self.v = [torch.zeros_like(p) for p in params]
        self.weight_sum = 0.0
        self.peak = settings["learning_rate"]
        self.warmup = settings["warmup_steps"]

    def step(self, grads, lr):
        b1, b2, eps = self.s["beta1"], self.s["beta2"], self.s["adam_epsilon"]
        wd = self.s["weight_decay"]
        self.count += 1
        t = self.count
        rate = self.peak * min(1.0, t / self.warmup) if self.warmup else self.peak
        rate = rate * math.sqrt(1 - b2**t)
        weight = rate**2
        self.weight_sum += weight
        c = weight / self.weight_sum if self.weight_sum else 0.0
        for i, (p, g) in enumerate(zip(self.params, grads)):
            self.v[i].mul_(b2).add_((1 - b2) * g * g)
            step = g / (torch.sqrt(self.v[i]) + eps)
            if wd and self.decay[i]:
                step = step + wd * p
            self.z[i].sub_(rate * step)
            self.x[i].mul_(1 - c).add_(c * self.z[i])
            p.copy_((1 - b1) * self.z[i] + b1 * self.x[i])

    def evaluation_params(self):
        return [x.clone() for x in self.x]


class Native:
    """A PyTorch optimizer driven at Carbon's learning rate each update."""

    def __init__(self, optimizer):
        self.optimizer = optimizer

    def step(self, grads, lr):
        for group in self.optimizer.param_groups:
            group["lr"] = lr
        params = [p for group in self.optimizer.param_groups for p in group["params"]]
        for p, g in zip(params, self._ordered(grads)):
            p.grad = g
        self.optimizer.step()

    def bind(self, params):
        index = {id(p): i for i, p in enumerate(params)}
        order = [
            index[id(p)]
            for group in self.optimizer.param_groups
            for p in group["params"]
        ]
        self._ordered = lambda grads: [grads[i] for i in order]
        return self


def _groups(params, settings):
    """Decayed and undecayed parameter groups for a native optimizer."""
    wd = settings["weight_decay"]
    decayed = _decayed(params, settings)
    on = [p for p, d in zip(params, decayed) if d]
    off = [p for p, d in zip(params, decayed) if not d]
    groups = []
    if on:
        groups.append({"params": on, "weight_decay": wd})
    if off:
        groups.append({"params": off, "weight_decay": 0.0})
    return groups


def optimizer(params, settings):
    """The optimizer for a registered family, over `params` (leaf tensors)."""
    s = settings
    name = s["optimizer_family"]
    betas, eps = (s["beta1"], s["beta2"]), s["adam_epsilon"]
    if name in ("adam", "sam"):
        return Native(
            torch.optim.AdamW(
                _groups(params, s), lr=s["learning_rate"], betas=betas, eps=eps
            )
        ).bind(params)
    if name == "radam":
        return Native(
            torch.optim.RAdam(
                _groups(params, s),
                lr=s["learning_rate"],
                betas=betas,
                eps=eps,
                decoupled_weight_decay=True,
            )
        ).bind(params)
    if name == "nadamw":
        return Native(
            torch.optim.NAdam(
                _groups(params, s),
                lr=s["learning_rate"],
                betas=betas,
                eps=eps,
                decoupled_weight_decay=True,
            )
        ).bind(params)
    if name == "adafactor":
        return Native(
            torch.optim.Adafactor(_groups(params, s), lr=s["learning_rate"])
        ).bind(params)
    if name == "muon":
        return MuonWithAdam(params, s)
    if name == "sgd_momentum":
        return SGDMomentum(params, s)
    if name == "lion":
        return Lion(params, s)
    if name == "lamb":
        return Lamb(params, s)
    if name == "prodigy":
        return Prodigy(params, s)
    if name == "free_adamw":
        return ScheduleFreeAdamW(params, s)
    raise ValueError("unregistered optimizer")  # pragma: no cover


class MuonWithAdam:
    """Muon for matrices, AdamW for every other parameter, as optax's Muon
    applies Adam to non-matrix parameters."""

    def __init__(self, params, settings):
        s = settings
        matrices = [p for p in params if p.ndim == 2]
        rest = [p for p in params if p.ndim != 2]
        decay = s["weight_decay"]
        self.parts = []
        if matrices:
            self.parts.append(
                Native(
                    torch.optim.Muon(
                        matrices,
                        lr=s["learning_rate"],
                        weight_decay=decay,
                        momentum=s["beta1"],
                        eps=s["adam_epsilon"],
                    )
                ).bind(matrices)
            )
        if rest:
            mask_off = s["weight_decay_mask"] == "matrices"
            self.parts.append(
                Native(
                    torch.optim.AdamW(
                        rest,
                        lr=s["learning_rate"],
                        betas=(s["beta1"], s["beta2"]),
                        eps=s["adam_epsilon"],
                        weight_decay=0.0 if mask_off else decay,
                    )
                ).bind(rest)
            )
        self.index = [
            [i for i, p in enumerate(params) if p.ndim == 2],
            [i for i, p in enumerate(params) if p.ndim != 2],
        ]

    def step(self, grads, lr):
        parts = [index for index in self.index if index]
        for part, index in zip(self.parts, parts):
            part.step([grads[i] for i in index], lr)


# --- The training loop ----------------------------------------------------------


def train(
    *, network, f, z, sw, gw, trajectory, settings, seed, order, dtype, device=None
):
    """Train `network` in place; returns the parameters Carbon predicts from.

    The PyTorch port of `training.train`, surface for surface. `f`, `z`, `sw`,
    `gw` and `order` are NumPy arrays. Training runs on `device` (the CPU by
    default); the minibatch order is drawn on the CPU on either device.
    """
    device = torch.device("cpu") if device is None else device
    s = settings
    n = f.shape[0]
    steps = s["steps"] - s["polish_steps"]
    batch = min(s["batch_size"], n)
    micro = s["microbatches"]
    generator = torch.Generator().manual_seed(seed + 1)
    f, z, sw, gw = (torch.tensor(a, dtype=dtype, device=device) for a in (f, z, sw, gw))
    rank = torch.tensor(order, device=device)
    params = [
        p.detach().clone().to(device).requires_grad_(True) for p in network.params
    ]
    apply = network._apply
    lr_at = curve(s, steps)
    opt = optimizer(params, s)
    sam = s["optimizer_family"] == "sam"
    plateau = s["learning_rate_curve"] == "train_loss_plateau"
    patience = max(10, steps // 20)
    best, waited, plateau_scale = math.inf, 0, 1.0

    def ramp(length):
        if s["time_weighting"] == "early":
            return torch.linspace(2.0, 0.0, length, dtype=dtype, device=device)
        return torch.linspace(0.0, 2.0, length, dtype=dtype, device=device)

    def case_loss(p, idx):
        zhat = apply(p, f[idx])
        zt = z[idx]
        base = torch.sum((zhat - zt) ** 2 * gw[None, :], dim=1)
        if s["relative_loss"]:
            base = base / (torch.sum(zt**2 * gw[None, :], dim=1) + 1e-6)
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
                    extra = extra + torch.mean(ramp(e.shape[1]) * e**2, dim=1)
                if s["h1_weight"]:
                    d = torch.diff(e, dim=1)
                    extra = extra + s["h1_weight"] * torch.mean(d**2, dim=1)
                if s["h2_weight"]:
                    d = torch.diff(e, n=2, dim=1)
                    extra = extra + s["h2_weight"] * torch.mean(d**2, dim=1)
                if s["spectral_weight"]:
                    spectrum = torch.abs(torch.fft.rfft(e, dim=1)) ** 2
                    k = torch.linspace(
                        0.0, 1.0, spectrum.shape[1], dtype=dtype, device=device
                    )
                    extra = (
                        extra
                        + s["spectral_weight"]
                        * torch.mean(k * spectrum, dim=1)
                        / e.shape[1]
                    )
        return base + extra

    def weights(p, idx, step):
        w = sw[idx]
        if s["curriculum"] != "none":
            admitted = min(1.0, 0.25 + 1.5 * step / steps)
            w = w * (rank[idx] < math.ceil(admitted * n)).to(dtype)
        if s["hard_example_weight"]:
            with torch.no_grad():
                current = case_loss(p, idx)
            w = (
                w
                * (current / (torch.mean(current) + 1e-12)) ** s["hard_example_weight"]
            )
        return w

    def loss(p, idx, step):
        w = weights(p, idx, step).detach()
        return torch.sum(w * case_loss(p, idx)) / (torch.sum(w) + 1e-12)

    def gradient(p, idx, step):
        chunks = idx.reshape(micro, -1) if micro > 1 else idx[None]
        total, grads = 0.0, None
        for chunk in chunks:
            value = loss(p, chunk, step)
            g = torch.autograd.grad(value, p)
            total = total + value.detach()
            grads = list(g) if grads is None else [a + b for a, b in zip(grads, g)]
        return total / len(chunks), [g / len(chunks) for g in grads]

    tail = int(steps * (1.0 - s["tail_averaging"])) if s["tail_averaging"] else steps
    decay = s["ema_decay"]
    use_ema = s["inference_weights"] == "ema"
    ema = [p.detach().clone() for p in params]
    avg = [p.detach().clone() for p in params]
    everything = torch.arange(n, device=device)
    adversary = None
    from .training import keep_history, recording_history

    # Trainer v2 (RSURF-D3): read the loss each update already computes.
    recording = recording_history()
    history = []
    for i in range(steps):
        idx = (
            everything
            if batch >= n
            else torch.randperm(n, generator=generator)[:batch].to(device)
        )
        if sam and i % 2 == 0:
            # SAM's adversarial update: a normalized-gradient step of SAM_RHO.
            _, g = gradient(params, idx, i)
            norm = torch.sqrt(sum(torch.sum(x * x) for x in g)) + 1e-12
            adversary = [SAM_RHO * x / norm for x in g]
            continue
        if sam:
            perturbed = [
                (p + e).detach().requires_grad_(True) for p, e in zip(params, adversary)
            ]
            value, g = gradient(perturbed, idx, i)
        else:
            value, g = gradient(params, idx, i)
        if recording:
            history.append((i, float(value)))
        if s["clip_norm"] > 0:
            norm = torch.sqrt(sum(torch.sum(x * x) for x in g))
            factor = min(1.0, s["clip_norm"] / (float(norm) + 1e-12))
            g = [x * factor for x in g]
        if plateau:
            current = float(value)
            if current < best:
                best, waited = current, 0
            else:
                waited += 1
                if waited >= patience:
                    plateau_scale, waited = plateau_scale * 0.5, 0
        with torch.no_grad():
            opt.step(g, lr_at(i) * plateau_scale)
            if use_ema:
                for e, p in zip(ema, params):
                    e.mul_(decay).add_((1 - decay) * p)
            if s["tail_averaging"] and i >= tail:
                count = i - tail + 1
                for a, p in zip(avg, params):
                    a.add_((p - a) / count)
    if recording:
        keep_history(history, steps)
    if s["optimizer_family"] == "free_adamw":
        final = opt.evaluation_params()
    elif use_ema:
        final = ema
    elif s["tail_averaging"]:
        final = avg
    else:
        final = [p.detach().clone() for p in params]
    if s["polish_steps"]:
        final = polish(final, lambda q: loss(q, everything, steps), s["polish_steps"])
    return [p.detach() for p in final]


def polish(params, objective, count):
    """Full-batch L-BFGS steps with a strong-Wolfe line search."""
    params = [p.detach().clone().requires_grad_(True) for p in params]
    lbfgs = torch.optim.LBFGS(
        params, lr=1.0, max_iter=1, history_size=10, line_search_fn="strong_wolfe"
    )

    def closure():
        lbfgs.zero_grad()
        value = objective(params)
        value.backward()
        return value

    for _ in range(count):
        lbfgs.step(closure)
    return [p.detach() for p in params]


# --- Fit and predict for recipes.MLP --------------------------------------------


def fit(model, d, y, seed):
    """Train `model` (a `recipes.MLP` with backend pytorch) on TRAIN `d`."""
    import hashlib
    import time

    from .recipes import features

    s = model.settings
    dtype = torch_dtype(s["precision"])
    np_dtype = np.float64 if dtype is torch.float64 else np.float32
    t0 = time.perf_counter()
    device = rebuild_device()
    with _determinism(device):
        z = model._encode(y).astype(np_dtype)
        f = features(d.x, model.rich).astype(np_dtype)
        sw = np.where(d.important, model.important_weight, 1.0).astype(np_dtype)
        gw = model._group_weights(z.shape[1]).astype(np_dtype)
        generator = torch.Generator().manual_seed(seed)
        network = build_network(model, generator, f.shape[1], z.shape[1], dtype)
        order = np.argsort(np.argsort(d.x[:, 0] + d.x[:, 1], kind="stable"))
        if s["curriculum"] == "high_rate_first":
            order = len(order) - 1 - order
        params = train(
            network=network,
            f=f,
            z=z,
            sw=sw,
            gw=gw,
            trajectory=trajectory(model, dtype, device),
            settings=s,
            seed=seed,
            order=order,
            dtype=dtype,
            device=device,
        )
        with torch.no_grad():
            x = torch.tensor(f, dtype=dtype, device=device)
            zhat = network(params, x).cpu().numpy()
    leaves = [p.cpu().numpy() for p in params]
    model.params, model._network_torch = leaves, network
    final = float(np.mean((zhat - z) ** 2 * gw[None, :]) * gw.size)
    blob = b"".join(a.tobytes() for a in leaves)
    from .training import take_history

    stats = {
        "compile_s": 0.0,
        "train_s": time.perf_counter() - t0,
        "final_loss": final,
        "params_sha256": hashlib.sha256(blob).hexdigest(),
        "n_params": int(sum(a.size for a in leaves)),
        "backend": TORCH_BACKEND,
    }
    if device.type != "cpu":
        # A CPU rebuild's statistics are implementation 1.0's, key for key. A
        # GPU rebuild names its device class: its scores are never compared
        # with another class's (`carbon.battery.rebuild_identity`).
        stats["device"] = device.type
        stats["device_class"] = "gpu:" + torch.cuda.get_device_name(device)
    history = take_history()
    if history is not None:
        stats["loss_history"] = history
    return stats


def trajectory(model, dtype, device=None):
    """Normalized voltage and temperature trajectories from outputs z."""
    nv, nt = model.layout.nv, model.layout.nt
    if not model.pca:
        return lambda z: (z[:, :nv], z[:, nv : nv + nt])

    def t(a):
        return torch.tensor(np.asarray(a), dtype=dtype, device=device)

    zsd, zmu, pv, pt = t(model.zsd), t(model.zmu), t(model.pv), t(model.pt)
    vm, tm, mu, sd, p = t(model.vm), t(model.tm), t(model.mu), t(model.sd), model.pca

    def trajectory_(z):
        c = z * zsd + zmu
        v = (c[:, :p] @ pv + vm - mu[:nv]) / sd[:nv]
        tt = (c[:, p : 2 * p] @ pt + tm - mu[nv : nv + nt]) / sd[nv : nv + nt]
        return v, tt

    return trajectory_


def predict(model, f):
    """Network outputs z for features `f` (NumPy), in float64."""
    dtype = torch_dtype(model.settings["precision"])
    with deterministic(), torch.no_grad():
        params = [torch.tensor(a, dtype=dtype) for a in model.params]
        z = model._network_torch(params, torch.tensor(f, dtype=dtype))
        return z.numpy().astype(float)


def restore(model, leaves, n_in, n_out):
    """Rebuild the network skeleton for a stored state; never trains."""
    dtype = torch_dtype(model.settings["precision"])
    generator = torch.Generator().manual_seed(0)
    network = build_network(model, generator, n_in, n_out, dtype)
    if len(network.params) != len(leaves) or any(
        tuple(p.shape) != tuple(a.shape) for p, a in zip(network.params, leaves)
    ):
        raise ValueError("stored PyTorch state does not match its network")
    model.params, model._network_torch = list(leaves), network
    return model
