# Championship economics — owner summary

**Research simulation, not adopted economics or an income forecast.** Recommendation: consider **10% daily reward reduction (retention d=0.90)** as the primary alternative to current daily halving, with **20% reduction (d=0.80)** as the stronger-burn option. Keep equal Challenge shares; expand the denominator only through an owner-approved policy with a credible, runnable research budget. The simulation does not identify an optimal decay or split.

We implemented the announced daily championship with the posted margin AND paired t guard, shared fresh Gaussian comparison statistics, frozen king, top-ten nomination, one slot/coldkey, an assumed-grain ladder and king-retaining ties. Actual measured ladder grain remains HUMAN_INPUT. The **1%** ceiling is not injected as a random false crown. Primary payout clocks preserve the current same-miner no-reset policy.

**Conditional results:** synthetic population, illustrative N=4, **160 episodes** over **180 days**. Low/base/high below are **95% Monte Carlo intervals**, not real-world forecast uncertainty.

| Daily retention | Crown changes / 30 days L/B/H | Paid battery allocation %, L/B/H | Newcomer crown within first 30 days %, L/B/H |
| --- | --- | --- | --- |
| 0.5 | 1.48 / 1.52 / 1.56 | 10.74 / 11.00 / 11.25 | 9.89 / 12.34 / 14.80 |
| 0.8 | 1.54 / 1.58 / 1.62 | 25.33 / 25.87 / 26.41 | 9.86 / 12.50 / 15.14 |
| 0.9 | 1.33 / 1.36 / 1.39 | 38.13 / 38.78 / 39.43 | 8.26 / 10.78 / 13.30 |
| 0.95 | 0.94 / 0.98 / 1.02 | 45.65 / 46.69 / 47.73 | 7.15 / 9.22 / 11.29 |
| 1 | 0.78 / 0.83 / 0.89 | 97.72 / 100.00 / 100.00 | 4.46 / 6.25 / 8.04 |

At d=0.90, expected **30-day-capped tenure** is **17.33 / 17.70 / 18.06 days**; unrestricted mean tenure is unidentified. The largest recipient takes **37.65 / 38.90 / 40.14%** of paid targets; the top three take **82.64 / 84.16 / 85.68%**.

Fixed-effort controls leave turnover unchanged when decay/split changes. Adaptive responses produce the differences above. Slower decay funds more research/defense; very slow or absent decay raises concentration and reduces newcomer opportunities in this assumed world. More crown changes alone do not mean more value: doubling the illustrative split denominator reduces effort and net latent accuracy gain even when turnover rises.

Exact copies cannot beat identical predictions. Imitation **plus real improvement** takes much of the reward under the assumed cheap access route; this is not proof that Carbon can be copied at that cost. Admission/IP treatment remains separate. The no-reset rule discourages an aged king's own research; enabling a qualified self-reset increases advances and concentration, so it is a separate owner decision.

[Report](REPORT.md), [model](MODEL.md), [assumptions](assumptions.json), [results](results.json), [CSV](results.csv), [sources](SOURCES.md) and [figure](economics.svg) retain the controls, adverse findings and gaps. Missing inputs are actual miner effort/costs, growth, copying access, available pool/settlement, score-proof decision value and the caller's self-entry interpretation. No solver/model run, mining, spend, hidden material or AX42 was used.
