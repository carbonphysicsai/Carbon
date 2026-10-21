"""Carbon's training loop for a catalog entry, and its float64 predictions.

Fixed, declared choices (engineering, not quality claims):
- full-batch Adam on the mean squared error of per-point standardized
  targets, every case weighted equally;
- training in float32, the libraries' own precision; predictions returned
  in float64;
- one torch thread and deterministic algorithms, so a rebuild on any host
  repeats the same arithmetic (thread count changes summation order);
- every random draw from Carbon's reconstruction seed.
"""

from __future__ import annotations

import numpy as np
import torch

from .torch_backbones import Shape, build

LOOP = "carbon.backbone-catalog.torch-loop.v1"
THREADS = 1


class Fitted:
    """A trained entry: `predict` maps (cases, n_in) scaled inputs to
    (cases, points) float64 outputs in the Challenge's own units."""

    def __init__(self, module, mean, scale):
        self.module, self.mean, self.scale = module, mean, scale

    def predict(self, inputs):
        x = torch.as_tensor(np.asarray(inputs, dtype=np.float32))
        threads = torch.get_num_threads()
        torch.set_num_threads(THREADS)
        try:
            with torch.no_grad():
                out = self.module(x).to(torch.float64).numpy()
        finally:
            torch.set_num_threads(threads)
        return out * self.scale + self.mean


def fit(catalog_id, settings, inputs, targets, *, seed, shape):
    """Train `catalog_id` on (cases, n_in) `inputs` and (cases, points)
    `targets` with Carbon's `seed`. Returns (Fitted, fit record)."""
    if type(seed) is not int or seed < 0:
        raise ValueError("Carbon's reconstruction seed is required")
    if type(shape) is not Shape:
        raise TypeError("a catalog Shape is required")
    x = np.asarray(inputs, dtype=np.float64)
    y = np.asarray(targets, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != shape.n_in or y.shape != (x.shape[0], shape.points):
        raise ValueError("TRAIN does not match the catalog shape")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("TRAIN must be finite")
    from .entries import resolve

    s = resolve(catalog_id, settings)
    mean = y.mean(axis=0)
    scale = y.std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)
    # Process-wide torch state, restored after: a shared validator process
    # keeps its own settings.
    threads, strict = (
        torch.get_num_threads(),
        torch.are_deterministic_algorithms_enabled(),
    )
    torch.set_num_threads(THREADS)
    torch.use_deterministic_algorithms(True)
    try:
        torch.manual_seed(seed)
        # Built in torch's default float32 (spectral weights stay complex).
        module = build(catalog_id, s, shape)
        tx = torch.as_tensor(x, dtype=torch.float32)
        ty = torch.as_tensor((y - mean) / scale, dtype=torch.float32)
        optimizer = torch.optim.Adam(module.parameters(), lr=s["learning_rate"])
        module.train()
        loss = None
        for _ in range(s["steps"]):
            optimizer.zero_grad(set_to_none=True)
            loss = torch.mean((module(tx) - ty) ** 2)
            if not torch.isfinite(loss):
                raise FloatingPointError("training loss is not finite")
            loss.backward()
            optimizer.step()
        module.eval()
    finally:
        torch.set_num_threads(threads)
        torch.use_deterministic_algorithms(strict)
    record = {
        "loop": LOOP,
        "catalog_id": catalog_id,
        "settings": s,
        "seed": seed,
        "threads": THREADS,
        "parameters": sum(p.numel() for p in module.parameters()),
        "final_loss": None if loss is None else float(loss.detach()),
    }
    return Fitted(module, mean, scale), record
