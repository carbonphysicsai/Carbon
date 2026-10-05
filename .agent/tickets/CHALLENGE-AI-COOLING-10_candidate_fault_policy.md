# CHALLENGE-AI-COOLING-10 — registered candidate-fault policy

**Status:** implementation and bounded local validation complete; canonical
repository CI and PR Lead delivery pending

**Authority:** Test Lead follow-up after PR #586, `VALIDATOR-01` Interface v1,
`CHALLENGE-AI-COOLING-08`, and Carbon invariant 7 (infrastructure failure is
not scientific failure).

**Predecessors:** the Challenge-neutral validator (#559), Cooling Interface v1
(#586), the versioned Graphite pod-attribution policy (#580), and the Cooling
Level-0 attack adapter (#587).

**Tracking:** one branch and one PR. PR Lead may take over after the author
pushes the reviewable head.

## Outcome

Register and digest-pin the DEVELOPMENT policy that classifies a
candidate-triggered Cooling rebuild exception, prediction exception, or
non-finite aggregate score. The existing classification remains
`FAILED_INFRA / adapter_failure`; every result names the exact policy version,
digest and fault kind so Track A can test the selective-crash/retry surface.

The policy also records what that classification means at the lifecycle seam:
the validator itself performs no retry, charge or refund; a surrounding
registered A7 lifecycle may retry the same attempt within its existing attempt
budget without a new charge, and terminal charged `FAILED_INFRA` receives the
existing full remaining-balance refund. If the attempt was never charged there
is no fee event. This ticket does not add a retry loop or fee service to the
standalone DEVELOPMENT validator.

## Scope

- Add `cooling-candidate-fault-v1.json` beside the existing Graphite
  attribution policies and pin it in their registry.
- Add strict load-time schema, digest, Challenge, safe-classification and
  retry/refund invariants.
- Type the three Cooling candidate-fault sites and carry the policy record in
  the neutral result envelope.
- Expose and exercise the registered record through Cooling's existing Track A
  resource/failure-accounting family.
- Add focused policy, validator and attacker regression tests and update the
  bounded Cooling DEVELOPMENT documentation.

Out of scope:

- changing the chosen classification, A7 attempt budget, fee amounts or
  customer/scientific policy;
- running a Graphite pod, counted CFD, a fresh confirmation set or paid
  compute;
- changing Cooling's frozen study, physical gates, score or construction
  contract;
- Motor scoring, which is the next separate ticket;
- EV5, journal sequence 14 or Battery's live contract.

## Working decisions

- **COOL-CFP-D1 — data owns the disposition.** The validator reads the current
  Challenge policy from a digest-pinned registry. A future semantic change is
  a new registered policy version, never an edit to dispatch constants.
- **COOL-CFP-D2 — invariants stay in code.** No policy may turn an adapter
  exception or non-finite value into `SCORED`, scientific failure, candidate
  success, qualification or reward. The current schema admits only
  `FAILED_INFRA`.
- **COOL-CFP-D3 — faults are closed and typed.** V1 covers exactly
  `rebuild_exception`, `predict_exception` and `non_finite_score`. Exception
  text is never returned or persisted in the result.
- **COOL-CFP-D4 — retry/refund is an implication, not local execution.** The
  policy records the existing A7 interpretation while declaring that the
  validator performs neither retry nor fee mutation. No retry count is
  invented here.
- **COOL-CFP-D5 — attackability remains visible.** The Level-0 Cooling
  attacker reads the registered record and has an attack input for every V1
  fault kind; a mutation that substitutes candidate/scientific treatment must
  turn its guard red.

## Acceptance

- [x] The exact current Cooling policy is registered and digest-pinned.
- [x] Missing, altered, unregistered, cross-Challenge or unsafe policies fail
      closed at load.
- [x] Rebuild exceptions, prediction exceptions and non-finite scores produce
      `FAILED_INFRA / adapter_failure` with the exact policy record and no
      exception text or score.
- [x] The policy states the retry/refund implications and the validator's
      non-ownership of both actions.
- [x] Cooling's attacker surface exposes the policy and tests all three fault
      kinds through resource/failure accounting.
- [x] Existing generic adapter-failure behavior and Battery remain unchanged.
- [x] Focused tests, applicable subsystem checks, lessons validation and
      quality pass on the exact implementation tree.
- [ ] Repository CI passes on the delivered PR head.

## Local validation evidence

- The exact LF-native implementation tree passed 150 focused policy, Cooling
  validator and Cooling attacker tests in 68.09 seconds.
- After removing Cooling fault literals from the shared loader, the exact
  implementation tree passed the full 150-test focused suite in 47.12 seconds.
- The affected validator, Battery compatibility, Cooling attacker and existing
  pod-attribution subsystem matrix passed 317 tests in 146.66 seconds.
- Focused Ruff passed and Black left all eight changed Python files unchanged.
- The challenge-pipeline validator accepted 7 records and 257 lessons with no
  pending decision before the final pass records were appended; canonical CI
  validates the delivered complete set.

## Maturity ceiling

At most SPECIFIED, IMPLEMENTED and TESTED for a DEVELOPMENT classification
policy and attack seam. Not security/scientific qualification, customer
acceptance, LIVE, reward or network authority.

## Hub impact

Primary historical map reference: `challenge.ai_cooling.validator`. No Hub
source or derived output changes: the Development Hub is retired by the
current delivery protocol.

## Human input required

None for registering the existing behavior. Any future change to its
classification, lifecycle retry eligibility or refund semantics requires a
new policy version and the applicable owner authority.
