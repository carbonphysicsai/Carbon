# C-EP2 Variant-A measurement and Variant-B decision

**Recommendation:** `COLLECT MISSING INPUTS FIRST`

**Implemented baseline:** C-EP1 PR #143, accepted head
`e0fbb6208cf0bf95910d51e7a3c996b09387a14e`, merged as
`d783c2c7209c7eea2d46dd395c4eaaf8094a9e71`

**Frozen study implementation:**
`bb009a2d8a3045fd29ea2c2c8c46aed2218c5c76`

**Primary map_ref:** `WAVE-C/C-EP2`

## 1. Plain-language result

C-EP1 already gives each separately admitted DEVELOPMENT candidate one durable
child pack. The miner-facing behavior remains submit an immutable Strategy,
retain its receipt/status, and read the permitted fixture result after durable
pack closure. Copies, retries, restarts and repeated reads do not create another
pack, draw, result or reward effect. Evidence remains private and C-EP1 results
remain outside incompatible accepted-result/reward consumers.

C-EP2 measured that existing singleton fixture path, its local SQLite owners,
deduplication, retry/restart and closure-replay behavior. It also ran a detached
offline arithmetic model of hypothetical already-admitted sharing. It added no
shared membership, fill wait, early summary, public answer, production entropy,
reward route, real archive acknowledgement or real finalization capability.

The current evidence cannot answer whether reference sharing is worth building.
A8 is still a deterministic scalar stub: it executes no Strategy and exposes no
physical reconstruction, reference generation or candidate inference phase.
Consequently the actually shareable reference fraction, real compatibility
rate, B control/recovery overhead and representative offered workload are all
unknown. A favorable normalized replay would be a forecast built from assumed
costs, not evidence of recurring compute savings.

## 2. Provenance and compatibility

At study start, `origin/main` was exactly the C-EP1 merge commit above. The
owner-supplied C-EP1 delivery ZIP was listed and integrity-tested before use;
its SHA-256 matched
`9c8bc20b643f098eb064f8d40731a94d8729311b3be7f3a223270de4adb434fc`.
The separately supplied report and changed-path inventory are byte-identical to
their archive copies. The 62-line inventory exactly matches the PR #143 merge
diff. The prior gauntlet ZIP matched
`088d3e1182cbd8974c14ba6614a470cdcf3d5f3e6335c1db085699789ec5ffcb`.
Checksums establish byte identity, not correctness or qualification.

PR #143 and successful RUNTIME_FULL run `34708322417` were verified. Its
historical 5,220 CPU passes/one skip, 208 invariant passes, 87 package passes and
17 authority-boundary passes remain C-EP1 evidence and are not copied into
C-EP2 results. PR #140 remains open and unmerged; issue #141 remains open. They
were not bundled or bypassed.

C-EP2 preserves C-EP1's global Strategy, Challenge, CandidateRef, receipt,
pack, result and reward meanings. One narrow C-01-owned repair adds an atomic
claim for an exact already-admitted attempt. The prior synchronous composition
could claim an older unrelated queue entry and only then discover the mismatch.
The regression now proves the unrelated attempt remains `QUEUED` while the
intended C-EP1 job completes. `claim_next` remains unchanged for general queue
consumers; no scheduler or sharing surface was added.

## 3. Observed DEVELOPMENT execution

The frozen protocol used one validator identity, concurrency one, disposable
SQLite databases, Python 3.11.16 on arm64 Darwin 24.6.0, eight logical CPUs,
8 GiB memory and no GPU. It retained 131 trace records, including two explicit
missing observations. Root spans totaled 507.591 ms wall and 436.938 ms process
time. Internal C-EP1 event timings are reported separately because each stops
before its final event INSERT/commit and is not a full durable transaction.

The study reconciled:

| Item | Observed count |
|---|---:|
| Distinct admitted jobs / packs | 49 / 49 |
| Completed fixture outcomes | 41 |
| Scored ordinary fixture results | 24 |
| Mandatory-gate results | 4 |
| Incomplete terminal jobs | 4 |
| Pending reconciliation jobs | 4 |
| Execution attempts / fixture reconstruction obligations | 53 / 53 |
| Infrastructure retries | 4 |
| Result / summary records | 41 / 41 |
| Deduplicated requests | 12 |
| Post-result / post-closure recovery replays | 4 / 4 |
| Physical reference cases / candidate inference / GPU time | unknown / unknown / unknown |

The accounting identity holds: 49 admitted jobs = 41 completed fixture
outcomes + 4 incomplete terminal jobs + 4 pending reconciliation jobs. Replays
created no fresh pack or extra completed proposal.

Selected wall-time distributions are below. Median is only the middle of 12 or
four local observations, not a production p50 estimate; maxima are especially
sensitive to host scheduling.

| Completed boundary | n | min | median | max |
|---|---:|---:|---:|---:|
| Owner startup/open | 12 | 5.548 ms | 6.556 ms | 12.728 ms |
| Cold aggregate Variant-A job | 12 | 6.797 ms | 7.217 ms | 7.842 ms |
| Warm distinct aggregate job | 12 | 6.425 ms | 7.314 ms | 9.255 ms |
| Duplicate candidate commit | 12 | 0.392 ms | 0.411 ms | 0.491 ms |
| Completed-job replay | 12 | 0.453 ms | 0.476 ms | 0.571 ms |
| Read-only summary replay | 12 | 0.221 ms | 0.234 ms | 0.294 ms |
| Retryable-infrastructure successor | 4 | 10.355 ms | 10.990 ms | 11.719 ms |
| Ambiguous restart injection | 4 | 5.170 ms | 5.358 ms | 22.099 ms |

Eight fixed-input observer pairs had zero semantic mismatches. Enabled-minus-
disabled wall differences ranged from -1.381 ms to +0.606 ms, with a -0.300 ms
median. That noisy signed range does not establish a speedup or a precise
observer cost; it shows no resolvable positive overhead at this sample size.
Diagnostic sink failure is tested to leave the operation result unchanged while
marking performance evidence unusable.

No public numerical probe ran because no eligible, pinned public research
fixture was selected. Neural training, physical references, CFD, candidate
inference, accelerator work and exams/day are not measured zero; they are
`UNKNOWN` or `NOT_IMPLEMENTED`.

## 4. Counterfactual model only

The detached replay uses explicit normalized assumptions: candidate work 2–40,
reference work 10 per admitted job/group, closure work 1 per member, group bound
three, zero intentional fill wait and seven fixed offered streams. Only
compatible jobs already admitted at a dispatch opportunity may group. It never
writes the pack ledger, changes A4, sees future arrivals, crosses Challenges or
routes results into scientific/reward owners.

With B overhead still unknown, every B total and summary time remains unknown;
the replay reports lower bounds and break-even sensitivity instead. Sparse
demand formed only singletons and saved zero normalized work. The ordinary
assumption reduced lower-bound work from 92 to 72, but could tolerate only 20
total added B work units across two groups before break-even (less than 10 per
group for a positive result). The bursty assumption reduced 138 to 98 and could
tolerate 40 total units. These are arithmetic consequences of assuming the
reference phase costs 10 and is reusable; neither input is observed.

Closure delay is real in the model even with zero fill wait. Lower-bound delay
from candidate finish to group release reached 14 normalized units in the
ordinary case, 27 in the saturated case and 38 in the mixed-duration case,
before unknown B overhead. In the slow/failed/unresolved scenario, a three-
member pack containing one unresolved member withheld the otherwise completed
fast member's summary; B produced two eligible summaries versus A's three.
Independent Challenge work continued, so there is no modeled global barrier.
Duplicate flood traffic created only three admitted jobs and therefore no extra
groups or work.

The only potentially shareable work is a future C-04-owned evaluation-reference
calculation whose exact Challenge, physical I/O, evidence plan, generator,
reference configuration, resource comparison, uncertainty, disclosure and
custody permissions all match. Training-label generation, candidate
reconstruction, candidate inference, mandatory measurements, witness/audit and
per-member closure evidence remain separately charged. C-EP2 has not observed
any of those real costs or decided whether a common realization preserves the
intended TRAIN/EVAL randomness or comparison semantics.

## 5. Decision and next investment

`COLLECT MISSING INPUTS FIRST` is the only supported recommendation. The
smallest useful next investment is not a B implementation. It is to rerun the
same observation method on an authorized C-02 reconstruction, C-04 reference
and C-07 orchestration path on declared hardware, plus a bounded representative
trace of already-admitted workload and explicit compatibility refusals. That
would measure the reference fraction, candidate/reference resource occupancy,
failure/witness costs and grouping opportunity. A separately authorized common-
comparison study must also decide whether B's common realization has adequate
scientific meaning.

Only then could a B-specific DEVELOPMENT experiment be considered. Its durable
tests must cover admission racing before case exposure, immutable membership,
shared-reference completeness, per-member failure/cancellation, last-member
closure, restart/stale-write rejection, and TRAIN/EVAL randomness separation.
This report authorizes none of those runtime features.

AT-09, AT-16, AT-19, AT-22 and AT-30 remain blocked exactly as in the gauntlet.
Measurement does not solve public-root confidentiality, hostile plaintext hosts,
reference lineage/freshness, honest execution or future-case overlap.
Independent integrity, production entropy/event/finality, real custody and
archive acknowledgement remain unavailable.

## 6. Verification and delivery status

Focused Python 3.11 verification currently reports `58 passed` with zero skips
or failures across C-EP2, C-EP1 and C-01 tests. Pinned Black 26.5.1 and Ruff
0.16.3 pass the changed Python paths. The runbook records exact commands and the
noncanonical Mac limitation. Applicable PR CI, Merge gate and merge status are
pending at this report revision; no production activation is claimed.

Machine-readable outputs are in `.agent/evidence/wave_c/c-ep2-study/`. The
committed trace is public-safe; the private trace is retained only in the local
delivery bundle. This study is unqualified supporting evidence, not an external
scientific result, qualified Carbon evidence or security certificate.
