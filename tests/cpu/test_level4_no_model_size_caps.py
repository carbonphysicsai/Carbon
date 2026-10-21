"""No model-size caps from allowlist v7 (owner, 2026-10-21: "No cap. Only cap
should be if it fits the training resource limit"; Validator,
VALIDATOR_NO_MODEL_SIZE_CAP_SPEC_20261021).

Claims tested:
- v7 is measured only against the constants cap (kept: it enforces
  from-scratch) and two containment bounds (64 MiB documents, call depth
  256); v1-v6 keep the owner's caps unchanged, and an unknown version gets
  them too.
- A 20,000-node graph is admitted under v7 and refused under v6.
- A constant over 16 KiB is still refused under v7.
- A document over 64 MiB and a call depth over 256 are refused as
  containment; the depth guard is typed, not a RecursionError.
- The lowering tooling's pre-checks follow the same caps.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, validate

HERE = Path(allowlist_module.__file__).parent
V6 = allowlist_module.load(HERE / "allowlist_v6.json")
V7 = allowlist_module.load(HERE / "allowlist_v7.json")
OWNER_CAPS = {
    "constant_bytes": 16 * 1024,
    "nodes_executed": 4096,
    "call_depth": 16,
    "document_bytes": 1024**2,
    "largest_intermediate_bytes": 256 * 1024**2,
}


def _chain(allowlist, length, *, constant_values=0):
    """A forward graph of ``length`` neg nodes on one (5, 3) input, plus an
    optional float32 constant of ``constant_values`` values added at the end."""
    import numpy as np

    shape = [5, 3]
    nodes, value = [], 0
    constants = []
    for i in range(length):
        nodes.append(
            {
                "op": "neg",
                "in": [value],
                "out": [{"value": i + 1, "dtype": "float32", "shape": shape}],
                "params": {},
            }
        )
        value = i + 1
    if constant_values:
        # Distinct values, so the constants cap counts every one.
        values = np.arange(constant_values, dtype=np.float32)
        constants.append({"value": value + 1, **graph.encode_array(values)})
    return {
        "schema": graph.SCHEMA,
        "allowlist": allowlist.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {"value": 0, "name": "inputs/x", "dtype": "float32", "shape": shape}
                ],
                "constants": constants,
                "nodes": nodes,
                "outputs": [value],
            }
        },
    }


def test_v7_has_only_the_constants_cap_and_containment():
    caps = allowlist_module.caps_for(V7)
    assert caps == {
        "constant_bytes": 16 * 1024,
        "document_bytes": 64 * 1024**2,
        "call_depth": 256,
    }
    assert "nodes_executed" not in caps and "largest_intermediate_bytes" not in caps


@pytest.mark.parametrize("version", [f"level4-allowlist-v{i}" for i in range(1, 7)])
def test_earlier_versions_keep_the_owners_caps(version):
    assert allowlist_module.caps_for(version) == OWNER_CAPS
    assert allowlist_module.CAPS == OWNER_CAPS


def test_an_unknown_version_keeps_the_owners_caps():
    assert allowlist_module.caps_for("level4-allowlist-v99") == OWNER_CAPS
    assert allowlist_module.caps_for(None) == OWNER_CAPS


def test_a_20000_node_graph_is_admitted_under_v7_and_refused_under_v6():
    doc = _chain(V7, 20_000)
    assert graph.measure(doc)["nodes_executed"] == 20_000
    assert validate.validate(doc, V7, role="forward")["status"] == "admitted"
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(_chain(V6, 20_000), V6, role="forward")
    assert refused.value.code == "cap_exceeded"
    assert "nodes_executed" in refused.value.where


def test_a_large_constant_is_still_refused_under_v7():
    # 16 KiB / VALUE_BYTES distinct values pass; one more refuses.
    limit = allowlist_module.CAPS["constant_bytes"] // graph.VALUE_BYTES
    within = _chain(V7, 3, constant_values=limit)
    assert graph.measure(within)["constant_value_bytes"] <= 16 * 1024
    assert allowlist_module.check_caps(
        graph.measure(within), allowlist_module.caps_for(V7)
    )["constant_bytes"] == ("pass")
    over = _chain(V7, 3, constant_values=limit + 1)
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(over, V7, role="forward")
    assert refused.value.code == "cap_exceeded"
    assert "constant_bytes" in refused.value.where


def test_a_document_over_64_mib_is_refused_as_containment():
    caps = allowlist_module.caps_for(V7)
    measured = {**graph.measure(_chain(V7, 1)), "document_bytes": 64 * 1024**2 + 1}
    assert allowlist_module.check_caps(measured, caps)["document_bytes"] == "refuse"
    measured["document_bytes"] = 64 * 1024**2
    assert allowlist_module.check_caps(measured, caps)["document_bytes"] == "pass"
    # Under v6 the owner's 1 MiB document cap is unchanged.
    measured["document_bytes"] = 1024**2 + 1
    assert (
        allowlist_module.check_caps(measured, allowlist_module.caps_for(V6))[
            "document_bytes"
        ]
        == "refuse"
    )


def _nested(depth):
    """A document whose entry calls a chain of ``depth - 1`` nested graphs."""
    graphs = {}
    for level in range(depth):
        name = f"g{level}"
        inner = f"g{level + 1}" if level + 1 < depth else None
        nodes = (
            [
                {
                    "op": "closed_call",
                    "in": [0],
                    "out": [{"value": 1, "dtype": "float32", "shape": [2]}],
                    "params": {"call_jaxpr": {"graph": inner}},
                }
            ]
            if inner
            else []
        )
        graphs[name] = {
            "inputs": [
                {"value": 0, "name": "inputs/x", "dtype": "float32", "shape": [2]}
            ],
            "constants": [],
            "nodes": nodes,
            "outputs": [1 if inner else 0],
        }
    return {
        "schema": graph.SCHEMA,
        "allowlist": V7.version,
        "role": "forward",
        "entry": "g0",
        "graphs": graphs,
    }


def test_a_call_depth_over_256_is_refused_as_containment():
    graph.check_structure(_nested(256))
    assert graph.call_depth(_nested(256)) == 256
    with pytest.raises(graph.GraphRefused) as refused:
        graph.check_structure(_nested(257))
    assert refused.value.code == "graph_call_depth_containment"
    # Far past Python's own recursion limit: still a typed refusal.
    with pytest.raises(graph.GraphRefused) as refused:
        graph.check_structure(_nested(5000))
    assert refused.value.code == "graph_call_depth_containment"


def test_v6_still_refuses_a_call_depth_over_16():
    measured = {**graph.measure(_chain(V6, 1)), "call_depth": 17}
    assert (
        allowlist_module.check_caps(measured, allowlist_module.caps_for(V6))[
            "call_depth"
        ]
        == "refuse"
    )


def test_the_lowering_pre_checks_follow_the_allowlists_caps():
    from carbon.level4.tooling import lower_torch

    class Builder:
        def __init__(self, allowlist):
            self.allowlist = allowlist

    assert lower_torch._over(Builder(V6), "nodes_executed", 5000)
    assert not lower_torch._over(Builder(V7), "nodes_executed", 10**9)
    assert not lower_torch._over(Builder(V7), "largest_intermediate_bytes", 10**12)
    assert lower_torch._over(Builder(V7), "constant_bytes", 16 * 1024 + 1)
    assert not lower_torch._over(Builder(V7), "constant_bytes", 16 * 1024)


def test_the_bundle_route_freezes_a_large_graph_only_under_v7():
    import numpy as np
    from test_bundle_graph_state import _recipe

    from carbon.development_session import bundle_graph_state
    from carbon.development_session.construction_recipe import RecipeRefused

    def doc_for(allowlist):
        doc = _chain(allowlist, 6000)
        doc["graphs"]["main"]["inputs"].append(
            {"value": 10**6, "name": "params/0", "dtype": "float32", "shape": [2]}
        )
        return doc

    parameters = [np.asarray([1.0, 2.0], dtype=np.float32)]
    state = bundle_graph_state.freeze(_recipe(), doc_for(V7), parameters, V7)
    loaded, _ = bundle_graph_state.load(state, _recipe(), V7)
    assert graph.measure(loaded)["nodes_executed"] == 6000
    with pytest.raises(RecipeRefused) as refused:
        bundle_graph_state.freeze(_recipe(), doc_for(V6), parameters, V6)
    assert refused.value.code == "bundle_graph_caps_refused"


def test_the_state_ceiling_follows_the_allowlist_version():
    from carbon.development_session import bundle_graph_state as state

    assert state.state_limit(V6) == state.MAX_BYTES == 64 * 1024**2
    assert state.state_limit(V7) is None
    assert state.state_limit(V7.raw) is None
    assert state.state_limit(b"not an allowlist") == state.MAX_BYTES
    assert state.state_fits(65 * 1024**2, V7.raw)
    assert not state.state_fits(65 * 1024**2, V6.raw)
    assert not state.state_fits(0, V7.raw)


def test_custody_reads_up_to_the_workers_output_envelope():
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.reconstruction.worker import model as worker

    assert retention._STATE_CUSTODY_BYTES == worker.OUTPUT_BYTES


def test_a_state_over_64_mib_freezes_and_loads_only_under_v7():
    import numpy as np
    from test_bundle_graph_state import _recipe

    from carbon.development_session import bundle_graph_state
    from carbon.development_session.construction_recipe import RecipeRefused

    size = 17 * 1024**2  # float32: 68 MiB, past the 64 MiB fixed ceiling

    def doc_for(allowlist):
        doc = _chain(allowlist, 2)
        doc["graphs"]["main"]["inputs"].append(
            {"value": 10**6, "name": "params/0", "dtype": "float32", "shape": [size]}
        )
        return doc

    parameters = [np.zeros(size, dtype=np.float32)]
    frozen = bundle_graph_state.freeze(_recipe(), doc_for(V7), parameters, V7)
    assert len(frozen) > 64 * 1024**2
    _, loaded = bundle_graph_state.load(frozen, _recipe(), V7)
    assert loaded[0].shape == (size,)
    with pytest.raises(RecipeRefused) as refused:
        bundle_graph_state.freeze(_recipe(), doc_for(V6), parameters, V6)
    assert refused.value.code == "bundle_state_oversized"
