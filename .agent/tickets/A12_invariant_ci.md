# Ticket A12 — Invariant suite in CI

**Wave:** A  
**Build_Out:** §2 invariants, §12 Wave A done  
**Depends on:** A4, A5, A6, A8, A9, A10  

**Goal:** One CI entrypoint that fails if cross-cutting invariants regress.

**DoD:**
- [ ] `tests/invariants/` or pytest marker `invariant` covering: no seed leakage; mock isolation; forbidden score inputs; stub emission_capable=False; LIVE blocked without qualification; fee≠score
- [ ] CI job runs invariant suite
- [ ] `.agent/WAVE.md` A12 evidence = command + green run note
- [ ] Optional: `.agent/WAVE_A_REPORT.md` listing remaining human/SciML inputs

**Must not:** Skip invariant failures to greenwash Wave A.

**Tests:** `pytest -m invariant -q` or `pytest tests/invariants -q`
