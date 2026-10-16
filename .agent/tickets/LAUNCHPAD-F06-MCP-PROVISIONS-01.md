# LAUNCHPAD-F06-MCP-PROVISIONS-01: research provisions on both doors

**Authority:** OWNER-LAUNCHPAD-E2E-SUITE-01 F06 in `docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`; OWNER-RESEARCH-ENVIRONMENT-01 in `docs/development/RESEARCH_ENVIRONMENT_STANDARD.md`; C-MLP-04. OWNER-DX-03 governs delivery.

**Status:** in progress; source implementation only. F06 live acceptance stays UNTESTED until the installed MCP and Control Center readouts and the actual cost reservation are checked together.

**Map ref:** historical `SYSTEM/AGENT-EXECUTION`; the Development Hub is retired, so no Hub source or generated files change.

## Working contract

The open-tier `carbon_challenges_v1__describe` payload must expose the same public, per-Challenge `provisions` shape as the Control Center: provided status and note, or a named gap with reason and next step. Read both from `carbon.challenge_kit.standard.ENVIRONMENTS`; never publish internal evidence symbol references, official material, or a new scientific assertion. Retired Challenges remain refused by the existing typed registry boundary; the standard's historical retired record remains readable. Reserved/deferred Challenges remain unselectable. No version, execution, cost, qualification, or live-status behavior changes.

**Disposition:** KEEP the registry and standard; REPAIR the missing public projection; WRAP both doors around one projection to prevent drift.

**Expected paths:** this ticket, `carbon/challenge_kit/standard.py`, `carbon/challenge_registry/registry.py`, `scripts/dev/miner_launchpad/capabilities.py`, and focused CPU tests.

**Validation:** focused challenge-registry, research-environment, and Control Center CPU tests; canonical lint/format and applicable CI when published. Compare named-gap and retired behavior. No live F06 PASS from these tests.
