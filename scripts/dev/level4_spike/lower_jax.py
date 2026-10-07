"""Lower a traced JAX program (a closed jaxpr) into the Carbon graph format.

In B' this runs on the miner's machine (Launchpad tooling): Carbon's hosts
only ever parse the JSON it writes. Lowering refuses, with a typed code, any
primitive the allowlist does not admit for the graph's role, any parameter
outside its declared kind, and any symbolic (dynamic) shape.

`inventory` is the Phase 0 survey tool: it walks every nested jaxpr and
counts primitives, with no allowlist involved.
"""

from __future__ import annotations

import collections

from . import graph, params

#: Ops whose parameter of kind "graph" is evaluated inline as a nested graph.
CALL_OPS = ("jit", "closed_call", "custom_jvp_call")


def trace(fn, *args):
    """The closed jaxpr of `fn` at `args` (arrays or `jax.ShapeDtypeStruct`)."""
    import jax

    return jax.make_jaxpr(fn)(*args)


def _subjaxprs(value):
    from jax.extend.core import ClosedJaxpr, Jaxpr

    if isinstance(value, ClosedJaxpr | Jaxpr):
        yield value
    elif isinstance(value, tuple | list):
        for item in value:
            yield from _subjaxprs(item)


def inventory(closed):
    """Primitive counts over a jaxpr and every jaxpr nested in its parameters,
    with each primitive's parameter names and the deepest nesting seen."""
    counts = collections.Counter()
    names = collections.defaultdict(set)
    deepest = [1]

    def walk(jaxpr, depth):
        deepest[0] = max(deepest[0], depth)
        jaxpr = getattr(jaxpr, "jaxpr", jaxpr)
        for eqn in jaxpr.eqns:
            counts[eqn.primitive.name] += 1
            names[eqn.primitive.name] |= set(eqn.params)
            for value in eqn.params.values():
                for sub in _subjaxprs(value):
                    walk(sub, depth + 1)

    walk(closed, 1)
    return {
        "primitives": dict(sorted(counts.items())),
        "parameters": {k: sorted(v) for k, v in sorted(names.items())},
        "nesting_depth": deepest[0],
    }


def _aval(aval, where):
    shape = []
    for d in aval.shape:
        if type(d) is not int:
            raise graph.GraphRefused("dynamic_shape", where)
        shape.append(d)
    dtype = str(aval.dtype)
    graph.itemsize(dtype)  # refuses dtypes the format cannot carry
    return {"dtype": dtype, "shape": shape}


def lower(closed, *, role, allowlist, input_names):
    """The Carbon graph document for `closed`, or `GraphRefused`."""
    import numpy as np
    from jax.extend.core import ClosedJaxpr, Literal

    if role not in graph.ROLES:
        raise graph.GraphRefused("role_unknown")
    graphs, names = {}, {}

    def lower_graph(sub, entry_names=None):
        key = id(sub)
        if key in names:
            return names[key]
        name = "main" if not graphs and entry_names is not None else f"g{len(graphs)}"
        names[key] = name
        graphs[name] = None  # reserved: keeps names stable under recursion
        if isinstance(sub, ClosedJaxpr):
            jaxpr, consts = sub.jaxpr, sub.consts
        else:
            jaxpr, consts = sub, []
            if jaxpr.constvars:
                raise graph.GraphRefused("open_constants", name)
        ids = {}
        counter = iter(range(1 << 62))

        def new(var):
            ids[var] = next(counter)
            return ids[var]

        inputs, constants, nodes = [], [], []
        for var, value in zip(jaxpr.constvars, consts):
            constants.append(
                {"value": new(var), **graph.encode_array(np.asarray(value))}
            )
        for i, var in enumerate(jaxpr.invars):
            label = entry_names[i] if entry_names is not None else f"arg{i}"
            inputs.append({"value": new(var), "name": label, **_aval(var.aval, name)})

        def use(atom):
            if isinstance(atom, Literal):
                array = np.asarray(atom.val, dtype=atom.aval.dtype)
                value = next(counter)
                constants.append({"value": value, **graph.encode_array(array)})
                return value
            return ids[atom]

        for i, eqn in enumerate(jaxpr.eqns):
            where = f"{name}.nodes[{i}]"
            op = eqn.primitive.name
            spec = allowlist.admit(op, role, where)
            encoded = params.encode(spec, eqn.params, lower_graph)
            ins = [use(a) for a in eqn.invars]
            outs = [{"value": new(v), **_aval(v.aval, where)} for v in eqn.outvars]
            nodes.append({"op": op, "in": ins, "out": outs, "params": encoded})
        outputs = [use(a) for a in jaxpr.outvars]
        graphs[name] = {
            "inputs": inputs,
            "constants": constants,
            "nodes": nodes,
            "outputs": outputs,
        }
        return name

    if len(input_names) != len(closed.jaxpr.invars):
        raise graph.GraphRefused("input_names_mismatch")
    lower_graph(closed, list(input_names))
    doc = {
        "schema": graph.SCHEMA,
        "allowlist": allowlist.version,
        "role": role,
        "entry": "main",
        "graphs": graphs,
    }
    graph.prune(doc)
    graph.check_structure(doc)
    return doc
