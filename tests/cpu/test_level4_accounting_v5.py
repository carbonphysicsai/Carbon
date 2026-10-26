"""Fitted-value accounting v5 under allowlist v8 (Validator
VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025 sections 3 and 7, after Graphite's v8 attacks V5a,
V5b and V8; the owner's B' counts by what a value really stores).

The 16 KiB cap is the one bound on fitted values, so it must count every channel that
can carry one into the rebuilt model, by what the channel really stores:

- constants: an integer by the bits its range needs plus the range's offset (a lone
  scalar costs the bits of its value), a bool one bit, a float its real size (float16 and
  bfloat16 two bytes, float32 four, float64 eight), a complex number its two components
  (complex64 eight, complex128 sixteen); identical copies once;
- static parameters: every integer, bool and float a node carries (slice, gather and
  padding indices, strides, shapes, permutations, dimension lists), each occurrence by
  the bits it needs;
- honest graphs stay cheap, and every earlier allowlist keeps accounting v3.

Attack cases (Graphite V5a, V5b, V8) and the channels found while closing them are
tests here: data hidden in slice start indices, in init graphs that ignore the key, in
float64 and complex128 constants, and in lone scalar constants.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, validate
from carbon.level4.tooling import lower_jax

HERE = Path(allowlist_module.__file__).parent
V7 = allowlist_module.load(HERE / "allowlist_v7.json")
V8 = allowlist_module.load(HERE / "allowlist_v8.json")
CAP = allowlist_module.CAPS["constant_bytes"]
ACCOUNTING = "level4-constant-accounting-v5"


def _constant(array, value=0):
    return {"value": value, **graph.encode_array(np.asarray(array))}


def _bytes(array):
    return graph.constant_info_bytes([_constant(array)])


def _doc(allowlist, *arrays):
    constants = [
        {"value": 1 + i, **graph.encode_array(np.asarray(a))}
        for i, a in enumerate(arrays)
    ]
    return {
        "schema": graph.SCHEMA,
        "allowlist": allowlist.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {"value": 0, "name": "inputs/x", "dtype": "float32", "shape": [2]}
                ],
                "constants": constants,
                "nodes": [],
                "outputs": [0],
            }
        },
    }


def _refused(doc, allowlist):
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(doc, allowlist, role=doc["role"])
    return refused.value


# --- the version -----------------------------------------------------------------


def test_v8_is_measured_by_v5_and_every_earlier_version_by_v3():
    assert allowlist_module.accounting_for(V8)[0] == ACCOUNTING
    assert (
        allowlist_module.accounting_for(V7)[0] == allowlist_module.CONSTANT_ACCOUNTING
    )
    assert allowlist_module.accounting_for("level4-allowlist-v6")[1] == (
        allowlist_module.MEASURED_AS
    )
    assert allowlist_module.accounting_for(None)[1] == allowlist_module.MEASURED_AS
    verdict = validate.validate(
        _doc(V8, np.arange(8, dtype=np.int32)), V8, role="forward"
    )
    assert verdict["constant_accounting"] == ACCOUNTING
    verdict = validate.validate(
        _doc(V7, np.arange(8, dtype=np.int32)), V7, role="forward"
    )
    assert verdict["constant_accounting"] == allowlist_module.CONSTANT_ACCOUNTING


# --- constants -------------------------------------------------------------------


@pytest.mark.parametrize(
    "dtype,per_value",
    [
        ("float16", 2),
        ("bfloat16", 2),
        ("float32", 4),
        ("float64", 8),
        ("complex64", 8),
        ("complex128", 16),
    ],
)
def test_a_float_is_charged_its_real_size(dtype, per_value):
    import ml_dtypes

    np_dtype = ml_dtypes.bfloat16 if dtype == "bfloat16" else np.dtype(dtype)
    array = np.arange(1, 101, dtype=np.float32).astype(np_dtype)
    assert _bytes(array) == 100 * per_value


def test_V5b_float64_and_complex128_at_the_cap_hold_what_they_are_charged():
    """Graphite V5b: 4,096 float64 values used to be charged 16,384 B and held 32,768 B."""
    ok = np.linspace(0, 1, CAP // 8, dtype=np.float64)
    assert _bytes(ok) == CAP
    assert validate.validate(_doc(V8, ok), V8, role="forward")["status"] == "admitted"
    assert _refused(_doc(V8, np.append(ok, 1.0)), V8).code == "cap_exceeded"
    wide = np.linspace(0, 1, CAP // 16, dtype=np.complex128)
    assert _bytes(wide) == CAP
    assert _refused(_doc(V8, np.append(wide, 1j)), V8).code == "cap_exceeded"


def test_integers_are_charged_the_bits_their_range_needs_and_the_offset():
    assert _bytes(np.zeros(1000, np.int32)) == -(-1001 // 8)  # a bit each, offset 1 bit
    assert _bytes(np.arange(256, dtype=np.int32)) == -(-(256 * 8 + 1) // 8)
    assert _bytes(np.arange(1024, dtype=np.int64) % 64) == -(-(1024 * 6 + 1) // 8)
    wide = np.array([0, 1 << 40] * 50, dtype=np.int64)  # 41 bits at full width
    assert _bytes(wide) == -(-(100 * 41 + 1) // 8)
    assert _bytes(np.zeros(0, np.int32)) == 0
    # a range far from zero pays for where it starts
    far = np.arange(100, dtype=np.int64) + (1 << 40)
    assert _bytes(far) == -(-(100 * 7 + 41) // 8)


def test_the_declared_dtype_does_not_set_the_price_the_values_do():
    narrow = np.arange(2000, dtype=np.int32) % 8
    wide = narrow.astype(np.int64) * (2**28)
    assert _bytes(narrow) == -(-(2000 * 3 + 1) // 8)
    assert _bytes(wide) == -(-(2000 * 31 + 1) // 8)


def test_bool_is_one_bit_and_identical_copies_count_once():
    assert _bytes(np.ones(8192, bool)) == 1024
    table = (np.arange(1000) % 16).astype(np.int32)
    assert graph.constant_info_bytes(
        [_constant(table, 0), _constant(table.copy(), 1)]
    ) == (graph.constant_info_bytes([_constant(table)]))


def test_lone_scalar_constants_cost_the_bits_of_their_value():
    """A scalar literal is a constant of range zero: it used to cost one bit whatever its
    value, so 3,000 scalars of 60 bits passed as 3,000 bytes. Now each costs 8 bytes."""
    rng = np.random.default_rng(3)
    scalars = [
        _constant(np.int64(v), i + 1)
        for i, v in enumerate(rng.integers(2**58, 2**60, 3000))
    ]
    assert graph.constant_info_bytes(scalars) == 3000 * 8
    doc = _doc(V8)
    doc["graphs"]["main"]["constants"] = scalars
    assert _refused(doc, V8).code == "cap_exceeded"


def test_the_cap_holds_what_each_dtype_really_stores():
    holds = {np.float16: CAP // 2, np.float32: CAP // 4, np.float64: CAP // 8}
    for dtype, count in holds.items():
        assert _bytes(np.arange(count).astype(dtype)) <= CAP
        assert _bytes(np.arange(count + 1).astype(dtype)) > CAP


# --- static parameters -----------------------------------------------------------


def test_every_static_integer_bool_and_float_counts_in_its_own_bits():
    bits = graph.param_value_bits
    assert bits(0) == 1 and bits(1) == 1 and bits(255) == 8 and bits(256) == 9
    assert bits(-1) == 2 and bits(-255) == 9
    assert bits(True) == 1 and bits(False) == 1
    assert bits(1.5) == 64
    assert bits([1, [2, 3], {"a": 255}]) == 1 + 2 + 2 + 8
    assert bits("a name") == 0 and bits(None) == 0
    assert bits({"graph": "g0"}) == 0
    assert bits([{"graph": "g0"}, {"graph": "g1"}]) == 0


def _template(role):
    """A lowered one-slice graph and its slice node, to clone."""
    import jax.numpy as jnp
    from jax import lax

    if role == "init":
        closed = lower_jax.trace(
            lambda key: lax.slice(jnp.arange(4096.0), (0,), (1,)),
            jnp.zeros(2, jnp.uint32),
        )
        names = ["carbon/key"]
    else:
        closed = lower_jax.trace(lambda x: lax.slice(x, (0,), (1,)), jnp.zeros(4096))
        names = ["inputs/x"]
    doc = lower_jax.lower(closed, role=role, allowlist=V8, input_names=names)
    node = next(n for n in doc["graphs"]["main"]["nodes"] if n["op"] == "slice")
    return doc, node


def _smuggle(role, payload):
    """A document that carries ``payload`` (integers below 4096) only in the start indices
    of one slice node each: no constant holds any of it."""
    doc, template = _template(role)
    entry = doc["graphs"]["main"]
    source = template["in"][0]
    top = max(
        [i["value"] for i in entry["inputs"]]
        + [c["value"] for c in entry["constants"]]
        + [o["value"] for n in entry["nodes"] for o in n["out"]]
    )
    nodes = [n for n in entry["nodes"] if n["op"] != "slice"]
    outs = []
    for i, value in enumerate(payload):
        node = copy.deepcopy(template)
        node["params"]["start_indices"] = [int(value)]
        node["params"]["limit_indices"] = [int(value) + 1]
        node["out"][0]["value"] = top + 1 + i
        node["in"] = [source]
        nodes.append(node)
        outs.append(top + 1 + i)
    entry["nodes"] = nodes
    entry["outputs"] = outs[-1:]
    return doc


@pytest.mark.parametrize("role", ["forward", "init"])
def test_V5a_V8_data_in_slice_start_indices_counts_against_the_cap(role):
    """Graphite V5a: 24,000 start indices (about 48 KB) were charged 4 bytes and the rebuilt
    graph returned them exactly; V8: the same in an init graph that ignores the key."""
    rng = np.random.default_rng(5)
    big = _smuggle(role, rng.integers(0, 4096, size=24000))
    measured = graph.measure(big)
    assert measured["constant_info_bytes"] < 64
    assert measured["param_info_bytes"] > 3 * CAP  # 24,000 x two indices of ~12 bits
    assert _refused(big, V8).code == "cap_exceeded"
    # A few hundred indices are structure, not a table: they pass.
    small = _smuggle(role, rng.integers(0, 4096, size=200))
    assert graph.measure(small)["fitted_info_bytes"] < CAP
    assert allowlist_module.check_caps(
        graph.measure(small),
        {"constant_bytes": CAP},
        allowlist_module.accounting_for(V8)[1],
    ) == {"constant_bytes": "pass"}


def test_constants_and_parameters_share_one_cap():
    """Half the cap in a table and half in indices is over: the budget is one."""
    rng = np.random.default_rng(6)
    doc = _smuggle("forward", rng.integers(0, 4096, size=3000))
    param = graph.measure(doc)["param_info_bytes"]
    assert param > CAP // 2
    doc["graphs"]["main"]["constants"] = [
        _constant(np.linspace(0, 1, (CAP - param) // 4 + 64, dtype=np.float32), 10_000)
    ]
    assert graph.measure(doc)["fitted_info_bytes"] > CAP
    assert _refused(doc, V8).code == "cap_exceeded"


def test_the_cap_is_the_submissions_not_each_documents():
    """A table split across the forward, init and loss graphs would pass three times over:
    under v5 their fitted bytes add up against the one cap."""
    forward = {"measurements": {"fitted_info_bytes": CAP * 6 // 10}}
    loss = {"measurements": {"fitted_info_bytes": CAP * 6 // 10}}
    validate.check_submission_budget({"forward": forward}, V8)
    with pytest.raises(graph.GraphRefused) as refused:
        validate.check_submission_budget({"forward": forward, "loss": loss}, V8)
    assert refused.value.code == "cap_exceeded"
    # every earlier accounting caps each document alone, as it always did
    validate.check_submission_budget({"forward": forward, "loss": loss}, V7)


def test_the_attack_suite_is_clean_on_v8_and_names_the_new_channels():
    from carbon.level4 import specimens

    rows = specimens.attack_suite(V8, max_bytes=1 << 26)
    executed = [r for r in rows if r["status"] != "recorded"]
    assert [r for r in executed if r["status"] != "pass"] == []
    names = {r["specimen"] for r in executed}
    assert "a table carried in 6,000 slice start indices" in names
    assert "an init building the same index table without the key" in names
    assert "init returning a table over the cap" in names


def test_v7_keeps_accounting_v3_and_so_its_recorded_verdicts():
    doc = _smuggle("forward", np.arange(3000) % 4096)
    flags = allowlist_module.accounting_for(V7)
    assert flags[0] == allowlist_module.CONSTANT_ACCOUNTING
    # the measurement v7 reads does not include parameters
    assert allowlist_module.check_caps(
        graph.measure(doc), {"constant_bytes": CAP}, flags[1]
    ) == {"constant_bytes": "pass"}


def test_honest_graphs_cost_almost_nothing():
    """A dozen conv blocks or attention blocks carry a few hundred bytes of structure."""
    import jax
    import jax.numpy as jnp
    from jax import lax

    def cnn(x, *ws):
        h = x
        for w in ws:
            h = lax.conv_general_dilated(
                h, w, (1, 1), "SAME", dimension_numbers=("NCHW", "OIHW", "NCHW")
            )
            h = jax.nn.gelu(h) + jnp.mean(h, axis=(2, 3), keepdims=True)
        return jnp.sum(h)

    def attn(x, wq, wk, wv, wo):
        h = x
        for _ in range(12):
            q, k, v = h @ wq, h @ wk, h @ wv
            a = jax.nn.softmax(q @ jnp.swapaxes(k, -1, -2) / 8.0, axis=-1)
            h = h + (a @ v) @ wo
            h = (h - h.mean(-1, keepdims=True)) / jnp.sqrt(
                h.var(-1, keepdims=True) + 1e-5
            )
        return h.sum()

    for fn, args in (
        (
            cnn,
            (jnp.ones((2, 8, 32, 32)),)
            + tuple(jnp.ones((8, 8, 3, 3)) for _ in range(12)),
        ),
        (attn, (jnp.ones((2, 64, 32)),) + tuple(jnp.ones((32, 32)) for _ in range(4))),
    ):
        closed = lower_jax.trace(fn, *args)
        doc = lower_jax.lower(
            closed,
            role="forward",
            allowlist=V8,
            input_names=[f"inputs/{i}" for i in range(len(args))],
        )
        measured = graph.measure(doc)
        assert measured["param_info_bytes"] < 400, measured["param_info_bytes"]
        assert measured["fitted_info_bytes"] < 1024


# --- the lowering pre-check ------------------------------------------------------


def test_the_lowering_precheck_measures_like_the_validator():
    from carbon.level4.tooling import lower_torch

    class Builder:
        def __init__(self, allowlist, constants):
            self.allowlist = allowlist
            self.constants = constants

    held = [_constant(np.arange(1000, dtype=np.int32) % 256)]
    # 4,000 more indices below 256 are 4,000 bytes: fine under v5, 16,000 under v3.
    assert not lower_torch._constants_over(Builder(V8, held), 4000, bits=8)
    assert lower_torch._constants_over(Builder(V7, held), 4000, bits=8)
    assert lower_torch._constants_over(Builder(V8, held), 20000, bits=8)
