# Ticket A1 — CI skeleton (C0)

**Wave:** A  
**Build_Out:** C0, §17 CI matrix note (CPU-only units)  
**Depends on:** A0  

**Goal:** Pytest runs locally and on GitHub Actions without GPU.

**DoD:**
- [ ] `tests/` with at least one smoke test that imports the package
- [ ] `requirements-dev.txt` (or `pyproject.toml` optional-deps) includes `pytest`
- [ ] `.github/workflows/ci.yml` runs `pytest -q` on push/PR (ubuntu, CPU)
- [ ] README or `agent_pack` note documents: `pytest -q`
- [ ] Optional: pytest marker `invariant` registered in `pytest.ini` / `pyproject.toml` for A12

**Must not:** Require GPU, network services, or secrets in default CI.

**Tests:** `pytest -q` exits 0 locally and in CI config.

**Files (suggested):**
```text
tests/test_smoke.py
requirements-dev.txt
.github/workflows/ci.yml
pytest.ini  # optional markers
```
