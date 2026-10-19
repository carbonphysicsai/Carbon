"""Backbone gaps from the coverage probe (B0). FFTs over non-trailing dims
(AFNO's channels-last `rfft2` over H, W) lower by moving the transformed dims
last and back, under every allowlist that admits the FFT ops. The prospective
v6 allowlist alone adds `F.pad` with a constant (`aten.constant_pad_nd`,
PhysicsNeMo FNO), `view_as_real`, `abs`, `sign` and `eq.Scalar` (AFNO), and
`clamp` (UNO), batch norm in inference mode (U-shaped operators) and
instance norm (CODANO), `split_with_sizes`, `reciprocal` and `mul.Scalar`;
v5 stays refused for them. Interpolation's gather index,
`arange` arithmetic on no input, folds to a static index (UNO's resampling).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

V5 = Path(allowlist_module.__file__).with_name("allowlist_v5.json")
V6 = Path(allowlist_module.__file__).with_name("allowlist_v6.json")
torch = pytest.importorskip("torch")
jax = pytest.importorskip("jax")


def _lower_and_run(module, x, allowlist_path):
    import numpy as np

    allowlist = allowlist_module.load(allowlist_path)
    program = torch.export.export(module, (x,)).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowlist)
    got = rebuilt(jax.numpy.asarray(x.numpy()))[0]
    return doc, np.asarray(got)


class ChannelsLastSpectral(torch.nn.Module):
    """AFNO's pattern: rfft2 over (H, W) of a (B, H, W, C) tensor, a spectral
    scaling, and irfft2 back."""

    def __init__(self, norm):
        super().__init__()
        self.norm = norm

    def forward(self, x):
        z = torch.fft.rfft2(x, dim=(1, 2), norm=self.norm)
        z = z * 0.5
        return torch.fft.irfft2(z, s=x.shape[1:3], dim=(1, 2), norm=self.norm)


@pytest.mark.parametrize("path", [V5, V6])
@pytest.mark.parametrize("norm", ["backward", "ortho", "forward"])
def test_fft_over_non_trailing_dims_matches_torch(path, norm):
    import numpy as np

    module = ChannelsLastSpectral(norm)
    x = torch.randn(2, 6, 8, 3, generator=torch.Generator().manual_seed(3))
    doc, got = _lower_and_run(module, x, path)
    ops = [n["op"] for n in doc["graphs"][doc["entry"]]["nodes"]]
    assert ops.count("transpose") == 4 and ops.count("fft") == 2
    np.testing.assert_allclose(got, module(x).numpy(), rtol=2e-5, atol=2e-5)


class Pad(torch.nn.Module):
    def __init__(self, pad, value):
        super().__init__()
        self.pad, self.value = pad, value

    def forward(self, x):
        return torch.nn.functional.pad(x, self.pad, value=self.value) * 2.0


def test_v5_refuses_a_constant_pad():
    program = torch.export.export(Pad((1, 2), 0.0), (torch.ones(2, 3, 4),))
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(
            program.run_decompositions(), allowlist=allowlist_module.load(V5)
        )
    assert refused.value.code == "aten_op_not_allowlisted"


@pytest.mark.parametrize(
    "pad, value", [((1, 2), 0.0), ((0, 3, 2, 1), -1.5), ((-1, 2, 1, -1), 0.25)]
)
def test_a_constant_pad_matches_torch(pad, value):
    import numpy as np

    module = Pad(pad, value)
    x = torch.randn(2, 5, 4, generator=torch.Generator().manual_seed(5))
    doc, got = _lower_and_run(module, x, V6)
    assert "pad" in [n["op"] for n in doc["graphs"][doc["entry"]]["nodes"]]
    np.testing.assert_array_equal(got, module(x).numpy())


class AfnoOps(torch.nn.Module):
    """AFNO's softshrink and complex-to-pairs steps."""

    def forward(self, x):
        z = torch.fft.rfft(x, dim=-1)
        pairs = torch.view_as_real(z)
        shrunk = torch.sign(pairs) * torch.relu(torch.abs(pairs) - 0.1)
        return shrunk.sum(-1) + (x == 0.5).to(x.dtype)[..., : shrunk.shape[-2]]


def test_afno_ops_match_torch_and_v5_refuses_them():
    import numpy as np

    module = AfnoOps()
    x = torch.randn(2, 3, 8, generator=torch.Generator().manual_seed(7))
    x[0, 0, 1] = 0.5
    _, got = _lower_and_run(module, x, V6)
    np.testing.assert_allclose(got, module(x).numpy(), rtol=2e-5, atol=2e-5)
    program = torch.export.export(module, (x,)).run_decompositions()
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V5))
    assert refused.value.code == "aten_op_not_allowlisted"


class Clamp(torch.nn.Module):
    def forward(self, x):
        return torch.clamp(x, -0.5, 0.75) * 3.0


def test_clamp_matches_torch_values_and_gradient_at_the_bounds():
    import numpy as np

    module = Clamp()
    x = torch.tensor([[-1.0, -0.5, 0.0, 0.75, 2.0]])
    doc, got = _lower_and_run(module, x, V6)
    np.testing.assert_array_equal(got, module(x).numpy())
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowlist_module.load(V6))
    grad = jax.grad(lambda v: rebuilt(v)[0].sum())(jax.numpy.asarray(x.numpy()))
    want = x.clone().requires_grad_(True)
    module(want).sum().backward()
    np.testing.assert_array_equal(np.asarray(grad), want.grad.numpy())


class Interpolate(torch.nn.Module):
    def __init__(self, mode, **kw):
        super().__init__()
        self.mode, self.kw = mode, kw

    def forward(self, x):
        return torch.nn.functional.interpolate(x, mode=self.mode, **self.kw) * 2.0


@pytest.mark.parametrize(
    "mode, kw",
    [
        ("nearest", {"scale_factor": 2}),
        ("nearest-exact", {"size": 45}),
        ("linear", {"size": 30, "align_corners": False}),
    ],
)
def test_interpolation_index_arithmetic_folds_to_a_static_gather(mode, kw):
    import numpy as np

    module = Interpolate(mode, **kw)
    x = torch.randn(2, 3, 60, generator=torch.Generator().manual_seed(9))
    doc, got = _lower_and_run(module, x, V6)
    assert "gather" not in [n["op"] for n in doc["graphs"][doc["entry"]]["nodes"]]
    np.testing.assert_allclose(got, module(x).numpy(), rtol=1e-6, atol=1e-6)


class Norms(torch.nn.Module):
    """Inference batch norm, instance norm, a three-way split, a reciprocal and
    a scalar multiply: the U-Net / CODANO / OFormer / GNOT steps."""

    def __init__(self):
        super().__init__()
        self.bn = torch.nn.BatchNorm1d(4)
        self.inorm = torch.nn.InstanceNorm1d(4, affine=True)
        with torch.no_grad():
            for p in (*self.bn.parameters(), *self.inorm.parameters()):
                p.copy_(torch.rand(p.shape, generator=torch.Generator().manual_seed(1)))
            self.bn.running_mean.uniform_(-1, 1)
            self.bn.running_var.uniform_(0.5, 2)

    def forward(self, x):
        a, b, c = torch.split(self.bn(x) + self.inorm(x), [1, 2, 1], dim=1)
        return torch.cat([c, a * 0.5, torch.reciprocal(b * b + 1.0)], dim=1)


def test_norms_split_reciprocal_match_torch_values_and_gradients():
    import numpy as np

    module = Norms().eval()
    x = torch.randn(3, 4, 10, generator=torch.Generator().manual_seed(4))
    names = [n for n, _ in module.named_parameters()]
    params = [p.detach() for _, p in module.named_parameters()]
    buffers = dict(module.named_buffers())

    def apply(ps, inputs):
        return torch.func.functional_call(
            module, (dict(zip(names, ps)), buffers), (inputs,)
        )

    allowlist = allowlist_module.load(V6)
    _, core = lower_torch.export(apply, params, x)
    doc, _ = lower_torch.lower(core, allowlist=allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowlist)
    weights = [jax.numpy.asarray(p.numpy()) for p in params]
    value = jax.numpy.asarray(x.numpy())
    np.testing.assert_allclose(
        np.asarray(rebuilt(*weights, value)[0]),
        module(x).detach().numpy(),
        rtol=1e-5,
        atol=1e-5,
    )
    got = jax.grad(lambda ws: rebuilt(*ws, value)[0].sum())(weights)
    want = [p.clone().requires_grad_(True) for p in params]
    apply(want, x).sum().backward()
    for g, w in zip(got, want):
        np.testing.assert_allclose(np.asarray(g), w.grad.numpy(), rtol=1e-4, atol=1e-5)
    with pytest.raises(graph.GraphRefused):
        lower_torch.lower(core, allowlist=allowlist_module.load(V5))
