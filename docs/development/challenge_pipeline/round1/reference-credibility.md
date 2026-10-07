# Buyer reference credibility — targets, not earned tiers

These additions apply to all eight mock-customer packets under
[REFERENCE-CREDIBILITY-01](../../../../.agent/decisions/2026-10-07-REFERENCE-CREDIBILITY-01.md).
Tool choices are **role-play assumptions**, not verified market share or actual
customer discovery. Confirm the buyer's tool, version and use before engagement.
No benchmark or lab comparison was run for this addition.

| Target | What the buyer requires | What does not establish it |
| --- | --- | --- |
| Tier 1 | Carbon uses the buyer's own reference tool at their exact model/settings: version, parameters, geometry, mesh, boundary conditions, solve and observation conventions | The same product name, governing equation or a default tutorial |
| Tier 2 | Carbon's reference agrees with the buyer's industry-tool workflow on named published benchmarks **and** matched task witnesses, under accepted unit-bearing limits | Successful execution, self-convergence, a vendor capability page, or an unrelated published example |
| Tier 3 | Independent calibrated experiment/lab observations corroborate the reference within accepted uncertainty for the stated buyer use | Solver agreement, fitted calibration traces reused as validation, or a model's unmeasurable internal diagnostic |

Every packet states **Credibility evidence: NOT_DEMONSTRATED** for its new buyer
decision. This does not erase older, separately scoped verification. These
targets are not a runtime maturity enum, qualification artifact or new gate.
The seven offline simulator-design jobs target Tier 2; Battery targets Tier 3
before EV use, with Tier 2 only an interim simulation-screening route. Other
hardware claims trigger the specifically named later Tier 3 requirement.

## Agreement contract to settle before evidence

All new **Acceptance tolerance: HUMAN_INPUT** entries carry recommendations,
not approved acceptance limits. Existing packet numerical controls remain
selected DEVELOPMENT demands; new cross-tool or lab recommendations neither
replace them nor declare them demonstrated. Numeric recommendations are the
mock buyer's error allocation, not vendor guarantees or literature constants.

Freeze both tools' executable/dependency identities and complete case decks,
mesh/refinement rungs, material/parameter laws, excitation, units, coordinate/
phase conventions, observation locations, normalization and extraction code.
Use identical physics and observations, independently converged discretizations,
and retained raw results, failures, uncertainty and comparison scripts. Do not
optimize two different geometries and compare their unrelated best scores.
Published benchmark agreement is a verification rung: chemistry, geometry or
physics absent from it requires additional matched packet witnesses. Document
any purchased model/data access or redistribution restrictions before use.

Compare full curves and decision-relevant extrema, not only averages. Relative
error needs a declared nonzero scale; near-zero torque, pressure, response,
reflection or transmission uses a separately accepted absolute floor/metric.
Those floors remain HUMAN_INPUT if not specified; no dividing by zero, clipping
or favorable imputation. A missing crossing, unresolved resonance or reference
interval intersecting a mandatory buyer limit is UNRESOLVED. Agreement slack
is not permission to exceed a buyer limit or compensate a failed stratum.

Tier 3 additionally binds specimen/batch, calibrated sensors, actuation and
timestamp alignment, observation mapping, uncertainty, raw provenance, rights,
calibration versus held-out validation data and applicability. A room-temperature
discharge trace is not warm fast-charge/ageing/plating validation. Experimental
agreement is limited to measured observables, conditions and uncertainty.

## Decision agreement alongside pointwise agreement

For **each of the eight Challenges**, report both pointwise agreement and
decision agreement on the same matched witness bank. Neither measure replaces
the other: acceptable curve errors can still flip a decision at a limit, while
a curve discrepancy can leave the decision unchanged. Retain both findings.
Before comparison, freeze the common designs/actions, complete scenario strata,
buyer limits, value objective, aggregation and tie-breaking rule from the
applicable packet. A missing decision definition remains HUMAN_INPUT; do not
invent an objective or score weight to choose a winner.

- **Feasibility verdict per design:** report each tool's feasible, infeasible
  or UNRESOLVED verdict, agreement counts with denominators, and the affected
  mandatory limits/strata for every disagreement. Missing or uncertain reference
  evidence remains UNRESOLVED, not an inferred pass; two unresolved verdicts
  are not evidence of feasibility agreement. Retain unresolved coverage.
- **Best-in-bank pick and regret:** report both tools' selected design identities
  and whether they agree under the frozen tie rule. If they differ, report the
  regret between their picks in the packet's buyer units, evaluating both picks
  under each tool separately with the same value rule. Name the direction and
  objective: for example, lost torque in N·m, additional charge time in minutes,
  or lost acoustic attenuation in dB, as applicable. If one tool regards the
  other's pick as infeasible, report that verdict mismatch rather than a
  fabricated finite regret. If no resolved feasible design exists, report no
  pick/UNRESOLVED, not a successful agreement between absent picks.

**Decision-agreement thresholds: HUMAN_INPUT**, including allowed verdict
disagreement, pick agreement and regret. This connects reference credibility to
the buyer's decision value; it does not adopt an official score, compensate a
mandatory failure, establish population reliability or make Challenge scores
comparable. Cooling's bank remains cell-level under the scope exclusion below.

## Witness sourcing and custody

Buyer-tool runs occur **outside the producer's custody boundary**. Matched
witnesses must come from either a **separate, non-hidden draw from the same task
distribution** and versioned case contract, or **retired, published bank cases**
with verified release provenance. Retirement alone does not authorize disclosure.
Witnesses never come from **hidden EVAL, STRESS, quiz or tuning cases**, nor their
protected seeds, labels or reconstruction-sensitive derivatives. Renaming or
anonymizing a protected case does not make it a public witness.

Stratify witnesses toward **near-limit and decision-flipping regions**, where
the quiz and design tasks discriminate, using public task definitions rather
than protected quiz/tuning cases or outcomes. Freeze the selection/stratification
rule before tool comparisons and retain all selected cases, failures and results,
not just agreeing pairs. Record task/reference versions, source/release identity,
selection rule and stratum coverage. Published benchmark controls are a separate
verification rung, not silently samples from the customer task distribution.
An enriched diagnostic witness sampling law Q is distinct from population P;
report its enrichment explicitly and do not infer P-weighted reliability from
raw agreement fractions or invent missing evidence weights w.

## Reference disagreement and prospective revision

A systematic gap between tools in a region is a **reference finding, never a
candidate failure**. Retain the region, matched decks, both reference identities,
observations, uncertainty and decision consequences; investigate physics,
discretization and observation mismatches without declaring either tool true by
default or relaxing buyer limits to hide the gap.

The finding triggers a **versioned reference revision for future batches** under
the reference owner's authority, with explicit applicability and renewed
agreement evidence before the revised reference is used. An unresolved affected
region remains UNRESOLVED, not a candidate penalty or an earned credibility
tier. **Already-sealed results keep their original reference identity** and
interpretation: they are **not silently re-scored** under the revision. Attach
the finding prospectively without rewriting sealed evidence.

## Claim and scope discipline

Before agreement evidence: “reference-credibility target specified; agreement
NOT_DEMONSTRATED.” After accepted Tier 1/2 evidence, the permitted claim is
**“matches the reference simulator”**, naming tool/settings, cases, observables
and agreement bounds. Never **“matches reality”** unless Tier 3 is met; even
then prefer the narrower “agrees with these independent lab measurements within
these bounds,” not a universal truth, safety, yield or deployment claim.

No tier substitutes for Carbon's scientific, security, rights, process or launch
authority. No licences, rigs, compute, solver downloads or execution grants
follow. Protected EVAL/STRESS cases/seeds/labels stay operator-side. Battery EV5,
sealed journal sequence 14 and its live contract are unchanged. Full-cold-plate
packaging/cost testing is excluded by the latest owner direction: the Cooling
subsection concerns cell evidence only, not assembly acceptance. Bank publication
and free-CPU panel proposals retain their separate versioned authority.
