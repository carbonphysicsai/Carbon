## 2026-11-12 — Conditions of OWNER-COOL18-FIT-BREAKER-SEAL-WAIVER-01 (Cooling 1.8 only, until its seal)

This is the conditions report that the `ood_min_accuracy` waiver form names by sha256 (`tests/cpu/test_fit_breaker_conformance.py`, `_waiver_ok`). It records the conditions that bound the waiver. It decides nothing. The decision is the owner record `OWNER-COOL18-FIT-BREAKER-SEAL-WAIVER-01`. This report contains no hidden values: no thresholds, seeds, region bounds or case inputs.

## What is waived
- Version: `chip-cold-plate 1.8` (Cooling 1.8) only. No other version's row names this record.
- Rules (OWNER-FIT-BREAKER-RULES-LOCK-01):
  - `separation_read`;
  - `engineer_shortcut_d_zero` (rule 2', the menu zero);
  - `ood_min_accuracy`.
- The `v_var` waiver (OWNER-VARIANT-RULE-NULL-MENU-D-18-01) is separate and unchanged.

## Why
The three switches can only be turned on with Cooling 1.8 seal values, as real sha256 values:
- `fit_breaker.separation_read_sha256`;
- `fit_breaker.d_zero` `dv_proof_sha256` / `arms_sha256` / `zero_records_sha256`;
- `physics.cells_sha256`.

None of these exists before the Cooling 1.8 seal. Registering a placeholder sha would invent a value. Without a waiver, every head that carries the Cooling 1.8 row fails the conformance test, and with it the Motor 1.8 push. The row has carried those leaves since pool constants 1051ee13 (10 Nov).

## Conditions (all must hold while the waiver stands)
1. **Not served.** No door serves Cooling 1.8. The Cooling launch door stays on 1.6 (`scripts/dev/miner_launchpad/published_endpoints.json`).
2. **Grades nothing.** The Cooling 1.8 row keeps its HUMAN_INPUT leaves, so `pool_version.registered_policies("chip-cold-plate", "1.8")` refuses, and Cooling 1.8 is not in `published_exam._REGISTERED_POOL`. A test pins both while this record is named.
3. **Expires at the Cooling 1.8 seal.** In the same change that fills the row's seal values:
   - each of the three rules is switched on with its sealed values;
   - the three waiver entries are removed from the row.

   The conformance test then checks the rules as for any new version.
4. **No rule changes.** The conformance test and OWNER-FIT-BREAKER-RULES-LOCK-01 are unchanged. Every other new version is still checked in full.
