"""OWNER-GRAPH-OPS-FREEDOM-01 (2026-10-25, miner feedback): the graph route admits
every pure, deterministic array op. This file covers the JAX route: a function using
the op traces, lowers to a Carbon graph under allowlist v7, rebuilds on Carbon's side
and returns exactly what the same JAX call returns (values and, where the op is
differentiable, gradients), twice in a row bit for bit. v6 still refuses each one.
Containment is unchanged: custom_call, callbacks, RNG without a seed and unbounded
loops stay refused (last test).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")
jax = pytest.importorskip("jax")

import jax.numpy as jnp
import jax.scipy.linalg as jsl
import numpy as np
from jax import lax

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_jax

V6 = Path(allowlist_module.__file__).with_name("allowlist_v6.json")
V7 = Path(allowlist_module.__file__).with_name("allowlist_v7.json")
V8 = Path(allowlist_module.__file__).with_name("allowlist_v8.json")


def _spd(n=3):
    a = jnp.asarray(
        np.random.default_rng(0).normal(size=(n, n)).astype(np.float32)
    )
    return a @ a.T + n * jnp.eye(n, dtype=jnp.float32)


def _positive(shape=(3, 4)):
    return jnp.asarray(
        np.random.default_rng(1).uniform(0.2, 2.0, size=shape).astype(np.float32)
    )


def _signed(shape=(3, 4)):
    return jnp.asarray(
        np.random.default_rng(2).uniform(-1.0, 1.0, size=shape).astype(np.float32)
    )


def _unit(shape=(3, 4)):
    return _signed(shape) * 0.9


def _ints(shape=(3, 4)):
    return jnp.asarray(
        np.random.default_rng(3).integers(1, 200, size=shape).astype(np.int32)
    )


#: name -> (op names the graph must hold, function, example inputs, differentiable)
CASES = {
    "asin": (("asin",), lambda x: jnp.arcsin(x), (_unit(),), True),
    "acos": (("acos",), lambda x: jnp.arccos(x), (_unit(),), True),
    "atan": (("atan",), lambda x: jnp.arctan(x), (_signed(),), True),
    "atan2": (("atan2",), lambda y, x: jnp.arctan2(y, x), (_signed(), _positive()), True),
    "sinh": (("sinh",), lambda x: jnp.sinh(x), (_signed(),), True),
    "cosh": (("cosh",), lambda x: jnp.cosh(x), (_signed(),), True),
    "asinh": (("asinh",), lambda x: jnp.arcsinh(x), (_signed(),), True),
    "acosh": (("acosh",), lambda x: jnp.arccosh(x), (_positive() + 1.0,), True),
    "atanh": (("atanh",), lambda x: jnp.arctanh(x), (_unit(),), True),
    "cbrt": (("cbrt",), lambda x: jnp.cbrt(x), (_positive(),), True),
    "exp2": (("exp2",), lambda x: jnp.exp2(x), (_signed(),), True),
    "ceil": (("ceil",), lambda x: jnp.ceil(x * 3.0), (_signed(),), True),
    "round_even": (
        ("round",),
        lambda x: lax.round(x * 4.0, lax.RoundingMethod.TO_NEAREST_EVEN),
        (_signed(),),
        True,
    ),
    "round_away": (
        ("round",),
        lambda x: lax.round(x * 4.0, lax.RoundingMethod.AWAY_FROM_ZERO),
        (_signed(),),
        True,
    ),
    "is_finite": (
        ("is_finite",),
        lambda x: jnp.where(jnp.isfinite(x / (x - x[0, 0])), x, 0.0),
        (_signed(),),
        False,
    ),
    "clamp": (
        ("clamp",),
        lambda x: lax.clamp(jnp.float32(-0.3), x, jnp.float32(0.4)),
        (_signed(),),
        True,
    ),
    "lgamma": (("lgamma",), lambda x: lax.lgamma(x), (_positive(),), True),
    "digamma": (("digamma",), lambda x: lax.digamma(x), (_positive(),), True),
    "bessel_i0e": (("bessel_i0e",), lambda x: lax.bessel_i0e(x), (_signed(),), True),
    "bessel_i1e": (("bessel_i1e",), lambda x: lax.bessel_i1e(x), (_signed(),), True),
    "igamma": (("igamma",), lambda a, x: lax.igamma(a, x), (_positive(), _positive()), False),
    "stack": (("stack",), lambda x, y: jnp.stack([x, y], axis=1), (_signed(), _signed()), True),
    "unstack": (
        ("unstack",),
        lambda x: sum(jnp.unstack(x, axis=1)[::2]),
        (_signed(),),
        True,
    ),
    "cumprod": (("cumprod",), lambda x: jnp.cumprod(x, axis=1), (_positive(),), True),
    "cummax": (("cummax",), lambda x: lax.cummax(x, axis=1), (_signed(),), True),
    "cummin": (("cummin",), lambda x: lax.cummin(x, axis=1, reverse=True), (_signed(),), True),
    "cumlogsumexp": (
        ("cumlogsumexp",),
        lambda x: lax.cumlogsumexp(x, axis=1),
        (_signed(),),
        True,
    ),
    "reduce_and_or": (
        ("reduce_and", "reduce_or"),
        lambda x: jnp.where(jnp.all(x > -2.0) & jnp.any(x > 0.5), x, 0.0),
        (_signed(),),
        True,
    ),
    "bitwise": (
        ("xor", "shift_left", "population_count"),
        lambda i: (i ^ (i << 1)) + lax.population_count(i),
        (_ints(),),
        False,
    ),
    "clz_shift": (
        ("clz", "shift_right_arithmetic"),
        lambda i: lax.clz(i) + (i >> 2),
        (_ints(),),
        False,
    ),
    "cholesky": (("cholesky",), lambda a: jnp.linalg.cholesky(a), (_spd(),), True),
    "triangular_solve": (
        ("triangular_solve",),
        lambda a, b: jsl.solve_triangular(jnp.tril(a) + 3.0 * jnp.eye(3), b, lower=True),
        (_spd(), _signed((3, 2))),
        True,
    ),
    "cho_solve": (
        ("cholesky", "triangular_solve"),
        lambda a, b: jsl.cho_solve(jsl.cho_factor(a), b),
        (_spd(), _signed((3, 2))),
        True,
    ),
    "eigvalsh": (
        ("eigh",),
        lambda a: jnp.linalg.eigvalsh(a),
        (_spd(),),
        True,
    ),
    "eigh_reconstruction": (
        ("eigh",),
        lambda a: (lambda w, v: (v * w) @ v.T)(*jnp.linalg.eigh(a)),
        (_spd(),),
        False,
    ),
    "lu": (("lu",), lambda a: jsl.lu(a)[1], (_spd(),), True),
    "qr_reconstruction": (
        ("qr",),
        lambda a: (lambda q, r: q @ r)(*jnp.linalg.qr(a)),
        (_spd(),),
        False,
    ),
    "singular_values": (
        ("svd",),
        lambda a: jnp.linalg.svd(a, compute_uv=False),
        (_spd(),),
        True,
    ),
    # ---- control flow, as nested graphs
    "scan": (
        ("scan",),
        lambda x: lax.scan(lambda c, v: (c * 0.9 + v, jnp.tanh(c)), jnp.zeros((4,), jnp.float32), x)[1],
        (_signed((5, 4)),),
        True,
    ),
    "scan_reverse_carry": (
        ("scan",),
        lambda x: lax.scan(lambda c, v: (c + v, c * v), jnp.ones((4,), jnp.float32), x, reverse=True)[0],
        (_signed((5, 4)),),
        True,
    ),
    "fori_loop": (
        ("scan",),
        lambda x: lax.fori_loop(0, 4, lambda i, c: c * 1.1 + jnp.sin(c), x),
        (_signed(),),
        True,
    ),
    "cond": (
        ("cond",),
        lambda x: lax.cond(x[0, 0] > 0, lambda v: v * 2.0, lambda v: v + 1.0, x),
        (_signed(),),
        True,
    ),
    "switch": (
        ("cond",),
        lambda x, i: lax.switch(i, [lambda v: v, lambda v: v * 2.0, lambda v: v * v], x),
        (_signed(), jnp.int32(2)),
        True,
    ),
    "remat": (("remat2",), lambda x: jax.checkpoint(lambda v: jnp.sin(v) * v)(x), (_signed(),), True),
    # ---- scatters, windows, top_k, the rest
    "scatter_add": (
        ("scatter_add",),
        lambda x, u: x.at[jnp.array([0, 2, 0])].add(u),
        (_signed(), _signed((3, 4))),
        True,
    ),
    "scatter_mul": (
        ("scatter_mul",),
        lambda x, u: x.at[jnp.array([1, 1, 0])].multiply(u),
        (_signed(), _positive()),
        True,
    ),
    "scatter_min": (
        ("scatter_min",),
        lambda x, u: x.at[jnp.array([1, 1, 0])].min(u),
        (_signed(), _signed()),
        True,
    ),
    "scatter_max": (
        ("scatter_max",),
        lambda x, u: x.at[jnp.array([1, 1, 0])].max(u),
        (_signed(), _signed()),
        True,
    ),
    "top_k": (("top_k",), lambda x: lax.top_k(x, 2)[0], (_signed(),), True),
    "reduce_window_sum": (
        ("reduce_window_sum",),
        lambda x: lax.reduce_window(x, 0.0, lax.add, (1, 2), (1, 1), "VALID"),
        (_signed(),),
        True,
    ),
    "reduce_window_max": (
        ("reduce_window_max",),
        lambda x: lax.reduce_window(x, -jnp.inf, lax.max, (2, 2), (1, 1), "SAME"),
        (_signed(),),
        True,
    ),
    "reduce_window_min": (
        ("reduce_window_min",),
        lambda x: lax.reduce_window(x, jnp.inf, lax.min, (1, 2), (1, 2), "VALID"),
        (_signed(),),
        True,
    ),
    "reduce_precision": (
        ("reduce_precision",),
        lambda x: lax.reduce_precision(x, 5, 10),
        (_signed(),),
        False,
    ),
    "polygamma": (("polygamma",), lambda x: jax.scipy.special.polygamma(1, x), (_positive(),), False),
    "betainc": (
        ("regularized_incomplete_beta",),
        lambda x: jax.scipy.special.betainc(x, x + 0.5, jnp.clip(x * 0.3, 0.01, 0.99)),
        (_positive(),),
        False,
    ),
    "device_put": (("device_put",), lambda x: jax.device_put(x) * 2.0, (_signed(),), True),
    "householder": (
        ("geqrf", "householder_product"),
        lambda a: (lambda f, t: jax.lax.linalg.householder_product(f, t))(*jax.lax.linalg.geqrf(a)),
        (_spd(),),
        False,
    ),
    "tridiagonal_solve": (
        ("tridiagonal_solve",),
        lambda d, b: jax.lax.linalg.tridiagonal_solve(
            jnp.ones(3, jnp.float32).at[0].set(0.0), d + 4.0, jnp.ones(3, jnp.float32).at[2].set(0.0), b
        ),
        (_signed((3,)), _signed((3, 2))),
        True,
    ),
    "eigvals": (("eig",), lambda a: jnp.sort(jnp.abs(jnp.linalg.eigvals(a))), (_spd(),), False),
    "hessenberg": (("hessenberg",), lambda a: jax.scipy.linalg.hessenberg(a)[0], (_spd(),), False),
    "schur": (("schur",), lambda a: jax.scipy.linalg.schur(a)[0], (_spd(),), False),
}


def _rebuilt(fn, args, path=V8):
    allowlist = allowlist_module.load(path)
    closed = lower_jax.trace(fn, *[jax.ShapeDtypeStruct(a.shape, a.dtype) for a in args])
    doc = lower_jax.lower(
        closed,
        role="forward",
        allowlist=allowlist,
        input_names=[f"x{i}" for i in range(len(args))],
    )
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    return doc, interpret.rebuild(parsed, allowlist)


def _ops(doc):
    return {n["op"] for g in doc["graphs"].values() for n in g["nodes"]}


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_op_lowers_rebuilds_and_matches_jax(name):
    ops, fn, args, differentiable = CASES[name]
    doc, run = _rebuilt(fn, args)
    assert set(ops) <= _ops(doc), (name, _ops(doc))
    want = np.asarray(fn(*args))
    got = np.asarray(run(*args)[0])
    again = np.asarray(run(*args)[0])
    np.testing.assert_array_equal(got, want)  # the same primitive, the same bytes
    assert got.tobytes() == again.tobytes()  # deterministic: a repeat is bit for bit
    if differentiable:
        want_grad = jax.grad(lambda *a: jnp.sum(fn(*a) * 1.5), argnums=0)(*args)
        got_grad = jax.grad(lambda *a: jnp.sum(run(*a)[0] * 1.5), argnums=0)(*args)
        # Gradients come from the same rules; XLA fusion may move the last bit.
        np.testing.assert_allclose(
            np.asarray(got_grad), np.asarray(want_grad), rtol=1e-5, atol=1e-6
        )


@pytest.mark.parametrize("path", [V6, V7], ids=["v6", "v7"])
@pytest.mark.parametrize("name", sorted(CASES))
def test_earlier_versions_still_refuse_the_op(name, path):
    """v8 is a new file: v6 and v7 keep refusing what they always refused."""
    ops, fn, args, _ = CASES[name]
    with pytest.raises(graph.GraphRefused) as refused:
        _rebuilt(fn, args, path=path)
    assert refused.value.code in {
        "op_not_allowlisted",
        "parameters_not_allowlisted",
        "op_not_supported_v0",
        "op_refused",
    }


SOLVES = {
    "solve_matrix": lambda a, b: jnp.linalg.solve(a, b),
    "solve_vector": lambda a, b: jnp.linalg.solve(a, b[:, 0]),
    "inv": lambda a, b: jnp.linalg.inv(a) @ b,
    "scipy_solve": lambda a, b: jsl.solve(a, b),
    "scipy_solve_spd": lambda a, b: jsl.solve(a, b, assume_a="pos"),
}


@pytest.mark.parametrize("name", sorted(SOLVES))
def test_a_linear_solve_keeps_its_gradient_in_the_matrix_and_the_right_side(name):
    """jnp.linalg.solve lowers through custom_linear_solve; inlining its stop-gradient
    factorization would lose the gradient in the matrix, so the rule is kept."""
    fn = SOLVES[name]
    args = (_spd(), _signed((3, 2)))
    doc, run = _rebuilt(fn, args)
    assert "custom_linear_solve" in _ops(doc)
    np.testing.assert_allclose(
        np.asarray(run(*args)[0]), np.asarray(fn(*args)), rtol=1e-6, atol=1e-6
    )
    assert np.asarray(run(*args)[0]).tobytes() == np.asarray(run(*args)[0]).tobytes()
    probe = jnp.linspace(-1.0, 2.0, int(np.prod(np.asarray(fn(*args)).shape))).reshape(
        np.asarray(fn(*args)).shape
    )
    want = jax.grad(lambda a, b: jnp.sum(fn(a, b) * probe), argnums=(0, 1))(*args)
    got = jax.grad(lambda a, b: jnp.sum(run(a, b)[0] * probe), argnums=(0, 1))(*args)
    for g, w in zip(got, want):
        assert np.abs(np.asarray(w)).max() > 1e-3  # the gradient is not trivially zero
        np.testing.assert_allclose(np.asarray(g), np.asarray(w), rtol=1e-4, atol=1e-5)


def test_a_malformed_nested_solve_reference_is_refused():
    allowlist = allowlist_module.load(V8)
    args = (_spd(), _signed((3, 2)))
    doc, _ = _rebuilt(SOLVES["solve_matrix"], args)
    node = next(
        n
        for g in doc["graphs"].values()
        for n in g["nodes"]
        if n["op"] == "custom_linear_solve"
    )
    node["params"]["solve"] = "not-a-reference"
    with pytest.raises(graph.GraphRefused):
        allowlist.check(doc)


def test_containment_is_unchanged():
    """Escapes, callbacks and unseeded generators stay refused in v7."""
    ops = allowlist_module.load(V8).ops
    for name in (
        "custom_call",
        "ffi_call",
        "pure_callback",
        "io_callback",
        "debug_callback",
        "infeed",
        "outfeed",
        "rng_bit_generator",
        "rng_uniform",
        "random_seed",
        "while",
    ):
        assert ops[name]["default"] == "refuse", name
