"""Lazy JAX execution for bounded, public, development-only reconstruction."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from carbon.construction import ResolvedConstructionPlan
from carbon.execution import ExecutionAttemptRef
from carbon.reconstruction.model import (
    EnvironmentEligibility,
    PredictionReceipt,
    PublicTrainingArchive,
    ReconstructionFailure,
    ReconstructionProfile,
    ReconstructionReceipt,
    ReconstructionStatus,
)
from carbon.reconstruction.profile import compile_development_profile
from carbon.seeding import DerivedSeed

_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "execution_id",
        "plan_digest",
        "profile_digest",
        "source_digest",
        "environment_digest",
        "observed_environment",
        "observed_environment_digest",
        "environment_eligibility",
        "input_interface_digest",
        "output_interface_digest",
        "training_archive_digest",
        "training_fingerprint",
        "training_role",
        "normalization_scale",
        "randomness_digest",
        "checkpoint_digest",
        "checkpoint_subdirectory",
        "inference_weights",
        "completed_steps",
        "status",
        "compile_seconds",
        "train_execution_seconds",
        "mapping_receipt",
    }
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _execution_id(value: ExecutionAttemptRef) -> str:
    if type(value) is not ExecutionAttemptRef:
        raise ReconstructionFailure("reconstruction.execution_ref.invalid")
    return f"{value.submission_id.value}:{value.attempt_number}"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _tree_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_dir():
        raise ReconstructionFailure("reconstruction.artifact.member_invalid")
    digest = hashlib.sha256()
    for member in sorted(path.rglob("*")):
        if member.is_symlink() or (not member.is_file() and not member.is_dir()):
            raise ReconstructionFailure("reconstruction.artifact.member_invalid")
        if member.is_dir():
            continue
        relative = member.relative_to(path).as_posix()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative.encode("utf-8"))
        digest.update(bytes.fromhex(_file_digest(member)[7:]))
    return "sha256:" + digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > (1 << 22):
        raise ReconstructionFailure("reconstruction.artifact.manifest_invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ReconstructionFailure("reconstruction.artifact.manifest_invalid")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise ReconstructionFailure(
            "reconstruction.artifact.manifest_invalid"
        ) from None
    if type(value) is not dict or set(value) != _MANIFEST_FIELDS:
        raise ReconstructionFailure("reconstruction.artifact.manifest_invalid")
    return value


def _exact_digest(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ReconstructionFailure("reconstruction.artifact.manifest_invalid")
    return value


def _exact_float(value: object) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ReconstructionFailure("reconstruction.artifact.manifest_invalid")
    return value


def _receipt(path: Path, manifest: dict[str, object]) -> ReconstructionReceipt:
    try:
        status = ReconstructionStatus(manifest["status"])
        eligibility = EnvironmentEligibility(manifest["environment_eligibility"])
    except (TypeError, ValueError):
        raise ReconstructionFailure(
            "reconstruction.artifact.manifest_invalid"
        ) from None
    return ReconstructionReceipt(
        artifact_path=path,
        artifact_digest=_tree_digest(path),
        execution_id=manifest["execution_id"],
        plan_digest=_exact_digest(manifest["plan_digest"]),
        profile_digest=_exact_digest(manifest["profile_digest"]),
        training_data_digest=_exact_digest(manifest["training_archive_digest"]),
        randomness_digest=_exact_digest(manifest["randomness_digest"]),
        checkpoint_digest=_exact_digest(manifest["checkpoint_digest"]),
        status=status,
        completed_steps=manifest["completed_steps"],
        compile_seconds=_exact_float(manifest["compile_seconds"]),
        train_execution_seconds=_exact_float(manifest["train_execution_seconds"]),
        source_digest=_exact_digest(manifest["source_digest"]),
        environment_digest=_exact_digest(manifest["environment_digest"]),
        observed_environment_digest=_exact_digest(
            manifest["observed_environment_digest"]
        ),
        environment_eligibility=eligibility,
        input_interface_digest=_exact_digest(manifest["input_interface_digest"]),
        output_interface_digest=_exact_digest(manifest["output_interface_digest"]),
        normalization_scale=_exact_float(manifest["normalization_scale"]),
        inference_weights=manifest["inference_weights"],
    )


def _environment_eligibility(observed: dict[str, object]) -> EnvironmentEligibility:
    common = {
        "jax": "0.9.0.1",
        "jaxlib": "0.9.0.1",
        "numpy": "2.3.5",
        "backend": "cpu",
        "x64": False,
    }
    if not observed.get("python", "").startswith("3.11.") or any(
        observed.get(key) != value for key, value in common.items()
    ):
        raise ReconstructionFailure("reconstruction.runtime.environment_ineligible")
    if observed.get("platform") == "Linux" and observed.get("machine") == "x86_64":
        return EnvironmentEligibility.CANONICAL_DEVELOPMENT
    if observed.get("platform") == "Darwin" and observed.get("machine") == "arm64":
        return EnvironmentEligibility.NATIVE_MAC_DIAGNOSTIC
    raise ReconstructionFailure("reconstruction.runtime.environment_ineligible")


def _validate_artifact(
    path: Path,
    *,
    inspect_checkpoint: Callable[[Path], dict[str, object]],
    execution_id: str | None = None,
    profile: ReconstructionProfile | None = None,
    archive: PublicTrainingArchive | None = None,
    randomness_digest: str | None = None,
    promised_receipt: ReconstructionReceipt | None = None,
) -> ReconstructionReceipt:
    try:
        if path.is_symlink() or not path.is_dir():
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        if {member.name for member in path.iterdir()} != {
            "manifest.json",
            "checkpoint",
        }:
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        manifest = _read_json(path / "manifest.json")
        if manifest["schema"] != "carbon.c02.reconstruction-artifact.v2":
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        if manifest["scope"] != "UNQUALIFIED_PUBLIC_DEVELOPMENT":
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        for field in (
            "execution_id",
            "training_fingerprint",
            "training_role",
            "checkpoint_subdirectory",
            "inference_weights",
            "status",
            "environment_eligibility",
        ):
            if type(manifest[field]) is not str:
                raise ReconstructionFailure(
                    "reconstruction.artifact.reconciliation_required"
                )
        if type(manifest["completed_steps"]) is not int:
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        for field in (
            "compile_seconds",
            "train_execution_seconds",
            "normalization_scale",
        ):
            _exact_float(manifest[field])
        for field in (
            "plan_digest",
            "profile_digest",
            "source_digest",
            "environment_digest",
            "observed_environment_digest",
            "input_interface_digest",
            "output_interface_digest",
            "training_archive_digest",
            "randomness_digest",
            "checkpoint_digest",
        ):
            _exact_digest(manifest[field])
        observed = manifest["observed_environment"]
        if type(observed) is not dict:
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        eligibility = _environment_eligibility(observed)
        if eligibility.value != manifest["environment_eligibility"]:
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        if _tagged(_canonical(observed)) != manifest["observed_environment_digest"]:
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        expected: dict[str, object] = {
            "schema": "carbon.c02.reconstruction-artifact.v2",
            "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
            "training_role": "TRAIN",
            "checkpoint_subdirectory": "checkpoint",
        }
        if execution_id is not None:
            expected["execution_id"] = execution_id
        if profile is not None:
            expected.update(
                {
                    "plan_digest": profile.plan_digest,
                    "profile_digest": profile.profile_digest,
                    "source_digest": profile.source_digest,
                    "environment_digest": profile.environment_digest,
                    "input_interface_digest": profile.input_interface_digest,
                    "output_interface_digest": profile.output_interface_digest,
                    "mapping_receipt": json.loads(profile.mapping_receipt_json),
                }
            )
        if archive is not None:
            expected["training_archive_digest"] = archive.content_digest
        if randomness_digest is not None:
            expected["randomness_digest"] = randomness_digest
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        if _tree_digest(path / "checkpoint") != manifest["checkpoint_digest"]:
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        checkpoint = inspect_checkpoint(path / "checkpoint")
        checkpoint_expected = {
            "training_data": manifest["training_fingerprint"],
            "u_scale": manifest["normalization_scale"],
            "step": manifest["completed_steps"],
            "environment": observed,
            "runtime_key_digest": manifest["randomness_digest"][7:],
            "source_id": manifest["source_digest"][7:],
        }
        if profile is not None:
            checkpoint_expected.update(
                {
                    "model": json.loads(profile.model_config_json),
                    "task": json.loads(profile.task_config_json),
                    "train": json.loads(profile.train_config_json),
                }
            )
        if any(
            checkpoint.get(key) != value for key, value in checkpoint_expected.items()
        ):
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        train = checkpoint["train"]
        if (
            type(train) is not dict
            or train.get("inference_weights") != manifest["inference_weights"]
        ):
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        steps = train.get("steps")
        completed = manifest["completed_steps"]
        status = manifest["status"]
        if (
            type(steps) is not int
            or completed < 0
            or completed > steps
            or (status == ReconstructionStatus.COMPLETE.value) != (completed == steps)
            or status
            not in {
                item.value
                for item in ReconstructionStatus
                if item is not ReconstructionStatus.RECONCILIATION_REQUIRED
            }
        ):
            raise ReconstructionFailure(
                "reconstruction.artifact.reconciliation_required"
            )
        rebuilt = _receipt(path, manifest)
        if promised_receipt is not None and rebuilt != promised_receipt:
            raise ReconstructionFailure("reconstruction.resume.binding_mismatch")
        return rebuilt
    except ReconstructionFailure:
        raise
    except Exception:  # noqa: BLE001 - corrupted artifacts fail closed.
        raise ReconstructionFailure(
            "reconstruction.artifact.reconciliation_required"
        ) from None


def _validate_existing(
    path: Path,
    *,
    inspect_checkpoint: Callable[[Path], dict[str, object]],
    execution_id: str,
    profile: ReconstructionProfile,
    archive: PublicTrainingArchive,
    randomness_digest: str,
) -> ReconstructionReceipt:
    return _validate_artifact(
        path,
        inspect_checkpoint=inspect_checkpoint,
        execution_id=execution_id,
        profile=profile,
        archive=archive,
        randomness_digest=randomness_digest,
    )


def reconstruct(
    *,
    execution_ref: ExecutionAttemptRef,
    plan: ResolvedConstructionPlan,
    training_archive: PublicTrainingArchive,
    derived_seed: DerivedSeed,
    artifact_path: Path,
    until_step: int | None = None,
    cancel: Callable[[], bool] | None = None,
    wall_budget_seconds: float | None = None,
    resume_from: ReconstructionReceipt | None = None,
) -> ReconstructionReceipt:
    """Train or resume exactly one public development artifact."""
    execution_id = _execution_id(execution_ref)
    if type(training_archive) is not PublicTrainingArchive:
        raise ReconstructionFailure("reconstruction.archive.invalid")
    if type(derived_seed) is not DerivedSeed:
        raise ReconstructionFailure("reconstruction.seed.invalid")
    if not isinstance(artifact_path, Path) or not artifact_path.is_absolute():
        raise ReconstructionFailure("reconstruction.artifact.path_invalid")
    profile = compile_development_profile(plan)
    key_material = derived_seed.as_backend_bytes()
    randomness_digest = _tagged(key_material)
    if not training_archive.path.is_file() or training_archive.path.is_symlink():
        raise ReconstructionFailure("reconstruction.archive.path_invalid")
    if (
        training_archive.path.stat().st_size > (1 << 30)
        or _file_digest(training_archive.path) != training_archive.content_digest
    ):
        raise ReconstructionFailure("reconstruction.archive.digest_mismatch")
    parent = artifact_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise ReconstructionFailure("reconstruction.artifact.path_invalid")

    # Optional numerical imports remain entirely below the execution boundary.
    try:
        from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
            environment as observed_environment,
        )
        from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
            inspect_checkpoint,
            load_checkpoint,
            save_checkpoint,
        )
        from carbon.reconstruction._vendor.carbon_jax_lab.config import (
            ModelConfig,
            TaskConfig,
            TrainConfig,
        )
        from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
        from carbon.reconstruction._vendor.carbon_jax_lab.training import (
            CancelledTraining,
            NonFiniteTrainingError,
            Trainer,
        )
    except ImportError:
        raise ReconstructionFailure("reconstruction.runtime.unavailable") from None

    if artifact_path.exists() or artifact_path.is_symlink():
        return _validate_existing(
            artifact_path,
            inspect_checkpoint=inspect_checkpoint,
            execution_id=execution_id,
            profile=profile,
            archive=training_archive,
            randomness_digest=randomness_digest,
        )

    try:
        data = Trajectories.load(training_archive.path)
        if data.role != "train":
            raise ReconstructionFailure("reconstruction.archive.role_invalid")
        model = ModelConfig(**json.loads(profile.model_config_json))
        task = TaskConfig(**json.loads(profile.task_config_json))
        train = TrainConfig(**json.loads(profile.train_config_json))
        trainer = Trainer(model, task, train, data, runtime_key_material=key_material)
    except ReconstructionFailure:
        raise
    except Exception:  # noqa: BLE001 - numerical archive parsers fail closed.
        raise ReconstructionFailure("reconstruction.archive.content_invalid") from None

    if resume_from is not None:
        if type(resume_from) is not ReconstructionReceipt:
            raise ReconstructionFailure("reconstruction.resume.receipt_invalid")
        _validate_artifact(
            resume_from.artifact_path,
            inspect_checkpoint=inspect_checkpoint,
            execution_id=execution_id,
            profile=profile,
            archive=training_archive,
            randomness_digest=randomness_digest,
            promised_receipt=resume_from,
        )
        try:
            load_checkpoint(trainer, resume_from.artifact_path / "checkpoint")
        except Exception:  # noqa: BLE001 - checkpoint parser failures are private.
            raise ReconstructionFailure(
                "reconstruction.resume.checkpoint_invalid"
            ) from None

    status = ReconstructionStatus.COMPLETE
    try:
        trainer.fit(
            until_step=until_step,
            cancel=cancel,
            wall_budget_seconds=wall_budget_seconds,
        )
        if int(trainer.state.step) < train.steps:
            status = ReconstructionStatus.PARTIAL
    except CancelledTraining:
        status = ReconstructionStatus.CANCELLED
    except NonFiniteTrainingError:
        status = ReconstructionStatus.NONFINITE_REJECTED

    staging = Path(tempfile.mkdtemp(prefix=".c02-artifact-", dir=parent))
    try:
        checkpoint = staging / "checkpoint"
        save_checkpoint(trainer, checkpoint)
        checkpoint_digest = _tree_digest(checkpoint)
        observed = observed_environment()
        eligibility = _environment_eligibility(observed)
        manifest = {
            "schema": "carbon.c02.reconstruction-artifact.v2",
            "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
            "execution_id": execution_id,
            "plan_digest": profile.plan_digest,
            "profile_digest": profile.profile_digest,
            "source_digest": profile.source_digest,
            "environment_digest": profile.environment_digest,
            "observed_environment": observed,
            "observed_environment_digest": _tagged(_canonical(observed)),
            "environment_eligibility": eligibility.value,
            "input_interface_digest": profile.input_interface_digest,
            "output_interface_digest": profile.output_interface_digest,
            "training_archive_digest": training_archive.content_digest,
            "training_fingerprint": data.fingerprint,
            "training_role": "TRAIN",
            "normalization_scale": trainer.u_scale,
            "randomness_digest": randomness_digest,
            "checkpoint_digest": checkpoint_digest,
            "checkpoint_subdirectory": "checkpoint",
            "inference_weights": train.inference_weights,
            "completed_steps": int(trainer.state.step),
            "status": status.value,
            "compile_seconds": float(trainer.timing["compile_seconds"]),
            "train_execution_seconds": float(trainer.timing["train_execution_seconds"]),
            "mapping_receipt": json.loads(profile.mapping_receipt_json),
        }
        manifest_path = staging / "manifest.json"
        with manifest_path.open("xb") as stream:
            stream.write(_canonical(manifest) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(staging, artifact_path)
        if hasattr(os, "O_DIRECTORY"):
            descriptor = os.open(parent, os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return _validate_artifact(
        artifact_path,
        inspect_checkpoint=inspect_checkpoint,
        execution_id=execution_id,
        profile=profile,
        archive=training_archive,
        randomness_digest=randomness_digest,
    )


def predict(
    receipt: ReconstructionReceipt,
    *,
    initial: object,
    viscosity: object,
    requested_times: object,
    positions: object,
    batch_size: int = 32,
) -> tuple[object, PredictionReceipt]:
    """Reload an artifact and predict without accepting any target labels."""
    if type(receipt) is not ReconstructionReceipt:
        raise ReconstructionFailure("reconstruction.prediction.receipt_invalid")
    if type(batch_size) is not int or batch_size < 1:
        raise ReconstructionFailure("reconstruction.prediction.batch_size_invalid")
    try:
        import jax
        import jax.numpy as jnp
        import numpy as np

        from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
            inspect_checkpoint,
            load_inference,
        )
    except ImportError:
        raise ReconstructionFailure("reconstruction.runtime.unavailable") from None

    try:
        validated = _validate_artifact(
            receipt.artifact_path,
            inspect_checkpoint=inspect_checkpoint,
            promised_receipt=receipt,
        )
    except ReconstructionFailure:
        raise ReconstructionFailure(
            "reconstruction.prediction.artifact_mismatch"
        ) from None
    if validated.status is not ReconstructionStatus.COMPLETE:
        raise ReconstructionFailure("reconstruction.prediction.artifact_status_invalid")

    try:
        u0 = np.asarray(initial)
        nu = np.asarray(viscosity)
        times = np.asarray(requested_times)
        x = np.asarray(positions)
        if (
            u0.ndim != 2
            or u0.shape[0] < 1
            or u0.shape[1] < 1
            or nu.shape != (u0.shape[0],)
            or times.ndim != 2
            or times.shape[0] != u0.shape[0]
            or x.shape != (u0.shape[1],)
        ):
            raise ValueError
        if times.shape[1] < 1 or not all(
            np.issubdtype(a.dtype, np.floating) and np.isfinite(a).all()
            for a in (u0, nu, times, x)
        ):
            raise ValueError
        if (nu <= 0).any() or (times < 0).any():
            raise ValueError
        with np.errstate(over="ignore", invalid="ignore"):
            u0_f32 = u0.astype(np.float32)
            nu_f32 = nu.astype(np.float32)
            times_f32 = times.astype(np.float32)
            x_f32 = x.astype(np.float32)
        if not all(
            np.isfinite(array).all() for array in (u0_f32, nu_f32, times_f32, x_f32)
        ):
            raise ValueError
    except ReconstructionFailure:
        raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:  # noqa: BLE001 - arbitrary array providers fail closed.
        raise ReconstructionFailure(
            "reconstruction.prediction.request_invalid"
        ) from None

    try:
        predictor, params, _ = load_inference(
            receipt.artifact_path / "checkpoint", strict_environment=True
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:  # noqa: BLE001 - runtime initialization is a backend failure.
        raise ReconstructionFailure(
            "reconstruction.prediction.backend_unavailable"
        ) from None

    try:
        domain_length = predictor.task.domain_length
        expected_x = np.arange(u0.shape[1], dtype=np.float64) * (
            domain_length / u0.shape[1]
        )
        if not np.array_equal(x_f32, expected_x.astype(np.float32)):
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ReconstructionFailure(
            "reconstruction.prediction.request_invalid"
        ) from None

    try:
        started = time.perf_counter()
        outputs = []
        total = u0.shape[0] * times.shape[1]
        apply = jax.jit(predictor.__call__)
        for start in range(0, total, batch_size):
            ids = np.arange(start, min(start + batch_size, total))
            cases = ids // times.shape[1]
            offsets = ids % times.shape[1]
            value = apply(
                params,
                jnp.asarray(u0_f32[cases]),
                jnp.asarray(nu_f32[cases]),
                jnp.asarray(times_f32[cases, offsets]),
                jnp.asarray(x_f32),
            )
            value = np.asarray(jax.block_until_ready(value))
            expected_shape = (len(ids), u0.shape[1])
            if value.shape != expected_shape or value.dtype != np.dtype("float32"):
                raise ReconstructionFailure(
                    "reconstruction.prediction.output_contract_invalid"
                )
            if not np.isfinite(value).all():
                raise ReconstructionFailure(
                    "reconstruction.prediction.output_nonfinite"
                )
            outputs.append(value)
        result = np.concatenate(outputs, axis=0).reshape(
            u0.shape[0], times.shape[1], u0.shape[1]
        )
        elapsed = float(time.perf_counter() - started)
    except ReconstructionFailure:
        raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:  # noqa: BLE001 - numerical failures are non-echoing.
        raise ReconstructionFailure(
            "reconstruction.prediction.numerical_failure"
        ) from None

    def framed_array_digest(named_arrays: tuple[tuple[str, object], ...]) -> str:
        digest = hashlib.sha256()
        for name, value in named_arrays:
            array = np.ascontiguousarray(value)
            metadata = _canonical(
                {"name": name, "dtype": array.dtype.str, "shape": list(array.shape)}
            )
            digest.update(len(metadata).to_bytes(8, "big"))
            digest.update(metadata)
            digest.update(len(array.tobytes()).to_bytes(8, "big"))
            digest.update(array.tobytes())
        return "sha256:" + digest.hexdigest()

    request_digest = framed_array_digest(
        (
            ("initial", u0),
            ("viscosity", nu),
            ("requested_times", times),
            ("positions", x),
        )
    )
    output_digest = framed_array_digest((("prediction", result),))
    prediction_receipt = PredictionReceipt(
        artifact_digest=receipt.artifact_digest,
        request_digest=request_digest,
        output_digest=output_digest,
        cases=u0.shape[0],
        times=times.shape[1],
        points=u0.shape[1],
        execution_seconds=elapsed,
    )
    return result, prediction_receipt


__all__ = ["predict", "reconstruct"]
