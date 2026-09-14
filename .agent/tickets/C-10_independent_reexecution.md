# C-10 — Independent re-execution and disagreement

**Wave:** C1 real scientific execution foundations
**Status:** `done` in the bounded public-data DEVELOPMENT slice; broader
scientific/independence/security qualification remains open
**Status scope:** one bounded public-data DEVELOPMENT slice
**Selected slice:** linked fresh C-07 execution, exact-byte observation,
disagreement journal and fail-closed quarantine
**Selection authority:** repository-owner continuation after merged PR #168;
implemented by `C-10-D1`
**Primary Hub map_ref:** `WAVE-C/C-10`
**Depends on:** C-06, C-07
**Delivery:** accepted head
`82073ae2d5cc8504b7e77a9824642f98f0827526` passed required run
`34882900413`; PR #173 normally merged as
`d7ef7270eeb3b9a5594704efe0876ff3fb5ded49`

## Goal

Implement independent re-execution, disagreement records, quarantine, and contested non-settlement.

## Definition of Done

- [x] Bind primary and independent attempts to the same exact candidate, case, policies, allowed resources, and comparison policy while recording material shared dependencies.
- [x] Agreement strengthens evidence only when the prospective policy says it can; source count or majority vote creates no authority.
- [x] Reference, evaluator, receipt, or reconstruction disagreement produces a typed contested record and quarantines the affected result.
- [x] Contested, incomplete, unavailable, or mismatched evidence cannot finalize, settle, publish a winner, or update weights.
- [x] Deterministic fault and replay tests cover agreement, disagreement, timeout, stale evidence, missing artifacts, and recovery.

Exact-head Linux service acceptance ran 17 actual service cases in 383.00s and
the full required acceptance passed before the normal merge. This earns
`SPECIFIED / IMPLEMENTED / TESTED` only for the bounded DEVELOPMENT slice.

## Authority ceiling

Verification engineering only. Resolution thresholds and final scientific/economic decisions remain human-owned.

## Selected DEVELOPMENT contract

- C-01 remains the only attempt, claim, restart and result owner; C-07 remains
  the only numerical orchestration owner; C-06 remains the only receipt,
  signer and evidence-ledger owner.
- One audit request links an exact retained primary result to a different C-07
  execution identity, fresh isolated workers and separate scratch. It preserves
  the same three registered reconstruction slots and randomness roles without
  treating the audit as a fourth scientific-stability replica.
- Material commitments must match before dispatch. Execution/container/
  location identities must differ and material shared dependencies remain
  disclosed.
- Launch intent and the C-01 claim are durable before dispatch; actual C-07
  evidence bytes bind afterward to the same intent and claim. Exact checkpoint,
  prediction, reference and measurement byte agreement is DEVELOPMENT
  reproducibility evidence only. Whole artifact envelopes retain their own
  execution/timing provenance and are not misclassified as scientific state.
  Different scientific bytes have no invented tolerance and remain unresolved.
- Disagreement, missing/revoked evidence, failure, cancellation, unavailable
  execution and reconciliation are distinct durable outcomes. Required cases
  quarantine the affected result without producing an official, winner,
  publication, archive, network, weight, reward or settlement effect.
- Re-execution consumes a prospectively frozen additional budget under the
  existing C-03 profile. It never resets the primary budget, grants a miner
  retry, or authorizes automatic replacement.
