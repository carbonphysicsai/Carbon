# EV4: does Carbon's scoring prefer models that make better engineering decisions?

Public synthetic DEVELOPMENT evidence. It changes no testnet rule and claims no qualification. "Best" means best in the tested candidate set, not a global optimum. No optimal weight ratio is claimed.

- Contract: `sha256:fedd753c0e7aa69d2fd4d6efbf3d877ac8eeb211859d9f32d76a61f38bbe38d1`
- Scoring set: `docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/records.jsonl` (1588 cases, sha256 `88df01aacec5222f…`)
- Rule chosen on development scenarios: **control-exam-v1**
- Kendall τ (rule score vs. decision quality) on the verification scenarios: chosen rule 0.400, control 0.400

## The deciding rule and the proposed rule, side by side

The deciding rule is the frozen exam rule. The proposed rule is a prospective proposal and decides nothing until its own approval. Read both columns: ranking real models and catching optimism at the safety limits are separate questions, and a rule can win one and lose the other.

| Rule | τ verification (ranking real models) | τ development | Boundary-optimist control |
|---|---|---|---|
| deciding `control-exam-v1` | 0.400 | 0.095 | 99 of 99 members at or below it (not caught) |
| proposed `dar-p0-r100-a0` | 0.262 | -0.093 | 0 of 99 members at or below it (caught) |

Basis: `comparison.<rule>.tau_verification` and `summary.boundary_optimist_check` in this run's results. With a small panel, τ differences are indicative only.

## Pre-registered hypotheses

**H1 (primary, paired).** Δτ = τ(`dar-p0-r100-a0`) − τ(`control-exam-v1`) = -0.142 (0.262 − 0.403), 95 % paired bootstrap interval [-0.275, 0.121] over 99 eligible members and 12 verification conditions (B = 10000, seed 20261001, 0 replicates undefined). Decision: **UNRESOLVED**.

An interval that includes 0 is UNRESOLVED: it does not show that the rules rank models equally well.

**H2 (boundary-optimist control).**

- `dar-p0-r100-a0`: below every eligible member: True (0 of 99 at or below it)
- `control-exam-v1`: below every eligible member: False (99 of 99 at or below it)

**H3 (real-model blind spot).** 56 of 99 eligible real members select a protocol the reference verifies INFEASIBLE on at least one verification condition.

| Member | Conditions | Rank `dar-p0-r100-a0` | Rank `control-exam-v1` |
|---|---|---|---|
| deeponet-s1 | V-T9-S0.06 | 43 | 41 |
| deeponet_t1500_w128_d2-s0 | V-T9-S0.06 | 55 | 78 |
| deeponet_t1500_w256_d3-s1 | V-T9-S0.06 | 36 | 67 |
| deeponet_t1500_w512_d3-s0 | V-T9-S0.06, V-T29-S0.06 | 75 | 77 |
| deeponet_t3000_w128_d3-s0 | V-T9-S0.06 | 28 | 53 |
| deeponet_t3000_w256_d2-s0 | V-T9-S0.06 | 3 | 64 |
| deeponet_t3000_w256_d2-s1 | V-T9-S0.06 | 28 | 60 |
| deeponet_t3000_w512_d3-s0 | V-T9-S0.06 | 20 | 62 |
| deeponet_t500_w128_d2-s0 | V-T9-S0.06, V-T38-S0.22 | 88 | 91 |
| deeponet_t6000_w512_d2-s0 | V-T9-S0.06 | 83 | 61 |
| deeponet_t6000_w512_d3-s1 | V-T9-S0.06 | 22 | 54 |
| knn-s0 | V-T19-S0.40, V-T29-S0.06, V-T38-S0.22 | 91 | 93 |
| knn1-s0 | V-T9-S0.22, V-T9-S0.40, V-T38-S0.22 | 99 | 98 |
| knn10-s0 | V-T29-S0.06, V-T29-S0.40 | 90 | 94 |
| knn15-s0 | V-T29-S0.06, V-T29-S0.40 | 94 | 96 |
| knn25-s0 | V-T29-S0.06, V-T29-S0.40 | 97 | 97 |
| knn3-s0 | V-T9-S0.06, V-T9-S0.22, V-T29-S0.06, V-T38-S0.22 | 96 | 95 |
| knn40-s0 | V-T29-S0.06 | 98 | 99 |
| mlp_half-s1 | V-T9-S0.06 | 64 | 68 |
| mlp_localized-s0 | V-T9-S0.06 | 77 | 15 |
| mlp_plus-s0 | V-T9-S0.22 | 80 | 73 |
| mlp_t1500_w512_d2-s0 | V-T9-S0.06 | 59 | 36 |
| mlp_t1500_w512_d2-s1 | V-T9-S0.06 | 38 | 42 |
| mlp_t1500_w512_d3-s0 | V-T9-S0.06 | 72 | 25 |
| mlp_t1500_w64_d2-s0 | V-T9-S0.06 | 66 | 74 |
| mlp_t3000_w128_d2-s0 | V-T9-S0.06 | 28 | 37 |
| mlp_t3000_w128_d2_ens3-s0 | V-T9-S0.06 | 9 | 63 |
| mlp_t3000_w256_d2-s0 | V-T9-S0.06 | 39 | 27 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T9-S0.06, V-T9-S0.22 | 68 | 75 |
| mlp_t3000_w256_d3_f25-s0 | V-T9-S0.06 | 89 | 85 |
| mlp_t3000_w512_d2-s0 | V-T9-S0.06 | 55 | 30 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T9-S0.06 | 62 | 31 |
| mlp_t3000_w64_d2-s0 | V-T9-S0.06 | 14 | 56 |
| mlp_t3000_w64_d3-s1 | V-T9-S0.06 | 58 | 46 |
| mlp_t500_w128_d2-s0 | V-T9-S0.06 | 73 | 82 |
| mlp_t500_w128_d3-s0 | V-T9-S0.06 | 15 | 80 |
| mlp_t500_w128_d3_f50-s0 | V-T9-S0.06 | 10 | 81 |
| mlp_t500_w256_d2-s0 | V-T9-S0.06 | 85 | 79 |
| mlp_t500_w256_d3-s0 | V-T9-S0.06 | 64 | 70 |
| mlp_t500_w512_d2-s0 | V-T9-S0.06 | 86 | 76 |
| mlp_t500_w512_d3-s0 | V-T9-S0.06 | 31 | 55 |
| mlp_t500_w64_d2-s0 | V-T9-S0.06 | 74 | 90 |
| mlp_t500_w64_d2-s1 | V-T9-S0.06 | 12 | 92 |
| mlp_t500_w64_d3-s0 | V-T9-S0.06 | 84 | 86 |
| mlp_t6000_w128_d2-s0 | V-T9-S0.06 | 68 | 29 |
| mlp_t6000_w128_d3-s1 | V-T9-S0.06 | 17 | 18 |
| mlp_t6000_w256_d2-s0 | V-T9-S0.06 | 2 | 19 |
| mlp_t6000_w256_d3_arr-s0 | V-T9-S0.06 | 16 | 4 |
| mlp_t6000_w256_d3_ens4-s0 | V-T9-S0.06 | 49 | 3 |
| mlp_t6000_w256_d3_f25-s0 | V-T9-S0.06 | 93 | 87 |
| mlp_t6000_w256_d3_irw03-s0 | V-T9-S0.06 | 49 | 9 |
| mlp_t6000_w512_d2_f25-s0 | V-T9-S0.06 | 95 | 89 |
| mlp_t6000_w512_d2_f50-s0 | V-T9-S0.40 | 67 | 71 |
| mlp_t6000_w512_d3-s0 | V-T9-S0.06 | 19 | 22 |
| mlp_t6000_w64_d2-s1 | V-T9-S0.06 | 13 | 51 |
| mlp_wide-s0 | V-T9-S0.06 | 57 | 24 |

## Panel families

| Family | Members | Eligible | Verification loss range |
|---|---|---|---|
| deeponet | 16 | 16 | 0.002 – 1.919 |
| knn | 7 | 7 | 1.384 – 4.263 |
| mlp | 77 | 76 | 0.000 – 1.949 |

## Reference outcomes per scenario

| Scenario | Split | Best in tested set | Baseline | Feasible / infeasible / unresolved / unavailable |
|---|---|---|---|---|
| D-T5-S0.12 | development | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| D-T5-S0.33 | development | none | INFEASIBLE | 0 / 34 / 1 / 0 |
| D-T5-S0.48 | development | none | INFEASIBLE | 0 / 29 / 1 / 5 |
| D-T14-S0.12 | development | c1=1.5,c2=0.6 | FEASIBLE | 4 / 29 / 2 / 0 |
| D-T14-S0.33 | development | c1=1,c2=0.6 | FEASIBLE | 3 / 32 / 0 / 0 |
| D-T14-S0.48 | development | c1=0.75,c2=0.6 | FEASIBLE | 4 / 29 / 2 / 0 |
| D-T24-S0.12 | development | c1=1.75,c2=1 | INFEASIBLE | 14 / 21 / 0 / 0 |
| D-T24-S0.33 | development | c1=1.25,c2=1 | FEASIBLE | 10 / 24 / 1 / 0 |
| D-T24-S0.48 | development | c1=1,c2=0.8 | FEASIBLE | 9 / 20 / 6 / 0 |
| D-T34-S0.12 | development | c1=1,c2=1 | INFEASIBLE | 4 / 31 / 0 / 0 |
| D-T34-S0.33 | development | c1=1.75,c2=1 | FEASIBLE | 17 / 15 / 3 / 0 |
| D-T34-S0.48 | development | c1=1.25,c2=1 | FEASIBLE | 22 / 13 / 0 / 0 |
| V-T9-S0.06 | verification | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| V-T9-S0.22 | verification | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| V-T9-S0.40 | verification | c1=0.75,c2=0.4 | INFEASIBLE | 2 / 33 / 0 / 0 |
| V-T19-S0.06 | verification | c1=2,c2=1 | INFEASIBLE | 13 / 19 / 3 / 0 |
| V-T19-S0.22 | verification | c1=1.25,c2=0.8 | FEASIBLE | 6 / 23 / 6 / 0 |
| V-T19-S0.40 | verification | c1=1,c2=0.8 | FEASIBLE | 4 / 29 / 2 / 0 |
| V-T29-S0.06 | verification | c1=1.25,c2=1 | INFEASIBLE | 6 / 29 / 0 / 0 |
| V-T29-S0.22 | verification | c1=2,c2=1 | FEASIBLE | 18 / 16 / 1 / 0 |
| V-T29-S0.40 | verification | c1=1.5,c2=1 | FEASIBLE | 15 / 20 / 0 / 0 |
| V-T38-S0.06 | verification | none | INFEASIBLE | 0 / 35 / 0 / 0 |
| V-T38-S0.22 | verification | c1=0.75,c2=0.8 | INFEASIBLE | 1 / 34 / 0 / 0 |
| V-T38-S0.40 | verification | c1=1.5,c2=0.8 | FEASIBLE | 13 / 20 / 2 / 0 |

## Scoring rules against decision quality

τ > 0 means the rule prefers the models whose selections lose less. The panel is small, so treat these values as indicative.

| Rule | Measurable | τ development | τ verification | τ dev incl. controls | Top member (LOBO stable) |
|---|---|---|---|---|---|
| control-exam-v1 | yes | 0.095 | 0.400 | 0.105 | mlp_t6000_w256_d3_ens2-s0 (8/8) |
| p45-r30-a25 | no: NOT_MEASURABLE:missing_component | — | — | — | — |
| p0-r30-a70 | yes | 0.087 | 0.402 | 0.106 | mlp_t6000_w256_d3_ens2-s0 (8/8) |
| p0-r20-a80 | yes | 0.090 | 0.400 | 0.102 | mlp_t6000_w256_d3_ens2-s0 (8/8) |
| p0-r40-a60 | yes | 0.085 | 0.398 | 0.110 | mlp_t6000_w256_d3_ens2-s0 (8/8) |
| dar-p0-r100-a0 | yes | -0.093 | 0.262 | -0.031 | mlp_t6000_w256_d3_pca8-s0 (8/8) |
| dar-p0-r30-a70 | yes | 0.041 | 0.407 | 0.091 | mlp_t6000_w256_d2-s0 (4/8) |
| dar-p0-r50-a50 | yes | -0.007 | 0.403 | 0.049 | mlp_t6000_w256_d3_pca8-s0 (8/8) |

## Does each rule rank the boundary-optimist control below every eligible model?

The control is accurate almost everywhere and optimistic exactly near the plating and temperature limits, so it tends to select unsafe protocols.

| Rule | Below every eligible member | Members scored at or below it |
|---|---|---|
| control-exam-v1 | no | 99 of 99 |
| p45-r30-a25 | not measurable | — |
| p0-r30-a70 | no | 76 of 99 |
| p0-r20-a80 | no | 94 of 99 |
| p0-r40-a60 | no | 59 of 99 |
| dar-p0-r100-a0 | yes | 0 of 99 |
| dar-p0-r30-a70 | no | 3 of 99 |
| dar-p0-r50-a50 | yes | 0 of 99 |

## Members

Decision loss is measured in multiples of the minimum useful improvement; a false acceptance costs 10 and a missed opportunity costs 1 (provisional DEVELOPMENT costs).

| Member | Kind | Eligible | Mean loss (dev) | Mean loss (verify) | Control score | p0-r30-a70 |
|---|---|---|---|---|---|---|
| control-boundary_optimist | SYNTHETIC_CONTROL | True | 7.273 | 7.273 | -0.0462 | 0.9451 |
| control-conservative | SYNTHETIC_CONTROL | True | 3.119 | 2.749 | -0.2417 | 0.8053 |
| control-localized_sign_error | SYNTHETIC_CONTROL | True | 3.333 | 4.320 | -0.0077 | 0.9832 |
| control-oracle | SYNTHETIC_CONTROL | True | 0.000 | 0.000 | -0.0000 | 1.0000 |
| control-rank_preserving_delay | SYNTHETIC_CONTROL | True | 0.000 | 0.000 | -0.0329 | 0.9676 |
| deeponet-s0 | RECONSTRUCTED | True | 2.260 | 0.071 | -0.0617 | 0.9433 |
| deeponet-s1 | RECONSTRUCTED | True | 3.006 | 1.004 | -0.0640 | 0.9413 |
| deeponet_t1500_w128_d2-s0 | RECONSTRUCTED | True | 1.340 | 0.992 | -0.0999 | 0.9104 |
| deeponet_t1500_w256_d3-s0 | RECONSTRUCTED | True | 1.130 | 0.002 | -0.0836 | 0.9242 |
| deeponet_t1500_w256_d3-s1 | RECONSTRUCTED | True | 2.006 | 1.069 | -0.0828 | 0.9251 |
| deeponet_t1500_w512_d3-s0 | RECONSTRUCTED | True | 2.072 | 1.919 | -0.0977 | 0.9121 |
| deeponet_t3000_w128_d3-s0 | RECONSTRUCTED | True | 2.732 | 1.025 | -0.0685 | 0.9369 |
| deeponet_t3000_w256_d2-s0 | RECONSTRUCTED | True | 1.130 | 0.945 | -0.0814 | 0.9262 |
| deeponet_t3000_w256_d2-s1 | RECONSTRUCTED | True | 2.001 | 0.947 | -0.0782 | 0.9290 |
| deeponet_t3000_w512_d3-s0 | RECONSTRUCTED | True | 2.241 | 1.026 | -0.0799 | 0.9275 |
| deeponet_t500_w128_d2-s0 | RECONSTRUCTED | True | 0.151 | 1.786 | -0.1501 | 0.8728 |
| deeponet_t6000_w128_d2-s0 | RECONSTRUCTED | True | 2.032 | 0.098 | -0.0655 | 0.9395 |
| deeponet_t6000_w256_d2-s0 | RECONSTRUCTED | True | 2.016 | 0.097 | -0.0675 | 0.9383 |
| deeponet_t6000_w512_d2-s0 | RECONSTRUCTED | True | 1.012 | 0.972 | -0.0792 | 0.9281 |
| deeponet_t6000_w512_d3-s0 | RECONSTRUCTED | True | 2.727 | 0.038 | -0.0676 | 0.9383 |
| deeponet_t6000_w512_d3-s1 | RECONSTRUCTED | True | 1.146 | 0.910 | -0.0692 | 0.9362 |
| knn-s0 | RECONSTRUCTED | True | 2.088 | 3.131 | -0.1708 | 0.8562 |
| knn1-s0 | RECONSTRUCTED | True | 4.333 | 4.158 | -0.2263 | 0.8175 |
| knn10-s0 | RECONSTRUCTED | True | 1.351 | 2.163 | -0.1780 | 0.8520 |
| knn15-s0 | RECONSTRUCTED | True | 0.137 | 2.096 | -0.1907 | 0.8433 |
| knn25-s0 | RECONSTRUCTED | True | 1.782 | 2.339 | -0.2133 | 0.8275 |
| knn3-s0 | RECONSTRUCTED | True | 1.924 | 4.263 | -0.1784 | 0.8508 |
| knn40-s0 | RECONSTRUCTED | True | 0.472 | 1.384 | -0.2417 | 0.8093 |
| mlp-s0 | RECONSTRUCTED | True | 1.125 | 0.058 | -0.0551 | 0.9490 |
| mlp-s1 | RECONSTRUCTED | True | 2.046 | 0.112 | -0.0564 | 0.9476 |
| mlp-s2 | RECONSTRUCTED | True | 0.055 | 0.003 | -0.0574 | 0.9466 |
| mlp_ens3-s0 | RECONSTRUCTED | True | 2.017 | 0.003 | -0.0514 | 0.9522 |
| mlp_half-s0 | RECONSTRUCTED | True | 1.103 | 0.040 | -0.0874 | 0.9204 |
| mlp_half-s1 | RECONSTRUCTED | True | 2.038 | 0.909 | -0.0834 | 0.9262 |
| mlp_localized-s0 | RECONSTRUCTED | True | 1.446 | 1.001 | -0.0572 | 0.9461 |
| mlp_localized-s1 | RECONSTRUCTED | True | 3.017 | 0.119 | -0.0585 | 0.9457 |
| mlp_plus-s0 | RECONSTRUCTED | True | 4.016 | 0.964 | -0.0890 | 0.9190 |
| mlp_raw-s0 | RECONSTRUCTED | False | 1.124 | 1.000 | — | 0.0000 |
| mlp_t1500_w128_d2-s0 | RECONSTRUCTED | True | 1.130 | 0.052 | -0.0751 | 0.9323 |
| mlp_t1500_w128_d2_f25-s0 | RECONSTRUCTED | True | 1.159 | 0.128 | -0.1173 | 0.8966 |
| mlp_t1500_w128_d2_f50-s0 | RECONSTRUCTED | True | 2.032 | 0.074 | -0.0828 | 0.9252 |
| mlp_t1500_w128_d3-s0 | RECONSTRUCTED | True | 2.000 | 0.003 | -0.0677 | 0.9378 |
| mlp_t1500_w128_d3-s1 | RECONSTRUCTED | True | 2.013 | 0.038 | -0.0671 | 0.9386 |
| mlp_t1500_w128_d3_wd1em4-s0 | RECONSTRUCTED | True | 2.000 | 0.003 | -0.0677 | 0.9378 |
| mlp_t1500_w256_d2-s0 | RECONSTRUCTED | True | 1.005 | 0.036 | -0.0684 | 0.9371 |
| mlp_t1500_w256_d2_arr-s0 | RECONSTRUCTED | True | 1.001 | 0.002 | -0.0611 | 0.9437 |
| mlp_t1500_w256_d3-s0 | RECONSTRUCTED | True | 0.014 | 0.099 | -0.0611 | 0.9437 |
| mlp_t1500_w512_d2-s0 | RECONSTRUCTED | True | 1.039 | 1.069 | -0.0628 | 0.9423 |
| mlp_t1500_w512_d2-s1 | RECONSTRUCTED | True | 1.045 | 0.947 | -0.0645 | 0.9409 |
| mlp_t1500_w512_d3-s0 | RECONSTRUCTED | True | 1.050 | 1.082 | -0.0598 | 0.9446 |
| mlp_t1500_w64_d2-s0 | RECONSTRUCTED | True | 1.228 | 1.146 | -0.0902 | 0.9187 |
| mlp_t1500_w64_d3-s0 | RECONSTRUCTED | True | 1.117 | 0.038 | -0.0771 | 0.9296 |
| mlp_t3000_w128_d2-s0 | RECONSTRUCTED | True | 0.019 | 0.886 | -0.0635 | 0.9416 |
| mlp_t3000_w128_d2_ens3-s0 | RECONSTRUCTED | True | 2.084 | 1.008 | -0.0812 | 0.9268 |
| mlp_t3000_w128_d2_irw01-s0 | RECONSTRUCTED | True | 0.056 | 0.002 | -0.0635 | 0.9402 |
| mlp_t3000_w128_d3-s0 | RECONSTRUCTED | True | 1.149 | 0.003 | -0.0599 | 0.9447 |
| mlp_t3000_w256_d2-s0 | RECONSTRUCTED | True | 1.130 | 1.008 | -0.0602 | 0.9443 |
| mlp_t3000_w256_d2-s1 | RECONSTRUCTED | True | 2.171 | 0.063 | -0.0610 | 0.9439 |
| mlp_t3000_w256_d3-s0 | RECONSTRUCTED | True | 0.016 | 0.036 | -0.0555 | 0.9489 |
| mlp_t3000_w256_d3_arr_pca16-s0 | RECONSTRUCTED | True | 1.217 | 1.949 | -0.0918 | 0.9166 |
| mlp_t3000_w256_d3_f25-s0 | RECONSTRUCTED | True | 1.149 | 1.289 | -0.1185 | 0.8954 |
| mlp_t3000_w256_d3_f25-s1 | RECONSTRUCTED | True | 2.308 | 0.162 | -0.1256 | 0.8882 |
| mlp_t3000_w256_d3_f50-s0 | RECONSTRUCTED | True | 1.046 | 0.058 | -0.0824 | 0.9247 |
| mlp_t3000_w512_d2-s0 | RECONSTRUCTED | True | 1.006 | 1.028 | -0.0605 | 0.9443 |
| mlp_t3000_w512_d2_wd1em4-s0 | RECONSTRUCTED | True | 1.006 | 1.028 | -0.0606 | 0.9442 |
| mlp_t3000_w512_d3-s0 | RECONSTRUCTED | True | 2.370 | 0.110 | -0.0567 | 0.9473 |
| mlp_t3000_w512_d3_f25-s0 | RECONSTRUCTED | True | 0.042 | 0.038 | -0.1160 | 0.8980 |
| mlp_t3000_w64_d2-s0 | RECONSTRUCTED | True | 1.112 | 0.964 | -0.0728 | 0.9337 |
| mlp_t3000_w64_d3-s0 | RECONSTRUCTED | True | 1.017 | 0.003 | -0.0672 | 0.9382 |
| mlp_t3000_w64_d3-s1 | RECONSTRUCTED | True | 0.007 | 1.002 | -0.0674 | 0.9379 |
| mlp_t500_w128_d2-s0 | RECONSTRUCTED | True | 2.345 | 1.057 | -0.1125 | 0.9014 |
| mlp_t500_w128_d3-s0 | RECONSTRUCTED | True | 1.110 | 0.966 | -0.1032 | 0.9084 |
| mlp_t500_w128_d3_f50-s0 | RECONSTRUCTED | True | 2.308 | 1.066 | -0.1101 | 0.9032 |
| mlp_t500_w256_d2-s0 | RECONSTRUCTED | True | 2.315 | 1.027 | -0.1014 | 0.9098 |
| mlp_t500_w256_d3-s0 | RECONSTRUCTED | True | 2.609 | 1.025 | -0.0838 | 0.9242 |
| mlp_t500_w256_d3-s1 | RECONSTRUCTED | True | 1.006 | 0.057 | -0.0766 | 0.9302 |
| mlp_t500_w512_d2-s0 | RECONSTRUCTED | True | 2.315 | 1.025 | -0.0949 | 0.9152 |
| mlp_t500_w512_d3-s0 | RECONSTRUCTED | True | 0.007 | 0.945 | -0.0726 | 0.9339 |
| mlp_t500_w64_d2-s0 | RECONSTRUCTED | True | 1.110 | 0.941 | -0.1458 | 0.8759 |
| mlp_t500_w64_d2-s1 | RECONSTRUCTED | True | 1.276 | 1.427 | -0.1575 | 0.8670 |
| mlp_t500_w64_d3-s0 | RECONSTRUCTED | True | 1.197 | 1.053 | -0.1208 | 0.8941 |
| mlp_t6000_w128_d2-s0 | RECONSTRUCTED | True | 0.001 | 0.949 | -0.0605 | 0.9437 |
| mlp_t6000_w128_d3-s0 | RECONSTRUCTED | True | 1.292 | 0.002 | -0.0569 | 0.9475 |
| mlp_t6000_w128_d3-s1 | RECONSTRUCTED | True | 1.050 | 0.909 | -0.0577 | 0.9467 |
| mlp_t6000_w256_d2-s0 | RECONSTRUCTED | True | 2.013 | 0.910 | -0.0584 | 0.9467 |
| mlp_t6000_w256_d3_arr-s0 | RECONSTRUCTED | True | 1.012 | 1.002 | -0.0544 | 0.9501 |
| mlp_t6000_w256_d3_ens2-s0 | RECONSTRUCTED | True | 0.057 | 0.002 | -0.0508 | 0.9527 |
| mlp_t6000_w256_d3_ens4-s0 | RECONSTRUCTED | True | 2.001 | 1.004 | -0.0536 | 0.9503 |
| mlp_t6000_w256_d3_f25-s0 | RECONSTRUCTED | True | 1.241 | 1.182 | -0.1228 | 0.8920 |
| mlp_t6000_w256_d3_irw003-s0 | RECONSTRUCTED | True | 0.020 | 0.055 | -0.0585 | 0.9444 |
| mlp_t6000_w256_d3_irw03-s0 | RECONSTRUCTED | True | 0.006 | 0.910 | -0.0560 | 0.9478 |
| mlp_t6000_w256_d3_irw03-s1 | RECONSTRUCTED | True | 1.125 | 0.000 | -0.0571 | 0.9478 |
| mlp_t6000_w256_d3_irw3-s0 | RECONSTRUCTED | True | 2.743 | 0.000 | -0.0572 | 0.9468 |
| mlp_t6000_w256_d3_pca8-s0 | RECONSTRUCTED | True | 2.033 | 0.042 | -0.0637 | 0.9416 |
| mlp_t6000_w256_d3_wd1em3-s0 | RECONSTRUCTED | True | 1.125 | 0.058 | -0.0550 | 0.9491 |
| mlp_t6000_w256_d3_wd1em3-s1 | RECONSTRUCTED | True | 2.050 | 0.112 | -0.0563 | 0.9477 |
| mlp_t6000_w256_d3_wd1em5-s0 | RECONSTRUCTED | True | 1.125 | 0.058 | -0.0551 | 0.9490 |
| mlp_t6000_w512_d2_f25-s0 | RECONSTRUCTED | True | 0.197 | 1.222 | -0.1266 | 0.8903 |
| mlp_t6000_w512_d2_f50-s0 | RECONSTRUCTED | True | 1.129 | 0.949 | -0.0871 | 0.9219 |
| mlp_t6000_w512_d3-s0 | RECONSTRUCTED | True | 1.929 | 1.060 | -0.0587 | 0.9459 |
| mlp_t6000_w512_d3-s1 | RECONSTRUCTED | True | 1.130 | 0.002 | -0.0587 | 0.9457 |
| mlp_t6000_w64_d2-s0 | RECONSTRUCTED | True | 0.038 | 0.118 | -0.0637 | 0.9415 |
| mlp_t6000_w64_d2-s1 | RECONSTRUCTED | True | 1.130 | 1.004 | -0.0684 | 0.9377 |
| mlp_t6000_w64_d3-s0 | RECONSTRUCTED | True | 0.007 | 0.004 | -0.0604 | 0.9444 |
| mlp_wide-s0 | RECONSTRUCTED | True | 3.006 | 0.972 | -0.0591 | 0.9455 |

## Decisions

| Member | Scenario | Outcome | Selected | Gap to best (s) | vs baseline (s) | False acc. | False rej. | τ ranking |
|---|---|---|---|---|---|---|---|---|
| control-boundary_optimist | D-T5-S0.12 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 3 | 0 | — |
| control-boundary_optimist | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 2 | 0 | — |
| control-boundary_optimist | D-T5-S0.48 | MODEL_OUTPUT_MISSING | — | — | — | — | — | — |
| control-boundary_optimist | D-T14-S0.12 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 9 | 0 | 1.000 |
| control-boundary_optimist | D-T14-S0.33 | SELECTED_INFEASIBLE | c1=1,c2=1 | — | — | 5 | 0 | 1.000 |
| control-boundary_optimist | D-T14-S0.48 | SELECTED_INFEASIBLE | c1=1.25,c2=0.8 | — | — | 6 | 0 | 1.000 |
| control-boundary_optimist | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 1.000 |
| control-boundary_optimist | D-T24-S0.33 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 4 | 0 | 1.000 |
| control-boundary_optimist | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 7 | 0 | 1.000 |
| control-boundary_optimist | D-T34-S0.12 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| control-boundary_optimist | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 1.000 |
| control-boundary_optimist | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 0 | 1.000 |
| control-boundary_optimist | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 12 | 0 | — |
| control-boundary_optimist | V-T9-S0.22 | SELECTED_INFEASIBLE | c1=1,c2=0.8 | — | — | 4 | 0 | — |
| control-boundary_optimist | V-T9-S0.40 | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 2 | 0 | 1.000 |
| control-boundary_optimist | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| control-boundary_optimist | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 2 | 0 | 1.000 |
| control-boundary_optimist | V-T19-S0.40 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 5 | 0 | 1.000 |
| control-boundary_optimist | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 3 | 0 | 1.000 |
| control-boundary_optimist | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 1.000 |
| control-boundary_optimist | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 3 | 0 | 1.000 |
| control-boundary_optimist | V-T38-S0.06 | SELECTED_INFEASIBLE | c1=1,c2=1 | — | — | 3 | 0 | — |
| control-boundary_optimist | V-T38-S0.22 | SELECTED_INFEASIBLE | c1=1,c2=1 | — | — | 4 | 0 | — |
| control-boundary_optimist | V-T38-S0.40 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 6 | 0 | 1.000 |
| control-conservative | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-conservative | D-T5-S0.48 | MODEL_OUTPUT_MISSING | — | — | — | — | — | — |
| control-conservative | D-T14-S0.12 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | 1.000 |
| control-conservative | D-T14-S0.33 | MISSED_OPPORTUNITY | — | — | — | 0 | 3 | 1.000 |
| control-conservative | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 1357.3 | -1357.3 | 0 | 2 | 1.000 |
| control-conservative | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 439.4 | — | 0 | 8 | 1.000 |
| control-conservative | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 372.4 | 890.5 | 0 | 4 | 1.000 |
| control-conservative | D-T24-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 663.5 | 0.0 | 0 | 5 | 1.000 |
| control-conservative | D-T34-S0.12 | SELECTED_FEASIBLE | c1=0.75,c2=1 | 586.7 | — | 0 | 2 | 1.000 |
| control-conservative | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 457.6 | 1107.7 | 0 | 8 | 1.000 |
| control-conservative | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 6 | 1.000 |
| control-conservative | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | V-T9-S0.40 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | 1.000 |
| control-conservative | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=0.6 | 1104.1 | — | 0 | 9 | 1.000 |
| control-conservative | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 659.6 | 355.4 | 0 | 3 | 1.000 |
| control-conservative | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 634.1 | 42.1 | 0 | 1 | 1.000 |
| control-conservative | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1,c2=1 | 330.2 | — | 0 | 4 | 1.000 |
| control-conservative | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 41.9 | 1725.7 | 0 | 7 | 1.000 |
| control-conservative | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 6 | 1.000 |
| control-conservative | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-conservative | V-T38-S0.22 | MISSED_OPPORTUNITY | — | — | — | 0 | 1 | — |
| control-conservative | V-T38-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 946.8 | 0.0 | 0 | 11 | 1.000 |
| control-localized_sign_error | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 0 | 0 | — |
| control-localized_sign_error | D-T5-S0.48 | MODEL_OUTPUT_MISSING | — | — | — | — | — | — |
| control-localized_sign_error | D-T14-S0.12 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 7 | 4 | 1.000 |
| control-localized_sign_error | D-T14-S0.33 | SELECTED_INFEASIBLE | c1=1,c2=0.8 | — | — | 2 | 3 | 1.000 |
| control-localized_sign_error | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 2 | 1.000 |
| control-localized_sign_error | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| control-localized_sign_error | D-T24-S0.33 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 4 | 2 | 1.000 |
| control-localized_sign_error | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 0 | 1.000 |
| control-localized_sign_error | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-localized_sign_error | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 1.000 |
| control-localized_sign_error | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 3 | 1.000 |
| control-localized_sign_error | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.75,c2=0.6 | — | — | 4 | 0 | — |
| control-localized_sign_error | V-T9-S0.22 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 2 | 0 | — |
| control-localized_sign_error | V-T9-S0.40 | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 1 | 0 | 1.000 |
| control-localized_sign_error | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 381.6 | — | 1 | 5 | 1.000 |
| control-localized_sign_error | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 1 | 3 | 1.000 |
| control-localized_sign_error | V-T19-S0.40 | SELECTED_INFEASIBLE | c1=1,c2=1 | — | — | 1 | 1 | 1.000 |
| control-localized_sign_error | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-localized_sign_error | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 3 | 1.000 |
| control-localized_sign_error | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 1 | 1.000 |
| control-localized_sign_error | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-localized_sign_error | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| control-localized_sign_error | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-oracle | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-oracle | D-T5-S0.48 | MODEL_OUTPUT_MISSING | — | — | — | — | — | — |
| control-oracle | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| control-oracle | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| control-oracle | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| control-oracle | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| control-oracle | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| control-oracle | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 1.000 |
| control-oracle | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 0 | 1.000 |
| control-oracle | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 0 | 0 | 1.000 |
| control-oracle | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| control-oracle | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-oracle | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 1.000 |
| control-oracle | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 1.000 |
| control-oracle | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-oracle | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| control-oracle | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | D-T5-S0.48 | MODEL_OUTPUT_MISSING | — | — | — | — | — | — |
| control-rank_preserving_delay | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 1 | 1.000 |
| control-rank_preserving_delay | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 1.000 |
| control-rank_preserving_delay | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| control-rank_preserving_delay | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 1.000 |
| deeponet-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| deeponet-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 0.667 |
| deeponet-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| deeponet-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| deeponet-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| deeponet-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 2 | 1 | 0.948 |
| deeponet-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| deeponet-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| deeponet-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| deeponet-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| deeponet-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.924 |
| deeponet-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 1 | 0 | 0.897 |
| deeponet-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet-s1 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| deeponet-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet-s1 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| deeponet-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| deeponet-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 3 | 0 | 1.000 |
| deeponet-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| deeponet-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 0 | 0.957 |
| deeponet-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 1 | 0 | — |
| deeponet-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| deeponet-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| deeponet-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| deeponet-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.922 |
| deeponet-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| deeponet-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet-s1 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 1 | 0 | 0.923 |
| deeponet_t1500_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w128_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet_t1500_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t1500_w128_d2-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.667 |
| deeponet_t1500_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| deeponet_t1500_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| deeponet_t1500_w128_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| deeponet_t1500_w128_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| deeponet_t1500_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 4 | 0 | 0.944 |
| deeponet_t1500_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| deeponet_t1500_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| deeponet_t1500_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 2 | 3 | 0.957 |
| deeponet_t1500_w128_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| deeponet_t1500_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet_t1500_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.974 |
| deeponet_t1500_w128_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t1500_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 0.667 |
| deeponet_t1500_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| deeponet_t1500_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.869 |
| deeponet_t1500_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| deeponet_t1500_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w128_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| deeponet_t1500_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 104.4 | 842.5 | 1 | 1 | 0.846 |
| deeponet_t1500_w256_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| deeponet_t1500_w256_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet_t1500_w256_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| deeponet_t1500_w256_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| deeponet_t1500_w256_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| deeponet_t1500_w256_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| deeponet_t1500_w256_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.913 |
| deeponet_t1500_w256_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| deeponet_t1500_w256_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| deeponet_t1500_w256_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.882 |
| deeponet_t1500_w256_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.943 |
| deeponet_t1500_w256_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t1500_w256_d3-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.949 |
| deeponet_t1500_w256_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t1500_w256_d3-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| deeponet_t1500_w256_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t1500_w256_d3-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet_t1500_w256_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| deeponet_t1500_w256_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| deeponet_t1500_w256_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| deeponet_t1500_w256_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 1 | 0.922 |
| deeponet_t1500_w256_d3-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| deeponet_t1500_w256_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t1500_w256_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.974 |
| deeponet_t1500_w256_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t1500_w256_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 0.667 |
| deeponet_t1500_w256_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| deeponet_t1500_w256_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| deeponet_t1500_w256_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.943 |
| deeponet_t1500_w256_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| deeponet_t1500_w256_d3-s1 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.923 |
| deeponet_t1500_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w512_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t1500_w512_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t1500_w512_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| deeponet_t1500_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 0.333 |
| deeponet_t1500_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t1500_w512_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| deeponet_t1500_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| deeponet_t1500_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| deeponet_t1500_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| deeponet_t1500_w512_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| deeponet_t1500_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 2 | 2 | 0.948 |
| deeponet_t1500_w512_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 3 | 0 | — |
| deeponet_t1500_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t1500_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 2 | 1.000 |
| deeponet_t1500_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t1500_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 0.667 |
| deeponet_t1500_w512_d3-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 3 | 1 | 0.800 |
| deeponet_t1500_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.869 |
| deeponet_t1500_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.771 |
| deeponet_t1500_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t1500_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| deeponet_t1500_w512_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 1 | 0.949 |
| deeponet_t3000_w128_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w128_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t3000_w128_d3-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t3000_w128_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t3000_w128_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet_t3000_w128_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.956 |
| deeponet_t3000_w128_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 1 | 0.939 |
| deeponet_t3000_w128_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 3 | 0 | — |
| deeponet_t3000_w128_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w128_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t3000_w128_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| deeponet_t3000_w128_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t3000_w128_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| deeponet_t3000_w128_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| deeponet_t3000_w128_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.905 |
| deeponet_t3000_w128_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w128_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t3000_w128_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.897 |
| deeponet_t3000_w256_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| deeponet_t3000_w256_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t3000_w256_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.934 |
| deeponet_t3000_w256_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| deeponet_t3000_w256_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| deeponet_t3000_w256_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.912 |
| deeponet_t3000_w256_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.913 |
| deeponet_t3000_w256_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| deeponet_t3000_w256_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 1 | 0.939 |
| deeponet_t3000_w256_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| deeponet_t3000_w256_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| deeponet_t3000_w256_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.905 |
| deeponet_t3000_w256_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| deeponet_t3000_w256_d2-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t3000_w256_d2-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 1 | 1.000 |
| deeponet_t3000_w256_d2-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet_t3000_w256_d2-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| deeponet_t3000_w256_d2-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.944 |
| deeponet_t3000_w256_d2-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| deeponet_t3000_w256_d2-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| deeponet_t3000_w256_d2-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 1 | 0 | 0.957 |
| deeponet_t3000_w256_d2-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| deeponet_t3000_w256_d2-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.872 |
| deeponet_t3000_w256_d2-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t3000_w256_d2-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| deeponet_t3000_w256_d2-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| deeponet_t3000_w256_d2-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.886 |
| deeponet_t3000_w256_d2-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w256_d2-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t3000_w256_d2-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.949 |
| deeponet_t3000_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w512_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t3000_w512_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t3000_w512_d3-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| deeponet_t3000_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t3000_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t3000_w512_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| deeponet_t3000_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| deeponet_t3000_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 2 | 0 | 0.889 |
| deeponet_t3000_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| deeponet_t3000_w512_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| deeponet_t3000_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 1 | 0 | 0.913 |
| deeponet_t3000_w512_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 2 | 0 | — |
| deeponet_t3000_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t3000_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| deeponet_t3000_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t3000_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t3000_w512_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 2 | 0.667 |
| deeponet_t3000_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| deeponet_t3000_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.829 |
| deeponet_t3000_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t3000_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t3000_w512_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.923 |
| deeponet_t500_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t500_w128_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet_t500_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t500_w128_d2-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 1 | 2 | 0.333 |
| deeponet_t500_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| deeponet_t500_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t500_w128_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 3 | 0 | 0.780 |
| deeponet_t500_w128_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| deeponet_t500_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.722 |
| deeponet_t500_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 2 | 1.000 |
| deeponet_t500_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 53.3 | 1512.0 | 0 | 2 | 0.912 |
| deeponet_t500_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 0 | 3 | 0.844 |
| deeponet_t500_w128_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| deeponet_t500_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t500_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t500_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 1 | 0.879 |
| deeponet_t500_w128_d2-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 1.000 |
| deeponet_t500_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| deeponet_t500_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 1 | 0.800 |
| deeponet_t500_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 41.9 | 1725.7 | 0 | 1 | 0.824 |
| deeponet_t500_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.829 |
| deeponet_t500_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t500_w128_d2-s0 | V-T38-S0.22 | SELECTED_INFEASIBLE | c1=0.75,c2=1 | — | — | 1 | 0 | — |
| deeponet_t500_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 1 | 0.923 |
| deeponet_t6000_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w128_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t6000_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t6000_w128_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t6000_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t6000_w128_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.978 |
| deeponet_t6000_w128_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| deeponet_t6000_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 1.000 |
| deeponet_t6000_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet_t6000_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.912 |
| deeponet_t6000_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1,c2=1 | 37.5 | 1210.9 | 3 | 0 | 0.931 |
| deeponet_t6000_w128_d2-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t6000_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| deeponet_t6000_w128_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t6000_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| deeponet_t6000_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| deeponet_t6000_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.935 |
| deeponet_t6000_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.848 |
| deeponet_t6000_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w128_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t6000_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 2 | 0.949 |
| deeponet_t6000_w256_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w256_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t6000_w256_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t6000_w256_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w256_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| deeponet_t6000_w256_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| deeponet_t6000_w256_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.934 |
| deeponet_t6000_w256_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| deeponet_t6000_w256_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.889 |
| deeponet_t6000_w256_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet_t6000_w256_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.926 |
| deeponet_t6000_w256_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.905 |
| deeponet_t6000_w256_d2-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w256_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w256_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t6000_w256_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| deeponet_t6000_w256_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t6000_w256_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| deeponet_t6000_w256_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| deeponet_t6000_w256_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| deeponet_t6000_w256_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.905 |
| deeponet_t6000_w256_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w256_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t6000_w256_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.949 |
| deeponet_t6000_w512_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d2-s0 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t6000_w512_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t6000_w512_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| deeponet_t6000_w512_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| deeponet_t6000_w512_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| deeponet_t6000_w512_d2-s0 | D-T24-S0.48 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 663.5 | 3 | 0 | 0.944 |
| deeponet_t6000_w512_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| deeponet_t6000_w512_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.956 |
| deeponet_t6000_w512_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 2 | 0 | 0.931 |
| deeponet_t6000_w512_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 2 | 0 | — |
| deeponet_t6000_w512_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| deeponet_t6000_w512_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| deeponet_t6000_w512_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t6000_w512_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| deeponet_t6000_w512_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| deeponet_t6000_w512_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.886 |
| deeponet_t6000_w512_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t6000_w512_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.949 |
| deeponet_t6000_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t6000_w512_d3-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| deeponet_t6000_w512_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| deeponet_t6000_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 2 | 0 | 0.889 |
| deeponet_t6000_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| deeponet_t6000_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 2 | 1 | 0.948 |
| deeponet_t6000_w512_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| deeponet_t6000_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| deeponet_t6000_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| deeponet_t6000_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.886 |
| deeponet_t6000_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t6000_w512_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| deeponet_t6000_w512_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s1 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.934 |
| deeponet_t6000_w512_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| deeponet_t6000_w512_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| deeponet_t6000_w512_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.956 |
| deeponet_t6000_w512_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1,c2=1 | 37.5 | 1210.9 | 1 | 0 | 0.913 |
| deeponet_t6000_w512_d3-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 1 | 0 | — |
| deeponet_t6000_w512_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| deeponet_t6000_w512_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| deeponet_t6000_w512_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| deeponet_t6000_w512_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| deeponet_t6000_w512_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| deeponet_t6000_w512_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| deeponet_t6000_w512_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| deeponet_t6000_w512_d3-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.974 |
| knn-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 0 | 0 | — |
| knn-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn-s0 | D-T14-S0.12 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 1 | 3 | -1.000 |
| knn-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| knn-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 3 | -1.000 |
| knn-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 4 | 0.778 |
| knn-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 2 | 0 | 0.822 |
| knn-s0 | D-T24-S0.48 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 663.5 | 2 | 2 | 0.929 |
| knn-s0 | D-T34-S0.12 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 2 | 2 | 1.000 |
| knn-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.794 |
| knn-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 0 | 1 | 0.743 |
| knn-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| knn-s0 | V-T19-S0.06 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 2 | 6 | 0.833 |
| knn-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 2 | 0.733 |
| knn-s0 | V-T19-S0.40 | SELECTED_INFEASIBLE | c1=1.25,c2=1 | — | — | 2 | 1 | 1.000 |
| knn-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 2 | 2 | 0.667 |
| knn-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 4 | 0.765 |
| knn-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 2 | 0 | 0.829 |
| knn-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn-s0 | V-T38-S0.22 | SELECTED_INFEASIBLE | c1=0.5,c2=1 | — | — | 2 | 0 | — |
| knn-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 2 | 4 | 0.727 |
| knn1-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn1-s0 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 0 | 0 | — |
| knn1-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| knn1-s0 | D-T14-S0.12 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 2 | 3 | 1.000 |
| knn1-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.5,c2=0.6 | 615.2 | -529.4 | 1 | 2 | 1.000 |
| knn1-s0 | D-T14-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.8 | — | — | 1 | 3 | -1.000 |
| knn1-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 75.2 | — | 2 | 2 | 0.625 |
| knn1-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 435.8 | 827.2 | 6 | 1 | 0.523 |
| knn1-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 2 | 0.743 |
| knn1-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| knn1-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 2 | 0 | 0.862 |
| knn1-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 473.1 | 775.3 | 2 | 2 | 0.636 |
| knn1-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn1-s0 | V-T9-S0.22 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 2 | 0 | — |
| knn1-s0 | V-T9-S0.40 | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 1 | 0 | — |
| knn1-s0 | V-T19-S0.06 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 2 | 4 | 0.801 |
| knn1-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 2 | 1 | 0.645 |
| knn1-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 634.1 | 42.1 | 2 | 1 | 0.913 |
| knn1-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1,c2=1 | 330.2 | — | 2 | 0 | 0.701 |
| knn1-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 41.9 | 1725.7 | 1 | 2 | 0.682 |
| knn1-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 5 | 0 | 0.837 |
| knn1-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn1-s0 | V-T38-S0.22 | SELECTED_INFEASIBLE | c1=0.5,c2=0.8 | — | — | 1 | 0 | — |
| knn1-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 311.0 | 635.8 | 0 | 5 | 0.469 |
| knn10-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn10-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn10-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn10-s0 | D-T14-S0.12 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | — |
| knn10-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| knn10-s0 | D-T14-S0.48 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | 1.000 |
| knn10-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 4 | 0.689 |
| knn10-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 1 | 0.833 |
| knn10-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 1 | 1 | 0.929 |
| knn10-s0 | D-T34-S0.12 | SELECTED_INFEASIBLE | c1=1.25,c2=0.8 | — | — | 1 | 2 | 1.000 |
| knn10-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 1 | 0.850 |
| knn10-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 0 | 3 | 0.754 |
| knn10-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn10-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn10-s0 | V-T9-S0.40 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| knn10-s0 | V-T19-S0.06 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 9 | 1.000 |
| knn10-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 1 | 1 | 0.867 |
| knn10-s0 | V-T19-S0.40 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 0 | 1 | 1.000 |
| knn10-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 2 | 3 | 0.333 |
| knn10-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 2 | 0.817 |
| knn10-s0 | V-T29-S0.40 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 2 | 0 | 0.752 |
| knn10-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn10-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| knn10-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 2 | 3 | 0.872 |
| knn15-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn15-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn15-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 3 | — |
| knn15-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| knn15-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 2 | 1.000 |
| knn15-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 3 | 4 | 0.822 |
| knn15-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| knn15-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 1 | 2 | 0.857 |
| knn15-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 2 | 1.000 |
| knn15-s0 | D-T34-S0.33 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 1 | 0.817 |
| knn15-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 0 | 2 | 0.821 |
| knn15-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | V-T9-S0.40 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| knn15-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 0 | 7 | 0.905 |
| knn15-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 1 | 1 | 0.800 |
| knn15-s0 | V-T19-S0.40 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 1 | 1.000 |
| knn15-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 2 | 4 | -1.000 |
| knn15-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 4 | 0.736 |
| knn15-s0 | V-T29-S0.40 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 4 | 0 | 0.771 |
| knn15-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn15-s0 | V-T38-S0.22 | MISSED_OPPORTUNITY | — | — | — | 0 | 1 | — |
| knn15-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 1 | 4 | 0.758 |
| knn25-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn25-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn25-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn25-s0 | D-T14-S0.12 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | — |
| knn25-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| knn25-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.5,c2=0.6 | 184.5 | -184.5 | 0 | 2 | -1.000 |
| knn25-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 7 | 0.714 |
| knn25-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 3 | 1 | 0.778 |
| knn25-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 1 | 2 | 0.857 |
| knn25-s0 | D-T34-S0.12 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | — |
| knn25-s0 | D-T34-S0.33 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 1 | 0.900 |
| knn25-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 3 | 0.871 |
| knn25-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn25-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn25-s0 | V-T9-S0.40 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| knn25-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 0 | 7 | 0.714 |
| knn25-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 2 | 1 | 0.800 |
| knn25-s0 | V-T19-S0.40 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 1 | 1.000 |
| knn25-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 2 | 4 | -1.000 |
| knn25-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 41.9 | 1725.7 | 0 | 6 | 0.606 |
| knn25-s0 | V-T29-S0.40 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 2 | 0 | 0.714 |
| knn25-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn25-s0 | V-T38-S0.22 | MISSED_OPPORTUNITY | — | — | — | 0 | 1 | — |
| knn25-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 1 | 5 | 0.818 |
| knn3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| knn3-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| knn3-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 1 | -0.333 |
| knn3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| knn3-s0 | D-T14-S0.48 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | 1.000 |
| knn3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 4 | 0.867 |
| knn3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 2 | 0 | 0.778 |
| knn3-s0 | D-T24-S0.48 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 663.5 | 2 | 2 | 0.643 |
| knn3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| knn3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.824 |
| knn3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 0 | 1 | 0.714 |
| knn3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 1 | 0 | — |
| knn3-s0 | V-T9-S0.22 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 1 | 0 | — |
| knn3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| knn3-s0 | V-T19-S0.06 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 7 | 0.889 |
| knn3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 3 | 0.867 |
| knn3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| knn3-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 1 | 2 | 0.667 |
| knn3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 3 | 0.733 |
| knn3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 1 | 0 | 0.752 |
| knn3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn3-s0 | V-T38-S0.22 | SELECTED_INFEASIBLE | c1=0.5,c2=1 | — | — | 3 | 0 | — |
| knn3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 311.0 | 635.8 | 1 | 4 | 0.455 |
| knn40-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn40-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn40-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| knn40-s0 | D-T14-S0.12 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | — |
| knn40-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| knn40-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.5,c2=0.6 | 184.5 | -184.5 | 0 | 2 | -1.000 |
| knn40-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 7 | 0.714 |
| knn40-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 3 | 1 | 0.722 |
| knn40-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 1 | 1 | 1.000 |
| knn40-s0 | D-T34-S0.12 | MISSED_OPPORTUNITY | — | — | — | 0 | 4 | — |
| knn40-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 1 | 0.867 |
| knn40-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 0 | 5 | 0.868 |
| knn40-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn40-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn40-s0 | V-T9-S0.40 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| knn40-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 0 | 9 | 0.619 |
| knn40-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 1 | 1 | 1.000 |
| knn40-s0 | V-T19-S0.40 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 1 | 1 | 1.000 |
| knn40-s0 | V-T29-S0.06 | SELECTED_INFEASIBLE | c1=1.75,c2=1 | — | — | 4 | 4 | 1.000 |
| knn40-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 8 | 0.733 |
| knn40-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 4 | 0 | 0.867 |
| knn40-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| knn40-s0 | V-T38-S0.22 | MISSED_OPPORTUNITY | — | — | — | 0 | 1 | — |
| knn40-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 2 | 7 | 0.778 |
| mlp-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| mlp-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.879 |
| mlp-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.974 |
| mlp-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.943 |
| mlp-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.949 |
| mlp-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.844 |
| mlp-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.886 |
| mlp-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.897 |
| mlp-s2 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp-s2 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp-s2 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp-s2 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp-s2 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| mlp-s2 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp-s2 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp-s2 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp-s2 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp-s2 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.912 |
| mlp-s2 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.931 |
| mlp-s2 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp-s2 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp-s2 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp-s2 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp-s2 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp-s2 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp-s2 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.943 |
| mlp-s2 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp-s2 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp-s2 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.897 |
| mlp_ens3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_ens3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_ens3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 0 | 0.978 |
| mlp_ens3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_ens3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_ens3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_ens3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_ens3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.913 |
| mlp_ens3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_ens3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_ens3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_ens3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_ens3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_ens3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_ens3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.867 |
| mlp_ens3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_ens3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_ens3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.949 |
| mlp_half-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_half-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_half-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_half-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_half-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_half-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.934 |
| mlp_half-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_half-s0 | D-T24-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 69.2 | 594.3 | 3 | 0 | 0.722 |
| mlp_half-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_half-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.882 |
| mlp_half-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 3 | 0.887 |
| mlp_half-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_half-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.872 |
| mlp_half-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_half-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_half-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_half-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.791 |
| mlp_half-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 1 | 0 | 0.924 |
| mlp_half-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_half-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.641 |
| mlp_half-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_half-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_half-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_half-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_half-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_half-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_half-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| mlp_half-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 2 | 0 | 0.889 |
| mlp_half-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_half-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.882 |
| mlp_half-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 3 | 0.844 |
| mlp_half-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_half-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_half-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.872 |
| mlp_half-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_half-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_half-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_half-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 1 | 0.843 |
| mlp_half-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.848 |
| mlp_half-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_half-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_half-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 2 | 0.821 |
| mlp_localized-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_localized-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_localized-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_localized-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 1 | 0.667 |
| mlp_localized-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_localized-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_localized-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_localized-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_localized-s0 | D-T34-S0.33 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 0 | 0.941 |
| mlp_localized-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.853 |
| mlp_localized-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_localized-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_localized-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_localized-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_localized-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_localized-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.974 |
| mlp_localized-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| mlp_localized-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_localized-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 0.718 |
| mlp_localized-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_localized-s1 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_localized-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_localized-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_localized-s1 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | D-T24-S0.33 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_localized-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_localized-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_localized-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.941 |
| mlp_localized-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.835 |
| mlp_localized-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_localized-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_localized-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_localized-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_localized-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_localized-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| mlp_localized-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_localized-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_localized-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.897 |
| mlp_plus-s0 | D-T5-S0.12 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_plus-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_plus-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_plus-s0 | D-T14-S0.12 | SELECTED_INFEASIBLE | c1=1,c2=0.8 | — | — | 2 | 0 | 0.667 |
| mlp_plus-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_plus-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_plus-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.912 |
| mlp_plus-s0 | D-T24-S0.33 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_plus-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp_plus-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_plus-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.926 |
| mlp_plus-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.827 |
| mlp_plus-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | V-T9-S0.22 | SELECTED_INFEASIBLE | c1=0.5,c2=0.6 | — | — | 1 | 0 | — |
| mlp_plus-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_plus-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 1 | 0 | 0.974 |
| mlp_plus-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_plus-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 0.667 |
| mlp_plus-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_plus-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.935 |
| mlp_plus-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.886 |
| mlp_plus-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_plus-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_plus-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 1 | 0 | 0.872 |
| mlp_raw-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_raw-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| mlp_raw-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_raw-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 1 | 0.333 |
| mlp_raw-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_raw-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_raw-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 0 | 0.778 |
| mlp_raw-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_raw-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.985 |
| mlp_raw-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 0 | 1 | 0.876 |
| mlp_raw-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_raw-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_raw-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_raw-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_raw-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 0.667 |
| mlp_raw-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_raw-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.987 |
| mlp_raw-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.886 |
| mlp_raw-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_raw-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_raw-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.897 |
| mlp_t1500_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w128_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.934 |
| mlp_t1500_w128_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t1500_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t1500_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t1500_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.922 |
| mlp_t1500_w128_d2-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t1500_w128_d2-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t1500_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t1500_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t1500_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 2 | 0 | 0.848 |
| mlp_t1500_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 1 | 1 | 0.949 |
| mlp_t1500_w128_d2_f25-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| mlp_t1500_w128_d2_f25-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 1 | 1.000 |
| mlp_t1500_w128_d2_f25-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.5,c2=0.6 | 184.5 | -184.5 | 0 | 0 | 0.333 |
| mlp_t1500_w128_d2_f25-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.912 |
| mlp_t1500_w128_d2_f25-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.911 |
| mlp_t1500_w128_d2_f25-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp_t1500_w128_d2_f25-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 2 | 0 | 1.000 |
| mlp_t1500_w128_d2_f25-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 1 | 0 | 0.868 |
| mlp_t1500_w128_d2_f25-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 3 | 0.870 |
| mlp_t1500_w128_d2_f25-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t1500_w128_d2_f25-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 0 | 3 | 0.818 |
| mlp_t1500_w128_d2_f25-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2_f25-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w128_d2_f25-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 1 | 0.800 |
| mlp_t1500_w128_d2_f25-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 1 | 2 | 0.935 |
| mlp_t1500_w128_d2_f25-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 1 | 0.943 |
| mlp_t1500_w128_d2_f25-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f25-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 2 | 0.795 |
| mlp_t1500_w128_d2_f50-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w128_d2_f50-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t1500_w128_d2_f50-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 1 | 0.897 |
| mlp_t1500_w128_d2_f50-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1,c2=1 | 37.5 | 1210.9 | 2 | 2 | 0.922 |
| mlp_t1500_w128_d2_f50-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t1500_w128_d2_f50-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w128_d2_f50-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t1500_w128_d2_f50-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t1500_w128_d2_f50-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.848 |
| mlp_t1500_w128_d2_f50-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w128_d2_f50-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 104.4 | 842.5 | 0 | 2 | 0.923 |
| mlp_t1500_w128_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w128_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| mlp_t1500_w128_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| mlp_t1500_w128_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t1500_w128_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 1 | 0.956 |
| mlp_t1500_w128_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 1 | 0.913 |
| mlp_t1500_w128_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t1500_w128_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t1500_w128_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t1500_w128_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp_t1500_w128_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.886 |
| mlp_t1500_w128_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w128_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.897 |
| mlp_t1500_w128_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s1 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s1 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w128_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 0 | 0.934 |
| mlp_t1500_w128_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t1500_w128_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 2 | 1 | 0.939 |
| mlp_t1500_w128_d3-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t1500_w128_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 0.667 |
| mlp_t1500_w128_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t1500_w128_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.935 |
| mlp_t1500_w128_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 2 | 0 | 0.924 |
| mlp_t1500_w128_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w128_d3-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.956 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 1 | 0.956 |
| mlp_t1500_w128_d3_wd1em4-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 1 | 0.913 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.872 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.886 |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w128_d3_wd1em4-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.897 |
| mlp_t1500_w256_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w256_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t1500_w256_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w256_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.890 |
| mlp_t1500_w256_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 0.956 |
| mlp_t1500_w256_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t1500_w256_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w256_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| mlp_t1500_w256_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 2 | 0.957 |
| mlp_t1500_w256_d2-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t1500_w256_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w256_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t1500_w256_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t1500_w256_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 2 | 0 | 0.829 |
| mlp_t1500_w256_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w256_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.949 |
| mlp_t1500_w256_d2_arr-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w256_d2_arr-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.912 |
| mlp_t1500_w256_d2_arr-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t1500_w256_d2_arr-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 0 | 0.957 |
| mlp_t1500_w256_d2_arr-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t1500_w256_d2_arr-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w256_d2_arr-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t1500_w256_d2_arr-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_t1500_w256_d2_arr-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.867 |
| mlp_t1500_w256_d2_arr-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w256_d2_arr-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.949 |
| mlp_t1500_w256_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w256_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t1500_w256_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w256_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w256_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.956 |
| mlp_t1500_w256_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t1500_w256_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t1500_w256_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w256_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.941 |
| mlp_t1500_w256_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 2 | 1 | 0.948 |
| mlp_t1500_w256_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t1500_w256_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t1500_w256_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w256_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w256_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t1500_w256_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_t1500_w256_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.867 |
| mlp_t1500_w256_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w256_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w256_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.949 |
| mlp_t1500_w512_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w512_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t1500_w512_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w512_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.956 |
| mlp_t1500_w512_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t1500_w512_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp_t1500_w512_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w512_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.912 |
| mlp_t1500_w512_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 0 | 0.922 |
| mlp_t1500_w512_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t1500_w512_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t1500_w512_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t1500_w512_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 0.667 |
| mlp_t1500_w512_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t1500_w512_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.882 |
| mlp_t1500_w512_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.829 |
| mlp_t1500_w512_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w512_d2-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 0.923 |
| mlp_t1500_w512_d2-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w512_d2-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t1500_w512_d2-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.890 |
| mlp_t1500_w512_d2-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t1500_w512_d2-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| mlp_t1500_w512_d2-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.957 |
| mlp_t1500_w512_d2-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t1500_w512_d2-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t1500_w512_d2-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w512_d2-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t1500_w512_d2-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t1500_w512_d2-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.829 |
| mlp_t1500_w512_d2-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d2-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w512_d2-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.949 |
| mlp_t1500_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w512_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w512_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t1500_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t1500_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t1500_w512_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t1500_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t1500_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t1500_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w512_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t1500_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.905 |
| mlp_t1500_w512_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t1500_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t1500_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t1500_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t1500_w512_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t1500_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t1500_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.848 |
| mlp_t1500_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t1500_w512_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 2 | 0.923 |
| mlp_t1500_w64_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w64_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t1500_w64_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t1500_w64_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t1500_w64_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.978 |
| mlp_t1500_w64_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t1500_w64_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 4 | 0 | 1.000 |
| mlp_t1500_w64_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t1500_w64_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t1500_w64_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 4 | 1 | 0.939 |
| mlp_t1500_w64_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t1500_w64_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w64_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 1 | 0.939 |
| mlp_t1500_w64_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w64_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t1500_w64_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t1500_w64_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.922 |
| mlp_t1500_w64_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.867 |
| mlp_t1500_w64_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t1500_w64_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 311.0 | 635.8 | 1 | 4 | 0.923 |
| mlp_t1500_w64_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t1500_w64_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t1500_w64_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| mlp_t1500_w64_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 0 | 0.978 |
| mlp_t1500_w64_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | D-T34-S0.33 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 0 | 0.941 |
| mlp_t1500_w64_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 0 | 0.931 |
| mlp_t1500_w64_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t1500_w64_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t1500_w64_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t1500_w64_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t1500_w64_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.924 |
| mlp_t1500_w64_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t1500_w64_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t1500_w64_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 1 | 0.974 |
| mlp_t3000_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t3000_w128_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t3000_w128_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_t3000_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.948 |
| mlp_t3000_w128_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t3000_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t3000_w128_d2-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t3000_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t3000_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t3000_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.886 |
| mlp_t3000_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.949 |
| mlp_t3000_w128_d2_ens3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 1 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| mlp_t3000_w128_d2_ens3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t3000_w128_d2_ens3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t3000_w128_d2_ens3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 2 | 1 | 0.913 |
| mlp_t3000_w128_d2_ens3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t3000_w128_d2_ens3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t3000_w128_d2_ens3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t3000_w128_d2_ens3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t3000_w128_d2_ens3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp_t3000_w128_d2_ens3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.867 |
| mlp_t3000_w128_d2_ens3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t3000_w128_d2_ens3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| mlp_t3000_w128_d2_irw01-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t3000_w128_d2_irw01-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_irw01-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_irw01-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t3000_w128_d2_irw01-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w128_d2_irw01-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w128_d2_irw01-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w128_d2_irw01-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.956 |
| mlp_t3000_w128_d2_irw01-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 2 | 0.931 |
| mlp_t3000_w128_d2_irw01-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_irw01-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t3000_w128_d2_irw01-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d2_irw01-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t3000_w128_d2_irw01-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t3000_w128_d2_irw01-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t3000_w128_d2_irw01-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 2 | 0 | 0.867 |
| mlp_t3000_w128_d2_irw01-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w128_d2_irw01-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.897 |
| mlp_t3000_w128_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w128_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t3000_w128_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_t3000_w128_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w128_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.971 |
| mlp_t3000_w128_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 1 | 0.939 |
| mlp_t3000_w128_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t3000_w128_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_t3000_w128_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t3000_w128_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp_t3000_w128_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| mlp_t3000_w128_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w128_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w128_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.923 |
| mlp_t3000_w256_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t3000_w256_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w256_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t3000_w256_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w256_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t3000_w256_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 2 | 0.913 |
| mlp_t3000_w256_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t3000_w256_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t3000_w256_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t3000_w256_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 0.667 |
| mlp_t3000_w256_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t3000_w256_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.922 |
| mlp_t3000_w256_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.810 |
| mlp_t3000_w256_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w256_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| mlp_t3000_w256_d2-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d2-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d2-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.5,c2=0.6 | 184.5 | -184.5 | 0 | 0 | 0.667 |
| mlp_t3000_w256_d2-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.934 |
| mlp_t3000_w256_d2-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w256_d2-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w256_d2-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t3000_w256_d2-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 1 | 2 | 0.922 |
| mlp_t3000_w256_d2-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t3000_w256_d2-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t3000_w256_d2-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d2-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t3000_w256_d2-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t3000_w256_d2-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp_t3000_w256_d2-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.848 |
| mlp_t3000_w256_d2-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d2-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w256_d2-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.897 |
| mlp_t3000_w256_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 1 | 0.667 |
| mlp_t3000_w256_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.934 |
| mlp_t3000_w256_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w256_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w256_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.971 |
| mlp_t3000_w256_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.922 |
| mlp_t3000_w256_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t3000_w256_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t3000_w256_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.886 |
| mlp_t3000_w256_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w256_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 2 | 0 | 0.667 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.912 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=1 | 100.3 | 1162.7 | 1 | 0 | 0.956 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 2 | 0 | 0.833 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| mlp_t3000_w256_d3_arr_pca16-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 2 | 0 | 0.844 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T9-S0.22 | SELECTED_INFEASIBLE | c1=0.5,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 1 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 1 | 1 | 0.974 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 0.667 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.908 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.829 |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w256_d3_arr_pca16-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 0 | 0.821 |
| mlp_t3000_w256_d3_f25-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | -0.333 |
| mlp_t3000_w256_d3_f25-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 1 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| mlp_t3000_w256_d3_f25-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=0.75,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp_t3000_w256_d3_f25-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 2 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.882 |
| mlp_t3000_w256_d3_f25-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 3 | 0.896 |
| mlp_t3000_w256_d3_f25-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 381.6 | — | 0 | 4 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t3000_w256_d3_f25-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 1 | 0 | 0.908 |
| mlp_t3000_w256_d3_f25-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.886 |
| mlp_t3000_w256_d3_f25-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 2 | 0 | — |
| mlp_t3000_w256_d3_f25-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.795 |
| mlp_t3000_w256_d3_f25-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 2 | 1 | 0.333 |
| mlp_t3000_w256_d3_f25-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t3000_w256_d3_f25-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_t3000_w256_d3_f25-s1 | D-T24-S0.33 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 1 | 0 | 0.911 |
| mlp_t3000_w256_d3_f25-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.667 |
| mlp_t3000_w256_d3_f25-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.882 |
| mlp_t3000_w256_d3_f25-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 3 | 0.827 |
| mlp_t3000_w256_d3_f25-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t3000_w256_d3_f25-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 1 | 0 | 0.974 |
| mlp_t3000_w256_d3_f25-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s1 | V-T19-S0.40 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 3 | 1 | 1.000 |
| mlp_t3000_w256_d3_f25-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f25-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 41.9 | 1725.7 | 0 | 1 | 0.895 |
| mlp_t3000_w256_d3_f25-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 2 | 0 | 0.790 |
| mlp_t3000_w256_d3_f25-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 2 | 0 | — |
| mlp_t3000_w256_d3_f25-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 2 | 4 | 0.923 |
| mlp_t3000_w256_d3_f50-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t3000_w256_d3_f50-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t3000_w256_d3_f50-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t3000_w256_d3_f50-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.890 |
| mlp_t3000_w256_d3_f50-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f50-s0 | D-T24-S0.48 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 663.5 | 4 | 0 | 0.889 |
| mlp_t3000_w256_d3_f50-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w256_d3_f50-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.897 |
| mlp_t3000_w256_d3_f50-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 3 | 0.870 |
| mlp_t3000_w256_d3_f50-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f50-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.872 |
| mlp_t3000_w256_d3_f50-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w256_d3_f50-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_t3000_w256_d3_f50-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t3000_w256_d3_f50-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.791 |
| mlp_t3000_w256_d3_f50-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 1 | 0 | 0.886 |
| mlp_t3000_w256_d3_f50-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w256_d3_f50-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.667 |
| mlp_t3000_w512_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w512_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t3000_w512_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t3000_w512_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w512_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w512_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w512_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.926 |
| mlp_t3000_w512_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 0 | 0.896 |
| mlp_t3000_w512_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t3000_w512_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t3000_w512_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t3000_w512_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_t3000_w512_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t3000_w512_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.895 |
| mlp_t3000_w512_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.810 |
| mlp_t3000_w512_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w512_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.923 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.926 |
| mlp_t3000_w512_d2_wd1em4-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 0 | 0.896 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.895 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.810 |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w512_d2_wd1em4-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.923 |
| mlp_t3000_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w512_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t3000_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t3000_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w512_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_t3000_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=1 | 100.3 | 1162.7 | 0 | 0 | 0.956 |
| mlp_t3000_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t3000_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w512_d3-s0 | D-T34-S0.33 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 0 | 0 | 0.941 |
| mlp_t3000_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.896 |
| mlp_t3000_w512_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t3000_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t3000_w512_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t3000_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.987 |
| mlp_t3000_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.886 |
| mlp_t3000_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t3000_w512_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.897 |
| mlp_t3000_w512_d3_f25-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | 0.333 |
| mlp_t3000_w512_d3_f25-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t3000_w512_d3_f25-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 1 | 1.000 |
| mlp_t3000_w512_d3_f25-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 0 | 0.912 |
| mlp_t3000_w512_d3_f25-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.867 |
| mlp_t3000_w512_d3_f25-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t3000_w512_d3_f25-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t3000_w512_d3_f25-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.824 |
| mlp_t3000_w512_d3_f25-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 2 | 0.905 |
| mlp_t3000_w512_d3_f25-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w512_d3_f25-s0 | V-T19-S0.06 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 1 | 4 | 0.939 |
| mlp_t3000_w512_d3_f25-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 1 | 0 | 1.000 |
| mlp_t3000_w512_d3_f25-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t3000_w512_d3_f25-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| mlp_t3000_w512_d3_f25-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 1 | 0 | 0.882 |
| mlp_t3000_w512_d3_f25-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.886 |
| mlp_t3000_w512_d3_f25-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w512_d3_f25-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 1 | 0.641 |
| mlp_t3000_w64_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d2-s0 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w64_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w64_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_t3000_w64_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t3000_w64_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_t3000_w64_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 4 | 0 | 0.948 |
| mlp_t3000_w64_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t3000_w64_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t3000_w64_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 0.667 |
| mlp_t3000_w64_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w64_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.935 |
| mlp_t3000_w64_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.905 |
| mlp_t3000_w64_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t3000_w64_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.897 |
| mlp_t3000_w64_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t3000_w64_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t3000_w64_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w64_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t3000_w64_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t3000_w64_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 1 | 0.913 |
| mlp_t3000_w64_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t3000_w64_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t3000_w64_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t3000_w64_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t3000_w64_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 2 | 0 | 0.943 |
| mlp_t3000_w64_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w64_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.949 |
| mlp_t3000_w64_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s1 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t3000_w64_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t3000_w64_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t3000_w64_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_t3000_w64_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 1 | 0.931 |
| mlp_t3000_w64_d3-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 3 | 0 | — |
| mlp_t3000_w64_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t3000_w64_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t3000_w64_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t3000_w64_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_t3000_w64_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.943 |
| mlp_t3000_w64_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t3000_w64_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t3000_w64_d3-s1 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.897 |
| mlp_t500_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w128_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | 0.333 |
| mlp_t500_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w128_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.824 |
| mlp_t500_w128_d2-s0 | D-T24-S0.33 | SELECTED_INFEASIBLE | c1=1.5,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_t500_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t500_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| mlp_t500_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t500_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 2 | 0.957 |
| mlp_t500_w128_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 3 | 0 | — |
| mlp_t500_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t500_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 1 | 0.818 |
| mlp_t500_w128_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t500_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| mlp_t500_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 41.9 | 1725.7 | 0 | 1 | 0.882 |
| mlp_t500_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.886 |
| mlp_t500_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 3 | 0.974 |
| mlp_t500_w128_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w128_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w128_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | 0.333 |
| mlp_t500_w128_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 0.333 |
| mlp_t500_w128_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t500_w128_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 0 | 0.956 |
| mlp_t500_w128_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t500_w128_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 4 | 0 | 1.000 |
| mlp_t500_w128_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| mlp_t500_w128_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 1 | 0.912 |
| mlp_t500_w128_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 2 | 0.965 |
| mlp_t500_w128_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t500_w128_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t500_w128_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 1 | 0.848 |
| mlp_t500_w128_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 0.867 |
| mlp_t500_w128_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 0.667 |
| mlp_t500_w128_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t500_w128_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 1 | 0.922 |
| mlp_t500_w128_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.905 |
| mlp_t500_w128_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w128_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 3 | 0.923 |
| mlp_t500_w128_d3_f50-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 0.333 |
| mlp_t500_w128_d3_f50-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w128_d3_f50-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t500_w128_d3_f50-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 4 | 0 | 0.956 |
| mlp_t500_w128_d3_f50-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t500_w128_d3_f50-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t500_w128_d3_f50-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| mlp_t500_w128_d3_f50-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 1 | 0.912 |
| mlp_t500_w128_d3_f50-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 1 | 0.957 |
| mlp_t500_w128_d3_f50-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t500_w128_d3_f50-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 0 | 2 | 0.879 |
| mlp_t500_w128_d3_f50-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w128_d3_f50-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 0.667 |
| mlp_t500_w128_d3_f50-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t500_w128_d3_f50-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 1 | 0 | 0.882 |
| mlp_t500_w128_d3_f50-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.886 |
| mlp_t500_w128_d3_f50-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w128_d3_f50-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 3 | 0.872 |
| mlp_t500_w256_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w256_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w256_d2-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 0.333 |
| mlp_t500_w256_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w256_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w256_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| mlp_t500_w256_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t500_w256_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 4 | 0 | 0.944 |
| mlp_t500_w256_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t500_w256_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| mlp_t500_w256_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 2 | 2 | 0.922 |
| mlp_t500_w256_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 3 | 0 | — |
| mlp_t500_w256_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t500_w256_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 1 | 0.939 |
| mlp_t500_w256_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w256_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t500_w256_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| mlp_t500_w256_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.974 |
| mlp_t500_w256_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.867 |
| mlp_t500_w256_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w256_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 3 | 0.923 |
| mlp_t500_w256_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w256_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 0.333 |
| mlp_t500_w256_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t500_w256_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t500_w256_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t500_w256_d3-s0 | D-T34-S0.33 | SELECTED_UNRESOLVED | c1=2,c2=1 | — | — | 1 | 0 | 0.912 |
| mlp_t500_w256_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 2 | 0.922 |
| mlp_t500_w256_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t500_w256_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t500_w256_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.974 |
| mlp_t500_w256_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 0.667 |
| mlp_t500_w256_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t500_w256_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.935 |
| mlp_t500_w256_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.981 |
| mlp_t500_w256_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t500_w256_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 2 | 0.949 |
| mlp_t500_w256_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w256_d3-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t500_w256_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t500_w256_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 2 | 0.948 |
| mlp_t500_w256_d3-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.821 |
| mlp_t500_w256_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w256_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 0.667 |
| mlp_t500_w256_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t500_w256_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t500_w256_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.848 |
| mlp_t500_w256_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w256_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t500_w256_d3-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 3 | 1.000 |
| mlp_t500_w512_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w512_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w512_d2-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 1.000 |
| mlp_t500_w512_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w512_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t500_w512_d2-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.934 |
| mlp_t500_w512_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t500_w512_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 4 | 0 | 0.944 |
| mlp_t500_w512_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t500_w512_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| mlp_t500_w512_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 2 | 0.922 |
| mlp_t500_w512_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 3 | 0 | — |
| mlp_t500_w512_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t500_w512_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t500_w512_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w512_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 0.667 |
| mlp_t500_w512_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t500_w512_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.922 |
| mlp_t500_w512_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.886 |
| mlp_t500_w512_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t500_w512_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 3 | 0.949 |
| mlp_t500_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w512_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 0 | 0.956 |
| mlp_t500_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t500_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t500_w512_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t500_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 2 | 0.922 |
| mlp_t500_w512_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t500_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t500_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t500_w512_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t500_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.935 |
| mlp_t500_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 1 | 0 | 0.905 |
| mlp_t500_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t500_w512_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 1 | 0.949 |
| mlp_t500_w64_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w64_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 2 | 1.000 |
| mlp_t500_w64_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w64_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w64_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 3 | 1 | 0.821 |
| mlp_t500_w64_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t500_w64_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 2 | 0 | 0.833 |
| mlp_t500_w64_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 2 | 1.000 |
| mlp_t500_w64_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 1 | 0.912 |
| mlp_t500_w64_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 3 | 0.922 |
| mlp_t500_w64_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t500_w64_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 1 | — |
| mlp_t500_w64_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 2 | 0.855 |
| mlp_t500_w64_d2-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 0.867 |
| mlp_t500_w64_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t500_w64_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| mlp_t500_w64_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 1 | 0.791 |
| mlp_t500_w64_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.905 |
| mlp_t500_w64_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w64_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 7 | 0.872 |
| mlp_t500_w64_d2-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s1 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 2 | 1.000 |
| mlp_t500_w64_d2-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w64_d2-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w64_d2-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 2 | 0.846 |
| mlp_t500_w64_d2-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t500_w64_d2-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 2 | 0 | 0.667 |
| mlp_t500_w64_d2-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| mlp_t500_w64_d2-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 53.3 | 1512.0 | 0 | 2 | 0.912 |
| mlp_t500_w64_d2-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 1 | 3 | 0.948 |
| mlp_t500_w64_d2-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t500_w64_d2-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s1 | V-T9-S0.40 | MISSED_OPPORTUNITY | — | — | — | 0 | 2 | — |
| mlp_t500_w64_d2-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 2 | 0.818 |
| mlp_t500_w64_d2-s1 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 0.867 |
| mlp_t500_w64_d2-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t500_w64_d2-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 1 | 0.800 |
| mlp_t500_w64_d2-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 1 | 0.838 |
| mlp_t500_w64_d2-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.867 |
| mlp_t500_w64_d2-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d2-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w64_d2-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 732.1 | 214.8 | 0 | 4 | 0.897 |
| mlp_t500_w64_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t500_w64_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t500_w64_d3-s0 | D-T14-S0.12 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 0.333 |
| mlp_t500_w64_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 85.8 | 0.0 | 0 | 1 | 1.000 |
| mlp_t500_w64_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t500_w64_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 2 | 0 | 0.824 |
| mlp_t500_w64_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 1 | 0 | 1.000 |
| mlp_t500_w64_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 4 | 0 | 0.944 |
| mlp_t500_w64_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 0 | 1 | 1.000 |
| mlp_t500_w64_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 1 | 0.956 |
| mlp_t500_w64_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 3 | 0.983 |
| mlp_t500_w64_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 3 | 0 | — |
| mlp_t500_w64_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t500_w64_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 2 | 0.745 |
| mlp_t500_w64_d3-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 0.867 |
| mlp_t500_w64_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t500_w64_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t500_w64_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 1 | 0.895 |
| mlp_t500_w64_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| mlp_t500_w64_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t500_w64_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t500_w64_d3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 311.0 | 635.8 | 0 | 4 | 0.897 |
| mlp_t6000_w128_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d2-s0 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w128_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w128_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t6000_w128_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_t6000_w128_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 0 | 0.939 |
| mlp_t6000_w128_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t6000_w128_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w128_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w128_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w128_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t6000_w128_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 1 | 0 | 0.848 |
| mlp_t6000_w128_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w128_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.974 |
| mlp_t6000_w128_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w128_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 0 | 0.956 |
| mlp_t6000_w128_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=0.75,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t6000_w128_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.971 |
| mlp_t6000_w128_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 0 | 0.948 |
| mlp_t6000_w128_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w128_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w128_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t6000_w128_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t6000_w128_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.924 |
| mlp_t6000_w128_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w128_d3-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.949 |
| mlp_t6000_w128_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s1 | D-T5-S0.33 | SELECTED_UNRESOLVED | c1=0.75,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s1 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w128_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w128_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 1.000 |
| mlp_t6000_w128_d3-s1 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t6000_w128_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w128_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 4 | 0 | 0.778 |
| mlp_t6000_w128_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w128_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t6000_w128_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.879 |
| mlp_t6000_w128_d3-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t6000_w128_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t6000_w128_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w128_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w128_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w128_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.974 |
| mlp_t6000_w128_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.924 |
| mlp_t6000_w128_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w128_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w128_d3-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.974 |
| mlp_t6000_w256_d2-s0 | D-T5-S0.12 | SELECTED_INFEASIBLE | c1=0.5,c2=0.2 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d2-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t6000_w256_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t6000_w256_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t6000_w256_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 2 | 0.939 |
| mlp_t6000_w256_d2-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=0.5,c2=0.2 | — | — | 4 | 0 | — |
| mlp_t6000_w256_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.872 |
| mlp_t6000_w256_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t6000_w256_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w256_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| mlp_t6000_w256_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.905 |
| mlp_t6000_w256_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.949 |
| mlp_t6000_w256_d3_arr-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_arr-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_arr-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t6000_w256_d3_arr-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t6000_w256_d3_arr-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_arr-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t6000_w256_d3_arr-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_arr-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.971 |
| mlp_t6000_w256_d3_arr-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.939 |
| mlp_t6000_w256_d3_arr-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.5,c2=0.6 | — | — | 3 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_arr-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t6000_w256_d3_arr-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_arr-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_arr-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w256_d3_arr-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_t6000_w256_d3_arr-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.848 |
| mlp_t6000_w256_d3_arr-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_arr-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_ens2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w256_d3_ens2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_ens2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_ens2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.971 |
| mlp_t6000_w256_d3_ens2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.931 |
| mlp_t6000_w256_d3_ens2-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_ens2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_t6000_w256_d3_ens2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.886 |
| mlp_t6000_w256_d3_ens2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_ens2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_ens4-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 0 | 0.956 |
| mlp_t6000_w256_d3_ens4-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_ens4-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 2 | 0 | 0.965 |
| mlp_t6000_w256_d3_ens4-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t6000_w256_d3_ens4-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_ens4-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t6000_w256_d3_ens4-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.935 |
| mlp_t6000_w256_d3_ens4-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.848 |
| mlp_t6000_w256_d3_ens4-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_ens4-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_f25-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | 0.333 |
| mlp_t6000_w256_d3_f25-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 1 | 1.000 |
| mlp_t6000_w256_d3_f25-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_f25-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.978 |
| mlp_t6000_w256_d3_f25-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=1 | 100.3 | 1162.7 | 0 | 0 | 0.911 |
| mlp_t6000_w256_d3_f25-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=0.75,c2=1 | — | — | 3 | 0 | 0.722 |
| mlp_t6000_w256_d3_f25-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 2 | 0 | 1.000 |
| mlp_t6000_w256_d3_f25-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.912 |
| mlp_t6000_w256_d3_f25-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 3 | 3 | 0.844 |
| mlp_t6000_w256_d3_f25-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_f25-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=0.8 | 381.6 | — | 0 | 4 | 0.927 |
| mlp_t6000_w256_d3_f25-s0 | V-T19-S0.22 | SELECTED_FEASIBLE | c1=1.25,c2=0.8 | 0.0 | 1015.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_f25-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_t6000_w256_d3_f25-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.733 |
| mlp_t6000_w256_d3_f25-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 1 | 0 | 0.882 |
| mlp_t6000_w256_d3_f25-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.886 |
| mlp_t6000_w256_d3_f25-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 2 | 0 | — |
| mlp_t6000_w256_d3_f25-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 1 | 1 | 0.744 |
| mlp_t6000_w256_d3_irw003-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 1 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t6000_w256_d3_irw003-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.941 |
| mlp_t6000_w256_d3_irw003-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 1 | 0.922 |
| mlp_t6000_w256_d3_irw003-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t6000_w256_d3_irw003-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw003-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 0.867 |
| mlp_t6000_w256_d3_irw003-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.961 |
| mlp_t6000_w256_d3_irw003-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.962 |
| mlp_t6000_w256_d3_irw003-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw003-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.872 |
| mlp_t6000_w256_d3_irw03-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_irw03-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_irw03-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t6000_w256_d3_irw03-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 1 | 0 | 0.971 |
| mlp_t6000_w256_d3_irw03-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 0 | 0.905 |
| mlp_t6000_w256_d3_irw03-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t6000_w256_d3_irw03-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w256_d3_irw03-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t6000_w256_d3_irw03-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.867 |
| mlp_t6000_w256_d3_irw03-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw03-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.872 |
| mlp_t6000_w256_d3_irw03-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_irw03-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t6000_w256_d3_irw03-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.941 |
| mlp_t6000_w256_d3_irw03-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.922 |
| mlp_t6000_w256_d3_irw03-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw03-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t6000_w256_d3_irw03-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.924 |
| mlp_t6000_w256_d3_irw03-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw03-s1 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_irw3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.75,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| mlp_t6000_w256_d3_irw3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 2 | 0 | 0.978 |
| mlp_t6000_w256_d3_irw3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_irw3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t6000_w256_d3_irw3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.897 |
| mlp_t6000_w256_d3_irw3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.887 |
| mlp_t6000_w256_d3_irw3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_irw3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t6000_w256_d3_irw3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w256_d3_irw3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.948 |
| mlp_t6000_w256_d3_irw3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.962 |
| mlp_t6000_w256_d3_irw3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_irw3-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.846 |
| mlp_t6000_w256_d3_pca8-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | 0.333 |
| mlp_t6000_w256_d3_pca8-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.912 |
| mlp_t6000_w256_d3_pca8-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 4 | 0 | 0.944 |
| mlp_t6000_w256_d3_pca8-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 1 | 0 | 0.926 |
| mlp_t6000_w256_d3_pca8-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 2 | 0 | 0.913 |
| mlp_t6000_w256_d3_pca8-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 52.0 | — | 0 | 1 | 0.897 |
| mlp_t6000_w256_d3_pca8-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_pca8-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w256_d3_pca8-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.908 |
| mlp_t6000_w256_d3_pca8-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.981 |
| mlp_t6000_w256_d3_pca8-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t6000_w256_d3_pca8-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t6000_w256_d3_wd1em3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.879 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.974 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.943 |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.923 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t6000_w256_d3_wd1em3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.844 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.886 |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_wd1em3-s1 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.897 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t6000_w256_d3_wd1em5-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 0 | 0.879 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.897 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.974 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.943 |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w256_d3_wd1em5-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.949 |
| mlp_t6000_w512_d2_f25-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | D-T5-S0.48 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 1 | 0.333 |
| mlp_t6000_w512_d2_f25-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 1 | 1.000 |
| mlp_t6000_w512_d2_f25-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 1 | 0.667 |
| mlp_t6000_w512_d2_f25-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.780 |
| mlp_t6000_w512_d2_f25-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=1 | 100.3 | 1162.7 | 0 | 1 | 0.911 |
| mlp_t6000_w512_d2_f25-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.611 |
| mlp_t6000_w512_d2_f25-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 3 | 0 | 1.000 |
| mlp_t6000_w512_d2_f25-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 53.3 | 1512.0 | 1 | 0 | 0.809 |
| mlp_t6000_w512_d2_f25-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 2 | 0.870 |
| mlp_t6000_w512_d2_f25-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 1 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d2_f25-s0 | V-T19-S0.06 | SELECTED_UNRESOLVED | c1=1.5,c2=1 | — | — | 0 | 4 | 0.782 |
| mlp_t6000_w512_d2_f25-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d2_f25-s0 | V-T19-S0.40 | SELECTED_UNRESOLVED | c1=0.75,c2=0.8 | — | — | 3 | 0 | 1.000 |
| mlp_t6000_w512_d2_f25-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.333 |
| mlp_t6000_w512_d2_f25-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 1 | 1 | 0.922 |
| mlp_t6000_w512_d2_f25-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 1 | 1 | 0.924 |
| mlp_t6000_w512_d2_f25-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 2 | 0 | — |
| mlp_t6000_w512_d2_f25-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 2 | 2 | 0.744 |
| mlp_t6000_w512_d2_f50-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w512_d2_f50-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w512_d2_f50-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t6000_w512_d2_f50-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 1 | 0 | 0.890 |
| mlp_t6000_w512_d2_f50-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=1 | 100.3 | 1162.7 | 0 | 0 | 0.956 |
| mlp_t6000_w512_d2_f50-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t6000_w512_d2_f50-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w512_d2_f50-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.882 |
| mlp_t6000_w512_d2_f50-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 14.5 | 1234.0 | 3 | 2 | 0.913 |
| mlp_t6000_w512_d2_f50-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | V-T9-S0.40 | SELECTED_INFEASIBLE | c1=0.75,c2=0.6 | — | — | 1 | 0 | 1.000 |
| mlp_t6000_w512_d2_f50-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.821 |
| mlp_t6000_w512_d2_f50-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d2_f50-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 1.000 |
| mlp_t6000_w512_d2_f50-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w512_d2_f50-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.830 |
| mlp_t6000_w512_d2_f50-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 3 | 0 | 0.810 |
| mlp_t6000_w512_d2_f50-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w512_d2_f50-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.75,c2=0.8 | 47.8 | 899.1 | 0 | 1 | 0.795 |
| mlp_t6000_w512_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w512_d3-s0 | D-T5-S0.48 | SELECTED_INFEASIBLE | c1=0.5,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t6000_w512_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w512_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1,c2=1 | 100.3 | 1162.7 | 0 | 0 | 0.956 |
| mlp_t6000_w512_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.778 |
| mlp_t6000_w512_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | 1565.3 | 0 | 0 | 0.897 |
| mlp_t6000_w512_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 0 | 0.922 |
| mlp_t6000_w512_d3-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t6000_w512_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w512_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.5,c2=0.8 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w512_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | 1767.6 | 0 | 0 | 0.974 |
| mlp_t6000_w512_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1,c2=1 | 72.5 | 1220.9 | 0 | 0 | 0.905 |
| mlp_t6000_w512_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w512_d3-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 2 | 0.744 |
| mlp_t6000_w512_d3-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s1 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w512_d3-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | D-T14-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=0.6 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w512_d3-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t6000_w512_d3-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 2 | 0 | 0.922 |
| mlp_t6000_w512_d3-s1 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.974 |
| mlp_t6000_w512_d3-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 1 | 0 | 1.000 |
| mlp_t6000_w512_d3-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w512_d3-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.961 |
| mlp_t6000_w512_d3-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.924 |
| mlp_t6000_w512_d3-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w512_d3-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w512_d3-s1 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.923 |
| mlp_t6000_w64_d2-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.25,c2=0.6 | 39.5 | 522.5 | 0 | 0 | 0.667 |
| mlp_t6000_w64_d2-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t6000_w64_d2-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.956 |
| mlp_t6000_w64_d2-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_t6000_w64_d2-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w64_d2-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.926 |
| mlp_t6000_w64_d2-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1248.4 | 4 | 0 | 0.939 |
| mlp_t6000_w64_d2-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_t6000_w64_d2-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w64_d2-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 3 | 0 | 0.667 |
| mlp_t6000_w64_d2-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w64_d2-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.895 |
| mlp_t6000_w64_d2-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.905 |
| mlp_t6000_w64_d2-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 72.4 | 874.4 | 0 | 1 | 0.974 |
| mlp_t6000_w64_d2-s1 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s1 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s1 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_t6000_w64_d2-s1 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s1 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s1 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 0.667 |
| mlp_t6000_w64_d2-s1 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 3 | 0 | 0.978 |
| mlp_t6000_w64_d2-s1 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s1 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 3 | 0 | 0.889 |
| mlp_t6000_w64_d2-s1 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 1 | 1.000 |
| mlp_t6000_w64_d2-s1 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.956 |
| mlp_t6000_w64_d2-s1 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=2,c2=1 | 19.4 | 1229.1 | 3 | 0 | 0.913 |
| mlp_t6000_w64_d2-s1 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=1.25,c2=0.6 | — | — | 2 | 0 | — |
| mlp_t6000_w64_d2-s1 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s1 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s1 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.949 |
| mlp_t6000_w64_d2-s1 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w64_d2-s1 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t6000_w64_d2-s1 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.733 |
| mlp_t6000_w64_d2-s1 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.922 |
| mlp_t6000_w64_d2-s1 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 0 | 0 | 0.943 |
| mlp_t6000_w64_d2-s1 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d2-s1 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w64_d2-s1 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 1 | 0.974 |
| mlp_t6000_w64_d3-s0 | D-T5-S0.12 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d3-s0 | D-T5-S0.33 | ABSTENTION_UNRESOLVED | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d3-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_t6000_w64_d3-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d3-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 1 | 1.000 |
| mlp_t6000_w64_d3-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_t6000_w64_d3-s0 | D-T24-S0.12 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 0.0 | — | 0 | 0 | 0.978 |
| mlp_t6000_w64_d3-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_t6000_w64_d3-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.833 |
| mlp_t6000_w64_d3-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_t6000_w64_d3-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 0 | 0 | 0.941 |
| mlp_t6000_w64_d3-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 2 | 1 | 0.879 |
| mlp_t6000_w64_d3-s0 | V-T9-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d3-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d3-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.75,c2=0.4 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_t6000_w64_d3-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.923 |
| mlp_t6000_w64_d3-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_t6000_w64_d3-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_t6000_w64_d3-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 1 | 0 | 0.867 |
| mlp_t6000_w64_d3-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.974 |
| mlp_t6000_w64_d3-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 1.8 | 1291.6 | 2 | 0 | 0.924 |
| mlp_t6000_w64_d3-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_t6000_w64_d3-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_t6000_w64_d3-s0 | V-T38-S0.40 | SELECTED_UNRESOLVED | c1=1.25,c2=0.8 | — | — | 0 | 0 | 0.949 |
| mlp_wide-s0 | D-T5-S0.12 | SELECTED_INFEASIBLE | c1=0.5,c2=0.2 | — | — | 1 | 0 | — |
| mlp_wide-s0 | D-T5-S0.33 | SELECTED_INFEASIBLE | c1=0.5,c2=0.4 | — | — | 1 | 0 | — |
| mlp_wide-s0 | D-T5-S0.48 | SELECTED_UNRESOLVED | c1=0.5,c2=0.4 | — | — | 0 | 0 | — |
| mlp_wide-s0 | D-T14-S0.12 | SELECTED_FEASIBLE | c1=1.5,c2=0.6 | 0.0 | 562.0 | 0 | 0 | 1.000 |
| mlp_wide-s0 | D-T14-S0.33 | SELECTED_FEASIBLE | c1=1,c2=0.6 | 0.0 | 85.8 | 1 | 0 | 1.000 |
| mlp_wide-s0 | D-T14-S0.48 | SELECTED_FEASIBLE | c1=0.75,c2=0.6 | 0.0 | 0.0 | 0 | 0 | 1.000 |
| mlp_wide-s0 | D-T24-S0.12 | SELECTED_INFEASIBLE | c1=2,c2=1 | — | — | 1 | 0 | 0.978 |
| mlp_wide-s0 | D-T24-S0.33 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | 1262.9 | 0 | 0 | 0.956 |
| mlp_wide-s0 | D-T24-S0.48 | SELECTED_UNRESOLVED | c1=1,c2=1 | — | — | 3 | 0 | 0.944 |
| mlp_wide-s0 | D-T34-S0.12 | SELECTED_FEASIBLE | c1=1,c2=1 | 0.0 | — | 1 | 0 | 1.000 |
| mlp_wide-s0 | D-T34-S0.33 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 1.1 | 1564.2 | 1 | 0 | 0.897 |
| mlp_wide-s0 | D-T34-S0.48 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 6.1 | 1242.4 | 3 | 0 | 0.896 |
| mlp_wide-s0 | V-T9-S0.06 | SELECTED_INFEASIBLE | c1=0.5,c2=0.2 | — | — | 2 | 0 | — |
| mlp_wide-s0 | V-T9-S0.22 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_wide-s0 | V-T9-S0.40 | SELECTED_FEASIBLE | c1=0.5,c2=0.4 | 80.4 | — | 0 | 0 | -1.000 |
| mlp_wide-s0 | V-T19-S0.06 | SELECTED_FEASIBLE | c1=2,c2=1 | 0.0 | — | 0 | 0 | 0.974 |
| mlp_wide-s0 | V-T19-S0.22 | SELECTED_UNRESOLVED | c1=1.25,c2=1 | — | — | 0 | 0 | 1.000 |
| mlp_wide-s0 | V-T19-S0.40 | SELECTED_FEASIBLE | c1=1,c2=0.8 | 0.0 | 676.2 | 2 | 0 | 1.000 |
| mlp_wide-s0 | V-T29-S0.06 | SELECTED_FEASIBLE | c1=1.25,c2=1 | 0.0 | — | 0 | 0 | 1.000 |
| mlp_wide-s0 | V-T29-S0.22 | SELECTED_FEASIBLE | c1=1.75,c2=1 | 2.8 | 1764.8 | 0 | 0 | 0.948 |
| mlp_wide-s0 | V-T29-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=1 | 0.0 | 1293.4 | 0 | 0 | 0.867 |
| mlp_wide-s0 | V-T38-S0.06 | CORRECT_ABSTENTION | — | — | — | 0 | 0 | — |
| mlp_wide-s0 | V-T38-S0.22 | SELECTED_FEASIBLE | c1=0.75,c2=0.8 | 0.0 | — | 1 | 0 | — |
| mlp_wide-s0 | V-T38-S0.40 | SELECTED_FEASIBLE | c1=1.5,c2=0.8 | 0.0 | 946.8 | 0 | 0 | 0.897 |

## Limitations

- Charging speed is time to constant-voltage onset (the 4.19 V crossing), not time to a target state of charge. The reference keeps no SOC or current trajectory.
- The physics leg is not measurable for battery, so profiles that weight it are reported, not computed.
- The scoring set omits hidden duplicates, so the paired-repeat gate is not exercised.
- Reconstruction seeds are repetitions of a recipe, not independent models; the bootstrap treats members as exchangeable.
