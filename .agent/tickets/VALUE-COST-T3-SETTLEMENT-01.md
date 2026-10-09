# VALUE-COST-T3-SETTLEMENT-01 working contract

**Status:** DEVELOPMENT follow-up to merged #850, authorized by the owner on
2026-10-08. Base: merged main at branch start. One PR to PR Head. Historical
Development Hub map_ref: `SYSTEM/DEVELOPMENT-SEQUENCING`; current owner
direction retires Hub maintenance, so no Hub files change.

## Scope

The producer's `solved-panel-export.v1` may carry per-candidate feasibility
verdicts settled under a named two-rung refinement rule. Its ID and verdicts
must be covered by the export digest. The neutral plain and indexed power
paths use these verdicts without changing task limits, reference quantities,
score contracts, or historical exports. An unsettled candidate matters only
when it could change a band's winner or feasible existence. A control pick of
such a candidate is unscored for that control on that question. Report only
aggregate unscored mass. Data Collection owns rung verification and the real
battery v3 export; Test Lead owns power interpretation. No solver, hidden bank,
AX42 data, spend, or LIVE work.

## Plan and evidence

1. Add a producer-only reference-resolution helper and optional sealed export
   fields while preserving the old export shape.
2. Apply the helper consistently to summaries, good/control judgments, and
   plain/indexed aggregate reports.
3. Toy-test digest binding, settled and decision-irrelevant unresolved cases,
   mandatory indexed failure, and an unresolved control pick.
4. Pin the helper in task freeze, document the export, run focused regression
   and canonical CI, then hand the exact PR head to PR Head.

The new field shape and its interpretation are an engineering interface
decision recorded in `.agent/decisions/2026-10-08-VALUE-COST-T3-SETTLEMENT-01.md`.
Completion is a green exact-head PR handoff, not scientific acceptance of any
real panel or power threshold.
