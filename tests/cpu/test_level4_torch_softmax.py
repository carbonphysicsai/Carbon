"""Core ATen softmax lowers to inert, stable Carbon graph arithmetic."""

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
    # Test the prospective lowering without altering registered v4 material.
    document = json.loads(V4.read_text())
    document["version"] = "test-softmax-prospective"
    document["aten_core"]["aten._softmax.default"] = {
        "category": "reduction",
        "default": "allow",
        "lowering": "emitted",
    }
    return allowlist_module.Allowlist(json.dumps(document).encode())


def _program(dim, x):
    torch = pytest.importorskip("torch")

    class Softmax(torch.nn.Module):
        def forward(self, value):
            return torch.ops.aten._softmax.default(value, dim, False)

    module = Softmax()
    program = torch.export.export(module, (x,)).run_decompositions()
    assert [
        str(node.target) for node in program.graph.nodes if node.op == "call_function"
    ] == ["aten._softmax.default"]
    return torch, module, program


@pytest.mark.parametrize("dim", [0, 1, -1])
@pytest.mark.parametrize("extreme", [False, True])
def test_softmax_forward_and_gradient_match_torch(dim, extreme):
    jax = pytest.importorskip("jax")
    import numpy as np

    torch = pytest.importorskip("torch")
    values = np.linspace(-2.0, 2.0, 24, dtype=np.float32).reshape(2, 3, 4)
    if extreme:
        values = values * 1000.0 + 10000.0
    x = torch.from_numpy(values.copy())
    torch, module, program = _program(dim, x)
    allowlist = _test_allowlist()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    assert {n["op"] for n in doc["graphs"]["main"]["nodes"]} >= {
        "reduce_max",
        "reduce_sum",
        "exp",
        "div",
    }
    decoded = graph.parse(graph.dumps(doc), max_bytes=1 << 20)
    allowlist.check(decoded)
    rebuilt = interpret.rebuild(decoded, allowlist)
    got = rebuilt(jax.numpy.asarray(values))[0]
    with torch.no_grad():
        want = module(x)
    np.testing.assert_allclose(np.asarray(got), want.numpy(), rtol=2e-5, atol=2e-6)
    assert np.isfinite(np.asarray(got)).all()

    weights = np.linspace(0.1, 1.1, 24, dtype=np.float32).reshape(2, 3, 4)
    source = x.detach().clone().requires_grad_(True)
    ((module(source) * torch.from_numpy(weights)) ** 2).sum().backward()
    gradient = jax.grad(
        lambda value: jax.numpy.sum(
            (rebuilt(value)[0] * jax.numpy.asarray(weights)) ** 2
        )
    )(jax.numpy.asarray(values))
    np.testing.assert_allclose(
        np.asarray(gradient), source.grad.numpy(), rtol=3e-4, atol=3e-5
    )


def test_registered_v4_still_refuses_unregistered_softmax():
    torch = pytest.importorskip("torch")
    _, _, program = _program(-1, torch.randn(2, 3, 4))
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V4))
    assert refused.value.code == "aten_op_not_allowlisted"


@pytest.mark.parametrize(
    "arguments", [(3, False), (-4, False), (-1, True), (True, False)]
)
def test_prospective_softmax_refuses_unsupported_arguments(arguments):
    torch = pytest.importorskip("torch")
    _, _, program = _program(-1, torch.randn(2, 3, 4))
    node = next(
        node
        for node in program.graph.nodes
        if str(node.target) == "aten._softmax.default"
    )
    node.args = (node.args[0], *arguments)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_test_allowlist())
    assert refused.value.code == "aten_arguments_not_supported"
