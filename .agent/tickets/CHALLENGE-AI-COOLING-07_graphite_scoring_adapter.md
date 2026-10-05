# CHALLENGE-AI-COOLING-07 — Graphite public-practice scoring adapter

**Status:** implementation and canonical validation complete; exact-head
delivery review, approval and merge gates pending

**Authority:** OWNER-CHALLENGE-FOUNDATION-01,
OWNER-CHALLENGE-DESIGN-01, OWNER-GRAPHITE-TEST-WAVE-01 section 3, and
OWNER-LAUNCH-PORTFOLIO-02.

**Predecessor:** `CHALLENGE-AI-COOLING-06_launchpad_level0.md`; Cooling Level 0
merged in PR #566.

**Tracking:** one branch and one PR. PR Lead may take over after the author
pushes the reviewable head.

## Outcome

Register `chip-cold-plate` with the existing challenge-neutral
`ChallengeScoring` port so Graphite can:

1. compile and independently rebuild the existing Level-0 kernel-ridge recipe;
2. ship only the digest-pinned public TRAIN/PRACTICE/calibration material;
3. execute the existing fixed CPU practice program on Carbon's pod;
4. score returned predictions on Carbon's host with the existing cold-plate
   DEVELOPMENT gates and aggregate; and
5. report a descriptive paired difference from the existing scaffold without
   conferring promotion, qualification, official-exam, reward or LIVE authority.

Shared code continues to receive the Challenge scoring explicitly. Once two
scorings are registered, an unnamed scoring request must fail closed.

## Scope

KEEP the exact Cooling Level-0 construction contract, public material digests,
practice program, case gates, TRAIN-normalized three-component error, important
region and scaffold recipe. WRAP them behind the already merged neutral pod
scoring interface.

Out of scope:

- a general Cooling validator deployment or private scoring pool;
- any new official Score Pack, promotion threshold, confidence interval,
  reliability claim or scientific qualification;
- PB-ADV/Mode X, Track-B constructed controls or fresh confirmation cases;
- changing the frozen 8-design × 6-condition decision study;
- EV5, journal sequence 14, Battery's live contract, rewards or chain effects.

## Working decisions

- **COOL-SCORE-D1 — reuse the public rule.** The adapter calls
  `carbon.cold_plate.practice.score_practice`; it does not restate or change a
  gate, threshold, component, case, scale or aggregate.
- **COOL-SCORE-D2 — descriptive comparison only.** The paired common-case mean
  error difference is reported with no confidence interval. It is always
  `promotable: false`; a promotion rule requires separate scientific authority.
- **COOL-SCORE-D3 — explicit Challenge selection.** Cooling becomes the second
  registered scoring. Shared callers may not silently default to Battery or
  Cooling when no Challenge is named.
- **COOL-SCORE-D4 — public data only.** Only the registered TRAIN, PRACTICE and
  calibration files may be shipped. Counted CFD and confirmation evidence have
  no loader on this path.
- **COOL-SCORE-D5 — deterministic rebuild.** The pod and host compile the same
  strategy under the recorded contract and bind the recipe, plan, staged files,
  program and seed by digest before execution.
- **COOL-SCORE-D6 — downstream evaluation stays closed.** The Launchpad
  campaign's `evaluate_frozen` remains `cooling_validator_not_served`; this
  ticket is Graphite public-practice scoring, not a private validator.

## Acceptance

- [x] Cooling is a named registered `ChallengeScoring`; unnamed resolution is
      refused once Battery and Cooling are both present.
- [x] The adapter rebuild record contains every neutral comparison field and
      is stable across host/pod routes.
- [x] Only the pinned public Cooling files pass the protected-data ship check.
- [x] The existing public practice score and gate semantics are unchanged.
- [x] The comparison reports paired descriptive differences, no interval and
      no promotable result.
- [x] Battery's named scoring behavior remains unchanged.
- [x] Focused tests, applicable Graphite regression tests, lint and canonical
      acceptance pass at the delivered head.

Engineering evidence: the final selected canonical matrix passed all 498 tests,
and the exact-main changed-path quality gate reported Ruff 0/776 and Black
0/68 debt entries across 26 changed Python files. These checks establish only
the maturity ceiling below; delivery completion still depends on the current
exact-head review, approval, merge and external-receipt protocol.

## Maturity ceiling

At most SPECIFIED, IMPLEMENTED and TESTED for adaptive public DEVELOPMENT
practice. This ticket cannot establish a qualified exam, population
reliability, security qualification, customer acceptance, production or LIVE.

## Hub impact

None. The Development Hub is retired by the current delivery protocol.

## Human input required

None for this bounded engineering adapter. Any promotion rule, private/fresh
evaluation design, attack budget, confirmation population and compute spend
remain separately human-owned and fail closed.
