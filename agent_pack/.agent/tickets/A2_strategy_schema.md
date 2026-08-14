# Ticket A2 — Strategy schema + dry_validate

**Wave:** A  
**Goal:** JSON Schema (or equivalent) for miner strategies + a `dry_validate` function used by MCP later.

**DoD:**
- [ ] Schema file under package (e.g. `carbon/schema/strategy.schema.json`)
- [ ] `dry_validate(strategy: dict) -> ValidationResult` with clear errors
- [ ] Denylist stub (unsupported keys/backbones) returns invalid
- [ ] Unit tests for valid / invalid / denylist

**Must not:** Accept arbitrary code execution fields without explicit allow-list design.

**Tests:** `pytest tests/test_strategy_schema.py -q`
