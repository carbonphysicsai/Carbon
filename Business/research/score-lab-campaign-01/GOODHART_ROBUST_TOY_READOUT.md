# Robust-value Goodhart search: analytic toy only

The existing ten read-only candidate proxies were rerun with
`goodhart-robust-search-example.json`; all search effort, population and
physics settings stayed at the earlier Goodhart example values. This value
scope takes the worst member loss across each target task, its neighbours and
its extrapolated task. It does not claim an exact min-max oracle; the separate
value search remains an approximate random-plus-coordinate hill climb.

Seven proxies were scored. Sampled score-maximizer minus approximate
value-oracle loss gaps were +0.11648 (N1), +0.01667 (N4), zero for N2, N3
and V2r2 k1, and -0.01667 for V2r2 k3 and k5. Negative gaps mean the
approximate oracle missed the score-search point, not that the rule beats an
exact oracle. The in-force, V9 and V10 toy proxies remained unscored.
No rule selection follows from one seed and this narrow trait grammar.

The aggregate artifact is `GOODHART_ROBUST_TOY_ALL10.json.gz`
(`sha256:6a55a265559b0818bd08d18db5c1d4f0f4d74cabecba911235cecded35ed7a8d`).
No public battery reference, independent holdout or protected bank was used.
