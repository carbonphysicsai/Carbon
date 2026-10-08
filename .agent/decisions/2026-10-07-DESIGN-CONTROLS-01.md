## 2026-10-07 — DESIGN-CONTROLS-01: behaviour controls and clustered power diagnostics

Ticket: DESIGN-CONTROLS-01 (owner request, 2026-10-07). DEVELOPMENT only.
Primary map ref: `carbon/design_search` (Track B / Challenge admission).
The Development Hub is retired; no Hub source or generated file is changed.

Decision: keep the historical battery control implementation byte-identical.
Add neutral reference-output operations and a battery parity adapter in new
`carbon/design_search/controls.py`, then add task-level controls whose errors
are defined by each registered hard-limit margin. A control registration binds
its kind, limit quantities, severity and any action/stratum region. The
path-aware control uses the path the registered optimizer takes on the
known-good predictor; a lattice-aware control is accurate on every canonical
lattice action. Neither receives starts or paths from miner input.

Decision: the producer power harness uses sealed toy-capable bank records,
registered grid and continuous laws, and an exact-reference predictor table.
It runs the registered optimizer for each question and control, judges every
commitment, and reports only aggregated outcomes. It estimates detection
separately for false-feasible, missed-opportunity abstention, and defined
regret. A one-sided exact sign test treats a shared reference bank as one
cluster. Producer-supplied alpha, target power, simulation seed, replicate
count and maximum batch size are required; no result chooses a score rule or
claims qualified power. P and Q are reported separately.

Why: battery's historical outputs must remain interpretable under their old
code identity. Independent question variants sharing a solved bank cannot be
counted as independent clusters. A single compound pass/fail rule would be a
new scientific acceptance decision, so this harness leaves each metric's
separation visible to Test Lead.

Implementation: new `controls.py` and `power.py`, the producer CLI in
`carbon/design_search/__main__.py`, new code pins in `task_freeze.py`, toy tests
and `docs/development/DESIGN_CONTROLS_01.md`. No solver, Challenge physics,
hidden bank or LIVE path is added. Alternative rejected: edit battery's
`panel.py` directly (would change historical freeze bytes); count each
requirement variant as independent (would overstate power).

If a lead disagrees, supersede this decision and change the new neutral modules,
their toy tests and documentation. Human-reserved inputs remain: actual
severity, alpha, target power, sampling law, scoring use, attacks, and any
scientific qualification.
