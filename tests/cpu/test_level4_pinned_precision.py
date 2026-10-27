"""A graph is lowered at the default matmul precision whatever the process pins.

The validator GPU worker sets JAX_DEFAULT_MATMUL_PRECISION=highest (`accelerators.pinned_environment`). JAX writes
that into every traced dot/conv as an explicit precision, and Level-4 intake admits only the default, so every JAX
catalog twin's GPU build refused with `parameter_not_default at parameter precision`. `lower_jax.trace` now traces
under the default precision; the pin still decides the arithmetic when the graph runs.
"""

from __future__ import annotations

import pytest

jax = pytest.importorskip("jax")
import jax.numpy as jnp

from carbon.level4 import allowlist as allowlist_module
from carbon.level4.tooling import lower_jax

# v7's dot_general registers `precision` as a `none` parameter (the served versions' allowlist);
# v8's accepts the pair JAX records, so only v7 shows the refusal.
V7 = allowlist_module.load(
    __import__("pathlib").Path(allowlist_module.__file__).with_name("allowlist_v7.json")
)


def _lower(fn, *shapes):
    args = [jax.ShapeDtypeStruct(s, jnp.float32) for s in shapes]
    closed = lower_jax.trace(fn, *args)
    return lower_jax.lower(
        closed,
        role="forward",
        allowlist=V7,
        input_names=[f"x{i}" for i in range(len(args))],
    )


def test_a_pinned_process_still_lowers_a_matmul():
    previous = jax.config.jax_default_matmul_precision
    jax.config.update("jax_default_matmul_precision", "highest")
    try:
        doc = _lower(lambda a, b: a @ b, (2, 3), (3, 2))
        assert any(
            n["op"] == "dot_general" for g in doc["graphs"].values() for n in g["nodes"]
        )
        # the pin is still in force for everything that runs afterwards
        assert jax.config.jax_default_matmul_precision == "highest"
    finally:
        jax.config.update("jax_default_matmul_precision", previous)


def test_the_graph_is_the_same_pinned_or_not():
    previous = jax.config.jax_default_matmul_precision
    try:
        jax.config.update("jax_default_matmul_precision", None)
        plain = _lower(lambda a, b: jnp.tanh(a @ b), (4, 4), (4, 4))
        jax.config.update("jax_default_matmul_precision", "highest")
        pinned = _lower(lambda a, b: jnp.tanh(a @ b), (4, 4), (4, 4))
    finally:
        jax.config.update("jax_default_matmul_precision", previous)
    assert plain == pinned


def test_a_precision_the_author_writes_is_still_refused():
    from carbon.level4.graph import GraphRefused

    with pytest.raises(GraphRefused):
        _lower(
            lambda a, b: jnp.dot(a, b, precision=jax.lax.Precision.HIGHEST),
            (2, 3),
            (3, 2),
        )
