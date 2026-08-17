# Ticket A11 — Observability: logs + metrics (C16)

**Wave:** A  
**Build_Out:** **v1.4** C16 (logs **and metrics**)  
**Depends on:** A7  

**Goal:** Structured logs and minimal metrics on submit/score paths without leaking secrets or seeds.

**DoD:**
- [ ] Logger helper with redaction for seed/secret patterns
- [ ] Correlation id = `submission_id` where applicable
- [ ] Structured **failure tags** on strategy/infra/reject paths
- [ ] Metrics hooks: submit/score/reject/FAILED_INFRA counts; stage durations
- [ ] Unit tests: redaction; no seeds/draw ids in metrics/tags

**Must not:** Log official seeds, master secrets, full strategy weights at info level, or hidden exam identifiers.

**Tests:** `pytest tests/test_logging_redaction.py -q`
