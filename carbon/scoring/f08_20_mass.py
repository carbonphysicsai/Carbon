"""Ribbed Bracket 2.0's ``cad_mass_kg``: EXACT from the inputs (U = 0), never a model output and never graded.

The closed form is exam-rb's ``rb20_physics_baseline.mass_kg`` (codex-queue/reports/RB20_PHYSICS_BASELINE_20261121,
sha256 f027fcd8..., lines 115-120), copied as math only:

    vol  = L W t + 2 L tr hr + 4 L (1 - pi/4) rf^2 - (lr RELIEF_W - (4 - pi) RELIEF_R^2) t       [mm^3]
    mass = rho vol 1000                                                                          [kg; rho in t/mm^3]

The relief slot is ``RELIEF_W_MM`` x ``lr`` with corner radius ``RELIEF_R_MM`` (the deck's fixed geometry). The density
comes from the SIGNED alloy table (OWNER-F08-V2-ALLOYS-SIGNED-01, ``f08_v2_alloy_table.json`` sha256 d5b8cc56...), in
the deck's unit conversion (kg/m^3 x 1e-12 = t/mm^3, `f08_deck_v2.KG_M3_TO_T_MM3`), by ``alloy_index`` in
`f08_v2_train.ALLOY_IDS` order. The three densities are carried here so a grade never reads a scripts file; a test pins
them to the signed file and its sha256, and the formula to all 240 public TRAIN rows (public table cd78ee98).

It lives in ``carbon/scoring`` so it is inside RB 2.0's producer identity (`f08_20_dual_pack.FILES`): the pool derive
runs it on every answer.
"""

from __future__ import annotations

import math

#: The deck's fixed relief slot (f08_deck_v2 / rb20_physics_baseline).
RELIEF_W_MM = 20.0
RELIEF_R_MM = 3.0
#: kg/m^3 -> t/mm^3 (f08_deck_v2.KG_M3_TO_T_MM3).
KG_M3_TO_T_MM3 = 1e-12
#: The signed table's rho_kg_m3, by alloy_index (6061-T6, 4130-normalized, Ti-6Al-4V-annealed).
RHO_KG_M3 = (2712.6, 7833.4, 4428.8)
#: The inputs the mass reads, by their interface names (`f08_v2_train.INPUT_NAMES`).
INPUTS = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
    "fillet_radius_mm",
    "alloy_index",
)


class MassRefused(ValueError):
    """The inputs give no mass (a missing or non-finite input, or an alloy_index outside 0 / 1 / 2)."""


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def cad_mass_kg(inputs) -> float:
    """``cad_mass_kg`` of one 2.0 design, ``inputs`` = {interface name: value} (extra names are ignored)."""
    if type(inputs) is not dict:
        raise MassRefused("mass_inputs_malformed")
    for name in INPUTS:
        if not _finite(inputs.get(name)):
            raise MassRefused("mass_input_missing_" + name)
    alloy = inputs["alloy_index"]
    if float(alloy) not in (0.0, 1.0, 2.0):
        raise MassRefused("mass_alloy_index")
    length, width, thickness, rib_h, rib_t, relief_l, fillet = (
        float(inputs[name]) for name in INPUTS[:7]
    )
    vol = (
        length * width * thickness
        + 2.0 * length * rib_t * rib_h
        + 4.0 * length * (1.0 - math.pi / 4.0) * fillet**2
    )
    vol -= (relief_l * RELIEF_W_MM - (4.0 - math.pi) * RELIEF_R_MM**2) * thickness
    rho = RHO_KG_M3[int(alloy)] * KG_M3_TO_T_MM3
    return rho * vol * 1000.0


__all__ = ["INPUTS", "RHO_KG_M3", "MassRefused", "cad_mass_kg"]
