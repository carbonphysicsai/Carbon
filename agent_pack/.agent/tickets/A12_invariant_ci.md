# Ticket A12 — Invariant suite in CI

**Wave:** A  
**Build_Out:** §2 invariants, §12 Wave A done  
**Depends on:** A4, A5, A6, A8, A9, A10  

**Goal:** One CI entrypoint that fails if cross-cutting invariants regress.

**DoD:**
- [ ] `tests/invariants/` **or** pytest marker `invariant` covering at least:
  - no seed leakage (card / leaderboard / MCP shapes)
  - mock isolation (TrainEval mock refuses official)
  - forbidden score inputs ignored
  - stub `emission_capable=False`
  - LIVE blocked without qualification (registry)
  - fee≠score
- [ ] CI job runs invariant suite
- [ ] WAVE.md A12 evidence = command + green run note
- [ ] Optional: short `.agent/WAVE_A_REPORT.md` draft listing remaining human/SciML inputs

**Must not:** Skip invariant failures to greenwash Wave A.

**Tests:** `pytest -m invariant -q` or `pytest tests/invariants -q`
