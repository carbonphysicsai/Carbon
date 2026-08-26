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
from tltorch.factorized_tensors.core import FactorizedTensor
from neuralop.layers.spectral_convolution import SpectralConv as TorchSpectralConv
from neuralop.layers.channel_mlp import ChannelMLP as TorchChannelMLP

from poc.models.fno_neuralop.spectral_conv import SpectralConv1D
from poc.models.fno_neuralop.channel_mlp import ChannelMLP1D

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
