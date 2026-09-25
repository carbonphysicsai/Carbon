"""The battery Challenge's identity, interface and pinned public material.

Values are the exam-design campaign's pinned reference configuration
(`scripts/dev/exam_design/battery_reference.py` SPEC), restated here so the
runtime never imports research scripts. A test holds the two equal.

The reference is PyBaMM's DFN under OKane2022, not a real cell. Agreement with
it says nothing about real-cell lifetime or safety.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    BATTERY_CONTRACT,
)
from carbon.registry import ChallengeKey

CHALLENGE = ChallengeKey(BATTERY_CHALLENGE, BATTERY_CONTRACT.version)
IDENTITY = BATTERY_CONTRACT.identity

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

#: The campaign's retained public files, pinned by their exact bytes.
OCV_TABLE_SHA256 = "847cb3e92acaca7340072ca5c5bea8e4e6273b3bffea09378ba672e5f93372d7"
TRAIN_V1_SHA256 = "3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3"
TRAIN_V1_CASES = 400
#: Where the campaign retained them, relative to the repository root.
OCV_TABLE_PATH = "docs/development/evidence/exam-design-2026-09-24/ocv_table.json"
TRAIN_V1_PATH = (
    "docs/development/evidence/exam-design-2026-09-24/datasets/train-v1.jsonl.gz"
)


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


class MaterialMismatch(ValueError):
    """Public material whose bytes are not the pinned bytes."""


def _pinned(path, expected, name):
    body = Path(path).read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise MaterialMismatch(name + " does not match its pinned digest")
    return body


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


@dataclass(frozen=True)
class PublicMaterial:
    """The OCV table and TRAIN v1, each verified against its pinned digest.

    A constructed value always holds verified material: `load` is the only
    constructor that reads bytes, and it refuses a mismatch by name.
    """

    ocv_soc: np.ndarray
    ocv_v: np.ndarray
    train: TrainingData

    @staticmethod
    def load(root="."):
        root = Path(root)
        table = json.loads(
            _pinned(root / OCV_TABLE_PATH, OCV_TABLE_SHA256, "ocv_table")
        )
        body = gzip.decompress(
            _pinned(root / TRAIN_V1_PATH, TRAIN_V1_SHA256, "train_v1")
        )
        records = [json.loads(line) for line in body.splitlines() if line.strip()]
        if len(records) != TRAIN_V1_CASES or any(
            r.get("role") != "train" or r.get("status") != "OK" for r in records
        ):
            raise MaterialMismatch("train_v1 is not 400 OK TRAIN cases")
        return PublicMaterial(
            np.asarray(table["soc"], float),
            np.asarray(table["ocv_v"], float),
            TrainingData.from_records(records),
        )
