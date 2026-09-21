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


STRICT_HOST_GRANT_AUTHORITY = "STRICT_HOST_GRANT"
LOCAL_DEVELOPMENT_AUTHORITY = "LOCAL_DEVELOPMENT_APPROVAL"
# A host admitting itself from local policy and its installed record. No human
# signs a record per run: that model cannot work for a network of miners, and
# the CPU lane has never required it.
#
# Since the owner decision of 2026-09-21 (ticket C-CORE-19) this is also how a
# validator's GPU reconstruction is admitted. The value names *how the host was
# admitted*, not who ran - the role is carried separately and is what decides
# the lane. The string is unchanged so that every record written before that
# decision keeps its exact previous meaning and digest.
MINER_HOST_AUTHORITY = "MINER_HOST_SELF_SERVICE"
# The same value under a name that does not imply a role, for the paths that now
# serve both. Not a second authority: an alias, deliberately identical, because
# a "validator self-service" authority distinct from this one would be exactly
# the relaxed variant of the strict grant that the decision forbids inventing.
SELF_SERVICE_HOST_AUTHORITY = MINER_HOST_AUTHORITY

# The authorities whose cleanup is task-owned: they remove exactly what their
# own launch created and never assert that the whole device was released,
# because neither ever had the evidence that claim requires. The strict grant is
# deliberately absent - its allocation is owed a verified release, and letting a
# weaker authority complete it would skip exactly that.
TASK_OWNED_AUTHORITIES = (LOCAL_DEVELOPMENT_AUTHORITY, MINER_HOST_AUTHORITY)
ALLOCATION_AUTHORITIES = (STRICT_HOST_GRANT_AUTHORITY, *TASK_OWNED_AUTHORITIES)


def registered_run_controls() -> dict[str, object]:
    """The bounds the worker implementation itself enforces, with nothing added.

    The miner lane has no approval to narrow anything, so resolving its controls
    means reading what the worker is already built to apply - the same bounds the
    CPU lane runs under. Every value here is a registered constant.

    The fields an approval would add are **absent rather than defaulted**: a
    whole-attempt deadline, a batch window and a training-step ceiling are all
    batch authority, and the implementation registers no value for them. Giving
    them an invented number here would publish a bound nobody set and that
    nothing enforces.
    """
    return {
        "productive_seconds": PRODUCTIVE_DEADLINE_SECONDS,
        "host_ram_bytes": MEMORY_BYTES,
        "output_bytes": OUTPUT_BYTES,
        "worker_network": "DISABLED",
    }


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
    accelerator_authority: str | None = None
    accelerator_plan_digest: str | None = None
    # Which device on THIS host the launch is bound to. Supplied per run from
    # the installed host record, never from a constant in the source tree.
    accelerator_device_uuid: str | None = None
    # The resolved effective controls for this run, when an authority narrowed
    # them. Absent means the registered implementation constants apply, which is
    # the case for every CPU and strict launch, so their bodies are unchanged.
    accelerator_controls: dict | None = None

    @property
    def effective_deadline_seconds(self) -> int:
        """The productive deadline this launch is actually run under."""
        controls = self.accelerator_controls
        if not controls:
            return PRODUCTIVE_DEADLINE_SECONDS
        return int(controls["productive_seconds"])

    @property
    def effective_output_bytes(self) -> int:
        """The output ceiling this launch's collection is actually bounded by."""
        controls = self.accelerator_controls
        if not controls:
            return OUTPUT_BYTES
        return int(controls["output_bytes"])

    def __post_init__(self) -> None:
        if self.accelerator_profile_id is None:
            if (
                self.profile_id != PROFILE_ID
                or self.profile_version != PROFILE_VERSION
                or self.accelerator_grant_digest is not None
                or self.accelerator_role is not None
                or self.accelerator_authority is not None
                or self.accelerator_plan_digest is not None
                or self.accelerator_device_uuid is not None
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
        else:
            from carbon.reconstruction.accelerators import (
                GPU_PROFILE,
                HISTORICAL_PROFILES,
                TPU_PROFILE,
                AcceleratorRole,
            )

            permitted = {
                (GPU_PROFILE.profile_id, "carbon.c03.cuda.development.v1"),
                (TPU_PROFILE.profile_id, "carbon.c03.tpu.preparation.v1"),
            }
            # Retained GPU profiles, which pinned their own device and so were
            # paired with the same worker profile. A record naming one stays
            # readable; it does not become runnable. `_registered` refuses a
            # historical profile wherever execution is actually decided, and the
            # local development authority is refused for it below.
            permitted |= {
                (profile.profile_id, "carbon.c03.cuda.development.v1")
                for profile in HISTORICAL_PROFILES
            }
            if (
                (self.accelerator_profile_id, self.profile_id) not in permitted
                or self.profile_version != "1.0"
                or self.accelerator_role not in [role.value for role in AcceleratorRole]
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
            # An omitted authority means the historical strict grant, so every
            # existing profile keeps its exact previous meaning and digest.
            if self.accelerator_authority is None:
                object.__setattr__(
                    self, "accelerator_authority", STRICT_HOST_GRANT_AUTHORITY
                )
            if self.accelerator_authority not in (
                STRICT_HOST_GRANT_AUTHORITY,
                LOCAL_DEVELOPMENT_AUTHORITY,
                MINER_HOST_AUTHORITY,
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
            # Neither weaker variant exists for anything but the portable GPU
            # profile; a TPU request is rejected before this and never becomes
            # one, and a retained profile is not an execution route.
            if (
                self.accelerator_authority
                in (LOCAL_DEVELOPMENT_AUTHORITY, MINER_HOST_AUTHORITY)
                and self.accelerator_profile_id != GPU_PROFILE.profile_id
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
            # Self-service host admission now serves both GPU roles, by the
            # owner decision of 2026-09-21 (ticket C-CORE-19). It is still
            # reached by being a role rather than by presenting a weaker
            # authority: the role decides the lane, and neither role can select
            # the other's by choosing an authority value.
            #
            # A third role, if one is ever added, does not get this by default.
            if self.accelerator_authority == MINER_HOST_AUTHORITY and (
                self.accelerator_role
                not in (
                    AcceleratorRole.MINER_RESEARCH.value,
                    AcceleratorRole.VALIDATOR_RECONSTRUCTION.value,
                )
            ):
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
            exact_digest(self.accelerator_grant_digest)
            # Two distinct identities. accelerator_grant_digest is the authority
            # record (a strict grant, or a local approval record). The approved
            # diagnostic plan is a separate digest carried only by the local
            # variant, and neither may stand in for the other.
            if self.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
                exact_digest(self.accelerator_plan_digest)
                if self.accelerator_plan_digest == self.accelerator_grant_digest:
                    raise WorkerFailure(WorkerCode.UNSUPPORTED)
            elif self.accelerator_plan_digest is not None:
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
            # A launch under the portable profile must name the device it is
            # bound to, because that profile pins none. The TPU preparation
            # profile dispatches nothing and carries none, and a historical
            # profile already names its own device, so for both the field must
            # be absent rather than supplied a second time.
            if self.accelerator_profile_id == GPU_PROFILE.profile_id:
                from carbon.reconstruction.host_inventory import NVIDIA_DEVICE_UUID

                if (
                    type(self.accelerator_device_uuid) is not str
                    or NVIDIA_DEVICE_UUID.fullmatch(self.accelerator_device_uuid)
                    is None
                ):
                    raise WorkerFailure(WorkerCode.UNSUPPORTED)
            elif self.accelerator_device_uuid is not None:
                raise WorkerFailure(WorkerCode.UNSUPPORTED)
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
                "bytes": self.effective_output_bytes,
                "expanded_bytes": EXPANDED_OUTPUT_BYTES,
                "members": OUTPUT_MEMBERS,
            },
            "diagnostic_bytes": DIAGNOSTIC_BYTES,
            "nofile_per_process": NOFILE_LIMIT,
            "core_dumps": False,
            "accelerators": "NOT_APPLICABLE",
            "deadline_seconds": self.effective_deadline_seconds,
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
            elif self.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
                # Deliberately not "grant_digest": a development approval must
                # never acquire strict authority by occupying the old key.
                result["schema"] = "carbon.c03.development-worker-profile.v4"
                result["accelerators"] = {
                    "profile_id": self.accelerator_profile_id,
                    "profile_digest": GPU_PROFILE.digest,
                    "authority": LOCAL_DEVELOPMENT_AUTHORITY,
                    "approval_digest": self.accelerator_grant_digest,
                    "diagnostic_plan_digest": self.accelerator_plan_digest,
                    "role": self.accelerator_role,
                    "device_uuid": self.accelerator_device_uuid,
                    "allocation": "TASK_OWNED_NOT_EXCLUSIVE",
                    "device_memory_cap": "NOT_ENFORCED_BY_THIS_AUTHORITY",
                    "official_eligible": False,
                    # The controls this run is executed under, resolved from the
                    # approval and the registered implementation ceilings. They
                    # live in the development block, not at the top level, so
                    # accepted CPU and strict bodies stay byte-identical.
                    "effective_controls": dict(
                        sorted((self.accelerator_controls or {}).items())
                    ),
                }
            elif self.accelerator_authority == MINER_HOST_AUTHORITY:
                from carbon.reconstruction.accelerators import (
                    AcceleratorRole,
                    lane_for_role,
                    miner_lane_assurance,
                    validator_self_service_assurance,
                )

                # The lane follows the role and is never hardcoded here. Before
                # the 2026-09-21 decision only a miner could reach this branch,
                # so a literal was indistinguishable from the rule; now the two
                # differ and only the rule is correct.
                role = AcceleratorRole(self.accelerator_role)
                lane = lane_for_role(role)
                miner = role is AcceleratorRole.MINER_RESEARCH
                # A separate version for the validator body. v5 has only ever
                # meant a miner-lane run, and every v5 record already written is
                # one; widening it in place would silently change what those
                # records assert to a consumer that reads the version. A miner
                # run stays byte-identical.
                result["schema"] = (
                    "carbon.c03.development-worker-profile.v5"
                    if miner
                    else "carbon.c03.development-worker-profile.v6"
                )
                result["accelerators"] = {
                    "profile_id": self.accelerator_profile_id,
                    "profile_digest": GPU_PROFILE.digest,
                    "lane": lane.value,
                    "authority": MINER_HOST_AUTHORITY,
                    # Deliberately not "grant_digest". There is no grant on this
                    # lane, and a consumer looking for one must not find a miner
                    # record sitting in the key a strict grant would occupy.
                    # What binds the run is the exact installed host record, so
                    # a replaced or withdrawn record does not keep admitting.
                    "host_record_digest": self.accelerator_grant_digest,
                    "role": self.accelerator_role,
                    "device_uuid": self.accelerator_device_uuid,
                    # Task-owned, and saying so. Nothing here claims the device
                    # is exclusively this run's, because nothing established it.
                    "allocation": "TASK_OWNED_NOT_EXCLUSIVE",
                    # Same admission, so the same established and not-established
                    # facts; different standing, so a different label. The
                    # validator label does not claim official eligibility -
                    # admission is not qualification.
                    "assurance": (
                        miner_lane_assurance()
                        if miner
                        else validator_self_service_assurance()
                    ),
                    "effective_controls": dict(
                        sorted((self.accelerator_controls or {}).items())
                    ),
                }
            else:
                from carbon.reconstruction.accelerators import resolve_profile

                # The profile this launch actually names, which is not always
                # the current one. Stamping the current profile's digest onto a
                # launch that names an earlier profile restates history instead
                # of recording it, and it moves the body - and therefore the
                # digest - of a request that was already accepted.
                named = resolve_profile(self.accelerator_profile_id)
                result["schema"] = "carbon.c03.development-worker-profile.v2"
                result["accelerators"] = {
                    "profile_id": self.accelerator_profile_id,
                    "profile_digest": named.digest,
                    "grant_digest": self.accelerator_grant_digest,
                    "role": self.accelerator_role,
                    # A profile that pins its own device supplies it. The
                    # portable profile pins none, so the launch supplies it
                    # and is required above to do so.
                    "device_uuid": (
                        named.device_uuid
                        if self.accelerator_device_uuid is None
                        else self.accelerator_device_uuid
                    ),
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
    # The productive window this launch was admitted for. Defaults to the
    # registered maximum, so every existing CPU and strict launch is unchanged.
    # An authority may narrow it; nothing may widen it past the registered
    # ceiling, which is what the worker is actually built to enforce.
    deadline_seconds: int = PRODUCTIVE_DEADLINE_SECONDS

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
            type(self.deadline_seconds) is not int
            or isinstance(self.deadline_seconds, bool)
            or not 0 < self.deadline_seconds <= PRODUCTIVE_DEADLINE_SECONDS
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        if (
            self.productive_deadline_unix
            != self.launch_started_unix + self.deadline_seconds
        ):
            raise WorkerFailure(WorkerCode.INVALID)
        exact_token(self.boot_id)

    @property
    def productive_deadline_monotonic(self) -> float:
        """Same-boot live deadline; never compare this value across boot IDs."""

        return self.launch_started_monotonic + self.deadline_seconds


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
