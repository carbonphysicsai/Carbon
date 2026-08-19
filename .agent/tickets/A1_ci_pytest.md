# Ticket A1 — CI skeleton (C0, preserve existing)

**Wave:** A  
**Build_Out:** **v1.4** C0, §17 CI matrix note (CPU-only units)  
**Depends on:** A0  

**Goal:** Pytest runs locally and on GitHub Actions without GPU. **Repair/extend existing CI** rather than replacing a working workflow blindly.

**DoD:**
- [x] **Baseline:** run existing CI/pytest before edits; record outcome
- [x] `tests/` with at least one smoke test that imports the package (KEEP existing smokes if present)
- [x] `requirements-dev.txt` (or `pyproject.toml` optional-deps) includes `pytest`
- [x] `.github/workflows/ci.yml` runs `pytest -q` on push/PR (ubuntu, CPU) — WRAP existing workflow if one exists
- [x] Document `pytest -q` and PoC smoke command if present
- [x] Optional: pytest marker `invariant` registered for A12
- [x] **Baseline + new smoke still green** — local clean-environment evidence and draft-PR run `32250522522` are green

**Must not:** Require GPU, network services, or secrets in default CI. Must not delete existing green CI without REPLACE justification in DECISIONS.md.

**Tests:** `pytest -q` exits 0 locally and in CI config.

## A1 execution evidence

**Authorized base:** `origin/main` was fetched and verified at
`0b2eec30250f1767cc434836e189cca219154d4d`; PR #4 was merged at that commit.
Work is isolated on `agent/a1-ci-skeleton`.

**Inherited baseline:** CPython 3.11.11/pip 24.0 local diagnostics were run in a
detached clean worktree at the authorized base. `python -m pip install -e
".[dev]"` exited 1 because `physicsnemo` had no matching distribution. The
workflow test command was therefore not reached in the actual base Actions run.
Forced `python -m pytest -q` exited 2 with 22 collection errors; forced
`pytest tests/ -q --tb=no` exited 2 with five legacy collection errors.
`ruff check .` exited 1 with 776 findings (544 fixable), while `black --check
.` exited 123 with 66 reformat findings and two parse failures. The no-dependency
editable install and all 14 outside-tree A0 role imports passed. `POC_FAST=1
bash poc/scripts/smoke.sh` exited 2 after its fixtures because
`poc.generators.burgers1d.role_seed` is absent. `git diff --check` exited 0.

Base Actions run `32244438188` corroborates the stage distinction: test job
`96041796858` failed dependency installation and skipped pytest; quality job
`96041796669` reached Ruff, failed on the inherited inventory, and skipped
Black.

**Local candidate evidence:** In a new detached worktree populated only by the
A1 diff, the literal `python -m pip install -e ".[dev]"` exited 0. The installed
distribution was `carbon==0.9.0`. From `/private/tmp` with isolated import mode,
`carbon` and all 14 A0 role imports passed. A separately built and installed
wheel contained the same 14 roles and imported from `site-packages`.
`python -m pytest -q` exited 0 with 22 passed. The blocking quality gate exited
0 with Ruff 769/776 and Black 64/68: seven inherited Ruff and four inherited
Black entries were removed, no new fingerprints appeared, and all 12 changed
Python files passed strict checks. The raw audits remain inherited-red: Ruff
769 (537 fixable), and Black 62 reformat findings plus the same two parse
failures. `git diff --check` exited 0.

The post-change PoC smoke command again exited 2 only when final pytest
collection reached the same missing `role_seed`; A1 did not worsen or claim the
PoC. Draft PR #5 Actions run `32250522522` passed both blocking jobs. CPU tests
job `96060233144` installed the supported environment, reached the literal
`python -m pytest -q`, and passed 22 tests. Code-quality job `96060233203`
passed the 769/776 Ruff and 64/68 Black ratchet, then uploaded complete inventory
artifact `9364221072`. The final PR head, changed-file inventory, and final
post-evidence Actions run are recorded in the PR body.

**Classification:** The five inherited root tests remain under `tests/legacy/`
with their assertions preserved. All 67 PoC tests are marked `poc`; 32 are
classified integration, two JAX-backend, and one opt-in gold. These explicit
lanes retain stale/scientific evidence without making it a false CPU contract.

**Maturity:** A1 implements and tests package installation, CPU import roles,
default pytest collection, and a no-new-quality-debt CI gate. It does not
qualify scientific models, scoring, seeds, TrainEval, Julia, Bittensor, network
operation, emissions, security, or production behavior.
