"""Functional JAX research operators for a bounded 1D domain.

FNO equations follow Carbon PR40/neuraloperator. Physics attention ports the
slice/attend/deslice core of THUML Transolver (MIT; see third_party/).
Haar/GNO/GINO are explicitly simplified Carbon research implementations, not
claims of parity with the named papers or industrial general-geometry solvers.
All trainable leaves are real fp32 arrays, including real/imaginary FFT parts.
"""

from __future__ import annotations

import math
from itertools import pairwise

import jax
import jax.numpy as jnp

from .config import ModelConfig


def gelu(x):
    return jax.nn.gelu(x, approximate=False)


def dense(p, x):
    y = x @ p["w"]
    return y + p["b"] if "b" in p else y


def mlp(p, x):
    for i, layer in enumerate(p):
        x = dense(layer, x)
        if i < len(p) - 1:
            x = gelu(x)
    return x


def layer_norm(p, x):
    mean = jnp.mean(x, axis=-1, keepdims=True)
    variance = jnp.mean(jnp.square(x - mean), axis=-1, keepdims=True)
    return (x - mean) * jax.lax.rsqrt(variance + 1e-5) * p["scale"] + p["bias"]


class Initializer:
    def __init__(self, key):
        self.key = key

    def next(self):
        self.key, key = jax.random.split(self.key)
        return key

    def normal(self, shape, scale):
        return jax.random.normal(self.next(), shape, dtype=jnp.float32) * scale

    def linear(self, din, dout, bias=True, zero=False):
        bound = din**-0.5
        w = (
            jnp.zeros((din, dout), jnp.float32)
            if zero
            else jax.random.uniform(
                self.next(), (din, dout), minval=-bound, maxval=bound
            )
        )
        p = {"w": w}
        if bias:
            p["b"] = jnp.zeros((dout,), jnp.float32)
        return p

    def mlp(self, dims):
        return tuple(self.linear(a, b) for a, b in pairwise(dims))


def norm_init(width):
    return {
        "scale": jnp.ones((width,), jnp.float32),
        "bias": jnp.zeros((width,), jnp.float32),
    }


def spectral_init(init, din, dout, n_modes):
    shape = (din, dout, n_modes // 2 + 1)
    scale = math.sqrt(2 / (din + dout))
    return {
        "real": init.normal(shape, scale),
        "imag": init.normal(shape, scale),
        "bias": jnp.zeros((dout,), jnp.float32),
    }


def spectral_apply(p, x):
    """[B,N,Cin] -> [B,N,Cout]; PR40 full n_modes convention at initialization."""
    n = x.shape[1]
    xft = jnp.fft.rfft(x, axis=1, norm="forward")
    kept = min(p["real"].shape[-1], xft.shape[1])
    w = p["real"][..., :kept] + 1j * p["imag"][..., :kept]
    low = jnp.einsum("bki,iok->bko", xft[:, :kept, :], w)
    out = jnp.zeros((x.shape[0], xft.shape[1], w.shape[1]), dtype=xft.dtype)
    out = out.at[:, :kept, :].set(low)
    out = out.at[:, 0, :].set(out[:, 0, :].real)
    if n % 2 == 0:
        out = out.at[:, -1, :].set(out[:, -1, :].real)
    return jnp.fft.irfft(out, n=n, axis=1, norm="forward") + p["bias"]


def fno_block_init(init, cfg):
    w = cfg.width
    return {
        "spectral": spectral_init(init, w, w, cfg.n_modes),
        "skip": init.linear(w, w, bias=False),
        "gate": jnp.ones((w,), jnp.float32),
        "mlp": init.mlp((w, max(1, round(w * 0.5)), w)),
    }


def fno_block(p, x, last):
    gate = x * p["gate"]
    h = spectral_apply(p["spectral"], x) + dense(p["skip"], x)
    if not last:
        h = gelu(h)
    h = mlp(p["mlp"], h) + gate
    return h if last else gelu(h)


def attention_init(init, cfg):
    w, d = cfg.width, cfg.width // cfg.heads
    return {
        "project_x": init.linear(w, w),
        "project_f": init.linear(w, w),
        "slice": init.linear(d, cfg.slices),
        "q": init.linear(d, d, False),
        "k": init.linear(d, d, False),
        "v": init.linear(d, d, False),
        "out": init.linear(w, w),
        "raw_temperature": jnp.full(
            (cfg.heads,), math.log(math.expm1(0.5)), jnp.float32
        ),
    }


def physics_attention(p, x, heads, point_weights=None):
    """Transolver slice/attention/deslice core. Positive temperature is a change.

    With uniform weights and equivalent temperature this matches the upstream
    irregular-mesh core at dropout=0. Quadrature weights are an explicit extension.
    """
    b, n, c = x.shape
    d = c // heads

    def split(z):
        return z.reshape(b, n, heads, d).transpose(0, 2, 1, 3)

    fx = split(dense(p["project_f"], x))
    xx = split(dense(p["project_x"], x))
    temperature = jax.nn.softplus(p["raw_temperature"])[None, :, None, None] + 1e-6
    assignment = jax.nn.softmax(dense(p["slice"], xx) / temperature, axis=-1)
    if point_weights is None:
        weighted = assignment
    else:
        weights = jnp.asarray(point_weights)
        if weights.ndim == 1:
            weights = weights[None, :]
        # Keep uniform weights at 1 to preserve the upstream epsilon convention.
        weights = weights / jnp.mean(weights, axis=-1, keepdims=True)
        weighted = assignment * weights[:, None, :, None]
    tokens = jnp.einsum("bhnd,bhnm->bhmd", fx, weighted) / (
        weighted.sum(2)[..., None] + 1e-5
    )
    q, k, v = (dense(p[name], tokens) for name in ("q", "k", "v"))
    a = jax.nn.softmax(jnp.einsum("bhmd,bhkd->bhmk", q, k) / math.sqrt(d), axis=-1)
    out = jnp.einsum("bhmk,bhkd->bhmd", a, v)
    out = (
        jnp.einsum("bhmd,bhnm->bhnd", out, assignment)
        .transpose(0, 2, 1, 3)
        .reshape(b, n, c)
    )
    return dense(p["out"], out)


def haar_forward(x, levels):
    details = []
    for _ in range(levels):
        if x.shape[1] % 2:
            raise ValueError("Haar grid must be divisible by 2**levels")
        even, odd = x[:, ::2, :], x[:, 1::2, :]
        details.append((even - odd) / math.sqrt(2))
        x = (even + odd) / math.sqrt(2)
    return x, tuple(details)


def haar_inverse(low, details):
    for d in reversed(details):
        low = jnp.stack(
            ((low + d) / math.sqrt(2), (low - d) / math.sqrt(2)), axis=2
        ).reshape(low.shape[0], 2 * low.shape[1], low.shape[2])
    return low


def haar_layer(p, x, levels):
    low, ds = haar_forward(x, levels)
    low = dense(p["low"], low) + dense(p["global"], low.mean(1, keepdims=True))
    ds = tuple(dense(pp, d) for pp, d in zip(p["detail"], ds))
    return haar_inverse(low, ds)


def graph_init(init, din, dout, width):
    return {
        "value": init.linear(din, dout, False),
        "kernel": init.mlp((3, width, dout)),
        "bias": jnp.zeros((dout,), jnp.float32),
    }


def graph_apply(p, values, source, target, radius, weights=None):
    """Dense radius-masked, diagonal-kernel quadrature on a periodic 1D domain.

    O(Nsource*Ntarget*width). This is not a scalable sparse 3D GNO implementation.
    source/target are unit coordinates [N,1]. Geometry is shared by the batch.
    """
    delta = target[:, None, 0] - source[None, :, 0]
    delta = (delta + 0.5) % 1.0 - 0.5
    mask = (jnp.abs(delta) <= radius).astype(values.dtype)
    q = (
        jnp.ones((source.shape[0],), values.dtype)
        if weights is None
        else jnp.asarray(weights)
    )
    q = mask * q[None, :]
    norm = q.sum(-1, keepdims=True)
    q = jnp.where(norm > 0, q / jnp.maximum(norm, 1e-20), 0)
    features = jnp.stack(
        (delta / radius, jnp.sin(2 * jnp.pi * delta), jnp.cos(2 * jnp.pi * delta)),
        axis=-1,
    )
    kernel = mlp(p["kernel"], features)
    return (
        jnp.einsum("ij,ijc,bjc->bic", q, kernel, dense(p["value"], values)) + p["bias"]
    )


def periodic_features(pos):
    return jnp.concatenate(
        (jnp.sin(2 * jnp.pi * pos), jnp.cos(2 * jnp.pi * pos)), axis=-1
    )


class Operator:
    """One immutable model specification; init/apply use ordinary JAX pytrees.

    Common native shape is [batch, points, features]. See pr40_bridge.py for
    the channels-first PR40 parameter/array bridge. Trainer features are
    [normalized initial field, viscosity/scale, time/scale].
    """

    def __init__(self, config: ModelConfig, in_features: int = 3):
        if not isinstance(config, ModelConfig) or in_features < 1:
            raise ValueError("model config")
        self.config = config
        self.in_features = in_features

    def init(self, key):
        c = self.config
        k = Initializer(key)
        w = c.width
        if c.kind == "deeponet1d":
            return {
                "branch": k.mlp((c.branch_points + self.in_features - 1, w, w, w)),
                "trunk": k.mlp((2, w, w, w)),
                "bias": jnp.zeros((), jnp.float32),
            }
        # PR40 uses one coordinate channel. Other families use periodic coordinates.
        coord_features = 1 if c.kind == "fno1d" else 2
        p = {
            "lift": k.mlp((self.in_features + coord_features, 2 * w, w)),
            "projection": k.mlp((w, 2 * w, 1)),
        }
        if c.kind in ("fno1d", "gino1d"):
            p["blocks"] = tuple(fno_block_init(k, c) for _ in range(c.depth))
            if c.kind == "gino1d":
                p["encoder"] = graph_init(k, w, w, w)
                p["decoder"] = graph_init(k, w, w, w)
        elif c.kind == "physics_attention1d":
            p["blocks"] = tuple(
                {
                    "norm1": norm_init(w),
                    "attention": attention_init(k, c),
                    "norm2": norm_init(w),
                    "mlp": k.mlp((w, c.expansion * w, w)),
                }
                for _ in range(c.depth)
            )
        elif c.kind == "haar_operator1d":
            p["blocks"] = tuple(
                {
                    "low": k.linear(w, w, False),
                    "global": k.linear(w, w, False),
                    "detail": tuple(
                        k.linear(w, w, False) for _ in range(c.wavelet_levels)
                    ),
                    "skip": k.linear(w, w),
                }
                for _ in range(c.depth)
            )
        elif c.kind == "gno1d":
            p["blocks"] = tuple(
                {"graph": graph_init(k, w, w, w), "skip": k.linear(w, w)}
                for _ in range(c.depth)
            )
        else:
            raise ValueError("unsupported backbone")
        return p

    def apply(self, p, features, positions, point_weights=None):
        c = self.config
        if features.ndim != 3 or features.shape[-1] != self.in_features:
            raise ValueError("expected [B,N,F]")
        if positions.shape != (features.shape[1], 1):
            raise ValueError("shared coordinates must have shape [N,1]")
        if c.kind == "deeponet1d":
            sensors = (
                jnp.arange(c.branch_points, dtype=features.dtype) / c.branch_points
            )
            resample = jax.vmap(
                lambda v: jnp.interp(sensors, positions[:, 0], v, period=1.0)
            )
            sampled = resample(features[..., 0])
            constants = features[:, 0, 1:]
            branch = mlp(p["branch"], jnp.concatenate((sampled, constants), axis=-1))
            trunk = mlp(p["trunk"], periodic_features(positions))
            return (
                jnp.einsum("bw,nw->bn", branch, trunk) / math.sqrt(c.width) + p["bias"]
            )[..., None]
        coords = positions if c.kind == "fno1d" else periodic_features(positions)
        coords = jnp.broadcast_to(coords, (features.shape[0], *coords.shape))
        h = mlp(p["lift"], jnp.concatenate((features, coords), axis=-1))
        if c.kind == "gino1d":
            latent = (
                jnp.arange(c.latent_points, dtype=features.dtype) / c.latent_points
            )[:, None]
            h = graph_apply(
                p["encoder"], h, positions, latent, c.graph_radius, point_weights
            )
        for i, block in enumerate(p["blocks"]):
            if c.kind in ("fno1d", "gino1d"):
                fn = lambda b, z, last=i == c.depth - 1: fno_block(b, z, last)
            elif c.kind == "physics_attention1d":

                def fn(b, z):
                    a = z + physics_attention(
                        b["attention"],
                        layer_norm(b["norm1"], z),
                        c.heads,
                        point_weights,
                    )
                    return a + mlp(b["mlp"], layer_norm(b["norm2"], a))

            elif c.kind == "haar_operator1d":
                fn = lambda b, z: gelu(
                    haar_layer(b, z, c.wavelet_levels) + dense(b["skip"], z)
                )
            else:
                fn = lambda b, z: gelu(
                    graph_apply(
                        b["graph"],
                        z,
                        positions,
                        positions,
                        c.graph_radius,
                        point_weights,
                    )
                    + dense(b["skip"], z)
                )
            h = (jax.checkpoint(fn) if c.remat else fn)(block, h)
        if c.kind == "gino1d":
            h = graph_apply(p["decoder"], h, latent, positions, c.graph_radius)
        return mlp(p["projection"], h)


def parameter_count(params):
    return sum(x.size for x in jax.tree.leaves(params))
