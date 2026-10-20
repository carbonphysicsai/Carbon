# OWNER-COOLING-VERIFICATION-01: Cooling code-verification criteria and convergence spend

Date: 2026-10-19
Status: APPROVED by the owner ("Ya to both"). Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it.
Implementation: **criteria only.** No verdict exists yet. `verification.json` is still `SPECIFIED_NOT_RUN` as of `a3e0771df`, and the manufactured-energy and round-off reruns (RR-12c) are pending.
Designs: `codex-queue/reports/COOLING_VERIFICATION_AND_CONVERGENCE_DESIGNS_20261019.md`, reviewed by the Validator.

## Decided

1. **Code-verification criteria for Cooling's OpenFOAM image** (`opencfd/openfoam-default@sha256:33fb575a…`, v2512):
   - observed order on the finest pair in **[1.7, 2.3]**, the same band as GetDP and Elmer (OWNER-CODE-VERIFICATION-ACCEPT-01);
   - conservation and interface terms at round-off.

   Applied to the existing closed-form rungs (Poiseuille, Nusselt, conjugate coupling) and the one remaining manufactured-energy rung. The verdict is packaged in the same shape as the GetDP verdict.
2. **Convergence spend:**
   - a probe under **USD 1** (one cell at r = 2, 2√2 and 4);
   - then a 5-cell near-limit ladder (2 cells near die_peak 100 °C, 2 near hydraulic 0.25 W, 1 far) at about **USD 2–4**;
   - under the Motor-style rule and the stop triggers in the design.

**Output:** `carbon.cooling.reference-uncertainty.v1`, reviewed by the Validator before it reaches any pack.

**Not decided here:** any reference-uncertainty value. That comes only from the runs.

## Applying the criteria (Carbon Validator, 2026-10-19, after RR-12b)

- **The [1.7, 2.3] band applies to every reported norm (L2 and L∞).** The band has two sides: an order above it means the test isn't measuring the formal order. That happened in RR-12b, where L∞ reached 2.99 because a Dirichlet T was imposed on the outflow boundary.
- **The manufactured-solution test uses the production outflow condition:**
  - zeroGradient only where the exact ∂T/∂x is 0 at the outlet;
  - otherwise fixedGradient set to the exact gradient.
- **The reading of "At round-off":** a term counts as at round-off when it is shown to be at the iterative-convergence floor.
  - **The test:** with every fvSolution tolerance 100× tighter, the term falls ≥ 10×, or reaches ≤ 1e-12 relative to its scale.
  - A term that doesn't move is a finding, not a pass.
  - This reading is the Validator's and is stated here for the owner.
