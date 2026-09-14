# C-07 durable non-official DEVELOPMENT orchestration

**Decision:** `OWNER-C1-BURGERS-ALPHA-01`, implemented by `C-07-D1`
**Status:** implementation candidate; exact-head acceptance pending
**Base:** C-06 PR #161 merge
`0c00350b98b9a0062006f5bd2ce50c20aff37b3c`
**Primary Hub map_ref:** `WAVE-C/C-07`

## Scope and ownership

Compose C-01's exact durable attempt/claim/partial/result association with
C-06's signed DEVELOPMENT receipt. The composition accepts only exact
source-owned reconstruction, prediction, reference and measurement result
types. It records their immutable identities and dispositions; it does not
implement their algorithms, create a ScoreInput, define a scientific limit,
acknowledge an archive, publish to a network or settle a reward.

## Fixed implementation

1. One C-07 request cross-binds the C-01 attempt to C-06 evidence plus a bounded
   public case manifest and exact reference/measurement request digests.
2. Exactly three complete reconstruction receipts must match one prospectively
   frozen repeat plan, immutable TRAIN commitment, plan, resource policy and
   Challenge. The aggregate retains all three in plan order and never selects a
   best replica.
3. Stage transitions reuse C-01's durable partial journal in the fixed order:
   frozen generator/case manifest, reconstruction, target-free prediction,
   reference, measurement, unresolved score disposition and receipt. Archive
   remains explicitly unavailable. Generator failure retains its own stage and
   is never rewritten as reconstruction failure.
4. Restart requires explicit `RESUME_EXISTING` reconciliation of the same claim;
   a completed result can be reattached only for exact idempotent replay.
   Receipt append followed by caller loss converges on the same C-06 ledger row
   and C-01 result association.
5. Generator, reconstruction, reference, measurement, infrastructure,
   cancellation, contested and indeterminate terminals produce a complete
   operational account without a completion receipt. Public and reviewer
   projections are positive allow-lists with every eligibility field false.
6. The owner command `./scripts/dev/c07_development_vertical.sh` runs three
   frozen lab replicas, target-free inference and separate isolated reference/
   measurement workers, then writes private, reviewer and public reports using
   an externally generated ephemeral DEVELOPMENT key.

## Acceptance and stop boundary

Focused tests cover cross-binding, exact types, ordering, every terminal
disposition, replay, restart, interrupted receipt association, changed evidence
and authority-upgrade denial. The required C-03/C-04/C-05/C-07 service lane
must execute the actual Docker path on Linux x86-64. The single service smoke is
public synthetic engineering evidence, not the frozen twelve-case scientific
campaign or evidence that three replicas are scientifically sufficient.

This slice can earn `SPECIFIED`, `IMPLEMENTED` and `TESTED` only. Official or
protected admission, qualified reference/measurement/scoring, independent
security acceptance, real signer/custody, real C-EA2 acknowledgement, testnet,
reward, production and LIVE authority remain absent.
