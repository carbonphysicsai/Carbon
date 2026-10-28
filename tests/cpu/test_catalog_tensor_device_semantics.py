"""Real tensor semantics of the admitted catalog helper, on CPU and CUDA.

Synthetic integer-valued features need no scientific tolerance. CUDA is a
required device when CARBON_REQUIRE_CUDA=1; CPU fallback cannot pass that run.
"""

from __future__ import annotations

import ast
import os
import tarfile
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.backbone_catalog import gpu_build, pipeline
from carbon.backbone_catalog.gpu_tensor_placement import rewrite

if os.environ.get("CARBON_REQUIRE_CUDA") == "1":
    import torch
else:
    torch = pytest.importorskip("torch")


def _functions(catalog_id):
    path = pipeline.BUNDLES / catalog_id / "source.tar.gz"
    with tarfile.open(path) as archive:
        (member,) = [m for m in archive.getmembers() if m.name.endswith(gpu_build.BACKBONES_MEMBER)]
        source = archive.extractfile(member).read()
    transformed = rewrite(source)
    assert transformed is not None
    tree = ast.parse(transformed)
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in (
            "_torch_scatter_standin", "_constant_graph_helpers"
        ):
            functions.extend(
                child for child in node.body
                if isinstance(child, ast.FunctionDef)
                and child.name in ("scatter", "concat_efeat", "aggregate_and_concat")
            )
    assert {node.name for node in functions} == {"scatter", "concat_efeat", "aggregate_and_concat"}
    namespace = {"torch": torch, "np": np}
    # Execute only these source-owned helper definitions, with real tensors;
    # no library imports, model construction or scientific grading is mocked.
    exec(compile(ast.Module(body=functions, type_ignores=[]), "catalog-device-helpers", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("catalog_id", [
    "physicsnemo.MeshGraphNet",
    "v2.motor.physicsnemo.MeshGraphNet",
    "v2.cooling.physicsnemo.MeshGraphNet",
    "v2.f08.physicsnemo.MeshGraphNet",
    "v2.f02.physicsnemo.MeshGraphNet",
    "neuralop.LocalNO",
])
@pytest.mark.parametrize("device", ["cpu", "cuda"])
@pytest.mark.parametrize("dtype_name", ["float32", "float64"])
@pytest.mark.parametrize("nodes", [3, 5])
def test_scatter_gather_and_aggregation_follow_tensor_device(catalog_id, device, dtype_name, nodes):
    if device == "cuda" and not torch.cuda.is_available():
        if os.environ.get("CARBON_REQUIRE_CUDA") == "1":
            pytest.fail("CUDA tensor semantics required; CPU fallback is not evidence")
        pytest.skip("CUDA unavailable; CPU tensor semantics are covered separately")
    dtype = getattr(torch, dtype_name)
    functions = _functions(catalog_id)
    cases, width = 2, 2
    src = np.concatenate((np.arange(nodes - 1), np.arange(1, nodes)))
    dst = np.concatenate((np.arange(1, nodes), np.arange(nodes - 1)))
    edges = len(dst)
    graph = SimpleNamespace(
        cases=cases,
        nodes_per_case=nodes,
        dst_local=dst,
        src_np=np.concatenate([src + case * nodes for case in range(cases)]),
        dst_np=np.concatenate([dst + case * nodes for case in range(cases)]),
    )
    edge_values = np.arange(cases * edges * width).reshape(cases * edges, width)
    node_values = np.arange(cases * nodes * width).reshape(cases * nodes, width)
    efeat = torch.tensor(edge_values, device=device, dtype=dtype)
    nfeat = torch.tensor(node_values, device=device, dtype=dtype)
    indices = torch.tensor(graph.dst_np, device=device, dtype=torch.int64)
    expected_concat = np.concatenate((edge_values, node_values[graph.src_np], node_values[graph.dst_np]), axis=1)
    concatenated = functions["concat_efeat"](efeat, nfeat, graph)
    assert concatenated.device == efeat.device
    assert concatenated.dtype == dtype
    assert tuple(concatenated.shape) == expected_concat.shape
    assert np.array_equal(concatenated.cpu().numpy(), expected_concat)
    for reduction in ("sum", "mean"):
        expected = np.zeros((cases * nodes, width), dtype=np.float64)
        counts = np.zeros(cases * nodes, dtype=np.int64)
        for edge, destination in enumerate(graph.dst_np):
            expected[destination] += edge_values[edge]
            counts[destination] += 1
        if reduction == "mean":
            expected /= counts[:, None]
        scattered = functions["scatter"](
            efeat, indices, dim_size=cases * nodes, reduce=reduction
        )
        aggregated = functions["aggregate_and_concat"](efeat, nfeat, graph, reduction)
        for actual, reference in (
            (scattered, expected),
            (aggregated, np.concatenate((expected, node_values), axis=1)),
        ):
            assert actual.device == efeat.device
            assert actual.dtype == dtype
            assert tuple(actual.shape) == reference.shape
            assert np.array_equal(actual.cpu().numpy(), reference)
