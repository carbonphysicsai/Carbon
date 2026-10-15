# OPT-11 — Phase 4 model-call reconciliation

**Status:** working contract, DEVELOPMENT only. **Authority:** optimizer queue
OPT-11 and Graphite B20. **Starting main:**
`a1e259d392653a78e5986743848a48a54b6d9339`. **Map ref:**
`WAVE-C/OPT-11`; bounded operator repair leaves the Development Hub's
purpose, placement, maturity and primary links unchanged. The current
`.agent/DELIVERY_PROTOCOL.md` retires Hub maintenance; no Hub output is edited.

## Scope and decisions

KEEP the research ledger's provider-call lease, reservation, single booking,
and `FAILED_INFRA` semantics. WRAP its explicit uncertain-call settlement in
`phase4 reconcile --root DIR --session N`. It reads only the named local
session, never dispatches a model or pod, and uses a retained provider charge
only when that call's response supplies one within its reservation. Otherwise
it books the full reservation and states the basis. It never infers a zero
charge from a missing usage record.

A crashed session that has not been terminalized may resume under its
existing session number after every uncertain call is settled. If a previous
resume already wrote terminal `reconciliation_required`, preserve that
historical export and append a reconciliation supplement with typed
`FAILED_INFRA`; no scientific result is produced. This does not reclaim an
already consumed grant slot or create spending authority.

## Plan and conditional completion

1. Add the narrow opt-in settlement basis to the existing research-agent
reconcile path, preserving its current default for other callers.
2. Add a private, idempotent Phase 4 command and a typed terminal supplement.
3. Toy crash-point and negative-control tests: exact once charge, no resend,
   unresolved refusal, resumed session or typed closed failure. Run focused
   tests, lint and canonical CI, then exact-head PR handoff.

**Baseline:** on this exact main, `test_graphite_phase4_model.py` and
`test_graphite_phase4_grant.py` produced 27 pass, 2 fail in unrelated prelive
path `session_model_ledger_controller` (missing row). Do not weaken those tests.
**Maturity ceiling:** implemented/tested development recovery only; no live
Graphite run, spend, security or scientific qualification.
