# OWNER-LARGE-MODEL-PROFILE-APPLIED-A100-MAINNET-01: the larger worker profile is accepted on the Lambda A100 40GB build box for mainnet 116

Date: 2026-11-16 (owner's local time, CST).
Status: ACCEPTED by the owner. Typed directly in the TE3 session at 13:41 CST (Mon 16 Nov 2026). TE3 had reported
that `tests/invariants/test_large_model_profile_testnet_only.py` refuses a finney entry for the A100 without this
acceptance, and the Lead relayed the ask.
Owner's words: "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container limits and containment settings
as testnet) on the Lambda A100 40GB build box for mainnet 116."

It extends OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01 and OWNER-A100-40GB-BUILD-CLASS-01 (2026-11-16, 13:14 CST), and
edits neither. It parallels OWNER-LARGE-MODEL-PROFILE-APPLIED-GPUYARD-MAINNET-01 for the RTX 4090.

## What is accepted

- On the Lambda A100 40GB build box, for **mainnet 116 (finney)**: the larger worker profile that
  `LARGE_MODEL_PROFILE_APPLIED = True` serves (carbon/reconstruction/worker/model.py). That profile is the same 2 GiB
  output, 4 GiB scratch and 16 GiB lane memory, with the same containment settings as on testnet.
- This covers the GPU BUILDS the remote GPU build lane sends to that box (carbon/reconstruction/remote_gpu_build.py),
  including the containment of miner graph builds on that rented machine.

## Scope, and what stays as it was

- `model.py` is not changed: the flag stays True and the 2/4/16 GiB values are as they were.
- `tests/invariants/test_large_model_profile_testnet_only.py` is widened by exactly two entries, finney only:
  `NVIDIA A100-SXM4-40GB` under the JAX GPU profile and under the PyTorch GPU profile, which
  `hardware_acceptance.ACCEPTED_DEVICE_CLASSES` opens under OWNER-A100-40GB-BUILD-CLASS-01. These still fail it:
  - every other non-testnet entry (another device kind, another A100 variant, another profile, `mainnet`, localnet);
  - a validator host class scoped other than DEVELOPMENT.
- The registry names a device kind (the exact `nvidia-smi` name), not a host. The lane record and the box's own device
  record bind the build lane to this box.
- OWNER-A100-40GB-BUILD-CLASS-01's conditions still apply: TE3's arrival checklist complete on the box, and
  Validator-2's receipt.

## Not covered

- Any other host, device class, A100 variant (including the 80GB line L12660 until its box exists) or network.
- Grading, inference or the speed gate on this box.
- Starting or switching any door, which follows the gate and Validator-2's FINAL.
- Any score, threshold, tolerance or economics. No host address appears here.
