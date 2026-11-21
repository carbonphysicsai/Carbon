"""The trust-head shape rule (carbon/level4/trust_head.py): one concatenate of a physics operand and a trust operand whose
parameter sets are disjoint. Structure only: the documents below are the smallest that carry the shape, not runnable graphs.
"""

from __future__ import annotations

import pytest

from carbon.level4.graph import GraphRefused
from carbon.level4.trust_head import check

W, K, B = 3, 2, 4  # physics width, trust width, batch


def aval(value, *shape):
    return {"value": value, "dtype": "float32", "shape": list(shape)}


def node(op, ins, out, **params):
    return {"op": op, "in": list(ins), "out": [out], "params": params}


def document(*, nodes, output, parameters=3, constants=()):
    """Entry graph with `parameters` parameter inputs (values 0..n-1) then the data input (value n)."""
    inputs = [dict(aval(i, 5, 5), name=f"p{i}") for i in range(parameters)]
    inputs.append(dict(aval(parameters, B, 5), name="x"))
    return {
        "schema": "carbon.development.level4-graph.v0",
        "allowlist": "8",
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": inputs,
                "constants": list(constants),
                "nodes": list(nodes),
                "outputs": [output],
            }
        },
    }


# values: p0=0, p1=1, p2=2, x=3
def good(trust_reads=(1, 3), physics_reads=(0, 3)):
    return document(
        nodes=[
            node("mul", physics_reads, aval(10, B, W)),
            node("mul", trust_reads, aval(11, B, K)),
            node("concatenate", (10, 11), aval(12, B, W + K), dimension=1),
        ],
        output=12,
    )


def test_a_disjoint_trust_head_passes_and_reports_each_operands_parameters():
    assert check(good(), physics_width=W, trust_width=K) == {
        "physics_parameters": [0],
        "trust_parameters": [1],
    }


def test_the_physics_operands_own_value_may_feed_the_trust_head():
    # the trust operand reads x, its own parameter p1 and the physics operand's VALUE (10): allowed (phase 2 freezes physics)
    doc = document(
        nodes=[
            node("mul", (0, 3), aval(10, B, W)),
            node("mul", (1, 10), aval(11, B, K)),
            node("concatenate", (10, 11), aval(12, B, W + K), dimension=1),
        ],
        output=12,
    )
    assert check(doc, physics_width=W, trust_width=K) == {
        "physics_parameters": [0],
        "trust_parameters": [1],
    }


def test_an_earlier_physics_value_feeding_the_trust_head_is_refused():
    # value 9 is a physics feature BEFORE the operand: it carries p0 into the trust operand
    doc = document(
        nodes=[
            node("mul", (0, 3), aval(9, B, W)),
            node("tanh", (9,), aval(10, B, W)),
            node("mul", (1, 9), aval(11, B, K)),
            node("concatenate", (10, 11), aval(12, B, W + K), dimension=1),
        ],
        output=12,
    )
    with pytest.raises(GraphRefused) as refused:
        check(doc, physics_width=W, trust_width=K)
    assert refused.value.code == "trust_head_shares_parameters"


def test_a_trust_operand_reading_only_the_data_input_and_its_own_parameter_passes():
    doc = good(trust_reads=(2, 3), physics_reads=(0, 3))
    assert check(doc, physics_width=W, trust_width=K)["trust_parameters"] == [2]


def test_a_shared_parameter_is_refused():
    with pytest.raises(GraphRefused) as refused:
        check(good(trust_reads=(0, 3)), physics_width=W, trust_width=K)
    assert refused.value.code == "trust_head_shares_parameters"


def test_a_parameter_reaching_both_operands_through_a_chain_is_refused():
    doc = document(
        nodes=[
            node("mul", (0, 3), aval(9, B, W)),
            node("tanh", (9,), aval(10, B, W)),
            node("mul", (1, 3), aval(8, B, K)),
            node("add", (8, 0), aval(11, B, K)),  # p0 enters the trust operand late
            node("concatenate", (10, 11), aval(12, B, W + K), dimension=1),
        ],
        output=12,
    )
    with pytest.raises(GraphRefused) as refused:
        check(doc, physics_width=W, trust_width=K)
    assert refused.value.code == "trust_head_shares_parameters"


def test_a_call_node_depends_on_all_its_operands():
    # a nested call over (p0, p1, x) is both operands' only producer of the trust value: it reaches p0 (physics) too
    doc = document(
        nodes=[
            node("mul", (0, 3), aval(10, B, W)),
            node("closed_call", (0, 1, 3), aval(11, B, K), graph="main"),
            node("concatenate", (10, 11), aval(12, B, W + K), dimension=1),
        ],
        output=12,
    )
    with pytest.raises(GraphRefused) as refused:
        check(doc, physics_width=W, trust_width=K)
    assert refused.value.code == "trust_head_shares_parameters"


def test_a_trust_head_with_no_parameter_of_its_own_is_refused():
    with pytest.raises(GraphRefused) as refused:
        check(good(trust_reads=(3, 3)), physics_width=W, trust_width=K)
    assert refused.value.code == "trust_head_has_no_parameters"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["graphs"]["main"][
            "nodes"
        ].pop(),  # output is not produced by a concatenate
        lambda d: d["graphs"]["main"]["nodes"][-1].update(
            {"in": [10, 11, 10]}
        ),  # three operands
        lambda d: d["graphs"]["main"]["nodes"][-1]["params"].update(
            dimension=0
        ),  # not the last axis
        lambda d: d["graphs"]["main"]["nodes"][-1].update(
            {"op": "add"}
        ),  # not a concatenate
        lambda d: d["graphs"]["main"].update(outputs=[12, 10]),  # two outputs
    ],
)
def test_any_other_output_shape_is_refused(mutate):
    doc = good()
    try:
        mutate(doc)
    except Exception:  # pragma: no cover
        raise
    with pytest.raises(GraphRefused) as refused:
        check(doc, physics_width=W, trust_width=K)
    assert refused.value.code == "trust_output_shape"


def test_the_operand_widths_and_their_order_are_exact():
    # physics first, trust second, each exactly its width
    with pytest.raises(GraphRefused) as refused:
        check(good(), physics_width=K, trust_width=W)
    assert refused.value.code == "trust_output_shape"
    for widths in ((0, K), (W, 0), (W, True)):
        with pytest.raises(GraphRefused) as refused:
            check(good(), physics_width=widths[0], trust_width=widths[1])
        assert refused.value.code == "trust_output_shape"


def test_a_negative_one_last_axis_is_the_same_axis():
    doc = good()
    doc["graphs"]["main"]["nodes"][-1]["params"]["dimension"] = -1
    assert check(doc, physics_width=W, trust_width=K)["trust_parameters"] == [1]
