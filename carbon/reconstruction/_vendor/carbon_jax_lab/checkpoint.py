"""Immutable local checkpoints: arrays + closed JSON metadata, never pickle.

Hashes establish integrity against accidental corruption, not authenticity against
an attacker who can rewrite the entire checkpoint. Not an encrypted evidence vault.
The filesystem owner must ensure a single writer; this is not distributed storage.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path

import jax
import jax.numpy as jnp
import jaxlib
import numpy as np

from .config import ModelConfig, TaskConfig, TrainConfig, canonical_json, identity
from .optim import init_adam
from .training import Predictor, TrainState

_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "model",
        "task",
        "train",
        "contract_id",
        "training_data",
        "training_case_keys",
        "training_grid_points",
        "u_scale",
        "step",
        "source_id",
        "environment",
        "state_sha256",
        "paths",
        "leaves",
        "runtime_key_digest",
    }
)
_MAX_LEAVES = 10_000
_MAX_ARRAY_BYTES = 1 << 30


def _closed_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=pairs)


def source_identity():
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def environment():
    return {
        "python": platform.python_version(),
        "jax": jax.__version__,
        "jaxlib": jaxlib.__version__,
        "numpy": np.__version__,
        "backend": jax.default_backend(),
        "x64": bool(jax.config.jax_enable_x64),
        "platform": platform.system(),
        "machine": platform.machine(),
    }


def _paths_and_leaves(tree):
    pairs, definition = jax.tree_util.tree_flatten_with_path(tree)
    return (
        [jax.tree_util.keystr(p) for p, _ in pairs],
        [v for _, v in pairs],
        definition,
    )


def _fsync(path):
    with open(path, "rb") as f:
        os.fsync(f.fileno())


def save_checkpoint(trainer, path):
    path = Path(path)
    if path.exists():
        raise FileExistsError("checkpoint is immutable; choose a new path")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".checkpoint-", dir=path.parent))
    try:
        paths, leaves, _ = _paths_and_leaves(trainer.state)
        arrays = {
            f"leaf_{i:05d}": np.asarray(jax.device_get(v)) for i, v in enumerate(leaves)
        }
        if any(a.dtype.hasobject for a in arrays.values()):
            raise ValueError("object array")
        np.savez_compressed(temp / "state.npz", **arrays)
        state_hash = hashlib.sha256((temp / "state.npz").read_bytes()).hexdigest()
        meta = {
            "schema": "carbon-jax-lab-checkpoint.v1",
            "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
            "model": asdict(trainer.model_config),
            "task": asdict(trainer.task_config),
            "train": asdict(trainer.config),
            "contract_id": trainer.contract_id,
            "training_data": trainer.data.fingerprint,
            "training_case_keys": list(trainer.data.case_keys),
            "training_grid_points": trainer.data.initial.shape[1],
            "u_scale": trainer.u_scale,
            "step": int(trainer.state.step),
            "source_id": source_identity(),
            "environment": environment(),
            "runtime_key_digest": trainer.runtime_key_digest,
            "state_sha256": state_hash,
            "paths": paths,
            "leaves": [
                {"shape": list(a.shape), "dtype": a.dtype.str} for a in arrays.values()
            ],
        }
        (temp / "manifest.json").write_text(canonical_json(meta) + "\n")
        _fsync(temp / "state.npz")
        _fsync(temp / "manifest.json")
        if path.exists():
            raise FileExistsError(path)
        # Atomic rename publishes the complete directory on the same filesystem.
        # The single-writer requirement is explicit; do not use a shared output path.
        os.rename(temp, path)
        if hasattr(os, "O_DIRECTORY"):
            fd = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return meta


def _read(path):
    path = Path(path)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("checkpoint directory required")
    members = {p.name for p in path.iterdir()}
    if members != {"manifest.json", "state.npz"}:
        raise ValueError("checkpoint members")
    if any((path / n).is_symlink() or not (path / n).is_file() for n in members):
        raise ValueError("symlink checkpoint rejected")
    if (path / "manifest.json").stat().st_size > 2**22:
        raise ValueError("manifest size")
    meta = _closed_json((path / "manifest.json").read_text(encoding="utf-8"))
    if type(meta) is not dict or set(meta) != _MANIFEST_FIELDS:
        raise ValueError("checkpoint manifest fields")
    if (
        meta.get("schema") != "carbon-jax-lab-checkpoint.v1"
        or meta.get("scope") != "UNQUALIFIED_PUBLIC_DEVELOPMENT"
    ):
        raise ValueError("checkpoint schema/scope")
    if type(meta["leaves"]) is not list or not 1 <= len(meta["leaves"]) <= _MAX_LEAVES:
        raise ValueError("checkpoint leaf count")
    if (
        type(meta["paths"]) is not list
        or len(meta["paths"]) != len(meta["leaves"])
        or any(type(p) is not str or len(p) > 4096 for p in meta["paths"])
    ):
        raise ValueError("checkpoint paths")
    if meta["runtime_key_digest"] is not None and (
        type(meta["runtime_key_digest"]) is not str
        or len(meta["runtime_key_digest"]) != 64
    ):
        raise ValueError("runtime key digest")
    state_path = path / "state.npz"
    if state_path.stat().st_size > _MAX_ARRAY_BYTES:
        raise ValueError("checkpoint too large for local profile")
    if hashlib.sha256(state_path.read_bytes()).hexdigest() != meta["state_sha256"]:
        raise ValueError("checkpoint byte integrity mismatch")
    with zipfile.ZipFile(state_path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        expected_zip = [f"leaf_{i:05d}.npy" for i in range(len(meta["leaves"]))]
        if names != expected_zip or len(names) != len(set(names)):
            raise ValueError("checkpoint ZIP members")
        if any(
            i.flag_bits & 1 or i.is_dir() or Path(i.filename).name != i.filename
            for i in infos
        ):
            raise ValueError("unsafe checkpoint ZIP member")
        if sum(i.file_size for i in infos) > _MAX_ARRAY_BYTES:
            raise ValueError("uncompressed checkpoint limits")
    with np.load(state_path, allow_pickle=False) as z:
        expected = [f"leaf_{i:05d}" for i in range(len(meta["leaves"]))]
        if sorted(z.files) != expected:
            raise ValueError("checkpoint array names")
        arrays = [z[name] for name in expected]
    for a, record in zip(arrays, meta["leaves"]):
        if type(record) is not dict or set(record) != {"shape", "dtype"}:
            raise ValueError("invalid checkpoint leaf record")
        if (
            type(record["shape"]) is not list
            or len(record["shape"]) > 16
            or any(type(v) is not int or v < 0 for v in record["shape"])
        ):
            raise ValueError("invalid checkpoint shape")
        if (
            a.nbytes > _MAX_ARRAY_BYTES
            or list(a.shape) != record["shape"]
            or a.dtype.str != record["dtype"]
            or a.dtype.hasobject
            or a.dtype.kind not in "biufc"
            or not np.isfinite(a).all()
        ):
            raise ValueError("invalid checkpoint array")
    if source_identity() != meta["source_id"]:
        raise ValueError("checkpoint source differs; explicit migration required")
    return meta, arrays


def _restore(template, meta, arrays):
    paths, leaves, definition = _paths_and_leaves(template)
    if paths != meta["paths"] or len(leaves) != len(arrays):
        raise ValueError("pytree contract mismatch")
    for expected, arr in zip(leaves, arrays):
        if tuple(expected.shape) != arr.shape or np.dtype(expected.dtype) != arr.dtype:
            raise ValueError("parameter/state shape or dtype mismatch")
    state = jax.tree_util.tree_unflatten(definition, [jnp.asarray(a) for a in arrays])
    if int(state.step) != meta["step"] or int(state.optimizer.count) != meta["step"]:
        raise ValueError("optimizer/step mismatch")
    return state


def load_checkpoint(trainer, path):
    meta, arrays = _read(path)
    if meta["environment"] != environment():
        raise ValueError("resume environment mismatch")
    if (
        meta["contract_id"] != trainer.contract_id
        or meta["training_data"] != trainer.data.fingerprint
        or meta["u_scale"] != trainer.u_scale
        or meta["runtime_key_digest"] != trainer.runtime_key_digest
    ):
        raise ValueError("resume plan/data/normalization mismatch")
    if not 0 <= meta["step"] <= trainer.config.steps:
        raise ValueError("checkpoint step")
    state = _restore(trainer.state, meta, arrays)
    trainer.state = state
    # Compiled executable is shape-compatible, but state is restored from bytes.
    return meta


def load_inference(path, *, strict_environment=True):
    """Load params/task without training labels. Cross-environment inference is opt-in.

    Disabling strict_environment does NOT waive source/schema/integrity checks
    and makes no numerical reproduction claim. Training resume remains strict.
    """
    meta, arrays = _read(path)
    if strict_environment and meta["environment"] != environment():
        raise ValueError("inference environment mismatch")
    model = ModelConfig(**meta["model"])
    task = TaskConfig(**meta["task"])
    train = TrainConfig(**meta["train"])
    if identity(model, task, train) != meta["contract_id"]:
        raise ValueError("configuration integrity mismatch")
    predictor = Predictor(model, task, meta["u_scale"])
    params = predictor.model.init(jax.random.PRNGKey(0))
    template = TrainState(
        params,
        init_adam(params),
        params,
        jax.random.PRNGKey(0),
        jnp.array(0, jnp.int32),
    )
    state = _restore(template, meta, arrays)
    params = state.params if train.inference_weights == "params" else state.ema
    return predictor, params, meta
