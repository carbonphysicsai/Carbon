"""Identity and pinned public material for the Motor Challenge.

Only public TRAIN and PRACTICE records are reachable here. The private pool,
decision-study reference results and future confirmation material deliberately
have no path or loader in this construction module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.capability_registry import MOTOR_CHALLENGE, MOTOR_CONTRACT
from carbon.registry import ChallengeKey

from .domain import ANGLE_STEPS, INPUT_BOUNDS, INPUTS, PREDICTED

CHALLENGE = ChallengeKey(MOTOR_CHALLENGE, MOTOR_CONTRACT.version)
IDENTITY = MOTOR_CONTRACT.identity

TRAIN_PATH = "docs/development/evidence/motor-pools-v1/train.jsonl"
PRACTICE_PATH = "docs/development/evidence/motor-pools-v1/practice.jsonl"
CALIBRATION_PATH = "docs/development/evidence/motor-pools-v1/baselines.json"
TRAIN_SHA256 = "d027f71133f2fdc0c74d2b62bdfc2fbeff445062f638dd2888f4f54c17389d4e"
PRACTICE_SHA256 = "0466627106bdcf8495b96a93ea89e5d5270ad845171d6770bac2b2d9922dd247"
CALIBRATION_SHA256 = "443006e780b00f92e0f7539ab12224e9f229f21c98df770964301aef57a3da88"
TRAIN_CASES = 150
PRACTICE_CASES = 30


class MaterialMismatch(ValueError):
    """Public material does not match its registered bytes and shape."""


def canonical_text(path, expected, name):
    """Return Git/LF bytes after checking the registered digest."""

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
        curve = record.get("outputs", {}).get("torque_nm")
        if (
            type(record) is not dict
            or record.get("case_id") != f"{prefix}-{index:04d}"
            or record.get("status") != "OK"
            or set(record.get("inputs", {})) != set(INPUTS)
            or type(curve) is not list
            or len(curve) != ANGLE_STEPS
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
        learned = calibration_document.get("learned", {})
        if learned.get("length") != 4.0 or learned.get("ridge") != 1e-4:
            raise MaterialMismatch("calibration winner differs")
        return PublicMaterial(
            _records(train, TRAIN_CASES, "train", "train"),
            _records(practice, PRACTICE_CASES, "practice", "practice"),
            calibration_document,
        )


PUBLIC_OUTPUTS = {"torque_nm": {"unit": "N.m", "shape": [ANGLE_STEPS]}}


def interface_document():
    return {
        "inputs": {name: list(INPUT_BOUNDS[name]) for name in INPUTS},
        "outputs": dict(PUBLIC_OUTPUTS),
        "predicted": list(PREDICTED),
    }
