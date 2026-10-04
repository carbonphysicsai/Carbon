# CHALLENGE-MOTOR-DECISION-FOUNDATION-01 — construct before reference and bind campaign custody

**Ticket:** `CHALLENGE-MOTOR-03_decision_foundation.md`

**Status:** IMPLEMENTED_WORKING_DECISION

## Problem

The motor Challenge has an independently tested GetDP/Gmsh evaluator, complete
development pools, a textbook baseline and a learned baseline, but it has no
customer-decision workflow. Directly evaluating candidate designs while search
is still running would leak reference results into construction and would not
separate model value from search-method value.

## Agent recommendation

Keep the existing 2D motor science unchanged and make construction a distinct
first stage. Freeze a finite synthetic design problem, reconstruct both
registered models, run the fixed-grid and screen-then-confirm methods at equal
declared budgets, and persist all four commitments before any reference plan,
import or evaluation is available.

The synthetic requirements are the exact internal DEVELOPMENT decisions in
OWNER-GRAPHITE-TEST-WAVE-01 section 6, not defaults or real-motor requirements.
Reuse Challenge-neutral campaign custody and comparator semantics under
`carbon/design_search`. A counted Motor plan binds the exact construction and
digest-pinned Docker image, reserves every attempt in a durable SQLite ledger
before dispatch, and admits results only through a retained-artifact importer.
The analytical fixture has its own evidence class and cannot become solver
evidence.

## Implementation location

- `carbon/motor/customer_decision.py`
- `carbon/motor/decision_study.py`
- `carbon/motor/reference_campaign.py`
- `carbon/design_search/aggregate_methods.py`
- `carbon/design_search/campaign.py`
- `carbon/design_search/reference_comparison.py`
- `scripts/dev/motor/decision_study.py`
- `scripts/dev/motor/reference/run_batch.py`
- `docs/development/studies/MOTOR_SYNTHETIC_DECISION_V1.json`
- `docs/development/MOTOR_DECISION_DESIGN_PACKET.md`

Branch: `codex/motor-decision-foundation`.

## Alternatives rejected

- Reusing the old generic `design_search.experiment.pilot` end to end: it
  verifies each arm immediately after committing that arm, so it does not
  establish the required all-commitments-before-reference boundary.
- Treating private-pool prediction scores as design evidence: those scores show
  model accuracy, not whether a selected geometry is reference feasible or
  better than a finite comparator.
- Adding full motor physics now: speed, voltage, efficiency, thermal and 3D
  effects are different scope and need separate reference and population work.
- Defaulting torque and ripple requirements: these are human/customer-owned
  scientific decisions.
- Accepting native execution for the registered campaign: it would not itself
  establish the pinned Docker image or registered CPU allocation.
- Counting plausible callback records as GetDP evidence: this would not bind
  solver configuration, mesh, convergence, run identity or artifacts.

## Interfaces, invariants and dependencies

The new layer depends on `carbon.motor.domain`, `exam`, `analytic`, the shared
`carbon.learned_baseline`, and the registered methods, campaign ledger and
finite comparator in `carbon.design_search`. It preserves no-hidden-evaluation
leakage, reference failure separation, mock isolation, deterministic bounded
construction, construction/evaluation separation and no placeholder LIVE
authority.

## Reversibility

The change is additive and DEVELOPMENT-only. Superseding the finite set,
conditions or proposed requirements changes the config and freeze identity;
it does not rewrite the existing motor exam or evidence. Replacing the
construction/campaign boundary requires changing this decision record, the
ticket, decision modules, CLIs and tests. An interrupted reservation is never
silently reclaimed; unsupported reconciliation remains a compute-owner
decision.

## Human-reserved input

The exact requirements/scenario are supplied for this internal study by
OWNER-GRAPHITE-TEST-WAVE-01 section 6. Compute approval of the exact
image-bound 48+12 campaign remains required. The smallest superseding science
change is a new owner decision plus a new study version generated before any
reference is observed.
