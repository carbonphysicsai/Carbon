# Live exam throughput: first development baselines

**Date:** 11 September 2026

**Status:** working research evidence and Engineering handoff. No LIVE exam, scientific/security qualification, production capacity, or optimal runtime is established. This extends [Runtime Profiles](RUNTIME_PROFILES.md), not the scoring, sampling, entropy or execution contracts.

## Owner clarification

Optimize Carbon's productive live comparison rate. The difference between 2–3 and 100–200 complete comparisons per day matters to the discovery program. Measure the supported improvement and useful feedback delivered under an explicit hardware and compute budget, alongside the raw comparison count.

Keep these four records separate:

| Record | Quantities |
|---|---|
| One-time exam qualification | Integration and qualification expenditure, elapsed onboarding time, unresolved adequacy/security risks and activation evidence |
| Recurring live operation | Fresh training labels, independent reconstruction, evaluation reference work, inference, measurements, receipts, audits, retries, worker occupancy and complete distinct comparisons/day |
| Discovery effectiveness | Heldout improvement at equal research resources, supported frontier gain, false/unresolved selection, candidate supply and feedback-cycle delay |
| Client deployment | Physical adequacy, cost/accuracy, latency/throughput, operating envelope, escalation and lifecycle value |

Do not amortize qualification expenditure into the live stopwatch. A lifetime commercial cost model may include it separately. Recurring reference refreshes and requalification are visible events, not omitted costs. No single scalar fit score may compensate for missing scientific evidence.

## Executed pilot and claim boundary

The repository read still showed bounded C1 engineering without a complete qualified live path. The available local device was CPU, not GPU. I ran standalone public research fixtures, not Carbon's canonical runtime, production secrets or Harshdeep's unavailable JAX library. No public-network operation or external paid compute was used.

A local protocol preceded numerical execution. Exploratory resampling/replay was specified after the reconstruction runs; it is not preregistered qualification evidence. Source, raw arrays, timing JSON/CSV, protocol, execution-event record and artifact hashes are supplied in the companion `carbon_throughput_pilot_2026_09_11` research bundle. They are not runtime files in this PR. The workbook is `Carbon_Live_Throughput_Baselines_v0_1.xlsx`; its live capacity values are labeled scenarios, not production inputs.

Physical scope: u_t + (u^2/2)_x = nu*u_xx, periodic [0,1], zero mean, nu=0.005, final time 0.25, four smooth Fourier initial-condition modes. Gaussian coefficients weighted by k^-2 were rescaled to an absolute coefficient sum uniformly between 0.1 and 0.3. These are development parameters and an easy research population, not an approved Challenge envelope or sampling law. Candidates receive a 128-point initial field and predict the 128-point final field. Data split: 256 training, 128 screening and 256 disjoint holdout cases.

Reference: float64 periodic Cole–Hopf heat evolution on 1,024 points, with 2,048-point refinement; an independently formulated centered conservative finite-difference/RK4 witness on eight cases shares author, assumptions and hardware and does not establish independent qualification. Witness mean relative-L2 disagreement decreased from 0.00042333 to 0.00010585 to 0.00002646 at 128/256/512 cells. The maximum 1,024-vs-2,048 discrepancy across all 640 cases was 1.89e-14. This is bounded implementation evidence, not a complete uncertainty budget.

Construction: compact FNO-inspired network (19,297 parameters) and periodic CNN (3,937 parameters), each width 16/depth 3, residual output, batch size 32, Adam and float32 learning. Two learning rates (0.001 and 0.003) and three initialization/batch seeds (11/22/33) give four strategies and twelve reconstructed models. Checkpoints at 25/100/400 steps give 36 correlated observations, not 36 independent official exams. The implementations and parameter counts are not matched for a definitive family comparison.

Each reconstruction process used two CPU-affinity slots within a four-CPU container quota. JAX/jaxlib 0.9.0.1, NumPy 2.3.5, SciPy 1.17.0. Timings synchronize device work and separate cold compilation from warm execution. Shared-host variation remains. No GPU or production multiplier is inferred.

## Measurements

### Reference and cache

| Work | Median elapsed | Observed repeat range |
|---|---:|---:|
| Compute 128 answers | 10.36 ms | 5.00–12.94 ms |
| Compute 512 answers | 18.92 ms | 16.86–34.23 ms |
| Compute 2,048 answers | 94.03 ms | 76.90–178.10 ms |
| Compute 384 screen/holdout answers | 14.46 ms | 12.64–33.97 ms |
| Warm local read/decrypt/deserialize of the 384 input/answer pairs | 1.08 ms | 0.864–2.392 ms |

The cache payload was 786,944 bytes. AES-GCM used an ephemeral in-memory key and associated identity. Byte parity held; wrong key, changed ciphertext and wrong identity each rejected. No network-store, malicious-host, candidate-egress, collusion, cumulative-feedback, access-control, durability or key-custody security campaign was run. These are primitive correctness checks, not secure-reference qualification.

Reference-stage loading was 13.36 times faster, but replacing reference compute with loading saved at most approximately 0.27% of the measured-phase 5.04 s cold FNO/0.003/400-step comparison. This optimistic bound omits cache creation. Reference caching is therefore not a priority throughput intervention for this fixture. No inference about industrial CFD reference cost follows. The fast direct method remains a deployable baseline; this pilot establishes no commercially useful surrogate speedup.

### Construction budgets

FNO at learning rate 0.003, over three reconstruction seeds:

| Steps | Median training execution | Median phase-accounted cold comparison | Mean holdout relative-L2 |
|---|---:|---:|---:|
| 25 | 0.288 s | 3.03 s | 3.162% |
| 100 | 0.684 s | 3.38 s | 0.541% |
| 400 | 2.287 s | 5.04 s | 0.201% |

Cold totals sum measured imports/setup/batching, training and inference compilation, training, first inference, host diagnostics and fresh evaluation-reference computation. They are not a stopwatch measurement of the complete Carbon exam. They exclude queues, containers, Carbon orchestration and signed receipts, fresh training-reference generation, required repeated reconstruction, audits and production security. All 640 fixture labels took 32.04 ms to create in a separate one-off measurement; real data policy determines recurring allocation.

At 400 steps, mean holdout relative-L2 was 0.276% for FNO/0.001, 2.047% for CNN/0.001 and 1.859% for CNN/0.003. All results and mass/energy/extrema diagnostics remain in the supplied bundle. Some predictions had nonzero mass error or extrema violations. No production gate was selected; no model is physically qualified.

### Equal-budget finite-pool replay

An exploratory simulation used 2,000 common random orders of the twelve recorded builds, finished builds while their cold phase sums fit a 30 s budget, selected using screening error, and reported distinct-holdout error. These are allocation replays, not new physical experiments or adaptive miner campaigns.

| Steps/build | Median recorded builds completed | Median selected holdout error |
|---|---:|---:|
| 25 | 7 | 2.855% |
| 100 | 6 | 0.465% |
| 400 | 4 | 0.184% |

Within this finite pool, fewer deeper builds delivered better prediction quality at equal phase-accounted resources. This does not establish that four exams is optimal, that 400 steps is sufficient, or that slow operation is preferable in general. The best result is at the boundary of a small tested grid; no live optimum has been found.

### Common-case diagnostic

Across all 66 pairs at 400 steps, conditional bootstrap sign disagreement against the 256-case holdout mean ordering was 4.70%/2.87%/1.99% with 8/32/128 shared screening samples, versus 10.35%/5.97%/3.95% with independent samples. Holdout order is uncertain, model pairs are dependent and the screen pool is finite. This motivates common-case comparison research; it cannot select a production sample count or establish a false-promotion bound.

One outer tool call timed out before its last process wrote a result. Four completed results were retained and only the missing fixed configuration was rerun. The interruption remains infrastructure history, not candidate failure. All twelve planned runs then completed. No timing from the missing attempt was discarded as a scientific outlier because it produced no completed result.

## Capacity targets, separate from measured production claims

For a homogeneous candidate pool, the idealized capacity bound is:

    distinct comparisons/day <= 1440 * slots * availability / candidate_slot_minutes_per_comparison

Candidate demand includes the registered rebuild count and other required work. A separate reference pool contributes its own bound using amortized reference slot-minutes/comparison. Take the minimum across pools and candidate supply. When stages share hardware, add their demands before applying the capacity bound. Track early mandatory failures, unresolved evidence, infrastructure/reference failures and complete admissible comparisons separately. Replicas, retries and checkpoints are not new strategy proposals.

Illustrative 75% availability, not a selected operational reserve:

| Candidate slots | Occupancy available for 100 comparisons/day | Occupancy available for 200 comparisons/day |
|---|---:|---:|
| 1 | 10.8 min | 5.4 min |
| 4 | 43.2 min | 21.6 min |
| 8 | 86.4 min | 43.2 min |
| 16 | 172.8 min | 86.4 min |

Those are total candidate slot-minutes per comparison. If three rebuilds alone consume the allowance, divide by three; inference and other required work reduce the remaining build allowance. A slot must identify hardware and concurrency. The algebra is not a queue-delay or p95 model.

A separate synthetic sensitivity example assumes one two-hour reference-batch worker, four 30-minute candidate workers, 75% availability and 100 arrivals/day:

| Committed cohort | System capacity/day | Supply-limited completions/day | Mean cohort-fill wait alone |
|---|---:|---:|---:|
| 1 | 9 | 9 | 0 h |
| 4 | 36 | 36 | 0.36 h |
| 16 | 144 | 100 | 1.80 h |
| 64 | 144 | 100 | 7.56 h |

These are computed scenarios, not measured industrial runtimes or queue simulation. At cohorts 1/4, offered arrivals exceed capacity. At 64, the candidate pool still limits throughput and fill delay rises. Under those assumptions, increasing reuse beyond 16 gives no throughput benefit. No cohort size or reuse authorization is selected.

## Engineering experiment requirements

1. Instrument the actual selected construction, reference, evaluation and receipt path on target hardware. Retain cold/warm times, device-seconds, contention, full comparison wall times and typed failures. Do not dispatch paid or public-network work without its existing authorization.
2. Measure learning curves under several fixed reconstruction resource profiles. Keep the same mandatory exam within each comparison. Qualification of alternate sample counts, repetition policies or reference fidelity is a separate prospective campaign, never candidate-specific pruning of official evidence.
3. Run repeated equal-resource discovery campaigns, randomizing schedules and measuring complete unique comparisons/day, independently supported improvement, time-to-target, selection uncertainty and feedback latency. Use fresh common holdouts for the decision. Record real proposal supply and correlation instead of treating repeated seeds as new ideas.
4. Compare fresh-per-candidate references with bounded frozen-cohort reuse under the separately approved custody/entropy/disclosure design. Include production cache overhead, replenishment, expiry, protection and retirement; do not infer security from AES-GCM rejection tests.
5. Fit candidate/reference/measurement resource-pool capacity and queue models from traces. Compare observed versus predicted throughput under load. Report a non-dominated rate/quality/cost/delay region rather than inventing a universal optimal daily count.
6. Keep one-time qualification risk, cost and elapsed time in a separate Carbon Fit section. It determines whether to open the program, not how many seconds an already-qualified recurring comparison consumes.

This work adds no mainnet dependency or new official score. The qualification/security/operations owners still select real tolerances, evidence sufficiency, resource ceilings, reuse limits, activation and client promises. The existing #141 acceptance blocker is not bypassed or repaired by this report.

## Sources

- [JAX benchmarking documentation](https://docs.jax.dev/en/latest/benchmarking.html): synchronized timing, compilation and data-transfer accounting.
- [FNO paper](https://arxiv.org/abs/2010.08895): architecture inspiration only.
- [Hyperband](https://arxiv.org/abs/1603.06560): research context for breadth/depth allocation, not official-pack pruning authority.
- [Weak numerical baselines](https://arxiv.org/abs/2407.07218): credible baseline comparison and reporting discipline.
- [Research Resource Policy Contract](../../Design_Specs/Research_Resource_Policy_Contract.md), [Validation Dossier](../../Design_Specs/Generator_Validation.md), [Trust-minimized verification](../../Design_Specs/Trustless_Verification.md), and [Scientific Canon](../../docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md): controlling Carbon authority.
