# Measurement design: fixed-population synthetic evidence

**No scoring rule or real sample count is selected.** This study completed
126 prospectively registered cells, using the existing ten Validator toy
proxies on six fixed model traits and four probes. It changes the measurement
design, not the models or score cases. It is not final ScoreLab qualification.

## Identity and execution

- Experiment source: `fef281b496c23d13b1d250e91502ef44153ac8f8`.
- Canonical plan digest: `c690920f8c03c2449aa7924d7bc492f8de4e2ab020c5e13925915d27cb106b0a`.
- External trusted candidate digest: `157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
- All controls passed. **100 actual scorer calls**, then frozen score-side
  results; no candidate training, model inference, reference solves or spend.
- **57.898265121 CPU-seconds, 57.947259008 wall-seconds** in the evaluator.
  Canonical setup, 82 tests, export and readout are additional overhead.
- 1,260 candidate/cell rows: **940 measured**, **320 unscored** by reference
  completeness. Of the measured rows, **94 have undefined tau** because the
  in-force proxy gates all members into one tied class; **846 have numeric tau**.
  Undefined tau is not zero and a measurement status is not admissibility.

The actual run used the pinned canonical environment, hard caps of 1800 CPU-s,
1900 wall-s and 2 GiB address space. START and a copied plan preceded execution;
IDENTITY binds every retained artifact. No scientific output was produced by
the transport wrapper. All 126 cells completed in the first experiment run.

## What the measurements show

### 1. More duplicate rows do not create block information

For each of 90 candidate/block-count/seed combinations under perfect within-block
replication, the block interval was **identical** at 30, 300 and 3,000 rows.
Here are mean joint 95% interval widths over nine candidates with defined tau,
three block counts and three sampling seeds (81 intervals per entry):

| Dependence | Draw rows N | Naive case interval width | Block interval width |
|---|---:|---:|---:|
| iid within blocks | 30 | 1.7667 | 1.7131 |
| iid within blocks | 300 | 1.6484 | 1.7792 |
| iid within blocks | 3,000 | 1.6415 | 1.7412 |
| One replicated draw per block | 30 | 1.6023 | 1.5926 |
| One replicated draw per block | 300 | 1.4639 | 1.5926 |
| One replicated draw per block | 3,000 | 1.5106 | 1.5926 |

These intervals remain very wide. Six illustrative recipe clusters dominate
much of the joint uncertainty; adding value rows cannot create independent
model families. The nonmonotone case widths are a result, not a smoothing error:
there are only 60 bootstrap replicates and three sampling seeds, with discrete
rank statistics. No nominal-coverage guarantee follows. Across 270
candidate/design combinations with three defined seed ranks, **110 changed
rank** when ordered by measured alignment. Those overlapping, correlated
comparisons are descriptive, not 270 independent experiments.

### 2. P and Q can reverse a candidate comparison

The fixed population P is uniform across 36 value questions. The alternative
proposal Q spends half its mass on the six extrapolated questions. Buyer w=1.
Using the exact finite population means, without sampling error:

| Toy proxy | Tau under P | Tau under Q |
|---|---:|---:|
| `V2r2@k3,kappa0.1` | 0.2000 | 0.0667 |
| `V2r2@k5,kappa0.25` | 0.0667 | 0.2000 |

This is a change of estimand, not evidence that one estimator discovered a
better rule. The P row uses unnormalised P/Q correction; the Q row uses raw
proposal draws. Both keep buyer weights separate. The stored physics example's
neighbourhood blend knob does not override this study's explicit finite P/Q/w
law: it is not the earlier neighbourhood-blend result under another label.

### 3. Small outage fractions can discard much more than the missing rows

With N=300 and B=10 (30 rows per block), the common mask included every model
and probe. These counts were identical across dependence assumptions and P/Q:

| Requested draw outages | Missing draws | Complete blocks surviving | Otherwise-resolved draws excluded |
|---|---:|---:|---:|
| 0% | 0 | 10 | 0 |
| 1% | 3 | 7–8 | 57–87 |
| 5% | 15 | 2–3 | 195–225 |

Strict completeness left every nonzero-outage cell unscored: 240 candidate
rows. Complete-block exclusion at 5% retained fewer than three blocks in two
of three seeds, making another 80 rows unscored. Exclusion with three or more
blocks was reported as conditional on retained draws. Nothing was charged to
a candidate for missing reference outcomes, and no unconditional coverage
claim was attached to the excluded sample.

## Limits and next use

The raw artifacts and `SUMMARY.json` contain tau, intervals and undefined
fractions, selected-member value and regret, admissibility counts, cheap-map /
always-abstain ranks and known-bad / adversarial placement for every measured
row. No candidate or inconvenient seed was dropped. Three seeds cannot establish
real coverage, and the nine candidate comparisons with numeric tau are highly
correlated. Scoring cases are fixed; their uncertainty is not measured here.

This supports preserving block identity, explicit common masks, and distinct
P/Q estimands in the eventual campaign. It does **not** establish an optimal
block count, sample count, scoring rule, real-bank power or a qualified value
ceiling. Real reference applicability, independent model-family evidence,
fresh validation and the custodian-run final holdout remain separate gates.
Alternative aggregation/normalisation, score-side outages and the championship
bridge remain later plan items.

Reproduce the full derived report from the retained artifacts:

```bash
python -m scripts.dev.score_lab.measurement_run readout \
  --plan Business/research/score-lab-campaign-01/measurement-study/REGISTRATION.json \
  --output Business/research/score-lab-campaign-01/measurement-study/results \
  > /tmp/measurement-summary.json
cmp /tmp/measurement-summary.json Business/research/score-lab-campaign-01/measurement-study/SUMMARY.json
```

See `scripts/dev/score_lab/MEASUREMENT_STUDY.md` for design, controls and cost
accounting. Every numerical setting is a toy ASSUMPTION, not an adopted rule.
