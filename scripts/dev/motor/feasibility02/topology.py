"""Motor customer feasibility (CHALLENGE-CUSTOMER-FEASIBILITY-02, #758 at
1ac5acfa): the revised design grammar as plain data. DEVELOPMENT only; the
registered motor Challenge (`carbon/motor`) is unchanged.

- **Topologies.** The 8-pole/24-slot single-layer control (the registered
  deck's frame) and a 10-pole/12-slot double-layer tooth winding. The tooth
  coils' phases come from the star of slots (`tooth_phases`), not a typed
  list, and the fundamental winding factor is checked (`winding_factor`).
- **Geometry.** Magnet thickness 1.5-4 mm, coverage 0.65-0.95 of pole pitch,
  air gap 0.3-1.0 mm, tooth width 0.20-0.40 of the bore slot pitch, slot
  opening 0.03-0.12 of the slot pitch, slot bottom radius 34-42 mm; the
  registered frame's fixed radii, stack and materials.
- **Commands.** Current density J in A/mm^2 over each coil region (the
  registered deck's convention: the source density equals J, so turns and
  phase amperes do not enter the magnetostatic solve) and current angle in
  electrical degrees from the q-axis.
- **Skew.** Three equal slices with rotor offsets -s/2, 0, +s/2 (mechanical);
  every slice sees the same phase currents, so slice k is the 2D solve at
  rotor angle theta + d_k with current angle gamma - p d_k. Each 2D slice is
  a full-stack-equivalent curve and the stack's curve is their mean (1/3
  each, applied once).
"""

from __future__ import annotations

import cmath
import hashlib
import math
import random

FIXED = {
    "r_shaft": 10.5,
    "r_ro": 25.6,
    "r_so": 46.0,
    "tip_h": 0.6,
    "wedge_h": 0.34,
    "length": 35.0,
    "br": 1.2,
    "mur_m": 1.0,
}
GRAMMAR = {
    "magnet_mm": (1.5, 4.0),
    "coverage": (0.65, 0.95),
    "airgap_mm": (0.3, 1.0),
    "tooth_frac": (0.20, 0.40),
    "opening_frac": (0.03, 0.12),
    "slot_bottom_mm": (34.0, 42.0),
}
TOPOLOGIES = {
    "8p24s": {"poles": 8, "slots": 24, "layers": 1},
    "10p12s": {"poles": 10, "slots": 12, "layers": 2},
}
SKEW_SPANS_DEG = (0.0, 2.0, 4.0)
MIN_SLOT_WIDTH_MM = 1.0
MIN_CLEARANCE_MM = 0.2
MIN_DEPTH_MM = 1.0
MIN_YOKE_MM = 1.0


def tooth_phases(poles, slots):
    """(phase, sign) per tooth coil for a double-layer tooth winding: each
    coil's EMF phasor is at p * (tooth angle) electrical; 60-degree belts
    [-30, 30) A+, [30, 90) C-, [90, 150) B+, [150, 210) A-, [210, 270) C+,
    [270, 330) B-."""
    pp = poles // 2
    belts = [("A", 1), ("C", -1), ("B", 1), ("A", -1), ("C", 1), ("B", -1)]
    out = []
    for t in range(slots):
        angle = (pp * 360.0 * t / slots + 30.0) % 360.0
        out.append(belts[int(angle // 60.0)])
    return out


def winding_table(topology):
    """(phase, sign) per coil region, in region order (201, 202, ...)."""
    poles, slots, layers = (topology[k] for k in ("poles", "slots", "layers"))
    if layers == 1:
        if slots != 3 * poles:
            raise ValueError("single layer needs one slot per pole per phase")
        pattern = [("A", 1), ("C", -1), ("B", 1), ("A", -1), ("C", 1), ("B", -1)]
        return [pattern[k % 6] for k in range(slots)]
    coils = tooth_phases(poles, slots)
    table = []
    for k in range(slots):
        # Slot k lies between tooth k and tooth k+1: its lower-angle side
        # holds tooth k's return conductor, its higher side tooth k+1's go.
        phase, sign = coils[k]
        table.append((phase, -sign))
        phase, sign = coils[(k + 1) % slots]
        table.append((phase, sign))
    return table


def region_angles(topology):
    """The mechanical angle (rad) of each coil region's slot centre (the
    textbook winding-factor convention: both layers at the slot centre)."""
    slots, layers = topology["slots"], topology["layers"]
    pitch = 2 * math.pi / slots
    return [(k + 0.5) * pitch for k in range(slots) for _ in range(layers)]


def current_offset_deg(topology):
    """The electrical offset alpha0 in i_A = I cos(p theta + alpha0 + gamma)
    that puts gamma = 0 on the q-axis. The registered deck uses -120 for its
    8p/24s winding, whose phase-A conductor axis is at 30 degrees; another
    winding keeps the same relation to its own phase-A axis (magnet 0's
    d-axis is at 90 electrical in both). Verified by a gamma sweep."""
    axis = winding_factor(topology)["A"][1]
    return (-120.0 - (axis - 30.0) + 180.0) % 360.0 - 180.0


def winding_factor(topology):
    """Fundamental winding factor of phase A and the electrical angles of
    the three phase axes (degrees)."""
    pp = topology["poles"] // 2
    table = winding_table(topology)
    angles = region_angles(topology)
    axes = {}
    for phase in "ABC":
        z = sum(
            sign * cmath.exp(1j * pp * a)
            for (ph, sign), a in zip(table, angles)
            if ph == phase
        )
        conductors = sum(ph == phase for ph, _ in table)
        axes[phase] = (abs(z) / conductors, math.degrees(cmath.phase(z)) % 360)
    return axes


def geometry(topology, design):
    """The mesh builder's parameters (mm) for a topology and design."""
    f = FIXED
    slots, poles = topology["slots"], topology["poles"]
    r_si = f["r_ro"] + design["airgap_mm"]
    return {
        "poles": poles,
        "slots": slots,
        "layers": topology["layers"],
        "r_shaft": f["r_shaft"],
        "r_ro": f["r_ro"],
        "h_m": design["magnet_mm"],
        "embrace": design["coverage"],
        "gap": design["airgap_mm"],
        "r_si": r_si,
        "tip_h": f["tip_h"],
        "wedge_h": f["wedge_h"],
        "slot_open_deg": design["opening_frac"] * 360.0 / slots,
        "tooth_w": design["tooth_frac"] * 2 * math.pi * r_si / slots,
        "r_sb": design["slot_bottom_mm"],
        "r_so": f["r_so"],
    }


def _slot_width(g, r):
    return 2 * r * math.sin(math.pi / g["slots"]) - g["tooth_w"]


def validity(topology, design):
    """Reasons the design cannot be built; empty when it can."""
    for name, (low, high) in GRAMMAR.items():
        if not low <= design[name] <= high:
            return [f"{name} outside [{low}, {high}]"]
    g = geometry(topology, design)
    reasons = []
    r_tip = g["r_si"] + g["tip_h"]
    r_body = r_tip + g["wedge_h"]
    opening = 2 * r_tip * math.sin(math.radians(g["slot_open_deg"]) / 2)
    width = MIN_SLOT_WIDTH_MM * (2 if topology["layers"] == 2 else 1)
    if _slot_width(g, r_body) < width:
        reasons.append("the slot is too narrow where the coil starts")
    if opening > _slot_width(g, r_tip) - MIN_CLEARANCE_MM:
        reasons.append("the slot opening is wider than the slot behind it")
    if g["r_sb"] <= r_body + MIN_DEPTH_MM:
        reasons.append("the slot is too shallow")
    if g["r_so"] - g["r_sb"] < MIN_YOKE_MM:
        reasons.append("the yoke is too thin")
    return reasons


def coil_side_area_mm2(topology, design):
    """One coil region's area, from the same polygon the mesh builds."""
    g = geometry(topology, design)
    pitch = 2 * math.pi / g["slots"]
    centre = 0.5 * pitch
    r_body = g["r_si"] + g["tip_h"] + g["wedge_h"]
    w = g["tooth_w"] / 2

    def edge(r, side):
        a = centre + side * pitch / 2
        b = a - side * math.asin(min(1.0, w / r))
        return r * math.cos(b), r * math.sin(b)

    poly = [edge(r_body, -1), edge(g["r_sb"], -1), edge(g["r_sb"], 1), edge(r_body, 1)]
    area = (
        abs(
            sum(
                poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1]
                for i in range(4)
            )
        )
        / 2
    )
    return area / topology["layers"]


def draw(label, count, topology):
    """`count` buildable public designs, uniform over the grammar."""
    seed = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")
    rng = random.Random(seed)
    out, attempts = [], 0
    while len(out) < count:
        attempts += 1
        if attempts > 1000 * count:
            raise RuntimeError("too few buildable designs")
        design = {k: rng.uniform(*v) for k, v in GRAMMAR.items()}
        if not validity(topology, design):
            out.append(design)
    return out, attempts


def slice_curve(curve, offset_steps):
    """A periodic curve sampled on one period, read at theta + offset."""
    n = len(curve)
    return [curve[(j + offset_steps) % n] for j in range(n)]


def stack_curve(slices):
    """The stack's torque from full-stack-equivalent slice curves: their
    mean (each slice is 1/3 of the stack)."""
    return [sum(values) / len(values) for values in zip(*slices)]


def metrics(curve):
    mean = sum(curve) / len(curve)
    pk = max(curve) - min(curve)
    return {
        "mean_nm": mean,
        "pk_pk_nm": pk,
        "ripple_fraction": pk / abs(mean) if mean else None,
        "max_nm": max(curve),
        "min_nm": min(curve),
    }
