"""The device classes a validator may score on (VALIDATOR-27).

A validator's GPU reconstruction is admitted only for a device class whose
hardware acceptance has passed: for battery, the A40 acceptance
(OWNER-A40-ACCEPTANCE-GRANT-01), which shows the released validator image
rebuilding to the same digest within a host and across hosts under the
pinned determinism configuration. Until a class is entered here, with the
owner's record and the acceptance evidence, no validator scores on it: GPU
deployments refuse at start, and a GPU run refuses before dispatch.

This is a registered list, not a configuration value: it changes only by a
reviewed commit naming the record. OWNER-GPU-DEVICE-CLASSES-01 (2026-10-09)
entered the A40 and the RTX 4090, each for JAX and PyTorch, for validator
scoring on testnet.
"""

from __future__ import annotations

#: The JAX and PyTorch GPU accelerator profiles
#: (`accelerators.GPU_PROFILE.profile_id`, `torch_profile.GPU_PROFILE_ID`).
JAX_GPU = "carbon_jax_cuda13_nvidia_development_v1"
TORCH_GPU = "carbon_torch_cuda13_nvidia_development_v1"
_OWNER = {
    "record": "OWNER-GPU-DEVICE-CLASSES-01",
    "evidence": (
        "the owner's direct acceptance, 2026-10-09, for validator scoring on "
        "testnet (.agent/decisions/2026-10-09-OWNER-GPU-DEVICE-CLASSES-01.md)"
    ),
}

#: `{device_kind: {profile_id: {"record", "evidence"}}}`: a class is
#: accepted per accelerator profile, so a JAX acceptance never admits the
#: PyTorch GPU worker (or the reverse). The device kind is the exact name
#: `nvidia-smi` reports, as the host device record binds it.
ACCEPTED_DEVICE_CLASSES: dict = {
    "NVIDIA A40": {JAX_GPU: dict(_OWNER), TORCH_GPU: dict(_OWNER)},
    "NVIDIA GeForce RTX 4090": {JAX_GPU: dict(_OWNER), TORCH_GPU: dict(_OWNER)},
}


class DeviceClassNotAccepted(ValueError):
    """No hardware acceptance names this device class (fail closed)."""

    code = "validator_device_class_not_accepted"


def require_accepted(device_kind, profile_id):
    """Refuse unless `device_kind` passed a hardware acceptance under
    `profile_id`."""
    profiles = ACCEPTED_DEVICE_CLASSES.get(device_kind)
    entry = profiles.get(profile_id) if type(profiles) is dict else None
    if type(entry) is not dict:
        raise DeviceClassNotAccepted(
            "no hardware acceptance names this device class for validator scoring"
        )
    return entry


__all__ = ["ACCEPTED_DEVICE_CLASSES", "DeviceClassNotAccepted", "require_accepted"]
