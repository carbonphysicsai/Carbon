"""Motor 1.9's model row: Motor 1.8's 240-wide row (`carbon.motor.row18`, unchanged) plus ONE scalar,
``magnet_min_b_t``, at column 240 (owner MAGNET CELLS MOTOR, 21 Nov 2026; MOTOR_19_REGISTRATION_DRAFT 'Interface
change'). TRAIN, the prediction, the grade and the practice tools share this one public layout; it imports nothing
sealed, so the public kit and the local scorer read it as the grade does (`carbon.scoring.motor19_dual_pack`
re-exports it).

``magnet_min_b_t`` (tesla) is the minimum over the 60 rotor steps of the magnet's flux density, which is the minimum
over the electrical cycle (PERIOD_DEG 15). It is one value per design and condition, never a waveform. A change here
is a change of the 1.9 interface.
"""

from __future__ import annotations

import math

from . import row18

#: The 1.8 slices, in their order, then the one 1.9 scalar.
ROW = (*row18.ROW, "magnet_min_b_t")
#: The scalar outputs after the 60-step slices, in row order.
SCALARS = ("magnet_min_b_t",)
WIDTH = row18.WIDTH + len(SCALARS)


def split(raw):
    """One 1.9 row -> ``{slice name: its 60 finite values}`` over row18's slices, plus ``{"magnet_min_b_t": float}``;
    None for any other width or a non-finite value (a 240-wide 1.8 row is not a 1.9 answer).
    """
    try:
        row = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    if len(row) != WIDTH or not all(math.isfinite(v) for v in row):
        return None
    parts = row18.split(row[: row18.WIDTH])
    if parts is None:
        return None
    for offset, name in enumerate(SCALARS):
        parts[name] = row[row18.WIDTH + offset]
    return parts


def linkages(raw):
    """The phase flux linkages of a 1.9 row in `carbon.motor.back_emf`'s form ``{"a", "b", "c"}``, or None."""
    parts = split(raw)
    if parts is None:
        return None
    return {phase: parts["phase_flux_linkage_wb_" + phase.upper()] for phase in "abc"}
