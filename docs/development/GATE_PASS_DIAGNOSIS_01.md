# GATE-PASS-DIAGNOSIS-01 — battery public PRACTICE

Status: DEVELOPMENT diagnosis. The miner's 5,711-trial Launchpad export stays
with the miner. Its failing gate and its own default-MLP result remain
unmeasured here; the headline alone does not identify them. Carbon must not
request or receive his export because it contains his recipes.

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
  Initial temperature is constructed from ambient, while initial voltage has
  an optional OCV head. The bounded voltage head is also optional. Which gate
  failed in the 5,711 trials must be read from those trials'
  `summary.gate_failures`.

## Device hypothesis

- PRACTICE has no registered twin cases (`practice_store` constructs a
  `CaseStore` without `twins`). `exam.evaluate_case` marks `paired_repeat`
  `NOT_APPLICABLE` when no twin is supplied. A device-dependent repeat mismatch
  therefore cannot explain public PRACTICE's gate failures. A toy test varies
  interior voltage predictions by 1 mV between duplicate-like cases and
  confirms no repeat failure when PRACTICE's twin map is empty; the existing
  exam-design test shows the same control fails `paired_repeat` when a twin is
  registered. This test does not claim to measure an A40.
- The battery GPU PRACTICE worker currently serves JAX recipes only. The FNO
  family requires PyTorch, and `BatteryPractice` refuses an unserved backend
  before dispatch, without producing a practice score. An A40 on the host does
  not by itself establish that a scored FNO trial trained on that GPU. The
  miner's private feedback records the backend that actually ran.
- The other six gates evaluate prediction shape, finiteness, initial values,
  voltage limits and capacity bounds with the same frozen rule on CPU or GPU.
  A different device may change numerical predictions enough to cross a
  boundary, but there is no device-specific practice gate or demonstrated
  erroneous A40 rejection. No tolerance change follows from this evidence.

## Run on the miner's own export

After this tool is merged, the miner can update Carbon, export his own campaign
locally, and run:

```sh
python -m scripts.dev.battery.gate_pass_diagnosis /path/to/campaign-export.json --counts-only
```

`--counts-only` prints each public gate's failed-trial and failed-case counts,
the total and checked trial counts, and aggregate unverified/unknown counts.
It prints no trial IDs, recipes, backbone, scores, case values or private exam
data. The miner shares **only that counts-only output**. The fuller local
report (without the flag) can check whether his exact default MLP scaffold
passed, but he keeps it private. A trial with a missing or contradictory
summary is never counted as a pass. Gate counts can overlap: one trial may fail
more than one gate. If `exported_trials` differs from 5,711, the export does
not cover the headline.

## Launchpad dashboard proposal

Add a small practice-gates card built from the **full** own-research projection
before the view limits experiment rows to the latest 50. Show each public gate's
failed-trial count and failed-case count, plus the number of trials checked and
the count whose summaries cannot be checked. The UI can use the same
counts-only allow-list and explicitly say counts may overlap. It must never
send the aggregate to Carbon or show another miner's trials. The current PR
specifies this view; it does not change the dashboard wire contract or UI.

No gate threshold or scientific rule is changed by this diagnostic. If the
miner chooses to send the counts-only output, it can identify which gate to
investigate next without revealing his recipes. It is miner-reported evidence,
not an independently inspected campaign. Any change to a scientific gate
tolerance remains an owner decision and must be prospective.

## Sources

- `carbon/battery/practice.py::score_practice` and
  `carbon/battery/exam.py::{evaluate_case,aggregate}`.
- `carbon/battery/scaffold.py::SCAFFOLD`.
- `docs/development/evidence/graphite-run5-q1/practice-summaries.json` and its
  README. That public development campaign is distinct from the miner's
  5,711-trial Launchpad campaign.
