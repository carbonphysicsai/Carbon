# Carbon Challenge Operating-Point Study

**Version:** 0.2 | **Date:** 11 September 2026

**Status:** working research evidence and Engineering requirements. This document does not select an active ticket, change the mandatory exam, qualify physics/security, authorize a production rate, or add a mainnet dependency.

**Related:** [Runtime Profiles](RUNTIME_PROFILES.md), [first throughput pilot](LIVE_THROUGHPUT_BASELINES.md), [decision method](DECISION_METHOD.md), [reference reuse](PROTECTED_REFERENCE_REUSE.md), [client tool](CLIENT_FIT_TOOL.md), and PR #140 / GOV-FIT-01.

## 1. Owner question and decision

Find the operating policy that produces the most independently supported scientific progress for a proposed Challenge under a declared resource allowance and calendar horizon. Do not assume 100–200 exams per day. Derive the completed-comparison rate from the selected policy.

An operating policy can bind reconstruction allowance, a separately qualified evidence plan, required rebuilds, worker allocation, batching, cache state, admission and proposal/feedback behavior. The intended physical decision, hardware/spend, research horizon and proposal supply must be explicit. Without those inputs, no unique rate has a scientific meaning.

For a declared lower-is-better scientific objective L, a research formulation is:

    p* = argmin over feasible p of E[L(selected candidate at H under B and policy p)]
    q* = E[complete distinct comparisons by H under p*] / H

Physical admissibility, reference adequacy, secrecy, permitted information and decision resolution constrain feasibility. Mandatory physical failure cannot be compensated by throughput or lower predictive error. L remains Challenge-owned; this formulation creates no universal score or reward rule. When the owner has not selected a scalar objective/preference, return non-dominated operating profiles with uncertainty.

Keep four records separate:

| Record | Meaning |
|---|---|
| Upfront qualification | Integration/qualification expenditure, onboarding time, unresolved scientific/security/rights risks |
| Recurring operation | Fresh labels, reconstruction, references, inference, measurements, receipts, required repetitions/audits/retries, worker occupancy and queueing |
| Discovery productivity | Independently checked frontier quality at a fixed budget/horizon, time to target, unresolved decisions and feedback delay |
| Client value | Acceptable physical outputs, deployment cost/latency, baseline advantage, workload and lifecycle |

Do not amortize upfront scientific qualification into the live stopwatch. Worker startup and compilation remain operating costs; a steady-worker study must disclose their exclusion and profile them separately. Reference refresh and requalification remain visible events. Replicas, checkpoints, retries and repeated seeds are not new proposed strategies.

## 2. Executed v0.2 pilot

The user authorized further bounded experiments before Wave C completes. The current repository still describes bounded C1 work, not a qualified live exam. The available local hardware was CPU. The experiment used standalone public research code, not Carbon production code, Harshdeep's unavailable JAX library, public-network execution or paid external compute.

A local timestamped protocol and source hashes preceded execution. This is a prospective local research record, not external registration or qualification.

### Physical scope and reference

The fixture retains v0.1's Burgers equation u_t + (u^2/2)_x = nu*u_xx, periodic [0,1], zero mean, nu=0.005 and T=0.25. Initial conditions have four smooth Fourier modes with Gaussian coefficients weighted k^-2 and rescaled to sum(abs(coefficients)) uniform on [0.1,0.3]. These values are inherited development settings, not approved production populations or limits. Each candidate receives a 128-point initial field and predicts the final field.

Each actual build generates 256 fresh training labels. A paired campaign block shares 128 screening cases and uses a separate 512-case outer set. The reference uses float64 periodic Cole–Hopf heat evolution at 1024 points with a 2048-point check. The maximum refinement discrepancy on 4096 new outer cases was 4.074e-14. A centered conservative finite-difference/RK4 witness on eight fresh cases had mean discrepancies 3.7559e-4, 9.3924e-5 and 2.3483e-5 at 128/256/512 cells. The witness shares author, assumptions and hardware; this is bounded consistency evidence, not independent reference qualification.

### Search and replication

The study ran 28 timed campaigns in eight paired blocks: three construction depths across four development and four confirmation blocks, plus a simple feedback-guided 400-step policy on the four confirmation blocks. Each campaign had a 12-second steady-worker allowance, with observations at 4/8/12 seconds.

The catalog contained 32 configurations: compact FNO-inspired and periodic CNN families, eight learning rates, and two decoupled weight-decay settings. The models retain v0.1's 19297 and 3937 parameters, width 16, depth 3, residual outputs, batch size 32 and float32 learning. This is not a parameter-matched family comparison. Random search samples without replacement. Matched profiles share proposal order and reconstruction seed/data identities for matched configurations, but each build initializes fresh weights and Adam state. Their observations remain paired, not independent.

The runs attempted 276 candidate builds, completed 248 finite diagnostic builds and retained 28 censored/late attempts. Twelve additional fresh finalist reconstructions measured sensitivity to new initialization and training data. The extra rebuilds are outside the inner campaign budget; a real recurring policy requiring them must charge them.

The inner search never receives outer data. It locks artifact nominations before the analyzer creates/evaluates outer cases. The analyzer selects the best development profile, records that choice, then opens confirmation results. Conditional resamples and queue simulations do not add independent scientific campaigns.

### Main result

Development geometric-mean outer error at 12 seconds selected the 400-step profile. Four confirmation blocks gave:

| Steps per candidate | Median complete candidates in 12 seconds | Mean selected outer relative-L2 | Geometric mean selected error |
|---|---:|---:|---:|
| 100 | 22 | 0.454% | 0.453% |
| 400 | 5 | 0.258% | 0.255% |
| 1600 | 1 | 0.917% | 0.698% |

This gives an interior best-tested setting on this grid and proposal process. It is not a global or production optimum. The paired geometric error ratio for 400/100 steps was 0.563; a diagnostic Student-t 95% interval on paired log ratios was 0.470–0.675. For 400/1600 steps it was 0.366, with a wide interval 0.065–2.049. Four blocks do not establish a calibrated superiority guarantee. The deepest profile won one confirmation block.

The preferred setting changed with the horizon. At four seconds, mean selected outer error was 0.541% for 100 steps and 1.105% for 400 steps. No 1600-step candidate finished by four seconds; the analysis retains the persistence baseline rather than dropping those campaigns. At eight seconds, the 400-step mean was 0.360%, versus 0.460% for 100 steps.

The simple feedback-guided policy had a 0.322% mean at 400 steps/12 seconds, versus random search's 0.258%. It is not an LLM-agent test and provides no general claim against adaptive search. It shows why guidance cannot enter capacity/value estimates as an assumed multiplier.

One additional fresh reconstruction per selected confirmation recipe gave mean errors 0.544%, 0.222% and 0.811% for 100/400/1600 steps. This is a sensitivity check, not sufficient reconstruction-variance qualification.

### What the clocks include

The worker used two logical CPUs on an Intel Xeon Platinum 8370C within a four-CPU container quota, JAX/jaxlib 0.9.0.1, NumPy 2.3.5 and SciPy 1.17.0. Timings synchronize device work. Initial setup/compilation took 7.466 seconds outside steady-worker campaign clocks. No trained weights were reused.

Each campaign includes fresh screening references, new training references/data, fresh-state/batch preparation, training, screening prediction, host diagnostics and artifact copying. JSON/NPZ persistence, cold starts, Carbon orchestration/receipts, network transport, isolation, formal audits, outer reporting and extra rebuilds are outside. These are not live Carbon runtime measurements and not comparable to v0.1's cold phase sums without aligning boundaries.

Deadline checks every 25 steps produced a maximum observed overshoot of 0.143 seconds, retained as resource use. No late candidate entered selection. Total search-plus-rebuild process wall time was 388.30 seconds, excluding subsequent analysis and queue work. No physical gate thresholds were selected. Mass, energy and extrema diagnostics remain recorded; no candidate is physically qualified.

### Secondary diagnostics and scenarios

Two hundred conditional resamples of each 400-step random confirmation candidate pool selected something other than the uncertain outer-pool best 4.75% of the time with eight screening cases, 0.25% with 32, and 0% with 128. These are finite-pool diagnostics, not false-promotion probabilities or permission to select 32 official cases. Near-frontier candidates and physical-failure controls need a separate resolution study.

Finite-trace replays adding a hypothetical one second per candidate reduced mean 12-second completions from 22 to 7 for 100 steps and from 5.25 to 3.25 for 400 steps. These are scenario replays, not measured Wave C overhead.

A separate planned queue simulation used one candidate worker, one reference worker, Poisson arrivals 0.25/s, a 300-second horizon, cohort caps 1/2/4/8 and a 30-second fill cap. One hundred paired simulations used empirical complete-build durations. Synthetic arrival assumptions, complete-service sampling and synthetic slower references remain limitations; unfinished arrivals stay counted.

At 400 steps and the observed mean screen-reference stage of 0.0103 seconds, cohort 1 completed a mean 74.67 arrivals with 3.11-second mean completed feedback; cohort 8 completed 70.09 with 21.59-second feedback. When reference time was replaced by a hypothetical 16 seconds per batch, cohort 1 completed 17.85 with 119.75-second completed feedback, versus cohort 8's 66.29 and 37.57 seconds. The latter is not an industrial timing measurement. Completed-only latency is conditional; the largest tested cohort remains an endpoint, not an optimum.

No new cache confidentiality/custody/adaptive-leakage qualification was performed. The protected-cohort design remains subject to its separate security and scientific reviews.

## 3. Reusable proposed-Challenge experiment

1. Define the job, baseline, permitted information, scientific objective/resolution, resource allowance, horizon and proposal source. Keep qualification cost/risk separate.
2. Verify the reference and measurement system to the intended claim depth. Calibrate alternative evidence plans on development cases using close contenders, repeated reconstructions and known mandatory-failure controls. Owners approve any plan before official use.
3. Measure the full real path, including cold/warm starts, worker occupancy, inference, references, receipts, contention, retries and failures. Hold total resources fixed when comparing worker allocations. Do not add stage p95 values to infer end-to-end p95.
4. Run blocked, equal-resource search campaigns over a small operating grid. Include a random baseline and a representative feedback-sensitive proposer. Keep the full registered mandatory exam within each comparison. Count incomplete work; retain the incumbent when no candidate finishes.
5. Select a profile on development campaigns, freeze the choice and confirm it on fresh campaigns and cases. Report uncertainty and inconclusive outcomes. An endpoint winner requires extending the grid; an interior winner still needs confirmation.
6. Fit service/productivity models to traces, test predictions on held-out workloads, and return a supported operating region plus predicted comparison rate. A finite fixed-rate simulation cannot establish the interaction between delays and an adaptive miner population.

Return BEST_TESTED_ONLY or an unresolved band when evidence does not support a sharper decision. No universal repeats, error tolerance, safety multiplier, sample size or runtime follows from this proposal.

## 4. Internal data and Carbon Fit

Store physical/geometry/BC regime, distributions, quantities of interest, reference and measurement identities, permitted information, construction, resources, proposal behavior, clock boundary, censoring, maturity and rights. Preserve qualification cost/risk, operating performance, discovery productivity and client value separately.

Compare a new proposal with compatible historical studies, not a global score or an embedding alone. Useful context features include reference demand by resource class, construction learning curves, reconstruction dispersion, near-frontier resolution, supply and feedback sensitivity. A single easy Burgers regime cannot train a defensible universal fit predictor.

With sufficient eligible history, test forecasts on held-out Challenges or clients against engineering/no-history baselines. Out-of-support proposals retain UNKNOWN and a targeted next experiment. Landscape proposes experiments; it does not define truth, modify the live exam or certify its own recommendations.

## 5. Wave C rerun contract

Preserve three separate comparisons:

- Same-fixture compatibility through the real construction/reference/measurement/evidence path on matched hardware, policy, cache state and clock boundaries.
- The actual proposed Challenge with its admitted catalog and scientific contracts. This is new context, not an automatic replacement for prototype measurements.
- New confirmation blocks and unexposed cases. Public fixtures remain regression evidence, not fresh confirmation.

Compare predicted versus actual completed comparisons, feedback delays, resource occupancy, reference/reconstruction failures, and independently checked progress. CPU-to-GPU changes do not isolate a software effect. Wave C completion permits authorized real-path characterization, not automatic LIVE scientific qualification.

Engineering must supply the real-backend adapter and existing-owner evidence bindings. The companion bundle supplies a blank challenge profile JSON, campaign endpoint exports, a descriptive before/after comparator with context warnings, raw traces/array artifacts, and a fresh-directory reproduction script. Production fields remain null.

## 6. Artifacts, tests and history

Companion deliverables are `Carbon_Challenge_Operating_Point_Study_v0_2.md` and `Carbon_Operating_Point_Research_Bundle_v0_2.zip`, supplied with the owner conversation. The bundle contains the locally frozen protocol, source, raw data, array-only model artifacts, analyses, queue tests and SHA-256 manifest. Binary research artifacts are not committed by this documentation change.

Verification checks campaign coverage, distinct configurations, deadline/censoring handling, nomination integrity, phase accounting, array shapes, outer means, split separation, zero-overhead replay parity and artifact hashes. Six queue unit tests cover FIFO, reference readiness, fill delay, batch sharing, cutoff occupancy and empty work.

The analyzer wrote the raw arrays/CSVs, then encountered a NumPy integer JSON serialization error. A type-only repair rebuilt the summary from preserved CSVs; no model, timing or witness run was replaced. Source hashes and the failure remain in the bundle. The prior interactive-shell launch mechanism was unsupported and started no numerical work. These are execution-history facts, not scientific failures.

Applicable repository acceptance is still required before merge. This update does not fix or waive the separate Hub test-harness issue #141.

## Primary-source method context

- [NIST experimental optimization](https://www.itl.nist.gov/div898/handbook/pri/section5/pri53.htm): sequential local operating-region studies with uncertainty; no Carbon thresholds.
- [Hyperband](https://jmlr.org/papers/v18/16-558.html): breadth/depth resource allocation research; no authority to prune a mandatory official exam.
- [Random search](https://www.jmlr.org/beta/papers/v13/bergstra12a.html): experimental baseline, not a universal superiority claim.
- [Cawley and Talbot](https://www.jmlr.org/beta/papers/v11/cawley10a.html): selection bias and separating tuning from evaluation.
- [JAX benchmarking](https://docs.jax.dev/en/latest/benchmarking.html): synchronization, compilation, transfer and precision accounting.

Carbon's existing scientific canon, Dossier, distribution/sampling, reference, measurement, resource, disclosure and product-evidence owners remain controlling. No source or this pilot qualifies a production Challenge by itself.
