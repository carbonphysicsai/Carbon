# Problem C: one fast-charge protocol for 15-35 °C

Public synthetic DEVELOPMENT evidence. Each model chose one two-step protocol from its own predictions at the 20 in-band conditions; the reference verified it at 90 conditions over 5-40 °C. The claim is the in-band result (15-35 °C); out-of-band points describe where the design breaks and never count against it. Not a global optimum, not a qualification.

## Primary: in band (15-35 °C)

| Role | Member | Design | Feasible at every in-band point | Violations (reach / plating / temp) | Worst t_CV (s) | Mean t_CV (s) | Worst saved vs baseline (s) |
|---|---|---|---|---|---|---|---|
| baseline | — | c1=0.75,c2=0.6 | False | 15 / 0 / 0 | — | — | — |
| best_deciding | mlp_t6000_w256_d3_ens2-s0 | c1=1,c2=0.675 | False | 0 / 0 / 0 | 3450.7 | 2381.1 | — |
| best_proposed | mlp_t6000_w512_d3-s1 | c1=1,c2=0.675 | False | 0 / 0 / 0 | 3450.7 | 2381.1 | — |
| median_deciding | mlp_t1500_w128_d3_wd1em4-s0 | ABSTAIN | — | — | — | — | — |
| best_knn | knn-s0 | ABSTAIN | — | — | — | — | — |
| lowest_verification_loss | mlp_t500_w64_d3-s0 | ABSTAIN | — | — | — | — | — |

## Secondary: out of band (below 15 °C, above 35 °C), descriptive

| Role | Member | Design | Feasible at every out-of-band point | Violations (reach / plating / temp) | Worst t_CV (s) | Mean t_CV (s) |
|---|---|---|---|---|---|---|
| baseline | — | c1=0.75,c2=0.6 | False | 11 / 16 / 3 | — | — |
| best_deciding | mlp_t6000_w256_d3_ens2-s0 | c1=1,c2=0.675 | False | 3 / 22 / 8 | — | — |
| best_proposed | mlp_t6000_w512_d3-s1 | c1=1,c2=0.675 | False | 3 / 22 / 8 | — | — |

## Adversarial search (Mode X)

| Member | Rank (deciding rule) | Points verified | In-band violations / unresolved / confirmed | Out-of-band violations / unresolved / confirmed |
|---|---|---|---|---|
| knn-s0 | 93 of 99 | 50 | 5 / 4 / 29 | 8 / 3 / 1 |
| mlp_t1500_w128_d3_wd1em4-s0 | 50 of 99 | 50 | 1 / 35 / 3 | 1 / 8 / 2 |
| mlp_t500_w64_d3-s0 | 86 of 99 | 50 | 11 / 17 / 12 | 4 / 4 / 2 |
| mlp_t6000_w256_d3_ens2-s0 | 1 of 99 | 50 | 6 / 33 / 4 | 1 / 4 / 2 |
| mlp_t6000_w512_d3-s1 | 23 of 99 | 50 | 2 / 34 / 2 | 7 / 5 / 0 |

Findings: 25 in band, 21 out of band (SCORE_VALUE_DIVERGENCE when the member is in the top half under the deciding rule, otherwise OTHER_SIGNAL). A search that finds nothing is not a safety bound.
