# Ticket A12 — Invariant suite in CI

**Wave:** A  
**Goal:** Aggregate invariant tests run in CI as a named marker or folder.

**DoD:**
- [ ] `tests/invariants/` or pytest marker `invariant`
- [ ] CI job runs them
- [ ] WAVE.md A12 marked done with command in evidence

**Tests:** `pytest -m invariant -q` or `pytest tests/invariants -q`
