# Ticket A12 — Invariant suite in CI

**Wave:** A  
**Build_Out:** §2 invariants, §12 Wave A done  
**Depends on:** A4, A5, A6, A7, A8, A9, A10, A11

**Goal:** One CI entrypoint that fails if cross-cutting invariants regress.

**DoD:**
- [ ] `tests/invariants/` or pytest marker `invariant` covering current
      enforceable guarantees: no seed leakage; fixture/mock isolation where
      implemented; forbidden score inputs; fixture/stub cannot become
      emission/production evidence; LIVE blocked without exact qualification;
      fee≠score; infrastructure failure≠scientific failure; disclosure
      allow-lists; and A11 redaction
- [ ] CI job runs invariant suite
- [ ] `.agent/WAVE.md` A12 evidence = command + green run note
- [ ] `.agent/WAVE_A_REPORT.md` records exact evidence, bounded maturity, and
      remaining human/SciML/security/network inputs

**Must not:** Skip invariant failures to greenwash Wave A.

**Tests:** `pytest -m invariant -q` or `pytest tests/invariants -q`
