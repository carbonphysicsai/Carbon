## 2026-10-04 — GRAPHITE-ATTACKER-COOLING-L0: cooling's Level 0 attack adapter

**Authority:** OWNER-GRAPHITE-ATTACKER-01 (one adapter per Challenge and
construction level) and the owner's 2026-10-04 approval of full Graphite
testing on battery, cooling and motor (OWNER-GRAPHITE-TEST-WAVE-01..03).
Engineering decisions inside that scope. No scientific value, threshold, gate,
weighting, grant or contract is chosen here.

**Files:** `carbon/agent_campaign/attack/adapters/cooling.py`,
`carbon/agent_campaign/attack/adapters/__init__.py` (one `BUILTIN` entry),
`tests/cpu/test_attack_cooling_adapter.py`,
`tests/invariants/test_attack_store_unreachable.py` (one numpy-free test),
`carbon/challenge_pipeline/lessons/2026-10-05-attacker-cooling-level0-adapter.json`.

### COOL-L0-D1 — Base and shape

The branch is built on #584 (`codex/cooling-scoring-adapter` at 4332ad6fe,
which already carries main with #569), which adds
cooling's `ChallengeScoring`, makes `phase4 run` take an explicit
`--challenge` and threads the Challenge through the attack provider and pods.
The adapter reuses that scoring (`scoring_for("chip-cold-plate")`, its frozen
public PRACTICE rule and its dry-run refusal fixture) instead of a scorer of
its own. Nothing in the neutral core, `graphite/phase4.py`, the pods or
battery's adapter changes.

The adapter has battery's shape (`FamilySpec`, `ControlSpec`, `SeamSpec`,
`Build`, `assess`, the session surface). `assess` is a copy of battery's
reading, kept in cooling's module so the shared modules stay untouched while
#584 is open; extracting it into `attack.adapter` is a follow-up. The oracle also answers a declared seam with `seam_oracle` (NOT_RUN).

### COOL-L0-D2 — Families by check

| Check | Families |
|---|---|
| baseline_and_permission_ablation | `permission_ablation` (every capability the live contract withholds, and one combined with a permitted change) |
| artifact_and_dependency_attacks | `recipe_surface`, `recipe_forgery` |
| adaptive_feedback_and_state_attacks | `practice_disclosure` |
| score_exploitation_and_tail_failures | `mandatory_failure`, `cooling_optimism`, `flow_imbalance_masking`, `pressure_underprediction`, `group_sacrifice`, `regime_screen` |
| resource_and_failure_accounting | `resource_accounting` |
| construction_evaluation_isolation | `staged_bytes` |
| reconstruction_and_recipient_rebuild | `rebuild_identity`, `rebuild_report`, `package_integrity` |
| fresh_attack_confirmation | NOT_RUN seam `fresh_cases_rerun` |

There is no climb ablation: cooling has no Level 1 draft or expansion record,
declared as the Level 1 seam.

### COOL-L0-D3 — The Test Lead's cooling vectors

| Vector | Runs as | Seam (missing owner value) |
|---|---|---|
| False cooling optimism | `cooling_optimism` (an optimistic set scores worse than exact, and the hot group's negative bias is reported); `mandatory_failure` (a face at the inlet is a gate failure) | `optimism_bias_tolerance`: a tolerance on the hot group's signed peak bias |
| Hidden flow imbalance | `flow_imbalance_masking` (a mean-preserving redistribution costs profile error); `recipe_surface` (an undeclared per-channel flow split is refused) | `channel_maldistribution`: a multi-channel or manifold reference and tolerance |
| Under-predicted pressure drop | `pressure_underprediction` (positive but low costs pressure error); `mandatory_failure` (non-positive is a gate failure) | `pressure_bias_and_hydraulic_limit`: a one-sided tolerance and a hydraulic limit |
| Group sacrifice | `group_sacrifice` (the hot group is reported apart and worse than the pooled score) | `group_weighting`: an evidence weighting or per-group tolerance |
| Out-of-regime Reynolds | `regime_screen` (the population screen admits no case above the laminar bound or outside the box) | `regime_applicability`: a policy for queries outside the development population |

Each vector's attack example is HELD at the real boundary and FIRES the
vulnerable specimen; its trained and held-out controls PASS (`COOLING_VECTORS`).
The "hot group" is the frozen rule's important group (reference peak at least
`exam.T_IMPORTANT_C`, a provisional DEVELOPMENT value, copied and checked).
The decision study's own case groups are never read.

**Recorded finding (no breach):** inside the registered input box, a grid and a
random search of the public closed-form screen found no case above the laminar
bound (`RE_LAMINAR_MAX`, 2,000) whose hottest wall stays inside the coolant
model (95 C). The Reynolds rule therefore never refuses an in-box case alone;
the attacks pair the box corner (Re about 2,200) with cases outside the box,
and the mutation that is caught disables the whole screen.

### COOL-L0-D4 — Controls

`CONTROLS_VERSION = carbon.attack.controls.cooling-l0.v1`. Trained controls are
the scaffold recipe, the exact public PRACTICE references, the first PRACTICE
inputs, a code run at the allowance and the pinned TRAIN bytes. Held-out
controls are genuinely different valid inputs: other grid points and the
registered defaults, the references as a float32 model emits them and rounded
to six decimals, conservative sets (half a kelvin warm, two percent more
rise, five percent more pressure drop), the last PRACTICE inputs and the
nominal design, shorter code runs, and TRAIN with CRLF line endings (which the
digest check normalises). A test checks each is canonically distinct from
every trained control of its family, and the engine refuses them by identity,
relabelled or not.

### COOL-L0-D5 — Oracle, rebuild and accounting

The oracle is battery's (AT-B-D5) unchanged in meaning. Rebuild calls
`experiment.admit` with cooling's scoring; every refusal maps to a core
`Unrebuildable` code, `public_material_mismatch`,
`construction_contract_unrecorded` and `backend_not_served` being Carbon's
side (`rebuild_failed_infra`). Note that the strategy schema refuses a
neural-operator or pretrained family structurally (`backbone.unsupported`), so
those read `refused_by_contract`, not `outside_level`. The code-run rule is the
core's one rule (`attack.adapter.code_run_refusal`, #569) at cooling's practice
allowance (`research.PRACTICE_SECONDS`, 600, copied and checked) and binds the
Attacker lane only, as battery's. A `check_design` call's construction is read
through `attack.analysis.design_of`, as battery's.

### COOL-L0-D6 — What is not read

A test records every file the adapter opens (an audit hook) while it runs all
attacks, specimens, controls, held-out outcomes, rebuild and session surface:
none is the decision study, its fixtures, counted CFD, customer material or
anything confirmation, private or sealed, and the public TRAIN and PRACTICE
records are among them. A second test checks that nothing the adapter emits,
nor its source, names a registered sealed identity, scoped or bare.

### COOL-L0-D7 — Grant: proposed, not committed

No grant file is added. Proposed for owner approval, the same shape and
amounts as GRAPHITE-GRANT-PHASE4 (cooling's attacker budget split is
identical: six reserved verify pods USD 1.48, model calls USD 1.93):
`GRAPHITE-GRANT-PHASE4-COOLING`, provider graphite, monetary ceiling USD 10.50,
cleanup allowance USD 0.25, worst-case run cost USD 3.41, three permitted
runs, concurrency 1, maximum runtime 15,600 s, three submissions. `phase4 run`
currently accepts only GRAPHITE-GRANT-PHASE4, so a cooling grant also needs
the runner to accept a per-Challenge grant (or the owner to scope the
existing grant's runs to cooling).

### Mutations (each turns a named guard red)

| Mutation | Guard |
|---|---|
| The gate admits withheld permissions | `permission_ablation` |
| The gate drops an unknown field | `recipe_surface` |
| The recipe token is not checked | `recipe_forgery` |
| A feedback field is added | `practice_disclosure` |
| Eligibility ignores gates | `mandatory_failure` |
| The hot group's peak bias is dropped | `cooling_optimism` |
| The profile is graded by its mean | `flow_imbalance_masking` |
| Pressure is left out of the score | `pressure_underprediction` |
| The hot group is pooled | `group_sacrifice` |
| The population screen is disabled | `regime_screen` |
| The code-run allowance is lifted, or FAILED_INFRA counts as a pass | `resource_accounting` |
| Cooling's practice allowance is lifted | the pin test |
| The stager adds labelled PRACTICE records | `staged_bytes` |
| The recipe digest drops the settings | `rebuild_identity` |
| A `REBUILT_FIELDS` entry is dropped | `rebuild_report` |
| The material digest is not checked | `package_integrity` |
| A protected marker is removed | the protected-material test |
| A finding outside CONDITIONS is emitted | the conditions test |
| The gate reads its own crash as a refusal | the gate-crash test |
| The engine control reads held-out controls | the trained-split test |
