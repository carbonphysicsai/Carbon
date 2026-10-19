"""Prospective static-index scatter-add lowering; no v5 contract change."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

V5 = Path(allowlist_module.__file__).with_name("allowlist_v5.json")


def _prospective():
    document = json.loads(V5.read_text())
    document["version"] = "test-scatter-add-static-prospective"
    document["aten_core"]["aten.scatter_add.default"] = {
        "category": "shape",
        "default": "allow",
        "lowering": "emitted",
        "note": "static int64 indices; ordered non-atomic expansion",
    }
    return allowlist_module.Allowlist(json.dumps(document).encode())


def _static_program():
    torch = pytest.importorskip("torch")

    class Scatter(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(
                torch.tensor([[0.5, -0.25, 1.0], [0.75, 0.125, -0.5]])
            )
            self.register_buffer(
                "index", torch.tensor([[2, 2, 0], [1, 1, 3]], dtype=torch.int64)
            )

        def forward(self, x):
            return x.scatter_add(1, self.index, self.weight)

    module = Scatter()
    x = torch.arange(8, dtype=torch.float32).reshape(2, 4) / 8
    program = torch.export.export(module, (x,)).run_decompositions()
    assert "aten.scatter_add.default" in lower_torch.inventory(program)
    return torch, module, x, program


def test_ordered_repeats_forward_gradient_and_source_free_state_parity():
    jax = pytest.importorskip("jax")
    import numpy as np

    _torch, module, x, program = _static_program()
    allowed = _prospective()
    doc, _ = lower_torch.lower(program, allowlist=allowed)
    assert any(entry["name"] == "params/0" for entry in doc["graphs"]["main"]["inputs"])
    assert any(
        entry["dtype"] == "int32" for entry in doc["graphs"]["main"]["constants"]
    )
    assert all(node["op"] != "scatter_add" for node in doc["graphs"]["main"]["nodes"])
    assert (
        graph.measure(doc)["nodes_executed"] <= allowlist_module.CAPS["nodes_executed"]
    )
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowed)

    def run(weight, base):
        values = {
            "params/0": weight,
            next(
                entry["name"]
                for entry in doc["graphs"]["main"]["inputs"]
                if entry["name"].startswith("inputs/")
            ): base,
        }
        return rebuilt(
            *(values[entry["name"]] for entry in doc["graphs"]["main"]["inputs"])
        )[0]

    weight = jax.numpy.asarray(module.weight.detach().numpy())
    base = jax.numpy.asarray(x.numpy())
    np.testing.assert_allclose(
        np.asarray(run(weight, base)),
        module(x).detach().numpy(),
        rtol=1e-6,
        atol=1e-6,
    )
    wanted_base = x.detach().clone().requires_grad_(True)
    (module(wanted_base) ** 2).sum().backward()
    got_weight, got_base = jax.grad(
        lambda w, b: jax.numpy.sum(run(w, b) ** 2), argnums=(0, 1)
    )(weight, base)
    np.testing.assert_allclose(
        np.asarray(got_weight), module.weight.grad.numpy(), rtol=1e-5, atol=1e-5
    )
    np.testing.assert_allclose(
        np.asarray(got_base), wanted_base.grad.numpy(), rtol=1e-5, atol=1e-5
    )


def test_pinned_v5_still_refuses_scatter_add():
    _, _, _, program = _static_program()
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V5))
    assert refused.value.code == "aten_op_not_allowlisted"


def test_input_derived_indices_refuse_until_runtime_bounds_have_a_trusted_path():
    torch = pytest.importorskip("torch")

    class Dynamic(torch.nn.Module):
        def forward(self, base, index, source):
            return base.scatter_add(1, index, source)

    base = torch.zeros((2, 4))
    index = torch.tensor([[2, 2, 0], [1, 1, 3]], dtype=torch.int64)
    source = torch.ones((2, 3))
    program = torch.export.export(Dynamic(), (base, index, source)).run_decompositions()
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_prospective())
    assert refused.value.code == "aten_scatter_index_not_static"


def test_static_out_of_bounds_and_registered_cost_refuse():
    _, _, _, program = _static_program()
    program.state_dict["index"][0, 0] = 4
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_prospective())
    assert refused.value.code == "aten_scatter_index_out_of_bounds"

    _, _, _, program = _static_program()
    original = allowlist_module.CAPS["nodes_executed"]
    allowlist_module.CAPS["nodes_executed"] = 1
    try:
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch.lower(program, allowlist=_prospective())
    finally:
        allowlist_module.CAPS["nodes_executed"] = original
    assert refused.value.code == "aten_scatter_registered_resource_bound"

    original = allowlist_module.CAPS["largest_intermediate_bytes"]
    allowlist_module.CAPS["largest_intermediate_bytes"] = 31
    try:
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch.lower(program, allowlist=_prospective())
    finally:
        allowlist_module.CAPS["largest_intermediate_bytes"] = original
    assert refused.value.code == "aten_scatter_registered_resource_bound"


def test_large_ordered_graph_uses_registered_single_intermediate_bound():
    torch = pytest.importorskip("torch")

    class Wide(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("index", torch.arange(256, dtype=torch.int64) // 2)

        def forward(self, base, source):
            return base.scatter_add(0, self.index, source)

    program = torch.export.export(
        Wide(), (torch.zeros(65536), torch.ones(256))
    ).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=_prospective())
    measured = graph.measure(doc)
    assert measured["nodes_executed"] == 2 + 7 * 256
    assert measured["largest_intermediate_bytes"] == 65536 * 4
    assert all(
        verdict == "pass" for verdict in allowlist_module.check_caps(measured).values()
    )


@pytest.mark.parametrize("case", ["dimension", "index_dtype", "source_shape"])
def test_static_scatter_refuses_invalid_dimension_dtype_or_shape(case):
    torch, _, _, program = _static_program()
    node = next(
        item
        for item in program.graph.nodes
        if str(item.target) == "aten.scatter_add.default"
    )
    if case == "dimension":
        node.args = (node.args[0], 3, node.args[2], node.args[3])
    elif case == "index_dtype":
        program.state_dict["index"] = program.state_dict["index"].to(torch.int32)
        node.args[2].meta["val"] = torch.empty((2, 3), dtype=torch.int32)
    else:
        node.args[3].meta["val"] = torch.empty((2, 2), dtype=torch.float32)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_prospective())
    assert refused.value.code == "aten_scatter_shape_or_dtype_not_supported"
