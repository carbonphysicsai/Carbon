"""Cross-framework parity tests: the JAX/Flax FNO port vs. PyTorch `neuralop`.

Methodology (see `Design_Specs/Burgers_FNO_JAX_Neuraloperator_Parity.md` §9):
for each layer, construct one shared set of weights independently of either
framework, inject it into both implementations' parameter storage, and diff
the forward-pass outputs at a stated fp32 tolerance. Initialization schemes
are *not* expected to match between the two frameworks — only the forward
computation, given identical weights.

Requires both the JAX/Flax stack (`carbon[poc]`) and the real PyTorch
`neuraloperator` package (`carbon[neuraloperator]`) installed together;
skips gracefully if either is absent so default CI stays green regardless
of which extras are installed.
"""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")
jax = pytest.importorskip("jax")
flax = pytest.importorskip("flax")
torch = pytest.importorskip("torch")
neuralop = pytest.importorskip("neuralop")
pytest.importorskip("tltorch")

import jax.numpy as jnp
import flax.linen as nn
from tltorch.factorized_tensors.core import FactorizedTensor
from neuralop.layers.spectral_convolution import SpectralConv as TorchSpectralConv
from neuralop.layers.channel_mlp import ChannelMLP as TorchChannelMLP
from neuralop.layers.embeddings import GridEmbeddingND as TorchGridEmbeddingND
from neuralop.layers.fno_block import FNOBlocks as TorchFNOBlocks

from poc.models.fno_neuralop.spectral_conv import SpectralConv1D
from poc.models.fno_neuralop.channel_mlp import ChannelMLP1D
from poc.models.fno_neuralop.embeddings import GridEmbedding1D
from poc.models.fno_neuralop.fno_block import FNOBlocks1D

pytestmark = [pytest.mark.backend_jax, pytest.mark.backend_torch]

# Single-operation layers (one FFT pair + one contraction, no activation
# compounding): tight fp32 tolerance.
RTOL = 1e-5
ATOL = 1e-6

# Multi-layer compositions (chained matmul + exact-gelu): fp32 rounding
# compounds across layers. Verified this is ordinary floating-point noise,
# not an architecture mismatch — failures at the tighter tolerance above
# were confined to <0.4% of elements, all near zero-crossings of the
# reference output (e.g. diff=1.8e-6 at |y_torch|=4.1e-2), and vanished
# entirely at this tolerance.
RTOL_MULTILAYER = 1e-4
ATOL_MULTILAYER = 1e-5


def _kept_modes(n_modes: int, nx: int) -> int:
    return min(n_modes // 2 + 1, nx // 2 + 1)


@pytest.mark.parametrize(
    ("nx", "n_modes", "in_channels", "out_channels", "bias"),
    [
        (128, 16, 3, 4, True),
        (128, 16, 3, 4, False),
        (65, 10, 2, 2, True),  # odd nx: no Nyquist-zeroing branch
        (32, 32, 1, 1, True),  # n_modes == nx: no truncation
        (17, 4, 2, 3, True),  # odd nx, small modes
    ],
)
def test_spectral_conv1d_matches_pytorch(nx, n_modes, in_channels, out_channels, bias):
    rng = np.random.default_rng(0)
    kept_modes = _kept_modes(n_modes, nx)
    weight_real = rng.standard_normal((in_channels, out_channels, kept_modes)).astype(
        np.float32
    )
    weight_imag = rng.standard_normal((in_channels, out_channels, kept_modes)).astype(
        np.float32
    )
    bias_vec = (
        rng.standard_normal(out_channels).astype(np.float32) if bias else None
    )
    x_np = rng.standard_normal((2, in_channels, nx)).astype(np.float32)

    torch_conv = TorchSpectralConv(
        in_channels,
        out_channels,
        (n_modes,),
        bias=bias,
        complex_data=False,
        fft_norm="forward",
    )
    w_complex = torch.from_numpy(weight_real + 1j * weight_imag).to(torch.cfloat)
    torch_conv.weight = FactorizedTensor.from_tensor(
        w_complex, rank=None, factorization="ComplexDense"
    )
    if bias:
        with torch.no_grad():
            torch_conv.bias.data = (
                torch.from_numpy(bias_vec).to(torch.float32).view(out_channels, 1)
            )

    with torch.no_grad():
        y_torch = torch_conv(torch.from_numpy(x_np)).numpy()

    model = SpectralConv1D(
        in_channels=in_channels,
        out_channels=out_channels,
        n_modes=n_modes,
        bias=bias,
    )
    params = model.init(jax.random.PRNGKey(0), jnp.asarray(x_np))
    params = flax.core.unfreeze(params)
    params["params"]["weight_real"] = jnp.asarray(weight_real)
    params["params"]["weight_imag"] = jnp.asarray(weight_imag)
    if bias:
        params["params"]["bias"] = jnp.asarray(bias_vec)
    y_jax = np.asarray(model.apply(params, jnp.asarray(x_np)))

    np.testing.assert_allclose(y_jax, y_torch, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize(
    ("nx", "in_channels", "out_channels", "hidden_channels", "n_layers"),
    [
        (128, 3, 5, 8, 2),  # lifting-like: in != out
        (128, 8, 3, 16, 2),  # projection-like
        (64, 4, 4, 4, 1),  # single-layer edge case (i == 0 == n_layers - 1)
        (32, 4, 4, 8, 3),  # n_layers=3: exercises the internal hidden->hidden layer
    ],
)
def test_channel_mlp1d_matches_pytorch(
    nx, in_channels, out_channels, hidden_channels, n_layers
):
    rng = np.random.default_rng(0)

    torch_mlp = TorchChannelMLP(
        in_channels=in_channels,
        out_channels=out_channels,
        hidden_channels=hidden_channels,
        n_layers=n_layers,
    )

    weights, biases = [], []
    for fc in torch_mlp.fcs:
        fan_out, fan_in = fc.weight.shape[0], fc.weight.shape[1]
        w = rng.standard_normal((fan_out, fan_in)).astype(np.float32)
        b = rng.standard_normal((fan_out,)).astype(np.float32)
        weights.append(w)
        biases.append(b)
        with torch.no_grad():
            fc.weight.data = torch.from_numpy(w).view(fan_out, fan_in, 1)
            fc.bias.data = torch.from_numpy(b)

    x_np = rng.standard_normal((2, in_channels, nx)).astype(np.float32)

    with torch.no_grad():
        y_torch = torch_mlp(torch.from_numpy(x_np)).numpy()

    model = ChannelMLP1D(
        in_channels=in_channels,
        out_channels=out_channels,
        hidden_channels=hidden_channels,
        n_layers=n_layers,
    )
    params = model.init(jax.random.PRNGKey(0), jnp.asarray(x_np))
    params = flax.core.unfreeze(params)
    for i, (w, b) in enumerate(zip(weights, biases)):
        params["params"][f"weight_{i}"] = jnp.asarray(w)
        params["params"][f"bias_{i}"] = jnp.asarray(b)
    y_jax = np.asarray(model.apply(params, jnp.asarray(x_np)))

    np.testing.assert_allclose(
        y_jax, y_torch, rtol=RTOL_MULTILAYER, atol=ATOL_MULTILAYER
    )


@pytest.mark.parametrize(("nx", "channels"), [(128, 3), (65, 1), (17, 5)])
def test_grid_embedding1d_matches_pytorch(nx, channels):
    rng = np.random.default_rng(0)
    x_np = rng.standard_normal((2, channels, nx)).astype(np.float32)

    torch_emb = TorchGridEmbeddingND(
        in_channels=channels, dim=1, grid_boundaries=[[0.0, 1.0]]
    )
    y_torch = torch_emb(torch.from_numpy(x_np)).numpy()

    jax_emb = GridEmbedding1D()
    y_jax = np.asarray(jax_emb.apply({}, jnp.asarray(x_np)))

    # Pure coordinate generation, no float accumulation: bit-exact.
    np.testing.assert_allclose(y_jax, y_torch, rtol=RTOL, atol=ATOL)


class _FNOBlocksStack(nn.Module):
    """Test-only wrapper looping over `n_layers`, matching how the
    top-level `FNO` module will drive `FNOBlocks1D` (see fno_block.py's
    class docstring: one shared instance, one call per layer index)."""

    in_channels: int
    out_channels: int
    n_modes: int
    n_layers: int
    channel_mlp_expansion: float = 0.5

    @nn.compact
    def __call__(self, x):
        block = FNOBlocks1D(
            in_channels=self.in_channels,
            out_channels=self.out_channels,
            n_modes=self.n_modes,
            n_layers=self.n_layers,
            channel_mlp_expansion=self.channel_mlp_expansion,
        )
        for i in range(self.n_layers):
            x = block(x, i)
        return x


@pytest.mark.parametrize(
    ("nx", "n_modes", "channels", "n_layers"),
    [
        (64, 8, 6, 1),
        (64, 8, 6, 3),
        (128, 16, 4, 2),
        (64, 8, 6, 4),  # matches poc's existing FNO1dConfig default depth
    ],
)
def test_fno_blocks1d_matches_pytorch(nx, n_modes, channels, n_layers):
    rng = np.random.default_rng(0)
    kept_modes = _kept_modes(n_modes, nx)
    hidden = round(channels * 0.5)

    torch_blocks = TorchFNOBlocks(
        in_channels=channels,
        out_channels=channels,
        n_modes=(n_modes,),
        n_layers=n_layers,
        channel_mlp_expansion=0.5,
        fno_skip="linear",
        channel_mlp_skip="soft-gating",
        norm=None,
        preactivation=False,
    )

    x_np = rng.standard_normal((2, channels, nx)).astype(np.float32)

    wrapper = _FNOBlocksStack(
        in_channels=channels, out_channels=channels, n_modes=n_modes, n_layers=n_layers
    )
    params = flax.core.unfreeze(wrapper.init(jax.random.PRNGKey(0), jnp.asarray(x_np)))
    layer_params = params["params"]["FNOBlocks1D_0"]

    for i in range(n_layers):
        w_real = rng.standard_normal((channels, channels, kept_modes)).astype(np.float32)
        w_imag = rng.standard_normal((channels, channels, kept_modes)).astype(np.float32)
        conv_bias = rng.standard_normal(channels).astype(np.float32)
        w_complex = torch.from_numpy(w_real + 1j * w_imag).to(torch.cfloat)
        torch_blocks.convs[i].weight = FactorizedTensor.from_tensor(
            w_complex, rank=None, factorization="ComplexDense"
        )
        with torch.no_grad():
            torch_blocks.convs[i].bias.data = torch.from_numpy(conv_bias).view(channels, 1)
        layer_params[f"convs_{i}"] = {
            "weight_real": jnp.asarray(w_real),
            "weight_imag": jnp.asarray(w_imag),
            "bias": jnp.asarray(conv_bias),
        }

        skip_w = rng.standard_normal((channels, channels)).astype(np.float32)
        with torch.no_grad():
            torch_blocks.fno_skips[i].conv.weight.data = torch.from_numpy(skip_w).view(
                channels, channels, 1
            )
        layer_params[f"fno_skip_weight_{i}"] = jnp.asarray(skip_w)

        gate_w = rng.standard_normal((channels,)).astype(np.float32)
        with torch.no_grad():
            torch_blocks.channel_mlp_skips[i].weight.data = torch.from_numpy(gate_w).view(
                1, channels, 1
            )
        layer_params[f"channel_mlp_skip_weight_{i}"] = jnp.asarray(gate_w)

        w0 = rng.standard_normal((hidden, channels)).astype(np.float32)
        b0 = rng.standard_normal((hidden,)).astype(np.float32)
        w1 = rng.standard_normal((channels, hidden)).astype(np.float32)
        b1 = rng.standard_normal((channels,)).astype(np.float32)
        with torch.no_grad():
            torch_blocks.channel_mlp[i].fcs[0].weight.data = torch.from_numpy(w0).view(
                hidden, channels, 1
            )
            torch_blocks.channel_mlp[i].fcs[0].bias.data = torch.from_numpy(b0)
            torch_blocks.channel_mlp[i].fcs[1].weight.data = torch.from_numpy(w1).view(
                channels, hidden, 1
            )
            torch_blocks.channel_mlp[i].fcs[1].bias.data = torch.from_numpy(b1)
        layer_params[f"channel_mlp_{i}"] = {
            "weight_0": jnp.asarray(w0),
            "bias_0": jnp.asarray(b0),
            "weight_1": jnp.asarray(w1),
            "bias_1": jnp.asarray(b1),
        }

    params["params"]["FNOBlocks1D_0"] = layer_params

    x_torch = torch.from_numpy(x_np)
    with torch.no_grad():
        for i in range(n_layers):
            x_torch = torch_blocks(x_torch, i)
    y_torch = x_torch.numpy()

    y_jax = np.asarray(wrapper.apply(params, jnp.asarray(x_np)))

    # Deeper stacks compound fp32 rounding further still, but relative error
    # stays bounded because output magnitude grows with the same random-walk
    # weights on both sides (verified up to 6 layers deep in the design
    # phase, well past this test's max of 4). RTOL_MULTILAYER holds.
    np.testing.assert_allclose(
        y_jax, y_torch, rtol=RTOL_MULTILAYER, atol=ATOL_MULTILAYER
    )
