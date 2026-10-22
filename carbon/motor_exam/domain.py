"""Motor's sealed-exam inputs and decision limits: the motor domain's inputs,
and the exam QA's limits (mean torque at least 4.0 N.m, peak-to-peak ripple at
most 0.30 of it), used here for placement only."""

from __future__ import annotations

from carbon.motor.domain import INPUT_BOUNDS, INPUTS

MIN_TORQUE_NM = 4.0
MAX_RIPPLE_FRACTION = 0.30

__all__ = ["INPUTS", "INPUT_BOUNDS", "MAX_RIPPLE_FRACTION", "MIN_TORQUE_NM"]
