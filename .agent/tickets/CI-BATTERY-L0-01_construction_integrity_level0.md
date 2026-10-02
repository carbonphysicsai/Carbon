# CI-BATTERY-L0-01: battery construction integrity (Track A), Level 0 harness

Owner authority: the owner, in chat on 2026-10-02:

> Start the construction-integrity attack tests for battery as long as no one
> else has. Communicate with all lanes

Protocol: `Design_Specs/Challenge_Admission.md` §3 (Track A), under
OWNER-CHALLENGE-ADMISSION-01 as amended on 2026-10-01. Internal DEVELOPMENT
protocol: not mainnet, not a qualification gate, not a security audit.

**Primary Development Hub map_ref:** `SYSTEM/AGENT-EXECUTION`,
`HUB_UPDATE_REQUIRED`.

**Status:** slice 2 implemented (engineering evidence only, 2026-10-02):
`carbon/battery/track_a.py`, with tests in `tests/cpu/test_battery_track_a.py`
and evidence in `docs/development/evidence/track-a-battery-l0-2026-10-02/`.
Slice 3 (battery-specific worker attacks against the pinned image) is open.
The pinned C-03 worker image cannot be built in the cloud container, because
TLS interception breaks the image build's downloads; that slice runs in the
CI service lane.

## Claim check (2026-10-02)

Before claiming:
- no open PR, issue or unmerged branch builds Track A attacks for battery;
- `docs/development/mira/level0/study-sheet.json` lists all eight Track A
  checks for battery Level 0 as `NOT_RUN`, `executed: false`;
- GRAPHITE-01 plans an **Attacker** role as its phase 4
  (`docs/development/GRAPHITE_TESTING_AGENT_PLAN.md` §5 and §7). It is not
  started; phase 3 is open as #504.

## Split with GRAPHITE-01 phase 4

This ticket builds the **instrument**. GRAPHITE phase 4 builds the
**attacker agent** that drives it. Concretely:

- **This ticket.** For each Track A family that applies at Level 0, it
  registers:
  - a hand-written attack;
  - a known-vulnerable specimen, showing that the detector can fire;
  - a valid control, measuring wrongful rejection.

  It runs them through the actual isolated battery worker (Docker, pinned
  image), writes the attempt ledger, and reports coverage with untested
  surfaces named.
- **GRAPHITE phase 4.** Agent-generated attempts against the same detectors,
  specimens and ledger. It reuses this harness, and does not rebuild it.

## Scope (Level 0 only)

Level 0 is the current battery recipe and its registered operations: the
permission inventory in `docs/development/mira/level0/permission-inventory.json`.
Level 0 recipes are declarative; no participant executable code runs. So:

| Track A check (`carbon.challenge_readiness.admission.CHECKS`) | At Level 0 |
|---|---|
| `artifact_and_dependency_attacks` | Recipe and submission parser abuse, malformed and nonfinite values, out-of-surface fields, embedded tables or weights in a recipe, refused before build |
| `score_exploitation_and_tail_failures` | Always-abstain, constant, boundary-optimist and subgroup-sacrifice predictors against the gates and the deciding rule; the score-value divergence detector |
| `resource_and_failure_accounting` | Recipes at the edges of the surface against the worker's CPU, memory and deadline envelope; typed `FAILED_INFRA` versus a candidate failure; no retry abuse |
| `construction_evaluation_isolation` | The worker's network, filesystem, canary and evaluator-handle boundary, with canaries; inspected on the real worker, not a helper |
| `adaptive_feedback_and_state_attacks` | What practice feedback, refusal codes and timing reveal; cross-attempt residue in the worker |
| `reconstruction_and_recipient_rebuild` | Rebuild of an attack construction from its record; typed refusal of one Carbon cannot rebuild |
| `baseline_and_permission_ablation` | The legitimate Level 0 baseline under the same budget |
| `fresh_attack_confirmation` | `NOT_RUN`: needs a frozen study sheet and fresh cases (reserved values below) |

Families that need participant executable code (hidden preprocessing,
child processes, custom inference) are not permitted at Level 0. They are
recorded as `NOT_RUN` for this profile, never as a pass. The only test here
is that the construction contract refuses them.

## Reserved; stays HUMAN_INPUT and blocks acceptance, not running

- The attack budget and its monetary ceiling: the science owner and the owner.
- The Level 0 study population and the reconstruction tolerances: the science
  owner.
- The security owner's approval of the threat model, and the isolation scope
  for any hostile executable.
- Who reviews and locks Track A (§3.3).

None of these is invented here. Results are DEVELOPMENT findings. Track A
stays `IN_PROGRESS` at most, and the readiness-record wiring (#477, held)
is not touched.

## Invariants exercised

1, 2, 4, 6, 7 and 13 in `.agent/INVARIANTS.md`; constitution §7.9
(construction never gains evaluator authority).

## Slices

1. Claim, ticket and lane notices (this commit).
2. The attack catalogue and detectors, with a specimen and a control for each
   family, as unit tests.
3. Battery-specific runs against the pinned worker image in the C-03 service
   lane (CI). Two attacks:
   - a canary scan of every staged and exported byte;
   - surface-edge recipes against the worker envelope.
   Until then, isolation is reused evidence, mapped in `track_a.COVERAGE`.
4. The coverage report, findings, docs, Hub event and PR, delivered with
   slice 2.

## Update 2026-10-02: owner values, the combined test and SR-1

- **OWNER-TRACK-A-L0-02.** The owner approved the threat model, the USD 25
  attack budget, the confirmation population, the reconstruction tolerances
  and the review roles. They are frozen in
  `docs/development/evidence/track-a-battery-l0-2026-10-02/study-sheet.json`.
  Track A at Level 0 is INCONCLUSIVE until the scoring rule stops ranking the
  boundary optimist at or above real models: route (a).
- **OWNER-ADMISSION-COMBINED-01.** Construction, attack and value run as one
  admission test per rung, with three separate verdicts. This harness is its
  attack side. GRAPHITE's Constructor and Attacker, the design optimizer
  (Mode X for attack, Mode D for value) and score tuning all run inside it.
- **SR-1** (`docs/development/BATTERY_SCORING_RATIOS_SR1.md`, results in
  `docs/development/evidence/sr1-2026-10-02/`) ended NO_PROMOTION.
  - 27 of 66 ratios catch the optimist without hurting real-model ranking.
  - No ratio of the three existing legs reduces the real-model divergence,
    which stays at 7 conditions on EV4 verification. The next scoring
    candidate needs new information, such as margin-aware decision error.
