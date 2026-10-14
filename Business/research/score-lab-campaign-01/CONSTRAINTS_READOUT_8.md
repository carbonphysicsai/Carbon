# Zero-to-five hard-limit toy smoke

`physics-constraints-example.json` and `campaign-axes-constraints-example.json`
vary the number of analytic hard margins from 0 to 5 and shift their offsets.
Every reference and prediction carries the same margin grammar. A zero-limit
problem requires complete coverage; its offered actions are all feasible.
Constraint offsets change feasibility without changing the objective.

The eight-profile LHS smoke evaluated only the N1 proxy. Its median
neighbourhood-blend Kendall tau was 0.067; the worst-tenth descriptive tau was
-0.333. The score-path gamer was in the proxy's top half in 7/8 profiles.
These figures show sensitivity, not a rule choice: eight profiles and one proxy
cannot establish a useful score or a Challenge threshold. The plan identity is
`sha256:69cf24697338f3d58c610032913b178b6e192eacf66c672beb4bc0c11be832f6`.

- `CONSTRAINTS_PLAN_8.json.gz`: `sha256:278a9e55139db9a511530c897cababb962434233f18383d5c1b0d6b6a843c122`
- `CONSTRAINTS_RESULTS_8.json.gz`: `sha256:e167adea02eda37c94f2ba6710c8a05b43d66159265f4c5d067b76819b3471de`
- `CONSTRAINTS_ATLAS_8.json.gz`: `sha256:75ca2a7d7bbe7898583dcb9d1298dd6adfbaba8fd4f1da303e10952d0c923750`

The CLI now writes deterministic gzip bytes when the requested output ends in
`.gz`; its own campaign reader accepts the result. No solver, battery reference,
hidden bank or independent holdout was used.
