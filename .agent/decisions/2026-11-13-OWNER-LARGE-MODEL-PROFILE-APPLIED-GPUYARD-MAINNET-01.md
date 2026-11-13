# OWNER-LARGE-MODEL-PROFILE-APPLIED-GPUYARD-MAINNET-01: the larger worker profile is accepted on the GPUYard validator for mainnet 116

Date: 2026-11-13 (owner's local time, CST)
Status: ACCEPTED by the owner, typed directly in the Deploy-C session at 12:57 CST (Fri 13 Nov 2026), after Validator-2C set out the choice (option A: accept the larger profile for mainnet 116; option B: a separate mainnet tree with the flag False).
Owner's words: "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container limits and containment settings as testnet) on the GPUYard validator for mainnet 116, extending OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01 and OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01."

Extends (neither is edited): `2026-10-23-OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01.md` and `2026-11-12-OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01.md`.

## What is accepted

- For **mainnet 116 (finney) on the GPUYard validator**, the larger worker profile that `LARGE_MODEL_PROFILE_APPLIED = True` serves in `carbon/reconstruction/worker/model.py`: the same 2 GiB output, 4 GiB scratch, 16 GiB lane memory and the same containment settings as on testnet.
- That discharges, for that network and host only, the "Not covered: mainnet" row and the release rule in the 2026-10-23 record ("no mainnet image from a tree where `LARGE_MODEL_PROFILE_APPLIED` is True"). A mainnet 116 image may be built from a tree where the flag is True.

## Scope, and what stays as it was

- `model.py` is not changed by this record: the flag stays True and the 2/4/16 GiB values are as they were.
- `tests/invariants/test_large_model_profile_testnet_only.py` is scoped to this record and no wider. It admits `finney` only for the two device-class entries `hardware_acceptance.ACCEPTED_DEVICE_CLASSES` opens for finney 116: the RTX 4090 under the JAX GPU profile and under the PyTorch GPU profile. Every other non-testnet entry (another device kind, another profile, `mainnet`, localnet, an unknown network) and a validator host class scoped other than DEVELOPMENT still fail it.
- The registry names a device kind (the exact `nvidia-smi` name), not a host, so the code does not itself tell the GPUYard host from another host with the same GPU. The host class (VALIDATOR-HOST-CLASS-EPYC7402P-VM-01) and the installer remain the binding to the GPUYard validator.
- Containment and the grading class are as in OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01: its conditions (the containment probes passing on the installed mainnet candidate, the Deploy posts of each door's CPU inference image and one testnet 1.8 speed result per Challenge) still apply.

## Not covered

- Any other mainnet host, any other device class (including the A40), any other network.
- Starting or opening the 116 door: that follows this record's landing and the Validator-2C go chain, not this record.
- Any score, threshold, tolerance or economics. No host address and no server id appear here; they are held in custody.
