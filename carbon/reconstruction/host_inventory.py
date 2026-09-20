"""What one host's accelerator *is*, kept out of the source tree.

Carbon's accelerator workload profile describes what the work needs: a backend,
a device count, a dtype and precision policy, and a pinned environment. That
must be byte-identical on every machine, because it is part of what makes two
runs comparable.

What a particular device is - its UUID, its marketed name, its driver, how much
memory it has, which platform and container runtime sit in front of it, and who
provides it - is a property of one host. It belongs in an operator-installed
record, not in this repository. A miner installs that record with the onboarding
command and never edits Carbon to run on their own hardware, whether that is a
laptop, a workstation, a rented virtual machine or other hosted compute.

A record is *evidence about a host*, never authority to use it. It carries the
provenance of the observation that produced it, and it is always paired with a
separate grant or approval before anything may be dispatched. Installing a
record qualifies nothing and grants nothing.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.worker.model import (
    WorkerCode,
    WorkerFailure,
    tagged_sha256,
)

HOST_DEVICE_SCHEMA = "carbon.accelerator-host-device.v1"
HOST_DEVICE_RECORD = "host-device.json"

# A record states what was observed; it never states that the observation was
# complete, exclusive, or sufficient to qualify results.
HOST_DEVICE_AUTHORITY = "HOST_OBSERVATION_ONLY_NOT_QUALIFICATION"

# Where the host sits. This is descriptive: no platform is privileged, and none
# is treated as evidence that device telemetry is complete. That question is
# settled by the enumeration-capability rules in `accelerator_runtime`, which
# this record cannot override.
PLATFORMS = frozenset(
    {
        "WSL2",
        "LINUX_BARE_METAL",
        "LINUX_VIRTUAL_MACHINE",
        "HOSTED_COMPUTE_INSTANCE",
    }
)

# Docker Engine and Docker Desktop differ in ways that matter for device
# passthrough and for what the controller may observe, so the record names
# which one is in front of the device rather than inferring it at dispatch.
CONTAINER_RUNTIMES = frozenset({"DOCKER_ENGINE", "DOCKER_DESKTOP"})

DRIVER_MODELS = frozenset({"WDDM", "TCC", "N/A"})
DISPLAY_STATES = frozenset({"Enabled", "Disabled"})

REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "record_id",
        "workload_profile_id",
        "device_uuid",
        "device_kind",
        "driver_version",
        "driver_model",
        "compute_capability",
        "device_memory_mib",
        "display_active",
        "platform",
        "container_runtime",
        "provider",
        "observed_at_unix",
        "observation_provenance",
        "observation_authority",
    }
)

# A vendor's identifier for one device. Deliberately narrow in character set -
# no whitespace, no shell metacharacters, no newlines - so a record can never
# carry anything into a command line or a container label, but not tied to one
# vendor's format, because that would put a second vendor back in the source.
_DEVICE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}")

# NVIDIA reports `GPU-<uuid>` for a whole device and `MIG-<uuid>` for a MIG
# instance. This exact shape is required of a record bound to an NVIDIA
# workload, so that path is no less strict than when the UUID was a constant.
# Matching it is still not proof that the named device exists or is free.
_NVIDIA_DEVICE_UUID = re.compile(
    r"(?:GPU|MIG)-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
)
_COMPUTE_CAPABILITY = re.compile(r"[0-9]{1,2}\.[0-9]{1,2}")
# Deliberately narrow: a free-form vendor or host string must not be able to
# carry shell metacharacters, whitespace or newlines into a command line or a
# container label.
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
# Marketed device names contain spaces and mixed case, so they get their own
# rule; still no control characters, no newlines and a bounded length.
_DEVICE_KIND = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.\-]{0,95}")
_DRIVER_VERSION = re.compile(r"[0-9][0-9.]{0,15}")
# Provenance is a human sentence that is only ever stored and displayed, never
# executed or passed as an argument, so it may contain path separators. Control
# characters and newlines are still excluded.
_PROVENANCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.,:/\-]{0,255}")


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class HostDeviceRecord:
    """An operator-installed description of one accelerator on one host."""

    document: dict[str, object]
    digest: str

    @classmethod
    def load(cls, root: Path) -> HostDeviceRecord:
        """Read the record installed under `root`, or fail closed.

        A missing record is UNAVAILABLE, not an invitation to guess the host's
        hardware from whatever happens to be visible at dispatch time.
        """
        from carbon.development_session.profile import canonical
        from carbon.development_session.research_admission import private_json

        try:
            document = private_json(Path(root) / HOST_DEVICE_RECORD)
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.UNAVAILABLE) from None
        record = cls(document, tagged_sha256(canonical(document)))
        record.validate()
        return record

    def validate(self) -> None:
        """Check the record's own shape. This authorizes nothing."""
        doc = self.document
        if type(doc) is not dict or set(doc) != REQUIRED_FIELDS:
            raise WorkerFailure(WorkerCode.POLICY)
        if (
            doc["schema"] != HOST_DEVICE_SCHEMA
            or doc["observation_authority"] != HOST_DEVICE_AUTHORITY
            or not _matches(_TOKEN, doc["record_id"])
            or not _matches(_TOKEN, doc["workload_profile_id"])
            or not _matches(_DEVICE_IDENTIFIER, doc["device_uuid"])
            or not _matches(_DEVICE_KIND, doc["device_kind"])
            or not _matches(_DRIVER_VERSION, doc["driver_version"])
            or doc["driver_model"] not in DRIVER_MODELS
            or not _matches(_COMPUTE_CAPABILITY, doc["compute_capability"])
            or doc["display_active"] not in DISPLAY_STATES
            or doc["platform"] not in PLATFORMS
            or doc["container_runtime"] not in CONTAINER_RUNTIMES
            or not _matches(_TOKEN, doc["provider"])
            or not _matches(_PROVENANCE, doc["observation_provenance"])
        ):
            raise WorkerFailure(WorkerCode.POLICY)
        memory = doc["device_memory_mib"]
        if type(memory) is not int or memory <= 0 or memory > 1 << 24:
            raise WorkerFailure(WorkerCode.POLICY)
        observed = doc["observed_at_unix"]
        if type(observed) not in (float, int) or not math.isfinite(observed):
            raise WorkerFailure(WorkerCode.POLICY)
        if observed <= 0:
            raise WorkerFailure(WorkerCode.POLICY)

    # --- accessors, so callers never index the raw document ------------------

    @property
    def device_uuid(self) -> str:
        return str(self.document["device_uuid"])

    @property
    def device_kind(self) -> str:
        return str(self.document["device_kind"])

    @property
    def driver_version(self) -> str:
        return str(self.document["driver_version"])

    @property
    def driver_model(self) -> str:
        return str(self.document["driver_model"])

    @property
    def device_memory_mib(self) -> int:
        return int(self.document["device_memory_mib"])

    @property
    def display_active(self) -> str:
        return str(self.document["display_active"])

    @property
    def platform(self) -> str:
        return str(self.document["platform"])

    @property
    def container_runtime(self) -> str:
        return str(self.document["container_runtime"])

    @property
    def provider(self) -> str:
        return str(self.document["provider"])

    @property
    def workload_profile_id(self) -> str:
        return str(self.document["workload_profile_id"])


def require_host_device(record: HostDeviceRecord, profile) -> HostDeviceRecord:
    """Bind an installed host record to the workload profile it claims to serve.

    A record for one workload profile may never stand in for another. This is
    the per-run binding: the workload says what the run needs, the record says
    what this host is, and the two are checked against each other here rather
    than assumed to match because only one host was ever contemplated.
    """
    from carbon.reconstruction.accelerators import AcceleratorProfile

    if type(record) is not HostDeviceRecord:
        raise WorkerFailure(WorkerCode.POLICY)
    if type(profile) is not AcceleratorProfile:
        raise WorkerFailure(WorkerCode.POLICY)
    record.validate()
    if record.workload_profile_id != profile.profile_id:
        raise WorkerFailure(WorkerCode.POLICY)
    from carbon.reconstruction.worker.backend_probe import Backend

    if profile.backend is Backend.NVIDIA and not _matches(
        _NVIDIA_DEVICE_UUID, record.device_uuid
    ):
        raise WorkerFailure(WorkerCode.POLICY)
    return record


__all__ = [
    "CONTAINER_RUNTIMES",
    "DRIVER_MODELS",
    "HOST_DEVICE_AUTHORITY",
    "HOST_DEVICE_RECORD",
    "HOST_DEVICE_SCHEMA",
    "NVIDIA_DEVICE_UUID",
    "PLATFORMS",
    "HostDeviceRecord",
    "require_host_device",
]

# Exposed so the worker profile can hold a device binding to the same rule.
NVIDIA_DEVICE_UUID = _NVIDIA_DEVICE_UUID
