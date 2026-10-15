# LAUNCHPAD-T03-REFUSAL-COVERAGE-01 — refusal reference inventory and regression check

Status: implementation. Starting base: `a8e52e6458927e9b9dfe6af2e94cce39d2537ca0`.
Authority: Root's bounded T03 assignment; the complete original handoff
`57c3e019f7f7de6deb274ffd5283395c91dfaa50:docs/development/LAUNCHPAD_E2E_SUITE_HANDOFF.md`
section T-03; OWNER-LAUNCHPAD-E2E-SUITE-01; current constitution/invariants.
Root retains actual host/model/pod/test dispatch and merge authority. The actual
R6 operator closure receipt selects TEST; this ticket performs no host action.

## Contract and plan

KEEP the existing supervisor NEXT_ACTIONS catalog, operation refusal fields,
typed refusal sites and tests. Add a standard-library-only static inventory;
never import or execute the inventoried modules. Enumerate closed literal codes
from the catalog and Launchpad/MCP production Python modules. Map exact string
literals in tests to source locations, with reached-literal/unreached-literal
labels. A literal reference is not proof that a refusal ran, that a gate was
reached, or that both doors agree. Computed/dynamic codes need independent tests;
this deliberately bounded inventory does not certify semantic completeness.

Freeze the initial source inventory and existing unreached backlog at the base
above. Every unreached row has an independently addressable child ticket ID,
owner, source and priority (direct production refusal site before catalog-only
entries). Those child tickets remain open; this ticket does not implement them.
The report publishes every row and how to regenerate it. No new unreached code,
formerly referenced code losing its reference, or larger unreached set passes.
Compare actual code/test inventories against the Git comparison base; the
baseline is never an allowance source, so editing it cannot hide a new gap.

The new CPU test integrates the check into the existing canonical collection.
Do not edit ci.sh, workflows, T02/T04/T05/T06 or PR1376 files. Platform2 owns
the T04 explicit service-list addition. No new harness, dependency, scientific
gate, production threshold, runtime refusal or door behavior is introduced.

Expected six-file manifest: this ticket; its dated decision;
`scripts/dev/launchpad_refusal_coverage.py`;
`tests/cpu/test_launchpad_refusal_coverage.py`;
`docs/development/launchpad/REFUSAL_COVERAGE.md`;
`docs/development/launchpad/refusal_coverage_baseline.json`.
Primary map_ref: SYSTEM/AGENT-EXECUTION. OWNER-DX-03 retires Hub maintenance;
no Hub source or generated output changes. No human-reserved value is needed.

## Validation and conditional completion

Root/remote CI runs canonical focused CPU tests, the report's --check command,
and applicable exact-head CI/Merge gate. Native AST/formatting/report generation
is static evidence only; do not report unrun application tests as passed.
Negative controls must reject new unreached catalog and direct-site codes,
removal of an old reference, exchanged gaps despite equal counts, and baseline
allowance inflation. Positive controls cover referenced additions, backlog
reduction, duplicate sources, deterministic output and no application imports.
Ready means these checks pass on the exact PR head and the complete diff is
reviewed. Root alone merges. No real-infrastructure acceptance, scientific,
security or production qualification follows from this engineering inventory.
