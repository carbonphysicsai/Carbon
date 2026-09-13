"""Trusted parent for the bounded C-03 Docker reconstruction worker.

The parent owns C-01 association and validates all worker output.  Docker is
the enforcement boundary; the worker's own diagnostics are never authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from carbon.construction import ResolvedConstructionPlan
from carbon.construction.plan import resolved_construction_plan_canonical_bytes
from carbon.execution import (
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionScope,
    ExecutionStage,
    PartialWorkRef,
    QueueClaim,
    ReconciliationDisposition,
)
from carbon.reconstruction.model import (
    PredictionReceipt,
    PublicTrainingArchive,
    ReconstructionFailure,
    ReconstructionReceipt,
    ReconstructionStatus,
)
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    development_replicate_digest,
    development_request_digest,
)
from carbon.reconstruction.service import validate_reconstruction_artifact
from carbon.reconstruction.worker_profile import (
    load_development_worker_profile,
    verify_profile_sources,
)
from carbon.resource_policy import BoundReconstructionReplicate
from carbon.seeding import DerivedSeed

_RESULT_FIELDS = frozenset(
    {
        "schema",
        "scope",
        "disposition",
        "worker_profile_digest",
        "image_id",
        "source_revision",
        "submission_id",
        "attempt_number",
        "plan_digest",
        "archive_digest",
        "randomness_digest",
        "prediction_request_digest",
        "receipt",
        "prediction",
        "observations",
        "replicate_id",
        "replicate_digest",
        "resource_policy_digest",
        "resource_class_digest",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "request_validation_seconds",
        "reconstruction_total_seconds",
        "jax_compile_seconds",
        "training_updates_seconds",
        "checkpoint_load_seconds",
        "checkpoint_save_seconds",
        "checkpoint_timing_missing_reason",
        "prediction_seconds",
        "worker_wall_seconds",
        "worker_process_cpu_seconds",
        "worker_reported_max_rss_bytes",
        "evidence_class",
    }
)


class WorkerDisposition(str, Enum):
    COMPLETE = "COMPLETE"
    CANCELLED_NON_SCIENTIFIC = "CANCELLED_NON_SCIENTIFIC"
    WALL_LIMIT_REACHED = "WALL_LIMIT_REACHED"
    MEMORY_LIMIT_REACHED = "MEMORY_LIMIT_REACHED"
    WORKER_FAILED = "WORKER_FAILED"
    OUTPUT_REJECTED = "OUTPUT_REJECTED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


@dataclass(frozen=True, slots=True, repr=False)
class WorkerDispatch:
    claim: QueueClaim
    container_id: str
    run_directory: Path
    request_digest: str
    profile_digest: str
    image_id: str
    source_revision: str
    preparation_observations: tuple[tuple[str, float | int | None, str], ...]


@dataclass(frozen=True, slots=True, repr=False)
class WorkerRunResult:
    disposition: WorkerDisposition
    execution_ref: ExecutionAttemptRef
    request_digest: str
    profile_digest: str
    image_id: str
    artifact_digest: str | None
    prediction_digest: str | None
    observations: tuple[tuple[str, float | int | None, str], ...]
    diagnostic_bytes: int
    diagnostic_digest: str
    cleanup_complete: bool


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    payload = _canonical(value) + b"\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _safe_tree_size(path: Path, *, maximum: int) -> int:
    total = 0
    if path.is_symlink() or not path.is_dir():
        raise ReconstructionFailure("reconstruction.worker.output_invalid")
    for members, member in enumerate(path.rglob("*"), start=1):
        if (
            members > 4096
            or member.is_symlink()
            or not (member.is_file() or member.is_dir())
        ):
            raise ReconstructionFailure("reconstruction.worker.output_invalid")
        if member.is_file():
            total += member.stat().st_size
            if total > maximum:
                raise ReconstructionFailure("reconstruction.worker.output_oversized")
    return total


def _load_json(path: Path, *, maximum: int) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ReconstructionFailure("reconstruction.worker.output_invalid")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_bytes(),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise ReconstructionFailure("reconstruction.worker.output_invalid") from None
    if type(value) is not dict:
        raise ReconstructionFailure("reconstruction.worker.output_invalid")
    return value


def _receipt_body(value: ReconstructionReceipt) -> dict[str, object]:
    return {
        "artifact_digest": value.artifact_digest,
        "checkpoint_digest": value.checkpoint_digest,
        "completed_steps": value.completed_steps,
        "compile_seconds": value.compile_seconds,
        "environment_digest": value.environment_digest,
        "environment_eligibility": value.environment_eligibility.value,
        "execution_id": value.execution_id,
        "inference_weights": value.inference_weights,
        "input_interface_digest": value.input_interface_digest,
        "normalization_scale": value.normalization_scale,
        "observed_environment_digest": value.observed_environment_digest,
        "output_interface_digest": value.output_interface_digest,
        "physical_scaling_digest": value.physical_scaling_digest,
        "physical_unit_system": value.physical_unit_system,
        "plan_digest": value.plan_digest,
        "profile_digest": value.profile_digest,
        "randomness_digest": value.randomness_digest,
        "source_digest": value.source_digest,
        "status": value.status.value,
        "train_execution_seconds": value.train_execution_seconds,
        "training_data_digest": value.training_data_digest,
    }


def _prediction_digest(path: Path) -> tuple[object, str]:
    if path.is_symlink() or not path.is_file():
        raise ReconstructionFailure("reconstruction.worker.prediction_invalid")
    try:
        import numpy as np

        with np.load(path, allow_pickle=False) as stored:
            if stored.files != ["prediction"]:
                raise ValueError
            array = stored["prediction"].copy()
        if (
            array.dtype != np.dtype("float32")
            or array.ndim != 3
            or not np.isfinite(array).all()
        ):
            raise ValueError
        contiguous = np.ascontiguousarray(array)
        metadata = _canonical(
            {
                "name": "prediction",
                "dtype": contiguous.dtype.str,
                "shape": list(contiguous.shape),
            }
        )
        digest = hashlib.sha256()
        digest.update(len(metadata).to_bytes(8, "big"))
        digest.update(metadata)
        body = contiguous.tobytes()
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
        return array, "sha256:" + digest.hexdigest()
    except ReconstructionFailure:
        raise
    except Exception:  # noqa: BLE001 - untrusted bytes fail closed.
        raise ReconstructionFailure(
            "reconstruction.worker.prediction_invalid"
        ) from None


def build_development_worker_image(
    repository: Path, *, docker: str = "docker"
) -> tuple[str, str]:
    """Build the exact clean source revision and return immutable image identity."""

    repository = repository.resolve(strict=True)
    profile = load_development_worker_profile()
    verify_profile_sources(profile, repository)
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout:
        raise ReconstructionFailure("reconstruction.worker.source_dirty")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tag = f"carbon-c03-worker:{revision[:16]}"
    subprocess.run(
        [
            docker,
            "build",
            "--platform",
            "linux/amd64",
            "--pull",
            "--file",
            str(repository / ".worker/Dockerfile"),
            "--build-arg",
            f"CARBON_SOURCE_REVISION={revision}",
            "--tag",
            tag,
            str(repository),
        ],
        check=True,
    )
    image_id = subprocess.run(
        [docker, "image", "inspect", "--format", "{{.Id}}", tag],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(image_id) != 71 or not image_id.startswith("sha256:"):
        raise ReconstructionFailure("reconstruction.worker.image_invalid")
    return image_id, revision


class DevelopmentReconstructionWorker:
    """One trusted-host adapter from a C-01 claim to the fixed Docker worker."""

    def __init__(
        self,
        queue: DurableExecutionQueue,
        *,
        private_root: Path,
        image_id: str,
        source_revision: str,
        repository: Path,
        docker: str = "docker",
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        if type(queue) is not DurableExecutionQueue:
            raise ReconstructionFailure("reconstruction.worker.queue_invalid")
        if not private_root.is_absolute() or private_root.is_symlink():
            raise ReconstructionFailure("reconstruction.worker.private_root_invalid")
        if len(image_id) != 71 or not image_id.startswith("sha256:"):
            raise ReconstructionFailure("reconstruction.worker.image_invalid")
        if type(source_revision) is not str or len(source_revision) != 40:
            raise ReconstructionFailure("reconstruction.worker.source_invalid")
        self.queue = queue
        self.private_root = private_root
        self.image_id = image_id
        self.source_revision = source_revision
        self.repository = repository.resolve(strict=True)
        self.docker = docker
        self.id_factory = id_factory
        self.profile = load_development_worker_profile()
        verify_profile_sources(self.profile, self.repository)
        self._verify_image()

    def _command(self, *args: str, **kwargs) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self.docker, *args],
                check=True,
                capture_output=True,
                text=True,
                **kwargs,
            )
        except (OSError, subprocess.SubprocessError):
            raise ReconstructionFailure(
                "reconstruction.worker.runtime_unavailable"
            ) from None

    def _verify_image(self) -> None:
        value = self._command("image", "inspect", self.image_id).stdout
        try:
            items = json.loads(value)
            item = items[0]
            labels = item["Config"]["Labels"]
            expected = {
                "org.opencontainers.image.carbon.worker-profile": self.profile.profile_id,
                "org.opencontainers.image.carbon.source-revision": self.source_revision,
                "org.opencontainers.image.carbon.security-state": "REVIEWABLE_NOT_SECURITY_ACCEPTED",
            }
            if (
                type(items) is not list
                or len(items) != 1
                or item["Id"] != self.image_id
                or item["Os"] != "linux"
                or item["Architecture"] != "amd64"
                or item["Config"]["User"] != self.profile.runtime_user
                or any(
                    labels.get(key) != expected_value
                    for key, expected_value in expected.items()
                )
            ):
                raise ValueError
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            raise ReconstructionFailure(
                "reconstruction.worker.image_mismatch"
            ) from None

    def _run_directory(self, ref: ExecutionAttemptRef) -> Path:
        return (
            self.private_root
            / "runs"
            / f"{ref.submission_id.value}-{ref.attempt_number}"
        )

    def prepare(
        self,
        *,
        execution_ref: ExecutionAttemptRef,
        plan: ResolvedConstructionPlan,
        training_archive: PublicTrainingArchive,
        derived_seed: DerivedSeed,
        prediction_request: Mapping[str, object],
        replicate_binding: BoundReconstructionReplicate,
    ) -> WorkerDispatch:
        """Persist a request, claim exactly that attempt, and create but do not start it."""

        validation_started = time.perf_counter()
        profile = compile_development_profile(plan)
        binding = self.queue.binding_for_dispatch(execution_ref)
        if type(replicate_binding) is not BoundReconstructionReplicate:
            raise ReconstructionFailure("reconstruction.worker.replicate_invalid")
        replicate = replicate_binding.replicate_identity
        if (
            binding.scope is not ExecutionScope.FIXTURE_DEVELOPMENT
            or binding.resolved_plan_digest != plan.to_ref().content_digest
            or binding.strategy_hash != plan.strategy_hash
            or binding.reconstruction_policy_digest != profile.profile_digest
            or binding.handle.environment_pin.backend_profile_id
            != self.profile.profile_id
            or binding.handle.environment_pin.container_digest != self.image_id
            or binding.handle.seed_pin.challenge_key != plan.challenge_key
            or training_archive.role != "TRAIN"
            or replicate.challenge_key != plan.challenge_key
            or replicate.construction_plan_ref != plan.to_ref()
            or replicate.policy_ref.content_digest != binding.resource_policy_digest
        ):
            raise ReconstructionFailure("reconstruction.worker.binding_mismatch")
        request_digest = development_request_digest(prediction_request)
        key = derived_seed.as_backend_bytes()
        randomness_digest = _tagged(key)
        expected_replicate_digest = development_replicate_digest(
            binding=replicate_binding,
            execution_ref=execution_ref,
            randomness_digest=randomness_digest,
            training_data_digest=training_archive.content_digest,
            request_digest=request_digest,
        )
        if replicate.replicate_digest != expected_replicate_digest:
            raise ReconstructionFailure("reconstruction.worker.replicate_mismatch")
        validation_seconds = float(time.perf_counter() - validation_started)
        staging_started = time.perf_counter()
        run_directory = self._run_directory(execution_ref)
        if run_directory.exists() or run_directory.is_symlink():
            raise ReconstructionFailure("reconstruction.worker.reconciliation_required")
        input_directory = run_directory / "input"
        collected = run_directory / "collected"
        input_directory.mkdir(parents=True, mode=0o700)
        collected.mkdir(mode=0o700)
        plan_bytes = resolved_construction_plan_canonical_bytes(plan)
        (input_directory / "plan.bin").write_bytes(plan_bytes)
        with (
            training_archive.path.open("rb") as source,
            (input_directory / "training.npz").open("xb") as target,
        ):
            shutil.copyfileobj(source, target, length=1 << 20)
            target.flush()
            os.fsync(target.fileno())
        try:
            import numpy as np

            with (input_directory / "prediction-request.npz").open("xb") as stream:
                np.savez_compressed(
                    stream,
                    initial=prediction_request["initial"],
                    viscosity=prediction_request["viscosity"],
                    requested_times=prediction_request["requested_times"],
                    positions=prediction_request["positions"],
                )
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:  # noqa: BLE001 - participant-like arrays fail closed.
            raise ReconstructionFailure(
                "reconstruction.worker.request_invalid"
            ) from None
        request = {
            "schema": "carbon.c03.worker-request.v1",
            "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
            "worker_profile_id": self.profile.profile_id,
            "worker_profile_digest": self.profile.profile_digest,
            "image_id": self.image_id,
            "source_revision": self.source_revision,
            "submission_id": execution_ref.submission_id.value,
            "attempt_number": execution_ref.attempt_number,
            "challenge_id": plan.challenge_key.challenge_id,
            "challenge_version": plan.challenge_key.version,
            "plan_digest": plan.to_ref().content_digest,
            "archive_digest": training_archive.content_digest,
            "archive_provenance": training_archive.provenance,
            "randomness_hex": key.hex(),
            "randomness_digest": randomness_digest,
            "prediction_request_digest": request_digest,
            "replicate_id": replicate.replicate_id,
            "replicate_digest": replicate.replicate_digest,
            "resource_policy_digest": replicate.policy_ref.content_digest,
            "resource_class_digest": replicate.resource_class_ref.content_digest,
        }
        request_bytes = _canonical(request) + b"\n"
        (input_directory / "request.json").write_bytes(request_bytes)
        for staged in input_directory.iterdir():
            staged.chmod(0o444)
        input_directory.chmod(0o555)
        durable_request_digest = _tagged(request_bytes)
        staging_seconds = float(time.perf_counter() - staging_started)
        limits = self.profile.limits
        name = f"carbon-c03-{self.id_factory().hex}"
        create_started = time.perf_counter()
        create = self._command(
            "create",
            "--name",
            name,
            "--platform",
            "linux/amd64",
            "--user",
            self.profile.runtime_user,
            "--read-only",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--cpus",
            str(limits.cpus),
            "--memory",
            str(limits.memory_bytes),
            "--memory-swap",
            str(limits.memory_bytes),
            "--pids-limit",
            str(limits.pids),
            "--ulimit",
            f"nofile={limits.open_files}:{limits.open_files}",
            "--tmpfs",
            f"/scratch:rw,noexec,nosuid,nodev,size={limits.scratch_bytes}",
            "--tmpfs",
            f"/output:rw,noexec,nosuid,nodev,size={limits.output_bytes}",
            "--env",
            "TMPDIR=/scratch",
            "--env",
            f"JAX_NUM_THREADS={limits.threads}",
            "--env",
            f"CARBON_C03_IMAGE_ID={self.image_id}",
            "--env",
            f"CARBON_C03_SOURCE_REVISION={self.source_revision}",
            "--label",
            f"carbon.request-digest={durable_request_digest}",
            "--mount",
            f"type=bind,source={input_directory},target=/input,readonly",
            self.image_id,
        )
        container_id = create.stdout.strip()
        if len(container_id) < 12 or any(
            character not in "0123456789abcdef" for character in container_id
        ):
            raise ReconstructionFailure("reconstruction.worker.container_invalid")
        self._verify_container_envelope(container_id, input_directory)
        create_seconds = float(time.perf_counter() - create_started)
        try:
            claimed = self.queue.claim(
                execution_ref,
                "c03-development-worker",
                claim_id=str(self.id_factory()),
            )
        except BaseException:
            self._command("rm", "--force", container_id)
            raise
        _atomic_json(
            run_directory / "dispatch.json",
            {
                "schema": "carbon.c03.dispatch.v1",
                "state": "CREATED_NOT_STARTED",
                "container_id": container_id,
                "request_digest": durable_request_digest,
                "claim_id": claimed.claim.claim_id,
                "worker_id": claimed.claim.worker_id,
                "image_id": self.image_id,
                "source_revision": self.source_revision,
            },
        )
        return WorkerDispatch(
            claimed.claim,
            container_id,
            run_directory,
            durable_request_digest,
            self.profile.profile_digest,
            self.image_id,
            self.source_revision,
            (
                (
                    "parent_input_validation_seconds",
                    validation_seconds,
                    "HOST_MONOTONIC",
                ),
                ("parent_input_staging_seconds", staging_seconds, "HOST_MONOTONIC"),
                ("parent_container_create_seconds", create_seconds, "HOST_MONOTONIC"),
            ),
        )

    def _state(self, container_id: str) -> dict[str, object]:
        value = self._command("inspect", container_id).stdout
        try:
            item = json.loads(value)[0]
            return item["State"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ReconstructionFailure(
                "reconstruction.worker.container_invalid"
            ) from None

    def _verify_container_envelope(
        self, container_id: str, input_directory: Path
    ) -> None:
        value = self._command("inspect", container_id).stdout
        limits = self.profile.limits
        try:
            item = json.loads(value)[0]
            host = item["HostConfig"]
            config = item["Config"]
            mounts = item["Mounts"]
            ulimits = host["Ulimits"]
            if (
                config["User"] != self.profile.runtime_user
                or host["ReadonlyRootfs"] is not True
                or host["NetworkMode"] != "none"
                or host["Privileged"] is not False
                or host["CapDrop"] != ["ALL"]
                or "no-new-privileges:true" not in host["SecurityOpt"]
                or host["NanoCpus"] != int(limits.cpus * 1_000_000_000)
                or host["Memory"] != limits.memory_bytes
                or host["MemorySwap"] != limits.memory_bytes
                or host["PidsLimit"] != limits.pids
                or host["PublishAllPorts"] is not False
                or host["PortBindings"] not in (None, {})
                or host["Devices"] not in (None, [])
                or host["Tmpfs"]
                != {
                    "/output": f"rw,noexec,nosuid,nodev,size={limits.output_bytes}",
                    "/scratch": f"rw,noexec,nosuid,nodev,size={limits.scratch_bytes}",
                }
                or len(ulimits) != 1
                or ulimits[0]
                != {
                    "Name": "nofile",
                    "Hard": limits.open_files,
                    "Soft": limits.open_files,
                }
                or len(mounts) != 1
                or mounts[0]["Type"] != "bind"
                or Path(mounts[0]["Source"]).resolve() != input_directory.resolve()
                or mounts[0]["Destination"] != "/input"
                or mounts[0]["RW"] is not False
            ):
                raise ValueError
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            try:
                self._command("rm", "--force", container_id)
            finally:
                raise ReconstructionFailure(
                    "reconstruction.worker.envelope_mismatch"
                ) from None

    def execute(
        self,
        dispatch: WorkerDispatch,
        *,
        cancel: Callable[[], bool] | None = None,
    ) -> WorkerRunResult:
        """Start one prepared container, enforce wall/cancel, validate, and associate."""

        if type(dispatch) is not WorkerDispatch:
            raise ReconstructionFailure("reconstruction.worker.dispatch_invalid")
        self.queue.mark_running(dispatch.claim)
        _atomic_json(
            dispatch.run_directory / "dispatch.json",
            {
                "schema": "carbon.c03.dispatch.v1",
                "state": "START_INTENT_RECORDED",
                "container_id": dispatch.container_id,
                "request_digest": dispatch.request_digest,
                "claim_id": dispatch.claim.claim_id,
                "worker_id": dispatch.claim.worker_id,
                "image_id": dispatch.image_id,
                "source_revision": dispatch.source_revision,
            },
        )
        startup_started = time.perf_counter()
        self._command("start", dispatch.container_id)
        startup_seconds = float(time.perf_counter() - startup_started)
        started = time.perf_counter()
        disposition: WorkerDisposition | None = None
        while True:
            state = self._state(dispatch.container_id)
            if state.get("Running") is False:
                break
            if cancel is not None and cancel():
                self._command("kill", dispatch.container_id)
                disposition = WorkerDisposition.CANCELLED_NON_SCIENTIFIC
                break
            if time.perf_counter() - started > self.profile.limits.wall_seconds:
                self._command("kill", dispatch.container_id)
                disposition = WorkerDisposition.WALL_LIMIT_REACHED
                break
            time.sleep(0.05)
        state = self._state(dispatch.container_id)
        logs = self._command("logs", dispatch.container_id).stdout.encode("utf-8")
        diagnostic_bytes = min(len(logs), self.profile.limits.diagnostic_bytes)
        diagnostic_digest = _tagged(logs[: self.profile.limits.diagnostic_bytes])
        if disposition is None:
            if state.get("OOMKilled") is True:
                disposition = WorkerDisposition.MEMORY_LIMIT_REACHED
            elif state.get("ExitCode") != 0:
                disposition = WorkerDisposition.WORKER_FAILED
        copied = dispatch.run_directory / "collected"
        try:
            self._command("cp", f"{dispatch.container_id}:/output/.", str(copied))
        except ReconstructionFailure:
            if disposition is None:
                disposition = WorkerDisposition.OUTPUT_REJECTED
        cleanup_started = time.perf_counter()
        cleanup_complete = True
        try:
            self._command("rm", "--force", dispatch.container_id)
        except ReconstructionFailure:
            cleanup_complete = False
            disposition = WorkerDisposition.CLEANUP_FAILED
        cleanup_seconds = float(time.perf_counter() - cleanup_started)
        observations: list[tuple[str, float | int | None, str]] = [
            *dispatch.preparation_observations,
            ("parent_worker_startup_seconds", startup_seconds, "HOST_MONOTONIC"),
            (
                "parent_worker_wall_seconds",
                float(time.perf_counter() - started),
                "HOST_MONOTONIC",
            ),
            ("parent_cleanup_seconds", cleanup_seconds, "HOST_MONOTONIC"),
            ("cpu_time_seconds", None, "UNAVAILABLE_DOCKER_CPU_THROTTLE_ONLY"),
            (
                "container_oom_killed",
                int(state.get("OOMKilled") is True),
                "DOCKER_STATE",
            ),
        ]
        if disposition is not None:
            if disposition is WorkerDisposition.CANCELLED_NON_SCIENTIFIC:
                self.queue.cancel_claim(dispatch.claim)
            else:
                self.queue.fail_infrastructure(dispatch.claim)
            return WorkerRunResult(
                disposition,
                dispatch.claim.ref,
                dispatch.request_digest,
                dispatch.profile_digest,
                dispatch.image_id,
                None,
                None,
                tuple(observations),
                diagnostic_bytes,
                diagnostic_digest,
                cleanup_complete,
            )
        try:
            output_validation_started = time.perf_counter()
            result, artifact, prediction = self._validate_complete(
                dispatch, copied=copied
            )
            observations.append(
                (
                    "parent_output_validation_seconds",
                    float(time.perf_counter() - output_validation_started),
                    "HOST_MONOTONIC",
                )
            )
            observations.extend(self._observations(result["observations"]))
            self.queue.record_partial(
                dispatch.claim,
                PartialWorkRef(
                    ExecutionStage.RECONSTRUCTION,
                    "c03-artifact-" + artifact.artifact_digest[7:39],
                    artifact.artifact_digest,
                ),
            )
            sealed = {
                "schema": "carbon.c03.sealed-parent-result.v1",
                "disposition": "COMPLETE",
                "request_digest": dispatch.request_digest,
                "profile_digest": dispatch.profile_digest,
                "image_id": dispatch.image_id,
                "source_revision": dispatch.source_revision,
                "artifact_digest": artifact.artifact_digest,
                "prediction_digest": prediction.output_digest,
                "observations": observations,
                "diagnostic_bytes": diagnostic_bytes,
                "diagnostic_digest": diagnostic_digest,
                "cleanup_complete": cleanup_complete,
            }
            _atomic_json(dispatch.run_directory / "sealed-result.json", sealed)
            return WorkerRunResult(
                WorkerDisposition.COMPLETE,
                dispatch.claim.ref,
                dispatch.request_digest,
                dispatch.profile_digest,
                dispatch.image_id,
                artifact.artifact_digest,
                prediction.output_digest,
                tuple(observations),
                diagnostic_bytes,
                diagnostic_digest,
                cleanup_complete,
            )
        except (OSError, ReconstructionFailure, ValueError):
            self.queue.fail_infrastructure(dispatch.claim)
            return WorkerRunResult(
                WorkerDisposition.OUTPUT_REJECTED,
                dispatch.claim.ref,
                dispatch.request_digest,
                dispatch.profile_digest,
                dispatch.image_id,
                None,
                None,
                tuple(observations),
                diagnostic_bytes,
                diagnostic_digest,
                cleanup_complete,
            )

    def read_completed(self, dispatch: WorkerDispatch) -> WorkerRunResult:
        """Validate and return a sealed result without dispatch or lifecycle effects."""

        sealed = _load_json(
            dispatch.run_directory / "sealed-result.json", maximum=1 << 20
        )
        result, artifact, prediction = self._validate_complete(
            dispatch, copied=dispatch.run_directory / "collected"
        )
        del result
        expected = {
            "schema": "carbon.c03.sealed-parent-result.v1",
            "disposition": "COMPLETE",
            "request_digest": dispatch.request_digest,
            "profile_digest": dispatch.profile_digest,
            "image_id": dispatch.image_id,
            "source_revision": dispatch.source_revision,
            "artifact_digest": artifact.artifact_digest,
            "prediction_digest": prediction.output_digest,
            "observations": sealed.get("observations"),
            "diagnostic_bytes": sealed.get("diagnostic_bytes"),
            "diagnostic_digest": sealed.get("diagnostic_digest"),
            "cleanup_complete": sealed.get("cleanup_complete"),
        }
        if sealed != expected or sealed["cleanup_complete"] is not True:
            raise ReconstructionFailure("reconstruction.worker.sealed_result_invalid")
        observations = tuple(tuple(item) for item in sealed["observations"])
        return WorkerRunResult(
            WorkerDisposition.COMPLETE,
            dispatch.claim.ref,
            dispatch.request_digest,
            dispatch.profile_digest,
            dispatch.image_id,
            artifact.artifact_digest,
            prediction.output_digest,
            observations,
            sealed["diagnostic_bytes"],
            sealed["diagnostic_digest"],
            True,
        )

    def recover_completed(self, dispatch: WorkerDispatch) -> WorkerRunResult:
        """Associate proven output after owner restart without another dispatch."""

        if (dispatch.run_directory / "sealed-result.json").exists():
            return self.read_completed(dispatch)
        result, artifact, prediction = self._validate_complete(
            dispatch, copied=dispatch.run_directory / "collected"
        )
        observations = list(self._observations(result["observations"]))
        observations.append(("reconciliation_count", 1, "C01_OWNER_RESTART"))
        self.queue.reconcile(dispatch.claim, ReconciliationDisposition.RESUME_EXISTING)
        self.queue.record_partial(
            dispatch.claim,
            PartialWorkRef(
                ExecutionStage.RECONSTRUCTION,
                "c03-artifact-" + artifact.artifact_digest[7:39],
                artifact.artifact_digest,
            ),
        )
        sealed = {
            "schema": "carbon.c03.sealed-parent-result.v1",
            "disposition": "COMPLETE",
            "request_digest": dispatch.request_digest,
            "profile_digest": dispatch.profile_digest,
            "image_id": dispatch.image_id,
            "source_revision": dispatch.source_revision,
            "artifact_digest": artifact.artifact_digest,
            "prediction_digest": prediction.output_digest,
            "observations": observations,
            "diagnostic_bytes": 0,
            "diagnostic_digest": _tagged(b""),
            "cleanup_complete": True,
        }
        _atomic_json(dispatch.run_directory / "sealed-result.json", sealed)
        return WorkerRunResult(
            WorkerDisposition.COMPLETE,
            dispatch.claim.ref,
            dispatch.request_digest,
            dispatch.profile_digest,
            dispatch.image_id,
            artifact.artifact_digest,
            prediction.output_digest,
            tuple(observations),
            0,
            _tagged(b""),
            True,
        )

    @staticmethod
    def _observations(value: object) -> tuple[tuple[str, float | int | None, str], ...]:
        if (
            type(value) is not dict
            or set(value) != _OBSERVATION_FIELDS
            or value.get("evidence_class") != "WORKER_SELF_REPORTED_DIAGNOSTIC"
            or value.get("checkpoint_load_seconds") is not None
            or value.get("checkpoint_save_seconds") is not None
            or value.get("checkpoint_timing_missing_reason")
            != "C02_SOURCE_HAS_NO_NONINTERFERING_STAGE_SEAM"
        ):
            raise ReconstructionFailure("reconstruction.worker.observation_invalid")
        result = []
        for key, item in value.items():
            if key in {
                "evidence_class",
                "checkpoint_load_seconds",
                "checkpoint_save_seconds",
                "checkpoint_timing_missing_reason",
            }:
                continue
            if item is not None and (
                type(item) not in (int, float) or not math.isfinite(item) or item < 0
            ):
                raise ReconstructionFailure("reconstruction.worker.observation_invalid")
            result.append((key, item, "WORKER_SELF_REPORTED_DIAGNOSTIC"))
        result.append(
            ("checkpoint_load_seconds", None, value["checkpoint_timing_missing_reason"])
        )
        result.append(
            ("checkpoint_save_seconds", None, value["checkpoint_timing_missing_reason"])
        )
        return tuple(result)

    def _validate_complete(
        self, dispatch: WorkerDispatch, *, copied: Path
    ) -> tuple[dict[str, object], ReconstructionReceipt, PredictionReceipt]:
        if {item.name for item in copied.iterdir()} != {
            "artifact",
            "prediction.npz",
            "result.json",
        }:
            raise ReconstructionFailure("reconstruction.worker.output_invalid")
        _safe_tree_size(copied, maximum=self.profile.limits.output_bytes)
        result = _load_json(copied / "result.json", maximum=1 << 20)
        if (
            set(result) != _RESULT_FIELDS
            or result["schema"] != "carbon.c03.worker-result.v1"
            or result["scope"] != "UNQUALIFIED_PUBLIC_DEVELOPMENT"
            or result["disposition"] != "COMPLETE"
        ):
            raise ReconstructionFailure("reconstruction.worker.output_invalid")
        request_path = dispatch.run_directory / "input/request.json"
        request = _load_json(request_path, maximum=65536)
        if (
            _tagged(request_path.read_bytes()) != dispatch.request_digest
            or request["worker_profile_digest"] != dispatch.profile_digest
            or request["image_id"] != dispatch.image_id
            or request["source_revision"] != dispatch.source_revision
            or request["submission_id"] != dispatch.claim.ref.submission_id.value
            or request["attempt_number"] != dispatch.claim.ref.attempt_number
        ):
            raise ReconstructionFailure(
                "reconstruction.worker.request_binding_mismatch"
            )
        for field in (
            "worker_profile_digest",
            "image_id",
            "source_revision",
            "submission_id",
            "attempt_number",
            "plan_digest",
            "archive_digest",
            "randomness_digest",
            "prediction_request_digest",
            "replicate_id",
            "replicate_digest",
            "resource_policy_digest",
            "resource_class_digest",
        ):
            if result[field] != request[field]:
                raise ReconstructionFailure(
                    "reconstruction.worker.output_binding_mismatch"
                )
        from carbon.construction import decode_resolved_construction_plan
        from carbon.construction.refs import ResolvedConstructionPlanRef
        from carbon.registry import ChallengeKey

        plan_bytes = (dispatch.run_directory / "input/plan.bin").read_bytes()
        plan = decode_resolved_construction_plan(
            plan_bytes,
            expected_ref=ResolvedConstructionPlanRef(
                ChallengeKey(request["challenge_id"], request["challenge_version"]),
                content_digest=request["plan_digest"],
            ),
        )
        archive = PublicTrainingArchive.from_file(
            dispatch.run_directory / "input/training.npz",
            provenance=request["archive_provenance"],
        )
        seed = DerivedSeed(bytes.fromhex(request["randomness_hex"]))
        artifact = validate_reconstruction_artifact(
            execution_ref=dispatch.claim.ref,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=copied / "artifact",
        )
        if artifact.status is not ReconstructionStatus.COMPLETE or result[
            "receipt"
        ] != _receipt_body(artifact):
            raise ReconstructionFailure("reconstruction.worker.output_binding_mismatch")
        array, output_digest = _prediction_digest(copied / "prediction.npz")
        prediction_body = result["prediction"]
        if type(prediction_body) is not dict:
            raise ReconstructionFailure("reconstruction.worker.prediction_invalid")
        try:
            prediction = PredictionReceipt(**prediction_body)
        except (TypeError, ReconstructionFailure):
            raise ReconstructionFailure(
                "reconstruction.worker.prediction_invalid"
            ) from None
        if (
            prediction.artifact_digest != artifact.artifact_digest
            or prediction.request_digest != request["prediction_request_digest"]
            or prediction.output_digest != output_digest
            or tuple(array.shape)
            != (prediction.cases, prediction.times, prediction.points)
        ):
            raise ReconstructionFailure("reconstruction.worker.prediction_invalid")
        return result, artifact, prediction


__all__ = [
    "DevelopmentReconstructionWorker",
    "WorkerDispatch",
    "WorkerDisposition",
    "WorkerRunResult",
    "build_development_worker_image",
]
