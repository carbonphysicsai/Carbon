# OPT-20: robustness as a score lever, analytic toy only

**Status: exploratory, INSUFFICIENT_EVIDENCE for rule or threshold selection.**
This comparison used one synthetic task shape, one proposal seed and the ten
trusted local Validator candidate proxies. Each proxy/arm scored the same 30
frozen model-trait proposals. Each arm got 30 candidate score calls and 120
buyer-value evaluations (30 proposals x four value scopes). Wrapper CPU time
was not matched. The value oracle is best in that finite slate, not a global
optimum. This run reads no public/hidden Challenge labels or sealed holdout.

The numbers below count candidates whose score-selected member had lower,
exactly equal, or higher **toy buyer loss** than that candidate's baseline
score-selected member on the same slate. `U` means no eligible score pick.
The `NO_OBSERVED_DIFFERENCE_ON_SLATE` result is an exact equality here, not a
powered equivalence finding. All lever values in the example files are
explicit `ASSUMPTION` settings, never recommended thresholds.

| Arm | Eligible proposals per candidate | Target better/same/worse/U | Shifted better/same/worse/U | Extrapolated better/same/worse/U | Blended-near better/same/worse/U |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weighted robustness term, 0.2 | 1–30 | 0/7/3/0 | 5/3/2/0 | 5/3/2/0 | 2/3/5/0 |
| Weighted robustness term, 1.0 | 1–30 | 0/6/4/0 | 6/2/2/0 | 6/2/2/0 | 2/2/6/0 |
| Robustness gate, 0.02 | 0–10 | 0/7/2/1 | 5/0/4/1 | 6/0/3/1 | 3/0/6/1 |
| Robustness gate, 0.08 | 1–19 | 0/10/0/0 | 3/7/0/0 | 3/7/0/0 | 3/7/0/0 |
| Robustness gate, 0.16 | 1–29 | 0/10/0/0 | 0/10/0/0 | 0/10/0/0 | 0/10/0/0 |
| Honest uncertainty/decline term | 1–30 | 0/10/0/0 | 6/4/0/0 | 3/4/3/0 | 6/4/0/0 |

**A, weighted term.** The predicted overconservative failure was *not*
isolated as sigma inflation in this slate. Some term winners instead had low
reported robustness but worse transfer or score-path-only behavior. The
stronger term worsened blended-near buyer loss for six proxies while improving
two. This is a toy Goodhart warning, not proof of a real failure rate.

**B, gate.** Tightening the assumed limit reduced admission. At 0.02 one
candidate had zero eligible proposals and six of the nine scored proxies had
worse blended-near loss. The 0.08 point improved three and tied seven here;
0.16 changed no selected value. The curve shows the admission/value trade,
but one shape and one seed cannot justify a gate value. A gate can itself be
threshold-hugged; it is not inherently immune to gaming.

**C, honest uncertainty.** The score-side Brier-like term rewards high
uncertainty when a toy prediction is materially wrong and penalizes high
uncertainty on accurate cells. The buyer-value path separately declines
high-uncertainty actions, so blanket caution loses available gain. Six proxies
improved blended-near value and four tied, yet three worsened extrapolated
value. Nearby scoring cells are an assumed outside-envelope proxy, not a
measured envelope. It is a candidate mechanism worth further tests, not a
selected rule.

The exact candidate, config, search and lever digests plus each arm's winner,
gate admission, target/near losses, finite-slate gap and no-difference labels
are in `TOY_ROBUSTNESS_ALL10.json.gz`. The candidate source stays in the local
untracked queue (sha256
`157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`).
The compressed readout's sha256 is
`3c4d95e2bdbe70c65fa6c303b72ac1518e84e18d191ee592fdc91440a21ee1c3`.
Real robustness calibration, more generator families/seeds,
independent final holdout and Carbon Validator review remain outstanding.
