# CHALLENGE-AI-COOLING-FOUNDATION-01 — customer-bound cooling design foundation

**Status:** candidate complete; canonical CI pending

**Authority:** OWNER-CHALLENGE-FOUNDATION-01

**Scope:** DEVELOPMENT only; pre-pipeline foundation for `chip-cold-plate`

**Maturity ceiling:** implemented and tested engineering foundation; not
scientifically, security, commercially or production qualified

## Outcome

Start with the valuable customer result: select a lower-pumping cold-plate
design under explicit customer thermal/hydraulic limits, commit the proposal
before expensive verification, and expose false-feasible or unavailable
evidence. Deliver that result on the exact current periodic-cell physics while
making the full-manifold, transient and experimental gaps impossible to miss.

## Working contract

### KEEP

- `carbon/cold_plate/domain.py`, `analytic.py`, `exam.py`, `openfoam.py` and
  the existing evidence pools.
- `carbon/design_search/`: equal-budget methods, freeze and pilot machinery.
- The registry's `RESERVED` state and f04/f03 queued prior-work records.

### WRAP

- Add a customer decision contract with no default limits.
- Adapt the cold plate to the challenge-neutral design-search interface.
- Enforce a write-once proposal commitment before independent reference access.

### REPAIR / REPLACE

None authorized. A full-manifold physical version is a prospective versioned
expansion, not a repair hidden in this ticket.

## Definition of Done

1. A ten-part design packet records the customer job, current truth, end state,
   population/case/reference/measurement/construction/evidence contracts and
   claim ceiling.
2. Customer die and hydraulic limits are explicit, finite, provenance-bound
   inputs with no defaults.
3. A design request binds the contract, model, candidate grid, condition set,
   method, budgets and seed policy; undeclared or malformed queries fail closed.
4. The fixed baseline chooses the feasible-everywhere design with minimum
   worst-case hydraulic power and a deterministic tie rule.
5. Only a write-once `Commitment` can reach reference verification. Altered/raw
   commitment documents are refused.
6. Verification keeps reference failure separate, reports false-feasible
   events, and denies global-optimum, customer-acceptance, scientific and
   production claims.
7. Focused CPU tests cover the contract, scope, budget, selection, commitment,
   verification and reuse of the generic search method.
8. The existing cold-plate CPU suite and applicable quality/acceptance checks
   pass in the canonical environment or their infrastructure unavailability is
   reported exactly.

## Out of scope

Pipeline entry or gate signatures; protocol lock; new reference runs or spend;
private/protected material; full headers/manifolds; spanwise maps; transient
loads; experiment construction; new scientific thresholds; customer acceptance;
LIVE, production, reward, frontier, settlement or chain behavior.

## Human input required for the next version

Customer requirements and rights; scientific population/measurement/reference/
acceptance decisions; technical manifold/construction/runtime bounds; and
process authorization for protocol/queue/budget. All remain fail closed.
