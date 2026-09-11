# Stratum allocation and finite-evidence efficiency

**Status:** illustrative development simulation. No production target population, sample count, stress weight, or score rule is selected.

## Question

When difficult physical regimes are rare in the deployment population but harder for models and references, can Carbon obtain better finite evidence by oversampling those regimes while preserving the declared target-population estimand?

## Development scenario

The development candidate was reconstructed separately in the easy, moderate, and hard synthetic Burgers regimes using 400 optimizer updates and 256 training trajectories. Each stratum retained 512 per-case holdout errors.

For this simulation only, the illustrative target population `P(x)` was 70% easy, 20% moderate, and 10% hard. This is not a proposed Carbon population.

Four finite sampling allocations `Q(x)` were compared at total case budgets of 30, 60, and 120: target-proportional, uniform strata, hard-heavy (20/30/50), and a development-only Neyman allocation proportional to target mass times the observed stratum standard deviation. Target-mean estimates retained the declared stratum weights, so oversampling did not redefine the target population.

## 60-case result

| Sampling design | Cases easy / moderate / hard | Target-mean RMSE | Hard-stratum p95 RMSE |
|---|---|---:|---:|
| target-proportional | 42 / 12 / 6 | 0.0611% | 1.870% |
| uniform | 20 / 20 / 20 | 0.0407% | 1.253% |
| hard-heavy | 12 / 18 / 30 | 0.0414% | 1.073% |
| development Neyman | 20 / 15 / 25 | 0.0397% | 1.160% |

In this finite development pool, target-proportional sampling spent only six cases on the hard stratum and produced noisier target-mean and hard-tail evidence than the stratified alternatives.

## Carbon interpretation

This demonstrates why Carbon keeps target population `P(x)`, finite sampling/proposal distribution `Q(x)`, and evidence/estimand weighting `w(x)` separate. A rare but decision-relevant hard regime can be sampled more often to obtain evidence while the final estimand still reflects the registered target population where scientifically appropriate.

The specific target proportions, case counts, hard-heavy allocation, Neyman rule, and p95 quantity are development assumptions only. Candidate outcomes cannot dynamically alter the official allocation. A LIVE SamplingPlan must be authored and qualified prospectively.

The preceding regime-conditioning study showed that the hard synthetic stratum had steeper fields, higher model error, low-resolution reference failures, and a nonzero extrema diagnostic. That makes finite-evidence allocation an operational concern: an exam can be inexpensive overall yet under-resolve the region where the candidate is least reliable.

## Challenge Profiler addition

After regime conditioning:

1. Author the target population and important strata independently of candidates.
2. Measure reference cost/failure and candidate variability by stratum in development evidence.
3. Compare prospective SamplingPlan allocations under the same total evidence budget.
4. Evaluate precision for the intended estimands and required subgroup evidence.
5. Verify that weighting maps sampled evidence back to the registered estimand.
6. Qualify the selected plan on independent evidence before LIVE.
7. Preserve censoring and reference failure by stratum.

The useful output is an **evidence-efficiency frontier**: how much finite exam cost is needed to resolve target-population performance, hard-regime behavior, and any other required estimands.

## Limits

One development candidate supplied the per-case error distributions; the target population is hypothetical; resampling treats a finite development pool as the empirical population. The Neyman allocation was derived from candidate outcomes and therefore cannot be copied into a LIVE plan without a separate prospective qualification process. No scientific gate, minimum stratum count, tail threshold, or production score weight is selected.
