## 2026-10-06 — GRAPHITE-COVERAGE-PARITY-02: missing predictions charged on cooling and motor

**Authority:** the owner's direction of 2026-10-06 to PR Head, "keep
everything consistent and optimal for users", answering the contradiction
#662 raised: battery typed a missing or null prediction as a schema-gate
failure charged to the construction (GRAPHITE-COVERAGE-PARITY-01), while
cooling and motor still typed it FAILED_INFRA and excluded it. The Carbon
Validator session holds gate ownership (owner, 2026-10-05) and builds this.
It extends GRAPHITE-COVERAGE-PARITY-01 (COV-D2) to cooling and motor with the
same shared rule, `challenge_validator.scoring.cover` and
`COVERAGE_RULE = "missing-prediction-is-a-schema-gate-failure.v1"`. No
scientific value, tolerance or weighting is chosen: an empty prediction fails
each Challenge's own existing `schema_finite` gate, and no exam, practice
scorer, gate, component, scale or aggregate changes.

**Base:** `origin/main`, branch `claude/coverage-parity-02`.

**Merge condition:** this change must not merge while a live cooling or motor
Graphite session is open: `CoolingPracticeRule.identity` and
`MotorPracticeRule.identity` gain a `coverage` key, so a session's records
would change rule identity part-way. Cooling's Interface v1 rule document
gains the same key, which moves its `rule_digest`; cooling's validator has no
deployment seed pin (checked: no deployment record names it), so no deployed
digest is broken.

### COV2-D1 — The same typing on every host

Every scored case is asked; a case left out or given null becomes an empty
prediction, which fails the Challenge's `schema_finite` gate, so the case is
GATE_FAILED, the set ineligible and the case charged to the construction,
never FAILED_INFRA and never excluded. Carbon's own infrastructure failures
keep their own path.

| Host | Change | State |
|---|---|---|
| Graphite host, battery (`BatteryPracticeRule.score`) | GRAPHITE-COVERAGE-PARITY-01 | done (-01) |
| Battery validator / Interface v1 battery (`daemon._infer`) | GRAPHITE-COVERAGE-PARITY-01, COV-D2a | done (-01) |
| Graphite host, cooling (`cooling_scoring.CoolingPracticeRule.score`) | `cover`; summary `n_missing`; identity `coverage` | done |
| Interface v1 cooling (`challenge_validator/cooling.py`) | it had a missing-case path: a construction's `predict` returning None was scored by `exam.score_case(None, ...)`, typed FAILED_INFRA and excluded. Now `cover` before scoring; the operator record's aggregate gains `n_missing`; the rule document names `COVERAGE_RULE`. Miner disclosure is unchanged (`eligible`, `n_gate_failed` already carry it) | done |
| Graphite host, motor (`motor_scoring.MotorPracticeRule.score`) | `cover`; summary `n_missing`; identity `coverage` | done |
| Interface v1 motor | none exists (official evaluation is the typed `motor_validator_not_served` refusal) | follows when one exists |
| Miner practice feedback (`cold_plate`/`motor` `practice.score_practice`, `practice.feedback`) | unchanged: the coverage rule sits in the rule wrappers, as for battery | not changed here |

### COV2-D2 — Cooling's and motor's Level 0 attack adapters read the new typing

Both adapters' `resource_accounting` family now holds battery's reading: a
partial set is never eligible, `n_failed_infra == 0` and `n_gate_failed`
equals the missing cases. The vulnerable specimen is the old typing (every
missing case FAILED_INFRA, excluded, the set eligible). `pod_timeout_typing`
stays an open owner seam; only its wording that the frozen rule types a
missing prediction FAILED_INFRA, now false, changed.

- **Cooling** (`attack/adapters/cooling.py`): `ADAPTER_VERSION` moves to
  `cooling-l0.v4`; the controls are unchanged, so `CONTROLS_VERSION` stays
  `cooling-l0.v2`. The byte pin (`test_attack_cooling_vectors.py`) moves
  only `resource_accounting`'s oracle evidence, recorded as `CHANGED_IN_V4`
  and regenerated from `_adapter_output()`. The `missing_prediction_attribution`
  seam's owner question is answered by this ruling; the seam stays NOT_RUN
  with no reserved decision, because no Level 0 construction can omit a case
  and a run family like battery's `prediction_omission` is not built here.
  Its premise is pinned by a test with an omitting construction on both real
  paths (the Interface v1 validator and Graphite's pod path): each omitted
  case is a gate failure, the set ineligible, no case dropped. The selective
  fault specimen (`dropping_accounting`) states the old typing explicitly.
- **Motor** (`attack/adapters/motor.py`): `_score` now scores through motor's
  frozen rule (`MotorPracticeRule`, via `experiment.FrozenRule` with motor's
  registered `ChallengeScoring`), as cooling's adapter does; the practice
  probe (`_probe`) keeps reading `practice.score_practice`, the miner
  feedback path. `ADAPTER_VERSION` moves to `motor-l0.v2`; controls
  unchanged (`motor-l0.v1`).

### COV2-D3 — Tests and mutations

- `test_graphite_coverage_parity.py`: cooling's and motor's frozen rules
  charge a missing and a null case (GATE_FAILED, `schema_finite`,
  `n_missing`, ineligible, identity `coverage`); mutations patch each
  rule's `cover`.
- `test_challenge_validator_cooling.py`: a construction returning None for
  four cases is SCORED ineligible with four gate failures, the operator
  record shows `n_missing` 4 and `n_failed_infra` 0; restoring exclusion
  (`cooling.cover`) turns it red.
- Both attack adapter tests: the partial-set test now reads "a gate failure,
  never a pass", with omitted and null cases. `failed_infra_counted_as_a_pass`
  is retired (a partial set has no FAILED_INFRA case left to count) for
  `missing_prediction_typed_failed_infra`, which restores the old typing at
  the names the hosts read and turns the partial-set guard and
  `resource_accounting` red (cooling: and the omission guard on both paths).
- `test_motor_scoring.py`: the rule's summary equals the practice summary
  plus `n_missing` (0 on the exact set); rows are unchanged.
- Cooling's two "harness drops a faulted case" mutations are not red alone
  any more (`cover` gate-fails the dropped cases; tested); each now combines
  the drop with the old typing, so the selective-fault dodge table is
  unchanged.

### Notes for owners

- **Codex** (`cooling_scoring.py`, `challenge_validator/cooling.py`, per
  `readiness/chip-cold-plate/ownership.json`): both files changed here under
  the owner's direction; the review should confirm the `rule_digest` move is
  acceptable for any cooling validator store outside this repository.
- **Test Engineer** (attack adapters): versions moved as above.
- No lessons entry is added: the lessons test requires none per decision.
