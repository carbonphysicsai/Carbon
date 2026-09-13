# Carbon Stratum Allocation Study v0.1

**Status:** illustrative development simulation; no production target population, sample count, stress weight, or score rule is selected.

## Question

When difficult physical regimes are rare in the deployment population but much harder for models and references, can Carbon obtain better finite evidence by oversampling those regimes while preserving the declared target-population estimand?

## Inputs

The development candidate was reconstructed separately in the easy, moderate, and hard synthetic Burgers regimes using 400 optimizer updates and 256 training trajectories. Each stratum retained 512 per-case holdout errors.

For this simulation only, the illustrative target population was:

- easy: 70%
- moderate: 20%
- hard: 10%

This `P(x)` is not a proposed Carbon population. It exists only to test the analysis method.

Four finite sampling allocations `Q(x)` were compared at total case budgets of 30, 60, and 120:

1. target-proportional sampling;
2. uniform strata;
3. hard-heavy sampling (20% easy / 30% moderate / 50% hard);
4. a development-only Neyman allocation proportional to target mass × observed stratum standard deviation.

All target-mean estimates used the declared stratum weights, so oversampling hard cases did not redefine the deployment population.

## 60-case development result

| Sampling design | Cases easy/moderate/hard | Target-mean RMSE | Hard-stratum p95 RMSE |
|---|---|---:|---:|
| target-proportional | 42 / 12 / 6 | 0.0611% | 1.870% |
| uniform | 20 / 20 / 20 | 0.0407% | 1.253% |
| hard-heavy | 12 / 18 / 30 | 0.0414% | 1.073% |
| development Neyman | 20 / 15 / 25 | 0.0397% | 1.160% |

The natural target-proportional design spent only six cases on the hard stratum. In this finite development pool it produced substantially noisier target-mean and hard-tail evidence than the stratified alternatives.

## Interpretation

This is the practical value of Carbon's separation between:

- target population `P(x)`;
- finite sampling/proposal distribution `Q(x)`; and
- evidence/estimand weighting `w(x)`.

Carbon can sample a rare but decision-relevant hard regime more often to learn about it, while weighting the resulting evidence according to the registered target estimand where that is scientifically appropriate.

The study does not authorize the specific target proportions, sample counts, hard-heavy allocation, Neyman rule, or p95 quantity. A LIVE Challenge must author and qualify those choices prospectively. Candidate outcomes cannot dynamically alter the official allocation.

## Relationship to regime conditioning

The preceding regime study showed that the hard synthetic stratum:

- had much steeper final fields;
- required higher reference resolution and produced low-resolution reference failures;
- retained materially higher model error after deeper reconstruction; and
- showed a nonzero extrema-violation diagnostic.

That makes stratum allocation a real operating concern: allocating too little evidence to a rare hard regime can make the overall exam cheap but scientifically weak exactly where the model is least reliable.

## Carbon Fit / Challenge Profiler addition

For each proposed Challenge, add a finite-evidence allocation study after regime conditioning:

1. Author the target population and important strata independently of candidates.
2. Measure reference cost/failure and candidate variability by stratum in development evidence.
3. Compare prospective SamplingPlan allocations under the same total evidence budget.
4. Evaluate precision for each intended estimand and mandatory subgroup requirement.
5. Check whether weighting correctly maps sampled evidence back to the registered estimand.
6. Qualify the selected plan on independent evidence before LIVE.
7. Preserve censoring and reference failure by stratum.

The operational output is an evidence-efficiency frontier: how much finite exam cost is needed to resolve the target-population performance, hard-regime behavior, and other required estimands.

## Limits

- One development candidate supplied the per-case error distributions.
- The target population is hypothetical.
- Resampling treats the finite development pool as the empirical population.
- The Neyman allocation was derived from candidate outcomes and therefore cannot be copied into a LIVE plan without a separate prospective qualification process.
- No scientific gate, minimum stratum count, tail threshold, or production score weight is selected.
