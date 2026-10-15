# Multidimensional analytic toy: eight-profile smoke

`physics-vector-example.json` and `campaign-axes-vector-example.json` vary
dimension 2, 4 or 8, offered finite-grid or continuous-coordinate samples,
9/13/17 actions and coupled-margin strength. Halton coordinates are generated
deterministically with a bounded attempt count. The fallback is included in
the offered set. The two hard margins and buyer value are checked on every
offered action. The reference best is the exact best **offered** action; no
global continuous optimum or exhaustive high-dimensional grid is claimed.

Eight profiles were evaluated for only the N1 toy proxy (plan
`sha256:55cacb725cd59f2a2fe01260ec95ef4342b6f6cf54b80759f004adda0efcdfa2`).
Neighbourhood-blend median Kendall tau was 0.333 and the worst profile was
0.067. This is a plumbing smoke, not a rule ranking or Challenge result.
The exact compressed plan, results and descriptive atlas are:

- `VECTOR_PLAN_8.json.gz` — `sha256:25b11de78a8a95db1d86d16bcbf9041a664bb8da123ffeccd8824709024cb002`
- `VECTOR_RESULTS_8.json.gz` — `sha256:66d3a3eed917faee211ed11b1e857b2fe0d178ee42bc70e6fc32776162462d19`
- `VECTOR_ATLAS_8.json.gz` — `sha256:f76417737432e85db23fb5e1bb3dafeb627f59b0d6b0d69dcb21830ae1b0c595`

No solver, battery reference, hidden bank or independent holdout was used.
