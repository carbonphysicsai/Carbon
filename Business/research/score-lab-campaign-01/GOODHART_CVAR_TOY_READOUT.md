# CVaR value-view Goodhart smoke: analytic toy only

`goodhart-cvar-search-example.json` declares a 0.25 worst-tail fraction as an
illustrative toy assumption. For each target task the value view averages the
worst ceil(25% × count) of its target, neighbour and extrapolated losses.
It uses those related tasks as an equally weighted finite toy distribution.
Score questions and score feedback remain separate from these buyer losses.

For N1 alone, the score-maximising toy member lost 0.18815 against the
approximate value-search member's 0.05165, a sampled gap of +0.13650 toy loss
units. The value search is random plus coordinate hill climb; its result is
not an exact CVaR oracle. One proxy, one search seed and an invented task mix
give no rule ranking, battery effect size or adopted tail fraction.

The aggregate artifact is `GOODHART_CVAR_TOY_N1.json.gz`
(`sha256:ab42d50686d5873d7792ee71889da6040a4bf5f1708b1d3714f90b09bf386186`).
No public battery reference, independent holdout or protected bank was used.
