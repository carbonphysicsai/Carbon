# Analytic toy task shape: eight-profile smoke

The separate `physics-shape-example.json` and five-axis
`campaign-axes-shape-example.json` vary one, three or ten analytic wells,
single/weighted/robust objectives, objective weight, sinusoidal roughness and
interior/boundary optimum placement. Each action's truth is evaluated exactly
and the oracle remains the best **offered** action, not a continuous optimum.
The earlier 25-axis inputs were left unchanged.

Eight deterministic profiles were evaluated for only the N1 toy proxy
(plan `sha256:77e47de2ed4d3abaace38003ecdc55cada8a769bcfb126e1ac0d55e5ca651498`).
Neighbourhood-blend median Kendall tau was 0.333 and the worst profile was
0.067. This is a plumbing smoke, not a comparison across rules or an estimate
of performance on a Challenge. The complete compressed plan, results and
descriptive atlas are:

- `TASK_SHAPE_PLAN_8.json.gz` — `sha256:110b0107eeaae6a428f8bca390b4d30c1da8ccefa3eeb94f084739b19ec73342`
- `TASK_SHAPE_RESULTS_8.json.gz` — `sha256:802fc904af808d45b82bca617670b0564ed85ef5c64e6648229025b76c153454`
- `TASK_SHAPE_ATLAS_8.json.gz` — `sha256:c2c3d5db816348a8f756e3f1d28707bc8d5a3412e0a1afef7b12f4a8f2dcd09c`

No solver, public battery reference or independent holdout was used.
