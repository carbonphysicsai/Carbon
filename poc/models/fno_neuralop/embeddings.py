"""1D grid positional embedding, ported from
`neuralop.layers.embeddings.GridEmbeddingND` (1D case).

Appends one coordinate channel `x_i = i / nx` (left-endpoint, matching the
default `grid_boundaries=[[0.0, 1.0]]` FNO uses regardless of the PDE's
physical domain length) after the existing channels. No learnable
parameters.
"""

from __future__ import annotations

from typing import Tuple

import jax.numpy as jnp
import flax.linen as nn


class GridEmbedding1D(nn.Module):
    grid_boundaries: Tuple[float, float] = (0.0, 1.0)

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """x: (batch, channels, nx) -> (batch, channels + 1, nx)."""
        batch, _channels, nx = x.shape
        start, stop = self.grid_boundaries
        coords = jnp.linspace(start, stop, nx + 1, dtype=x.dtype)[:-1]
        grid = jnp.broadcast_to(coords[None, None, :], (batch, 1, nx))
        return jnp.concatenate([x, grid], axis=1)
