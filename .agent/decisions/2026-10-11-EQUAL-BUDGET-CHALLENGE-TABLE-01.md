# EQUAL-BUDGET-CHALLENGE-TABLE-01 working decision

Status: DEVELOPMENT implementation decision; behavior-preserving tidy-up.

Authority: owner ticket EQUAL-BUDGET-CHALLENGE-TABLE-01 (2026-10-11),
`carbon/design_search/equal_budget.py`, and its existing toy replay tests.

Decision EQUAL-BUDGET-TABLE-D1: keep the replay and validator functions (KEEP),
and replace the duplicate Challenge set and per-Challenge dispatch branches
with one closed `CHALLENGE_ROUTES` registration table, shaped like
`BENCHMARK_ROUTES` in onboarding readiness. Each row names the existing budget
validator and flags the already-required indexed or representative schema.
`CHALLENGES` remains a set derived from table keys for callers that use the
existing constant. No Challenge, budget value, evidence status, objective,
report field, or solver-verification rule changes.

Reconciliation against main's new f17 route adds its existing
`micromixer_budget.validate` to the same table. The f17 readiness inspector
now recognizes this table mapping as wired, preserving its prior YES/NO/PLANNED
behavior; the mutation fixture still rejects a severed validator route.

Alternative rejected: moving or rewriting per-band scientific validation.
This ticket owns route selection only, and that validation already has tests.
The table is reversible without data migration. No human-reserved value is
selected. Existing fixture replay outputs must remain byte-for-byte equal.

Primary Development Hub map reference: `WAVE-B/EQUAL-BUDGET-DESIGN`.
Hub impact: none. Hub maintenance is retired by `.agent/DELIVERY_PROTOCOL.md`;
this internal dispatch refactor changes no purpose, placement, boundary,
maturity, dependency, or primary link.
