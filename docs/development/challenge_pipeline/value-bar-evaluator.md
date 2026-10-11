# Development Challenge value-bar evaluator

`PASSES-VALUE-EVALUATOR-01` supplies a one-command evidence check. It runs no
reference solver or model and cannot inspect an evidence directory. The owner
or producer passes explicit files:

```sh
python -m carbon.development_comparison.value_bar \
  --evidence DEVELOPMENT-value-pack.json --rule OWNER-registered-rule.json \
  --bootstrap-replicates 2000 --seed 17 \
  --output-json new-value-report.json --output-page new-owner-page.md
```

The replicate count and seed are analysis inputs. Thresholds are required in
the rule file, never supplied as built-in defaults. Omit `--rule` to inspect
gaps; items 2, 3 and 5 then return `INSUFFICIENT_EVIDENCE`. The command refuses
to overwrite existing outputs. The JSON report and Markdown page contain
aggregate metrics and evidence digests, with no per-case reference values.

## Input contract

The sealed pack has schema `carbon.challenge-value-evidence.v1`,
`scope: DEVELOPMENT`, `challenge`, `export_digest`, and the following fields.
Seal the JSON body with `value_bar.seal(body)` to add `evidence_digest`.

| Field | Required provenance |
| --- | --- |
| `selection` | Carbon model ID, strongest cheap baseline ID, TRAIN/TUNING selection role and pre-heldout selection receipt digest. The #994 baseline ID equals its family. The producer records why it is the strongest cheap admissible method before reading held-out outcomes. |
| `baseline_report` | #994 `carbon.development-portfolio-baseline-report.v1`, `material: DEVELOPMENT`, with digest-matched `equal_budget_screening` and held-out per-question decisions. |
| `carbon_report` | `carbon.development-carbon-value-arm.v1` with matching `challenge`, `model_id`, `export_digest`, and `decisions` in #994 decision-row shape. |
| `folds` | `carbon.challenge-value-heldout-folds.v1`, matching export digest and exactly two `{fold_id, source_digest, questions}` registrations, disjoint in source and question identity. Their independence is a producer assertion to audit, not something a hash proves. |
| `speed` | `carbon.challenge-value-query-costs.v1`, matching export digest, `status: MEASURED`, `query_unit: full_registered_decision_query`, a common hardware/software `route`, and paired `{query, reference_wall_s, carbon_wall_s}` rows. Timings include the complete mandatory condition panel per decision, not just one candidate-condition vector. |
| `equal_budget` | #998 `carbon.design-search.equal-budget-report.v1`, same challenge and source digest, `cost_basis: MEASURED`, 95% confidence, at least two independent bank clusters and the registered wall/core budget. Its values are solver verified. |
| `item_1`, `item_4` | Owner evidence receipts `{status, source_digest, rule_id, challenge, export_digest}` or null. The last two fields must match this pack. This command does not invent their decision definitions. |

The owner rule schema is `carbon.challenge-value-rule.v1` with `rule_id`,
`owner_record`, and `item_2`, `item_3`, `item_5`. Each item may be null (then
insufficient) or contain all of these registered buyer-specific fields:

```json
{
  "item_2": {"max_mean_regret_delta": "HUMAN_INPUT_IN_OBJECTIVE_UNITS"},
  "item_3": {"min_median_wall_speedup": "HUMAN_INPUT"},
  "item_5": {
    "budget": {"wall_s": "HUMAN_INPUT", "core_s": "HUMAN_INPUT"},
    "min_p_lower": "HUMAN_INPUT",
    "max_regret_excess": "HUMAN_INPUT_IN_OBJECTIVE_UNITS",
    "min_feasible_pick_fraction": "HUMAN_INPUT"
  }
}
```

Replace every placeholder with an owner-approved number in a separately
registered rule. Item 2 uses Carbon-minus-baseline regret: an upper 95% bound
strictly below the registered margin passes, a lower bound at or above it
fails, and a crossing interval is insufficient. The resampling unit is the
held-out fold, not individual correlated questions. Two folds provide a very
coarse interval. Settled `NONE_FEASIBLE` questions require correct abstention
by both arms and are reported but receive no invented numerical regret. An
unresolved or infeasible pick, missing question, mixed unit or overlap blocks
the item. This is a matched-admissibility comparison, not a compensating
penalty for an unsafe pick.

Item 3 is the median of paired reference/Carbon full-decision wall-time ratios;
it passes at or above the registered minimum. Item 5 passes only when the
registered budget's #998 lower bootstrap bound for P(model+solver beats
solver-alone), model-minus-cheap-baseline verified regret and model feasible
pick fraction satisfy all three owner limits. Any item failing makes the
overall status FAIL; all five must pass for overall PASS. Otherwise it is
INSUFFICIENT_EVIDENCE.

These identities cannot by themselves certify that a model was selected
before held-out access, that fold sources are physically independent, that the
cheap method is the strongest available, or that timings are comparable.
Producer custody and owner review must establish those claims. A numeric
development PASS is evidence for the owner, not automatic Challenge
qualification or a LIVE scoring decision.

## VALUE-BAR-V1 registered development rule

[`value-bar-v1.json`](value-bar-v1.json) registers the Test Lead's 2026-10-10
delegated value limits. It uses the existing rule envelope and a distinct
`rule_id`; earlier synthetic or historical rule IDs keep their original
meaning. This prospective value test does not change the owner launch record's
instruction to execute onboarding efficiently and record stage times. The
value-bar speed gate applies only when claiming the registered development
value bar.

Use `--rule docs/development/challenge_pipeline/value-bar-v1.json` to evaluate
available evidence. The base rule deliberately leaves `item_5.budget` null:
no common wall/core budget was supplied. It therefore returns
`INSUFFICIENT_EVIDENCE` for item 5 and cannot give an overall PASS. A
Challenge-specific prospective budget registration must use a distinct
`VALUE-BAR-V1:<Challenge>:<registration>` rule ID and add matching `challenge`,
positive `budget.wall_s` / `budget.core_s`, and a SHA-256
`budget_registration_digest` to item 5. The evaluator rejects a budget for a
different Challenge or a changed VALUE-BAR-V1 limit. A digest proves identity,
not that the budget was selected before results; the producer and owner audit
that registration. Never choose the best-looking point after seeing a curve.

The four gates and the reported-only item are:

1. An external decision receipt with status and at least two distinct
   `source_digests`; the owner verifies the sources are genuinely independent.
2. Carbon-minus-cheap-baseline buyer-unit regret, at matched admissibility,
   on exactly two independently registered held-out folds. The upper paired
   fold-bootstrap 95% bound must be **strictly below zero**. A wholly positive
   interval fails; a zero-touching or crossing interval is insufficient.
3. Median measured full-decision-query wall-time speed-up is at least 100×.
   A 20× allowance applies only when a separately measured reference solve is
   at least 3,600 CPU-seconds. The speed receipt adds
   `reference_solve_core_s` and `reference_solve_source_digest`; both are null
   if unmeasured. Whole-query wall time cannot stand in for one-solve CPU cost.
4. Value and volume are **reported, not gated**. Supply `value_range` and
   `volume_range`, each with `low`, `high`, `unit`, `basis` (`SOURCED` or
   `ASSUMPTION`) and `source_digests`. A sourced range needs a source digest;
   an assumption stays labelled in the owner page. Missing ranges do not
   change the overall gate result.
5. At the pre-registered wall/core budget, #998's solver-verified report must
   contain a complete paired model-screen-then-verify minus solver-alone
   **value** interval. Its 95% cluster-bootstrap interval must exclude zero
   strictly in Carbon's favour (negative for minimization, positive for
   maximization). A zero-touching interval is insufficient; an interval
   wholly against Carbon fails. The report requires measured cost, matching
   objective units, at least two independent bank clusters, and a verified
   feasible pick in both arms on every priced job. Win probability, regret
   against the cheap baseline, or separate arm intervals cannot substitute
   for the paired buyer-value interval.

For VALUE-BAR-V1, PASS requires gates 1, 2, 3 and 5. Item 4 appears on the
owner page with its `SOURCED` or `ASSUMPTION` basis but cannot turn a gate into
PASS or FAIL. All files here are public development contracts and toy fixtures;
no Challenge has an adopted budget or a measured VALUE-BAR-V1 PASS from this
registration alone.
