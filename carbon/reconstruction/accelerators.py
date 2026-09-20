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


class AcceleratorLane(str, Enum):
    """Which requirements apply, decided by the role rather than by a grant.

    Both roles have existed from the beginning and both were routed through one
    admission path written to validator requirements: a host grant asserting
    exclusive use of a dedicated device. Dispatch was disabled, so nobody had to
    find out whether a miner could satisfy that. When one common platform turned
    out to be unable to enumerate compute processes at all, every miner host was
    blocked by a requirement that had never been argued for on the miner side.

    The CPU lane is the decisive comparison: a miner runs CPU reconstruction with
    no grant, no lease, and no proof that nothing else is using their CPU.
    Containment, input binding and validator reconstruction carry the trust
    there. The GPU lane matches that model plus a device rather than inventing a
    stricter one.

    So the two lanes rest on different things. A miner is given nothing secret -
    a public plan and public TRAIN material - so device side-channels protect
    nothing, and the real question is whether this miner computed what they
    submitted, which content binding and downstream reconstruction answer. A
    validator is the arbiter and may hold protected material, where
    contamination, nondeterminism and side channels matter and exclusivity earns
    its cost.
    """

    #: Containment and attribution. Never claims exclusivity.
    MINER_CONTAINED = "MINER_CONTAINED"
    #: Isolation and determinism. The existing strict contract, unchanged.
    VALIDATOR_ISOLATED = "VALIDATOR_ISOLATED"


def lane_for_role(role: AcceleratorRole) -> AcceleratorLane:
    """The lane a role runs in. Not selectable, and not inferred from a grant."""
    if role is AcceleratorRole.MINER_RESEARCH:
        return AcceleratorLane.MINER_CONTAINED
    if role is AcceleratorRole.VALIDATOR_RECONSTRUCTION:
        return AcceleratorLane.VALIDATOR_ISOLATED
    raise ValueError("exact execution role required")


ASSURANCE_SCHEMA = "carbon.accelerator-assurance.v1"

# What a miner-lane result does and does not carry. Stated as a closed record
# rather than as prose, so a consumer can reject it on its own terms instead of
# having to know which lane produced it.
#
# Nothing here is a weaker version of the strict claims. The strict claims are
# absent, and their absence is written down.
MINER_LANE_ASSURANCE = {
    "schema": ASSURANCE_SCHEMA,
    "lane": AcceleratorLane.MINER_CONTAINED.value,
    "established": (
        "TASK_OWNED_CONTAINER_IDENTITY_AND_EXIT",
        "PINNED_IMAGE_AND_ENVIRONMENT_LOCK",
        "INPUT_AND_PLAN_CONTENT_BINDING",
        "PER_RUN_DEVICE_BINDING_FROM_INSTALLED_RECORD",
        "TASK_OWNED_RESOURCE_REMOVAL",
        "BOUNDED_DEADLINE_MEMORY_AND_OUTPUT",
    ),
    "not_established": (
        "WHOLE_DEVICE_EXCLUSIVITY",
        "FOREIGN_COMPUTE_PROCESS_ABSENCE",
        "DEVICE_MEMORY_SANITIZATION_BETWEEN_TENANTS",
        "WHOLE_DEVICE_RELEASE_AFTER_RUN",
    ),
    # A candidate submission, verified downstream exactly as a CPU result is.
    "verification": "DOWNSTREAM_VALIDATOR_RECONSTRUCTION",
    "official_eligible": False,
    "validator_grade": False,
    "strict_equivalent": False,
}


def miner_lane_assurance() -> dict[str, object]:
    """A fresh copy of the miner assurance label, with tuples as lists.

    Returned rather than exported directly so a caller cannot mutate the record
    every other caller reads.
    """
    return {
        key: list(value) if type(value) is tuple else value
        for key, value in MINER_LANE_ASSURANCE.items()
    }


def assurance_permits_official_use(assurance: object) -> bool:
    """Whether a result's own label permits official or strict use.

    False for every miner-lane label, and false for an absent, malformed or
    unrecognised one: a consumer that cannot tell what produced a result must
    not treat it as the strongest thing it could have been.

    **This is not the enforcement boundary.** Whether a launch actually ran
    under the strict contract is decided by its typed authority at admission,
    which is not something a record can assert about itself - a forged label
    changes what a record claims, never what it was permitted to do. This reads
    the claim, for a consumer deciding how to treat evidence it has been handed.
    Both exist because they answer different questions.
    """
    if type(assurance) is not dict or assurance.get("schema") != ASSURANCE_SCHEMA:
        return False
    return (
        assurance.get("official_eligible") is True
        and assurance.get("validator_grade") is True
        and assurance.get("lane") == AcceleratorLane.VALIDATOR_ISOLATED.value
    )


class AcceleratorUnavailable(RuntimeError):
    """A prepared profile is not an admitted execution or a resource grant."""


@dataclass(frozen=True, slots=True)
class AcceleratorProfile:
    """What the work needs, identically on every machine.

    This carries no device UUID, no marketed device name, no driver version and
    no provider. Those describe one host and live in an operator-installed
    `HostDeviceRecord`, so a miner runs Carbon on their own hardware by
    installing a record rather than by editing this file. Keeping them out is
    also what lets two runs on different machines share one profile digest and
    stay comparable.
    """

    profile_id: str
    backend: Backend
    local_device_count: int
    global_device_count: int
    process_count: int
    topology: str
    environment_file: str
    environment_lock_digest: str
    # Retained because profiles accepted on main pinned a host's device into the
    # profile itself, and their documents are already recorded under
    # `carbon.accelerator-profile.v1`. Dropping the three keys would have changed
    # what that schema serializes without changing what it is called, moving
    # every one of those digests. A portable profile leaves all three None, which
    # is the honest statement that it pins no device: the host's hardware is
    # installed evidence, not a field of the workload.
    device_kind: str | None = None
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

    @property
    def host_pinned(self) -> bool:
        """Whether this profile names a host's hardware in the workload itself."""
        return any(
            value is not None
            for value in (self.device_kind, self.device_uuid, self.host_driver)
        )

    def document(self) -> dict[str, object]:
        """The serialized profile, in the shape its version actually defines.

        Two shapes, two versions, because they are two different bodies. `v1`
        carries the device a profile pins - it is what every accepted record was
        written under, and it keeps that exact key set so those digests do not
        move. `v2` is the portable shape and omits those keys entirely rather
        than writing them as null: a workload profile that names no device
        should not have somewhere to put one.
        """
        fields = asdict(self)
        if self.host_pinned:
            schema = "carbon.accelerator-profile.v1"
        else:
            schema = "carbon.accelerator-profile.v2"
            for key in ("device_kind", "device_uuid", "host_driver"):
                fields.pop(key)
        return {
            "schema": schema,
            **fields,
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
    "carbon_jax_cuda13_nvidia_development_v1",
    Backend.NVIDIA,
    1,
    1,
    1,
    "single-device",
    ".devcontainer/accelerators/cuda13-py311.txt",
    "sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434",
)
TPU_PROFILE = AcceleratorProfile(
    "carbon_jax_tpu_v5e_8_development_v1",
    Backend.TPU,
    8,
    8,
    1,
    "2x4; provisioning SKU and observed topology pending",
    ".devcontainer/accelerators/tpu-py311.txt",
    "sha256:f42354e5eaec6c995fbee84407b095529b201ce82c04ea78b37777581d7bb3b2",
    device_kind="TPU v5 lite",
)

# The GPU profile accepted on main, which pinned one laptop's device into the
# workload. The portable profile above replaces it for new work, but replacing
# it in the registry would have made every record naming it unresolvable - a
# record does not stop meaning what it meant because a better profile exists.
# It is retained with its original body, and therefore its original digest.
#
# Retention is interpretation, not permission: it is deliberately absent from
# PROFILES, so `_registered` refuses it and it can never be dispatched, given a
# worker environment, or admitted. Old records keep their identity and their
# assurance level; they do not acquire the portable profile's.
RTX3060_LAPTOP_PROFILE = AcceleratorProfile(
    "carbon_jax_cuda13_rtx3060_laptop_development_v1",
    Backend.NVIDIA,
    1,
    1,
    1,
    "single-device",
    ".devcontainer/accelerators/cuda13-py311.txt",
    "sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434",
    device_kind="NVIDIA GeForce RTX 3060 Laptop GPU",
    device_uuid="GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81",
    host_driver="581.95",
)

PROFILES = (GPU_PROFILE, TPU_PROFILE)
HISTORICAL_PROFILES = (RTX3060_LAPTOP_PROFILE,)


def resolve_profile(profile_id: str) -> AcceleratorProfile:
    """Interpret a profile identity, current or historical.

    Reading an old record is not running it. A historical profile resolves here
    so its document, digest and meaning stay recoverable, and is refused by
    `_registered` wherever execution is actually decided.
    """
    if type(profile_id) is str:
        for profile in PROFILES + HISTORICAL_PROFILES:
            if profile.profile_id == profile_id:
                return profile
    raise ValueError("unregistered accelerator profile")


def dispatchable(profile: object) -> bool:
    """Whether this profile may be executed, as opposed to merely understood."""
    return type(profile) is AcceleratorProfile and profile in PROFILES


def _registered(profile: AcceleratorProfile) -> None:
    """The dispatch gate. Only a current profile may be executed."""
    if not dispatchable(profile):
        raise ValueError("exact registered accelerator profile required")


def _known(profile: AcceleratorProfile) -> None:
    """The interpretation gate: a profile this repository can still describe.

    Wider than `_registered` on purpose, and only for reading. Verifying what a
    retained plan pinned means computing what its profile required, which is a
    statement about a record rather than a step towards running it. An unknown
    profile is still refused, so this is not an escape from the registry - it is
    the difference between understanding a record and executing one.
    """
    if type(profile) is not AcceleratorProfile or profile not in (
        PROFILES + HISTORICAL_PROFILES
    ):
        raise ValueError("exact registered accelerator profile required")


def worker_environment(
    profile: AcceleratorProfile, role: AcceleratorRole, *, host_device=None
) -> dict[str, str]:
    """Proposed closed worker overlay, never applied to the control plane.

    The controller still owns the complete environment and role/principal-bound
    scratch mount. No persistent compilation cache crosses worker boundaries.
    Disabling preallocation is not a GPU memory cap or partition policy.

    `host_device` supplies which device this host exposes. It is required for a
    device-backed backend and must be the record already bound to `profile`, so
    the visible device comes from installed host evidence rather than from a
    constant compiled into Carbon.
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
        from carbon.reconstruction.host_inventory import require_host_device

        require_host_device(host_device, profile)
        result.update(
            {
                "CUDA_VISIBLE_DEVICES": host_device.device_uuid,
                # The worker cannot read the host record - it is operator-owned
                # storage outside the container - so the controller states which
                # device kind the run is bound to. The worker then checks what
                # the numerical backend reports against this, and refuses if the
                # variable is missing rather than skipping the check.
                "CARBON_ACCELERATOR_DEVICE_KIND": host_device.device_kind,
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
    expected_device_kind: str,
) -> None:
    """Check exact numerical observations; not physical-device attestation.

    UUID, driver, physical topology, allocation exclusivity and memory enforcement
    need independent supervisor observations; JAX's device kind cannot prove them.
    """
    _registered(profile)
    # The expected device kind comes from the host record the controller bound
    # this run to, not from a model name compiled into Carbon. The check is as
    # exact as it was; only its anchor moved off this machine.
    if type(expected_device_kind) is not str or not expected_device_kind:
        raise ValueError("expected device kind required")
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
            device.device_kind != expected_device_kind for device in observation.devices
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
    """Add explicit plugin pins; the profile also binds the entire resolved lock.

    Interpretation, not dispatch: this is how a retained plan's pinned
    dependency set is recomputed in order to verify it. Admission, the worker
    overlay and the observation check remain `_registered`, so a historical
    profile can be described here and still never reach a device.
    """
    _known(profile)
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


def require_local_diagnostic_profile_admission(profile, *, worker_profile=None) -> None:
    """Admit an operator-only LOCAL development profile.

    This is a parallel authority, never a relaxation of the strict one and never
    reached by falling back from a refused strict admission. A caller selects it
    by presenting a worker profile whose typed authority is the local variant;
    anything else belongs to `require_reconstruction_profile_admission`, which
    continues to reject local profiles at every strict entry point.
    """
    from carbon.reconstruction.model import ReconstructionFailure, ReconstructionProfile
    from carbon.reconstruction.worker.model import (
        LOCAL_DEVELOPMENT_AUTHORITY,
        DevelopmentWorkerProfile,
    )

    if (
        type(worker_profile) is not DevelopmentWorkerProfile
        or worker_profile.accelerator_authority != LOCAL_DEVELOPMENT_AUTHORITY
    ):
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")
    # Deliberately self-contained rather than sharing the strict helper's body:
    # the strict control stays exactly as written and reviewed. A drift test
    # asserts both refuse the same malformed and TPU profiles.
    if type(profile) is not ReconstructionProfile:
        raise ReconstructionFailure("reconstruction.profile.invalid")
    try:
        mapping = json.loads(profile.mapping_receipt_json)
    except (TypeError, ValueError):
        raise ReconstructionFailure("reconstruction.profile.invalid") from None
    if type(mapping) is not dict or "execution_profile" not in mapping:
        # A CPU plan carries no accelerator, so a local authority is meaningless.
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")
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
    # The local variant exists only for the GPU profile. A TPU request is
    # refused here as it is on the strict path.
    if (
        selected is not GPU_PROFILE
        or worker_profile.accelerator_profile_id != selected.profile_id
        or worker_profile.accelerator_grant_digest is None
        or worker_profile.accelerator_plan_digest is None
    ):
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")


def require_miner_lane_profile_admission(profile, *, worker_profile=None) -> None:
    """Admit a miner-lane accelerator profile.

    A parallel authority, never a relaxation of the strict one and never reached
    by falling back from a refused strict admission. A caller selects it by
    presenting a worker profile whose typed authority is the miner variant.

    What it does not require is the point: no host grant, no exclusive lease, no
    compute-process enumeration and no exclusivity claim. A miner receives a
    public plan and public TRAIN material, so there is nothing on their host to
    leak and device side-channels protect nothing. Whether they computed what
    they submitted is answered by content binding and downstream validator
    reconstruction, exactly as it is for a CPU submission.

    What it does require is containment, which is checked elsewhere and bound
    here: the pinned image and environment lock, the named device from the
    installed host record, and the resolved effective controls.
    """
    from carbon.reconstruction.model import ReconstructionFailure, ReconstructionProfile
    from carbon.reconstruction.worker.model import (
        MINER_HOST_AUTHORITY,
        DevelopmentWorkerProfile,
    )

    if (
        type(worker_profile) is not DevelopmentWorkerProfile
        or worker_profile.accelerator_authority != MINER_HOST_AUTHORITY
    ):
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")
    # Deliberately self-contained rather than sharing the strict helper's body,
    # for the same reason the local variant is: the strict control stays exactly
    # as written and reviewed. A drift test asserts all three refuse the same
    # malformed and TPU profiles.
    if type(profile) is not ReconstructionProfile:
        raise ReconstructionFailure("reconstruction.profile.invalid")
    try:
        mapping = json.loads(profile.mapping_receipt_json)
    except (TypeError, ValueError):
        raise ReconstructionFailure("reconstruction.profile.invalid") from None
    if type(mapping) is not dict or "execution_profile" not in mapping:
        # A CPU plan carries no accelerator, so a miner lane is meaningless.
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")
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
    # The miner lane exists only for the portable GPU profile. A TPU request is
    # refused here as it is on every other path, and a retained profile is not
    # an execution route however a caller labels it.
    if (
        selected is not GPU_PROFILE
        or worker_profile.accelerator_profile_id != selected.profile_id
        or worker_profile.accelerator_device_uuid is None
    ):
        raise ReconstructionFailure("reconstruction.accelerator.admission_disabled")


def require_profile_admission(profile, *, worker_profile=None) -> None:
    """Route to the authority the worker profile declares, never as a fallback.

    Staging and the worker-side reader accept every variant, so they dispatch on
    the typed authority rather than trying strict first and retrying something
    weaker. A refused strict admission does not become a miner run, and a miner
    run is not presentable as strict: each authority reaches exactly one check.
    """
    from carbon.reconstruction.worker.model import (
        LOCAL_DEVELOPMENT_AUTHORITY,
        MINER_HOST_AUTHORITY,
        DevelopmentWorkerProfile,
    )

    if type(worker_profile) is DevelopmentWorkerProfile:
        if worker_profile.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY:
            require_local_diagnostic_profile_admission(
                profile, worker_profile=worker_profile
            )
            return
        if worker_profile.accelerator_authority == MINER_HOST_AUTHORITY:
            require_miner_lane_profile_admission(profile, worker_profile=worker_profile)
            return
    require_reconstruction_profile_admission(profile, worker_profile=worker_profile)
