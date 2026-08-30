"""Per-position channel MLP, ported from `neuralop.layers.channel_mlp.ChannelMLP`.

A kernel-size-1 `nn.Conv1d` in PyTorch is mathematically a per-position
linear map shared across all spatial positions. This port implements that
directly via `einsum` rather than a JAX/Flax conv primitive, keeping the
channels-first `(batch, channels, spatial)` convention used throughout this
package (see `poc/models/fno_neuralop/__init__.py`).

Dropout is intentionally not ported: FNO's lifting/projection and the
per-block channel MLP all default to `dropout=0`, and stochastic dropout
has no meaningful cross-framework numerical parity target.
"""

from __future__ import annotations

from collections.abc import Callable

import flax.linen as nn
import jax
import jax.numpy as jnp

from poc.models.fno_neuralop.activations import exact_gelu


class ChannelMLP1D(nn.Module):
    """Two-or-more-layer per-position MLP over the channel axis.

    Parameters
    ----------
    in_channels : int
    out_channels : int, optional
        Defaults to `in_channels`, matching `ChannelMLP`.
    hidden_channels : int, optional
        Defaults to `in_channels`, matching `ChannelMLP`.
    n_layers : int, default 2
    non_linearity : callable, default exact-erf gelu
        Applied after every layer except the last, matching `ChannelMLP`.
    dropout : float, default 0.0
        Must be 0.0 — see module docstring.
    """

    in_channels: int
    out_channels: int | None = None
    hidden_channels: int | None = None
    n_layers: int = 2
    non_linearity: Callable = exact_gelu
    dropout: float = 0.0
    param_dtype: jnp.dtype = jnp.float32

    def _layer_dims(
        self, i: int, out_channels: int, hidden_channels: int
    ) -> tuple[int, int]:
        """Returns (fan_in, fan_out) for layer i."""
        if i == 0 and i == self.n_layers - 1:
            return self.in_channels, out_channels
        if i == 0:
            return self.in_channels, hidden_channels
        if i == self.n_layers - 1:
            return hidden_channels, out_channels
        return hidden_channels, hidden_channels

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """x: (batch, in_channels, nx) -> (batch, out_channels, nx)."""
        if self.dropout != 0.0:
            raise NotImplementedError(
                "ChannelMLP1D dropout is not ported (no cross-framework parity "
                "target); use dropout=0.0."
            )

        out_channels = (
            self.out_channels if self.out_channels is not None else self.in_channels
        )
        hidden_channels = (
            self.hidden_channels
            if self.hidden_channels is not None
            else self.in_channels
        )

        for i in range(self.n_layers):
            fan_in, fan_out = self._layer_dims(i, out_channels, hidden_channels)
            bound = 1.0 / (fan_in**0.5)

            def _uniform_init(key, shape, dtype, b=bound):
                return jax.random.uniform(key, shape, minval=-b, maxval=b, dtype=dtype)

            weight = self.param(
                f"weight_{i}", _uniform_init, (fan_out, fan_in), self.param_dtype
            )
            bias = self.param(f"bias_{i}", _uniform_init, (fan_out,), self.param_dtype)
            x = jnp.einsum("oi,bix->box", weight, x) + bias[None, :, None]
            if i < self.n_layers - 1:
                x = self.non_linearity(x)

        return x
