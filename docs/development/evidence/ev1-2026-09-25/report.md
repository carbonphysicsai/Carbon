# EV1: does Carbon's scoring prefer models that make better engineering decisions?

Public synthetic DEVELOPMENT evidence. It changes no testnet rule and claims no qualification. "Best" means best in the tested candidate set, not a global optimum. No optimal weight ratio is claimed.

- Contract: `sha256:292c0473f295ac5898845b2a75b05e9cf6d843722fecd3812ad79abe7ea8d0f9`
- Scoring set: `docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/records.jsonl` (1588 cases, sha256 `88df01aacec5222f…`)
- Rule chosen on development scenarios: **control-exam-v1**
- Kendall τ (rule score vs. decision quality) on the verification scenarios: chosen rule 0.165, control 0.165

## Reference outcomes per scenario

| Scenario | Split | Best in tested set | Baseline | Feasible / infeasible / unresolved / unavailable |
|---|---|---|---|---|
| D1-temperate | development | c1=1.25,c2=0.8 | INFEASIBLE | 3 / 12 / 1 / 0 |
| D2-warm | development | c1=0.75,c2=1 | INFEASIBLE | 1 / 15 / 0 / 0 |
| D3-cool | development | none | UNRESOLVED | 0 / 15 / 1 / 0 |
| V1-mild | verification | none | INFEASIBLE | 0 / 15 / 1 / 0 |
| V2-hot | verification | none | INFEASIBLE | 0 / 16 / 0 / 0 |
| V3-cold | verification | none | INFEASIBLE | 0 / 16 / 0 / 0 |

## Scoring rules against decision quality

τ > 0 means the rule prefers the models whose selections lose less. The panel is small, so treat these values as indicative.

| Rule | Measurable | τ development | τ verification | τ dev incl. controls | Top member (LOBO stable) |
|---|---|---|---|---|---|
| control-exam-v1 | yes | 0.341 | 0.165 | 0.000 | mlp_ens3-s0 (8/8) |
| p45-r30-a25 | no: NOT_MEASURABLE:missing_component | — | — | — | — |
| p0-r30-a70 | yes | 0.341 | 0.110 | 0.149 | mlp_ens3-s0 (8/8) |
| p0-r20-a80 | yes | 0.341 | 0.110 | 0.025 | mlp_ens3-s0 (8/8) |
| p0-r40-a60 | yes | 0.341 | 0.110 | 0.149 | mlp_ens3-s0 (8/8) |

## Members

Decision loss is measured in multiples of the minimum useful improvement; a false acceptance costs 10 and a missed opportunity costs 1 (provisional DEVELOPMENT costs).

| Member | Kind | Eligible | Mean loss (dev) | Mean loss (verify) | Control score | p0-r30-a70 |
|---|---|---|---|---|---|---|
| control-boundary_optimist | SYNTHETIC_CONTROL | True | 10.000 | 10.000 | -0.0462 | 0.9451 |
| control-conservative | SYNTHETIC_CONTROL | True | 1.000 | 0.000 | -0.2417 | 0.8053 |
| control-localized_sign_error | SYNTHETIC_CONTROL | True | 2.835 | 0.000 | -0.0077 | 0.9832 |
| control-oracle | SYNTHETIC_CONTROL | True | 0.000 | 0.000 | -0.0000 | 1.0000 |
| control-rank_preserving_delay | SYNTHETIC_CONTROL | True | 0.000 | 0.000 | -0.0329 | 0.9676 |
| knn-s0 | RECONSTRUCTED | True | 0.500 | 0.000 | -0.1708 | 0.8562 |
| mlp-s0 | RECONSTRUCTED | True | 0.000 | 0.000 | -0.0551 | 0.9490 |
| mlp-s1 | RECONSTRUCTED | True | 0.000 | 0.000 | -0.0564 | 0.9477 |
| mlp-s2 | RECONSTRUCTED | True | 0.000 | 3.333 | -0.0575 | 0.9466 |
| mlp_ens3-s0 | RECONSTRUCTED | True | 0.000 | 0.000 | -0.0514 | 0.9522 |
| mlp_half-s0 | RECONSTRUCTED | True | 0.000 | 0.000 | -0.0874 | 0.9204 |
| mlp_half-s1 | RECONSTRUCTED | True | 0.000 | 3.333 | -0.0834 | 0.9262 |
| mlp_localized-s0 | RECONSTRUCTED | True | 0.000 | 0.000 | -0.0572 | 0.9461 |
| mlp_localized-s1 | RECONSTRUCTED | True | 0.000 | 0.000 | -0.0584 | 0.9458 |
| mlp_plus-s0 | RECONSTRUCTED | True | 0.000 | 3.333 | -0.0890 | 0.9188 |
| mlp_raw-s0 | RECONSTRUCTED | False | 0.000 | 0.000 | — | 0.0000 |

## Decisions

| Member | Scenario | Outcome | Selected | Gap to best (s) | vs baseline (s) | False acc. | False rej. | τ ranking |
|---|---|---|---|---|---|---|---|---|
| control-boundary_optimist | D1-temperate | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 1 | 0 | 1.000 |
| control-boundary_optimist | D2-warm | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 3 | 0 | — |
| control-boundary_optimist | D3-cool | SELECTED_INFEASIBLE | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| control-boundary_optimist | V1-mild | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 4 | 0 | — |
| control-boundary_optimist | V2-hot | SELECTED_INFEASIBLE | c1=0.75,c2=1 | — | — | 1 | 0 | — |
| control-boundary_optimist | V3-cold | SELECTED_INFEASIBLE | c1=0.75,c2=0.8 | — | — | 2 | 0 | — |
| control-conservative | D1-temperate | MISSED_OPPORTUNITY | — | — | — | 0 | 3 | 1.000 |
| control-conservative | D2-warm | MISSED_OPPORTUNITY | — | — | — | 0 | 1 | — |
| control-conservative | D3-cool | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-conservative | V1-mild | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-conservative | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 680.4 | — | 0 | 2 | 1.000 |
| control-localized_sign_error | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| control-localized_sign_error | D3-cool | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-localized_sign_error | V1-mild | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-localized_sign_error | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| control-oracle | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| control-oracle | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 0 | 0 | — |
| control-oracle | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| control-rank_preserving_delay | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 1 | 1.000 |
| knn-s0 | D2-warm | MISSED_OPPORTUNITY | — | — | — | 0 | 1 | — |
| knn-s0 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| knn-s0 | V1-mild | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s0 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 1 | 0 | — |
| mlp-s0 | D3-cool | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp-s0 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s1 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp-s1 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp-s1 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp-s1 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s2 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp-s2 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp-s2 | V1-mild | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 1 | 0 | — |
| mlp-s2 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_ens3-s0 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp_ens3-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | D1-temperate | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_half-s0 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_half-s0 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp_half-s0 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp_half-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_half-s1 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_half-s1 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp_half-s1 | V1-mild | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 1 | 0 | — |
| mlp_half-s1 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_localized-s0 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_localized-s0 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp_localized-s0 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp_localized-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | D1-temperate | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_localized-s1 | D3-cool | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp_localized-s1 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_plus-s0 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_plus-s0 | D3-cool | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | V1-mild | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 1 | 0 | — |
| mlp_plus-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | D1-temperate | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_raw-s0 | D2-warm | SELECTED_FEASIBLE | c1=0.75,c2=1 | 0.0 | — | 0 | 0 | — |
| mlp_raw-s0 | D3-cool | SELECTED_UNRESOLVED | c1=0.75,c2=0.6 | — | — | 0 | 0 | — |
| mlp_raw-s0 | V1-mild | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 0 | — |
| mlp_raw-s0 | V2-hot | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | V3-cold | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |

## Limitations

- Charging speed is time to constant-voltage onset (the 4.19 V crossing), not time to a target state of charge. The reference keeps no SOC or current trajectory.
- The physics leg is not measurable for battery, so profiles that weight it are reported, not computed.
- The scoring set omits hidden duplicates, so the paired-repeat gate is not exercised.
- The model panel is small, and reconstruction seeds are repetitions of a recipe, not independent models.
