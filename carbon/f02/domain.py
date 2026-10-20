"""F02's exam inputs: one rectangular burst schedule in the fixed cold context.

The context (coolant 30 degC, h 2500 W/m^2K, initial 40 degC, left-source
fraction 0.5, rectangular pulse) is the one TRAIN40-v2 and the development
exam use (`carbon.challenge_kit.f02_train.CONTEXT`); only the schedule varies.
"""

from __future__ import annotations

INPUTS = ("peak_w", "on_time_s")
LIMIT_C = 95.0
