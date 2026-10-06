# CHALLENGE-MOTOR-05 — Graphite public-practice scoring adapter

**Status:** implementation prepared; merge pending

**Authority:** OWNER-GRAPHITE-TEST-WAVE-01 §3 and §6, the Test Lead's
three-Challenge DEVELOPMENT wave, `VALIDATOR-01`'s ChallengeScoring interface,
and `CHALLENGE-MOTOR-01` and `CHALLENGE-MOTOR-02`.

**Predecessors:** Motor Level 0 construction (#579), the challenge-neutral
Graphite scoring seam (#573), and Cooling's public-practice adapter (#584).
The separate motor score-candidate study (#603) is already merged; it does not
register a Graphite `ChallengeScoring` for Motor.

**Tracking:** one branch and one PR. PR Lead may take over once Codex delivers
the tested head.

## Outcome

Register `electric-motor-magnetics` with `ChallengeScoring` so Graphite can
compile and rebuild Motor's existing declarative Level 0 kernel-ridge recipe,
stage only its pinned public TRAIN and PRACTICE material, run the fixed CPU
practice program on Carbon's pod, and score its predictions on Carbon's host
using Motor's existing DEVELOPMENT exam. Report paired descriptive feedback
against the existing scaffold. This grants no promotion or qualification.

## Scope and working decisions

1. **MOTOR-SCORE-D1 — reuse the Motor rule.** The adapter calls
   `carbon.motor.practice.score_practice`. It does not change the 30 public
   cases, gates, TRAIN scales, components, aggregate, or 60-angle output.
2. **MOTOR-SCORE-D2 — explicit Challenge identity.** Add Motor to the existing
   registry. Shared Graphite code resolves scoring by Challenge token and
   still refuses an unnamed scorer.
3. **MOTOR-SCORE-D3 — public material only.** Stage the paths and files defined
   by Motor's current public practice module. Private pools, the counted
   decision campaign and confirmation sets have no loader on this route.
4. **MOTOR-SCORE-D4 — descriptive comparison.** Compare paired common-case
   errors, report the number of compared cases, and set `promotable: false`.
   No confidence interval or population inference is introduced.
5. **MOTOR-SCORE-D5 — deterministic custody.** Host and pod rebuild records
   bind the same contract, recipe, strategy, staged files, fixed program and
   seed by digest. Unrebuildable or cross-Challenge strategies fail closed.

The scope is Motor's existing two-dimensional, 8-pole/24-slot period and
public DEVELOPMENT practice. This ticket does not change the frozen 8 × 6
decision study, GetDP evidence, Motor score-candidate analysis, Track B
controls, private evaluation, EV5, Battery's live contract, or Launchpad
activation. It does not run paid pods or fresh confirmation cases.

## Acceptance

- [x] Motor is a named registered `ChallengeScoring`; unnamed resolution and
      wrong-Challenge construction are refused.
- [x] The Motor pod and host produce matching, digest-bound rebuild records.
- [x] Only pinned public Motor files can be shipped; protected material is
      refused.
- [x] The adapter reproduces Motor's existing public practice score and gates.
- [x] Comparison is paired, descriptive, and never promotable.
- [x] Existing Battery and Cooling scoring behavior remains intact in affected tests.
- [ ] Focused and affected subsystem tests, quality checks, lessons validation,
      and repository CI pass on the delivered implementation. Local 148-test
      affected suite and quality gate pass; PR CI remains pending.

## Maturity ceiling

SPECIFIED, IMPLEMENTED and TESTED for adaptive public DEVELOPMENT practice
only. No scientific or security qualification, customer acceptance, LIVE,
reward or network authority.

## Hub impact

Primary historical map reference: `challenge.motor.graphite_scoring`.
The Development Hub is retired under the current delivery protocol.

## Human input required

None for the bounded public-practice adapter. Any promotion rule, private or
fresh evaluation, population claim, pod spend, and qualification remains
human owned and fail closed.
