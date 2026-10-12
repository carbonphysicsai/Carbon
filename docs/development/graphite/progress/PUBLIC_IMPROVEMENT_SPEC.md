# Public-development improvement per level: the spec for the executor

**Why.** Graphite's own scores are on the hidden pool, which is sealed, so the progress ledger could not say how much a
bundled model improves on the baseline. The decision that hinges on it is which construction levels open at mainnet, by
measured improvement against risk. This spec measures the improvement on PUBLIC development data only, so the ledger can
report a median and a best improvement per level with an interval and the sample size. DEVELOPMENT evidence: the number is
never sealed, never a qualification claim, and small samples are flagged.

**Who computes it.** The executor, on the WSL host. Public data only, no pod, no model call, no spend. This page is the
spec; the ledger's script reads the executor's output (`improvement.py`).

## Inputs (per bundled run)

| Input | What | Pin |
|---|---|---|
| The run's best model | The run's BUNDLED proposal: `delivery.bundle` and `delivery.proposal_id` in the run's result document | the bundle's digest (`delivery.manifest_digest`) recorded in the output |
| The public accuracy panel | The public EV4 development scoring set that `carbon.battery.value.scoring.scoring_set` loads (public practice and development cases with their committed references) | the scoring set's digest, recorded in the output |
| The public decision questions | The EV4 development decision contract with its committed references (`ev4-dev-proof-v1`), and the public-dev-decisions questions (`public-dev-decisions-v1`) when their references are resolved | each contract digest, and the number of questions resolved for every member (the common mask) |
| The lane's baseline | The Level 0 baseline of the same Challenge: the Challenge's registered baseline strategy (`scoring.baseline_strategy()`, the baseline MLP) rebuilt at the lane's scored seeds | the baseline recipe digest and the seeds |

No sealed, hidden, tuning, bank or validator material is an input. A path that names such material is refused by the ledger.

## Procedure

1. Rebuild the bundle's model from the bundle alone (the clean rebuild the run already passed), and rebuild the baseline at
   each of the lane's scored seeds, with the same trainer and the same backend. The rebuild uses CPU or the lane's own
   existing path; nothing is purchased.
2. **Accuracy error** = the frozen exam's public error on the public panel (`carbon.battery.exam.evaluate` over the scoring
   set): the mean over the SCORABLE cases, lower is better. The baseline's value is the mean over its seeds.
3. **Decision loss** = the decision value of the model's recommendations on the public decision questions, scored against the
   committed references on the common resolved mask (`carbon.battery.value` evaluate): lower is better. Reference failures are
   not a model penalty (they leave the mask). The baseline's value is the mean over its seeds on the same mask.
4. Write one record per run.

## Output: one JSON file per run (`carbon.graphite.public-improvement.v1`)

    {
      "schema": "carbon.graphite.public-improvement.v1",
      "public_only": true,
      "run_id": "...", "lane": "D|E|F|G", "level": 0-4,
      "model": {"member": "...", "bundle_digest": "sha256:...", "accuracy_error": 0.0, "decision_loss": 0.0},
      "baseline": {"definition": "the Level 0 baseline MLP at the lane's scored seeds", "recipe_digest": "sha256:...",
                   "seeds": [..], "accuracy_error": 0.0, "decision_loss": 0.0},
      "panel": {"scoring_set_digest": "sha256:...", "cases": 0},
      "questions": {"contract_digests": ["sha256:..."], "common_mask": 0},
      "computed_by": "executor", "computed_on": "YYYY-MM-DD"
    }

A metric the executor could not measure is `null`, never a guess; `public_only` must be `true` (the ledger refuses a record
that says otherwise). The relative improvement is `(baseline - model) / baseline`, positive when the model is better.

## What the ledger reports

For each level and metric (`accuracy_error`, `decision_loss`): the **median** and the **best** relative improvement over the
level's runs, a **95% percentile-bootstrap interval of the median** (2000 resamples, fixed seed 20261012, so the same records
give the same interval), the number of runs `n`, and a `small_n` flag when `n` is under 5. Its label is "PUBLIC-DEV-MEASURED".
The column is `constructor.improvement.public_dev.{accuracy_error,decision_loss}` in each ledger line.

## How the executor hands it over

One file per bundled run, named `<run>-public-improvement.json`, beside the batch's other outputs, and the batch manifest names
it in the run's entry as `public_improvement_file`. Backfill: the existing bundles (the stage A, ladder and R4 runs) get the
same record, so earlier levels have points too; until a record exists the column reads UNMEASURED.

## What this does not say

It is an improvement against the baseline on public development data. It is not an improvement on the sealed exam, not a
qualification, not an economic or security claim, and with a handful of runs per level the interval is wide; the `n` beside each
number is the point.
