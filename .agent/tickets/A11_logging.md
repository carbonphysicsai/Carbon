# Ticket A11 — Observability: logs + metrics (C16)

**Wave:** A  
**Build_Out:** **v1.4** C16 (logs **and metrics**)  
**Depends on:** A5, A6, A7, A8, A9, A10

**Goal:** Structured logs and minimal metrics on submit/score paths without leaking secrets or seeds.

**DoD:**
- [ ] Logger helper with redaction for seed/secret patterns
- [ ] Correlation id = `submission_id` where applicable
- [ ] Structured **failure tags** that preserve reject, candidate/scientific,
      reconstruction, reference, and infrastructure separation where current
      owner types permit
- [ ] Metrics hooks: submit/score/reject/FAILED_INFRA counts; stage durations
- [ ] Unit tests: redaction; no seeds/draw ids or protected exam identity in
      logs, metrics, tags, error labels, or correlation fields
- [ ] A9/A10 provider and public-error telemetry uses fixed safe classes, not
      raw exception text, request values, private record fields, or hidden IDs

**Must not:** Log official seeds, master secrets, full strategy weights at info level, or hidden exam identifiers.

**Tests:** focused canonical CPU test path chosen by the ratified A11 plan,
then full CPU + invariant + quality gates
