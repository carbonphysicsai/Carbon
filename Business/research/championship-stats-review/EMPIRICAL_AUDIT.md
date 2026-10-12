# Public case-vector audit: what survives resampling

**DEVELOPMENT diagnostic, not championship qualification.** I15 in
[INPUT_PROVENANCE](INPUT_PROVENANCE.md) supplies 15 retained runs of five real
recipes on the same 200 public PRACTICE cases. There are 39 important cases;
all 15 runs were eligible under their historical frozen rule. This neither
rechecks v3 gates nor demonstrates false-feasible protection. No training or
reference solver was run, and no raw rows are committed.

The comparison panel follows M04's source: four MLP artifacts at source seed
one, giving six paired contrasts. The kNN and other training seeds are not
added to that panel. Aliases M1–M4 follow lexicographic public recipe identity;
both signs of each contrast are tested. Source SDs use the average of the two
mean losses, matching paired.py; they are **not incumbent-normalized takeover
gains**. Every descriptive source number is a fixed low=base=high observation,
not an estimated production range.

## Observed dependence and tails

The six sample SDs reproduce paired.json to floating-point precision.
Case-vector resampling retains actual cross-model dependence; same-case error
correlations span 0.675–0.889. No source/time blocks were supplied. Case IDs are
labels, not chronological measurements, so between-round autocorrelation is
unidentified rather than estimated as zero.

| Pair | Sample SD / pair-average loss | Centered skewness | Excess kurtosis | Largest absolute centered loss / SD | Variance in largest 5% of cases |
|---|---:|---:|---:|---:|---:|
| M1–M2 | 0.331 | -0.420 | 2.117 | 3.757 | 43.06% |
| M1–M3 | 0.278 | -0.391 | 1.555 | 3.592 | 38.12% |
| M1–M4 | 0.699 | -5.988 | 45.352 | 8.994 | 84.90% |
| M2–M3 | 0.291 | 0.227 | 1.490 | 3.828 | 37.71% |
| M2–M4 | 0.595 | -4.923 | 37.878 | 9.114 | 74.74% |
| M3–M4 | 0.638 | -4.716 | 31.527 | 8.152 | 75.42% |

These are empirical moments of 200 cases, with population-moment normalization
for skewness/kurtosis; the sign reverses in the opposite duel direction.
Concentrated tails make a generic median proxy particularly unsafe for a wider
pair. They do not prove what lies beyond the public sample's largest case.

## Conditional empirical null test

**ASSUMPTION simulation law:** center each full paired-case vector to zero mean,
sample uniformly with replacement from the 200 vectors, use N=3,000 per round,
14 rounds, alpha_art=0.05 and the M04 mixture boundary. Public synthetic seed
733 and 10,000 independent paths are fixed simulation choices. Resample all
contenders together. Repeated bootstrap draws are not 3,000 distinct physical
cases. The correct-SD scenario knows the variance of this empirical law; it
does not estimate a production variance from the batch being tested.

Across all six pairs and both directions, the **correct pair-specific empirical
SD** gives point false-crossing rates **0.42–0.73%**. Thus the original 0.6%
result remains plausible for this limited IID empirical exercise. Each rate's
95% Wilson interval is in [audit-results](audit-results.json); this range is
across scenarios, not one confidence interval.

For the wide M1–M4 contrast, Monte Carlo low/point/high percentages are:

| ASSUMPTION scenario | Positive original direction | Reversed direction |
|---|---|---|
| Correct empirical pair SD | 0.371 / 0.490 / 0.647 | 0.581 / 0.730 / 0.917 |
| Median proxy 0.46 used for actual sample SD 0.699 | 8.008 / 8.540 / 9.104 | 8.125 / 8.660 / 9.227 |
| Same batch counted twice as fresh | 4.130 / 4.520 / 4.945 | 4.878 / 5.300 / 5.757 |
| Same batch counted three times as fresh | 9.048 / 9.610 / 10.203 | 9.749 / 10.330 / 10.942 |

Reuse scenarios deliberately repeat the same increment for consecutive rounds
while increasing the nominal variance clock as if each round were new. They
illustrate information miscounting, **not observed Carbon bank reuse**. Across
all pairs/directions, twice-counted batches give 4.52–5.51% and three-times-counted
batches 9.15–10.33% point rates. Retirement and counting distinct information
matter even without revealing raw cases.

Actual fixed-round Holm on the same empirical vectors, with M1 the frozen
incumbent and three contenders, gives **4.053/4.440/4.862%** on day one and
**45.664/46.640/47.619%** for any rejection across 14 independently budgeted
days. These use normal-approximate fixed-round p-values, not a proof of their
finite-sample calibration. They show the daily/campaign distinction with the
public covariance structure; there is no alpha-investing, fast lane or changing
incumbent in this panel.

## Small-gain sensitivity

Add an **ASSUMPTION constant gain** of 1/2/3% of pair-average loss to each
centered contrast. With correct empirical SD, source-direction and reverse
results agree on the following point estimates for first reaching 80% wins:

| alpha_art | 1% gain | 2% gain | 3% gain |
|---|---|---|---|
| 0.05 | Narrower three pairs: 4–6 rounds; wider three: not by 14 | 2–6 rounds across pairs | 1–3 rounds |
| 0.01 | Narrower three pairs: 6–7 rounds; wider three: not by 14 | 2–8 rounds across pairs | 1–4 rounds |

Full per-pair win probabilities and Monte Carlo intervals are in the JSON.
First hitting 80% is a noisy point diagnostic, not a CI on waiting time. These
are shifts of public statistical contrasts, not demonstrated physically better
models. They retain M04's pair-average normalization and exclude the corrected
joint campaign budget, mandatory gates and incumbent changes. They support
narrowing the “2–3 rounds” claim rather than treating it as universal.

## Recommendation after seeing the rows

Keep fresh shared paired evidence and a pair-specific qualified variance route.
The public rows do **not** refute the original fixed-pair 0.6% scenario, but they
do refute transferring it merely from a median SD or nominal case count. The
combined adaptive rule is still unimplemented in M04, and source/time dependence,
new-tail coverage, mixed null/alternative incumbent changes, the alpha ledger
and hard-gate behavior still require the acceptance panel in
[STATISTICAL_CONTRACT](STATISTICAL_CONTRACT.md). All production limits remain
HUMAN_INPUT. Reference-relative accuracy is not decision-value qualification.
