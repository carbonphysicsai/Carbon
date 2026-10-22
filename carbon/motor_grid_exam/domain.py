"""Motor's sealed-grid inputs: the motor domain's, split into the six geometry
inputs (designs) and the two operating inputs (conditions), as the decision
contract splits them (`customer_decision.DESIGN_VARIABLES` / `CONDITION_VARIABLES`)."""

from __future__ import annotations

from carbon.motor.domain import INPUT_BOUNDS, INPUTS

DESIGN_INPUTS = INPUTS[:6]
CONDITION_INPUTS = INPUTS[6:]
MIN_TORQUE_NM = 4.0
MAX_RIPPLE_FRACTION = 0.30

__all__ = [
    "CONDITION_INPUTS",
    "DESIGN_INPUTS",
    "INPUTS",
    "INPUT_BOUNDS",
    "MAX_RIPPLE_FRACTION",
    "MIN_TORQUE_NM",
]
