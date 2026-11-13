## 2026-11-12 — OWNER-COOL18-FIT-BREAKER-SEAL-WAIVER-01: three fit-breaker rules waived for Cooling 1.8 until its seal

Date: 2026-11-12 (CST)
Status: DECIDED by the owner, directly in the mc-exam-C session, Thu 12 Nov 2026 ~20:03 CST.
This record holds his words and their plain meaning only. It contains no hidden values: no thresholds, seeds, region bounds or case inputs.

## The owner's words (typed, verbatim)
"Cooling 1.8 only: fit-breaker rules separation_read, engineer_shortcut_d_zero and ood_min_accuracy are waived under record OWNER-COOL18-FIT-BREAKER-SEAL-WAIVER-01 until the Cooling 1.8 seal, when each rule is switched on with its sealed values and the waiver is removed; Cooling 1.8 is not served meanwhile (the Cooling door stays on 1.6) and grades nothing (its row keeps its HUMAN_INPUT leaves, fail closed)."

## What it rests on
- Runner-C, gate621 / gate624 (Thu 12 Nov): on the Motor 1.8 line, the one remaining failure is `tests/cpu/test_fit_breaker_conformance.py`. It is exactly Cooling 1.8's three `rule_off` rows. Main is green there; every Line D head carries the Cooling 1.8 row (pool constants 1051ee13, 10 Nov).
- Each switch needs a Cooling 1.8 seal value as a real sha256, and none exists before the seal. Registering a placeholder would invent a value.
- The Lead chose the test's own waiver form (option (b)) over pushing on a red gate or holding Motor 1.8 for the Cooling seal.
- Validator-2C receipted the line and the commit form on 12 Nov at 19:59, with conditions W-1 to W-3.
- Carbon Validator-C gave the Cooling science yes on 12 Nov at 19:59.
- The waiver's conditions report is `.agent/decisions/2026-11-12-COOL18-FIT-BREAKER-WAIVER-CONDITIONS.md` (sha256 c5bddda7d15e706562288ad6b2b9c9c90b02e52ae57caf7e6c40987bd21373b4).

## Plain meaning
- In `scripts/validator_host_classes/pool_constants.json`, the `chip-cold-plate 1.8` row's `fit_breaker.waivers` names this record for:
  - `separation_read`;
  - `engineer_shortcut_d_zero`;
  - `ood_min_accuracy`, as `{record, conditions_report_sha256}`.

  Its `v_var` waiver (OWNER-VARIANT-RULE-NULL-MENU-D-18-01) is unchanged.
- Cooling 1.8 is not served and grades nothing while this record is named:
  - no published endpoint serves it, and the Cooling door stays on 1.6;
  - its row keeps its HUMAN_INPUT leaves, so `pool_version.registered_policies` refuses it;
  - it is not in `published_exam._REGISTERED_POOL`.

  `tests/cpu/test_cool18_seal_waiver.py` pins all of this, and only Cooling 1.8 may name the record.
- The waiver ends at the Cooling 1.8 seal. The change that fills the row's seal values switches each of the three rules on with its sealed values and removes the three waiver entries.
- The conformance rule (OWNER-FIT-BREAKER-RULES-LOCK-01) and its test are unchanged. No score moves.
