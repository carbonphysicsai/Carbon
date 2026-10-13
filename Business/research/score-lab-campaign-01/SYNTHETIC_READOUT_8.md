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

The separate score-only Goodhart smoke found a +0.0739 toy buyer-loss gap for
N1 against an approximate independent value search. This is one configuration
and one search seed, so it is a failure-mode demonstration, not an effect-size
estimate for a Challenge.

The saved artifacts are `SYNTHETIC_PLAN_8.json` (SHA-256
`454eb4b3efe4c041ca895790c8033977b3dbcd6629937f2e7595f41d59702fd0`),
`SYNTHETIC_SWEEP_8.json` (`f306e63df7c3f70c9a378b48ef509958968aa1a3007a2cda58dd5e53a4b6ca52`),
and `SYNTHETIC_ATLAS_8.json` (`7bd508e3e20544a0283d1a626041d54f07c7d390d4ca4df92fbd6bf6e7f4055c`).
The atlas reports target, shifted, extrapolated, and neighbourhood-blend
descriptives. Sobol indices and rule selection are unset: this eight-profile
LHS sample is neither a Saltelli design nor the preregistered final holdout.
The full §2 A–G grammar, realism calibration, EV4 v2 labels, tier-2 replay,
and final held-out confirmation remain outstanding.
