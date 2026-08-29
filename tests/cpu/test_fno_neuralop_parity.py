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

import flax.linen as nn
import jax.numpy as jnp
from neuralop.layers.channel_mlp import ChannelMLP as TorchChannelMLP
from neuralop.layers.embeddings import GridEmbeddingND as TorchGridEmbeddingND
from neuralop.layers.fno_block import FNOBlocks as TorchFNOBlocks
from neuralop.layers.spectral_convolution import SpectralConv as TorchSpectralConv
from neuralop.models.fno import FNO as TorchFNO
from tltorch.factorized_tensors.core import FactorizedTensor

from poc.models.fno_neuralop.channel_mlp import ChannelMLP1D
from poc.models.fno_neuralop.embeddings import GridEmbedding1D
from poc.models.fno_neuralop.fno import FNO
from poc.models.fno_neuralop.fno_block import FNOBlocks1D
from poc.models.fno_neuralop.spectral_conv import SpectralConv1D

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


def _inject_channel_mlp_weights(rng, torch_mlp, dims):
    """dims: [(fan_out, fan_in), ...] per layer, in `torch_mlp.fcs` order.

    Weights are scaled ~1/sqrt(fan_in) (realistic init magnitude) rather
    than raw N(0,1) — see `test_fno_matches_pytorch`'s docstring for why
    this matters for deep compositions.
    """
    out = {}
    for i, (fc, (fan_out, fan_in)) in enumerate(zip(torch_mlp.fcs, dims)):
        bound = 1.0 / (fan_in**0.5)
        w = (bound * rng.standard_normal((fan_out, fan_in))).astype(np.float32)
        b = (bound * rng.standard_normal((fan_out,))).astype(np.float32)
        with torch.no_grad():
            fc.weight.data = torch.from_numpy(w).view(fan_out, fan_in, 1)
            fc.bias.data = torch.from_numpy(b)
        out[f"weight_{i}"] = jnp.asarray(w)
        out[f"bias_{i}"] = jnp.asarray(b)
    return out


def _inject_fno_blocks_weights(
    rng, torch_blocks, n_layers, channels, kept_modes, hidden
):
    """Builds one shared, realistically-scaled weight set per layer and
    injects it into both `torch_blocks` (in place) and a returned JAX
    param dict for `FNOBlocks1D`."""
    spec_std = (2.0 / (channels + channels)) ** 0.5
    skip_bound = 1.0 / (channels**0.5)
    layer_params = {}
    for i in range(n_layers):
        w_real = (
            spec_std * rng.standard_normal((channels, channels, kept_modes))
        ).astype(np.float32)
        w_imag = (
            spec_std * rng.standard_normal((channels, channels, kept_modes))
        ).astype(np.float32)
        conv_bias = (spec_std * rng.standard_normal(channels)).astype(np.float32)
        w_complex = torch.from_numpy(w_real + 1j * w_imag).to(torch.cfloat)
        torch_blocks.convs[i].weight = FactorizedTensor.from_tensor(
            w_complex, rank=None, factorization="ComplexDense"
        )
        with torch.no_grad():
            torch_blocks.convs[i].bias.data = torch.from_numpy(conv_bias).view(
                channels, 1
            )
        layer_params[f"convs_{i}"] = {
            "weight_real": jnp.asarray(w_real),
            "weight_imag": jnp.asarray(w_imag),
            "bias": jnp.asarray(conv_bias),
        }

        skip_w = (skip_bound * rng.standard_normal((channels, channels))).astype(
            np.float32
        )
        with torch.no_grad():
            torch_blocks.fno_skips[i].conv.weight.data = torch.from_numpy(skip_w).view(
                channels, channels, 1
            )
        layer_params[f"fno_skip_weight_{i}"] = jnp.asarray(skip_w)

        gate_w = (0.1 * rng.standard_normal((channels,))).astype(np.float32)
        with torch.no_grad():
            torch_blocks.channel_mlp_skips[i].weight.data = torch.from_numpy(
                gate_w
            ).view(1, channels, 1)
        layer_params[f"channel_mlp_skip_weight_{i}"] = jnp.asarray(gate_w)

        mlp_params = _inject_channel_mlp_weights(
            rng, torch_blocks.channel_mlp[i], [(hidden, channels), (channels, hidden)]
        )
        layer_params[f"channel_mlp_{i}"] = {
            "weight_0": mlp_params["weight_0"],
            "bias_0": mlp_params["bias_0"],
            "weight_1": mlp_params["weight_1"],
            "bias_1": mlp_params["bias_1"],
        }
    return layer_params


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
    bias_vec = rng.standard_normal(out_channels).astype(np.float32) if bias else None
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
    ("n_modes", "in_channels", "out_channels", "bias", "init_nx", "apply_nx"),
    [
        (16, 2, 3, True, 8, 32),  # the exact scenario from review: init
        # resolution too small to hold all requested modes (nfreq=5 < 9),
        # apply resolution large enough to hold them all (nfreq=17 >= 9)
        (16, 2, 3, True, 128, 32),  # init large, apply smaller
        (8, 1, 1, False, 64, 64),  # same resolution: still works (regression guard)
    ],
)
def test_spectral_conv1d_reused_across_resolutions(
    n_modes, in_channels, out_channels, bias, init_nx, apply_nx
):
    """The same initialized parameters must apply cleanly at a different
    input resolution than the one used at `init()` -- this is FNO's whole
    discretization-invariance premise, and PyTorch's `SpectralConv`
    supports it because its weight shape is fixed by `n_modes` alone at
    construction time, never by whichever input happened to be passed
    through first.

    Regression test for a real bug: an earlier version of `SpectralConv1D`
    computed the *allocated* parameter shape as
    `min(n_modes // 2 + 1, nx // 2 + 1)` at init time, binding it to
    whichever `nx` `init()` was called with. Reusing those params at a
    different `nx` then asked Flax for a differently-sized slice than what
    was actually stored, raising `flax.errors.ScopeParamShapeError`. Note
    this must exercise the *actual* init()-produced params unmodified —
    overwriting a param's array by direct dict assignment (as the other
    tests in this file do, to inject shared cross-framework weights)
    bypasses Flax's shape check entirely and would silently pass even
    against the buggy code, which is why this test is structured
    differently from the rest of the file.
    """
    rng = np.random.default_rng(0)
    allocated_modes = n_modes // 2 + 1

    model = SpectralConv1D(
        in_channels=in_channels, out_channels=out_channels, n_modes=n_modes, bias=bias
    )
    x_init = jnp.asarray(
        rng.standard_normal((2, in_channels, init_nx)).astype(np.float32)
    )
    params = model.init(jax.random.PRNGKey(0), x_init)

    # Allocation must depend on n_modes alone, not on init_nx.
    assert params["params"]["weight_real"].shape == (
        in_channels,
        out_channels,
        allocated_modes,
    )

    x_apply_np = rng.standard_normal((2, in_channels, apply_nx)).astype(np.float32)
    x_apply = jnp.asarray(x_apply_np)
    # Must not raise flax.errors.ScopeParamShapeError.
    y = model.apply(params, x_apply)

    assert y.shape == (2, out_channels, apply_nx)
    assert bool(jnp.isfinite(y).all())

    # Numeric cross-check against PyTorch at the apply resolution, with a
    # freshly (not init()-derived) shared weight set of the same allocated
    # shape -- confirms this isn't just "doesn't crash" but matches
    # upstream's own discretization-invariant behavior numerically too.
    weight_real = rng.standard_normal(
        (in_channels, out_channels, allocated_modes)
    ).astype(np.float32)
    weight_imag = rng.standard_normal(
        (in_channels, out_channels, allocated_modes)
    ).astype(np.float32)
    bias_vec = rng.standard_normal(out_channels).astype(np.float32) if bias else None

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

    params = flax.core.unfreeze(params)
    params["params"]["weight_real"] = jnp.asarray(weight_real)
    params["params"]["weight_imag"] = jnp.asarray(weight_imag)
    if bias:
        params["params"]["bias"] = jnp.asarray(bias_vec)

    with torch.no_grad():
        y_torch = torch_conv(torch.from_numpy(x_apply_np)).numpy()
    y_jax = np.asarray(model.apply(params, x_apply))

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

    dims = [(fc.weight.shape[0], fc.weight.shape[1]) for fc in torch_mlp.fcs]

    x_np = rng.standard_normal((2, in_channels, nx)).astype(np.float32)

    model = ChannelMLP1D(
        in_channels=in_channels,
        out_channels=out_channels,
        hidden_channels=hidden_channels,
        n_layers=n_layers,
    )
    params = flax.core.unfreeze(model.init(jax.random.PRNGKey(0), jnp.asarray(x_np)))
    mlp_params = _inject_channel_mlp_weights(rng, torch_mlp, dims)
    for key, value in mlp_params.items():
        params["params"][key] = value

    with torch.no_grad():
        y_torch = torch_mlp(torch.from_numpy(x_np)).numpy()

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
    params["params"]["FNOBlocks1D_0"] = _inject_fno_blocks_weights(
        rng, torch_blocks, n_layers, channels, kept_modes, hidden
    )

    x_torch = torch.from_numpy(x_np)
    with torch.no_grad():
        for i in range(n_layers):
            x_torch = torch_blocks(x_torch, i)
    y_torch = x_torch.numpy()

    y_jax = np.asarray(wrapper.apply(params, jnp.asarray(x_np)))

    # Realistically-scaled weights (see _inject_fno_blocks_weights) keep
    # activations well-conditioned even through several layers, so the
    # tight single-operation tolerance holds here too -- observed
    # max_abs_diff ~3e-7 at n_layers=4 during test development.
    np.testing.assert_allclose(y_jax, y_torch, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize(
    ("nx", "n_modes", "in_channels", "out_channels", "hidden_channels", "n_layers"),
    [
        (
            64,
            8,
            1,
            1,
            16,
            4,
        ),  # matches the Burgers use case: 1->1 channel, realistic depth
        (32, 8, 2, 3, 8, 2),
        (128, 16, 1, 1, 32, 4),
    ],
)
def test_fno_matches_pytorch(
    nx, n_modes, in_channels, out_channels, hidden_channels, n_layers
):
    """Full lifting -> FNOBlocks -> projection stack, end to end.

    Uses realistically-scaled weights (~1/sqrt(fan_in), matching each
    layer's own natural init magnitude) rather than raw N(0,1): with 4
    layers of width up to 32 and unscaled N(0,1) weights, both
    implementations' activations blow up to O(1e4)+ before the final
    layer, at which point a passing np.allclose is nearly meaningless
    (any two large, similarly-scaled-but-wrong numbers satisfy a relative
    tolerance). Rescaled, both implementations stay in a numerically
    sane O(1) regime and the tight tolerance actually tests precision.
    """
    rng = np.random.default_rng(0)
    kept_modes = _kept_modes(n_modes, nx)
    lifting_channels = 2 * hidden_channels
    projection_channels = 2 * hidden_channels
    block_hidden = round(hidden_channels * 0.5)

    torch_fno = TorchFNO(
        n_modes=(n_modes,),
        in_channels=in_channels,
        out_channels=out_channels,
        hidden_channels=hidden_channels,
        n_layers=n_layers,
        lifting_channel_ratio=2,
        projection_channel_ratio=2,
        positional_embedding="grid",
        norm=None,
        channel_mlp_expansion=0.5,
        channel_mlp_skip="soft-gating",
        fno_skip="linear",
    )

    x_np = rng.standard_normal((2, in_channels, nx)).astype(np.float32)

    jax_fno = FNO(
        n_modes=n_modes,
        in_channels=in_channels,
        out_channels=out_channels,
        hidden_channels=hidden_channels,
        n_layers=n_layers,
    )
    params = flax.core.unfreeze(jax_fno.init(jax.random.PRNGKey(0), jnp.asarray(x_np)))

    # lifting: (in_channels + 1 grid channel) -> lifting_channels -> hidden_channels
    lifting_dims = [
        (lifting_channels, in_channels + 1),
        (hidden_channels, lifting_channels),
    ]
    params["params"]["lifting"] = _inject_channel_mlp_weights(
        rng, torch_fno.lifting, lifting_dims
    )

    params["params"]["fno_blocks"] = _inject_fno_blocks_weights(
        rng, torch_fno.fno_blocks, n_layers, hidden_channels, kept_modes, block_hidden
    )

    # projection: hidden_channels -> projection_channels -> out_channels
    projection_dims = [
        (projection_channels, hidden_channels),
        (out_channels, projection_channels),
    ]
    params["params"]["projection"] = _inject_channel_mlp_weights(
        rng, torch_fno.projection, projection_dims
    )

    with torch.no_grad():
        y_torch = torch_fno(torch.from_numpy(x_np)).numpy()

    y_jax = np.asarray(jax_fno.apply(params, jnp.asarray(x_np)))

    np.testing.assert_allclose(y_jax, y_torch, rtol=RTOL, atol=ATOL)
