"""D6 (Cooling 1.8 default candidate): the public analytic prior + a LEARNED affine of it + a LEARNED MLP residual, as a
graph route v2 Level 4 SPEC (mc-exam-B, Wed 11 Nov 2026; CV-B ce957672 section 2; board 06:58 (B)).

    python -m carbon.level4.tooling lower d6_spec.py OUT_DIR --challenge chip-cold-plate \
        --challenge-version 1.7 --interface sha256:<Cooling 1.7 interface digest> [--batch N]

The graph route v2 trainer (physical_graph_trainer_v2) fits forward(params, x_raw) to the TRAIN-standardised targets
z = (y - mu) / sd and decodes y = z * sd + mu, so this graph predicts z directly:

    z_pred = a * p(x) + b + MLP([u(x), p(x)])

- p(x): the 32 encoded slots of Cooling's PUBLIC analytic model (`prior.py`, the same code as the file in catalog bundle (black-formatted in this kit)
  v2.cooling.prior_krr 55e1425e, sha256 75a03364...; `cold_plate.analytic.v1`, called as encode(*native(x, 3, 2)): 3 cells
  per segment and 2 coupling passes, the size rule below; prior_krr itself uses 10 / 2),
  on FIXED physics scales chosen without TRAIN: peak-excess slot / 2, temperature slots (T - 60) / 20, pressure slot / 1e4.
- u(x): the inputs on the domain's public unit cube (prior.INPUT_BOUNDS).
- a, b: 32 + 32 trained per-output scale and offset (init 1 and 0).
- MLP: 41 -> 64 -> 64 -> 64 -> 64 -> 32, GELU, trained; the last layer starts at 0, so the untrained model is the scaled prior.
No constant here comes from TRAIN; every learned number is fitted by the graph trainer from scratch (keyed init, no
initial_state). Not production authority: a candidate default for the Cooling 1.8 gate, TRAIN-only until its pick.
"""

import importlib.util
from pathlib import Path

import jax
import jax.numpy as jnp

_spec = importlib.util.spec_from_file_location(
    "d6_prior", Path(__file__).resolve().with_name("prior.py")
)
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

FRAMEWORK = "jax"
INPUTS = {"inputs/features": ((9,), "float64")}
WIDTH, DEPTH, N_IN, N_OUT = 64, 4, 9, 32
SCALE_CENTRE_C, SCALE_SPAN_K, PEAK_SCALE, PRESSURE_SCALE_PA = 60.0, 20.0, 2.0, 1.0e4
#: The prior's march resolution, fixed by GRAPH SIZE ONLY (no data read): the shipped 2 coupling passes and the largest
#: cells-per-segment whose forward graph, lowered at the training batch 366, fits the v8 / accounting-v6 32 KiB recipe-information
#: budget with a 2 KiB margin. Measured recipe_info_bytes: 10/2 63,698 (prior_krr's own resolution, at the tool's default batch;
#: over); at batch 366: 4/2 32,395 (over the margin), 3/2 27,424 (fits). So 3 cells per segment, 2 passes: coarser than prior_krr's 10/2.
PRIOR_STEPS_PER_SEGMENT, PRIOR_COUPLING_PASSES = 3, 2


def scaled_prior(x):
    raw = P.encode(*P.native(x, PRIOR_STEPS_PER_SEGMENT, PRIOR_COUPLING_PASSES))
    return jnp.concatenate(
        [
            raw[:, :1] / PEAK_SCALE,
            (raw[:, 1:31] - SCALE_CENTRE_C) / SCALE_SPAN_K,
            raw[:, 31:] / PRESSURE_SCALE_PA,
        ],
        axis=1,
    )


def unit(x):
    lo = jnp.asarray([b[0] for b in P.INPUT_BOUNDS], dtype=x.dtype)
    hi = jnp.asarray([b[1] for b in P.INPUT_BOUNDS], dtype=x.dtype)
    return (x - lo) / (hi - lo)


def forward(params, x):
    a, b, layers = params[0], params[1], params[2:]
    p = scaled_prior(x)
    h = jnp.concatenate([unit(x), p], axis=1)
    for i in range(DEPTH):
        w, c = layers[2 * i], layers[2 * i + 1]
        h = jax.nn.gelu(h @ w + c)
    w, c = layers[2 * DEPTH], layers[2 * DEPTH + 1]
    return a * p + b + (h @ w + c)


def init(key):
    keys = jax.random.split(key, DEPTH)
    params = [jnp.ones((N_OUT,), jnp.float64), jnp.zeros((N_OUT,), jnp.float64)]
    fan_in = N_IN + N_OUT
    for i in range(DEPTH):
        params.append(
            jax.random.normal(keys[i], (fan_in, WIDTH), jnp.float64)
            * jnp.sqrt(2.0 / fan_in)
        )
        params.append(jnp.zeros((WIDTH,), jnp.float64))
        fan_in = WIDTH
    params.append(jnp.zeros((WIDTH, N_OUT), jnp.float64))
    params.append(jnp.zeros((N_OUT,), jnp.float64))
    return params
