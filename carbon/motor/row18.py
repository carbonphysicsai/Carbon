"""Motor 1.8's model row (owner 7 Nov evening: back-EMF in 1.8, the flux linkage in TRAIN): one public layout that
TRAIN, the prediction, the grade and the practice tools share. It imports nothing sealed, so the public kit and the
local scorer read it as the grade does (`carbon.scoring.motor18_dual_pack` re-exports it).

The row is four slices of the 60 rotor steps of one 15 degree mechanical window: the torque (N.m), then the per-phase
flux linkages A, B, C (Wb; the record-now runner's ``phase_flux_linkage_wb``). The 1.8 TRAIN interface declares the
same slices (mc-exam-B 7 Nov 20:35); a change here is a change of the 1.8 interface.
"""

from __future__ import annotations

import math

from .domain import ANGLE_STEPS

ROW = (
    "torque_nm",
    "phase_flux_linkage_wb_A",
    "phase_flux_linkage_wb_B",
    "phase_flux_linkage_wb_C",
)
WIDTH = len(ROW) * ANGLE_STEPS


def split(raw):
    """One 1.8 row -> ``{slice name: its 60 finite values}`` over `ROW`; None for any other width or a non-finite
    value (a torque-only 60-wide row is not a 1.8 answer)."""
    try:
        row = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    if len(row) != WIDTH or not all(math.isfinite(v) for v in row):
        return None
    return {
        name: row[k * ANGLE_STEPS : (k + 1) * ANGLE_STEPS] for k, name in enumerate(ROW)
    }


def linkages(raw):
    """The phase flux linkages of a 1.8 row in `carbon.motor.back_emf`'s form ``{"a", "b", "c"}``, or None."""
    parts = split(raw)
    if parts is None:
        return None
    return {phase: parts["phase_flux_linkage_wb_" + phase.upper()] for phase in "abc"}
