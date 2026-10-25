"""Allowlist v8, PyTorch side: the Core ATen forms the route was missing
(OWNER-GRAPH-OPS-OPEN-01; Validator VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025).

Each new `aten_core` entry has an emitter in `lower_torch`, written in the
Carbon ops the JAX route already has. Every case here exports a torch function,
lowers it under v8, rebuilds it in JAX and checks: the values against torch,
the gradients against torch autograd (for the differentiable ops), a bit-for-bit
rerun, a bounded node count, and that v7 refuses a program that holds a v8-only
target. Where torch's kernel and JAX's can differ in the last bits (the
transcendentals, a sum's order) the case states its tolerance.

The ops the audit keeps refused (backward ops, symbolic shapes, uninitialised
memory, RNG, an out= alias) and the running-statistics update of batch norm
stay refused, each with its reason recorded in the entry.
"""

from __future__ import annotations

import contextlib
import json
import os
import types
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

HERE = Path(allowlist_module.__file__).parent
V7 = HERE / "allowlist_v7.json"
V8 = HERE / "allowlist_v8.json"
torch = pytest.importorskip("torch")
jax = pytest.importorskip("jax")
np = pytest.importorskip("numpy")
F = torch.nn.functional
ATEN = torch.ops.aten

_V7_TARGETS = set(json.loads(V7.read_bytes())["aten_core"])
_V8_TARGETS = set(json.loads(V8.read_bytes())["aten_core"])
#: Targets only v8 lists: a program holding one cannot lower under v7.
V8_ONLY = _V8_TARGETS - _V7_TARGETS


class Fn(torch.nn.Module):
    """A parameter-free module around a function of its inputs."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def forward(self, *args):
        return self.fn(*args)


def _program(module, example, raw):
    program = torch.export.export(module, example)
    # `raw` keeps the ATen ops the module calls (the default decompositions
    # rewrite several Core ATen ops into others).
    return program.run_decompositions({}) if raw else program.run_decompositions()


def _lowered(module, example, path=V8, raw=False):
    allowlist = allowlist_module.load(path)
    program = _program(module, example, raw)
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    run = interpret.rebuild(parsed, allowlist)
    targets = {str(n.target) for n in program.graph.nodes if n.op == "call_function"}
    return doc, run, targets


def _jax(*tensors):
    return [jax.numpy.asarray(t.detach().numpy()) for t in tensors]


def _listed(value):
    return list(value) if isinstance(value, (tuple, list)) else [value]


def _same(got, want, rtol, atol, label=""):
    got = np.asarray(got)
    want = want.detach().numpy()
    assert got.shape == want.shape, (label, got.shape, want.shape)
    if want.dtype.kind in "fc":
        np.testing.assert_allclose(
            got, want, rtol=rtol, atol=atol, equal_nan=True, err_msg=label
        )
    else:
        np.testing.assert_array_equal(got.astype(want.dtype), want, err_msg=label)


def _bits(value):
    return np.asarray(value).tobytes()


def _gradients(module, run, inputs, diff, rtol, atol, label):
    """Input gradients of sum(out * probe) over the float outputs, torch's
    autograd against jax.grad of the rebuild."""
    tensors = [t.clone().requires_grad_(i in diff) for i, t in enumerate(inputs)]
    outs = [o for o in _listed(module(*tensors))]
    floats = [i for i, o in enumerate(outs) if o.dtype.is_floating_point]
    probes = {
        i: torch.linspace(-1.5, 2.0, outs[i].numel(), dtype=outs[i].dtype).reshape(
            outs[i].shape
        )
        for i in floats
    }
    total = sum((outs[i] * probes[i]).sum() for i in floats)
    total.backward()
    want = [tensors[i].grad.numpy() for i in diff]
    jprobes = {i: jax.numpy.asarray(probes[i].numpy()) for i in floats}

    def loss(*args):
        results = run(*args)
        return sum((results[i] * jprobes[i]).sum() for i in floats)

    got = jax.grad(loss, argnums=tuple(diff))(*_jax(*inputs))
    for g, w, i in zip(got, want, diff):
        np.testing.assert_allclose(
            np.asarray(g),
            w,
            rtol=rtol,
            atol=atol,
            equal_nan=True,
            err_msg=f"{label}: gradient of input {i}",
        )


CASES = []


def case(
    name,
    fn,
    inputs,
    *,
    expect=(),
    raw=False,
    rtol=1e-6,
    atol=1e-6,
    diff=(),
    grad_inputs=None,
    grad_rtol=None,
    grad_atol=None,
    nodes=80,
    signs=False,
    v7="auto",
    x64=False,
):
    """One case. `diff` lists the inputs whose gradient is checked (at
    `grad_inputs` when the value edge points have no finite gradient)."""
    CASES.append(
        pytest.param(
            {
                "fn": fn,
                "inputs": inputs,
                "expect": expect,
                "raw": raw,
                "rtol": rtol,
                "atol": atol,
                "diff": diff,
                "grad_inputs": grad_inputs,
                "grad_rtol": grad_rtol,
                "grad_atol": grad_atol,
                "nodes": nodes,
                "signs": signs,
                "v7": v7,
                "x64": x64,
            },
            id=name,
        )
    )


def _randn(*shape, seed=0, scale=1.0, dtype=torch.float32):
    generator = torch.Generator().manual_seed(seed)
    return (torch.randn(*shape, generator=generator) * scale).to(dtype)


def _ints(*shape, low=-5, high=6, seed=0, dtype=torch.int64):
    generator = torch.Generator().manual_seed(seed)
    return torch.randint(low, high, shape, generator=generator, dtype=dtype)


def _t(values, dtype=torch.float32):
    return torch.tensor(values, dtype=dtype)


NAN, INF = float("nan"), float("inf")
EDGE = _t([-3.0, -1.5, -1.0, -0.5, -0.0, 0.0, 0.25, 0.5, 1.0, 2.0, 7.5])
EDGE_POS = _t([0.0, 1e-30, 0.25, 0.5, 1.0, 2.0, 7.5, 1e20])
UNIT = _t([-1.0, -0.9, -0.5, -0.0, 0.0, 0.3, 0.5, 0.9, 1.0])
UNIT_INTERIOR = _t([-0.9, -0.5, -0.1, 0.0, 0.3, 0.5, 0.9])


def tolerant(name, fn, edge, interior, target, rtol=3e-6, atol=1e-6, grad_rtol=3e-5):
    """A transcendental: values at the edge points, gradients in the interior."""
    case(
        name,
        fn,
        (edge,),
        expect=(target,),
        rtol=rtol,
        atol=atol,
        diff=(0,),
        grad_inputs=(interior,),
        grad_rtol=grad_rtol,
        grad_atol=1e-6,
    )


# -- elementwise: one primitive each ---------------------------------------------------

BIG = _t([-3.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 5.0, 20.0, -20.0])
tolerant("erf", torch.erf, BIG, BIG, "aten.erf.default")
tolerant("expm1", torch.expm1, BIG, BIG, "aten.expm1.default")
tolerant(
    "rsqrt",
    torch.rsqrt,
    _t([0.0, 1e-30, 0.25, 1.0, 4.0, 1e20, -1.0]),
    _t([0.25, 1.0, 4.0, 9.0]),
    "aten.rsqrt.default",
)
tolerant(
    "tan",
    torch.tan,
    _t([-1.2, -0.5, -0.0, 0.0, 0.5, 1.0, 1.4]),
    _t([-1.0, -0.5, 0.0, 0.5, 1.0]),
    "aten.tan.default",
)
tolerant(
    "asin",
    torch.asin,
    _t([-1.0, -0.9, -0.5, -0.0, 0.0, 0.5, 0.9, 1.0, 1.5]),
    UNIT_INTERIOR,
    "aten.asin.default",
)
tolerant(
    "acos",
    torch.acos,
    _t([-1.0, -0.9, -0.5, 0.0, 0.5, 0.9, 1.0, -1.5]),
    UNIT_INTERIOR,
    "aten.acos.default",
)
tolerant(
    "atan",
    torch.atan,
    _t([-1e20, -3.0, -1.0, -0.0, 0.0, 0.5, 1.0, 7.0, INF, -INF]),
    _t([-3.0, -1.0, 0.0, 0.5, 7.0]),
    "aten.atan.default",
)
tolerant(
    "asinh",
    torch.asinh,
    _t([-100.0, -3.0, -0.5, -0.0, 0.0, 0.5, 3.0, 100.0]),
    _t([-3.0, -0.5, 0.0, 0.5, 3.0]),
    "aten.asinh.default",
)
tolerant(
    "acosh",
    torch.acosh,
    _t([1.0, 1.0000001, 1.5, 2.0, 10.0, 1e5, 0.5]),
    _t([1.5, 2.0, 10.0]),
    "aten.acosh.default",
)
tolerant(
    "atanh",
    torch.atanh,
    _t([-1.0, -0.99, -0.5, -0.0, 0.0, 0.5, 0.99, 1.0, 1.5]),
    UNIT_INTERIOR,
    "aten.atanh.default",
)
tolerant(
    "sinh",
    torch.sinh,
    _t([-8.0, -1.0, -0.0, 0.0, 1e-5, 1.0, 8.0]),
    _t([-2.0, -0.5, 0.0, 1.0, 2.0]),
    "aten.sinh.default",
)
tolerant(
    "cosh",
    torch.cosh,
    _t([-8.0, -1.0, -0.0, 0.0, 1e-5, 1.0, 8.0]),
    _t([-2.0, -0.5, 0.0, 1.0, 2.0]),
    "aten.cosh.default",
)

case(
    "atan2_quadrants",
    torch.atan2,
    (
        _t([0.0, -0.0, 1.0, -1.0, 2.0, 0.5, 0.0, -0.0, 1.0, -3.0]),
        _t([1.0, 1.0, 0.0, 0.0, -1.0, -2.0, -1.0, -1.0, 1e-30, INF]),
    ),
    expect=("aten.atan2.default",),
    rtol=3e-6,
    signs=True,
    diff=(0, 1),
    grad_inputs=(_t([0.5, -1.0, 2.0, -3.0, 1.0]), _t([1.0, 2.0, -1.0, 0.5, -2.0])),
    grad_rtol=3e-5,
)
case(
    "atan2_integer_inputs_promote",
    lambda a, c: torch.atan2(a, c),
    (_ints(2, 3, seed=1), _ints(2, 3, seed=2)),
    expect=("aten.atan2.default",),
    rtol=3e-6,
)
case(
    "log2",
    torch.log2,
    (EDGE_POS,),
    expect=("aten.log2.default",),
    rtol=3e-6,
    diff=(0,),
    grad_inputs=(_t([0.25, 1.0, 2.0, 8.0]),),
    grad_rtol=3e-5,
)
case(
    "log10",
    torch.log10,
    (_t([0.0, 1e-30, 0.1, 1.0, 10.0, 1000.0, -1.0]),),
    expect=("aten.log10.default",),
    rtol=3e-6,
    diff=(0,),
    grad_inputs=(_t([0.25, 1.0, 10.0, 8.0]),),
    grad_rtol=3e-5,
)
case(
    "log2_float64",
    torch.log2,
    (_randn(5, seed=3).abs().double() + 0.1,),
    expect=("aten.log2.default",),
    rtol=1e-12,
    x64=True,
)

for tag, alpha, scale, input_scale in (
    ("default", 1.0, 1.0, 1.0),
    ("alpha", 0.7, 1.0, 1.0),
    ("selu", 1.6732632423543772, 1.0507009873554805, 1.0),
    ("input_scale", 1.3, 0.8, 2.0),
):
    case(
        f"elu_{tag}",
        lambda x, a=alpha, s=scale, i=input_scale: ATEN.elu(x, a, s, i),
        (_t([-4.0, -1.0, -0.5, -0.0, 0.0, 0.5, 2.0, 10.0]),),
        expect=("aten.elu.default",),
        raw=True,
        rtol=3e-6,
        diff=(0,),
        grad_rtol=3e-5,
    )

case(
    "maximum_minimum_with_ties_and_nan",
    lambda a, c: torch.stack([torch.maximum(a, c), torch.minimum(a, c)]),
    (
        _t([1.0, -2.0, 3.0, NAN, 0.0, -0.0, 5.0]),
        _t([1.0, 2.0, -3.0, 1.0, -0.0, 0.0, NAN]),
    ),
    expect=("aten.maximum.default", "aten.minimum.default"),
    signs=False,
    diff=(0, 1),
    grad_inputs=(_t([1.0, -2.0, 3.0, 0.5]), _t([1.0, 2.0, -3.0, 0.5])),
)
case(
    "maximum_broadcast",
    lambda a, c: torch.maximum(a, c),
    (_randn(3, 4, seed=4), _randn(4, seed=5)),
    expect=("aten.maximum.default",),
    diff=(0, 1),
)

LOW = _t([-1.0, -1.0, 0.5, 2.0, -0.5, 0.0])
HIGH = _t([1.0, 0.5, 1.0, 1.0, 0.5, 0.0])
X6 = _t([-2.0, 0.5, 0.75, 3.0, -0.5, 0.0])
case(
    "clamp_tensor_both",
    lambda x, lo, hi: torch.clamp(x, lo, hi),
    (X6, LOW, HIGH),
    expect=("aten.clamp.Tensor",),
    diff=(0,),
    grad_inputs=(_t([-2.0, 0.6, 0.75, 3.0, -0.4, 0.2]), LOW, HIGH),
)
case(
    "clamp_tensor_min_only",
    lambda x, lo: torch.clamp(x, min=lo),
    (X6, LOW),
    expect=("aten.clamp.Tensor",),
    diff=(0,),
)
case(
    "clamp_tensor_max_only",
    lambda x, hi: torch.clamp(x, max=hi),
    (X6, HIGH),
    expect=("aten.clamp.Tensor",),
    diff=(0,),
)
case(
    "clamp_tensor_bounds_get_gradient_where_they_clamp",
    lambda x, lo, hi: torch.clamp(x, lo, hi),
    (_t([-2.0, 0.5, 3.0]), _t([-1.0, -1.0, -1.0]), _t([1.0, 1.0, 1.0])),
    expect=("aten.clamp.Tensor",),
    diff=(0, 1, 2),
)

HT = _t([-3.0, -1.0, -0.5, 0.0, 0.5, 1.0, 1.0000001, 2.0, NAN])
case(
    "hardtanh_gradient_zero_at_bounds",
    lambda x: F.hardtanh(x, -1.0, 1.0),
    (HT,),
    expect=("aten.hardtanh.default",),
    diff=(0,),
    grad_inputs=(HT[:-1],),
)
case(
    "relu6",
    F.relu6,
    (_t([-3.0, 0.0, 3.0, 6.0, 7.0]),),
    expect=("aten.hardtanh.default",),
    diff=(0,),
)
case(
    "hardtanh_asymmetric",
    lambda x: F.hardtanh(x, -0.25, 0.75),
    (_randn(2, 5, seed=6),),
    expect=("aten.hardtanh.default",),
    diff=(0,),
)

# pow
POW_X = _t([-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0])
for exponent in (2, 3, -1, -2, 0, 1, 0.5, 2.5, -0.5, 3.0):
    case(
        f"pow_tensor_scalar_{exponent}",
        lambda x, e=exponent: x**e,
        (POW_X,),
        expect=("aten.pow.Tensor_Scalar",),
        rtol=3e-6,
        diff=(0,),
        grad_inputs=(_t([0.5, 1.0, 2.0, 3.0]),),
        grad_rtol=3e-5,
    )
case(
    "pow_scalar_base",
    lambda y: 2.0**y,
    (_t([-3.0, -0.5, 0.0, 1.0, 2.5, 8.0]),),
    expect=("aten.pow.Scalar",),
    rtol=3e-6,
    diff=(0,),
    grad_rtol=3e-5,
)
case(
    "pow_scalar_base_zero",
    lambda y: 0.0**y,
    (_t([0.0, 1.0, 2.0, 0.5]),),
    expect=("aten.pow.Scalar",),
)
case(
    "pow_tensor_tensor",
    lambda x, y: x**y,
    (
        _t([0.5, 1.0, 2.0, 3.0, 0.0, -2.0, 4.0]),
        _t([2.0, 0.5, -1.0, 3.0, 2.0, 3.0, 0.0]),
    ),
    expect=("aten.pow.Tensor_Tensor",),
    rtol=3e-6,
    diff=(0, 1),
    grad_inputs=(_t([0.5, 1.0, 2.0, 3.0]), _t([2.0, 0.5, -1.0, 1.5])),
    grad_rtol=3e-5,
)
case(
    "pow_integer_tensor_scalar",
    lambda x: (x**3).to(torch.float32),
    (_ints(2, 3, seed=7),),
    expect=("aten.pow.Tensor_Scalar",),
)

# rounding
ROUND_X = _t(
    [-2.5, -1.5, -0.7, -0.5, -0.0, 0.0, 0.2, 0.5, 1.5, 2.5, 3.5, 1e8, INF, -INF, NAN]
)
case(
    "ceil",
    torch.ceil,
    (ROUND_X,),
    expect=("aten.ceil.default",),
    signs=True,
    diff=(0,),
    grad_inputs=(ROUND_X[:-4],),
)
case(
    "trunc",
    torch.trunc,
    (ROUND_X,),
    expect=("aten.trunc.default",),
    signs=True,
    diff=(0,),
    grad_inputs=(ROUND_X[:-4],),
)
case(
    "round_half_to_even",
    torch.round,
    (ROUND_X,),
    expect=("aten.round.default",),
    signs=True,
    diff=(0,),
    grad_inputs=(ROUND_X[:-4],),
)
case(
    "ceil_integers_pass_through",
    lambda x: torch.ceil(x),
    (_ints(3, seed=8, dtype=torch.int32),),
    expect=("aten.ceil.default",),
)
for decimals in (0, 1, 2, -1, -2):
    case(
        f"round_decimals_{decimals}",
        lambda x, d=decimals: torch.round(x, decimals=d),
        (_t([-123.456, -2.675, -0.05, 0.0, 0.05, 0.125, 1.005, 2.5, 15.0, 1234.5678]),),
        expect=("aten.round.decimals",),
        rtol=2e-6,
        atol=1e-5,
    )

# predicates and comparisons
case(
    "isnan_isinf",
    lambda x: torch.stack([torch.isnan(x), torch.isinf(x)]),
    (_t([1.0, NAN, INF, -INF, 0.0, -0.0, 1e38]),),
    expect=("aten.isnan.default", "aten.isinf.default"),
)
case(
    "isnan_of_integers",
    lambda x: torch.isnan(x),
    (_ints(4, seed=9),),
    expect=("aten.isnan.default",),
)
CMP_A = _t([1.0, 2.0, NAN, 0.0, -0.0, INF, 3.0])
CMP_B = _t([1.0, 3.0, NAN, -0.0, 0.0, INF, 2.0])
case("eq_tensor", lambda a, c: a == c, (CMP_A, CMP_B), expect=("aten.eq.Tensor",))
case("ne_tensor", lambda a, c: a != c, (CMP_A, CMP_B), expect=("aten.ne.Tensor",))
case("ne_scalar", lambda a: a != 1.0, (CMP_A,), expect=("aten.ne.Scalar",))
case("ne_scalar_nan", lambda a: a != NAN, (CMP_A,), expect=("aten.ne.Scalar",))
case(
    "eq_tensor_mixed_int_float",
    lambda a, c: a == c,
    (_t([1, 2, 3], torch.int32), _t([1.0, 2.5, 3.0])),
    expect=("aten.eq.Tensor",),
)
case(
    "ne_tensor_broadcast",
    lambda a, c: a != c,
    (_ints(2, 3, seed=10), _ints(3, seed=11)),
    expect=("aten.ne.Tensor",),
)
case(
    "ne_scalar_float_scalar_on_integers",
    lambda a: a != 1.5,
    (_ints(5, seed=12),),
    expect=("aten.ne.Scalar",),
)

# bitwise and logical
BITS_A = _t([0, 1, 5, -3, 255, -128, 12, 7], torch.int32)
BITS_B = _t([0, 3, 6, 5, 15, 127, -1, 7], torch.int32)
case(
    "bitwise_and_tensor_ints",
    lambda a, c: a & c,
    (BITS_A, BITS_B),
    expect=("aten.bitwise_and.Tensor",),
)
case(
    "bitwise_and_scalar",
    lambda a: a & 5,
    (BITS_A,),
    expect=("aten.bitwise_and.Scalar",),
)
case(
    "bitwise_or_tensor",
    lambda a, c: a | c,
    (BITS_A, BITS_B),
    expect=("aten.bitwise_or.Tensor",),
)
case(
    "bitwise_or_scalar", lambda a: a | 9, (BITS_A,), expect=("aten.bitwise_or.Scalar",)
)
case(
    "bitwise_xor_tensor",
    lambda a, c: a ^ c,
    (BITS_A, BITS_B),
    expect=("aten.bitwise_xor.Tensor",),
)
case(
    "bitwise_xor_scalar",
    lambda a: a ^ 6,
    (BITS_A,),
    expect=("aten.bitwise_xor.Scalar",),
)
case("bitwise_not_int", lambda a: ~a, (BITS_A,), expect=("aten.bitwise_not.default",))
case(
    "bitwise_not_bool",
    lambda a: ~(a > 0),
    (_t([-1.0, 0.0, 2.0]),),
    expect=("aten.bitwise_not.default",),
)
case(
    "bitwise_and_bool_masks_still_work",
    lambda a, c: (a > 0) & (c > 0),
    (_t([-1.0, 1.0, 2.0, 3.0]), _t([1.0, -1.0, 2.0, 0.0])),
    expect=("aten.bitwise_and.Tensor",),
)
case(
    "shift_left_scalar",
    lambda a: a << 2,
    (BITS_A,),
    expect=("aten.__lshift__.Scalar",),
    raw=True,
)
case(
    "shift_right_scalar_arithmetic",
    lambda a: a >> 1,
    (BITS_A,),
    expect=("aten.__rshift__.Scalar",),
    raw=True,
)
case(
    "shift_by_tensor",
    lambda a, s: (a << s, a >> s),
    (BITS_A, _t([0, 1, 2, 3, 4, 5, 6, 7], torch.int32)),
    expect=("aten.__lshift__.Tensor", "aten.__rshift__.Tensor"),
    raw=True,
)
LOGIC_A = _t([0.0, 1.0, 2.0, -3.0, 0.0, NAN])
LOGIC_B = _t([0.0, 0.0, 5.0, 0.0, -1.0, 0.0])
case(
    "logical_and_or_xor",
    lambda a, c: torch.stack(
        [torch.logical_and(a, c), torch.logical_or(a, c), torch.logical_xor(a, c)]
    ),
    (LOGIC_A, LOGIC_B),
    expect=(
        "aten.logical_and.default",
        "aten.logical_or.default",
        "aten.logical_xor.default",
    ),
)
case(
    "logical_ops_on_bool_and_broadcast",
    lambda a, c: torch.logical_xor(a > 0, c),
    (_t([[1.0], [-1.0]]), _t([True, False, True], torch.bool)),
    expect=("aten.logical_xor.default",),
)

# division, remainder, scalars
DIV_X = _t([7.0, -7.0, 7.0, -7.0, 1.0, 0.3, -0.3, 5.5, 0.0, -0.0, 1e30, 6.0])
DIV_Y = _t([2.0, 2.0, -2.0, -2.0, 0.1, 0.1, 0.1, 5.5, 3.0, 3.0, 1e-5, 0.0])
for mode in ("floor", "trunc"):
    case(
        f"div_{mode}_tensor",
        lambda a, c, m=mode: torch.div(a, c, rounding_mode=m),
        (DIV_X, DIV_Y),
        expect=("aten.div.Tensor_mode",),
        signs=True,
        rtol=0,
        atol=0,
    )
    case(
        f"div_{mode}_scalar",
        lambda a, m=mode: torch.div(a, 0.7, rounding_mode=m),
        (DIV_X,),
        expect=("aten.div.Tensor_mode",),
        signs=True,
        rtol=0,
        atol=0,
    )
    case(
        f"div_{mode}_integers",
        lambda a, c, m=mode: torch.div(a, c, rounding_mode=m),
        (
            _t([7, -7, 7, -7, 6, -6, 0, 1], torch.int32),
            _t([2, 2, -2, -2, 3, -3, 5, -1], torch.int32),
        ),
        expect=("aten.div.Tensor_mode",),
    )
case(
    "div_scalar_mode_raw",
    lambda a: ATEN.div.Scalar_mode(a, 2.0, rounding_mode="floor"),
    (DIV_X,),
    expect=("aten.div.Scalar_mode",),
    raw=True,
)
case(
    "floor_divide_operator",
    lambda a, c: a // c,
    (DIV_X, DIV_Y),
    expect=("aten.div.Tensor_mode",),
    signs=True,
    rtol=0,
    atol=0,
)
case(
    "add_scalar_raw",
    lambda a: ATEN.add.Scalar(a, 2.5),
    (EDGE,),
    expect=("aten.add.Scalar",),
    raw=True,
    diff=(0,),
)
case(
    "sub_scalar_raw",
    lambda a: ATEN.sub.Scalar(a, 2.5),
    (EDGE,),
    expect=("aten.sub.Scalar",),
    raw=True,
    diff=(0,),
)
case(
    "div_scalar_raw",
    lambda a: ATEN.div.Scalar(a, 4.0),
    (EDGE,),
    expect=("aten.div.Scalar",),
    raw=True,
    diff=(0,),
)
case(
    "add_scalar_integers",
    lambda a: ATEN.add.Scalar(a, 3),
    (_ints(4, seed=13),),
    expect=("aten.add.Scalar",),
    raw=True,
)
case(
    "add_scalar_alpha",
    lambda a: ATEN.add.Scalar(a, 3.0, alpha=2.0),
    (EDGE,),
    expect=("aten.add.Scalar",),
    raw=True,
)

REM_X = _t([5.0, -5.0, 5.0, -5.0, 5.5, -0.5, 0.0, -0.0, 6.0, 1e10, 3.0])
REM_Y = _t([3.0, 3.0, -3.0, -3.0, -2.0, 2.0, 3.0, -3.0, 3.0, 7.0, INF])
case(
    "remainder_tensor",
    torch.remainder,
    (REM_X, REM_Y),
    expect=("aten.remainder.Tensor",),
    rtol=0,
    atol=0,
    diff=(0, 1),
    grad_inputs=(_t([5.0, -5.0, 5.5, -0.5, 7.25]), _t([3.0, 3.0, -2.0, 2.0, -3.0])),
)
case(
    "remainder_scalar",
    lambda a: torch.remainder(a, 0.7),
    (REM_X,),
    expect=("aten.remainder.Scalar",),
    rtol=2e-6,
    diff=(0,),
    grad_inputs=(REM_X[:6],),
)
case(
    "remainder_scalar_negative_divisor",
    lambda a: torch.remainder(a, -3.0),
    (REM_X,),
    expect=("aten.remainder.Scalar",),
    rtol=2e-6,
)
case(
    "remainder_integers",
    lambda a: torch.remainder(a, 4),
    (_t([-9, -4, -1, 0, 1, 4, 9], torch.int32),),
    expect=("aten.remainder.Scalar",),
)
case(
    "remainder_scalar_tensor",
    lambda c: torch.remainder(5.0, c),
    (_t([3.0, -3.0, 2.0, -7.0]),),
    expect=("aten.remainder.Scalar_Tensor",),
    raw=True,
    rtol=0,
    atol=0,
)

case(
    "fill_scalar",
    lambda a: ATEN.fill.Scalar(a, 3.5),
    (EDGE,),
    expect=("aten.fill.Scalar",),
    raw=True,
)
case(
    "fill_scalar_integer",
    lambda a: ATEN.fill.Scalar(a, 3),
    (_ints(2, 2, seed=14),),
    expect=("aten.fill.Scalar",),
    raw=True,
)
case(
    "scalar_tensor",
    lambda a: a + ATEN.scalar_tensor(2.5),
    (EDGE,),
    expect=("aten.scalar_tensor.default",),
)

# -- reductions -------------------------------------------------------------------------

R3 = _randn(2, 3, 4, seed=20)
TIED = _t([[1.0, 3.0, 3.0, 2.0], [-1.0, -1.0, -2.0, -1.0]])
for tag, kwargs in (
    ("dims02", {"dim": (0, 2)}),
    ("dim1_keepdim", {"dim": 1, "keepdim": True}),
    ("all_dims_default", {"dim": ()}),
    ("negative_dim", {"dim": -1}),
):
    for name, op, target in (
        ("amax", torch.amax, "aten.amax.default"),
        ("amin", torch.amin, "aten.amin.default"),
    ):
        case(
            f"{name}_{tag}",
            lambda x, o=op, k=kwargs: o(x, **k),
            (R3,),
            expect=(target,),
            diff=(0,),
            nodes=10,
        )
case(
    "amax_ties_share_the_gradient",
    lambda x: torch.amax(x, dim=1),
    (TIED,),
    expect=("aten.amax.default",),
    diff=(0,),
)
case(
    "amin_nan_propagates",
    lambda x: torch.amin(x, dim=1),
    (_t([[1.0, NAN, 3.0], [2.0, 1.0, 3.0]]),),
    expect=("aten.amin.default",),
)
case(
    "max_default",
    lambda x: torch.max(x),
    (R3,),
    expect=("aten.max.default",),
    diff=(0,),
    nodes=5,
)
case(
    "min_default",
    lambda x: torch.min(x),
    (R3,),
    expect=("aten.min.default",),
    diff=(0,),
    nodes=5,
)

ANY_X = _t([[0.0, 0.0, 0.0], [0.0, 2.0, 0.0], [NAN, 0.0, 0.0]])
case("any_default", lambda x: torch.any(x > 0), (ANY_X,), expect=("aten.any.default",))
case(
    "any_default_all_false",
    lambda x: torch.any(x > 10.0),
    (ANY_X,),
    expect=("aten.any.default",),
)
case(
    "any_dims", lambda x: torch.any(x > 0, dim=(0, 1)), (R3,), expect=("aten.any.dims",)
)
case(
    "any_dims_keepdim",
    lambda x: torch.any(x > 0, dim=(1,), keepdim=True),
    (R3,),
    expect=("aten.any.dims",),
)
case(
    "any_of_float_values",
    lambda x: ATEN.any.default(x),
    (ANY_X,),
    expect=("aten.any.default",),
    raw=True,
)

ARG_X = _t([[1.0, 5.0, 5.0, 2.0], [NAN, 1.0, 2.0, NAN], [3.0, 3.0, 3.0, 3.0]])
case(
    "argmax_dim",
    lambda x: torch.argmax(x, dim=1),
    (ARG_X,),
    expect=("aten.argmax.default",),
)
case(
    "argmin_dim",
    lambda x: torch.argmin(x, dim=1),
    (ARG_X,),
    expect=("aten.argmin.default",),
)
case(
    "argmax_dim0_keepdim",
    lambda x: torch.argmax(x, dim=0, keepdim=True),
    (ARG_X,),
    expect=("aten.argmax.default",),
)
case(
    "argmin_flattened",
    lambda x: torch.argmin(x),
    (ARG_X[:1],),
    expect=("aten.argmin.default",),
)
case(
    "argmax_flattened_keepdim",
    lambda x: torch.argmax(x, keepdim=True),
    (ARG_X,),
    expect=("aten.argmax.default",),
)
case(
    "argmax_integers",
    lambda x: torch.argmax(x, dim=-1),
    (_ints(3, 5, seed=21),),
    expect=("aten.argmax.default",),
)

MD_X = _t([[1.0, 5.0, 2.0, -1.0], [4.0, 3.0, 9.0, 0.0], [7.0, -2.0, 6.0, 8.0]])
case(
    "max_dim",
    lambda x: torch.max(x, dim=1),
    (MD_X,),
    expect=("aten.max.dim",),
    diff=(0,),
)
case(
    "min_dim_keepdim",
    lambda x: torch.min(x, dim=0, keepdim=True),
    (MD_X,),
    expect=("aten.min.dim",),
    diff=(0,),
)
case(
    "max_dim_ties_first_index_values_only",
    lambda x: torch.max(x, dim=1),
    (TIED,),
    expect=("aten.max.dim",),
)
case(
    "max_dim_negative_dim_integers",
    lambda x: torch.max(x, dim=-1),
    (_ints(3, 4, seed=22),),
    expect=("aten.max.dim",),
)

PROD_X = _t([[1.5, 2.0, -0.5], [0.0, 3.0, 2.0], [0.0, 0.0, 4.0]])
case(
    "prod_default",
    lambda x: torch.prod(x),
    (_t([[1.5, 2.0], [-0.5, 3.0]]),),
    expect=("aten.prod.default",),
    rtol=2e-6,
    diff=(0,),
    grad_rtol=2e-5,
)
case(
    "prod_dim",
    lambda x: torch.prod(x, dim=1),
    (PROD_X,),
    expect=("aten.prod.dim_int",),
    rtol=2e-6,
    diff=(0,),
    grad_rtol=2e-5,
)
case(
    "prod_dim_keepdim",
    lambda x: torch.prod(x, dim=0, keepdim=True),
    (PROD_X,),
    expect=("aten.prod.dim_int",),
    rtol=2e-6,
    diff=(0,),
    grad_rtol=2e-5,
)
case(
    "prod_integers",
    lambda x: torch.prod(x, dim=1).to(torch.float32),
    (_ints(2, 4, low=1, high=4, seed=23),),
    expect=("aten.prod.dim_int",),
)
case(
    "prod_default_integers",
    lambda x: torch.prod(x).to(torch.float32),
    (_ints(4, low=1, high=4, seed=24),),
    expect=("aten.prod.default",),
)

for dim in (0, 1, 2, -1):
    case(
        f"cumsum_dim{dim}",
        lambda x, d=dim: torch.cumsum(x, dim=d),
        (R3,),
        expect=("aten.cumsum.default",),
        rtol=2e-6,
        atol=2e-6,
        diff=(0,),
        grad_rtol=2e-5,
    )
case(
    "cumsum_integers",
    lambda x: torch.cumsum(x, dim=1).to(torch.float32),
    (_ints(2, 5, seed=25),),
    expect=("aten.cumsum.default",),
)
case(
    "cumsum_booleans",
    lambda x: torch.cumsum(x > 0, dim=1).to(torch.float32),
    (R3[0],),
    expect=("aten.cumsum.default",),
)
case(
    "cumsum_scalar",
    lambda x: torch.cumsum(x, dim=0),
    (_t(2.5),),
    expect=("aten.cumsum.default",),
)
case(
    "cumprod_dim1",
    lambda x: torch.cumprod(x, dim=1),
    (_t([[1.5, 2.0, -0.5, 4.0], [2.0, 0.5, 3.0, 1.0]]),),
    expect=("aten.cumprod.default",),
    rtol=2e-6,
    diff=(0,),
    grad_rtol=2e-5,
)
case(
    "logcumsumexp",
    lambda x: torch.logcumsumexp(x, dim=1),
    (_t([[1.5, 2.0, -0.5, 4.0], [-30.0, 0.5, 3.0, 1.0]]),),
    expect=("aten.logcumsumexp.default",),
    rtol=3e-6,
    atol=1e-6,
    diff=(0,),
    grad_rtol=3e-5,
)
case(
    "mean_default",
    lambda x: x.mean(),
    (R3,),
    expect=("aten.mean.default",),
    rtol=2e-6,
    diff=(0,),
    nodes=6,
)
case(
    "var_dim_biased",
    lambda x: ATEN.var.dim(x, [1], False, False),
    (R3,),
    expect=("aten.var.dim",),
    raw=True,
    rtol=3e-6,
    atol=1e-6,
    diff=(0,),
    grad_rtol=3e-5,
)
case(
    "var_dim_unbiased_keepdim",
    lambda x: ATEN.var.dim(x, [0, 2], True, True),
    (R3,),
    expect=("aten.var.dim",),
    raw=True,
    rtol=3e-6,
    atol=1e-6,
    diff=(0,),
    grad_rtol=3e-5,
)

LS_X = _t(
    [
        [1.0, 2.0, 3.0],
        [1000.0, 1001.0, 999.0],
        [-1000.0, -1001.0, -999.0],
        [0.0, NAN, 1.0],
    ]
)
case(
    "log_softmax_dim1",
    lambda x: F.log_softmax(x, dim=1),
    (LS_X,),
    expect=("aten._log_softmax.default",),
    rtol=3e-6,
    atol=1e-5,
    diff=(0,),
    grad_inputs=(LS_X[:3],),
    grad_rtol=3e-5,
    grad_atol=1e-5,
)
case(
    "log_softmax_dim0_float64",
    lambda x: F.log_softmax(x, dim=0),
    (_randn(4, 3, seed=26).double(),),
    expect=("aten._log_softmax.default",),
    rtol=1e-12,
    atol=1e-12,
    diff=(0,),
    grad_rtol=1e-10,
    x64=True,
)

# -- selection, indexing and shapes ---------------------------------------------------------

case(
    "flip",
    lambda x: torch.flip(x, [0, 2]),
    (R3,),
    expect=("aten.flip.default",),
    diff=(0,),
    nodes=3,
)
case(
    "flip_negative_dim",
    lambda x: torch.flip(x, [-1]),
    (R3,),
    expect=("aten.flip.default",),
    diff=(0,),
    nodes=3,
)
case(
    "flip_no_dims",
    lambda x: torch.flip(x, []) + 1,
    (R3,),
    expect=("aten.flip.default",),
    nodes=4,
)

SQ = _randn(3, 4, 5, seed=30)
for offset in (0, 1, -1, 2, -2):
    case(
        f"diagonal_offset{offset}",
        lambda x, o=offset: torch.diagonal(x, o, 1, 2),
        (SQ,),
        expect=("aten.diagonal.default",),
        diff=(0,),
        nodes=10,
    )
case(
    "diagonal_dim0_dim2",
    lambda x: torch.diagonal(x, 1, 0, 2),
    (SQ,),
    expect=("aten.diagonal.default",),
    diff=(0,),
    nodes=10,
)
case(
    "diagonal_matrix",
    lambda x: torch.diagonal(x),
    (_randn(4, 4, seed=31),),
    expect=("aten.diagonal.default",),
    diff=(0,),
    nodes=10,
)
case(
    "diagonal_tall",
    lambda x: torch.diagonal(x, -1),
    (_randn(5, 3, seed=32),),
    expect=("aten.diagonal.default",),
    diff=(0,),
    nodes=10,
)

case(
    "select_scatter",
    lambda x, s: ATEN.select_scatter(x, s, 1, 1),
    (_randn(2, 3, 4, seed=33), _randn(2, 4, seed=34)),
    expect=("aten.select_scatter.default",),
    raw=True,
    diff=(0, 1),
    nodes=10,
)
case(
    "select_scatter_negative_index",
    lambda x, s: ATEN.select_scatter(x, s, 0, -1),
    (_randn(3, 4, seed=35), _randn(4, seed=36)),
    expect=("aten.select_scatter.default",),
    raw=True,
    diff=(0, 1),
    nodes=10,
)

IDX3 = torch.tensor(
    [
        [[0, 1, 2, 3], [3, 2, 1, 0], [1, 1, 0, 2]],
        [[2, 2, 2, 2], [0, 0, 1, 1], [3, 0, 3, 0]],
    ]
)
case(
    "gather_last_dim",
    lambda x, i: torch.gather(x, 2, i),
    (R3, IDX3),
    expect=("aten.gather.default",),
    diff=(0,),
    nodes=20,
)
case(
    "gather_dim0",
    lambda x, i: torch.gather(x, 0, i),
    (R3, torch.tensor([[[1, 0, 1, 0], [0, 1, 0, 1], [1, 1, 1, 1]]])),
    expect=("aten.gather.default",),
    diff=(0,),
    nodes=20,
)
case(
    "gather_index_smaller_than_input",
    lambda x, i: torch.gather(x, 1, i),
    (R3, torch.tensor([[[2, 0], [1, 1]], [[0, 2], [2, 2]]])),
    expect=("aten.gather.default",),
    diff=(0,),
    nodes=20,
)
case(
    "gather_integers",
    lambda x, i: torch.gather(x, 1, i),
    (_ints(3, 4, seed=37), torch.tensor([[0, 3], [1, 1], [2, 0]])),
    expect=("aten.gather.default",),
)
case(
    "gather_out_of_range_reads_a_fill_not_a_wrap",
    lambda x, i: torch.gather(x, 0, i),
    (_t([1.0, 2.0, 3.0]), torch.tensor([0, 1])),
    expect=("aten.gather.default",),
)

SCATTER_IDX = torch.tensor(
    [
        [[0, 1, 2, 3], [1, 0, 3, 2], [3, 2, 1, 0]],
        [[1, 1, 1, 1], [0, 1, 2, 3], [2, 3, 0, 1]],
    ]
)
case(
    "scatter_src_unique_rows",
    lambda x, s: x.scatter(
        2, torch.tensor([[[0, 1, 2, 3], [1, 0, 3, 2], [3, 2, 1, 0]]] * 2), s
    ),
    (R3, _randn(2, 3, 4, seed=38)),
    expect=("aten.scatter.src",),
    diff=(0, 1),
    nodes=30,
)
case(
    "scatter_src_larger_source",
    lambda x, s: x.scatter(1, torch.tensor([[[0, 1, 2, 0]], [[2, 1, 0, 1]]]), s),
    (R3, _randn(2, 3, 5, seed=39)),
    expect=("aten.scatter.src",),
    nodes=30,
)
case(
    "scatter_value",
    lambda x: x.scatter(
        2, torch.tensor([[[0, 1, 2, 3], [1, 0, 3, 2], [3, 2, 1, 0]]] * 2), 7.5
    ),
    (R3,),
    expect=("aten.scatter.value",),
    diff=(0,),
    nodes=30,
)
case(
    "scatter_value_repeated_index_same_value",
    lambda x: x.scatter(1, torch.tensor([[[0, 0, 0, 0]], [[1, 1, 1, 1]]]), -2.0),
    (R3,),
    expect=("aten.scatter.value",),
    nodes=30,
)

case(
    "scatter_add_with_an_input_index_runs_under_v8",
    lambda x, i, s: x.scatter_add(1, i, s),
    (
        _randn(2, 5, seed=40),
        torch.tensor([[0, 1, 0, 4], [3, 3, 2, 0]]),
        _randn(2, 4, seed=41),
    ),
    expect=("aten.scatter_add.default",),
    diff=(0, 2),
    nodes=30,
)

SR_IDX = torch.tensor([[0, 1, 0, 1, 2], [2, 2, 0, 1, 1]])
SR_SELF = _t([[1.0, 2.0, 3.0], [-1.0, 0.5, 4.0]])
SR_SRC = _t([[0.5, 1.5, 2.5, -1.0, 3.0], [2.0, -2.0, 1.0, 5.0, -3.0]])


def _scatter_reduce_diff(reduce_name, include_self):
    """Inputs to differentiate. prod: JAX has no gradient for the source when
    indices repeat. amax/amin without self: torch still counts the excluded
    self value among the ties it divides the source's gradient by, which is
    its quirk, so only self is compared there."""
    if reduce_name == "prod" or (reduce_name in ("amax", "amin") and not include_self):
        return (0,)
    return (0, 1)


for reduce_name in ("sum", "mean", "amax", "amin", "prod"):
    for include_self in (True, False):
        case(
            f"scatter_reduce_{reduce_name}_include_self_{include_self}",
            lambda x, s, r=reduce_name, inc=include_self: x.scatter_reduce(
                1, SR_IDX, s, r, include_self=inc
            ),
            (SR_SELF, SR_SRC),
            expect=("aten.scatter_reduce.two",),
            rtol=3e-6,
            diff=_scatter_reduce_diff(reduce_name, include_self),
            grad_rtol=3e-5,
            nodes=40,
        )
case(
    "scatter_reduce_untouched_positions_keep_self",
    lambda x, s: x.scatter_reduce(
        1, torch.tensor([[0, 0], [0, 0]]), s, "mean", include_self=False
    ),
    (SR_SELF, SR_SRC[:, :2]),
    expect=("aten.scatter_reduce.two",),
    nodes=40,
)

AS_X = _randn(3, 4, seed=42)
case(
    "as_strided_window",
    lambda x: torch.as_strided(x, (2, 2), (4, 1), 1),
    (AS_X,),
    expect=("aten.as_strided.default",),
    diff=(0,),
    nodes=14,
)
case(
    "as_strided_overlapping_unfold",
    lambda x: torch.as_strided(x, (3, 2, 2), (4, 1, 1), 0)[:, 0],
    (AS_X,),
    expect=("aten.as_strided.default",),
    diff=(0,),
    nodes=20,
)
case(
    "as_strided_transposed_view_of_contiguous",
    lambda x: torch.as_strided(x, (4, 3), (1, 4), 0),
    (AS_X,),
    expect=("aten.as_strided.default",),
    diff=(0,),
    nodes=14,
)

IP_X = _randn(4, 3, seed=43)
case(
    "index_put_rows",
    lambda x, v: x.index_put((torch.tensor([0, 2]),), v),
    (IP_X, _randn(2, 3, seed=44)),
    expect=("aten.index_put.default",),
    diff=(0, 1),
    nodes=30,
)
case(
    "index_put_accumulate_repeated",
    lambda x, v: x.index_put((torch.tensor([1, 1, 3]),), v, accumulate=True),
    (IP_X, _randn(3, 3, seed=45)),
    expect=("aten.index_put.default",),
    diff=(0, 1),
    nodes=30,
)
case(
    "index_put_negative_index_wraps",
    lambda x, v: x.index_put((torch.tensor([-1, 0]),), v),
    (IP_X, _randn(2, 3, seed=46)),
    expect=("aten.index_put.default",),
    diff=(0, 1),
    nodes=30,
)
case(
    "index_put_two_dims",
    lambda x, v: x.index_put(
        (torch.tensor([0, 1, 3]), torch.tensor([2, 0, 1])), v, accumulate=True
    ),
    (IP_X, _randn(3, seed=47)),
    expect=("aten.index_put.default",),
    diff=(0, 1),
    nodes=30,
)
case(
    "index_put_scalar_value",
    lambda x, v: x.index_put((torch.tensor([0, 2]),), v),
    (IP_X, _t(9.0)),
    expect=("aten.index_put.default",),
    diff=(0, 1),
    nodes=30,
)
case(
    "index_put_one_row_broadcast_value",
    lambda x, v: x.index_put((torch.tensor([1]),), v),
    (IP_X, _randn(1, 3, seed=48)),
    expect=("aten.index_put.default",),
    nodes=30,
)

EMB_W = _randn(6, 4, seed=50)
case(
    "embedding",
    lambda w, i: F.embedding(i, w),
    (EMB_W, torch.tensor([[0, 5, 2], [2, 2, 1]])),
    expect=("aten.embedding.default",),
    diff=(0,),
    nodes=10,
)
case(
    "embedding_padding_idx_row_gets_no_gradient",
    lambda w, i: F.embedding(i, w, padding_idx=2),
    (EMB_W, torch.tensor([[0, 2, 2], [2, 1, 1]])),
    expect=("aten.embedding.default",),
    diff=(0,),
    nodes=14,
)
case(
    "embedding_scalar_index",
    lambda w, i: F.embedding(i, w),
    (EMB_W, torch.tensor(3)),
    expect=("aten.embedding.default",),
    diff=(0,),
    nodes=10,
)

# padding modes (raw: the default decompositions rewrite them into index ops)
PAD_X = _randn(2, 3, 6, seed=51)
PAD_IMG = _randn(1, 2, 5, 6, seed=52)
PAD_VOL = _randn(1, 2, 3, 4, 5, seed=53)
case(
    "reflection_pad1d",
    lambda x: ATEN.reflection_pad1d(x, [2, 3]),
    (PAD_X,),
    expect=("aten.reflection_pad1d.default",),
    raw=True,
    diff=(0,),
    nodes=10,
)
case(
    "reflection_pad1d_zero_side",
    lambda x: ATEN.reflection_pad1d(x, [0, 4]),
    (PAD_X,),
    expect=("aten.reflection_pad1d.default",),
    raw=True,
    diff=(0,),
    nodes=10,
)
case(
    "reflection_pad2d",
    lambda x: ATEN.reflection_pad2d(x, [1, 2, 3, 1]),
    (PAD_IMG,),
    expect=("aten.reflection_pad2d.default",),
    raw=True,
    diff=(0,),
    nodes=20,
)
case(
    "reflection_pad3d",
    lambda x: ATEN.reflection_pad3d(x, [1, 1, 2, 1, 1, 2]),
    (PAD_VOL,),
    expect=("aten.reflection_pad3d.default",),
    raw=True,
    diff=(0,),
    nodes=30,
)
case(
    "replication_pad1d",
    lambda x: ATEN.replication_pad1d(x, [2, 3]),
    (PAD_X,),
    expect=("aten.replication_pad1d.default",),
    raw=True,
    diff=(0,),
    nodes=10,
)
case(
    "replication_pad2d",
    lambda x: ATEN.replication_pad2d(x, [1, 2, 3, 1]),
    (PAD_IMG,),
    expect=("aten.replication_pad2d.default",),
    raw=True,
    diff=(0,),
    nodes=20,
)
case(
    "replication_pad3d",
    lambda x: ATEN.replication_pad3d(x, [1, 1, 2, 1, 1, 2]),
    (PAD_VOL,),
    expect=("aten.replication_pad3d.default",),
    raw=True,
    diff=(0,),
    nodes=30,
)
case(
    "replication_pad2d_wider_than_input",
    lambda x: ATEN.replication_pad2d(x, [7, 0, 0, 5]),
    (PAD_IMG,),
    expect=("aten.replication_pad2d.default",),
    raw=True,
    diff=(0,),
    nodes=20,
)

# resizing
case(
    "upsample_nearest2d_scale2",
    lambda x: F.interpolate(x, scale_factor=2, mode="nearest"),
    (PAD_IMG,),
    expect=("aten.upsample_nearest2d.vec",),
    diff=(0,),
    nodes=24,
)
case(
    "upsample_nearest2d_size_odd",
    lambda x: F.interpolate(x, size=(9, 4), mode="nearest"),
    (PAD_IMG,),
    expect=("aten.upsample_nearest2d.vec",),
    diff=(0,),
    nodes=24,
)
case(
    "upsample_nearest2d_fractional_scale",
    lambda x: F.interpolate(x, scale_factor=(1.5, 2.5), mode="nearest"),
    (PAD_IMG,),
    expect=("aten.upsample_nearest2d.vec",),
    diff=(0,),
    nodes=24,
)
case(
    "upsample_nearest2d_down",
    lambda x: F.interpolate(x, size=(2, 3), mode="nearest"),
    (PAD_IMG,),
    expect=("aten.upsample_nearest2d.vec",),
    diff=(0,),
    nodes=24,
)
case(
    "upsample_nearest2d_float64",
    lambda x: F.interpolate(x, scale_factor=3, mode="nearest"),
    (PAD_IMG.double(),),
    expect=("aten.upsample_nearest2d.vec",),
    rtol=0,
    atol=0,
    nodes=24,
    x64=True,
)
for tag, kwargs in (
    ("scale2", {"scale_factor": 2}),
    ("size_odd", {"size": (9, 4)}),
    ("down", {"size": (2, 3)}),
    ("fractional_scale", {"scale_factor": (1.5, 2.5)}),
):
    for align in (False, True):
        case(
            f"upsample_bilinear2d_{tag}_align_{align}",
            lambda x, k=kwargs, a=align: F.interpolate(
                x, mode="bilinear", align_corners=a, **k
            ),
            (PAD_IMG,),
            expect=("aten.upsample_bilinear2d.vec",),
            rtol=3e-5,
            atol=3e-5,
            diff=(0,),
            grad_rtol=1e-4,
            grad_atol=1e-4,
            nodes=80,
        )
case(
    "upsample_bilinear2d_to_one_pixel",
    lambda x: F.interpolate(x, size=(1, 1), mode="bilinear", align_corners=True),
    (PAD_IMG,),
    expect=("aten.upsample_bilinear2d.vec",),
    rtol=3e-5,
    atol=3e-5,
    nodes=80,
)

# sorting and selection
SORT_X = _t(
    [[3.0, 1.0, 2.0, 1.0, NAN, -0.0, 0.0], [5.0, 5.0, 5.0, -1.0, 2.0, INF, -INF]]
)
case(
    "sort_ascending",
    lambda x: torch.sort(x, dim=1, stable=True),
    (SORT_X,),
    expect=("aten.sort.stable",),
    nodes=6,
)
case(
    "sort_default_overload",
    lambda x: ATEN.sort(x, 1, False),
    (SORT_X,),
    expect=("aten.sort.default",),
    raw=True,
    nodes=6,
)
case(
    "sort_descending",
    lambda x: torch.sort(x, dim=1, descending=True, stable=True),
    (SORT_X,),
    expect=("aten.sort.stable",),
    nodes=12,
)
case(
    "sort_default_overload_descending",
    lambda x: ATEN.sort(x, 1, True),
    (SORT_X[:, :3].clone(),),
    expect=("aten.sort.default",),
    raw=True,
    nodes=12,
)
case(
    "sort_dim0",
    lambda x: torch.sort(x, dim=0),
    (R3[:, :, 0],),
    expect=("aten.sort.default",),
    diff=(0,),
    nodes=6,
)
case(
    "sort_values_gradient",
    lambda x: torch.sort(x, dim=2)[0],
    (R3,),
    expect=("aten.sort.default",),
    diff=(0,),
    nodes=6,
)
case(
    "sort_descending_gradient",
    lambda x: torch.sort(x, dim=1, descending=True)[0],
    (R3,),
    expect=("aten.sort.default",),
    diff=(0,),
    nodes=12,
)
case(
    "sort_integers",
    lambda x: torch.sort(x, dim=1, stable=True),
    (_ints(3, 6, seed=60),),
    expect=("aten.sort.stable",),
    nodes=6,
)
case(
    "sort_scalar",
    lambda x: torch.sort(x),
    (_t(2.0),),
    expect=("aten.sort.default",),
    nodes=6,
)
case(
    "argsort_stable",
    lambda x: torch.argsort(x, dim=1, stable=True).to(torch.float32),
    (SORT_X,),
    expect=("aten.sort.stable",),
    nodes=6,
)

TOPK_X = _t(
    [
        [3.0, 1.0, 4.0, 1.5, 9.0, 2.0],
        [-1.0, -5.0, 0.0, 7.0, 7.5, -2.0],
        [2.0, 2.0, 2.0, 1.0, 3.0, 3.0],
    ]
)
case(
    "topk_largest",
    lambda x: torch.topk(x, 3, dim=1),
    (TOPK_X[:2],),
    expect=("aten.topk.default",),
    diff=(0,),
    nodes=10,
)
case(
    "topk_largest_values_with_ties",
    lambda x: torch.topk(x, 4, dim=1)[0],
    (TOPK_X,),
    expect=("aten.topk.default",),
    nodes=10,
)
case(
    "topk_smallest",
    lambda x: torch.topk(x, 2, dim=1, largest=False),
    (TOPK_X[:2],),
    expect=("aten.topk.default",),
    diff=(0,),
    nodes=10,
)
case(
    "topk_dim0",
    lambda x: torch.topk(x, 2, dim=0),
    (TOPK_X,),
    expect=("aten.topk.default",),
    diff=(0,),
    nodes=10,
)
case(
    "topk_nan_is_largest",
    lambda x: torch.topk(x, 2, dim=1)[0],
    (_t([[1.0, NAN, 3.0, 2.0]]),),
    expect=("aten.topk.default",),
    nodes=10,
)
case(
    "topk_smallest_nan_never_chosen",
    lambda x: torch.topk(x, 2, dim=1, largest=False)[0],
    (_t([[1.0, NAN, 3.0, 2.0]]),),
    expect=("aten.topk.default",),
    nodes=10,
)
case(
    "topk_all",
    lambda x: torch.topk(x, 6, dim=1)[0],
    (TOPK_X[:1],),
    expect=("aten.topk.default",),
    diff=(0,),
    nodes=10,
)
case(
    "topk_3d_middle_dim",
    lambda x: torch.topk(x, 2, dim=1)[0],
    (R3,),
    expect=("aten.topk.default",),
    diff=(0,),
    nodes=10,
)

# col2im, masked_scatter
COL = _randn(1, 2 * 2 * 2, 9, seed=70)
case(
    "col2im_overlapping",
    lambda c: F.fold(c, (4, 4), (2, 2), stride=1),
    (COL,),
    expect=("aten.col2im.default",),
    raw=True,
    rtol=3e-6,
    atol=3e-6,
    diff=(0,),
    nodes=60,
)
case(
    "col2im_stride_padding_dilation",
    lambda c: F.fold(c, (5, 6), (2, 3), dilation=(1, 1), padding=(1, 1), stride=(2, 2)),
    (_randn(2, 1 * 2 * 3, 3 * 3, seed=71),),
    expect=("aten.col2im.default",),
    raw=True,
    rtol=3e-6,
    atol=3e-6,
    diff=(0,),
    nodes=60,
)
case(
    "col2im_dilation",
    lambda c: F.fold(c, (6, 6), (2, 2), dilation=2),
    (_randn(1, 4, 16, seed=72),),
    expect=("aten.col2im.default",),
    raw=True,
    rtol=3e-6,
    atol=3e-6,
    diff=(0,),
    nodes=60,
)
case(
    "col2im_unbatched",
    lambda c: F.fold(c, (3, 3), (2, 2)),
    (_randn(4, 4, seed=73),),
    expect=("aten.col2im.default",),
    raw=True,
    rtol=3e-6,
    atol=3e-6,
    diff=(0,),
    nodes=60,
)

MS_X = _randn(2, 3, seed=76)
case(
    "masked_scatter",
    lambda x, m, s: x.masked_scatter(m, s),
    (
        MS_X,
        _t([[True, False, True], [False, True, True]], torch.bool),
        _randn(6, seed=77),
    ),
    expect=("aten.masked_scatter.default",),
    diff=(0, 2),
    nodes=20,
)
case(
    "masked_scatter_broadcast_mask",
    lambda x, m, s: x.masked_scatter(m, s),
    (MS_X, _t([True, False, True], torch.bool), _randn(2, 2, seed=78)),
    expect=("aten.masked_scatter.default",),
    diff=(0, 2),
    nodes=20,
)
case(
    "masked_scatter_nothing_selected",
    lambda x, m, s: x.masked_scatter(m, s),
    (MS_X, torch.zeros(2, 3, dtype=torch.bool), _randn(3, seed=79)),
    expect=("aten.masked_scatter.default",),
    diff=(0, 2),
    nodes=20,
)

# -- pooling ------------------------------------------------------------------------------

POOL_IMG = _randn(2, 3, 7, 8, seed=80)
POOL_VOL = _randn(1, 2, 5, 6, 7, seed=81)
POOL_TOL = {"rtol": 3e-6, "atol": 3e-6, "grad_rtol": 3e-5, "grad_atol": 3e-6}
for tag, kwargs in (
    ("k2", {"kernel_size": 2}),
    ("k3_s2_p1", {"kernel_size": 3, "stride": 2, "padding": 1}),
    (
        "k3_s2_p1_exclude_pad",
        {"kernel_size": 3, "stride": 2, "padding": 1, "count_include_pad": False},
    ),
    ("k3_s2_ceil", {"kernel_size": 3, "stride": 2, "ceil_mode": True}),
    ("k3_s2_p1_ceil", {"kernel_size": 3, "stride": 2, "padding": 1, "ceil_mode": True}),
    (
        "k3_s2_p1_ceil_exclude_pad",
        {
            "kernel_size": 3,
            "stride": 2,
            "padding": 1,
            "ceil_mode": True,
            "count_include_pad": False,
        },
    ),
    ("rect_kernel", {"kernel_size": (2, 3), "stride": (1, 2)}),
    ("divisor_override", {"kernel_size": 3, "stride": 1, "divisor_override": 2}),
):
    case(
        f"avg_pool2d_{tag}",
        lambda x, k=kwargs: F.avg_pool2d(x, **k),
        (POOL_IMG,),
        expect=("aten.avg_pool2d.default",),
        diff=(0,),
        nodes=30,
        **POOL_TOL,
    )
case(
    "avg_pool2d_unbatched",
    lambda x: F.avg_pool2d(x, 2),
    (POOL_IMG[0],),
    expect=("aten.avg_pool2d.default",),
    diff=(0,),
    nodes=30,
    **POOL_TOL,
)
case(
    "avg_pool1d_through_avg_pool2d",
    lambda x: F.avg_pool1d(x, 3, 2, 1),
    (_randn(2, 3, 9, seed=82),),
    expect=("aten.avg_pool2d.default",),
    diff=(0,),
    nodes=30,
    **POOL_TOL,
)
for tag, kwargs in (
    ("k2", {"kernel_size": 2}),
    ("k3_s2_p1", {"kernel_size": 3, "stride": 2, "padding": 1}),
    (
        "k3_s2_ceil_exclude_pad",
        {"kernel_size": 3, "stride": 2, "ceil_mode": True, "count_include_pad": False},
    ),
):
    case(
        f"avg_pool3d_{tag}",
        lambda x, k=kwargs: F.avg_pool3d(x, **k),
        (POOL_VOL,),
        expect=("aten.avg_pool3d.default",),
        diff=(0,),
        nodes=30,
        **POOL_TOL,
    )
for size in ((3, 2), (7, 8), (1, 3), (2, 4), (5, 3)):
    case(
        f"adaptive_avg_pool2d_{size[0]}x{size[1]}",
        lambda x, s=size: F.adaptive_avg_pool2d(x, s) + 0.0,
        (POOL_IMG,),
        expect=("aten._adaptive_avg_pool2d.default",),
        diff=(0,),
        nodes=120,
        **POOL_TOL,
    )
case(
    "adaptive_avg_pool2d_to_one_is_a_mean",
    lambda x: F.adaptive_avg_pool2d(x, 1),
    (POOL_IMG,),
    expect=("aten.mean.dim",),
    diff=(0,),
    nodes=20,
    **POOL_TOL,
)
case(
    "adaptive_avg_pool2d_unbatched",
    lambda x: F.adaptive_avg_pool2d(x, (2, 3)),
    (POOL_IMG[0],),
    expect=("aten._adaptive_avg_pool2d.default",),
    diff=(0,),
    nodes=120,
    **POOL_TOL,
)
for size in ((2, 2, 3), (5, 6, 7), (3, 1, 4)):
    case(
        f"adaptive_avg_pool3d_{size[0]}x{size[1]}x{size[2]}",
        lambda x, s=size: F.adaptive_avg_pool3d(x, s),
        (POOL_VOL,),
        expect=("aten._adaptive_avg_pool3d.default",),
        diff=(0,),
        nodes=120,
        **POOL_TOL,
    )
MAXP_TOL = {"rtol": 0, "atol": 0, "grad_rtol": 1e-6, "grad_atol": 1e-6}
POOL_DISTINCT = (
    torch.randperm(2 * 3 * 7 * 8, generator=torch.Generator().manual_seed(83))
    .reshape(2, 3, 7, 8)
    .float()
)
VOL_DISTINCT = (
    torch.randperm(2 * 5 * 6 * 7, generator=torch.Generator().manual_seed(84))
    .reshape(1, 2, 5, 6, 7)
    .float()
)
for tag, kwargs in (
    ("k2", {"kernel_size": 2}),
    ("k3_s2_p1", {"kernel_size": 3, "stride": 2, "padding": 1}),
    ("k3_s2_ceil", {"kernel_size": 3, "stride": 2, "ceil_mode": True}),
    ("k3_s2_p1_ceil", {"kernel_size": 3, "stride": 2, "padding": 1, "ceil_mode": True}),
):
    case(
        f"max_pool3d_{tag}",
        lambda x, k=kwargs: F.max_pool3d(x, **k),
        (VOL_DISTINCT,),
        expect=("aten.max_pool3d_with_indices.default",),
        diff=(0,),
        nodes=10,
        **MAXP_TOL,
    )
for tag, kwargs in (
    ("k3_s2_p1", {"kernel_size": 3, "stride": 2, "padding": 1}),
    ("k3_s1", {"kernel_size": 3, "stride": 1}),
    ("k3_s2_ceil", {"kernel_size": 3, "stride": 2, "ceil_mode": True}),
):
    case(
        f"max_pool2d_overlapping_{tag}",
        lambda x, k=kwargs: F.max_pool2d(x, **k),
        (POOL_DISTINCT,),
        expect=("aten.max_pool2d_with_indices.default",),
        diff=(0,),
        nodes=10,
        v7="refuse",
        **MAXP_TOL,
    )
case(
    "max_pool2d_non_overlapping_unchanged",
    lambda x: F.max_pool2d(x, 2),
    (POOL_DISTINCT,),
    expect=("aten.max_pool2d_with_indices.default",),
    diff=(0,),
    nodes=10,
    v7=False,
    **MAXP_TOL,
)
case(
    "max_pool1d_through_max_pool2d",
    lambda x: F.max_pool1d(x, 3, 2, 1),
    (POOL_DISTINCT[0, :, 0, :],),
    expect=("aten.max_pool2d_with_indices.default",),
    diff=(0,),
    nodes=10,
    v7="refuse",
    **MAXP_TOL,
)

# -- normalization and distances ------------------------------------------------------------

GN_X = _randn(2, 4, 5, seed=90)
GN_W, GN_B = _randn(4, seed=91) + 1.0, _randn(4, seed=92)
GN_TOL = {"rtol": 3e-5, "atol": 3e-5, "grad_rtol": 3e-4, "grad_atol": 3e-4}
for groups in (1, 2, 4):
    case(
        f"group_norm_{groups}_groups",
        lambda x, w, b, g=groups: F.group_norm(x, g, w, b, 1e-5),
        (GN_X, GN_W, GN_B),
        expect=("aten.native_group_norm.default",),
        diff=(0, 1, 2),
        nodes=40,
        **GN_TOL,
    )
case(
    "group_norm_images",
    lambda x, w, b: F.group_norm(x, 2, w, b, 1e-3),
    (_randn(2, 4, 3, 3, seed=93), GN_W, GN_B),
    expect=("aten.native_group_norm.default",),
    diff=(0, 1, 2),
    nodes=40,
    **GN_TOL,
)
case(
    "group_norm_without_affine",
    lambda x: F.group_norm(x, 2),
    (GN_X,),
    expect=("aten.native_group_norm.default",),
    diff=(0,),
    nodes=40,
    **GN_TOL,
)
case(
    "group_norm_mean_and_rstd_outputs",
    lambda x, w, b: ATEN.native_group_norm(x, w, b, 2, 4, 5, 2, 1e-5)[1:],
    (GN_X, GN_W, GN_B),
    expect=("aten.native_group_norm.default",),
    raw=True,
    nodes=40,
    **GN_TOL,
)
BN_X = _randn(4, 3, 5, seed=94)
case(
    "batch_norm_training_statistics_only",
    lambda x, w, b: F.batch_norm(
        x, torch.zeros(3), torch.ones(3), w, b, True, 0.1, 1e-5
    ),
    (BN_X, _randn(3, seed=95) + 1.0, _randn(3, seed=96)),
    expect=("aten._native_batch_norm_legit_functional.default",),
    diff=(0, 1, 2),
    nodes=40,
    **GN_TOL,
)

CD_A, CD_B = _randn(2, 5, 3, seed=100), _randn(2, 4, 3, seed=101)
NO_MM = "donot_use_mm_for_euclid_dist"
for p in (2.0, 1.0, 3.0, 0.5, INF, 0.0):
    case(
        f"cdist_p{p}",
        lambda a, c, q=p: torch.cdist(a, c, p=q, compute_mode=NO_MM),
        (CD_A, CD_B),
        expect=("aten._cdist_forward.default",),
        rtol=1e-5,
        atol=1e-5,
        diff=(0, 1) if p != 0.0 else (),
        grad_rtol=1e-4,
        grad_atol=1e-5,
        nodes=40,
    )
case(
    "cdist_unbatched_and_broadcast_batch",
    lambda a, c: torch.cdist(a, c, compute_mode=NO_MM),
    (_randn(5, 3, seed=102), _randn(2, 4, 3, seed=103)),
    expect=("aten._cdist_forward.default",),
    rtol=1e-5,
    atol=1e-5,
    diff=(0, 1),
    grad_rtol=1e-4,
    grad_atol=1e-5,
    nodes=40,
)
case(
    "cdist_zero_distance_has_zero_gradient",
    lambda a, c: torch.cdist(a, c, compute_mode=NO_MM),
    (CD_A[0], CD_A[0][:3].clone()),
    expect=("aten._cdist_forward.default",),
    rtol=1e-5,
    atol=1e-5,
    diff=(0, 1),
    grad_rtol=1e-4,
    grad_atol=1e-5,
    nodes=40,
)
for p in (2.0, 1.0, 3.0, INF):
    case(
        f"pdist_p{p}",
        lambda a, q=p: F.pdist(a, q),
        (_randn(6, 3, seed=104),),
        expect=("aten._pdist_forward.default",),
        rtol=1e-5,
        atol=1e-5,
        diff=(0,),
        grad_rtol=1e-4,
        grad_atol=1e-5,
        nodes=60,
    )
case(
    "pdist_coincident_rows_have_zero_gradient",
    lambda a: F.pdist(a),
    (torch.cat([CD_A[0][:2], CD_A[0][:1]]),),
    expect=("aten._pdist_forward.default",),
    rtol=1e-5,
    atol=1e-5,
    diff=(0,),
    grad_rtol=1e-4,
    grad_atol=1e-5,
    nodes=60,
)

# -- grid sampling --------------------------------------------------------------------------

GRID_IMG = _randn(2, 3, 5, 6, seed=110)
GRID = torch.rand(2, 4, 3, 2, generator=torch.Generator().manual_seed(111)) * 2.4 - 1.2
GRID_IN = (
    torch.rand(2, 4, 3, 2, generator=torch.Generator().manual_seed(112)) * 1.6 - 0.8
)
for tag, mode, padding in (
    ("bilinear_zeros", "bilinear", "zeros"),
    ("bilinear_border", "bilinear", "border"),
    ("nearest_zeros", "nearest", "zeros"),
    ("nearest_border", "nearest", "border"),
):
    for align in (False, True):
        case(
            f"grid_sample_{tag}_align_{align}",
            lambda x, g, m=mode, p=padding, a=align: F.grid_sample(
                x, g, mode=m, padding_mode=p, align_corners=a
            ),
            (GRID_IMG, GRID),
            expect=("aten.grid_sampler_2d.default",),
            rtol=3e-5,
            atol=3e-5,
            diff=(0, 1) if mode == "bilinear" else (0,),
            grad_inputs=(GRID_IMG, GRID_IN),
            grad_rtol=3e-4,
            grad_atol=3e-4,
            nodes=200,
        )
case(
    "grid_sample_nan_input_does_not_leak_through_masked_taps",
    lambda x, g: F.grid_sample(
        x, g, mode="bilinear", padding_mode="zeros", align_corners=False
    ),
    (
        torch.where(
            torch.arange(30).reshape(1, 1, 5, 6) == 0,
            torch.tensor(NAN),
            _randn(1, 1, 5, 6, seed=113),
        ),
        torch.tensor([[[[0.9, 0.9], [-1.5, -1.5], [0.5, -0.5]]]]),
    ),
    expect=("aten.grid_sampler_2d.default",),
    rtol=3e-5,
    atol=3e-5,
    nodes=200,
)

# -- linear algebra -------------------------------------------------------------------------

SPD_BASE = _randn(4, 4, seed=120)
SPD = SPD_BASE @ SPD_BASE.T + 4 * torch.eye(4)
LA_TOL = {"rtol": 3e-5, "atol": 3e-5, "grad_rtol": 3e-4, "grad_atol": 3e-4}
case(
    "cholesky_ex_lower",
    lambda a: torch.linalg.cholesky_ex(a)[0],
    (SPD,),
    expect=("aten.linalg_cholesky_ex.default",),
    nodes=30,
    **LA_TOL,
)
case(
    "cholesky_ex_from_a_product",
    lambda x: torch.linalg.cholesky_ex(x @ x.mT + 4 * torch.eye(4))[0],
    (SPD_BASE,),
    expect=("aten.linalg_cholesky_ex.default",),
    diff=(0,),
    nodes=60,
    **LA_TOL,
)
case(
    "cholesky_ex_upper_batched",
    lambda x: torch.linalg.cholesky_ex(x @ x.mT + 4 * torch.eye(4), upper=True)[0],
    (_randn(2, 4, 4, seed=121),),
    expect=("aten.linalg_cholesky_ex.default",),
    diff=(0,),
    nodes=60,
    **LA_TOL,
)
case(
    "cholesky_ex_reads_only_the_lower_triangle",
    lambda a: torch.linalg.cholesky_ex(a)[0],
    (torch.tril(SPD) + torch.triu(torch.full((4, 4), 99.0), 1),),
    expect=("aten.linalg_cholesky_ex.default",),
    nodes=60,
    **LA_TOL,
)
RHS = _randn(4, 3, seed=123)
for tag, kwargs in (
    ("lower", {"upper": False}),
    ("upper", {"upper": True}),
    ("lower_unit", {"upper": False, "unitriangular": True}),
):
    case(
        f"solve_triangular_{tag}",
        lambda a, c, k=kwargs: torch.linalg.solve_triangular(
            (a.triu() if k["upper"] else a.tril()) + 3 * torch.eye(4), c, **k
        ),
        (_randn(4, 4, seed=124), RHS),
        expect=("aten.linalg_solve_triangular.default",),
        diff=(0, 1),
        nodes=40,
        **LA_TOL,
    )
case(
    "solve_triangular_from_the_right",
    lambda a, c: torch.linalg.solve_triangular(
        a.tril() + 3 * torch.eye(4), c, upper=False, left=False
    ),
    (_randn(4, 4, seed=125), _randn(3, 4, seed=126)),
    expect=("aten.linalg_solve_triangular.default",),
    diff=(0, 1),
    nodes=40,
    **LA_TOL,
)
case(
    "solve_triangular_batched_broadcast",
    lambda a, c: torch.linalg.solve_triangular(
        a.tril() + 3 * torch.eye(4), c, upper=False
    ),
    (_randn(4, 4, seed=127), _randn(2, 4, 3, seed=128)),
    expect=("aten.linalg_solve_triangular.default",),
    diff=(0, 1),
    nodes=40,
    **LA_TOL,
)


def _eigh_reconstruction(x):
    values, vectors = torch.linalg.eigh(x + x.T)
    return (vectors * values) @ vectors.mT


def _qr_checks(x):
    q, r = torch.linalg.qr(x)
    return q @ r, q.mT @ q, torch.triu(r) - r


def _qr_complete(x):
    q, r = torch.linalg.qr(x, mode="complete")
    return q @ r, q.mT @ q


def _svd_reconstruction(x):
    u, s, vh = torch.linalg.svd(x, full_matrices=False)
    return (u * s) @ vh


def _svd_orthogonality(x):
    u, s, _vh = torch.linalg.svd(x, full_matrices=True)
    return u.mT @ u, s


EIG_BASE = _randn(4, 4, seed=130)
case(
    "eigh_eigenvalues",
    lambda a: torch.linalg.eigh(a)[0],
    (EIG_BASE + EIG_BASE.T,),
    expect=("aten._linalg_eigh.default",),
    nodes=40,
    **LA_TOL,
)
case(
    "eigh_eigenvalues_of_the_lower_triangle",
    lambda a: torch.linalg.eigh(a)[0],
    (EIG_BASE,),
    expect=("aten._linalg_eigh.default",),
    nodes=40,
    **LA_TOL,
)
case(
    "eigh_eigenvalues_upper",
    lambda a: torch.linalg.eigh(a, UPLO="U")[0],
    (EIG_BASE,),
    expect=("aten._linalg_eigh.default",),
    nodes=40,
    **LA_TOL,
)
case(
    "eigh_eigenvalue_gradient",
    lambda x: torch.linalg.eigvalsh(x + x.T),
    (EIG_BASE,),
    expect=("aten._linalg_eigh.default",),
    diff=(0,),
    nodes=60,
    **LA_TOL,
)
case(
    "eigh_reconstruction_is_a_gauge_free_output",
    _eigh_reconstruction,
    (EIG_BASE,),
    expect=("aten._linalg_eigh.default",),
    diff=(0,),
    nodes=60,
    rtol=1e-4,
    atol=1e-4,
    grad_rtol=1e-3,
    grad_atol=1e-3,
)
QR_X = _randn(5, 3, seed=131)
case(
    "qr_reconstruction_and_orthogonality",
    _qr_checks,
    (QR_X,),
    expect=("aten.linalg_qr.default",),
    diff=(0,),
    nodes=60,
    rtol=1e-4,
    atol=1e-4,
    grad_rtol=1e-3,
    grad_atol=1e-3,
)
case(
    "qr_complete_mode",
    _qr_complete,
    (QR_X,),
    expect=("aten.linalg_qr.default",),
    nodes=60,
    rtol=1e-4,
    atol=1e-4,
)
case(
    "qr_r_diagonal_magnitudes",
    lambda x: torch.linalg.qr(x)[1].diagonal().abs(),
    (QR_X,),
    expect=("aten.linalg_qr.default",),
    diff=(0,),
    nodes=60,
    rtol=1e-4,
    atol=1e-4,
    grad_rtol=1e-3,
    grad_atol=1e-3,
)
SVD_X = _randn(5, 3, seed=132)
case(
    "svd_singular_values",
    lambda x: torch.linalg.svdvals(x),
    (SVD_X,),
    expect=("aten._linalg_svd.default",),
    diff=(0,),
    nodes=40,
    **LA_TOL,
)
case(
    "svd_reconstruction",
    _svd_reconstruction,
    (SVD_X,),
    expect=("aten._linalg_svd.default",),
    diff=(0,),
    nodes=60,
    rtol=1e-4,
    atol=1e-4,
    grad_rtol=1e-3,
    grad_atol=1e-3,
)
case(
    "svd_full_matrices_orthogonality",
    _svd_orthogonality,
    (SVD_X,),
    expect=("aten._linalg_svd.default",),
    nodes=60,
    rtol=1e-4,
    atol=1e-4,
)
case(
    "svd_wide_batched_values",
    lambda x: torch.linalg.svdvals(x),
    (_randn(2, 3, 5, seed=133),),
    expect=("aten._linalg_svd.default",),
    diff=(0,),
    nodes=40,
    **LA_TOL,
)
SOLVE_A = _randn(4, 4, seed=134) + 4 * torch.eye(4)
case(
    "solve_via_lu",
    lambda a, c: torch.linalg.solve_ex(a, c)[0],
    (SOLVE_A, RHS),
    expect=("aten._linalg_solve_ex.default",),
    diff=(0, 1),
    nodes=40,
    **LA_TOL,
)
case(
    "solve_via_lu_batched",
    lambda a, c: torch.linalg.solve_ex(a, c)[0],
    (torch.stack([SOLVE_A, SOLVE_A.flip(0) + torch.eye(4)]), _randn(2, 4, 2, seed=135)),
    expect=("aten._linalg_solve_ex.default",),
    diff=(0, 1),
    nodes=40,
    **LA_TOL,
)
case(
    "solve_via_lu_needs_a_pivot",
    lambda a, c: torch.linalg.solve_ex(a, c)[0],
    (_t([[0.0, 2.0, 1.0], [1.0, 0.0, 3.0], [2.0, 1.0, 0.0]]), _randn(3, 2, seed=136)),
    expect=("aten._linalg_solve_ex.default",),
    diff=(0, 1),
    nodes=40,
    **LA_TOL,
)


# -- the runner --------------------------------------------------------------------------------


def _x64(enabled):
    if not enabled:
        return contextlib.nullcontext()
    try:
        from jax.experimental import enable_x64
    except ImportError:  # pragma: no cover - newer JAX
        return jax.enable_x64(True)
    return enable_x64()


@pytest.mark.parametrize("spec", CASES)
def test_lowering_matches_torch(spec):
    module = Fn(spec["fn"])
    inputs = spec["inputs"]
    label = spec["fn"].__name__
    rtol, atol = spec["rtol"], spec["atol"]
    with _x64(spec["x64"]):
        doc, run, targets = _lowered(module, inputs, V8, spec["raw"])
        for target in spec["expect"]:
            assert target in targets, (target, sorted(targets))
        nodes = sum(len(g["nodes"]) for g in doc["graphs"].values())
        assert nodes <= spec["nodes"], f"{nodes} nodes"
        refused = spec["v7"]
        if refused == "refuse" or (refused == "auto" and targets & V8_ONLY):
            with pytest.raises(graph.GraphRefused):
                _lowered(module, inputs, V7, spec["raw"])
        got = run(*_jax(*inputs))
        want = _listed(module(*inputs))
        assert len(got) == len(want)
        for position, (g, w) in enumerate(zip(got, want)):
            _same(g, w, rtol, atol, f"{label} output {position}")
            if spec["signs"] and w.dtype.is_floating_point:
                np.testing.assert_array_equal(
                    np.signbit(np.asarray(g)), np.signbit(w.numpy())
                )
        again = run(*_jax(*inputs))
        assert [_bits(g) for g in got] == [_bits(g) for g in again], "rerun differs"
        if spec["diff"]:
            at = spec["grad_inputs"] or inputs
            _doc, grad_run, _ = _lowered(module, at, V8, spec["raw"])
            _gradients(
                module,
                grad_run,
                at,
                spec["diff"],
                spec["grad_rtol"] or max(rtol, 1e-5),
                spec["grad_atol"] or max(atol, 1e-6),
                label,
            )


# -- embedding bags (a module parameter, so not in the table) ---------------------------------


class Bag(torch.nn.Module):
    def __init__(self, mode, padding_idx=None, per_sample=False, last=False):
        super().__init__()
        torch.manual_seed(140)
        self.weight = torch.nn.Parameter(torch.randn(6, 4))
        self.mode, self.padding, self.per_sample, self.last = (
            mode,
            padding_idx,
            per_sample,
            last,
        )

    def forward(self, index, offsets, weights=None):
        return F.embedding_bag(
            index,
            self.weight,
            offsets,
            mode=self.mode,
            padding_idx=self.padding,
            per_sample_weights=weights if self.per_sample else None,
            include_last_offset=self.last,
        )


BAG_INDEX = torch.tensor([0, 2, 1, 1, 5, 3, 3, 4])
BAG_PSW = torch.tensor([0.5, 2.0, -1.0, 1.0, 0.25, 3.0, 1.5, -2.0])


@pytest.mark.parametrize(
    "mode, offsets, extra",
    [
        ("sum", [0, 2, 2, 5], {}),
        ("sum", [0, 3, 8], {"per_sample": True}),
        ("sum", [0, 2, 5, 8], {"last": True}),
        ("sum", [0, 2, 5], {"padding_idx": 1}),
        ("mean", [0, 2, 2, 5], {}),
        ("mean", [0, 4], {"padding_idx": 3}),
        ("max", [0, 2, 2, 5], {}),
        ("max", [0, 3], {"padding_idx": 1}),
    ],
    ids=lambda v: str(v),
)
def test_embedding_bag_matches_torch(mode, offsets, extra):
    module = Bag(mode, **extra)
    offsets = torch.tensor(offsets)
    inputs = (BAG_INDEX, offsets) + ((BAG_PSW,) if extra.get("per_sample") else ())
    _doc, rebuilt, targets = _lowered(module, inputs)
    assert targets & {
        "aten._embedding_bag.default",
        "aten._embedding_bag_forward_only.default",
    }
    weights = [jax.numpy.asarray(p.detach().numpy()) for p in module.parameters()]
    got = rebuilt(*weights, *_jax(*inputs))
    want = module(*inputs)
    _same(got[0], want, 3e-6, 3e-6, "embedding bag")
    assert _bits(got[0]) == _bits(rebuilt(*weights, *_jax(*inputs))[0])
    with pytest.raises(graph.GraphRefused):
        _lowered(module, inputs, V7)
    # gradient of the weight
    module.zero_grad()
    out = module(*inputs)
    probe = torch.linspace(-1.5, 2.0, out.numel()).reshape(out.shape)
    (out * probe).sum().backward()
    jprobe = jax.numpy.asarray(probe.numpy())
    grad = jax.grad(lambda w: (rebuilt(w, *_jax(*inputs))[0] * jprobe).sum())(
        weights[0]
    )
    np.testing.assert_allclose(
        np.asarray(grad), module.weight.grad.numpy(), rtol=3e-5, atol=3e-5
    )


def test_embedding_bag_auxiliary_outputs_refuse_by_name():
    class Raw(torch.nn.Module):
        def forward(self, weight, index, offsets):
            return torch.embedding_bag(weight, index, offsets)

    example = (_randn(6, 4, seed=141), BAG_INDEX, torch.tensor([0, 3]))
    with pytest.raises(graph.GraphRefused) as refused:
        _lowered(Raw(), example)
    assert refused.value.code == "aten_embedding_bag_auxiliary_output"


# -- named refusals -----------------------------------------------------------------------------


def _refusal_code(module, example, raw=False, path=V8):
    with pytest.raises(graph.GraphRefused) as refused:
        _lowered(module, example, path, raw)
    return refused.value.code


def test_batch_norm_running_statistics_update_refuses_by_name():
    module = torch.nn.BatchNorm1d(3).train()
    assert _refusal_code(module, (_randn(4, 3, 5, seed=142),)) == (
        "aten_batch_norm_running_stats_update"
    )


def test_linalg_outputs_that_are_not_computed_refuse_by_name():
    spd = SPD_BASE @ SPD_BASE.T + torch.eye(4)
    assert _refusal_code(Fn(lambda a: torch.linalg.cholesky_ex(a)), (spd,)) == (
        "aten_linalg_info_not_computed"
    )
    assert _refusal_code(
        Fn(lambda a, c: torch.linalg.solve_ex(a, c)), (SOLVE_A, RHS)
    ) == ("aten_linalg_solve_auxiliary_output")


def test_as_strided_refuses_what_it_cannot_address():
    transposed = Fn(lambda x: torch.as_strided(x.t(), (2, 2), (3, 1), 0))
    assert _refusal_code(transposed, (AS_X,)) == "aten_arguments_not_supported"
    beyond = Fn(lambda x: torch.as_strided(x, (3, 3), (4, 2), 5))
    assert _refusal_code(beyond, (AS_X,)) == "aten_as_strided_out_of_bounds"


def test_grid_sampler_refuses_bicubic_and_reflection():
    for kwargs in ({"mode": "bicubic"}, {"padding_mode": "reflection"}):
        module = Fn(
            lambda x, g, k=kwargs: F.grid_sample(x, g, align_corners=False, **k)
        )
        assert _refusal_code(module, (GRID_IMG, GRID)) == "aten_arguments_not_supported"


def test_dilated_max_pooling_refuses_because_it_has_no_gradient_in_jax():
    module = Fn(lambda x: F.max_pool3d(x, 2, 1, 0, 2))
    assert _refusal_code(module, (VOL_DISTINCT,)) == "aten_arguments_not_supported"


# -- the allowlist ------------------------------------------------------------------------------

#: Emitted by branches of `_emit` that the earlier versions already had.
LEGACY_EMITTERS = {
    "aten.add.Scalar",
    "aten.sub.Scalar",
    "aten.div.Scalar",
    "aten.mean.default",
}
#: The 15 Core ATen ops the audit keeps refused, and the in-place batch norm.
AUDIT_REFUSED = {
    "aten._adaptive_avg_pool2d_backward.default",
    "aten.avg_pool2d_backward.default",
    "aten.convolution_backward.default",
    "aten.embedding_dense_backward.default",
    "aten.max_pool2d_with_indices_backward.default",
    "aten.native_group_norm_backward.default",
    "aten.native_layer_norm_backward.default",
    "aten.sym_numel.default",
    "aten.sym_size.int",
    "aten.sym_storage_offset.default",
    "aten.sym_stride.int",
    "aten.empty.memory_format",
    "aten.empty_strided.default",
    "aten.randperm.default",
    "aten.atan2.out",
}


def _entries(path):
    return json.loads(path.read_bytes())["aten_core"]


def test_v6_and_v7_are_untouched():
    assert allowlist_module.v7_bytes() == V7.read_bytes()
    assert allowlist_module.served_bytes() == (HERE / "allowlist_v6.json").read_bytes()


def test_v8_keeps_every_v7_aten_entry_unchanged():
    v7, v8 = _entries(V7), _entries(V8)
    for target, entry in v7.items():
        assert v8[target] == entry, target


def test_every_new_entry_is_emitted_or_refused_with_a_reason():
    v8 = _entries(V8)
    for target in sorted(V8_ONLY):
        entry = v8[target]
        assert entry["note"], target
        if entry["default"] == "allow":
            assert entry["lowering"] == "emitted", target
            assert (
                target in lower_torch._V8_LOWERINGS or target in LEGACY_EMITTERS
            ), target
        else:
            assert (
                entry["default"] == "refuse" and entry["lowering"] == "refused"
            ), target


def test_every_registered_emitter_has_an_allowing_entry():
    v8 = _entries(V8)
    for target in lower_torch._V8_LOWERINGS:
        assert v8[target]["default"] == "allow", target


def test_the_audit_refusals_are_recorded_with_their_reason():
    v8 = _entries(V8)
    for target in AUDIT_REFUSED | {"aten._native_batch_norm_legit.default"}:
        assert v8[target]["default"] == "refuse", target
        assert len(v8[target]["note"]) > 20, target
    assert "running statistics" in v8["aten._native_batch_norm_legit.default"]["note"]


class _Named:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


def test_the_refused_targets_refuse_in_lowering():
    allowlist = allowlist_module.load(V8)
    for target in sorted(AUDIT_REFUSED | {"aten._native_batch_norm_legit.default"}):
        builder = lower_torch._Builder(allowlist)
        fake = types.SimpleNamespace(target=_Named(target), args=(), kwargs={}, meta={})
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch._emit(builder, fake, {})
        assert refused.value.code == "aten_op_not_allowlisted", target


def test_v7_refuses_every_new_target():
    v7 = allowlist_module.load(V7)
    for target in sorted(V8_ONLY):
        assert target not in v7.aten, target


# -- narrow dtypes ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dtype, fn",
    [
        (torch.float16, lambda x: torch.erf(x) * 2 + 1),
        (torch.bfloat16, lambda x: x * 2 + 1),
        (torch.int8, lambda x: x * 2 + 1),
        (torch.int16, lambda x: (x << 1) + 3),
        (torch.uint8, lambda x: x + 3),
    ],
    ids=lambda v: str(v)[:20],
)
def test_narrow_dtypes_lower_only_under_v8(dtype, fn):
    x = (
        _ints(2, 3, low=0, high=20, seed=150).to(dtype)
        if not dtype.is_floating_point
        else (_randn(2, 3, seed=150)).to(dtype)
    )
    module = Fn(fn)
    doc, run, _ = _lowered(module, (x,), V8, raw=False)
    name = str(dtype).removeprefix("torch.")
    assert {
        o["dtype"] for g in doc["graphs"].values() for n in g["nodes"] for o in n["out"]
    } >= {name}
    arg = jax.numpy.asarray(x.float().numpy()).astype(name)
    got = np.asarray(run(arg)[0]).astype(np.float32)
    want = module(x).float().numpy()
    np.testing.assert_allclose(got, want, rtol=1e-2, atol=1e-2)
    again = np.asarray(run(arg)[0]).astype(np.float32)
    assert _bits(got) == _bits(again)
    # v7 keeps refusing them, also after a v8 lowering ran in the same process.
    assert _refusal_code(module, (x,), path=V7) == "dtype_not_allowed"


# -- v8 changes nothing for programs the earlier versions already lowered ---------------------------


class Mixed(torch.nn.Module):
    def __init__(self):
        super().__init__()
        torch.manual_seed(160)
        self.linear = torch.nn.Linear(4, 4)

    def forward(self, x):
        scattered = torch.zeros(3, 4).scatter_add(
            0, torch.tensor([[0, 1, 0, 2], [2, 2, 1, 0]]), x
        )
        pooled = torch.nn.functional.max_pool2d(self.linear(x).reshape(1, 1, 2, 4), 2)
        return (
            torch.softmax(torch.tanh(self.linear(x)), -1).sum()
            + scattered.sum()
            + pooled.sum()
        )


def test_programs_that_v7_lowered_lower_to_the_same_graph_under_v8():
    module = Mixed()
    example = (_randn(2, 4, seed=161),)
    old, _, _ = _lowered(module, example, V7)
    new, _, _ = _lowered(module, example, V8)
    assert old["graphs"] == new["graphs"]
    assert [n["op"] for n in new["graphs"]["main"]["nodes"]].count(
        "reduce_window_max"
    ) == 0
