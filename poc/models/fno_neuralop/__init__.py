"""JAX/Flax Linen FNO port structurally mirroring PyTorch `neuralop.models.FNO`.

Channel convention deliberately matches PyTorch (`(batch, channels,
*spatial)`, channels-first) rather than idiomatic JAX channels-last, so
weights can be transferred between the two implementations for parity
testing without an axis transpose. See
`Design_Specs/Burgers_FNO_JAX_Neuraloperator_Parity.md` for the module
mapping and the verified parity details this port depends on.
"""

from __future__ import annotations

from poc.models.fno_neuralop.channel_mlp import ChannelMLP1D
from poc.models.fno_neuralop.embeddings import GridEmbedding1D
from poc.models.fno_neuralop.fno_block import FNOBlocks1D
from poc.models.fno_neuralop.fno import FNO
from poc.models.fno_neuralop.spectral_conv import SpectralConv1D

__all__ = ["SpectralConv1D", "ChannelMLP1D", "GridEmbedding1D", "FNOBlocks1D", "FNO"]
