"""The device classes a validator may score on (VALIDATOR-27).

A validator's GPU reconstruction is admitted only for a device class whose
hardware acceptance has passed: for battery, the A40 acceptance
(OWNER-A40-ACCEPTANCE-GRANT-01), which shows the released validator image
rebuilding to the same digest within a host and across hosts under the
pinned determinism configuration. Until a class is entered here, with the
owner's record and the acceptance evidence, no validator scores on it: GPU
deployments refuse at start, and a GPU run refuses before dispatch.

This is a registered list, not a configuration value: it changes only by a
reviewed commit naming the record. Empty until the A40 acceptance passes.
"""

from __future__ import annotations

#: `{device_kind: {profile_id: {"record", "evidence"}}}`: a class is
#: accepted per accelerator profile, so a JAX acceptance never admits the
#: PyTorch GPU worker (or the reverse). Empty: no class has passed a hardware
#: acceptance yet.
ACCEPTED_DEVICE_CLASSES: dict = {}


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
