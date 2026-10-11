# Statistical sources and evidence discipline

Primary sources accessed 2026-10-11. Exact reviewed owner input hashes and scope
are in [INPUT_PROVENANCE](INPUT_PROVENANCE.md). Those inputs are public stand-ins,
not an independent record of actual private-bank or mainnet behavior.

| Source | What it supports / limit |
|---|---|
| [Holm 1979 original record](https://www.jstor.org/stable/4615733) and [R's official implementation documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html) | Strong fixed-family FWER under arbitrary p-value dependence, provided the individual null p-values are valid. Original full text was not readable in the web tool; implementation documentation supplies the accessible statement |
| [Howard et al., confidence sequences](https://arxiv.org/abs/1810.08240) | Time-uniform mixture/empirical-Bernstein inference under explicit conditional assumptions; not permission to substitute a sample SD into an arbitrary Gaussian process |
| [Ramdas et al., nonnegative martingale foundations](https://arxiv.org/abs/2009.03167) | Anytime validity and optional stopping need an appropriate e-process/p-process; a name alone is insufficient |
| [Foster and Stine, alpha-investing](https://deanfoster.net/research/edc.pdf) | Classic investing controls mFDR with a wealth/reward contract; not strong FWER for the proposed mixed population of contenders |
| [Waudby-Smith and Ramdas, finite-population inference](https://proceedings.neurips.cc/paper/2020/hash/e96c7de8f6390b1e6c71556e4e0a4959-Abstract.html) | Without-replacement evidence has a different sampling model; finite-bank identity and dependence cannot be discarded |
| [Statsmodels confidence-interval documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html) | Wilson proportion intervals; this audit implements the formula independently and adds no statsmodels dependency |

Carbon main pin `2cfc2508e267e1b794d32fa617603bcc7e122397`:
[owner v3 finals decision](https://github.com/carbonphysicsai/Carbon/blob/2cfc2508e267e1b794d32fa617603bcc7e122397/.agent/decisions/2026-10-11-OWNER-BATTERY-V3-FINALS-01.md),
[#1105/#1108 takeover crosswalk](https://github.com/carbonphysicsai/Carbon/blob/2cfc2508e267e1b794d32fa617603bcc7e122397/Business/research/takeover-rules-survey/CARBON_CROSSWALK.md),
[takeover recommendation](https://github.com/carbonphysicsai/Carbon/blob/2cfc2508e267e1b794d32fa617603bcc7e122397/Business/research/takeover-rules-survey/RECOMMENDATION.md),
[invariants](https://github.com/carbonphysicsai/Carbon/blob/2cfc2508e267e1b794d32fa617603bcc7e122397/.agent/INVARIANTS.md).

The inherited cost/source scenario is I3's **91 CPU-s/case** attributed to #1088;
it is treated as planning evidence, not a measured championship tariff. Native
Python diagnostics and exact-head engineering CI do not confer scientific,
security, qualification or network authority. No tolerance, alpha, case reuse,
incentive wealth or production score is adopted by this PR.
