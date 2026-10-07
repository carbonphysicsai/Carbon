"""Rebuild a JAX function from a Carbon graph (B'), then let Carbon's own
autodiff differentiate it.

Each allowlisted node maps to a primitive Carbon chose in `_PRIMITIVES`,
bound with parameters decoded through the allowlist's kinds. Nested calls are
evaluated inline. Every result's dtype and shape is checked against the
node's declaration, so measurements taken from declared shapes are the shapes
that run. Nothing here imports, unpickles or executes miner-supplied code.
"""

from __future__ import annotations

from . import graph, named, params
from .lower_jax import CALL_OPS


def _primitives():
    import jax.extend.core.primitives as public

    # Typed-key wrapping has no public handle in the pinned JAX.
    from jax._src.random import prng

    table = {}
    for name in dir(public):
        if name.endswith("_p"):
            primitive = getattr(public, name)
            table[primitive.name] = primitive
    table["random_wrap"] = prng.random_wrap_p
    table["random_unwrap"] = prng.random_unwrap_p
    return table


_PRIMITIVES = None


def _dtype_name(x):
    return str(x.dtype)


def rebuild(doc, allowlist):
    """`fn(*inputs) -> list of outputs` for a validated document.

    G4 (`allowlist.check`) runs first; a refused document never yields a
    function."""
    global _PRIMITIVES
    if _PRIMITIVES is None:
        _PRIMITIVES = _primitives()
    allowlist.check(doc)
    graphs = doc["graphs"]
    decoded = {
        name: [
            params.decode(allowlist.ops[n["op"]]["params"], n["params"])
            for n in g["nodes"]
        ]
        for name, g in graphs.items()
    }
    constants = {
        name: {c["value"]: graph.decode_array(c, name) for c in g["constants"]}
        for name, g in graphs.items()
    }

    def run(name, args):
        g = graphs[name]
        if len(args) != len(g["inputs"]):
            raise graph.GraphRefused("arity_mismatch", name)
        env = dict(constants[name])
        for entry, value in zip(g["inputs"], args):
            if (
                list(value.shape) != entry["shape"]
                or _dtype_name(value) != entry["dtype"]
            ):
                raise graph.GraphRefused("input_aval_mismatch", name)
            env[entry["value"]] = value
        for i, (node, bound) in enumerate(zip(g["nodes"], decoded[name])):
            ins = [env[v] for v in node["in"]]
            if node["op"] in CALL_OPS:
                ref = next(iter(graph.graph_refs(node["params"])))
                outs = run(ref, ins)
            elif node["op"] == "named_function":
                outs = named.call(bound["name"], ins)
            else:
                primitive = _PRIMITIVES[node["op"]]
                out = primitive.bind(*ins, **bound)
                outs = list(out) if primitive.multiple_results else [out]
            if len(outs) != len(node["out"]):
                raise graph.GraphRefused("result_count_mismatch", f"{name}.nodes[{i}]")
            for value, declared in zip(outs, node["out"]):
                if (
                    list(value.shape) != declared["shape"]
                    or _dtype_name(value) != declared["dtype"]
                ):
                    raise graph.GraphRefused(
                        "declared_aval_mismatch", f"{name}.nodes[{i}]"
                    )
                env[declared["value"]] = value
        return [env[v] for v in g["outputs"]]

    def fn(*inputs):
        return run(doc["entry"], list(inputs))

    return fn


def through_bprime(fn, example_args, *, role, allowlist, input_names, max_bytes):
    """Lower `fn` at `example_args`, write the canonical JSON bytes, parse
    them back with the strict parser and rebuild: the whole B' round trip.

    Returns `(rebuilt(*flat_inputs) -> list, document, raw_bytes)`."""
    import jax

    from . import lower_jax

    flat, _ = jax.tree_util.tree_flatten(example_args)

    def flat_fn(*leaves):
        args = jax.tree_util.tree_unflatten(
            jax.tree_util.tree_structure(example_args), leaves
        )
        return fn(*args)

    closed = lower_jax.trace(flat_fn, *flat)
    doc = lower_jax.lower(
        closed, role=role, allowlist=allowlist, input_names=input_names
    )
    raw = graph.dumps(doc)
    parsed = graph.parse(raw, max_bytes=max_bytes)
    return rebuild(parsed, allowlist), parsed, raw
