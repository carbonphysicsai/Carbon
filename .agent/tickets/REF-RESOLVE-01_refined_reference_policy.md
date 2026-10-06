# REF-RESOLVE-01: reference-resolution policy v1 (DEVELOPMENT only)

**Status:** DRAFT. The Test Lead approves it before any solve.

**Authority:** the Test Lead's assignment (2026-10-05). Refined references are approved for DEVELOPMENT only.

**Why:** Graphite run-5 Q1 (#609) resolved only 6 of 12 EV4 development scenarios. Six are excluded:
- D-T14-S0.12
- D-T14-S0.48
- D-T24-S0.48
- D-T34-S0.33
- D-T5-S0.33
- D-T5-S0.48

**27 reference cases** block them:
- 22 are UNRESOLVED: the value lies within the contract band of a threshold, all of them on plating.
- 5 are REFERENCE_SOLVER_FAILED.

## Policy v1 (`ev4-dev-refined-v1`)

1. **Scope.** EV4 *development* decision references only, for these 27 cases. It never applies to EV4's verification split, EV5, any sealed or confirmation set, or any scoring set.
2. **Settling solve.** Each case gets exactly one refined solve: `reference.solve_case(..., refined=True)` in the same pinned truth image and PyBaMM overlay (26.8.0.0), on the operator host's CPU, at no spend.
3. **Resolution rule.**
   - The refined value is checked against the **same contract band** (conservative: the band *is* the standard-to-refined shift).
   - Outside the band, it resolves PASS or FAIL.
   - Still inside the band, it stays **UNRESOLVED** and is never forced.
   - A refined solve that fails stays REFERENCE_UNAVAILABLE, which is never a candidate failure.
4. **Records.**
   - Original records are kept unchanged.
   - Settled records live in a separate versioned file (`docs/development/evidence/ev4-dev-refined-v1/records.jsonl.gz`). Each carries `refined: true`, the original case id, the image and lock digests, and the solve time.
   - A table records every settling solve and its outcome.
5. **Use.**
   - Studies that opt in read standard references overlaid by settled records, under the policy version: the run-5 Q1 rerun and the score-tuning loop's development decision data.
   - EV4's committed results and every earlier study are **not** rescored or reinterpreted (invariant 10).
6. **Coverage is reported, not assumed.** If some cases stay UNRESOLVED, the mask grows only as far as they allow, and the rerun says so.

## Decisions for the Test Lead

- **(a)** Keep the same band for the refined values (proposed), or use a refined-specific band. There is no committed basis for the latter, so it would be HUMAN_INPUT.
- **(b)** Approve the 27 cases and the host-CPU run (about 30 to 60 min, Graphite executor window).

## Policy v2 (`refined-measured-band`): evaluated, rejected (2026-10-05)

- **Proposal** (Test Lead): a refined case resolves when its margin's distance from the limit exceeds 2 × the largest measured |refined − original| shift across the settled cases.
- **Measured:** the largest plating shift across the 22 OK pairs is 1.245 mV, so 2 × shift = **2.49 mV**. That is wider than the contract band of **1.97 mV**.
- **Result:** none of the 16 still-UNRESOLVED cases would resolve (the largest |margin| is 1.91 mV), and some of v1's 6 resolutions would be undone. Coverage cannot exceed v1's 7/12.
- **Rejected.** The refinement shift is about two-thirds of the contract band, which supports the band rather than suggesting it is loose. No band decision goes to the science owner on this evidence.
- **Ruling:** the Test Lead, 2026-10-05, recorded as a negative result. v1 (the contract band) stays the only development policy.
