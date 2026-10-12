# V1 at Level 1: the score-basis rulings (record)

Two Test Lead rulings, both 2026-10-12, in order.

1. **An unnamed-rule score basis is not reproducible and is not accepted as gate evidence.** V1 and V2 at Level 1 were first judged
   on the 14 members that shared one named basis (the Graphite frozen-rule pod score); the mixed 20-member report was a labelled
   secondary.
2. **After the six Launchpad anchors were rescored under the frozen rule, the SAME-BASIS 20 is the gate input** (larger n, no
   basis confound). The 14-member result stays in the report as a SUPERSEDED row with its reason; nothing is deleted.

## What is committed

All under `carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/`:

| File | Role |
|---|---|
| `q1_report.L1.json` | **The gate input.** The 20 members, all on the named frozen-rule basis (six rescored), alignment recomputed on them. `basis_split` records the source, the basis evidence, the rescore record and the superseded 14-member result. |
| `q1_report.L1.mixed-basis.json` | The executor's 20-member report, **byte-identical** (sha256 `5b3ba574...dacf7`). The source. Never edited. |
| `q1_basis.L1.json` | The executor's per-member score basis (`scores-basis.json`), byte-identical. |
| `q1_rescore.L1.json` | The rescore of the six anchors: digests and scores, no host paths (`scripts/dev/battery/l1_anchor_rescore.py`). |
| `q1_report.L1.superseded-14-member.json` | The first ruling's gate input (14 members). SUPERSEDED, kept for history; it still verifies by itself. |
| `reviews/V1.json` | The Test Lead's rulings, transcribed: PASS as a measurement for Levels 0 and 1, evidence by digest. |

`python -m carbon.challenge_pipeline.readiness.q1 build-primary --source q1_report.L1.mixed-basis.json --basis-evidence q1_basis.L1.json --primary-basis "graphite frozen-rule pod score" --rescore q1_rescore.L1.json --superseded "q1_report.L1.superseded-14-member.json=<reason>" --out q1_report.L1.json`
reproduces the gate file. The gate (`q1.split_problem`) re-derives the split on every run and fails closed: the members are exactly
the source members on the primary basis plus the rescored ones; each row equals its source row (a rescored row carries the
recomputed score); a rescored member needs a committed rescore row whose output digest was verified and whose recomputed score
rounds to the recorded one; the secondary and superseded summaries equal their files' own alignment; a member with no recorded
basis fails the gate; any source digest that differs from its committed file fails the gate.

## The rescore

Launchpad confirmed the six anchors' stored practice outputs are recoverable. Each `export.stream` sha256 equals its recorded
`output_digest`. Each recovered `predictions.json` was scored with the Graphite frozen rule (`BatteryPracticeRule.score`, the 200 public
PRACTICE cases). **The recomputed scores equal the recorded practice-feedback v3 scores to six decimals for all six**, so the
"unnamed rule" is the same function on the same cases. No training, no pod, no spend.

## Result

| | Gate input (20, same basis) | Superseded (14) |
|---|---|---|
| Kendall tau-b | 0.467 | 0.281 |
| Spearman rho | 0.659 | 0.488 |
| Top-1 overlap | 0 | 0 |
| SCORE_VALUE_DIVERGENCE | 16 | 10 |

One seed per recipe, so the tau band is 0.0. Seven of twelve development scenarios, EV4 references. A measurement, not a
threshold; Level 1 remains an alignment measurement, not improvement hunting. The 16 divergences are real score-value findings (lessons
row S10).
