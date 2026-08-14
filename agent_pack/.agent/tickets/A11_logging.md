# Ticket A11 — Logging

**Wave:** A  
**Goal:** Structured logs for submit/score paths without leaking secrets/seeds.

**DoD:**
- [ ] Basic logger helper
- [ ] Redaction test for seed-like keys
- [ ] Used in at least submit or score path

**Tests:** `pytest tests/test_logging_redaction.py -q`
