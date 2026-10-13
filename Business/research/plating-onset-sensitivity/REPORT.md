# RES-12: unsafe picks by distance from plating onset

**DEVELOPMENT public-data sensitivity, 2026-10-13. No historical relabeling, new solves or qualification.**

The requested 2 mV plating-only sensitivity changes no aggregate action label or member outcome. It does not remove the unsafe-pick finding. A material concentration remains just outside the band: 48/69 historical eligible verification events and 50/72 later CPU verification events are in the 2-4 mV bin. Those are reference-relative labels; distance alone cannot establish discretization error.

All numbers below are MEASURED on this finite panel, low=base=high, unless explicitly marked OWNER_REPORTED or HUMAN_INPUT. Fixed source specifications and owner-requested diagnostics also have low=base=high. There is no population CI, economic inference or independent confirmation. [results.json](results.json) contains the exact unrounded outputs; [README.md](README.md) pins every source and [WORKING_CONTRACT.md](WORKING_CONTRACT.md) states scope.

## Evidence and denominator contract

The original EV4 record contains 100 reconstructed members, of which 99 were eligible, representing 79 recipe labels; five constructed controls remain separate. The RES-07/08 public CPU cohort contains 100 later real rebuilds / 80 recipe labels, plus 27 Graphite run-5, 11 additional proof and 10 adversarial rebuilds. These are distinct reconstructions and selections, not interchangeable copies. CPU eligibility is unknown; no historical gate status is transferred to them.

The source action lattice has 35 actions at each of 24 conditions (12 D + 12 V): 840 references, 835 OK and five failed D references. Reference failures remain REFERENCE_UNAVAILABLE, not INFEASIBLE. Candidate tables count action/condition pairs once, never once per model. Distance is abs(reference plating_margin_v)*1000; sign is retained separately. Bins are [0,0.5], (0.5,1], (1,2], (2,4], (4,infinity) mV. The 2 mV sensitivity is inclusive.

Original reference bands remain 1.97 mV plating, 0.157 C temperature and 3.15 s CV timing. The original reference helper prioritizes any definite constraint FAIL over UNRESOLVED. The objective is CV-onset time, not charging to a measured target SOC or real-cell safety. A selected design with a nonnegative/uncertain plating margin may still be infeasible because reach or temperature fails.

## Unsafe events and loss mass

Every historical SELECTED_INFEASIBLE event has the same 10 loss-unit mistake penalty. Thus the fraction of events in a bin equals the fraction of **unsafe penalty mass**, not the fraction of total loss including regret and misses. These are member-by-question counts; repetition across members is not extra physical coverage.

### Original 99 eligible EV4 members

| Distance (mV) | D events / penalty share | V events / penalty share | Pooled events / penalty share |
| --- | ---: | ---: | ---: |
| 0-0.5 | 0 / 0.00% | 0 / 0.00% | 0 / 0.00% |
| 0.5-1 | 0 / 0.00% | 0 / 0.00% | 0 / 0.00% |
| 1-2 | 52 / 40.62% | 0 / 0.00% | 52 / 26.40% |
| 2-4 | 16 / 12.50% | 48 / 69.57% | 64 / 32.49% |
| >4 | 60 / 46.88% | 21 / 30.43% | 81 / 41.12% |

Verification: 69 events / 690 penalty units. Pooled: 197 events / 1970 units. All picks in the 2-4 mV bin fail only plating; every pooled pick within 2 mV independently fails CV reach. Near-onset events in that last category: 52, all on one repeated action/condition pair.

### Later 100 real CPU rebuilds

| Distance (mV) | D events / penalty share | V events / penalty share | Pooled events / penalty share |
| --- | ---: | ---: | ---: |
| 0-0.5 | 0 / 0.00% | 0 / 0.00% | 0 / 0.00% |
| 0.5-1 | 0 / 0.00% | 0 / 0.00% | 0 / 0.00% |
| 1-2 | 50 / 38.76% | 0 / 0.00% | 50 / 24.88% |
| 2-4 | 18 / 13.95% | 50 / 69.44% | 68 / 33.83% |
| >4 | 61 / 47.29% | 22 / 30.56% | 83 / 41.29% |

Verification: 72 events / 720 penalty units. Pooled: 201 events / 2010 units. All picks in the 2-4 mV bin fail only plating; every pooled pick within 2 mV independently fails CV reach. Near-onset events in that last category: 50, all on one repeated action/condition pair.

## Reference-label inventory across every candidate

The inventory is independent of the model cohort. Failed records have no plating distance and appear separately. Sign counts concern margin alone and must not be read as combined feasibility.

| Split | Distance (mV) | FEASIBLE | INFEASIBLE | UNRESOLVED | Negative margin | Nonnegative margin |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| development | 0-0.5 | 0 | 2 | 5 | 5 | 2 |
| development | 0.5-1 | 0 | 0 | 1 | 1 | 0 |
| development | 1-2 | 0 | 8 | 10 | 12 | 6 |
| development | 2-4 | 11 | 24 | 0 | 19 | 16 |
| development | >4 | 76 | 278 | 0 | 167 | 187 |
| verification | 0-0.5 | 0 | 0 | 2 | 2 | 0 |
| verification | 0.5-1 | 0 | 1 | 2 | 2 | 1 |
| verification | 1-2 | 0 | 4 | 7 | 4 | 7 |
| verification | 2-4 | 10 | 13 | 0 | 9 | 14 |
| verification | >4 | 68 | 310 | 3 | 121 | 260 |
| pooled | 0-0.5 | 0 | 2 | 7 | 7 | 2 |
| pooled | 0.5-1 | 0 | 1 | 3 | 3 | 1 |
| pooled | 1-2 | 0 | 12 | 17 | 16 | 13 |
| pooled | 2-4 | 21 | 37 | 0 | 28 | 30 |
| pooled | >4 | 144 | 588 | 3 | 288 | 447 |

Totals: 165 FEASIBLE, 640 INFEASIBLE, 30 UNRESOLVED and five REFERENCE_UNAVAILABLE. Of 42 available candidates inside 2 mV, 27 already have combined status UNRESOLVED and 15 are INFEASIBLE solely because of CV-reach FAIL. There are no combined FEASIBLE candidates within 2 mV. Changing only the plating check to UNRESOLVED therefore changes no combined label, including the single action between 1.97 and 2 mV.

## Two interpretations of the requested sensitivity

Freeze each recorded pick, original model score and eligibility. Recompute the original decision.outcome on a deep copy of reference assessments, preserving original constraints, objectives and loss coefficients. Do not select a new model action or adopt a new best model. The best-in-tested-set reference is recomputed if a label changes. Unresolved outcomes have null loss; they are never counted as zero.

**Plating-only (scientifically bounded):** within 2 mV, only no_plating_onset becomes UNRESOLVED; temperature and CV-reach FAIL remain FAIL. No combined labels, losses, abstentions, ranks or score/value taus change in any cohort. Rank tau is 1 up to floating roundoff, with zero strict reversals and zero rank shifts.

**Literal whole-status censor (not a proposed gate):** set every available action within 2 mV to UNRESOLVED even when CV reach fails. This changes 15 action labels. It erases 52 historical / 50 CPU development unsafe events and changes 147 settled-NONE abstentions to unresolved in each real cohort. Verification unsafe events stay at 69 / 72 respectively, but member denominators still change because abstentions become unresolved. Apparent ranking movement is not evidence of an improved model or of corrected plating failures.

| Cohort | Split | Literal before/after rank tau | Strict reversals | Max average-rank shift | Common paired questions | Common-mask tau |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original eligible 99 | development | 0.733340 | 633 | 31 | 5 | 1.000000 |
| Original eligible 99 | pooled | 0.786916 | 516 | 26 | 12 | 1.000000 |
| Original eligible 99 | verification | 0.981867 | 43 | 21.5 | 7 | 1.000000 |
| CPU real 100 | development | 0.727458 | 660 | 32.5 | 5 | 1.000000 |
| CPU real 100 | pooled | 0.793205 | 511 | 22 | 12 | 1.000000 |
| CPU real 100 | verification | 0.988480 | 28 | 23.5 | 7 | 1.000000 |

Each common mask is the intersection of questions with numeric original and sensitivity outcomes for every member in that cohort. The masks differ from the member-specific original means; retaining a common mask avoids attributing censoring-induced denominator changes to model changes. Neither mask is a new P, Q or w. Full per-member numeric counts, losses and average ranks are in results.json.

### Frozen historical score/value agreement on verification

Higher score is compared with negative decision loss, using the original 99 eligible A40 members. Later CPU models have no paired historical score evidence; their rule_tau is intentionally empty. Historical p45-r30-a25 is unmeasurable and excluded. The original agreement below reproduces the original EV4 H1 statistics; it is not a new significance test.

| Original rule | Original tau | Plating-only tau | Literal censor tau |
| --- | ---: | ---: | ---: |
| control-exam-v1 | 0.403364 | 0.403364 | 0.413313 |
| dar-p0-r100-a0 | 0.261720 | 0.261720 | 0.272946 |
| dar-p0-r30-a70 | 0.409997 | 0.409997 | 0.419946 |
| dar-p0-r50-a50 | 0.406266 | 0.406266 | 0.417044 |
| p0-r20-a80 | 0.402949 | 0.402949 | 0.412899 |
| p0-r30-a70 | 0.404608 | 0.404608 | 0.414557 |
| p0-r40-a60 | 0.401291 | 0.401291 | 0.411241 |

Original eligible verification tau(loss, unsafe fraction) is 0.740635 with member-specific denominators and 0.783935 on the eight-question common mask. CPU real verification equivalents are 0.732833 and 0.786956. Plating-only leaves these unchanged. The owner-supplied postmortem tau 0.953 concerns another estimand/panel and is not reproduced or substituted here.

## Controls and additional public members

Original boundary optimist has eight unsafe verification events and loss 7.272727; localized sign-error has four and loss 4.320397. Neither changes under either sensitivity. Original conservative control has no unsafe verification events; literal censor changes its mean from 2.749017 to 2.998928 by excluding a settled-NONE abstention. Oracle and rank-preserving delay controls remain at zero loss. Missing-output control bookkeeping at D-T5-S0.48 remains as recorded (MODEL_OUTPUT_MISSING with numeric zero); it is not reinterpreted as successful abstention.

| Later public CPU cohort | Members | Unsafe V events | Within 2 mV | Plating-only rank changes |
| --- | ---: | ---: | ---: | --- |
| ADDITIONAL_PUBLIC_PROOF_MEMBER | 11 | 10 | 0 | none |
| ADVERSARIAL_REBUILD | 10 | 6 | 0 | none |
| EV4_REAL_CPU_REBUILD | 100 | 72 | 0 | none |
| GRAPHITE_RUN5_REBUILD | 27 | 16 | 0 | none |

The raw original 100-member cohort also appears separately in JSON (70 unsafe V events, 49 in 2-4 mV); its extra ineligible model is never added to the original eligible comparison. Additional CPU cohorts and adversarial rows are descriptive, not proof that all attacks are caught.

## The useful reference follow-up

The 50 CPU verification events in 2-4 mV arise from only these four public action/condition pairs. Values are derived from the pinned standard references and frozen selected outcomes; they are not new solver measurements.

| Public condition | Selected protocol | Standard signed margin (mV) | CPU event count |
| --- | --- | ---: | ---: |
| V-T9-S0.06 | c1=1.25,c2=0.6 | -2.432310 | 31 |
| V-T9-S0.06 | c1=1.5,c2=0.6 | -2.310943 | 12 |
| V-T9-S0.06 | c1=1,c2=0.6 | -2.742959 | 5 |
| V-T9-S0.22 | c1=1,c2=0.6 | -3.378895 | 2 |

Recommend a separately authorized public convergence/refinement check of those four pairs before strengthening physical claims. No solves are dispatched here. The task reports mesh-20/40/80 margins 2.11/1.53/1.14 mV and a rough 1.8 mV error extrapolation (**OWNER_REPORTED motivation**, low=base=high for the quoted numbers, not independently reproduced by this audit). The [public convergence-study PR #1266](https://github.com/carbonphysicsai/Carbon/pull/1266) is related work, not the measured basis for this sensitivity. A one-case convergence trend supplies neither a transferable error distribution nor a uniform correction. This report cannot infer that any of the four negative labels is incorrect, or that the reference is adequate beyond them.

If new evidence changes a band or grading contract, the Validator/owner must register it prospectively; historical results retain their versioned meaning. Revised scientific cutoffs, error models, physical validation and adoption remain HUMAN_INPUT. Public EV4 cannot determine whether sealed SCORE-PROOF/PICK-01 failures are due to noise. This analysis inspects neither sealed material nor current protected scoring outputs.

## Validation and limits

The script replays all original available reference status inventories and historical selected outcomes using unchanged RES-07/decision functions. CPU retained selections are exact-hash-bound, replayed against the same reference helper, and cross-checked against committed RES-07 nominal/shifted summaries. All 148 original public bundle identities are checked. No model executes. Eight synthetic structural tests cover inclusive signed bin boundaries, preserved independent failures, null reference outcomes, immutable inputs and rank direction. Aggregate replay is deterministic; pinned Black 26.5.1/Ruff 0.16.3 and explicit manifest checks accompany CI.

These counts are finite-panel observations with shared physical cases and repeated recipe seeds, not independent binomial trials. No confidence interval, causal noise attribution, production safety claim, superiority claim or deployment decision follows. The historical objective remains a cycle-1/CV proxy. Reference adequacy, population transport and buyer value beyond this panel remain gaps. No runtime or historical research files change.
