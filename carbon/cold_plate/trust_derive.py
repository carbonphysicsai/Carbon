"""The jax derive of Cooling's two scored decision quantities, for the self-trust trainer (SELF_TRUST H3e, Cooling).

The trust trainer (`carbon.development_session.physical_graph_trainer_v4`) fits a model's own sigma to the residual of each DERIVED scored
output. For Cooling those are the two decision quantities the pool grader scores (`carbon.scoring.pool_adapters._cooling`): the die peak
temperature and the hydraulic power. This module is the same arithmetic as the numpy reference (`exam.die_peak_c`, `exam.feasibility`,
`domain.heat_flux`, `domain.hotspot_shape`, `domain.derived`, `output_encoding.decode_row`), written in jax so it can be traced; a test
holds it equal to that reference on random cases. It takes the law-safe ENCODED 32-value row the model and the TRAIN targets are in (the
first 32 slots: Cooling 1.8's 34-slot row carries the same 32 first) and the case's inputs in `domain.INPUTS` order.

It carries no gate: the grader's physical gates decide whether a row is a valid answer; a trust read only compares the two quantities.
"""

from __future__ import annotations

import math

from . import domain

#: The two derived outputs, in the pool adapter's order: the trust outputs of Cooling.
OUTPUTS = ("die_peak_c", "hydraulic_w")
_PROFILE = slice(1, 1 + domain.PROFILE_SEGMENTS)
_PRESSURE = 1 + domain.PROFILE_SEGMENTS


def _softplus(x):
    import jax.numpy as jnp

    return jnp.log1p(jnp.exp(-jnp.abs(x))) + jnp.maximum(x, 0.0)


def derive(rows, inputs):
    """`(n, 2)`: die peak temperature (C) and hydraulic power (W) of each encoded row under its case.

    `rows` is `(n, >= 32)`; `inputs` is `(n, >= 9)` with the first nine columns the Cooling inputs in `domain.INPUTS` order.
    """
    import jax.numpy as jnp
    from jax.scipy.special import erf

    rows = jnp.asarray(rows)
    x = jnp.asarray(inputs)
    index = {name: i for i, name in enumerate(domain.INPUTS)}
    heat_load = x[:, index["heat_load_w"]]
    flow_per_kw = x[:, index["flow_lpm_per_kw"]]
    ratio = x[:, index["hotspot_ratio"]]
    centre = x[:, index["hotspot_center_mm"]]
    width = x[:, index["hotspot_width_mm"]]

    profile = rows[:, _PROFILE]
    peak = profile.max(axis=1) + _softplus(rows[:, 0])
    pressure = _softplus(rows[:, _PRESSURE])
    flow = heat_load / 1000.0 * flow_per_kw / 60000.0
    hydraulic = pressure * flow

    # the hot spot's axial map (`domain.hotspot_shape` / `domain.heat_flux`), sampled at each segment's mid-point
    length = domain.FIXED["footprint_mm"]
    root = width * math.sqrt(2.0)
    mean_g = (
        width
        * math.sqrt(math.pi / 2.0)
        / length
        * (erf((length - centre) / root) + erf(centre / root))
    )
    amplitude = (ratio - 1.0) / (1.0 - ratio * mean_g)
    mean_shape = 1.0 + amplitude * mean_g
    segment = 30.0 / domain.PROFILE_SEGMENTS
    at = (jnp.arange(domain.PROFILE_SEGMENTS) + 0.5) * segment
    g = jnp.exp(-0.5 * ((at[None, :] - centre[:, None]) / width[:, None]) ** 2)
    side = domain.FIXED["footprint_mm"] * 1e-3
    flux = (
        heat_load[:, None]
        / side**2
        * (1.0 + amplitude[:, None] * g)
        / mean_shape[:, None]
    )
    through_tim = (profile + flux * domain.TIM_RESISTANCE_M2K_W).max(axis=1)
    die = through_tim + jnp.maximum(0.0, peak - profile.max(axis=1))
    return jnp.stack([die, hydraulic], axis=1)
