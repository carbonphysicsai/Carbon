# Carbon operating-point pilot v0.2: measured search campaigns

**Date:** 11 September 2026

**Evidence class:** public CPU research measurements, conditional diagnostic resampling and labeled queue scenarios. No LIVE exam, physical/security qualification, production capacity or optimal production comparisons/day.

## Result

A 400-step construction profile had the lowest development geometric mean outer error at a fixed 12-second steady-worker research horizon. The script locked that choice before evaluating the confirmation blocks. On four confirmation blocks:

| Steps per candidate | Median complete candidates in 12 s | Mean selected outer relative-L2 | Geometric mean selected error |
|---:|---:|---:|---:|
| 100 | 22 | 0.454% | 0.453% |
| 400 | 5 | 0.258% | 0.255% |
| 1600 | 1 | 0.917% | 0.698% |

The 400/100-step paired geometric error ratio was 0.563, with a diagnostic Student-t 95% interval of 0.470–0.675 under approximately normal paired log ratios. For 400/1600 steps it was 0.366, with interval 0.065–2.049. Four blocks do not establish a general superiority guarantee. The deepest profile won one of the four paired confirmation comparisons.

The selected operating point changed with the horizon. At four seconds, the 100-step profile had mean selected outer error 0.541%, versus 1.105% at 400 steps. None of the 1600-step campaigns completed a candidate by four seconds; the reported baseline error remains in the analysis rather than dropping those campaigns. At eight seconds, the 400-step mean was 0.360%, versus 0.460% for 100 steps.

This is an interior best-tested setting on this grid for this proposal stream, worker mode and objective. It is not a global optimum or a production recommendation. The earlier pilot's deepest tested setting won; the new experiment demonstrates that the answer can change after including search breadth and a fixed elapsed deadline.

## Executed design and replication units

The locally timestamped protocol and implementation hashes preceded new numerical execution. There were 28 timed campaigns in eight paired blocks: three construction depths in each of four development and four confirmation blocks, plus a feedback-guided 400-step policy on the four confirmation blocks. Each campaign received a 12-second steady-worker allowance and reporting horizons of 4/8/12 seconds.

The catalog had 32 distinct configurations: two small model families, eight learning rates and two decoupled weight-decay values. Random policies sampled configurations without replacement and used a common proposal order within each block. Matched profiles shared initial seed/training-case identities for matched configurations, but each actual build recreated weights and optimizer state. These are paired observations, not 28 independent scientific replications. New blocks had new training, screening, proposal and initialization realizations.

The runs attempted 276 candidate reconstructions, completed 248 finite diagnostic builds and retained 28 censored/late attempts. Twelve additional fresh reconstructions of confirmation finalists measured reconstruction sensitivity. These checks were outside the inner campaign allowance; a real profile requiring them must charge their recurring cost. They are not twelve extra proposed strategies.

No model or candidate controls the outer evaluator. The search function receives only training and screening data. It locks nominations before the separate analyzer generates or evaluates outer cases. Development profiles use development outer evidence for selection; the four confirmation blocks supply the subsequent check. All material is public research data, and this software role separation is not a security qualification.

## Physical regime, equations and numerical evidence

The fixture retains the prior pilot's scalar viscous Burgers equation u_t + (u^2/2)_x = nu*u_xx on periodic [0,1], zero-mean smooth four-mode Fourier initial data, nu=0.005 and final time 0.25. Coefficients are Gaussian with k^-2 weighting and rescaled to a sum of absolute coefficients uniform on [0.1,0.3]. These are analyst-selected development settings inherited for comparison, not approved Carbon population semantics. Candidates receive the 128-point initial state and return a 128-point final state.

Each build generates 256 fresh training labels. Each paired block uses 128 common screening cases and a separate set of 512 outer cases. Eight blocks therefore provide 4096 outer physical cases, but only four independent confirmation blocks for comparing selected profiles.

Reference calculation uses the same float64 periodic Cole–Hopf heat evolution at 1024 points with 2048-point refinement. The maximum discrepancy on the new outer sets was 4.07e-14. A centered conservative finite-difference/RK4 witness on eight fresh cases had mean relative disagreements 0.000375589, 9.39244e-05, and 2.34828e-05 at 128/256/512 cells. Approximately fourfold refinement reductions support bounded numerical consistency on these smooth cases, not full uncertainty qualification. The witness shares authorship, physical assumptions and hardware.

Models use the prior compact FNO-inspired network (19297 parameters) and periodic CNN (3937 parameters), width 16, depth 3, residual outputs, batch size 32 and float32 Adam-style learning, with optional decoupled weight decay. This is not Harshdeep's library and not a parameter-matched family comparison. Relative-L2, mass, energy and extrema diagnostics are retained. No mandatory physical thresholds were selected; therefore none of the 248 completed builds is called physically admissible or qualified. A final-state task does not permit calling a spatial-only diagnostic a complete PDE residual.

## Clock and hardware boundaries

Device: ['TFRT_CPU_0']; Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz; two logical CPUs per worker within a four-CPU container quota; JAX 0.9.0.1, NumPy 2.3.5, SciPy 1.17.0. The host is shared. The measured initial worker setup and compilation took 7.466 seconds and remained outside steady-worker campaign clocks. New weights and optimizer state were created each time. Timings synchronize device work. Warm executable reuse is a research operating mode, not a qualified production cache.

Each campaign clock includes fresh screening reference generation, per-build training cases/references, new-state and batch preparation, training, screening predictions, host diagnostics and copying the artifact to host memory. JSON/NPZ persistence, signed Carbon receipts, orchestration, network transport, isolation, audits, outer reporting, extra finalist rebuilds and cold worker starts are outside that clock. The new figures are not directly comparable to the previous pilot's cold phase-accounted totals.

Checks every 25 steps bounded deadline overshoot; the largest observed overshoot was 0.143 seconds. No candidate finishing after the deadline could enter selection. That overshoot still consumed resources and remains in the trace. Total search-plus-finalist-rebuild process wall time was 388.30 seconds, separate from later audit, analysis and queue simulation work. This is not a billable production estimate.

## Additional findings

**Proposal quality matters.** The simple feedback-guided 400-step proposer completed a median five candidates and had mean selected outer error 0.322%, versus 0.258% for random search on the matched confirmation blocks. This small hand-coded policy is not an LLM agent or a general adaptive-search benchmark. It did not beat the baseline in this run, so guidance should earn prospective value rather than enter productivity estimates as an assumed multiplier.

**Fresh reconstruction can change the answer.** Mean outer errors of the selected recipes after one additional fresh initialization and training set were 0.544%, 0.222%, and 0.811% at 100/400/1600 steps, versus original selected-artifact means of 0.454%, 0.258%, and 0.917%. One rebuild per finalist is a sensitivity observation, not a variance qualification. The middle profile retained the strongest average in this check.

**Case count and decision risk require their own study.** On the four 400-step random confirmation pools, 200 conditional resamples per pool selected something other than the outer-pool best 4.75% of the time at 8 screening cases, 0.25% at 32, and 0% at 128. This is finite-pool resampling against an uncertain 512-case comparator. It is not a false-promotion probability or justification to select 32 cases. Near-frontier methods, correlated outputs, mandatory failure controls and reconstruction variation need explicit qualification.

**Orchestration changes the allocation.** Counterfactual finite-trace replays adding one second per candidate reduced mean 12-second completions from 22 to 7 for 100 steps and from 5.25 to 3.25 for 400 steps. Corresponding selected mean errors became 0.541% and 0.360%. These are scenario replays of fixed completed traces, not new timed runs or estimates of Wave C overhead. Unobserved candidates and deadline-censored outcomes cannot be reconstructed from the trace.

## Queue/cohort study: simulations kept separate

A secondary plan specified a one-candidate-worker/one-reference-worker FIFO queue, Poisson arrivals at 0.25/s, a 300-second horizon, cohort caps 1/2/4/8 and a 30-second fill cap. One hundred paired simulations per configuration used empirical complete-build durations. The complete-service approximation, synthetic arrivals and synthetic slower reference times are explicit limitations. Incomplete arrivals at the horizon remain counted; completed-only latency is labeled conditional.

For the 400-step profile, using the observed mean screen-reference stage of about 0.0103 seconds, cohort 1 completed a mean 74.67 arrivals with 3.11-second mean completed feedback; cohort 8 completed 70.09 with 21.59-second feedback. Waiting to batch was counterproductive in this scenario.

When reference-batch time was replaced by a hypothetical 16 seconds, cohort 1 completed 17.85 with 119.75-second completed feedback, while cohort 8 completed 66.29 with 37.57-second feedback. This is a sensitivity scenario, not measured industrial reference performance. It shows why the same batching policy cannot be assumed optimal for both reference regimes. The largest tested cohort remains an endpoint, not a qualified optimum; real supply/feedback coupling is absent.

No new cryptographic cache, custody, malicious-host, candidate-egress or adaptive-disclosure security experiment was executed. Reference sharing remains a separately qualified design.

## Limits and next decision

We can call 400 steps the best-tested 12-second profile for this fixture and random proposal process. We cannot supply an optimal production exams/day value. Only one easy physical regime, two small families, four confirmation blocks and a steady CPU worker were tested. There is no qualified physics acceptance rule, real miner supply, actual Carbon evidence path, actual GPU throughput, or customer workload.

The production study should choose an operating region by measured supported progress, then derive its daily completion rate under a declared hardware/spending budget and arrival process. Use the framework in FRAMEWORK.md and the blank challenge_profile_template.json. No production thresholds, samples, repetition count, reuse limit, population or runtime follows from these numbers.

## Execution repair and tests

The first interactive-shell launch mechanism was unavailable and started no numerical work. The process then ran through ordinary local subprocess execution. All 28 campaigns and 12 finalist rebuilds completed; partial candidates remained in their original traces.

The analyzer wrote all raw arrays and CSVs, then failed serializing a NumPy integer in its JSON summary. The repair converted that scalar to a Python integer and reconstructed the summary from existing CSVs. No model training, timing measurement or witness result was repeated or replaced. Both source hashes and the failure remain in execution_events.jsonl and analysis.log.

verify_study.py checks campaign coverage, distinct configurations, deadlines, complete-versus-censored status, nomination integrity, phase accounting, data shapes, heldout means, development/confirmation separation and zero-overhead replay consistency. Six queue unit tests cover FIFO, reference readiness, fill delays, batch sharing, cutoff occupancy and an empty workload. These tests establish bounded calculation and bookkeeping behavior, not scientific or security qualification.


---

# Carbon Challenge Operating-Point Study

**Version:** 0.2 | **Date:** 11 September 2026

**Status:** proposed research framework with public CPU pilot evidence. Not an official exam, a qualified operating profile, an optimal production exam count, or deployment permission.

## 1. Decision this study supports

For a proposed physical job, find the operating policy that produces the best independently checked progress under a declared research budget and calendar horizon. Report the resulting completed comparison rate as an output. Do not start by assuming 100–200 comparisons per day, and do not optimize that count in isolation.

An operating policy includes reconstruction allowance, a separately qualified evidence plan, required rebuilds, candidate/reference worker allocation, batching, cache state, admission, and proposal/feedback behavior. A count has no unique optimum without a hardware/spending boundary, an intended scientific decision, a time horizon and a proposal supply model.

For a single declared lower-is-better scientific objective L, a research formulation is:

    p* = argmin over feasible policies p of E[L(selected artifact at horizon H under budget B, policy p)]
    q* = E[complete distinct comparisons by H under p*] / H

Scientific admissibility, reference adequacy, secrecy, information access and decision resolution constrain the feasible set. Mandatory physics failures cannot enter the feasible frontier. L is a Challenge-owned estimand, not a new universal score. When no scalar objective or preference is authorized, return non-dominated operating profiles and their uncertainty. Do not manufacture a unique winner with arbitrary weights.

The experiment must count strategy comparisons, artifacts, reconstruction replicas, failed attempts, censored attempts and checkpoints separately. Multiple seeds are not multiple proposed methods. Improvement should concern the retained frontier or a job-relevant target; counting tiny frontier events can reward measurement noise or incremental reporting.

## 2. Four records, kept separate

| Record | Contents |
|---|---|
| Upfront qualification | Integration/qualification expenditure, onboarding elapsed time, unresolved scientific/security/rights risks and evidence needed to activate the exam |
| Recurring operation | Fresh construction labels, rebuilding, reference refresh, inference, measurements, evidence finalization, required audits/replicas/retries, worker occupancy, queues and complete comparisons |
| Discovery productivity | Independently checked frontier quality at fixed resources/horizon, time to a registered target, selection regret, inconclusive outcomes and feedback delay |
| Client value | Acceptable physical outputs, deployment cost/latency, credible baseline, workload, escalation and lifecycle evidence |

Scientific qualification expenditure does not enter the live stopwatch. Worker startup and compilation are operating costs, not scientific qualification; warm-worker experiments must disclose their exclusion and measure cold starts separately. Reference refresh and requalification remain visible events in the relevant operating/lifecycle record. A lifetime economic calculation may combine costs without collapsing the four records.

## 3. Reusable experiment outline

### A. Specify the job and the decision

Bind the physical system, causal inputs, outputs, envelope, target/proposal distributions, reference policy, measurements, intended resolution, information allowance, baseline/incumbent, hardware, spending, research horizon, and proposal source. Name the scientific and operational owners. Missing required values prevent live-profile approval, not bounded public feasibility probes.

Keep the cheapest acceptable deployable numerical method in the client-value comparison. A fast reference may itself be the appropriate client solution. Reference speed alone neither establishes nor refutes a useful surrogate opportunity.

### B. Check the measurement system before optimizing its throughput

Use analytic/manufactured cases and numerical refinement where applicable, role-qualified witnesses, and physical/experimental validation needed for the intended claim. Characterize reference, representation and measurement uncertainty by relevant stratum.

Study proposed evidence plans on calibration cases using near-frontier contenders, repeated reconstructions and known failure controls. Include controls that violate mandatory physical behavior, not just grossly different neural architectures. Estimate decision uncertainty at the intended superiority resolution. Population samples, independent reconstructions and cases within a trajectory are different replication units.

Alternative exam sizes, repetition counts or reference fidelities are separate prospective qualification experiments. They are not permission to shorten the mandatory pack for an individual live candidate. The owners approve an evidence plan before it can produce official results.

### C. Measure the complete execution path

Record start/finish events, wall time, CPU/GPU occupancy by hardware class, memory, fresh labels, reference work, startup/compilation, inference, measurements, receipts, retries and failures. Trace queueing and overlapping stages; do not add stage p95 values and call the sum an end-to-end p95.

Run cold and warm paths and controlled concurrency profiles. Hold total hardware/spend fixed when comparing allocation policies. A cache hit must identify exactly which computation it replaces and preserve case/reference identity. Resource or infrastructure timeouts are not physical-law violations. Incomplete evidence earns no positive official result.

### D. Run equal-resource search campaigns

Sweep a small set of construction depths and permitted operational configurations. Use a randomized or blocked order to reduce host/load/time confounding. Include random search as a baseline and at least one representative feedback-sensitive proposal process when available. Real agent compute and proposal latency belong in the budget if the comparison concerns the whole discovery system.

Use fresh campaign-level blocks. Within a matched block, common cases and common proposal seeds can improve comparisons, but results then remain paired rather than independent. Every candidate starts with its own permitted reconstruction; sharing compiled kernels does not authorize sharing trained weights.

Retain the best candidate selected by the permitted inner evidence at the reporting horizons. Assess it on a separate outer test that never guides candidate generation or selection. A campaign with no complete candidate retains the declared incumbent/baseline and counts as a censored/no-improvement outcome; do not silently drop it.

Optimize quality at the declared deadline or time to a client-relevant target, subject to physical acceptance. Record completed proposals and feedback latency alongside quality. A high count with weak comparisons, many redundant proposals, or no available headroom is not strong productivity.

### E. Lock a proposed profile and confirm it

Use development campaigns to choose a profile or operating band. Lock that decision, then evaluate it on untouched confirmation campaigns and physical cases. Report paired campaign dispersion and reference/reconstruction uncertainty. The number of cases is not the number of independent campaigns; simulated replays do not create independent scientific evidence.

The output can be BEST_TESTED_ONLY, a supported operating region, unresolved alternatives, or infeasibility under the stated scope. An endpoint winner requires expanding the experimental range. An interior winner still requires uncertainty and confirmation checks; it is not a proof of global optimality. Stop when the responsible owners' decision-resolution and resource criteria are met, not at an invented universal repeat count.

### F. Fit and challenge the operating model

Estimate service/capacity models from measured traces. Validate forecasts on withheld traces, loads and later real runs. Include arrival rate, burstiness, proposal quality/correlation, worker contention, repeated reconstruction, reference failures and feedback delay. A fixed candidate pool or a fixed-rate Poisson arrival model cannot establish the effect of delay on an adaptive miner population.

For protected-reference sharing, compare bounded committed cohorts and waiting-time policies under the same scientific requirements. Hold candidate proposals fixed before their common protected evidence becomes knowable. Model persistent reference reservoirs as a different policy requiring custody, sampling, freshness, disclosure and exhaustion evidence. This study does not qualify that security.

## 4. How internal history improves Carbon Fit

Store context and provenance before predicting fit: physical job and geometry/BC class, declared distributions, quantities of interest, permitted information, reference/measurement identities, model construction, resource class, proposal policy, clock boundary, censoring, maturity and rights.

A proposed Challenge then receives two judgments: evidence to qualify its exam, and its measured/forecast operating region. Compare it against historical studies only when those contexts are compatible. Candidate similarity or an embedding is not a scientific applicability test.

Useful cross-study features include reference occupancy per relevant resource class, construction learning-curve shape, reconstruction dispersion, near-frontier decision resolution, candidate supply, feedback sensitivity and prediction-versus-measured operating cost. Report measurement source and uncertainty for each.

With enough eligible history, compare cost/productivity forecasts against a simple no-history or engineering-estimate baseline on held-out Challenges or clients. An out-of-support proposal receives an explicit unknown and a targeted experiment, not an invented confidence percentage. The present dataset contains one easy physical regime and cannot train a defensible universal Carbon-fit predictor.

Qualification risk and commercial desirability remain distinct from scientific performance. A reference that is cheap, accurate and deployable can remove the acceleration opportunity without making an Evidence Audit pointless. Strategy owns product prioritization; Science owns the evidence claim; Engineering owns implementation.

## 5. Wave C comparison

Preserve this public prototype and its raw results. After Wave C, use three separate comparisons:

1. Same-fixture compatibility: run the same bounded physical mapping and scientific diagnostics through the real construction/reference/measurement/evidence path on matched hardware. Attribute overhead only when the workload, policy, cache state and timing boundaries match.
2. Real proposed Challenge: use its actual admitted catalog, reference policy, input information, scientific measurements and resource profile. This is new contextual evidence, not an apples-to-apples replacement for the prototype.
3. Fresh confirmation: retain public fixtures for regression, but use new campaign blocks and unexposed cases to test scientific generalization and the chosen operating policy.

Record predicted versus actual complete comparisons, feedback latency, uncertainty, reference/reconstruction failures and resource occupancy. A CPU-to-GPU comparison does not isolate a software effect. Completing Wave C permits real-path characterization under its authorization; it does not by itself qualify a LIVE exam.

`compare_studies.py` performs descriptive comparisons and warns about changed hardware, scientific/search inputs, clock boundaries and reused public blocks. The real backend must export the same study records through an Engineering-owned adapter; that adapter is not implemented here.

## 6. Primary-source context

- NIST experimental optimization: https://www.itl.nist.gov/div898/handbook/pri/section5/pri53.htm . Supports sequential local response-surface studies with uncertainty; does not supply Carbon thresholds or a universal optimum.
- Li et al., Hyperband: https://jmlr.org/papers/v18/16-558.html . Supports investigating breadth/depth allocation. Adaptive training search is not authority to prune a mandatory official exam.
- Bergstra and Bengio, random search: https://www.jmlr.org/beta/papers/v13/bergstra12a.html . Supports random search as an experimental baseline; no universal Carbon superiority claim.
- Cawley and Talbot, model-selection bias: https://www.jmlr.org/beta/papers/v11/cawley10a.html . Supports separating model/profile selection from evaluation.
- JAX benchmarking: https://docs.jax.dev/en/latest/benchmarking.html . Supports compilation, transfers, precision and synchronization accounting, not a production speed estimate.

Carbon source owners remain the scientific canon, InstanceDistributionContract/SamplingPlan, Validation Dossier, reference, measurement, resource, security/disclosure and product-evidence specifications. This research package changes none of their production semantics.

## 7. Deciding whether the data are sufficient

Before the confirmatory campaign, Science and Operations name the smallest profile difference that would change the decision, the acceptable uncertainty or error-control policy, the resource boundary, and the important strata. These are prospective owner inputs, not numeric defaults from this pilot.

Use development measurements of paired campaign dispersion, reconstruction variation, case/trajectory dependence, reference uncertainty and censoring to plan the next sample allocation. Simulate the actual selection procedure when it chooses among many profiles; a per-pair interval need not control the error of selecting the best of a large grid. Retain a separate confirmation cohort and respect any approved sequential stopping rule.

Collect additional evidence when it could change the next spending decision: resolve a reference uncertainty that exceeds the intended comparison resolution, distinguish nearby profiles, cover a missing high-consequence stratum, or test a queue forecast under representative load. When uncertainty spans practically equivalent alternatives, return an operating band rather than keep searching for a meaningless decimal winner. An unmeasured risk stays unknown even when timing is precise.

The four confirmation blocks in this pilot support a bounded development finding. They do not set the future number of campaigns, reference cases or reconstruction replicas. Internal historical data can improve these allocations only after the resulting forecasts demonstrate held-out accuracy in compatible contexts.
