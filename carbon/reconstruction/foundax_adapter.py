"""Pinned Foundax 0.2.0 FNO adapter for bounded C-02 development use.

The adapter owns training, explicit Carbon RNG consumption and a closed NPZ
checkpoint.  It does not import jNO, Orbax, pickle, evaluation labels at
inference, or any accelerator package.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

import equinox as eqx
import foundax
import jax
import jax.numpy as jnp
import jaxlib
import numpy as np
import optax

from carbon.reconstruction._vendor.carbon_jax_lab.config import (
    TaskConfig,
    TrainConfig,
    canonical_json,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.scaling import BurgersPhysicalScaling

FOUNDAX_REVISION = "b02b1da52bb03cfad8e437983fc1d1e411e78b04"
FOUNDAX_WHEEL_SHA256 = (
    "9240526f8bcf9860033807404c6e2402dfb10a73ed75088409c37aa58a6fc9b2"
)
FOUNDAX_LICENSE = "EPL-2.0"
FOUNDAX_LICENSE_SHA256 = (
    "209fe24bf55677bbf81c2b0481c1403201fab57b3b4c609971eba4ec8162b99c"
)
_MAX_ARRAY_BYTES = 1 << 30
_MAX_LEAVES = 10_000


class NonFiniteTrainingError(FloatingPointError):
    pass


class CancelledTraining(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FoundaxModelConfig:
    kind: str
    width: int
    depth: int
    n_modes: int
    linear_conv: bool
    dropout_rate: float

    def __post_init__(self) -> None:
        if self.kind != "foundax_fno1d":
            raise ValueError("unsupported Foundax backbone")
        for field in ("width", "depth", "n_modes"):
            if type(getattr(self, field)) is not int or getattr(self, field) < 1:
                raise ValueError(f"{field} must be a positive integer")
        if type(self.linear_conv) is not bool or self.linear_conv:
            raise ValueError("periodic Burgers requires circular Foundax convolution")
        if (
            type(self.dropout_rate) is not float
            or not math.isfinite(self.dropout_rate)
            or self.dropout_rate != 0.0
        ):
            raise ValueError("dropout is not supported by the deterministic profile")


def _root_key(material: bytes):
    if type(material) is not bytes or len(material) != 32:
        raise ValueError("runtime key must contain exactly 32 bytes")
    # The legacy-shaped uint32 key is deliberate: checkpoint leaves stay plain
    # numeric arrays while all 256 owner-derived bits are still folded in.
    key = jax.random.PRNGKey(0)
    for offset in range(0, 32, 4):
        key = jax.random.fold_in(
            key, int.from_bytes(material[offset : offset + 4], "big")
        )
    return key


def _make_model(config: FoundaxModelConfig, key):
    return foundax.fno1d(
        in_features=4,
        hidden_channels=config.width,
        n_modes=config.n_modes,
        d_vars=1,
        linear_conv=config.linear_conv,
        n_layers=config.depth,
        n_steps=1,
        norm=None,
        training=True,
        dropout_rate=config.dropout_rate,
        key=key,
    )


def _optimizer(config: TrainConfig):
    schedule = optax.warmup_cosine_decay_schedule(
        init_value=config.learning_rate / max(1, config.warmup_steps),
        peak_value=config.learning_rate,
        warmup_steps=config.warmup_steps,
        decay_steps=config.steps,
        end_value=config.learning_rate * config.min_learning_rate_ratio,
    )
    return optax.chain(
        optax.clip_by_global_norm(config.clip_norm),
        optax.adamw(
            schedule,
            b1=config.beta1,
            b2=config.beta2,
            eps=config.adam_epsilon,
            weight_decay=config.weight_decay,
        ),
    )


class FoundaxState(NamedTuple):
    model: object
    optimizer: object
    ema: object
    rng: jax.Array
    step: jax.Array


class Predictor:
    def __init__(self, task: TaskConfig, u_scale: float):
        self.task = task
        self.u_scale = float(u_scale)
        self.physical_scaling = BurgersPhysicalScaling(
            task.domain_length,
            task.time_scale,
            task.velocity_scale,
            task.physical_unit_system,
        )

    def __call__(self, model, u0, nu, t, positions):
        scaling = self.physical_scaling
        u_hat = u0 / scaling.velocity_scale
        numerical_u_scale = self.u_scale / scaling.velocity_scale
        nu_hat = nu * scaling.time_scale / scaling.length_scale**2
        numerical_nu_scale = (
            self.task.nu_scale * scaling.time_scale / scaling.length_scale**2
        )
        t_hat = t / scaling.time_scale
        x_hat = positions / scaling.length_scale

        def one(field, viscosity, requested_time):
            features = jnp.stack(
                (
                    field / numerical_u_scale,
                    jnp.broadcast_to(viscosity / numerical_nu_scale, field.shape),
                    jnp.broadcast_to(requested_time, field.shape),
                    x_hat,
                ),
                axis=-1,
            )
            raw = model(features)[0, :, 0]
            prediction = self.u_scale * raw
            if self.task.hard_initial_condition:
                prediction = (
                    field * scaling.velocity_scale + requested_time * prediction
                )
            if self.task.enforce_mean:
                physical_initial = field * scaling.velocity_scale
                prediction = (
                    prediction - jnp.mean(prediction) + jnp.mean(physical_initial)
                )
            return prediction

        return jax.vmap(one)(u_hat, nu_hat, t_hat)


class Trainer:
    def __init__(
        self,
        model_config: FoundaxModelConfig,
        task_config: TaskConfig,
        train_config: TrainConfig,
        data: Trajectories,
        *,
        runtime_key_material: bytes,
    ) -> None:
        if type(data) is not Trajectories or data.role != "train":
            raise ValueError("Foundax training requires declared TRAIN trajectories")
        if data.domain_length != task_config.domain_length:
            raise ValueError("domain mismatch")
        if data.times.max() > task_config.time_scale + 1e-12:
            raise ValueError("time scale does not cover TRAIN times")
        if model_config.n_modes > data.initial.shape[1] // 2 + 1:
            raise ValueError("Foundax mode count exceeds the training grid")
        if (
            train_config.microbatches != 1
            or train_config.relative_loss
            or train_config.h1_weight != 0.0
            or train_config.pde_weight != 0.0
            or train_config.physics_warmup_steps != 0
        ):
            raise ValueError("unsupported Foundax training option")
        self.model_config = model_config
        self.task_config = task_config
        self.config = train_config
        self.data = data
        self.u_scale = max(
            float(np.sqrt(np.mean(data.initial.astype(np.float64) ** 2))), 1e-8
        )
        self.predictor = Predictor(task_config, self.u_scale)
        self.physical_scaling = self.predictor.physical_scaling
        self.physical_scaling.assert_representable("float32")
        root = _root_key(runtime_key_material)
        init_key, batch_key = jax.random.split(root)
        model = _make_model(model_config, init_key)
        self.tx = _optimizer(train_config)
        optimizer_state = self.tx.init(eqx.filter(model, eqx.is_inexact_array))
        self.state = FoundaxState(
            model,
            optimizer_state,
            model,
            batch_key,
            jnp.array(0, dtype=jnp.int32),
        )
        self.runtime_key_digest = hashlib.sha256(runtime_key_material).hexdigest()
        self.arrays = tuple(
            jnp.asarray(array, dtype=jnp.float32)
            for array in (
                data.initial,
                data.viscosity,
                data.times,
                data.solution,
                data.positions,
            )
        )
        self.timing = {"compile_seconds": 0.0, "train_execution_seconds": 0.0}
        self._compiled = None
        self._step_fn = eqx.filter_jit(self._step)

    def _loss(self, model, batch, positions):
        u0, nu, requested_time, target = batch
        prediction = self.predictor(model, u0, nu, requested_time, positions)
        difference = (prediction - target) / self.u_scale
        return jnp.mean(difference * difference)

    def _step(self, state: FoundaxState, arrays):
        u0, nu, times, solution, positions = arrays
        rng, case_key, time_key = jax.random.split(state.rng, 3)
        count = self.config.batch_size * self.config.microbatches
        cases = jax.random.randint(case_key, (count,), 0, u0.shape[0])
        offsets = jax.random.randint(time_key, (count,), 0, times.shape[1])
        batch = (u0[cases], nu[cases], times[cases, offsets], solution[cases, offsets])
        loss, gradients = eqx.filter_value_and_grad(self._loss)(
            state.model, batch, positions
        )
        params = eqx.filter(state.model, eqx.is_inexact_array)
        updates, optimizer_state = self.tx.update(gradients, state.optimizer, params)
        model = eqx.apply_updates(state.model, updates)
        ema = jax.tree.map(
            lambda old, new: (
                self.config.ema_decay * old + (1.0 - self.config.ema_decay) * new
                if eqx.is_inexact_array(old)
                else old
            ),
            state.ema,
            model,
        )
        proposed = FoundaxState(model, optimizer_state, ema, rng, state.step + 1)
        leaves = [leaf for leaf in jax.tree.leaves(proposed) if eqx.is_array(leaf)]
        finite = jnp.isfinite(loss) & jnp.all(
            jnp.stack([jnp.all(jnp.isfinite(leaf)) for leaf in leaves])
        )
        accepted = jax.tree.map(
            lambda new, old: jnp.where(finite, new, old) if eqx.is_array(new) else old,
            proposed,
            state,
        )
        return accepted, (loss, finite)

    def compile(self) -> None:
        if self._compiled is None:
            started = time.perf_counter()
            self._compiled = self._step_fn.lower(self.state, self.arrays).compile()
            self.timing["compile_seconds"] += time.perf_counter() - started

    def fit(self, until_step=None, cancel=None, wall_budget_seconds=None):
        stop = self.config.steps if until_step is None else until_step
        if (
            type(stop) is not int
            or not int(self.state.step) <= stop <= self.config.steps
        ):
            raise ValueError("invalid stop step")
        if wall_budget_seconds is not None and (
            type(wall_budget_seconds) not in (int, float)
            or not math.isfinite(wall_budget_seconds)
            or wall_budget_seconds <= 0
        ):
            raise ValueError("wall budget")
        budget_started = time.perf_counter()
        self.compile()
        started = time.perf_counter()
        try:
            while int(self.state.step) < stop:
                if cancel is not None and cancel():
                    raise CancelledTraining("cancelled at an optimizer-step boundary")
                if (
                    wall_budget_seconds is not None
                    and time.perf_counter() - budget_started > wall_budget_seconds
                ):
                    raise CancelledTraining("development wall budget exhausted")
                proposed, metrics = self._compiled(self.state, self.arrays)
                jax.block_until_ready((proposed, metrics))
                if not bool(metrics[1]):
                    raise NonFiniteTrainingError("nonfinite Foundax update rejected")
                self.state = proposed
        finally:
            self.timing["train_execution_seconds"] += time.perf_counter() - started
        return self.state


def environment() -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "jax": jax.__version__,
        "jaxlib": jaxlib.__version__,
        "numpy": np.__version__,
        "scipy": importlib.metadata.version("scipy"),
        "chex": importlib.metadata.version("chex"),
        "einops": importlib.metadata.version("einops"),
        "pyyaml": importlib.metadata.version("pyyaml"),
        "backend": jax.default_backend(),
        "x64": bool(jax.config.jax_enable_x64),
        "platform": platform.system(),
        "machine": platform.machine(),
        "foundax": foundax.__version__,
        "equinox": eqx.__version__,
        "optax": optax.__version__,
    }


def _paths_and_leaves(tree):
    pairs, definition = jax.tree_util.tree_flatten_with_path(tree)
    return (
        [jax.tree_util.keystr(path) for path, _ in pairs],
        [v for _, v in pairs],
        definition,
    )


def _template(
    model: FoundaxModelConfig, task: TaskConfig, train: TrainConfig, u_scale: float
):
    instance = _make_model(model, jax.random.PRNGKey(0))
    tx = _optimizer(train)
    return FoundaxState(
        instance,
        tx.init(eqx.filter(instance, eqx.is_inexact_array)),
        instance,
        jax.random.PRNGKey(0),
        jnp.array(0, dtype=jnp.int32),
    )


def save_checkpoint(trainer: Trainer, path: Path) -> dict[str, object]:
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError("checkpoint is immutable")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".foundax-checkpoint-", dir=path.parent))
    try:
        paths, leaves, _ = _paths_and_leaves(trainer.state)
        arrays = {
            f"leaf_{i:05d}": np.asarray(jax.device_get(v)) for i, v in enumerate(leaves)
        }
        if (
            not arrays
            or len(arrays) > _MAX_LEAVES
            or any(
                array.dtype.hasobject or not np.isfinite(array).all()
                for array in arrays.values()
            )
        ):
            raise ValueError("invalid Foundax checkpoint state")
        np.savez_compressed(staging / "state.npz", **arrays)
        state_digest = hashlib.sha256((staging / "state.npz").read_bytes()).hexdigest()
        metadata = {
            "schema": "carbon-foundax-fno-checkpoint.v1",
            "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
            "source_id": FOUNDAX_WHEEL_SHA256,
            "source_revision": FOUNDAX_REVISION,
            "model": asdict(trainer.model_config),
            "task": asdict(trainer.task_config),
            "train": asdict(trainer.config),
            "training_data": trainer.data.fingerprint,
            "training_grid_points": trainer.data.initial.shape[1],
            "u_scale": trainer.u_scale,
            "step": int(trainer.state.step),
            "runtime_key_digest": trainer.runtime_key_digest,
            "physical_scaling": trainer.physical_scaling.to_dict(),
            "physical_scaling_digest": trainer.physical_scaling.digest,
            "environment": environment(),
            "state_sha256": state_digest,
            "paths": paths,
            "leaves": [
                {"shape": list(array.shape), "dtype": array.dtype.str}
                for array in arrays.values()
            ],
        }
        (staging / "manifest.json").write_text(canonical_json(metadata) + "\n")
        for member in (staging / "state.npz", staging / "manifest.json"):
            with member.open("rb") as stream:
                os.fsync(stream.fileno())
        os.rename(staging, path)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return metadata


_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "source_id",
        "source_revision",
        "model",
        "task",
        "train",
        "training_data",
        "training_grid_points",
        "u_scale",
        "step",
        "runtime_key_digest",
        "physical_scaling",
        "physical_scaling_digest",
        "environment",
        "state_sha256",
        "paths",
        "leaves",
    }
)


def _closed_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate checkpoint member")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
    )


def _read(path: Path):
    path = Path(path)
    if (
        path.is_symlink()
        or not path.is_dir()
        or {p.name for p in path.iterdir()} != {"manifest.json", "state.npz"}
    ):
        raise ValueError("Foundax checkpoint members")
    manifest_path = path / "manifest.json"
    state_path = path / "state.npz"
    if (
        manifest_path.is_symlink()
        or state_path.is_symlink()
        or manifest_path.stat().st_size > 1 << 22
        or state_path.stat().st_size > _MAX_ARRAY_BYTES
    ):
        raise ValueError("Foundax checkpoint bounds")
    metadata = _closed_json(manifest_path)
    if type(metadata) is not dict or set(metadata) != _FIELDS:
        raise ValueError("Foundax checkpoint manifest")
    if (
        metadata["schema"] != "carbon-foundax-fno-checkpoint.v1"
        or metadata["scope"] != "UNQUALIFIED_PUBLIC_DEVELOPMENT"
    ):
        raise ValueError("Foundax checkpoint schema")
    if (
        metadata["source_id"] != FOUNDAX_WHEEL_SHA256
        or metadata["source_revision"] != FOUNDAX_REVISION
    ):
        raise ValueError("Foundax source mismatch")
    for field, length in (
        ("source_id", 64),
        ("source_revision", 40),
        ("training_data", 64),
        ("runtime_key_digest", 64),
        ("state_sha256", 64),
    ):
        value = metadata[field]
        if (
            type(value) is not str
            or len(value) != length
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"Foundax checkpoint {field}")
    if type(metadata["environment"]) is not dict or set(metadata["environment"]) != {
        "python",
        "jax",
        "jaxlib",
        "numpy",
        "scipy",
        "optax",
        "chex",
        "equinox",
        "einops",
        "foundax",
        "pyyaml",
        "backend",
        "x64",
        "platform",
        "machine",
    }:
        raise ValueError("Foundax environment")
    if (
        any(
            type(metadata["environment"][field]) is not str
            for field in set(metadata["environment"]) - {"x64"}
        )
        or type(metadata["environment"]["x64"]) is not bool
    ):
        raise ValueError("Foundax environment")
    if (
        type(metadata["model"]) is not dict
        or type(metadata["task"]) is not dict
        or type(metadata["train"]) is not dict
    ):
        raise ValueError("Foundax configuration")
    model = FoundaxModelConfig(**metadata["model"])
    task = TaskConfig(**metadata["task"])
    train = TrainConfig(**metadata["train"])
    scaling = BurgersPhysicalScaling.from_dict(metadata["physical_scaling"])
    if scaling.digest != metadata["physical_scaling_digest"]:
        raise ValueError("Foundax scaling mismatch")
    if type(metadata["step"]) is not int or not 0 <= metadata["step"] <= train.steps:
        raise ValueError("Foundax checkpoint step")
    if (
        type(metadata["training_grid_points"]) is not int
        or metadata["training_grid_points"] < 8
    ):
        raise ValueError("Foundax checkpoint grid")
    if (
        type(metadata["u_scale"]) is not float
        or not math.isfinite(metadata["u_scale"])
        or metadata["u_scale"] <= 0
    ):
        raise ValueError("Foundax checkpoint normalization")
    if hashlib.sha256(state_path.read_bytes()).hexdigest() != metadata["state_sha256"]:
        raise ValueError("Foundax state digest")
    if (
        type(metadata["paths"]) is not list
        or type(metadata["leaves"]) is not list
        or len(metadata["paths"]) != len(metadata["leaves"])
        or not 1 <= len(metadata["leaves"]) <= _MAX_LEAVES
        or any(
            type(value) is not str or len(value) > 4096 for value in metadata["paths"]
        )
    ):
        raise ValueError("Foundax checkpoint tree")
    with zipfile.ZipFile(state_path) as archive:
        infos = archive.infolist()
        expected = [f"leaf_{index:05d}.npy" for index in range(len(metadata["leaves"]))]
        if (
            [info.filename for info in infos] != expected
            or any(
                info.flag_bits & 1
                or info.is_dir()
                or Path(info.filename).name != info.filename
                for info in infos
            )
            or sum(info.file_size for info in infos) > _MAX_ARRAY_BYTES
        ):
            raise ValueError("Foundax checkpoint archive")
    with np.load(state_path, allow_pickle=False) as archive:
        arrays = [
            archive[f"leaf_{index:05d}"] for index in range(len(metadata["leaves"]))
        ]
    for array, record in zip(arrays, metadata["leaves"], strict=True):
        if (
            type(record) is not dict
            or set(record) != {"shape", "dtype"}
            or type(record["shape"]) is not list
            or len(record["shape"]) > 16
            or any(type(value) is not int or value < 0 for value in record["shape"])
            or list(array.shape) != record["shape"]
            or array.dtype.str != record["dtype"]
            or array.dtype.hasobject
            or array.dtype.kind not in "biufc"
            or array.nbytes > _MAX_ARRAY_BYTES
            or not np.isfinite(array).all()
        ):
            raise ValueError("Foundax checkpoint leaf")
    return metadata, arrays, model, task, train


def inspect_checkpoint(path: Path) -> dict[str, object]:
    metadata, _, _, _, _ = _read(path)
    return json.loads(canonical_json(metadata))


def _restore(metadata, arrays, model, task, train):
    template = _template(model, task, train, metadata["u_scale"])
    paths, leaves, definition = _paths_and_leaves(template)
    if paths != metadata["paths"] or len(leaves) != len(arrays):
        raise ValueError("Foundax pytree mismatch")
    for expected, array in zip(leaves, arrays, strict=True):
        if (
            tuple(expected.shape) != array.shape
            or np.dtype(expected.dtype) != array.dtype
        ):
            raise ValueError("Foundax state shape or dtype mismatch")
    state = jax.tree_util.tree_unflatten(
        definition, [jnp.asarray(array) for array in arrays]
    )
    if int(state.step) != metadata["step"]:
        raise ValueError("Foundax restored step mismatch")
    return state


def load_checkpoint(trainer: Trainer, path: Path):
    metadata, arrays, model, task, train = _read(path)
    if (
        metadata["environment"] != environment()
        or metadata["training_data"] != trainer.data.fingerprint
        or metadata["runtime_key_digest"] != trainer.runtime_key_digest
        or metadata["physical_scaling_digest"] != trainer.physical_scaling.digest
        or model != trainer.model_config
        or task != trainer.task_config
        or train != trainer.config
    ):
        raise ValueError("Foundax resume binding mismatch")
    trainer.state = _restore(metadata, arrays, model, task, train)
    return metadata


def load_inference(path: Path, *, strict_environment: bool = True):
    metadata, arrays, model_config, task, train = _read(path)
    if strict_environment and metadata["environment"] != environment():
        raise ValueError("Foundax inference environment mismatch")
    state = _restore(metadata, arrays, model_config, task, train)
    model = state.model if train.inference_weights == "params" else state.ema
    return Predictor(task, metadata["u_scale"]), model, metadata


__all__ = [
    "CancelledTraining",
    "FoundaxModelConfig",
    "NonFiniteTrainingError",
    "Predictor",
    "Trainer",
    "environment",
    "inspect_checkpoint",
    "load_checkpoint",
    "load_inference",
    "save_checkpoint",
]
