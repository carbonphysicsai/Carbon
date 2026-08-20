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

## Post-merge corrective repair — cold-start backbone registry

PR #5 was reviewed at `c4d0a9210aaacad077287c2ca14e20b2bb6d396e` and
merged as `5f810a57379a608119aa9cc9bbd6fc78a48baf13`. A later independent
review found that its optional-backend tests primed adapter registration and
therefore did not establish the claimed cold-registry path. A fresh package
registry listed no adapters, and `carbon.backbones.registry` maintained a
second disconnected mapping. The checked DoD and evidence above remain the
historical record for PR #5's broader install, CPU CI, quality, and PoC work;
they are not evidence that this cold-start contract passed at the merged head.

The initial repair fetch found expected `main` at
`3e29fef703d4b60c97ff4873cb395d2436cdad0a`. A pre-publication fetch found
non-conflicting PR #8 had since advanced `main`; after inspecting its sole
scientific-reference-canon change, the branch was fast-forwarded to actual
repair base `7f499e589b86ed127745831ccacdc1c8e4ffb677`. This preserves PR #6,
PR #7, and PR #8. The repair keeps one canonical package-owned registry, adds
an explicit catalog for `physicsnemo_fno`, `fno`, `deeponet`, and `uno`, and
converts the historical registry module into a compatibility delegate. Fresh
isolated subprocess tests exercise discovery, extra-specific construction
failure, and preservation of transitive module failures without loading
optional scientific packages during discovery.

In a fresh Python 3.11.11 environment, the supported editable development
install exited 0 and installed `carbon==0.9.0`; the default suite passed 27
tests with no skips, xfails, or failures. All nine focused optional-backend tests
passed. The no-new-debt gate passed at Ruff 757/776 and Black 62/68 with three
changed Python files strict-clean, a repair delta of minus 12 Ruff and minus two
Black fingerprints from untouched current `main`. `git diff --check` exited 0.
The PoC smoke command exited 2 at the same inherited missing-`role_seed`
collection error.

This is a narrow A1 corrective repair. Installed-backend API compatibility and
scientific correctness remain unqualified, the inherited PoC failure remains
out of scope, and no A2+ behavior is introduced. At the corrective branch's
pre-merge record, A1 was `in_progress` and A2 remained `todo` pending independent
rereview and merge.

That gate is now closed. Independently rereviewed PR #9 final head
`a247bb189d44ddf18de504572ef620cf5d501d10` passed CI run `32326384939` with
27 CPU tests and the code-quality gate, then merged as
`819da3c163c2fb9476a6881aab8740cc6984066e`. The merge is ancestral to current
closure base `fb6bbf393f77ae80d76abf3eda0e53a7dfd12f17`. The corrective registry
contract is therefore on `main`, A1 is `done`, and A2 remains the unstarted
`todo` next ticket. Scientific backend compatibility and scientific or
production qualification remain unclaimed.
