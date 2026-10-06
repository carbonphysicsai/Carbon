# CHALLENGE-MOTOR-07 — Interface-v1 validator adapter

**Status:** working contract; implementation and checks pending

**Authority:** `VALIDATOR-01_challenge_neutral_validator.md` Interface v1,
`CHALLENGE-MOTOR-01_development_exam.md`,
`CHALLENGE-MOTOR-02_launchpad_level0.md`,
`CHALLENGE-MOTOR-05_graphite_practice_scoring.md`, and
OWNER-GRAPHITE-TEST-WAVE-01 §§3,6.

**Predecessors:** Motor Level-0 construction and public practice scoring are
merged. The Cooling Interface-v1 adapter provides the existing pattern. The
Graphite `MotorScoring` is not the validator `ChallengeAdapter`.

**Tracking:** one branch and one PR. PR Lead may take over after Codex pushes
the tested head. Coordination: [SCORING-ARCH-01 comment](https://github.com/carbonphysicsai/Carbon/issues/643#issuecomment-6021728006).

## Outcome

Register one Motor `ChallengeAdapter` for the exact `electric-motor-magnetics`
Level-0 contract digest. The neutral validator will strictly admit a Motor
strategy, rebuild its registered deterministic kernel-ridge recipe on the
digest-pinned public TRAIN records, and score all 30 fixed public PRACTICE
records with Motor's existing DEVELOPMENT exam. Operator custody contains
references, predictions, per-case gates and scores. The miner receives only an
allow-listed aggregate outcome. This is adaptive public DEVELOPMENT evidence,
not protected confirmation or official evaluation.

## Scope and working decisions

1. **MOTOR-VAL-D1 — exact public practice only.** The sole preparable batch
   kind is `public_practice`; its cases are the existing pinned PRACTICE file.
   Reference ingestion accepts only full records equal to that file, including
   provenance, outputs and checks. A plausible caller-supplied replacement is
   not reference authority. Private roles remain reserved and unprepared.
2. **MOTOR-VAL-D2 — existing science only.** Reuse Motor's registered
   `compile_recipe`, `rebuild`, `exam.scales_from_train`, `score_case` and
   `aggregate`, including the challenge-neutral missing-prediction coverage
   gate. Do not add torque/ripple acceptance values or adopt the prospective
   45/30/25 Score Pack.
3. **MOTOR-VAL-D3 — custody and disclosure.** Persist owner-only batches,
   references, submissions and operator score records. Return only score,
   eligibility and descriptive counts to the submitter. No case, prediction,
   label, recipe, private identity, reward or qualification reaches the miner.
4. **MOTOR-VAL-D4 — fault authority.** Candidate-caused rebuild/predict or
   non-finite scoring faults require an explicit registered candidate-fault
   policy; the adapter neither invents retry/refund nor converts them into a
   scientific score. Unexpected failures remain typed infrastructure failures.
5. **MOTOR-VAL-D5 — reuse.** Reuse or extract the existing public-practice
   custody mechanics behind a Challenge-parameterized seam. No Motor or
   Battery literal enters shared code. Preserve Cooling's existing store
   behavior and operator schema.

## Acceptance

- [ ] Registration binds the exact Motor contract/version and digest-pinned
      rule and implementation identities.
- [ ] Before explicit complete reference ingestion and pool opening, Motor
      evaluation returns typed `UNAVAILABLE` and no score.
- [ ] Invalid Motor recipes are `INVALID_CONSTRUCTION`; wrong-Challenge or
      unserved contracts are refused by neutral dispatch.
- [ ] Altered, duplicated or foreign public reference records are refused;
      restart preserves exact reference custody.
- [ ] A valid submission deterministically scores all 30 public cases using
      the existing Motor gates and aggregate. A missing prediction is charged
      as the registered schema gate, not excluded as infrastructure.
- [ ] Miner outcome is allow-listed; operator records are owner-only; the
      reserved Motor confirmation role cannot be prepared.
- [ ] Candidate faults follow a registered versioned policy with no adapter
      retry/refund; real infrastructure faults stay typed.
- [ ] Battery and Cooling adapter behavior remains covered; focused,
      applicable subsystem and repository acceptance checks pass.

## Explicit exclusions and maturity ceiling

No fresh or protected cases, hidden seed, counted GetDP campaign, new solver
execution, Graphite promotion, customer acceptance, LIVE authority, weights,
reward or qualification. At most SPECIFIED, IMPLEMENTED and TESTED in bounded
public DEVELOPMENT scope. Fresh confirmation population, protected scoring,
scientific qualification, security acceptance and any spend stay human-owned
and fail closed.

## Validation and hub impact

Focused and affected canonical test commands/results will be recorded here
before handoff. The Development Hub is retired by OWNER-WORKFLOW-SPEED-01;
there is no Hub mutation for this ticket.
