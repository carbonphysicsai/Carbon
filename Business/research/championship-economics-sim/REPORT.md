# Championship economics: measured conditional simulation

**CHAMPIONSHIP-ECONOMICS-SIM-01; research/recommendation only.** Source authority is pinned in [SOURCES](SOURCES.md). Every numerical output below is generated from [public synthetic assumptions](assumptions.json), not observed miners or payouts. Current announced scoring and current public decay are modeled prospectively. No live economics, physical solver/model run, hidden data, AX42 or spend.

## Recommendation and the objective trade-off

For owner consideration, take **d=0.90 (10% daily reduction)** forward as the primary slower-decay option; retain **d=0.80 (20% reduction)** where faster burn/lower passive rent is the priority. **d=0.95 (5% reduction)** is an explicit longer-research/defense option with more concentration and weaker newcomer results in the base population. **d=1** is a useful no-decay control, not the recommended default. These are ASSUMPTION option points, not statistically selected optimal policy or calibrated economic prescriptions.

Keep the equal-share structure. Current public policy lists N=3; illustrative N=4 and N=8 are prospective comparisons, not an adopted launch count. Expanding a denominator reduces the available prize per research problem. Owner chooses membership from readiness and measured effort/economics, never by comparing raw Challenge scores. A reserved/unready share continues burning under the existing policy unless the owner adopts a new policy; this research does not reassign it.

Do not optimize solely for crown turnover, burn or low imitation share. Useful reference-relative progress, entry, funded research and concentration trade off. Actual decision value still needs the score proof/equal-budget evidence; latent mean-error improvement here is not engineering gain.

## Experimental record

There are **84 scenarios**, each with **160 episode clusters**; base horizon **180 days**, with a **365-day** sensitivity. The base population comprises **24** synthetic actors of different skill/cost/capability, with delayed newcomers. The daily pool is **ASSUMPTION USD-equivalent 100/1,000/10,000**, never a token conversion, observed emission or guaranteed income. Base costs transfer published GPU prices to assumed effort and add assumed overhead.

Manifest SHA256: **b9d448656d7ed1a0dde5373617071f9dd40646b74c5868b68b517170cd3ea874**. Generated data records NumPy version; code/source are bound by this PR's immutable head. Native numerical generation is DEVELOPMENT evidence; canonical acceptance tests validate code/controls, not real incentive qualification. Reproduction commands and exact pinned checks are below.

The latest amendment 03 arrived during research. The primary runs now include one slot per known coldkey, exact-identity admission refusal, king self-entry and a relative-log ladder surrogate. The actual measured grain and score/operator remain HUMAN_INPUT. Ladder-grain and no-ladder sensitivity rows are separate; [MODEL](MODEL.md) explains the approximation and the strict-margin/helper boundary seam.

The broad grid varies daily retention and equal shares under **fixed effort** and **adaptive bounded expected-return choices**. Sensitivities change growth, noise, costs/pool, copying, screening bias, belief/planning, newcomer quality, self-reset/self-entry, effective information and horizon. They do not change the posted margin or error target.

## Decay, turnover, tenure and concentration

All tables show **MC low / mean / high**, approximate **95% episode-cluster** intervals conditional on the same assumption world. Boundary probability outputs use conservative episode-indicator limits; controls use Wilson. These are not simultaneous policy-selection tests and omit model/behavior uncertainty.

Base adaptive population, illustrative **N=4**:

| Retention d | Crown changes / 30 days | E[min(tenure,30 days)] | Paid slot % | Largest recipient's paid % | Newcomer first-30-day crown % |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 1.48 / 1.52 / 1.56 | 15.57 / 15.87 / 16.16 | 10.74 / 11.00 / 11.25 | 37.02 / 38.09 / 39.17 | 9.89 / 12.34 / 14.80 |
| 0.8 | 1.54 / 1.58 / 1.62 | 15.23 / 15.52 / 15.80 | 25.33 / 25.87 / 26.41 | 36.37 / 37.51 / 38.64 | 9.86 / 12.50 / 15.14 |
| 0.9 | 1.33 / 1.36 / 1.39 | 17.33 / 17.70 / 18.06 | 38.13 / 38.78 / 39.43 | 37.65 / 38.90 / 40.14 | 8.26 / 10.78 / 13.30 |
| 0.95 | 0.94 / 0.98 / 1.02 | 19.46 / 20.08 / 20.70 | 45.65 / 46.69 / 47.73 | 40.94 / 42.53 / 44.12 | 7.15 / 9.22 / 11.29 |
| 1 | 0.78 / 0.83 / 0.89 | 19.52 / 20.25 / 20.98 | 97.72 / 100.00 / 100.00 | 56.18 / 58.97 / 61.77 | 4.46 / 6.25 / 8.04 |

The expected tenure column uses spells starting early enough for full capped follow-up. At d=0.90, **10.87 / 11.11 / 11.35%** of all observed spells are terminal/censored. An unrestricted mean or stationary geometric tenure is not justified. The declared **1% false ceiling** cannot be converted into an assumed one-change-per-century-of-days process.

At d=0.90, top-three paid share is **82.64 / 84.16 / 85.68%**, HHI **0.280 / 0.290 / 0.300**. Concentration is among paid recipients, not the burn UID or validator dividends. Paid slot fraction and paid share of the subnet miner pool are different: the latter is **9.53 / 9.70 / 9.86%** for this one modeled slot; other Challenges' outcomes are not fabricated.

**Fixed-effort control:** crown changes remain **1.29 / 1.35 / 1.40 / 30 days** at both d=0.50 and d=0.90. Paid slot fraction rises from **9.38 / 9.74 / 10.11%** to **35.54 / 36.64 / 37.75%**. Changing payout arithmetic alone cannot improve models. The test requires identical fixed-effort scientific trajectories across these options.

**Adaptive activity:** research occupies **8.80 / 9.11 / 9.43%** of active actor-days at daily halving, **11.63 / 11.96 / 12.30%** at d=0.90, and **13.90 / 14.20 / 14.50%** without decay. This mechanism comes from assumed return forecasts, not an empirically measured effort elasticity. Very slow/no decay also funds incumbent defense; fewer turnovers can accompany more latent accuracy progress.

## Split sensitivity and budget viability

Adaptive d=0.90, other assumptions held fixed:

| Illustrative listed N | Fresh slot %, fixed point | Crown changes / 30 days | Research actor-days % | Net log accuracy gain | Newcomer first-30-day crown % |
| --- | --- | --- | --- | --- | --- |
| 3 | 33.33 | 1.28 / 1.32 / 1.36 | 12.09 / 12.46 / 12.84 | 0.31 / 0.32 / 0.33 | 7.31 / 9.69 / 12.07 |
| 4 | 25.00 | 1.33 / 1.36 / 1.39 | 11.63 / 11.96 / 12.30 | 0.30 / 0.31 / 0.32 | 8.26 / 10.78 / 13.30 |
| 8 | 12.50 | 1.50 / 1.54 / 1.58 | 10.23 / 10.59 / 10.94 | 0.28 / 0.28 / 0.29 | 9.58 / 11.88 / 14.17 |

With fixed effort, the split leaves comparisons/turnover identical and scales gross targets by the reciprocal denominator. In adaptive runs, smaller prizes change willingness to research/defend. The N=8 world can turn over more often than N=4 while delivering **less net latent accuracy progress**. A turnover KPI by itself can reward churn.

The focused-battery counterfactual gives battery **50%** of the modeled pool with other assumptions unchanged. It is an unequal-share option, **not approved 1/N policy**, and the rest of that portfolio is not simulated. Use its row to assess a temporary measured-work programme only if the owner wants that comparison; unequal allocations need an explicit budget/rights/version, not a change to scientific grades.

An analytical new-owner prize ceiling, with no future displacement or discount, is:

**lifetime gross target ≤ E / {N(1−d)}** for d<1.

For the **ASSUMPTION E=1,000, N=4** illustration, d=0.50 caps an indefinitely held new tenure at **500 USD-equivalent**; d=0.90 at **2,500**; d=0.95 at **5,000**. Those derived fixed points are ceilings, not expectations or receipts. At N=8 they halve; at d=1 no finite infinite-tenure ceiling exists. Finite survival, discount and unsuccessful attempts reduce the usable return.

A proposed viability test is **P(win) × expected gross tenure value > fully costed research investment**, with actual probability/cost/settlement inputs **HUMAN_INPUT**. The population model excludes several real costs. Gross target-minus-modeled-cost is therefore not profit or an earnings claim.

## Improvement, imitation and holding

| Sensitivity at d=0.90, N=4 | Crown changes / 30 days | Newcomer first-30-day crown % | Imitator-role paid share % | Net log accuracy gain |
| --- | --- | --- | --- | --- |
| Exact imitation only | 0.96 / 1.01 / 1.07 | 17.77 / 20.31 / 22.85 | 0.00 / 0.00 / 2.28 | 0.24 / 0.25 / 0.26 |
| Approximate imitation only | 0.96 / 1.01 / 1.07 | 17.77 / 20.31 / 22.85 | 0.00 / 0.00 / 2.28 | 0.24 / 0.25 / 0.26 |
| More imitation-plus-research actors | 1.72 / 1.76 / 1.80 | 3.95 / 5.63 / 7.30 | 82.80 / 84.74 / 86.69 | 0.38 / 0.39 / 0.39 |
| New entrant already 3% better | 1.43 / 1.47 / 1.50 | 47.96 / 50.47 / 52.98 | 38.75 / 42.02 / 45.30 | 0.35 / 0.35 / 0.36 |
| New entrant 12% behind | 1.29 / 1.33 / 1.36 | 0.00 / 0.00 / 2.28 | 65.94 / 69.29 / 72.64 | 0.29 / 0.29 / 0.30 |
| Smaller assumed target pool | 1.18 / 1.22 / 1.26 | 13.82 / 16.56 / 19.31 | 58.47 / 62.11 / 65.75 | 0.21 / 0.21 / 0.22 |
| Higher assumed effort overhead | 1.34 / 1.39 / 1.43 | 9.89 / 12.34 / 14.80 | 46.99 / 50.88 / 54.77 | 0.24 / 0.24 / 0.25 |
| Self-reset counterfactual | 0.63 / 0.69 / 0.74 | 4.84 / 6.72 / 8.60 | 36.98 / 42.05 / 47.12 | 0.37 / 0.38 / 0.39 |
| No self-entry interpretation | 1.71 / 1.75 / 1.79 | 6.78 / 9.06 / 11.34 | 47.46 / 51.48 / 55.49 | 0.31 / 0.31 / 0.32 |

Exact copying of identical predictions has zero paired difference; it cannot clear the margin or noise guard. The exact-copy control observed no wins and the algebra enforces that in this surrogate. Approximate copying without improvement also gets no paid share in the selected adaptive runs: miners forecast insufficient return and hold. This is **not** a claim that all possible copying, model fingerprint fraud or submission attacks are defeated.

Imitation plus research is different. Under the assumed low-cost incumbent-quality access, the base imitator group takes **55.22 / 59.09 / 62.96%** of paid targets. Those wins generally improve latent mean error. The result warns that a championship may reward efficient reuse plus improvement rather than pay original discovery alone. Whether a real copy route exists, its off-grid quality/cost and rights status are unmeasured. Prior similarity must not become an invented scientific score term.

Increasing that group's population changes both competition and nomination pressure. The lower newcomer outcome is conditional on the assumed population/access law; it is not a measured subnet complaint or universal effect. The screen-bias sensitivity distinguishes nomination gaming from final fresh evaluation. Cross-owner Sybil linkage/attribution and collusion are not modeled: independent known actors are assumed. A single person alternating unlinked keys requires a separate identity/clock audit.

The current no-self-reset rule means an already-aged king receives no fresh prize merely for improving its model. Under fast halving the adaptive base has **0.00 / 0.00 / 0.00 self advances**, while the fixed-effort base still produces **7.57 / 8.01 / 8.45** over the horizon. Independent improvements may happen without an economic return; a quality freeze and passive reward are distinct issues.

The self-reset counterfactual uses the same accepted comparison, not an easier scientific bar. It raises self advances to **8.92 / 9.48 / 10.04**, but raises largest-recipient share to **58.61 / 61.63 / 64.65%** and reduces newcomer opportunities. This supports a separate owner decision on rewarding substantive self progress, with actor/artifact attribution and withholding/reset abuse reviewed. No self-reset is adopted here.

## Ladder sensitivity

At d=0.90, illustrative grains 0.5% / 1% / 2.5% produce crown-change MC triplets **1.33 / 1.36 / 1.39**, **1.31 / 1.34 / 1.38**, **1.26 / 1.30 / 1.33** per 30 days. First-30-day newcomer chances are **8.26 / 10.78 / 13.30%**, **7.76 / 10.16 / 12.55%**, **6.94 / 9.22 / 11.50%**. The no-ladder counterfactual has **1.38 / 1.42 / 1.45** changes. These illustrative log-grain outcomes are not a contamination guarantee or a measured grain selection.

## False crowns, marginal wins and adverse findings

All-null shared-batch controls use **20,000** independent synthetic rounds per noise level. The low/base per-case-noise settings produced **0** false crowns; Wilson upper bound **0.0192%**, not proof of zero risk. At the high-noise setting, the measured rate is **0.713 / 0.830 / 0.966%** (MC 95%), within the declared ceiling in this Gaussian world. An additional exact-copy control used **20,000** rounds with zero wins. These controls validate internal implementation under assumptions; they do not validate physical safety, real nonnegative/tail losses, stratum gates or the production error claim.

At the base noise level, a contender with true **1%** mean-error improvement won **0.177 / 0.260 / 0.381%** of control rounds, while a true **3%** improvement won **95.36 / 95.77 / 96.15%**. The true **2.25%** boundary is about half-power in that control. Counts, settings and full curves are in [results](results.json).

The rule tests a positive improvement plus an observed margin; it is not a lower confidence bound above the margin. In the base adaptive d=0.90 population, **29.32% of pooled model promotions** have positive true synthetic gain at or below the posted margin. They are **not no-better false crowns**. This is an adverse/interpretation finding to preserve; changing the null or useful-gain rule would be an owner scientific decision, outside this job.

Other negative findings: unchanged reward arithmetic does not cause discovery; unrestricted tenure is unestimated; newcomers who start far behind can fail to enter economically; very slow decay increases concentration; imitation access and endogenous behavior are not calibrated; source same-miner clock policy differs materially from “every better model starts fresh.” No favorable economics repairs an unsafe or low-value judge.

## What to measure before adopting an option

Owner decisions remain decay, split membership/allocation, same-actor reset/admission, attribution and deployment. Needed public/canary receipts: actual effort and full costs by construction level; available miner pool and settled targets; practice-to-fresh-grade uncertainty; self-entry/caller behavior; distinct actor/artifact identity; newcomers' initial gap and research progression; legal/technical copying access; eligibility/refusal and outcome delay. Use them to update the assumption manifest prospectively, not silently reinterpret this evidence.

Compare d=0.80/0.90 options against current halving using the same published target/clock accounting and registered scientific rule. Predetermine the observation horizon and outcomes; include adverse findings and intrinsic/low-budget miners. No automatic rollout, “optimal rate” claim or miner earnings promise follows.

## Reproduce and validation

```sh
python Business/research/championship-economics-sim/simulate.py
python Business/research/championship-economics-sim/test_simulate.py
python Business/research/championship-economics-sim/plot_results.py
```

NumPy comes from Carbon's existing science-jax environment; plotting additionally requires Matplotlib. The native run used CPython **3.12.14**, NumPy **2.5.4**, Matplotlib **3.11.2**; SciPy **1.18.1** independently checked the t expansion but is not a simulator dependency. Cross-version RNG/float bit identity is not promised; preserve software identity with evidence.

Pinned format/static checks use **Black 26.5.1** and **Ruff 0.16.3**. Native Black's CLI stalled on this shared checkout's discovery; its pinned library formatted/checked the explicit files, and Ruff used explicit files without repository ignore traversal. Nine focused controls pass; the canonical CPU collector runs the same tests in exact-head CI. Native generation is DEVELOPMENT evidence, not canonical runtime acceptance or qualified economics. The [working contract](WORKING_CONTRACT.md) records scope and maturity.
