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

**Final evidence (2026-08-20):** Exact original base
`e696cc43ace96a963f00bb28394da03d35eb267e`; reviewed final head
`d73f697ebd9df9b8c96b7a46fd4c9986444f0928`; normal PR #12 merge commit
`bfc0b97e1b16625141de3950428bc2fdf69f42ea`. The reviewed branch passed 231
focused tests and 258 default CPU tests. Post-merge main CI run `32360050671`
also reported 258 default tests passing and the code-quality gate succeeded.
Strict Ruff/Black, no-new-debt quality, `git diff --check`, and fresh
wheel/import isolation passed. The inherited PoC `role_seed` failure remains
unrelated and unfixed.

**Status:** A2 is `done`, **IMPLEMENTED and TESTED** only for its schema and
`dry_validate` boundary. This status does not claim scientific validation,
end-to-end hostile execution isolation, LIVE qualification, or production
qualification. A3 remains `todo` and unstarted.
