"""Where does an honest model cross the accounting-v6 budget? For each architecture family, lower the
forward graph at growing depth and print its v6 size (zlib-9 of the canonical document) until it passes
the 16 KiB cap or the depth limit. Read-only.

Usage: python scripts/dev/level4_v6_curve.py [family ...]   (default: every family)"""

# ruff: noqa: BLE001 - a family that does not lower is reported, not fatal

from __future__ import annotations

import sys
from pathlib import Path

import jax
import jax.numpy as jnp
from jax import lax

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph
from carbon.level4.tooling import lower_jax

CAP = allowlist_module.CAPS["constant_bytes"]
V8 = allowlist_module.load(
    Path(allowlist_module.__file__).with_name("allowlist_v8.json")
)
DEPTH_LIMIT = 512


def _ln(x):
    m = x.mean(-1, keepdims=True)
    v = ((x - m) ** 2).mean(-1, keepdims=True)
    return (x - m) / jnp.sqrt(v + 1e-5)


def mlp(depth, width):
    shapes = [(width, width)] * depth

    def f(p, x):
        for w in p:
            x = jnp.tanh(x @ w)
        return x

    return shapes, (8, width), f


def attention(depth, width):
    shapes = [(width, width)] * (6 * depth)

    def f(p, x):
        for i in range(depth):
            q, k, v, o, a, b = p[6 * i : 6 * i + 6]
            att = jax.nn.softmax((x @ q) @ (x @ k).T / width**0.5) @ (x @ v) @ o
            x = _ln(x + att)
            x = _ln(x + jax.nn.gelu(x @ a) @ b)
        return x

    return shapes, (8, width), f


def conv(depth, width):
    shapes = [(width, width, 3, 3)] * depth

    def f(p, x):
        for w in p:
            x = jax.nn.relu(lax.conv_general_dilated(x, w, (1, 1), "SAME"))
        return x

    return shapes, (2, width, 16, 16), f


def unet(depth, width):
    # `depth` down/up levels with skip connections (2 convs per level each way)
    shapes = [(width, width, 3, 3)] * (4 * depth)

    def conv_(x, w):
        return jax.nn.relu(lax.conv_general_dilated(x, w, (1, 1), "SAME"))

    def f(p, x):
        skips = []
        for i in range(depth):
            x = conv_(conv_(x, p[4 * i]), p[4 * i + 1])
            skips.append(x)
            x = lax.reduce_window(
                x, -jnp.inf, lax.max, (1, 1, 1, 1), (1, 1, 1, 1), "VALID"
            )
        for i in reversed(range(depth)):
            x = conv_(conv_(x + skips[i], p[4 * i + 2]), p[4 * i + 3])
        return x

    return shapes, (2, width, 16, 16), f


def fno(depth, width):
    shapes = [(width, width)] * (2 * depth)

    def f(p, x):  # x: (batch, grid, width); spectral conv + pointwise per layer
        for i in range(depth):
            spec = jnp.fft.rfft(x, axis=1)
            spec = spec * 0 + spec @ p[2 * i].astype(spec.dtype)
            y = jnp.fft.irfft(spec, n=x.shape[1], axis=1)
            x = jax.nn.gelu(y + x @ p[2 * i + 1])
        return x

    return shapes, (4, 32, width), f


FAMILIES = {"mlp": mlp, "attention": attention, "conv": conv, "unet": unet, "fno": fno}
WIDTHS = {
    "mlp": (64, 512),
    "attention": (256, 512),
    "conv": (16, 64),
    "unet": (16, 64),
    "fno": (64, 256),
}


def measure(family, depth, width):
    shapes, xshape, forward = FAMILIES[family](depth, width)
    params = [jnp.zeros(s, jnp.float32) for s in shapes]
    x = jnp.zeros(xshape, jnp.float32)
    closed = lower_jax.trace(lambda *a: forward(list(a[:-1]), a[-1]), *params, x)
    names = [f"params/p{i}" for i in range(len(params))] + ["inputs/x"]
    doc = lower_jax.lower(closed, role="forward", allowlist=V8, input_names=names)
    return (
        graph.recipe_info_bytes(doc),
        len(graph.dumps(doc)),
        graph.measure(doc)["nodes_stored"],
    )


def main():
    families = sys.argv[1:] or list(FAMILIES)
    for family in families:
        for width in WIDTHS[family]:
            depth, crossed = 1, None
            while depth <= DEPTH_LIMIT:
                try:
                    packed, raw, nodes = measure(family, depth, width)
                except Exception as error:
                    print(
                        f"{family} w{width} d{depth}: did not lower: {str(error)[:90]}"
                    )
                    break
                print(
                    f"{family:9} w{width:<4} d{depth:<4} v6={packed:>7} raw={raw:>8} nodes={nodes}",
                    flush=True,
                )
                if packed > CAP:
                    crossed = depth
                    break
                depth *= 2
            print(
                f"CROSS {family} w{width}: "
                + (
                    f"over {CAP} at depth {crossed}"
                    if crossed
                    else f"stays under {CAP} to depth {depth // 2 if depth > DEPTH_LIMIT else depth}"
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
