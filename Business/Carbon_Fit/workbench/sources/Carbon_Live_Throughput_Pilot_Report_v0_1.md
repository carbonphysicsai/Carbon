# Carbon live-throughput pilot: first baseline measurements

**Date:** 11 September 2026

**Evidence class:** development measurements and labeled allocation models. Not a LIVE Carbon exam, scientific qualification, security qualification, production-capacity measurement, or verified frontier advance.

## Decision change

The owner prioritizes the number of complete, scientifically usable candidate comparisons per day and the resulting pace of discovery. A service that can evaluate 100–200 distinct proposals per day may have substantially greater search capacity than one evaluating 2–3, provided comparison quality, candidate supply and resource use remain comparable. Raw submission count alone does not measure that capacity.

Keep four records separate:

| Record | Contents |
|---|---|
| One-time exam qualification | Integration and qualification expenditure, elapsed onboarding time, unresolved physical/reference/security risks, and evidence needed to activate a profile |
| Recurring live operation | Fresh construction labels, independent rebuilds, evaluation references, candidate inference, measurements, receipts, audits, retries, worker occupancy and completed distinct comparisons/day |
| Discovery effectiveness | Progress on fresh independent evidence at equal resource budgets, false or unresolved selections, diversity of attempted interventions, and feedback-cycle delay |
| Client deployment | Accuracy, physical requirements, latency/throughput, operating envelope, baseline advantage, escalation and lifecycle cost |

Do not divide one-time qualification by submission count and add it to the live stopwatch. It may enter a separate lifetime commercial cost calculation. A recurring reference refresh or requalification is recorded when it occurs, without erasing its cost or describing it as ordinary per-candidate inference.

## What was executed

The active repository read identified bounded Wave C engineering without a complete qualified live path. The local environment exposed a JAX CPU device and no GPU. This experiment therefore used new, isolated research code in this bundle; it did not run Carbon production code, public-network transactions, external paid compute, or Harshdeep's unavailable JAX repository.

The initial protocol was written locally before the measurements. It is not an externally registered or owner-qualified exam. `analysis_plan.json` describes exploratory replay and resampling specified after the reconstruction runs. All seeds, samples and results here are public development fixtures; none is protected production exam material.

### Physical and numerical scope

The equation is u_t + (u^2/2)_x = nu u_xx on [0,1] with periodic boundary conditions, zero-mean smooth initial data, nu=0.005 and T=0.25. Four sine/cosine modes have Gaussian coefficients weighted by inverse squared mode number, then rescaled so the sum of absolute coefficients lies uniformly between 0.1 and 0.3. These values define this small research population, not a proposed Carbon operating envelope or sampling law.

Each candidate receives only u(x,0) at 128 points and predicts u(x,T) at those points. The fixed split has 256 training, 128 screening and 256 independent holdout cases. The comparison uses a float64 periodic Cole–Hopf computation: integrate the initial field, exponentiate the transformed potential, evolve the heat equation in Fourier space, differentiate, and reconstruct u. The timing path upsamples the same band-limited input to 1,024 points. A 2,048-point calculation checks refinement. This refinement is useful implementation evidence, not a complete uncertainty budget.

An independently formulated centered conservative finite-difference/RK4 implementation provides a witness on eight development cases. It shares author, physical assumptions and hardware with the primary calculation, so it does not establish methodologically independent qualification. Its mean relative-L2 disagreement was 0.00042333, 0.00010585 and 0.00002646 at 128, 256 and 512 cells. The approximately fourfold reductions support the expected second-order spatial convergence on these smooth cases. The maximum 1,024-versus-2,048 discrepancy across all 640 labeled cases was 1.89e-14. These results do not cover shocks, turbulent CFD, geometry changes or industrial reference costs.

### Reconstruction scope

Four strategy configurations: two compact model families multiplied by two learning rates. Each configuration has three fresh initialization/batch seeds, giving 12 reconstructed models. Each trajectory has 25, 100 and 400-step checkpoints, giving 36 correlated observations, not 36 independently reconstructed official exams.

The FNO-inspired network has 19,297 parameters, width 16, depth 3 and 12 Fourier modes. The periodic CNN has 3,937 parameters, width 16, depth 3 and five-point convolutions. Both use residual outputs, batch size 32, float32 learning and the same permitted inputs/data. The optimizer is Adam. This is neither a parameter-matched family comparison nor an optimized implementation of either family.

Each process is restricted to two available logical CPUs. JAX and jaxlib versions are 0.9.0.1; NumPy is 2.3.5; SciPy is 1.17.0. The container has a four-CPU cgroup quota. Timers synchronize JAX work. Cold compilation, imports/setup, training, first inference and warm inference are recorded separately. The host is shared, and timings show variation. No GPU rate follows from these numbers.

## Measured results

### Reference generation and cached loading

| Work | Median elapsed time | Observed repetition range |
|---|---:|---:|
| Compute 128 reference answers | 10.36 ms | 5.00–12.94 ms |
| Compute 512 reference answers | 18.92 ms | 16.86–34.23 ms |
| Compute 2,048 reference answers | 94.03 ms | 76.90–178.10 ms |
| Compute 384 screen/holdout answers | 14.46 ms | 12.64–33.97 ms |
| Read/decrypt/deserialize the same 384 input/answer pairs | 1.08 ms | 0.864–2.392 ms |

The cache payload was 786,944 bytes. It used local AES-GCM, an ephemeral in-memory key, associated identity bytes and a warm filesystem cache. Input/answer parity held. Wrong key, modified ciphertext and wrong associated identity each rejected. No network storage, tenant isolation, key custody, malicious-host, timing, adaptive-feedback, durability or collusion security campaign was performed. These are primitive and byte-path checks, not a claim that production answers remain secret.

The reference-stage ratio was 13.36, but reference work accounted for very little of this small learned-model pipeline. Replacing 14.46 ms with 1.08 ms saves about 0.27% of the 5.04 s phase-accounted cold FNO/0.003/400-step comparison. Cache creation is omitted from that savings bound, making it optimistic. A 16-candidate batch requires approximately 31.77 ms of one reference computation plus 16 local reads, instead of 231.35 ms for 16 reference computations; these are derived totals, not measured concurrent execution.

**Finding:** reference caching is not a priority throughput intervention for this fixture. This result cannot be transferred to an expensive CFD reference. The unqualified fast direct solver also remains a deployment baseline; this pilot demonstrates no commercially useful surrogate speedup.

### Training budget versus quality

For the FNO with learning rate 0.003:

| Training steps | Median training execution | Median phase-accounted cold comparison | Mean holdout relative-L2 across three reconstructions |
|---|---:|---:|---:|
| 25 | 0.288 s | 3.03 s | 3.162% |
| 100 | 0.684 s | 3.38 s | 0.541% |
| 400 | 2.287 s | 5.04 s | 0.201% |

Cold comparison figures are sums of measured phase times, not wall-clock measurements of Carbon end-to-end execution. They include imports/setup, batching, training/evaluation compilation, training, first inference, host measurements and fresh evaluation-reference work. They omit queueing, containers, Carbon orchestration and signed receipts, reconstruction repeats, production audits/security, and new training-reference creation. The latter took 32.04 ms for all 640 fixture labels in a separate one-off measurement; it must be allocated according to the real training-data policy.

At 400 steps, FNO/0.001 had mean holdout error 0.276%; CNN/0.001 had 2.047%; CNN/0.003 had 1.859%. All 36 records and physical diagnostics remain in `reconstruction_metrics.csv`. Some predictions violated extrema or had nonzero mass error. No production gate or physical qualification criterion was selected, and no model is reported as physically qualified.

**Finding:** the number of short builds can increase while useful prediction quality falls. Cold setup and compilation can also make a sixteenfold increase in training steps much less than a sixteenfold increase in complete build cost.

### Equal-budget replay

A labeled conditional simulation replayed random orders of the twelve measured builds. For each checkpoint budget, it completed builds until the next build did not fit a 30 s sum-of-phase-times budget. It selected the lowest screening error and measured the selected model on the distinct holdout. There were 2,000 common random orders, not 2,000 new model training campaigns.

| Steps per build | Median completed recorded builds | Median selected holdout error |
|---|---:|---:|
| 25 | 7 | 2.855% |
| 100 | 6 | 0.465% |
| 400 | 4 | 0.184% |

The longer-build schedule gave better heldout prediction quality in this finite pool despite completing fewer builds. This does not locate a live optimum: there are only four strategy settings, three seeds each, no adaptive miner behavior, no official physical admission test and no production hardware. The 400-step result remains the best observed endpoint of this grid; a true optimum could lie outside it.

### Common-case comparison diagnostic

At the 400-step checkpoint, conditional bootstrap resampling across all 66 model pairs produced these sign-disagreement rates against the 256-case holdout mean ordering:

| Screening cases resampled | Common cases for the pair | Independent cases for the pair |
|---|---:|---:|
| 8 | 4.70% | 10.35% |
| 32 | 2.87% | 5.97% |
| 128 | 1.99% | 3.95% |

This retrospective diagnostic motivates common-case comparisons, but supplies no qualified false-promotion bound or sample-size choice. The holdout order has sampling uncertainty, pairs are dependent and many comparisons are easy family separations. Repeated reconstructions and close-frontier pairs need targeted evidence. Do not shorten any official pack using these numbers.

## Translating desired exam counts into resource targets

Count **distinct completed comparisons**, not replicas, retries, checkpoint observations, early failures or API submissions. Track fully evaluated admissible candidates, conclusive mandatory failures, infrastructure/reference failures and unresolved comparisons separately.

For homogeneous candidate slots, an idealized capacity bound is:

    comparisons/day <= 1,440 * effective_slots * availability / candidate_slot_minutes_per_comparison

Required repeated reconstructions, inference, audit and finalization work belong in the per-comparison resource demand. For separate reference workers:

    comparisons/day <= 1,440 * reference_slots * reference_availability / amortized_reference_slot_minutes_per_comparison

Use the minimum of these and other resource-pool bounds, constrained by eligible candidate supply. Add demands before applying the capacity limit when stages share the same resource pool. Utilization near the limit, bursty arrivals and reference failures can enlarge queue delay; neither expression predicts end-to-end tail latency.

Illustrative 75% availability, with the full candidate-side occupancy including required repeats:

| Candidate slots | Occupancy allowed for 100 comparisons/day | Occupancy allowed for 200 comparisons/day |
|---|---:|---:|
| 1 | 10.8 min | 5.4 min |
| 4 | 43.2 min | 21.6 min |
| 8 | 86.4 min | 43.2 min |
| 16 | 172.8 min | 86.4 min |

The 75% value is an arithmetic scenario, not a selected safety factor. If three rebuilds consume the entire allowance, divide the second and third columns by three; any other candidate-side work reduces the remainder. A slot must name its hardware and concurrency entitlement. These values are targets to profile against, not measured live capacity.

### Expensive-reference sensitivity

A synthetic scenario assumes one reference worker needs two hours per common reference batch, four candidate workers need 30 minutes per comparison, both pools have 75% availability, and arrivals are 100 candidates/day. No validation/security benefit is assumed.

| Committed cohort | Idealized system capacity/day | Arrival-limited completed rate/day | Mean cohort-fill delay alone |
|---|---:|---:|---:|
| 1 | 9 | 9 | 0 h |
| 4 | 36 | 36 | 0.36 h |
| 16 | 144 | 100 | 1.80 h |
| 64 | 144 | 100 | 7.56 h |

This is a computed sensitivity model, not an industrial measurement or a queue simulation. At cohorts 1 and 4, arrivals exceed service capacity so a persistent queue is unstable without admission control. At 16, the reference and candidate pool capacities match. At 64, reference capacity increases but candidate capacity does not; cohort-fill delay increases and a larger group faces shared evidence. Under these assumptions, 64 provides no throughput advantage over 16. A different solver cost, worker allocation, arrival process or reuse policy changes the result.

## Finding the productive operating point

Optimize the rate of independently supported improvement on a specified Challenge, subject to mandatory scientific evidence, resource capacity and an acceptable feedback delay. Record raw throughput alongside quality; do not select an arbitrary product of uncalibrated probabilities or convert this research objective into an official score.

The next real-path campaign should use the actual admitted catalog, reference and evidence path on target hardware. Freeze each comparison protocol before exposure to protected instances. Sweep construction budgets and worker allocations across separate prospective development profiles. Keep the required evidence fixed within each profile; compare any proposed alternative exam sizes or repetition policies through a separate qualification campaign.

Randomize independent repeated search campaigns at equal total resources, log agent/strategy proposals and actual queue arrival patterns, and assess selected models on common fresh holdouts. Measure completed unique comparisons/day, useful complete evidence/day, time to a registered target, supported frontier gain, ranking uncertainty, p50/p95 feedback delay, failures, fresh-reference throughput and total resource consumption. Report p95 only when sample support is defensible; summing stage p95 values is not an end-to-end percentile.

Use the resulting learning and service curves to identify a non-dominated operating region. Select a profile only after the intended physical resolution and service needs are supported. A fast screening/practice path may help propose candidates but must remain non-authoritative and cannot give an official nonzero result using reduced evidence.

## Limitations and execution history

One tool call running five sequential processes hit its outer wall limit before the last process produced a result. Four complete results were retained; only the missing configuration was rerun. `execution_events.jsonl` retains that event. No scientific outcome was assigned to the interrupted run. All twelve planned configurations then completed, with about 82.50 s total recorded process time across those successful runs. This excludes interruptions and analysis and is not an operational cost estimate.

The cache pilot tests primitive rejection only. A bounded-cohort confidentiality experiment with real custody, candidate isolation, collusion and cumulative-feedback attacks remains outstanding. A fit page must not call this pilot a secure cache or a measured production exam rate.

No production thresholds, solver tolerances, Challenge population, sample plan, admission criteria, cohort limit or max runtime follows from this report.

## Reproduction and artifacts

Run `reference_pilot.py`, then `reconstruction_pilot.py` separately for each Cartesian product of families `{compact_fno,periodic_cnn}`, seeds `{11,22,33}` and learning rates `{0.001,0.003}`; finally run `analyze.py`. `run_all.sh` automates the sequence for a provisioned local environment. Research seeds are public and exact. Source and artifact hashes are in `manifest.json`. JSON/CSV files retain raw timings, checks, learning curves and conditional analyses. Re-execution can change timing; the stated software/CPU profile matters.

External primary sources used for method context:

- JAX benchmarking: https://docs.jax.dev/en/latest/benchmarking.html . Supports synchronized timings, compilation and transfer accounting; not a Carbon performance claim.
- FNO paper: https://arxiv.org/abs/2010.08895 . Architecture inspiration only; this is not its official implementation or reproduction.
- Hyperband: https://arxiv.org/abs/1603.06560 . Supports studying breadth/depth allocation; its adaptive pruning is not authorized for Carbon's mandatory official pack.
- Weak numerical baselines: https://arxiv.org/abs/2407.07218 . Supports retaining credible non-ML alternatives; not a measured advantage of this fixture.
- Carbon resource policy: Design_Specs/Research_Resource_Policy_Contract.md; truth/measurement/distribution qualifications remain controlled by Carbon's respective domain specifications and scientific canon.
