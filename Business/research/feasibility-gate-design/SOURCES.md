# Sources, custody and numeric provenance

Authority/source snapshot: main `0d1370d01ec4bf76c38627c85b9426910d8be3a3`. Counts and estimates are source-derived (low=base=high); reported intervals describe uncertainty separately. Sweep grids, iid-recipe confidence model and the development A-Q proxy are labelled ASSUMPTION research designs. Production cutoffs, risk budgets, minimum strata and adoption are **HUMAN_INPUT**. No claim of qualification or physical safety follows from this audit.

## Explicit public input allowlist

| Local cache name | Committed public path | Exact Git blob |
|---|---|---|
| ev5.json | docs/development/evidence/ev5-2026-10-03/results.json | 7d6ccf75a47c2df56c66d0b223300e5fd9398512 |
| analysis.json | docs/development/evidence/ev5-2026-10-03/analysis.json | c2131424a3d979b71b2881a114507c2b9dcd9bf6 |
| run5-results.json | docs/development/evidence/graphite-run5-q1/results.json | 2ea791a0c8dd8badd41a9d5823d491ec39ee9ed8 |
| run5-defences.json | docs/development/evidence/graphite-run5-q1/defences.json | d35c544075dac3f20588ba42c27e988303aca304 |
| run5-report.json | docs/development/evidence/graphite-run5-q1/q1-report.json | bcc6e905f635b4aa08aacb870d4ee132aa5e14a2 |

Public classification was checked before data access: [EV5 README](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/docs/development/evidence/ev5-2026-10-03/README.md) and [Graphite Q1 README](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/docs/development/evidence/graphite-run5-q1/README.md). These are previously published DEVELOPMENT evidence, not hidden confirmation material. SHA-256, bytes and source commit are recorded per file in `results.json/sources`. The analyzer has an exact allowlist; it never discovers files, fetches inputs, reads host-only bundles, runs solvers or reconstructs members. An optional source download is a read-only Git blob retrieval for these public paths. Unrelated cached files are ignored and excluded from the PR.

## Measurement semantics and missing inputs

- [Near-limit constraint false acceptance](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/carbon/battery/value/false_acceptance.py), blob `5004236be08a7b852b0577ebd1580b29921cd466`: FAIL reference with bands, PASS prediction without bands, constraint-specific denominator; missing predictions are unmeasured.
- [Score tuning](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/carbon/battery/value/score_tuning.py): distinct scoring-set JOINT `feasibility` and near-region `plating_fa`; no decision-grid substitution. Current gate list permits one of near/envelope/feasibility/plating_fa/error per candidate.
- [Registry v5](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/docs/development/evidence/battery-score-tuning/registry-v5.json), blob `d325fa62a18750ef53aa484b7050ed4c2de0c176`: A-Q weights, existing sweeps and strict >0.05 owner variant. Registry compatibility refers to representation, not adoption.
- [Decision semantics](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/carbon/battery/value/decision.py), blob `b1d899d116317bd190ad6812f0aae5d3e8a16c0c`: outcome kinds, reference-resolved agreement and unresolved loss.
- [Accuracy leg](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/carbon/battery/value/ratios.py), blob `4c4876deb19a91a0ba2db51a209d45292501f9c3`: a=1/(1+E), geometric weighting.
- [Public quiz README](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/docs/development/evidence/battery-quiz-designs/README.md), [quiz v5](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/docs/development/evidence/battery-quiz-designs/q3-v5-public-standin.json), [v6 cautious control](https://github.com/carbonphysicsai/Carbon/blob/0d1370d01ec4bf76c38627c85b9426910d8be3a3/docs/development/evidence/battery-quiz-designs/value-v6-public-standin.json): separate quiz/good-bad aggregate evidence, not a per-member A-Q vector or scoring-set gate counts. The misleading `all_12_false_feasible` key actually describes nine feasible verification scenarios in that quiz; it is not a new population law.
- [#1044 SCORE-PROOF-01](https://github.com/carbonphysicsai/Carbon/pull/1044), inspected public PR snapshot: actual A-Q reports INCOMPLETE_LEGS on its stand-in because Q3 is missing. No owner sheets, host predictions or sealed run outputs were accessed.

The public Q1 README explicitly says prediction bundles remain on the operator host. Per-case joint predictions, margin residuals, disjoint conformal calibration records, stratum-indexed scoring counts and member-wise Q3 regret are missing from the input allowlist. This is an identifiability boundary, not authorization to reconstruct them.

## Statistical primary sources

- [NIST exact binomial intervals](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm): exact binomial interval definition. Recipe-level iid use is our explicitly labelled sensitivity assumption. The standalone calculation is KEEP reuse of the numerical approach in #1055's public planning audit, without importing its runtime or changing that job.
- [Angelopoulos, Bates, Fisch, Lei and Schuster, Conformal Risk Control](https://arxiv.org/abs/2208.02814): expected monotone-loss control. The proposed selected-action loss needs its assumptions checked; this does not establish Carbon's conditional accepted-action or worst-stratum safety.
- [Bates, Angelopoulos, Lei, Malik and Jordan, Distribution-Free Risk-Controlling Prediction Sets](https://arxiv.org/abs/2101.02703): holdout calibration of risk-controlled sets. The proposed Carbon adapter and its data/split prerequisites remain research design.

Accessed for this research batch on 2026-10-11 UTC. Source publication/revision dates differ from this access date. No market, solver-cost or commercial claims are made by this gate audit.
