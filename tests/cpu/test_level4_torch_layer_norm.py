"""Core ATen layer norm remains reconstructible without a Torch runtime."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

V3 = Path(allowlist_module.__file__).with_name("allowlist_v3.json")
V4 = Path(allowlist_module.__file__).with_name("allowlist_v4.json")


def _program(*, affine: bool, epsilon: float = 1e-5):
    torch = pytest.importorskip("torch")

    class LayerNormTriple(torch.nn.Module):
        def __init__(self):
            super().__init__()
            if affine:
                self.weight = torch.nn.Parameter(
                    torch.linspace(0.5, 1.5, 12).reshape(3, 4)
                )
                self.bias = torch.nn.Parameter(
                    torch.linspace(-0.5, 0.5, 12).reshape(3, 4)
                )
            else:
                self.weight = None
                self.bias = None

        def forward(self, x):
            return torch.ops.aten.native_layer_norm.default(
                x, [3, 4], self.weight, self.bias, epsilon
            )

    module = LayerNormTriple().eval()
    x = torch.arange(120, dtype=torch.float32).reshape(2, 5, 3, 4) / 17
    program = torch.export.export(module, (x,)).run_decompositions()
    return torch, module, x, program


@pytest.mark.parametrize("affine", [False, True])
def test_native_layer_norm_all_outputs_match_torch_and_rebuild_without_torch(affine):
    jax = pytest.importorskip("jax")
    import numpy as np

    torch, module, x, program = _program(affine=affine)
    allowlist = allowlist_module.load(V4)
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    assert doc["allowlist"] == "level4-allowlist-v4"
    assert len(doc["graphs"]["main"]["outputs"]) == 3
    assert {n["op"] for n in doc["graphs"]["main"]["nodes"]} >= {
        "reduce_sum",
        "rsqrt",
        "integer_pow",
        "reshape",
    }
    assert all(n["op"] != "native_layer_norm" for n in doc["graphs"]["main"]["nodes"])
    decoded = graph.parse(graph.dumps(doc), max_bytes=1 << 20)
    rebuilt = interpret.rebuild(decoded, allowlist)
    values = {"inputs/x": x.numpy()}
    if affine:
        values.update(
            {
                "params/0": module.weight.detach().numpy(),
                "params/1": module.bias.detach().numpy(),
            }
        )
    args = [
        jax.numpy.asarray(values[item["name"]])
        for item in doc["graphs"]["main"]["inputs"]
    ]
    got = rebuilt(*args)
    with torch.no_grad():
        want = module(x)
    for actual, expected in zip(got, want):
        np.testing.assert_allclose(
            np.asarray(actual), expected.numpy(), rtol=2e-5, atol=2e-6
        )
    assert [list(v.shape) for v in got] == [[2, 5, 3, 4], [2, 5, 1, 1], [2, 5, 1, 1]]

    # Construction trains this graph: its differentiable normalization and
    # affine inputs must remain usable, not merely match one inference pass.
    x_grad = x.detach().clone().requires_grad_(True)
    torch_output, torch_mean, torch_rstd = module(x_grad)
    assert not torch_mean.requires_grad and not torch_rstd.requires_grad
    coefficient = torch.linspace(0.1, 1.1, torch_output.numel()).reshape(
        torch_output.shape
    )
    (
        ((torch_output * coefficient) ** 2).sum()
        + 7.0 * torch_mean.sum()
        + 11.0 * torch_rstd.sum()
    ).backward()
    weights = jax.numpy.asarray(coefficient.numpy())

    def loss(*inputs):
        output, mean, rstd = rebuilt(*inputs)
        return (
            jax.numpy.sum((output * weights) ** 2)
            + 7.0 * jax.numpy.sum(mean)
            + 11.0 * jax.numpy.sum(rstd)
        )

    gradients = jax.grad(loss, argnums=tuple(range(len(args))))(*args)
    expected_gradients = {"inputs/x": x_grad.grad.numpy()}
    if affine:
        expected_gradients.update(
            {
                "params/0": module.weight.grad.numpy(),
                "params/1": module.bias.grad.numpy(),
            }
        )
    for entry, actual in zip(doc["graphs"]["main"]["inputs"], gradients):
        np.testing.assert_allclose(
            np.asarray(actual),
            expected_gradients[entry["name"]],
            rtol=2e-4,
            atol=2e-5,
        )


def test_v3_refuses_native_layer_norm_without_reinterpreting_history():
    _, _, _, program = _program(affine=True)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V3))
    assert refused.value.code == "aten_op_not_allowlisted"


def test_pytorch_layer_norm_module_one_axis_export_matches():
    torch = pytest.importorskip("torch")
    jax = pytest.importorskip("jax")
    import numpy as np

    module = torch.nn.LayerNorm(4).eval()
    with torch.no_grad():
        module.weight.copy_(torch.linspace(0.5, 1.5, 4))
        module.bias.copy_(torch.linspace(-0.5, 0.5, 4))
    x = torch.arange(24, dtype=torch.float32).reshape(2, 3, 4) / 7
    program = torch.export.export(module, (x,)).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=allowlist_module.load(V4))
    assert len(doc["graphs"]["main"]["outputs"]) == 1
    values = {
        "params/0": module.weight.detach().numpy(),
        "params/1": module.bias.detach().numpy(),
        "inputs/input": x.numpy(),
    }
    args = [
        jax.numpy.asarray(values[entry["name"]])
        for entry in doc["graphs"]["main"]["inputs"]
    ]
    actual = interpret.rebuild(doc, allowlist_module.load(V4))(*args)[0]
    with torch.no_grad():
        expected = module(x).numpy()
    np.testing.assert_allclose(np.asarray(actual), expected, rtol=2e-5, atol=2e-6)


@pytest.mark.parametrize("replacement", [[2, 4], [3, 0], []])
def test_v4_refuses_invalid_normalized_axes(replacement):
    _, _, _, program = _program(affine=True)
    norm = next(
        n
        for n in program.graph.nodes
        if str(n.target) == "aten.native_layer_norm.default"
    )
    norm.args = (norm.args[0], replacement, *norm.args[2:])
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V4))
    assert refused.value.code == "aten_arguments_not_supported"


@pytest.mark.parametrize("epsilon", [float("nan"), float("inf"), -1e-5])
def test_v4_refuses_invalid_epsilon(epsilon):
    _, _, _, program = _program(affine=False)
    norm = next(
        n
        for n in program.graph.nodes
        if str(n.target) == "aten.native_layer_norm.default"
    )
    norm.args = (*norm.args[:4], epsilon)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V4))
    assert refused.value.code == "aten_arguments_not_supported"


def test_v4_refuses_invalid_tuple_index():
    _, _, _, program = _program(affine=False)
    selected = next(
        n for n in program.graph.nodes if str(n.target) == "<built-in function getitem>"
    )
    selected.args = (selected.args[0], 3)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V4))
    assert refused.value.code == "aten_tuple_index_not_supported"
