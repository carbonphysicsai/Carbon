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
import re

from .. import graph, named, params

CALL_OPS = graph.CALL_OPS
_TYPE_LABEL = re.compile(r"[A-Za-z0-9_.]{1,160}\Z")


def _safe_type_label(value):
    """Class identity for a private refusal, never an object's repr or value."""
    kind = type(value)
    label = f"{kind.__module__}.{kind.__qualname__}"
    return label if _TYPE_LABEL.fullmatch(label) else "unrecognized"


def wide(args):
    """Whether any leaf of `args` is declared float64."""
    import jax
    import numpy as np

    return any(
        getattr(leaf, "dtype", None) is not None and np.dtype(leaf.dtype) == np.float64
        for leaf in jax.tree_util.tree_leaves(args)
    )


def trace(fn, *args):
    """The closed jaxpr of `fn` at `args` (arrays or `jax.ShapeDtypeStruct`).

    A float64 argument traces with x64 on, so a graph keeps the precision it
    declares: with JAX's default (x64 off) float64 inputs lowered as float32
    and the interface then refused them (miner report, 19 Oct). Otherwise the
    caller's own x64 setting is left as it is."""
    import jax

    if wide(args):
        with jax.enable_x64(True):
            return jax.make_jaxpr(fn)(*args)
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
        if jaxpr.effects:
            raise graph.GraphRefused("op_refused", name)
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
            # JAX hyphenates some primitive names (scatter-add); the allowlist
            # names them with underscores.
            op = eqn.primitive.name.replace("-", "_")
            kernel = None
            if op == "custom_jvp_call" and allowlist.named:
                kernel = named.recognize(eqn, allowlist)
            if kernel is not None:
                # A registered kernel: one node; Carbon supplies its rule.
                allowlist.admit("named_function", role, where)
                allowlist.admit_named(kernel, role, where)
                op, encoded = "named_function", {"name": kernel}
            else:
                spec = allowlist.admit(op, role, where)
                eqn_params = eqn.params
                if op == "custom_jvp_call":
                    # A derivative rule JAX holds as a Python callable is traced to a
                    # jaxpr here, on the miner's machine, and carried as a nested
                    # graph that Carbon validates like any other (pure ops only).
                    import jax.extend.core as jex_core

                    n_args = len(eqn.invars) - eqn.params["num_consts"]
                    jvp_jaxpr, jvp_consts, out_zeros = eqn.params[
                        "jvp_jaxpr_fun"
                    ].call_wrapped(*([False] * n_args))
                    eqn_params = {
                        "call_jaxpr": eqn.params["call_jaxpr"],
                        "jvp_jaxpr": jex_core.ClosedJaxpr(jvp_jaxpr, jvp_consts),
                        "num_consts": eqn.params["num_consts"],
                        "out_zeros": tuple(bool(z) for z in out_zeros),
                        "symbolic_zeros": eqn.params["symbolic_zeros"],
                    }
                if op == "custom_linear_solve":
                    # jnp.linalg.solve / inv: the four callables of the solve, each
                    # a nested graph, beside the lengths of their closed-over values.
                    jaxprs = eqn_params["jaxprs"]
                    eqn_params = {
                        "const_lengths": tuple(eqn_params["const_lengths"]),
                        "matvec": jaxprs.matvec,
                        "vecmat": jaxprs.vecmat,
                        "solve": jaxprs.solve,
                        "transpose_solve": jaxprs.transpose_solve,
                    }
                try:
                    encoded = params.encode(spec, eqn_params, lower_graph)
                except graph.GraphRefused as refused:
                    if (
                        refused.code == "parameter_not_default"
                        and refused.where == "parameter sharding"
                    ):
                        # Keep this context safe even if a caller surfaces the
                        # refusal: no placement identity, tensor value or repr.
                        label = _safe_type_label(eqn.params["sharding"])
                        raise graph.GraphRefused(
                            refused.code,
                            f"{where} op {op} parameter sharding type {label}",
                        ) from None
                    raise
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
