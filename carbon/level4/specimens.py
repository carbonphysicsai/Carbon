"""Known-vulnerable specimens for the spike's gates (Challenge-neutral).

Each specimen is a small synthetic program or a tampered graph document; the
gate it must hit is named with it. These are the spike's seed of the Phase 1
suite (proposal §8.1, §8.3), not the suite itself.
"""

from __future__ import annotations

import copy
import json

from . import graph, interpret
from .tooling import lower_jax


def _x():
    import jax.numpy as jnp

    return jnp.ones((4, 3), jnp.float32)


def program_specimens():
    """`(label, fn, args, role, expected code)` refused at lowering (G4)."""
    import jax
    import jax.numpy as jnp
    from jax import lax
    from jax.experimental import io_callback

    x = _x()
    shape = jax.ShapeDtypeStruct(x.shape, x.dtype)

    def pure(v):
        return jax.pure_callback(lambda a: a, shape, v)

    @jax.custom_jvp
    def hidden(v):
        return pure(v)

    hidden.defjvp(lambda primals, tangents: (hidden(*primals), tangents[0]))

    @jax.custom_vjp
    def own_rule(v):
        return v * 2.0

    own_rule.defvjp(lambda v: (v * 2.0, None), lambda _, g: (g * 2.0,))

    flagged = jax.jit(
        lambda v: v + 1.0, compiler_options={"xla_cpu_enable_fast_math": True}
    )
    return [
        ("callback: pure_callback", pure, (x,), "forward", "op_refused"),
        (
            "callback: io_callback",
            lambda v: io_callback(lambda a: a, shape, v),
            (x,),
            "forward",
            "op_refused",
        ),
        (
            "callback: debug print",
            lambda v: (jax.debug.print("{}", v), v + 1.0)[1],
            (x,),
            "forward",
            "op_refused",
        ),
        (
            "callback nested in jit",
            jax.jit(lambda v: pure(v) + 1.0),
            (x,),
            "forward",
            "op_refused",
        ),
        ("callback inside custom_jvp", hidden, (x,), "forward", "op_refused"),
        (
            "unbounded while loop",
            lambda v: lax.while_loop(lambda a: a.sum() < 100.0, lambda a: a * 2.0, v),
            (x,),
            "forward",
            "op_refused",
        ),
        (
            "RNG seeded inside the graph",
            lambda v: v + jax.random.normal(jax.random.PRNGKey(0), v.shape),
            (x,),
            "forward",
            "op_refused",
        ),
        (
            "RNG from a wrapped key in inference",
            lambda v: v
            + jax.random.normal(
                jax.random.wrap_key_data(jnp.zeros(2, jnp.uint32)), v.shape
            ),
            (x,),
            "forward",
            "op_not_allowed_in_role",
        ),
        (
            "RNG from a wrapped key in the loss",
            lambda v: jnp.sum(
                v
                * jax.random.uniform(
                    jax.random.wrap_key_data(jnp.zeros(2, jnp.uint32)), v.shape
                )
            ),
            (x,),
            "loss",
            "op_not_allowed_in_role",
        ),
        ("custom_vjp rule", own_rule, (x,), "forward", "op_not_supported_v0"),
        (
            "stop_gradient",
            lambda v: lax.stop_gradient(v) * v,
            (x,),
            "forward",
            "op_not_supported_v0",
        ),
        (
            "static scan (not yet in v0)",
            lambda v: lax.fori_loop(0, 3, lambda i, a: a + 1.0, v),
            (x,),
            "forward",
            "op_not_supported_v0",
        ),
        (
            "nested jit with compiler options",
            lambda v: flagged(v) * 2.0,
            (x,),
            "forward",
            "framework_refused",
        ),
    ]


def constant_specimens():
    """Constants are measured, never capped here: the caps are HUMAN_INPUT."""
    import jax.numpy as jnp
    import numpy as np

    table = np.arange(4096, dtype=np.float32)
    pieces = [np.full((), float(i), np.float32) for i in range(512)]

    def one_table(v):
        return v + jnp.asarray(table)[: v.shape[1]]

    def split_table(v):
        total = v
        for piece in pieces:
            total = total + piece
        return total

    return [("embedded table", one_table), ("table split into scalars", split_table)]


def _small_document(allowlist):
    import jax.numpy as jnp

    x = _x()
    w = jnp.ones((3, 2), jnp.float32)
    # linspace brings a nested `jit` call into the document.
    closed = lower_jax.trace(
        lambda a, b: jnp.tanh(b @ a) * jnp.linspace(0.0, 1.0, 2), w, x
    )
    return lower_jax.lower(
        closed,
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", "inputs/x"],
    )


def document_specimens(allowlist):
    """`(label, raw bytes, expected code)`: tampered B' documents."""
    base = _small_document(allowlist)
    raw = graph.dumps(base)
    out = []

    def add(label, mutate, code):
        doc = copy.deepcopy(base)
        mutate(doc)
        out.append((label, graph.dumps(doc), code))

    main = "main"
    nodes = lambda d: d["graphs"][main]["nodes"]
    tanh = next(
        i for i, n in enumerate(base["graphs"][main]["nodes"]) if n["op"] == "tanh"
    )

    out.append(
        (
            "duplicate key",
            raw.replace(b'{"allowlist"', b'{"role":"forward","allowlist"', 1),
            "json_duplicate_key",
        )
    )
    out.append(
        (
            "non-finite number",
            raw.replace(b'"outputs":[', b'"outputs":[NaN,', 1),
            "json_non_finite_value",
        )
    )
    out.append(
        (
            "nesting bomb",
            b'{"schema":' + b"[" * 40 + b"]" * 40 + b"}",
            "json_strategy_nesting_too_deep",
        )
    )
    out.append(("not JSON", raw[:-1], "json_strategy_not_json"))
    add(
        "unknown op",
        lambda d: nodes(d)[tanh].update(op="totally_new_op"),
        "op_not_allowlisted",
    )
    add(
        "op swapped for a callback",
        lambda d: nodes(d)[tanh].update(op="pure_callback", params={}),
        "op_refused",
    )
    add(
        "extra parameter",
        lambda d: nodes(d)[tanh]["params"].update(sneaky=1),
        "parameters_not_allowlisted",
    )
    add(
        "non-default parameter",
        lambda d: nodes(d)[tanh]["params"].update(accuracy=3),
        "parameter_not_default",
    )
    add(
        "constant byte count lie",
        lambda d: d["graphs"][main]["constants"].append(
            {
                "value": 999,
                "dtype": "float32",
                "shape": [2],
                "bytes": 4,
                "data": "AAAAAA==",
            }
        ),
        "constant_bytes_mismatch",
    )
    add(
        "value used before definition",
        lambda d: nodes(d)[0]["in"].append(10_000),
        "value_undefined",
    )
    add(
        "key dtype in a forward graph",
        lambda d: d["graphs"][main]["inputs"][0].update(dtype="key<fry>", shape=[]),
        "key_dtype_outside_init",
    )
    add(
        "allowlist version mismatch",
        lambda d: d.update(allowlist="level4-allowlist-v999"),
        "allowlist_version_mismatch",
    )

    def cycle(d):
        d["graphs"]["g1"] = {
            "inputs": [],
            "constants": [],
            "nodes": [
                {"op": "jit", "in": [], "out": [], "params": {"jaxpr": {"graph": "g1"}}}
            ],
            "outputs": [],
        }
        nodes(d).append(
            {"op": "jit", "in": [], "out": [], "params": {"jaxpr": {"graph": "g1"}}}
        )

    add("call cycle", cycle, "graph_call_cycle")

    def options(d):
        for g in d["graphs"].values():
            for node in g["nodes"]:
                if node["op"] == "jit":
                    node["params"]["compiler_options_kvs"] = [
                        ["xla_cpu_enable_fast_math", "true"]
                    ]

    add("compiler options smuggled into a call", options, "parameter_not_default")
    add(
        "declared shape lie",
        lambda d: nodes(d)[tanh]["out"][0].update(shape=[4, 3]),
        "declared_aval_mismatch",
    )
    return out


def run_documents(allowlist, max_bytes):
    """Each tampered document's observed refusal code (None = accepted)."""
    import jax.numpy as jnp

    results = []
    for label, raw, expected in document_specimens(allowlist):
        observed = None
        try:
            doc = graph.parse(raw, max_bytes=max_bytes)
            fn = interpret.rebuild(doc, allowlist)
            fn(jnp.ones((3, 2), jnp.float32), _x())
        except graph.GraphRefused as refused:
            observed = refused.code
        results.append({"specimen": label, "expected": expected, "observed": observed})
    return results


def run_programs(allowlist):
    results = []
    for label, fn, args, role, expected in program_specimens():
        observed = None
        try:
            closed = lower_jax.trace(fn, *args)
        except Exception:  # noqa: BLE001 - the framework refused before Carbon saw it
            observed = "framework_refused"
        else:
            names = [f"inputs/{i}" for i in range(len(closed.jaxpr.invars))]
            try:
                lower_jax.lower(
                    closed, role=role, allowlist=allowlist, input_names=names
                )
            except graph.GraphRefused as refused:
                observed = refused.code
        results.append({"specimen": label, "expected": expected, "observed": observed})
    return results


def run_constants(allowlist):
    from . import allowlist as allowlist_module

    out = []
    for label, fn in constant_specimens():
        closed = lower_jax.trace(fn, _x())
        doc = lower_jax.lower(
            closed, role="forward", allowlist=allowlist, input_names=["inputs/x"]
        )
        m = graph.measure(doc)
        out.append(
            {
                "specimen": label,
                "constant_count": m["constant_count"],
                "constant_bytes": m["constant_bytes"],
                "caps": allowlist_module.check_caps(m),
            }
        )
    return out


def summary(results):
    return json.dumps(
        [r for r in results if r["expected"] != r["observed"]], sort_keys=True
    )
