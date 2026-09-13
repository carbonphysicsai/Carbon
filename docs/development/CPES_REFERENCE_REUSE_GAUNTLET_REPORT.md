# CPES reference-reuse gauntlet continuation

**Decision:** `RETAIN_A`

**Issue:** [EXAM-PROTECT-01 #142](https://github.com/carbonphysicsai/Carbon/issues/142)

**Research baseline:** `d94a22bb3c09089e01402db9e7ebf6eb3c662966`
(PR #149 merge)

**Protocol:** `carbon.cpes-reference-reuse-gauntlet.protocol.v2`
**Authority:** detached DEVELOPMENT research only

## Owner decision brief

Carbon should keep its current simple policy: one independently admitted job,
one fresh child pack, private evidence, and a summary only after that pack
closes. The only reuse design that survived the executed research attacks is a
strict form of Variant B: one common fresh pack for compatible jobs already
committed at the dispatch point, immutable membership before case knowability,
exact reference-cache identity, no early feedback, and last-member closure.
That result is limited to an in-memory model and a disposable SQLite prototype;
it is not evidence that a production B path is secure.

Variant B can reduce recurring work when at least two truly compatible jobs are
ready and the avoided repeated reference work exceeds the added group control
work. For fixed membership and unchanged evidence, the exact arithmetic
condition is `(b - 1) * R > H`. Carbon does not yet know the real compatible
demand, B overhead, field-dependent evidence cost, or qualified reference
cost. Those unknowns prevent an implementation recommendation today.

Variant C sometimes improves a bursty synthetic queue by waiting long enough
to avoid another reference calculation, but it adds delay in sparse traffic
and creates no new protection. It is not supported. Repeated exact feedback
against a finite hidden bank is directly exploitable and is rejected as a
candidate design. Early summaries and answer publication remain absent.

## Provenance and current authority

The study used a separate worktree and did not modify the Wave C executor's
checkout or selection records. Current `origin/main` was exactly the reviewed
PR #149 merge when the protocol was frozen. Issue #142 remains open. PR #140
remains open at proposal head
`1cf65ef3b13b675b20a7566b7441cf25d1784f2a`; its CPES-1 v0.2 files are design
inputs, not runtime authority.

The owner-supplied original gauntlet ZIP matched SHA-256
`088d3e1182cbd8974c14ba6614a470cdcf3d5f3e6335c1db085699789ec5ffcb`.
It was listed and checked for absolute/traversal paths before extraction. The
two embedded reports and separately supplied `outputs/GAUNTLET_REPORT.md` are
byte-identical, SHA-256
`2954e8505202f58be86d5048c571102f2603c30ebd1a56fa23a5bb8f12132395`.
The model, attacks, operating replay, publication proxy, configuration,
commands and tests were read before execution.

The unchanged extracted harness reran successfully: 26 tests passed, and its
summary reproduced 25 model rejections, five blocked claims, three vulnerable
control exploits, 15 exploratory replays and three confirmation replays. This
reproduces the historical model only. It does not promote those outcomes to
repository-interface or production evidence. The historical 72.5% exact
overlap remains one deliberately finite scalar-publication counterexample, not
an expected Carbon overlap rate.

The continuation reads C-EP2's corrected endogenous-grouping model, C-EP3's
public numerical component record and C-03's public-data worker report without
modifying them. C-EP3 measured one public Burgers case: its two warm primary
reference calls were 288.438 and 289.821 ms on an Apple M3. C-03 separately
reported an 11.384 s Foundax reconstruction worker trace on Linux x86-64.
Those are different components, hosts and timing boundaries and are not added
or divided to manufacture a shareable fraction.

## Experiments executed

### Attack model and persistent transition prototype

The continuation preserves all 30 original IDs. Current classifications are:

| Classification | Count | Meaning |
|---|---:|---|
| Rejected by reproduced original model | 17 | The unchanged historical hypothesis model rerun rejected the attempted transition; no runtime claim follows. |
| Rejected by persistent research prototype | 8 | A disposable SQLite transaction/constraint rejected the attack after restart or at a durable transition boundary. |
| Blocked | 5 | Required owner, provider, lineage, host-integrity or scientific evidence is absent. |

The five blocked attacks remain exactly AT-09, AT-16, AT-19, AT-22 and
AT-30. AT-19's prototype rejects a declared identical case alias, but that is
not an authoritative Carbon asset-lineage registry. AT-30's vulnerable control
demonstrates an exploit, but no qualified Carbon-family freshness test or
leakage criterion exists.

The persistent probes used independent SQLite connections and restart. They
observed:

- a same-job assignment race with one `ASSIGNED` effect and one
  `INELIGIBLE_MEMBER` rejection;
- `MEMBERSHIP_CLOSED` for late admission after exposure;
- `PACK_CLOSURE_REQUIRED` for an early summary;
- `ANSWER_DEPENDENT_OPPORTUNITY_OPEN` for premature close and an open retry;
- `PREDICTION_CONFLICT` for changed bytes under the same attempt;
- `PACK_CLOSED` for a stale post-restart write;
- exact cache hits only when Challenge, physical input, output request,
  units/scaling, solver, environment, policy and evidence depth all match;
- a distinct retained `FAILED_REFERENCE` rather than a candidate score; and
- `ANSWER_PUBLICATION_NOT_AUTHORIZED` at the direct prototype interface.

Removing the late-membership, retirement and evidence-authority guards made
all three attacks succeed. These are vulnerable controls, not production
features.

### Adaptive finite-bank control

The D arm exposed only an exact correct-count score, not raw answers. Against a
32-case synthetic bank, a zero baseline plus 32 single-case flips recovered
all 32 labels in 33 adaptive queries. Accuracy was 100% on the reused bank and
46.875% on an independently generated 32-case holdout. This is a concrete
feedback-channel exploit: hiding files does not prevent extraction through
repeated precise scores. It does not estimate Carbon's future overlap or
define an acceptable leakage rate.

[Dwork et al.](https://papers.nips.cc/paper_files/paper/2015/file/bad5f33780c42f2588878a9d07405083-Paper.pdf)
show that adaptive holdout reuse requires an information-limiting mechanism
and stated assumptions. [Blum and Hardt's Ladder](https://arxiv.org/abs/1502.04585)
addresses a narrower adaptive leaderboard problem. Neither result turns
ordinary repeated scores or public answer archives into safe Carbon policy.

### Conditional cost and delay

The frozen replay used one serial validator resource, explicit synthetic
arrivals, group bound three, fill wait four units for C, and group-overhead
scenarios 0, 4 and 12 units. It recomputed endogenous membership for every
overhead value. The following table shows the declared `H=4` scenario; units
are synthetic and cannot be interpreted as milliseconds, dollars or exams per
day.

| Workload | A work / mean feedback | B work / mean feedback | C work / mean feedback | Key result |
|---|---:|---:|---:|---|
| Cheap sparse | 72 / 12.0 | 96 / 16.0 | 96 / 20.0 | No groups form; B adds control work and C adds wait. |
| Expensive bursty | 459 / 241.3 | 275 / 167.1 | 231 / 147.0 | Sharing helps in this assumed bottleneck; C groups more work before dispatch. |
| Mixed Challenges | 360 / 196.5 | 270 / 150.8 | 226 / 150.3 | No cross-Challenge grouping; C's incremental result is workload-specific. |
| Duplicate flood | 255 / 151.0 | 187 / 125.6 | 143 / 105.0 | Eight copies are deduplicated and add no scientific jobs. |
| Slow/unresolved member | 186 / 116.0 | 114 / 113.0 | 114 / 121.0 | A yields three summaries; B/C yield one because the shared pack remains unresolved. |

The slow-member row is why total work alone cannot justify B: its apparently
lower bill accompanies fewer complete comparisons. No-work and failed work
remain in the denominator and backlog. In the bursty rows, C can reduce queue
work enough to offset its intentional wait; in sparse rows, it only worsens
feedback. There is no owner-supplied service preference with which to choose
that trade-off.

For the fixed-membership sanity grid, `H=4` requires `R>4` for `b=2` and
`R>2` for `b=3`. With unknown H, compatible demand and evidence scaling,
there is no unconditional break-even region. The public C-EP3 timing can be
substituted only as a scoped component assumption; it is not an adequate
reference floor and does not establish that compatible jobs co-occur.

## Smallest supported later design

If future measurements satisfy the named conditions, Engineering should
consider only this minimal B profile:

1. Keep CandidateRef, Strategy, Challenge, attempt, replica and reward
   identities unchanged. Sharing creates a child pack association, not a new
   candidate entitlement.
2. At one predefined dispatch opportunity, atomically select only compatible
   jobs already durably admitted. Lock membership and its exact compatibility
   digest before case-selection material becomes knowable. Singleton fallback
   is mandatory.
3. Bind cache reuse to the complete scientific identity: Challenge/version,
   physical inputs, requested outputs, units/scaling, generator/reference
   configuration, environment, policy, evidence depth and complete artifact
   commitment. A name, URL or caller-provided reference is insufficient.
4. Keep TRAIN/reconstruction randomness and required replicas candidate-owned.
   Share only the reference operation whose source-owned identity and evidence
   semantics are genuinely common.
5. Persist intent before draw and dispatch. Retry the same pack/attempt under
   C-01 rules; ambiguity requires reconciliation, never a fresh draw.
6. Record private predictions and reference evidence before result binding.
   Changed, cross-attempt, cross-pack and stale bytes reject.
7. Release no result summary until every member's answer-dependent work and
   retry/cancellation path is durably terminal. A blocked pack must not block
   unrelated Challenges.
8. Quarantine all affected pending uses on suspected leakage. Preserve history
   and prevent subsequent effects; do not claim already observed feedback can
   be recalled.
9. Add no answer publication in the first B slice. Retirement, public rights,
   cross-pack lineage and safe archive release remain a separate blocked
   disclosure decision.
10. Keep B outside accepted-result, frontier and reward consumers until the
    scientific comparison owner defines common-case evidence and field-size
    resolution.

The later Engineering acceptance must include coordinated membership/exposure
races, immutable compatibility, exact cache mismatches, reference completeness,
per-member failure/cancellation, last-member closure, slow/unresolved members,
restart at every intent boundary, stale writes, retry/replica separation,
TRAIN/EVAL randomness separation, incident quarantine, cross-Challenge
progress, disclosure absence and reward exclusion. The prototype here does not
satisfy those runtime tests.

## What remains unqualified

- AT-09: production provider/event/finality and active-case confidentiality;
- AT-16: secrecy from a privileged plaintext host;
- AT-19: authoritative asset lineage and future-case overlap;
- AT-22: independent evidence of honest execution;
- AT-30: qualified freshness, adaptive leakage and publication criteria;
- qualified reference adequacy and field-dependent evidence cost;
- representative compatible demand and adaptive miner behavior;
- actual B membership, recovery, audit and closure overhead;
- acceptable feedback delay and production group/repeat limits.

The [drand protocol](https://docs.drand.love/docs/specification/) supports
verification of public beacon output. It does not make that output secret.
[Timelock encryption](https://docs.drand.love/docs/timelock-encryption/)
releases by time under threshold assumptions; it does not prove Carbon work is
closed. Those mechanisms therefore do not clear AT-09, AT-16 or AT-20 by name
alone.

## Verification and evidence

Focused continuation tests: **14 passed**, zero skipped or failed. The original
isolated harness rerun: **26 passed**, zero skipped or failed. Black and Ruff
pass on the new Python paths. The combined continuation/C-EP1/C-EP2 regression
set passed **52 tests**, and the full invariant suite passed **208 tests**, all
with zero skips or failures. These are current local runs; historical C-EP
counts are not copied here and canonical CI remains a separate delivery gate.

Raw outputs and hashes are under
`.agent/evidence/research/cpes-reference-reuse-v2/`. The profiler-safe output
contains no protected case, answer, seed, candidate identity or qualification
toggle. The research harness is under `scripts/dev` and imports no Carbon
runtime pack, scoring, reward, disclosure or launch service.

## Recommendation

**RETAIN A.** Variant B is worth preserving as a narrowly specified option,
not building now. Revisit it only when an eligible trace shows compatible jobs
coexisting at dispatch and a qualified, same-identity reference cost plus a
bounded B overhead estimate satisfies `(b - 1)R > H` without unacceptable
last-member closure delay or weaker evidence. Variant C requires an additional
incremental showing over B. Reject repeated hidden-bank feedback and keep
answer publication absent.

This research does not modify C-02, C-03, C-04, C-05, C-07, C-EA2, C2,
runtime seeding, construction, workers, scoring, rewards or Wave C selection.
It is not a security certificate or production activation.

## Hub impact

Primary relationship: issue #142 / EXAM-PROTECT-01. No Wave or ticket status
changes, no selection changes and no generated Hub pages are part of this
parallel research delivery. The profiler JSON is an import-safe evidence
artifact only and cannot create an approval or alter Hub authority.
