# Battery quiz designs (quiz-registry-v3), compared on the public stand-in

The designs and the metric were registered in `quiz-registry-v3.json` (commit 1871cbd0) before any computation. This comparison uses the **public scoring set** as a stand-in. It is not the tuning set, whose quiz is chosen operator-side.

**Setup.**
- Each of the 1000 draws simulates a batch: a random half of the 1588 public cases.
- **Known-bad:** the 8 EV5 Track A constructions and the run-5 winner.
- **Known-good:** 3 controls and the best quarter of EV4's real members by development decision value.

**Results** (`comparison-public-standin.json`). AUC is given as mean / 5th percentile.

| Design | Best G-FEAS AUC | Best G-PLATE AUC | False-infeasible |
|---|---|---|---|
| Q0 random | 0.57 / 0.31 (n 160) | 0.50 | 0.036 |
| Q1 near band (k ≤ 4) | 0.68 / 0.50 (k 4, n 160) | 0.56 | 0.063–0.067 |
| **Q2 panel disagreement** | **0.76 / 0.58 (n 40)** | **0.74 / 0.74 (n 10–20)** | 0.11–0.21 |

**Reading.**
- **No design reaches the registered bar** (5th-percentile AUC ≥ 0.9 on both measures), so no size meets the sizing rule.
- **Q2 is the only design with real signal.** Its cost is a higher false-infeasible rate at small n.
- **Q1 is weak.** Few near-limit public cases fail on plating: 48 lie within 0.5 band and 83 within 1 band, so G-PLATE is often undefined under narrow bands.
- **The deeper finding.** EV5's Track A constructions fail on *decisions* in EV conditions, but on single-case feasibility calls they look like good deciders. A per-case quiz alone does not expose them. Decision-level checks (the B4 practice decision set, Mode X) remain necessary.

## Q3: the decision-scenario quiz (quiz-registry-v4, commit fa865e57)

**Setup.** The stand-in pool is EV4's 12 verification scenarios: committed reference grids, disjoint from ev4-dev-tuning-v1's development-split value. Each model decides with EV4's fixed rules (`q3-public-standin.json`).

**Results.**
- **The 8 EV5 Track A constructions make no infeasible pick on these 12 scenarios** (decision false-feasible 0.0). The good set's worst is 0.11.
  - Their EV5 FAIL was scenario-specific: they rank high and picked infeasibly in EV5's conditions.
  - As decision-makers on other conditions they are indistinguishable from good members.
  - So "known-bad" does not hold for them outside EV5, and Q3's AUC with them as positives sits below 0.5 at every k (0.49 at k 1, 0.37 at k 12).
- **Run 5's winner is caught:** decision false-feasible 0.20 over the 12 scenarios, above every good member (0.11 or less).
- **Producer cost per scenario:** 35 reference solves at a median of 82 CPU-s, about **0.8 CPU-hours** (B4's host solves, pinned truth image).

**Reading.**
- A decision-level quiz catches a model whose decisions are bad (the run-5 winner). It cannot "catch" constructions whose decisions are only bad in particular conditions, because nothing about them is intrinsically unsafe.
- The detection metric needs a known-bad set defined by behaviour across conditions, not by one study's verdict. Candidates: the boundary-optimist and localized-sign-error controls, the run-5 winner, and constructions selected adversarially per scenario (Mode X).

## v5: behaviour-defined known-bad (quiz-registry-v5, commit 25dc2f1e)

**Known-bad:** the boundary-optimist and localized-sign-error controls and the run-5 winner, plus the synthetic `mode-x-aggressive` decider for Q3 (the fastest protocol on each grid, ignoring constraints). Known-good is unchanged.

**Q2 and Q1 on the public stand-in** (`comparison-v5-public-standin.json`). AUC is mean / 5th percentile.

| Design | n | G-FEAS | G-PLATE | False-infeasible |
|---|---|---|---|---|
| Q0 random | 160 | 0.82 / 0.55 | 0.90 / 0.80 | 0.036 |
| Q1 ≤ 4 bands | 160 | 0.97 / 0.87 | 0.97 / 0.88 | 0.063 |
| **Q2 panel disagreement** | **80** | **0.97 / 0.90** | **0.98 / 0.95** | 0.086 |
| Q2 | 40 | 0.84 / 0.51 | 0.95 / 0.80 | 0.106 |

**Q3 on the 9 pool scenarios with a feasible design** (`q3-v5-public-standin.json`). Three of EV4's 12 verification scenarios are all-infeasible and are excluded under v5's rule.

| k | Decision false-feasible AUC |
|---|---|
| 1 | 0.77 / 0.50 |
| 4 | 0.89 / 0.74 |
| 8 | 0.98 / 0.86 |

**Per-member decision false-feasible** over the 9 scenarios:
- boundary optimist: 0.63;
- mode-x-aggressive: 0.67;
- sign error: 0.29;
- run-5 winner: 0.14 (its 12-scenario 0.20 includes the excluded scenarios);
- good set: at most 0.17.

**Reading.**
- With a behaviour-defined known-bad set, both strata work.
- Q2 reaches the registered bar at about 80 near-limit cases, at a false-infeasible rate of 0.086.
- Q3 approaches it at k = 8 scenarios, costing 35 solves, about 0.8 CPU-hours, per scenario.
- The run-5 winner's decision errors are only partly visible on feasible scenarios. Its per-case plating behaviour (Q2, G-PLATE) is the stronger signal.

## v6: over-caution (quiz-registry-v6 and score-tuning registry v3, commit ccafd40a)

**The control.** The near-limit-cautious control (`score_tuning.near_limit_cautious`) is the mirror of the boundary optimist. It was decided on EV4's 9 feasible verification scenarios (`value-v6-public-standin.json`).

**Results.**
- **Over-caution** (the share of feasible opportunities missed): **0.67** for the cautious control against **0.02** for the known-good mean. This is the clean separator.
- **Q3 decision regret:** the control's is 1.77. Its regret AUC against the known-good set is 0.93–0.96 mean, 0.93 at the 5th percentile, for k = 1–8. One good member has a higher maximum regret (3.67), because one infeasible pick costs 10, so regret alone is noisier than over-caution.

**Reading.**
- A gate alone can be passed cheaply by over-caution.
- Score-tuning registry v3 therefore adds leg **q** = 1/(1 + mean Q3 regret) and candidates A-Q, SR2-Q, G-N-Q, R-G-N-Q, and G-FEAS over A-Q. Over-caution then costs score as well as appearing in the report.
- `tuning_rescore --q3-regret` takes the quiz producer's per-member regret aggregate for the tuning-set comparison.
