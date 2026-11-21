# OWNER-RTX6000ADA-BUILD-CLASS-01: the Lium RTX 6000 Ada accepted as a Carbon GPU build class

Date: 2026-11-21, 22:27:52Z.
Status: ACCEPTED by the owner. Typed directly in the infra seat (P2-16 line B) and recorded verbatim by infra in
codex-queue/ops/OWNER_LINES.md (RECEIPTS 22:27:52Z).

Owner's words: "approved: OWNER-RTX6000ADA-BUILD-CLASS-01: the RTX 6000 Ada build class (S6 record 52dd54ca, S6c curve
a970b2a1) for finney doors named in INFRA-17; slots 4 at the first admission; raise to 6 only after an S7 read on the real
door (GPUYard -> Ada) shows fail <= 3.2 % and p50/p90 within the LO-4 bar at 6; never 7 without that read."

INFRA-17 (owner, typed in the infra seat, 2026-11-21T14:27:39Z): "approved: Motor 1.9 and later versions open on the
Lium RTX 6000 Ada build class (device_kind NVIDIA RTX 6000 Ada Generation, its own values row, slots from S6c); Motor 1.8
stays on the Lambda A100 until it retires."

## Scope

- **Device class:** the exact name `nvidia-smi` reports on the rented box, `NVIDIA RTX 6000 Ada Generation`. The box's
  device record binds this name, and it keys `hardware_acceptance.ACCEPTED_DEVICE_CLASSES`.
- **Profiles:** JAX (`carbon_jax_cuda13_nvidia_development_v1`) and PyTorch
  (`carbon_torch_cuda13_nvidia_development_v1`) GPU builds, as for the A100 build class.
- **Network:** finney (mainnet 116) only. Testnet is not included.
- **Doors:** those INFRA-17 names: Motor 1.9 and later Motor versions. The values row
  (`scripts/validator_host_classes/remote_gpu_build.json`, `"electric-motor-magnetics 1.9"`) binds the class to the
  Motor 1.9 door. Motor 1.8 and Cooling 1.8 stay on the A100.
- **Role:** GPU BUILDS on the remote GPU build lane (`carbon/reconstruction/remote_gpu_build.py`). Grading, inference and
  the speed gate are not moved by this record.

## Slots

- 4 shared slots per box at the first admission, which is the values row's `slots`.
- 6 only after an S7 read on the real door shows fail <= 3.2 % and p50/p90 within the LO-4 bar at 6. That raise is a
  new values-row head citing that read.
- Never 7 without that read.

## Not covered

- The LARGE_MODEL worker profile on these boxes for mainnet 116. That is its own owner record,
  OWNER-LARGE-MODEL-PROFILE-APPLIED-ADA-MAINNET-01 (2026-11-21), as the A100's was.
- Admitting any box to the live pool. That still follows the operator check and Validator-2's receipt (INFRA-6:
  "no box enters the live pool without v2's receipt").
- Any score, threshold, tolerance or economics. No host address appears here.
