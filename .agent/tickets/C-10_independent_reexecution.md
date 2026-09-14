# C-10 — Independent re-execution and disagreement

**Wave:** C1 real scientific execution foundations
**Status:** `in_progress`
**Status scope:** one bounded public-data DEVELOPMENT slice
**Selected slice:** linked fresh C-07 execution, exact-byte observation,
disagreement journal and fail-closed quarantine
**Selection authority:** repository-owner continuation after merged PR #168;
implemented by `C-10-D1`
**Primary Hub map_ref:** `WAVE-C/C-10`
**Depends on:** C-06, C-07

## Goal

Implement independent re-execution, disagreement records, quarantine, and contested non-settlement.

## Definition of Done

- [x] Bind primary and independent attempts to the same exact candidate, case, policies, allowed resources, and comparison policy while recording material shared dependencies.
- [x] Agreement strengthens evidence only when the prospective policy says it can; source count or majority vote creates no authority.
- [x] Reference, evaluator, receipt, or reconstruction disagreement produces a typed contested record and quarantines the affected result.
- [x] Contested, incomplete, unavailable, or mismatched evidence cannot finalize, settle, publish a winner, or update weights.
- [x] Deterministic fault and replay tests cover agreement, disagreement, timeout, stale evidence, missing artifacts, and recovery.

Exact-head Linux service acceptance and normal merge remain pending before this
bounded slice earns `TESTED` status.

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
- Exact scientific-state byte agreement is DEVELOPMENT reproducibility evidence
  only. Different bytes have no invented tolerance and remain unresolved.
- Disagreement, missing/revoked evidence, failure, cancellation, unavailable
  execution and reconciliation are distinct durable outcomes. Required cases
  quarantine the affected result without producing an official, winner,
  publication, archive, network, weight, reward or settlement effect.
- Re-execution consumes a prospectively frozen additional budget under the
  existing C-03 profile. It never resets the primary budget, grants a miner
  retry, or authorizes automatic replacement.
