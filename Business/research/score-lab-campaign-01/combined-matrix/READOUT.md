# Combined ScoreLab diagnostic: fixed examples, no rule selection

The registered synthetic matrix completed all 96 profile/component cells:
three profiles x 32 component subsets x four physics modes x sixteen score
proxies, evaluated on four value views. The controls passed. This tests
interactions among existing examples. It does not establish optimal weights,
real-model generalization, a scientific gate, or a recommended score.

The result source is `6e90df8fc47dad8dbfa663db26579f4c8fb8f2cb`; the complete
registration was committed on that source before execution. Its canonical JSON
digest is `a2374abb8508a2c1caae28850ddd31fe1dd584e4e89d5ddef59f40887b9cd76c`.
The authoritative full digest is also recorded in SUMMARY.json and each cell.
`results/IDENTITY.json` binds every raw cell, control result and run receipt.

## What the combinations did

Of 24,576 scoped outcomes, 14,976 are measured development outcomes, 9,216
lack the cheap method's own physics measurements, and 384 have unscored primary
members. Missing measurements remain unscored; they are not zeroes or failed
scientific gates. A measured outcome can still have no eligible winner and an
undefined tau. No favourable subset replaces the full catalogue.

Each nonempty component subset is compared with the no-component baseline at
the same profile, candidate, physics mode and value mask. The 23,808 paired
comparisons break down as follows:

| Change in selected analytic value | Comparisons |
| --- | ---: |
| Higher | 1,649 |
| Lower | 1,451 |
| Unchanged | 8,812 |
| Unscored pair | 11,896 |

These comparisons reuse models, questions and candidate families. Their counts
are descriptive, not independent trials or estimated probabilities of benefit.
The existing per-row bootstrap intervals are not intervals on these paired
component effects. Neither a majority count nor the largest observed gain is a
selection criterion. The answer at this stage is that combinations can improve
or damage value, and many leave the selected design unchanged.

## Accuracy, quiz and their fixed combination

The table uses the preregistered neighbourhood-blended value view, physics OFF,
no optional components and no G-FEAS gate. Tau is computed over six MODEL
members; two PROBE members are reported separately in the raw records. Values
are toy utility units, not battery minutes or real buyer outcomes.

| Profile | A tau [exploratory 95% interval] | Q tau [interval] | A+Q tau [interval] |
| --- | --- | --- | --- |
| Nominal error example | -0.467 [-1.000, 0.455] | -0.298 [-1.000, 0.481] | -0.467 [-1.000, 0.455] |
| Tight boundary/coupled | -0.067 [-0.833, 1.000] | 0.596 [0.077, 1.000] | 0.067 [-1.000, 1.000] |
| Registered error64 row 0 | -0.333 [-1.000, 0.636] | -0.276 [-1.000, 0.905] | -0.333 [-1.000, 0.636] |

In the nominal profile, Q selects value -0.125525 while A and A+Q select
-0.182156. In the tight-boundary profile all three select -0.065824 despite
different rank correlations. In error64 row 0 all three select -0.182156.
Thus improved ranking correlation need not change the buyer's selected result.

Adding the existing G-FEAS example rejects all eight members in the first two
profiles, leaving no winner and undefined tau. In error64 row 0 it rejects
seven of eight; the remaining winner has value -0.206775. This is evidence about
these toy profiles and the copied gate, not a threshold recommendation. Raw
probe ranks include rejected members; a probe in that raw top half is not an
admitted winning model.

All intervals use only 30 bootstrap replicates on small fixed synthetic panels.
They are exploratory and do not adjust for searching thousands of settings.
No multiple-comparison claim, tuned weight or powered equivalence is made.
All four scopes and all candidate outcomes remain in the gzip receipts.

## Cost and reproducibility

The retained run used 388.327415 evaluation CPU-seconds, 0.556320 control
CPU-seconds and 389.805556 wall-seconds. It made 30,720 scorer evaluations and
reused frozen scores across the value views. There were no solver calls, model
rebuilds, model inference calls, provider calls or spend.

An earlier identical run completed but lost its detailed export because of a
CRLF shell-path error. Its observed 339.441742 evaluation CPU-seconds remain
charged in `FIRST_RUN_EXPORT_LOSS.json`; no findings are claimed from it.
Total evaluation CPU time for both runs is 727.769157 seconds. First-run control
and wall time are unknown. These figures exclude image/bootstrap, tests and
artifact export, and do not represent a matched full-workflow baseline cost.

Regenerate the descriptive summary and the separate capacity/reliability
diagnostics without importing candidate code or rerunning the matrix:

```sh
python -m scripts.dev.score_lab.combined_readout \
  Business/research/score-lab-campaign-01/combined-matrix/REGISTRATION.json \
  Business/research/score-lab-campaign-01/combined-matrix/results \
  /tmp/combined-summary.json \
  --diagnostics /tmp/combined-diagnostics.json --bootstrap-seed 20261013
```

The explicit bootstrap seed reuses the existing `core.analyze` default; it is
synthetic research configuration, not an official or hidden seed. Capacity
witnesses and the measurement reliability estimate answer different questions.
See the diagnostic artifact and `scripts/dev/score_lab/FINISH_LINE.md` for their
assumptions and the remaining real-input and engineering prerequisites.
