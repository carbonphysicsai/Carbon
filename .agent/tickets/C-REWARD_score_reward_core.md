# C-REWARD — Bounded-linear development reward core

**Wave:** C0 network foundation
**Status:** `done`
**Depends on:** NET-3
**Primary Hub map_ref:** `WAVE-C/C-REWARD`
**Evidence:** `.agent/evidence/wave_c/c-reward.md`
**Starting main:** d55fdeb4d9be6f25f963eac0ed608414dbf0b4e6 (PR #122).
**Authority:** OWNER-C0-REWARD-01, OWNER-C0-VALIDATION-01; Scoring/A6 owners;
launch v1.0.6 and DELIVERY_PROTOCOL. This is DEVELOPMENT policy, not live economics.

## Working contract and dependency plan

KEEP A5 binary64 scientific comparison and score bytes, NET-3 resolved accepted
fixture records, A6 disclosure ownership, NET-1 finalized snapshots and NET-2
journal transactions. Add carbon/rewards pure arithmetic, registered contracts,
closed batches, checkpointed ledger and projections; add an A6-owned versioned
fixture scorecard projection. SDK signing stays in NET-4B. Treasury stays absent.

1. Implement pure bounded-linear Q12 floor/remainder arithmetic and golden cases.
2. Register immutable challenge/baseline/upper/allocation/evaluation/funding terms;
   adapt journal-resolved accepted records and finalized-chain time, close full
   admitted batches, persist provenance and bounded restart/replay work.
3. Aggregate independent challenge targets before UID mapping; implement burn-only
   complete accounting, unusable-winner withholding, optional disabled reserve seam.
4. Add opening-anchored weekly healthy 72-hour review and A6 allow-listed aliases,
   coefficients before competition, accepted combined/aggregate scores afterward.
5. Test adversarial and integration cases; reconcile roadmap/Hub; focused canonical
   acceptance and expected-head merge. NET-4A is next after accepted delivery.

## Definition of Done

- [x] Opening credit is zero. Strict accepted record gains contribute
      (new_record - previous_record)/(U - S0), with S0 < U. Existing scientific
      comparison precedes reward arithmetic. No cap, opening gift or loser floor.
- [x] Immutable finalized activation gives 24-hour half-life. Current holder gets
      all current earned target; self-improvement adds gain; takeover transfers it;
      ties retain incumbents; a closed batch selects best once, receipt-order ties.
- [x] Registered real parameters are never inferred. C0 fixtures have explicit
      baseline evidence and immutable version, upper/allocation/funding windows.
      New versions start with their own accepted baseline and no free old credit.
- [x] Exact replay is idempotent, conflicts/stale time fail, artifact/wallet changes
      cannot renew credit. Persist record, credit age and provenance with indexed
      replay and checkpoint recovery, without scanning all historical events.
- [x] Challenges stay independent; shared hotkeys aggregate before UID mapping.
      Preserve all unearned and unused allocation as burn. Missing/disqualified/
      contested winners receive zero new target; never promote a worse result.
- [x] Publish admission, evaluation, cutoff and funding terms. Preserve admitted
      pending processing and funding commitments; no retirement while pending.
      An alert or local publisher expiry does not erase chain state or promise pay.
- [x] Weekly review is opening anchored; preceding complete healthy 72-hour earned/
      allocated strictly below 10% alerts. Missing/duplicate/unhealthy/zero windows
      are indeterminate. Tiny gains and routing changes never reset the schedule.
- [x] A6 versioned allow-list publishes registered physics/robustness/accuracy
      coefficients and actual geometric formula before competition; accepted
      combined/aggregate scores afterward. Use aliases, bounded cadence/accounting,
      three-decimal DEVELOPMENT display; no hidden cases/seeds/margins/credentials.
- [x] Golden cases cover no winner, ties, self-improvement, takeover, batch order,
      copies/wallet resets, exact/conflicting replay, shared winner, allocation
      changes, restart/stale time, .8/1/.99 => .95/.475/.007421875 at 0/1/7 days.
      Preserve withholding, tiny-gain and coordinated-identity counterexamples.
- [x] Treasury interface is disabled with separate follow-up. No reserve deployment,
      liability forgiveness, cap guarantee, automatic jackpot or cross-challenge spend.
- [x] Meaningful pure/adapter/disclosure/invariant tests and one applicable canonical
      acceptance pass. No localnet, real science, strategy-proofness or LIVE claim.

## C-REWARD-D1 — Arithmetic and authority boundary

Use exact binary64 comparison for current A5 fixture semantics and retain float.hex
bytes in accepted provenance. For target arithmetic project each binary64 through
its canonical shortest round-trip decimal string, then use Decimal precision 80,
Q12 floor and unearned remainder. This matches the provided analytical vectors
without using three-decimal public values. Queries never mutate credit anchors.
An absolute-gain checkpoint advances only on accepted improvement; provenance is
append-only/indexed. A reward service obtains finalized time from its ChainAdapter;
callers cannot refresh credit with timestamps. Fixture accepted records cannot
construct real scientific or network authority.

Alternatives rejected: synthetic accepted Boolean as trust root, public rounded
score comparison, repeated event-log reconstruction, caller timestamps, or SDK
signing inside the reward engine. These would weaken ownership, identity or
recovery. New private schemas are versioned and reversible; supersede this section,
carbon/rewards and A6 development scorecard for a migration. A future qualified
scientific comparator/uncertainty contract remains human/science owned; no real
parameters are selected. NET-4A/4B consume complete projections with exact provenance.

Finite range and zero opening credit bound constant-allocation lifetime target by
1/ln(2) days (~1.443). This is not guaranteed receipts, fiat value, strategy-proofness
or evidence of participation. Delaying and drip-feeding improvements can change
incentives; tests and the operator documentation retain those counterexamples.

Hub impact: map_structural; WAVE-C/C-REWARD primary, NET-3, CI, maturity, A6 and
sequencing affected. Owner notification is asynchronous, not an approval gate.

## Accepted delivery

PR #123 passed run 34416168621 (1,793 focused CPU, 176 invariants, package,
quality, Hub and Merge gate) and normally merged as
505f08cde173eab197aa397a09536bb6bf576065. Completion:
https://github.com/carbonphysicsai/Carbon/pull/123#issuecomment-5610094123.
Bounded DEVELOPMENT implementation/test maturity only. NET-4A is next.
