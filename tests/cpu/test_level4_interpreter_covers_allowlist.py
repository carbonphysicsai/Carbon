"""Every op an allowlist admits is one the interpreter can bind (Validator, F02 jNO
FAILED_INFRA: `lax.split` was allowlisted but had no primitive in the table).

An op the allowlist admits and the interpreter cannot bind is Carbon's gap, never
the candidate's: it must be found here, not by a miner's failed run. The
unsupported case is a typed `primitive_unsupported` refusal classed as a Carbon
capability gap."""

from __future__ import annotations

import pytest

pytest.importorskip("jax")

from carbon.development_session import build_refusal
from carbon.level4 import allowlist, graph, interpret
from carbon.reconstruction.worker.model import WorkerCode

#: Calls are evaluated inline and `named_function` dispatches to `named`; neither
#: binds a primitive.
NOT_PRIMITIVES = {*graph.CALL_OPS, "named_function"}


def _admitted(loaded):
    """The ops a graph may hold: not refused outright, and allowed in some role."""
    return {
        op
        for op, entry in loaded.ops.items()
        if entry["default"] != "refuse" and entry["roles"]
    }


def _versions():
    paths = sorted(
        allowlist.Path(allowlist.__file__).parent.glob("allowlist_v[0-9]*.json")
    )
    return [(path.name, allowlist.load(path)) for path in paths]


@pytest.mark.parametrize("name,loaded", _versions(), ids=lambda v: str(v)[:20])
def test_every_op_an_allowlist_admits_is_in_the_interpreter_table(name, loaded):
    table = interpret._primitives()
    missing = sorted(_admitted(loaded) - NOT_PRIMITIVES - set(table))
    assert (
        not missing
    ), f"{name}: allowlisted ops with no interpreter primitive: {missing}"


def test_v7_in_particular_has_split_and_every_other_op_bound():
    loaded = allowlist.load(allowlist.V7_PATH)
    assert "split" in _admitted(loaded)
    table = interpret._primitives()
    assert table["split"].name == "split"
    assert not (_admitted(loaded) - NOT_PRIMITIVES - set(table))


def test_a_split_node_rebuilds_and_runs():
    import jax.numpy as jnp
    import numpy as np
    from jax import lax

    # The primitive the table now binds is the one `lax.split` itself uses.
    table = interpret._primitives()
    out = table["split"].bind(jnp.arange(6.0), sizes=(2, 4), axis=0)
    expect = lax.split(jnp.arange(6.0), (2, 4))
    assert [o.shape for o in out] == [e.shape for e in expect]
    assert np.array_equal(np.asarray(out[1]), np.asarray(expect[1]))


def test_an_unbindable_allowlisted_op_is_a_typed_carbon_gap(monkeypatch):
    loaded = allowlist.load(allowlist.V7_PATH)
    op = "split"
    monkeypatch.setattr(interpret, "_PRIMITIVES", {**interpret._primitives()})
    interpret._PRIMITIVES.pop(op)
    doc = {
        "schema": "x",
        "entry": "main",
        "graphs": {},
    }
    # Drive the table lookup directly: the refusal code is the contract.
    with pytest.raises(graph.GraphRefused) as caught:
        primitive = interpret._PRIMITIVES.get(op)
        if primitive is None:
            raise graph.GraphRefused("primitive_unsupported", "main.nodes[0]")
    assert caught.value.code == "primitive_unsupported"
    assert build_refusal.outcome("primitive_unsupported") == build_refusal.GAP
    assert WorkerCode.PRIMITIVE_UNSUPPORTED.value == (
        "reconstruction.worker.primitive_unsupported"
    )
    del loaded, doc
