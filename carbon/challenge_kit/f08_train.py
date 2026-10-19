"""Source-bound, partial public f08 DEVELOPMENT TRAIN for normal construction.

This material is 255 observed rows from an incomplete 256-action bank. It is
neither an official evaluation pack nor a qualified physical reference.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path

CHALLENGE_ID = "f08-ribbed-bracket"
CHALLENGE_VERSION = "1.0"
TRAIN_SHA256 = "65eb6a5f4e95ab3e2120c78cf3cd6a60d37554934c7d7ddea71e53cdadaac947"
PROVENANCE_SHA256 = "f510f92f77ec0c1d3655069703e70d25585648dc2766e14cef5f4689089c1860"
OBSERVED_SHA256 = "bb2d030d486b313efe2c0ebf57151bb4a34727d6e307892a87e1d8a9211ccc45"
MANIFEST_SHA256 = "ecad1a1205448aedccb4feb037f55663bc6dd96c9aae7f75b3c1251c193fa80c"
FIELDS = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
)
TARGETS = (
    "static_tip_mm_per_n",
    "peak_tip_z005_mm_per_n",
    "peak_frequency_z005_hz",
    "peak_tip_z010_mm_per_n",
    "peak_frequency_z010_hz",
    "peak_tip_z020_mm_per_n",
    "peak_frequency_z020_hz",
)
_ZETAS = ("zeta_0.005", "zeta_0.01", "zeta_0.02")
_DATA = Path(__file__).with_name("data")
_TRAIN = "f08-dev-train-255-v1.npz"
_PROVENANCE = "f08-dev-train-255-v1.provenance.json"
_CASE_ID = re.compile(r"train-[0-9]{4}\Z")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _json(raw: bytes) -> dict:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate f08 source key")
            value[key] = item
        return value

    def nonfinite(value):
        raise ValueError("nonfinite f08 source token: " + value)

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if type(value) is not dict:
        raise ValueError("f08 source object required")
    return value


def _number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite f08 source number required")
    return float(value)


def _archive(inputs, targets) -> bytes:
    import numpy as np

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, array in (("inputs", inputs), ("targets", targets)):
            member = zipfile.ZipInfo(name + ".npy")
            member.create_system = 0
            member.external_attr = 0o600 << 16
            with archive.open(member, "w", force_zip64=True) as stream:
                np.lib.format.write_array(stream, array, allow_pickle=False)
    return output.getvalue()


def derive_public_train(observed_raw: bytes, manifest_raw: bytes) -> tuple[bytes, dict]:
    """Reproduce inert TRAIN bytes from the exact retained public observations."""
    import numpy as np

    if (
        _digest(observed_raw) != OBSERVED_SHA256
        or _digest(manifest_raw) != MANIFEST_SHA256
    ):
        raise ValueError("f08 TRAIN source identity differs")
    observed, manifest = _json(observed_raw), _json(manifest_raw)
    cases = manifest.get("cases")
    if (
        manifest.get("bank", {}).get("role") != "train"
        or type(cases) is not list
        or len(cases) != 256
        or any(type(row) is not dict for row in cases)
    ):
        raise ValueError("f08 original TRAIN manifest differs")
    frozen = {row.get("case"): row.get("action") for row in cases}
    if (
        len(frozen) != 256
        or any(type(key) is not str or not _CASE_ID.fullmatch(key) for key in frozen)
        or any(
            type(action) is not dict or set(action) != set(FIELDS)
            for action in frozen.values()
        )
    ):
        raise ValueError("f08 original action inventory differs")
    rows = observed.get("cases")
    if type(rows) is not dict or set(rows) != set(frozen):
        raise ValueError("f08 observed action inventory differs")
    failed = rows["train-0016"]
    if type(failed) is not dict or failed.get("status") != "OBSERVER_FAILED":
        raise ValueError("f08 failed original action differs")
    accepted = tuple(sorted(set(frozen) - {"train-0016"}))
    inputs, targets = [], []
    for case_id in accepted:
        row = rows[case_id]
        if (
            type(row) is not dict
            or row.get("mode_ladder", {}).get("verdict") != "PASS"
            or row.get("case") != frozen[case_id]
        ):
            raise ValueError("f08 source row or frozen action differs")
        inputs.append([_number(row["case"][name]) for name in FIELDS])
        target = [_number(row["static_tip_mm_per_n"])]
        for zeta in _ZETAS:
            damping = row["damping"][zeta]
            target.extend(
                (_number(damping["worst_mm_per_n"]), _number(damping["worst_hz"]))
            )
        targets.append(target)
    x, y = np.asarray(inputs, dtype=np.float32), np.asarray(targets, dtype=np.float32)
    if (
        x.shape != (255, 6)
        or y.shape != (255, 7)
        or not (np.isfinite(x).all() and np.isfinite(y).all())
    ):
        raise ValueError("f08 TRAIN tensor shape or values differ")
    raw = _archive(x, y)
    provenance = {
        "schema": "carbon.f08.dev-train-255.provenance.v1",
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "challenge": {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION},
        "observed_sha256": "sha256:" + OBSERVED_SHA256,
        "original_manifest_sha256": "sha256:" + MANIFEST_SHA256,
        "train_sha256": "sha256:" + _digest(raw),
        "case_ids": list(accepted),
        "failed_case": {"id": "train-0016", "status": "OBSERVER_FAILED"},
        "original_256_complete": False,
        "inputs_mm": list(FIELDS),
        "learned_targets": list(TARGETS),
        "analytic_mass": "separate CAD check; excluded from learned targets",
        "original_action_sha256": {
            case_id: "sha256:" + _digest(_canonical(frozen[case_id]))
            for case_id in sorted(frozen)
        },
        "original_action_evaluation_role": "EXCLUDED_ALL_256",
    }
    return raw, provenance


def load_public_train() -> dict:
    """Load pinned inert tensors; admission and scientific use belong elsewhere."""
    import numpy as np

    raw = (_DATA / _TRAIN).read_bytes()
    provenance_raw = (_DATA / _PROVENANCE).read_bytes()
    if _digest(raw) != TRAIN_SHA256 or _digest(provenance_raw) != PROVENANCE_SHA256:
        raise ValueError("f08 public TRAIN artifact identity differs")
    provenance = _json(provenance_raw)
    case_ids = provenance.get("case_ids")
    original_actions = provenance.get("original_action_sha256")
    if (
        provenance.get("schema") != "carbon.f08.dev-train-255.provenance.v1"
        or provenance.get("scope") != "PUBLIC_DEVELOPMENT_ONLY"
        or provenance.get("challenge")
        != {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION}
        or provenance.get("observed_sha256") != "sha256:" + OBSERVED_SHA256
        or provenance.get("original_manifest_sha256") != "sha256:" + MANIFEST_SHA256
        or provenance.get("train_sha256") != "sha256:" + TRAIN_SHA256
        or type(case_ids) is not list
        or len(case_ids) != 255
        or case_ids != sorted(case_ids)
        or len(set(case_ids)) != 255
        or "train-0016" in case_ids
        or provenance.get("failed_case")
        != {"id": "train-0016", "status": "OBSERVER_FAILED"}
        or provenance.get("original_256_complete") is not False
        or provenance.get("inputs_mm") != list(FIELDS)
        or provenance.get("learned_targets") != list(TARGETS)
        or type(original_actions) is not dict
        or len(original_actions) != 256
        or set(original_actions) != set(case_ids) | {"train-0016"}
        or provenance.get("original_action_evaluation_role") != "EXCLUDED_ALL_256"
    ):
        raise ValueError("f08 public TRAIN provenance differs")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if (
            {member.filename for member in members} != {"inputs.npy", "targets.npy"}
            or len(members) != 2
            or any(
                member.compress_type != zipfile.ZIP_STORED or member.flag_bits & 1
                for member in members
            )
        ):
            raise ValueError("f08 public TRAIN members differ")
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        if set(data.files) != {"inputs", "targets"}:
            raise ValueError("f08 public TRAIN arrays differ")
        inputs, targets = data["inputs"], data["targets"]
    if (
        inputs.shape != (255, 6)
        or targets.shape != (255, 7)
        or inputs.dtype != np.float32
        or targets.dtype != np.float32
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise ValueError("f08 public TRAIN tensors differ")
    inputs.setflags(write=False)
    targets.setflags(write=False)
    return {
        "train": raw,
        "inputs": inputs,
        "targets": targets,
        "case_ids": tuple(case_ids),
        "provenance": provenance,
    }
