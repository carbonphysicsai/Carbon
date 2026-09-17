"""Closed DEVELOPMENT identities for the C-03 isolated worker."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum

from carbon.registry import is_sha256_digest

PROFILE_ID = "carbon.c03.linux-x86_64-cpu.development.v1"
PROFILE_VERSION = "1.0"
SCOPE = "UNQUALIFIED_PUBLIC_DEVELOPMENT"
PRODUCTIVE_DEADLINE_SECONDS = 600
GRACEFUL_CANCELLATION_SECONDS = 5
CLEANUP_CONFIRMATION_SECONDS = 30
CPU_COUNT = 2
MEMORY_BYTES = 4 * 1024**3
SWAP_BYTES = 0
PIDS_LIMIT = 256
SCRATCH_BYTES = 512 * 1024**2
SCRATCH_INODES = 8192
INPUT_BYTES = 128 * 1024**2
EXPANDED_INPUT_BYTES = 128 * 1024**2
CONTROL_BYTES = 1024**2
OUTPUT_BYTES = 128 * 1024**2
EXPANDED_OUTPUT_BYTES = 128 * 1024**2
OUTPUT_MEMBERS = 1024
DIAGNOSTIC_BYTES = 1024**2
NOFILE_LIMIT = 1024
WORKER_UID = 65532
WORKER_GID = 65532
VALIDATION_MEMORY_BYTES = 4 * 1024**3
VALIDATION_CPU_SECONDS = 60
VALIDATION_WALL_SECONDS = 90
VALIDATION_NOFILE_LIMIT = 256

_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[._:-][A-Za-z0-9]+)*\Z", re.ASCII)


class WorkerCode(str, Enum):
    INVALID = "reconstruction.worker.request.invalid"
    UNSUPPORTED = "reconstruction.worker.profile.unsupported"
    UNAVAILABLE = "reconstruction.worker.infrastructure.unavailable"
    CONFLICT = "reconstruction.worker.launch.conflict"
    POLICY = "reconstruction.worker.policy.mismatch"
    STAGING = "reconstruction.worker.staging.rejected"
    RUNTIME = "reconstruction.worker.runtime.failed"
    DEADLINE = "reconstruction.worker.deadline.exceeded"
    CANCELLED = "reconstruction.worker.cancelled"
    OUTPUT = "reconstruction.worker.output.rejected"
    CLEANUP = "reconstruction.worker.cleanup.uncertain"
    QUARANTINED = "reconstruction.worker.slot.quarantined"


class WorkerFailure(RuntimeError):
    """Stable, non-echoing failure for the controller/worker boundary."""

    def __init__(
        self, code: WorkerCode, *, private_diagnostic: bytes | None = None
    ) -> None:
        if private_diagnostic is not None and type(private_diagnostic) is not bytes:
            raise TypeError("private_diagnostic must be bytes")
        self.code = code
        self.private_diagnostic = (private_diagnostic or b"")[:DIAGNOSTIC_BYTES]
        super().__init__("Development reconstruction worker operation failed.")


class WorkerLaunchState(str, Enum):
    INTENT_RECORDED = "INTENT_RECORDED"
    CREATING = "CREATING"
    CREATED = "CREATED"
    CONTROLS_VERIFIED = "CONTROLS_VERIFIED"
    RUNNING = "RUNNING"
    OUTPUT_SNAPSHOTTED = "OUTPUT_SNAPSHOTTED"
    TERMINATED = "TERMINATED"
    ASSOCIATED = "ASSOCIATED"
    CANCELLED = "CANCELLED"
    FAILED_INFRA = "FAILED_INFRA"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    QUARANTINED = "QUARANTINED"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def tagged_sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def exact_digest(value: object) -> str:
    if type(value) is not str or not is_sha256_digest(value):
        raise WorkerFailure(WorkerCode.INVALID)
    return value


def exact_token(value: object, *, maximum: int = 256) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= maximum
        or _TOKEN.fullmatch(value) is None
    ):
        raise WorkerFailure(WorkerCode.INVALID)
    return value


@dataclass(frozen=True, slots=True)
class DevelopmentWorkerProfile:
    """One exact B-02C-bound worker policy; not a production resource class."""

    research_resource_policy_digest: str
    resource_class_digest: str
    profile_id: str = PROFILE_ID
    profile_version: str = PROFILE_VERSION
    accelerator_profile_id: str | None = None
    accelerator_grant_digest: str | None = None
    accelerator_role: str | None = None

    def __post_init__(self) -> None:
        if self.accelerator_profile_id is None:
            if (
                self.profile_id != PROFILE_ID
                or self.profile_version != PROFILE_VERSION
                or self.accelerator_grant_digest is not None
                or self.accelerator_role is not None
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
        else:
            from carbon.reconstruction.accelerators import (
                GPU_PROFILE,
                TPU_PROFILE,
                AcceleratorRole,
            )

            if (
                (self.accelerator_profile_id, self.profile_id)
                not in (
                    (GPU_PROFILE.profile_id, "carbon.c03.cuda.development.v1"),
                    (TPU_PROFILE.profile_id, "carbon.c03.tpu.preparation.v1"),
                )
                or self.profile_version != "1.0"
                or self.accelerator_role not in [role.value for role in AcceleratorRole]
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
            exact_digest(self.accelerator_grant_digest)
        object.__setattr__(
            self,
            "research_resource_policy_digest",
            exact_digest(self.research_resource_policy_digest),
        )
        object.__setattr__(
            self, "resource_class_digest", exact_digest(self.resource_class_digest)
        )

    @property
    def body(self) -> dict[str, object]:
        result = {
            "schema": "carbon.c03.development-worker-profile.v1",
            "scope": SCOPE,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "b02c": {
                "research_resource_policy_digest": self.research_resource_policy_digest,
                "resource_class_digest": self.resource_class_digest,
            },
            "concurrency": 1,
            "cpu": {"count": CPU_COUNT, "quota_cpus": 2, "cpuset_count": 2},
            "memory": {"bytes": MEMORY_BYTES, "swap_bytes": SWAP_BYTES},
            "pids": PIDS_LIMIT,
            "scratch": {"bytes": SCRATCH_BYTES, "inodes": SCRATCH_INODES},
            "input": {"bytes": INPUT_BYTES, "expanded_bytes": EXPANDED_INPUT_BYTES},
            "control_bytes": CONTROL_BYTES,
            "output": {
                "bytes": OUTPUT_BYTES,
                "expanded_bytes": EXPANDED_OUTPUT_BYTES,
                "members": OUTPUT_MEMBERS,
            },
            "diagnostic_bytes": DIAGNOSTIC_BYTES,
            "nofile_per_process": NOFILE_LIMIT,
            "core_dumps": False,
            "accelerators": "NOT_APPLICABLE",
            "deadline_seconds": PRODUCTIVE_DEADLINE_SECONDS,
            "graceful_cancellation_seconds": GRACEFUL_CANCELLATION_SECONDS,
            "cleanup_confirmation_seconds": CLEANUP_CONFIRMATION_SECONDS,
            "security": {
                "network": "none",
                "read_only_root": True,
                "non_root": f"{WORKER_UID}:{WORKER_GID}",
                "capabilities": [],
                "no_new_privileges": True,
                "seccomp": "docker-default",
                "restart": "no",
            },
        }

        if self.accelerator_profile_id is not None:
            from carbon.reconstruction.accelerators import GPU_PROFILE, TPU_PROFILE

            if self.accelerator_profile_id == TPU_PROFILE.profile_id:
                result["schema"] = "carbon.c03.development-worker-profile.v3"
                result["accelerators"] = {
                    "profile_id": TPU_PROFILE.profile_id,
                    "profile_digest": TPU_PROFILE.digest,
                    "grant_digest": self.accelerator_grant_digest,
                    "role": self.accelerator_role,
                    "local_device_count": TPU_PROFILE.local_device_count,
                    "global_device_count": TPU_PROFILE.global_device_count,
                    "process_count": TPU_PROFILE.process_count,
                    "allocation": "EXCLUSIVE_TPU_HOST_REQUIRED_NOT_VERIFIED",
                    "host_dispatch": "UNAVAILABLE",
                }
            else:
                result["schema"] = "carbon.c03.development-worker-profile.v2"
                result["accelerators"] = {
                    "profile_id": self.accelerator_profile_id,
                    "profile_digest": GPU_PROFILE.digest,
                    "grant_digest": self.accelerator_grant_digest,
                    "role": self.accelerator_role,
                    "device_uuid": GPU_PROFILE.device_uuid,
                    "allocation": "EXCLUSIVE_SINGLE_DEVICE",
                }
        return result

    @property
    def digest(self) -> str:
        return tagged_sha256(_canonical(self.body))


@dataclass(frozen=True, slots=True)
class WorkerImageIdentity:
    image_id: str
    config_digest: str
    source_tree_digest: str
    wheel_digest: str
    lock_digest: str
    base_image_digest: str
    build_recipe_digest: str
    entrypoint_digest: str

    def __post_init__(self) -> None:
        for name in (
            "image_id",
            "config_digest",
            "source_tree_digest",
            "wheel_digest",
            "lock_digest",
            "base_image_digest",
            "build_recipe_digest",
            "entrypoint_digest",
        ):
            object.__setattr__(self, name, exact_digest(getattr(self, name)))
        if self.image_id != self.config_digest:
            raise WorkerFailure(WorkerCode.INVALID)


@dataclass(frozen=True, slots=True)
class WorkerTiming:
    launch_started_unix: float
    productive_deadline_unix: float
    launch_started_monotonic: float
    boot_id: str

    def __post_init__(self) -> None:
        if any(
            type(value) is not float or not math.isfinite(value) or value < 0
            for value in (
                self.launch_started_unix,
                self.productive_deadline_unix,
                self.launch_started_monotonic,
            )
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        if (
            self.productive_deadline_unix
            != self.launch_started_unix + PRODUCTIVE_DEADLINE_SECONDS
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        exact_token(self.boot_id)

    @property
    def productive_deadline_monotonic(self) -> float:
        """Same-boot live deadline; never compare this value across boot IDs."""

        return self.launch_started_monotonic + PRODUCTIVE_DEADLINE_SECONDS


__all__ = [
    "CLEANUP_CONFIRMATION_SECONDS",
    "CONTROL_BYTES",
    "CPU_COUNT",
    "DIAGNOSTIC_BYTES",
    "EXPANDED_INPUT_BYTES",
    "EXPANDED_OUTPUT_BYTES",
    "GRACEFUL_CANCELLATION_SECONDS",
    "INPUT_BYTES",
    "MEMORY_BYTES",
    "NOFILE_LIMIT",
    "OUTPUT_BYTES",
    "OUTPUT_MEMBERS",
    "PIDS_LIMIT",
    "PRODUCTIVE_DEADLINE_SECONDS",
    "PROFILE_ID",
    "SCOPE",
    "SCRATCH_BYTES",
    "SCRATCH_INODES",
    "SWAP_BYTES",
    "VALIDATION_CPU_SECONDS",
    "VALIDATION_MEMORY_BYTES",
    "VALIDATION_NOFILE_LIMIT",
    "VALIDATION_WALL_SECONDS",
    "WORKER_GID",
    "WORKER_UID",
    "DevelopmentWorkerProfile",
    "WorkerCode",
    "WorkerFailure",
    "WorkerImageIdentity",
    "WorkerLaunchState",
    "WorkerTiming",
    "exact_digest",
    "exact_token",
    "tagged_sha256",
]
