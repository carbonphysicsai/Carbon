# DESIGN-TASKS-03 working contract

Status: DEVELOPMENT implementation in progress. Owner request dated
2026-10-08 is the active ticket; no earlier ticket is silently reselected.
Start from approved DESIGN-REPORTS-BATTERY-01 PR #808 head
`dd615697e6041c49cb2fda020816d19555099cc9` and stack one PR on that
branch until #808 merges. Primary map reference: `carbon/design_search`.
The retired Hub's purpose, placement, boundary and maturity remain accurate;
no Hub source or generated output is changed.

## Working decision and plan

KEEP runnable v2 tasks, their typed action grammar, optimizer paths, query
cost accounting, reference judgement, and private/public projection. WRAP
them in a versioned indexed registration. Each index has a registered value,
one runnable subtask, and a nonnegative buyer-mix weight. The weights sum to
one and are separate from every subtask's P, Q and w. A parent shared budget
equals the sum of registered per-index quotas; execution visits indices in
their registered order and a subtask's quota cannot be borrowed by another.
This fixed allocation is deterministic from registration alone. The parent
commitment is created from subcommitments before any reference access.

Every subtask has its own canonical action bank, conditions and hard limits.
An indexed pick is feasible only when every selected band is reference
feasible; a mandatory breach in any band makes the entire pick infeasible,
including if that band's buyer weight is zero. Missing or unresolved
reference evidence remains unresolved. Per-index outcomes are always
retained. The weighted mean is reported only for complete feasible maps,
with a common objective quantity, unit and sense across indices.

Value equivalence is a required registration containing objective quantity,
unit, a nonnegative finite tolerance and a fixed rule. Each per-index and
aggregate regret is zero when the objective difference is within that
tolerance; beyond it, regret is the full objective difference in objective
units. Objective proximity alone never causes UNRESOLVED. Battery's suggested
roughly 0.5 minute tolerance is HUMAN_INPUT and is not an executable default.

The miner projection uses a positive allow-list. It may reveal the index
count and public action/limit schema, but never registered starts, seeds,
candidate or bank order, digest pre-images, protected IDs, reference values,
or private buyer-mix weights. Controls run on each subtask's reference
margins with its own quantity-specific registered severities. The indexed
power diagnostic reports per-index and aggregate separation, retaining
shared-bank clustering; alpha, power target, tolerance, weights and severities
are required inputs, with no adopted production values.

Implementation sequence: contract; indexed task/optimizer/judge and
projection; controls/power; toy tests; canonical validation; one stacked PR
to PR Lead. Expected paths are this decision, `carbon/design_search/tasks.py`,
`indexed.py`, `optimizer.py`, `task_projection.py`, `power.py`,
`task_freeze.py`, toy tests and a short development contract. No Challenge
physics, solver, hidden material, LIVE authority or score use is included.

Rejected alternatives: widening runnable v2 in place would reinterpret
historical task identities; treating each band as an independent buyer
question would hide whole-map mandatory breaches and overstate power;
reusing stratum `w` for buyer mix would mix different measures. This wrapper
can be superseded prospectively without changing historical v1/v2 tasks.

Human-reserved inputs: battery v3's actual buyer-mix weights, value tolerance,
question law, power threshold and score use. Test Lead owns those decisions.
The ticket is complete only after toy tests and required canonical CI pass,
exact-head review is ready for PR Lead, and the PR remains DEVELOPMENT only.
