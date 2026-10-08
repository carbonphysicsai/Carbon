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


# --- One specimen per attack row (proposal §8.1 and §8.3) ---------------------

#: Caps for the cap-gated specimens ONLY: small enough that the specimen
#: crosses one, generous enough that the honest control passes. These are
#: test fixtures, NOT values for any Challenge; every real cap stays
#: HUMAN_INPUT (`allowlist.CAPS`).
FIXTURE_CAPS = {
    "constant_bytes": 4096,
    "nodes_executed": 10**6,
    "call_depth": 8,
    "document_bytes": 10**8,
    "largest_intermediate_bytes": 10**9,
}


def _program(fn, args, role="forward"):
    return ("program", (fn, args, role))


def _swapped(op):
    """A Carbon-side document whose one op a hostile miner replaced."""
    return ("document_op", op)


def _recorded(owner):
    return ("recorded", owner)


def _attack_rows():
    import jax
    import jax.numpy as jnp
    import numpy as np
    from jax import lax

    x = _x()
    shape = jax.ShapeDtypeStruct(x.shape, x.dtype)
    asset = np.linspace(0.0, 1.0, 4096, dtype=np.float32)  # 16 KB "weights file"
    pieces = [np.float32(i) for i in range(2048)]
    wrapped = jnp.zeros(2, jnp.uint32)

    def callback(v):
        return jax.pure_callback(lambda a: a, shape, v)

    @jax.custom_jvp
    def hidden(v):
        return callback(v)

    hidden.defjvp(lambda p, t: (hidden(*p), t[0]))

    def loaded(v):
        return v + jnp.asarray(asset)[: v.shape[1]]

    def split(v):
        total = v
        for piece in pieces:
            total = total + piece
        return total

    def nested(v, depth=12):
        f = lambda a: a + 1.0
        for _ in range(depth):
            f = jax.jit(lambda a, _f=f: _f(a) * 1.0)
        return f(v)

    def procedural(v):
        return v + jnp.sin(jnp.arange(v.shape[1], dtype=v.dtype) * 3.7)

    def residue(key):
        return [jax.random.normal(key, (2,)), jnp.asarray(asset[:8])]

    def fixed_weights(key):
        return [jax.random.normal(key, (2,)), jnp.cos(jnp.arange(8.0))]

    def widened(v):
        return jnp.concatenate([v, v[:, :1] * 1e-7], axis=1)

    def gathered(v):
        return jnp.take_along_axis(v, jnp.argsort(v, axis=1), axis=1)

    rng = jax.random.wrap_key_data
    return [
        (
            "8.1",
            "Network access, undeclared dependencies",
            "io_callback node",
            _swapped("io_callback"),
            "op_refused",
        ),
        (
            "8.1",
            "Model loaders, hidden assets",
            "a loaded weights file as one constant",
            _program(loaded, (x,)),
            "cap_exceeded:constant_bytes",
        ),
        (
            "8.1",
            "Embedded weights or tables",
            "a table split into 2,048 scalars",
            _program(split, (x,)),
            "cap_exceeded:constant_bytes",
        ),
        (
            "8.1",
            "Child processes, resource escapes",
            "ffi_call node",
            _swapped("ffi_call"),
            "op_refused",
        ),
        (
            "8.1",
            "Caches, checkpoints, cross-attempt residue",
            "init returning a stored table",
            _program(residue, (jax.random.PRNGKey(0),), "init"),
            "init_output_not_keyed",
        ),
        (
            "8.1",
            "Run identification, timing feedback",
            "RNG in the forward graph",
            _program(lambda v: v + jax.random.normal(rng(wrapped), v.shape), (x,)),
            "op_not_allowed_in_role",
        ),
        (
            "8.1",
            "Construction-to-evaluator access, answer-key exfiltration",
            "custom_call node",
            _swapped("custom_call"),
            "op_refused",
        ),
        (
            "8.1",
            "Hidden preprocessing, inference/solver hybrids",
            "pure_callback wrapping a solver",
            _program(callback, (x,)),
            "op_refused",
        ),
        (
            "8.1",
            "Malformed outputs, nonfinite values, parser abuse",
            "nesting bomb document",
            ("raw", b'{"schema":' + b"[" * 40 + b"]" * 40 + b"}"),
            "json_strategy_nesting_too_deep",
        ),
        (
            "8.1",
            "Malformed outputs, nonfinite values (outputs)",
            "NaN on selected cases",
            _recorded(
                "G7: the exam's gates type the cases "
                "(tests/cpu/test_level4_grade.py)"
            ),
            None,
        ),
        (
            "8.3",
            "Callback smuggling",
            "pure_callback inside custom_jvp",
            _program(hidden, (x,)),
            "op_refused",
        ),
        (
            "8.3",
            "Constant splitting",
            "the same table spread across nested calls",
            _program(lambda v: jax.jit(split)(v), (x,)),
            "cap_exceeded:constant_bytes",
        ),
        (
            "8.3",
            "Procedural tables",
            "iota arithmetic regenerating a table",
            _program(procedural, (x,)),
            "not_refused",
        ),
        (
            "8.3",
            "Unbounded loop",
            "data-dependent while",
            _program(
                lambda v: lax.while_loop(
                    lambda a: a.sum() < 100.0, lambda a: a * 2.0, v
                ),
                (x,),
            ),
            "op_refused",
        ),
        (
            "8.3",
            "Compute under-counting",
            "denormal- or gather-heavy graph",
            _recorded("R6/R7, plan Phase 4"),
            None,
        ),
        (
            "8.3",
            "Compile bomb",
            "calls nested 12 deep",
            _program(nested, (x,)),
            "cap_exceeded:call_depth",
        ),
        (
            "8.3",
            "Compiler exploit",
            "a crafted XLA bug trigger",
            _recorded(
                "G5 isolation: accepted for development and testnet "
                "(OWNER-L4-G5-COMPILE-ISOLATION-01); mainnet security review"
            ),
            None,
        ),
        (
            "8.3",
            "Trace-time divergence",
            "code that differs when traced",
            _recorded("not applicable on Carbon hosts: only the graph is trained"),
            None,
        ),
        (
            "8.3",
            "Nondeterminism",
            "gather and sort (scatter-add gradient on GPU)",
            _program(gathered, (x,)),
            "review_flagged",
        ),
        (
            "8.3",
            "RNG leakage",
            "keyed RNG in the loss",
            _program(
                lambda v: jnp.sum(v * jax.random.uniform(rng(wrapped), v.shape)),
                (x,),
                "loss",
            ),
            "op_not_allowed_in_role",
        ),
        (
            "8.3",
            "Interface abuse",
            "an extra output column carrying signal",
            ("interface", widened),
            "interface_shape",
        ),
        (
            "8.3",
            "Initializer abuse",
            "init building fixed weights without the key",
            _program(fixed_weights, (jax.random.PRNGKey(0),), "init"),
            "init_output_not_keyed",
        ),
        (
            "control",
            "Honest graph",
            "tanh(x @ w) under the fixture caps",
            ("honest", None),
            "admitted",
        ),
    ]


def _observe(kind, payload, allowlist, max_bytes):
    """The code a specimen produces at Carbon's gates (G3, G4)."""
    import jax.numpy as jnp

    from . import validate

    try:
        if kind == "program":
            fn, args, role = payload
            closed = lower_jax.trace(fn, *args)
            names = (
                ["carbon/key"]
                if role == "init"
                else [f"inputs/{i}" for i in range(len(closed.jaxpr.invars))]
            )
            doc = lower_jax.lower(
                closed, role=role, allowlist=allowlist, input_names=names
            )
            raw = graph.dumps(doc)
        elif kind == "document_op":
            doc = _small_document(allowlist)
            node = next(n for n in doc["graphs"]["main"]["nodes"] if n["op"] == "tanh")
            node.update(op=payload, params={})
            raw = graph.dumps(doc)
        elif kind == "raw":
            raw = payload
        elif kind == "interface":
            from .tooling import through_bprime

            _, doc, raw = through_bprime(
                payload,
                (_x(),),
                role="forward",
                allowlist=allowlist,
                input_names=["inputs/x"],
                max_bytes=max_bytes,
            )
            interface = validate.Interface(
                inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (3,)),)
            )
            validate.validate(
                graph.parse(raw, max_bytes=max_bytes), allowlist, interface=interface
            )
            return "not_refused"
        else:  # honest control
            raw = graph.dumps(_small_document(allowlist))
        doc = graph.parse(raw, max_bytes=max_bytes)
        verdict = validate.validate(doc, allowlist, caps=FIXTURE_CAPS)
        if kind == "honest":
            interpret.rebuild(doc, allowlist)(jnp.ones((3, 2), jnp.float32), _x())
            return verdict["status"]
        if verdict["review_flags"]:
            return "review_flagged"
        return "not_refused"
    except graph.GraphRefused as refused:
        if refused.code == "cap_exceeded":
            return f"cap_exceeded:{refused.where}"
        return refused.code


def attack_suite(allowlist, *, max_bytes):
    """One row per attack family: what was tried, the gate, the code seen.
    `recorded` rows name the owner of a family no graph gate can test."""
    rows = []
    for section, family, specimen, (kind, payload), expected in _attack_rows():
        if kind == "recorded":
            rows.append(
                {
                    "section": section,
                    "family": family,
                    "specimen": specimen,
                    "status": "recorded",
                    "owner": payload,
                }
            )
            continue
        observed = _observe(kind, payload, allowlist, max_bytes)
        rows.append(
            {
                "section": section,
                "family": family,
                "specimen": specimen,
                "expected": expected,
                "observed": observed,
                "status": "pass" if observed == expected else "FINDING",
            }
        )
    return rows
