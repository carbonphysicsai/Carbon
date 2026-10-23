"""Motor (Electric Motor Magnetics) public textbook prior as pure JAX ops (backbone-catalog lane, 2026-10-23).

Validator-ruled admissible as `prior.motor.surface-pm-v1`. A port of `carbon.motor.analytic.predict` (the repository's
published surface-PM torque model: Carter's coefficient, airgap field under the magnet, fundamental of the pole arc, flux
linkage, T = 3/2 p psi I cos(gamma); no saturation, slotting or cogging, so the curve is flat over the rotor angle). The coil
area `domain.coil_area_mm2` (a shoelace over the meshed polygon, which needs asin) is computed in closed form: the polygon's
vertices lie on lines offset w = tooth/2 from the tooth centre rays, at distance sqrt(r^2 - w^2) along the ray.

`prior(x)` takes (n, 8) inputs in the interface's order and returns (n, 60): the torque, repeated at the 60 rotor angles.
It is a prior, never the exam reference.
"""

from __future__ import annotations

import math

import jax.numpy as jnp

PRIOR_ID = "prior.motor.surface-pm-v1"
INPUTS = (
    "magnet_mm",
    "embrace",
    "airgap_mm",
    "slot_open_deg",
    "tooth_mm",
    "slot_bottom_mm",
    "current_density_a_mm2",
    "current_angle_deg",
)
INPUT_BOUNDS = ((1.5, 4.0), (0.55, 0.95), (0.3, 1.0), (1.0, 6.0), (2.5, 5.0), (34.0, 42.0), (0.0, 15.0), (0.0, 60.0))
N_OUT = 60
POSITIVE_OUTPUTS = ()
POLES, SLOTS, R_RO, TIP_H, WEDGE_H, LENGTH_MM, TURNS, BR, MUR = 8, 24, 25.6, 0.6, 0.34, 35.0, 104, 1.2, 1.0


def _coil_area_mm2(gap, tooth, r_sb):
    pitch = 2 * math.pi / SLOTS
    half = pitch / 2
    r_body = R_RO + gap + TIP_H + WEDGE_H
    w = tooth / 2
    cos_h, sin_h = math.cos(half), math.sin(half)

    def vertex(radius, side):
        along = jnp.sqrt(radius**2 - w**2)
        # side -1: tooth ray at -half, slot is above it; side +1: ray at +half, slot is below it (slot-centred frame)
        if side < 0:
            return along * cos_h + w * sin_h, -along * sin_h + w * cos_h
        return along * cos_h + w * sin_h, along * sin_h - w * cos_h

    points = [vertex(r_body, -1), vertex(r_sb, -1), vertex(r_sb, 1), vertex(r_body, 1)]
    total = 0.0
    for i in range(4):
        (x1, y1), (x0, y0) = points[i], points[i - 1]
        total = total + (x1 * y0 - x0 * y1)
    return jnp.abs(total) / 2


def prior(x):
    """(n, 8) inputs -> (n, 60)."""
    x = jnp.asarray(x)
    h_m, embrace, gap, slot_open, tooth, r_sb, density, angle = (x[:, i] for i in range(8))
    pairs = POLES // 2
    r_si = R_RO + gap
    tau_s = 2 * math.pi * r_si / SLOTS
    b_o = r_si * (slot_open * math.pi / 180.0)
    ratio = b_o / gap
    carter = tau_s / (tau_s - ratio * ratio / (5 + ratio) * gap)
    b_g = BR * h_m / (h_m + MUR * carter * gap)
    b_1 = 4 / math.pi * b_g * jnp.sin(embrace * math.pi / 2)
    diameter = 2 * (R_RO + gap / 2) * 1e-3
    series_turns = SLOTS / 6 * TURNS
    psi = series_turns * b_1 * diameter * (LENGTH_MM * 1e-3) / pairs
    current = density * _coil_area_mm2(gap, tooth, r_sb) / TURNS
    torque = 1.5 * pairs * psi * current * jnp.cos(angle * math.pi / 180.0)
    return jnp.broadcast_to(torque[:, None], (torque.shape[0], N_OUT))
