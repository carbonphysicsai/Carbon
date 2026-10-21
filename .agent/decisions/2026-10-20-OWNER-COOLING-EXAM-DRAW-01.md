# OWNER-COOLING-EXAM-DRAW-01: Cooling sealed exams are placed 4×4 grids

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Approve").

## Decided

- **Each sealed Cooling batch** is 16 cases: 4 cold-plate designs × 4 operating conditions, drawn fresh by seed from the registered input box.
- **Every cell** passes the development population's screen.
- **Placement:** a closed-form estimate places the grid so that about a third falls on each side of both limits (die peak 100 °C and hydraulic power 0.25 W).
  - The estimate is **placement only**. It's never stored or used as a label, and labels come from the reference solver.
  - The search accepts 7–9 of 16 predicted feasible per limit (Data Collection's working decision). The QA floor is 6 per side.
- **Disjoint** from every published Cooling case. The draw fails closed if the published set is missing or empty.

## Reference and QA (Validator, under this decision)

- **Reference:** `graded-hotspot-v1` at r = 2√2, with the graded heat-in analysis version.
- **U:**
  - die 0.037 °C (RR-14 band plus the RR-12d floor);
  - hydraulic 3 % of each case's value.
- **A cell within U** is re-solved at r = 4. If it's still within U, the batch is redrawn. More than 1 such cell stops the family, and the r = 4√2 level returns to the owner priced.
- **Evaluation version:** `cooling-dual-sealed-batch-16-v1`, cohort `decision_sealed_grid`.
