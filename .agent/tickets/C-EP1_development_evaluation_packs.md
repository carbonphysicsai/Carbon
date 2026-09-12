# C-EP1 — DEVELOPMENT evaluation-pack lifecycle

**Wave:** C1 development evaluation foundations  
**Status:** `in_progress`  
**Selection authority:** repository-owner Codex task linked from issue #142  
**Depends on:** NET-3, C-01, A4 fixture entropy, A5, A6, A7, A8  
**Primary Hub map_ref:** `WAVE-C/C-EP1`  
**Evidence:** `.agent/evidence/wave_c/c-ep1.md`  
**Gauntlet:** local evidence ZIP SHA-256
`088d3e1182cbd8974c14ba6614a470cdcf3d5f3e6335c1db085699789ec5ffcb`

## Goal and boundary

Add the smallest durable Variant-A child pack lifecycle for one separately
admitted fixture evaluation job. Preserve the existing Strategy/candidate,
Challenge context, receipt ordering, A5 scoring, A6 disclosure, C-01 retry,
archive, and reward owners. The miner receives the existing immutable
submission receipt/status and may read the existing permitted fixture card only
after its pack closes.

This ticket does not implement CPES-1 wholesale. Sharing, intentional waits,
answer publication, real/provider entropy, `REAL_PATH_NON_LIVE`, production,
network, frontier, reward, qualification, and an operating-policy optimizer are
structurally absent. C-EA2 remains required for every applicable real result;
C-EA1 `INTERNAL_AUDIT` acknowledgement is not accepted here.

## C-EP1-D1 — identity, ownership, and transitions

KEEP `CandidateRef` as the evaluation entitlement: one parent context plus one
canonical Strategy hash, independent of hotkey copies and transport retries.
WRAP it with `EvaluationPackIdentity`, whose pre-draw digest binds the unchanged
parent `FixtureEvaluationContext`, the exact nominal DEVELOPMENT policy, a
fixture case-selection identity, and an owner-generated allocation nonce.
Membership associates the candidate later; candidate bytes, hotkey, receipt
order, and retry count are not pack-generation inputs. The pack identity fills
the existing A4 `EvaluationBinding` slot and therefore reaches actual fixture
seed derivation without altering A4 roles or provider types.

The additive tables live in NET-3's receipt SQLite owner. The legal success path
is `ASSIGNED -> ATTEMPT_BOUND -> RESULT_RECORDED -> CLOSED ->
SUMMARY_DELIVERED`. Ambiguous work moves explicitly to
`RECONCILIATION_REQUIRED`; incomplete work closes without a summary. Assignment
and candidate-state reservation are one receipt-database transaction. C-01
owns dispatch intent, partial evidence, retry continuity, result references,
and restart reconciliation. A6 records the private card while A7 remains
`SCORED`; the pack ledger stores its sealed projection, verifies C-01's bound
attempt is durably `RESULT_RECORDED`, closes, and only then dispatches that
projection idempotently.

Incomplete closure is not a caller assertion: the ledger requires the exact
bound C-01 attempt to be durably `FAILED_INFRA`, `FAILED_STRATEGY`, or
`CANCELLED`. Retryable or ambiguous work remains open to its existing owner.
An A7-authorized retry creates a C-01 successor attempt and a new immutable
attempt-manifest row under the same pack; the A4 seed and environment pins stay
byte-identical and no new pack or draw is allocated.

No cross-database atomicity is claimed. A crash after C-01 result recording but
before pack closure resumes closure from the retained association. A crash
before the result is durable requires reconciliation and never allocates a new
pack. Duplicate execution can still occur outside the supported single-owner
local topology after an ambiguous external dispatch, but stale claims and
conflicting result bytes cannot create a second accepted effect or draw.

The schema is additive and checksum-pinned. Existing candidate rows receive no
pack backfill and retain their identity/state until explicitly admitted to this
path. Downgrade after pack rows exist is unsupported; an unknown schema or
migration digest fails closed. Rollback can disable new C-EP1 admission but must
retain the new tables as incident/history evidence.

## Definition of Done

- [ ] One unchanged parent context supports distinct, durable per-job child packs.
- [ ] Copies, retries, restarts, races, and repeated reads cannot allocate another pack.
- [ ] The materialization manifest binds exact candidate, pack, attempt, A4 slot,
      generator, score, environment, and policy identities and detects mutation.
- [ ] C-01-confirmed closure gates one idempotent A6 fixture summary; no earlier
      public card or legacy accepted fixture projection exists on this path.
- [ ] Legacy NET-3/C-01/A7/A8/reward behavior and golden identities pass.
- [ ] Required fault, migration, negative-control, and no-authority tests pass.
- [ ] A reproducible local baseline and all 30 gauntlet attack dispositions are recorded.
- [ ] Applicable canonical acceptance and Merge gate pass at the expected PR head.

## Handoff ceiling

Completion earns bounded DEVELOPMENT implementation/test maturity only. It is
not scientific, security, archive, network, commercial, production, or LIVE
qualification. Variant B requires a separately selected measurement ticket and
actual phase-level evidence/cost instrumentation; it is not activated here.
