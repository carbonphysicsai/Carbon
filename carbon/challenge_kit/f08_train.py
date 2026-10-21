"""Source-bound, partial public f08 DEVELOPMENT TRAIN for normal construction.

Version 1.0's material is 255 observed rows from an incomplete 256-action bank.
Version 1.1's TRAIN v2 is those 255 rows byte-for-byte plus RR-PACKS-07b's 32
near-limit rows (stratum N1r, 16 on each side of 0.15 mm/N at h = 3 mm). Neither
is an official evaluation pack nor a qualified physical reference.
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
#: 1.1 adds the near-limit TRAIN stratum and the straddling exam ladder; 1.0
#: stays loadable and unchanged.
#: 1.2 (step-2 batch, STEP2_BATCH_VERSIONS_20261020) serves 1.1's TRAIN v2 bytes
#: unchanged; only the version binding differs.
CHALLENGE_VERSIONS = ("1.0", "1.1", "1.2")
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
_TRAIN_V2 = "f08-dev-train-287-v2.npz"
_PROVENANCE_V2 = "f08-dev-train-287-v2.provenance.json"
TRAIN_V2_SHA256 = "4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a"
PROVENANCE_V2_SHA256 = (
    "b36fe2f524ccfc42b192d2ab38abfa1e8b5f389cd65c5e62f3f02d30efca14ec"
)
#: RR-PACKS-07b (Validator-approved N1 redraw, kept 16/16): four batches of
#: eight h = 3 mm solves, each with the frozen action file it was run from.
NEAR_LIMIT_EVIDENCE = "docs/development/evidence/f08-near-limit-public-20261020"
_NEAR_LIMIT_SOURCES = (
    (
        ("n1r-b0-observed.json", "87a75ac14ea91a9351fe0d2212b2b89c6a3c3f4f63f602f44365ee08d4c62d18"),
        ("n1r-b0-actions.json", "0ab858c01bb76d506b9cfa4bda158e0ba7f2b6c5749cff7fba93e72c292059e5"),
    ),
    (
        ("n1r-b1-observed.json", "627504c4819f70a08d91268030d32c63f12042e325a91dc11ec62823206c9745"),
        ("n1r-b1-actions.json", "7c5ec47ce892664d4b2ab561f53359b1bda245fb7e33c597cd9c7f852d20dfff"),
    ),
    (
        ("n1r-b2-observed.json", "b6021ebeeca01d09969a23520628611efad71e20e050fa68f699f33abba72fdf"),
        ("n1r-b2-actions.json", "4e74b8bb30608f2a7b10352c71e0959006837eed067301155d5124081f1bf288"),
    ),
    (
        ("n1r-b3-observed.json", "5e9cac589d256cbce508daf8fadaff60d4241358c323d5c311badae23cf8ce42"),
        ("n1r-b3-actions.json", "0a0734a8b4e4e53eba4fd459ce52879deb9c7982d933c0790d600022fed3a766"),
    ),
)  # fmt: skip
_NEAR_LIMIT_CASE_ID = re.compile(r"near-limit-[0-9]{4}\Z")
#: TRAIN is solved at h = 3 mm and exam references at h = 1.7 mm. Measured on
#: the 16 cases solved at both (RR-PACKS-07 README, Validator-reviewed): worst
#: dynamic h3 - h1.7 = -0.000090 to -0.000131 mm/N, so at the 0.15 mm/N limit
#: TRAIN reads about 0.07 % (about 1e-4 mm/N) lower than the exam truth.
TRAIN_MESH_STATEMENT = {
    "train_mesh_h_mm": 3.0,
    "exam_reference_mesh_h_mm": 1.7,
    "worst_dynamic_shift_h3_minus_h17_mm_per_n": {
        "min": -0.000131,
        "max": -0.000090,
        "max_abs": 0.000131,
        "cases": 16,
    },
    "statement": "F08 TRAIN is h = 3 mm; the exam truth is h = 1.7 mm; at the "
    "0.15 mm/N limit, h3 reads about 0.07 % (about 1e-4 mm/N) lower.",
}
_DYNAMIC_LIMIT_MM_PER_N = 0.15


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
        targets.append(_target_row(row))
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


def _target_row(row: dict) -> list[float]:
    target = [_number(row["static_tip_mm_per_n"])]
    for zeta in _ZETAS:
        damping = row["damping"][zeta]
        target.extend(
            (_number(damping["worst_mm_per_n"]), _number(damping["worst_hz"]))
        )
    return target


def derive_public_train_v2(
    v1_raw: bytes, sources: dict[str, bytes]
) -> tuple[bytes, dict]:
    """TRAIN v2: v1's exact tensors, then the 32 N1r rows in batch order.

    ``sources`` maps each pinned near-limit file name to its bytes. Every row
    must be a completed h = 3 mm solve whose mode ladder passed and whose
    geometry equals its frozen action; the stratum must hold its measured
    16/16 split, the acceptance it was kept under.
    """
    import numpy as np

    if _digest(v1_raw) != TRAIN_SHA256:
        raise ValueError("f08 TRAIN v1 identity differs")
    with np.load(io.BytesIO(v1_raw), allow_pickle=False) as data:
        v1_inputs, v1_targets = data["inputs"], data["targets"]
    v1_ids = list(load_public_train("1.0")["case_ids"])
    inputs, targets, case_ids, batches, worst = [], [], [], [], []
    for (observed_name, observed_pin), (
        actions_name,
        actions_pin,
    ) in _NEAR_LIMIT_SOURCES:
        observed_raw, actions_raw = sources[observed_name], sources[actions_name]
        if _digest(observed_raw) != observed_pin or _digest(actions_raw) != actions_pin:
            raise ValueError("f08 near-limit source identity differs")
        observed, actions = _json(observed_raw), _json(actions_raw)
        frozen = actions.get("actions")
        rows = observed.get("cases")
        if (
            actions.get("scope") != "PUBLIC_DEVELOPMENT_ONLY"
            or type(frozen) is not list
            or len(frozen) != 8
            or type(rows) is not dict
            or set(rows) != {f"pilot-{k:04d}" for k in range(8)}
        ):
            raise ValueError("f08 near-limit batch inventory differs")
        for k, action in enumerate(frozen):
            row = rows[f"pilot-{k:04d}"]
            if (
                type(row) is not dict
                or type(action) is not dict
                or row.get("case") != action
                or set(action) != set(FIELDS)
                or row.get("h_mm") != 3.0
                or row.get("mode_ladder", {}).get("verdict") != "PASS"
                or row.get("cost", {}).get("outcome") != "COMPLETED"
            ):
                raise ValueError("f08 near-limit row or frozen action differs")
            case_ids.append(f"near-limit-{len(case_ids):04d}")
            inputs.append([_number(action[name]) for name in FIELDS])
            targets.append(_target_row(row))
            worst.append(_number(row["worst_dynamic_mm_per_n"]))
        batches.append(
            {
                "observed": NEAR_LIMIT_EVIDENCE + "/" + observed_name,
                "observed_sha256": "sha256:" + observed_pin,
                "actions": NEAR_LIMIT_EVIDENCE + "/" + actions_name,
                "actions_sha256": "sha256:" + actions_pin,
            }
        )
    safe = sum(value <= _DYNAMIC_LIMIT_MM_PER_N for value in worst)
    if len(case_ids) != 32 or safe != 16:
        raise ValueError("f08 near-limit stratum split differs")
    x = np.concatenate([v1_inputs, np.asarray(inputs, dtype=np.float32)])
    y = np.concatenate([v1_targets, np.asarray(targets, dtype=np.float32)])
    if (
        x.shape != (287, 6)
        or y.shape != (287, 7)
        or x.dtype != np.float32
        or y.dtype != np.float32
        or not (np.isfinite(x).all() and np.isfinite(y).all())
    ):
        raise ValueError("f08 TRAIN v2 tensor shape or values differ")
    raw = _archive(x, y)
    provenance = {
        "schema": "carbon.f08.dev-train-v2.provenance.v1",
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "challenge": {"id": CHALLENGE_ID, "version": "1.1"},
        "train_sha256": "sha256:" + _digest(raw),
        "v1_train_sha256": "sha256:" + TRAIN_SHA256,
        "v1_provenance_sha256": "sha256:" + PROVENANCE_SHA256,
        "v1_rows": {"first": 0, "count": 255, "byte_identical_tensors": True},
        "case_ids": v1_ids + case_ids,
        "near_limit_stratum": {
            "name": "N1r",
            "run": "RR-PACKS-07b",
            "rows": {"first": 255, "count": 32},
            "selection": "lattice actions predicted 0.12-0.18 mm/N by a log-linear "
            "fit to the 40 RR-PACKS-07 solves; disjoint from TRAIN-256, the pilot, "
            "the ladder and RR-PACKS-07 N1",
            "acceptance": "each side of 0.15 mm/N at least one third, else redraw",
            "measured_split": {"safe": safe, "unsafe": len(worst) - safe},
            "worst_dynamic_mm_per_n": {"min": min(worst), "max": max(worst)},
            "batches": batches,
        },
        "superseded_stratum": {
            "name": "N1",
            "run": "RR-PACKS-07",
            "role": "HISTORY_NOT_TRAIN",
            "reason": "4/32 safe, under the one-third acceptance",
        },
        "mesh": TRAIN_MESH_STATEMENT,
        "inputs_mm": list(FIELDS),
        "learned_targets": list(TARGETS),
        "analytic_mass": "separate CAD check; excluded from learned targets",
        "original_256_complete": False,
        "failed_case": {"id": "train-0016", "status": "OBSERVER_FAILED"},
        "original_action_evaluation_role": "EXCLUDED_ALL_256",
        "near_limit_action_evaluation_role": "EXCLUDED_ALL_32",
    }
    return raw, provenance


def near_limit_sources(repository: Path) -> dict[str, bytes]:
    """The pinned N1r files' bytes from a repository checkout."""
    return {
        name: (repository / NEAR_LIMIT_EVIDENCE / name).read_bytes()
        for pair in _NEAR_LIMIT_SOURCES
        for name, _ in pair
    }


def _check_members(raw: bytes) -> None:
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


def _load_v2() -> dict:
    import numpy as np

    raw = (_DATA / _TRAIN_V2).read_bytes()
    provenance_raw = (_DATA / _PROVENANCE_V2).read_bytes()
    if (
        _digest(raw) != TRAIN_V2_SHA256
        or _digest(provenance_raw) != PROVENANCE_V2_SHA256
    ):
        raise ValueError("f08 public TRAIN artifact identity differs")
    provenance = _json(provenance_raw)
    case_ids = provenance.get("case_ids")
    v1 = load_public_train("1.0")
    if (
        provenance.get("schema") != "carbon.f08.dev-train-v2.provenance.v1"
        or provenance.get("scope") != "PUBLIC_DEVELOPMENT_ONLY"
        or provenance.get("challenge") != {"id": CHALLENGE_ID, "version": "1.1"}
        or provenance.get("train_sha256") != "sha256:" + TRAIN_V2_SHA256
        or provenance.get("v1_train_sha256") != "sha256:" + TRAIN_SHA256
        or type(case_ids) is not list
        or len(case_ids) != 287
        or len(set(case_ids)) != 287
        or tuple(case_ids[:255]) != v1["case_ids"]
        or not all(_NEAR_LIMIT_CASE_ID.fullmatch(c) for c in case_ids[255:])
        or provenance.get("mesh") != TRAIN_MESH_STATEMENT
        or provenance.get("inputs_mm") != list(FIELDS)
        or provenance.get("learned_targets") != list(TARGETS)
        or provenance.get("near_limit_stratum", {}).get("measured_split")
        != {"safe": 16, "unsafe": 16}
    ):
        raise ValueError("f08 public TRAIN provenance differs")
    _check_members(raw)
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        if set(data.files) != {"inputs", "targets"}:
            raise ValueError("f08 public TRAIN arrays differ")
        inputs, targets = data["inputs"], data["targets"]
    if (
        inputs.shape != (287, 6)
        or targets.shape != (287, 7)
        or inputs.dtype != np.float32
        or targets.dtype != np.float32
        or not np.array_equal(inputs[:255], v1["inputs"])
        or not np.array_equal(targets[:255], v1["targets"])
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


def load_public_train(version: str) -> dict:
    """Load pinned inert tensors; admission and scientific use belong elsewhere."""
    import numpy as np

    if version not in CHALLENGE_VERSIONS:
        raise ValueError("unknown public f08 TRAIN version")
    if version in ("1.1", "1.2"):
        return _load_v2()
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
    _check_members(raw)
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
