"""Source-bound public f02 DEVELOPMENT TRAIN: TRAIN40-v2 (OWNER-F02-TRAIN40-V2-01).

Forty RR-PACKS-08 solves in the fixed cold context (c30-i40-s0.5-rectangular):
24 S1 near-limit rows (70-100 W, 4-6 s; 12 on each side of 95 degC) and 16 S2
context rows (80-150 W, 5-20 s). One row per schedule: (peak power, on-time)
in, the spatial peak top temperature out. The extra energy is analytic and is
not a learned target. Neither an official evaluation pack nor a qualified
physical reference.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import statistics
import zipfile
from pathlib import Path

CHALLENGE_ID = "f02"
#: TRAIN40-v2 is F02's evaluation version 2 (the owner record calls it a new
#: evaluation version); TRAIN40 (v1) is history and is not served here.
CHALLENGE_VERSION = "2.0"
#: 2.1 (step-2 batch, STEP2_BATCH_VERSIONS_20261020) serves 2.0's TRAIN40-v2
#: bytes unchanged; only the version binding differs. Every loader names its
#: version; there is no default.
#: 2.2 (the catalog version, serving allowlist v7; Validator 2026-10-20)
#: serves the same TRAIN40-v2 bytes; only the version binding differs.
#: 2.3 (the Validator, 2026-10-20: the catalog binding plus Carbon's graph
#: training adapter) serves the same TRAIN40-v2 bytes.
CHALLENGE_VERSIONS = ("2.0", "2.1", "2.2", "2.3")
CONTEXT = {
    "coolant_c": 30.0,
    "h_w_m2_k": 2500.0,
    "initial_c": 40.0,
    "left_source_fraction": 0.5,
    "waveform": "rectangular",
}
FIELDS = ("peak_w", "on_time_s")
TARGETS = ("peak_top_c",)
LIMIT_C = 95.0
EVIDENCE = "docs/development/evidence/f02-cold-pack-20261020"
SOURCE = (
    EVIDENCE + "/train40v2.jsonl",
    "b6875185efbaef2d759d9b1159d4343ae7b1f2b3a8f23aa21b212685a4caf754",
)
TRAIN_SHA256 = "1201ec5461bfc08ad2ae4522eafc147282f4167e4bb222ed4e798284faa9a4c3"
PROVENANCE_SHA256 = "47764c7bdf68b3d3b70bb1c98f66afc766a84e301be466d805d3e63d388e4d3d"
#: OWNER-F02-TRAIN40-V2-01 revision: the TRAIN spread is the population std
#: (ddof 0) of the 24 S1 rows' peak, recorded as 6.701 degC. The exact value is
#: recomputed from the pinned rows and must round to the recorded figure.
TRAIN_PEAK_STD_RECORDED_C = 6.701
_DATA = Path(__file__).with_name("data")
_REPOSITORY = Path(__file__).resolve().parents[2]
_TRAIN = "f02-dev-train40-v2.npz"
_PROVENANCE = "f02-dev-train40-v2.provenance.json"
_CASE_ID = re.compile(
    r"c30-i40-s0\.5-rectangular-p[0-9]+-d[0-9]+(\.[0-9]+)?-train-v2(s1|s2)\Z"
)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite f02 source number required")
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


def _rows(raw: bytes) -> list[dict]:
    if _digest(raw) != SOURCE[1]:
        raise ValueError("f02 TRAIN source identity differs")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if len(rows) != 40 or len({r.get("case_id") for r in rows}) != 40:
        raise ValueError("f02 TRAIN inventory differs")
    for row in rows:
        inputs = row.get("inputs")
        if (
            row.get("schema") != "carbon.f02.train-record.v1"
            or type(row.get("case_id")) is not str
            or not _CASE_ID.fullmatch(row["case_id"])
            or type(inputs) is not dict
            or set(inputs) != set(CONTEXT) | set(FIELDS)
            or {k: inputs[k] for k in CONTEXT} != CONTEXT
        ):
            raise ValueError("f02 TRAIN row or context differs")
    return rows


def _stratum(case_id: str) -> str:
    return case_id.rsplit("-train-v2", 1)[1].upper()


def train_peak_std_c(rows: list[dict]) -> float:
    """The decided spread: population std (ddof 0) of the S1 rows' peak."""
    s1 = [
        _number(r["outputs"]["peak_top_c"])
        for r in rows
        if _stratum(r["case_id"]) == "S1"
    ]
    if len(s1) != 24:
        raise ValueError("f02 S1 stratum differs")
    return statistics.pstdev(s1)


def derive_public_train(source_raw: bytes) -> tuple[bytes, dict]:
    """Reproduce inert TRAIN bytes from the exact retained export."""
    import numpy as np

    rows = _rows(source_raw)
    std = train_peak_std_c(rows)
    if round(std, 3) != TRAIN_PEAK_STD_RECORDED_C:
        raise ValueError("f02 TRAIN spread no longer matches its record")
    strata = {}
    for row in rows:
        side = (
            "at_or_below"
            if _number(row["outputs"]["peak_top_c"]) <= LIMIT_C
            else "above"
        )
        counts = strata.setdefault(
            _stratum(row["case_id"]), {"at_or_below": 0, "above": 0}
        )
        counts[side] += 1
    if (
        strata.get("S1") != {"at_or_below": 12, "above": 12}
        or sum(strata.get("S2", {}).values()) != 16
    ):
        raise ValueError("f02 TRAIN stratum split differs")
    x = np.asarray(
        [[_number(r["inputs"][k]) for k in FIELDS] for r in rows], dtype=np.float32
    )
    y = np.asarray(
        [[_number(r["outputs"]["peak_top_c"])] for r in rows], dtype=np.float32
    )
    if x.shape != (40, 2) or y.shape != (40, 1):
        raise ValueError("f02 TRAIN tensor shape differs")
    raw = _archive(x, y)
    provenance = {
        "schema": "carbon.f02.dev-train40-v2.provenance.v1",
        "scope": "PUBLIC_DEVELOPMENT_ONLY",
        "challenge": {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION},
        "decision": "OWNER-F02-TRAIN40-V2-01",
        "run": "RR-PACKS-08",
        "source": {"path": SOURCE[0], "sha256": "sha256:" + SOURCE[1]},
        "train_sha256": "sha256:" + _digest(raw),
        "case_ids": [r["case_id"] for r in rows],
        "context": dict(CONTEXT),
        "inputs": list(FIELDS),
        "learned_targets": list(TARGETS),
        "analytic_extra_energy": "(peak_w - 20) * on_time_s; excluded from learned targets",
        "strata": strata,
        "limit_c": LIMIT_C,
        "train_peak_std_c": {
            "value": std,
            "recorded": TRAIN_PEAK_STD_RECORDED_C,
            "rule": "population std (ddof 0) of the 24 S1 rows' peak_top_c",
        },
        "superseded": {"name": "TRAIN40", "role": "HISTORY_NOT_SERVED"},
    }
    return raw, provenance


def load_public_train(version: str) -> dict:
    """Load pinned inert tensors; admission and scientific use belong elsewhere.

    The version is required, never defaulted: a version bump must not silently move what is served.
    """
    import numpy as np

    if version not in CHALLENGE_VERSIONS:
        raise ValueError("unknown public f02 TRAIN version")
    raw = (_DATA / _TRAIN).read_bytes()
    provenance_raw = (_DATA / _PROVENANCE).read_bytes()
    if _digest(raw) != TRAIN_SHA256 or _digest(provenance_raw) != PROVENANCE_SHA256:
        raise ValueError("f02 public TRAIN artifact identity differs")
    provenance = json.loads(provenance_raw)
    if (
        provenance.get("challenge")
        != {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION}
        or provenance.get("train_sha256") != "sha256:" + TRAIN_SHA256
        or provenance.get("inputs") != list(FIELDS)
        or provenance.get("learned_targets") != list(TARGETS)
        or provenance.get("context") != CONTEXT
        or len(provenance.get("case_ids", ())) != 40
    ):
        raise ValueError("f02 public TRAIN provenance differs")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if {m.filename for m in members} != {"inputs.npy", "targets.npy"} or any(
            m.compress_type != zipfile.ZIP_STORED or m.flag_bits & 1 for m in members
        ):
            raise ValueError("f02 public TRAIN members differ")
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        inputs, targets = data["inputs"], data["targets"]
    if (
        inputs.shape != (40, 2)
        or targets.shape != (40, 1)
        or inputs.dtype != np.float32
        or targets.dtype != np.float32
        or not (np.isfinite(inputs).all() and np.isfinite(targets).all())
    ):
        raise ValueError("f02 public TRAIN tensors differ")
    inputs.setflags(write=False)
    targets.setflags(write=False)
    return {
        "train": raw,
        "inputs": inputs,
        "targets": targets,
        "case_ids": tuple(provenance["case_ids"]),
        "provenance": provenance,
        "train_peak_std_c": provenance["train_peak_std_c"]["value"],
    }
