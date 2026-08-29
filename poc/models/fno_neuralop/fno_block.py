"""FNOBlocks, ported from `neuralop.layers.fno_block.FNOBlocks` (1D,
postactivation path only).

Only the PyTorch defaults are ported: `preactivation=False`,
`fno_skip="linear"`, `channel_mlp_skip="soft-gating"`. `"identity"`/`None`
skip variants and the preactivation path are not needed for v1 and are not
implemented (see `Design_Specs/Burgers_FNO_JAX_Neuraloperator_Parity.md`
§3). `Flattened1dConv` and `SoftGating` are not ported as standalone
modules — both are trivial and only used here — see the mapping table in
that design note.

Per layer index `i` (verified against `FNOBlocks.forward_with_postactivation`,
not assumed — see the design note §5):

    x_skip_fno  = LinearSkip_i(x)             # unbiased 1x1 conv, from block input
    x_skip_gate = SoftGate_i(x)                # per-channel scalar, no bias, from block input
    x_spec      = SpectralConv1D_i(x)
    x           = x_spec + x_skip_fno
    if i < n_layers - 1: x = exact_gelu(x)
    x           = ChannelMLP1D_i(x) + x_skip_gate   # bypasses spectral conv AND channel MLP
    if i < n_layers - 1: x = exact_gelu(x)
    return x

Both skips are computed from the same pre-spectral-conv `x` at the top of
the block; `x_skip_gate` re-enters *after* the channel-MLP step, which is a
long residual bypassing two sublayers, not two short sequential ones.
"""

from __future__ import annotations

import flax.linen as nn
import jax
import jax.numpy as jnp

from poc.models.fno_neuralop.activations import exact_gelu
from poc.models.fno_neuralop.channel_mlp import ChannelMLP1D
from poc.models.fno_neuralop.spectral_conv import SpectralConv1D


class FNOBlocks1D(nn.Module):
    """A stack of `n_layers` Fourier layers; one layer runs per `__call__`.

    Mirrors `FNOBlocks.forward(x, index)`: this module holds all `n_layers`
    worth of parameters (distinguished by name), but a single call only
    executes layer `layer_idx`. The caller (the top-level `FNO` module) is
    responsible for looping over `range(n_layers)`, matching
    `FNO.forward`'s own loop over `self.fno_blocks(x, layer_idx)`.
    """

    in_channels: int
    out_channels: int
    n_modes: int
    n_layers: int = 1
    channel_mlp_expansion: float = 0.5
    param_dtype: jnp.dtype = jnp.float32

    @nn.compact
    def __call__(self, x: jnp.ndarray, layer_idx: int) -> jnp.ndarray:
        """x: (batch, in_channels, nx) -> (batch, out_channels, nx)."""
        if not (0 <= layer_idx < self.n_layers):
            raise ValueError(f"layer_idx={layer_idx} out of range [0, {self.n_layers})")
        is_last = layer_idx == self.n_layers - 1

        def _uniform_init(key, shape, dtype, fan_in):
            bound = 1.0 / (fan_in**0.5)
            return jax.random.uniform(
                key, shape, minval=-bound, maxval=bound, dtype=dtype
            )

        # fno_skip="linear": unbiased 1x1 conv/Dense, from the block's input.
        skip_fno_weight = self.param(
            f"fno_skip_weight_{layer_idx}",
            lambda key, shape, dtype: _uniform_init(
                key, shape, dtype, self.in_channels
            ),
            (self.out_channels, self.in_channels),
            self.param_dtype,
        )
        x_skip_fno = jnp.einsum("oi,bix->box", skip_fno_weight, x)

        # channel_mlp_skip="soft-gating": per-channel scalar, no bias, from
        # the block's input. Requires in_channels == out_channels, matching
        # PyTorch's SoftGating constraint (FNOBlocks always calls it with
        # in_channels == out_channels == hidden_channels for every layer).
        if self.in_channels != self.out_channels:
            raise ValueError(
                "soft-gating channel_mlp_skip requires in_channels == out_channels, "
                f"got {self.in_channels} != {self.out_channels}"
            )
        gate_weight = self.param(
            f"channel_mlp_skip_weight_{layer_idx}",
            lambda key, shape, dtype: jnp.ones(shape, dtype=dtype),
            (self.out_channels,),
            self.param_dtype,
        )
        x_skip_gate = gate_weight[None, :, None] * x

        x_spec = SpectralConv1D(
            in_channels=self.in_channels,
            out_channels=self.out_channels,
            n_modes=self.n_modes,
            name=f"convs_{layer_idx}",
        )(x)

        x = x_spec + x_skip_fno
        if not is_last:
            x = exact_gelu(x)

        hidden_channels = round(self.out_channels * self.channel_mlp_expansion)
        x = (
            ChannelMLP1D(
                in_channels=self.out_channels,
                hidden_channels=hidden_channels,
                n_layers=2,
                name=f"channel_mlp_{layer_idx}",
            )(x)
            + x_skip_gate
        )
        if not is_last:
            x = exact_gelu(x)

        return x
