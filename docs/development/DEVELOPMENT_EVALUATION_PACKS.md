# DEVELOPMENT evaluation packs

This runbook describes C-EP1's fixture-only Variant-A lifecycle. It is an
implementation contract, not CPES production policy.

## Identity and API behavior

`CandidateRef` remains the job identity and existing deduplication boundary.
`EvaluationPackIdentity` is a private child of the unchanged
`FixtureEvaluationContext`; it does not alter Strategy hashes, Challenge
versions, receipts, hotkeys, or reward identity. The child identity is bound
before A4 fixture acquisition and occupies A4's existing `EvaluationBinding`
slot. The later materialization manifest binds the candidate artifact,
submission/attempt, generator, score pack, environment, DEVELOPMENT policy,
and evaluation-binding digest.

The supported interaction is:

1. submit one immutable Strategy through NET-2/NET-3 and retain its receipt;
2. query `DevelopmentEvaluationPackService.status(CandidateRef)`;
3. allow the nominal local fixture composition to assign and execute the job;
4. read the A6 `EvaluationCard` through `read_summary` only after state
   `SUMMARY_DELIVERED`.

The status view omits pack identity, case-selection identity, seed material,
lineage, Strategy bytes, artifact references, scores, and result bytes. No
sharing, reevaluation, replica-expansion, answer-key, production-admission, or
authority-flag method exists.

## Persistence and linearization

The receipt SQLite database owns four additive v1 tables: schema metadata, one
candidate-to-pack row, immutable attempt-manifest history, and an append-only
event/timing table. Its migration text has a retained digest. Linearization
points are:

- assignment: insert the pack row and reserve `candidate_v1` in one transaction;
- attempt binding: persist the immutable materialization manifest before C-01 admission;
- dispatch: C-01 atomically records `DISPATCHING` and the claim;
- result: C-01 records immutable private result references, then the pack ledger
  seals the A6 projection as `RESULT_RECORDED`;
- closure: the ledger verifies the exact C-01 attempt is `RESULT_RECORDED`, then
  marks the candidate/pack closed;
- incomplete closure: the ledger requires the exact C-01 attempt to hold a
  terminal failure/cancellation state and seals no summary;
- summary dispatch: `CLOSED -> SUMMARY_DELIVERED` commits before the card is
  returned, so a lost response replays the same bytes.

A second C-01 worker uses `DurableExecutionQueue.attach`; attachment performs no
recovery sweep. Reconstructing the authoritative owner uses the normal
constructor and moves ambiguous `DISPATCHING`/`RUNNING` work to
`RECONCILIATION_REQUIRED`. Reconciliation never silently redraws. The existing
successor-attempt rule remains the only retry authority. A retryable A8 outcome
first passes through A7's budget; if A7 queues a successor, C-01 requires the
prior attempt to be `RETRYABLE_INFRA` and accepts only the next attempt with
byte-identical scientific/environment bindings. The pack ledger retains both
manifests under one pack.

No transaction spans the receipt database, C-01 database, and process-local A6
store. The durable result and summary intents make the supported post-result
seams replayable. A crash earlier in A7/A8 remains explicit reconciliation;
C-EP1 does not pretend process-local A7 state is durable.

## Operations and rollback

Use disposable fixture databases only. Capacity is bounded at 10,000 packs and
does not establish throughput. Opening the ledger validates schema, migration,
binding, materialization, event, and summary digests without mutating live work.
Corrupt or unknown state fails closed.

Rollback means stop constructing `DevelopmentEvaluationPackService`. Do not
drop the additive tables if any pack was assigned. Older code may continue to
read legacy candidates but cannot interpret new pack states; downgrade is
therefore unsupported after C-EP1 activity. No retention period or production
cleanup default is introduced.

## Requirement-to-test matrix

| Req. | Focused evidence |
|---|---|
| 1 | `test_distinct_jobs_get_distinct_child_packs_and_fixture_material` |
| 2, 6 | `test_copy_lost_response_repeated_read_and_restart_reuse_one_pack`; NET-3 copy tests |
| 3 | `test_independent_connections_race_to_one_assignment`; C-01 claim race tests |
| 4, 5, 11 | wrong-pack and mutated-materialization tests; NET-3 context/artifact tests |
| 7, 8 | assignment/reconciliation, worker-attach, result/closure crash tests; C-01 restart tests |
| 9 | C-01 retry-continuity and stale-claim tests |
| 10 | nominal policy fixes one obligation; no replica-admission API exists |
| 12 | preclosure read and premature-close tests; legacy A7 publication tests |
| 13 | incomplete fixture tests plus NET-3/C-01 typed failure tests |
| 14, 15 | late-close/result conflict and both summary crash-window tests |
| 16 | corrupt/forged state and unsupported-schema tests |
| 17 | legacy upgrade/no-backfill plus unchanged NET-3 identities |
| 18 | per-row transactions and bounded capacity; no global pack barrier exists |
| 19 | legacy acceptance/reward exclusion and fixture-only scope assertions |
| 20 | structural absence test for B/C, answers, production, and authority flags |

The focused tests coordinate independent SQLite connections rather than using
sleeps. Existing C-01 tests cover lock/claim conflicts, partial/result conflicts,
restart ambiguity, retry successors, stale claims, corrupt storage, and typed
terminal outcomes.

## Measurement boundary

The private event table records counts and local transaction elapsed time for
assignment, attempt binding, the aggregate A8 fixture call, result sealing,
closure, summary dispatch, and reconciliation. C-01 separately records
admission, dispatch, partial evidence, result, retry, and reconciliation events.
A8's current public fixture interface
returns only a completed result or typed failure; it does not expose trustworthy
separate acquisition/reference/prediction/measurement timestamps. C-EP1 does
not fabricate those subdivisions. The owner report therefore labels the local
fixture run as an end-to-end fixture timing and the ledger events as ledger
overhead, not a scientific exam or capacity forecast.

## Fail-closed exclusions

The path cannot use `REAL_PATH_NON_LIVE`, official entropy, protected customer
cases, C-EA1 acknowledgements, C-EA2 finalization, network publication, reward
adapters, answer archives, or public diagnostics. Privileged-host integrity,
independent execution audit, production provider/event/finality, real custody,
rights, lineage, freshness, and statistical comparability remain unresolved.
Different fixture pack identities demonstrate binding separation and replay,
not independent physical draws or future-case novelty.
