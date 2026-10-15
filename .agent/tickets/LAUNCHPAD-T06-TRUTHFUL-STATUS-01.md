# LAUNCHPAD-T06-TRUTHFUL-STATUS-01 — truthful acceptance metadata

Status: implementation. Base `bedd08d451f19603231b621ceb3e2993500387b2`.
Authority: full `docs/development/LAUNCHPAD_E2E_SUITE_HANDOFF.md` at published
owner commit `57c3e019f7f7de6deb274ffd5283395c91dfaa50`, T06 and execution
guidance; canonical LAUNCHPAD-ACCEPT-01 / acceptance plan section 3.7;
Ryan's OWNER-LAUNCHPAD-E2E-SUITE-01 D4/D5/D1, recorded separately by Platform2
at `018818453` (owner record SHA256 prefix `9f431e87`); Root's T06 assignment.
The owner record takes precedence over older handoff sequencing. No owner
record is copied or invented here. Constitution, invariants and OWNER-DX-03
remain controlling. Hub maintenance is retired.

## Contract, scope and decisions

KEEP existing choice providers, gates, payloads, browser/MCP journeys and
real-cell format. REPAIR their acceptance projection: default UNTESTED;
TESTED only from an actual latest PASS cell with an explicit revision and
public evidence reference. FAIL/BLOCKED/missing/malformed/conflicting evidence
cannot yield TESTED. Historical evidence names its original cell/revision;
it never claims the current checkout or a new release was accepted. Fixture
CI, availability, scientific checks and successful operation calls are not
acceptance evidence. Labels do not create a new admission or launch blocker.

Implement a small read-only stdlib cell reader and shared projection in
`scripts/dev/launchpad_acceptance/release_check.py`; annotate existing HTTP/MCP
results and choices; render labels in both browser panes; run the check before
the existing release rehearsal. No new application/test harness or dependency.
Read only the fixed public evidence tree; disclose an allowlist of cell ID,
result, revision and evidence path, never arbitrary evidence content.
Until separately authorized, level acceptance stays BLOCKED under D5; LA-F17
stays BLOCKED/UNTESTED under D1 without blocking unrelated launch behavior.

Platform2 confirmed one-writer separation. Hands off its PR1375 levels.py,
runner.py, operations.py, owner record, plan and historical cells. Product
confirmed release-rehearsal.yml is outside its R6 ownership. All R6 operator,
public build and ScoreLab files remain untouched.

Expected manifest: this ticket and one engineering decision;
`scripts/dev/launchpad_acceptance/{__init__.py,release_check.py}`;
`scripts/dev/miner_launchpad/{construction_options.py,controller.py,app.js,research_view.js}`;
`carbon/miner_mcp/{mcp_operations.py,mcp_setup.py}`;
`.github/workflows/release-rehearsal.yml`;
`tests/cpu/test_launchpad_acceptance.py`, plus existing focused test expectations
only if the explicit additive metadata contract requires them.

## Validation and completion

Static baseline: no executable release check exists at base; choice availability
and historical snippet verification are not revision-bound acceptance labels.
OPERATOR prohibits local app/test/import execution. Authorized remote canonical
CI supplies focused reader/projection, existing CPU/service/browser regressions,
rehearsal check and scope-required Merge gate results. No unrun pass is claimed.
Tests must cover defaults, latest PASS, FAIL/BLOCKED, malformed/conflicting data,
historical revision limits, disclosure, nonmutation, both door closed fields,
browser labels and rejecting unsupported TESTED claims in release rehearsal.
Root alone merges the exact tested head. Reviewer: Launchpad owner Platform2,
or Root's assigned independent reviewer. Completion earns bounded engineering
implementation/test evidence only; no actual owner block, security/science,
LIVE, product/release, network or production qualification is inferred.
