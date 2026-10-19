"""Dimensioned Core ATen sum uses the existing inert reduction primitive."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

V4 = Path(allowlist_module.__file__).with_name("allowlist_v4.json")


def _test_allowlist():
    document = json.loads(V4.read_text())
    document["version"] = "test-sum-prospective"
    document["aten_core"]["aten.sum.dim_IntList"] = {
        "category": "reduction",
        "default": "allow",
        "lowering": "emitted",
    }
    return allowlist_module.Allowlist(json.dumps(document).encode())


def _program(dim, keepdim=False, dtype=None, x=None):
    torch = pytest.importorskip("torch")

    class Sum(torch.nn.Module):
        def forward(self, value):
            return torch.sum(value, dim=dim, keepdim=keepdim, dtype=dtype)

    module = Sum()
    if x is None:
        x = torch.linspace(-2.0, 3.0, 24).reshape(2, 3, 4)
    program = torch.export.export(module, (x,)).run_decompositions()
    assert [
        str(node.target) for node in program.graph.nodes if node.op == "call_function"
    ] == ["aten.sum.dim_IntList"]
    return torch, module, x, program


@pytest.mark.parametrize(
    ("dim", "keepdim"),
    [([2], False), ((0, -1), False), ([1], True), (None, False), ([], True)],
)
def test_sum_forward_and_gradient_match_torch(dim, keepdim):
    jax = pytest.importorskip("jax")
    import numpy as np

    torch, module, x, program = _program(dim, keepdim)
    allowlist = _test_allowlist()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    assert "reduce_sum" in {node["op"] for node in doc["graphs"]["main"]["nodes"]}
    rebuilt = interpret.rebuild(
        graph.parse(graph.dumps(doc), max_bytes=1 << 20), allowlist
    )
    got = rebuilt(jax.numpy.asarray(x.numpy()))[0]
    with torch.no_grad():
        want = module(x)
    np.testing.assert_allclose(np.asarray(got), want.numpy(), rtol=1e-6, atol=1e-6)

    weights = np.linspace(0.2, 1.2, want.numel(), dtype=np.float32).reshape(want.shape)
    source = x.detach().clone().requires_grad_(True)
    ((module(source) * torch.from_numpy(weights)) ** 2).sum().backward()
    gradient = jax.grad(
        lambda value: jax.numpy.sum(
            (rebuilt(value)[0] * jax.numpy.asarray(weights)) ** 2
        )
    )(jax.numpy.asarray(x.numpy()))
    np.testing.assert_allclose(
        np.asarray(gradient), source.grad.numpy(), rtol=1e-5, atol=1e-5
    )


@pytest.mark.parametrize(
    ("dim", "keepdim"),
    [([0], False), ([-1], True), (None, False), ([], True)],
)
def test_scalar_sum_retains_scalar_shape_and_gradient(dim, keepdim):
    jax = pytest.importorskip("jax")
    import numpy as np

    torch = pytest.importorskip("torch")
    _, module, x, program = _program(dim, keepdim, x=torch.tensor(2.25))
    allowlist = _test_allowlist()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    assert doc["graphs"]["main"]["nodes"] == []
    rebuilt = interpret.rebuild(doc, allowlist)
    got = rebuilt(jax.numpy.asarray(x.numpy()))[0]
    np.testing.assert_allclose(np.asarray(got), module(x).numpy())
    assert got.shape == ()
    source = x.detach().clone().requires_grad_(True)
    (module(source) ** 2).backward()
    gradient = jax.grad(lambda value: rebuilt(value)[0] ** 2)(
        jax.numpy.asarray(x.numpy())
    )
    np.testing.assert_allclose(np.asarray(gradient), source.grad.numpy())


@pytest.mark.parametrize("scalar", [False, True])
def test_explicit_float64_accumulation_matches_torch(scalar):
    jax = pytest.importorskip("jax")
    import numpy as np

    torch = pytest.importorskip("torch")
    x_input = torch.tensor(2.25) if scalar else None
    _, module, x, program = _program(
        [0] if scalar else [1], dtype=torch.float64, x=x_input
    )
    allowlist = _test_allowlist()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    assert "convert_element_type" in {
        node["op"] for node in doc["graphs"]["main"]["nodes"]
    }
    rebuilt = interpret.rebuild(doc, allowlist)
    with jax.enable_x64():
        got = rebuilt(jax.numpy.asarray(x.numpy()))[0]
    assert str(got.dtype) == "float64"
    np.testing.assert_allclose(
        np.asarray(got), module(x).numpy(), rtol=1e-12, atol=1e-12
    )


def test_registered_v4_still_refuses_unregistered_dim_sum():
    _, _, _, program = _program([2])
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V4))
    assert refused.value.code == "aten_op_not_allowlisted"


@pytest.mark.parametrize(
    ("dims", "keepdim", "dtype"),
    [
        ([3], False, None),
        ([-4], False, None),
        ([1, 1], False, None),
        ([1, -2], False, None),
        ([True], False, None),
        ([1], 1, None),
        ([1], False, "int32"),
    ],
)
def test_prospective_sum_refuses_unsupported_arguments(dims, keepdim, dtype):
    torch, _, _, program = _program([1])
    node = next(
        node
        for node in program.graph.nodes
        if str(node.target) == "aten.sum.dim_IntList"
    )
    node.args = (node.args[0], dims, keepdim)
    node.kwargs = {"dtype": getattr(torch, dtype)} if dtype else {}
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_test_allowlist())
    assert refused.value.code == "aten_arguments_not_supported"


def test_prospective_sum_refuses_wrong_result_metadata():
    torch, _, _, program = _program([1])
    node = next(
        node
        for node in program.graph.nodes
        if str(node.target) == "aten.sum.dim_IntList"
    )
    node.meta["val"] = torch.empty(2, 3)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_test_allowlist())
    assert refused.value.code == "aten_result_metadata_not_supported"
