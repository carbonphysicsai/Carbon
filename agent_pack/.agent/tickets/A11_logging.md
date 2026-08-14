# Ticket A11 — Observability / logging (C16)

**Wave:** A  
**Build_Out:** C16  
**Depends on:** A7  

**Goal:** Structured logs on submit/score paths without leaking secrets or seeds.

**DoD:**
- [ ] Logger helper with redaction for keys matching seed/secret/hotkey-secret patterns
- [ ] Used on submit and score (or FSM transition) paths
- [ ] Correlation id = `submission_id` where applicable
- [ ] Unit test: redaction strips seed-like fields from log payload

**Must not:** Log official seeds, master secrets, or full strategy weights at info level.

**Tests:** `pytest tests/test_logging_redaction.py -q`
