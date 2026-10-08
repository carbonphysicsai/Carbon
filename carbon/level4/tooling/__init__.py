"""Miner-side Level 4 tooling: lowering a JAX or PyTorch program into the
Carbon graph format. In B' this runs on the miner's machine (Launchpad);
Carbon's hosts only parse what it writes (`carbon.level4.graph`).
"""

from __future__ import annotations


def through_bprime(fn, example_args, *, role, allowlist, input_names, max_bytes):
    """Lower `fn` at `example_args`, write the canonical JSON bytes, parse
    them back with the strict parser and rebuild: the whole B' round trip.

    Returns `(rebuilt(*flat_inputs) -> list, document, raw_bytes)`."""
    import jax

    from .. import graph, interpret
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
    return interpret.rebuild(parsed, allowlist), parsed, raw
