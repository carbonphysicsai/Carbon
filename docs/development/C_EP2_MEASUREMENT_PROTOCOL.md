# C-EP2 DEVELOPMENT measurement protocol

**Protocol:** `carbon.c-ep2.measurement-protocol.v1`
**Frozen configuration:** `.agent/preregistrations/C-EP2_measurement_study_v1.json`
**Source baseline:** merge `d783c2c7209c7eea2d46dd395c4eaaf8094a9e71`
with accepted C-EP1 parent `e0fbb6208cf0bf95910d51e7a3c996b09387a14e`
**Primary map_ref:** `WAVE-C/C-EP2`

This is a bounded DEVELOPMENT study protocol, not production policy or an exam
qualification. Variant A is the only executable evaluation policy. Variant B
exists only in the detached replay.

## Decisions and hypotheses

The study asks whether already-admitted compatible jobs on one validator could
avoid enough repeated reference work to justify a separately authorized
Variant-B DEVELOPMENT experiment without unacceptable closure delay.

- H1: C-EP1's observable orchestration/persistence costs can be measured
  repeatably without changing identities, result bytes, retry/deduplication,
  closure, disclosure, or reward exclusion.
- H2: zero-fill-wait grouping can save modeled recurring reference work only
  when compatible jobs are already queued, and the opportunity shrinks under
  sparse/incompatible demand.
- H3: shared-pack closure increases some completed members' feedback latency
  when member durations differ or a member is unresolved.
- Alternative: no credible B decision is possible because the current A8 stub
  contains no observed physical reconstruction/reference/inference work and B
  overhead/workload compatibility remain unknown.

The final choice is one of `KEEP VARIANT A`, `REQUEST A B-SPECIFIC DEVELOPMENT
EXPERIMENT`, or `COLLECT MISSING INPUTS FIRST`. No post-hoc threshold selects a
preferred result.

## Observation map

| Source / owner | Operation | Boundary and clocks | Unit/count | Evidence | Limitation |
|---|---|---|---|---|---|
| NET-3 `CandidateJournal.commit` | receipt-to-candidate admission/dedup | completed call; `perf_counter_ns`, `process_time_ns` | wall/process ns; request | observed DEVELOPMENT execution | authentication fixture only |
| C-EP1 ledger constructor | DB open/schema verification | completed constructor | wall/process ns; open | observed DEVELOPMENT execution | disposable local SQLite |
| `DevelopmentEvaluationPackService.evaluate` | complete singleton lifecycle | completed/raised call | wall/process ns; job | observed DEVELOPMENT execution | aggregate fixture orchestration, not physics |
| C-EP1 event rows | assignment, attempt bind, aggregate A8 call, result, closure, summary | owner-recorded internal elapsed field | ns; event | observed DEVELOPMENT execution | event time stops before its final INSERT/commit; not separately chargeable |
| C-01 event/state rows | admit, exact claim/dispatch, running, partial, result, retry/reconciliation | durable state/event inspection after call | counts/states | observed DEVELOPMENT execution | no cross-database atomicity |
| C-EP1 `read_summary`/replay | read-only or idempotent recovery | completed call | wall/process ns; read | observed DEVELOPMENT execution | repeated reads are not exams |
| A8 `run_fixture` | aggregate fixture call | C-EP1 retained event | wall ns; invocation | observed DEVELOPMENT execution | scalar HMAC stub; executes no Strategy |
| C-02/C-04/C-07 real phases | reconstruction/reference/inference/witness | unavailable | unknown | not implemented | authorized backend/reference/orchestrator absent |
| eligible public numerical fixture | standalone numerical reference probe | unavailable in this source revision | unknown | observed public numerical probe | no eligible pinned fixture selected; no probe run |
| C-EP2 replay | hypothetical grouping/accounting | detached deterministic model | normalized work/time units | counterfactual model | not calibrated to physical work or adaptive miners |

Root call spans are the only chargeable observed wall/process intervals.
Nested/pre-commit event durations are reported separately and never summed into
root work. Unexplained wall/process remainder stays visible. A missing phase is
`UNKNOWN`/`NOT_IMPLEMENTED`, never zero.

## Trace and privacy contract

Each closed v1 record binds a study run/revision, opaque local association,
attempt number when known, owner, operation, boundary, clocks, elapsed values,
work count, outcome, missingness, evidence class, nesting, chargeability and
durability qualification. The committed fixture-safe trace removes private
association and absolute clock values. No Strategy bytes, candidate/pack IDs,
seeds, tensors, result bytes, reference data, latent lineage, credentials, or
reward data are written.

Diagnostic observation is best-effort and outside lifecycle authority. A sink
failure marks performance evidence unusable but cannot change a lifecycle
outcome or consume a pack/attempt/event. Authoritative evidence failures remain
owned by their source service and are never suppressed.

## Frozen execution plan

- One validator identity, one synchronous owner, concurrency one.
- Python 3.11 supported local runtime when available; record exact host/runtime.
- Disposable SQLite databases for every independent block.
- Twelve ordinary blocks, each measuring cold first job, warm distinct job,
  exact duplicate evaluation, and summary read.
- Eight fixed-input observer-parity pairs.
- Four repetitions each for mandatory fixture result, terminal infrastructure
  failure, retryable infrastructure successor, ambiguous restart,
  post-result closure recovery, and post-closure summary replay.
- One queued-unrelated-work interleaving to validate exact C-01 claim behavior.
- Stable seed `20260913`; deterministic UUIDs and explicit scenario values.
- Stop after the frozen repetitions. Do not rerun based on favorability.

The ordinary block reconciles admitted distinct jobs against completed,
incomplete/terminal, and pending jobs. Deduplicated requests, packs, attempts,
retries, reconstruction partials, results, summaries, and replay deltas are
reported separately.

## Detached replay plan

The seven small scenarios are sparse compatible demand, ordinary compatible
demand, saturated/bursty demand, mixed durations, multiple incompatible
Challenges, duplicate/flood traffic, and a slow/failed/unresolved group. All
arrival and work values are explicit synthetic assumptions in normalized
units. Group bound is three. At each dispatch opportunity the replay may use
only admitted compatible jobs already present; it never waits to fill, sees
future jobs, crosses Challenges, or changes per-candidate work. A singleton is
used when sharing is unavailable.

Variant B pays one modeled reference cost per hypothetical group, all candidate
and closure work per member, and an unknown group-level overhead. Results show
an explicit zero-overhead counterfactual and separately recomputed dynamic-
grouping scenarios at the frozen overhead values. They are not universal
bounds: overhead changes dispatch time and can therefore change which admitted
jobs group. Any break-even quantity that fixes membership states that
assumption. Unknown overhead leaves actual B work, eligibility and release
times unknown. A numeric synthetic overhead supports only an assumption-
conditioned model result, never empirical savings. A fast member's summary
waits for the last terminal member; an unresolved member leaves its entire
group unfinished while unrelated later groups remain independently processable.

This wording is the v2 post-freeze reporting correction. The original v1 replay
artifact remains historical evidence; its `lower_bound` labels are superseded
by `variant_b_replay_correction_v2.json` and must not be interpreted as bounds
on the endogenous grouping policy.

## Stop conditions and claim limits

Stop or mark the affected result unusable on semantic parity failure, identity
change, unexpected pack/attempt/reward effect, malformed trace, clock
discontinuity, missing required span, accounting imbalance, nonfinite input,
unexpected sharing surface, or a baseline defect without a source-owner
disposition.

The study does not measure neural training, physical reference generation,
model inference, CFD, GPU work, protected comparisons/day, miner satisfaction,
adaptive behavior, scientific adequacy, or independent integrity. It cannot
clear AT-09, AT-16, AT-19, AT-22, or AT-30. Reuse this observation method on
the authorized reconstruction/reference path and declared hardware when those
inputs exist.
