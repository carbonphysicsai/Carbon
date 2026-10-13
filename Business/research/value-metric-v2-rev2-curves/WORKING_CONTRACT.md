# RES-09: rev-2 owner-choice curves

DEVELOPMENT research only. The queue authorizes one PR against main, public
EV4 analysis and five curves; no parameter selection, registration, solver,
training, spend, hidden material or production changes. Reviewer: Carbon Validator.

KEEP the immutable RES-07 measurement functions and RES-08 preparation,
inventory, reference interpretation and bootstrap helpers from merged #1218.
WRAP them with an explicitly versioned rev-2 selector and aggregation.
The old draft hash remains an archive identity; the new adapter checks the
actual rev-2 draft hash. Never change the old reports or results.

Exploratory grids (ASSUMPTION; all choices HUMAN_INPUT): P = strict nominal,
strict shifted, their question-uniform union, edge, robust-SOC, robust-temperature;
k = 1, 2, 3, 4, 5; kappa = 0.05, 0.1, 0.25, 0.5 benefit units per
condition-solve; absolute delta = 0, 0.01, 0.05, 0.1, 0.25 benefit units;
alpha = 0.001, 0.005, 0.01, 0.025, 0.05. The plotting anchor
(union, k=3, kappa=0.1, delta=0.05, alpha=0.01) is arbitrary, not a proposal.
Report the full k/kappa cross-grid on each nonempty population too.

Primary bank: fallback FEASIBLE and every action FEASIBLE or INFEASIBLE.
Band-UNRESOLVED is not a settled reference. No relaxation for a fuller plot.
P describes the conditional estimand; Q is the existing finite public grid,
not a fresh draw; w is uniform over retained questions, not over strata.
Composed families remain separate and reuse weight is zero.

Shortlists use predicted feasibility and strictly improved predicted objective
relative to the model's own fallback prediction; missing fallback objective
means abstention. This interpretation is explicit and compared with a known
reference-fallback-objective sensitivity. The Validator must freeze the rule.
The bilinear D map is a fixed illustrative cheap arm, not a selection on V
and not a claim of strongest registered baseline or matched acquisition budget.

Use paired temperature/condition-block bootstrap intervals and paired exact
block sign-flip tests as exploratory options, not calibrated takeover authority.
Report sparse-block granularity, singleton CI gaps, multiplicity and dependence.
U ranks raw members; safety gates remain mandatory and their new-bank verdicts
are unavailable. Unsafe counts order exact U ties only.

Delivery: OWNER_SUMMARY.md, REPORT.md, five charts, replay analysis/tests,
machine-readable public measurements, source pins and rev-1 archive index.
Native checks are supplementary; canonical CI must pass before handoff.
Hub is retired under current main AGENTS.md OWNER-WORKFLOW-SPEED-01;
no frozen Hub files change. Owner and PR Head retain adoption and merge authority.
