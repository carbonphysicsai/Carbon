# Ticket A6 — Card store + disclosure filter

**Wave:** A  
**Goal:** Store InternalResult; miner-facing read returns budgeted EvaluationCard only.

**DoD:**
- [ ] write_internal / read_budgeted APIs
- [ ] Allow-list filter (no seeds, draw ids, fine margins)
- [ ] Unauthorized hotkey denied (simple authz stub OK)
- [ ] Tests for filter and deny

**Must not:** Return full Model Card on miner path.

**Tests:** `pytest tests/test_card_store.py -q`
