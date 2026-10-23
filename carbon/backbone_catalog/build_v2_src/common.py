"""Shared helpers for the catalog trainer v2 (backbone-catalog lane, 2026-10-23).

Every build trains a fresh model from the fixed TRAIN it is given; nothing is downloaded, loaded or reused. Inputs and
targets are standardised with TRAIN statistics, which the returned forward carries as small constants.

v2 differs from the pinned v1 `common.py` in one place: the build seed may be any 64-bit unsigned integer (torch seeds
with it directly); v1 refused anything above uint32 with no reason beyond Carbon's own choice.
"""

from __future__ import annotations

import os

import numpy as np

# Deterministic cuBLAS must be configured before CUDA initialises.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch  # noqa: E402

#: Train on the rebuild worker's GPU when it has one; the trained state is
#: returned on the CPU, where Carbon lowers and freezes it.
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

#: torch.manual_seed takes up to 2**64 - 1.
SEED_LIMIT = 2**64


def check_seed(seed, name="seed"):
    if type(seed) is not int or not 0 <= seed < SEED_LIMIT:
        raise ValueError(f"{name} must be an integer from 0 to 2**64 - 1")
    return seed


def prepare(train_inputs, train_targets, seed):
    x = np.asarray(train_inputs, dtype=np.float64)
    y = np.asarray(train_targets, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or len(x) < 2:
        raise ValueError("expected paired 2-D TRAIN inputs and targets")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("TRAIN must be finite")
    check_seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)  # one thread: identical rebuilds give identical bytes
    torch.use_deterministic_algorithms(True)
    stats = {
        "mx": torch.from_numpy(x.mean(axis=0)),
        "sx": torch.from_numpy(x.std(axis=0) + 1e-9),
        "my": torch.from_numpy(y.mean(axis=0)),
        "sy": torch.from_numpy(y.std(axis=0) + 1e-9),
    }
    z = ((torch.from_numpy(x) - stats["mx"]) / stats["sx"]).to(DEVICE)
    t = ((torch.from_numpy(y) - stats["my"]) / stats["sy"]).to(DEVICE)
    return z, t, stats


def positive_int(value, name, default):
    value = default if value is None else value
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def rate(value, default):
    value = default if value is None else value
    if type(value) not in (int, float) or not 0 < value <= 1:
        raise ValueError("learning_rate must be in (0, 1]")
    return float(value)


def only(mapping, allowed, name):
    if type(mapping) is not dict or set(mapping) - set(allowed):
        raise ValueError(f"unsupported {name}: {sorted(set(mapping) - set(allowed))}")


def module_product(model, stats):
    """The worker product for a trained nn.Module: parameters plus a pure forward."""
    model = model.cpu().eval()
    named = list(model.named_parameters())
    names = tuple(name for name, _ in named)
    buffers = {name: value.detach().clone() for name, value in model.named_buffers()}
    parameters = [value.detach().clone() for _, value in named]
    if not all(bool(torch.isfinite(p).all()) for p in parameters):
        raise RuntimeError("nonfinite trained state")
    mx, sx, my, sy = (stats[k] for k in ("mx", "sx", "my", "sy"))

    def apply(params, inputs):
        if len(params) != len(names):
            raise ValueError("parameter count differs")
        z = (torch.as_tensor(inputs) - mx) / sx
        out = torch.func.functional_call(
            model, (dict(zip(names, params)), buffers), (z,)
        )
        return out * sy + my

    return {"framework": "torch", "apply": apply, "parameters": parameters}


def fit(model, z, t, steps, lr):
    """Plain full-batch Adam on mean squared error."""
    model = model.to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        loss = torch.nn.functional.mse_loss(model(z), t)
        if not bool(torch.isfinite(loss)):
            raise RuntimeError("nonfinite TRAIN loss")
        loss.backward()
        optimizer.step()
    return model


def mlp(n_in, width, depth, n_out, activation=torch.nn.GELU):
    layers, size = [], n_in
    for _ in range(depth):
        layers += [torch.nn.Linear(size, width), activation()]
        size = width
    layers.append(torch.nn.Linear(size, n_out))
    return torch.nn.Sequential(*layers).double().to(DEVICE)
