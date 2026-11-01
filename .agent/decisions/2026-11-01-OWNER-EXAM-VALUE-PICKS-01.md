# OWNER-EXAM-VALUE-PICKS-01: week-1 exam optimisation picks (all five approved)

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "All 5 yes"
Basis: codex-queue/reports/WEEK1_EXAM_VALUE_ANSWERS_20261101.md (Validator), relayed by the Lead with recommendations.

## Decided (new exam versions only; nothing already graded is rescored)
1. **F08 1.8 quick version: GO.** Stricter accuracy scale (0.01×), the strict design scale, shell U v2, and 2 new hidden targets built around resonance band-edge crossings. About 3–4 days and ~200 solves under the smoke-gate and spend-cap rules. It must pass the mandatory closed-form + cheap-method adversary gate; if that gate fails in-range, the owner decides "interim ship vs wait for F08 2.0".
2. **Top-k design scoring with k = 3:** design value scores the best verified of the model's top 3 picks per target (screen, then verify a few), replacing single-pick scoring in new versions.
3. **Balanced per-region scoring:** a model's accuracy cannot hide a broken region (TRAIN, extended shell, regime bands) behind a good average. The Validator specifies the exact balancing rule in the version's qualification record.
4. **The strict design honesty scale (k = 0.25)** on every new exam version.
5. **Cooling:** act on the Validator's fairness check of the baseline refit. If the minimums come from a refit that sees data miners lack, use Option B (baseline sets only the bar to win) or refit on TRAIN only, whichever the Validator shows is correct, in Cooling's next version.

## Bounds
- Testnet. Each change enters through a new registered exam version with its own qualification and margins recal, then a zero-downtime cutover.
- Exact numeric values not listed here (the balancing rule, the new targets' thresholds) come back to the owner on the daily sheet as proposals.
