# Error-structure smoke: eight analytic toy profiles

The separate `physics-error-example.json` plus six-axis
`campaign-axes-error-example.json` generated eight deterministic LHS profiles
(plan `sha256:592f802146f5ef96013661c8ca1ce5ec8fa19f7b35bb359be2ac6ef9e32fdfd5`).
Only the N1 toy proxy was evaluated; this smoke checks that the new knobs reach
the candidate rule and atlas. Its neighbourhood-blend median Kendall tau was
0.267 and its worst-profile tau was 0.067 across these eight profiles. Axis
associations are descriptive median splits, not Sobol effects or causal
effects. No rule is selected from this smoke.

The exact compressed plan, results and atlas are `ERROR_STRUCTURE_PLAN_8.json.gz`
(`sha256:36fe11e0d3c82c26c5fddeb865b53f3a907c139747944207b8c4178d8d91168d`),
`ERROR_STRUCTURE_RESULTS_8.json.gz`
(`sha256:2a8127f064fc0abcdffdca9d21d756c4f0935cd1a13469cac615fee7cff31e7f`),
and `ERROR_STRUCTURE_ATLAS_8.json.gz`
(`sha256:fa4229a16c1c40114488b4960e47639305a82b2e916a9e8180024d8bed00acc7`).
All data are synthetic development assumptions; no Challenge reference or
held-out material was used.
