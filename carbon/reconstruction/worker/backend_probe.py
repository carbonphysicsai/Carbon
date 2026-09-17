"""Explicit JAX backend observation for future worker profiles.

This module does not admit jobs, allocate cloud resources, or relax C-03's CPU
policy. Call it inside an already admitted, supervised worker process: backend
initialization may acquire device resources and is not a pure metadata read.
Observations are diagnostics, not attestation or scientific qualification.
"""

from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

SCHEMA = "carbon.jax-backend-observation.v1"
MAX_LOCAL_DEVICES = 1024


class Backend(str, Enum):
    CPU = "cpu"
    NVIDIA = "cuda"
    TPU = "tpu"


class ProbeCode(str, Enum):
    INVALID_REQUEST = "backend_probe.invalid_request"
    UNAVAILABLE = "backend_probe.backend_unavailable"
    INVALID_OBSERVATION = "backend_probe.invalid_observation"
    PLATFORM_MISMATCH = "backend_probe.platform_mismatch"
    DEVICE_COUNT_MISMATCH = "backend_probe.device_count_mismatch"
    RUNTIME_MISMATCH = "backend_probe.runtime_mismatch"


class BackendProbeError(RuntimeError):
    """Closed diagnostic errors; do not echo driver messages or private paths."""

    def __init__(self, code: ProbeCode):
        if type(code) is not ProbeCode:
            raise TypeError("ProbeCode required")
        self.code = code
        super().__init__(code.value)


def _text(value: object, *, maximum: int = 160) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= maximum
        or not value.isascii()
        or any(ord(char) < 32 or ord(char) > 126 for char in value)
    ):
        raise BackendProbeError(ProbeCode.INVALID_OBSERVATION)
    return value


def _index(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 2**31 - 1:
        raise BackendProbeError(ProbeCode.INVALID_OBSERVATION)
    return value


@dataclass(frozen=True, slots=True)
class BackendRequest:
    """Exact local visibility and optional runtime pin; not a resource grant."""

    backend: Backend
    local_device_count: int = 1
    jax_version: str | None = None
    jaxlib_version: str | None = None

    def __post_init__(self):
        if (
            type(self.backend) is not Backend
            or type(self.local_device_count) is not int
            or not 1 <= self.local_device_count <= MAX_LOCAL_DEVICES
            or (self.jax_version is None) != (self.jaxlib_version is None)
        ):
            raise BackendProbeError(ProbeCode.INVALID_REQUEST)
        try:
            for value in (self.jax_version, self.jaxlib_version):
                if value is not None:
                    _text(value, maximum=64)
        except BackendProbeError:
            raise BackendProbeError(ProbeCode.INVALID_REQUEST) from None


@dataclass(frozen=True, slots=True)
class DeviceObservation:
    device_id: int
    process_index: int
    platform: str
    device_kind: str

    def __post_init__(self):
        _index(self.device_id)
        _index(self.process_index)
        _text(self.platform, maximum=16)
        _text(self.device_kind)


@dataclass(frozen=True, slots=True)
class BackendObservation:
    requested_backend: Backend
    jax_version: str
    jaxlib_version: str
    process_index: int
    x64_enabled: bool
    devices: tuple[DeviceObservation, ...]

    def __post_init__(self):
        if (
            type(self.requested_backend) is not Backend
            or type(self.x64_enabled) is not bool
            or type(self.devices) is not tuple
            or not 1 <= len(self.devices) <= MAX_LOCAL_DEVICES
            or any(type(device) is not DeviceObservation for device in self.devices)
        ):
            raise BackendProbeError(ProbeCode.INVALID_OBSERVATION)
        _text(self.jax_version, maximum=64)
        _text(self.jaxlib_version, maximum=64)
        _index(self.process_index)
        identifiers = [
            (device.process_index, device.device_id) for device in self.devices
        ]
        if len(set(identifiers)) != len(identifiers) or any(
            device.process_index != self.process_index for device in self.devices
        ):
            raise BackendProbeError(ProbeCode.INVALID_OBSERVATION)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "evidence_kind": "LOCAL_RUNTIME_OBSERVATION_ONLY",
            "requested_backend": self.requested_backend.value,
            "jax_version": self.jax_version,
            "jaxlib_version": self.jaxlib_version,
            "process_index": self.process_index,
            # A config flag is not proof that a backend implements FP64.
            "jax_x64_enabled": self.x64_enabled,
            "local_device_count": len(self.devices),
            "devices": [
                {
                    "device_id": device.device_id,
                    "process_index": device.process_index,
                    "platform": device.platform,
                    "device_kind": device.device_kind,
                }
                for device in self.devices
            ],
        }


def validate_observation(
    request: BackendRequest, observation: BackendObservation
) -> BackendObservation:
    if type(request) is not BackendRequest:
        raise BackendProbeError(ProbeCode.INVALID_REQUEST)
    if type(observation) is not BackendObservation:
        raise BackendProbeError(ProbeCode.INVALID_OBSERVATION)
    expected_platform = {
        Backend.CPU: "cpu",
        Backend.NVIDIA: "gpu",
        Backend.TPU: "tpu",
    }[request.backend]
    if observation.requested_backend is not request.backend or any(
        device.platform != expected_platform for device in observation.devices
    ):
        raise BackendProbeError(ProbeCode.PLATFORM_MISMATCH)
    if len(observation.devices) != request.local_device_count:
        raise BackendProbeError(ProbeCode.DEVICE_COUNT_MISMATCH)
    if request.jax_version is not None and (
        observation.jax_version != request.jax_version
        or observation.jaxlib_version != request.jaxlib_version
    ):
        raise BackendProbeError(ProbeCode.RUNTIME_MISMATCH)
    return observation


class BackendObserver(Protocol):
    def observe(self, backend: Backend) -> BackendObservation: ...


class JaxBackendObserver:
    """Lazy local observation. Never queries the default backend or falls back."""

    def observe(self, backend: Backend) -> BackendObservation:
        if type(backend) is not Backend:
            raise BackendProbeError(ProbeCode.INVALID_REQUEST)
        try:
            jax = importlib.import_module("jax")
            jaxlib = importlib.import_module("jaxlib")
            # 'cuda', not the generic 'gpu' alias, selects the NVIDIA backend.
            # Do not retry another backend after initialization fails.
            devices = jax.local_devices(backend=backend.value)
            if type(devices) not in (list, tuple) or len(devices) > MAX_LOCAL_DEVICES:
                raise BackendProbeError(ProbeCode.INVALID_OBSERVATION)
            return BackendObservation(
                requested_backend=backend,
                jax_version=jax.__version__,
                jaxlib_version=jaxlib.__version__,
                process_index=jax.process_index(backend=backend.value),
                x64_enabled=jax.config.jax_enable_x64,
                devices=tuple(
                    DeviceObservation(
                        device_id=device.id,
                        process_index=device.process_index,
                        platform=device.platform,
                        device_kind=device.device_kind,
                    )
                    for device in devices
                ),
            )
        except BackendProbeError:
            raise
        except Exception:  # noqa: BLE001 - redact runtime/driver diagnostics.
            raise BackendProbeError(ProbeCode.UNAVAILABLE) from None


def probe_backend(
    request: BackendRequest, *, observer: BackendObserver | None = None
) -> BackendObservation:
    """Check an explicit local backend. The caller still owns admission/isolation."""
    if type(request) is not BackendRequest:
        raise BackendProbeError(ProbeCode.INVALID_REQUEST)
    selected = observer if observer is not None else JaxBackendObserver()
    try:
        observation = selected.observe(request.backend)
    except BackendProbeError:
        raise
    except Exception:  # noqa: BLE001 - implementations may carry private errors.
        raise BackendProbeError(ProbeCode.UNAVAILABLE) from None
    return validate_observation(request, observation)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=[item.value for item in Backend], required=True
    )
    parser.add_argument("--local-device-count", type=int, default=1)
    parser.add_argument("--jax-version")
    parser.add_argument("--jaxlib-version")
    args = parser.parse_args(argv)
    try:
        request = BackendRequest(
            Backend(args.backend),
            args.local_device_count,
            args.jax_version,
            args.jaxlib_version,
        )
        result = probe_backend(request).to_dict()
    except BackendProbeError as error:
        print(json.dumps({"schema": SCHEMA, "error": error.code.value}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
