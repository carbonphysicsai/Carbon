# OPT-15c named toy stress readout

The five explicitly limited analytic scenarios in
`scripts/dev/score_lab/campaign-stress-example.json` ran across all ten
candidate proxies (70 physics-switch rows per scenario; 350 total). Local WSL
cost was 28.31 user plus 0.51 system CPU seconds and 30.46 wall seconds. No
solver, pod, EV4 label, sealed data, or final held-out generator was used.

The OFF-switch neighbourhood-blend τ for N1 was 0.200 on the small-grid toy,
0.467 on the tight-boundary toy, 0.467 on the larger-shift toy, 0.200 with the
heavier fixed score-path probe, and 0.600 on the three-question toy. Those are
descriptive values for five hand-built assumptions, not a robust ranking or a
real Challenge prediction. Some other proxy/scenario combinations had no
estimable τ; the raw output retains those missing outcomes.

The machine-readable result is `NAMED_STRESS_ALL10.json.gz` (SHA-256
`85d78b44d15cec433d9fd109d1da8e2703772d6eb129c302dd0fcafd62450852`).
The scenario schema records each analogy's limitation. The present toy cannot
stand in for §2's variable dimension, 0–5 independent constraints, robust
objective, chance constraint, or feedback-adaptive miner population. No rule
is selected or threshold adopted.
