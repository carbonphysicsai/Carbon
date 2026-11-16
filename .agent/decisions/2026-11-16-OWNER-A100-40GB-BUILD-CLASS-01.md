# OWNER-A100-40GB-BUILD-CLASS-01: the Lambda A100 40GB SXM4 accepted as a Carbon GPU build class

Date: 2026-11-16, 13:14 CST.
Status: ACCEPTED by the owner. Typed directly in the Deploy-B session and posted by Deploy-B (PC board L12667), relayed
verbatim by the Lead.

Owner's words: "Deploy-B: I accept the Lambda 1× A100 40GB SXM4 as a Carbon GPU build class for JAX and PyTorch builds,
after TE3's arrival checklist and Validator-2's receipt. Standing until I say stop."

## Scope

- **Device class:** the exact name `nvidia-smi` reports on the rented box (`NVIDIA A100-SXM4-40GB`). The host device
  record binds this name, and it keys `hardware_acceptance.ACCEPTED_DEVICE_CLASSES`.
- **Profiles:** JAX (`carbon_jax_cuda13_nvidia_development_v1`) and PyTorch
  (`carbon_torch_cuda13_nvidia_development_v1`) GPU builds.
- **Network:** finney (mainnet 116). The owner named no network. The line was given for the 116 GPU build lane
  (the Lead's reading, 16 Nov). Testnet is NOT included unless the owner says so.
- **Role:** GPU BUILDS on the remote GPU build lane (`carbon/reconstruction/remote_gpu_build.py`). Grading, inference and
  the speed gate are not moved by this record.

## Conditions (the owner's)

- TE3's arrival checklist is complete on the box (codex-queue/reports/TE3_REMOTE_GPU_BUILD_20261116/A100_ARRIVAL_CHECKLIST.md).
  That includes:
  - the loaded image id equals the pinned id;
  - the A100-SXM4-40GB class check (bit-identical repeat, on GPU, allowlist v8).
- Validator-2's receipt.

Entering the class in code does not satisfy either condition. The code entry only lets a receiver configured with this
class start. The door switch still needs the gate, Validator-2's FINAL and the declared door migration.

## Related

- OWNER line L12660 (13:03 CST), with the same wording for an A100 80GB, also stands. It is not entered in code until a box
  of that class exists and its exact `nvidia-smi` name is read on it.
- This record sets no score, threshold, tolerance or economics, and records no host address.
