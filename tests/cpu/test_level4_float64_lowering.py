"""A float64 graph lowers as float64 (miner report, 19 Oct).

With JAX's default (x64 off), a graph declaring float64 inputs was lowered as
float32, and the Challenge interface then refused it. Lowering now turns x64
on for a float64 argument or interface, and leaves the caller's setting as it
was otherwise.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

jax = pytest.importorskip("jax")

import jax.numpy as jnp

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, validate
from carbon.level4.tooling import __main__ as cli
from carbon.level4.tooling import lower_jax

pytestmark = pytest.mark.skipif(
    bool(jax.config.jax_enable_x64), reason="needs JAX's default x64-off"
)
INTERFACE = validate.Interface(
    inputs=(("inputs/x", "float64", (3,)),), outputs=(("float64", (2,)),)
)


def _dtypes(doc):
    entry = doc["graphs"][doc["entry"]]
    return {i["name"]: i["dtype"] for i in entry["inputs"]}


def test_a_float64_input_lowers_as_float64_and_passes_the_interface():
    closed = lower_jax.trace(
        lambda w, x: jnp.tanh(x @ w),
        jax.ShapeDtypeStruct((3, 2), "float64"),
        jax.ShapeDtypeStruct((4, 3), "float64"),
    )
    doc = lower_jax.lower(
        closed,
        role="forward",
        allowlist=allowlist_module.load(),
        input_names=["params/0", "inputs/x"],
    )
    assert set(_dtypes(doc).values()) == {"float64"}
    assert validate.check_interface(doc, INTERFACE) == 4
    assert not jax.config.jax_enable_x64  # the caller's setting is restored


def test_the_lowering_cli_keeps_a_float64_interface_and_its_parameters():
    module = SimpleNamespace(
        INPUTS={"inputs/x": ((3,), "float64")},
        init=lambda key: [jax.random.normal(key, (3, 2), jnp.float64)],
        forward=lambda params, x: x @ params[0],
    )
    documents = cli._jax_documents(
        module, 4, allowlist_module.load(), intake.BOUNDS["document_bytes"]
    )
    assert _dtypes(documents["forward"]) == {
        "params/0": "float64",
        "inputs/x": "float64",
    }
    assert validate.check_interface(documents["forward"], INTERFACE) == 4
    assert not jax.config.jax_enable_x64


def test_a_float32_graph_is_unchanged():
    closed = lower_jax.trace(lambda x: x * 2, jax.ShapeDtypeStruct((4, 3), "float32"))
    doc = lower_jax.lower(
        closed,
        role="forward",
        allowlist=allowlist_module.load(),
        input_names=["inputs/x"],
    )
    assert _dtypes(doc) == {"inputs/x": "float32"}
