# C-01 — Durable execution state and queue

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; unselected and unstarted
**Depends on:** A7, B-GATE; C1 selection follows the G2 disposition.
**Authority:** launch v1.0.3 C-01 as amended by v1.0.4–v1.0.6;
Build Out/overlay, existing A7/card/transcript owners and C-EA0–C-EA3.

## Goal and owning interfaces

Preserve the existing C-01 scope: durable submission/card/transcript state,
queue, crash recovery and idempotency. Reuse source-owned identities, A7 lifecycle,
A6 disclosures and current persistence. Define the concrete C1 execution design
needed by C-02 and C-EA0 without widening the declarative Strategy language,
creating a second result owner or inventing production custody/retention values.

## Definition of Done

- [ ] Durable admission, queue ownership and bounded retry/recovery preserve each
      source submission, attempt and result association across restart.
- [ ] Card/transcript projections retain existing privacy, version and lifecycle
      contracts; concurrent duplicate requests converge and conflicts fail closed.
- [ ] Crash/restart/replay/concurrency tests cover dispatch and persistence seams;
      infrastructure failure stays distinct from scientific failure.
- [ ] The C1 reconstruction/orchestration interfaces identify exact Strategy,
      resource/environment and protected-evaluation boundaries for C-02 onward.
- [ ] C-EA0 capture/custody/retention/acknowledgement design dependencies are explicit;
      C-EA2 archive-before-finalization remains mandatory for required real results.

## Maturity and handoff

This is a concrete future handoff, not a selected implementation or earned DoD.
C-02's existing Definition of Done is unchanged. Production storage/custody,
retention, scientific values and qualification remain with their existing owners.
G2 is currently NOT_READY; no C1 runtime or scientific authority is inferred.
