"""Top-level FNO, ported from `neuralop.models.fno.FNO` (1D case).

Forward pass (verified against `FNO.forward`):

    x = GridEmbedding1D(x)                         # if positional_embedding == "grid"
    x = ChannelMLP1D(lifting_in_channels -> hidden_channels)(x)   # "lifting"
    for i in range(n_layers): x = FNOBlocks1D(x, i)               # "fno_blocks"
    x = ChannelMLP1D(hidden_channels -> out_channels)(x)          # "projection"

`lifting_in_channels = in_channels + 1` when the grid positional embedding
is enabled (it appends one coordinate channel), matching
`FNO.__init__`'s `lifting_in_channels += self.n_dim` for `n_dim=1`.

Only what v1 needs is ported: `positional_embedding in {"grid", None}`,
`norm=None`, `complex_data=False`, `domain_padding=None`,
`resolution_scaling_factor=None`, `use_channel_mlp=True`,
`fno_skip="linear"`, `channel_mlp_skip="soft-gating"`, postactivation only
— all PyTorch defaults except `positional_embedding=None`, which PyTorch
also supports natively. See
`Design_Specs/Burgers_FNO_JAX_Neuraloperator_Parity.md` §3 for what's
deliberately not ported (tensor factorization, complex data, domain
padding, resolution scaling, non-default norms).
"""

from __future__ import annotations

from typing import Optional

import jax.numpy as jnp
import flax.linen as nn

from poc.models.fno_neuralop.channel_mlp import ChannelMLP1D
from poc.models.fno_neuralop.embeddings import GridEmbedding1D
from poc.models.fno_neuralop.fno_block import FNOBlocks1D


class FNO(nn.Module):
    """1D FNO: lifting -> `n_layers` Fourier layers -> projection.

    Parameters mirror `neuralop.models.fno.FNO`'s constructor where this
    port's scope allows (see module docstring for what's excluded).
    """

    n_modes: int
    in_channels: int
    out_channels: int
    hidden_channels: int
    n_layers: int = 4
    lifting_channel_ratio: float = 2
    projection_channel_ratio: float = 2
    positional_embedding: Optional[str] = "grid"
    channel_mlp_expansion: float = 0.5

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """x: (batch, in_channels, nx) -> (batch, out_channels, nx)."""
        lifting_channels = int(self.lifting_channel_ratio * self.hidden_channels)
        projection_channels = int(self.projection_channel_ratio * self.hidden_channels)

        lifting_in_channels = self.in_channels
        if self.positional_embedding == "grid":
            x = GridEmbedding1D()(x)
            lifting_in_channels += 1
        elif self.positional_embedding is not None:
            raise NotImplementedError(
                f"positional_embedding={self.positional_embedding!r} not ported; "
                'use "grid" or None.'
            )

        x = ChannelMLP1D(
            in_channels=lifting_in_channels,
            out_channels=self.hidden_channels,
            hidden_channels=lifting_channels,
            n_layers=2,
            name="lifting",
        )(x)

        fno_blocks = FNOBlocks1D(
            in_channels=self.hidden_channels,
            out_channels=self.hidden_channels,
            n_modes=self.n_modes,
            n_layers=self.n_layers,
            channel_mlp_expansion=self.channel_mlp_expansion,
            name="fno_blocks",
        )
        for layer_idx in range(self.n_layers):
            x = fno_blocks(x, layer_idx)

        x = ChannelMLP1D(
            in_channels=self.hidden_channels,
            out_channels=self.out_channels,
            hidden_channels=projection_channels,
            n_layers=2,
            name="projection",
        )(x)

        return x
