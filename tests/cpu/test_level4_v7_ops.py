"""Allowlist v7 (Test Lead's assignment, owner-approved 2026-10-20; the
Validator reviews it): v6 plus the B2 backbone ops neg, log, leaky_relu,
any.dim and the antialiased bicubic resize, and two argument forms, strided
slice_scatter and transposed convolution, admitted only where an allowlist
entry names them (`forms`). rand_like stays refused, with its reason recorded.
Each lowering matches torch in values and gradients on edge cases, repeats
bit for bit, and expands to a bounded number of nodes; v6 refuses all of it
and keeps every op it allowed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

V6 = Path(allowlist_module.__file__).with_name("allowlist_v6.json")
V7 = Path(allowlist_module.__file__).with_name("allowlist_v7.json")
torch = pytest.importorskip("torch")
jax = pytest.importorskip("jax")
np = pytest.importorskip("numpy")


def _rebuilt(module, example, path=V7):
    allowlist = allowlist_module.load(path)
    program = torch.export.export(module, example).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    run = interpret.rebuild(parsed, allowlist)
    # Module parameters are the graph's leading inputs, in export order.
    weights = [jax.numpy.asarray(p.detach().numpy()) for p in module.parameters()]
    return doc, lambda *xs: run(*weights, *xs)


def _ops(doc):
    return [n["op"] for g in doc["graphs"].values() for n in g["nodes"]]


def _jax(*tensors):
    return [jax.numpy.asarray(t.detach().numpy()) for t in tensors]


def _grads(module, rebuilt, tensors):
    """The input gradients of sum(out * probe) in torch and in the rebuild."""
    inputs = [t.clone().requires_grad_(True) for t in tensors]
    out = module(*inputs)
    probe = torch.linspace(-1.5, 2.0, out.numel(), dtype=out.dtype).reshape(out.shape)
    (out * probe).sum().backward()
    want = [t.grad.numpy() for t in inputs]
    p = jax.numpy.asarray(probe.numpy())
    got = jax.grad(
        lambda *a: (rebuilt(*a)[0] * p).sum(), argnums=tuple(range(len(tensors)))
    )(*_jax(*tensors))
    return [np.asarray(g) for g in got], want


class Neg(torch.nn.Module):
    def forward(self, x):
        return -x * 2.0


class Log(torch.nn.Module):
    def forward(self, x):
        return torch.log(x)


class LeakyRelu(torch.nn.Module):
    def __init__(self, slope=0.01):
        super().__init__()
        self.slope = slope

    def forward(self, x):
        return torch.nn.functional.leaky_relu(x, self.slope)


class AnyDim(torch.nn.Module):
    def __init__(self, dim, keepdim):
        super().__init__()
        self.dim, self.keepdim = dim, keepdim

    def forward(self, x):
        return torch.any(x > 0, dim=self.dim, keepdim=self.keepdim).to(x.dtype)


class Bicubic(torch.nn.Module):
    def __init__(self, size=None, align_corners=False, scale_factor=None):
        super().__init__()
        self.size, self.align, self.scale = size, align_corners, scale_factor

    def forward(self, x):
        return torch.nn.functional.interpolate(
            x,
            size=self.size,
            scale_factor=self.scale,
            mode="bicubic",
            align_corners=self.align,
            antialias=True,
        )


class StridedScatter(torch.nn.Module):
    def __init__(self, dim, start, end, step):
        super().__init__()
        self.args = (dim, start, end, step)

    def forward(self, base, src):
        dim, start, end, step = self.args
        return torch.slice_scatter(base, src, dim, start, end, step) * 1.5


class ConvTransposed(torch.nn.Module):
    def __init__(
        self,
        c_in,
        c_out,
        kernel,
        stride,
        padding,
        output_padding,
        groups,
        dilation=1,
        bias=True,
        dims=2,
    ):
        super().__init__()
        cls = torch.nn.ConvTranspose2d if dims == 2 else torch.nn.ConvTranspose1d
        torch.manual_seed(3)
        self.conv = cls(
            c_in,
            c_out,
            kernel,
            stride=stride,
            padding=padding,
            output_padding=output_padding,
            groups=groups,
            dilation=dilation,
            bias=bias,
        )

    def forward(self, x):
        return self.conv(x)


def _strided_operands(shape, dim, start, end, step, dtype=torch.float32):
    torch.manual_seed(5)
    base = torch.randn(shape, dtype=dtype)
    count = len(range(*slice(start, end, step).indices(shape[dim])))
    src_shape = list(shape)
    src_shape[dim] = count
    return base, torch.randn(src_shape, dtype=dtype)


# -- v6 is unchanged ----------------------------------------------------------


def _refusal(module, example, path):
    with pytest.raises(graph.GraphRefused) as refused:
        _rebuilt(module, example, path)
    return refused.value.code


def test_v6_refuses_every_v7_op_and_form():
    x = torch.randn(2, 3, 1, 12)
    base, src = _strided_operands((2, 8, 3), 1, 0, None, 2)
    for module, example, code in (
        (Neg(), (x,), "aten_op_not_allowlisted"),
        (Log(), (x.abs() + 1,), "aten_op_not_allowlisted"),
        (LeakyRelu(), (x,), "aten_op_not_allowlisted"),
        (AnyDim(-1, True), (x,), "aten_op_not_allowlisted"),
        (Bicubic(size=(1, 6)), (x,), "aten_op_not_allowlisted"),
        (StridedScatter(1, 0, None, 2), (base, src), "aten_arguments_not_supported"),
        (
            ConvTransposed(4, 4, (1, 4), (1, 2), (0, 1), 0, 4),
            (torch.randn(2, 4, 1, 9),),
            "aten_arguments_not_supported",
        ),
    ):
        assert _refusal(module, example, V6) == code


def test_v7_keeps_everything_v6_allowed():
    v6 = json.loads(V6.read_bytes())
    v7 = json.loads(V7.read_bytes())
    assert v7["carbon_ops"] == v6["carbon_ops"]
    assert v7["named_functions"] == v6["named_functions"]
    assert v7["framework_pins"] == v6["framework_pins"]
    for name, entry in v6["aten_core"].items():
        kept = {
            k: v for k, v in v7["aten_core"][name].items() if k not in ("forms", "note")
        }
        assert kept == {k: v for k, v in entry.items() if k != "note"}, name
    added = set(v7["aten_core"]) - set(v6["aten_core"])
    assert added == {
        "aten.neg.default",
        "aten.log.default",
        "aten.leaky_relu.default",
        "aten.any.dim",
        "aten._upsample_bicubic2d_aa.default",
        "aten.rand_like.default",
    }
    forms = {k: e["forms"] for k, e in v7["aten_core"].items() if "forms" in e}
    assert forms == {
        "aten.slice_scatter.default": ["strided"],
        "aten.convolution.default": ["transposed"],
    }


def test_v7_bytes_are_pinned_and_caps_are_unchanged():
    assert hashlib.sha256(V7.read_bytes()).hexdigest() == allowlist_module.V7_SHA256
    assert allowlist_module.v7_bytes() == V7.read_bytes()
    assert allowlist_module.CAPS == {
        "constant_bytes": 16 * 1024,
        "nodes_executed": 4096,
        "call_depth": 16,
        "document_bytes": 1024**2,
        "largest_intermediate_bytes": 256 * 1024**2,
    }
    assert allowlist_module.served_bytes() == V6.read_bytes()  # v7 is not served


def test_rand_like_stays_refused_and_says_why():
    class Noisy(torch.nn.Module):
        def forward(self, x):
            return x + torch.rand_like(x)

    assert _refusal(Noisy(), (torch.randn(2, 3),), V7) == "aten_op_not_allowlisted"
    note = json.loads(V7.read_bytes())["aten_core"]["aten.rand_like.default"]
    assert note["default"] == "refuse"
    assert "graded-vs-timed" in note["note"] and "paired-repeat" in note["note"]


# -- values and gradients against torch ----------------------------------------


def test_neg_matches_torch():
    x = torch.tensor([0.0, -0.0, 1.5, -2.25, 3.0e38, -1.0e-30])
    doc, rebuilt = _rebuilt(Neg(), (x,))
    assert "neg" in _ops(doc)
    got = np.asarray(rebuilt(*_jax(x))[0])
    np.testing.assert_array_equal(got, Neg()(x).numpy())
    np.testing.assert_array_equal(np.signbit(got), np.signbit(Neg()(x).numpy()))
    grads, want = _grads(Neg(), rebuilt, [x])
    np.testing.assert_array_equal(grads[0], want[0])


def test_log_matches_torch_including_zero_and_negative():
    x = torch.tensor([1.0, 2.718281828, 1.0e-30, 1.0e30, 0.5, 0.0, -1.0, 7.0])
    doc, rebuilt = _rebuilt(Log(), (x,))
    assert "log" in _ops(doc)
    got = np.asarray(rebuilt(*_jax(x))[0])
    want = torch.log(x).numpy()
    np.testing.assert_allclose(got, want, rtol=2e-7, atol=0)
    assert np.isneginf(got[5]) and np.isnan(got[6])
    positive = x > 0
    grads, wgrads = _grads(Log(), rebuilt, [x.clamp_min(1e-6)])
    np.testing.assert_allclose(grads[0], wgrads[0], rtol=1e-6)
    assert positive.any()


@pytest.mark.parametrize("slope", [0.01, 0.2, -0.5, 0.0])
def test_leaky_relu_matches_torch_with_its_gradient_at_zero(slope):
    x = torch.tensor([-3.0, -1.0e-8, -0.0, 0.0, 1.0e-8, 2.5, -7.25, 4.0])
    _doc, rebuilt = _rebuilt(LeakyRelu(slope), (x,))
    got = np.asarray(rebuilt(*_jax(x))[0])
    np.testing.assert_array_equal(got, LeakyRelu(slope)(x).numpy())
    grads, want = _grads(LeakyRelu(slope), rebuilt, [x])
    np.testing.assert_array_equal(grads[0], want[0])


@pytest.mark.parametrize(
    "dim, keepdim", [(-1, True), (-1, False), (1, True), (0, False)]
)
def test_any_dim_matches_torch(dim, keepdim):
    x = torch.tensor(
        [[[-1.0, -2.0, -3.0], [0.0, 0.0, 0.0]], [[-1.0, 2.0, -3.0], [5.0, 6.0, 7.0]]]
    )
    doc, rebuilt = _rebuilt(AnyDim(dim, keepdim), (x,))
    assert "reduce_max" in _ops(doc)
    got = np.asarray(rebuilt(*_jax(x))[0])
    np.testing.assert_array_equal(got, AnyDim(dim, keepdim)(x).numpy())


BICUBIC_CASES = [
    # (input shape, module kwargs): CNO1d's resizes, square up and down,
    # unequal factors, align_corners and a scale factor.
    ((2, 3, 1, 120), {"size": (1, 30)}),
    ((2, 3, 1, 15), {"size": (1, 30)}),
    ((2, 3, 1, 60), {"size": (1, 15)}),
    ((2, 3, 1, 30), {"size": (1, 60)}),
    ((1, 2, 7, 9), {"size": (13, 4)}),
    ((1, 2, 16, 16), {"size": (5, 5)}),
    ((1, 2, 6, 10), {"size": (6, 10)}),
    ((1, 2, 9, 11), {"size": (4, 23), "align_corners": True}),
    ((1, 2, 9, 2), {"size": (3, 2), "align_corners": True}),
    ((1, 1, 10, 10), {"scale_factor": 0.37}),
    ((1, 1, 5, 8), {"scale_factor": 2.5}),
]


@pytest.mark.parametrize("shape, kwargs", BICUBIC_CASES)
def test_bicubic_antialias_matches_torch(shape, kwargs):
    torch.manual_seed(7)
    x = torch.randn(shape) * 3.0
    module = Bicubic(**kwargs)
    doc, rebuilt = _rebuilt(module, (x,))
    got = np.asarray(rebuilt(*_jax(x))[0])
    want = module(x).numpy()
    assert got.shape == want.shape
    np.testing.assert_allclose(got, want, rtol=1e-5, atol=1e-5)
    grads, wgrads = _grads(module, rebuilt, [x])
    np.testing.assert_allclose(grads[0], wgrads[0], rtol=1e-5, atol=1e-5)
    measured = graph.measure(doc)
    assert measured["constant_value_bytes"] <= 1024  # scalars only, no weights


def test_bicubic_antialias_refuses_an_h_resize_at_width_1():
    # torch 2.13 returns its first row for every output row here, unlike its
    # own weights; v7 refuses the form rather than copy it.
    x = torch.arange(18.0).reshape(1, 2, 9, 1)
    module = Bicubic(size=(3, 1))
    assert len(set(module(x)[0, 0].flatten().tolist())) == 1
    assert _refusal(module, (x,), V7) == "aten_arguments_not_supported"


def test_bicubic_antialias_in_float64_is_tight():
    torch.manual_seed(8)
    x = torch.randn(1, 2, 11, 37, dtype=torch.float64)
    module = Bicubic(size=(4, 90))
    with jax.enable_x64(True):
        _, rebuilt = _rebuilt(module, (x,))
        got = np.asarray(rebuilt(*_jax(x))[0])
    assert got.dtype == np.float64
    np.testing.assert_allclose(got, module(x).numpy(), rtol=1e-12, atol=1e-12)


STRIDED_CASES = [
    ((90, 16, 1, 3), 1, 0, None, 2),  # MWT's even and odd channels
    ((90, 16, 1, 3), 1, 1, None, 2),
    ((4, 10, 5), 1, 1, 8, 3),
    ((4, 10, 5), 2, 0, None, 4),
    ((3, 7), 0, 0, None, 5),
    ((6, 9), -1, 2, 9, 2),
]


@pytest.mark.parametrize("shape, dim, start, end, step", STRIDED_CASES)
def test_strided_slice_scatter_matches_torch(shape, dim, start, end, step):
    base, src = _strided_operands(shape, dim, start, end, step)
    module = StridedScatter(dim, start, end, step)
    doc, rebuilt = _rebuilt(module, (base, src))
    assert "pad" in _ops(doc) and "dynamic_update_slice" not in _ops(doc)
    got = np.asarray(rebuilt(*_jax(base, src))[0])
    np.testing.assert_array_equal(got, module(base, src).numpy())
    grads, want = _grads(module, rebuilt, [base, src])
    for g, w in zip(grads, want):
        np.testing.assert_array_equal(g, w)


def test_a_unit_step_slice_scatter_keeps_the_v6_lowering():
    base, src = _strided_operands((4, 10, 5), 1, 2, 6, 1)
    doc, _ = _rebuilt(StridedScatter(1, 2, 6, 1), (base, src))
    assert "dynamic_update_slice" in _ops(doc)


TRANSPOSED_CASES = [
    # WNO1d's grouped stride-2 upsampling, then general groups, dilation,
    # output padding, no bias, and a 1-D transposed convolution.
    {
        "c_in": 32,
        "c_out": 32,
        "kernel": (1, 8),
        "stride": (1, 2),
        "padding": (0, 6),
        "output_padding": 0,
        "groups": 32,
        "shape": (3, 32, 1, 20),
    },
    {
        "c_in": 6,
        "c_out": 4,
        "kernel": (3, 2),
        "stride": (2, 3),
        "padding": (1, 0),
        "output_padding": (1, 2),
        "groups": 2,
        "shape": (2, 6, 5, 4),
    },
    {
        "c_in": 3,
        "c_out": 5,
        "kernel": 3,
        "stride": 2,
        "padding": 1,
        "output_padding": 0,
        "groups": 1,
        "dilation": 2,
        "bias": False,
        "shape": (2, 3, 6, 6),
    },
    {
        "c_in": 4,
        "c_out": 8,
        "kernel": 5,
        "stride": 3,
        "padding": 2,
        "output_padding": 1,
        "groups": 4,
        "dims": 1,
        "shape": (2, 4, 7),
    },
]


@pytest.mark.parametrize("case", TRANSPOSED_CASES)
def test_transposed_convolution_matches_torch(case):
    case = dict(case)
    shape = case.pop("shape")
    module = ConvTransposed(**case)
    torch.manual_seed(9)
    x = torch.randn(shape)
    doc, rebuilt = _rebuilt(module, (x,))
    assert "rev" in _ops(doc)
    got = np.asarray(rebuilt(*_jax(x))[0])
    want = module(x).detach().numpy()
    assert got.shape == want.shape
    np.testing.assert_allclose(got, want, rtol=1e-5, atol=1e-5)
    grads, wgrads = _grads(module, rebuilt, [x])
    np.testing.assert_allclose(grads[0], wgrads[0], rtol=1e-5, atol=1e-5)


# -- determinism and expansion bounds -------------------------------------------


DETERMINISM = [
    (Bicubic(size=(1, 30)), (torch.randn(2, 3, 1, 120),)),
    (StridedScatter(1, 1, None, 2), _strided_operands((4, 8, 3), 1, 1, None, 2)),
    (ConvTransposed(8, 8, (1, 4), (1, 2), (0, 1), 0, 8), (torch.randn(2, 8, 1, 9),)),
    (AnyDim(-1, True), (torch.randn(2, 4, 5),)),
    (LeakyRelu(0.1), (torch.randn(3, 4),)),
    (Log(), (torch.rand(3, 4) + 0.1,)),
    (Neg(), (torch.randn(3, 4),)),
]


@pytest.mark.parametrize("module, example", DETERMINISM)
def test_lowering_and_execution_repeat_bit_for_bit(module, example):
    first, rebuilt = _rebuilt(module, example)
    second, again = _rebuilt(module, example)
    assert graph.dumps(first) == graph.dumps(second)
    inputs = _jax(*example)
    a = np.asarray(rebuilt(*inputs)[0])
    b = np.asarray(again(*inputs)[0])
    np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(a, np.asarray(rebuilt(*inputs)[0]))


#: Nodes one call may expand to beyond its operands' own (the bicubic bound
#: is per resized axis).
BOUNDS = [
    (Neg(), (torch.randn(4),), 3),
    (Log(), (torch.rand(4) + 1,), 2),
    (LeakyRelu(), (torch.randn(4),), 6),
    (AnyDim(-1, False), (torch.randn(2, 4),), 8),
    (StridedScatter(1, 0, None, 2), _strided_operands((2, 8), 1, 0, None, 2), 8),
    (ConvTransposed(4, 4, (1, 4), (1, 2), (0, 1), 0, 4), (torch.randn(2, 4, 1, 9),), 8),
    (Bicubic(size=(1, 30)), (torch.randn(1, 2, 1, 120),), 72),
    (Bicubic(size=(5, 30)), (torch.randn(1, 2, 9, 120),), 144),
]


@pytest.mark.parametrize("module, example, bound", BOUNDS)
def test_each_lowering_expands_to_a_bounded_node_count(module, example, bound):
    doc, _ = _rebuilt(module, example)
    assert len(_ops(doc)) <= bound
