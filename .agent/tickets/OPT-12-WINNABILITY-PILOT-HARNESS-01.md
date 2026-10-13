# OPT-12 — public development winnability pilot harness

## Working contract and start state

Owner queue `codex-queue/optimizer.md` OPT-12, on merged main after #1217.
Reviewer: Carbon Validator. One PR against main. The queue remains untracked.
This ticket implements a no-execution three-arm replay and a historical public
EV4 battery row. It does not run a solver, train a model, qualify a Challenge or
select scientific thresholds. A current registered job needs separate public
held-out panel, arm proposals, complete costs and a budget registration.

Primary hub map_ref: `SYSTEM/DEVELOPMENT-HUB`; impact: no change to Hub purpose,
placement, wave status, authority boundaries, maturity, dependencies or links.
This is an isolated development-analysis tool under Challenge factory's existing
proposal; the derived Hub is left intact. No Hub event is warranted unless the
result changes team understanding beyond the ticket's PR and retrospective.

## Decisions, reuse and plan

KEEP #1217's proposed three-arm experiment and RES-07's public research record.
WRAP `carbon.design_search.equal_budget` for registered solver-only, plain L0
screen-and-verify, and strongest-cheap screen-and-verify replays. The input
requires the same registered time/compute/evaluation caps, preparation costs,
separate P/Q/w identities, and a public held-out role. No new spend path.
The EV4 historical row is derived only from digest-checked owner-supplied public
inputs and committed RES-07 aggregates. Historical token caps are diagnostics;
they are not matched complete costs or a strong adaptive solver-alone arm.

Implement strict input/role validation, prepared-cost amortisation, per-stratum
learning descriptors, paired cheap-versus-model uncertainty, finite-bank
headroom, toy failures, and a deterministic EV4 retrospective. The output is
PROPOSED / UNDECIDED; all buyer-useful thresholds remain HUMAN_INPUT.

Expected manifest: `carbon/design_search/winnability_pilot.py`, toy tests,
Challenge-factory harness note and battery retrospective JSON, this ticket.
Validation: focused pilot/equal-budget tests, Black/Ruff, canonical CI and
delivery hygiene on exact head. No raw input or queue file enters the PR.

Completion predicate: exact-head CI green and Ready handoff to PR Head; no
scientific qualification, value-bar PASS, launch or LIVE state is earned.
