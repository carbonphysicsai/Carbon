# CHALLENGE-AI-COOLING-STUDY-02 — bounded first decision experiment

**Date:** 2026-10-04

**Status:** selected working decision; counted execution remains owner-reserved

**Authority:** user-authorized continuation of
`CHALLENGE-AI-COOLING-FOUNDATION-01`; scientific acceptance, compute/spend,
customer acceptance and LIVE authority remain reserved

## Decision

Continue the periodic straight-channel cell as a concrete synthetic
DEVELOPMENT decision study. Repair query/reference accounting before producing
evidence, then freeze and compare:

1. analytical versus reconstructed learned KRR under the same fixed-grid search;
2. fixed-grid versus registered screen-then-confirm under the same learned model
   and equal declared budgets; and
3. every selected design versus the best independently reference-feasible
   design in the complete declared 8 × 6 comparison set.

The query unit is an attempted model point. Duplicate points are forbidden
within and across calls. Any failed model batch seals the oracle. The
verification unit is a condition evidence evaluation; cached cases still cost
an evaluation, while solver executions and retries are counted separately.

Analytical callbacks are classified fixture evidence. Counted CFD requires the
pinned solver image and importer-verified plan, generated case, mesh,
convergence/applicability evidence, run identity, solver outputs/logs and
artifact digests.

## Proposed synthetic study

- Limits: 100 °C maximum die temperature; 0.25 W maximum periodic-cell
  hydraulic power.
- Design set: 8 full-grid designs from two widths, one fin width, two depths and
  two flow coefficients.
- Conditions: 4 representative plus 2 boundary-stress conditions.
- Control: steady-state feed-forward
  `total_flow_lpm = flow_lpm_per_kw * heat_load_w / 1000`.
- Query budget: 48 attempted model points per arm.
- Verification: 6 condition evaluations per selected design.
- Comparator: all 48 design-condition pairs; finite-set regret only.
- Grouping: representative and boundary-stress results remain separate; no
  approved combined weighting or pass threshold.

These values are proposed DEVELOPMENT assumptions, not owner-approved physical
truth or customer requirements.

## Counted execution boundary

Prepare but do not launch:

- 48 initial OpenFOAM executions;
- at most one retry per failed case;
- 12-execution retry reserve and hard cap of 60;
- 2 CPUs per execution, 6 parallel, 3600 seconds per case, all artifacts kept;
- approximately 19.2 initial and 24.0 hard-cap core-hours using the prior
  planning estimate of 0.4 core-hour per case.

The smallest remaining decision is approval by the science owner of the frozen
synthetic protocol and by the compute/spend owner of that exact cap. Until then,
only the analytical fixture smoke may run.

## Delivery-protocol reconciliation

Current `.agent/DELIVERY_PROTOCOL.md` and the `OWNER-DX-03` override supersede
older routine fresh-GPT-review, distinct-human-approval and external-receipt
ceremony. Those older statements are documentation lag, not restored gates.
This change still requires the applicable automated acceptance, Merge gate,
normal PR ownership rules and the designated PR Head for merge. This session
must not merge the PR.

## Maturity ceiling

Implemented/tested DEVELOPMENT decision-study machinery and analytical fixture
evidence only. No scientific qualification, customer acceptance, commercial
validation, production qualification or LIVE authority.
