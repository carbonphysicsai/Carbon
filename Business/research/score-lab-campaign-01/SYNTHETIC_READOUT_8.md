# OPT-15c eight-profile synthetic readout (development diagnostic)

The digest-bound LHS plan `96ee9d4d959e1db9bb5a77824b2dca9b357cac8f82ce11ed173cc87398971c22`
evaluated eight analytic toy configurations under the ten candidate proxies at
candidate-file digest `157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
The run produced 560 candidate × physics-switch rows, all marked measured by
the toy evaluator. It took 104.33 user plus 2.98 system CPU seconds and 107.56
wall seconds on local WSL. No solver, pod, held-out generator, EV4 label, or
sealed data was used.

The OFF-switch neighbourhood-blend τ was variable across the eight profiles.
N1's median was 0.533 with a worst profile of −0.200; N2's median was 0.507
with a worst profile of 0.086; N3's median was 0.621 with a worst profile of
0.086. V2r2@k5,kappa0.25 had median −0.133 and worst −0.467. The in-force
proxy had no estimable τ in these profiles; this summary does not diagnose
why. These are observations, not winner selection.

The separate score-only Goodhart search covered all ten proxies on one toy
configuration and seed. N1's score-maximising member had +0.0739 toy buyer
loss versus the approximate independent value search; N4 had +0.0107. Three
physics-gated proxies returned `all_score_proposals_unscored`, so they have no
gap estimate. Negative gaps for two other proxies show the approximate oracle
can miss a better point; they do not prove those scores improve value. This is
a failure-mode demonstration, not a Challenge effect-size estimate. The raw
result is `GOODHART_TOY_ALL10.json` (SHA-256
`2ce7628fb15ffeeef36ab115888a94097cb3165c8d86a59ac7aafbe3a418a646`).

The saved artifacts are `SYNTHETIC_PLAN_8.json.gz` (SHA-256
`2b16364d9720df436ab24961d8021baba639a4ec0c141fc7a2b91f12143c1d29`),
`SYNTHETIC_SWEEP_8.json.gz` (`24c822b71556cfbd2f5dd217539285a334fd1d0533fc81f9e589ed0fe12cdc34`;
decompressed JSON SHA-256 `f306e63df7c3f70c9a378b48ef509958968aa1a3007a2cda58dd5e53a4b6ca52`),
and `SYNTHETIC_ATLAS_8.json.gz` (`384b525b85540ef7431b1c4664f034f072f4b9fdd7abdae7e83855eea39f11b3`).
The atlas reports target, shifted, extrapolated, and neighbourhood-blend
descriptives plus exploratory OFF-switch axis associations. Sobol indices and
rule selection are unset: this eight-profile
LHS sample is neither a Saltelli design nor the preregistered final holdout.
The full §2 A–G grammar, realism calibration, EV4 v2 labels, tier-2 replay,
and final held-out confirmation remain outstanding.
