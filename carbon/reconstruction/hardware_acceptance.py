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
OWNER-A6000-48GB-BUILD-CLASS-01 (2026-11-23, G-LEAD-60) accepted the Lambda RTX A6000 48 GB VM (``NVIDIA RTX A6000``)
as the JAX build class of Motor 1.9 and RB 2.0. Its FINNEY entry is NOT entered yet (v2 5793): finney builds run the
LARGE_MODEL worker profile, which needs the owner's own mainnet acceptance for this class (as the A100's and the Ada's),
and G-LEAD-60 names no profile. The finney entry returns with that line; meanwhile the A6000 is entered only on the
rehearsal localnet (below), and a finney door bound to it refuses at start (fail closed). PyTorch is not entered.
Owner G-LEAD-58 (2026-11-23, launch rehearsals R1-R3b build on the launch build class) adds ``localnet`` for the two
launch build classes (the A100 40GB and the A6000), for rehearsal doors only: the disposable localnet row exists only in
a process bound to it (no stage, no publication, no miners, no economics, `carbon.chain.networks`).
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


#: The owner's own words, typed in the Lead seat at 2026-11-23T18:51:18Z (OWNER_LINES.md G-LEAD-60, "I guess that's the
#: move", answering block 57): "approved: OWNER-A6000-48GB-BUILD-CLASS-01: Motor 1.9 and RB 2.0 miner builds may run on
#: Lambda RTX A6000 48 GB VMs (gpu_1x_a6000) with the door's pinned engine, after infra's class record passes; on demand,
#: same pool rules as the A100." The record passed (infra RECEIPTS 5505): a6000-class-check.json sha256 54446e4a...,
#: GPU_REPEATS 16/16, slots 1 / 2 / 3 digest-equal, memory shared, JAX only (--no-torch).
_OWNER_A6000_48GB_FINNEY = {
    "record": "OWNER-A6000-48GB-BUILD-CLASS-01",
    "networks": ("finney",),
    "evidence": (
        "the owner's direct acceptance, 2026-11-23 (G-LEAD-60), of the Lambda RTX A6000 48 GB VM as a Carbon GPU build "
        "class for Motor 1.9 and RB 2.0 after infra's class record passed: a6000-class-check.json sha256 "
        "54446e4a6675e2e67466961af8ada2d26da2b904ebb0f615d77d80ee4f2e1535, ops record sha256 "
        "a2887c4af2f9e36c914d6160962393d49bc8df9eaf7dd29eddcdcbb12d202a22 "
        "(.agent/decisions/2026-11-23-OWNER-A6000-48GB-BUILD-CLASS-01.md)"
    ),
}


#: Owner G-LEAD-58, typed in the Lead seat at 2026-11-23T16:41:51Z ("Approve 54"): "approved: launch rehearsals R1-R3b
#: build on the launch build class (the A100 GPU path) with the door side on gate-class pods, up to USD 50 total, one run
#: at a time, scratch packs only, deleted or released on DONE." G-LEAD-60 moved the launch class of Motor 1.9 and RB 2.0
#: to the A6000. A rehearsal door is bound to the disposable localnet (`chain.networks`: a row present only in a process
#: bound to it, its one endpoint the host's own node, no stage: nothing it does is published, paid or ranked), so these
#: classes are accepted there for the rehearsals' builds; finney's record and evidence are untouched (``by_network``).
_OWNER_REHEARSALS_LOCALNET = {
    "record": "G-LEAD-58-LAUNCH-REHEARSALS",
    "networks": ("localnet",),
    "evidence": (
        "the owner's approval, 2026-11-23 (G-LEAD-58, OWNER_LINES.md), that launch rehearsals build on the launch build "
        "class with scratch packs only; localnet is staging only (no stage, no publication, no economics)"
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
        JAX_GPU: _entry(_OWNER_A100_40GB_FINNEY, _OWNER_REHEARSALS_LOCALNET),
        TORCH_GPU: _entry(_OWNER_A100_40GB_FINNEY, _OWNER_REHEARSALS_LOCALNET),
    },
    # the Lium build class of Motor 1.9 and later (OWNER-RTX6000ADA-BUILD-CLASS-01, INFRA-17): the exact nvidia-smi name
    "NVIDIA RTX 6000 Ada Generation": {
        JAX_GPU: _entry(_OWNER_RTX6000ADA_FINNEY),
        TORCH_GPU: _entry(_OWNER_RTX6000ADA_FINNEY),
    },
    # the Lambda launch class of Motor 1.9 and RB 2.0 (OWNER-A6000-48GB-BUILD-CLASS-01, G-LEAD-60): JAX only, as measured
    # finney waits the owner's LARGE_MODEL line for this class (v2 5793): `_OWNER_A6000_48GB_FINNEY` is re-entered with it
    "NVIDIA RTX A6000": {JAX_GPU: _entry(_OWNER_REHEARSALS_LOCALNET)},
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
