# C-01 — Durable execution state and queue

**Wave:** C1 real scientific execution foundations
**Status:** `in_progress`
**Depends on:** A7, B-GATE
**Selection:** `OWNER-C1-C2-BURGERS-01`; offline C1 engineering may proceed while
G2 remains NOT_READY. G2 still gates every network-readiness claim and dependent
chain run.
**Authority:** launch v1.0.3 C-01 as amended by v1.0.4–v1.0.6;
Build Out/overlay, existing A7/card/transcript owners and C-EA0–C-EA3.

## Goal and owning interfaces

Preserve the existing C-01 scope: durable submission/card/transcript state,
queue, crash recovery and idempotency. Reuse source-owned identities, A7 lifecycle,
A6 disclosures and current persistence. Define the concrete C1 execution design
needed by C-02 and C-EA0 without widening the declarative Strategy language,
creating a second result owner or inventing production custody/retention values.

## Definition of Done

- [x] Durable admission, queue ownership and bounded retry/recovery preserve each
      source submission, attempt and result association across restart.
- [x] Card/transcript projections retain existing privacy, version and lifecycle
      contracts; concurrent duplicate requests converge and conflicts fail closed.
- [x] Crash/restart/replay/concurrency tests cover dispatch and persistence seams;
      infrastructure failure stays distinct from scientific failure.
- [x] The C1 reconstruction/orchestration interfaces identify exact Strategy,
      resource/environment and protected-evaluation boundaries for C-02 onward.
- [x] C-EA0 capture/custody/retention/acknowledgement design dependencies are explicit;
      C-EA2 archive-before-finalization remains mandatory for required real results.

## Maturity and handoff

The implementation candidate is bounded to the private durable queue and exact
source-owned identities. Completion remains conditional on applicable acceptance
and normal expected-head merge. C-02's existing Definition of Done is unchanged. Production storage/custody,
retention, scientific values and qualification remain with their existing owners.
G2 is currently NOT_READY; no public-network, C2 eligibility, scientific
qualification, archive acknowledgement, or LIVE authority is inferred.

## C-01-D1 — Journal dispatch intent and reconcile ambiguity explicitly

Use one SQLite owner for private execution bindings and write dispatch intent before
external work. A restart moves `DISPATCHING` and `RUNNING` attempts to
`RECONCILIATION_REQUIRED`; an operator/worker must prove either `NOT_DISPATCHED` or
`RESUME_EXISTING`. Never mint a replacement attempt during reconciliation. A new
attempt is admissible only after the exact previous attempt records retryable
infrastructure failure and retains every scientific/environment binding. Store only
opaque result/card/transcript references, and hard-code the still-required C-EA2
archive acknowledgement instead of claiming finalization.
