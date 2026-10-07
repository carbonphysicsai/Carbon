## 2026-10-07 — BATTERY-CLIMB-1-REVIEW: battery's Level 2 and Level 3 climb, reviewed for development-only variants

**Authority.**
- **The climb.** The owner approved battery's declarative-only Level 2 and
  Level 3 climb on 2026-10-07, relayed by the Test Lead. Graphite's level
  planner proposed the capabilities in a climb session (`level-climb-1`,
  GRAPHITE-PLANNER-CLIMB-01, #732) under GRAPHITE-GRANT-PLANNER-02. The owner
  confirmed the pool-selection addition directly in the Test Engineer's
  session.
- **The review.** The Test Lead's F1 review, 2026-10-07, under
  OWNER-GRAPHITE-DEV-LEVELS-01: for development-only variants the Test Lead
  accepts, and the construction contract owner decides only at LOCK.

**What is recorded.** Under
`carbon/challenge_pipeline/proposals/battery-fastcharge-ageing-development-v1/climbs/`:
- **The proposals:** the two climb proposals, byte for byte as the planner
  wrote them, with status PROPOSED.
- **The disposition:** the Test Lead's review, in
  `level-climb-1-disposition.json`.

The accepted contract proposals (`level-N.json`) are unchanged. A climb is not
a contract decision.

**The disposition.**

| Level | Capability | Disposition |
|---|---|---|
| 2 | `data.pool_selection` | Accepted with changes: Carbon's dynamic published pool (TRAIN plus PRACTICE plus auto-retired published bank cases), versioned by its published-set digest and pinned by the recipe; disjoint by `overlap_check`; the subset size counts in the cost calculator |
| 2 | `optimizer.muon_spectral` | Accepted, as a Muon-family variant |
| 2 | `stages.polish_optimizer` | Dropped: it duplicates Level 3's quasi-Newton family |
| 3 | `numerics.quasi_newton_family` | Accepted: lbfgs, bfgs, ssbfgs and ssbroyden, default lbfgs |
| 3 | `numerics.line_search` | Accepted: strong_wolfe, backtracking and none; "none" is the miner's risk, bounded by the step budget |
| 3 | `numerics.spectral_preconditioner` | Dropped for now: it duplicates `muon_spectral`; revisit after the Level 2 data |

**Conditions on every kept capability.**
1. **Tests:**
   - determinism (R1 on CPU);
   - a loss decrease on a fixed battery checkpoint;
   - default equivalence (the default is byte-identical to today).

   No test claims a paper's improvement.
2. **Cost:** the training budget cost calculator counts each routine's real
   cost, and Phase F stress-tests it.
3. **GPU risk:** SVD and BFGS are flagged as GPU-nondeterminism risks for the
   A40 R1 leg.
4. **Placement:** development-only variants outside CONTRACTS. Miner surfaces
   refuse them, and findings block LOCK, not exploration.

**Next.** The development-only variants follow the #611 pattern, in JAX and
PyTorch, one PR each: Level 3's numerics, Level 2's SpecMuon, and Level 2's
pool selection (which needs the published, versioned pool).
