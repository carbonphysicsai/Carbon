# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The cold plate Challenge's interface as plain data.

Numpy only, with no Carbon imports, so the exact bytes can later be staged into
an isolated research worker, as `carbon.battery.domain` is.

**What a case is.** One copper plate on a 30 x 30 mm heated footprint, with
straight parallel channels running the footprint's length, cooled by PG25.
Nine inputs set it (`INPUTS`); everything else is fixed (`FIXED`). The
reference solves one repeating cell (half a channel and half a fin between
symmetry planes), so a case is the periodic interior of the plate: no headers,
manifolds or plate edges.

**The heat map** varies along the flow only: a hot band across the die, a
Gaussian on a uniform floor, normalized so the plate still receives the heat
load (`heat_flux`). A ratio of 1 is the uniform map. Variation across the
channels needs a multi-channel domain and is not in this version.

**Provenance.** Ranges and fixed values are the provisional design basis
(`scripts/dev/cold_plate/DESIGN_BASIS.md`), chosen under owner delegation. They
are DEVELOPMENT choices, not a qualified population, tolerance or product claim.
"""

from __future__ import annotations

import math

INPUTS = (
    "channel_width_mm",
    "fin_width_mm",
    "channel_depth_mm",
    "flow_lpm_per_kw",
    "inlet_c",
    "heat_load_w",
    "hotspot_ratio",
    "hotspot_center_mm",
    "hotspot_width_mm",
)
#: DESIGN_BASIS.md section 2. The hot spot's peak-to-average ratio is the
#: basis's "up to 3x the average"; its centre and width are section 2a's.
INPUT_BOUNDS = {
    "channel_width_mm": (0.2, 0.5),
    "fin_width_mm": (0.2, 0.5),
    "channel_depth_mm": (1.0, 3.0),
    "flow_lpm_per_kw": (1.25, 2.0),
    "inlet_c": (30.0, 45.0),
    "heat_load_w": (500.0, 1500.0),
    "hotspot_ratio": (1.0, 3.0),
    "hotspot_center_mm": (3.0, 27.0),
    "hotspot_width_mm": (1.5, 3.5),
}
NOMINAL = {
    "channel_width_mm": 0.3,
    "fin_width_mm": 0.3,
    "channel_depth_mm": 2.0,
    "flow_lpm_per_kw": 1.5,
    "inlet_c": 40.0,
    "heat_load_w": 1000.0,
    "hotspot_ratio": 1.0,
    "hotspot_center_mm": 15.0,
    "hotspot_width_mm": 2.5,
}
#: Fixed for every case. The footprint is square and the channels run its
#: whole length, so the channel length equals the footprint side.
FIXED = {
    "footprint_mm": 30.0,
    "base_mm": 1.0,
    "lid_mm": 0.5,
    #: Copper C11000 at 20 C (Copper Development Association); within about
    #: 1 % over 20-80 C, so constant.
    "copper_k_w_mk": 391.0,
}
#: The thermal interface (DESIGN_BASIS.md section 3): a uniform areal
#: resistance, m^2 K/W, added after the solve. Reported beside every result,
#: never part of a predicted output or the plate's score.
TIM_RESISTANCE_M2K_W = 5e-6

#: PG25 as polynomials in T (kelvin), value = sum c_i T^i, fitted to CoolProp
#: 6.8.0 `INCOMP::MPG[0.25]` at 2 bar over 30-99 C by
#: `scripts/dev/cold_plate/plate_channel/fit_properties.py` under its stated
#: selection rule. Largest relative residual, as written: rho 4e-16 and kappa
#: 4e-16 (the model itself is cubic in T), cp 8.2e-5, mu 1.7e-4.
PG25 = {
    "rho": (
        471.83672241567854,
        5.3710481851085525,
        -0.01615703005055183,
        1.4345731910287373e-05,
    ),
    "cp": (
        2927.6100828735266,
        4.2380574169872585,
        -0.002916907594152528,
    ),
    "kappa": (
        0.33130560354466126,
        -0.0005363884701318896,
        5.322835865529474e-06,
        -6.495569444909945e-09,
    ),
    "mu": (
        11.809225533760118,
        -0.19835015412139706,
        0.0013929060738771873,
        -5.23132660955004e-06,
        1.1076921123177383e-08,
        -1.2533006110289745e-11,
        5.917954657407082e-15,
    ),
}
#: Where the fits hold. CoolProp refuses 100 C, so no fluid may exceed 99 C.
PG25_VALID_C = (30.0, 99.0)
#: The design basis's laminar check (section 2): every case it computed stays
#: below this, under the usual straight-duct transition near 2,300.
RE_LAMINAR_MAX = 2000.0

#: The heated-face profile is the span-mean temperature averaged over each of
#: these many equal segments along the flow, inlet first.
PROFILE_SEGMENTS = 30
#: What the reference reports: output name -> (unit, shape).
OUTPUTS = {
    "peak_c": ("degC", ()),
    "mean_c": ("degC", ()),
    "profile_c": ("degC", (PROFILE_SEGMENTS,)),
    "outlet_c": ("degC", ()),
    "pressure_drop_pa": ("Pa", ()),
}
#: What a model predicts and is scored on. The other two are exact functions
#: of these and the inputs, so Carbon derives them (`derived_outputs`) and
#: grades nothing a model could get wrong only by ignoring arithmetic: the
#: mean is the mean of the 30 equal segments, and the outlet is the energy
#: balance (heat capacity is held at the inlet value in the reference).
PREDICTED = ("peak_c", "profile_c", "pressure_drop_pa")

K0 = 273.15


def pg25(name, t_kelvin):
    """One PG25 property at `t_kelvin` (scalar), from the pinned fit."""
    value = 0.0
    for c in reversed(PG25[name]):
        value = value * t_kelvin + c
    return value


def check_inputs(case):
    """The six inputs as floats, refused if any is missing, extra or outside
    its bounds. A refusal is a malformed request, never a reference result."""
    if set(case) != set(INPUTS):
        raise ValueError(
            "inputs must be exactly " + ", ".join(INPUTS) + f"; got {sorted(case)}"
        )
    values = {}
    for name in INPUTS:
        value = case[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        low, high = INPUT_BOUNDS[name]
        if not low <= value <= high:
            raise ValueError(f"{name}={value} is outside [{low}, {high}]")
        values[name] = float(value)
    return values


def channels(case):
    """The whole number of channel-plus-fin periods across the footprint."""
    period = case["channel_width_mm"] + case["fin_width_mm"]
    return int(FIXED["footprint_mm"] // period + 1e-9)


def derived(case):
    """Quantities every model and the reference compute the same way.

    The plate's flow is `heat_load_w / 1000 * flow_lpm_per_kw` L/min, shared
    equally by the channels and measured at the inlet temperature. The heat
    flux is the heat load over the whole footprint. The periodic cell carries
    that flux over the channels' span only, so where the period does not divide
    the footprint the coolant absorbs slightly less than the heat load
    (`absorbed_w`): a property of the cell model, not an error."""
    side = FIXED["footprint_mm"] * 1e-3
    n = channels(case)
    period = (case["channel_width_mm"] + case["fin_width_mm"]) * 1e-3
    area = case["channel_width_mm"] * case["channel_depth_mm"] * 1e-6
    flow = case["heat_load_w"] / 1000.0 * case["flow_lpm_per_kw"] / 60000.0
    t_in = K0 + case["inlet_c"]
    flux = case["heat_load_w"] / side**2
    amplitude, mean_shape = hotspot_shape(case)
    return {
        "channels": n,
        "flow_m3_s": flow,
        "inlet_velocity_m_s": flow / (n * area),
        "mass_flow_kg_s": pg25("rho", t_in) * flow,
        "heat_flux_w_m2": flux,
        "absorbed_w": flux * n * period * side,
        "hotspot_amplitude": amplitude,
        "hotspot_mean_shape": mean_shape,
    }


def derived_outputs(case, predicted):
    """The mean and the outlet, from a prediction and the inputs."""
    case = check_inputs(case)
    d = derived(case)
    cp = pg25("cp", K0 + case["inlet_c"])
    profile = list(predicted["profile_c"])
    return {
        "mean_c": sum(profile) / len(profile),
        "outlet_c": case["inlet_c"] + d["absorbed_w"] / (d["mass_flow_kg_s"] * cp),
    }


def hotspot_shape(case):
    """(a, s_bar) for the axial map q(x) = q_avg (1 + a g(x)) / s_bar, where
    g(x) = exp(-((x - x_c) / w)^2 / 2) and s_bar = 1 + a mean(g) over the
    channel length, so the map's mean is exactly q_avg. `a` is chosen so the
    largest value of q is `hotspot_ratio` times q_avg: (1 + a g_max) / s_bar
    = ratio, with g_max = 1 because the centre lies inside the channel."""
    ratio = case["hotspot_ratio"]
    length = FIXED["footprint_mm"]
    centre, width = case["hotspot_center_mm"], case["hotspot_width_mm"]
    root = width * math.sqrt(2.0)
    mean_g = (
        width
        * math.sqrt(math.pi / 2.0)
        / length
        * (math.erf((length - centre) / root) + math.erf(centre / root))
    )
    if ratio * mean_g >= 1.0:
        raise ValueError("this hot spot cannot reach that ratio")
    amplitude = (ratio - 1.0) / (1.0 - ratio * mean_g)
    return amplitude, 1.0 + amplitude * mean_g


def heat_flux(case, x_mm):
    """The map's heat flux, W/m^2, at `x_mm` along the flow from the inlet."""
    amplitude, mean_shape = hotspot_shape(case)
    g = math.exp(
        -0.5 * ((x_mm - case["hotspot_center_mm"]) / case["hotspot_width_mm"]) ** 2
    )
    side = FIXED["footprint_mm"] * 1e-3
    return case["heat_load_w"] / side**2 * (1.0 + amplitude * g) / mean_shape
