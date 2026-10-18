"""Custody and codec checks for public, Challenge-unbound model artifacts.

This module validates bytes and closed declarations only. It never imports a
declared constructor, loads a model, or asserts that an external receiver ran.
"""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import hashlib
import io
import json
import math
import re
import struct
import sys
import zipfile
from pathlib import Path

SCHEMA = "carbon.scorelab.public-unbound-native-custody.v1"
SCHEMA_V2 = "carbon.scorelab.public-unbound-native-custody.v2"
FIXTURE_SCHEMA = "carbon.development.library-public-fixture.v1"
FIXTURE_SCHEMA_V2 = "carbon.development.library-public-fixture.v2"
MODE = "PUBLIC_SYNTHETIC_UNBOUND"
LEGACY_BINDING = "UNBOUND_SYNTHETIC_DEVELOPMENT"
CODEC = "numpy.npz.numeric.v1"
MAX_STATE_BYTES = 512 * 1024 * 1024
MAX_FIXTURE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_COUNT = 128
MAX_CENTRAL_DIRECTORY_BYTES = 65536
MIN_NPY_MEMBER_NAME_BYTES = 5
MAX_V2_STATE_MEMBER_COUNT = MAX_CENTRAL_DIRECTORY_BYTES // (
    46 + MIN_NPY_MEMBER_NAME_BYTES
)
MAX_ZIP_MEMBER_NAME_BYTES = 128
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_AUXILIARY_ARTIFACTS = 16
MAX_AUXILIARY_JSON_BYTES = 4 * 1024 * 1024
MAX_AUXILIARY_TOTAL_BYTES = 8 * 1024 * 1024
_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.npz$")
_JSON_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json$")
_ARRAY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_AUX_ROLE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PROOF_AUX_ROLE = {
    "PRODUCER_DECLARATION": "producer_declaration",
    "BUILD_RECEIPT_BYTES": "build_receipt",
    "HOST_INSPECTION_RECEIPT_BYTES": "host_inspection_receipt",
}
_DTYPE_BYTES = {
    "bool": 1,
    "float16": 2,
    "float32": 4,
    "float64": 8,
    "int8": 1,
    "int16": 2,
    "int32": 4,
    "int64": 8,
    "uint8": 1,
    "uint16": 2,
    "uint32": 4,
    "uint64": 8,
    "complex64": 8,
    "complex128": 16,
}
_NPY_DTYPE = re.compile(r"^(?P<endian>[<>=|])(?P<kind>[biufc])(?P<size>16|8|4|2|1)$")


class CustodyRefused(ValueError):
    """The public artifact set is malformed or does not match its declaration."""


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _exact_keys(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise CustodyRefused(f"{label}_fields")


def _digest(value, label):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise CustodyRefused(f"{label}_digest")


def _safe_file(root: Path, name: str, *, json_file: bool = False) -> Path:
    allowed = _JSON_FILE if json_file else _FILE
    if type(name) is not str or not allowed.fullmatch(name):
        raise CustodyRefused("artifact_filename")
    path = root / name
    if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
        raise CustodyRefused("artifact_file_not_regular")
    return path


def _artifact_root(value) -> Path:
    root = Path(value)
    if root.is_symlink() or not root.is_dir():
        raise CustodyRefused("artifact_root")
    try:
        return root.resolve(strict=True)
    except OSError as exc:
        raise CustodyRefused("artifact_root") from exc


def _read_bounded(path: Path, limit: int, label: str) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CustodyRefused(f"{label}_stat") from exc
    if size <= 0 or size > limit:
        raise CustodyRefused(f"{label}_size")
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise CustodyRefused(f"{label}_read") from exc
    if len(data) > limit:
        raise CustodyRefused(f"{label}_size")
    if len(data) != size:
        raise CustodyRefused(f"{label}_size_changed")
    try:
        if path.stat().st_size != len(data):
            raise CustodyRefused(f"{label}_size_changed")
    except OSError as exc:
        raise CustodyRefused(f"{label}_stat") from exc
    return data


def _npy_header(stream):
    if stream.read(6) != b"\x93NUMPY":
        raise CustodyRefused("npz_npy_magic")
    version = stream.read(2)
    if version == b"\x01\x00":
        length = struct.unpack("<H", stream.read(2))[0]
    elif version == b"\x02\x00":
        length = struct.unpack("<I", stream.read(4))[0]
    else:
        raise CustodyRefused("npz_npy_version")
    if not 1 <= length <= 65536:
        raise CustodyRefused("npz_npy_header_size")
    raw_header = stream.read(length)
    if len(raw_header) != length:
        raise CustodyRefused("npz_npy_header_truncated")
    try:
        header = ast.literal_eval(raw_header.decode("ascii").strip())
    except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
        raise CustodyRefused("npz_npy_header") from exc
    if (
        type(header) is not dict
        or set(header) != {"descr", "fortran_order", "shape"}
        or header["fortran_order"] is not False
        or type(header["shape"]) is not tuple
        or len(header["shape"]) > 6
        or any(type(dim) is not int or dim < 1 for dim in header["shape"])
        or type(header["descr"]) is not str
    ):
        raise CustodyRefused("npz_npy_header_fields")
    match = _NPY_DTYPE.fullmatch(header["descr"])
    if match is None:
        raise CustodyRefused("npz_numeric_dtype")
    endian = match["endian"]
    kind = match["kind"]
    size = int(match["size"])
    names = {
        ("b", 1): "bool",
        ("i", 1): "int8",
        ("u", 1): "uint8",
        ("i", 2): "int16",
        ("u", 2): "uint16",
        ("i", 4): "int32",
        ("u", 4): "uint32",
        ("i", 8): "int64",
        ("u", 8): "uint64",
        ("f", 2): "float16",
        ("f", 4): "float32",
        ("f", 8): "float64",
        ("c", 8): "complex64",
        ("c", 16): "complex128",
    }
    dtype = names.get((kind, size))
    if dtype is None or (size == 1 and endian not in "|=<>"):
        raise CustodyRefused("npz_numeric_dtype")
    if size > 1 and endian not in {"=", "<" if sys.byteorder == "little" else ">"}:
        raise CustodyRefused("npz_nonnative_dtype")
    return header["shape"], dtype, size


def _preflight_zip_directory(
    data: bytes,
    *,
    max_bytes: int,
    max_member_count: int = MAX_MEMBER_COUNT,
    allow_graph_header: bool = False,
    max_directory_bytes: int = MAX_CENTRAL_DIRECTORY_BYTES,
) -> None:
    """Bound and validate central-directory records before ZipFile parses them."""
    if not 22 <= len(data) <= max_bytes:
        raise CustodyRefused("npz_archive_size")
    search_start = max(0, len(data) - (22 + 65535))
    eocd_offset = data.rfind(b"PK\x05\x06", search_start)
    if eocd_offset < 0 or eocd_offset + 22 > len(data):
        raise CustodyRefused("npz_eocd")
    (
        _signature,
        disk_number,
        directory_disk,
        entries_on_disk,
        entry_count,
        directory_size,
        directory_offset,
        comment_size,
    ) = struct.unpack_from("<4s4H2LH", data, eocd_offset)
    if (
        eocd_offset + 22 + comment_size != len(data)
        or disk_number != 0
        or directory_disk != 0
        or entries_on_disk != entry_count
        or entry_count in {0, 0xFFFF}
        or entry_count > max_member_count
        or directory_size in {0xFFFFFFFF}
        or directory_offset in {0xFFFFFFFF}
        or directory_size > max_directory_bytes
        or directory_offset + directory_size != eocd_offset
    ):
        raise CustodyRefused("npz_directory_bounds")
    if eocd_offset >= 20 and data[eocd_offset - 20 : eocd_offset - 16] == b"PK\x06\x07":
        # ZipFile treats this adjacent locator as authoritative and can replace
        # the ordinary EOCD bounds above with ZIP64 directory metadata.
        raise CustodyRefused("npz_zip64_locator")

    cursor = directory_offset
    end = directory_offset + directory_size
    names = set()
    expanded_size = 0
    for _ in range(entry_count):
        if cursor + 46 > end:
            raise CustodyRefused("npz_directory_record_truncated")
        (
            signature,
            _version_made,
            _version_needed,
            flags,
            compression,
            _mod_time,
            _mod_date,
            _crc32,
            compressed_size,
            uncompressed_size,
            name_size,
            extra_size,
            member_comment_size,
            disk_start,
            _internal_attributes,
            external_attributes,
            local_header_offset,
        ) = struct.unpack_from("<4s6H3L5H2L", data, cursor)
        record_size = 46 + name_size + extra_size + member_comment_size
        name_start = cursor + 46
        name_end = name_start + name_size
        extra_end = name_end + extra_size
        record_end = cursor + record_size
        if (
            signature != b"PK\x01\x02"
            or record_end > end
            or not 1 <= name_size <= MAX_ZIP_MEMBER_NAME_BYTES
            or extra_size > 4096
            or member_comment_size > 1024
            or flags & (1 | 0x40)
            or compression not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            or disk_start != 0
            or compressed_size == 0xFFFFFFFF
            or uncompressed_size == 0xFFFFFFFF
            or local_header_offset == 0xFFFFFFFF
            or local_header_offset >= directory_offset
            or compressed_size > max_bytes
            or uncompressed_size > max_bytes
            or ((external_attributes >> 16) & 0o170000) not in {0, 0o100000}
        ):
            raise CustodyRefused("npz_directory_member")
        try:
            name = data[name_start:name_end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise CustodyRefused("npz_directory_member_name") from exc
        if name in names or not (
            re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}\.npy", name)
            or (allow_graph_header and name == "__header__.npy")
        ):
            raise CustodyRefused("npz_directory_member_name")
        # Reject malformed and ZIP64 extra fields before handing the bytes to ZipFile.
        extra_cursor = name_end
        while extra_cursor < extra_end:
            if extra_cursor + 4 > extra_end:
                raise CustodyRefused("npz_directory_extra")
            extra_id, extra_length = struct.unpack_from("<HH", data, extra_cursor)
            extra_cursor += 4
            if extra_cursor + extra_length > extra_end or extra_id == 0x0001:
                raise CustodyRefused("npz_directory_extra")
            extra_cursor += extra_length
        names.add(name)
        expanded_size += uncompressed_size
        if expanded_size > max_bytes:
            raise CustodyRefused("npz_member_set_or_size")
        cursor = record_end
    if cursor != end:
        raise CustodyRefused("npz_directory_trailing_bytes")


def _array_map(value, *, label: str, max_arrays: int, max_bytes: int):
    if type(value) is not dict or not 1 <= len(value) <= max_arrays:
        raise CustodyRefused(f"{label}_arrays")
    total = 0
    checked = {}
    for name, field in value.items():
        if (
            type(name) is not str
            or not _ARRAY.fullmatch(name)
            or type(field) is not dict
            or set(field) != {"dtype", "shape"}
            or type(field["dtype"]) is not str
            or field["dtype"] not in _DTYPE_BYTES
            or type(field["shape"]) is not list
            or len(field["shape"]) > 6
            or any(
                type(dim) is not int or not 1 <= dim <= 1_000_000
                for dim in field["shape"]
            )
        ):
            raise CustodyRefused(f"{label}_array_descriptor")
        count = 1
        for dimension in field["shape"]:
            count *= dimension
            if count > max_bytes:
                raise CustodyRefused(f"{label}_array_size")
        total += count * _DTYPE_BYTES[field["dtype"]]
        if total > max_bytes:
            raise CustodyRefused(f"{label}_total_size")
        checked[name] = {"dtype": field["dtype"], "shape": list(field["shape"])}
    return checked


def validate_numeric_npz(
    path_or_bytes,
    arrays: dict,
    *,
    max_bytes: int,
    max_member_count: int = MAX_MEMBER_COUNT,
) -> dict:
    """Validate exact descriptors and return raw member digests without unpickling."""
    observed = inspect_numeric_npz(
        path_or_bytes, max_bytes=max_bytes, max_member_count=max_member_count
    )
    if set(observed) != set(arrays):
        raise CustodyRefused("npz_member_set_or_size")
    for name, expected in arrays.items():
        if (
            observed[name]["dtype"] != expected["dtype"]
            or observed[name]["shape"] != expected["shape"]
        ):
            raise CustodyRefused("npz_numeric_descriptor_mismatch")
    return {name: value["raw_sha256"] for name, value in observed.items()}


def inspect_numeric_npz(
    path_or_bytes,
    *,
    max_bytes: int,
    max_member_count: int = MAX_MEMBER_COUNT,
    allow_graph_header: bool = False,
    max_directory_bytes: int = MAX_CENTRAL_DIRECTORY_BYTES,
) -> dict:
    """Discover only bounded numeric descriptors; never materialize array values."""
    try:
        result = {}
        archive_bytes = (
            path_or_bytes
            if type(path_or_bytes) is bytes
            else _read_bounded(Path(path_or_bytes), max_bytes, "npz_archive")
        )
        _preflight_zip_directory(
            archive_bytes,
            max_bytes=max_bytes,
            max_member_count=max_member_count,
            allow_graph_header=allow_graph_header,
            max_directory_bytes=max_directory_bytes,
        )
        source = io.BytesIO(archive_bytes)
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if (
                not 1 <= len(entries) <= max_member_count
                or len({entry.filename for entry in entries}) != len(entries)
                or sum(entry.file_size for entry in entries) > max_bytes
            ):
                raise CustodyRefused("npz_member_set_or_size")
            for entry in entries:
                if (
                    entry.is_dir()
                    or entry.flag_bits & 1
                    or not entry.filename.endswith(".npy")
                    or not (
                        re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}\.npy", entry.filename)
                        or (allow_graph_header and entry.filename == "__header__.npy")
                    )
                    or entry.file_size <= 0
                    or entry.file_size > max_bytes
                    or entry.compress_size > max_bytes
                ):
                    raise CustodyRefused("npz_unsafe_member")
                with archive.open(entry) as stream:
                    shape, dtype, itemsize = _npy_header(stream)
                    count = 1
                    for dimension in shape:
                        count *= dimension
                        if count * itemsize > max_bytes:
                            raise CustodyRefused("npz_array_size")
                    if entry.file_size - stream.tell() != count * itemsize:
                        raise CustodyRefused("npz_payload_length")
                    raw_hash = hashlib.sha256()
                    while chunk := stream.read(1024 * 1024):
                        raw_hash.update(chunk)
                    result[entry.filename[:-4]] = {
                        "dtype": dtype,
                        "shape": list(shape),
                        "raw_sha256": "sha256:" + raw_hash.hexdigest(),
                    }
        return result
    except CustodyRefused:
        raise
    except (
        OSError,
        EOFError,
        struct.error,
        ValueError,
        TypeError,
        OverflowError,
        RecursionError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise CustodyRefused("npz_invalid") from exc


def manifest_from_jno_r2(artifact_root: Path) -> dict:
    """Bind the retained public R2 probe/custody records to e82's closed ABI."""
    artifact_root = _artifact_root(artifact_root)
    probe_path = _safe_file(artifact_root, "jno-probe.json", json_file=True)
    custody_path = _safe_file(artifact_root, "jno-state-custody.json", json_file=True)
    _, probe = _load_json(probe_path, label="jno_probe")
    custody_bytes, custody_record = _load_json(custody_path, label="jno_custody")
    if type(probe) is not dict or type(custody_record) is not dict:
        raise CustodyRefused("jno_r2_receipt_identity")
    identity = probe.get("declared_identity")
    if (
        probe.get("schema") != "carbon.development.jno-public-probe.v1"
        or custody_record.get("schema") != "carbon.development.jno-state-custody.v1"
        or probe.get("evidence") != "SYNTHETIC_DEVELOPMENT_ONLY"
        or probe.get("identity_verification") != "PRODUCT_HOST_RECEIPT_REQUIRED"
        or custody_record.get("identity_verification")
        != "PRODUCT_HOST_RECEIPT_REQUIRED"
        or type(identity) is not dict
        or identity != custody_record.get("declared_identity")
        or type(probe.get("recipe")) is not dict
        or probe.get("seed") != custody_record.get("seed")
        or probe.get("seed") != 11
    ):
        raise CustodyRefused("jno_r2_receipt_identity")

    fixture_path = _safe_file(artifact_root, "jno-fixture.npz")
    state_path = _safe_file(artifact_root, "jno-state.npz")
    fixture_bytes = _read_bounded(fixture_path, MAX_FIXTURE_BYTES, "fixture")
    state_bytes = _read_bounded(state_path, MAX_STATE_BYTES, "state")
    if (
        _sha(fixture_bytes) != probe.get("fixture_sha256")
        or len(fixture_bytes) != probe.get("fixture_bytes")
        or _sha(state_bytes) != probe.get("state_sha256")
        or _sha(state_bytes) != custody_record.get("state_sha256")
        or len(state_bytes) != probe.get("state_bytes")
        or len(state_bytes) != custody_record.get("state_bytes")
    ):
        raise CustodyRefused("jno_r2_artifact_digest")
    fixture_observed = inspect_numeric_npz(fixture_bytes, max_bytes=MAX_FIXTURE_BYTES)
    state_observed = inspect_numeric_npz(state_bytes, max_bytes=MAX_STATE_BYTES)
    if (
        set(fixture_observed) != {"x", "y", "prediction"}
        or set(state_observed) != {f"leaf_{index:04d}" for index in range(6)}
        or len(state_observed) != probe.get("state_leaves")
        or len(state_observed) != custody_record.get("state_leaves")
        or fixture_observed["x"]["raw_sha256"] != probe.get("input_x_sha256")
        or fixture_observed["y"]["raw_sha256"] != probe.get("input_y_sha256")
        or fixture_observed["prediction"]["raw_sha256"]
        != probe.get("prediction_sha256")
        or fixture_observed["prediction"]["shape"] != probe.get("prediction_shape")
        or probe.get("roundtrip_prediction_sha256") != probe.get("prediction_sha256")
        or [16, 1] != probe.get("prediction_shape")
    ):
        raise CustodyRefused("jno_r2_npz_descriptor")

    inputs = {
        key: {
            "dtype": fixture_observed[key]["dtype"],
            "shape": fixture_observed[key]["shape"],
        }
        for key in ("x", "y")
    }
    outputs = {
        "prediction": {
            "dtype": fixture_observed["prediction"]["dtype"],
            "shape": fixture_observed["prediction"]["shape"],
        }
    }
    state_arrays = {
        key: {"dtype": value["dtype"], "shape": value["shape"]}
        for key, value in state_observed.items()
    }
    descriptor = {
        "schema": FIXTURE_SCHEMA,
        "file": fixture_path.name,
        "prediction_file": fixture_path.name,
        "prediction_array": "prediction",
        "inputs": inputs,
        "outputs": outputs,
        "state_arrays": state_arrays,
        "expected_prediction": {
            "array": "prediction",
            "encoding": "C_CONTIGUOUS_RAW_V1",
            "sha256": fixture_observed["prediction"]["raw_sha256"],
            "file_digest": _sha(fixture_bytes),
        },
    }
    recipe_bytes = json.dumps(
        probe["recipe"], sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    source_digest = identity.get("source_sha256")
    bundle_digest = identity.get("bundle_digest")
    environment_digest = identity.get("environment_digest")
    image_digest = identity.get("image_id")
    manifest = {
        "schema": SCHEMA,
        "mode": MODE,
        "legacy_binding": LEGACY_BINDING,
        "challenge": None,
        "challenge_version": None,
        "interface_digest": None,
        "interface_authority_verified": False,
        "serving_verified": False,
        "official_eligible": False,
        "stage": "STATE_REPLAY",
        "state_codec": CODEC,
        "fixture": {
            **descriptor,
            "file_digest": _sha(fixture_bytes),
            "descriptor_digest": _sha(
                json.dumps(
                    descriptor, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ),
        },
        "state": {
            "file": state_path.name,
            "file_digest": _sha(state_bytes),
            "arrays": state_arrays,
        },
        "recipe": {
            "constructor_module": "jno",
            "constructor_name": "nn",
            "recipe_digest": _sha(recipe_bytes),
        },
        "lineage": {
            "source_digest": source_digest,
            "bundle_digest": bundle_digest,
            "environment_digest": environment_digest,
            "image_digest": image_digest,
            "producer_receipt_digest": _sha(custody_bytes),
        },
        "producer_prediction": {
            "file": fixture_path.name,
            "array": "prediction",
            "encoding": "C_CONTIGUOUS_RAW_V1",
            "file_digest": _sha(fixture_bytes),
            "raw_sha256": fixture_observed["prediction"]["raw_sha256"],
        },
        "receiver_ack": {
            "state": "PENDING",
            "receipt_file": None,
            "receipt_digest": None,
        },
    }
    _validate_manifest(manifest)
    for key, value in manifest["lineage"].items():
        _digest(value, "lineage_" + key)
    return manifest


def _role_array_map(value, *, label: str, allow_empty: bool):
    if type(value) is not dict:
        raise CustodyRefused(f"{label}_arrays")
    if not value and allow_empty:
        return {}
    return _array_map(
        value,
        label=label,
        max_arrays=MAX_MEMBER_COUNT,
        max_bytes=MAX_FIXTURE_BYTES,
    )


def _validate_v2_manifest(manifest):
    """Validate the prospective role-aware schema without changing v1 rules."""
    _exact_keys(
        manifest,
        {
            "schema",
            "mode",
            "legacy_binding",
            "challenge",
            "challenge_version",
            "interface_digest",
            "interface_authority_verified",
            "serving_verified",
            "official_eligible",
            "stage",
            "state_codec",
            "fixture",
            "state",
            "recipe",
            "lineage",
            "producer_prediction",
            "receiver_ack",
        },
        "manifest_v2",
    )
    if (
        manifest["schema"] != SCHEMA_V2
        or manifest["mode"] != MODE
        or manifest["legacy_binding"] != LEGACY_BINDING
        or manifest["challenge"] is not None
        or manifest["challenge_version"] is not None
        or manifest["interface_digest"] is not None
        or manifest["interface_authority_verified"] is not False
        or manifest["serving_verified"] is not False
        or manifest["official_eligible"] is not False
        or manifest["stage"] != "STATE_REPLAY"
        or manifest["state_codec"] != CODEC
    ):
        raise CustodyRefused("unbound_scope_v2")

    fixture = manifest["fixture"]
    _exact_keys(
        fixture,
        {
            "schema",
            "file",
            "model_inputs",
            "training_targets",
            "original_predictions",
            "auxiliary_artifacts",
            "file_digest",
            "descriptor_digest",
        },
        "fixture_v2",
    )
    if (
        fixture["schema"] != FIXTURE_SCHEMA_V2
        or type(fixture["file"]) is not str
        or not _FILE.fullmatch(fixture["file"])
    ):
        raise CustodyRefused("fixture_identity_v2")
    _digest(fixture["file_digest"], "fixture_file_v2")
    _digest(fixture["descriptor_digest"], "fixture_descriptor_v2")

    model_inputs = _role_array_map(
        fixture["model_inputs"], label="fixture_model_input_v2", allow_empty=False
    )
    training_targets = _role_array_map(
        fixture["training_targets"],
        label="fixture_training_target_v2",
        allow_empty=True,
    )
    original_predictions = _role_array_map(
        fixture["original_predictions"],
        label="fixture_original_prediction_v2",
        allow_empty=False,
    )
    role_names = [set(model_inputs), set(training_targets), set(original_predictions)]
    if any(
        role_names[left] & role_names[right]
        for left in range(3)
        for right in range(left + 1, 3)
    ):
        raise CustodyRefused("fixture_array_role_overlap_v2")

    auxiliary = fixture["auxiliary_artifacts"]
    if type(auxiliary) is not list or len(auxiliary) > MAX_AUXILIARY_ARTIFACTS:
        raise CustodyRefused("auxiliary_artifact_count_v2")
    auxiliary_by_file = {}
    auxiliary_roles = set()
    auxiliary_total_limit = 0
    for item in auxiliary:
        _exact_keys(
            item,
            {"file", "role", "media_type", "max_bytes", "file_digest"},
            "auxiliary_artifact_v2",
        )
        name = item["file"]
        role = item["role"]
        limit = item["max_bytes"]
        if (
            type(name) is not str
            or not _JSON_FILE.fullmatch(name)
            or name in auxiliary_by_file
            or name == fixture["file"]
            or type(role) is not str
            or not _AUX_ROLE.fullmatch(role)
            or role in auxiliary_roles
            or item["media_type"] != "application/json"
            or type(limit) is not int
            or not 1 <= limit <= MAX_AUXILIARY_JSON_BYTES
        ):
            raise CustodyRefused("auxiliary_artifact_descriptor_v2")
        _digest(item["file_digest"], "auxiliary_artifact_file_v2")
        auxiliary_total_limit += limit
        if auxiliary_total_limit > MAX_AUXILIARY_TOTAL_BYTES:
            raise CustodyRefused("auxiliary_artifact_total_size_v2")
        auxiliary_by_file[name] = item
        auxiliary_roles.add(role)

    state = manifest["state"]
    _exact_keys(state, {"file", "file_digest", "arrays"}, "state_v2")
    if (
        type(state["file"]) is not str
        or not _FILE.fullmatch(state["file"])
        or state["file"] == fixture["file"]
    ):
        raise CustodyRefused("replay_state_required_v2")
    _digest(state["file_digest"], "state_file_v2")
    state_arrays = _array_map(
        state["arrays"],
        label="state_v2",
        max_arrays=MAX_V2_STATE_MEMBER_COUNT,
        max_bytes=MAX_STATE_BYTES,
    )

    lineage = manifest["lineage"]
    _exact_keys(lineage, {"source", "bundle", "environment", "image"}, "lineage_v2")
    for label, item in lineage.items():
        _exact_keys(
            item,
            {"digest", "proof_kind", "evidence_file"},
            f"lineage_{label}_v2",
        )
        _digest(item["digest"], f"lineage_{label}_v2")
        if (
            type(item["proof_kind"]) is not str
            or item["proof_kind"] not in _PROOF_AUX_ROLE
            or type(item["evidence_file"]) is not str
            or not _JSON_FILE.fullmatch(item["evidence_file"])
            or item["evidence_file"] not in auxiliary_by_file
            or auxiliary_by_file[item["evidence_file"]]["role"]
            != _PROOF_AUX_ROLE[item["proof_kind"]]
        ):
            raise CustodyRefused(f"lineage_evidence_v2_{label}")

    recipe = manifest["recipe"]
    _exact_keys(
        recipe,
        {"constructor_module", "constructor_name", "recipe_digest"},
        "recipe_v2",
    )
    if any(
        type(recipe[key]) is not str or not _IDENT.fullmatch(recipe[key])
        for key in ("constructor_module", "constructor_name")
    ):
        raise CustodyRefused("recipe_identifier_v2")
    _digest(recipe["recipe_digest"], "recipe_v2")

    prediction = manifest["producer_prediction"]
    _exact_keys(
        prediction,
        {"file", "encoding", "file_digest", "arrays"},
        "producer_prediction_v2",
    )
    if (
        type(prediction["file"]) is not str
        or not _FILE.fullmatch(prediction["file"])
        or prediction["encoding"] != "C_CONTIGUOUS_RAW_V1"
    ):
        raise CustodyRefused("producer_prediction_identity_v2")
    _digest(prediction["file_digest"], "producer_prediction_file_v2")
    prediction_hashes = prediction["arrays"]
    if type(prediction_hashes) is not dict or set(prediction_hashes) != set(
        original_predictions
    ):
        raise CustodyRefused("producer_prediction_arrays_v2")
    for name, digest in prediction_hashes.items():
        _digest(digest, f"producer_prediction_{name}_v2")
    separate_prediction = prediction["file"] != fixture["file"]
    if separate_prediction and prediction["file"] == state["file"]:
        raise CustodyRefused("producer_prediction_state_collision_v2")
    if separate_prediction and prediction["file"] in auxiliary_by_file:
        raise CustodyRefused("producer_prediction_auxiliary_collision_v2")

    ack = manifest["receiver_ack"]
    _exact_keys(ack, {"state", "receipt_file", "receipt_digest"}, "ack_v2")
    if ack != {"state": "PENDING", "receipt_file": None, "receipt_digest": None}:
        raise CustodyRefused("receiver_ack_must_remain_pending_v2")

    return (
        model_inputs,
        training_targets,
        original_predictions,
        state_arrays,
        auxiliary_by_file,
    )


def prepare_custody_v2(artifact_root: Path, manifest: dict) -> dict:
    """Byte-bind a role-aware public R2 artifact set; never runs a model or receiver."""
    artifact_root = _artifact_root(artifact_root)
    (
        model_inputs,
        training_targets,
        original_predictions,
        state_arrays,
        auxiliary,
    ) = _validate_v2_manifest(manifest)
    fixture = manifest["fixture"]
    prediction = manifest["producer_prediction"]
    fixture_path = _safe_file(artifact_root, fixture["file"])
    fixture_bytes = _read_bounded(fixture_path, MAX_FIXTURE_BYTES, "fixture_v2")
    if _sha(fixture_bytes) != fixture["file_digest"]:
        raise CustodyRefused("fixture_file_digest_v2")
    descriptor = {
        key: fixture[key]
        for key in (
            "schema",
            "file",
            "model_inputs",
            "training_targets",
            "original_predictions",
            "auxiliary_artifacts",
        )
    }
    descriptor_digest = _sha(
        json.dumps(
            descriptor, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    if descriptor_digest != fixture["descriptor_digest"]:
        raise CustodyRefused("fixture_descriptor_digest_v2")
    fixture_roles = model_inputs | training_targets
    if prediction["file"] == fixture["file"]:
        fixture_roles |= original_predictions
    observed_fixture = validate_numeric_npz(
        fixture_bytes, fixture_roles, max_bytes=MAX_FIXTURE_BYTES
    )
    if prediction["file"] == fixture["file"]:
        prediction_observed = observed_fixture
        if prediction["file_digest"] != fixture["file_digest"]:
            raise CustodyRefused("producer_prediction_fixture_file_digest_v2")
    else:
        prediction_path = _safe_file(artifact_root, prediction["file"])
        prediction_bytes = _read_bounded(
            prediction_path, MAX_FIXTURE_BYTES, "producer_prediction_v2"
        )
        if _sha(prediction_bytes) != prediction["file_digest"]:
            raise CustodyRefused("producer_prediction_file_digest_v2")
        prediction_observed = validate_numeric_npz(
            prediction_bytes, original_predictions, max_bytes=MAX_FIXTURE_BYTES
        )
    if any(
        prediction_observed[name] != digest
        for name, digest in prediction["arrays"].items()
    ):
        raise CustodyRefused("producer_prediction_raw_digest_v2")

    state = manifest["state"]
    state_path = _safe_file(artifact_root, state["file"])
    state_bytes = _read_bounded(state_path, MAX_STATE_BYTES, "state_v2")
    if _sha(state_bytes) != state["file_digest"]:
        raise CustodyRefused("state_file_digest_v2")
    validate_numeric_npz(
        state_bytes,
        state_arrays,
        max_bytes=MAX_STATE_BYTES,
        max_member_count=MAX_V2_STATE_MEMBER_COUNT,
    )

    observed_auxiliary = []
    for item in manifest["fixture"]["auxiliary_artifacts"]:
        path = _safe_file(artifact_root, item["file"], json_file=True)
        raw = _read_bounded(path, item["max_bytes"], "auxiliary_artifact_v2")
        if _sha(raw) != item["file_digest"]:
            raise CustodyRefused("auxiliary_artifact_digest_v2")
        observed_auxiliary.append(
            {
                "file": item["file"],
                "role": item["role"],
                "media_type": item["media_type"],
                "bytes": len(raw),
                "sha256": _sha(raw),
            }
        )

    receipt = {
        "schema": "carbon.scorelab.public-unbound-custody-receipt.v2",
        "mode": MODE,
        "legacy_binding": LEGACY_BINDING,
        "challenge": None,
        "challenge_version": None,
        "declared_interface_digest": None,
        "interface_authority_verified": False,
        "serving_verified": False,
        "official_eligible": False,
        "stage": "STATE_REPLAY",
        "state_codec": CODEC,
        "fixture_file_digest": fixture["file_digest"],
        "fixture_descriptor_digest": fixture["descriptor_digest"],
        "fixture_array_roles": {
            "model_inputs": sorted(model_inputs),
            "training_targets": sorted(training_targets),
            "original_predictions": sorted(original_predictions),
        },
        "auxiliary_artifacts": observed_auxiliary,
        "native_state_digest": _sha(state_bytes),
        "producer_prediction_raw_sha256": dict(prediction["arrays"]),
        "recipe_digest": manifest["recipe"]["recipe_digest"],
        "identity_evidence": {
            name: {
                **item,
                "evidence_file_digest": auxiliary[item["evidence_file"]]["file_digest"],
                "verification": "DIGEST_BOUND_UNVERIFIED",
            }
            for name, item in manifest["lineage"].items()
        },
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "producer_identity_verification": "PRODUCT_HOST_RECEIPT_REQUIRED",
        "identity_authenticity": "NOT_VERIFIED_BY_THIS_TOOL",
        "lineage_assertion_status": "EVIDENCE_BYTES_BOUND_NOT_AUTHENTICATED",
        "replay_state": "PENDING_EXTERNAL_RECEIVER",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "receiver_ack_authenticity": "NOT_VERIFIED_BY_THIS_TOOL",
    }
    if prediction["file"] != fixture["file"]:
        receipt["producer_prediction_separate_file"] = {
            "file": prediction["file"],
            "file_digest": prediction["file_digest"],
        }
    return receipt


# V3 is a prospective data-only extension of this custody family. Unlike the
# historical unbound formats above, it preserves a producer's real Challenge
# identity. It does not execute the graph or authenticate producer declarations.
GRAPH_CUSTODY_SCHEMA_V3 = "carbon.scorelab.public-model-custody-receipt.v3"
GRAPH_LINEAGE_SCHEMA = "carbon.battery.direct-graph-local-evidence.v1"
GRAPH_SCOPE = "PUBLIC_DEVELOPMENT_LOCAL_C03"
GRAPH_HTTP_SCOPE = "PUBLIC_DEVELOPMENT_LOCAL_C03_NORMAL_LAUNCHPAD_HTTP"
MAX_GRAPH_FILES = 128
MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024
MAX_GRAPH_TOTAL_BYTES = 768 * 1024 * 1024
_GRAPH_PATH_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_GRAPH_REQUIRED = frozenset(
    {
        "carrier-receipt.json",
        "image-identity.json",
        "inference-receipt.json",
        "source-envelope.json",
        "stage/recipe.json",
        "stage/train-v1.jsonl.gz",
        "stage/test-inputs.json",
        "output/fit.json",
        "output/predictions.json",
        "output/state.npz",
        "inference/stage/state.npz",
        "inference/output/predictions.json",
        "inference/output/receipt.json",
    }
)


def _graph_file(root: Path, name: str) -> Path:
    if (
        type(name) is not str
        or len(name) > 384
        or not 1 <= len(name.split("/")) <= 4
        or any(
            part in {".", ".."} or not _GRAPH_PATH_PART.fullmatch(part)
            for part in name.split("/")
        )
    ):
        raise CustodyRefused("graph_path")
    path = root
    for part in name.split("/"):
        path = path / part
        if path.is_symlink():
            raise CustodyRefused("graph_symlink")
    if not path.is_file() or path.resolve() != path.absolute():
        raise CustodyRefused("graph_file")
    return path


def _graph_json(raw: bytes, label: str) -> dict:
    def refuse_constant(_value):
        raise ValueError("nonfinite JSON constant")

    def finite_float(raw_value):
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON float")
        return value

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=refuse_constant,
            parse_float=finite_float,
            object_pairs_hook=unique_pairs,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CustodyRefused(f"graph_{label}_json") from exc
    if type(value) is not dict:
        raise CustodyRefused(f"graph_{label}_object")
    return value


def _graph_digest_equal(value, expected, label):
    _digest(value, label)
    if value != expected:
        raise CustodyRefused(f"graph_{label}_mismatch")


def _graph_rehash_inventory(
    root: Path, files: dict, required: frozenset, *, lineage_name="lineage.json"
):
    """Share the rooted original-byte inventory checks across custody versions."""
    if (
        type(files) is not dict
        or not required <= set(files)
        or not len(required) <= len(files) <= MAX_GRAPH_FILES
        or (lineage_name is not None and lineage_name in files)
    ):
        raise CustodyRefused("graph_retained_files")
    observed = {}
    raw = {}
    total = 0
    for name, declared in sorted(files.items()):
        _digest(declared, "graph_retained")
        file_limit = (
            4 * 1024 * 1024
            if name.endswith((".json", ".py"))
            else 128 * 1024 * 1024 if name.endswith(".gz") else MAX_GRAPH_FILE_BYTES
        )
        body = _read_bounded(_graph_file(root, name), file_limit, "graph_artifact")
        total += len(body)
        if total > MAX_GRAPH_TOTAL_BYTES or _sha(body) != declared:
            raise CustodyRefused("graph_retained_digest_or_size")
        observed[name] = {"sha256": declared, "bytes": len(body)}
        if name in required:
            raw[name] = body
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != set(files) | ({lineage_name} if lineage_name is not None else set()):
        raise CustodyRefused("graph_undeclared_or_missing_file")
    return observed, raw


def prepare_custody_v3(artifact_root: Path) -> dict:
    """Bind original Challenge-bound public graph bytes; never replay or admit."""
    root = _artifact_root(artifact_root)
    lineage_raw = _read_bounded(
        _graph_file(root, "lineage.json"), MAX_MANIFEST_BYTES, "graph_lineage"
    )
    lineage = _graph_json(lineage_raw, "lineage")
    _exact_keys(
        lineage,
        {
            "schema",
            "scope",
            "graph_digest",
            "image_id",
            "operation",
            "inference_operation",
            "recipe_digest",
            "state_digest",
            "train_digest",
            "inference_predictions_digest",
            "retained_files",
        },
        "graph_lineage",
    )
    if lineage["schema"] != GRAPH_LINEAGE_SCHEMA or lineage["scope"] != GRAPH_SCOPE:
        raise CustodyRefused("graph_scope")
    for field in (
        "graph_digest",
        "image_id",
        "recipe_digest",
        "state_digest",
        "train_digest",
        "inference_predictions_digest",
    ):
        _digest(lineage[field], f"graph_{field}")
    for field in ("operation", "inference_operation"):
        if type(lineage[field]) is not str or not re.fullmatch(
            r"operation-[0-9a-f]{64}", lineage[field]
        ):
            raise CustodyRefused(f"graph_{field}")
    files = lineage["retained_files"]
    observed, raw = _graph_rehash_inventory(root, files, _GRAPH_REQUIRED)

    recipe = _graph_json(raw["stage/recipe.json"], "recipe")
    if recipe.get("schema") != "carbon.construction-recipe.v1":
        raise CustodyRefused("graph_recipe_schema")
    challenge = recipe.get("challenge")
    if (
        type(challenge) is not dict
        or set(challenge)
        != {
            "id",
            "version",
            "interface_digest",
            "train_digest",
            "construction_limits_digest",
        }
        or type(challenge["id"]) is not str
        or not challenge["id"]
        or type(challenge["version"]) is not str
        or not challenge["version"]
        or recipe.get("source")
        != {"kind": "graph", "submission_digest": lineage["graph_digest"]}
    ):
        raise CustodyRefused("graph_challenge_or_source")
    _graph_digest_equal(
        challenge["train_digest"], lineage["train_digest"], "train_identity"
    )
    _digest(challenge["interface_digest"], "graph_interface")
    _digest(challenge["construction_limits_digest"], "graph_limits")
    if _sha(raw["stage/recipe.json"]) != lineage["recipe_digest"]:
        raise CustodyRefused("graph_recipe_digest")
    if _sha(raw["stage/train-v1.jsonl.gz"]) != lineage["train_digest"]:
        raise CustodyRefused("graph_train_bytes")
    envelope = _graph_json(raw["source-envelope.json"], "source_envelope")
    if (
        envelope.get("schema") != "carbon.level4.staging-bundle.v1"
        or envelope.get("submission") != lineage["graph_digest"]
    ):
        raise CustodyRefused("graph_source_envelope")

    fit = _graph_json(raw["output/fit.json"], "fit")
    for key, expected in (
        ("graph_digest", lineage["graph_digest"]),
        ("interface_digest", challenge["interface_digest"]),
        ("recipe_digest", lineage["recipe_digest"]),
        ("state_sha256", lineage["state_digest"]),
        ("train_digest", lineage["train_digest"]),
    ):
        _graph_digest_equal(fit.get(key), expected, f"fit_{key}")
    for state_file in ("output/state.npz", "inference/stage/state.npz"):
        if _sha(raw[state_file]) != lineage["state_digest"]:
            raise CustodyRefused("graph_state_digest")
        state_arrays = inspect_numeric_npz(
            raw[state_file],
            max_bytes=MAX_STATE_BYTES,
            max_member_count=MAX_V2_STATE_MEMBER_COUNT,
            allow_graph_header=True,
        )
        if (
            state_arrays.get("__header__", {}).get("dtype") != "uint8"
            or len(state_arrays["__header__"]["shape"]) != 1
        ):
            raise CustodyRefused("graph_state_header")
    predictions = _graph_json(raw["output/predictions.json"], "predictions")
    inputs = _graph_json(raw["stage/test-inputs.json"], "inputs")
    cases = inputs.get("cases")
    if (
        type(cases) is not list
        or not cases
        or any(
            type(case) is not dict or set(case) != {"case_id", "inputs"}
            for case in cases
        )
        or any(type(case["case_id"]) is not str for case in cases)
        or len({case["case_id"] for case in cases}) != len(cases)
        or set(predictions) != {case["case_id"] for case in cases}
    ):
        raise CustodyRefused("graph_original_case_binding")
    if raw["output/predictions.json"] != raw["inference/output/predictions.json"]:
        raise CustodyRefused("graph_prediction_copy")
    _graph_digest_equal(
        _sha(raw["output/predictions.json"]),
        lineage["inference_predictions_digest"],
        "prediction_bytes",
    )
    inference = _graph_json(raw["inference/output/receipt.json"], "inference")
    if inference.get("schema") != "carbon.battery.direct-graph-inference.v1":
        raise CustodyRefused("graph_inference_schema")
    for key, expected in (
        ("state_digest", lineage["state_digest"]),
        ("recipe_digest", lineage["recipe_digest"]),
        ("predictions_digest", lineage["inference_predictions_digest"]),
        ("inputs_digest", _sha(raw["stage/test-inputs.json"])),
    ):
        _graph_digest_equal(inference.get(key), expected, f"inference_{key}")
    image = _graph_json(raw["image-identity.json"], "image")
    if image.get("schema") != "carbon.c03.worker-image.v1":
        raise CustodyRefused("graph_image_schema")
    _graph_digest_equal(image.get("image_id"), lineage["image_id"], "image_id")

    for name, operation, expected_files, provenance in (
        (
            "carrier-receipt.json",
            lineage["operation"],
            {
                "fit.json": "output/fit.json",
                "predictions.json": "output/predictions.json",
                "state.npz": "output/state.npz",
            },
            "BATTERY_DIRECT_GRAPH_PUBLIC_RECONSTRUCTION",
        ),
        (
            "inference-receipt.json",
            lineage["inference_operation"],
            {
                "predictions.json": "inference/output/predictions.json",
                "receipt.json": "inference/output/receipt.json",
            },
            "BATTERY_DIRECT_GRAPH_PUBLIC_INFERENCE",
        ),
    ):
        carrier = _graph_json(raw[name], "carrier")
        reported = carrier.get("files")
        if (
            type(reported) is not dict
            or any(type(short) is not str for short in reported)
            or any(type(digest) is not str for digest in reported.values())
        ):
            raise CustodyRefused("graph_carrier_files")
        if (
            carrier.get("schema") != "carbon.autoresearch.worker-result.v1"
            or carrier.get("official_eligible") is not False
            or carrier.get("scientific_qualification") is not False
            or carrier.get("operation") != operation
            or carrier.get("provenance") != provenance
            or reported
            != {short: files[path] for short, path in expected_files.items()}
        ):
            raise CustodyRefused("graph_carrier_receipt")
    return {
        "schema": GRAPH_CUSTODY_SCHEMA_V3,
        "source_schema": GRAPH_LINEAGE_SCHEMA,
        "scope": GRAPH_SCOPE,
        "challenge": challenge["id"],
        "challenge_version": challenge["version"],
        "interface_digest": challenge["interface_digest"],
        "train_digest": challenge["train_digest"],
        "source_digest": lineage["graph_digest"],
        "recipe_digest": lineage["recipe_digest"],
        "image_digest": lineage["image_id"],
        "state_digest": lineage["state_digest"],
        "prediction_digest": lineage["inference_predictions_digest"],
        "operations": [lineage["operation"], lineage["inference_operation"]],
        "lineage_sha256": _sha(lineage_raw),
        "original_files": observed,
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "replay_state": "PRODUCER_INFERENCE_BOUND_RECEIVER_REPLAY_NOT_ATTEMPTED",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "identity_authenticity": "DIGEST_BOUND_UNVERIFIED",
        "official_eligible": False,
    }


GRAPH_ROLE_SCHEMA_V1 = "carbon.scorelab.public-model-artifact-roles.v1"
GRAPH_CUSTODY_SCHEMA_V4 = "carbon.scorelab.public-model-custody-receipt.v4"
_GRAPH_ROLE_CODECS = {
    "recipe": "json",
    "train": "raw_bytes",
    "source": "json",
    "image": "json",
    "state": "numeric_npz",
    "inputs": "json",
    "predictions": "json",
    "fit": "json",
    "inference_state": "numeric_npz",
    "inference_predictions": "json",
    "inference_receipt": "json",
    "selected_recipe": "json",
    "feedback": "json",
}
_GRAPH_CORE_ROLES = frozenset(
    {"recipe", "train", "source", "image", "state", "inputs", "predictions"}
)


def prepare_custody_v4(artifact_root: Path, role_manifest_path: Path) -> dict:
    """Rehash original public graph bytes through finite declared artifact roles.

    Optional producer evidence is validated when present. Absence remains
    explicit and never becomes replay, admission, a score, or receiver ACK.
    """
    root = _artifact_root(artifact_root)
    manifest_path = Path(role_manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise CustodyRefused("graph_role_manifest_file")
    manifest_raw = _read_bounded(
        manifest_path, MAX_MANIFEST_BYTES, "graph_role_manifest"
    )
    manifest = _graph_json(manifest_raw, "role_manifest")
    _exact_keys(manifest, {"schema", "source_schema", "scope", "roles"}, "graph_roles")
    if manifest["schema"] != GRAPH_ROLE_SCHEMA_V1:
        raise CustodyRefused("graph_role_schema")
    roles = manifest["roles"]
    if (
        type(roles) is not dict
        or not _GRAPH_CORE_ROLES <= set(roles) <= set(_GRAPH_ROLE_CODECS)
        or len(roles) > len(_GRAPH_ROLE_CODECS)
    ):
        raise CustodyRefused("graph_roles")
    role_paths = {}
    for role, declaration in roles.items():
        _exact_keys(declaration, {"file", "codec"}, f"graph_role_{role}")
        if declaration["codec"] != _GRAPH_ROLE_CODECS[role]:
            raise CustodyRefused("graph_role_codec")
        _graph_file(root, declaration["file"])
        role_paths[role] = declaration["file"]
    if len(set(role_paths.values())) != len(role_paths):
        raise CustodyRefused("graph_role_duplicate_file")

    lineage_raw = _read_bounded(
        _graph_file(root, "lineage.json"), MAX_MANIFEST_BYTES, "graph_lineage"
    )
    lineage = _graph_json(lineage_raw, "lineage")
    if (
        lineage.get("schema") != GRAPH_LINEAGE_SCHEMA
        or lineage.get("scope") != GRAPH_HTTP_SCOPE
        or manifest["source_schema"] != lineage["schema"]
        or manifest["scope"] != lineage["scope"]
        or lineage.get("official_eligible") is not False
    ):
        raise CustodyRefused("graph_role_scope")
    for field in (
        "graph_digest",
        "image_id",
        "recipe_digest",
        "state_digest",
        "train_digest",
    ):
        _digest(lineage.get(field), f"graph_{field}")
    if "inference_predictions_digest" in lineage:
        _digest(lineage["inference_predictions_digest"], "graph_inference_predictions")
    if "feedback_digest" in lineage:
        _digest(lineage["feedback_digest"], "graph_feedback")
    for field in ("build_operation", "inference_operation"):
        if field in lineage and (
            type(lineage[field]) is not str
            or not re.fullmatch(r"operation-[0-9a-f]{64}", lineage[field])
        ):
            raise CustodyRefused(f"graph_{field}")
    if "campaign_id" in lineage and (
        type(lineage["campaign_id"]) is not str
        or not re.fullmatch(r"[0-9a-f]{32}", lineage["campaign_id"])
    ):
        raise CustodyRefused("graph_campaign_id")
    if "task_id" in lineage and (
        type(lineage["task_id"]) is not str
        or not re.fullmatch(r"rtsk_[0-9a-f]{64}", lineage["task_id"])
    ):
        raise CustodyRefused("graph_task_id")
    required = frozenset(role_paths.values())
    observed, raw = _graph_rehash_inventory(
        root, lineage.get("retained_files"), required
    )
    by_role = {role: raw[path] for role, path in role_paths.items()}
    decoded = {
        role: _graph_json(body, role)
        for role, body in by_role.items()
        if _GRAPH_ROLE_CODECS[role] == "json"
    }
    recipe = decoded["recipe"]
    challenge = recipe.get("challenge")
    if (
        recipe.get("schema") != "carbon.construction-recipe.v1"
        or type(challenge) is not dict
        or set(challenge)
        != {
            "id",
            "version",
            "interface_digest",
            "train_digest",
            "construction_limits_digest",
        }
        or type(challenge["id"]) is not str
        or not challenge["id"]
        or type(challenge["version"]) is not str
        or not challenge["version"]
        or recipe.get("source")
        != {"kind": "graph", "submission_digest": lineage["graph_digest"]}
        or decoded["source"].get("schema") != "carbon.level4.staging-bundle.v1"
        or decoded["source"].get("submission") != lineage["graph_digest"]
        or decoded["image"].get("schema") != "carbon.c03.worker-image.v1"
        or decoded["image"].get("image_id") != lineage["image_id"]
    ):
        raise CustodyRefused("graph_role_identity")
    _digest(challenge["interface_digest"], "graph_interface")
    _digest(challenge["construction_limits_digest"], "graph_limits")
    for body, expected, label in (
        (by_role["recipe"], lineage["recipe_digest"], "recipe"),
        (by_role["train"], lineage["train_digest"], "train"),
        (by_role["state"], lineage["state_digest"], "state"),
    ):
        _graph_digest_equal(_sha(body), expected, label)
    _graph_digest_equal(
        challenge["train_digest"], lineage["train_digest"], "train_identity"
    )
    for role in ("state", "inference_state"):
        if role in by_role:
            _graph_digest_equal(_sha(by_role[role]), lineage["state_digest"], role)
            arrays = inspect_numeric_npz(
                by_role[role],
                max_bytes=MAX_STATE_BYTES,
                max_member_count=MAX_V2_STATE_MEMBER_COUNT,
                allow_graph_header=True,
            )
            if (
                arrays.get("__header__", {}).get("dtype") != "uint8"
                or len(arrays["__header__"]["shape"]) != 1
            ):
                raise CustodyRefused("graph_state_header")
    cases = decoded["inputs"].get("cases")
    predictions = decoded["predictions"]
    if (
        type(cases) is not list
        or not cases
        or any(
            type(case) is not dict or set(case) != {"case_id", "inputs"}
            for case in cases
        )
        or any(type(case["case_id"]) is not str for case in cases)
        or len({case["case_id"] for case in cases}) != len(cases)
        or set(predictions) != {case["case_id"] for case in cases}
    ):
        raise CustodyRefused("graph_role_cases")
    if "fit" in decoded:
        for key, expected in (
            ("graph_digest", lineage["graph_digest"]),
            ("interface_digest", challenge["interface_digest"]),
            ("recipe_digest", lineage["recipe_digest"]),
            ("state_sha256", lineage["state_digest"]),
            ("train_digest", lineage["train_digest"]),
        ):
            _graph_digest_equal(decoded["fit"].get(key), expected, f"fit_{key}")
    if "inference_predictions" in by_role:
        if by_role["inference_predictions"] != by_role["predictions"]:
            raise CustodyRefused("graph_role_prediction_copy")
        if "inference_predictions_digest" in lineage:
            _graph_digest_equal(
                _sha(by_role["inference_predictions"]),
                lineage["inference_predictions_digest"],
                "inference_predictions",
            )
    if "inference_receipt" in decoded:
        if not {"inference_state", "inference_predictions"} <= set(by_role):
            raise CustodyRefused("graph_inference_roles")
        receipt = decoded["inference_receipt"]
        if receipt.get("schema") != "carbon.battery.direct-graph-inference.v1":
            raise CustodyRefused("graph_inference_schema")
        for key, expected in (
            ("state_digest", lineage["state_digest"]),
            ("recipe_digest", lineage["recipe_digest"]),
            (
                "predictions_digest",
                _sha(by_role.get("inference_predictions", by_role["predictions"])),
            ),
            ("inputs_digest", _sha(by_role["inputs"])),
        ):
            _graph_digest_equal(receipt.get(key), expected, f"inference_{key}")
    if "selected_recipe" in decoded:
        selected = decoded["selected_recipe"]
        if (
            selected.get("schema") != "carbon.direct-selected-recipe.v1"
            or selected.get("status") != "SELECTED"
            or selected.get("final_evidence") is not False
            or selected.get("used_feedback") is not False
            or selected.get("strategy") != recipe
            or selected.get("strategy_hash") != lineage["recipe_digest"]
            or selected.get("construction_recipe_digest") != lineage["recipe_digest"]
            or selected.get("construction_source_digest") != lineage["graph_digest"]
            or selected.get("source_envelope_digest")
            != observed[role_paths["source"]]["sha256"]
            or selected.get("interface_digest") != challenge["interface_digest"]
            or selected.get("construction_limits_digest")
            != challenge["construction_limits_digest"]
            or selected.get("train_digest") != lineage["train_digest"]
        ):
            raise CustodyRefused("graph_selection")
    if "feedback_digest" in lineage and "feedback" not in decoded:
        raise CustodyRefused("graph_feedback_missing")
    if "feedback" in decoded:
        feedback = decoded["feedback"]
        if "feedback_digest" in lineage:
            _graph_digest_equal(
                _sha(by_role["feedback"]), lineage["feedback_digest"], "feedback"
            )
        worker = feedback.get("worker")
        if (
            feedback.get("schema") != "carbon.battery.direct-practice-feedback.v1"
            or feedback.get("provenance") != "BATTERY_PUBLIC_PRACTICE"
            or feedback.get("official_eligible") is not False
            or feedback.get("scientific_qualification") is not False
            or feedback.get("final_exam") is not False
            or feedback.get("challenge") != challenge
            or feedback.get("recipe") != recipe
            or feedback.get("source") != recipe["source"]
            or feedback.get("recipe_digest") != lineage["recipe_digest"]
            or feedback.get("backend")
            != {"image": lineage["image_id"], "kind": "ISOLATED_C03_DIRECT_GRAPH"}
            or type(feedback.get("model")) is not dict
            or feedback["model"].get("sha256") != lineage["state_digest"]
            or type(worker) is not dict
            or worker.get("state_sha256") != lineage["state_digest"]
            or worker.get("build_predictions_sha256") != _sha(by_role["predictions"])
            or worker.get("predictions_sha256")
            != _sha(by_role.get("inference_predictions", by_role["predictions"]))
            or worker.get("provenance") != "BATTERY_DIRECT_GRAPH_PUBLIC_RECONSTRUCTION"
            or (
                "build_operation" in lineage
                and worker.get("operation") != lineage["build_operation"]
            )
            or (
                "inference_operation" in lineage
                and worker.get("inference_operation") != lineage["inference_operation"]
            )
        ):
            raise CustodyRefused("graph_feedback")
    role_records = {
        role: {
            "file": path,
            "codec": roles[role]["codec"],
            "sha256": observed[path]["sha256"],
        }
        for role, path in sorted(role_paths.items())
    }
    return {
        "schema": GRAPH_CUSTODY_SCHEMA_V4,
        "source_schema": lineage["schema"],
        "scope": lineage["scope"],
        "challenge": challenge["id"],
        "challenge_version": challenge["version"],
        "interface_digest": challenge["interface_digest"],
        "train_digest": lineage["train_digest"],
        "source_digest": lineage["graph_digest"],
        "recipe_digest": lineage["recipe_digest"],
        "image_digest": lineage["image_id"],
        "state_digest": lineage["state_digest"],
        "prediction_digest": _sha(by_role["predictions"]),
        "role_manifest_sha256": _sha(manifest_raw),
        "roles": role_records,
        "lineage_sha256": _sha(lineage_raw),
        "original_files": observed,
        "campaign_id": lineage.get("campaign_id"),
        "task_id": lineage.get("task_id"),
        "operations": [
            lineage.get("build_operation"),
            lineage.get("inference_operation"),
        ],
        "evidence_state": {
            "build": (
                "FEEDBACK_BOUND"
                if {"feedback", "fit"} <= set(decoded)
                else "INCOMPLETE"
            ),
            "inference": (
                "RECEIPT_BOUND" if "inference_receipt" in decoded else "INCOMPLETE"
            ),
            "receiver_replay": "NOT_ATTEMPTED",
        },
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "replay_state": "PRODUCER_EVIDENCE_BOUND_RECEIVER_REPLAY_NOT_ATTEMPTED",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "identity_authenticity": "DIGEST_BOUND_UNVERIFIED",
        "official_eligible": False,
    }


BUNDLE_ROLE_SCHEMA_V2 = "carbon.scorelab.public-model-artifact-roles.v2"
GRAPH_ROLE_SCHEMA_V3 = "carbon.scorelab.public-model-artifact-roles.v3"
BUNDLE_CUSTODY_SCHEMA_V5 = "carbon.scorelab.public-model-custody-receipt.v5"
BUNDLE_STATE_SCHEMA = "carbon.development.bundle-graph-state.v1"
GRAPH_SOURCE_STATE_SCHEMA = "carbon.development.graph-source-state.v1"
BUNDLE_SCOPE = "PUBLIC_DEVELOPMENT_BUNDLE_MODEL"
_BUNDLE_ROLE_CODECS = {
    "recipe": "json",
    "train": "numeric_npz",
    "fixture": "numeric_npz",
    "state": "bundle_graph_npz",
    "predictions": "json",
    "source": "raw_bytes",
    "environment": "raw_bytes",
    "image": "json",
    "seed": "json",
    "inputs": "numeric_npz",
    "allowlist": "json",
    "build_receipt": "json",
    "inference_receipt": "json",
}
_BUNDLE_CORE_ROLES = frozenset(
    {
        "recipe",
        "train",
        "state",
        "source",
        "environment",
        "image",
    }
)
_GRAPH_ROLE_CODECS = {
    **{
        role: codec
        for role, codec in _BUNDLE_ROLE_CODECS.items()
        if role != "environment"
    },
    "source": "json",
    "construction_kit": "json",
    "worker_evidence": "json",
    "task_receipt": "raw_bytes",
}
_GRAPH_CORE_ROLES = frozenset(
    {
        "recipe",
        "construction_kit",
        "train",
        "state",
        "source",
        "image",
        "allowlist",
        "build_receipt",
        "worker_evidence",
        "inputs",
        "predictions",
        "inference_receipt",
    }
)


def _bundle_header(state: bytes, *, graph_source: bool = False) -> tuple[dict, dict]:
    """Inspect the producer's inert graph NPZ without loading or executing it."""
    arrays = inspect_numeric_npz(
        state,
        max_bytes=64 * 1024 * 1024,
        max_member_count=4098,
        max_directory_bytes=512 * 1024,
        allow_graph_header=True,
    )
    header_descriptor = arrays.get("__header__")
    graph_descriptor = arrays.get("graph")
    if (
        type(header_descriptor) is not dict
        or header_descriptor["dtype"] != "uint8"
        or len(header_descriptor["shape"]) != 1
        or header_descriptor["shape"][0] > 65536
        or type(graph_descriptor) is not dict
        or graph_descriptor["dtype"] != "uint8"
        or len(graph_descriptor["shape"]) != 1
        or graph_descriptor["shape"][0] > 1024 * 1024
    ):
        raise CustodyRefused("bundle_state_members")
    try:
        with zipfile.ZipFile(io.BytesIO(state)) as archive:
            with archive.open("__header__.npy") as stream:
                _npy_header(stream)
                header_raw = stream.read(65537)
            with archive.open("graph.npy") as stream:
                _npy_header(stream)
                graph_raw = stream.read(1024 * 1024 + 1)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise CustodyRefused("bundle_state_members") from exc
    if (
        len(header_raw) != header_descriptor["shape"][0]
        or len(graph_raw) != graph_descriptor["shape"][0]
    ):
        raise CustodyRefused("bundle_state_member_size")
    header = _graph_json(header_raw, "bundle_header")
    source_field = "submission_digest" if graph_source else "bundle_digest"
    source_schema = GRAPH_SOURCE_STATE_SCHEMA if graph_source else BUNDLE_STATE_SCHEMA
    if (
        set(header)
        != {
            "schema",
            "recipe_digest",
            source_field,
            "train_digest",
            "interface_digest",
            "graph_digest",
            "allowlist_digest",
            "parameter_count",
        }
        or header["schema"] != source_schema
        or type(header["parameter_count"]) is not int
        or not 0 <= header["parameter_count"] <= 4096
        or set(arrays)
        != {"__header__", "graph"}
        | {f"parameter{index:04d}" for index in range(header["parameter_count"])}
    ):
        raise CustodyRefused("bundle_state_header")
    for field in (
        "recipe_digest",
        source_field,
        "train_digest",
        "interface_digest",
        "graph_digest",
        "allowlist_digest",
    ):
        _digest(header[field], f"bundle_{field}")
    _graph_digest_equal(_sha(graph_raw), header["graph_digest"], "bundle_graph")
    return header, arrays


def _bundle_json(raw: bytes, label: str):
    def refuse_constant(_value):
        raise ValueError("nonfinite JSON constant")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON float")
        return parsed

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=refuse_constant,
            parse_float=finite_float,
            object_pairs_hook=unique_pairs,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CustodyRefused(f"bundle_{label}_json") from exc


def _graph_finite_number(value, *, nonnegative=False):
    if type(value) not in (int, float):
        return False
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(number) and (not nonnegative or number >= 0)


def _graph_positive_timing(values):
    if not all(_graph_finite_number(value, nonnegative=True) for value in values):
        return False
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(total) and total > 0


def _graph_prediction_shape(value, shape, dtype):
    if not shape:
        if not _graph_finite_number(value):
            return False
        if dtype.startswith(("int", "uint")):
            bits = int(dtype[4:] if dtype.startswith("uint") else dtype[3:])
            lower = 0 if dtype.startswith("uint") else -(1 << (bits - 1))
            upper = (
                (1 << bits) - 1 if dtype.startswith("uint") else (1 << (bits - 1)) - 1
            )
            return type(value) is int and lower <= value <= upper
        if dtype == "float16":
            return abs(value) <= 65504
        if dtype == "float32":
            return abs(value) <= 3.4028234663852886e38
        return True
    return (
        type(value) is list
        and len(value) == shape[0]
        and all(_graph_prediction_shape(item, shape[1:], dtype) for item in value)
    )


def _prepare_graph_custody_v5(root, manifest_raw, manifest):
    """Bind a measured direct graph without executing its source or state."""
    from carbon.level4 import staging
    from carbon.level4.graph import GraphRefused

    if manifest["source_schema"] != GRAPH_SOURCE_STATE_SCHEMA:
        raise CustodyRefused("graph_role_scope")
    roles = manifest["roles"]
    if type(roles) is not dict or not _GRAPH_CORE_ROLES <= set(roles) <= set(
        _GRAPH_ROLE_CODECS
    ):
        raise CustodyRefused("graph_roles")
    role_paths = {}
    for role, declaration in roles.items():
        _exact_keys(declaration, {"file", "codec"}, f"graph_role_{role}")
        if declaration["codec"] != _GRAPH_ROLE_CODECS[role]:
            raise CustodyRefused("graph_role_codec")
        _graph_file(root, declaration["file"])
        role_paths[role] = declaration["file"]
    if len(set(role_paths.values())) != len(role_paths):
        raise CustodyRefused("graph_role_duplicate_file")
    observed, raw = _graph_rehash_inventory(
        root,
        manifest["retained_files"],
        frozenset(role_paths.values()),
        lineage_name=None,
    )
    by_role = {role: raw[path] for role, path in role_paths.items()}
    recipe = _graph_json(by_role["recipe"], "source_recipe")
    kit = _graph_json(by_role["construction_kit"], "construction_kit")
    challenge = recipe.get("challenge")
    source = recipe.get("source")
    procedure = recipe.get("procedure")
    output = recipe.get("output")
    if (
        set(recipe) != {"schema", "challenge", "source", "procedure", "output"}
        or recipe["schema"] != "carbon.construction-recipe.v1"
        or type(challenge) is not dict
        or set(challenge)
        != {
            "id",
            "version",
            "interface_digest",
            "train_digest",
            "construction_limits_digest",
        }
        or type(challenge["id"]) is not str
        or not challenge["id"]
        or type(challenge["version"]) is not str
        or not challenge["version"]
        or type(source) is not dict
        or set(source) != {"kind", "submission_digest"}
        or source["kind"] != "graph"
        or type(procedure) is not dict
        or set(procedure)
        != {"entrypoint", "configuration", "train_use", "initial_state"}
        or procedure["entrypoint"] is not None
        or procedure["initial_state"] is not None
        or type(procedure["configuration"]) is not dict
        or type(procedure["train_use"]) is not dict
        or type(output) is not dict
        or set(output) != {"format", "interface_digest"}
        or output["format"] != "carbon.numeric-graph.v1"
        or output["interface_digest"] != challenge["interface_digest"]
        or set(kit)
        != {
            "id",
            "version",
            "train_digest",
            "interface_digest",
            "construction_limits_digest",
        }
        or kit
        != {
            "id": challenge["id"],
            "version": challenge["version"],
            "train_digest": challenge["train_digest"],
            "interface_digest": challenge["interface_digest"],
            "construction_limits_digest": challenge["construction_limits_digest"],
        }
    ):
        raise CustodyRefused("graph_recipe_kit_identity")
    for field in ("train_digest", "interface_digest", "construction_limits_digest"):
        _digest(challenge[field], f"graph_{field}")
    _digest(source["submission_digest"], "graph_submission")
    recipe_canonical = json.dumps(
        recipe,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if by_role["recipe"] != recipe_canonical:
        raise CustodyRefused("graph_recipe_noncanonical")
    recipe_digest = _sha(recipe_canonical)
    envelope = _graph_json(by_role["source"], "source_envelope")
    try:
        submission_digest, manifest_bytes, documents = staging.from_envelope(envelope)
        canonical_envelope = json.dumps(
            staging.envelope(manifest_bytes, documents),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (GraphRefused, ValueError, TypeError, UnicodeError) as exc:
        raise CustodyRefused("graph_source_envelope") from exc
    if (
        submission_digest != source["submission_digest"]
        or by_role["source"] != canonical_envelope
    ):
        raise CustodyRefused("graph_source_identity")
    header, state_arrays = _bundle_header(by_role["state"], graph_source=True)
    for value, expected, label in (
        (header["recipe_digest"], recipe_digest, "recipe"),
        (header["submission_digest"], submission_digest, "submission"),
        (header["train_digest"], challenge["train_digest"], "train"),
        (header["train_digest"], _sha(by_role["train"]), "train_bytes"),
        (header["interface_digest"], challenge["interface_digest"], "interface"),
        (header["allowlist_digest"], _sha(by_role["allowlist"]), "allowlist"),
    ):
        _graph_digest_equal(value, expected, label)
    input_arrays = None
    for role in ("train", "inputs", "fixture"):
        if role in by_role:
            arrays = inspect_numeric_npz(by_role[role], max_bytes=MAX_FIXTURE_BYTES)
            if role == "inputs" and set(arrays) != {"inputs"}:
                raise CustodyRefused("graph_inputs_members")
            if role == "inputs":
                input_arrays = arrays
    predictions = _bundle_json(by_role["predictions"], "graph_predictions")
    image = _graph_json(by_role["image"], "worker_image")
    image_fields = {
        "image_id",
        "config_digest",
        "source_tree_digest",
        "wheel_digest",
        "lock_digest",
        "base_image_digest",
        "build_recipe_digest",
        "entrypoint_digest",
    }
    if set(image) != image_fields or image["image_id"] != image["config_digest"]:
        raise CustodyRefused("graph_image_identity")
    for field in image_fields:
        _digest(image[field], f"graph_image_{field}")
    build = _graph_json(by_role["build_receipt"], "build_receipt")
    fit = build.get("fit")
    if (
        set(build)
        != {
            "schema",
            "recipe_digest",
            "submission_digest",
            "train_digest",
            "state_digest",
            "allowlist_digest",
            "framework",
            "fit",
        }
        or build["schema"] != "carbon.development.graph-build.v1"
        or build["recipe_digest"] != recipe_digest
        or build["submission_digest"] != submission_digest
        or build["train_digest"] != challenge["train_digest"]
        or build["state_digest"] != _sha(by_role["state"])
        or build["allowlist_digest"] != _sha(by_role["allowlist"])
        or build["framework"] != "jax"
        or type(fit) is not dict
        or not 1 <= len(fit) <= 32
        or any(
            type(key) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key) is None
            or not (
                _graph_finite_number(value)
                or type(value) is bool
                or type(value) is str
                and _SHA.fullmatch(value)
            )
            for key, value in fit.items()
        )
    ):
        raise CustodyRefused("graph_build_receipt")
    inference = _graph_json(by_role["inference_receipt"], "inference_receipt")
    measured = inference.get("measurement")
    if (
        set(inference)
        != {
            "schema",
            "recipe_digest",
            "state_digest",
            "inputs_digest",
            "predictions_digest",
            "measurement",
        }
        or inference["schema"] != "carbon.development.bundle-inference.v2"
        or inference["recipe_digest"] != recipe_digest
        or inference["state_digest"] != _sha(by_role["state"])
        or inference["inputs_digest"] != _sha(by_role["inputs"])
        or inference["predictions_digest"] != _sha(by_role["predictions"])
        or type(measured) is not dict
        or set(measured)
        != {
            "scope",
            "timing_s",
            "input_shape",
            "input_dtype",
            "output_shape",
            "output_dtype",
        }
        or measured["scope"]
        != "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
        or type(measured["timing_s"]) is not dict
        or set(measured["timing_s"])
        != {"preprocess", "inference", "postprocess", "export"}
        or not _graph_positive_timing(measured["timing_s"].values())
        or any(
            type(measured[field]) is not list
            or not measured[field]
            or len(measured[field]) > 32
            or any(type(n) is not int or n < 1 for n in measured[field])
            for field in ("input_shape", "output_shape")
        )
        or type(measured["input_dtype"]) is not str
        or type(measured["output_dtype"]) is not str
        or measured["output_dtype"]
        not in {
            "float16",
            "float32",
            "float64",
            "int8",
            "int16",
            "int32",
            "int64",
            "uint8",
            "uint16",
            "uint32",
            "uint64",
        }
        or measured["input_dtype"] != input_arrays["inputs"]["dtype"]
        or measured["input_shape"] != input_arrays["inputs"]["shape"]
        or not _graph_prediction_shape(
            predictions, measured["output_shape"], measured["output_dtype"]
        )
    ):
        raise CustodyRefused("graph_measured_inference_receipt")
    worker = _graph_json(by_role["worker_evidence"], "worker_evidence")
    worker_fields = {
        "schema",
        "image_id",
        "parent_image_id",
        "inference_image_id",
        "build_operation",
        "inference_operation",
        "build_controls_digest",
        "inference_controls_digest",
        "state_digest",
        "predictions_digest",
        "build_receipt",
        "inference_receipt",
        "predictions_raw_base64",
        "submission_digest",
    }
    if (
        set(worker) != worker_fields
        or worker["schema"] != "carbon.direct-private-attempt.graph.v1"
        or any(
            worker[field] != image["image_id"]
            for field in ("image_id", "parent_image_id", "inference_image_id")
        )
        or worker["submission_digest"] != submission_digest
        or worker["state_digest"] != _sha(by_role["state"])
        or worker["predictions_digest"] != _sha(by_role["predictions"])
        or worker["build_receipt"] != build
        or worker["inference_receipt"] != inference
        or any(
            type(worker[field]) is not str
            or re.fullmatch(r"operation-[0-9a-f]{64}", worker[field]) is None
            for field in ("build_operation", "inference_operation")
        )
        or worker["build_operation"] == worker["inference_operation"]
    ):
        raise CustodyRefused("graph_worker_lineage")
    for field in ("build_controls_digest", "inference_controls_digest"):
        _digest(worker[field], f"graph_{field}")
    try:
        encoded = worker["predictions_raw_base64"].encode("ascii")
        worker_predictions = base64.b64decode(encoded, validate=True)
    except (AttributeError, UnicodeError, ValueError, binascii.Error) as exc:
        raise CustodyRefused("graph_worker_predictions") from exc
    if (
        base64.b64encode(worker_predictions) != encoded
        or worker_predictions != by_role["predictions"]
    ):
        raise CustodyRefused("graph_worker_predictions")
    if "seed" in by_role:
        seed = _graph_json(by_role["seed"], "seed")
        if set(seed) != {"seed"} or type(seed["seed"]) is not int or seed["seed"] < 0:
            raise CustodyRefused("graph_seed")
    physics = manifest["physics_contract"]
    if physics is not None:
        _exact_keys(physics, {"version", "definition"}, "graph_physics")
        if (
            type(physics["version"]) is not str
            or not physics["version"]
            or type(physics["definition"]) is not dict
        ):
            raise CustodyRefused("graph_physics")
        physics_digest = _sha(
            json.dumps(
                physics,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
    else:
        physics_digest = None
    role_records = {
        role: {
            "file": path,
            "codec": roles[role]["codec"],
            "sha256": observed[path]["sha256"],
        }
        for role, path in sorted(role_paths.items())
    }
    return {
        "schema": BUNDLE_CUSTODY_SCHEMA_V5,
        "source_kind": "graph",
        "role_schema": GRAPH_ROLE_SCHEMA_V3,
        "source_schema": GRAPH_SOURCE_STATE_SCHEMA,
        "scope": BUNDLE_SCOPE,
        "challenge": challenge["id"],
        "challenge_version": challenge["version"],
        "interface_digest": challenge["interface_digest"],
        "train_digest": challenge["train_digest"],
        "submission_digest": submission_digest,
        "bundle_digest": None,
        "environment_ref_digest": None,
        "source_digest": _sha(by_role["source"]),
        "environment_digest": None,
        "image_digest": _sha(by_role["image"]),
        "recipe_digest": recipe_digest,
        "state_digest": _sha(by_role["state"]),
        "fixture_digest": _sha(by_role["fixture"]) if "fixture" in by_role else None,
        "fixture_evidence": (
            "BYTE_BOUND_UNVERIFIED" if "fixture" in by_role else "PENDING"
        ),
        "prediction_digest": _sha(by_role["predictions"]),
        "prediction_evidence": "BYTE_BOUND_UNVERIFIED",
        "seed_digest": _sha(by_role["seed"]) if "seed" in by_role else None,
        "seed_provenance": "DECLARED_UNVERIFIED" if "seed" in by_role else "PENDING",
        "physics_contract": {
            "version": physics["version"] if physics else None,
            "definition_digest": physics_digest,
            "authenticity": "DECLARED_UNVERIFIED" if physics else "PENDING",
        },
        "role_manifest_sha256": _sha(manifest_raw),
        "roles": role_records,
        "state_members": {name: state_arrays[name] for name in sorted(state_arrays)},
        "original_files": observed,
        "provenance_state": "TRUSTED_CHALLENGE_AND_PHYSICS_PENDING",
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "replay_state": "NOT_ATTEMPTED",
        "official_eligible": False,
    }


def prepare_custody_v5(artifact_root: Path, role_manifest_path: Path) -> dict:
    """Index original common-bundle bytes; official physics and replay stay pending."""
    root = _artifact_root(artifact_root)
    manifest_file = Path(role_manifest_path)
    if manifest_file.is_symlink() or not manifest_file.is_file():
        raise CustodyRefused("bundle_role_manifest_file")
    manifest_raw = _read_bounded(manifest_file, MAX_MANIFEST_BYTES, "bundle_roles")
    manifest = _graph_json(manifest_raw, "bundle_roles")
    _exact_keys(
        manifest,
        {
            "schema",
            "scope",
            "source_schema",
            "roles",
            "retained_files",
            "physics_contract",
        },
        "bundle_roles",
    )
    if manifest["scope"] != BUNDLE_SCOPE:
        raise CustodyRefused("bundle_role_scope")
    if manifest["schema"] == GRAPH_ROLE_SCHEMA_V3:
        return _prepare_graph_custody_v5(root, manifest_raw, manifest)
    if (
        manifest["schema"] != BUNDLE_ROLE_SCHEMA_V2
        or manifest["source_schema"] != BUNDLE_STATE_SCHEMA
    ):
        raise CustodyRefused("bundle_role_scope")
    roles = manifest["roles"]
    if type(roles) is not dict or not _BUNDLE_CORE_ROLES <= set(roles) <= set(
        _BUNDLE_ROLE_CODECS
    ):
        raise CustodyRefused("bundle_roles")
    role_paths = {}
    for role, declaration in roles.items():
        _exact_keys(declaration, {"file", "codec"}, f"bundle_role_{role}")
        if declaration["codec"] != _BUNDLE_ROLE_CODECS[role]:
            raise CustodyRefused("bundle_role_codec")
        _graph_file(root, declaration["file"])
        role_paths[role] = declaration["file"]
    if len(set(role_paths.values())) != len(role_paths):
        raise CustodyRefused("bundle_role_duplicate_file")
    observed, raw = _graph_rehash_inventory(
        root,
        manifest["retained_files"],
        frozenset(role_paths.values()),
        lineage_name=None,
    )
    by_role = {role: raw[path] for role, path in role_paths.items()}
    recipe = _graph_json(by_role["recipe"], "bundle_recipe")
    challenge = recipe.get("challenge")
    source = recipe.get("source")
    if (
        recipe.get("schema") != "carbon.construction-recipe.v1"
        or type(challenge) is not dict
        or set(challenge)
        != {
            "id",
            "version",
            "interface_digest",
            "train_digest",
            "construction_limits_digest",
        }
        or type(challenge["id"]) is not str
        or not challenge["id"]
        or type(challenge["version"]) is not str
        or not challenge["version"]
        or type(source) is not dict
        or source.get("kind") != "bundle"
        or type(source.get("bundle_ref")) is not dict
        or source["bundle_ref"].get("schema") != "carbon.library-bundle-ref.v1"
    ):
        raise CustodyRefused("bundle_recipe_identity")
    for field in ("interface_digest", "train_digest", "construction_limits_digest"):
        _digest(challenge[field], f"bundle_{field}")
    bundle_ref = source["bundle_ref"]
    for field in ("bundle_digest", "environment_digest"):
        _digest(bundle_ref.get(field), f"bundle_{field}")
    recipe_digest = _sha(
        json.dumps(
            recipe,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )
    header, state_arrays = _bundle_header(by_role["state"])
    for value, expected, label in (
        (header["recipe_digest"], recipe_digest, "recipe"),
        (header["bundle_digest"], bundle_ref["bundle_digest"], "bundle"),
        (header["train_digest"], challenge["train_digest"], "train"),
        (header["train_digest"], _sha(by_role["train"]), "train_bytes"),
        (header["interface_digest"], challenge["interface_digest"], "interface"),
    ):
        _graph_digest_equal(value, expected, label)
    _digest(header["allowlist_digest"], "allowlist")
    if "allowlist" in by_role:
        _graph_digest_equal(
            _sha(by_role["allowlist"]), header["allowlist_digest"], "allowlist_bytes"
        )
    for role in ("train", "fixture", "inputs"):
        if role in by_role:
            inspect_numeric_npz(by_role[role], max_bytes=MAX_FIXTURE_BYTES)
    for role in ("predictions", "image", "seed", "build_receipt", "inference_receipt"):
        if role in by_role:
            decoded = _bundle_json(by_role[role], role)
            if (
                role in {"image", "seed", "build_receipt", "inference_receipt"}
                and type(decoded) is not dict
            ):
                raise CustodyRefused(f"bundle_{role}_object")
            if role == "seed" and (
                type(decoded) is not dict
                or type(decoded.get("seed")) is not int
                or decoded["seed"] < 0
            ):
                raise CustodyRefused("bundle_seed")
            if role == "predictions" and type(decoded) not in (list, dict):
                raise CustodyRefused("bundle_predictions")
            if role == "build_receipt" and (
                decoded.get("schema") != "carbon.development.bundle-build.v1"
                or decoded.get("recipe_digest") != recipe_digest
                or decoded.get("state_digest") != _sha(by_role["state"])
                or decoded.get("train_digest") != challenge["train_digest"]
                or decoded.get("bundle_digest") != bundle_ref["bundle_digest"]
            ):
                raise CustodyRefused("bundle_build_receipt")
            if role == "inference_receipt" and (
                "predictions" not in by_role
                or decoded.get("schema") != "carbon.development.bundle-inference.v1"
                or decoded.get("recipe_digest") != recipe_digest
                or decoded.get("state_digest") != _sha(by_role["state"])
                or decoded.get("predictions_digest") != _sha(by_role["predictions"])
                or (
                    "inputs" in by_role
                    and decoded.get("inputs_digest") != _sha(by_role["inputs"])
                )
            ):
                raise CustodyRefused("bundle_inference_receipt")
    physics = manifest["physics_contract"]
    if physics is not None:
        _exact_keys(physics, {"version", "definition"}, "bundle_physics")
        if (
            type(physics["version"]) is not str
            or not physics["version"]
            or type(physics["definition"]) is not dict
        ):
            raise CustodyRefused("bundle_physics")
        physics_digest = _sha(
            json.dumps(
                physics,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
    else:
        physics_digest = None
    role_records = {
        role: {
            "file": path,
            "codec": roles[role]["codec"],
            "sha256": observed[path]["sha256"],
        }
        for role, path in sorted(role_paths.items())
    }
    return {
        "schema": BUNDLE_CUSTODY_SCHEMA_V5,
        "source_schema": BUNDLE_STATE_SCHEMA,
        "scope": BUNDLE_SCOPE,
        "challenge": challenge["id"],
        "challenge_version": challenge["version"],
        "interface_digest": challenge["interface_digest"],
        "train_digest": challenge["train_digest"],
        "bundle_digest": bundle_ref["bundle_digest"],
        "environment_ref_digest": bundle_ref["environment_digest"],
        "source_digest": _sha(by_role["source"]),
        "environment_digest": _sha(by_role["environment"]),
        "image_digest": _sha(by_role["image"]),
        "recipe_digest": recipe_digest,
        "state_digest": _sha(by_role["state"]),
        "fixture_digest": _sha(by_role["fixture"]) if "fixture" in by_role else None,
        "fixture_evidence": (
            "BYTE_BOUND_UNVERIFIED" if "fixture" in by_role else "PENDING"
        ),
        "prediction_digest": (
            _sha(by_role["predictions"]) if "predictions" in by_role else None
        ),
        "prediction_evidence": (
            "BYTE_BOUND_UNVERIFIED" if "predictions" in by_role else "PENDING"
        ),
        "seed_digest": _sha(by_role["seed"]) if "seed" in by_role else None,
        "seed_provenance": "DECLARED_UNVERIFIED" if "seed" in by_role else "PENDING",
        "physics_contract": {
            "version": physics["version"] if physics else None,
            "definition_digest": physics_digest,
            "authenticity": "DECLARED_UNVERIFIED" if physics else "PENDING",
        },
        "role_manifest_sha256": _sha(manifest_raw),
        "roles": role_records,
        "state_members": {name: state_arrays[name] for name in sorted(state_arrays)},
        "original_files": observed,
        "provenance_state": "TRUSTED_CHALLENGE_AND_PHYSICS_PENDING",
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "replay_state": (
            "NOT_ATTEMPTED"
            if {"fixture", "predictions"} <= set(by_role)
            else "UNAVAILABLE_PENDING_FIXTURE_OR_PREDICTIONS"
        ),
        "official_eligible": False,
    }


def _validate_manifest(manifest):
    _exact_keys(
        manifest,
        {
            "schema",
            "mode",
            "legacy_binding",
            "challenge",
            "challenge_version",
            "interface_digest",
            "interface_authority_verified",
            "serving_verified",
            "official_eligible",
            "stage",
            "state_codec",
            "fixture",
            "state",
            "recipe",
            "lineage",
            "producer_prediction",
            "receiver_ack",
        },
        "manifest",
    )
    if (
        manifest["schema"] != SCHEMA
        or manifest["mode"] != MODE
        or manifest["legacy_binding"] != LEGACY_BINDING
        or manifest["challenge"] is not None
        or manifest["challenge_version"] is not None
        or manifest["interface_digest"] is not None
        or manifest["interface_authority_verified"] is not False
        or manifest["serving_verified"] is not False
        or manifest["official_eligible"] is not False
        or manifest["state_codec"] != CODEC
        or type(manifest["stage"]) is not str
        or manifest["stage"] not in {"CONSTRUCT_FIT", "STATE_REPLAY"}
    ):
        raise CustodyRefused("unbound_scope")

    fixture = manifest["fixture"]
    _exact_keys(
        fixture,
        {
            "schema",
            "file",
            "prediction_file",
            "prediction_array",
            "inputs",
            "outputs",
            "state_arrays",
            "expected_prediction",
            "file_digest",
            "descriptor_digest",
        },
        "fixture",
    )
    if (
        fixture["schema"] != FIXTURE_SCHEMA
        or type(fixture["file"]) is not str
        or not _FILE.fullmatch(fixture["file"])
    ):
        raise CustodyRefused("fixture_identity")
    _digest(fixture["file_digest"], "fixture_file")
    _digest(fixture["descriptor_digest"], "fixture_descriptor")
    inputs = _array_map(
        fixture["inputs"],
        label="fixture_input",
        max_arrays=16,
        max_bytes=MAX_FIXTURE_BYTES,
    )
    outputs = _array_map(
        fixture["outputs"],
        label="fixture_output",
        max_arrays=16,
        max_bytes=MAX_FIXTURE_BYTES,
    )
    state_arrays = _array_map(
        fixture["state_arrays"],
        label="fixture_state",
        max_arrays=128,
        max_bytes=MAX_STATE_BYTES,
    )
    if (
        type(fixture["prediction_file"]) is not str
        or not _FILE.fullmatch(fixture["prediction_file"])
        or type(fixture["prediction_array"]) is not str
        or not _ARRAY.fullmatch(fixture["prediction_array"])
        or set(inputs) & set(outputs)
        or fixture["prediction_array"] not in outputs
    ):
        raise CustodyRefused("fixture_input_output_roles")
    expected = fixture["expected_prediction"]
    if expected is not None:
        _exact_keys(
            expected,
            {"array", "encoding", "sha256", "file_digest"},
            "expected_prediction",
        )
        if (
            expected["array"] != fixture["prediction_array"]
            or expected["encoding"] != "C_CONTIGUOUS_RAW_V1"
        ):
            raise CustodyRefused("expected_prediction_identity")
        _digest(expected["sha256"], "expected_prediction_raw")
        _digest(expected["file_digest"], "expected_prediction_file")
    if manifest["stage"] == "STATE_REPLAY" and expected is None:
        raise CustodyRefused("replay_expected_prediction_required")
    state = manifest["state"]
    if manifest["stage"] == "CONSTRUCT_FIT":
        _exact_keys(state, {"file", "file_digest", "arrays"}, "state")
        if (
            state["file"] is not None
            or state["file_digest"] is not None
            or state["arrays"] is not None
        ):
            raise CustodyRefused("fit_state_must_be_absent")
        if manifest["producer_prediction"] is not None:
            raise CustodyRefused("fit_prediction_must_be_absent")
        if fixture["expected_prediction"] is not None:
            raise CustodyRefused("fit_fixture_prediction_must_be_absent")
    else:
        _exact_keys(state, {"file", "file_digest", "arrays"}, "state")
        if type(state["file"]) is not str or not _FILE.fullmatch(state["file"]):
            raise CustodyRefused("replay_state_required")
        _digest(state["file_digest"], "state_file")
        state_arrays_observed = _array_map(
            state["arrays"], label="state", max_arrays=128, max_bytes=MAX_STATE_BYTES
        )
        if state_arrays_observed != state_arrays:
            raise CustodyRefused("state_descriptor_differs_from_fixture")
        prediction = manifest["producer_prediction"]
        _exact_keys(
            prediction,
            {"file", "array", "encoding", "file_digest", "raw_sha256"},
            "producer_prediction",
        )
        if (
            type(prediction["file"]) is not str
            or not _FILE.fullmatch(prediction["file"])
            or type(prediction["array"]) is not str
            or not _ARRAY.fullmatch(prediction["array"])
            or prediction["encoding"] != "C_CONTIGUOUS_RAW_V1"
        ):
            raise CustodyRefused("prediction_identity")
        _digest(prediction["file_digest"], "prediction_file")
        _digest(prediction["raw_sha256"], "prediction_raw")

    recipe = manifest["recipe"]
    _exact_keys(
        recipe, {"constructor_module", "constructor_name", "recipe_digest"}, "recipe"
    )
    if any(
        type(recipe[key]) is not str or not _IDENT.fullmatch(recipe[key])
        for key in ("constructor_module", "constructor_name")
    ):
        raise CustodyRefused("recipe_identifier")
    _digest(recipe["recipe_digest"], "recipe")
    lineage = manifest["lineage"]
    _exact_keys(
        lineage,
        {
            "source_digest",
            "bundle_digest",
            "environment_digest",
            "image_digest",
            "producer_receipt_digest",
        },
        "lineage",
    )
    for key, value in lineage.items():
        _digest(value, "lineage_" + key)
    ack = manifest["receiver_ack"]
    _exact_keys(ack, {"state", "receipt_file", "receipt_digest"}, "receiver_ack")
    if type(ack["state"]) is not str or ack["state"] not in {
        "PENDING",
        "RECORDED_UNVERIFIED",
    }:
        raise CustodyRefused("receiver_ack_state")
    if ack["state"] == "PENDING" and (
        ack["receipt_file"] is not None or ack["receipt_digest"] is not None
    ):
        raise CustodyRefused("pending_ack_has_receipt")
    if ack["state"] == "RECORDED_UNVERIFIED" and (
        type(ack["receipt_file"]) is not str
        or not _JSON_FILE.fullmatch(ack["receipt_file"])
    ):
        raise CustodyRefused("ack_receipt_required")
    if ack["state"] == "RECORDED_UNVERIFIED":
        if manifest["stage"] != "STATE_REPLAY":
            raise CustodyRefused("fit_cannot_have_receiver_ack")
        _digest(ack["receipt_digest"], "ack_receipt")
    if manifest["stage"] == "STATE_REPLAY" and state["file"] in {
        fixture["file"],
        fixture["prediction_file"],
    }:
        raise CustodyRefused("state_fixture_files_must_be_distinct")
    return inputs, outputs, state_arrays


def prepare_custody(artifact_root: Path, manifest: dict) -> dict:
    """Rehash exact public files and return a custody receipt, without running a model."""
    artifact_root = _artifact_root(artifact_root)
    inputs, outputs, state_arrays = _validate_manifest(manifest)
    fixture = manifest["fixture"]
    fixture_path = _safe_file(artifact_root, fixture["file"])
    fixture_bytes = _read_bounded(fixture_path, MAX_FIXTURE_BYTES, "fixture")
    if _sha(fixture_bytes) != fixture["file_digest"]:
        raise CustodyRefused("fixture_file_digest")
    # Descriptor hash excludes its own digest and is canonical JSON as in e82.
    descriptor = {
        key: fixture[key]
        for key in (
            "schema",
            "file",
            "prediction_file",
            "prediction_array",
            "inputs",
            "outputs",
            "state_arrays",
            "expected_prediction",
        )
    }
    if (
        _sha(json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode())
        != fixture["descriptor_digest"]
    ):
        raise CustodyRefused("fixture_descriptor_digest")
    expected = fixture["expected_prediction"]
    fixture_arrays = (
        inputs | outputs
        if expected is not None and fixture["prediction_file"] == fixture["file"]
        else inputs
    )
    validate_numeric_npz(fixture_bytes, fixture_arrays, max_bytes=MAX_FIXTURE_BYTES)

    if expected is not None:
        prediction_path = _safe_file(artifact_root, fixture["prediction_file"])
        prediction_bytes = _read_bounded(
            prediction_path, MAX_FIXTURE_BYTES, "fixture_prediction"
        )
        if _sha(prediction_bytes) != expected["file_digest"]:
            raise CustodyRefused("fixture_prediction_file_digest")
        if fixture["prediction_file"] != fixture["file"]:
            prediction_observed = validate_numeric_npz(
                prediction_bytes, outputs, max_bytes=MAX_FIXTURE_BYTES
            )
        else:
            prediction_observed = validate_numeric_npz(
                prediction_bytes, inputs | outputs, max_bytes=MAX_FIXTURE_BYTES
            )
        if prediction_observed[expected["array"]] != expected["sha256"]:
            raise CustodyRefused("fixture_prediction_raw_digest")

    state = manifest["state"]
    state_digest = None
    if manifest["stage"] == "STATE_REPLAY":
        state_path = _safe_file(artifact_root, state["file"])
        state_bytes = _read_bounded(state_path, MAX_STATE_BYTES, "state")
        if _sha(state_bytes) != state["file_digest"]:
            raise CustodyRefused("state_file_digest")
        validate_numeric_npz(state_bytes, state_arrays, max_bytes=MAX_STATE_BYTES)
        state_digest = _sha(state_bytes)
        prediction = manifest["producer_prediction"]
        if (
            prediction["file"] != fixture["prediction_file"]
            or prediction["array"] != fixture["prediction_array"]
            or prediction["encoding"] != fixture["expected_prediction"]["encoding"]
            or prediction["file_digest"]
            != fixture["expected_prediction"]["file_digest"]
            or prediction["raw_sha256"] != fixture["expected_prediction"]["sha256"]
        ):
            raise CustodyRefused("producer_prediction_not_fixture_bound")

    ack = manifest["receiver_ack"]
    if ack["state"] == "RECORDED_UNVERIFIED":
        ack_path = _safe_file(artifact_root, ack["receipt_file"], json_file=True)
        ack_bytes = _read_bounded(ack_path, MAX_MANIFEST_BYTES, "ack_receipt")
        if _sha(ack_bytes) != ack["receipt_digest"]:
            raise CustodyRefused("ack_receipt_digest")
        ack_doc = _parse_json(ack_bytes, "ack_receipt")
        _exact_keys(
            ack_doc,
            {
                "schema",
                "mode",
                "stage",
                "challenge",
                "fixture_file_digest",
                "state_file_digest",
                "prediction_raw_sha256",
                "receiver_result",
                "receiver_identity",
                "verified_prediction_file_digest",
                "verified_prediction_raw_sha256",
                "source_digest",
                "bundle_digest",
                "environment_digest",
                "image_digest",
            },
            "ack_receipt",
        )
        expected_ack = {
            "schema": "carbon.scorelab.public-unbound-receiver-ack.v1",
            "mode": MODE,
            "stage": "STATE_REPLAY",
            "challenge": None,
            "fixture_file_digest": fixture["file_digest"],
            "state_file_digest": state["file_digest"],
            "prediction_raw_sha256": fixture["expected_prediction"]["sha256"],
            "source_digest": manifest["lineage"]["source_digest"],
            "bundle_digest": manifest["lineage"]["bundle_digest"],
            "environment_digest": manifest["lineage"]["environment_digest"],
            "image_digest": manifest["lineage"]["image_digest"],
        }
        if any(ack_doc.get(key) != value for key, value in expected_ack.items()):
            raise CustodyRefused("ack_receipt_binding")
        if type(ack_doc["receiver_identity"]) is not str or not _IDENT.fullmatch(
            ack_doc["receiver_identity"]
        ):
            raise CustodyRefused("ack_receiver_identity")
        if ack_doc["receiver_result"] != "REPLAY_VERIFIED":
            raise CustodyRefused("ack_receiver_result")
        _digest(ack_doc["verified_prediction_file_digest"], "ack_output_file")
        if (
            ack_doc["verified_prediction_raw_sha256"]
            != fixture["expected_prediction"]["sha256"]
        ):
            raise CustodyRefused("ack_output_prediction_mismatch")

    receiver_state = manifest["receiver_ack"]["state"]
    return {
        "schema": "carbon.scorelab.public-unbound-custody-receipt.v1",
        "mode": MODE,
        "legacy_binding": LEGACY_BINDING,
        "challenge": None,
        "challenge_version": None,
        "declared_interface_digest": None,
        "interface_authority_verified": False,
        "serving_verified": False,
        "official_eligible": False,
        "stage": manifest["stage"],
        "state_codec": CODEC,
        "fixture_file_digest": fixture["file_digest"],
        "fixture_descriptor_digest": fixture["descriptor_digest"],
        "native_state_digest": state_digest,
        "producer_prediction_file_digest": (
            fixture["expected_prediction"]["file_digest"]
            if fixture["expected_prediction"]
            else None
        ),
        "producer_prediction_raw_sha256": (
            fixture["expected_prediction"]["sha256"]
            if fixture["expected_prediction"]
            else None
        ),
        "recipe_digest": manifest["recipe"]["recipe_digest"],
        "lineage": dict(manifest["lineage"]),
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "producer_identity_verification": "PRODUCT_HOST_RECEIPT_REQUIRED",
        "lineage_assertion_status": "PRODUCER_DECLARED_NOT_HOST_VERIFIED",
        "replay_state": "PENDING_EXTERNAL_RECEIVER",
        "receiver_ack_state": (
            "RECEIVER_ACK_PENDING"
            if receiver_state == "PENDING"
            else "RECEIVER_ACK_RECORDED_UNVERIFIED"
        ),
        "receiver_ack_authenticity": "NOT_VERIFIED_BY_THIS_TOOL",
    }


def _parse_json(raw: bytes, label: str):
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CustodyRefused(f"{label}_json") from exc


def _load_json(path, *, label="manifest"):
    raw = _read_bounded(Path(path), MAX_MANIFEST_BYTES, label)
    return raw, _parse_json(raw, label)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser(
        "prepare", help="rehash a closed public unbound artifact set"
    )
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--artifacts", type=Path, required=True)
    prepare.add_argument("--out", type=Path, required=True)
    prepare_v2 = sub.add_parser(
        "prepare-v2",
        help="rehash a role-aware public unbound v2 artifact set",
    )
    prepare_v2.add_argument("--manifest", type=Path, required=True)
    prepare_v2.add_argument("--artifacts", type=Path, required=True)
    prepare_v2.add_argument("--out", type=Path, required=True)
    prepare_bundle = sub.add_parser(
        "prepare-bundle-v5",
        help="rehash inert common-bundle original bytes; score provenance stays pending",
    )
    prepare_bundle.add_argument("--roles", type=Path, required=True)
    prepare_bundle.add_argument("--artifacts", type=Path, required=True)
    prepare_bundle.add_argument("--out", type=Path, required=True)
    jno = sub.add_parser(
        "prepare-jno-r2",
        help="validate retained public jNO R2 bytes and prepare custody",
    )
    jno.add_argument("--artifacts", type=Path, required=True)
    jno.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("output already exists; custody receipts are immutable")
    if args.command == "prepare-bundle-v5" and args.out.resolve().is_relative_to(
        args.artifacts.resolve()
    ):
        parser.error("bundle custody receipt must be outside original artifacts")
    if args.command == "prepare-jno-r2":
        manifest = manifest_from_jno_r2(args.artifacts)
        receipt = prepare_custody(args.artifacts, manifest)
    elif args.command == "prepare-v2":
        _, manifest = _load_json(args.manifest)
        receipt = prepare_custody_v2(args.artifacts, manifest)
    elif args.command == "prepare-bundle-v5":
        receipt = prepare_custody_v5(args.artifacts, args.roles)
    else:
        _, manifest = _load_json(args.manifest)
        receipt = prepare_custody(args.artifacts, manifest)
    raw = (
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    with args.out.open("xb") as stream:
        stream.write(raw)
        stream.flush()
    print(json.dumps({"status": "PUBLIC_BYTES_REHASHED", "receipt_sha256": _sha(raw)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
