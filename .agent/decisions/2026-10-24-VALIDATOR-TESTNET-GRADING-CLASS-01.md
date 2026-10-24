# VALIDATOR-TESTNET-GRADING-CLASS-01: testnet grades on the ccx33 DEVELOPMENT class; the GPU class waits for mainnet

Date: 2026-10-24
Status: Validator decision under existing owner records. No new owner value is set.
Amends:
- VALIDATOR-HOST-CLASS-CCX33-01, where the "non-grading only" note is lifted for testnet;
- VALIDATOR-TESTNET-GPU-CLASS-01, where testnet on the GPU class is deferred.

## Why

OWNER-VALIDATOR-4090-AFTER-TESTNET-01: the monthly 4090 isn't ordered until testnet is a full success, and "testnet runs on the existing hosts and standing rentals". So the GPU class can't grade testnet.

## Decided

- **The testnet grading host is valV3 on the registered DEVELOPMENT class** (Hetzner ccx33: AMD EPYC-Milan, avx2+fma, no avx512/amx, nproc 8, ≥ 30 GiB; `carbon/challenge_validator/validator-host-class.json`).
- **The one registered recalibration** (rebuild wall, rebuild-noise margin, leg minimums and baseline_total, allowance R) runs on that class, with the owner-published pinned image. Its values are valid for that class only, and the install check refuses any other host.
- **The GPU class registration (OWNER-VALIDATOR-GPU-CLASS-01) and its own recalibration** happen at the mainnet step, after testnet's full success. Values never carry over between classes.
- **Plan and timing:** `codex-queue/reports/PROOF_RUN_SUNDAY_PLAN_20261024.md`, last section.
