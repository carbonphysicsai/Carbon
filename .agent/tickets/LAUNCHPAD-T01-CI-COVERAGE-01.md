# LAUNCHPAD-T01-CI-COVERAGE-01 — execute the existing journey checks in CI

Status: implementation; bounded corrective T-01 under LAUNCHPAD-ACCEPT-01.
Starting base: `27f74451eacc346e323f1ff2d5f86a8b12407187`.

Authority: Ryan's 2026-10-15 OWNER-LAUNCHPAD-E2E-SUITE-01 R3 answers,
recorded by Launchpad owner Platform2; Root's bounded T01 assignment;
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`; current constitution,
invariants and OWNER-DX-03 delivery protocol. Platform2 confirmed this file
set is disjoint from T07/default/client/owner-record work before editing.

Static starting evidence: pytest's default paths are `tests/cpu`; the explicit
MCP service lane omits `tests/service/test_launchpad_production_journey.py`.
The workflow never enables `browser_smoke.py`; ci.sh also turns missing-browser
discovery into a successful skip. Neither test's presence establishes execution.
No local baseline tests run: OPERATOR assigns all host/test actuation to Root;
remote CI is authorized. This is an implementation gap, not an owner question.

## Bounded contract and plan

KEEP both existing real-process/HTTP and browser fixture journeys and their
assertions. REPAIR CI wiring: add the service journey to the pinned MCP lane;
require the browser smoke on hosted canonical shard 4; propagate missing
browser, startup and assertion failures. Keep explicit local opt-in on machines
without a browser, including the browser-free development image. Remove the
service journey's historical optional Graphite imports so missing current
capabilities fail rather than silently skipping required stages.

Expected manifest: `.github/workflows/ci.yml`, `scripts/dev/ci.sh`,
`tests/service/test_launchpad_production_journey.py`,
`tests/cpu/test_launchpad_ci_coverage.py`, this ticket, and
`.agent/decisions/2026-10-15-LAUNCHPAD-T01-CI-COVERAGE-01.md`.
No new application harness, dependency, provider, host command or release gate.
Hub maintenance is retired under OWNER-DX-03; no Hub files change.

## Validation and completion

Remote canonical CI must run the existing service journey and browser smoke,
plus focused orchestration regressions covering shard placement and failure
propagation. Focused command in canonical CI:
`python -m pytest tests/cpu/test_launchpad_ci_coverage.py tests/cpu/test_ci_shard.py -q`.
The full `./scripts/dev/ci.sh` workflow supplies scope-required acceptance and
Merge gate. No passing execution is claimed before those results exist.
Root alone merges the exact tested head; the PR is ready for Platform2 review.

DoD: both existing checks actually succeed in applicable hosted CI; missing
required capabilities and failing assertions fail the lane; orchestration
regressions pass; no scientific/security/economic or real owner-block acceptance
is inferred from engineering fixtures. This does not close T07 or create real
F01-F17 acceptance cells. Report actual CI failures as findings, never skip them.
