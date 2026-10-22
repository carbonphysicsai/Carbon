# OWNER-BATTERY-EXAM-GRID-01: Battery sealed exams are 4 scenarios × EV4's 35 candidates, so design value is graded

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session ("4 scenarios").
Maturity: DEVELOPMENT exam design. No qualification, LIVE or mainnet authority.

## Why

- **The rule:** the graded score is 0.5·A + 0.5·D (OWNER-BATTERY-DUAL-SCORE-01). Battery's D is registry leg `q` = 1/(1 + mean decision regret) over scenarios, each choosing among **EV4's 35 frozen charging candidates** (`battery_dual_measurement.decision_value`).
- **What didn't fit:** the Validator's 2026-10-22 approval of 8 cases drawn uniformly over the 420 grid's hull has no scenario × candidate structure, so D is undefined. It is withdrawn: the same cross-Challenge issue as Motor (OWNER-MOTOR-EXAM-GRID-01).

## Decided

- **The batch:** each Battery sealed batch is **4 scenarios × the 35 EV4 frozen candidates = 140 cases**.
  - The scenarios (ambient temperature and initial state of charge) are drawn fresh by seed from the 420 grid's hull, and are disjoint from EV4's development scenarios and every published case.
  - The candidates are EV4's public frozen 35.
- **The cost (Data Collection's measured ledgers):** about 2 h of wall time per batch at parallel 6 on the custody host, plus about 70 min of mesh-320 spot solves. $0 marginal.
- **The grade:** D is the registered `q` on the batch's own 4 scenarios, and the total is 0.5·A + 0.5·D.
- **The two 8-case batches already packed** become **rehearsal-only**: never for launch or official grading. Their records stay as recorded.
- **Unchanged:** the U record (VALIDATOR-BATTERY-PLATING-U-01, 0.23 mV); the v2 plating label; run alone; one redraw, then STOP.
- **Engineering rules the Validator sets** (reference policy, separate ruling): reference-failure handling, the post-solve decision check, and the placement of scenarios.
