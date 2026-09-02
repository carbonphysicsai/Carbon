# Ticket GOV-REVIEW-01 — manual Codex/GPT review governance

**Lane:** repository delivery governance; outside the active Wave-B implementation board
**Status:** `done` only after the conditional completion gate below
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`
**Exact base commit:** `938f94d3cf0ae8ff092b52659c39f0952ec352da`
**Exact base tree:** `ca050935b1b4881931d438e47a7a69a98bd5fcfa`
**Plan:** `.agent/plans/GOV-REVIEW-01_manual_gpt_review.md`
**Stable evidence:** `.agent/evidence/governance/gov-review-01.md`

This bounded governance migration ticket replaces the unavailable Greptile service
with exact-head manual Codex/GPT review evidence plus a distinct human approval.
It does not alter scientific authority, Wave-B scope, B-04 runtime semantics,
or any maturity claim.

## Owner-selected process

```text
coherent candidate + required validation
→ fresh read-only Codex/GPT review of the complete PR diff
→ closed-schema exact-head/tree review receipt
→ distinct non-author human APPROVED review carrying that receipt
→ protected GPT review gate
→ zero unresolved findings and review threads
→ normal expected-head merge
→ reviewed-tree and exact-main verification
```

Historical Greptile receipts remain immutable evidence of earlier deliveries.
Greptile is removed only from live and prospective authority, automation, and
required checks.

## Definition of Done

- [x] Record `GOV-REVIEW-01-D1` and the exact replacement contract.
- [x] Add a protected-base review validator and exact review-receipt template.
- [x] Version the main ruleset to require `Merge gate`, `GPT review gate`, one
      non-stale human approval, last-push approval, resolved threads, normal
      merge only, and no bypass actors.
- [x] Generalize guarded ruleset convergence for an open exact candidate or
      the exact checked main produced by a normally merged governance PR.
- [x] Reconcile live/prospective delivery authority and active/future ticket
      gates without rewriting historical review evidence.
- [ ] Obtain exact-head acceptance, a complete-diff Codex/GPT receipt, distinct
      human approval, normal merge, exact-main `Merge gate`, guarded ruleset
      convergence, and the completed normalized external receipt.

## One-time bootstrap boundary

The live ruleset was manually changed before stable authority landed: Greptile
is absent, but human approvals are still zero and no GPT review check is yet
required. Classify this as `MIGRATION_REQUIRED`. During this governance PR only:

1. keep deletion, non-fast-forward, strict-base, normal-merge, thread, and
   `Merge gate` protections active;
2. require the same structured exact-head Codex/GPT receipt and distinct human
   approval by delivery procedure before merge, even though the transitional
   live ruleset cannot yet enforce them;
3. merge normally with an expected-head guard only after those facts exist;
4. require exact-main `Merge gate`; and
5. converge and verify the versioned ruleset from exact checked main using this
   normally merged governance PR as the mutation guard.

No later PR may use this bootstrap exception.

## Must not

Do not add an OpenAI API key, automated model billing, a caller-selected review
mode, a self-approval path, a bypass actor, squash/rebase/auto-merge, a review
receipt detached from the exact head/tree, or any B-04/B-05/scientific/network
runtime behavior.

## Conditional completion gate

This ticket becomes `done` only after the exact reviewed candidate normally
merges, reviewed-tree equality and exact-main checks pass, the versioned live
ruleset is applied and verified, and the completed external receipt is posted.
B-04 remains the selected `in_progress` implementation ticket throughout.
