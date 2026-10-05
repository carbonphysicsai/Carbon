# CHALLENGE-AI-COOLING-09 — PB-ADV / Mode X for the periodic-cell Cooling model

**Status:** implementation and bounded host validation complete; canonical
repository CI and delivery handoff pending

**Authority:** OWNER-GRAPHITE-TEST-WAVE-01 section 4, the Test Lead's Cooling
item 4, `Design_Specs/Challenge_Admission.md`, and
`Design_Specs/Specialist_Bank.md`'s PB-ADV definition.

**Predecessors:** Cooling Level 0 (#566), the Challenge-neutral design-search
seam, Cooling public-practice scoring (#584), and the Cooling Graphite attack
adapter (#587). The adapter and its constructed controls are neighboring work;
this ticket does not duplicate them.

**Tracking:** one branch and one PR. PR Lead may take over after the author
pushes the reviewable head.

## Outcome

Serve `PB-ADV` through Cooling's existing `SearchAdapter` instead of raising
`pb_adv_not_served`. Under the same declared DEVELOPMENT model, candidate
space, conditions, query budget and reference budget, Mode X:

1. queries only declared, unique design-condition points through the existing
   attempt-accounted model oracle;
2. ranks predicted-feasible points by their smallest supplied-limit-normalized
   constraint margin;
3. commits at most the caller-supplied verification budget of exact points
   before reference access;
4. verifies only those committed points through the existing classified
   reference session; and
5. reports false-feasible findings, unavailable evidence and accounting under
   the existing non-qualification claims.

The mechanism chooses no attack count, grid, conditions, physical threshold,
population or pass policy. Those arrive in a separately frozen request. A
missing or non-positive verification budget fails closed.

## Scope

KEEP the periodic straight-channel cell, existing customer decision contract,
prediction-validity gates, attempt-accounted oracle, classified reference
session, commitment custody and generic registered search methods. REPAIR only
Cooling's mode dispatch, point selection, commitment validation and job
construction. WRAP the already available predicted die and hydraulic margins;
do not clone Battery's optimizer.

Out of scope:

- changing the frozen eight-design by six-condition study, its limits, models,
  results or counted CFD evidence;
- running counted CFD, a fresh confirmation set, a Graphite pod or any paid
  compute;
- inventing K, a new grid, an acceptance tolerance, a population reliability
  claim or a scientific pass threshold;
- changing the Cooling Graphite attacker adapter or Track-B constructed
  controls from PR #587;
- manifolds, transient loads, chiplet maps, a physical rig, customer
  acceptance, qualification, LIVE, rewards or chain action;
- EV5, journal sequence 14 or Battery's live contract.

## Working decisions

- **COOL-PBADV-D1 — preserve the decision-contract identity.** The registered
  PB-INV contract and its tie-policy text remain byte-for-meaning unchanged.
  PB-ADV's point-order policy is adapter/search behavior, not a retroactive
  rewrite of the completed decision study.
- **COOL-PBADV-D2 — reuse the neutral Mode-X rule.** Rank only
  predicted-feasible queried points by the minimum of die-temperature margin
  divided by `max(1, abs(supplied die limit))` and hydraulic-power margin
  divided by `max(1, abs(supplied hydraulic limit))`; then design tuple,
  condition tuple and binding-constraint name. This is the existing neutral
  method's deterministic ordering and adds no scientific tolerance.
- **COOL-PBADV-D3 — K is the required verification budget.** Mode X commits no
  more points than the request's positive integer `verification_budget`. No
  default K exists. Unlike PB-INV, PB-ADV does not require K to cover every
  condition because each proposal is one exact design-condition point.
- **COOL-PBADV-D4 — commit exact evidence.** Every committed point must be
  declared, uniquely queried successfully, predicted feasible, and carry the
  recomputed margin and binding constraint. A mismatch fails before a
  commitment file is written.
- **COOL-PBADV-D5 — reference access remains downstream.** PB-INV verifies the
  committed design at every condition. PB-ADV verifies each committed point
  once. Both use the existing write-once commitment and classified reference
  session; the search layer receives no reference object.
- **COOL-PBADV-D6 — descriptive DEVELOPMENT evidence only.** Finding a
  false-feasible point is evidence of a model hole in the declared request.
  Finding none does not prove safety, qualification, reliability or coverage
  outside that finite search.

## Acceptance

- [x] Cooling advertises both `PB-INV` and `PB-ADV`; an unknown mode fails
      closed.
- [x] The registered fixed-grid baseline and `coarse_to_fine` method both serve
      Cooling PB-ADV without a Challenge-specific branch in shared code.
- [x] Selection order is deterministic and matches the documented margin,
      design, condition and binding-constraint tie policy.
- [x] A PB-ADV request may use any positive K; selections above K, duplicate or
      unqueried points, infeasible points and altered prediction evidence are
      refused before persistence.
- [x] PB-ADV reference jobs are exactly the committed point set; PB-INV keeps
      all-condition verification unchanged.
- [x] Reference access cannot occur before a valid write-once commitment.
- [x] Existing PB-INV behavior and frozen study configuration remain covered.
- [ ] Focused tests, applicable design-search/customer-decision regressions,
      lessons validation, quality and repository CI pass at the delivered head.

## Baseline evidence

Local canonical execution was unavailable before implementation: the Windows
WSL shim was denied, the named Docker WSL distribution was absent, and Git
Bash could not satisfy the wrapper's exact root identity because MSYS and Git
used different path forms. Available host Python interpreters lacked pytest.
Each attempt has its own lessons entry. No test failure was observed because no
test was collected. The normal pinned GitHub canonical lanes remain required
for delivery.

## Current validation evidence

- The noncanonical analytical PB-ADV smoke served both fixed grid and the
  registered `coarse_to_fine` method at K=2, then persisted and reference-
  evaluated exactly two committed points.
- The focused customer-decision regression passed all 22 tests.
- The final affected-subsystem matrix passed 79 tests across Cooling PB-INV and
  PB-ADV, the decision study, Cooling and neutral Track B, and Battery's shared
  design-search commitment conformance. One Windows raw-byte closeout hash test
  was deselected; canonical Linux CI retains it.
- Focused Ruff passed. Black's in-process API confirmed both changed Python
  files exactly formatted after two host launcher stalls.
- The analytical fixture was regenerated from the unchanged study
  configuration and final LF-normalized code. All four arms still select d03;
  it remains explicitly `ANALYTICAL_FIXTURE` and makes no learned-model
  advantage or population claim. Counted CFD evidence was untouched.
- The lessons validator passed before the final pass records were appended;
  every subsequent execution also has one schema-shaped record. Canonical CI
  must validate the complete final lessons set.

## Maturity ceiling

At most SPECIFIED, IMPLEMENTED and TESTED for a bounded DEVELOPMENT attack
search mechanism. Not scientifically or security qualified. No customer,
population-reliability, production, LIVE, reward or network claim.

## Hub impact

Primary historical map reference: `challenge.ai_cooling.pb_adv`. No Hub source
or derived output changes: the Development Hub is retired by the current
delivery protocol.

## Human input required

None for the bounded mechanism. A future execution must separately supply and
freeze K, candidate/condition sets, model identities, budgets, reference
allocation and analysis policy, and must obtain any applicable compute or
fresh-confirmation authority. Until then no such execution is dispatched.
