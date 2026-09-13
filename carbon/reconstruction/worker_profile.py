"""Closed C-03 CPU DEVELOPMENT worker profile.

The profile is an engineering test envelope.  It is deliberately incapable of
authorizing protected inputs, security qualification, production, or LIVE use.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType

from carbon.reconstruction.model import ReconstructionFailure

_PROFILE_RESOURCE = "profiles/c03_cpu_development_v1.json"
_EXPECTED_TOP_LEVEL = frozenset(
    {
        "schema",
        "scope",
        "profile_id",
        "profile_version",
        "security_state",
        "protected_workloads_enabled",
        "trusted_host_assumption",
        "participant_inputs",
        "image",
        "source",
        "environment",
        "limits",
        "filesystem",
        "network",
        "termination",
        "claims",
    }
)
_EXPECTED_LIMITS = frozenset(
    {
        "cpus",
        "cpu_time_seconds",
        "memory_bytes",
        "swap_bytes",
        "wall_seconds",
        "pids",
        "threads",
        "scratch_bytes",
        "output_bytes",
        "open_files",
        "diagnostic_bytes",
    }
)


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _load_exact_json(payload: bytes) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in items:
            if key in value:
                raise ValueError
            value[key] = item
        return value

    try:
        parsed = json.loads(
            payload,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise ReconstructionFailure("reconstruction.worker.profile_invalid") from None
    if type(parsed) is not dict or set(parsed) != _EXPECTED_TOP_LEVEL:
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    return parsed


def _positive_integer(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    return value


@dataclass(frozen=True, slots=True)
class DevelopmentWorkerLimits:
    cpus: float
    cpu_time_seconds: None
    memory_bytes: int
    swap_bytes: int
    wall_seconds: int
    pids: int
    threads: int
    scratch_bytes: int
    output_bytes: int
    open_files: int
    diagnostic_bytes: int

    def __post_init__(self) -> None:
        if (
            type(self.cpus) is not float
            or not math.isfinite(self.cpus)
            or self.cpus <= 0
        ):
            raise ReconstructionFailure("reconstruction.worker.profile_invalid")
        if self.cpu_time_seconds is not None or self.swap_bytes != 0:
            raise ReconstructionFailure("reconstruction.worker.profile_invalid")
        for field in (
            "memory_bytes",
            "wall_seconds",
            "pids",
            "threads",
            "scratch_bytes",
            "output_bytes",
            "open_files",
            "diagnostic_bytes",
        ):
            object.__setattr__(self, field, _positive_integer(getattr(self, field)))
        if self.threads > self.pids or self.diagnostic_bytes > self.output_bytes:
            raise ReconstructionFailure("reconstruction.worker.profile_invalid")


@dataclass(frozen=True, slots=True, repr=False)
class DevelopmentWorkerProfile:
    profile_id: str
    profile_version: str
    profile_digest: str
    image_definition_sha256: str
    dependency_lock_sha256: str
    runtime_user: str
    runtime_architecture: str
    c02_environment_digest: str
    limits: DevelopmentWorkerLimits
    raw: Mapping[str, object]

    def __post_init__(self) -> None:
        if (
            self.profile_id != "carbon_c03_cpu_development_v1"
            or self.profile_version != "1.0"
            or self.runtime_user != "10001:10001"
            or self.runtime_architecture != "linux/amd64"
            or not self.profile_digest.startswith("sha256:")
            or not self.image_definition_sha256.startswith("sha256:")
            or not self.dependency_lock_sha256.startswith("sha256:")
            or not self.c02_environment_digest.startswith("sha256:")
        ):
            raise ReconstructionFailure("reconstruction.worker.profile_invalid")
        object.__setattr__(self, "raw", MappingProxyType(dict(self.raw)))


def load_development_worker_profile() -> DevelopmentWorkerProfile:
    """Load and strictly validate the sole non-production worker profile."""

    payload = files("carbon.reconstruction").joinpath(_PROFILE_RESOURCE).read_bytes()
    value = _load_exact_json(payload)
    if (
        value["schema"] != "carbon.c03.worker-profile.v1"
        or value["scope"] != "UNQUALIFIED_PUBLIC_DEVELOPMENT"
        or value["security_state"] != "REVIEWABLE_NOT_SECURITY_ACCEPTED"
        or value["protected_workloads_enabled"] is not False
    ):
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    image = value["image"]
    environment = value["environment"]
    limits = value["limits"]
    if (
        type(image) is not dict
        or type(environment) is not dict
        or type(limits) is not dict
    ):
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    if set(limits) != _EXPECTED_LIMITS:
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    if value["claims"] != {
        "production_repeat_count": None,
        "protected_workload_approval": None,
        "security_qualification": None,
        "hostile_host_resistance": None,
        "side_channel_resistance": None,
    }:
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    worker_limits = DevelopmentWorkerLimits(**limits)
    return DevelopmentWorkerProfile(
        profile_id=value["profile_id"],
        profile_version=value["profile_version"],
        profile_digest=_tagged(payload),
        image_definition_sha256=image["definition_sha256"],
        dependency_lock_sha256="sha256:" + environment["dependency_lock_sha256"],
        runtime_user=image["runtime_user"],
        runtime_architecture=image["runtime_architecture"],
        c02_environment_digest=environment["c02_environment_digest"],
        limits=worker_limits,
        raw=value,
    )


def verify_profile_sources(profile: DevelopmentWorkerProfile, repository: Path) -> None:
    """Verify the profile's image definition and dependency lock in a checkout."""

    if type(profile) is not DevelopmentWorkerProfile or not repository.is_absolute():
        raise ReconstructionFailure("reconstruction.worker.profile_invalid")
    expected = {
        repository / ".worker/Dockerfile": profile.image_definition_sha256,
        repository / "uv.lock": profile.dependency_lock_sha256,
    }
    for path, digest in expected.items():
        if (
            path.is_symlink()
            or not path.is_file()
            or _tagged(path.read_bytes()) != digest
        ):
            raise ReconstructionFailure("reconstruction.worker.profile_source_mismatch")


__all__ = [
    "DevelopmentWorkerLimits",
    "DevelopmentWorkerProfile",
    "load_development_worker_profile",
    "verify_profile_sources",
]
