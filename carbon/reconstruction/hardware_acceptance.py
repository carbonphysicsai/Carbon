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
scoring on testnet. OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01 (2026-11-12)
enters the RTX 4090 (the GPUYard validator's GPU) for finney (mainnet 116),
under the same two profiles; the A40 has no mainnet acceptance. OWNER-A100-40GB-BUILD-CLASS-01 (2026-11-16) enters the
Lambda A100 40GB SXM4 (``NVIDIA A100-SXM4-40GB``) for JAX and PyTorch builds on finney, the remote GPU build lane's class.
OWNER-RTX6000ADA-BUILD-CLASS-01 (2026-11-21) enters the Lium RTX 6000 Ada (``NVIDIA RTX 6000 Ada Generation``) the same
way, finney only: the build class of the doors INFRA-17 names (Motor 1.9 and later).
"""

from __future__ import annotations

#: The JAX and PyTorch GPU accelerator profiles
#: (`accelerators.GPU_PROFILE.profile_id`, `torch_profile.GPU_PROFILE_ID`).
JAX_GPU = "carbon_jax_cuda13_nvidia_development_v1"
TORCH_GPU = "carbon_torch_cuda13_nvidia_development_v1"
_OWNER = {
    "record": "OWNER-GPU-DEVICE-CLASSES-01",
    # Testnet only: another network needs its own owner record.
    "networks": ("testnet",),
    "evidence": (
        "the owner's direct acceptance, 2026-10-09, for validator scoring on "
        "testnet (.agent/decisions/2026-10-09-OWNER-GPU-DEVICE-CLASSES-01.md)"
    ),
}

#: The owner's own words, typed in the Deploy-C session at 06:46 CST on 12 Nov 2026: "I accept
#: containment and the EPYC7402P-VM grading class on the GPUYard validator for mainnet 116." The
#: speed ceilings registered for that class carry over unchanged (Validator-2C ruling aef9598a).
_OWNER_GPUYARD_FINNEY = {
    "record": "OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01",
    # mainnet 116 only: finney is the chain network name the deployment carries.
    "networks": ("finney",),
    "evidence": (
        "the owner's direct acceptance, 2026-11-12, of containment and the "
        "EPYC7402P-VM grading class on the GPUYard validator for mainnet 116 "
        "(.agent/decisions/2026-11-12-OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01.md)"
    ),
}


#: The owner's own words, typed in the Deploy-B session at 13:14 CST on 16 Nov 2026 (PC board L12667): "Deploy-B: I
#: accept the Lambda 1× A100 40GB SXM4 as a Carbon GPU build class for JAX and PyTorch builds, after TE3's arrival
#: checklist and Validator-2's receipt. Standing until I say stop." Given for the 116 GPU build lane: finney only.
_OWNER_A100_40GB_FINNEY = {
    "record": "OWNER-A100-40GB-BUILD-CLASS-01",
    "networks": ("finney",),
    "evidence": (
        "the owner's direct acceptance, 2026-11-16, of the Lambda 1x A100 40GB SXM4 as a Carbon GPU build class "
        "for JAX and PyTorch builds, after TE3's arrival checklist and Validator-2's receipt "
        "(.agent/decisions/2026-11-16-OWNER-A100-40GB-BUILD-CLASS-01.md)"
    ),
}


#: The owner's own words, typed in the infra seat at 2026-11-21T22:27:52Z (OWNER_LINES.md, P2-16 line B): "approved:
#: OWNER-RTX6000ADA-BUILD-CLASS-01: the RTX 6000 Ada build class (S6 record 52dd54ca, S6c curve a970b2a1) for finney
#: doors named in INFRA-17; slots 4 at the first admission; raise to 6 only after an S7 read on the real door (GPUYard ->
#: Ada) shows fail <= 3.2 % and p50/p90 within the LO-4 bar at 6; never 7 without that read." INFRA-17 (14:27:39Z):
#: Motor 1.9 and later versions open on this class; Motor 1.8 stays on the Lambda A100 until it retires.
_OWNER_RTX6000ADA_FINNEY = {
    "record": "OWNER-RTX6000ADA-BUILD-CLASS-01",
    "networks": ("finney",),
    "evidence": (
        "the owner's direct acceptance, 2026-11-21, of the Lium RTX 6000 Ada as a Carbon GPU build class for the "
        "finney doors INFRA-17 names, slots 4 at the first admission "
        "(.agent/decisions/2026-11-21-OWNER-RTX6000ADA-BUILD-CLASS-01.md)"
    ),
}


def _entry(*records):
    """One profile's acceptance: the first record's own fields, the networks every record names, and each
    network's record (`by_network`) so a network's acceptance is never read as another's.
    """
    first = records[0]
    return {
        "record": first["record"],
        "evidence": first["evidence"],
        "networks": tuple(n for record in records for n in record["networks"]),
        "by_network": {
            n: {"record": r["record"], "evidence": r["evidence"]}
            for r in records
            for n in r["networks"]
        },
    }


#: `{device_kind: {profile_id: {"record", "evidence", "networks", "by_network"}}}`: a class is
#: accepted per accelerator profile, so a JAX acceptance never admits the
#: PyTorch GPU worker (or the reverse). The device kind is the exact name
#: `nvidia-smi` reports, as the host device record binds it. The RTX 4090 is
#: accepted for testnet and, as the GPUYard validator's GPU, for finney 116.
ACCEPTED_DEVICE_CLASSES: dict = {
    "NVIDIA A40": {JAX_GPU: _entry(_OWNER), TORCH_GPU: _entry(_OWNER)},
    "NVIDIA GeForce RTX 4090": {
        JAX_GPU: _entry(_OWNER, _OWNER_GPUYARD_FINNEY),
        TORCH_GPU: _entry(_OWNER, _OWNER_GPUYARD_FINNEY),
    },
    # the remote GPU build lane's rented class (OWNER-A100-40GB-BUILD-CLASS-01): the exact name nvidia-smi reports
    "NVIDIA A100-SXM4-40GB": {
        JAX_GPU: _entry(_OWNER_A100_40GB_FINNEY),
        TORCH_GPU: _entry(_OWNER_A100_40GB_FINNEY),
    },
    # the Lium build class of Motor 1.9 and later (OWNER-RTX6000ADA-BUILD-CLASS-01, INFRA-17): the exact nvidia-smi name
    "NVIDIA RTX 6000 Ada Generation": {
        JAX_GPU: _entry(_OWNER_RTX6000ADA_FINNEY),
        TORCH_GPU: _entry(_OWNER_RTX6000ADA_FINNEY),
    },
}


class DeviceClassNotAccepted(ValueError):
    """No hardware acceptance names this device class (fail closed)."""

    code = "validator_device_class_not_accepted"


def require_accepted(device_kind, profile_id, network):
    """Refuse unless `device_kind` passed a hardware acceptance under
    `profile_id` for `network` (the deployment's chain network). An acceptance
    names its networks, so a testnet acceptance never admits another network,
    and an unknown network (None) is refused."""
    profiles = ACCEPTED_DEVICE_CLASSES.get(device_kind)
    entry = profiles.get(profile_id) if type(profiles) is dict else None
    if (
        type(entry) is not dict
        or type(network) is not str
        or network not in entry.get("networks", ())
    ):
        raise DeviceClassNotAccepted(
            "no hardware acceptance names this device class for validator scoring"
        )
    return entry


__all__ = ["ACCEPTED_DEVICE_CLASSES", "DeviceClassNotAccepted", "require_accepted"]
