"""D6 VARIANT GRAPH 'head' (D6d): D6 with a SEPARATE relative-residual head for the pressure slot (mc-exam-B, Wed 11 Nov 2026;
CV-B ca723721 (3) variants; written before any fit of this graph).

Slots 0-30: D6's exactly (a * p + b + MLP, d6_spec.py 41213fb5).
Slot 31 (pressure, from which hydraulic_w derives): z31 = a31 * p31(x) * exp(H([u(x), log p31(x)])) + b31, where H is its OWN
small MLP 10 -> 16 -> 16 -> 1 (GELU), trained, last layer starting at 0. The main MLP's slot-31 output is not used.
The head sees the inputs and the log of the prior's (scaled) pressure, so it learns a relative correction of the prior's
pressure law without sharing capacity with the 31 temperature slots. Nothing comes from TRAIN; keyed init; no initial_state.
"""

import importlib.util
from pathlib import Path

import jax
import jax.numpy as jnp

_spec = importlib.util.spec_from_file_location(
    "d6_base", Path(__file__).resolve().with_name("d6_spec.py")
)
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

FRAMEWORK = B.FRAMEWORK
INPUTS = B.INPUTS
HEAD_WIDTH, HEAD_IN = 16, 10
N_MAIN = 2 + 2 * (
    B.DEPTH + 1
)  # a, b + the main MLP's weights and biases (D6's params, in D6's order)


def init(key):
    main_key, head_key = jax.random.split(key)
    params = B.init(main_key)
    k1, k2 = jax.random.split(head_key)
    params.append(
        jax.random.normal(k1, (HEAD_IN, HEAD_WIDTH), jnp.float64)
        * jnp.sqrt(2.0 / HEAD_IN)
    )
    params.append(jnp.zeros((HEAD_WIDTH,), jnp.float64))
    params.append(
        jax.random.normal(k2, (HEAD_WIDTH, HEAD_WIDTH), jnp.float64)
        * jnp.sqrt(2.0 / HEAD_WIDTH)
    )
    params.append(jnp.zeros((HEAD_WIDTH,), jnp.float64))
    params.append(jnp.zeros((HEAD_WIDTH, 1), jnp.float64))
    params.append(jnp.zeros((1,), jnp.float64))
    return params


def forward(params, x):
    a, b, layers, head = params[0], params[1], params[2:N_MAIN], params[N_MAIN:]
    p = B.scaled_prior(x)
    u = B.unit(x)
    h = jnp.concatenate([u, p], axis=1)
    for i in range(B.DEPTH):
        h = jax.nn.gelu(h @ layers[2 * i] + layers[2 * i + 1])
    out = h @ layers[2 * B.DEPTH] + layers[2 * B.DEPTH + 1]
    g = jnp.concatenate([u, jnp.log(p[:, 31:])], axis=1)
    g = jax.nn.gelu(g @ head[0] + head[1])
    g = jax.nn.gelu(g @ head[2] + head[3])
    g = g @ head[4] + head[5]
    linear = a[:31] * p[:, :31] + b[:31] + out[:, :31]
    pressure = a[31:] * p[:, 31:] * jnp.exp(g) + b[31:]
    return jnp.concatenate([linear, pressure], axis=1)
