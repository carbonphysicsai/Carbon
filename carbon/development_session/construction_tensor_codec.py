"""Trusted tensor decoding for independently reconstructed construction tasks.

Only the controller's checked Challenge binding selects a TRAIN codec. Battery
keeps its original gzip identity; the existing numeric fixture keeps its NPZ
contract. No source callable, target normalization or model choice lives here.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path

import numpy as np

from .bundle_graph_state import MAX_BYTES, _preflight_npy

_BINDING_FIELDS = {
    "challenge_id",
    "challenge_version",
    "train_digest",
    "interface_digest",
    "construction_limits_digest",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BASE_MODULES = (
    "carbon.development_session.construction_tensor_codec",
    "carbon.development_session.bundle_graph_state",
    "carbon.development_session.construction_recipe",
    "carbon.challenge_validator.strict_json",
    "carbon.level4.allowlist",
    "carbon.level4.graph",
    "carbon.level4.params",
)
_BATTERY_MODULES = (
    "carbon.battery.construction_material",
    "carbon.battery.challenge",
    "carbon.battery.domain",
    "carbon.battery.recipes",
    "carbon.reconstruction.worker.model",
    "carbon.registry.__init__",
    "carbon.registry.development",
    "carbon.registry.digest",
    "carbon.registry.gate",
    "carbon.registry.model",
    "carbon.registry.store",
)


class TensorCodecError(ValueError):
    """Malformed or mismatched construction tensors; never a scientific verdict."""


def _checked_binding(binding: dict) -> None:
    if (
        type(binding) is not dict
        or set(binding) != _BINDING_FIELDS
        or any(
            type(binding[name]) is not str or not binding[name]
            for name in ("challenge_id", "challenge_version")
        )
        or any(
            type(binding[name]) is not str or _DIGEST.fullmatch(binding[name]) is None
            for name in _BINDING_FIELDS - {"challenge_id", "challenge_version"}
        )
    ):
        raise TensorCodecError("checked construction binding required")


def _battery(binding: dict) -> bool:
    _checked_binding(binding)
    # This selects a byte codec, not Challenge admission or scientific meaning.
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return binding["challenge_id"] == BATTERY_CHALLENGE


def _checked_bytes(raw: bytes, expected_digest: str) -> None:
    if (
        type(raw) is not bytes
        or not 0 < len(raw) <= MAX_BYTES
        or type(expected_digest) is not str
        or _DIGEST.fullmatch(expected_digest) is None
        or "sha256:" + hashlib.sha256(raw).hexdigest() != expected_digest
    ):
        raise TensorCodecError("construction tensor bytes differ")


def _npz(raw: bytes, names: set[str]) -> dict[str, np.ndarray]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if (
                len(members) != len(names)
                or {member.filename for member in members}
                != {name + ".npy" for name in names}
                or any(member.compress_type != zipfile.ZIP_STORED for member in members)
                or any(member.flag_bits & 1 for member in members)
                or sum(member.file_size for member in members) > MAX_BYTES
            ):
                raise TensorCodecError("construction tensor members differ")
            for member in members:
                _preflight_npy(archive, member)
        with np.load(io.BytesIO(raw), allow_pickle=False) as data:
            if set(data.files) != names:
                raise TensorCodecError("construction tensor members differ")
            arrays = {name: data[name] for name in names}
        if any(
            array.dtype.kind not in "fiu" or not np.isfinite(array).all()
            for array in arrays.values()
        ):
            raise TensorCodecError("construction tensor values differ")
        return arrays
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        EOFError,
        zipfile.BadZipFile,
    ) as error:
        if type(error) is TensorCodecError:
            raise
        raise TensorCodecError("construction tensor archive malformed") from None


def train_tensors(raw: bytes, binding: dict) -> tuple[np.ndarray, np.ndarray]:
    """Decode exact bound TRAIN bytes; the caller owns registered admission."""
    _checked_binding(binding)
    _checked_bytes(raw, binding["train_digest"])
    if _battery(binding):
        from carbon.battery import challenge, construction_material

        if (
            binding["challenge_version"] != challenge.CHALLENGE.version
            or binding["train_digest"] != "sha256:" + challenge.TRAIN_V1_SHA256
        ):
            raise TensorCodecError("Battery TRAIN binding differs")
        try:
            return construction_material.train_tensors(raw)
        except challenge.MaterialMismatch:
            raise TensorCodecError("Battery TRAIN material differs") from None
    arrays = _npz(raw, {"inputs", "targets"})
    inputs, targets = arrays["inputs"], arrays["targets"]
    if (
        inputs.ndim < 2
        or targets.ndim < 2
        or len(inputs) < 1
        or len(inputs) != len(targets)
    ):
        raise TensorCodecError("construction TRAIN tensor contract differs")
    return inputs, targets


def input_tensor(raw: bytes, expected_digest: str) -> np.ndarray:
    """Decode checked input-only example/inference bytes, never TRAIN targets."""
    _checked_bytes(raw, expected_digest)
    inputs = _npz(raw, {"inputs"})["inputs"]
    if inputs.ndim < 2 or len(inputs) < 1:
        raise TensorCodecError("construction input tensor contract differs")
    return inputs


def requires_x64(*arrays_or_dtypes) -> bool:
    """Tell the worker whether checked numeric arrays need JAX's x64 context.

    This reports dtype semantics only. The caller sets the context around both
    construction tracing and separate inert inference; this imports no JAX.
    """
    try:
        dtypes = [
            value.dtype if type(value) is np.ndarray else np.dtype(value)
            for value in arrays_or_dtypes
        ]
    except (TypeError, ValueError):
        raise TensorCodecError("checked numeric dtype required") from None
    if any(dtype.kind not in "fiuc" for dtype in dtypes):
        raise TensorCodecError("checked numeric dtype required")
    return any(dtype.itemsize >= (16 if dtype.kind == "c" else 8) for dtype in dtypes)


def worker_module_files(binding: dict, *, training: bool = True) -> dict[str, bytes]:
    """Exact trusted module closure, without TRAIN, source or evaluation bytes.

    Flat stage names match the existing worker's dotted-module convention.
    The bootstrap must create parent package directories before copying and
    preserve the supplied registry __init__; other package inits can be empty.
    Inference uses training=False and receives no Battery TRAIN decoder modules.
    """
    _checked_binding(binding)
    if type(training) is not bool:
        raise TensorCodecError("trusted worker stage role required")
    modules = _BASE_MODULES
    if training:
        modules += ("carbon.reconstruction.capability_registry",)
        if _battery(binding):
            modules += _BATTERY_MODULES
    root = Path(__file__).resolve().parents[2]
    return {
        name + ".py": (root / (name.replace(".", "/") + ".py")).read_bytes()
        for name in modules
    }
