"""Shared synthetic host device records for the accelerator tests.

Each entry is a plausible *shape* of host - a consumer laptop behind WSL2, a
bare-metal workstation, a hosted instance, one device of a multi-device machine,
a MIG instance. They exist to show that expressing a different host needs no
source edit.

They are not hardware coverage claims. No device is attached anywhere in these
tests, nothing is dispatched, and installing a record qualifies nothing. Every
device UUID here is synthetic.
"""

import time

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.host_inventory import (
    HOST_DEVICE_AUTHORITY,
    HOST_DEVICE_RECORD,
    HOST_DEVICE_SCHEMA,
    HostDeviceRecord,
)

HOSTS = {
    # The shape of the machine this milestone was developed against: a consumer
    # laptop GPU reached through WSL2 and Docker Desktop, where the driver model
    # is WDDM and compute-process enumeration is therefore unsupported.
    "laptop_wsl2": {
        "record_id": "wsl2-consumer-gpu",
        "device_uuid": "GPU-00000000-1111-2222-3333-444444444444",
        "device_kind": "NVIDIA GeForce RTX 3060 Laptop GPU",
        "driver_version": "581.95",
        "driver_model": "WDDM",
        "compute_capability": "8.6",
        "device_memory_mib": 6144,
        "display_active": "Disabled",
        "platform": "WSL2",
        "container_runtime": "DOCKER_DESKTOP",
        "provider": "self-hosted",
    },
    # A different NVIDIA device on bare-metal Linux behind Docker Engine. Same
    # record format, different in every machine-specific value.
    "workstation_linux": {
        "record_id": "workstation-linux",
        "device_uuid": "GPU-55555555-6666-7777-8888-999999999999",
        "device_kind": "NVIDIA RTX A4000",
        "driver_version": "550.127",
        "driver_model": "N/A",
        "compute_capability": "8.6",
        "device_memory_mib": 16376,
        "display_active": "Disabled",
        "platform": "LINUX_BARE_METAL",
        "container_runtime": "DOCKER_ENGINE",
        "provider": "self-hosted",
    },
    # Rented compute from a third party. The provider is just a token in the
    # record; Carbon has no per-provider branch anywhere.
    "hosted_instance": {
        "record_id": "hosted-instance",
        "device_uuid": "GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "device_kind": "NVIDIA L4",
        "driver_version": "535.183",
        "driver_model": "N/A",
        "compute_capability": "8.9",
        "device_memory_mib": 23034,
        "display_active": "Disabled",
        "platform": "HOSTED_COMPUTE_INSTANCE",
        "container_runtime": "DOCKER_ENGINE",
        "provider": "example-provider",
    },
    # One device of a multi-device host. The single-device workload profile
    # still names exactly one device; the record says which.
    "multi_device_host": {
        "record_id": "multi-device-host",
        "device_uuid": "GPU-12121212-3434-5656-7878-909090909090",
        "device_kind": "NVIDIA A100-SXM4-40GB",
        "driver_version": "535.183",
        "driver_model": "N/A",
        "compute_capability": "8.0",
        "device_memory_mib": 40960,
        "display_active": "Disabled",
        "platform": "LINUX_VIRTUAL_MACHINE",
        "container_runtime": "DOCKER_ENGINE",
        "provider": "example-provider",
    },
    # A MIG instance rather than a whole device.
    "mig_instance": {
        "record_id": "mig-instance",
        "device_uuid": "MIG-fedcba98-7654-3210-fedc-ba9876543210",
        "device_kind": "NVIDIA A100-SXM4-40GB MIG 1g.5gb",
        "driver_version": "535.183",
        "driver_model": "N/A",
        "compute_capability": "8.0",
        "device_memory_mib": 4864,
        "display_active": "Disabled",
        "platform": "LINUX_VIRTUAL_MACHINE",
        "container_runtime": "DOCKER_ENGINE",
        "provider": "example-provider",
    },
    # A host for the prospective TPU workload. Its identifier is not
    # NVIDIA-shaped, which is exactly why the record format must not assume one
    # vendor's format.
    "tpu_host": {
        "record_id": "tpu-host",
        "device_uuid": "tpu-v5litepod-8:0",
        "device_kind": "TPU v5 lite",
        "driver_version": "1.14",
        "driver_model": "N/A",
        "compute_capability": "0.0",
        "device_memory_mib": 16384,
        "display_active": "Disabled",
        "platform": "HOSTED_COMPUTE_INSTANCE",
        "container_runtime": "DOCKER_ENGINE",
        "provider": "example-provider",
    },
}

DEFAULT_SHAPE = "laptop_wsl2"
NVIDIA_SHAPES = tuple(name for name in HOSTS if name != "tpu_host")


def document(shape=DEFAULT_SHAPE, **overrides):
    values = {
        "schema": HOST_DEVICE_SCHEMA,
        "workload_profile_id": GPU_PROFILE.profile_id,
        "observed_at_unix": float(int(time.time())),
        "observation_provenance": "nvidia-smi query, recorded by the operator",
        "observation_authority": HOST_DEVICE_AUTHORITY,
        **HOSTS[shape],
    }
    values.update(overrides)
    return values


def install(root, value=None):
    """Write a record into a synthetic host root, as an operator tool would."""
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / HOST_DEVICE_RECORD
    path.write_bytes(canonical(document() if value is None else value))
    path.chmod(0o600)
    return path


def installed(root, shape=DEFAULT_SHAPE, **overrides):
    install(root, document(shape, **overrides))
    return HostDeviceRecord.load(root)


def for_profile(root, profile, shape=None, **overrides):
    """A record describing a host that serves `profile`."""
    if shape is None:
        shape = (
            "tpu_host"
            if profile.profile_id.startswith("carbon_jax_tpu")
            else DEFAULT_SHAPE
        )
    return installed(root, shape, workload_profile_id=profile.profile_id, **overrides)


def identity_row(shape=DEFAULT_SHAPE):
    """The nvidia-smi identity line a host of this shape would report."""
    host = HOSTS[shape]
    return (
        f"{host['device_uuid']}, {host['device_kind']}, "
        f"{host['driver_version']}, {host['device_memory_mib']}, "
        f"{host['display_active']}"
    )
