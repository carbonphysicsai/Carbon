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
