"""Cooling's sealed-exam inputs: the counted nine (`carbon.cold_plate.domain`),
split as the development exam splits them into a design (geometry and flow
policy) and an operating condition, and its two decision limits (the
registered synthetic decision study, AI_ACCELERATOR_COOLING_SYNTHETIC_V1)."""

from __future__ import annotations

from carbon.cold_plate.domain import INPUTS

DESIGN_INPUTS = (
    "channel_width_mm",
    "fin_width_mm",
    "channel_depth_mm",
    "flow_lpm_per_kw",
)
CONDITION_INPUTS = (
    "inlet_c",
    "heat_load_w",
    "hotspot_ratio",
    "hotspot_center_mm",
    "hotspot_width_mm",
)
DIE_LIMIT_C = 100.0
HYDRAULIC_LIMIT_W = 0.25

__all__ = [
    "CONDITION_INPUTS",
    "DESIGN_INPUTS",
    "DIE_LIMIT_C",
    "HYDRAULIC_LIMIT_W",
    "INPUTS",
]
