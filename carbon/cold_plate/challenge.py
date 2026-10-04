"""Identity and pinned public material for the cold-plate Challenge.

Only the public TRAIN and PRACTICE records are reachable here.  Counted CFD,
the private pool and any future confirmation material deliberately have no
path or loader in this construction module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.capability_registry import (
    COLD_PLATE_CHALLENGE,
    COLD_PLATE_CONTRACT,
)
from carbon.registry import ChallengeKey

from .domain import INPUT_BOUNDS, INPUTS, PREDICTED, PROFILE_SEGMENTS

CHALLENGE = ChallengeKey(COLD_PLATE_CHALLENGE, COLD_PLATE_CONTRACT.version)
IDENTITY = COLD_PLATE_CONTRACT.identity

TRAIN_PATH = "docs/development/evidence/cold-plate-pools-v1/train.jsonl"
PRACTICE_PATH = "docs/development/evidence/cold-plate-pools-v1/practice.jsonl"
CALIBRATION_PATH = "docs/development/evidence/cold-plate-pools-v1/baselines.json"
TRAIN_SHA256 = "122e001e7ff9f6faefe4e1c558e936089cdc38b6b6dbe8728278812c9d8a6582"
PRACTICE_SHA256 = "a541d43e4a8b59f9704aa642e1c19f1c6725f59d5d60f804d5c20660e50111be"
CALIBRATION_SHA256 = "52236abadb40913e638a8ff5c5d0ff76728b52d27a76b4d6ecadf590852e1aa6"
TRAIN_CASES = 400
PRACTICE_CASES = 100


class MaterialMismatch(ValueError):
    """Public material does not match its registered bytes and shape."""


def canonical_text(path, expected, name):
    """Git/LF bytes, verified even from a CRLF Windows checkout."""

    body = Path(path).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(body).hexdigest() != expected:
        raise MaterialMismatch(name + " does not match its pinned digest")
    return body


def _records(body, count, prefix, name):
    try:
        records = tuple(json.loads(line) for line in body.splitlines() if line.strip())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterialMismatch(name + " is not JSON lines") from error
    if len(records) != count:
        raise MaterialMismatch(f"{name} is not {count} records")
    for index, record in enumerate(records):
        if (
            type(record) is not dict
            or record.get("case_id") != f"{prefix}-{index:04d}"
            or record.get("status") != "OK"
            or set(record.get("inputs", {})) != set(INPUTS)
            or set(record.get("outputs", {}))
            < {"peak_c", "profile_c", "pressure_drop_pa"}
            or len(record["outputs"]["profile_c"]) != PROFILE_SEGMENTS
        ):
            raise MaterialMismatch(name + " record shape differs")
    return records


@dataclass(frozen=True)
class PublicMaterial:
    """Verified public records used by construction and practice."""

    train: tuple[dict, ...]
    practice: tuple[dict, ...]
    calibration: dict

    @staticmethod
    def load(root="."):
        root = Path(root)
        train = canonical_text(root / TRAIN_PATH, TRAIN_SHA256, "train")
        practice = canonical_text(root / PRACTICE_PATH, PRACTICE_SHA256, "practice")
        calibration = canonical_text(
            root / CALIBRATION_PATH, CALIBRATION_SHA256, "calibration"
        )
        try:
            calibration_document = json.loads(calibration)
        except json.JSONDecodeError as error:
            raise MaterialMismatch("calibration is not JSON") from error
        return PublicMaterial(
            _records(train, TRAIN_CASES, "train", "train"),
            _records(practice, PRACTICE_CASES, "practice", "practice"),
            calibration_document,
        )


PUBLIC_OUTPUTS = {
    "peak_c": {"unit": "degC", "shape": []},
    "profile_c": {"unit": "degC", "shape": [PROFILE_SEGMENTS]},
    "pressure_drop_pa": {"unit": "Pa", "shape": []},
}


def interface_document():
    return {
        "inputs": {name: list(INPUT_BOUNDS[name]) for name in INPUTS},
        "outputs": dict(PUBLIC_OUTPUTS),
        "predicted": list(PREDICTED),
    }
