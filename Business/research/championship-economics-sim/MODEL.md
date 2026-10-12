# Model contract and interpretation

**CHAMPIONSHIP-ECONOMICS-SIM-01 — DEVELOPMENT research.** This is a conditional simulation of target allocation and miner choices. It is not a validator, a game-theoretic equilibrium, an observed payout study, a forecast of Alpha income or evidence of physical/decision value. All free quantities and alternatives are in [assumptions.json](assumptions.json); immutable sources are in [SOURCES](SOURCES.md).

## Fixed owner rule and source policy

The [championship design](https://github.com/carbonphysicsai/Carbon/blob/24e03bf9e7f5e34a7a9425ded33bc2736da1b298/.agent/decisions/2026-10-11-OWNER-BATTERY-CHAMPIONSHIP-01.md) and [amendment](https://github.com/carbonphysicsai/Carbon/blob/24e03bf9e7f5e34a7a9425ded33bc2736da1b298/.agent/decisions/2026-10-11-OWNER-BATTERY-CHAMPIONSHIP-02.md) control: daily fresh shared batch, stored king plus top **10** eligible candidate models, offered **4,000** cases, strict **2.25%** relative observed improvement AND a positive paired-improvement t guard with family target **1%/round**. Ties retain the king. The comparison here uses the accuracy-final mean-error interpretation; an unmeasured design-question composite is not invented.

The [public decay code](https://github.com/carbonphysicsai/Carbon/blob/24e03bf9e7f5e34a7a9425ded33bc2736da1b298/carbon/rewards/winner_decay.py) pays the new eligible winner its full slot during the initial **24 hours**, then halves each **24 hours**. Every listed Challenge receives its budget fraction; the remainder burns. The [registered policy](https://github.com/carbonphysicsai/Carbon/blob/24e03bf9e7f5e34a7a9425ded33bc2736da1b298/carbon/rewards/weight_policies/testnet-winner-v1.json) currently lists **three** Challenges, not the simulation's illustrative four. A listed but unserved/ineligible slot burns. The [eligibility code](https://github.com/carbonphysicsai/Carbon/blob/24e03bf9e7f5e34a7a9425ded33bc2736da1b298/carbon/rewards/winner_eligibility.py) keeps the previous clock for the same hotkey/coldkey; self-improvement resets are not implemented even if a factor were set. Source support is not evidence of deployment or settlement.

The simulation uses normalized daily target fractions and daily round boundaries, rather than intra-day chain epochs/Q12 rounding. Full pool E means the **miner-directed pool available to Carbon's allocation**, not all protocol rewards. [Bittensor's dTAO description](https://www.bittensor.com/dtao-whitepaper) separates miner, validator and owner rewards. We do not simulate consensus clipping, bonds, validator disagreement, settlement lag, token price/liquidity or receipts.

## Synthetic population and research choices

**Late authority update:** [OWNER-BATTERY-CHAMPIONSHIP-03](https://github.com/carbonphysicsai/Carbon/blob/dcbc13d59a049e1d8bdc380d50fe15a9fa25604a/.agent/decisions/2026-10-11-OWNER-BATTERY-CHAMPIONSHIP-03.md) adds one contention slot per coldkey, permits the king's coldkey to enter one other model, immediate pooled screening display through a per-coldkey ladder, and D6 exact-recipe dedup across coldkeys. The primary population has one candidate slot per known synthetic owner and rejects exact copied identities. It uses a relative-log-score ladder surrogate, keeps the artifact associated with the best displayed submission and ranks by that display with synthetic commit order as tie priority. Actual registered score units/operator and measured grain remain HUMAN_INPUT. Illustrative grain points 0.5% / 1% / 2.5% are ASSUMPTION; only the announced floor is sourced. Display updates only on a new admitted artifact. No-ladder is counterfactual; bank probing/overfit, per-hotkey rate limits and hidden-window dependence remain unmodeled.

The new public rev-5 helper keeps the king when top qualifying contenders exactly tie. This research does too. Its source currently accepts relative gain >= margin whereas the original owner wording says greater than; the research preserves strict >. That deterministic-boundary seam has zero probability in the continuous synthetic sweep and needs caller/authority reconciliation before an exact runtime-equivalence claim. No runtime patch or policy choice is made here.

Base **ASSUMPTION** population: **4 experts, 8 steady researchers, 4 imitators, 4 holders and 4 newcomers**. Newcomers arrive on day **30**; horizon **180 days**. Every episode varies initial candidate gaps and skills. Initial standing candidates have normalized mean-error gaps **2%/7%/12%** (uniform endpoints, midpoint shown); the king begins at unit mean error. Skill multipliers are uniform **0.7/1.0/1.3**. These are synthetic labels and normalized errors, not actual Carbon members.

| Role | ASSUMPTION base log research-growth coefficient/day; low/base/high | ASSUMPTION GPU hours/research day; low/base/high | Pricing proxy |
| --- | --- | --- | --- |
| Expert | 0.003 / 0.006 / 0.012 | 4 / 8 / 24 | Advertised L40S rate |
| Steady | 0.0015 / 0.003 / 0.006 | 1.5 / 3 / 9 | Advertised A40 rate |
| Imitator who also improves | 0.0015 / 0.003 / 0.006 | 1.5 / 3 / 9, plus imitation effort | Advertised A40 rate |
| Holder | 0 / 0 / 0 | 0 / 0 / 0 research | No new research |
| Newcomer | 0.0025 / 0.005 / 0.01 | 2 / 4 / 12 | Advertised A40 rate |

[Runpod](https://www.runpod.io/pricing) lists A40 **USD 0.59/hour** and L40S **USD 1.09/hour** in the reviewed page. Those fixed source points are not interchangeable performance estimates. Transfer to hypothetical miner workloads is ASSUMPTION; actual registered reconstruction budget and owned-hardware economics are not measured. Research overhead is **ASSUMPTION USD 0/5/100 per effort day**; imitation effort **0.05/0.25/2 GPU-hours**. The sweep multiplies cost by **0.5/1/3** and tests a higher-overhead case. Registration, capital, tax and additional labor/opportunity costs are excluded.

Research advances a candidate toward an assumed normalized-error asymptote, with diminishing growth and random breakthroughs. Every attempted research day incurs cost, including rejected proposals. Build/gate rejection is **ASSUMPTION 0/5/20%**; rejected work cannot enter the current candidate. Initial standing models are assumed eligible; all admitted models satisfy the hard checks by construction. This does not calibrate false-feasibility gates or relax a physical limit.

Imitation may start from the published incumbent-quality proxy, with penalty and correlation from the manifest. Exact imitation uses identical artifact predictions. Approximate imitation alone is weaker by an assumed gap; imitation plus research can genuinely improve the latent mean. Access, quality, cost and time to reproduce a real incumbent are **unmeasured**; the [showcase study](https://github.com/carbonphysicsai/Carbon/blob/24e03bf9e7f5e34a7a9425ded33bc2736da1b298/Business/research/showcase-distillation-risk/README.md) supplies no universal safe exposure or copy cost. “Imitator” does not assert IP infringement or fraudulent authorship. Rights/admission evidence is separate from scientific score.

An actor has one standing candidate plus the separately stored king. A king owner's new artifact may occupy its one contender slot, consistent with amendment 03; no-self-entry is counterfactual. No production API is modified. Synthetic admission order resolves entry ties; no chain commitment is simulated. Known exact copied identities are refused by the admission surrogate, and identical predictions share signal/noise in the statistical control. Near-copy grouping or an operational identity detector is not invented.

## Two effort regimes

**Fixed effort:** experts/steady/newcomers research every active day; imitators follow the selected imitation strategy; holders retain existing models. Altering decay or split changes payments only. Identical random streams must produce identical scientific trajectories; a regression test enforces this.

**Adaptive:** risk-neutral actors choose hold, independent research, pure imitation or imitation-plus-research within their declared capabilities. They use noisy synthetic public/practice beliefs, the stored king's published-performance proxy, an approximate nomination probability and a rolling investment horizon. Research is chosen only when forecast gross target rent exceeds modeled cost. Current kings compare the expected defensive benefit against holding their aged payout; the counterfactual self-reset grants a fresh clock only after the same accepted comparison.

This is a **bounded behavioral hypothesis**, not a Nash equilibrium or calibrated response curve. The base planning horizon is **ASSUMPTION 14 days**; short planning and belief noise are tested. It assumes static-rival forecasts, ignores risk aversion and does not model miners reallocating between Challenges. Holder roles are exogenous. A sophisticated agent, coordinated actors, employers or intrinsic researchers may behave differently.

Forecast gross rent over horizon H uses:

**V(age) = E × share × d^age × sum[j=0…H−1] {d × discount × (1−hazard)}^j.**

The survival hazard, discount and forecast model are ASSUMPTION, distinct from the simulated realized tenure. Money influences research/entry decisions only; it never enters the simulated official comparison.

## Shared fresh grading model

No real case or model is run. We draw sufficient statistics for an **assumed IID Gaussian paired-loss world** with declared effective draw count B. Normalized candidate mean error is latent quality, not physical truth. Gaussian residuals can imply negative individual loss observations; this is a comparison surrogate, not an admissible synthetic physics dataset.

For every round, candidates are frozen/nominated before the fresh grading stream. King and candidates share common-case and incumbent components. Exact copies have zero paired difference/SE. Centered normal components projected onto the common/king directions produce joint paired variance estimates using normal coordinates and chi-square residual norms; means and centered variances are independent in this assumed world. [NumPy's chi-square definition](https://numpy.org/doc/stable/reference/random/generated/numpy.random.Generator.chisquare.html) and [Student-t guidance](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm) support the statistical construction.

The king's observed mean is the relative-margin denominator. Promotion requires observed difference greater than **both** the posted margin times that mean and **t(1−0.01/10; B−1) × paired SE**. The guard tests positive improvement; it does **not** test that the true gain exceeds the posted margin with confidence. Consequently a smaller real gain may occasionally pass the observed-margin bar. That is reported separately from a false promotion of a no-better model.

The base takes effective B equal to offered case count as **ASSUMPTION**, not knowledge of hidden duplicates. The half-information case keeps offered cases fixed and models fewer independent units. Real duplicate collapse, strata, weights, q questions, non-Gaussian tails and reference uncertainty need the actual registered measurement contract. No official seeds, identities, draws or reference material are read.

At large df, the t quantile uses a third-order expansion independently checked against SciPy for the relevant counts; simulator runtime needs only existing NumPy. Under this normal model each null pair has level at most alpha/K, and the union bound controls the fixed round's family despite shared king/case dependence. We do **not** inject a separate 1% false-crown event or claim this proves the real championship's error rate. Exact-copy and all-null/power controls measure the implemented surrogate.

## Outputs and uncertainty

- Crown turnover counts **owner changes**; model promotions, self advances and payout-clock resets are separate.
- Tenure is **E[min(T,30 days)]** for spells beginning early enough to have full capped follow-up. It is a lower-bound/restricted expectation for this calendar cohort; unrestricted expected tenure and a stationary long-run mean are not identified. Terminal spells are flagged, never dropped to manufacture a short mean.
- Concentration is recipient top-one/top-three paid fraction and HHI, including zero-pay actors in role summaries. Burn is measured within the battery slot; other Challenges are not secretly modeled.
- Newcomer chances are fractions of the delayed newcomer cohort crowned within their first **30 days**, or by the horizon, summarized by episode.
- Activity, modeled cost, gross target, net target-minus-cost and role-specific returns show improvement/hold/imitation incentives. Net target is not miner profit.
- Gross positive log advances and net final log error reduction are separate; false promotions cannot inflate the latter by counting only recoveries.
- Missed nomination counts eligible other-actor candidates with true gain above the posted floor excluded from the top-ten screen.

Low/base/high in results are **approximate 95% Monte Carlo mean intervals over independent episode clusters**, not uncertainty bands over real-world assumptions. All-zero/all-one bounded outputs use conservative episode-indicator exact-binomial limits, avoiding fake zero rare-event uncertainty. Grading controls use Wilson intervals over independent synthetic rounds. Same public random streams support comparisons; changing an economic option can alter actions and therefore the subsequent path.

The grid/sensitivities are descriptive. Intervals are not simultaneous selection-adjusted claims that one policy is optimal. Free-parameter low/base/high values and stress scenarios carry the larger, uncalibrated uncertainty. Preserve negative results and gaps.
