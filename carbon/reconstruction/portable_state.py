"""Logical state transport inside already admitted public research workers.

This is not an admission or artifact-authentication API. The research controller
owns the principal, operation and expected input digest. No evaluator imports
this module. A bundle contains arrays and metadata, never compiled code/caches.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

SCHEMA = "carbon.public-research.logical-state.v1"
SCOPE = "MINER_SELF_REPORTED_NO_EVALUATION_AUTHORITY"
_FIELDS = {
    "schema",
    "scope",
    "principal",
    "operation_id",
    "checkpoint_manifest_sha256",
    "placement",
}


def _token(value):
    if (
        type(value) is not str
        or not 1 <= len(value.encode("utf-8")) <= 256
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("bounded principal/operation identity required")
    return value


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_value(value):
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(c not in "0123456789abcdef" for c in value[7:])
    ):
        raise ValueError("exact expected bundle digest required")
    return value


def _runtime():
    from carbon.reconstruction._vendor.carbon_jax_lab import checkpoint
    from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer

    return checkpoint, Trainer


def _placement(state):
    import jax

    leaves = jax.tree.leaves(state)
    devices = set()
    for leaf in leaves:
        if not isinstance(leaf, jax.Array) or not leaf.is_fully_addressable:
            raise ValueError("fully addressable JAX logical state required")
        local = leaf.devices()
        if len(local) != 1 or not leaf.is_fully_replicated:
            raise ValueError("sharded state requires an explicit transport policy")
        devices.update(local)
    if len(devices) != 1 or jax.process_count() != 1:
        raise ValueError("single-device single-process state required")
    device = next(iter(devices))
    return {
        "backend": device.platform,
        "device_kind": device.device_kind,
        "device_count": 1,
        "process_count": 1,
        "layout": "FULL_LOGICAL_ARRAYS_SINGLE_DEVICE",
    }


def _validate_placement(value, environment):
    if (
        type(value) is not dict
        or set(value)
        != {"backend", "device_kind", "device_count", "process_count", "layout"}
        or value["backend"] not in {"cpu", "gpu", "tpu"}
        or value["backend"] != environment["backend"]
        or type(value["device_count"]) is not int
        or value["device_count"] != 1
        or type(value["process_count"]) is not int
        or value["process_count"] != 1
        or value["layout"] != "FULL_LOGICAL_ARRAYS_SINGLE_DEVICE"
    ):
        raise ValueError("unsupported or inconsistent source placement")
    _token(value["device_kind"])


def save_research_state(trainer, path, *, principal, operation_id):
    """Seal a new bundle; return its digest for the existing workspace ledger."""
    checkpoint, trainer_type = _runtime()
    if type(trainer) is not trainer_type:
        raise TypeError("registered lab Trainer required")
    principal, operation_id = _token(principal), _token(operation_id)
    placement = _placement(trainer.state)
    _validate_placement(placement, checkpoint.environment())
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError("research bundle is immutable")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise ValueError("symlink bundle parent")
    temporary = Path(tempfile.mkdtemp(prefix=".logical-state-", dir=path.parent))
    try:
        checkpoint.save_checkpoint(trainer, temporary / "checkpoint")
        manifest = (temporary / "checkpoint/manifest.json").read_bytes()
        binding = {
            "schema": SCHEMA,
            "scope": SCOPE,
            "principal": principal,
            "operation_id": operation_id,
            "checkpoint_manifest_sha256": _digest(manifest),
            "placement": placement,
        }
        raw = _canonical(binding)
        with (temporary / "binding.json").open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise FileExistsError("research bundle is immutable")
        os.rename(temporary, path)
        return _digest(raw)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _read_bundle(path, expected_digest):
    checkpoint, _ = _runtime()
    expected_digest = _digest_value(expected_digest)
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("research bundle directory required")
    if {p.name for p in path.iterdir()} != {"checkpoint", "binding.json"}:
        raise ValueError("closed research bundle members required")
    binding_file = path / "binding.json"
    if (
        binding_file.is_symlink()
        or not binding_file.is_file()
        or binding_file.stat().st_size > 8192
    ):
        raise ValueError("bounded research binding required")
    raw = binding_file.read_bytes()
    if _digest(raw) != expected_digest:
        raise ValueError("research bundle digest differs")
    binding = checkpoint._closed_json(raw)
    if (
        type(binding) is not dict
        or set(binding) != _FIELDS
        or binding["schema"] != SCHEMA
        or binding["scope"] != SCOPE
        or _canonical(binding) != raw
    ):
        raise ValueError("closed canonical research binding required")
    _token(binding["principal"])
    _token(binding["operation_id"])
    _digest_value(binding["checkpoint_manifest_sha256"])
    meta, arrays = checkpoint._read(path / "checkpoint")
    if (
        _digest((path / "checkpoint/manifest.json").read_bytes())
        != binding["checkpoint_manifest_sha256"]
    ):
        raise ValueError("checkpoint manifest binding differs")
    _validate_placement(binding["placement"], meta["environment"])
    return binding, meta, arrays


def inspect_research_state(path, *, expected_digest):
    """Return verified logical leaf/shape/dtype, units, RNG/progress and placement."""
    binding, meta, _ = _read_bundle(path, expected_digest)
    return {"binding": binding, "logical_state": meta, "digest": expected_digest}


def load_research_continuation(
    trainer, path, *, principal, operation_id, expected_digest
):
    """Restore state for a NEW already-admitted research operation, never evaluation.

    Only backend/machine placement may change. Library/precision/source/recipe/
    data identities stay exact. Actual cross-backend numerical behavior must be
    measured; this function makes no equivalence or qualification claim.
    """
    checkpoint, trainer_type = _runtime()
    if type(trainer) is not trainer_type:
        raise TypeError("registered lab Trainer required")
    principal, operation_id = _token(principal), _token(operation_id)
    binding, meta, arrays = _read_bundle(path, expected_digest)
    if binding["principal"] != principal:
        raise ValueError("cross-principal research continuation rejected")
    if binding["operation_id"] == operation_id:
        raise ValueError("continuation requires a new bound operation")
    target_environment = checkpoint.environment()
    target_placement = _placement(trainer.state)
    _validate_placement(target_placement, target_environment)
    placement_fields = {"backend", "platform", "machine"}
    if any(
        meta["environment"][key] != target_environment[key]
        for key in target_environment.keys() - placement_fields
    ):
        raise ValueError("undeclared library or precision change")
    if (
        meta["contract_id"] != trainer.contract_id
        or meta["training_data"] != trainer.data.fingerprint
        or meta["u_scale"] != trainer.u_scale
        or meta["runtime_key_digest"] != trainer.runtime_key_digest
        or meta["physical_scaling_digest"] != trainer.physical_scaling.digest
    ):
        raise ValueError("continuation recipe/data/normalization/RNG binding differs")
    restored = checkpoint._restore(trainer.state, meta, arrays)
    _validate_placement(_placement(restored), target_environment)
    receipt = {
        "schema": "carbon.public-research.continuation.v1",
        "scope": SCOPE,
        "principal": principal,
        "source_operation": binding["operation_id"],
        "operation_id": operation_id,
        "source_bundle": expected_digest,
        "source_placement": binding["placement"],
        "target_placement": target_placement,
        "target_environment": target_environment,
        "backend_changed": binding["placement"]["backend"]
        != target_placement["backend"],
        "continued_from_step": meta["step"],
        "scientifically_qualified": False,
    }
    trainer.state = restored
    return receipt
