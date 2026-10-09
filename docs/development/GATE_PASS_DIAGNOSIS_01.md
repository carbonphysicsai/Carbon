# GATE-PASS-DIAGNOSIS-01 — battery public PRACTICE

Status: DEVELOPMENT diagnosis. The miner's 5,711-trial Launchpad export is not
in this repository. Its failing gate and its own default-MLP result remain
unmeasured here; the headline alone does not identify them.

## What the existing evidence establishes

- Battery PRACTICE calls `exam.evaluate` with the same case gates and frozen
  tolerances as the exam. Its public 200-case set has no paired repeats, so
  `paired_repeat` is not applicable in PRACTICE.
- `exam.aggregate` marks a trial ineligible if **any** scored case fails a
  mandatory gate. Its reported error averages only the scorable cases. A lower
  error can therefore coexist with an ineligible trial; the stated 46% FNO
  improvement does not establish gate passage.
- The published default MLP scaffold is `mlp`, 2,000 steps, width 64, depth 3.
  In the committed graphite-run5 CPU practice evidence, all three baseline
  seeds have `eligible: true`, 200/200 cases scored, and empty `gate_failures`.
  All 27 committed run-5 practice summaries are likewise eligible. This proves
  that public PRACTICE can satisfy its gates for those recorded builds. It does
  **not** prove that a particular default-MLP build in the miner's campaign did.
- The current gates are `schema_finite`, `initial_voltage`,
  `initial_temperature`, `voltage_ceiling`, `voltage_floor`, and
  `capacity_bound`; `paired_repeat` applies only where a twin is supplied.
  The two initial-value choices are explicit battery construction surfaces;
  the voltage head is optional. Which gate failed in the 5,711 trials must be
  read from those trials' `summary.gate_failures`.

## Run on the miner's own export

Export the campaign from Launchpad, then run:

```sh
python -m scripts.dev.miner_launchpad.gate_pass_diagnosis /path/to/campaign-export.json
```

The command prints aggregate trial and case counts for each failing gate,
counts the exact published MLP scaffold separately, and distinguishes the best
descriptive error from the best *eligible* error by backbone. A trial with a
missing or contradictory summary is counted as such, never counted as a pass.
The report contains no trial IDs, recipes, case values, or private exam data.
Gate counts can overlap: one trial may fail more than one gate. If
`exported_trials` differs from 5,711, the export does not cover the headline.

No gate threshold or scientific rule is changed by this diagnostic. Once the
actual export is available, record its aggregate output here and decide whether
there is an implementation defect or a genuine mandatory failure. Any change
to a scientific gate tolerance remains an owner decision and must be
prospective.

## Sources

- `carbon/battery/practice.py::score_practice` and
  `carbon/battery/exam.py::{evaluate_case,aggregate}`.
- `carbon/battery/scaffold.py::SCAFFOLD`.
- `docs/development/evidence/graphite-run5-q1/practice-summaries.json` and its
  README. That public development campaign is distinct from the miner's
  5,711-trial Launchpad campaign.
