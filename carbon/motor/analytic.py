"""The textbook surface-PM torque model: the motor's conventional baseline.

#344 asks for an analytical baseline beside the learned one. This is the
classical sizing model of a surface-mounted PM machine with linear iron:

- **Airgap field under a magnet:** B_g = Br h_m / (h_m + mu_r g_e), with the
  effective gap g_e = k_c g and Carter's coefficient for the slot openings,
  k_c = tau_s / (tau_s - gamma g), gamma = (b_o/g)^2 / (5 + b_o/g).
- **Fundamental:** B_1 = (4/pi) B_g sin(embrace pi/2) for a radially
  magnetized arc of the given pole embrace.
- **Flux linkage:** psi_m = N_ph k_w1 B_1 D L / p, with D the mean airgap
  diameter, N_ph the series turns per phase and k_w1 = 1 (full-pitch,
  one slot per pole per phase).
- **Torque:** T = (3/2) p psi_m I cos(gamma): no reluctance torque (surface
  magnets, mu_r = 1), no saturation, no slotting or cogging, so the
  predicted torque is the same at every rotor angle.

What it leaves out is what the Challenge exists to capture: saturation (rung
M2: about 10 % of the torque at 10.9 A on the benchmark machine), cogging and
torque ripple. Its error against the reference is measured, not assumed.
"""

from __future__ import annotations

import math

from .domain import ANGLE_STEPS, FIXED, check_inputs, current_amplitude_a, geometry


def predict(case):
    case = check_inputs(case)
    g = geometry(case)
    f = FIXED
    pairs = f["poles"] // 2
    gap = g["gap"]
    r_si = g["r_si"]
    tau_s = 2 * math.pi * r_si / f["slots"]
    b_o = r_si * math.radians(g["slot_open_deg"])
    ratio = b_o / gap
    carter = tau_s / (tau_s - ratio * ratio / (5 + ratio) * gap)
    b_g = f["br"] * g["h_m"] / (g["h_m"] + f["mur_m"] * carter * gap)
    b_1 = 4 / math.pi * b_g * math.sin(g["embrace"] * math.pi / 2)
    diameter = 2 * (g["r_ro"] + gap / 2) * 1e-3
    length = f["length"] * 1e-3
    # Single layer, one slot per pole per phase: each phase has slots/3 coil
    # sides, slots/6 coils in series, `turns` turns each.
    series_turns = f["slots"] / 6 * f["turns"]
    psi = series_turns * b_1 * diameter * length / pairs
    current = current_amplitude_a(case)
    torque = (
        1.5 * pairs * psi * current * math.cos(math.radians(case["current_angle_deg"]))
    )
    return {
        "torque_nm": [torque] * ANGLE_STEPS,
        "diagnostics": {
            "carter": carter,
            "airgap_b_t": b_g,
            "fundamental_b_t": b_1,
            "flux_linkage_wb": psi,
            "current_a": current,
        },
    }
