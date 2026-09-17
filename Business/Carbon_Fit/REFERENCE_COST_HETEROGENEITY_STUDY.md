# Reference-cost heterogeneity across Challenge strata

**Status:** public development research only. No production target population, sample count, reference tolerance, batching policy, or qualification threshold is selected.

## Question

When difficult physical regimes are both rarer and more expensive to reference, how should Carbon allocate one fixed reference-compute budget without weakening the target-population estimand or starving mandatory hard-regime evidence?

This study extends the regime-conditioning and stratum-allocation work already recorded in the Carbon Fit research track.

## Inputs

The empirical evidence pool contains 512 per-case holdout errors in each synthetic Burgers stratum from the prior 400-update development candidate.

For this study only, the illustrative target population remains:

- easy: 70%;
- moderate: 20%;
- hard: 10%.

The target population `P(x)`, finite sampling allocation `Q(x)`, and evidence weighting `w(x)` remain separate. All target-mean estimates use the declared 70/20/10 weights.

### Measured reference-cost proxy

The Cole-Hop f development reference was repeated on 4,096 cases at the lowest development grid that the prior regime study treated as adequate for its diagnostic criterion:

| Regime | Development grid | Median compute / case |
|---|---:|---:|
| easy | 32 | 11.32 microseconds |
| moderate | 64 | 14.54 microseconds |
| hard | 96 | 24.13 microseconds |

The hard reference therefore cost about **2.13x** the easy reference in this analytic fixture. These timings are a Burgers implementation proxy, not an industrial CFD claim.

### Synthetic cost-heterogeneity stress scenarios

To test the method outside the mild Burgers ratio, two explicitly synthetic scenarios were added:

- moderate = 3x easy, hard = 12x easy;
- moderate = 5x easy, hard = 30x easy.

These are stress scenarios, not measurements of any CFD solver.

For each cost scenario, the total reference budget was initially fixed to the cost of the earlier 60-case target-proportional design: 42 easy / 12 moderate / 6 hard cases.

## Policies compared

1. target-proportional sampling;
2. uniform stratum allocation;
3. hard-heavy allocation;
4. equal-case-cost Neyman allocation using the empirical stratum variances;
5. cost-aware Neyman allocation proportional to `P_h * sigma_h / sqrt(cost_h)`;
6. the development Pareto frontier between target-mean precision and hard-stratum p95 precision.

The Neyman policies are development allocation diagnostics only. Candidate-derived allocation cannot be copied into a LIVE SamplingPlan without prospective qualification.

## Main result

Under the measured Burgers cost ratio and one fixed reference budget, target-proportional sampling produced 42/12/6 cases and about:

- target-mean RMSE: **0.0600%**;
- hard-stratum p95 RMSE: **1.862%**.

At the same budget, cost-aware Neyman sampling used 19/13/16 cases and improved target-mean RMSE to **0.0456%**, while hard-p95 RMSE improved to **1.313%**.

When hard cases became much more expensive, the behavior changed.

Under the synthetic **30x hard-case** scenario, the same target-proportional budget is 282 easy-case-equivalent reference units. The cost-aware Neyman allocation became 37/13/6: it preserved many easy cases but did not buy additional hard evidence. Its target-mean RMSE was about **0.0603%** and its hard-p95 RMSE about **1.874%**.

A hard-heavy allocation improved hard-tail evidence, but because hard cases were expensive it could afford only 22 total cases (7/7/8), and target-mean precision worsened.

**Interpretation:** there is no single cost-optimal allocation unless Carbon first states which estimands and subgroup evidence are mandatory. Optimizing only the target-population mean can rationally underfund the expensive hard regime.

## Fixed development precision target

To make the cost effect concrete, this study defines a development-only precision target equal to the earlier 20/20/20 allocation:

- target-mean RMSE about **0.0411%**;
- hard-stratum p95 RMSE about **1.266%**.

These are comparison targets, not production thresholds.

The minimum reference budgets found by exhaustive integer allocation were:

| Cost scenario | Minimum budget | Allocation easy/moderate/hard |
|---|---:|---|
| measured Burgers (~2.13x hard/easy) | **86.7** easy-case-equivalent units | 24 / 14 / 21 |
| synthetic 12x hard/easy | **293** | 32 / 15 / 18 |
| synthetic 30x hard/easy | **644** | 39 / 13 / 18 |

The required scientific precision stayed fixed. Only the cost of acquiring evidence changed.

Under the 30x scenario, the original target-proportional 60-case budget of 282 units could not meet both development precision targets under any tested integer allocation.

> **A rare expensive stratum can make reference evidence, rather than candidate reconstruction, the limiting factor.**

The possible responses are prospective: increase reference budget, share a protected cohort, lower cadence, narrow/split the Challenge envelope, or change the scientific claim. Carbon must not silently drop hard cases.

## Bounded committed-cohort reuse

If one already-qualified protected reference cohort can legitimately serve multiple already-committed candidates, the cohort reference cost can be amortized.

For the synthetic 30x hard-case scenario, the 39/13/18 development precision plan costs 644 easy-case-equivalent units per fresh cohort:

| Committed candidates sharing that cohort | Amortized reference cost / candidate |
|---:|---:|
| 1 | 644.0 |
| 2 | 322.0 |
| 4 | 161.0 |
| 8 | 80.5 |
| 16 | 40.25 |

At an illustrative arrival rate of 100 committed candidates/day, the simple mean cohort-fill delay is about 0.84 h for an eight-candidate cohort.

This arithmetic does **not** qualify reuse. It excludes security/custody, adaptive-feedback leakage, reference exhaustion, fresh-cohort requirements, and client/solver rights constraints.

Reuse lowers recurring cost per candidate. It does not increase the number of independent hard cases in that cohort.

## Challenge Profiler addition

For each important stratum, record:

- target prevalence;
- reference role/configuration;
- per-case compute/cost distribution;
- numerical failure/censoring;
- reference uncertainty;
- candidate-error variability;
- intended estimands and mandatory subgroup evidence.

Then:

1. set the scientific evidence requirements first;
2. compute the cost-constrained Pareto frontier;
3. identify the cheapest plan that satisfies every required estimand/subgroup;
4. evaluate whether bounded committed-cohort reuse changes recurring economics enough to justify its security and latency burden;
5. if no feasible plan exists, narrow/split the Challenge or decline it.

The default optimizer must not minimize reference cost by reducing evidence from the very stratum that creates the engineering risk.

## Limits

- One development candidate supplies the empirical error distributions.
- The target population is hypothetical.
- The 12x and 30x hard-cost scenarios are synthetic stress tests.
- The measured Burgers reference is unusually cheap and analytic.
- The hard-p95 precision estimate comes from resampling the finite development pool.
- No LIVE sampling law, minimum subgroup count, uncertainty threshold, solver tolerance, batching limit, or client SLA is selected.
- Cohort reuse assumes one protected answer set is scientifically and legally reusable across already-committed candidates; that remains a separate qualification/security question.

## Next experiment

The remaining gap is **reference failure and retry cost**, not only nominal per-case runtime. Expensive CFD-like hard cases can fail to converge, require mesh refinement, or move to a stronger solver path. The next study should treat per-stratum reference cost as a distribution with typed failure/censoring and test how much reserve Carbon needs so difficult cases do not disappear from the realized exam.
