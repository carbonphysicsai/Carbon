# PKT19-LAW-OBSERVABILITY-01

Ticket: PKT-19 PHYSICS-LAW-GATES-01. Classification: `DOCUMENTATION_LAG`.
Working engineering decision: KEEP registered laws and gate operators;
implement a synthetic control/sweep harness and an observable-coverage audit.
Test Lead accepted this bounded scope on 2026-10-13 and owns routing the
remaining scientific question to Carbon Validator.

The queue's "no conservation/boundary/PDE check anywhere" premise is false:
`carbon.measurement_runtime.development`, `carbon.scoring.development` and
`CW1_DEVELOPMENT_SCORING_RULE.md` already define conserved-mean and
initial-condition gates. Their limited energy/weak-PDE diagnostics remain
diagnostics. Battery's `exam.GATES` includes initial temperature, bounded
initial voltage, voltage bounds and an inventory-derived capacity bound.

`OWNER-PHYSICS-GATES-01` adopts only B15 as its additional mandatory gate;
B16/B9 card roles and B8 diagnostic role must remain intact. Neither omitted
internal battery inventories/fluxes nor Fourier representation closure can
establish a new independently measured conservation/boundary law.

The correction lives in `scripts/dev/physics_law_gates.py`, its dedicated
tests and `docs/development/physics-law-gates/`. Existing registered runtime
files, tolerances, score inputs and contracts are unchanged. Synthetic
threshold curves report counterfactual admitted/excluded controls, not a
recommended tolerance or qualification. New adoption values are `HUMAN_INPUT`.

Rejected: inventing a battery heat/charge law from insufficient outputs;
promoting non-adopted laws or underresolved diagnostics; replacing current
judge code or reinterpreting historical results. Reversal is deletion of the
new harness/audit paths; no migration of existing data is needed.

Smallest additional domain decision: identify an already-authorized law,
its measurable observable and Challenge, applicability and owner-set
adoption/tolerance. Until then the additional scope remains fail closed;
the existing-law engineering harness proceeds without guessing science.
