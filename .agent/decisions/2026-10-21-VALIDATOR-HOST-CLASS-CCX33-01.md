# VALIDATOR-HOST-CLASS-CCX33-01: the DEVELOPMENT host class moves to Hetzner ccx33

Date: 2026-10-21
Status: APPROVED by the owner, directly in the Carbon Validator's session on 2026-10-21. The owner first said "make your best judgement" on the one open point (the memory floor), then answered "Yes, approve 30 GiB" when the Validator asked.
Amends: OWNER-VALIDATOR-HOST-CLASS-01 (the class definition and the "one class" rule are unchanged; this replaces the measured host).
Maturity: engineering control, DEVELOPMENT scope. No scientific or security acceptance is created, and no score, minimum or noise is registered.

## Why

The registered class host (Targon noise-h1, "AMD EPYC-v4 Processor", 4 vCPU) was deleted on 2026-10-20. Hetzner ccx33 was accepted as the replacement, on condition that lscpu shows avx2+fma, no avx512/amx, and at least 32 GiB. Hetzner has no 4-vCPU / 32 GiB dedicated shape.

## Measured (Test Lead, host `claude-hz-devclass`, Hetzner ccx33, fsn1, 2026-10-21)

- lscpu model name: `AMD EPYC-Milan Processor` (KVM).
- ISA flags: avx2 yes, fma yes, avx512f no, avx512_bf16 no, amx no. This is the same exact set as the old class.
- nproc: 8.
- Memory: `free -g` total 30 GiB. The install check floors `MemTotal` to whole GiB the same way.

## The class registered (`carbon/challenge_validator/validator-host-class.json`)

| Field | Old | New |
|---|---|---|
| cpu_model_name | AMD EPYC-v4 Processor | AMD EPYC-Milan Processor |
| isa_flags_present | avx2, fma only | unchanged |
| nproc | 4 | 8 |
| mem_total_min_gib | 50 | 30 |

## The memory floor (the one judgement call)

- **The acceptance said "at least 32 GiB".** It was written for Hetzner's ccx33, which is sold as 32 GB. 32 GB is about 29.8 GiB, and the kernel keeps some of that for itself, so the floor the check can register on this host is 30. The shortfall is units and kernel reservation, not a smaller machine.
- **The floor is a capacity requirement, not exam protection.** One v7 worker lane is 16 GiB (OWNER-WORKER-RESOURCES-LARGE-MODELS-01), and it fits.
- **The alternative changes more than memory.** Hetzner's next dedicated shape, ccx43, has 16 vCPU, which would be a different class.
- **Decision:** register 30 GiB, the floor this host actually reports. If the Test Lead's exact `MemTotal` floors to less than 30, the install check refuses it, and the class must be re-registered (fail closed).

## Consequences

- **Cadence:** R in `exam_cadence.json` is re-derived from the class: 8 vCPU × 24 h × 0.7 = **134.4 CPU-h/day** (was 67.2). At the placeholder rebuild costs (Σt = 4.7 CPU-h), the daily graded allowance per Challenge is 14 at 2 active miners, 5 at 5, and 1 (the floor) at 25 or more.
- **Determinism:** the BLAS thread pin stays fixed, so scores do not depend on nproc. Worker lanes keep their own CPU profile (4 vCPU under the v7 profile); only the host's capacity changes.
- **Nothing is invalidated.** No minimum or noise was ever registered against the old class, because the one registered recalibration is still held. Leg minimums and rebuild noise are measured on this class's own CPU, never carried over (OWNER-VALIDATOR-HOST-CLASS-01, "Why the ISA match is an exact set").
- **Next:** the Test Lead measures each catalog entry's build alone on this host (the rebuild wall, OWNER-REBUILD-TIME-LIMIT-01). That measurement is provisional until the worker-resources wiring and the owner-published image land.
