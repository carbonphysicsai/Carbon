"""The photonic coupler test Challenge's interface as plain data (#345).

The exam-design campaign's coupler family, fixed (`scripts/dev/exam_design/
photonic_reference.py` SPEC): two identical 500 x 220 nm silicon strips in
silica (non-dispersive n 3.48 and 1.444), cosine S-bends of 3.0 um (left) and
2.0 um (right) to a 1.6 um port pitch. Two inputs set a case: the coupling
gap and length, within the campaign's bounds. The reference is the declared
local-supermode model (`carbon.photonic.coupler`, `reference`).

A DEVELOPMENT test Challenge under OWNER-CHALLENGE-DESIGN-01: cheap and exact
in its phase convention, of low engineering value for this symmetric family
(the reference model is itself the conventional design method;
CHALLENGE-PHOTONIC-01 D2).
"""

from __future__ import annotations

import math

INPUTS = ("gap_nm", "length_um")
INPUT_BOUNDS = {"gap_nm": (150.0, 300.0), "length_um": (1.0, 6.0)}
NOMINAL = {"gap_nm": 208.832, "length_um": 5.618}  # the campaign's diagnostic case
WIDTH_UM = 0.5
HEIGHT_UM = 0.22
N_SI, N_OX = 3.48, 1.444
BEND_LEFT_UM, BEND_RIGHT_UM = 3.0, 2.0
PORT_PITCH_UM = 1.6
WAVELENGTHS_UM = (1.50, 1.525, 1.55, 1.575, 1.60)
OUTPUTS = {
    "cross_power": ("1", (len(WAVELENGTHS_UM),)),
    "common_phase_rad": ("rad", (len(WAVELENGTHS_UM),)),
}
PREDICTED = ("cross_power", "common_phase_rad")
#: The supermode tables' gap ladder: geometric from the smallest admitted gap
#: to the port gap, where the bends end, so it holds every gap a case passes.
GAP_LADDER_COUNT = 41


def ladder(count=GAP_LADDER_COUNT):
    low, top = INPUT_BOUNDS["gap_nm"][0] * 1e-3, PORT_PITCH_UM - WIDTH_UM
    ratio = (top / low) ** (1 / (count - 1))
    gaps = [low * ratio**i for i in range(count)]
    gaps[0], gaps[-1] = low, top
    return gaps


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
