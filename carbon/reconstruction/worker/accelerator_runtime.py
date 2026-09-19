"""Host admission and exclusive ownership for the existing C-03 controller.

This module neither issues grants nor schedules work. It reuses operator-private
record validation and the existing numerical-supervisor lock. Its fixed host
root prevents a different output/campaign directory from making another slot.
"""

from __future__ import annotations

import math
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker.model import (
    PRODUCTIVE_DEADLINE_SECONDS,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    exact_digest,
    tagged_sha256,
)

HOST_ROOT = Path("/var/lib/carbon/accelerators")
GRANT_SCHEMA = "carbon.accelerator-host-grant.v1"


@dataclass(frozen=True, slots=True)
class AcceleratorHostAdmission:
    """Immutable reference to an operator-installed, revocable host grant."""

    document: dict[str, object]
    digest: str

    @classmethod
    def load(cls) -> AcceleratorHostAdmission:
        from carbon.development_session.profile import canonical
        from carbon.development_session.research_admission import private_json

        try:
            document = private_json(HOST_ROOT / "grant.json")
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        return cls(document, tagged_sha256(canonical(document)))

    def verify(
        self,
        *,
        principal: str,
        state_root: Path,
        image: WorkerImageIdentity,
        role: AcceleratorRole,
        now: float,
        dispatch: bool = False,
    ) -> None:
        fresh = self.load()
        if (HOST_ROOT / "device-quarantined").exists():
            raise WorkerFailure(WorkerCode.QUARANTINED)
        if fresh.document != self.document or fresh.digest != self.digest:
            raise WorkerFailure(WorkerCode.POLICY)
        doc = self.document
        fields = {
            "schema",
            "status",
            "authority",
            "grant_id",
            "host_root",
            "controller_root",
            "principal",
            "roles",
            "device_uuid",
            "execution_profile_digest",
            "image_id",
            "resource_policy_digest",
            "resource_class_digest",
            "expires_unix",
            "allocation",
            "cleanup",
            "host_use",
        }
        if (
            set(doc) != fields
            or doc["schema"] != GRANT_SCHEMA
            or doc["status"] != "APPROVED"
            or type(doc["authority"]) is not str
            or not doc["authority"]
            or type(doc["grant_id"]) is not str
            or not doc["grant_id"]
            or doc["host_root"] != str(HOST_ROOT)
            or doc["controller_root"] != str(state_root)
            or state_root.resolve() != state_root
            or doc["principal"] != principal
            or type(role) is not AcceleratorRole
            or type(doc["roles"]) is not list
            or not doc["roles"]
            or any(
                value not in [r.value for r in AcceleratorRole]
                for value in doc["roles"]
            )
            or role.value not in doc["roles"]
            or doc["device_uuid"] != GPU_PROFILE.device_uuid
            or doc["execution_profile_digest"] != GPU_PROFILE.digest
            or type(image) is not WorkerImageIdentity
            or doc["image_id"] != image.image_id
            or image.lock_digest != GPU_PROFILE.environment_lock_digest
            or doc["allocation"] != "EXCLUSIVE_SINGLE_DEVICE"
            or doc["cleanup"] != "EXACT_GRANT_OWNED_CONTAINERS_AND_DEVICE_RELEASE"
            or doc["host_use"] != "DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE"
        ):
            raise WorkerFailure(WorkerCode.POLICY)
        exact_digest(doc["resource_policy_digest"])
        exact_digest(doc["resource_class_digest"])
        expiry = doc["expires_unix"]
        if (
            type(now) is not float
            or not math.isfinite(now)
            or type(expiry) not in (float, int)
            or not math.isfinite(expiry)
            or now >= expiry
            or (dispatch and now + PRODUCTIVE_DEADLINE_SECONDS > expiry)
        ):
            raise WorkerFailure(WorkerCode.DEADLINE)

    @contextmanager
    def exclusive_lease(self):
        from carbon.development_session.research_carrier import _numerical_lease

        # The installed private grant's parent is the sole shared host lock root.
        # No request, output directory or caller-selected path can create a slot.
        try:
            with _numerical_lease(SimpleNamespace(root=HOST_ROOT)):
                yield
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.CONFLICT) from None


def verify_image_and_toolkit(*, cli, image: WorkerImageIdentity) -> None:
    """Read daemon/image metadata only; never initialize a numerical backend."""
    if image.lock_digest != GPU_PROFILE.environment_lock_digest:
        raise WorkerFailure(WorkerCode.POLICY)
    info = cli.json(["info", "--format", "{{json .}}"])
    if type(info) is not dict or "nvidia" not in (info.get("Runtimes") or {}):
        raise WorkerFailure(WorkerCode.UNAVAILABLE)
    value = cli.json(["image", "inspect", image.image_id, "--format", "{{json .}}"])
    labels = value.get("Config", {}).get("Labels", {}) if type(value) is dict else {}
    if (
        labels.get("org.opencontainers.image.carbon.accelerator.profile")
        != GPU_PROFILE.digest
        or labels.get("org.opencontainers.image.carbon.accelerator.environment")
        != GPU_PROFILE.environment_lock_digest
    ):
        raise WorkerFailure(WorkerCode.POLICY)


def device_request() -> dict[str, object]:
    return {
        "Driver": "nvidia",
        "Count": 0,
        "DeviceIDs": [GPU_PROFILE.device_uuid],
        "Capabilities": [["gpu"]],
        "Options": {},
    }


# Driver models whose compute-process enumeration may be read as complete.
# "N/A" is the Linux reading of a Windows-only field; TCC is the Windows compute
# driver model. Anything else, including an absent or malformed reading, stays
# unestablished, so this allowlist fails closed by construction.
ESTABLISHED_ENUMERATION_DRIVER_MODELS = frozenset({"N/A", "TCC"})


def process_enumeration_established(driver_model: object) -> bool:
    """Whether an empty compute-process list may be read as an idle device.

    An unsupported query and a genuinely idle device both return nothing, so
    emptiness alone is never evidence of exclusivity. NVIDIA documents WDDM/WSL
    NVML process enumeration as incomplete and reports per-process memory as
    unavailable under WDDM, so no WDDM observation can carry the exclusivity
    this contract requires. Capability is read from the observing source, never
    asserted by an operator document, a grant field or a caller argument.
    """
    if type(driver_model) is not str:
        return False
    return driver_model.strip().upper() in ESTABLISHED_ENUMERATION_DRIVER_MODELS


def inspect_gpu_device(*, cli, container_name: str) -> dict[str, object]:
    """Observe the fixed device from the bounded container before authorization."""
    result = cli.run(
        [
            "exec",
            container_name,
            "/usr/bin/nvidia-smi",
            "--query-gpu=uuid,name,driver_version,memory.total,display_active",
            "--format=csv,noheader,nounits",
        ],
        timeout=10,
    )
    try:
        rows = result.stdout.decode("ascii", "strict").strip().splitlines()
        values = [part.strip() for part in rows[0].split(",")]
        if (
            len(rows) != 1
            or len(values) != 5
            or values[0] != GPU_PROFILE.device_uuid
            or values[1] != GPU_PROFILE.device_kind
            or values[2] != GPU_PROFILE.host_driver
            or values[3] != "6144"
            or values[4].lower() != "disabled"
        ):
            raise ValueError()
        model = cli.run(
            [
                "exec",
                container_name,
                "/usr/bin/nvidia-smi",
                "--query-gpu=driver_model.current",
                "--format=csv,noheader,nounits",
            ],
            timeout=10,
        )
        if not process_enumeration_established(
            model.stdout.decode("ascii", "strict").strip()
        ):
            # Refuse rather than record an empty foreign-process list: this
            # source cannot be shown to enumerate compute processes, so its
            # silence is unestablished, not observed exclusivity.
            raise ValueError()
        processes = cli.run(
            [
                "exec",
                container_name,
                "/usr/bin/nvidia-smi",
                "--query-compute-apps=pid,gpu_uuid",
                "--format=csv,noheader,nounits",
            ],
            timeout=10,
        )
        if processes.stdout.strip():
            raise ValueError()
    except (UnicodeError, ValueError, IndexError):
        raise WorkerFailure(WorkerCode.POLICY) from None
    return {
        "uuid": values[0],
        "name": values[1],
        "driver": values[2],
        "memory_capacity_mib": 6144,
        "display_active": False,
        "other_compute_processes": [],
        "device_memory_cap": "EXCLUSIVE_ALLOCATION_NOT_HOST_CGROUP",
        "evidence": "OBSERVED_NOT_SECURITY_QUALIFIED",
    }


def reject_existing_device_containers(*, cli) -> None:
    """After controller loss, a released flock cannot duplicate a live allocation.

    Retained containers block admission until the existing watchdog/reconciliation
    path confirms exact removal. This function never deletes unrelated work.
    """
    if (HOST_ROOT / "active-allocation.json").exists():
        raise WorkerFailure(WorkerCode.CONFLICT)
    raw = cli.run(
        [
            "ps",
            "--all",
            "--filter",
            f"label=carbon.accelerator.device={GPU_PROFILE.device_uuid}",
            "--format",
            "{{json .ID}}",
        ],
        timeout=10,
    ).stdout
    if raw.strip():
        raise WorkerFailure(WorkerCode.CONFLICT)


def mark_device_allocation(*, container_name: str, launch_digest: str) -> None:
    """Persist ownership before create, including an uncertain create response."""
    from carbon.development_session.profile import canonical
    from carbon.reconstruction.worker.model import exact_token

    payload = {
        "container_name": exact_token(container_name),
        "launch_digest": exact_digest(launch_digest),
    }
    try:
        path = HOST_ROOT / "active-allocation.json"
        with path.open("xb") as stream:
            stream.write(canonical(payload))
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
        descriptor = os.open(HOST_ROOT, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        raise WorkerFailure(WorkerCode.CONFLICT) from None


def owns_device_allocation(*, container_name: str, launch_digest: str) -> bool:
    from carbon.development_session.research_admission import private_json

    path = HOST_ROOT / "active-allocation.json"
    if not path.exists():
        return False
    try:
        return private_json(path) == {
            "container_name": container_name,
            "launch_digest": launch_digest,
        }
    except (OSError, ValueError):
        raise WorkerFailure(WorkerCode.CLEANUP) from None


def finish_device_allocation(*, container_name: str, launch_digest: str) -> None:
    if not owns_device_allocation(
        container_name=container_name, launch_digest=launch_digest
    ):
        raise WorkerFailure(WorkerCode.CLEANUP)
    verify_device_release()
    try:
        (HOST_ROOT / "active-allocation.json").unlink()
        descriptor = os.open(HOST_ROOT, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        raise WorkerFailure(WorkerCode.CLEANUP) from None


def admission_document(admission: AcceleratorHostAdmission) -> dict[str, object]:
    # Only identity is staged/recorded; the grant path and operator document never
    # enter the worker. External credential/authority records remain host-owned.
    return {
        "grant_digest": admission.digest,
        "profile_digest": GPU_PROFILE.digest,
        "device_uuid": GPU_PROFILE.device_uuid,
    }


def verify_device_release() -> None:
    """Observe host-owned GPU release after exact container removal.

    No host install or device reset is performed. Unavailable telemetry remains
    unreconciled and blocks the one shared host slot, including after restart.
    The existing watchdog uses this same cleanup function through Docker removal.
    """
    from carbon.reconstruction.worker.docker_runtime import _bounded_capture

    try:
        candidates = (Path("/usr/bin/nvidia-smi"), Path("/usr/lib/wsl/lib/nvidia-smi"))
        binary = next((path for path in candidates if path.is_file()), None)
        if binary is None:
            raise WorkerFailure(WorkerCode.CLEANUP)
        command = [str(binary), "--id=" + GPU_PROFILE.device_uuid]
        environment = {"PATH": "/usr/bin:/bin"}
        model = _bounded_capture(
            command
            + ["--query-gpu=driver_model.current", "--format=csv,noheader,nounits"],
            environment=environment,
            timeout=10,
            maximum=4096,
        )
        # An unestablished source cannot certify a released device either, so
        # this stays unreconciled and keeps the existing quarantine behaviour
        # rather than reporting a verified whole-device release.
        if model.returncode != 0 or not process_enumeration_established(
            model.stdout.decode("ascii", "replace").strip()
        ):
            raise WorkerFailure(WorkerCode.CLEANUP)
        processes = _bounded_capture(
            command
            + ["--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader,nounits"],
            environment=environment,
            timeout=10,
            maximum=4096,
        )
        memory = _bounded_capture(
            command
            + [
                "--query-gpu=uuid,memory.used,display_active",
                "--format=csv,noheader,nounits",
            ],
            environment=environment,
            timeout=10,
            maximum=4096,
        )
        fields = [
            part.strip() for part in memory.stdout.decode("ascii").strip().split(",")
        ]
        if (
            processes.returncode != 0
            or processes.stdout.strip()
            or memory.returncode != 0
            or fields != [GPU_PROFILE.device_uuid, "0", "Disabled"]
        ):
            raise WorkerFailure(WorkerCode.CLEANUP)
    except (WorkerFailure, OSError, UnicodeError):
        # This is controller-owned fixed storage, never supplied by a worker.
        # Removal requires operator reconciliation; changing output directories
        # cannot escape an unreconciled allocation.
        try:
            marker = HOST_ROOT / "device-quarantined"
            with marker.open("xb") as output:
                output.write(b"UNRECONCILED_DEVICE_RELEASE\n")
            marker.chmod(0o600)
        except FileExistsError:
            pass
        except OSError:
            pass
        raise WorkerFailure(WorkerCode.CLEANUP) from None
