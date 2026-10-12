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
| The run's own baseline | The baseline strategy of that run's session: the baseline entry in the run's proposals' `expected.json` (its recipe digest and scored seed). Each run is compared with its OWN baseline; baselines are not shared across runs or lanes | the baseline recipe digest and seed, per run |

No sealed, hidden, tuning, bank or validator material is an input. A path that names such material is refused by the ledger.

## Procedure

1. Rebuild the bundle's model from the bundle alone (the clean rebuild the run already passed), and rebuild the run's OWN baseline
   (the baseline recipe at the seed its `expected.json` records), with the same trainer and the same backend. The rebuild uses CPU or the lane's own
   existing path; nothing is purchased.
2. **Accuracy error** = the frozen exam's public error on the public panel (`carbon.battery.exam.evaluate` over the scoring
   set): the mean over the SCORABLE cases, lower is better. The baseline's value is its single rebuild at the recorded seed.
3. **Decision loss** = the decision value of the model's recommendations on the public decision questions, scored against the
   committed references on the common resolved mask (`carbon.battery.value` evaluate): lower is better. Reference failures are
   not a model penalty (they leave the mask). The baseline's value is its rebuild at the recorded seed, on the same mask.
4. Write one record per run.

## Output: one JSON file per run (`carbon.graphite.public-improvement.v1`)

    {
      "schema": "carbon.graphite.public-improvement.v1",
      "public_only": true,
      "run_id": "...", "lane": "D|E|F|G", "level": 0-4,
      "model": {"member": "...", "bundle_digest": "sha256:...", "accuracy_error": 0.0, "decision_loss": 0.0},
      "baseline": {"definition": "the run's own baseline strategy from its proposals' expected.json", "recipe_digest": "sha256:...",
                   "seed": 0, "accuracy_error": 0.0, "decision_loss": 0.0},
      "panel": {"scoring_set_digest": "sha256:...", "cases": 0},
      "questions": {"contract_digests": ["sha256:..."], "common_mask": 0,
                    "skipped": [{"contract": "public-dev-decisions-v1", "reason": "references_unresolved"}]},
      "computed_by": "executor", "computed_on": "YYYY-MM-DD"
    }

A metric the executor could not measure is `null`, never a guess; `public_only` must be `true` (the ledger refuses a record
that says otherwise). The relative improvement is `(baseline - model) / baseline`, positive when the model is better.

## Which levels are measurable when

A Level 1 to 4 bundle is a recipe compiled under its own construction level; rebuilding it on CPU needs the level-compile step
of the value path (`Experiment(level_compiler=...)`, `carbon.battery.value.level_compile`). The executor does not invent that glue.

| Levels | Measurable | Entry point |
|---|---|---|
| L0 | now | the existing value path (`carbon.battery.value`, no level compile) |
| L1 | after OPT-08 (#1188) merges | `python -m scripts.dev.battery.l1_decision_q1` over `ev4-dev-proof-l1-v1` (public EV4 decision, public references; bundles compiled at Level 1), verified against #1188's branch (head 442643fe9) |
| L2 to L4 | after the same registration exists for those levels (a contract and a runner like #1188's); not yet built | `level_compile` with a per-level contract |

Until then the record for such a run is not written (the ledger reads UNMEASURED for that level), never a Level 0 rebuild of a
level bundle.

## Questions that cannot be scored

`public-dev-decisions-v1` is SKIPPED, not failed, when its references are unresolved: the record lists it under
`questions.skipped` with the reason (`references_unresolved`), `decision_loss` is then computed from `ev4-dev-proof-v1` alone
(or `null` when that is unavailable too), and the record is still written. A skipped contract is never silently dropped.

## CPU-hours (the executor's figures)

The executor's unit is about 0.16 CPU-hours per rebuild; each bundled run needs two rebuilds (its model and its own baseline).
#1188's proxy puts a Level 1 rebuild nearer 0.2. The executor's all-in figure for the 16 bundled runs so far is about 6 to 11
CPU-hours.

| Level | Bundled runs so far | Rebuilds (2 per run) | Unit (CPU-h) | CPU-h | When |
|---|---|---|---|---|---|
| L0 | 5 | 10 | 0.16 | about 1.6 | now |
| L1 | 2 | 4 | 0.2 | about 0.8 | after #1188 |
| L2 | 3 | 6 | 0.16 to 0.2 | about 1.0 to 1.2 | after its registration |
| L3 | 3 | 6 | 0.16 to 0.2 | about 1.0 to 1.2 | after its registration |
| L4 | 3 | 6 | 0.16 to 0.2 | about 1.0 to 1.2 | after its registration |
| All | 16 | 32 | | about 5.4 to 6.4 at the unit figure; the executor's all-in 6 to 11 | |

If a level's credible full estimate exceeds about 6 CPU-hours or 10 GB, the executor stops and routes it to the Test Lead (the
rule #1188 sets); nothing here is purchased.

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
