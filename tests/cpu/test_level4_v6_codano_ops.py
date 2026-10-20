"""CODANO's ops in the prospective v6 allowlist (Validator, 2026-10-20): floor,
fmod and index_select. fmod is C-style (the result takes the dividend's sign)
and lowers to Carbon's rem; Python-style aten.remainder is never mapped onto
it and stays refused. Values and gradients match torch, with negative
operands, exact integers, a zero divisor (NaN in both) and large magnitudes;
floor's gradient is 0 everywhere and rem's is d/dx = 1, d/dy = -trunc(x / y).
index_select is the static take of aten.index.Tensor: bounds-checked, never a
gather primitive. v5 refuses all of them.
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
np = pytest.importorskip("numpy")


def _rebuilt(module, example, path=V6):
    allowlist = allowlist_module.load(path)
    program = torch.export.export(module, example).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    return doc, interpret.rebuild(parsed, allowlist)


def _ops(doc):
    # Every graph's nodes: JAX's jnp functions lower inside a nested `jit` call.
    return [n["op"] for g in doc["graphs"].values() for n in g["nodes"]]


class Fmod(torch.nn.Module):
    def forward(self, x, y):
        return torch.fmod(x, y)


class FmodScalar(torch.nn.Module):
    def __init__(self, divisor):
        super().__init__()
        self.divisor = divisor

    def forward(self, x):
        return torch.fmod(x, self.divisor)


class Remainder(torch.nn.Module):
    def forward(self, x, y):
        return torch.remainder(x, y)


class Floor(torch.nn.Module):
    def forward(self, x):
        return torch.floor(x) * 1.5 + x


class IndexSelect(torch.nn.Module):
    def __init__(self, index, dim):
        super().__init__()
        self.register_buffer("index", torch.tensor(index, dtype=torch.int64))
        self.dim = dim

    def forward(self, x):
        return torch.index_select(x, self.dim, self.index) * 2.0


class IndexSelectInput(torch.nn.Module):
    def forward(self, x, index):
        return torch.index_select(x, 0, index)


def _operands():
    # Negative operands, exact integers, a fractional mix and large magnitudes.
    x = torch.tensor(
        [7.0, -7.0, 7.0, -7.0, 5.5, -5.5, 9.0, -9.0, 1.0e7 + 3.0, -2.5e6, 0.0, 3.25],
        dtype=torch.float32,
    )
    y = torch.tensor(
        [3.0, 3.0, -3.0, -3.0, 2.0, -2.0, 4.5, 4.5, 3.3, 7.0, 2.0, -0.5],
        dtype=torch.float32,
    )
    return x, y


def test_v5_refuses_floor_fmod_and_index_select():
    x, y = _operands()
    for module, example in (
        (Fmod(), (x, y)),
        (FmodScalar(3.0), (x,)),
        (Floor(), (x,)),
        (IndexSelect([2, 0], 0), (x,)),
    ):
        with pytest.raises(graph.GraphRefused) as refused:
            _rebuilt(module, example, V5)
        assert refused.value.code == "aten_op_not_allowlisted"


def test_fmod_is_c_style_rem_and_matches_torch_values_and_gradients():
    x, y = _operands()
    doc, rebuilt = _rebuilt(Fmod(), (x, y))
    assert "rem" in _ops(doc)
    xj, yj = jax.numpy.asarray(x.numpy()), jax.numpy.asarray(y.numpy())
    got = np.asarray(rebuilt(xj, yj)[0])
    want = torch.fmod(x, y).numpy()
    np.testing.assert_array_equal(got, want)
    # C-style: a nonzero result takes the dividend's sign.
    nonzero = want != 0
    assert (np.sign(got[nonzero]) == np.sign(x.numpy()[nonzero])).all()
    gx, gy = jax.grad(lambda a, b: rebuilt(a, b)[0].sum(), argnums=(0, 1))(xj, yj)
    tx, ty = x.clone().requires_grad_(True), y.clone().requires_grad_(True)
    torch.fmod(tx, ty).sum().backward()
    np.testing.assert_array_equal(np.asarray(gx), tx.grad.numpy())
    np.testing.assert_array_equal(np.asarray(gy), ty.grad.numpy())
    np.testing.assert_array_equal(np.asarray(gx), np.ones_like(want))
    np.testing.assert_array_equal(np.asarray(gy), -np.trunc(x.numpy() / y.numpy()))


@pytest.mark.parametrize("divisor", [3.0, -2.5])
def test_fmod_by_a_scalar_matches_torch(divisor):
    x, _ = _operands()
    doc, rebuilt = _rebuilt(FmodScalar(divisor), (x,))
    assert "rem" in _ops(doc)
    got = np.asarray(rebuilt(jax.numpy.asarray(x.numpy()))[0])
    np.testing.assert_array_equal(got, torch.fmod(x, divisor).numpy())


def test_a_zero_divisor_is_nan_in_both():
    x = torch.tensor([1.0, -2.0, 0.0, 5.0])
    y = torch.tensor([0.0, 0.0, 0.0, 2.0])
    _, rebuilt = _rebuilt(Fmod(), (x, y))
    got = np.asarray(
        rebuilt(jax.numpy.asarray(x.numpy()), jax.numpy.asarray(y.numpy()))[0]
    )
    want = torch.fmod(x, y).numpy()
    np.testing.assert_array_equal(np.isnan(got), np.isnan(want))
    assert np.isnan(got[:3]).all() and got[3] == want[3]


def test_python_style_remainder_is_never_mapped_onto_rem():
    x, y = _operands()
    with pytest.raises(graph.GraphRefused) as refused:
        _rebuilt(Remainder(), (x, y))
    assert refused.value.code == "aten_op_not_allowlisted"
    assert "remainder" in str(refused.value)


def test_floor_matches_torch_and_its_gradient_is_zero():
    x, _ = _operands()
    x = torch.cat([x, torch.tensor([-0.5, 0.5, -1.0, 2.0])])
    doc, rebuilt = _rebuilt(Floor(), (x,))
    assert "floor" in _ops(doc)
    xj = jax.numpy.asarray(x.numpy())
    np.testing.assert_array_equal(np.asarray(rebuilt(xj)[0]), Floor()(x).numpy())
    # d/dx (1.5 floor(x) + x) = 1: floor contributes 0 everywhere, as in torch.
    grad = jax.grad(lambda v: rebuilt(v)[0].sum())(xj)
    want = x.clone().requires_grad_(True)
    Floor()(want).sum().backward()
    np.testing.assert_array_equal(np.asarray(grad), want.grad.numpy())
    np.testing.assert_array_equal(np.asarray(grad), np.ones(x.shape, np.float32))


def test_floor_and_fmod_refuse_integer_operands():
    i = torch.tensor([7, -7, 3], dtype=torch.int64)
    for module, example in ((Floor(), (i,)), (FmodScalar(2), (i,))):
        with pytest.raises(graph.GraphRefused):
            _rebuilt(module, example)


@pytest.mark.parametrize(
    "index, dim", [([2, 0, 0, 3], 0), ([1, 2, 3], 1), ([3, 1], -1)]
)
def test_index_select_is_a_static_take_matching_torch_values_and_gradient(index, dim):
    x = torch.randn(4, 5, generator=torch.Generator().manual_seed(11))
    module = IndexSelect(index, dim)
    doc, rebuilt = _rebuilt(module, (x,))
    ops = _ops(doc)
    assert "gather" not in ops and "scatter-add" not in ops and "slice" in ops
    xj = jax.numpy.asarray(x.numpy())
    np.testing.assert_array_equal(np.asarray(rebuilt(xj)[0]), module(x).numpy())
    grad = jax.grad(lambda v: rebuilt(v)[0].sum())(xj)
    want = x.clone().requires_grad_(True)
    module(want).sum().backward()
    np.testing.assert_array_equal(np.asarray(grad), want.grad.numpy())


def test_index_select_out_of_bounds_and_input_indices_refuse():
    x = torch.randn(4, 5)
    with pytest.raises(graph.GraphRefused) as refused:
        _rebuilt(IndexSelect([1, 4], 0), (x,))
    assert refused.value.code == "aten_index_out_of_bounds"
    # torch refuses a negative index_select index (x[index] would wrap it).
    with pytest.raises(IndexError):
        torch.index_select(x, 0, torch.tensor([-1]))
    with pytest.raises(graph.GraphRefused) as refused:
        _rebuilt(IndexSelect([0, -1], 0), (x,))
    assert refused.value.code == "aten_index_out_of_bounds"
    with pytest.raises(graph.GraphRefused) as refused:
        _rebuilt(IndexSelectInput(), (x, torch.tensor([0, 2])))
    assert refused.value.code == "aten_index_not_static"


def test_jax_fmod_and_floor_lower_as_rem_and_floor_and_match_torch():
    from carbon.level4.tooling import through_bprime

    x, y = _operands()
    registry = allowlist_module.load(V6)
    rebuilt, doc, _ = through_bprime(
        lambda a, b: jax.numpy.fmod(a, b) + jax.numpy.floor(a),
        (jax.numpy.asarray(x.numpy()), jax.numpy.asarray(y.numpy())),
        role="forward",
        allowlist=registry,
        input_names=["inputs/x", "inputs/y"],
        max_bytes=allowlist_module.CAPS["document_bytes"],
    )
    ops = _ops(doc)
    assert "rem" in ops and "floor" in ops
    got = np.asarray(
        rebuilt(jax.numpy.asarray(x.numpy()), jax.numpy.asarray(y.numpy()))[0]
    )
    np.testing.assert_array_equal(got, (torch.fmod(x, y) + torch.floor(x)).numpy())
