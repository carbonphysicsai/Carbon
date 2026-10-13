## 2026-10-13 — OWNER-PHYSICS-GATES-01: battery physics gates — B15 adopted (1e-4 °C); B16 and B9 on the model card; B9 Guard threshold; B8 diagnostic

**Authority.** The owner, directly in the Carbon Validator session on 2026-10-13: "Physics gates: (1) adopt B15 as a gate with allowance 1e-4 °C; (2) B16 model card only; (3) B9 model card plus Guard VERIFY at 0.1 °C below ambient; (4) B8 diagnostic only." He chose from the Validator's decision page `PHYSICS_GATES_DECISION_2026-10-13.md`.
The PR Head put the same four to him directly and he confirmed them in that session
on 2026-10-13, before this record was merged: these are scientific gate values that
fill HUMAN_INPUT slots in the physics contract, and such a decision is not recorded
on a relay alone. The evidence is PHYSICS-CONTRACT-BUILD-01 (#1191), `docs/development/evidence/physics-contract-01/`. Testnet DEVELOPMENT. Mainnet values are not decided here.

**1. B15, rest-period temperature causality: ADOPTED as a mandatory admissibility gate.**
- **Law:** with soc0 and T_amb fixed, the predicted temperature at 0, 30, 60 and 90 s (the 120 s switch excluded) does not change when only c1 or c2 changes. Probe pairs use the contract's registered c1 and c2 steps.
- **Allowance:** 1e-4 °C absolute, maximum over the probe pairs. Permitted violation rate: 0.
- **Basis:** the pinned reference's own residual is exactly 0. Its verified numerical error (OWNER-CODE-VERIFICATION-ACCEPT-01) and 32-bit output rounding (≤ about 3e-5 K) are both below 1e-4 °C, so the allowance never punishes numerical noise (guardrail 1).
- **Bound to the reference solver image** `sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940`. A different image needs a new screen and a new record (guardrail 3).
- **Screened on 142 public members:** 0/65 good-value members rejected, 0/137 rebuilt members rejected, the constructed `control-boundary_optimist` (3.5 °C) caught.
  - It catches no real adversarial member today. It is a structural guard against future-protocol leakage.
- **Prospective:** it applies from the first window of the next deployment state that carries a physics contract with B15 ADOPTED. Current windows, past results and the frozen EV5 are unchanged (invariant 10).
- A B15 failure makes a submission ineligible. It is never compensated by score (invariant 7.3). **A gate never substitutes for verified decisions:** G-FEAS and decision verification are unchanged.

**2. B16, rest-period voltage causality: model card only.** Every good member fails exact invariance: 7–82 mV, median 16 mV. Reported as "rest-voltage leak (mV)", and a construction target. Not a gate, not a score term.

**3. B9, temperature below ambient: model card plus the Envelope Guard.**
- **The card** shows each model's maximum below-ambient deficit, and the share of cases more than 0.1 °C and more than 1 °C below ambient.
- **The Envelope Guard** returns VERIFY when a query's predicted temperature falls more than **0.1 °C** below ambient.
- **Not an exam gate:** the allowance that admits every good member is 5.58 °C, and it catches nothing.
- **Still open (science):** the pinned OKane2022 entropic coefficients are zero, so the reference never dips. The proof that the other signed heat terms are non-negative is HUMAN_INPUT.

**4. B8, temperature curve rises with ambient: diagnostic only.** It catches only the constructed control (1/13 at a 1 % rate) and lowers the rank agreement slightly. Revisit with new attack families or v4 outputs.

**Not adopted:** B5a, B5b, B6, B7, B10 (they reject good members, or catch only controls). B1–B3 are existing exam gates; the contract references them by identity.

**Build:**
- **Platform Codex:** B15 ADOPTED in a new physics contract version; the checker in the validator's eligibility path, as a new deployment-state component; tests.
- **Product Codex:** the Guard's B9 threshold policy.
- **The Carbon Validator** reviews both. It is a scoring-path change, so it goes into the next release and the owner's upgrade sheet.
