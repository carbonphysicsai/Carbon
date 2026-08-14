# Ticket A2 — Strategy schema + dry_validate (C2)

**Wave:** A  
**Build_Out:** C2 Strategy schema  
**Depends on:** A0, A1  
**Authority:** Miner_MCP / SPEC strategy fields if present; else minimal schema + extension points  

**Goal:** Versioned strategy document validation used by MCP `dry_validate` and submit path.

**DoD:**
- [ ] JSON Schema (or Pydantic model) at e.g. `carbon/schema/strategy.schema.json` or `carbon/schema/strategy.py`
- [ ] Required fields for Wave A: at least `challenge_id`, `backbone` (or equivalent), `strategy_version`; extensible object for training hyperparameters
- [ ] `dry_validate(strategy: dict) -> ValidationResult` with `ok: bool`, structured `errors[]`
- [ ] Denylist / unsupported-backbone path returns invalid (fixture list OK)
- [ ] Unit tests: valid fixture, missing required field, denylist hit
- [ ] Schema version field present for future evolution

**Must not:** Accept arbitrary executable code blobs without an explicit allow-listed mechanism. Do not invent full production hyperparameter catalogs.

**Tests:** `pytest tests/test_strategy_schema.py -q`

**Pin to Carbon:** This is what miners submit; MCP and FSM both call the same validator.
