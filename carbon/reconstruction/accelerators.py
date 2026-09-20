"""Prospective accelerator contracts; no allocation or dispatch authority.

The accepted CPU compiler/environment remains unchanged. These closed profiles
describe the hardware evidence still required before the existing controller may
admit an accelerator attempt. Import and discovery never initialize JAX.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum

from carbon.reconstruction.worker.backend_probe import (
    Backend,
    BackendObservation,
    BackendRequest,
    validate_observation,
)


class AcceleratorRole(str, Enum):
    MINER_RESEARCH = "MINER_RESEARCH"
    VALIDATOR_RECONSTRUCTION = "VALIDATOR_RECONSTRUCTION"


class AcceleratorUnavailable(RuntimeError):
    """A prepared profile is not an admitted execution or a resource grant."""


@dataclass(frozen=True, slots=True)
class AcceleratorProfile:
    profile_id: str
    backend: Backend
    device_kind: str
    local_device_count: int
    global_device_count: int
    process_count: int
    topology: str
    environment_file: str
    environment_lock_digest: str
    device_uuid: str | None = None
    host_driver: str | None = None

    @property
    def admission_enabled(self) -> bool:
        # Enabling execution requires a prospective controller/profile migration,
        # not a supplied Boolean or a discovered device.
        return False

    @property
    def backend_request(self) -> BackendRequest:
        return BackendRequest(self.backend, self.local_device_count, "0.10.2", "0.10.2")

    def document(self) -> dict[str, object]:
        return {
            "schema": "carbon.accelerator-profile.v1",
            **asdict(self),
            "backend": self.backend.value,
            "python": "3.11.16",
            "jax": "0.10.2",
            "jaxlib": "0.10.2",
            "roles": [role.value for role in AcceleratorRole],
            "language": "python-jax",
            "tasks": ["research_training", "independent_reconstruction", "prediction"],
            "parameter_dtype": "float32",
            "complex_dtype": "complex64",
            "x64": False,
            "matmul_precision": "highest",
            "allocation": "EXCLUSIVE_REQUIRED_NOT_VERIFIED",
            "memory_cap": "DEVICE_ENFORCEMENT_UNVERIFIED",
            "admission_enabled": False,
            "execution_acceptance": "NOT_EXECUTED",
            "scientifically_qualified": False,
            "final_comparison_eligible": False,
            "multi_device_workload": "NOT_EXECUTED",
        }

    @property
    def digest(self) -> str:
        raw = json.dumps(self.document(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(raw.encode("ascii")).hexdigest()


GPU_PROFILE = AcceleratorProfile(
    "carbon_jax_cuda13_rtx3060_laptop_development_v1",
    Backend.NVIDIA,
    "NVIDIA GeForce RTX 3060 Laptop GPU",
    1,
    1,
    1,
    "single-device",
    ".devcontainer/accelerators/cuda13-py311.txt",
    "sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434",
    "GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81",
    "581.95",
)
TPU_PROFILE = AcceleratorProfile(
    "carbon_jax_tpu_v5e_8_development_v1",
    Backend.TPU,
    "TPU v5 lite",
    8,
    8,
    1,
    "2x4; provisioning SKU and observed topology pending",
    ".devcontainer/accelerators/tpu-py311.txt",
    "sha256:f42354e5eaec6c995fbee84407b095529b201ce82c04ea78b37777581d7bb3b2",
)
PROFILES = (GPU_PROFILE, TPU_PROFILE)


def resolve_profile(profile_id: str) -> AcceleratorProfile:
    if type(profile_id) is str:
        for profile in PROFILES:
            if profile.profile_id == profile_id:
                return profile
    raise ValueError("unregistered accelerator profile")


def _registered(profile: AcceleratorProfile) -> None:
    if type(profile) is not AcceleratorProfile or profile not in PROFILES:
        raise ValueError("exact registered accelerator profile required")


def worker_environment(
    profile: AcceleratorProfile, role: AcceleratorRole
) -> dict[str, str]:
    """Proposed closed worker overlay, never applied to the control plane.

    The controller still owns the complete environment and role/principal-bound
    scratch mount. No persistent compilation cache crosses worker boundaries.
    Disabling preallocation is not a GPU memory cap or partition policy.
    """
    _registered(profile)
    if type(role) is not AcceleratorRole:
        raise ValueError("exact execution role required")
    result = {
        "JAX_PLATFORMS": profile.backend.value,
        "JAX_ENABLE_X64": "false",
        "JAX_DEFAULT_MATMUL_PRECISION": "highest",
        "JAX_ENABLE_COMPILATION_CACHE": "false",
        "JAX_COMPILATION_CACHE_DIR": f"/scratch/{role.value.lower()}/jax-cache",
    }
    if profile.backend is Backend.NVIDIA:
        result.update(
            {
                "CUDA_VISIBLE_DEVICES": profile.device_uuid,
                "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
                "XLA_PYTHON_CLIENT_ALLOCATOR": "platform",
            }
        )
    return result


def validate_worker_observation(
    profile: AcceleratorProfile,
    observation: BackendObservation,
    *,
    global_device_count: int,
    process_count: int,
    matmul_precision: str,
) -> None:
    """Check exact numerical observations; not physical-device attestation.

    UUID, driver, physical topology, allocation exclusivity and memory enforcement
    need independent supervisor observations; JAX's device kind cannot prove them.
    """
    _registered(profile)
    validate_observation(profile.backend_request, observation)
    if (
        type(global_device_count) is not int
        or global_device_count != profile.global_device_count
        or type(process_count) is not int
        or process_count != profile.process_count
        or observation.process_index != 0
        or observation.x64_enabled
        or matmul_precision != "highest"
        or any(
            device.device_kind != profile.device_kind for device in observation.devices
        )
    ):
        raise ValueError("accelerator topology, device or precision mismatch")


def require_accelerator_admission(
    profile: AcceleratorProfile, role: AcceleratorRole
) -> None:
    _registered(profile)
    if type(role) is not AcceleratorRole:
        raise ValueError("exact execution role required")
    raise AcceleratorUnavailable(
        "accelerator.dispatch_disabled: existing controller migration, pinned image, "
        "grant, containment and hardware acceptance are required"
    )


def accelerator_dependency_specs(
    profile: AcceleratorProfile,
) -> tuple[tuple[str, str, str], ...]:
    """Add explicit plugin pins; the profile also binds the entire resolved lock."""
    _registered(profile)
    pins = (
        (("jax-cuda13-plugin", "0.10.2"), ("jax-cuda13-pjrt", "0.10.2"))
        if profile.backend is Backend.NVIDIA
        else (("libtpu", "0.0.42"),)
    )
    return tuple(
        (
            name,
            version,
            "sha256:"
            + hashlib.sha256(f"pypi:{name}=={version}".encode("ascii")).hexdigest(),
        )
        for name, version in pins
    )


def require_reconstruction_profile_admission(profile, *, worker_profile=None) -> None:
    """Require the closed controller-staged worker profile for accelerator work.

    No caller can relax the accepted CPU controller by choosing an accelerator
    environment in a valid construction plan. This check runs before staging,
    trainer imports or hardware initialization. The internal staged profile is
    constructed only after the controller verifies the private host grant. It
    is not exposed as a public admission flag; image, allocation and controls
    remain independently enforced by that same controller.
    """
    from carbon.reconstruction.model import ReconstructionFailure, ReconstructionProfile

    if type(profile) is not ReconstructionProfile:
        raise ReconstructionFailure("reconstruction.profile.invalid")
    try:
        mapping = json.loads(profile.mapping_receipt_json)
    except (TypeError, ValueError):
        raise ReconstructionFailure("reconstruction.profile.invalid") from None
    if type(mapping) is not dict:
        raise ReconstructionFailure("reconstruction.profile.invalid")
    if "execution_profile" not in mapping:
        if profile.profile_id in {item.profile_id for item in PROFILES}:
            raise ReconstructionFailure("reconstruction.accelerator.profile_mismatch")
        return
    try:
        selected = resolve_profile(profile.profile_id)
        if (
            profile.profile_version != "4.0"
            or profile.environment_digest != selected.digest
            or mapping["execution_profile"] != selected.document()
            or mapping.get("execution_profile_digest") != selected.digest
        ):
            raise ValueError()
    except (TypeError, ValueError):
        raise ReconstructionFailure(
            "reconstruction.accelerator.profile_mismatch"
        ) from None
    from carbon.reconstruction.worker.model import DevelopmentWorkerProfile

    # A prospective TPU request/profile is not a validated TPU host adapter.
    # Keep this before staging, numerical imports and backend initialization,
    # including when a caller constructs a typed internal worker profile.
    if selected is TPU_PROFILE:
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")

    from carbon.reconstruction.worker.model import STRICT_HOST_GRANT_AUTHORITY

    # A local development approval never satisfies strict admission, however it
    # is labelled: its authority is checked, not merely the presence of a digest
    # in the field a strict grant would have occupied.
    if (
        type(worker_profile) is not DevelopmentWorkerProfile
        or worker_profile.accelerator_profile_id != selected.profile_id
        or worker_profile.accelerator_grant_digest is None
        or worker_profile.accelerator_authority != STRICT_HOST_GRANT_AUTHORITY
    ):
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")
