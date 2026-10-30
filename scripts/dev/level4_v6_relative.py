"""Accounting v6 with RELATIVE operand ids (measurement only): the same zlib-9 size, but every value id is
rewritten as its distance from the next fresh id, so repeated layers have identical bytes. Injective
(the next fresh id is recomputed while decoding), so no information is dropped. Prints the family depth
curve and the lookup-table attacks under this measure.

Usage: python scripts/dev/level4_v6_relative.py"""

from __future__ import annotations

import copy
import zlib

import level4_v6_curve as curve  # same directory
import numpy as np

from carbon.level4 import graph

CAP = curve.CAP


def relative(doc):
    doc = copy.deepcopy(doc)
    for g in doc["graphs"].values():
        top = -1
        for entry in g["inputs"] + g["constants"]:
            value = entry["value"]
            entry["value"] = value - top  # delta from the previous definition
            top = max(top, value)
        for node in g["nodes"]:
            fresh = top + 1
            node["in"] = [fresh - i for i in node["in"]]
            for out in node["out"]:
                value = out["value"]
                out["value"] = value - fresh
                top = max(top, value)
        fresh = top + 1
        g["outputs"] = [fresh - o for o in g["outputs"]]
    return doc


def size(*docs):
    return len(zlib.compress(b"\n".join(graph.dumps(relative(d)) for d in docs), 9))


graph.recipe_info_bytes = size  # curve.measure reads it at call time


def wired(symbols, levels):
    import jax.numpy as jnp

    from carbon.level4.tooling import lower_jax

    values = [jnp.full((1,), 0.001 * (i + 1), jnp.float32) for i in range(levels)]
    closed = lower_jax.trace(
        lambda x: jnp.concatenate([values[int(s)] for s in symbols]),
        jnp.zeros(2, jnp.float32),
    )
    return lower_jax.lower(
        closed, role="forward", allowlist=curve.V8, input_names=["inputs/x"]
    )


def attacks():
    rng = np.random.default_rng(1)
    cases = [
        (
            "200k operands, 2 constants (25 KB of bits)",
            wired(rng.integers(0, 2, 200_000), 2),
        ),
        (
            "200k operands, 256 constants (200 KB)",
            wired(rng.integers(0, 256, 200_000), 256),
        ),
        (
            "random-byte wiring, 32768 operands x 256",
            wired(rng.integers(0, 256, 32_768), 256),
        ),
        (
            "651-entry table in wiring (651 distinct levels)",
            wired(rng.permutation(651), 651),
        ),
    ]
    import jax.numpy as jnp

    from carbon.level4.tooling import lower_jax

    table = jnp.asarray(
        rng.normal(70, 10, 651), jnp.float32
    )  # 651 float32 constants (peak_top_c-like)
    closed = lower_jax.trace(lambda x: table[:2] + x, jnp.zeros(2, jnp.float32))
    cases.append(
        (
            "651 float32 constants (2.6 KB of data, ITEM d)",
            lower_jax.lower(
                closed, role="forward", allowlist=curve.V8, input_names=["inputs/x"]
            ),
        )
    )
    for name, doc in cases:
        packed, absolute = size(doc), zlib.compress(graph.dumps(doc), 9).__len__()
        print(
            f"{'REFUSED' if packed > CAP else 'ADMITTED':8} relative={packed:>8} absolute={absolute:>8}  {name}",
            flush=True,
        )


def main():
    for family, depths in [
        ("attention", (16, 32, 64, 128)),
        ("fno", (64, 128, 256, 512)),
        ("unet", (64, 128, 256, 512)),
        ("conv", (512,)),
        ("mlp", (512,)),
    ]:
        width = curve.WIDTHS[family][0]
        crossed = None
        for depth in depths:
            packed, raw, _nodes = curve.measure(family, depth, width)
            print(
                f"{family:9} w{width:<4} d{depth:<4} v6rel={packed:>7} raw={raw:>8}",
                flush=True,
            )
            if packed > CAP and crossed is None:
                crossed = depth
        print(
            f"CROSS {family}: "
            + (
                f"over {CAP} at depth {crossed}"
                if crossed
                else f"under {CAP} to depth {depths[-1]}"
            ),
            flush=True,
        )
    attacks()


if __name__ == "__main__":
    main()
