# C-EP2 — Variant-A measurement and offline Variant-B decision

**Wave:** C1 development evaluation foundations
**Status:** `in_progress`
**Delivery:** study complete; automated acceptance pending
**Selection authority:** repository-owner C-EP2 assignment following merged PR #143
**Depends on:** C-EP1
**Primary Hub map_ref:** `WAVE-C/C-EP2`
**Evidence:** `.agent/evidence/wave_c/c-ep2.md`

## Goal

Measure the implemented C-EP1 Variant-A fixture path with a bounded private
development harness, validate non-interference and accounting, and replay a
small frozen set of hypothetical zero-fill-wait Variant-B scenarios offline.
Deliver one evidence-based recommendation without implementing sharing.

## Boundary

The A8 backend is a deterministic scalar stub that executes no Strategy and no
physics. The study may observe DEVELOPMENT orchestration, persistence, fixture,
closure, disclosure, retries and reconciliation. It may not call those values
training, inference, physical cases, reference generation, CFD, protected
comparisons, or throughput. Missing real reconstruction/reference/workload
evidence remains unknown.

No pack membership, singleton restriction, A4 semantics, public API, reward,
accepted-record, production, archive, answer, network, or finalization behavior
is widened. Variant B remains a detached counterfactual only.

## C-EP2-D1 — observation and accounting boundary

KEEP C-EP1 runtime semantics. Add a closed development-study module and CLI
harness around existing interfaces. Diagnostic recording is best-effort and
cannot mutate lifecycle state. Root call wall/process spans are chargeable;
nested pre-commit ledger event timings are retained separately and never added
as independent durable transaction costs. Trace validation rejects invalid
units, nonfinite values, clock discontinuity, missing-span contradictions and
unknown values disguised as zero. Public evidence contains only fixture-safe
aggregate or opaque study associations, never seeds, pack identities, Strategy
bytes, private results, or raw evidence.

## C-EP2-D2 — exact C-01 claim repair

REPAIR the observed queued-work mismatch at its C-01 owner: add an atomic exact
attempt claim that preserves `claim_next` compatibility and use it from C-EP1.
The previous composition could claim the oldest unrelated queued job and then
reject after the dispatch-intent side effect. The exact claim admits no new
work, sharing or scheduler; it only lets an owner claim the binding it already
persisted. Focused tests must reproduce the old interleaving and prove the
unrelated job remains queued while the intended job proceeds.

## C-EP2-D3 — detached replay semantics

The replay consumes closed study/scenario records only. It groups no more than
the declared bound, only at a dispatch opportunity, only from jobs already
admitted and explicitly compatible, with zero fill wait and no future
information. Candidate/reconstruction work remains per member; only explicitly
modeled reference work is per hypothetical group. Shared-pack summaries wait
for the last terminal member; unresolved members remain unfinished. Unknown B
overhead yields only an explicit zero-overhead counterfactual; actual B work,
eligibility and release times remain unknown. Numeric overhead scenarios
recompute endogenous grouping and support only assumption-conditioned model
results. A fixed-membership break-even quantity must name that assumption and
is not a bound on the dynamic policy.

## Definition of Done

- [x] C-EP1 completion and C-EP2 selection records are reconciled.
- [x] Frozen protocol/config and observation map distinguish observed
      execution, optional public numerical probe, and counterfactual model.
- [x] Executable harness records repeated cold/warm, duplicate/replay,
      mandatory-failure, infrastructure-failure/retry, restart, closure and
      summary-replay observations against disposable persistent stores.
- [x] Observation parity, privacy, validation, overhead and sink-failure tests pass.
- [x] The queued-work exact-claim defect has a failing reproduction and narrow
      C-01-owned repair with regression evidence.
- [x] Detached replay/accounting tests cover singleton equivalence, no future
      information, compatibility, underfill, finite resources, closure delay,
      unknown overhead and no double charging.
- [x] Replay v2 reproduces the endogenous-grouping counterexample, rejects
      contradictory grouped reference requirements, and never promotes a
      numeric synthetic input to empirical support; frozen v1 evidence remains
      retained with its reporting labels superseded.
- [x] Raw fixture-safe traces, aggregate accounting, profiler summary and owner
      report state all missing physical/reference/workload evidence.
- [x] No Variant B/C runtime, sharing, wait, early summary, public answer,
      production, reward or real-finalization route exists.
- [ ] Applicable automated acceptance and Merge gate pass at the expected head.

## Required final recommendation

Choose exactly one: `KEEP VARIANT A`, `REQUEST A B-SPECIFIC DEVELOPMENT
EXPERIMENT`, or `COLLECT MISSING INPUTS FIRST`. A future experiment
recommendation is not implementation authority. Stop after this study.

## Maturity ceiling

C-EP2 may earn bounded DEVELOPMENT `SPECIFIED`, `IMPLEMENTED`, and `TESTED`
for its measurement/replay tooling. It cannot earn scientific, reference,
security, archive, network, reward, production, LIVE, or Variant-B-runtime
qualification.
