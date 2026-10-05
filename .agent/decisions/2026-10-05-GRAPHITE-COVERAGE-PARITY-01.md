## 2026-10-05 — GRAPHITE-COVERAGE-PARITY-01: no flattering score, missing predictions charged, battery parity

**Authority:** the Test Lead's four decisions on the selective-crash probe
(PR #602, GRAPHITE-ATTACKER-COOLING-SF-01), made under the delegated
failure-attribution authority of OWNER-GRAPHITE-TEST-WAVE-02 §3 and the
roadmap's Track A rule that a partial artifact is never graded as valid,
relayed by the coordinator on 2026-10-05. This branch builds items 2-4. Item 1
(Interface v1 numerical faults charged as `CANDIDATE_NUMERICAL_FAULT`, a v2
policy) is Codex's #586 and goes through PR Head; the cooling validator's
fault typing is not changed here. No scientific value, tolerance or weighting
is chosen.

**Base:** stacked on `claude/cooling-selective-crash` at 345d4606 (#602).

### COV-D1 — Item 2: an ineligible record never headlines a score

Graphite's experiment records move to
`carbon.graphite.phase3.proposal-result.v2` (`experiment.PROPOSAL_SCHEMA`;
`PROPOSAL_SCHEMAS` keeps v1). A scored record's `frozen_rule` is
`experiment.frozen_rule_view`:

- eligible: `headline` SCORED, the score as before, plus `n_cases`;
- ineligible: `headline` INELIGIBLE with `gate_failures`; `score`,
  `important_score` and `components` are None, and the soft score over the
  scorable cases sits under `partial_coverage` with the label
  "partial coverage, k of n cases" (`k`, `n` beside it), where no score
  column reads it.

v1 records are never rewritten. Readers go through `frozen_headline` and
`headline_score`, which read v1 and v2 alike and never show an ineligible
set's soft score. The places it appeared, and what each does now:

| Place | Now |
|---|---|
| Experiment record (`frozen_rule`) | v2 view above |
| Experiment record (`baseline` block) | `score` via `headline_score`, plus `headline` |
| Constructor feedback (`_feedback_view`) | copies the v2 `frozen_rule` |
| Delivery bundle ablation entries | carry the v2 `frozen_rule` |
| Delivery write-up (baseline line) | `delivery._result_line`: an ineligible baseline reads INELIGIBLE with its gate reasons; an eligible one is byte-identical to before |
| `best_improvement` | already selected eligible records only |
| `Experiment.summary`, phase-3/phase-4 reports, attack family reports | carry no score (checked: outcomes, digests and verdicts only) |

Not changed here (owned elsewhere, flagged): the miner-facing practice
feedback summaries (`cold_plate`/`battery` `practice.feedback`) and the
Interface v1 miner outcomes (cooling's adapter outcome, battery's
`_public_score`) still report `score` beside `eligible: false`. The paired
comparison's `mean_delta` for an ineligible proposal is the rule's own output
and is kept; its outcome is REGRESSION.

### COV-D2 — Item 3: a missing prediction is a schema-gate failure

The shared rule is `challenge_validator.scoring.cover` with
`COVERAGE_RULE = "missing-prediction-is-a-schema-gate-failure.v1"`: every
scored case is asked; a case left out or given null becomes an empty
prediction, which fails the Challenge's own `schema_finite` gate, so the case
is GATE_FAILED, the set ineligible and the case charged to the construction,
never FAILED_INFRA and never excluded. Carbon's own infrastructure failures
keep their own path. Hosts:

| Host | Change | State |
|---|---|---|
| Graphite host, battery (`experiment` -> `BatteryPracticeRule.score`) | `cover`; summary `n_missing`; identity `coverage` | done |
| Battery validator / Interface v1 battery (`daemon._infer`) | `daemon.incomplete`: an absent, extra or null case is `prediction_cases_differ`, candidate-charged (RECONSTRUCTION_FAILED). Absent and extra cases were already refused; null was the hole | done |
| Battery intake (`battery/intake.py`) | none needed: it screens and queues; scoring is the daemon's | checked |
| Graphite host, cooling (`CoolingPracticeRule.score`) | the same `cover` change | **blocked**: the edit to `challenge_validator/cooling_scoring.py` was refused by the session's permission classifier as a shared-resource change; reverted, not pursued another way |
| Interface v1 cooling (`challenge_validator/cooling.py`, Codex #586) | `cover` before scoring, and the rule document naming `COVERAGE_RULE` | **not attempted**, same reason and owner (Codex) |
| Levels 4-5 hook | `cover` states the gate failure holds at every level and attribution waits for the uid-separated path (VALIDATOR-04). A record-level `coverage` block in `experiment` (charged-to from the attribution policy's trusted writers) was refused by the classifier and is not built | partial |

So cooling's `missing_prediction_attribution` seam stays open on this branch:
closing it needs the two cooling edits above, by their owners or with the
owner's permission. Battery's partial-set reading changed accordingly: its
`resource_accounting` family now holds a partial set to "never eligible, every
missing case a gate failure" (the old `failed_infra_counted_as_a_pass`
mutation is retired for `missing_prediction_typed_failed_infra`).

Battery's `track_a` byte pin holds: `track_a` scores through
`battery.practice.score_practice` directly, which is unchanged; only the
Graphite `PracticeRule` wrapper applies `cover`.

### COV-D3 — Item 4: battery parity

Battery's Level 0 adapter (`attack/adapters/battery.py`) gains
`selective_fault` and `prediction_omission` (check
`resource_and_failure_accounting`), in cooling's shape, versions
`battery-l0.v2` / controls `battery-l0.v3`. The probe construction is the
public reference plus a small deterministic error sized by the case's own
inputs (so a hidden duplicate is predicted identically; every gate passes), run
through both real paths:

- **Interface v1**: `Validator.evaluate` over `BatteryAdapter` and battery's
  own daemon (`deployment.evaluate`, `process`, `_infer`, `exam.evaluate`) on a
  temporary private pool of the published development examples battery's
  validator tests use, with `DirectBackend.infer` itself running the probe
  model, then the same submission again;
- **Graphite**: `Experiment.run` at Level 0 on a scripted pod account, the
  pod's files from battery's practice program after its fitted model, run as
  written (the pod's GPU program is that program plus a runtime record).

Battery's contract compile is memoised while the probe runs (a deterministic
function of the strategy and contract, its slowest step and not what these
families probe); every other step runs as written.

Results, all HELD: a raise fails the whole attempt and charges it
(Interface v1 RECONSTRUCTION_FAILED `prediction_failed:ConstructionFault`,
resubmission reads the same; Graphite CANDIDATE_FAILED `program`, never
retried); a non-finite output is a gate failure on both (ineligible, nothing
excluded); an omission is refused by the validator
(`prediction_cases_differ`) and gate-failed by Graphite's rule (ineligible,
score column empty).

Mutations (each patches the name the path reads) and what turns red:
`missing_prediction_typed_failed_infra` (`battery_scoring.cover`: the partial-
set guard and every omission attack on Graphite),
`daemon_accepts_a_null_prediction` (`daemon.incomplete`: the null attacks on
Interface v1), `nonfinite_case_typed_failed_infra` (`exam.evaluate_case`: the
non-finite attacks on both paths). A per-case catch in battery's practice
program is not a red mutation any more: `cover` gate-fails the cases it drops.

Motor gets both probes later, once its scorer (`ChallengeScoring`) exists.

### Notes for owners

- **Carbon Validator session** (`challenge_validator/`, attribution policy):
  `scoring.py` gains `cover`/`COVERAGE_RULE`; `battery_scoring.py` applies it
  and names it in its identity. The record-level attribution hook was not
  built (classifier refusal); the policy's trusted-writer levels are the
  natural source for it.
- **Codex** (#584/#586): cooling needs `cooling_scoring.CoolingPracticeRule.score`
  to call `cover` (as battery's does) and `challenge_validator/cooling.py` to
  cover its predictions before scoring and name `COVERAGE_RULE` in its rule
  document; then cooling's seam closes and an omission probe like battery's
  holds there.
