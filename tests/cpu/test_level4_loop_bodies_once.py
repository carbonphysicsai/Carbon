"""Graph loop bodies are built once per rebuilt document (carbon/level4/interpret.py, miner report 11-01).

Claims: `scan`, `while` and a multi-branch `cond` give BIT-EQUAL values, gradients (jvp for `while`) to the earlier interpreter,
whose functions are copied verbatim below as the reference; that holds when the loop's consts change between calls (a reused body
never replays an earlier call's constant); and from the second call on the body graphs are not traced again (the trace count).
"""

from __future__ import annotations

import json
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

V8 = Path(allowlist_module.__file__).with_name("allowlist_v8.json")


# --- the earlier interpreter's loop functions, verbatim (main bd9f5f07), as the "before" ---------------------------------
def _old_while(run, bound, ins):
    cond_n, body_n = bound["cond_nconsts"], bound["body_nconsts"]
    cond_consts = list(ins[:cond_n])
    body_consts = list(ins[cond_n : cond_n + body_n])
    init = tuple(ins[cond_n + body_n :])
    cond_ref, body_ref = bound["cond_jaxpr"]["graph"], bound["body_jaxpr"]["graph"]
    return list(
        jax.lax.while_loop(
            lambda state: run(cond_ref, [*cond_consts, *state])[0],
            lambda state: tuple(run(body_ref, [*body_consts, *state])),
            init,
        )
    )


def _old_scan(run, bound, ins):
    consts = bound["num_consts"]
    carry = bound["num_carry"]
    held, init, xs = ins[:consts], ins[consts : consts + carry], ins[consts + carry :]
    body = bound["jaxpr"]["graph"]

    def step(state, x):
        outs = run(body, [*held, *state, *x])
        return tuple(outs[:carry]), tuple(outs[carry:])

    state, ys = jax.lax.scan(
        step,
        tuple(init),
        tuple(xs),
        length=bound["length"],
        reverse=bound["reverse"],
        unroll=bound["unroll"],
    )
    return [*state, *ys]


def _old_cond(run, bound, ins):
    refs = [item["graph"] for item in bound["branches"]]
    index, operands = ins[0], list(ins[1:])
    branches = [
        (lambda *ops, target=target: tuple(run(target, list(ops)))) for target in refs
    ]
    return list(jax.lax.switch(index, branches, *operands))


def _admitted():
    raw = json.loads(V8.read_bytes())
    raw["carbon_ops"]["while"][
        "default"
    ] = "allow"  # as test_level4_graph_ops_freedom does for while
    return allowlist_module.Allowlist(json.dumps(raw).encode())


def _doc(fn, args, allowlist):
    closed = lower_jax.trace(
        fn, *[jax.ShapeDtypeStruct(a.shape, a.dtype) for a in args]
    )
    doc = lower_jax.lower(
        closed,
        role="forward",
        allowlist=allowlist,
        input_names=[f"x{i}" for i in range(len(args))],
    )
    return graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )


def _bits(values):
    return [np.asarray(v).tobytes() for v in jax.tree_util.tree_leaves(values)]


def _f32(seed, shape):
    return jnp.asarray(
        np.random.default_rng(seed).uniform(-1.0, 1.0, size=shape).astype(np.float32)
    )


def _scan_fn(x, w):
    # w is an outer value, so it reaches the scan body as a const that changes with each call
    return lax.scan(
        lambda c, v: (c * w + v, jnp.tanh(c * w) + v), jnp.zeros((4,), jnp.float32), x
    )[1]


def _while_fn(x, w):
    return lax.while_loop(lambda c: c[0] < 3.0, lambda c: c * w + 0.25, x)


def _switch_fn(x, i, w):
    return lax.switch(
        i,
        [
            lambda v: v * w,
            lambda v: jnp.sin(v) + w,
            lambda v: v * v - w,
            lambda v: jnp.tanh(v * w),
        ],
        x,
    )


def test_scan_is_bit_equal_before_and_after_with_consts_that_change_per_call(
    monkeypatch,
):
    allowlist = allowlist_module.load(V8)
    args0 = (_f32(0, (50, 4)), _f32(1, (4,)))
    doc = _doc(_scan_fn, args0, allowlist)
    with monkeypatch.context() as m:
        m.setattr(
            interpret,
            "_while",
            lambda run, bound, ins, bodies, key: _old_while(run, bound, ins),
        )
        m.setattr(
            interpret,
            "_scan",
            lambda run, bound, ins, bodies, key: _old_scan(run, bound, ins),
        )
        m.setattr(
            interpret,
            "_cond",
            lambda run, bound, ins, bodies, key: _old_cond(run, bound, ins),
        )
        old = interpret.rebuild(doc, allowlist)
        calls = [args0, (_f32(2, (50, 4)), _f32(3, (4,))), args0]
        want = [
            (
                _bits(old(*a)),
                _bits(
                    jax.grad(lambda x, w: jnp.sum(old(x, w)[0] * 1.5), argnums=(0, 1))(
                        *a
                    )
                ),
            )
            for a in calls
        ]
    new = interpret.rebuild(doc, allowlist)
    for args, (values, grads) in zip(calls, want, strict=True):
        assert _bits(new(*args)) == values
        assert (
            _bits(
                jax.grad(lambda x, w: jnp.sum(new(x, w)[0] * 1.5), argnums=(0, 1))(
                    *args
                )
            )
            == grads
        )
    np.testing.assert_array_equal(
        np.asarray(new(*calls[1])[0]), np.asarray(_scan_fn(*calls[1]))
    )  # and JAX's own


def test_while_is_bit_equal_before_and_after_forward_and_jvp(monkeypatch):
    allowlist = _admitted()
    args0 = (jnp.asarray([0.5, 1.0, -0.5], jnp.float32), jnp.asarray(1.25, jnp.float32))
    doc = _doc(_while_fn, args0, allowlist)
    calls = [
        args0,
        (jnp.asarray([0.25, 2.0, 0.0], jnp.float32), jnp.asarray(1.5, jnp.float32)),
        args0,
    ]
    tangent = (jnp.ones((3,), jnp.float32), jnp.asarray(0.5, jnp.float32))
    with monkeypatch.context() as m:
        m.setattr(
            interpret,
            "_while",
            lambda run, bound, ins, bodies, key: _old_while(run, bound, ins),
        )
        old = interpret.rebuild(doc, allowlist)
        want = [
            (_bits(old(*a)), _bits(jax.jvp(lambda x, w: old(x, w)[0], a, tangent)))
            for a in calls
        ]
    new = interpret.rebuild(doc, allowlist)
    for args, (values, jvps) in zip(calls, want, strict=True):
        assert _bits(new(*args)) == values
        assert _bits(jax.jvp(lambda x, w: new(x, w)[0], args, tangent)) == jvps


def test_a_four_branch_cond_is_bit_equal_before_and_after_on_every_branch(monkeypatch):
    allowlist = allowlist_module.load(V8)
    x, w = _f32(4, (3, 4)), jnp.asarray(0.75, jnp.float32)
    doc = _doc(_switch_fn, (x, jnp.asarray(0, jnp.int32), w), allowlist)
    calls = [(x, jnp.asarray(i, jnp.int32), w) for i in (0, 1, 2, 3, 1, 3)]
    with monkeypatch.context() as m:
        m.setattr(
            interpret,
            "_cond",
            lambda run, bound, ins, bodies, key: _old_cond(run, bound, ins),
        )
        old = interpret.rebuild(doc, allowlist)
        want = [
            (
                _bits(old(*a)),
                _bits(
                    jax.grad(lambda x, i, w: jnp.sum(old(x, i, w)[0]), argnums=(0, 2))(
                        *a
                    )
                ),
            )
            for a in calls
        ]
    new = interpret.rebuild(doc, allowlist)
    for args, (values, grads) in zip(calls, want, strict=True):
        assert _bits(new(*args)) == values
        assert (
            _bits(
                jax.grad(lambda x, i, w: jnp.sum(new(x, i, w)[0]), argnums=(0, 2))(
                    *args
                )
            )
            == grads
        )


def _traced(monkeypatch, fn, args):
    """How many nested-graph runs one call makes (interpret's `run` checks every input's dtype: `_dtype_name` counts)."""
    count = [0]
    real = interpret._dtype_name

    def counting(value):
        count[0] += 1
        return real(value)

    monkeypatch.setattr(interpret, "_dtype_name", counting)
    fn(*args)
    monkeypatch.setattr(interpret, "_dtype_name", real)
    return count[0]


@pytest.mark.parametrize(
    "case",
    ["scan500", "while", "cond"],
)
def test_the_loop_bodies_are_traced_on_the_first_call_only(monkeypatch, case):
    if case == "scan500":
        allowlist, fn = allowlist_module.load(V8), _scan_fn
        calls = [(_f32(5, (500, 4)), _f32(6, (4,))), (_f32(7, (500, 4)), _f32(8, (4,)))]
    elif case == "while":
        allowlist, fn = _admitted(), _while_fn
        calls = [(jnp.asarray([0.5, 1.0, -0.5], jnp.float32), jnp.asarray(1.25, jnp.float32)),
                 (jnp.asarray([0.25, 2.0, 0.0], jnp.float32), jnp.asarray(1.5, jnp.float32))]  # fmt: skip
    else:
        allowlist, fn = allowlist_module.load(V8), _switch_fn
        x, w = _f32(9, (3, 4)), jnp.asarray(0.5, jnp.float32)
        calls = [(x, jnp.asarray(2, jnp.int32), w), (x, jnp.asarray(1, jnp.int32), w)]
    run = interpret.rebuild(_doc(fn, calls[0], allowlist), allowlist)
    first = _traced(monkeypatch, run, calls[0])
    second = _traced(monkeypatch, run, calls[1])
    third = _traced(monkeypatch, run, calls[0])
    assert (
        second == third < first
    )  # the bodies ran in Python on the first call only; later calls replay JAX's trace
    # the earlier interpreter traced them on every call
    with monkeypatch.context() as m:
        m.setattr(
            interpret,
            "_while",
            lambda run, bound, ins, bodies, key: _old_while(run, bound, ins),
        )
        m.setattr(
            interpret,
            "_scan",
            lambda run, bound, ins, bodies, key: _old_scan(run, bound, ins),
        )
        m.setattr(
            interpret,
            "_cond",
            lambda run, bound, ins, bodies, key: _old_cond(run, bound, ins),
        )
        old = interpret.rebuild(_doc(fn, calls[0], allowlist), allowlist)
        old_first = _traced(m, old, calls[0])
        assert _traced(m, old, calls[1]) == old_first
