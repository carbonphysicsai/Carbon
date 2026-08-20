# Ticket A2 — Strategy schema + dry_validate (C2)

**Wave:** A  
**Build_Out:** C2 Strategy schema  
**Depends on:** A0, A1  
**Authority:** Root `SPEC.md` strategy intent; reconciled
`Design_Specs/Miner_MCP.md` dry-validation contract; maintainer-ratified
`.agent/DECISIONS.md` A2 reconciliation; and `Design_Specs/Build_Out.md`
sequencing

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
superseded for A2 by the ratified `schema_version` decision. The Miner MCP
scaffold is reconciled to the four-field envelope. Rich top-level forms in
older material are not accepted Strategy v1.0 wire fields.

**OQ-008 scope:** A2 implements only declarative schema and denylist validation.
The permitted execution surface, sandbox/process isolation, parser and resource
limits, and production security/operations qualification remain unresolved.

**Tests:** `python -m pytest tests/cpu/test_strategy_schema.py -q`

**Local evidence (2026-08-20):** Exact base
`e696cc43ace96a963f00bb28394da03d35eb267e`; the review-corrected branch passes
231 focused tests and 258 default CPU tests. Strict Ruff/Black, no-new-debt
quality, `git diff --check`, and fresh wheel/import isolation pass. The quality
inventory remains Ruff 757/776 and Black 62/68 from the A2 base; A2 added no
debt, and the gate's 19/6 removal is cumulative against its older baseline.
Draft PR #12 review findings are addressed by a focused same-branch correction
that remains pending independent rereview. The unchanged PoC `role_seed`
collection failure remains inherited. A2 is locally IMPLEMENTED/TESTED only
and remains `in_progress` pending external review and merge; no scientific,
security, LIVE, execution-isolation, or production qualification is claimed.
