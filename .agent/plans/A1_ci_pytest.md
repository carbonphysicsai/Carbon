# Plan — A1 CPU-only CI and pytest baseline

**Ticket:** A1 only (`.agent/tickets/A1_ci_pytest.md`)

**Starting commit:** `0b2eec30250f1767cc434836e189cca219154d4d`
**Relevant specifications:** root `AGENTS.md`; `Design_Specs/Build_Out.md`
C0 and section 17; `.agent/{WAVE,DECISIONS,INVARIANTS}.md`;
`agent_pack/EXECUTION_PROTOCOL.md`.

## Existing implementation and classification

- **KEEP** the lowercase `carbon/` package and the fourteen behavior-free A0
  role boundaries.
- **REPAIR** `pyproject.toml`: the default dependency list currently mixes the
  core boundary with chain, scientific, accelerator, and post-P0 dependencies;
  `.[dev]` is referenced by CI but is not declared.
- **REPAIR** the existing two-job GitHub Actions workflow so its test job reaches
  pytest and its quality job remains a separate blocking result.
- **WRAP** inherited Ruff and Black debt with a fingerprint ratchet. Full cleanup
  would touch most of the legacy Python tree and two files do not parse.
- **CLASSIFY** the five root historical tests as legacy and the PoC tests as an
  explicit optional scientific/PoC lane. Preserve their assertions and current
  failure evidence; do not promote stale behavior into the A1 CPU contract.
- **REPAIR** only the optional NeuralOperator and PhysicsNeMo import boundaries
  needed to keep optional packages out of core import and to produce actionable
  missing-extra errors.

## Proposed changes

1. Declare an empty core dependency set; add pinned development tools and
   explicit chain/scientific backend extras. Keep the PoC dependency lane
   explicit and outside default CI.
2. Add a meaningful default CPU suite for the package import, all fourteen A0
   roles, distribution metadata, outside-tree editable imports, and absence of
   optional scientific packages.
3. Move historical root tests to an explicitly documented legacy lane and
   mark the existing PoC test lane without weakening or deleting assertions.
4. Add a committed machine-readable Ruff/Black debt inventory captured from
   the starting commit and a blocking comparator that rejects new diagnostics.
   Require strict Ruff and Black checks for every Python file touched by the PR.
5. Repair `.github/workflows/ci.yml`, document commands/extras/markers, and
   record baseline and post-change evidence in the A1 ticket/decision log.

## Expected files

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `.ci/quality-baseline.json`
- `scripts/check_quality.py`
- `tests/` and `legacy_tests/` classification/import tests
- `poc/tests/conftest.py`
- `carbon/backbones/{neural_operator,physicsnemo}.py`
- `README.md`, `docs/DEVELOPMENT.md`
- `.agent/{DECISIONS,WAVE}.md`, `.agent/tickets/A1_ci_pytest.md`

## Verification

- Clean Python 3.11 virtual environment:
  `python -m pip install -e ".[dev]"`; `python -m pytest -q`.
- Outside-tree imports of `carbon` and all fourteen A0 roles, plus distribution
  and wheel/editable discovery inspection.
- `python scripts/check_quality.py ...`, `ruff check .`, `black --check .`, and
  `git diff --check`, with raw inherited failures distinguished from the green
  ratchet.
- `POC_FAST=1 bash poc/scripts/smoke.sh`, recorded as inherited/out of scope if
  its existing failure is unchanged.
- Draft PR Actions: test and blocking quality jobs must both pass before A1 is
  marked done.

## Risks / unresolved decisions

- Legacy tests encode retired namespaces/APIs and superseded scientific
  expectations. A1 must retain them without treating them as current-spec
  acceptance evidence.
- PhysicsNeMo is optional and unqualified. Only its supported distribution/API
  boundary is repaired; no backend or scientific qualification is claimed.
- The quality baseline must never be regenerated from the A1 head merely to
  absorb new violations. It remains anchored to the recorded starting SHA.
- No scientific, security, Bittensor-network, emissions, or A2+ behavior is in
  scope.

### Implementation result

The dependency boundary, 22-test CPU lane, explicit legacy/PoC classification,
lazy optional-backend failure contracts, fingerprint quality ratchet, and
repaired two-job workflow are implemented. Clean-environment editable and wheel
installation/import proofs pass; default pytest and the blocking local quality
gate are green. The inherited PoC terminal failure is unchanged. Draft PR #5
run `32250522522` passed both blocking jobs, reached 22 CPU tests, and uploaded
the full quality inventory. A1 is complete; no A2+ behavior was introduced.

### Post-merge corrective addendum — 2026-08-20

The implementation result immediately above records the conclusion reached for
PR #5. After that PR merged, independent review showed that the optional-backend
tests imported adapter modules before registry lookup and concealed an empty
cold registry; a second mapping in `carbon.backbones.registry` also split the
state. The narrow corrective plan is to preserve `carbon.backbones` as the
canonical API, add an explicit built-in-name-to-local-module catalog, delegate
the compatibility module to that one state, and test the contract in fresh
isolated subprocesses. Scientific packages stay lazy, and installed-backend API
or scientific qualification remains deferred.

This correction does not reopen the broader A1 dependency, pytest-lane, PoC, or
quality-ratchet design, and it introduces no A2+ behavior. A1 returns to
`in_progress`; A2 remains `todo` until the corrective draft PR is independently
rereviewed and merged.
