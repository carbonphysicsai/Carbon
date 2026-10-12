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
| The public scoring set (accuracy panel and decision references) | `public_ev4_scoring_set` from #1188's runner (`scripts/dev/battery/l1_decision_q1.py`): only the committed public EV4 decision references, `docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz`, digest `sha256:ff10f9aea9097cd500d646ffe02f479d04401207b30a44aeee33566433e436cb` (the contract's literal). Accuracy and decision loss BOTH use it (pass it as `scoring_set=` to the experiment, as #1188 does) | the digest, recorded in the output; the ledger compares it with the committed contract's literal (below) and refuses any other |
| The public decision questions | The EV4 development decision contract (`ev4-dev-proof-v1`, or `ev4-dev-proof-l1-v1` for Level 1) run with `scoring_set=public_ev4_scoring_set`, and the public-dev-decisions questions (`public-dev-decisions-v1`) when their references are resolved | each contract digest, and the number of questions resolved for every member (the common mask) |
| The run's own baseline | The baseline strategy of that run's session: the baseline entry in the run's proposals' `expected.json` (its recipe digest and scored seed). Each run is compared with its OWN baseline; baselines are not shared across runs or lanes | the baseline recipe digest and seed, per run |

No sealed, hidden, tuning, bank or validator material is an input. A path that names such material is refused by the ledger.

**Where the pin is.** The pin is the committed contract `ev4-dev-proof-l1-v1.json` (#1188), whose literal
`public_reference_sha256` is `sha256:ff10f9ae…436cb`; #1188's test asserts that literal equals the runner's reference digest and
that no "private" path is in the scoring identity. The runner's own check inside `public_ev4_scoring_set` compares a fresh read with
a digest taken from the same file at import: it guards a change in between, not the content, so it is not the pin. The ledger reads
the literal from the committed contract and compares the record's digest with it; a missing contract or one without the literal
refuses every record.

**What is NOT public, and never used here.** `carbon.battery.value.scoring.scoring_set` (and the default scoring set of the
EV contracts, whose `scoring_data` reads "retained exam-design private-role references") loads the retained exam-design
private-role references under `docs/development/evidence/exam-design-2026-09-24/refs-b/`. Those are not public. They are never
opened on this path: the run uses `public_ev4_scoring_set` and nothing else. A function's name or a contract's title is not
evidence that it is public; check the source files it reads.

## Procedure

1. Rebuild the bundle's model from the bundle alone (the clean rebuild the run already passed), and rebuild the run's OWN baseline
   (the baseline recipe at the seed its `expected.json` records), with the same trainer and the same backend. The rebuild uses CPU or the lane's own
   existing path; nothing is purchased.
2. **Accuracy error** = the frozen exam's error (`carbon.battery.exam.evaluate`) on the cases of `public_ev4_scoring_set`: the mean over the SCORABLE cases, lower is better. The baseline's value is its single rebuild at the recorded seed.
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
                   "seeds": [0], "accuracy_error": 0.0, "decision_loss": 0.0},
      "panel": {"scoring_set": {"function": "public_ev4_scoring_set", "sha256": "sha256:ff10f9aea9097cd500d646ffe02f479d04401207b30a44aeee33566433e436cb", "cases": 0}},
      "questions": {"contract_digests": ["sha256:..."], "common_mask": 0,
                    "skipped": [{"contract": "public-dev-decisions-v1", "reason": "references_unresolved"}]},
      "computed_by": "executor", "computed_on": "YYYY-MM-DD"
    }

A metric the executor could not measure is `null`, never a guess; `public_only` must be `true` and `panel.scoring_set` must
name `public_ev4_scoring_set` with the contract's literal digest (the ledger refuses a record that says otherwise, lacks the digest, or names a
private-role source). The relative improvement is `(baseline - model) / baseline`, positive when the model is better.

## Which levels are measurable when

A Level 1 to 4 bundle is a recipe compiled under its own construction level; rebuilding it on CPU needs the level-compile step
of the value path (`Experiment(level_compiler=...)`, `carbon.battery.value.level_compile`). The executor does not invent that glue.

| Levels | Measurable | Entry point |
|---|---|---|
| L0 | now, using `public_ev4_scoring_set` (defined in #1188's runner; until that merges the executor imports it from the branch, read-only) | the existing value path (`carbon.battery.value`, no level compile) with `scoring_set=public_ev4_scoring_set` |
| L1 | accuracy error now (executor records of 2026-10-12, #1188 on main); decision loss only once the bundle is a registered panel member | `python -m scripts.dev.battery.l1_decision_q1` over `ev4-dev-proof-l1-v1` (public EV4 decision, public references; bundles compiled at Level 1), verified against #1188's branch (head 442643fe9) |
| L2 to L4 | after the same registration exists for those levels (a contract and a runner like #1188's); not yet built | `level_compile` with a per-level contract |

Until then the record for such a run is not written (the ledger reads UNMEASURED for that level), never a Level 0 rebuild of a
level bundle.

**Level 1 accuracy error without a panel registration.** A Graphite bundle is not a registered member of the 20-member
`ev4-dev-proof-l1-v1` panel (11 Level 0 anchors, 9 Level 1), so `member_bundle`'s level path refuses it. The executor rebuilds it
the way that path does (`level_compile.base_for(strategy, level, None)` then the Level 0 base) without the registered-panel
guard, scores accuracy error on `public_ev4_scoring_set` against its own baseline, and writes `decision_loss` null with
`questions.decision_loss_null_reason`. The ledger keeps that reason on the decision-loss column and carries a **caveat on the
accuracy column** naming the missing guard (`improvement.public_dev.accuracy_error.caveats`). Registering Graphite bundles as panel
members, for decision loss at Level 1 and for any scoring at Levels 2 to 4, is the Test Engineer's decision; until it is made, Levels 2
to 4 read UNMEASURED and the line says why. A record's `level` must equal its manifest run's level or the batch is refused.

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
give the same interval; with fewer than 3 runs the interval is `null` and the column says "interval not meaningful at n=2", since
a bootstrap of two values is only their range), the number of runs `n`, and a `small_n` flag when `n` is under 10. Its label is "PUBLIC-DEV-MEASURED".
The column is `constructor.improvement.public_dev.{accuracy_error,decision_loss}` in each ledger line.

**Noisy decision loss.** Decision loss is scored on the common resolved mask, which differs between runs. When the masks differ or
the runs disagree in sign, the ledger shows the column as `MEASURED_BUT_NOISY` with the per-run values and the masks, and it is
not an improvement claim; the accuracy-error column is the headline until the masks are comparable (for instance when
`public-dev-decisions-v1` is resolved).

## How the executor hands it over

One file per bundled run, named `<run>-public-improvement.json`, beside the batch's other outputs, and the batch manifest names
it in the run's entry as `public_improvement_file`. Backfill: the existing bundles (the stage A, ladder and R4 runs) get the
same record, so earlier levels have points too; until a record exists the column reads UNMEASURED.

## What this does not say

It is an improvement against the baseline on public development data. It is not an improvement on the sealed exam, not a
qualification, not an economic or security claim, and with a handful of runs per level the interval is wide; the `n` beside each
number is the point.

## Addendum: registered-guard records for Levels 1 to 4 (plan; OPT-09 panel, #1208)

**Status, 2026-10-12: the record shape and the ledger reading below are built (`improvement.validate`, `public_dev_block`, with
tests); the rebuild is run by the executor under the Test Lead's resource decision (OPT-09 README: the total for these builds is
UNMEASURED).** It replaces the guard-skipped, accuracy-only
Level 1 to 4 records. Those stay in the ledger, labelled `guard: skipped`, as history.

### Which bundles

OPT-09 (`carbon/battery/value/contracts/ev4-dev-proof-bundled-v1.json`, panel `ev4-dev-proof-bundled`, merged in #1208 at
`a4ba57bf0`) registers ten public Graphite bundles as panel members. They are the bundles of the existing records:

| Level | Members (label) | Lane | Counts for the level |
|---|---|---|---|
| 1 | `l1-D-913bf188-p-4fd7fb870d2b-s2687932037` | D | yes |
| 2 | `l2-E-18fc7b1c-p-839de482ac6b-s2360653682`, `l2-E-913bf188-p-fa5c88711f35-s441520862`, `l2-E-d90a8ccf-p-891e0fd1ebdb-s3706087842` | E | yes |
| 3 | `l3-F-18fc7b1c-p-69268f1b74ec-s280224976`, `l3-F-913bf188-p-50299fa270c6-s4218777628`, `l3-F-d90a8ccf-p-839de482ac6b-s2080028190` | F | yes |
| 4 | `l4v3-plain-G-18fc7b1c-p-5730cc1c70c2-s3205818801`, `l4v3-plain-G-913bf188-p-e11e2f73879f-s2331991164`, `l4v3-plain-G-d90a8ccf-p-37985e699fe3-s3133732938` | G | **no** (`counts_for_level: false`) |

The Level 1 record of run `18fc7b1c` (member `p-74b8c69ead59`) has no registered counterpart. It stays a guard-skipped record, shown
apart; the registered Level 1 line therefore rests on one member until more are registered.

### Entry point and guard

The `value_panel` phase of `scripts/dev/exam_design/value_phases.py` (`run_value_panel`), with a `cfg.json` like the Level 1
panel run: `{"contract": "carbon/battery/value/contracts/ev4-dev-proof-bundled-v1.json", "phase": "value_panel", "shard": 0,
"shards": 1}`; the plan form is `python -m scripts.dev.exam_design.value_plans panel --study ev4-bundled --shards 1`. It calls
`experiment.member_bundle(...)` with `level`, `arm`, `level_compiler=level_compile` and `panel_name="ev4-dev-proof-bundled"`, so the
**registered-panel guard is on**: a changed contract, member, variant or recipe digest is refused, and a level member never falls back
to the Level 0 base. It checks `public_reference_sha256` against the committed literal (the same pin as the EV4 records). Run it on
host CPU, in the same way and at the same (no) cost as the Level 1 run; no pod, no network, no hidden material.

### Outputs

For each member the phase writes `predictions/<member>.json.gz`. The executor scores those stored bundles (no second rebuild)
exactly as the existing public-improvement records do:

- **Accuracy error:** `exam.evaluate` on `public_ev4_scoring_set`, against the run's own Level 0 baseline at its recorded seed.
- **Decision loss:** `_decide` per development scenario with the bundled contract's candidates, on the common resolved mask,
  against the baseline's decisions (three baseline rebuilds, one per run, about 10 s each, are needed for the baseline side).
  This is the EV4-scenario column, so the existing noise rule applies (masks that differ, or runs that disagree in sign, read
  `MEASURED_BUT_NOISY`); the public-dev VALUE-half column, when built, supersedes it as the headline.
- **Always-abstain control (#1209, read narrowly).** RES-07 (`Business/research/value-metric-audit/reports/REPORT.md`, section 3)
  constructs *always abstain* as "not a prediction model: zero unsafe selections and zero new design benefit" and computes its
  **registered loss** only on the real cohort's common mask; a question with no feasible design is settled NONE, not unresolved.
  It ranked 2nd of 100 on the historical EV5 verification mask. The executor computes the control the same way: it never selects;
  its loss on each scenario of the same common mask is the registered decision loss of an ABSTAIN outcome, through the same
  `carbon.battery.value` loss function as the models (a missed opportunity when the reference has a feasible best design in the
  tested set, 0 when none does), not a re-derived formula. The record carries `controls.always_abstain` =
  `{"decision_loss": number or null, "rank": integer or null, "of": integer, "mask": integer}`: its loss, its rank among {panel
  members, baseline, control} by decision loss (1 = lowest), the size of that field and the common-mask size. A decision-loss
  improvement that does not beat the control is not evidence of better decisions.

### Record shape the ledger accepts

The schema stays `carbon.graphite.public-improvement.v1`; every addition is optional, so **every existing record is still
accepted unchanged** (no `guard` field reads as `guard: skipped`). `panel` is always an object. A registered-guard record is a v1
record with these changes (one file per member, `<run>-<lane>-L<n>-registered-public-improvement.json`):

    "guard": "registered",
    "panel": {"name": "ev4-dev-proof-bundled",
              "scoring_set": {"function": "public_ev4_scoring_set", "sha256": "sha256:ff10f9ae...436cb", "cases": 840}},
    "member": "<registered label, e.g. l2-E-913bf188-p-fa5c88711f35-s441520862>",
    "level": <the member's level>, "counts_for_level": true | false,
    "supersedes": {"file": "<guard-skipped record file>", "sha256": "sha256:..."},
    "controls": {"always_abstain": {"decision_loss": 0.0, "rank": 1, "of": 12, "mask": 7}}

There is no top-level `scoring_set` or `scoring_set_digest` duplicate: the scoring set stays at `panel.scoring_set`, where the
ledger already reads it, and the same digest pin applies (the committed contract's literal `public_reference_sha256`). The ledger
refuses a registered record when: `panel.name` is not the committed bundled contract's panel; `member` is not in the contract's
`panel_registration.member_sha256` (labels with the seed suffix `-s<seed>`); `level` or `counts_for_level` differs from
`carbon/battery/value/panels/proof-panel-levels-v1.json`; `supersedes` lacks a file and a `sha256:` digest;
`controls.always_abstain` is missing or malformed; or `counts_for_level`, `supersedes` or `controls` appear without `guard:
"registered"`.

### Ledger change

- A `guard` flag on every public-dev block (`registered`, `skipped`, or `mixed`). The missing-panel-guard caveat applies to
  `skipped` records only.
- For a run that has a registered record, the registered one is used; the old record is listed under `superseded` with its digest
  and is not counted.
- **Level 4 lane G is non-counting.** Non-counting records are left out of `n`, the median, the best and the interval. They are
  listed under `non_counting` with their values, labelled base-recipe-only (the Level 4 caveat: no graph, not evidence about graph
  lowering or the Level 4 freedoms). With no counting member the Level 4 value reads UNMEASURED with that reason, never a number.
- Decision loss comes from the registered panel (the EV4-scenario column above, with the always-abstain control beside it).

### Cost, order and limits

- Planning bound **about 0.2 CPU-hours per member rebuild**: 10 members, each rebuilt once and then run once more through the grid
  pass, so about 4 CPU-hours at the upper end (measured Level 1 builds were 100 to 165 s). The executor measures the first member
  and stops for the Test Lead if the credible total exceeds the stop rule above (about 6 CPU-hours or 10 GB).
- Run `nice`d, one process, RSS watchdog at 9.5 GB (the limit of the existing driver), shard 0 of 1, in the order Level 1, 2, 3, 4.
- Development evidence only: public EV4 panel, own baseline, not sealed, no qualification claim, no mainnet-level claim by
  itself. With one to three members per level the interval is not meaningful or coarse; the `n` beside each number is the point.
