## 2026-10-04 — GRAPHITE-ATTACKER-AT-B: battery's Level 0 attack adapter

**Authority:** OWNER-GRAPHITE-ATTACKER-01 (a general attack engine with one
adapter per Challenge and construction level; battery Level 0, declarative
recipes, first). Engineering decisions inside that scope, slice AT-B. No
scientific value, threshold, gate, grant or contract is chosen here.

**Files:** `carbon/agent_campaign/attack/adapters/__init__.py`,
`carbon/agent_campaign/attack/adapters/battery.py`,
`tests/cpu/test_attack_battery_adapter.py`.

### AT-B-D1 — The core's types, with a shim until the core merges

The adapter returns the neutral core's own types: `attack.adapter.FamilyDef`
(with its `attack.engine.Family`), `Control`, `OracleResult`, `Rebuilt`,
`Unrebuildable`, `SeamFamily`. They are taken from slice AT-A's committed
interface (`claude/atk-core` at 4137ffb1c) and its working tree, which adds
the specimen to `OracleResult` and INCONCLUSIVE. It also carries the core's
`SessionSurface`: `permission_inventory`, `public_identity`,
`admission_refusals`, `code_run_seconds` and `recipe_outside_contract`, from
the step-4 battery adapter.

This branch does not contain the core. Where the core is absent
(`importlib.util.find_spec` finds no `attack.adapter` or `attack.engine`), a
private `_Shim` with the same field names stands in, so the adapter and its
tests still run. A core that is present but fails to import raises; it is
never quietly replaced by the unvalidated shim. Once the core merges, the shim
is never used and can be deleted.

Importing `attack.adapters` registers every `BUILTIN` adapter in
`attack.adapter.ADAPTERS`, which imports that package the first time it is
read.

The adapter keeps its richer internal tables (`FamilySpec`, `ControlSpec`,
`SeamSpec`, `Build`) and a full reading of each attempt (`assess`). Those are
battery's own; the protocol methods map them to the core's types.

### AT-B-D2 — Families: track_a's five reused, four added

The eight Track A checks (`admission.CHECKS`) map to:

| Check | Family |
|---|---|
| baseline_and_permission_ablation | `permission_ablation` (added) |
| artifact_and_dependency_attacks | `recipe_surface`, `recipe_forgery` (track_a) |
| adaptive_feedback_and_state_attacks | `practice_disclosure` (added) |
| score_exploitation_and_tail_failures | `mandatory_failure` (track_a attacks and specimen; boundary `FrozenRule.score`) |
| resource_and_failure_accounting | `resource_accounting` (added) |
| construction_evaluation_isolation | `staged_bytes` (track_a) |
| reconstruction_and_recipient_rebuild | `rebuild_identity` (track_a), `rebuild_report` (added) |
| fresh_attack_confirmation | NOT_RUN seam `fresh_cases_rerun` |

track_a's functions are looked up at call time and are not changed, so its
coverage report stays byte-identical and a weakened boundary is seen by the
adapter. Each family has a specimen that must fire on every attack, an attack
example and trained and held-out controls.

### AT-B-D3 — Permission ablation reuses the climb harness as is

`climb.ClimbPlan` refuses level 0, so the Level 0 ablation runs the climb over
battery's registered Level 1 draft plan (`level1_draft.climb_plan`). Its
previous profile and its ablated profile are both exactly the Level 0
permissions, so every attack under them checks that a permission Level 0
withholds comes back REFUSED from the live gate
(`challenge_contracts.compile_submission`). Nothing is opened: the live gate
is Level 0's whatever profile a run is labelled with. The family also sends
one item per capability the live contract withholds (derived from the contract,
read only). The panel control is an EV4 panel member.

The climb report's profile labels (`level-1-draft`, `ablated:...`) are the
draft plan's names; every run is against the Level 0 gate. It is not Level 1
testing.

`gate()` reads only the gate's typed refusals (`SubmissionRefused`,
`RecipeRejected`) as REFUSED. Any other exception is the gate failing: it
propagates, so the engine records CRASHED, never a hold (review repair). The
gate's typed refusals already cover malformed input (a string, `None`, a list,
an empty object). `track_a.compile_boundary` still turns `TypeError`,
`ValueError`, `KeyError` and `AttributeError` into a refusal; that is
track_a's code (AT-A's), handed off rather than changed here.

### AT-B-D4 — Controls: split, versioned, named outside Graphite's deny list

`CONTROLS_VERSION = carbon.attack.controls.battery-l0.v1`. Trained controls are
track_a's `RECIPE_CONTROL`, the EV4 `mlp` member, the exact public PRACTICE
predictions, a code run at the allowance and the sealed rule. Held-out
controls are three other EV4 panel members (`knn`, `deeponet`,
`mlp_t1500_w128_d2_f25`), reordered and JSON-round-tripped predictions, and
shorter code runs. Control names (`<family>_<split>_<label>`, unique across splits) say
`panel_`, never `ev4_`: `ev4`, `ev5`, `confirmation` and `canary` are Graphite
deny fragments (`agent_campaign.boundaries.DENY_FRAGMENTS`). For the same reason
the seam that covers `fresh_attack_confirmation` is named `fresh_cases_rerun`.
The engine family's default control (`trained_control`) reads the trained
split only. Held-out controls are read only through their own `check()`, by
the core's `held_out_outcomes`, for the wrongful-rejection rate.

### AT-B-D5 — Oracle semantics

`assess` gives the full reading; `oracle` puts it in the core's verdicts.

| Attempt | Reading | Core verdict and condition |
|---|---|---|
| Declared attack the real boundary's detector catches | BREACH | BREACHED, FAILING_TRIGGER |
| Declared attack that holds, specimen fired | HELD | HELD |
| Declared attack that holds, specimen silent | HELD | INCONCLUSIVE |
| Observed attempt the path accepted and Carbon's own gate refuses | BREACH | BREACHED, FAILING_TRIGGER |
| Observed attempt the path refused and Carbon would admit and run | WRONGFUL_REFUSAL | BREACHED, FAILING_TRIGGER |
| Observed attempt the path refused and Carbon admits but would not run here (an unserved backend), or the family cannot tell why a path refused (code runs) | UNDETERMINED | INCONCLUSIVE |
| Observed attempt where the path and Carbon's gate agree | HELD | HELD, or INCONCLUSIVE with a silent specimen |
| Observed attempt with an unknown path outcome | UNDETERMINED | INCONCLUSIVE |
| Family with no independent gate, no input, or a lane its gate does not judge | NOT_APPLICABLE | NOT_RUN |
| Result (`result`/`output`) carrying protected material, or a path that accepted an attempt naming it | EXPOSURE | BREACHED, OTHER_SIGNAL |
| Attempt naming protected material that the path refused, whose outcome is unknown, or that is declared | PROTECTED_WITHHELD | NOT_RUN |
| Boundary that does not answer | its no-answer verdict | FAILED_INFRA, TIMEOUT or CRASHED |

- Carbon's own gate is `experiment.admit`, the Level 0 permissions, the
  code-run rule (Attacker lane only, D7) or `FrozenRule.score`.
- A held attack whose specimen stays silent is INCONCLUSIVE, because the
  detector cannot vouch for it.
- **Wrongful refusal (review repair, working decision).** A disagreement is
  never reported as agreement. A path that refused what Carbon would admit
  *and run on that path* is BREACHED with FAILING_TRIGGER, as the design
  states for a wrongly refused control. "Would run" is `runnable`: for
  recipes, Carbon rebuilds it and the phase-3 pods serve its backend; for
  predictions, the frozen rule finds them eligible. Where Carbon admits the
  input but would not run it there, or the family cannot tell why the path
  refused (a code run, which the path may refuse for reasons the code-run rule
  does not judge), the reading is UNDETERMINED: no finding, never HELD. The
  alternative, a non-finding reading for every wrongful refusal, is open to
  the lead; it would change only `CONDITION_OF[WRONGFUL_REFUSAL]`.
- **Protected material (review repair, working decision).** Protected material
  is detected by `graphite.tools.protected`. Such an input never reaches a
  boundary or a specimen. Naming protected material is not an exposure: an
  attempt that names it and was refused by the path, whose path outcome is
  unknown, or that was only declared, is PROTECTED_WITHHELD (core NOT_RUN, no
  finding, never scored), because the boundary held or was never asked. An
  exposure is protected material that got through: a path that accepted such
  an attempt, or a result or output that carries it (BREACHED, OTHER_SIGNAL;
  the specimen recorded SILENT with a digest saying it was not run). A
  development finding that names a protected case stays OTHER_SIGNAL in the
  verifier (AT-C), which is a different object from an attempt. The lead may
  confirm or change this; the request side is also refused by Graphite before
  dispatch (`refused_by: graphite`), which AT-C scores HELD.
- A boundary that does not answer is never a pass and never a finding.
- A breach is decided before the output scan, so a staged canary stays a
  breach. Evidence is kept by digest only.
- Conditions are only FAILING_TRIGGER and OTHER_SIGNAL. The core's
  `OracleResult` carries a condition only on BREACHED, so an exposure is
  BREACHED with OTHER_SIGNAL.
- Controls are the core's `Control`, each with its own `check()`. The engine
  runs the trained ones; the core's `held_out_outcomes` reads the held-out
  ones.

### AT-B-D6 — Rebuild

`rebuild` calls `graphite.experiment.admit`.

A backend the phase-3 pods do not serve is still `Rebuilt`, with
`detail.served=False` and Carbon's own `built_record`. It is never run on
those pods.

Every refusal is a core `Unrebuildable` code. The detail begins with Carbon's
own code (`REFUSAL_CODES`): admit's five codes, plus `strategy_too_large`
(experiment's `MAX_STRATEGY_BYTES`), `strategy_not_json`, `seed_invalid` and
`protected_material_named`. Each maps to `not_declarative`,
`unknown_construction`, `refused_by_contract` or `protected_material`. A
contract refusal for a permission Level 0 withholds (`*.not_rebuildable`)
becomes `outside_level`.

`construction_contract_unrecorded` maps to `rebuild_failed_infra`. It means
Carbon's own record is not current: a fault on Carbon's side, never the
construction's, so Carbon can check nothing. `carbon_code(refused)` reads
Carbon's code back out of the detail.

`admission_refusals` returns Carbon's code and the issue codes, and is empty
when Carbon would rebuild the recipe. This is the step-4 adapter's semantics.

### AT-B-D7 — Resource accounting

`CODE_RUN_SECONDS = 600` is a copy of `battery.research.PRACTICE_SECONDS`, as
the step-4 adapter pinned it.

**The code-run rule is this adapter's, for the Attacker only.** An Attacker
code run must ask for a whole number of seconds from 1 to 600, or it is
refused before dispatch; missing seconds counts as unbounded and is refused.
The adapter *defines* this rule (`code_run_refusal`); it does not attack a
Carbon dispatcher. Its declared attacks and the "code_run_seconds lifted"
mutation test the rule itself. It binds only the phase-4 Attacker dispatcher,
which should call `adapter.code_run_refusal` before dispatch (handoff to AT-E;
phase-4 currently carries the same rule as its own copy). It is not the miner
lane's rule (`research_carrier`: any positive allowance or none, by owner
direction) nor Carbon's own worker lane's (40 to 600 seconds), and the miner
`run_python` tool is unchanged.

An observed code run is judged against the rule only when it names the
Attacker lane (`lane == "graphite_attacker"`, `ATTACKER_LANE`). On any other
lane, or with no lane, it is NOT_APPLICABLE: never a finding, never scored. A
run the path refused that the rule admits is UNDETERMINED (the path may refuse
for reasons the rule does not judge). Review repair: before this, any observed
`run_python` without seconds that a path accepted was a false FAILING_TRIGGER.

**Missing predictions.** A partial prediction set scored by the frozen rule
types every omitted case FAILED_INFRA, never a gate failure, and a set with
nothing scored is never eligible. Whether a set that omits *some* cases may
still be eligible is not judged: `FrozenRule.score` gives a set predicting 100
of the 200 PRACTICE cases eligible over the 100 it has. That is the
omitted-case exclusion recorded with the Level 5 seam (D9), a scientific
question. At Level 0 Carbon's fixed program writes every prediction.

**Pod timeouts are a seam.** The pod path (`experiment`'s pod outcome) types a
stage `timeout` CANDIDATE_FAILED, never scored, while the frozen rule types a
missing prediction FAILED_INFRA. Review repair: the family no longer claims "a
timed-out run is FAILED_INFRA" on a stand-in. `pod_timeout_typing` is a Level
0 NOT_RUN seam carrying the open owner question: is a pod timeout FAILED_INFRA
or CANDIDATE_FAILED?

### AT-B-D8 — Adaptive feedback and disclosure

Repeated identical practice probes must give byte-identical feedback, with the
published fields only (`PRACTICE_FEEDBACK_FIELDS`, the summary's
`PRACTICE_SUMMARY_FIELDS`) and the four authority flags. What the intake tells
a miner about results (`BatteryIntake._rule_facts`) must equal
`exam.disclosure(rule)`. Under rule v2 that is the sealed term
(`SEALED_DISCLOSURE`, OWNER-BATTERY-3B-AND-EXPOSURE-01).

These are function-level checks: the probes call the pure `practice.feedback`
and `_rule_facts` with a stand-in `self`. They never reach the stateful
research-task result path (`get_research_result`), so "no state between
probes" holds there by construction, and `_rule_facts` returns
`exam.disclosure(rule)` itself. The family is weak evidence for
`adaptive_feedback_and_state_attacks`. The stateful path is the Level 0
NOT_RUN seam `practice_result_path_state`; probing it needs a running
research session.

### AT-B-D9 — Seams

Levels 1–5 of the ladder are declared NOT_RUN seams. Level 0 has three:
`fresh_cases_rerun` (fresh_attack_confirmation), `pod_timeout_typing` (D7,
with the owner question) and `practice_result_path_state` (D8). Levels 3–5
need participant code and carry the reserved security-owner isolation
decision.
Nothing in a seam is callable. A case a participant's own inference omits is
typed FAILED_INFRA and excluded by `exam.aggregate`, so it becomes an attack
surface only at Level 5. The seam records it rather than raising a Level 0
finding: Carbon's fixed program writes every prediction at Level 0.

### AT-B-D10 — Pinned copies and what is not read

Every value pinned here is checked against its battery source by a test. A
change in battery therefore fails that test and moves `ADAPTER_VERSION`. The
following are never read or changed: EV5, sealed or confirmation material,
hidden pools, seeds, the construction contract (read only) and the expansion
records (read only through `experiment.recorded_contract`). Panel controls
come from `value.panel.PANELS["ev4"]` only.

Cached reads follow their source: the contract index is keyed by the live
contract digest, and Carbon's admit records by the recorded contract
(`contract_digest`, `record_sequence`). `clear_caches()` drops every cached
read, including the frozen rule, for a long-lived driver starting a new
session.

### Mutations (each turns a named guard red)

| Mutation | Guard |
|---|---|
| The compiler accepts an unknown field | `recipe_surface` |
| The gate admits withheld permissions | `permission_ablation` |
| A `REBUILT_FIELDS` entry is dropped | `rebuild_report` |
| The averaging scorer | `mandatory_failure` |
| The leaky stager | `staged_bytes` |
| A `PROTECTED_MARKERS` entry is removed | the protected-material test |
| `code_run_seconds` is lifted, or battery's allowance is | `resource_accounting`, and the pin test |
| A feedback field is added | `practice_disclosure` |
| FAILED_INFRA counts as a pass | the partial-prediction test |
| A finding outside CONDITIONS is emitted | the condition guard |
| The gate reads its own crash as a refusal | the gate-crash test |
| The engine control reads held-out controls | the trained-split test |
