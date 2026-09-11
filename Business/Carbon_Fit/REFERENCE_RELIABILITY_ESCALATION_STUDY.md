# Carbon Reference Reliability, Retry, and Escalation Study v0.1

**Status:** development research only. No production failure rate, reserve, retry count, fallback multiplier, solver hierarchy, or service target is selected.

## Question

How much recurring reference-compute reserve does Carbon need when difficult cases can fail, retry, or escalate to a stronger reference path, and what happens if failed cases are simply dropped?

This study uses the prior synthetic 30× hard-case reference-cost profile and its development evidence plan:

- easy: 39 cases at cost 1 unit each;
- moderate: 13 cases at cost 5 units each;
- hard: 18 cases at cost 30 units each;
- nominal fresh-cohort cost: **644 easy-case-equivalent units**.

The hard-cost ratio is a synthetic stress input, not a CFD measurement.

## Failure model

Each primary reference case can encounter:

1. a **deterministic/applicability failure**: repeating the same primary configuration is assumed not to help;
2. a **transient failure**: a same-configuration retry may succeed.

The stronger fallback is assumed to succeed for this cost sensitivity. That assumption is deliberately optimistic; real fallback failure must remain typed and may make the exam indeterminate or incomplete.

Three synthetic failure scenarios were tested:

| Scenario | Easy det/trans | Moderate det/trans | Hard det/trans |
|---|---|---|---|
| Low | 0% / 0.5% | 1% / 1% | 2% / 3% |
| Moderate | 0.5% / 1% | 2% / 3% | 8% / 7% |
| High | 1% / 2% | 5% / 5% | 20% / 10% |

These probabilities are research stress inputs, not production estimates.

The main comparison uses a stronger-fallback cost equal to **5×** the primary case cost. A 2× and 10× sensitivity is retained in the companion research bundle.

## Policies

- `drop`: failed primary cases disappear from the realized evidence population;
- `fallback_immediate`: any primary failure escalates immediately;
- `retry_all_once`: retry every failure once, then escalate if the retry fails;
- `typed_retry`: idealized upper bound where deterministic/applicability failures escalate immediately and transient failures receive one retry before fallback.

The typed policy assumes perfect failure classification and therefore measures the potential value of failure attribution, not a qualified implementation.

## Main result 1: dropping failures censors the hard regime

Under the three stress scenarios, simply dropping failed reference cases caused the planned 18-case hard stratum to lose at least one case in approximately:

- **59.5%** of low-failure cohorts;
- **93.8%** of moderate-failure cohorts;
- **99.7%** of high-failure cohorts.

The probability of losing two or more hard cases was about:

- **22.0%**;
- **75.5%**;
- **97.9%**.

Reference failure therefore cannot be treated as harmless missing data. It can reshape the realized exam exactly where the reference is already difficult.

## Main result 2: reserve can dominate recurring economics

For the idealized typed policy with a 5× fallback, the p95 total reference budgets were:

| Failure scenario | Nominal budget | p95 budget | p95 reserve |
|---|---:|---:|---:|
| Low Failure | 644 | 944 | 46.6% |
| Moderate Failure | 644 | 1269 | 97.0% |
| High Failure | 644 | 1729 | 168.5% |

The reliability-adjusted reference capacity is therefore lower than the no-failure capacity even before queues, custody, or network overhead.

At the mean-cost level, the nominal 644-unit cohort capacity is derated by approximately:

- low failure: **89.5%** of nominal capacity;
- moderate failure: **70.2%** of nominal capacity;
- high failure: **50.6%** of nominal capacity;

These are simulation outputs, not production availability factors.

## Main result 3: typed failure attribution has compute value

Blindly retrying deterministic failures wastes the original reference cost again before eventually escalating.

In this model, `typed_retry` reduced both mean and p95 reference cost relative to blind retry across all three scenarios.

At high failure stress, blind retry had a slightly worse p95 cost than immediate fallback because deterministic hard failures were expensive and retries could not repair them.

The design implication is:

> **Failure classification belongs in the throughput model. `REFERENCE_NUMERICAL_FAILURE`, out-of-applicability, infrastructure/transient failure, and disagreement cannot share one generic retry rule.**

This is consistent with Carbon's existing typed reference-failure doctrine; the present study adds an operational cost reason.

## Cohort reuse with reliability reserve

Bounded committed-cohort reuse still amortizes the reference campaign, but the reserve must be applied to the cohort before division across candidates.

Under the high-failure, 5×-fallback typed scenario:

- nominal no-failure cohort = 644 units;
- mean reliability-adjusted cohort = **1272.8** units;
- p95 cohort = **1729** units.

At cohort size 8, that p95 cost is about **216.1 units per committed candidate**, versus 80.5 units per candidate under the no-failure 644-unit cohort.

Reuse can still rescue expensive-reference economics, but a throughput model that ignores convergence/fallback reserve can materially overstate capacity.

## Challenge Profiler addition: reference reliability profile

For each reference stratum, the profiler should retain separately:

- nominal per-case cost distribution;
- success/failure status and attribution;
- same-configuration retry cost and observed recovery rate;
- fallback method/configuration and cost;
- fallback success/failure;
- final censoring/replacement status;
- effect on realized SamplingPlan and scientific uncertainty.

The operating analysis then reports:

1. nominal reference budget;
2. expected reliability-adjusted budget;
3. p95/p99 reserve sensitivity;
4. reference capacity derating;
5. realized evidence-population distortion if failed cases are not restored;
6. benefit of typed retry/escalation;
7. amortized cost under any prospectively qualified committed-cohort reuse.

## Scientific boundary

Reserve engineering cannot weaken the exam.

When a required hard case fails reference realization, permitted responses include a registered retry, registered stronger fallback, an indeterminate/incomplete outcome, or prospective redesign. Carbon must not silently replace the failed hard case with an easier one outside the SamplingPlan or turn reference failure into candidate scientific failure.

## Limits

- Failure probabilities are synthetic.
- The 30× hard-case and 5× fallback costs are synthetic stress inputs.
- Fallback is assumed successful.
- Failure classification is assumed perfect in the typed-policy upper bound.
- Correlated failures, solver-wide outages, queue bursts, cache loss, and adaptive feedback are not modeled.
- The evidence plan comes from one earlier development candidate and illustrative population.
- No retry count, reserve percentile, or availability requirement is selected for production.

## Next experiment

The next highest-value study is **correlated reference failure**: common solver/configuration failures can invalidate many cases in the same stratum or an entire reference cohort, so independent per-case retry models can understate tail risk. The profiler should test solver-wide/common-mode failure, multi-fidelity fallback independence, and the value of a methodologically distinct witness/anchor.
