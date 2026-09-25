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

from .domain import (  # noqa: F401 - the interface, re-exported
    CAPACITY_CYCLES,
    GRID_POINTS,
    GRID_STEP_S,
    INPUT_BOUNDS,
    INPUTS,
    OUTPUTS,
    PLATING_BAND_V,
    T_IMPORTANT_C,
    V_MAX,
    V_MIN,
    WINDOW_S,
    TrainingData,
    is_important,
)

CHALLENGE = ChallengeKey(BATTERY_CHALLENGE, BATTERY_CONTRACT.version)
IDENTITY = BATTERY_CONTRACT.identity

#: The campaign's retained public files, pinned by their exact bytes.
OCV_TABLE_SHA256 = "847cb3e92acaca7340072ca5c5bea8e4e6273b3bffea09378ba672e5f93372d7"
TRAIN_V1_SHA256 = "3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3"
TRAIN_V1_CASES = 400
#: Where the campaign retained them, relative to the repository root.
OCV_TABLE_PATH = "docs/development/evidence/exam-design-2026-09-24/ocv_table.json"
TRAIN_V1_PATH = (
    "docs/development/evidence/exam-design-2026-09-24/datasets/train-v1.jsonl.gz"
)


class MaterialMismatch(ValueError):
    """Public material whose bytes are not the pinned bytes."""


def _pinned(path, expected, name):
    body = Path(path).read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise MaterialMismatch(name + " does not match its pinned digest")
    return body


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
