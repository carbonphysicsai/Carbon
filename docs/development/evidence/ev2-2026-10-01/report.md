# EV2: does Carbon's scoring prefer models that make better engineering decisions?

Public synthetic DEVELOPMENT evidence. It changes no testnet rule and claims no qualification. "Best" means best in the tested candidate set, not a global optimum. No optimal weight ratio is claimed.

- Contract: `sha256:1877091055d1dac2515da5aa05bf4f0ad56cf3376045d73086dcf1f0848ce743`
- Scoring set: `docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/records.jsonl` (1588 cases, sha256 `88df01aacec5222f…`)
- Rule chosen on development scenarios: **dar-p0-r100-a0**
- Kendall τ (rule score vs. decision quality) on the verification scenarios: chosen rule 0.202, control 0.298

## Reference outcomes per scenario

| Scenario | Split | Best in tested set | Baseline | Feasible / infeasible / unresolved / unavailable |
|---|---|---|---|---|
| D-T17-S0.08 | development | c1=2,c2=0.8 | INFEASIBLE | 9 / 20 / 6 / 0 |
| D-T17-S0.28 | development | c1=1,c2=0.6 | FEASIBLE | 3 / 28 / 4 / 0 |
| D-T27-S0.08 | development | c1=1.5,c2=1 | INFEASIBLE | 11 / 24 / 0 / 0 |
| D-T27-S0.28 | development | c1=1.5,c2=1 | FEASIBLE | 13 / 18 / 4 / 0 |
| D-T37-S0.08 | development | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| D-T37-S0.28 | development | c1=0.75,c2=0.8 | FEASIBLE | 4 / 30 / 1 / 0 |
| D-T7-S0.08 | development | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| D-T7-S0.28 | development | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| V-T11-S0.18 | verification | none | UNRESOLVED | 0 / 32 / 3 / 0 |
| V-T11-S0.45 | verification | c1=0.75,c2=0.4 | UNRESOLVED | 2 / 32 / 1 / 0 |
| V-T21-S0.18 | verification | c1=1.75,c2=1 | FEASIBLE | 13 / 20 / 2 / 0 |
| V-T21-S0.45 | verification | c1=1,c2=0.8 | FEASIBLE | 7 / 26 / 2 / 0 |
| V-T31-S0.18 | verification | c1=1.25,c2=1 | INFEASIBLE | 8 / 27 / 0 / 0 |
| V-T31-S0.45 | verification | c1=1.25,c2=1 | FEASIBLE | 15 / 17 / 3 / 0 |
| V-T40-S0.18 | verification | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| V-T40-S0.45 | verification | c1=1.5,c2=0.6 | FEASIBLE | 5 / 29 / 1 / 0 |

## Scoring rules against decision quality

τ > 0 means the rule prefers the models whose selections lose less. The panel is small, so treat these values as indicative.

| Rule | Measurable | τ development | τ verification | τ dev incl. controls | Top member (LOBO stable) |
|---|---|---|---|---|---|
| control-exam-v1 | yes | -0.030 | 0.298 | -0.071 | mlp_ens3-s0 (8/8) |
| dar-p0-r100-a0 | yes | 0.188 | 0.202 | 0.466 | mlp_localized-s1 (8/8) |
| dar-p0-r30-a70 | yes | 0.050 | 0.221 | 0.159 | mlp_localized-s1 (5/8) |
| dar-p0-r50-a50 | yes | 0.129 | 0.221 | 0.225 | mlp_localized-s1 (8/8) |
| p0-r20-a80 | yes | -0.050 | 0.317 | -0.071 | mlp_ens3-s0 (8/8) |
| p0-r30-a70 | yes | -0.050 | 0.317 | -0.005 | mlp_ens3-s0 (8/8) |
| p0-r40-a60 | yes | -0.050 | 0.298 | 0.016 | mlp_ens3-s0 (8/8) |
| p45-r30-a25 | no: NOT_MEASURABLE:missing_component | — | — | — | — |

## Does each rule rank the boundary-optimist control below every eligible model?

The control is accurate almost everywhere and optimistic exactly near the plating and temperature limits, so it tends to select unsafe protocols.

| Rule | Below every eligible member | Members scored at or below it |
|---|---|---|
| control-exam-v1 | no | 14 of 14 |
| dar-p0-r100-a0 | yes | 0 of 14 |
| dar-p0-r30-a70 | yes | 0 of 14 |
| dar-p0-r50-a50 | yes | 0 of 14 |
| p0-r20-a80 | no | 13 of 14 |
| p0-r30-a70 | no | 7 of 14 |
| p0-r40-a60 | no | 5 of 14 |
| p45-r30-a25 | not measurable | — |

## Members

Decision loss is measured in multiples of the minimum useful improvement; a false acceptance costs 10 and a missed opportunity costs 1 (provisional DEVELOPMENT costs).

| Member | Kind | Eligible | Mean loss (dev) | Mean loss (verify) | Control score | p0-r30-a70 |
|---|---|---|---|---|---|---|
| control-boundary_optimist | SYNTHETIC_CONTROL | True | 10.000 | 7.500 | -0.0462 | 0.9451 |
| control-conservative | SYNTHETIC_CONTROL | True | 1.520 | 2.521 | -0.2417 | 0.8053 |
| control-localized_sign_error | SYNTHETIC_CONTROL | True | 4.000 | 3.342 | -0.0077 | 0.9832 |
| control-oracle | SYNTHETIC_CONTROL | True | 0.000 | 0.000 | -0.0000 | 1.0000 |
| control-rank_preserving_delay | SYNTHETIC_CONTROL | True | 0.000 | 0.000 | -0.0329 | 0.9676 |
| deeponet-s0 | RECONSTRUCTED | True | 0.000 | 1.685 | -0.0618 | 0.9432 |
| deeponet-s1 | RECONSTRUCTED | True | 1.694 | 0.010 | -0.0640 | 0.9414 |
| knn-s0 | RECONSTRUCTED | True | 4.000 | 0.842 | -0.1708 | 0.8562 |
| knn15-s0 | RECONSTRUCTED | True | 2.857 | 1.908 | -0.1907 | 0.8433 |
| mlp-s0 | RECONSTRUCTED | True | 2.000 | 0.050 | -0.0551 | 0.9490 |
| mlp-s1 | RECONSTRUCTED | True | 1.667 | 0.000 | -0.0564 | 0.9477 |
| mlp-s2 | RECONSTRUCTED | True | 2.000 | 0.027 | -0.0575 | 0.9466 |
| mlp_ens3-s0 | RECONSTRUCTED | True | 2.000 | 0.000 | -0.0514 | 0.9522 |
| mlp_half-s0 | RECONSTRUCTED | True | 1.775 | 0.249 | -0.0874 | 0.9204 |
| mlp_half-s1 | RECONSTRUCTED | True | 3.333 | 0.026 | -0.0834 | 0.9262 |
| mlp_localized-s0 | RECONSTRUCTED | True | 1.667 | 0.166 | -0.0572 | 0.9461 |
| mlp_localized-s1 | RECONSTRUCTED | True | 1.667 | 1.717 | -0.0584 | 0.9458 |
| mlp_plus-s0 | RECONSTRUCTED | True | 1.452 | 0.125 | -0.0890 | 0.9188 |
| mlp_raw-s0 | RECONSTRUCTED | False | 0.000 | 0.026 | — | 0.0000 |
| mlp_wide-s0 | RECONSTRUCTED | True | 4.000 | 0.071 | -0.0592 | 0.9454 |

## Decisions

| Member | Scenario | Outcome | Selected | Gap to best (s) | vs baseline (s) | False acc. | False rej. | τ ranking |
|---|---|---|---|---|---|---|---|---|
| control-boundary_optimist | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 2 | 0 | 1.000 |
| control-boundary_optimist | D-T17-S0.28 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 4 | 0 | 1.000 |
| control-boundary_optimist | D-T27-S0.08 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 3 | 0 | 1.000 |
| control-boundary_optimist | D-T27-S0.28 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 1.000 |
| control-boundary_optimist | D-T37-S0.08 | SELECTED_INFEASIBLE | c1=1,c2=1 | — | — | 3 | 0 | — |
| control-boundary_optimist | D-T37-S0.28 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 8 | 0 | 1.000 |
| control-boundary_optimist | D-T7-S0.08 | SELECTED_INFEASIBLE | c1=1.5,c2=0.8 | — | — | 8 | 0 | — |
| control-boundary_optimist | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=1,c2=0.8 | — | — | 4 | 0 | — |
| control-boundary_optimist | V-T11-S0.18 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 6 | 0 | — |
| control-boundary_optimist | V-T11-S0.45 | SELECTED_INFEASIBLE | c1=1,c2=0.8 | — | — | 5 | 0 | 1.000 |
| control-boundary_optimist | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 3 | 0 | 1.000 |
| control-boundary_optimist | V-T21-S0.45 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 7 | 0 | 1.000 |
| control-boundary_optimist | V-T31-S0.18 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 6 | 0 | 1.000 |
| control-boundary_optimist | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 3 | 0 | 1.000 |
| control-boundary_optimist | V-T40-S0.18 | SELECTED_INFEASIBLE | c1=1,c2=0.8 | — | — | 4 | 0 | — |
| control-boundary_optimist | V-T40-S0.45 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 15 | 0 | 1.000 |
| control-conservative | D-T17-S0.08 | MISSED_OPPORTUNITY | — | — | — | 0 | 9 | 1.000 |
| control-conservative | D-T17-S0.28 | MISSED_OPPORTUNITY | — | — | — | 0 | 3 | 1.000 |
| control-conservative | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 171.3 | — | 0 | 5 | 1.000 |
| control-conservative | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 398.8 | 1107.6 | 0 | 4 | 1.000 |
| control-conservative | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | D-T37-S0.28 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 649.5 | 0.0 | 0 | 3 | 1.000 |
| control-conservative | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-conservative | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| control-conservative | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 1111.4 | 498.1 | 0 | 9 | 1.000 |
| control-conservative | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 641.0 | 5.5 | 0 | 3 | 1.000 |
| control-conservative | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1,c2=1 | 245.6 | — | 0 | 3 | 1.000 |
| control-conservative | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 0 | 1 | 1.000 |
| control-conservative | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | V-T40-S0.45 | MISSED_OPPORTUNITY | — | — | — | 0 | 5 | 1.000 |
| control-localized_sign_error | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 1 | 4 | 1.000 |
| control-localized_sign_error | D-T17-S0.28 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| control-localized_sign_error | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-localized_sign_error | D-T27-S0.28 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 1.000 |
| control-localized_sign_error | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-localized_sign_error | D-T7-S0.08 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 2 | 0 | — |
| control-localized_sign_error | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | V-T11-S0.18 | SELECTED_INFEASIBLE | c1=1.25,c2=0.8 | — | — | 1 | 0 | — |
| control-localized_sign_error | V-T11-S0.45 | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 1 | 0 | 1.000 |
| control-localized_sign_error | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 407.3 | 1202.1 | 0 | 5 | 1.000 |
| control-localized_sign_error | V-T21-S0.45 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 3 | 3 | 1.000 |
| control-localized_sign_error | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-localized_sign_error | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 0 | 0 | 1.000 |
| control-localized_sign_error | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 0 | 0 | 1.000 |
| control-oracle | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 0 | 1.000 |
| control-oracle | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-oracle | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 1.000 |
| control-oracle | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-oracle | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-oracle | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 1.000 |
| control-oracle | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 0 | 0 | 1.000 |
| control-oracle | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 0 | 0 | 1.000 |
| control-oracle | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| control-rank_preserving_delay | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 0 | 0 | 1.000 |
| deeponet-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.889 |
| deeponet-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| deeponet-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.891 |
| deeponet-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.974 |
| deeponet-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 0.667 |
| deeponet-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 13.0 | — | 0 | 0 | -1.000 |
| deeponet-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.897 |
| deeponet-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 2 | 0 | 1.000 |
| deeponet-s0 | V-T31-S0.18 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 3 | 0 | 0.929 |
| deeponet-s0 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 2 | 0 | 0.905 |
| deeponet-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | V-T40-S0.45 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 4 | 0 | 0.800 |
| deeponet-s1 | D-T17-S0.08 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 19.5 | — | 0 | 0 | 0.944 |
| deeponet-s1 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 1 | 1.000 |
| deeponet-s1 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.891 |
| deeponet-s1 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 1.000 |
| deeponet-s1 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s1 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 1.000 |
| deeponet-s1 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s1 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| deeponet-s1 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet-s1 | V-T11-S0.45 | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | 1.000 |
| deeponet-s1 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.923 |
| deeponet-s1 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 2 | 0 | 0.810 |
| deeponet-s1 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 2 | 0 | 0.929 |
| deeponet-s1 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.0 | 1253.6 | 2 | 0 | 0.962 |
| deeponet-s1 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s1 | V-T40-S0.45 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 4 | 0 | 0.800 |
| knn-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 2 | 5 | 0.867 |
| knn-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 1 | 1.000 |
| knn-s0 | D-T27-S0.08 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 4 | 0.810 |
| knn-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 2 | 0.891 |
| knn-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 3 | 0 | 0.000 |
| knn-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| knn-s0 | V-T11-S0.18 | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| knn-s0 | V-T11-S0.45 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| knn-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 36.2 | 1573.3 | 2 | 2 | 0.769 |
| knn-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 0 | 1 | 1.000 |
| knn-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.714 |
| knn-s0 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1259.6 | 1 | 0 | 0.695 |
| knn-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=0.5,c2=0.6 | 550.8 | -496.7 | 0 | 4 | 0.800 |
| knn15-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 7 | 0.667 |
| knn15-s0 | D-T17-S0.28 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 182.2 | 0 | 1 | 1.000 |
| knn15-s0 | D-T27-S0.08 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 5 | 7 | 0.333 |
| knn15-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 1 | 1 | 0.848 |
| knn15-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | D-T37-S0.28 | SELECTED_INFEASIBLE | c1=1,c2=1 | — | — | 4 | 1 | -0.333 |
| knn15-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn15-s0 | V-T11-S0.45 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| knn15-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 1 | 3 | 0.927 |
| knn15-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 2 | 1 | 1.000 |
| knn15-s0 | V-T31-S0.18 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 2 | 3 | 0.600 |
| knn15-s0 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 2 | 0 | 0.829 |
| knn15-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 54.1 | 0.0 | 0 | 3 | 1.000 |
| mlp-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.889 |
| mlp-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.891 |
| mlp-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.949 |
| mlp-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 0.667 |
| mlp-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 36.2 | 1573.3 | 0 | 0 | 0.949 |
| mlp-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 2 | 0 | 1.000 |
| mlp-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp-s0 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 3 | 0 | 0.943 |
| mlp-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 1 | 0 | 0.800 |
| mlp-s1 | D-T17-S0.08 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 0.0 | — | 0 | 0 | 0.833 |
| mlp-s1 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp-s1 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.964 |
| mlp-s1 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.949 |
| mlp-s1 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 0.667 |
| mlp-s1 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp-s1 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp-s1 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s1 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.949 |
| mlp-s1 | V-T21-S0.45 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 3 | 0 | 1.000 |
| mlp-s1 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp-s1 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 4 | 0 | 0.924 |
| mlp-s1 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 0 | 0 | 0.800 |
| mlp-s2 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.889 |
| mlp-s2 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp-s2 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.891 |
| mlp-s2 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 1.000 |
| mlp-s2 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 0.667 |
| mlp-s2 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp-s2 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp-s2 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 13.0 | — | 0 | 0 | -1.000 |
| mlp-s2 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.949 |
| mlp-s2 | V-T21-S0.45 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 3 | 0 | 0.810 |
| mlp-s2 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp-s2 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 4 | 0 | 0.962 |
| mlp-s2 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | V-T40-S0.45 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.833 |
| mlp_ens3-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.927 |
| mlp_ens3-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 0.667 |
| mlp_ens3-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_ens3-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_ens3-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.974 |
| mlp_ens3-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 3 | 0 | 1.000 |
| mlp_ens3-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp_ens3-s0 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 3 | 0 | 0.886 |
| mlp_ens3-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 2 | 0 | 1.000 |
| mlp_half-s0 | D-T17-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 77.7 | — | 0 | 2 | 0.778 |
| mlp_half-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 1 | 1.000 |
| mlp_half-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 1 | 0.855 |
| mlp_half-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 1.000 |
| mlp_half-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 1.000 |
| mlp_half-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_half-s0 | V-T11-S0.18 | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp_half-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_half-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 36.2 | 1573.3 | 0 | 1 | 0.923 |
| mlp_half-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 3 | 0 | 0.810 |
| mlp_half-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 2 | 0 | 0.929 |
| mlp_half-s0 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.0 | 1253.6 | 4 | 0 | 0.924 |
| mlp_half-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=2,c2=0.6 | 166.7 | -112.6 | 2 | 0 | 0.000 |
| mlp_half-s1 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.889 |
| mlp_half-s1 | D-T17-S0.28 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 182.2 | 0 | 0 | 1.000 |
| mlp_half-s1 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.964 |
| mlp_half-s1 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.974 |
| mlp_half-s1 | D-T37-S0.08 | SELECTED_INFEASIBLE | c1=0.75,c2=1 | — | — | 1 | 0 | — |
| mlp_half-s1 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 0.667 |
| mlp_half-s1 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_half-s1 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_half-s1 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 13.0 | — | 0 | 0 | -1.000 |
| mlp_half-s1 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.872 |
| mlp_half-s1 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 2 | 0 | 1.000 |
| mlp_half-s1 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp_half-s1 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.0 | 1253.6 | 4 | 0 | 0.867 |
| mlp_half-s1 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | V-T40-S0.45 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 3 | 1 | 0.800 |
| mlp_localized-s0 | D-T17-S0.08 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 0.0 | — | 0 | 0 | 0.889 |
| mlp_localized-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.855 |
| mlp_localized-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.974 |
| mlp_localized-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 0.667 |
| mlp_localized-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_localized-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | V-T11-S0.45 | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.949 |
| mlp_localized-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 3 | 0 | 1.000 |
| mlp_localized-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp_localized-s0 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 3 | 0 | 0.905 |
| mlp_localized-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.75,c2=0.6 | 99.7 | -45.7 | 2 | 1 | 0.600 |
| mlp_localized-s1 | D-T17-S0.08 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.891 |
| mlp_localized-s1 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.974 |
| mlp_localized-s1 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 1 | 0 | 1.000 |
| mlp_localized-s1 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_localized-s1 | V-T11-S0.18 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | — |
| mlp_localized-s1 | V-T11-S0.45 | SELECTED_INFEASIBLE | c1=0.5,c2=0.6 | — | — | 1 | 0 | 1.000 |
| mlp_localized-s1 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 36.2 | 1573.3 | 0 | 1 | 0.949 |
| mlp_localized-s1 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 3 | 0 | 1.000 |
| mlp_localized-s1 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp_localized-s1 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 4 | 0 | 0.943 |
| mlp_localized-s1 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 0 | 0 | 0.800 |
| mlp_plus-s0 | D-T17-S0.08 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 19.5 | — | 0 | 0 | 0.889 |
| mlp_plus-s0 | D-T17-S0.28 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 182.2 | 0 | 0 | 1.000 |
| mlp_plus-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.855 |
| mlp_plus-s0 | D-T27-S0.28 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.974 |
| mlp_plus-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | D-T37-S0.28 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | 649.5 | 1 | 1 | 1.000 |
| mlp_plus-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.5,c2=0.6 | — | — | 2 | 0 | — |
| mlp_plus-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_plus-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 36.2 | 1573.3 | 0 | 1 | 0.923 |
| mlp_plus-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 1 | 0 | 1.000 |
| mlp_plus-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 2 | 0 | 0.929 |
| mlp_plus-s0 | V-T31-S0.45 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 3 | 0 | 0.810 |
| mlp_plus-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 54.1 | 0.0 | 3 | 0 | 0.800 |
| mlp_raw-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 0 | 0.889 |
| mlp_raw-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 1 | 1.000 |
| mlp_raw-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.927 |
| mlp_raw-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.974 |
| mlp_raw-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_raw-s0 | D-T7-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | D-T7-S0.28 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 13.0 | — | 0 | 0 | -1.000 |
| mlp_raw-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 1.000 |
| mlp_raw-s0 | V-T21-S0.45 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 1 | 0 | 1.000 |
| mlp_raw-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp_raw-s0 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.0 | 1253.6 | 0 | 0 | 0.848 |
| mlp_raw-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 54.1 | 0 | 0 | 0.800 |
| mlp_wide-s0 | D-T17-S0.08 | SELECTED_UNRESOLVED | c1=1.75,c2=1 | — | — | 0 | 2 | 0.944 |
| mlp_wide-s0 | D-T17-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_wide-s0 | D-T27-S0.08 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | — | 0 | 0 | 0.927 |
| mlp_wide-s0 | D-T27-S0.28 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1506.4 | 0 | 0 | 0.974 |
| mlp_wide-s0 | D-T37-S0.08 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_wide-s0 | D-T37-S0.28 | SELECTED_UNRESOLVED | c1=1,c2=0.8 | — | — | 0 | 0 | 0.667 |
| mlp_wide-s0 | D-T7-S0.08 | SELECTED_INFEASIBLE | c1=0.5,c2=0.2 | — | — | 1 | 0 | — |
| mlp_wide-s0 | D-T7-S0.28 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_wide-s0 | V-T11-S0.18 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_wide-s0 | V-T11-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_wide-s0 | V-T21-S0.18 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1609.4 | 0 | 0 | 0.949 |
| mlp_wide-s0 | V-T21-S0.45 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 646.5 | 2 | 0 | 0.905 |
| mlp_wide-s0 | V-T31-S0.18 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.929 |
| mlp_wide-s0 | V-T31-S0.45 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.0 | 1253.6 | 3 | 0 | 0.848 |
| mlp_wide-s0 | V-T40-S0.18 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_wide-s0 | V-T40-S0.45 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 54.1 | 0.0 | 2 | 0 | 0.800 |

## Limitations

- Charging speed is time to constant-voltage onset (the 4.19 V crossing), not time to a target state of charge. The reference keeps no SOC or current trajectory.
- The physics leg is not measurable for battery, so profiles that weight it are reported, not computed.
- The scoring set omits hidden duplicates, so the paired-repeat gate is not exercised.
- The model panel is small, and reconstruction seeds are repetitions of a recipe, not independent models.
