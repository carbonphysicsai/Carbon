"""The battery exam's frozen calibration (OD-2).

The tolerances and TRAIN scales the exam-design campaign froze, pinned by the
exact bytes of its committed prepare record, and the prediction shapes every
scorer checks. Used by practice and by the validator daemon; neither may use
any other calibration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import exam
from .challenge import CAPACITY_CYCLES, GRID_POINTS

PREPARE_PATH = "docs/development/evidence/exam-design-2026-09-24/prepare.json"
PREPARE_SHA256 = "b23e3151d21eadd7fa63950ad41f6460d9fe21d75a345f825adcfa44182d5e99"
SHAPES = {
    "voltage_v": (GRID_POINTS,),
    "temperature_c": (GRID_POINTS,),
    "plating_margin_v": (),
    "capacity_ah": (len(CAPACITY_CYCLES),),
}


def frozen_calibration(root="."):
    """The campaign's frozen tolerances and TRAIN scales (OD-2), pinned by the
    exact bytes of the committed prepare record."""
    body = (Path(root) / PREPARE_PATH).read_bytes()
    if hashlib.sha256(body).hexdigest() != PREPARE_SHA256:
        raise ValueError("the frozen calibration does not match its pinned digest")
    prep = json.loads(body)
    tol = exam.Tolerances(
        **{
            k: prep["tolerances"][k]
            for k in (
                "tau_v0",
                "tau_t0",
                "tau_vmax",
                "tau_vmin",
                "q_bound",
                "v_max",
                "v_min",
            )
        }
    )
    return tol, prep["scales"]
