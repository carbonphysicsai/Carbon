"""F08 (Ribbed Bracket) public textbook prior as pure JAX ops (backbone-catalog lane, 2026-10-23).

Validator-ruled admissible as `prior.f08.cantilever-beam-v1`. Variable-section Euler-Bernoulli cantilever from the public brief
(cantilever plate length L, width w, thickness t; two upper ribs of height h and thickness tr at y = +-w/4; a centred cable relief
of length Lr and width 20 mm; E = 70 GPa, rho = 2700 kg/m^3; root clamped, unit tip force; modal damping zeta 0.005, 0.01, 0.02).
The note with the formulas and their errors on TRAIN and the practice bank: codex-queue/reports/PRIORS_F08_F02_FOR_VALIDATOR_20261023.md.

`prior(x)` takes (n, 6) inputs in mm (the interface's order) and returns the (n, 7) outputs in the interface's order:
static_tip_mm_per_n, then (peak_tip_mm_per_n, peak_frequency_hz) for zeta 0.005, 0.01, 0.02.
It is a prior, never the exam reference: the scored outputs are the learned model's.
"""

from __future__ import annotations

import math

import jax.numpy as jnp

PRIOR_ID = "prior.f08.cantilever-beam-v1"
INPUTS = ("length_mm", "width_mm", "thickness_mm", "rib_height_mm", "rib_thickness_mm", "relief_length_mm")
INPUT_BOUNDS = ((180.0, 260.0), (60.0, 100.0), (4.0, 8.0), (8.0, 16.0), (3.0, 5.0), (20.0, 60.0))
N_OUT = 7
#: Every output is a positive physical quantity, so a learned model may work in log space on any of them.
POSITIVE_OUTPUTS = (0, 1, 2, 3, 4, 5, 6)
E_PA, RHO, RELIEF_WIDTH_M = 70e9, 2700.0, 0.020
ZETAS = (0.005, 0.01, 0.02)
CANTILEVER_TIP_MASS = 33.0 / 140.0


def _section(w, t, tr, hr, relief):
    """(area, second moment about the neutral axis) of the plate with two ribs, the plate narrowed by the relief width if asked."""
    plate_w = w - RELIEF_WIDTH_M if relief else w
    a_plate, z_plate = plate_w * t, t / 2
    a_rib, z_rib = tr * hr, t + hr / 2
    area = a_plate + 2 * a_rib
    z_c = (a_plate * z_plate + 2 * a_rib * z_rib) / area
    inertia = (
        plate_w * t**3 / 12
        + a_plate * (z_plate - z_c) ** 2
        + 2 * (tr * hr**3 / 12 + a_rib * (z_rib - z_c) ** 2)
    )
    return area, inertia


def prior(x):
    """(n, 6) inputs in mm -> (n, 7) outputs."""
    x = jnp.asarray(x) * 1e-3
    length, w, t, hr, tr, relief = (x[:, i] for i in range(6))
    area_full, inertia_full = _section(w, t, tr, hr, False)
    area_relief, inertia_relief = _section(w, t, tr, hr, True)
    start, stop = length / 2 - relief / 2, length / 2 + relief / 2

    def segment(low, high):
        return ((length - low) ** 3 - (length - high) ** 3) / 3.0

    zero = jnp.zeros_like(length)
    delta = (segment(zero, start) + segment(stop, length)) / (E_PA * inertia_full) + segment(start, stop) / (
        E_PA * inertia_relief
    )
    mass = RHO * (area_full * (length - relief) + area_relief * relief)
    frequency = jnp.sqrt(1.0 / delta / (CANTILEVER_TIP_MASS * mass)) / (2 * math.pi)
    columns = [delta * 1e3]
    for zeta in ZETAS:
        columns += [delta * 1e3 / (2 * zeta), frequency * math.sqrt(1 - 2 * zeta * zeta)]
    return jnp.concatenate([column[:, None] for column in columns], axis=1)
