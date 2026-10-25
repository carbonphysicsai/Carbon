"""Allowlist v8 gaps found by a differential sweep (240 jnp / lax / scipy calls
lowered under the miner role): platform dispatch (jnp.diag, jnp.diagonal,
jnp.linalg.det, corrcoef), jax.hessian's empty-mesh sharding, debug prints
and sharding hints (stripped at lowering, never carried), approx_top_k, and a
guard that every primitive JAX defines is admitted or refused with a reason."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")
jax = pytest.importorskip("jax")
import jax.numpy as jnp
import numpy as np
from jax import lax

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_jax

V8 = allowlist_module.load(
    Path(allowlist_module.__file__).with_name("allowlist_v8.json")
)
V = jnp.array([0.5, -1.25, 2.0, 0.75], jnp.float32)
BIG = jnp.eye(4, dtype=jnp.float32) * 2.0 + 0.1


def _lower(fn, args, role="forward"):
    closed = lower_jax.trace(fn, *args)
    names = [f"a{i}" for i in range(len(closed.jaxpr.invars))]
    doc = lower_jax.lower(closed, role=role, allowlist=V8, input_names=names)
    parsed = graph.parse(graph.dumps(doc), max_bytes=1 << 26)
    return doc, interpret.rebuild(parsed, V8)


def _nodes(doc):
    return [n for g in doc["graphs"].values() for n in g["nodes"]]


@pytest.mark.parametrize(
    "fn,args",
    [
        (jnp.diag, (BIG,)),
        (jnp.diagonal, (BIG,)),
        (lambda a: jnp.corrcoef(a), (BIG + jnp.arange(16.0).reshape(4, 4),)),
    ],
    ids=["diag", "diagonal", "corrcoef"],
)
def test_platform_dispatch_lowers_and_matches_jax(fn, args):
    doc, run = _lower(fn, args)
    assert any(n["op"] == "platform_index" for n in _nodes(doc))
    for got, want in zip(run(*args), jax.tree_util.tree_leaves(fn(*args))):
        np.testing.assert_allclose(got, want, rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize(
    "fn", [jnp.linalg.det, lambda a: jnp.linalg.slogdet(a)[1]], ids=["det", "slogdet"]
)
def test_det_and_slogdet_lower_and_match_jax(fn):
    _, run = _lower(fn, (BIG,))
    np.testing.assert_allclose(
        run(BIG)[0], jax.tree_util.tree_leaves(fn(BIG))[0], rtol=1e-5
    )


@pytest.mark.parametrize(
    "fn", [jnp.linalg.det, lambda a: jnp.linalg.slogdet(a)[1]], ids=["det", "slogdet"]
)
def test_det_and_slogdet_gradients_use_the_carried_rule(fn):
    _, run = _lower(fn, (BIG,))
    want = jax.grad(lambda a: jnp.sum(jax.tree_util.tree_leaves(fn(a))[0]))(BIG)
    got = jax.grad(lambda a: jnp.sum(run(a)[0]))(BIG)
    np.testing.assert_allclose(got, want, rtol=1e-4, atol=1e-5)


def test_a_platform_cond_keeps_its_optional_parameter():
    doc, _ = _lower(jnp.diagonal, (BIG,))
    conds = [n for n in _nodes(doc) if n["op"] == "cond"]
    assert any("branches_platforms" in n["params"] for n in conds)
    # An ordinary cond has no such parameter and still lowers.
    doc, run = _lower(lambda a: lax.cond(a.sum() > 0, jnp.sin, jnp.cos, a), (V,))
    assert all("branches_platforms" not in n["params"] for n in _nodes(doc))
    np.testing.assert_allclose(run(V)[0], jnp.sin(V), rtol=1e-6)


def test_jax_hessian_lowers():
    fn = lambda a: jax.hessian(lambda x: (x**3).sum())(a)
    _, run = _lower(fn, (V,))
    np.testing.assert_allclose(run(V)[0], fn(V), rtol=1e-5)


def test_debug_prints_and_sharding_hints_are_stripped_not_carried():
    def noisy(a):
        jax.debug.print("a = {}", a)
        jax.debug.callback(lambda x: None, a)
        b = lax.with_sharding_constraint(
            a, jax.sharding.SingleDeviceSharding(jax.devices()[0])
        )
        return b * 2.0

    doc, run = _lower(noisy, (V,))
    ops = {n["op"] for n in _nodes(doc)}
    assert not ops & {"debug_print", "debug_callback", "sharding_constraint"}
    np.testing.assert_allclose(run(V)[0], V * 2.0)


def test_other_effects_stay_refused():
    from jax.experimental import io_callback

    shape = jax.ShapeDtypeStruct(V.shape, V.dtype)
    with pytest.raises(graph.GraphRefused):
        _lower(lambda a: io_callback(lambda x: x, shape, a), (V,))


def test_approx_top_k_matches_jax():
    x = jnp.linspace(-1.0, 1.0, 12, dtype=jnp.float32).reshape(3, 4)
    fn = lambda a: lax.approx_max_k(a, 2)
    _, run = _lower(fn, (x,))
    for got, want in zip(run(x), fn(x)):
        np.testing.assert_array_equal(got, want)


def test_a_reduction_with_your_own_computation_lowers_and_matches_jax():
    fn = lambda a: lax.reduce(a, 0.0, lambda x, y: x + y * y, (0,))  # noqa: E731
    doc, run = _lower(fn, (V,))
    assert "reduce" in {n["op"] for n in _nodes(doc)}
    np.testing.assert_allclose(run(V)[0], fn(V), rtol=1e-6)
    two = lambda a: lax.reduce(  # noqa: E731
        (a, a * 2), (0.0, 1.0), lambda x, y: (x[0] + y[0], x[1] * y[1]), (0,)
    )
    _, run = _lower(two, (V,))
    for got, want in zip(run(V), two(V)):
        np.testing.assert_allclose(got, want, rtol=1e-5)


def test_a_window_reduction_with_your_own_computation_matches_jax():
    fn = lambda a: lax.reduce_window(  # noqa: E731
        a, 0.0, lambda x, y: x + y * y, (2,), (1,), "VALID"
    )
    doc, run = _lower(fn, (V,))
    assert "reduce_window" in {n["op"] for n in _nodes(doc)}
    np.testing.assert_allclose(run(V)[0], fn(V), rtol=1e-6)


def test_ragged_dot_and_symmetric_product_match_jax():
    lhs = jnp.arange(16.0, dtype=jnp.float32).reshape(4, 4) / 10
    rhs = jnp.arange(24.0, dtype=jnp.float32).reshape(2, 4, 3) / 10
    sizes = jnp.array([1, 3], jnp.int32)
    fn = lambda a, b, g: lax.ragged_dot(a, b, g)  # noqa: E731
    doc, run = _lower(fn, (lhs, rhs, sizes))
    assert "ragged_dot_general" in {n["op"] for n in _nodes(doc)}
    np.testing.assert_allclose(run(lhs, rhs, sizes)[0], fn(lhs, rhs, sizes), rtol=1e-5)
    from jax._src.lax import linalg

    sym = lambda a, c: linalg.symmetric_product_p.bind(a, c, alpha=2.0, beta=0.5)  # noqa: E731
    _, run = _lower(sym, (lhs, jnp.zeros((4, 4), jnp.float32)))
    np.testing.assert_allclose(
        run(lhs, jnp.zeros((4, 4), jnp.float32))[0],
        sym(lhs, jnp.zeros((4, 4), jnp.float32)),
        rtol=1e-5,
    )
