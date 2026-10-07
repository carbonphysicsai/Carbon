"""Named functions: custom derivative rules as first-class graph nodes (Q1).

A `custom_jvp_call` carries its derivative rule as a Python callable, which no
graph can hold. Lowering the primal body alone changes the gradient (Phase 0:
relu and softplus diverge from native). Instead, a registered kernel becomes
one node, `named_function` with its allowlisted name, and the interpreter
rebuilds it with Carbon's own implementation of that name, which brings
Carbon's own JVP (and so VJP) rule.

Recognition runs where lowering runs (the miner's machine in B'): the call's
primal body must equal, structure and constants, the body Carbon's own
kernel produces when traced at the same input types. Anything else stays a `custom_jvp_call`,
which allowlist v1 refuses. Carbon's side never trusts a name for more than
choosing which of its own functions to run; the interpreter still checks the
declared result shapes.
"""

from __future__ import annotations


def _kernels():
    """Carbon's implementations, by the names the allowlist may list. A name
    absent here can never run, whatever a document says."""
    import jax
    import jax.numpy as jnp
    from jax.scipy import special

    return {
        "relu": jax.nn.relu,
        "relu6": jax.nn.relu6,
        "log1mexp": jax.nn.log1mexp,
        "logaddexp": jnp.logaddexp,
        "logaddexp2": jnp.logaddexp2,
        "logit": special.logit,
        "log_ndtr": special.log_ndtr,
        "xlogy": special.xlogy,
        "xlog1py": special.xlog1py,
        "i0": jnp.i0,
        "exp1": special.exp1,
        "sici": special.sici,
        "poch": special.poch,
        "zeta": special.zeta,
    }


_KERNELS = None


def kernels():
    global _KERNELS
    if _KERNELS is None:
        _KERNELS = _kernels()
    return _KERNELS


def _first_custom_jvp(jaxpr):
    for eqn in getattr(jaxpr, "jaxpr", jaxpr).eqns:
        if eqn.primitive.name == "custom_jvp_call":
            return eqn
        for value in eqn.params.values():
            for sub in value if isinstance(value, tuple | list) else [value]:
                if hasattr(sub, "eqns") or hasattr(sub, "jaxpr"):
                    found = _first_custom_jvp(sub)
                    if found is not None:
                        return found
    return None


def _same_body(a, b):
    """Two closed jaxprs are the same program: identical printed structure
    (primitives, parameters, literals, avals) and identical constants.

    The body is never run or admitted op by op: Carbon replaces it with its
    own kernel, so it may use ops outside the allowlist (exp1's loops,
    log_ndtr's erfc). Any difference only fails recognition, which refuses."""
    import numpy as np

    if str(a) != str(b) or len(a.consts) != len(b.consts):
        return False
    return all(
        np.array_equal(np.asarray(x), np.asarray(y)) for x, y in zip(a.consts, b.consts)
    )


def recognize(eqn, allowlist):
    """The allowlisted name whose kernel this `custom_jvp_call` is, or None."""
    import jax

    if eqn.params.get("num_consts") != 0:
        return None
    avals = [v.aval for v in eqn.invars]
    specs = [
        jax.ShapeDtypeStruct(a.shape, a.dtype, weak_type=getattr(a, "weak_type", False))
        for a in avals
    ]
    target = eqn.params["call_jaxpr"]
    for name, entry in sorted(allowlist.named.items()):
        if entry["default"] == "refuse" or entry["arity"] != len(specs):
            continue
        fn = kernels().get(name)
        if fn is None:
            continue
        try:
            reference = _first_custom_jvp(jax.make_jaxpr(fn)(*specs))
        except (TypeError, ValueError):
            continue
        if (
            reference is None
            or reference.params["symbolic_zeros"] != eqn.params["symbolic_zeros"]
        ):
            continue
        if _same_body(reference.params["call_jaxpr"], target):
            return name
    return None


def call(name, args):
    """Carbon's implementation of `name` on `args`, as a list of results."""
    out = kernels()[name](*args)
    return list(out) if isinstance(out, tuple) else [out]
