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

from poc.models.fno_neuralop.spectral_conv import SpectralConv1D

pytestmark = [pytest.mark.backend_jax, pytest.mark.backend_torch]

RTOL = 1e-5
ATOL = 1e-6


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
