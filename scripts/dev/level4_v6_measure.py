"""Measure accounting v6 (zlib-9 of the canonical recipe) over the graph documents Carbon ships and a
sweep of lowered reference architectures. Read-only; prints one line per document and a summary.

Usage: python scripts/dev/level4_v6_measure.py [--sweep]"""

# ruff: noqa: BLE001 - a family that does not lower is reported, not fatal

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph

ROOT = Path(__file__).resolve().parents[2]
CAP = allowlist_module.CAPS["constant_bytes"]


def _shipped():
    patterns = [
        "docs/development/graphite/level4/a40_leg/*/*.json",
        "carbon/battery/public_scaffold/*.json",
    ]
    for pattern in patterns:
        for path in sorted(glob.glob(str(ROOT / pattern))):
            doc = json.loads(Path(path).read_bytes())
            if doc.get("schema") == graph.SCHEMA:
                yield str(Path(path).relative_to(ROOT))[:80], [doc]


def _sweep():
    import jax
    import jax.numpy as jnp

    from carbon.level4.tooling import lower_jax

    v8 = allowlist_module.load(
        Path(allowlist_module.__file__).with_name("allowlist_v8.json")
    )

    def lowered(name, forward, params, x):
        closed = lower_jax.trace(lambda *a: forward(a[:-1], a[-1]), *params, x)
        names = [f"params/p{i}" for i in range(len(params))] + ["inputs/x"]
        doc = lower_jax.lower(closed, role="forward", allowlist=v8, input_names=names)
        yield name, [doc]

    key = jax.random.PRNGKey(0)

    def mlp(depth, width):
        params = [jnp.zeros((width, width)) for _ in range(depth)]

        def forward(p, x):
            for w in p:
                x = jnp.tanh(x @ w)
            return x

        return lowered(
            f"sweep mlp d{depth} w{width}", forward, params, jnp.zeros((8, width))
        )

    def block(depth, width):
        params = []
        for _ in range(depth):
            params += [jnp.zeros((width, width))] * 4

        def forward(p, x):
            for i in range(depth):
                q, k, v, o = p[4 * i : 4 * i + 4]
                a = jax.nn.softmax((x @ q) @ (x @ k).T / width**0.5) @ (x @ v) @ o
                x = x + a
                m = (
                    jax.nn.layer_norm
                    if hasattr(jax.nn, "layer_norm")
                    else (lambda t: t)
                )
                x = x + jnp.tanh(m(x))
            return x

        return lowered(
            f"sweep attention d{depth} w{width}", forward, params, jnp.zeros((8, width))
        )

    for depth, width in [(2, 64), (4, 128), (8, 256), (16, 256), (32, 256)]:
        yield from mlp(depth, width)
    for depth in (2, 6, 12, 24):
        try:
            yield from block(depth, 64)
        except (
            Exception
        ) as error:  # a sweep entry that does not lower is reported, not fatal
            print("sweep attention", depth, "did not lower:", str(error)[:80])
    _ = key


def main():
    rows = list(_shipped())
    if "--sweep" in sys.argv:
        rows += list(_sweep())
    over = 0
    for name, docs in rows:
        raw = sum(len(graph.dumps(d)) for d in docs)
        packed = graph.recipe_info_bytes(*docs)
        flag = "OVER" if packed > CAP else "ok"
        over += packed > CAP
        print(f"{flag:4} v6={packed:>8} raw={raw:>9} {name}")
    print(f"documents={len(rows)} over_{CAP}={over}")


if __name__ == "__main__":
    main()
