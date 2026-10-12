# V1 at Level 1: the score-basis ruling (record)

**Ruling (Test Lead, 2026-10-12):** an unnamed-rule score basis is not reproducible and is not accepted as gate evidence.
V1 and V2 at Level 1 are judged on the members that share one named basis. The mixed 20-member report is kept as a labelled
SECONDARY. This replaces the unsigned draft that asked whether to accept the mixed basis.

## What is committed

All under `carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/`:

| File | Role |
|---|---|
| `q1_report.L1.mixed-basis.json` | The executor's 20-member report, **byte-identical** (sha256 `5b3ba574...dacf7`). The SECONDARY. Never edited. |
| `q1_basis.L1.json` | The executor's per-member score basis (`scores-basis.json`), byte-identical. The evidence for who is on which basis. |
| `q1_report.L1.json` | The DERIVED primary-basis report the gate reads: the 14 members on the Graphite frozen-rule pod score, alignment recomputed on them, `basis_split` recording the source, the basis evidence, the excluded six and the secondary's summary. |
| `reviews/V1.json` | The Test Lead's ruling, transcribed: PASS as a measurement for Levels 0 and 1. |

`python -m carbon.challenge_pipeline.readiness.q1 build-primary --source q1_report.L1.mixed-basis.json --basis-evidence q1_basis.L1.json --primary-basis "graphite frozen-rule pod score" --out q1_report.L1.json`
reproduces the derived file. The gate (`q1.split_problem`) re-derives the split on every run: primary members are exactly the source
members whose recorded basis is the primary basis, each row equals its source row, the excluded members are the rest with their
bases, the secondary summary equals the source's own alignment, and a member with no recorded basis fails closed.

## Result

| | Primary (14, gate evidence) | Secondary (20, mixed basis, not gate evidence) |
|---|---|---|
| Kendall tau-b | 0.281 | 0.467 |
| Spearman rho | 0.488 | 0.659 |
| Top-1 overlap | 0 | 0 |
| SCORE_VALUE_DIVERGENCE | 10 | 16 |

One seed per recipe, so the tau band is 0.0. Seven of twelve development scenarios, EV4 references. A measurement, not a
threshold; Level 1 remains an alignment measurement, not improvement hunting.

Six of the 16 secondary divergences are **basis-confounded**: the five Launchpad anchors that score above
`minerI-bsub-ed8a517f`, and `l1-D-913bf188-p-50299fa270c6`, whose only better-valued comparator is that anchor. They are not
findings against the score.

## Update: the six anchors rescored under the named rule (2026-10-12)

Launchpad confirmed the six anchors' stored practice outputs are recoverable. Each `export.stream` sha256 equals its recorded
`output_digest`. `scripts/dev/battery/l1_anchor_rescore.py` scored each recovered `predictions.json` with the Graphite frozen rule
(`BatteryPracticeRule.score`, the 200 public PRACTICE cases); the record is `q1_rescore.L1.json` (digests and scores, no host paths).
**The recomputed scores equal the recorded practice-feedback v3 scores to six decimals for all six**, so the "unnamed rule" is the
same function on the same cases, now shown rather than assumed.

`q1_report.L1.same-basis.json` is the 20-member variant with all 20 on the named basis (six rescored, `basis_split.rescored`
records them; the source stays byte-identical). It re-evaluates as: tau-b 0.467, rho 0.659, top-1 overlap 0, 16 divergences; V1
automated PASS and V2 PASS (15 outcomes). That is **identical** to the mixed 20 and different from the 14-member primary
(0.281 / 0.488 / 0 / 10). The gate still reads the 14-member `q1_report.L1.json` (the Test Lead's ruling, and `reviews/V1.json` names
its digest); promoting the same-basis variant is the Test Lead's decision. The divergences that involve the six are therefore not
basis-confounded after all.
