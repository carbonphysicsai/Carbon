# OWNER-MOTOR-EXAM-GRID-01: Motor sealed exams are drawn as a placed design × condition grid, so design value stays half the score

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Redraw as a grid").
Amends: OWNER-MOTOR-EXAM-DRAW-01 (the placement method, batch size, U, QA and stop rule are unchanged).
Maturity: DEVELOPMENT exam design. No qualification, LIVE or mainnet authority.

## Why

- **The rule:** every dual pack scores 0.5·A + 0.5·D (OWNER-BATTERY-DUAL-SCORE-01 records it for Motor, Cooling, F08, F02 and Battery). D is design value: Motor's registered D is the regret of choosing designs under each operating condition (`motor_dual_measurement`, the decision cohorts).
- **The owner raised the gap:** "That's supposed to be half our score".
- **What didn't fit:** Motor's sealed batches were 30 independent placed cases. They can't define a selection regret, so the Validator's interim ruling of 2026-10-22 had D UNAVAILABLE. That ruling is **withdrawn**.

## Decided

- **The grid:** each Motor sealed batch is still 30 cases, drawn fresh by seed from the registered Motor law and placed to straddle both limits (mean torque ≥ 4.0 N·m, ripple fraction ≤ 0.30). They are drawn as a **grid of designs × operating conditions** (about 5 × 6), so each condition offers several designs to choose among.
  - This matches Cooling's sealed grid (OWNER-COOLING-EXAM-DRAW-01).
  - Data Collection proposes the exact split, and the Validator approves it against the straddle, QA and decision-contract needs.
- **The grade:** `motor-dual-sealed-batch-30-v1` grades with **A and D both present**, total = 0.5·A + 0.5·D. D is Motor's registered decision measure, unchanged, applied to the batch's grid.
- **The two existing QA-passed batches** (exam-1 `e0d7a8c3…`, exam-2 `4af69030…`) are not grids. They become **rehearsal-only**: used for flow checks and A-only diagnostics, and never for launch or official grading.
- **Unchanged:** placement is never a label; U (0.0052 N·m, 0.026); the record-declared ⅓ within-U stop; the exam QA; 2 consecutive failing batches stop the family; batches run alone.
