# Ticket A6 — Card store + Phase 0 disclosure (C12)

**Wave:** A  
**Build_Out:** C12, §9 Model Card vs EvaluationCard  
**Depends on:** A5 (InternalResult shape)  

**Goal:** Persist full InternalResult; miner-facing reads return **budgeted EvaluationCard** only.

**DoD:**
- [ ] `write_internal(submission_id, internal_result)`
- [ ] `read_budgeted(submission_id, requester_hotkey) -> EvaluationCard | deny`
- [ ] Allow-list filter: overall score, coarse components, gate pass/fail, failure tags, short diagnostics
- [ ] Strip: seeds, draw ids, fine margins, per-stress breakdowns, pack-internal diagnostics not allow-listed
- [ ] Unauthorized hotkey denied (simple equality stub OK)
- [ ] Hotkey↔submission binding test
- [ ] Tests for filter, deny, and “full internal never equals budgeted”

**Must not:** Return full Model Card / InternalResult on miner MCP path.

**Tests:** `pytest tests/test_card_store.py -q`
