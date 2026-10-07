# Q3 grid-resolution sensitivity (quiz-diagnostics-v1 (b), public stand-in)

This is a reported diagnostic and never a gate.

**Setup.**
- **Grid.** The refined grid is 117 points: c1 in 0.125 C steps × c2 in 0.1 C steps, the registered count. It contains EV4's 35-point grid. The registered "0.125 C" wording cannot give 9 c2 values over 0.2–1.0, so the count was honoured.
- **Pool.** EV4's 9 verification scenarios with a feasible design.
- **Members.** 26: the known-good best quarter of EV4's real members plus the run-5 winner, rebuilt on the operator host's CPU.
- **Reference-judged scenarios.** V-T19-S0.22 and V-T19-S0.06, fixed by the rule in `selection.json` before any solve. Their 164 new public reference solves are all OK.

**Results** (`grid-resolution.json`).
- **The pick moves** to a different coarse cell in **18.4 %** of decisions (43 of 234).
- **The reference verdict changes** in **3.8 %** of the judged decisions (2 of 52). Both changes are FEASIBLE ↔ UNRESOLVED at the band edge:
  - mlp_t3000_w128_d2-s0 on V-T19-S0.22, (1.25, 0.8) → (1.375, 1.0);
  - mlp_t3000_w512_d3_f25-s0 on V-T19-S0.06, (1.5, 1.0) → (1.625, 1.0).
- **No pick changes between feasible and infeasible.**
- **The run-5 winner's picks never move.**

**Reading.**
- Grid coarseness changes *which* design is picked fairly often. Neighbouring designs differ little in speed, and the pick moves to them.
- It almost never changes whether the pick is safe. Q3's false-feasible verdict is robust to grid resolution on this stand-in.
- Regret is more grid-sensitive than the safety verdict, because the refined optimum can be a little faster.
