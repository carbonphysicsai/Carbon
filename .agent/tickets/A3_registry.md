# Ticket A3 — Challenge registry + LIVE gate (C1)

**Wave:** A  
**Build_Out:** **v1.4** C1 Challenge registry, **§8 LIVE qualification manifest**  
**Depends on:** A0, A1, A2

**Status:** `in_progress` on exact base
`e6fb20b1dc361ded442fcf41d118cea5f2c775cd`; local verification is complete,
while independent review, merge, and post-merge CI remain pending.

**Goal:** File-backed registry of challenges; **cannot** transition to LIVE without qualification slots filled **and content hashes bound to the exact challenge version**.

**DoD:**
- [x] Standard-library JSON registry under `carbon/registry/`, with canonical
  layout `<registry_root>/<challenge_id>/<version>.json`
- [x] Immutable `ChallengeKey(challenge_id, version)` and record fields for
  lifecycle status, declarative backbone compatibility, artifact bindings,
  qualification evidence, and reserved receipt/backend identities
- [x] Exact-version `load`, `save`, `scan`, diagnostic eligibility, boolean
  eligibility, effective-LIVE, checked activation, and compatibility APIs
- [x] `can_go_live(challenge_id, version) -> bool` is **False** if:
  - any required qualification slot missing / `HUMAN_INPUT`, **or**
  - any required artifact hash is missing / does not match the bound challenge version artifacts
- [x] Required slot/state pairs are exact and mixed, not a blanket
  `APPROVED` state:

  | Slot | State |
  |---|---|
  | `generator_envelope` | `APPROVED` |
  | `generator_validation` | `PASSED` |
  | `dossier_level_1` | `APPROVED` |
  | `score_pack` | `APPROVED` |
  | `mock_incompleteness` | `APPROVED` |
  | `train_backend` | `QUALIFIED` |
  | `launch_bar` | `SIGNED` |
  | `mcp_readiness` | `SIGNED` |
- [x] Every declared artifact binding is checked as
  `sha256:<64 lowercase hex>` against actual regular-file bytes below the
  configured artifact root; non-null labels alone are insufficient
- [x] Default status is `draft`; ordinary save cannot create or overwrite
  `live`; checked activation requires a complete production assessment; an
  effective-LIVE query revalidates current bytes
- [x] Fixture isolation is structural: `status="fixture"`, manifest
  `mode="fixture"`, and an explicit `fixture_mode=True` eligibility call are
  independently required; fixture records cannot use production activation
- [x] Optional receipt/backend identity fields are exact structural bindings
  to `mcp_readiness` and `train_backend` evidence
- [x] Persistence and hashing use no-follow descriptor-relative access;
  writes use a per-key interprocess lock and fsynced same-directory atomic
  replacement
- [x] Complete local CPU, strict-format/lint, no-new-debt, diff, and fresh-wheel
  outside-tree verification
- [ ] Complete independent review, merge, and post-merge CI evidence

**Reserved-binding boundary:** Exact equality of the ordered backend-profile
binding or receipt schema identifier binds evidence to a record. It never
approves a backend, qualifies an environment, establishes scientific
correctness, verifies a signer, or proves a receipt is signed. The eight state
strings are human-owned assertions plus structural evidence requirements, not
an A3 scientific judgment engine.

**Must not:** Ship any challenge with `status=live` by default. Do not invent
real scientific hashes.

**Tests:** `python -m pytest tests/cpu/test_registry.py -q`. A static
structure-only fixture is kept below `tests/fixtures/registry/`; verification
evidence is recorded below.

**Local evidence (2026-08-20):** the untouched supported baseline passed 258
tests; the focused A3 suite passed 127 tests; the complete default CPU suite
passed 385 tests. Strict Ruff and Black passed all six changed Python files.
The CI-equivalent quality gate against exact base `e6fb20b1...` passed with
inventory `Ruff 757/776; Black 62/68`, 19 Ruff and 6 Black debt items removed,
and no new debt. `git diff --check` passed. A no-dependency wheel with SHA-256
`bed35b88db038e6b4c89cae6b813d3b721703ff8d70b6c4d161f098fee18c08c`
installed into a fresh environment and ran from outside the checkout; the
registry loaded no blocked scientific, MCP, validator, or Bittensor modules.
The inherited PoC smoke reached its protocol-only NumPy runs, then exited 2 at
the pre-existing `poc.generators.burgers1d.role_seed` collection import error;
A3 does not change that PoC boundary.

**Implementation boundary:** No default or fixture is production LIVE. No real
challenge, scientific hash, backend approval, receipt-signature verification,
Score Pack behavior, official seeding, scoring, execution, MCP transport, or
Bittensor capability is added by A3.
