# VALIDATOR-HOST-CLASS-7950X-01: the DEVELOPMENT host class moves to the dedicated validator box

Date: 2026-10-29
Status: authored by the Carbon Validator under the owner's overnight testnet delegation, on the owner's own choice of machine. The owner ordered this dedicated box and said it is final and kept for mainnet; the Lead relayed it the same day. This needs a non-author review before it folds.
Amends: VALIDATOR-HOST-CLASS-CCX33-01. It replaces the measured host. The class definition and the "one class" rule of OWNER-VALIDATOR-HOST-CLASS-01 are unchanged.
Maturity: engineering control, DEVELOPMENT (testnet) scope. It creates no scientific or security acceptance, and it registers no score, minimum, noise or GPU class.

## Why

- The owner moved the validator to a dedicated server, with a Ryzen 9 7950X, 128 GB and an RTX 4090.
- `install_validator.sh --check-only --gpu` on that box refused V_HOST_CLASS_MODEL, V_HOST_CLASS_ISA and V_HOST_CLASS_VCPU against the EPYC-Milan class, as the day-one runbook expects (step 2 refuses until step 3 registers the box).
- The install check is what ties every later grade to one CPU class, so the class is re-registered from this box's measured identity. It is never skipped.

## Measured (Test Lead, the dedicated box, 2026-10-29; kit4090 `s1_identity_check.sh`, run as root)

- identity.json sha256 `6b3be11b74edae1d920a8bc4c60016d18bc90a0345b4e2caac83693e4cd20ec2`, kept with the Test Lead's results.
  - PASS 6, NOTE 2, FAIL 0; bare metal (`systemd-detect-virt` none).
  - The host address is kept in the private ledger only.
- lscpu model name: `AMD Ryzen 9 7950X 16-Core Processor`.
- ISA flags: avx2 yes, fma yes, avx512f yes, avx512_bf16 yes, amx no. This is the first registered class with AVX-512.
- nproc: 32.
- `MemTotal: 130980140 kB` = 124.9 GiB, which floors to 124, so the install check passes at the registered floor. Memory is non-ECC (dmidecode Error Correction Type None; no EDAC controller).
- OS: Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic (held).
- Held host stack:
  - nvidia-driver-580 / DKMS 580.178.04-0ubuntu0.24.04.1;
  - docker-ce 5:29.1.3-1~ubuntu.24.04~noble;
  - containerd.io 2.4.2-3~ubuntu.24.04~noble;
  - nvidia-container-toolkit 1.20.1-1.
  These are recorded here for the GPU class record. This change doesn't touch HOST_STACK.

## The class registered (`carbon/challenge_validator/validator-host-class.json`)

| Field | Old (ccx33) | New |
|---|---|---|
| cpu_model_name | AMD EPYC-Milan Processor | AMD Ryzen 9 7950X 16-Core Processor |
| isa_flags_present | avx2, fma | avx2, fma, avx512f, avx512_bf16 (amx false) |
| nproc | 8 | 32 |
| mem_total_min_gib | 30 | 124 |
| scope | DEVELOPMENT | DEVELOPMENT (unchanged) |

## Consequences

- **The ccx33 hosts can't reinstall.** valV3 and any EPYC-Milan host keep running what is already installed, but `install_validator.sh` now refuses them (one class, fail closed).
- **Nothing measured transfers.** No minimum or noise was ever registered against the old class. Reference states, KRR legs, baselines, grade repeatability, the speed ceiling and the rebuild wall are all re-measured on this class (the AVX-512 code paths differ in the last bits).
  - The BLAS thread pins stay fixed in code, so scores don't depend on nproc.
- **Cadence R** in `exam_cadence.json` follows the class in the same way as before: 32 vCPU × 24 h × 0.7 = 537.6 CPU-h/day. It is re-derived in its own change after the box's measured rebuild costs, not here.
- **This admits the install and nothing else.** No GPU rebuild and no counted crown on this class until the class qualification evidence (the second-rebuild rule, grade repeatability, parity and containment with the GPU attached) is receipted, and the owner accepts containment in his own words.
- **Next, in a separate change:** the GPU half of the class record (image ids, the BLAS core type, thread pins, lane cpusets, the toolkit in HOST_STACK's tested list), after the install builds the images.
