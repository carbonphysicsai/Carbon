# Problem C: one fast-charge protocol for 15-35 °C

Public synthetic DEVELOPMENT evidence. Each model chose one two-step protocol from its own predictions at the 20 in-band conditions; the reference verified it at 90 conditions over 5-40 °C. The claim is the in-band result (15-35 °C); out-of-band points describe where the design breaks and never count against it. Not a global optimum, not a qualification.

## Primary: in band (15-35 °C)

| Role | Member | Design | Feasible at every in-band point | Violations (reach / plating / temp) | Worst t_CV (s) | Mean t_CV (s) | Worst saved vs baseline (s) |
|---|---|---|---|---|---|---|---|
| baseline | — | c1=0.75,c2=0.6 | False | 15 / 0 / 0 | — | — | — |
| best_deciding | mlp_t6000_w256_d3_ens2-s0 | c1=1,c2=0.7 | False | 0 / 0 / 0 | 3364.8 | 2292.2 | — |
| best_proposed | mlp_t6000_w256_d3_pca8-s0 | c1=1,c2=0.675 | False | 0 / 0 / 0 | 3458.5 | 2377.0 | — |
| median_deciding | mlp_t1500_w128_d3_wd1em4-s0 | ABSTAIN | — | — | — | — | — |
| best_knn | knn-s0 | ABSTAIN | — | — | — | — | — |
| lowest_verification_loss | mlp_t6000_w256_d3_irw03-s1 | c1=1,c2=0.7 | False | 0 / 0 / 0 | 3364.8 | 2292.2 | — |

## Secondary: out of band (below 15 °C, above 35 °C), descriptive

| Role | Member | Design | Feasible at every out-of-band point | Violations (reach / plating / temp) | Worst t_CV (s) | Mean t_CV (s) |
|---|---|---|---|---|---|---|
| baseline | — | c1=0.75,c2=0.6 | False | 11 / 16 / 2 | — | — |
| best_deciding | mlp_t6000_w256_d3_ens2-s0 | c1=1,c2=0.7 | False | 1 / 22 / 8 | — | — |
| best_proposed | mlp_t6000_w256_d3_pca8-s0 | c1=1,c2=0.675 | False | 3 / 22 / 8 | — | — |
| lowest_verification_loss | mlp_t6000_w256_d3_irw03-s1 | c1=1,c2=0.7 | False | 1 / 22 / 8 | — | — |

## Adversarial search (Mode X)

| Member | Rank (deciding rule) | Points verified | In-band violations / unresolved / confirmed | Out-of-band violations / unresolved / confirmed |
|---|---|---|---|---|
| knn-s0 | 93 of 99 | 50 | 7 / 18 / 15 | 3 / 7 / 0 |
| mlp_t1500_w128_d3_wd1em4-s0 | 50 of 99 | 50 | 5 / 27 / 6 | 1 / 8 / 3 |
| mlp_t6000_w256_d3_ens2-s0 | 1 of 99 | 50 | 2 / 35 / 2 | 4 / 7 / 0 |
| mlp_t6000_w256_d3_irw03-s1 | 14 of 99 | 50 | 8 / 30 / 3 | 4 / 5 / 0 |
| mlp_t6000_w256_d3_pca8-s0 | 40 of 99 | 50 | 7 / 25 / 4 | 5 / 9 / 0 |

Findings: 29 in band, 17 out of band (SCORE_VALUE_DIVERGENCE when the member is in the top half under the deciding rule, otherwise OTHER_SIGNAL). A search that finds nothing is not a safety bound.
