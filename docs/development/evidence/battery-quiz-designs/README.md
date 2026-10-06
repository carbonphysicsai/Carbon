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
