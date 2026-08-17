# Ticket A1 — CI skeleton (C0, preserve existing)

**Wave:** A  
**Build_Out:** **v1.4** C0, §17 CI matrix note (CPU-only units)  
**Depends on:** A0  

**Goal:** Pytest runs locally and on GitHub Actions without GPU. **Repair/extend existing CI** rather than replacing a working workflow blindly.

**DoD:**
- [ ] **Baseline:** run existing CI/pytest before edits; record outcome
- [ ] `tests/` with at least one smoke test that imports the package (KEEP existing smokes if present)
- [ ] `requirements-dev.txt` (or `pyproject.toml` optional-deps) includes `pytest`
- [ ] `.github/workflows/ci.yml` runs `pytest -q` on push/PR (ubuntu, CPU) — WRAP existing workflow if one exists
- [ ] README or `agent_pack` note documents: `pytest -q` and PoC smoke command if present
- [ ] Optional: pytest marker `invariant` registered for A12
- [ ] **Baseline + new smoke still green**

**Must not:** Require GPU, network services, or secrets in default CI. Must not delete existing green CI without REPLACE justification in DECISIONS.md.

**Tests:** `pytest -q` exits 0 locally and in CI config.

**Files (suggested):**
```text
tests/test_smoke.py
requirements-dev.txt
.github/workflows/ci.yml
pytest.ini  # optional markers
```
