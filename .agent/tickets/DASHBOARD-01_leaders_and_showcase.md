# DASHBOARD-01: leaders dashboard and live design showcase

**Status:** PLANNED. The plan is `docs/development/DASHBOARD_PLAN.md`.
**Authority:** OWNER-DASHBOARD-01 (2026-10-08). Directed by the Test Lead.
**Delivery:** one PR per slice to PR Head (D0 plan, D1 leaderboard, D2
showcase, D3 live wiring and deploy package). The owner asked for the plan
first and then one PR per slice.

**Scope:** a public, read-only display of the Carbon Validator's signed score
feed (VALIDATOR-29), and a replay of the registered `design_search` optimizer
driven by a model on a public design task, against public reference solves.

**Excluded:** hidden, live or unreleased material of any kind; validator state,
bank draws, seeds, quizzes and private readers; model execution behind the
page; recipe or architecture disclosure; deploy, publication and spend (an
owner decision); score, rank, frontier, weight, settlement, qualification or
production authority; any change to the optimizer, the score bridge or the
feed's semantics.

**Acceptance (per slice, details in the plan §5.3):**
- every disclosure check in plan §2 refuses its bad case in a focused test;
- the showcase commits before reading references, agrees with `tasks.judge`,
  and refuses inputs outside the committed public allow-list;
- `DEVELOPMENT` (and `TESTNET` where stated) on every view; no claim words;
- the browser check at desktop and phone width; the quality gate; one
  canonical focused run.

**Maturity ceiling:** IMPLEMENTED and TESTED display software. Never
qualification, security acceptance or production readiness.
