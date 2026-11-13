## 2026-11-11 — OWNER-VARIANT-RULE-NULL-MENU-D-18-01: no grading-optimizer variant rule for Motor 1.8 and Cooling 1.8 (menu D)

Date: 2026-11-11 (CST)
Status: DECIDED by the owner, directly in the Lead session, Wed 11 Nov 2026 19:1x CST (TEAM_BOARD 19:12, the Lead's "OWNER WORDS" line, board L7471).
This record holds his words and their plain meaning only. It contains no hidden values: no thresholds, seeds, region bounds or case inputs.

## The owner's words (typed, verbatim)
"Motor 1.8 + Cooling 1.8: the grading optimizer's variant_rule is null for menu-D versions (menu D replaces pick D; no score effect), recorded as such; population null and sigma0 0.25 as every registered version."

## What it rests on
- design-optimum-B's note `codex-queue/reports/FILL18_OPTIMIZER_LEAVES_20261111.md` (sha256 prefix 1bf74cae): these are the leaves of the grading optimizer (the pool grader's pick-D search), not D-engine values.
- Carbon Validator-B and Carbon Validator-Motor, 11 Nov 17:56: the 1.8 total never reads the pick-D optimizer, because menu D replaces pick D (`pool_exam`).
- Carbon Validator-C, 11 Nov 21:07: record this as a waiver for the two named versions, not as a change to the conformance rule. Carbon Validator-Motor-C concurred at 21:12.
- Validator-2C ruled the form on 11 Nov 21:32 (board, "V_VAR FORM ... = OPTION A"): the existing waiver mechanism, this record id, waivers on exactly the two 1.8 rows, and the `variant_rule` key absent. Two test edits are allowed in exactly this form:
  - the conformance test seeds byte copies of the real tracked records a row's waivers name, and keeps a negative case (a waiver with no record still fails);
  - the pool-pack documents test requires 4 documents (plus the region) for a menu-D row with no variant rule, and still requires the variant-starts document wherever a rule is present.

## Plain meaning
- Motor 1.8 and Cooling 1.8 register no neighbour-task variant rule for the grading optimizer. In `scripts/validator_host_classes/pool_constants.json`, their `optimizer` blocks carry no `variant_rule` key. That absent key is the registry's own form of "no rule" (`pool_version._variant_rule` returns None), so the policy's variant_rule is null.
- Each of those two rows names this record in `fit_breaker.waivers.v_var`. The fit-breaker rule 4 (v_var) is waived for these two versions only.
- Rule 4 itself is unchanged. Any later version graded by pick D is still checked.
- No score moves. Menu D sets the D of these versions, and the pick-D optimizer grades nothing in their total.
