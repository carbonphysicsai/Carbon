# Ticket A2 — Strategy schema + dry_validate (C2)

**Wave:** A  
**Build_Out:** C2 Strategy schema  
**Depends on:** A0, A1  
**Authority:** Ratified A2 contract recorded in the implementation plan; stale
Miner_MCP/SPEC examples are historical conflicts for later repair

**Goal:** Versioned strategy document validation used by MCP `dry_validate` and submit path.

**DoD:**
- [x] Standard-library schema implementation at `carbon/schema/strategy.py`
- [x] Exact required fields: `schema_version`, `challenge_id`, scalar
  `backbone`, and inert object `parameters`
- [x] `dry_validate(strategy: object) -> ValidationResult` with immutable
  `ok: bool` and structured `errors: tuple[ValidationIssue, ...]`
- [x] Recursive forbidden-capability and unsupported-backbone paths return
  stable invalid results
- [x] Current CPU tests cover valid, missing-field, hostile JSON, denylist,
  purity, deterministic error, and installed/outside-tree behavior
- [x] Exact schema version `"1.0"` is required; aliases/defaults fail closed

**Must not:** Accept arbitrary executable code blobs without an explicit allow-listed mechanism. Do not invent full production hyperparameter catalogs.

**Canonical-field note:** This ticket's original `strategy_version` wording is
superseded for A2 by the ratified `schema_version` decision. Rich top-level
training/loss/curriculum/data examples remain stale and are not accepted.

**Tests:** `python -m pytest tests/cpu/test_strategy_schema.py -q`

**Local evidence (2026-08-20):** Exact base
`e696cc43ace96a963f00bb28394da03d35eb267e`; 181 focused tests and 208 default
CPU tests passed; strict Ruff/Black, no-new-debt quality, `git diff --check`,
fresh wheel/import isolation, and independent adversarial review passed. The
unchanged PoC `role_seed` collection failure remains inherited. A2 is locally
IMPLEMENTED/TESTED only and remains `in_progress` pending external review and
merge; no scientific, LIVE, execution-isolation, or production qualification
is claimed.
