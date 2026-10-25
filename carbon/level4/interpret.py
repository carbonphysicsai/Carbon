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
from .graph import CALL_OPS


def _primitives():
    import jax.extend.core.primitives as public

    # Typed-key wrapping has no public handle in the pinned JAX.
    from jax._src.lax import lax as lax_internal
    from jax._src.random import prng

    table = {}
    for name in dir(public):
        if name.endswith("_p"):
            primitive = getattr(public, name)
            table[primitive.name] = primitive
    # `lax.split` has no public primitive handle in the pinned JAX either.
    table["split"] = lax_internal.split_p
    # `jnp.stack` / `jnp.unstack` bind these; no public handle either.
    table["stack"] = lax_internal.stack_p
    table["unstack"] = lax_internal.unstack_p
    # Primitives JAX does not re-export publicly (the pivot permutation, tile, ...):
    # a lookup only; what a graph may bind is the allowlist's decision.
    import importlib
    import pkgutil

    from jax._src import lax as lax_package
    from jax.extend.core import Primitive

    for info in pkgutil.walk_packages(lax_package.__path__, "jax._src.lax."):
        try:
            module = importlib.import_module(info.name)
        except ImportError:
            continue
        for name in dir(module):
            value = getattr(module, name, None)
            if name.endswith("_p") and isinstance(value, Primitive):
                table.setdefault(value.name, value)
    # The allowlist names ops with underscores where JAX hyphenates (scatter-add):
    # every hyphenated primitive is also bound under its underscore name.
    for name, primitive in list(table.items()):
        if "-" in name:
            table.setdefault(name.replace("-", "_"), primitive)
    table["random_wrap"] = prng.random_wrap_p
    table["random_unwrap"] = prng.random_unwrap_p
    return table


_PRIMITIVES = None


def _dtype_name(x):
    return str(x.dtype)


def _custom_vjp(run, bound, ins):
    """`jax.custom_vjp` over three nested graphs: the function, its forward rule
    (arguments in; the residuals JAX did not simply forward, then the primal outputs,
    out) and its backward rule (residuals then output cotangents in; one cotangent per
    argument out). Reverse mode only, as the rule is."""
    import jax
    import jax.numpy as jnp

    consts = bound["num_consts"]
    function = bound["call_jaxpr"]["graph"]
    forward = bound["fwd_jaxpr"]["graph"]
    backward = bound["bwd_jaxpr"]["graph"]
    fwds, n_out = bound["fwds"], bound["n_out"]
    if consts < 0 or consts > len(ins) or n_out < 0:
        raise graph.GraphRefused("parameter_kind_mismatch")

    @jax.custom_vjp
    def call(*args):
        return tuple(run(function, list(args)))

    def fwd(*args):
        outs = run(forward, list(args[consts:]))
        if n_out > len(outs):
            raise graph.GraphRefused("result_count_mismatch")
        pruned, primals = iter(outs[: len(outs) - n_out]), outs[len(outs) - n_out :]
        residuals = tuple(
            args[consts + index] if index is not None else next(pruned)
            for index in fwds
        )
        return tuple(primals), residuals

    def bwd(residuals, cotangents):
        cts = run(backward, [*residuals, *cotangents])
        return tuple(jnp.zeros_like(a) for a in ins[:consts]) + tuple(cts)

    call.defvjp(fwd, bwd)
    return list(call(*ins))


def _custom_jvp(run, bound, ins):
    """`jax.custom_jvp` over two nested graphs: the function, and its derivative
    rule (primals then tangents in, primal outputs then the non-zero tangent
    outputs out), so a rule the miner wrote differentiates as it did for them
    while Carbon has validated every op in it."""
    import jax
    import jax.numpy as jnp

    consts = bound["num_consts"]
    function = bound["call_jaxpr"]["graph"]
    rule = bound["jvp_jaxpr"]["graph"]
    zeros = bound["out_zeros"]
    if consts < 0 or consts > len(ins):
        raise graph.GraphRefused("parameter_kind_mismatch")

    @jax.custom_jvp
    def call(*args):
        return tuple(run(function, list(args)))

    @call.defjvp
    def derivative(primals, tangents):
        outs = run(rule, [*primals[consts:], *tangents[consts:]])
        out_primals, nonzero = outs[: len(zeros)], iter(outs[len(zeros) :])
        out_tangents = [
            jnp.zeros_like(p) if zero else next(nonzero)
            for p, zero in zip(out_primals, zeros)
        ]
        return tuple(out_primals), tuple(out_tangents)

    return list(call(*ins))


def _while(run, bound, ins):
    """`lax.while_loop` over a condition graph and a body graph. The trip count is
    the data's, so the build and inference walls bound it; a loop that never ends is
    the candidate's failure (Validator ruling 2(b): served only once both walls end
    in a typed candidate failure)."""
    import jax

    cond_n, body_n = bound["cond_nconsts"], bound["body_nconsts"]
    if cond_n < 0 or body_n < 0 or cond_n + body_n > len(ins):
        raise graph.GraphRefused("parameter_kind_mismatch")
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


def _scan(run, bound, ins):
    """`lax.scan` over a nested body graph (inputs: consts, carry, x slices;
    outputs: new carry, y slices). Static length; the body runs once per step."""
    import jax

    consts = bound["num_consts"]
    carry = bound["num_carry"]
    if consts < 0 or carry < 0 or consts + carry > len(ins):
        raise graph.GraphRefused("parameter_kind_mismatch")
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


def _cond(run, bound, ins):
    """`lax.switch` over the branch graphs: the first operand is the integer
    index, the rest go to the chosen branch."""
    import jax

    refs = [item["graph"] for item in bound["branches"]]
    index, operands = ins[0], list(ins[1:])
    branches = [
        (lambda *ops, target=target: tuple(run(target, list(ops)))) for target in refs
    ]
    return list(jax.lax.switch(index, branches, *operands))


_SCATTERS = frozenset(
    {"scatter_add", "scatter_sub", "scatter_mul", "scatter_min", "scatter_max"}
)


def _scatter(op, bound, ins):
    """A combining scatter through JAX's own function, so the combiner jaxpr is
    JAX's and never the document's."""
    import jax

    operand, indices, updates = ins
    function = getattr(jax.lax, op)
    return function(
        operand,
        indices,
        updates,
        bound["dimension_numbers"],
        indices_are_sorted=bound["indices_are_sorted"],
        unique_indices=bound["unique_indices"],
        mode=bound["mode"],
    )


def _linear_solve(run, bound, ins):
    """`jax.lax.custom_linear_solve` over the node's four nested graphs, so the
    solve keeps the implicit-differentiation rule JAX gives it (a solve through
    an inlined, stop-gradient factorization would lose the gradient in the matrix)."""
    import jax

    lengths = bound["const_lengths"]
    if len(lengths) != 4 or any(n < 0 for n in lengths):
        raise graph.GraphRefused("parameter_kind_mismatch")
    consts, at = [], 0
    for n in lengths:
        consts.append(list(ins[at : at + n]))
        at += n
    b = list(ins[at:])
    matvec_c, vecmat_c, solve_c, transpose_c = consts

    def ref(name):
        return None if bound[name] is None else bound[name]["graph"]

    def callable_of(name, held):
        target = ref(name)
        if target is None:
            return None
        return lambda *x: run(target, [*held, *x])

    matvec = callable_of("matvec", matvec_c)
    solve_g = callable_of("solve", solve_c)
    transpose_g = callable_of("transpose_solve", transpose_c)
    if matvec is None or solve_g is None:
        raise graph.GraphRefused("parameter_kind_mismatch")
    return list(
        jax.lax.custom_linear_solve(
            lambda x: matvec(*x),
            b,
            lambda _matvec, rhs: solve_g(*rhs),
            None if transpose_g is None else (lambda _vecmat, rhs: transpose_g(*rhs)),
        )
    )


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
            elif node["op"] == "custom_linear_solve":
                outs = _linear_solve(run, bound, ins)
            elif node["op"] == "custom_jvp_call":
                outs = _custom_jvp(run, bound, ins)
            elif node["op"] == "custom_vjp_call":
                outs = _custom_vjp(run, bound, ins)
            elif node["op"] == "while":
                outs = _while(run, bound, ins)
            elif node["op"] == "scan":
                outs = _scan(run, bound, ins)
            elif node["op"] == "cond":
                outs = _cond(run, bound, ins)
            elif node["op"] in _SCATTERS:
                outs = [_scatter(node["op"], bound, ins)]
            elif node["op"] == "device_put":
                outs = list(ins)  # no placement requested: the same values
            else:
                primitive = _PRIMITIVES.get(node["op"])
                if primitive is None:
                    # An allowlisted op this interpreter cannot bind is Carbon's gap,
                    # never the candidate's (build_refusal: CARBON_CAPABILITY_GAP).
                    raise graph.GraphRefused(
                        "primitive_unsupported", f"{name}.nodes[{i}]"
                    )
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
