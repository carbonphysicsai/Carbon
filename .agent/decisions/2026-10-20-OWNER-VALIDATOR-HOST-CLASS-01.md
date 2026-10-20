# OWNER-VALIDATOR-HOST-CLASS-01: every validator runs one host class

Date: 2026-10-20
Status: APPROVED by the owner. Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it.
Implementation: **not yet implemented.** There's no machine check in the validator install yet.

## Owner, verbatim

> all validators will be running the same hardware.

## Decided

- **One registered validator host class** is a validator requirement for the testnet and mainnet alike.
- **The class** is `(lscpu model name, the ISA flags among avx2/fma/avx512f/avx512_bf16/amx_*, vCPU count, minimum memory)`, measured once on the calibration host. It's registered as `validator-host-class.json`, which the Validator reviews.
- **The validator install's machine check refuses any other class,** with a typed code, before anything is installed or graded.

## What it settles

- **Rebuild noise and leg minimums are measured on, and valid for, that one class** (KOTH-TAKEOVER-RULE-01 §2a). With no other class there's no cross-class comparison.
- **Wall-time headroom stops varying between validators:** every validator runs the same speed class (OWNER-REBUILD-TIME-LIMIT-01).

## Not decided here

The class's actual values. They're measured from the calibration host, not chosen.

## The registered DEVELOPMENT class (measured by the Test Lead, 2026-10-20)

- **Source:** measured on the calibration VM, carbon-motorcal3-step1-20261020 (a Targon cpu-small-amd host).
- **Processor:** `AMD EPYC-v4 Processor`, with avx2 and fma; no avx512f, avx512_bf16 or amx.
- **vCPU:** 4.
- **Memory:** at least 50 GiB, the measured MemTotal of 52,858,868 KiB rounded down to whole GiB.
- **Scope:** testnet and rehearsal only. **The mainnet class comes from the owner's choice of validator hardware before launch.** That's a new registration, with re-measured rebuild noise and leg minimums.
- **Consequence for cadence:** R in `exam_cadence.json` (270 CPU-h a day) assumed a 16-vCPU host. On this 4-vCPU class the measured capacity is about a quarter of that, so R must be re-registered from the class. That's a measured value, not a choice.
