# Ticket A1 — CI skeleton

**Wave:** A  
**Goal:** Pytest runs locally and in GitHub Actions on PRs.

**DoD:**
- [ ] `tests/` with at least one passing smoke test
- [ ] `requirements-dev.txt` or equivalent with pytest
- [ ] `.github/workflows/ci.yml` runs pytest on push/PR
- [ ] Document command: `pytest -q`

**Must not:** Require GPU in CI.

**Tests:** `pytest -q` exits 0
