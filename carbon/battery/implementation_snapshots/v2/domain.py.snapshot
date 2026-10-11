"""The battery Challenge's interface as plain data: constants and TRAIN arrays.

Numpy only, with no Carbon imports, so the exact bytes of this module, the
recipes and the training loop can be staged into the isolated research worker
(`carbon.battery.practice`). `challenge` re-exports everything here and adds
the registered identity and the pinned public material.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

INPUTS = ("c1", "c2", "t_amb_c", "soc0")
INPUT_BOUNDS = {
    "c1": (0.5, 2.0),
    "c2": (0.2, 1.0),
    "t_amb_c": (5.0, 40.0),
    "soc0": (0.05, 0.5),
}
V_MIN, V_MAX = 2.5, 4.2
GRID_STEP_S, WINDOW_S = 30, 3600
GRID_POINTS = WINDOW_S // GRID_STEP_S + 1
CAPACITY_CYCLES = (1, 10, 20, 30)
OUTPUTS = ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah")

#: The published important region (provisional DEVELOPMENT values, OD-2): a
#: reference plating margin within 5 mV of zero, or a reference peak
#: temperature of at least 55 C. It is defined from reference data alone.
PLATING_BAND_V = 0.005
T_IMPORTANT_C = 55.0


def is_important(record):
    return (
        abs(record["outputs"]["plating_margin_v"]) <= PLATING_BAND_V
        or record.get("diagnostics", {}).get("t_max_c", -1e9) >= T_IMPORTANT_C
    )


@dataclass(frozen=True)
class TrainingData:
    """TRAIN arrays in the recipe's layout. Built only from pinned material."""

    x: np.ndarray  # (n, 4) c1, c2, t_amb_c, soc0
    v: np.ndarray  # (n, G)
    t: np.ndarray  # (n, G)
    eta: np.ndarray  # (n,)
    q: np.ndarray  # (n, K)
    case_ids: tuple[str, ...]
    #: Each TRAIN case's membership of the published important region.
    important: np.ndarray  # (n,) bool

    @staticmethod
    def from_records(records):
        outputs = [r["outputs"] for r in records]
        return TrainingData(
            np.array([[r["inputs"][k] for k in INPUTS] for r in records], float),
            np.array([o["voltage_v"] for o in outputs]),
            np.array([o["temperature_c"] for o in outputs]),
            np.array([o["plating_margin_v"] for o in outputs]),
            np.array([o["capacity_ah"] for o in outputs]),
            tuple(r["case_id"] for r in records),
            np.array([is_important(r) for r in records], bool),
        )

    def take(self, index):
        """The cases at `index`, in that order."""
        index = np.asarray(index)
        return TrainingData(
            self.x[index],
            self.v[index],
            self.t[index],
            self.eta[index],
            self.q[index],
            tuple(self.case_ids[i] for i in index),
            self.important[index],
        )

    def subset(self, count):
        """The first `count` cases: for bounded tests and diagnostics only."""
        return self.take(np.arange(count))
