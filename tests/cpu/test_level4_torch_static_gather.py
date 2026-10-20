"""Graph networks in the prospective v6 allowlist: a static gather
(`aten.index.Tensor` on a captured index), `zeros_like` (`aten.full_like`), and
v6's static scatter reached through a broadcast index. v5 stays refused.

A gather lowers to slices of consecutive index runs and one concatenate, never
a gather primitive, so neither inference nor a rebuild's gradient needs a
nondeterministic scatter.
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


def _export(module, *example):
    return torch.export.export(module, example).run_decompositions()


def _run(doc, allowlist, values):
    """The rebuilt graph on `values` (by input name), first output."""
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowlist)
    entry = doc["graphs"][doc["entry"]]
    return rebuilt(*(values[i["name"]] for i in entry["inputs"]))[0]


class Gather(torch.nn.Module):
    def __init__(self, index):
        super().__init__()
        self.register_buffer("idx", torch.tensor(index, dtype=torch.int64))

    def forward(self, x):
        return x[:, self.idx] * 2.0


def _ops(doc):
    return [n["op"] for n in doc["graphs"][doc["entry"]]["nodes"]]


def test_v5_still_refuses_a_gather():
    program = _export(Gather([0, 1]), torch.ones(2, 5, 3))
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V5))
    assert refused.value.code == "aten_op_not_allowlisted"


def test_a_static_gather_with_repeats_and_negative_indices_matches_torch():
    jax = pytest.importorskip("jax")
    import numpy as np

    module = Gather([3, 0, 0, -1, 1, 2])
    x = torch.arange(30, dtype=torch.float32).reshape(2, 5, 3) / 7
    doc, _ = lower_torch.lower(_export(module, x), allowlist=allowlist_module.load(V6))
    assert "gather" not in _ops(doc)
    name = next(i["name"] for i in doc["graphs"]["main"]["inputs"])
    got = _run(doc, allowlist_module.load(V6), {name: jax.numpy.asarray(x.numpy())})
    np.testing.assert_array_equal(np.asarray(got), module(x).numpy())


def test_consecutive_index_runs_lower_to_one_slice_each():
    module = Gather(list(range(10)) + list(range(1, 11)))
    doc, _ = lower_torch.lower(
        _export(module, torch.ones(2, 12, 3)), allowlist=allowlist_module.load(V6)
    )
    assert _ops(doc).count("slice") == 2 and _ops(doc).count("concatenate") == 1


def test_an_input_derived_or_out_of_bounds_index_refuses():
    class FromInput(torch.nn.Module):
        def forward(self, x, idx):
            return x[:, idx]

    program = _export(FromInput(), torch.ones(2, 5, 3), torch.tensor([0, 1]))
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V6))
    assert refused.value.code == "aten_index_not_static"

    program = _export(Gather([0, 1]), torch.ones(2, 5, 3))
    program.state_dict["idx"][1] = 5
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V6))
    assert refused.value.code == "aten_index_out_of_bounds"


class ChainGNN(torch.nn.Module):
    """One message-passing layer on a fixed chain graph, as graph libraries do it."""

    def __init__(self, points=6, hidden=4):
        super().__init__()
        src = list(range(points - 1)) + list(range(1, points))
        dst = list(range(1, points)) + list(range(points - 1))
        self.register_buffer("src", torch.tensor(src, dtype=torch.int64))
        self.register_buffer("dst", torch.tensor(dst, dtype=torch.int64))
        torch.manual_seed(0)
        self.message = torch.nn.Linear(2 * hidden, hidden)

    def forward(self, h):
        m = torch.tanh(self.message(torch.cat([h[:, self.src], h[:, self.dst]], dim=2)))
        index = self.dst.view(1, -1, 1).expand(h.shape[0], -1, h.shape[2])
        return torch.zeros_like(h).scatter_add(1, index, m)


def test_a_chain_graph_network_lowers_under_v6_and_matches_torch():
    jax = pytest.importorskip("jax")
    import numpy as np

    module = ChainGNN()
    h = torch.arange(2 * 6 * 4, dtype=torch.float32).reshape(2, 6, 4) / 48
    program = _export(module, h)
    with pytest.raises(graph.GraphRefused):
        lower_torch.lower(program, allowlist=allowlist_module.load(V5))
    v6 = allowlist_module.load(V6)
    doc, _ = lower_torch.lower(program, allowlist=v6)
    assert not {"gather", "scatter_add"} & set(_ops(doc))
    measured = graph.measure(doc)
    assert all(v == "pass" for v in allowlist_module.check_caps(measured).values())
    entry = doc["graphs"]["main"]["inputs"]
    values = {}
    params = dict(module.named_parameters())
    for item in entry:
        name = item["name"]
        if name.startswith("params/"):
            # Lowering names parameters in the program's order.
            key = list(params)[int(name.split("/")[1])]
            values[name] = jax.numpy.asarray(params[key].detach().numpy())
        else:
            values[name] = jax.numpy.asarray(h.numpy())
    got = _run(doc, v6, values)
    np.testing.assert_allclose(
        np.asarray(got), module(h).detach().numpy(), rtol=1e-6, atol=1e-6
    )


def test_the_miner_s_tensor_and_carbon_s_unrolling_are_refused_apart():
    program = _export(Gather([3, 0, 0, -1, 1, 2]), torch.ones(2, 5, 3))
    original = dict(allowlist_module.CAPS)
    try:
        allowlist_module.CAPS["largest_intermediate_bytes"] = 8
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch.lower(program, allowlist=allowlist_module.load(V6))
        assert refused.value.code == "aten_index_registered_resource_bound"
        allowlist_module.CAPS.update(original)
        allowlist_module.CAPS["nodes_executed"] = 1
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch.lower(program, allowlist=allowlist_module.load(V6))
        assert refused.value.code == "aten_index_lowering_expansion_bound"
    finally:
        allowlist_module.CAPS.clear()
        allowlist_module.CAPS.update(original)
