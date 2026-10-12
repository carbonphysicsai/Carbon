# Independent review of MARGIN-SIZING-04

## Verdict and evidence boundary

The shared fresh batch, paired retained artifacts, conservative ties and batch
retirement are good directions. **The combined championship is not validated by
the supplied simulation.** This review neither approves a production threshold
nor alleges an observed private-bank failure.

Inputs I1–I14 in [INPUT_PROVENANCE](INPUT_PROVENANCE.md) were supplied by the
owner as public PRACTICE evidence. m04.py has no imports of a physical solver;
its statistical model uses hardcoded SD scenarios. This review executed a new
independent audit, not the source scripts with their WSL paths/output writes.
The copied input directory was read-only and is excluded from the PR.

All source constants below are fixed low=base=high at that version. Synthetic
parameters are ASSUMPTION. Simulation intervals reflect Monte Carlo uncertainty
conditional on the scenario, not uncertainty about a production population.

## Findings

| Finding | Evidence | Consequence / required response |
|---|---|---|
| R1: full procedure absent | I10 m04.py computes `z(0.05/k)` sizing, then simulates one stream with fixed alpha; it never constructs contender p-values, runs Holm, selects among winners, changes incumbent or updates wealth | Keep power tables as analytic scenario sizing. Do not attach their guarantee to unimplemented combined logic |
| R2: false-rate scope mismatch | I7's 0.006 is one stream at N=2,000, alpha_art=0.05, 14 rounds, 6,000 paths | Not a 5%-daily global rule, not N=3,000, not multiple/repeated entrants or a mixed null/alternative championship |
| R3: known variance is not measured adequacy | I9 paired.json supplies six relative SDs from public cases; I10 uses Gaussian aggregate draws and V=n*sigma^2 | Need a valid conditional MGF/variance process, tail/block review and held-out sizing. Matching a marginal sample SD does not prove a martingale |
| R4: alpha-investing absent and target differs | I2/I3 describe it; I10 has no wealth balance, charge, reward, entry ordering or theorem | If the intended claim is probability of any false crown, ordinary mFDR investing is the wrong guarantee; choose FWER spending or explicitly change the owner claim |
| R5: carry and round selection do not compose automatically | I2/I3 assign per-day/per-artifact levels; I3 recommends daily Holm plus carry and optional immediate finals | Declare a single family and all rejection routes. Fixed cohort anytime-Holm can work; two independent full-level rules need joint control |
| R6: moving target / alpha denominator | I3 resets evidence on new artifact/incumbent, divides alpha by artifacts open | Resetting evidence cannot refund alpha. A smaller current k cannot automatically increase a historical process's allowance; new incumbent changes the tested pair |
| R7: Sybil statement too broad | I2 says splitting hotkeys buys nothing after artifact keying | True for exact duplicate identity only. Distinct perturbed artifacts remain multiple hypotheses; disclose the power/queue trade-off without claiming complete Sybil resistance |
| R8: reuse tolerance unsourced | I3 proposes up to three failed-challenge reuses but also disclosure of a lower bound | A numerical bound conveys more than one bit. No leakage budget or K=3 experiment is supplied; retire after scored use for adaptive new entrants |
| R9: important/gate and costs excluded | I3 caveats explicitly omit important region; code has no G-FEAS events; 91 CPU-s is inherited planning cost | Gates can only restrict promotions if applied correctly, but their false acceptance, sampling and cost need separate evidence. Reference pre-solving alone is not total daily cost |
| R10: power and latency claims need narrowing | I10 assumes fixed SD/cohort and no incumbent transition; I7 median k=5, N=3,000, 2% needs four rounds | “2–3 rounds” is conditional: median 2% requires 3 rounds at k=1 but 4 at k=5. Daily schedule also adds up to a day's wait; no guaranteed runtime is measured |

These are research-contract findings, not edits to Validator code. The owner
decides epsilon, alpha, retention and deployment; Test Engineer owns the repaired
selection proof. [Recommended contract](STATISTICAL_CONTRACT.md).

## What is statistically valid in the proposed structure

**Shared fresh cases and incumbent rescoring.** Holding both model artifacts
fixed, infer both on the same newly generated inputs and references each round.
Compare per-unit losses, not the challenger's new score against a stored old
incumbent score. Correlation between contenders caused by the shared incumbent
does not invalidate Holm: Holm needs each null p-value valid, and tolerates
arbitrary dependence between them. Freeze the cohort before the batch is drawn;
screening feedback may select models, provided final material is conditionally
fresh and its selection law is honored. [Holm/R primary documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html).

**Optional stopping on a fixed pair.** For paired increments X, M04's positive
boundary is

`b(V)=sqrt((V+rho)*log((V+rho)/(rho*alpha^2)))`,
`V=m*sigma^2`, `rho=N*sigma^2`.

Under the declared known-Gaussian independent null, it is a conservative
one-sided crossing of a normal-mixture construction. More generally a valid
conditional sub-Gaussian proxy suffices; ordinary marginal variance does not.
For S>=0, the nonnegative-lambda half-normal mixture is at least the symmetric
mixture that yields this boundary, so positive crossing is controlled under
the one-sided conditional null. This does not repair an underestimated V or
unmodeled latent correlation. Under a composite unconditional mean null with
arbitrary dependence, the same theorem does not follow.
[Mixture boundaries and confidence sequences](https://arxiv.org/abs/1810.08240),
[nonnegative martingale foundations](https://arxiv.org/abs/2009.03167).

**Re-scoring is useful, not magic.** The same immutable incumbent contributes
to every pair; this creates within-round correlation handled by Holm. Shared
source blocks, recurring conditions, repeated cases or overlapping weighted
strata can also create between-round dependence and miscounted information.
Fresh hidden seeds do not prove independent semantic cases. A finite bank
sampled without replacement has a different conditional model from M04's
unlimited IID cases. Dedup counts, batch provenance and the true sampling
contract are required. [Finite-population sequences](https://proceedings.neurips.cc/paper/2020/hash/e96c7de8f6390b1e6c71556e4e0a4959-Abstract.html).

## Reproduced and independently measured results

I7/I10 reproduce **36/6,000 = 0.600%**, Wilson 95% **0.434/0.600/0.829%**,
over 14 rounds at N=2,000. Original seed 3 is explicitly a public synthetic
simulation seed, not an official draw seed. The replication preserves RNG order
and early stopping. [audit-results](audit-results.json), [audit](audit.py).

Independent audit uses public synthetic seed 731, fixed 40,000 paths/scenario,
14 rounds, proxy sigma 0.46, alpha 0.05. Each scenario has zero true improvement.
Rows below show **Monte Carlo low/point/high 95% Wilson**, not planning ranges:

| ASSUMPTION scenario, N=3,000 | False positive crossing %, low / point / high |
|---|---|
| Independent Gaussian, proxy correct | 0.506 / 0.575 / 0.654 |
| Independent Gaussian, actual SD 1.25 × proxy | 3.120 / 3.290 / 3.469 |
| Independent Gaussian, actual SD 1.50 × proxy | 8.046 / 8.312 / 8.587 |
| Independent Gaussian, actual SD 2.00 × proxy | 20.730 / 21.127 / 21.530 |
| Stationary Gaussian AR(1) round shock, phi 0.25 | 2.378 / 2.527 / 2.686 |
| Stationary Gaussian AR(1) round shock, phi 0.50 | 6.634 / 6.878 / 7.130 |
| Stationary Gaussian AR(1) round shock, phi 0.75 | 13.141 / 13.473 / 13.811 |
| Stationary Gaussian AR(1) round shock, phi 0.90 | 17.614 / 17.988 / 18.367 |
| IID standardized Student-t(3) round shocks | 1.645 / 1.770 / 1.904 |
| Rare-positive round shocks, probability 0.01 | 8.255 / 8.525 / 8.803 |

Rare-positive shocks take values `sqrt((1-p)/p)` with probability p and
`-sqrt(p/(1-p))` otherwise, then multiply by sigma*sqrt(N). They have zero mean
and the same marginal batch variance as the Gaussian scenario. They are a
deliberate skewed **batch-shock** stress, not an empirical IID-case model.
AR(1) preserves marginal round variance but adds covariance. These are plausible
failure mechanisms to test, **not evidence that Carbon's data have these laws**.
Increasing N alone does not remove a latent batch shock or certify the proxy.

The audit also implements actual fixed-round Holm under a shared-incumbent
Gaussian correlation model. At k=5, correlation 0.5, day-one null family error
is **3.871/4.060/4.258%**; any crossing across 14 separately budgeted days is
**43.269/43.755/44.242%**. At k=1 it is approximately 51% across 14 days,
matching DERIVED `1-(1-0.05)^14 = 51.23%` in the independent ideal. This is
consistent with 5%-per-day control, not a failure of Holm. It shows why a daily
and a campaign claim are different. No adaptive incumbent-changing, alpha-ledger
or combined fast-lane guarantee was simulated by this audit.

## Power, epsilon and cost checks

M04's analytic first-Holm-threshold calculation is
`detect80=(z_(1-alpha/k)+z_.8)*sigma/sqrt(N)`.
It is a sufficient fixed-candidate Gaussian threshold, not a full simulation
of selecting the best model. Split-half's formula assumes the selected model
is actually the useful candidate; it omits selection probability. Under its
own equations, the crossover is DERIVED **k=13.373**, so at k=20 split-half
already has the smaller conditional threshold; “Holm better to about 20” is
too broad. Compare complete rules on the same contender effects/covariance and
gates before claiming an end-to-end power advantage.

At N=3,000 and sigma 0.46, fixed Gaussian first-threshold detection at k=1/5/20
is **2.088/2.661/3.064%** (source/derived fixed points, rounded). With epsilon>0,
the required true gain approximately increases by epsilon, under the same
normalization. I7's median 1% carry needs **11/13 rounds** at k=1/5, while 2%
needs **3/4**, and 3% **2/2**. These are source scenario results, not forecasts
for a corrected global budget or true tail distribution. [Epsilon proposal](STATISTICAL_CONTRACT.md).

The inherited cost **91 CPU-s/case** is a planning value, not a measured
championship cost. DERIVED N=3,000 reference cost **75.833 CPU-h/day**; stock
9,000 cases **227.5 CPU-h**. This excludes inference for k+1 retained artifacts,
loading, gates/refinement, failed references, working storage and refill retries.
At perfect scaling 16/8 physical workers need **4.740/9.479 hours/day** to refill,
not a capacity guarantee. Three batches cover three scheduled withdrawals only
if nothing else consumes them and an outage does not exceed that interval.

## Still needed to validate realistic distributions

The owner subsequently supplied the 200 public per-case rows (I15). The
[empirical resampling panel](EMPIRICAL_AUDIT.md) reproduces all six source SDs,
measures their skew/tail concentration, and resamples whole shared-case contender
vectors under an explicitly IID empirical law. Correct pair SDs preserve null
rates near 0.6% in that limited test; a fixed median proxy on wider pairs does not.
No source/time blocks were supplied, so **realistic between-round dependence,
unseen tails and the complete adaptive championship remain unvalidated**.
Resampling 200 rows does not create 3,000 distinct physical cases or prove future
coverage. No WSL/private-bank access or solver run occurred.

Required public next panel: inspect centered paired-loss tails and strata,
bootstrap complete shared-case contender vectors and relevant blocks, test
incumbent changes, entry/adaptive screening, different cohort sizes, duplicate
and near-copy entrants, alpha exhaustion, regime shifts and all mandatory gates.
Predeclare scenario/metric choices and hold out calibration from verification.
Report false-promotion probability, small-gain power, wait time, and total cost
with uncertainty. No adverse result is suppressed; reference failure is typed
infrastructure, not model inferiority.
