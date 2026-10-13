# CVaR value-view Goodhart smoke: analytic toy only

`goodhart-cvar-search-example.json` declares a 0.25 worst-tail fraction as an
illustrative toy assumption. For each target task the value view averages the
worst ceil(25% × count) of its target, neighbour and extrapolated losses.
It uses those related tasks as an equally weighted finite toy distribution.
Score questions and score feedback remain separate from these buyer losses.

Seven of ten proxies produced scored searches; three were unscored. The
sampled score-maximiser minus approximate value-search loss gap was +0.13650
for N1, +0.01762 for N4, zero for N2, N3 and V2r2 k1, and -0.00833 for
V2r2 k3 and k5. A negative gap means the approximate value search missed the
score-search point; it is not evidence that a rule beats an exact CVaR oracle.
For N1, the two toy losses were 0.18815 and 0.05165. One search seed and an
invented task mix give no rule ranking, battery effect size or adopted tail
fraction.

The aggregate artifact is `GOODHART_CVAR_TOY_N1.json.gz`
(`sha256:ab42d50686d5873d7792ee71889da6040a4bf5f1708b1d3714f90b09bf386186`).
The ten-proxy aggregate is `GOODHART_CVAR_TOY_ALL10.json.gz`
(`sha256:c63a999afed00c271ec27afc96ed36149369a5a9f8dd0bc9bb86498011a494f5`).
No public battery reference, independent holdout or protected bank was used.
