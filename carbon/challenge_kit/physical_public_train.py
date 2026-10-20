"""Pinned numeric transport for existing public Motor and Cooling TRAIN records.

The native JSONL remains the source of truth. These DEVELOPMENT-only NPZ files
make the same rows usable by the normal, non-Battery construction tensor codec;
they do not define a loss, a reference exam, or scientific qualification.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np

from carbon.cold_plate import challenge as cooling
from carbon.cold_plate import domain as cooling_domain
from carbon.motor import challenge as motor
from carbon.motor import domain as motor_domain

_DATA = Path(__file__).with_name("data")
_SCHEMA = "carbon.physical-public-train.provenance.v1"
_SCOPE = "PUBLIC_DEVELOPMENT_ONLY"
_INPUT_UNITS = {
    motor.CHALLENGE.challenge_id: (
        "millimetre",
        "dimensionless",
        "millimetre",
        "degree",
        "millimetre",
        "millimetre",
        "ampere_per_square_millimetre",
        "degree",
    ),
    cooling.CHALLENGE.challenge_id: (
        "millimetre",
        "millimetre",
        "millimetre",
        "litre_per_minute_per_kilowatt",
        "celsius",
        "watt",
        "dimensionless",
        "millimetre",
        "millimetre",
    ),
}
_SOURCE_SCHEMAS = {
    motor.CHALLENGE.challenge_id: "carbon.motor.reference-record.v1",
    cooling.CHALLENGE.challenge_id: "carbon.cold-plate.reference-record.v1",
}
_ARTIFACTS = {
    motor.CHALLENGE.challenge_id: (
        "motor-dev-train-150-v1.npz",
        "motor-dev-train-150-v1.provenance.json",
    ),
    cooling.CHALLENGE.challenge_id: (
        "cooling-dev-train-400-v1.npz",
        "cooling-dev-train-400-v1.provenance.json",
    ),
}
_PINNED = {
    motor.CHALLENGE.challenge_id: (
        "5d27220b8b0c0ccddd013299183118cdce61f205057fe99bceb95c1f52173361",
        "41f5b570f86f9274b83e89cd7527fa00e46ecfec7ceb6fe72a097e2a2fd115fc",
    ),
    cooling.CHALLENGE.challenge_id: (
        "b8d7839dcbfc777aa8b506a18bb9fc9b216786cb0d3533df18e6fb76ca4ec3bf",
        "47bddd23a1015cf38c1cfbdab393ff2db5289b9879c78406f223392cd55daefb",
    ),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError("duplicate public TRAIN key")
        result[name] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite public TRAIN token: " + value)


def _number(value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError("finite numeric public TRAIN value required")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("finite float64 public TRAIN value required") from error
    if not math.isfinite(converted):
        raise ValueError("finite float64 public TRAIN value required")
    return converted


def _source(challenge_id: str):
    if challenge_id == motor.CHALLENGE.challenge_id:
        return motor, motor_domain, motor.TRAIN_CASES
    if challenge_id == cooling.CHALLENGE.challenge_id:
        return cooling, cooling_domain, cooling.TRAIN_CASES
    raise ValueError("unknown public physical TRAIN challenge")


def numeric_interface_document(challenge_id: str) -> dict:
    """Reversible layout of one native case per numeric row, without scaling."""
    challenge, domain, _ = _source(challenge_id)
    if challenge_id == motor.CHALLENGE.challenge_id:
        slices = {"torque_nm": [0, domain.ANGLE_STEPS]}
        axis = {
            "name": "rotor_angle_deg",
            "unit": "degree",
            "values": [
                i * domain.PERIOD_DEG / domain.ANGLE_STEPS
                for i in range(domain.ANGLE_STEPS)
            ],
        }
    else:
        slices = {
            "peak_c": [0, 1],
            "profile_c": [1, 1 + domain.PROFILE_SEGMENTS],
            "pressure_drop_pa": [
                1 + domain.PROFILE_SEGMENTS,
                2 + domain.PROFILE_SEGMENTS,
            ],
        }
        axis = {
            "name": "axial_segment",
            "unit": None,
            "values": list(range(domain.PROFILE_SEGMENTS)),
        }
    return {
        "schema": "carbon.physical-public-train.numeric-interface.v1",
        "challenge": {"id": challenge_id, "version": challenge.CHALLENGE.version},
        "native_identity": challenge.IDENTITY,
        "native_interface_sha256": "sha256:"
        + _sha(_canonical(challenge.interface_document())),
        "dtype": "<f8",
        "input_names": list(domain.INPUTS),
        "input_units": list(_INPUT_UNITS[challenge_id]),
        "target_slices": slices,
        "target_units": {
            name: challenge.PUBLIC_OUTPUTS[name]["unit"] for name in domain.PREDICTED
        },
        "target_axis": axis,
        "one_row_per_native_case": True,
        "transform": "native parsed numbers in source row/index order; no scaling or aggregation",
    }


def _npz(inputs: np.ndarray, targets: np.ndarray) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, array in (("inputs", inputs), ("targets", targets)):
            member = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o600 << 16
            with archive.open(member, "w", force_zip64=True) as stream:
                np.lib.format.write_array(stream, array, allow_pickle=False)
    return output.getvalue()


def derive_public_train(challenge_id: str, source_raw: bytes) -> tuple[bytes, dict]:
    """Derive fixed bytes from the exact pinned native public JSONL source."""
    challenge, domain, count = _source(challenge_id)
    if type(source_raw) is not bytes or _sha(source_raw) != challenge.TRAIN_SHA256:
        raise ValueError("public TRAIN source identity differs")
    lines = source_raw.splitlines()
    if len(lines) != count:
        raise ValueError("public TRAIN row count differs")
    layout = numeric_interface_document(challenge_id)
    inputs, targets, case_ids = [], [], []
    for index, line in enumerate(lines):
        row = json.loads(line, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        case_id = f"train-{index:04d}"
        if (
            type(row) is not dict
            or row.get("schema") != _SOURCE_SCHEMAS[challenge_id]
            or row.get("case_id") != case_id
            or row.get("status") != "OK"
            or type(row.get("inputs")) is not dict
            or set(row["inputs"]) != set(domain.INPUTS)
            or type(row.get("outputs")) is not dict
            or not set(domain.PREDICTED) <= set(row["outputs"])
        ):
            raise ValueError("public TRAIN source row differs")
        inputs.append([_number(row["inputs"][name]) for name in domain.INPUTS])
        output = row["outputs"]
        if challenge_id == motor.CHALLENGE.challenge_id:
            curve = output["torque_nm"]
            if type(curve) is not list or len(curve) != domain.ANGLE_STEPS:
                raise ValueError("Motor TRAIN curve differs")
            targets.append([_number(value) for value in curve])
        else:
            profile = output["profile_c"]
            if type(profile) is not list or len(profile) != domain.PROFILE_SEGMENTS:
                raise ValueError("Cooling TRAIN profile differs")
            targets.append(
                [_number(output["peak_c"])]
                + [_number(value) for value in profile]
                + [_number(output["pressure_drop_pa"])]
            )
        case_ids.append(case_id)
    x = np.asarray(inputs, dtype="<f8")
    y = np.asarray(targets, dtype="<f8")
    if x.shape != (count, len(domain.INPUTS)) or y.shape != (
        count,
        max(end for _, end in layout["target_slices"].values()),
    ):
        raise ValueError("public TRAIN numeric shape differs")
    raw = _npz(x, y)
    provenance = {
        "schema": _SCHEMA,
        "scope": _SCOPE,
        "challenge": layout["challenge"],
        "native_identity": challenge.IDENTITY,
        "source_schema": _SOURCE_SCHEMAS[challenge_id],
        "source_sha256": "sha256:" + challenge.TRAIN_SHA256,
        "train_sha256": "sha256:" + _sha(raw),
        "transformation_version": "native-jsonl-to-float64-npz-v1",
        "case_ids": case_ids,
        "numeric_interface": layout,
    }
    return raw, provenance


def load_public_train(challenge_id: str) -> dict:
    """Load only pinned DEVELOPMENT bytes; never admit an evaluation role."""
    challenge, domain, count = _source(challenge_id)
    train_name, provenance_name = _ARTIFACTS[challenge_id]
    train_raw = (_DATA / train_name).read_bytes()
    provenance_raw = (_DATA / provenance_name).read_bytes()
    train_sha, provenance_sha = _PINNED[challenge_id]
    if _sha(train_raw) != train_sha or _sha(provenance_raw) != provenance_sha:
        raise ValueError("public numeric TRAIN artifact identity differs")
    provenance = json.loads(
        provenance_raw, object_pairs_hook=_pairs, parse_constant=_nonfinite
    )
    if (
        type(provenance) is not dict
        or provenance.get("schema") != _SCHEMA
        or provenance.get("scope") != _SCOPE
        or provenance.get("challenge")
        != {"id": challenge_id, "version": challenge.CHALLENGE.version}
        or provenance.get("native_identity") != challenge.IDENTITY
        or provenance.get("source_schema") != _SOURCE_SCHEMAS[challenge_id]
        or provenance.get("source_sha256") != "sha256:" + challenge.TRAIN_SHA256
        or provenance.get("train_sha256") != "sha256:" + train_sha
        or provenance.get("transformation_version") != "native-jsonl-to-float64-npz-v1"
        or provenance.get("case_ids") != [f"train-{i:04d}" for i in range(count)]
        or provenance.get("numeric_interface")
        != numeric_interface_document(challenge_id)
    ):
        raise ValueError("public numeric TRAIN provenance differs")
    with zipfile.ZipFile(io.BytesIO(train_raw)) as archive:
        members = archive.infolist()
        if (
            len(members) != 2
            or {member.filename for member in members} != {"inputs.npy", "targets.npy"}
            or any(
                member.compress_type != zipfile.ZIP_STORED or member.flag_bits & 1
                for member in members
            )
        ):
            raise ValueError("public numeric TRAIN members differ")
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        if set(data.files) != {"inputs", "targets"}:
            raise ValueError("public numeric TRAIN arrays differ")
        x, y = data["inputs"], data["targets"]
    width = max(
        end for _, end in provenance["numeric_interface"]["target_slices"].values()
    )
    if (
        x.shape != (count, len(domain.INPUTS))
        or y.shape != (count, width)
        or x.dtype != np.dtype("<f8")
        or y.dtype != np.dtype("<f8")
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
    ):
        raise ValueError("public numeric TRAIN tensor differs")
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "train": train_raw,
        "inputs": x,
        "targets": y,
        "case_ids": tuple(provenance["case_ids"]),
        "provenance": provenance,
    }
