"""Ribbed Bracket 2.0 (f08-ribbed-bracket 2.0): the numeric interface and the public DEVELOPMENT TRAIN 240.

RB 2.0 is a NEW interface, not F08 1.x's. It has 12 inputs: the 1.7 geometry plus fillet radius, alloy, payload, load
angle, load position in the gap, and damping.

Owner RB20-COLS (typed in the exam-rb seat, 22 Nov 2026 01:56Z) widens 2.0's graded outputs from the MOUNT deck's 7 to
the 22 columns `GRADED_OUTPUTS`, in exam-rb's column order (RECEIPTS 22 Nov 01:58:57Z):
- c0-c6: the deck's 7 graded outputs (slice 1, 12 Nov, unchanged);
- c7-c16: the 2nd to 11th natural frequencies (`modes_hz[1..10]`, 0-based: `modes_hz[0]` is `first_mode_hz`);
- c17-c19: the three patch '2.0' outputs;
- c20-c21: the first two components of the static tip displacement vector. Its third component is `static_tip_mm_per_n`
  (c1); this is the tip re-scope.

`cad_mass_kg` is EXACT (U = 0) and never a model output.

Interface names are identifiers (`modes_hz_7`, `patch_static_max_principal`, `tip_static_displacement_mm_per_n_0`), so
every grade surface, log code and registration key can carry them. `SOURCE_KEYS` maps each name to the record key the
public records use (`modes_hz[7]`, `patch.static_max_principal`, ...).

**The TRAIN.** It is re-assembled from PUBLIC data only, by exam-rb's tool
(`codex-queue/reports/RB20_TRAIN22_ASSEMBLE_20261122/rb20_train22_assemble.py`):
- inputs: the public table cd78ee98 (the 8 MOUNT outputs), joined by job_id to the public aux extract 8b7087c2 of the
  same TRAIN records e0eaf28e (the 15 new columns);
- output: an allow-listed source JSONL of 23 outputs per row (no job id, draw id, batch, wall time or image), ordered by
  the sha256 of each row's canonical inputs and numbered train-0001.. in that order.

This module derives the npz and the provenance from that source and pins the three artifacts. No new solve: the owner's
cost clause is answered by exam-rb (every truth and rough record already carries the 22 columns).

**Fail closed.** `RULINGS` holds the receipts this interface needs, each None (HUMAN_INPUT) until its owner rules. The
three artifact pins are None until v2 receipts the assembled TRAIN. While any of these is None, `load_public_train`
REFUSES. Nothing here is an evaluation, a qualification or LIVE authority; the values are DEVELOPMENT values.
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
CHALLENGE_VERSION = "2.0"
TRAIN_NAME = "f08-dev-train-2p0-v2"
_DATA = Path(__file__).with_name("data")
_PROVENANCE_SCHEMA = "carbon.f08.dev-train-2p0.provenance.v2"
_INTERFACE_SCHEMA = "carbon.f08.numeric-interface.v2p0-22"
_SCOPE = "PUBLIC_DEVELOPMENT_ONLY"
_TRANSFORM = "rb20-public-table-plus-aux-to-sorted-jsonl-to-npz-v2"

#: The interface inputs = THE MINER ORDER (slice 1, Miner X-C 12 Nov): the RB 2.0 row runner's order. alloy_index is an
#: exact 0.0 / 1.0 / 2.0 index into `ALLOY_IDS` (any other value refuses).
INPUT_NAMES = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
    "fillet_radius_mm",
    "alloy_index",
    "payload_mass_kg",
    "load_angle_deg",
    "load_position_in_gap",
    "damping_ratio",
)
INPUT_UNITS = (
    "millimetre",
    "millimetre",
    "millimetre",
    "millimetre",
    "millimetre",
    "millimetre",
    "millimetre",
    "index",
    "kilogram",
    "degree",
    "dimensionless",
    "dimensionless",
)
#: f08_deck_v2.ALLOY_IDS (OWNER-F08-V2-ALLOYS-SIGNED-01), in alloy_index order.
ALLOY_IDS = ("6061-T6", "4130-normalized", "Ti-6Al-4V-annealed")
#: The MOUNT deck's outputs, in the deck's order (f08_v2_payload OUTPUTS then MOUNT_OUTPUTS; the public table's `outs`).
DECK_OUTPUTS = (
    "worst_dynamic_mm_per_n",
    "static_tip_mm_per_n",
    "cad_mass_kg",
    "static_fillet_stress_mpa_per_n",
    "dynamic_fillet_stress_mpa_per_n",
    "first_mode_hz",
    "worst_dynamic_base_mm_per_g",
    "dynamic_fillet_stress_base_mpa_per_g",
)
#: Exact from the inputs (U = 0): never a model output, never graded.
EXACT_OUTPUTS = ("cad_mass_kg",)
_PATCH = (
    "dynamic_frequency_hz",
    "dynamic_max_principal_at_vm_frequency",
    "static_max_principal",
)
#: The 22 graded outputs, in exam-rb's column order (owner RB20-COLS): interface name -> the public records' key.
SOURCE_KEYS = {
    **{k: k for k in DECK_OUTPUTS if k not in EXACT_OUTPUTS},
    **{f"modes_hz_{i}": f"modes_hz[{i}]" for i in range(1, 11)},
    **{f"patch_{name}": f"patch.{name}" for name in _PATCH},
    **{
        f"tip_static_displacement_mm_per_n_{i}": f"tip_static_displacement_mm_per_n[{i}]"
        for i in (0, 1)
    },
}
GRADED_OUTPUTS = tuple(SOURCE_KEYS)
#: The keys of one source row's outputs: the 22 graded ones (under their record keys) and the exact mass.
SOURCE_OUTPUTS = (*SOURCE_KEYS.values(), *EXACT_OUTPUTS)
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
OUTPUT_UNITS = {
    "worst_dynamic_mm_per_n": "millimetre_per_newton",
    "static_tip_mm_per_n": "millimetre_per_newton",
    "cad_mass_kg": "kilogram",
    "static_fillet_stress_mpa_per_n": "megapascal_per_newton",
    "dynamic_fillet_stress_mpa_per_n": "megapascal_per_newton",
    "first_mode_hz": "hertz",
    "worst_dynamic_base_mm_per_g": "millimetre_per_g",
    "dynamic_fillet_stress_base_mpa_per_g": "megapascal_per_g",
    **{f"modes_hz_{i}": "hertz" for i in range(1, 11)},
    "patch_dynamic_frequency_hz": "hertz",
    "tip_static_displacement_mm_per_n_0": "millimetre_per_newton",
    "tip_static_displacement_mm_per_n_1": "millimetre_per_newton",
    # the two patch principal stresses' units are NOT set here: `RULINGS["new_output_units"]` (exam-rb) names them
    "patch_dynamic_max_principal_at_vm_frequency": None,
    "patch_static_max_principal": None,
}
#: The interface dtype of TRAIN, inputs and outputs (F08 1.x's; slice 1's ruling).
DTYPE = "float32"
ROWS = 240

#: The receipts this interface needs, each None (HUMAN_INPUT) until ruled; while any is None the TRAIN refuses:
#: - graded_outputs: model-eval writes it (19 Nov approval + 17 Nov KEEP 6 + owner RB20-COLS, 22 Nov);
#: - train_of_record: v2 (the re-assembled table: its source / npz / provenance shas);
#: - mesh_statement: v2 + model-eval (TRAIN hoo2 h 1.7 / fh 0.5 vs the exam's per-design production rung);
#: - interface_order: the 22-column order (slice 1's Miner X-C ruling named the 7-output order only);
#: - new_output_units: exam-rb (the units of the two patch principal stresses).
RULINGS = {
    "graded_outputs": None,
    "train_of_record": None,
    "mesh_statement": None,
    "interface_order": None,
    "new_output_units": None,
}

#: Upstream identities of the PUBLIC inputs the source is assembled from.
TABLE_SHA256 = "cd78ee98608e26def6eb5b97b1a1ce9c7f6acb531a7c1abc4a2367a291c79f5a"
AUX_SHA256 = "8b7087c2cc6bc288491ce2c200eca832cbda1373c3afc0f6b5dab8ad879dcdee"
TABLE_RECORDS_SHA256 = (
    "e0eaf28ed60052ff2eff0955ae08ec87045533ca1d0e07444d8012d3db651b43"
)
#: The assembled artifacts' own identities (bytes in `data/`): None until v2 receipts the assembler's run.
SOURCE_SHA256 = None
TRAIN_SHA256 = None
PROVENANCE_SHA256 = None

_CASE_ID = re.compile(r"train-[0-9]{4}\Z")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError("duplicate RB 2.0 TRAIN key")
        result[name] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite RB 2.0 TRAIN token: " + value)


def _json(raw: bytes):
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)


def _number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise ValueError("finite numeric RB 2.0 TRAIN value required")
    return float(value)


def interface_document() -> dict:
    """The numeric layout of one row: inputs and graded outputs, unscaled."""
    return {
        "schema": _INTERFACE_SCHEMA,
        "challenge": {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION},
        "dtype": "<f4" if DTYPE == "float32" else "<f8",
        "input_names": list(INPUT_NAMES),
        "input_units": list(INPUT_UNITS),
        "alloy_ids": list(ALLOY_IDS),
        "target_names": list(GRADED_OUTPUTS),
        "target_units": [OUTPUT_UNITS[k] for k in GRADED_OUTPUTS],
        "target_source_keys": [SOURCE_KEYS[k] for k in GRADED_OUTPUTS],
        "exact_outputs": list(EXACT_OUTPUTS),
        "learned_targets_only": True,
        "one_row_per_case": True,
    }


def _row(inputs: object, outputs: object) -> tuple[dict, dict]:
    """One source row's inputs and its 22 graded outputs under their INTERFACE names (the exact mass checked, dropped)."""
    if type(inputs) is not dict or set(inputs) != set(INPUT_NAMES):
        raise ValueError("an RB 2.0 TRAIN row needs exactly the 12 inputs")
    if type(outputs) is not dict or set(outputs) != set(SOURCE_OUTPUTS):
        raise ValueError(
            "an RB 2.0 TRAIN row needs exactly the 22 graded outputs and the mass"
        )
    x = {k: _number(inputs[k]) for k in INPUT_NAMES}
    if x["alloy_index"] not in tuple(float(i) for i in range(len(ALLOY_IDS))):
        raise ValueError("alloy_index must index ALLOY_IDS")
    _number(outputs["cad_mass_kg"])
    return x, {name: _number(outputs[key]) for name, key in SOURCE_KEYS.items()}


def _parse_source(source_raw: bytes) -> list[tuple[str, dict, dict]]:
    if not source_raw.endswith(b"\n") or b"\r" in source_raw:
        raise ValueError("RB 2.0 TRAIN source must be LF-terminated lines")
    rows, keys = [], []
    for i, line in enumerate(source_raw[:-1].split(b"\n"), 1):
        record = _json(line)
        if type(record) is not dict or set(record) != {"case_id", "inputs", "outputs"}:
            raise ValueError("RB 2.0 TRAIN source record fields differ")
        if record["case_id"] != f"train-{i:04d}" or not _CASE_ID.match(
            record["case_id"]
        ):
            raise ValueError("RB 2.0 TRAIN case ids must be train-0001.. in order")
        x, y = _row(record["inputs"], record["outputs"])
        if _canonical(record) != line:
            raise ValueError("RB 2.0 TRAIN source line is not canonical")
        rows.append((record["case_id"], x, y))
        keys.append(_sha(_canonical(x)))
    if len(rows) != ROWS or keys != sorted(keys) or len(set(keys)) != ROWS:
        raise ValueError("RB 2.0 TRAIN source order or count differs")
    return rows


def _npz(inputs, targets) -> bytes:
    import numpy as np

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, array in (("inputs", inputs), ("targets", targets)):
            member = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o600 << 16
            with archive.open(member, "w", force_zip64=True) as stream:
                np.lib.format.write_array(stream, array, allow_pickle=False)
    return output.getvalue()


def derive_public_train(source_raw: bytes) -> tuple[bytes, dict]:
    """TRAIN npz (inputs 240 x 12, targets 240 x 22) + provenance from the source JSONL (deterministic bytes)."""
    import numpy as np

    rows = _parse_source(source_raw)
    dtype = "<f4" if DTYPE == "float32" else "<f8"
    x = np.asarray([[r[1][k] for k in INPUT_NAMES] for r in rows], dtype=dtype)
    y = np.asarray([[r[2][k] for k in GRADED_OUTPUTS] for r in rows], dtype=dtype)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("RB 2.0 TRAIN is not finite at the interface dtype")
    raw = _npz(x, y)
    provenance = {
        "schema": _PROVENANCE_SCHEMA,
        "scope": _SCOPE,
        "challenge": {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION},
        "train_name": TRAIN_NAME,
        "table_sha256": "sha256:" + TABLE_SHA256,
        "aux_sha256": "sha256:" + AUX_SHA256,
        "table_records_sha256": "sha256:" + TABLE_RECORDS_SHA256,
        "source_sha256": "sha256:" + _sha(source_raw),
        "train_sha256": "sha256:" + _sha(raw),
        "transformation_version": _TRANSFORM,
        "case_ids": [r[0] for r in rows],
        "numeric_interface": interface_document(),
    }
    return raw, provenance


def _ruled() -> None:
    open_rulings = sorted(k for k, v in RULINGS.items() if v is None)
    if open_rulings:
        raise ValueError(
            "RB 2.0 public TRAIN is not ruled yet (HUMAN_INPUT): "
            + ", ".join(open_rulings)
        )
    if None in (SOURCE_SHA256, TRAIN_SHA256, PROVENANCE_SHA256):
        raise ValueError("RB 2.0 public TRAIN is not frozen yet (HUMAN_INPUT)")
    if any(OUTPUT_UNITS[k] is None for k in GRADED_OUTPUTS):
        raise ValueError("RB 2.0 output units are not all set yet (HUMAN_INPUT)")


def load_public_train(version: str = CHALLENGE_VERSION) -> dict:
    """Pinned inert tensors; admission and scientific use belong elsewhere."""
    import numpy as np

    if version != CHALLENGE_VERSION:
        raise ValueError("unknown public RB 2.0 TRAIN version")
    _ruled()
    source_raw = (_DATA / f"{TRAIN_NAME}.source.jsonl").read_bytes()
    train_raw = (_DATA / f"{TRAIN_NAME}.npz").read_bytes()
    provenance_raw = (_DATA / f"{TRAIN_NAME}.provenance.json").read_bytes()
    if (
        _sha(source_raw) != SOURCE_SHA256
        or _sha(train_raw) != TRAIN_SHA256
        or _sha(provenance_raw) != PROVENANCE_SHA256
    ):
        raise ValueError("RB 2.0 public TRAIN artifact identity differs")
    want_raw, want = derive_public_train(source_raw)
    if want_raw != train_raw or _json(provenance_raw) != want:
        raise ValueError("RB 2.0 public TRAIN provenance differs")
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        x, y = data["inputs"], data["targets"]
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "train": train_raw,
        "inputs": x,
        "targets": y,
        "case_ids": tuple(want["case_ids"]),
        "provenance": want,
    }


def provenance_bytes(provenance: dict) -> bytes:
    """The provenance file's bytes: canonical JSON plus a newline."""
    return _canonical(provenance) + b"\n"


assert len(GRADED_OUTPUTS) == 22 and all(_IDENTIFIER.match(k) for k in GRADED_OUTPUTS)
