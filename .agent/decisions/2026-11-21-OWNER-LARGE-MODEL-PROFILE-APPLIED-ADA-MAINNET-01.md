# OWNER-LARGE-MODEL-PROFILE-APPLIED-ADA-MAINNET-01: the larger worker profile is accepted on the Lium RTX 6000 Ada build boxes for mainnet 116

Date: 2026-11-21, ~22:4xZ (read at 22:43:55Z).
Status: ACCEPTED by the owner. Typed directly in the door-code seat. door-code had reported (RECEIPTS 22:3xZ) that
`tests/invariants/test_large_model_profile_testnet_only.py` refuses a finney entry for the Ada without this acceptance,
and gave the text.
Owner's words: "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container limits and containment settings
as testnet) on the Lium RTX 6000 Ada build boxes for mainnet 116 (OWNER-LARGE-MODEL-PROFILE-APPLIED-ADA-MAINNET-01)."

It extends OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01 and OWNER-RTX6000ADA-BUILD-CLASS-01 (2026-11-21, 22:27:52Z),
and edits neither. It parallels OWNER-LARGE-MODEL-PROFILE-APPLIED-A100-MAINNET-01 for the Lambda A100 40GB.

## What is accepted

- On the Lium RTX 6000 Ada build boxes, for **mainnet 116 (finney)**: the larger worker profile that
  `LARGE_MODEL_PROFILE_APPLIED = True` serves (carbon/reconstruction/worker/model.py). That profile is the same 2 GiB
  output, 4 GiB scratch and 16 GiB lane memory, with the same containment settings as on testnet.
- This covers the GPU BUILDS the remote GPU build lane sends to those boxes (carbon/reconstruction/remote_gpu_build.py),
  including the containment of miner graph builds on the rented machines.

## Scope, and what stays as it was

- `model.py` is not changed: the flag stays True and the 2/4/16 GiB values are as they were.
- `tests/invariants/test_large_model_profile_testnet_only.py` is widened by exactly two entries, finney only:
  `NVIDIA RTX 6000 Ada Generation` under the JAX GPU profile and under the PyTorch GPU profile, which
  `hardware_acceptance.ACCEPTED_DEVICE_CLASSES` opens under OWNER-RTX6000ADA-BUILD-CLASS-01. These still fail it:
  - every other non-testnet entry (another device kind, another RTX 6000 name, another profile, `mainnet`, localnet);
  - a validator host class scoped other than DEVELOPMENT.
- The registry names a device kind (the exact `nvidia-smi` name), not a host. The box files and each box's own device
  record bind the build lane to a box.
- OWNER-RTX6000ADA-BUILD-CLASS-01's terms still apply: slots 4 at the first admission, 6 only after the S7 read on the
  real door, never 7 without it. INFRA-6 also still applies: no box enters the live pool without Validator-2's receipt.

## Not covered

- Any other host, device class or network.
- Grading, inference or the speed gate on these boxes.
- Starting or switching any door, which follows the gate and Validator-2's FINAL.
- Any score, threshold, tolerance or economics. No host address appears here.
