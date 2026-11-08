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

from . import version_registry

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


def numeric_interface_document(challenge_id: str, encoding=None) -> dict:
    """Reversible layout of one native case per numeric row, without scaling.

    `encoding` (Cooling only; `cold_plate.output_encoding.ENCODING`) names a
    law-safe output encoding: slots 0 and 31 then hold raw values the decoder
    maps back (peak excess and pressure), and the document records it, so its
    digest differs from the unencoded one."""
    challenge, domain, _ = _source(challenge_id)
    if encoding is not None and (
        challenge_id != cooling.CHALLENGE.challenge_id
        or encoding != _cooling_encoding()
    ):
        raise ValueError("unknown output encoding")
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
        **(
            {}
            if encoding is None
            else {
                "output_encoding": encoding,
                "transform": (
                    "native parsed numbers in source row/index order; slot 0 "
                    "holds e with peak_c = max(profile_c) + softplus(e), slot "
                    "31 holds q with pressure_drop_pa = softplus(q)"
                ),
            }
        ),
    }


def _cooling_encoding():
    from carbon.cold_plate.output_encoding import ENCODING

    return ENCODING


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


#: Versions whose TRAIN is the law-safe encoded artifact (Cooling 1.3 and
#: 1.4), derived once from the pinned v1 TRAIN (`derive_encoded_public_train`)
#: and pinned by sha256 so every host reads the same bytes. Read from the
#: version registry, where each version names its TRAIN.
ENCODED_VERSIONS = version_registry.keys(train=version_registry.COOLING_TRAIN_ENCODED)
_ENCODED_ARTIFACTS = {
    cooling.CHALLENGE.challenge_id: (
        "cooling-dev-train-400-v2-encoded.npz",
        "cooling-dev-train-400-v2-encoded.provenance.json",
    ),
}
_ENCODED_PINNED = {
    cooling.CHALLENGE.challenge_id: (
        "2df26b41a2fdba6a6a64921a9d8c357370374d43d313840ea6e8a371920641d0",
        "f6edbb850fb635bdc317df9b87ba1ee09b7539c43db982d9bfcf65fdc0c60c39",
    ),
}
_ENCODED_SCHEMA = "carbon.physical-public-train.encoded-provenance.v1"


def derive_encoded_public_train(challenge_id: str) -> tuple[bytes, dict]:
    """The law-safe encoded TRAIN from the pinned v1 TRAIN: same inputs and
    case order, targets through `output_encoding.encode_targets`."""
    from carbon.cold_plate.output_encoding import encode_targets

    source = load_public_train(challenge_id)
    encoding = _cooling_encoding()
    y = encode_targets(source["targets"])
    raw = _npz(np.asarray(source["inputs"], dtype="<f8"), y.astype("<f8"))
    challenge, _, _ = _source(challenge_id)
    provenance = {
        "schema": _ENCODED_SCHEMA,
        "scope": _SCOPE,
        "challenge": {"id": challenge_id, "version": challenge.CHALLENGE.version},
        "encoding": encoding,
        "source_train_sha256": source["provenance"]["train_sha256"],
        "train_sha256": "sha256:" + _sha(raw),
        "transformation_version": "law-safe-output-encoding-v1",
        "case_ids": list(source["case_ids"]),
        "numeric_interface": numeric_interface_document(challenge_id, encoding),
    }
    return raw, provenance


#: Later public TRAINs, by the TRAIN name a version declares in the version
#: registry (or its host overlay): the Challenge's native rows byte-equal plus
#: added in-box rows, with the SAME numeric interface (Cooling 1.8: peak /
#: profile / pressure; Motor 1.8 is a FRESH lambda TRAIN, `FRESH_LAMBDA`). Each is pinned by
#: sha256 when its TRAIN is frozen; until then every pin is None and loading
#: it refuses (HUMAN_INPUT), never a nearby TRAIN. ``encoded_from`` names the
#: native TRAIN an encoded one is derived from (Cooling's law-safe encoding).
EXTENDED = {
    "cooling-dev-train-1p8-v1": {
        "challenge": cooling.CHALLENGE.challenge_id,
        "encoded_from": None,
        "rows": None,
        "source_sha256": None,
        "train_sha256": None,
        "provenance_sha256": None,
    },
    "cooling-dev-train-1p8-v1-encoded": {
        "challenge": cooling.CHALLENGE.challenge_id,
        "encoded_from": "cooling-dev-train-1p8-v1",
        "rows": None,
        "source_sha256": None,
        "train_sha256": None,
        "provenance_sha256": None,
    },
}
#: Where the extended TRAIN files sit (the same data directory; a separate name so a test can point it elsewhere).
_EXTENDED_DATA = _DATA
_EXTENDED_TRANSFORM = "native-plus-added-jsonl-to-float64-npz-v1"
#: The record fields a published added row keeps (allow-listed): no batch,
#: run, wall time, diagnostics or source case id of the custody draw.
_ADDED_FIELDS = ("schema", "kind", "status", "inputs", "outputs", "options", "image")
_NATIVE_TRAIN_NAMES = {
    motor.CHALLENGE.challenge_id: version_registry.MOTOR_TRAIN,
    cooling.CHALLENGE.challenge_id: version_registry.COOLING_TRAIN,
}


#: Motor 1.8's TRAIN (owner 7 Nov ~19:2x "all in" + Carbon Validator-B's
#: ruling ad947355 section 1): the flux linkage is SEEN in TRAIN. Every row
#: comes from the record-now route. The 150 TRAIN rows keep their ids and
#: their torque must be BYTE-EQUAL to the pinned TRAIN 150, else the assembly
#: refuses (STOP). 240 targets: torque_nm[60], then phase_flux_linkage_wb_A /
#: _B / _C [60 each]. Pinned at the freeze; a None pin refuses (HUMAN_INPUT).
FRESH_LAMBDA = {
    "motor-dev-train-1p8-v1": {
        "challenge": motor.CHALLENGE.challenge_id,
        "rows": None,
        "source_sha256": None,
        "train_sha256": None,
        "provenance_sha256": None,
    },
}
_LAMBDA_PHASES = ("A", "B", "C")
_FRESH_TRANSFORM = "record-now-jsonl-to-float64-npz-v1"
_FRESH_FIELDS = (
    "schema",
    "kind",
    "status",
    "inputs",
    "outputs",
    "options",
    "image",
    "runner",
)


def motor18_interface_document() -> dict:
    """Motor 1.8's numeric layout: the native torque interface plus the three
    phase flux linkages (record-now's winding-signed per-phase sums), on the
    same rotor axis, unscaled. Its digest differs from the torque-only one."""
    base = numeric_interface_document(motor.CHALLENGE.challenge_id)
    steps = motor_domain.ANGLE_STEPS
    slices = {"torque_nm": [0, steps]}
    units = dict(base["target_units"])
    for i, phase in enumerate(_LAMBDA_PHASES, 1):
        slices[f"phase_flux_linkage_wb_{phase}"] = [i * steps, (i + 1) * steps]
        units[f"phase_flux_linkage_wb_{phase}"] = "weber"
    return {
        **base,
        "schema": "carbon.physical-public-train.numeric-interface.v2-motor-lambda",
        "target_slices": slices,
        "target_units": units,
        "transform": (
            "native parsed numbers in source row/index order: torque_nm, then "
            "phase_flux_linkage_wb A, B, C (record-now, winding-signed per phase); "
            "no scaling or aggregation"
        ),
    }


def _fresh(name: str, challenge_id: str) -> dict:
    spec = FRESH_LAMBDA.get(name)
    if spec is None or spec["challenge"] != challenge_id:
        raise ValueError(
            f"public TRAIN {name!r} is not a fresh lambda TRAIN of {challenge_id}"
        )
    pins = ("rows", "source_sha256", "train_sha256", "provenance_sha256")
    if any(spec[key] is None for key in pins):
        raise ValueError(f"public TRAIN {name!r} is not frozen yet (HUMAN_INPUT)")
    return spec


def _lambda_of(record):
    lam = (record.get("record_now") or {}).get("phase_flux_linkage_wb")
    if type(lam) is not dict or set(lam) != set(_LAMBDA_PHASES):
        return None
    out = {}
    for phase in _LAMBDA_PHASES:
        values = lam[phase]
        if type(values) is not list or len(values) != motor_domain.ANGLE_STEPS:
            return None
        out[phase] = [_number(v) for v in values]
    return out


def _native_motor_rows():
    raw = (Path(__file__).resolve().parents[2] / motor.TRAIN_PATH).read_bytes()
    if _sha(raw) != motor.TRAIN_SHA256:
        raise ValueError("public TRAIN source identity differs")
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != motor.TRAIN_CASES:
        raise ValueError("public TRAIN row count differs")
    return rows


def _is_train_id(cid):
    return (
        isinstance(cid, str)
        and len(cid) == 10
        and cid.startswith("train-")
        and cid[6:].isdigit()
    )


def assemble_motor18_source(records) -> bytes:
    """Motor 1.8's public source JSONL from typed-OK RECORD-NOW records.

    Records whose case_id is a TRAIN id (train-NNNN) keep it; the ids must run
    from train-0000 without a gap and cover the 150 TRAIN rows, and rows 0-149
    must equal the pinned TRAIN 150 inputs AND torque byte for byte, else this
    REFUSES (Carbon Validator-B: byte-equal or STOP). Every other record (an
    added row with a custody id) is ordered by the sha256 of its canonical
    inputs and numbered on. Each row keeps the allow-listed fields only, with
    outputs = torque_nm + phase_flux_linkage_wb {A, B, C}. Refuses a non-OK,
    malformed, lambda-less or duplicate-design row."""
    domain = motor_domain
    native = _native_motor_rows()
    kept, added, seen = {}, [], set()
    for record in records:
        if (
            type(record) is not dict
            or record.get("status") != "OK"
            or record.get("schema") != _SOURCE_SCHEMAS[motor.CHALLENGE.challenge_id]
            or type(record.get("inputs")) is not dict
            or set(record["inputs"]) != set(domain.INPUTS)
            or type(record.get("outputs")) is not dict
            or type(record["outputs"].get("torque_nm")) is not list
            or len(record["outputs"]["torque_nm"]) != domain.ANGLE_STEPS
        ):
            raise ValueError(
                "a Motor 1.8 TRAIN record is not a typed-OK reference record"
            )
        lam = _lambda_of(record)
        if lam is None:
            raise ValueError(
                "a Motor 1.8 TRAIN record has no complete phase flux linkage (record-now)"
            )
        inputs = {name: _number(record["inputs"][name]) for name in domain.INPUTS}
        key = _sha(_canonical(inputs))
        if key in seen:
            raise ValueError("a Motor 1.8 TRAIN record repeats a design")
        seen.add(key)
        row = {name: record[name] for name in _FRESH_FIELDS if name in record}
        row["inputs"] = inputs
        row["outputs"] = {
            "torque_nm": [_number(v) for v in record["outputs"]["torque_nm"]],
            "phase_flux_linkage_wb": lam,
        }
        row["kind"] = "ordinary"
        cid = record.get("case_id")
        if _is_train_id(cid):
            if cid in kept:
                raise ValueError("a Motor 1.8 TRAIN id appears twice")
            kept[cid] = row
        else:
            added.append((key, row))
    ids = sorted(kept)
    if ids != [f"train-{i:04d}" for i in range(len(ids))] or len(ids) < len(native):
        raise ValueError(
            "the kept TRAIN ids must run from train-0000 without a gap and cover TRAIN 150"
        )
    for i, old in enumerate(native):
        row = kept[f"train-{i:04d}"]
        if row["inputs"] != {n: _number(v) for n, v in old["inputs"].items()}:
            raise ValueError(f"train-{i:04d}: inputs differ from TRAIN 150")
        if row["outputs"]["torque_nm"] != [
            _number(v) for v in old["outputs"]["torque_nm"]
        ]:
            raise ValueError(
                f"train-{i:04d}: torque is not byte-equal to TRAIN 150 (STOP)"
            )
    out = []
    for cid in ids:
        kept[cid]["case_id"] = cid
        out.append(kept[cid])
    ordered = sorted(added, key=lambda item: item[0])
    for index, (_, row) in enumerate(ordered, len(ids)):
        row["case_id"] = f"train-{index:04d}"
        out.append(row)
    lines = [
        json.dumps(r, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        for r in out
    ]
    return b"\n".join(lines) + b"\n"


def derive_motor18_public_train(name: str, source_raw: bytes) -> tuple[bytes, dict]:
    """Fixed bytes of Motor 1.8's fresh lambda TRAIN from its source JSONL:
    x = the 8 inputs, y = 240 targets (torque, then lambda A, B, C). Re-checks
    the TRAIN 150 byte-equal torque."""
    if name not in FRESH_LAMBDA:
        raise ValueError(f"public TRAIN {name!r} is not a fresh lambda TRAIN")
    if type(source_raw) is not bytes:
        raise ValueError("public TRAIN source must be bytes")
    domain = motor_domain
    native = _native_motor_rows()
    layout = motor18_interface_document()
    inputs, targets, case_ids = [], [], []
    for index, line in enumerate(source_raw.splitlines()):
        row = json.loads(line, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        x_row, torque = _row(
            motor.CHALLENGE.challenge_id, domain, row, f"train-{index:04d}"
        )
        lam = row["outputs"].get("phase_flux_linkage_wb")
        if (
            type(lam) is not dict
            or set(lam) != set(_LAMBDA_PHASES)
            or any(
                type(lam[p]) is not list or len(lam[p]) != domain.ANGLE_STEPS
                for p in _LAMBDA_PHASES
            )
        ):
            raise ValueError("Motor 1.8 TRAIN lambda differs")
        if index < len(native) and torque != [
            _number(v) for v in native[index]["outputs"]["torque_nm"]
        ]:
            raise ValueError(
                f"train-{index:04d}: torque is not byte-equal to TRAIN 150 (STOP)"
            )
        inputs.append(x_row)
        targets.append(torque + [_number(v) for p in _LAMBDA_PHASES for v in lam[p]])
        case_ids.append(row["case_id"])
    if len(case_ids) < len(native):
        raise ValueError("a Motor 1.8 TRAIN covers at least the 150 TRAIN rows")
    raw = _npz(np.asarray(inputs, dtype="<f8"), np.asarray(targets, dtype="<f8"))
    provenance = {
        "schema": _SCHEMA,
        "scope": _SCOPE,
        "challenge": layout["challenge"],
        "native_identity": motor.IDENTITY,
        "source_schema": _SOURCE_SCHEMAS[motor.CHALLENGE.challenge_id],
        "train_name": name,
        "native_source_sha256": "sha256:" + motor.TRAIN_SHA256,
        "source_sha256": "sha256:" + _sha(source_raw),
        "train_sha256": "sha256:" + _sha(raw),
        "transformation_version": _FRESH_TRANSFORM,
        "case_ids": case_ids,
        "numeric_interface": layout,
    }
    return raw, provenance


def _load_fresh(name: str, challenge_id: str) -> dict:
    spec = _fresh(name, challenge_id)
    train_raw = (_EXTENDED_DATA / f"{name}.npz").read_bytes()
    provenance_raw = (_EXTENDED_DATA / f"{name}.provenance.json").read_bytes()
    source_raw = (_EXTENDED_DATA / f"{name}.source.jsonl").read_bytes()
    if (
        _sha(train_raw) != spec["train_sha256"]
        or _sha(provenance_raw) != spec["provenance_sha256"]
        or _sha(source_raw) != spec["source_sha256"]
    ):
        raise ValueError("fresh public TRAIN artifact identity differs")
    provenance = json.loads(
        provenance_raw, object_pairs_hook=_pairs, parse_constant=_nonfinite
    )
    want_raw, want = derive_motor18_public_train(name, source_raw)
    if (
        want_raw != train_raw
        or provenance != want
        or len(provenance["case_ids"]) != spec["rows"]
    ):
        raise ValueError("fresh public TRAIN provenance differs")
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        x, y = data["inputs"], data["targets"]
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "train": train_raw,
        "inputs": x,
        "targets": y,
        "case_ids": tuple(provenance["case_ids"]),
        "provenance": provenance,
    }


def _train_name(challenge_id: str, version: str | None):
    """The registered TRAIN name of a version, or None (no version, or one the
    registry does not declare: the native/encoded rule below, as before). A
    registered version naming a TRAIN this loader does not serve REFUSES: it
    is never loaded as the native one."""
    if version is None:
        return None
    entry = version_registry.find(challenge_id, version)
    if entry is None:
        return None
    served = {_NATIVE_TRAIN_NAMES.get(challenge_id), *EXTENDED, *FRESH_LAMBDA}
    if challenge_id == cooling.CHALLENGE.challenge_id:
        served.add(version_registry.COOLING_TRAIN_ENCODED)
    if entry.train not in served:
        raise ValueError(f"public TRAIN {entry.train!r} is not served by this loader")
    return entry.train


def _extended(name: str, challenge_id: str) -> dict:
    spec = EXTENDED.get(name)
    if spec is None or spec["challenge"] != challenge_id:
        raise ValueError(
            f"public TRAIN {name!r} is not an extended TRAIN of {challenge_id}"
        )
    pins = ("rows", "train_sha256", "provenance_sha256") + (
        () if spec["encoded_from"] else ("source_sha256",)
    )
    if any(spec[key] is None for key in pins):
        raise ValueError(f"public TRAIN {name!r} is not frozen yet (HUMAN_INPUT)")
    return spec


def assemble_extended_source(challenge_id: str, added_records) -> bytes:
    """The public source JSONL of an extended TRAIN: the Challenge's pinned
    native TRAIN lines byte-equal, then each typed-OK added record reduced to
    the allow-listed fields (outputs: the predicted ones only), ordered by the
    sha256 of its canonical inputs (never a draw id) and numbered on from the
    native rows. Refuses a non-OK, duplicate, malformed or native-equal row."""
    challenge, domain, count = _source(challenge_id)
    native = (Path(__file__).resolve().parents[2] / challenge.TRAIN_PATH).read_bytes()
    if _sha(native) != challenge.TRAIN_SHA256:
        raise ValueError("public TRAIN source identity differs")
    lines = native.splitlines()
    if len(lines) != count:
        raise ValueError("public TRAIN row count differs")
    seen = {
        _sha(_canonical({n: _number(v) for n, v in json.loads(line)["inputs"].items()}))
        for line in lines
    }
    rows = []
    for record in added_records:
        if (
            type(record) is not dict
            or record.get("status") != "OK"
            or record.get("schema") != _SOURCE_SCHEMAS[challenge_id]
            or type(record.get("inputs")) is not dict
            or set(record["inputs"]) != set(domain.INPUTS)
            or type(record.get("outputs")) is not dict
            or not set(domain.PREDICTED) <= set(record["outputs"])
        ):
            raise ValueError("an added TRAIN record is not a typed-OK reference record")
        inputs = {name: _number(record["inputs"][name]) for name in domain.INPUTS}
        key = _sha(_canonical(inputs))
        if key in seen:
            raise ValueError("an added TRAIN record repeats a TRAIN design")
        seen.add(key)
        row = {name: record[name] for name in _ADDED_FIELDS if name in record}
        row["inputs"] = inputs
        row["outputs"] = {name: record["outputs"][name] for name in domain.PREDICTED}
        row["kind"] = "ordinary"
        rows.append((key, row))
    if not rows:
        raise ValueError("an extended TRAIN needs at least one added row")
    out = list(lines)
    for index, (_, row) in enumerate(sorted(rows, key=lambda item: item[0]), count):
        row["case_id"] = f"train-{index:04d}"
        out.append(
            json.dumps(
                row, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        )
    return b"\n".join(out) + b"\n"


def derive_extended_public_train(name: str, source_raw: bytes) -> tuple[bytes, dict]:
    """Fixed bytes of an extended native TRAIN from its source JSONL (as
    `derive_public_train`, any row count: the native rows first)."""
    spec = EXTENDED.get(name)
    if spec is None or spec["encoded_from"] is not None:
        raise ValueError(f"public TRAIN {name!r} is not an extended native TRAIN")
    challenge_id = spec["challenge"]
    challenge, domain, count = _source(challenge_id)
    if type(source_raw) is not bytes:
        raise ValueError("public TRAIN source must be bytes")
    lines = source_raw.splitlines()
    native = (
        (Path(__file__).resolve().parents[2] / challenge.TRAIN_PATH)
        .read_bytes()
        .splitlines()
    )
    if len(lines) <= count or lines[:count] != native:
        raise ValueError(
            "an extended TRAIN must start with the native TRAIN rows byte-equal"
        )
    layout = numeric_interface_document(challenge_id)
    inputs, targets, case_ids = [], [], []
    for index, line in enumerate(lines):
        row = json.loads(line, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        x_row, y_row = _row(challenge_id, domain, row, f"train-{index:04d}")
        inputs.append(x_row)
        targets.append(y_row)
        case_ids.append(row["case_id"])
    raw = _npz(np.asarray(inputs, dtype="<f8"), np.asarray(targets, dtype="<f8"))
    provenance = {
        "schema": _SCHEMA,
        "scope": _SCOPE,
        "challenge": layout["challenge"],
        "native_identity": challenge.IDENTITY,
        "source_schema": _SOURCE_SCHEMAS[challenge_id],
        "train_name": name,
        "native_source_sha256": "sha256:" + challenge.TRAIN_SHA256,
        "source_sha256": "sha256:" + _sha(source_raw),
        "train_sha256": "sha256:" + _sha(raw),
        "transformation_version": _EXTENDED_TRANSFORM,
        "case_ids": case_ids,
        "numeric_interface": layout,
    }
    return raw, provenance


def derive_extended_encoded_public_train(name: str, native: dict) -> tuple[bytes, dict]:
    """The law-safe encoded form of a loaded extended Cooling TRAIN (as
    `derive_encoded_public_train`)."""
    from carbon.cold_plate.output_encoding import encode_targets

    spec = EXTENDED.get(name)
    if spec is None or spec["encoded_from"] is None:
        raise ValueError(f"public TRAIN {name!r} is not an extended encoded TRAIN")
    encoding = _cooling_encoding()
    y = encode_targets(native["targets"])
    raw = _npz(np.asarray(native["inputs"], dtype="<f8"), y.astype("<f8"))
    provenance = {
        "schema": _ENCODED_SCHEMA,
        "scope": _SCOPE,
        "challenge": native["provenance"]["challenge"],
        "train_name": name,
        "encoding": encoding,
        "source_train_sha256": native["provenance"]["train_sha256"],
        "train_sha256": "sha256:" + _sha(raw),
        "transformation_version": "law-safe-output-encoding-v1",
        "case_ids": list(native["case_ids"]),
        "numeric_interface": numeric_interface_document(spec["challenge"], encoding),
    }
    return raw, provenance


def _row(challenge_id, domain, row, case_id):
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
    x_row = [_number(row["inputs"][name]) for name in domain.INPUTS]
    output = row["outputs"]
    if challenge_id == motor.CHALLENGE.challenge_id:
        curve = output["torque_nm"]
        if type(curve) is not list or len(curve) != domain.ANGLE_STEPS:
            raise ValueError("Motor TRAIN curve differs")
        return x_row, [_number(value) for value in curve]
    profile = output["profile_c"]
    if type(profile) is not list or len(profile) != domain.PROFILE_SEGMENTS:
        raise ValueError("Cooling TRAIN profile differs")
    return x_row, (
        [_number(output["peak_c"])]
        + [_number(value) for value in profile]
        + [_number(output["pressure_drop_pa"])]
    )


def _load_extended(name: str, challenge_id: str) -> dict:
    spec = _extended(name, challenge_id)
    train_raw = (_EXTENDED_DATA / f"{name}.npz").read_bytes()
    provenance_raw = (_EXTENDED_DATA / f"{name}.provenance.json").read_bytes()
    if (
        _sha(train_raw) != spec["train_sha256"]
        or _sha(provenance_raw) != spec["provenance_sha256"]
    ):
        raise ValueError("extended public TRAIN artifact identity differs")
    provenance = json.loads(
        provenance_raw, object_pairs_hook=_pairs, parse_constant=_nonfinite
    )
    rows = spec["rows"]
    if spec["encoded_from"] is None:
        source_raw = (_EXTENDED_DATA / f"{name}.source.jsonl").read_bytes()
        if _sha(source_raw) != spec["source_sha256"]:
            raise ValueError("extended public TRAIN source identity differs")
        want_raw, want = derive_extended_public_train(name, source_raw)
        native_x = None
    else:
        native = _load_extended(spec["encoded_from"], challenge_id)
        want_raw, want = derive_extended_encoded_public_train(name, native)
        native_x = native["inputs"]
    if (
        want_raw != train_raw
        or provenance != want
        or len(provenance["case_ids"]) != rows
    ):
        raise ValueError("extended public TRAIN provenance differs")
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        x, y = data["inputs"], data["targets"]
    if native_x is not None and not np.array_equal(x, native_x):
        raise ValueError("extended encoded public TRAIN inputs differ")
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "train": train_raw,
        "inputs": x,
        "targets": y,
        "case_ids": tuple(provenance["case_ids"]),
        "provenance": provenance,
    }


def load_extended_train(name: str, challenge_id: str) -> dict:
    """One extended TRAIN by name (a native one for a sealed adapter's measurement); refuses until it is frozen."""
    if name in FRESH_LAMBDA:
        return _load_fresh(name, challenge_id)
    return _load_extended(name, challenge_id)


def load_public_train(challenge_id: str, version: str | None = None) -> dict:
    """Load only pinned DEVELOPMENT bytes; never admit an evaluation role.
    `version` selects the encoded TRAIN where that version uses it
    (`ENCODED_VERSIONS`), an extended TRAIN where it names one (`EXTENDED`),
    otherwise the native TRAIN, as for every version before. Each version
    declares its TRAIN in the version registry, so Cooling 1.4 names 1.3's
    encoded TRAIN itself; a registered version naming a TRAIN this loader does
    not serve refuses."""
    name = _train_name(challenge_id, version)
    if name in FRESH_LAMBDA:
        return _load_fresh(name, challenge_id)
    if name in EXTENDED:
        return _load_extended(name, challenge_id)
    if (challenge_id, version) in ENCODED_VERSIONS:
        return _load_encoded(challenge_id)
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


def _load_encoded(challenge_id: str) -> dict:
    _source(challenge_id)
    train_name, provenance_name = _ENCODED_ARTIFACTS[challenge_id]
    train_raw = (_DATA / train_name).read_bytes()
    provenance_raw = (_DATA / provenance_name).read_bytes()
    train_sha, provenance_sha = _ENCODED_PINNED[challenge_id]
    if _sha(train_raw) != train_sha or _sha(provenance_raw) != provenance_sha:
        raise ValueError("encoded public TRAIN artifact identity differs")
    provenance = json.loads(provenance_raw, object_pairs_hook=_pairs)
    source = load_public_train(challenge_id)
    if (
        type(provenance) is not dict
        or provenance.get("schema") != _ENCODED_SCHEMA
        or provenance.get("encoding") != _cooling_encoding()
        or provenance.get("source_train_sha256") != source["provenance"]["train_sha256"]
        or provenance.get("train_sha256") != "sha256:" + train_sha
        or provenance.get("case_ids") != list(source["case_ids"])
        or provenance.get("numeric_interface")
        != numeric_interface_document(challenge_id, _cooling_encoding())
    ):
        raise ValueError("encoded public TRAIN provenance differs")
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        if set(data.files) != {"inputs", "targets"}:
            raise ValueError("encoded public TRAIN arrays differ")
        x, y = data["inputs"], data["targets"]
    if (
        x.shape != source["inputs"].shape
        or y.shape != source["targets"].shape
        or x.dtype != np.dtype("<f8")
        or y.dtype != np.dtype("<f8")
        or not np.array_equal(x, source["inputs"])
        or not np.isfinite(y).all()
    ):
        raise ValueError("encoded public TRAIN tensor differs")
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "train": train_raw,
        "inputs": x,
        "targets": y,
        "case_ids": tuple(provenance["case_ids"]),
        "provenance": provenance,
    }
