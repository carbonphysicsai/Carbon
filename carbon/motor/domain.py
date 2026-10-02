"""The motor Challenge's interface as plain data.

**What a case is.** One surface-mounted PM machine cross-section with a fixed
frame: 8 poles, 24 slots, a single-layer winding with one slot per pole per
phase, a fixed rotor surface, stator outer radius and stack length. Eight
inputs set it (`INPUTS`). The reference turns the rotor through one 15 degree
period (the cogging and the six-pulse torque period coincide for this slot
and pole count), with sinusoidal phase currents turning with it, and reports
the torque at `ANGLE_STEPS` evenly spaced angles.

**Provenance.** The fixed frame is the GRUCAD 8-pole benchmark machine
(Ferreira da Luz, Dular, Sadowski, Geuzaine and Bastos, IEEE Trans. Magn.
38(2), 2002); its published dimensions are used, its model files are not.
The ranges are DEVELOPMENT choices under OWNER-CHALLENGE-DESIGN-01. None is
a qualified population, tolerance or product claim.
"""

from __future__ import annotations

import math

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
INPUT_BOUNDS = {
    "magnet_mm": (1.5, 4.0),
    "embrace": (0.55, 0.95),
    "airgap_mm": (0.3, 1.0),
    "slot_open_deg": (1.0, 6.0),
    "tooth_mm": (2.5, 5.0),
    "slot_bottom_mm": (34.0, 42.0),
    "current_density_a_mm2": (0.0, 15.0),
    "current_angle_deg": (0.0, 60.0),
}
#: The GRUCAD machine's published values, at the nominal current density of
#: its 10.9 A over 104 turns in a 55.8 mm^2 slot (20.3 A/mm^2 lies above
#: this Challenge's range, so the nominal case uses 10).
NOMINAL = {
    "magnet_mm": 2.352,
    "embrace": 0.726,
    "airgap_mm": 0.42,
    "slot_open_deg": 3.7,
    "tooth_mm": 3.5,
    "slot_bottom_mm": 38.16,
    "current_density_a_mm2": 10.0,
    "current_angle_deg": 0.0,
}
FIXED = {
    "poles": 8,
    "slots": 24,
    "r_shaft": 10.5,
    "r_ro": 25.6,
    "r_so": 46.0,
    "tip_h": 0.6,
    "wedge_h": 0.34,
    "length": 35.0,
    "turns": 104,
    "br": 1.2,
    "mur_m": 1.0,
}
#: Rotor positions per 15 degree period: 0.25 degree apart.
ANGLE_STEPS = 60
PERIOD_DEG = 15.0
#: Airgap nodes: 1,440 gives 0.25 degree rotor steps (rung M1: Maxwell-stress
#: torque within about 2 % of the extrapolated value at the cogging peak).
N_GAP = 1440
H_MAX_MM = 1.0
#: Geometric validity margins, mm.
MIN_SLOT_WIDTH_MM = 1.0
MIN_OPENING_CLEARANCE_MM = 0.2
OUTPUTS = {"torque_nm": ("N.m", (ANGLE_STEPS,))}
PREDICTED = ("torque_nm",)


def check_inputs(case):
    if set(case) != set(INPUTS):
        raise ValueError("inputs must be exactly " + ", ".join(INPUTS))
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


def geometry(case):
    """The mesh builder's parameters, in mm, for a case."""
    case = check_inputs(case)
    f = FIXED
    return {
        "poles": f["poles"],
        "slots": f["slots"],
        "r_shaft": f["r_shaft"],
        "r_ro": f["r_ro"],
        "h_m": case["magnet_mm"],
        "embrace": case["embrace"],
        "gap": case["airgap_mm"],
        "r_si": f["r_ro"] + case["airgap_mm"],
        "tip_h": f["tip_h"],
        "wedge_h": f["wedge_h"],
        "slot_open_deg": case["slot_open_deg"],
        "tooth_w": case["tooth_mm"],
        "r_sb": case["slot_bottom_mm"],
        "r_so": f["r_so"],
        "n_gap": N_GAP,
        "h_max": H_MAX_MM,
    }


def slot_width_mm(g, r):
    """The slot's width at radius r between parallel-sided teeth."""
    pitch = 2 * math.pi / g["slots"]
    return 2 * r * math.sin(pitch / 2) - g["tooth_w"]


def validity(case):
    """Reasons a case's geometry cannot be built; empty when it can."""
    g = geometry(case)
    reasons = []
    r_tip = g["r_si"] + g["tip_h"]
    r_body = r_tip + g["wedge_h"]
    opening = 2 * r_tip * math.sin(math.radians(g["slot_open_deg"]) / 2)
    if slot_width_mm(g, r_body) < MIN_SLOT_WIDTH_MM:
        reasons.append("the slot is narrower than 1 mm where the coil starts")
    if opening > slot_width_mm(g, r_tip) - MIN_OPENING_CLEARANCE_MM:
        reasons.append("the slot opening is wider than the slot behind it")
    if g["r_sb"] <= r_body + 1.0:
        reasons.append("the slot is less than 1 mm deep")
    return reasons


def coil_polygon(case, k=0):
    """Slot k's coil as the mesh builds it (`carbon.motor.mesh`): the four
    points where the tooth edges meet the coil's inner and outer radii,
    joined by straight edges."""
    g = geometry(case)
    pitch = 2 * math.pi / g["slots"]
    centre = (k + 0.5) * pitch
    r_body = g["r_si"] + g["tip_h"] + g["wedge_h"]
    w = g["tooth_w"] / 2

    def edge(r, side):
        a = centre + side * pitch / 2
        b = a - side * math.asin(min(1.0, w / r))
        return r * math.cos(b), r * math.sin(b)

    return [edge(r_body, -1), edge(g["r_sb"], -1), edge(g["r_sb"], 1), edge(r_body, 1)]


def coil_area_mm2(case):
    """The coil's area, exactly as meshed (shoelace over `coil_polygon`)."""
    p = coil_polygon(case)
    return (
        abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p))))
        / 2
    )


def current_amplitude_a(case):
    """Peak phase current that gives the case's peak current density."""
    case = check_inputs(case)
    return case["current_density_a_mm2"] * coil_area_mm2(case) / FIXED["turns"]
