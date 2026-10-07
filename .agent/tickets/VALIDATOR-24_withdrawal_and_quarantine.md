# VALIDATOR-24: a signed batch withdrawal, and tranche quarantine

**Status:** design, then build. Security-sensitive (AGENTS.md §13): it
changes what validators score on after an incident. It needs a dedicated
review.

**Authority:**
- the Test Lead's ruling of 2026-10-07, closing the leak-incident runbook's
  two gaps (`/home/carbon/shared/operator/LEAK_INCIDENT_RUNBOOK.md`);
- OWNER-SHARED-ANSWER-KEY-01;
- OWNER-BANK-ARCHITECTURE-01;
- OWNER-AUTO-PUBLISH-RETIRED-01.

**Priority:** after bank slice 2 and the capacity model, and before
rehearsal 3a runs more than one validator.

**Executor:** the Carbon Validator session.

## Design

1. **The producer withdraws a batch window**
   (`producer withdraw --challenge C --fingerprint FP --reason CODE`).
   - It journals `withdrawn` (fingerprint, reason code, block) and moves the
     package out of the outbox into `producer/withdrawn/`, so the next push
     removes it from the distribution host.
   - It writes a **withdrawal notice**: a manifest signed with the producer
     key (`{schema, challenge_id, fingerprint, reason, block}`), in
     `outbox/<challenge>/withdrawals/`. The reason is a public code, never
     a case.
   - Idempotent. A withdrawn batch is never scheduled, published or
     reinstated. Its slot is not refilled late; the next slot proceeds as
     usual.
2. **The distribution host** verifies each notice against the pinned
   producer key and lists them beside the packages for permit holders
   (`withdrawals`). It never serves a package that a notice names.
3. **Validators** (`answer_key sync` and `import`) apply every verified
   notice before importing anything:
   - The named batch leaves the active windows at once. It is never
     scored on again, and never re-imported.
   - The withdrawal is journaled in the validator's own state.
   - It is typed: never a score, never a miner's fault.
4. **Scores already computed** on a withdrawn window stay in the record,
   marked withdrawn (invariant 10). They are **descriptive only: never
   ranked, nominated, promoted or weighted.** The ranking and the weights
   source skip any submission whose scoring windows include a withdrawn
   batch.
5. **`BankLedger.quarantine_tranche(tranche, slot, reason)`:**
   - The tranche stops being drawn at once: its state becomes
     `QUARANTINED`, outside the live set.
   - Each of its cases is retired into the release queue, recording the
     slot and the reason.
   - Its cases publish through the normal path, only after every window
     that drew them is revealed (OWNER-AUTO-PUBLISH-RETIRED-01).
   - The bank tops up as usual.
6. **The runbook** references both:
   - containment uses `producer withdraw`;
   - a leaked bank uses `quarantine_tranche`.

## Slices

1. Quarantine; the producer's withdraw and notice; the distribution host's
   listing and refusal; validator import stopping activation.
2. Excluding withdrawn-window scores from ranking and weights (the battery
   daemon's ranking, `hidden_score`, `winner_eligibility`).

## Tests

- A quarantined tranche is never drawn again. Its cases retire, and publish
  only after reveal.
- A withdrawal notice:
  - verifies against the producer key, and a tampered or foreign one is
    refused;
  - stops a held window at once, on every validator that syncs;
  - prevents re-import;
  - is idempotent.
- The distribution host never serves a withdrawn package.
- A submission scored on a withdrawn window is never ranked or weighted, and
  its record keeps its score, marked withdrawn.

## Out of scope

- Choosing when to withdraw (the owner, per incident).
- Notifying miners (the runbook).

## Maturity ceiling

IMPLEMENTED and TESTED. Not SECURITY_QUALIFIED. No LIVE authority.
