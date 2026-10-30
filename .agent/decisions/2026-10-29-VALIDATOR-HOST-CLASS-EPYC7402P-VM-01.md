# VALIDATOR-HOST-CLASS-EPYC7402P-VM-01: stage 1 (identity) of the GPUYard VM host class

Date: 2026-10-29
Status: registered by the Test Engineer from the Test Lead's readings, as the Validator's procedure (GPUYARD_EPYC7402P_VM_PROCEDURES_20261029, section C.2) assigns it; the Carbon Validator receipted the design. This needs a non-author review before it folds, and the Validator receipts the diff.
Maturity: engineering control, DEVELOPMENT (testnet) scope. It creates no scientific or security acceptance and registers no score, minimum, noise, GPU class or stage-2 value.
Decision it serves: OWNER-GPUYARD-BACKUP-VALIDATOR-01 (testnet only; mainnet needs a dedicated box and a fresh acceptance).
Amends: nothing. It sits beside VALIDATOR-HOST-CLASS-7950X-01, which stays registered unchanged.

## Why

- The testnet validator moves to the GPUYard VM while the HOSTKEY box is repaired.
- `install_validator.sh --check-only --gpu` on that VM refuses against the registered 7950X class (V_HOST_CLASS_MODEL, V_HOST_CLASS_ISA, V_HOST_CLASS_VCPU, V_HOST_CLASS_MEMORY), as the install check is meant to until the box's own class is registered. The check is never skipped: this registers the class from measured identity.

## Measured (Test Lead, the VM, 2026-10-29; kit `s1_identity_check.sh`)

- `identity.json` sha256 `8281e814898e4490182e1ef1e8d472fdad48b0bb20d5b7d629e83950fafc64cf`, kept with the Test Lead's results.
- CPU model string exactly as the guest shows it: `AMD EPYC 7402P 24-Core Processor`.
- ISA flags: avx2 yes, fma yes, avx512f no, avx512_bf16 no, amx no.
- nproc 8. `MemTotal: 65819092 kB` = 62.77 GiB, which floors to 62.
- Machine type: `systemd-detect-virt` = `vm-other` (oVirt/KVM guest, GPU passthrough).
- Microcode 0x830107d; Ubuntu 24.04.5 LTS; kernel 6.8.0-147-generic; NVIDIA driver 580.178.04; Docker 29.1.3.
- GPU: RTX 4090, compute capability 8.9, 24564 MiB, PCIe gen4 x16.
- Known quirk, recorded and not acted on: `nvidia-smi` reports clocks_throttle_reasons 0x4 (software power cap) at 25-50% of the 450 W limit with SM clocks at max boost.

## The class registered

`scripts/validator_host_classes/EPYC7402P-VM-01.json`, schema `carbon.validator.host-class.v2`, stage 1:

| Field | Value |
|---|---|
| id | VALIDATOR-HOST-CLASS-EPYC7402P-VM-01 |
| cpu_model_name | AMD EPYC 7402P 24-Core Processor |
| isa_flags_present | avx2, fma; avx512f, avx512_bf16, amx absent |
| nproc | 8 |
| mem_total_min_gib | 62 |
| virtualization | vm-other |
| scope | DEVELOPMENT |

- It lives outside `carbon/`, so it is not a worker build input and no image id moves (the build-inputs digest stays `sha256:986d7a0954a7082703436cdeb5970160506415109db60115fb7b07a68cc37519`).
- `install_validator.sh` accepts a machine that matches ONE registered class in full (the primary class under `carbon/challenge_validator/` or a v2 record here). A class file counts only if it is tracked at HEAD and unmodified; a tree that is not a git work tree is refused as `V_HOST_CLASS_UNVERIFIABLE`.

## Not registered here (stage 2, after the install)

- the worker image ids, the thread pins per role, the lane cpusets, the CPU pin values and `cpu_pin.require()` passing on the box;
- any score, minimum, noise or GPU-class value (the recalibration on this class is its own run, with no carry-over from another host).

## Consequences

- This admits the install check and nothing else. No GPU rebuild and no counted crown on this class until its stage 2 and the class qualification evidence are receipted, and the owner accepts containment in his own words.
- A change to the CPU model string, ISA flags, vCPU count, memory floor or machine type is a new class.
