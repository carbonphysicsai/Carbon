# Ticket A11 — Observability: logs + metrics (C16)

**Wave:** A  
**Build_Out:** **v1.4** C16 (logs **and metrics**)  
**Depends on:** A7  

**Goal:** Structured logs and minimal metrics on submit/score paths without leaking secrets or seeds. Expand beyond “a logger exists.”

**DoD:**
- [ ] Logger helper with redaction for keys matching seed/secret/hotkey-secret patterns
- [ ] Correlation id = `submission_id` where applicable
- [ ] Structured **failure tags** on strategy/infra/reject paths (stable string codes, not free text only)
- [ ] Metrics hooks (counters/timers acceptable as in-memory or log-based for Wave A):
  - submit / score / reject / FAILED_INFRA counts
  - duration of validate / run / score stages when available
  - optional: agent ticket retry count fields if threaded through harness
- [ ] Unit test: redaction strips seed-like fields from log payload
- [ ] Unit test or smoke: metrics/failure tags do not include official seeds or draw ids

**Must not:** Log official seeds, master secrets, full strategy weights at info level, or hidden exam identifiers.

**Tests:** `pytest tests/test_logging_redaction.py -q` (and metrics/failure-tag assertions as added)

**Note:** Token/$ spend for the **coding agent** is logged in `.agent/DECISIONS.md` by the agent process; runtime subnet metrics are this ticket’s concern.
