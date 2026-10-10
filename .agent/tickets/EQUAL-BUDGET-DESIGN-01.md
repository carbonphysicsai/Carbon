# EQUAL-BUDGET-DESIGN-01 — development design-search comparison

**Owner assignment:** 2026-10-10. **Maturity ceiling:** IMPLEMENTED / TESTED
development analysis. No LIVE, hidden/AX42 access, reference solve, spend,
Challenge qualification or adopted buyer/scoring rule.

## Contract

For battery v3, motor and f02, replay the same complete registered design bank
under paired elapsed-time and core-second budgets. Compare a registered
solver-alone order, a model screen followed by solver verification, and the
strongest registered cheap-baseline screen followed by the same verification.
Only a solver-confirmed feasible candidate can supply value. Report best
verified objective, raw regret against the complete settled panel's true best,
and the paired probability that model screen plus solver beats solver-alone.
Use independent bank clusters for bootstrap intervals. Report no interval from
one bank and no curves from any unresolved candidate.

## Working decisions

**EBD-D1 (engineering):** extend `carbon.design_search.track_b` by wrapping
its read-only `Reference`/`Case` records in `equal_budget.py`, without changing
Track B's existing Q1/Q2 behavior. A solver evaluation is an entire mandatory
condition panel. The two resource limits are both hard; screening cost is paid
before verification. Each solver attempt uses a separately registered planning
bound that covers its measured cost; it stops before the first unaffordable
complete candidate in the registered order. A one-time fit/acquisition cost
must be included in the supplied amortized screen cost for the registered
number of decisions. This avoids a free model or cheap baseline screen.
The alternative of adapting Track B's single-resource `economic` output was
rejected because it cannot represent top-candidate verification and simultaneous
wall/compute constraints. Reversible by removing the new module. No owner
threshold is chosen here.

**EBD-D2 (evidence):** each input identifies source, rule, solver search,
model, cheap baseline and cost-plan registrations and binds the full input by
SHA-256. Those identities are evidence supplied by Data Collection, not a
claim that a self-generated digest proves temporal precommitment. Retrospective
plots remain exploratory unless registrations predate reference access.
For battery v3, all five index verdicts and the owner-registered buyer weights
must be present; any band breach makes the map infeasible. No compensating
weighted average is allowed. We reject an incomplete bank for all arms rather
than silently deleting hard cases. Alternative of computing regret against the
best observed partial design was rejected because it is not regret to true best.

**EBD-D3 (analysis):** report objective values in the registered buyer unit.
Among jobs with a feasible pick, report conditional mean best value and raw
regret; report feasible-pick rate beside them. A no-pick arm loses to a feasible
pick. P(model beats solver) uses a strict objective improvement, counting ties
and no-pick pairs as non-wins. Resample whole bank clusters for percentile
bootstrap intervals. This is an exploratory raw-value comparison; any
prospective value-equivalence policy remains Test Lead/owner input. No other
challenge's value is pooled with it.

## Inputs Data Collection must provide

For each current Challenge version and buyer job: a complete settled candidate
panel with hard-limit verdict and objective; for battery, five settled per-band
results and registered buyer weights; measured whole-panel wall and core cost
for each candidate including mandatory conditions/refinement; registered
pre-solve planning bounds; solver-alone search order from its independent
budgeted path; held-out model and matched cheap-baseline rankings; screening,
acquisition, fitting and inference costs amortized over a registered decision
count; source/rule/method digests; and multiple independent solved-bank clusters.
CCX63 wall/core measurements must identify the route. No number in the toy
tests is a production threshold or physical estimate.

## Acceptance

- Pure replay and aggregate CLI; no solver or model call.
- Paired time/compute budget accounting, hard stop, settled reference only.
- Three-arm deterministic toy tests for battery v3, motor and f02; any-band
  breach, unresolved, digest, planning-bound, one-bank and maximization tests.
- Canonical validation; PR to PR Lead at exact tested head. Do not merge.
