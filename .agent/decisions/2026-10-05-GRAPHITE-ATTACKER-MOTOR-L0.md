## 2026-10-05 — GRAPHITE-ATTACKER-MOTOR-L0: motor's Level 0 attack adapter

**Authority:** OWNER-GRAPHITE-ATTACKER-01 (one adapter per Challenge and
construction level) and the owner's 2026-10-04 approval of full Graphite
testing on battery, cooling and motor (OWNER-GRAPHITE-TEST-WAVE-01..03).
Engineering decisions inside that scope. No scientific value, threshold, gate,
weighting, grant, scoring or contract is chosen here.

**Files:** `carbon/agent_campaign/attack/adapters/motor.py`,
`carbon/agent_campaign/attack/adapters/__init__.py` (one `BUILTIN` entry),
`tests/cpu/test_attack_motor_adapter.py`,
`tests/invariants/test_attack_store_unreachable.py` (one assertion, still
numpy-free),
`carbon/challenge_pipeline/lessons/2026-10-05-attacker-motor-level0-adapter.json`.

### MOTOR-L0-D1 — Base and shape

The branch is stacked on `claude/attack-adapter-cooling-l0` (#587, itself on
#584). #584 makes `phase4 run` and `phase4 prelive` take an explicit
`--challenge` and resolve the Challenge's `ChallengeScoring` before anything
starts, which is the path that gives motor its typed refusal; #587 already
registers cooling in `BUILTIN` and adds the numpy-free registry test this
branch extends. Basing on main would have meant re-touching both and
conflicting with #587. Nothing in the neutral core, `graphite/phase4.py`, the
pods, `carbon/motor/*`, the design-search code, `uv.lock`, or the battery and
cooling adapters changes.

The adapter has cooling's shape (`FamilySpec`, `ControlSpec`, `SeamSpec`,
`Build`, `assess`, the session surface). `assess` is a third copy of battery's
reading; extracting it into `attack.adapter` stays a follow-up.

### MOTOR-L0-D2 — No motor scoring: what the adapter reads instead

No `ChallengeScoring` is registered for motor:
`challenge_validator.scoring.scoring_for("electric-motor-magnetics")` raises
`ScoringUnavailable("challenge_scoring_not_registered")`. No scoring is
invented here. Instead:

- the scoring families attack motor's own public PRACTICE rule,
  `carbon.motor.practice.score_practice` (the exam's typing, gates, mean and
  ripple components and aggregate, normalised by public TRAIN), the rule the
  motor practice provider already uses (#579);
- Carbon's typed rebuild is a build record made from the same public pieces a
  scoring would use: the contract gate and motor's compiler
  (`challenge_contracts.compile_submission`), `practice.staged_files` and
  `practice.PROGRAM`, under the newest expansion record. It carries every
  `REBUILT_FIELDS` entry and is compared with the shared
  `scoring.rebuild_differences`. It is marked `served: False` with the
  registry's refusal code: no pod serves motor;
- the session surface's refused recipe (`recipe_outside_contract`) is declared
  in the adapter (a `transolver` backbone), because no motor scoring declares
  one.

A tripwire test fails when a motor scoring is registered, so the adapter is
then moved to `experiment.admit`, as cooling's is.

### MOTOR-L0-D3 — Families by check

| Check | Families |
|---|---|
| baseline_and_permission_ablation | `permission_ablation` (every capability the live contract withholds, and one combined with a permitted change) |
| artifact_and_dependency_attacks | `recipe_surface` (including an undeclared iron B-H curve and skew angle), `recipe_forgery` |
| adaptive_feedback_and_state_attacks | `practice_disclosure` |
| score_exploitation_and_tail_failures | `mandatory_failure`, `ripple_omission`, `ripple_phase`, `ripple_scaling`, `saturation_optimism`, `population_screen` |
| resource_and_failure_accounting | `resource_accounting` |
| construction_evaluation_isolation | `staged_bytes` |
| reconstruction_and_recipient_rebuild | `rebuild_identity`, `rebuild_report`, `package_integrity` |
| fresh_attack_confirmation | NOT_RUN seam `fresh_cases_rerun` |

### MOTOR-L0-D4 — The Test Lead's motor vectors

| Vector | Runs as | Seam (missing owner value) |
|---|---|---|
| Flat curve with the right mean | `ripple_omission`: a flat curve at each case's own mean passes every gate and costs ripple error (specimen: a mean-only rule) | `ripple_amplitude_bias_tolerance`: a one-sided ripple-amplitude tolerance |
| Phase-shifted ripple | `ripple_phase`: a quarter-period, one-step or half-period shift costs ripple error, angle by angle (specimen: a phase-blind rule comparing sorted ripple values) | `ripple_phase_tolerance`: a rotor-angle phase tolerance |
| Flipped period or orientation | `ripple_phase` (the period swept the other way); `mandatory_failure` (a sign-flipped curve breaks the motoring-mean gate); `population_screen` (a generating-quadrant current angle or reversed current is outside the box) | none: registered gates, score and box cover it whole |
| Saturation-blind linear iron | `saturation_optimism`: the important group's mean torque grown in proportion to the current density above the important floor scores worse and is reported as a positive `important_mean_bias_nm` (specimen: a rule rewarding promised torque with the bias dropped); `population_screen` (the benchmark machine's own 20.3 A/mm^2 is outside the box) | `saturation_bias_tolerance`: a tolerance on the important group's signed mean-torque bias |
| Ripple scaled to game the normalised error | `ripple_scaling`: halved, doubled, tenfold ripple with its shape kept costs ripple error, because the rule normalises by a fixed public TRAIN scale (specimen: a rule normalising each ripple by its own amplitude) | `ripple_amplitude_bias_tolerance` |

Each vector's attack example, and each further attack it maps to, is HELD at
the real boundary and FIRES the vulnerable specimen; its trained and held-out
controls PASS (`MOTOR_VECTORS`). The "important group" is the exam's own
(current density at least `exam.J_IMPORTANT`, a provisional DEVELOPMENT value,
copied and checked). The attack magnitudes (a 10 % mean, a quarter period, a
halved ripple) are attack inputs, not thresholds; no breach rule reads one.

### MOTOR-L0-D5 — Controls

`CONTROLS_VERSION = carbon.attack.controls.motor-l0.v1`. Trained controls are
the scaffold recipe, the exact public PRACTICE references, the first PRACTICE
inputs, a code run at the allowance and the pinned TRAIN bytes. Held-out
controls are genuinely different valid inputs: other grid points and the
registered defaults, the references as a float32 model emits them and rounded
to six decimals, conservative sets (every mean two percent low, the important
group's one percent low), the last PRACTICE inputs and the benchmark nominal
design, shorter code runs, and TRAIN with CRLF line endings. A test checks
each is canonically distinct from every trained control of its family, and
the engine refuses them by identity, relabelled or not. The measured
wrongful-rejection rate is 0.0 for all fifteen families.

### MOTOR-L0-D6 — Seams (NOT_RUN, never a pass)

| Seam | Check | Level | Reserved |
|---|---|---|---|
| `fresh_cases_rerun` | fresh_attack_confirmation | 0 | owner: the fresh evaluator-held case set's size and sampling law, and the attack budget (both `None` in the admission study) |
| `pod_scoring_not_registered` | reconstruction_and_recipient_rebuild | 0 | owner: a registered motor `ChallengeScoring` |
| `ripple_amplitude_bias_tolerance` | score | 0 | owner (science) |
| `ripple_phase_tolerance` | score | 0 | owner (science) |
| `saturation_bias_tolerance` | score | 0 | owner (science) |
| `paired_repeat_gate` | score | 0 | owner: the evaluator's duplicate-case design (public PRACTICE has none) |
| `pod_timeout_typing` | resource | 0 | owner: FAILED_INFRA or CANDIDATE_FAILED |
| `practice_result_path_state` | adaptive | 0 | — (needs a running research session) |
| `level_1_physical_structure_and_objective` … `level_5_custom_inference` | various | 1–5 | Levels 3–5: security owner (participant-code isolation) |

### MOTOR-L0-D7 — The phase-4 dry run and pre-live gate

`python -m carbon.agent_campaign.graphite.phase4 run --root <tmp> --challenge
electric-motor-magnetics --dry-run` and `... prelive --root <tmp> --challenge
electric-motor-magnetics` each print
`{"status": "REFUSED", "reason_code": "challenge_scoring_not_registered"}` and
exit 2, before writing anything. What unblocks them: a motor
`ChallengeScoring` registered in `challenge_validator.scoring` (its
`built_record`, `refusal`, `backend` = numpy, a `frozen_rule` over the public
PRACTICE rule with a descriptive, non-promoting comparison, the baseline
strategy, the dry-run variant and refused fixtures, synthetic predictions and
the public data paths), then a phase-4 grant that covers motor (the runner
accepts only GRAPHITE-GRANT-PHASE4). No grant is proposed here.

### MOTOR-L0-D8 — What is not read

A test records every file the adapter opens (an audit hook) while it runs all
attacks, specimens, controls, held-out outcomes, rebuild and session surface:
the only evidence files opened are the public TRAIN and PRACTICE records and
the public calibration document their loader checks; none is the private
pool's commitment (`pools.json`), the decision study, its references, counted
or pilot GetDP runs, customer material or anything sealed. A second test
checks that nothing the adapter emits, nor its source, names the registered
motor pool commitment or any other sealed identity.

### Mutations (each turns a named guard red)

| Mutation | Guard |
|---|---|
| The gate admits withheld permissions | `permission_ablation` |
| The gate drops an unknown field | `recipe_surface` |
| The recipe token is not checked | `recipe_forgery` |
| A feedback field is added | `practice_disclosure` |
| Eligibility ignores gates | `mandatory_failure` |
| The motoring-mean gate always passes | the sign-flip guard |
| Ripple is left out of the score | `ripple_omission` |
| Ripple is compared by sorted values | `ripple_phase` |
| Ripple is normalised by its own amplitude | `ripple_scaling` |
| The important group's mean bias is dropped | `saturation_optimism` |
| The geometry screen, or the whole screen, is disabled | `population_screen` |
| The code-run allowance is lifted, or FAILED_INFRA counts as a pass | `resource_accounting` |
| Motor's practice allowance is lifted, or the important floor moves | the pin test |
| The stager adds labelled PRACTICE records | `staged_bytes` |
| The recipe digest drops the settings | `rebuild_identity` |
| A `REBUILT_FIELDS` entry is dropped | `rebuild_report` |
| The material digest is not checked | `package_integrity` |
| A protected marker is removed | the protected-material test |
| A finding outside CONDITIONS is emitted | the conditions test |
| The gate reads its own crash as a refusal | the gate-crash test |
| The engine control reads held-out controls | the trained-split test |
