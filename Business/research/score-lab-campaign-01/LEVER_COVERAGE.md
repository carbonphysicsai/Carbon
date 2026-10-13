# OPT-15c synthetic lever coverage against experiment plan §2

This is an implementation ledger, not a claim that the synthetic campaign is
complete. `IMPLEMENTED` means the toy harness changes that quantity and a
fixture exercises it. `PARTIAL` means the setting is narrower than the plan.

| Plan group | Current toy coverage | Status / remaining work |
| --- | --- | --- |
| A: design dimension, space, shape and optimum | One-dimensional small/dense offered grids; one or two parabolic optima; loose/tight coupled margins | PARTIAL: dimensions 2–8, 3/10 optima, smoothness and optimum-location controls missing |
| A: constraints and objective | Two coupled hard margins, single objective, variable verification cost | PARTIAL: 0–5 margins, robust/chance/multi-objective and reference-noise semantics missing |
| A: decision forms | Best predicted feasible shortlist with k and abstention/unsafe loss; legacy single-pick value alternative; robust worst-case buyer-value view | PARTIAL: threshold, feasibility-only and sensitivity decisions missing |
| B: task neighbourhood | Objective, constraint, operating and boundary changes; size, extrapolation distance and value/score weights | IMPLEMENTED as analytic toy assumptions |
| C: model errors and traits | Error scale, transfer, score-path overfit, law events, drift, robustness, extrapolation; optional toy heteroscedasticity (uniform/boundary/optimum), cross-design correlation, rare tails and sigma scale | PARTIAL: these new knobs are fixture-tested but not yet in a broad result; gradient fidelity and calibrated uncertainty data are missing |
| D: population and gamers | Several toy model types, cheap map, abstain, bad and path probes; disclosed-score feedback gamer connected to analytic toy candidate rules | PARTIAL: adaptive competition within every sweep profile and copy/fallback strategies missing |
| E: measurement | Disjoint score/value sets, 3–20 questions, LHS shards, bootstrap, mean/tail descriptive atlas | PARTIAL: 10–4,000 questions, 3–30 blocks, P/Q/w sampling, reference-failure policy, median/quantile aggregation and true Sobol design missing |
| F: score components | Ten Validator candidate proxies, optional cheap-relative/CRPS/gradient-sign/CVaR wrappers, physics GATE/FLOOR/BLEND | PARTIAL: full combinatorial component sweep and exact registered Tier-2 replay missing |
| G: championship | None in Score Lab campaign runner | MISSING: paired crown/tie/margin sweep against true toy value |

Eight-profile and 16-profile outputs exercise subsets of this ledger only.
`FEEDBACK_TOY_READOUT.md` records one 10-rule score-only feedback diagnostic;
its disclosure settings are assumptions rather than Launchpad measurements.
`ERROR_STRUCTURE_READOUT_8.md` records a one-rule, eight-profile plumbing
smoke for the new error knobs, with no sensitivity or rule-selection claim.
`GOODHART_ROBUST_TOY_READOUT.md` records the separate worst-case value view;
its value oracle is approximate and it does not pick a winner.
The 142-member realism calibration, D3-approved EV4 reference v2, independent
final holdout, tier-2 replay and one-page owner verdict are still absent.
The held Test Engineer holdout is never read or queried to fill these gaps.
