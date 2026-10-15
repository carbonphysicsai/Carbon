## LAUNCHPAD-T01-CI-COVERAGE-01 — required hosted journey execution

Ryan's OWNER-LAUNCHPAD-E2E-SUITE-01 R3 and Root's T01 assignment supersede
ci.sh's older 2026-10-07 browser opt-out for the hosted canonical lane.
The existing MCP service journey runs on shard 3; browser smoke runs on shard 4
with `CARBON_LAUNCHPAD_SMOKE=1` supplied by the canonical workflow. Calling the
existing browser script directly retains its strict discovery/startup/assertion
failure semantics. Local opt-in remains available; browser-free dev-image CI
does not claim browser coverage. The hosted canonical job is already required
by Merge gate; no new gate or harness is introduced.

The journey's Graphite modules are current repository capabilities, so normal
imports replace historical optional skips. Engineering fixture checks remain
separate from real infrastructure acceptance, owner hands, testnet registration,
exposure, signing, provider execution, science and qualification.
