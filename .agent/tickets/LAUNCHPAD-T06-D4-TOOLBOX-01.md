# LAUNCHPAD-T06-D4-TOOLBOX-01 — toolbox acceptance projection repair

Status: in progress. Base: `97106c1b36a19f7750f8e7ac344c4d6536d4b767`.
Authority: OWNER-LAUNCHPAD-E2E-SUITE-01 D4, T06, and
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md` §3.7. Reviewer: Launchpad
owner Platform2 or Root's independent reviewer.

## Working contract and decision

The `toolbox` operation is offered through the same HTTP and MCP operation
table as `options` and `ladder`, but T06's `_PROJECTED_NAMES` omits it. The
shared door adapters call `release_check.project(payload, name)` already.
REPAIR the omission in the named-operation allowlist. KEEP the existing
toolbox body, admission gates, schema, and acceptance reader. Do not infer a
PASS from availability or a successful response. Without a matching public
PASS cell, the toolbox response's closed `acceptance_status` is `UNTESTED`.

Decision T06-D4-TOOLBOX-D1: add `toolbox` to the projector allowlist and cover
both emitted doors plus release-check rejection of a missing/forged label.
This is a reversible, additive metadata repair; no human-reserved science,
security, launch, or economic value is selected. Alternatives of modifying
each door separately or treating the toolbox's presence as acceptance would
duplicate logic or violate D4. A later owner may supersede this by changing
the named projection contract, not by relabeling historical cells.

Expected manifest: this ticket, `scripts/dev/launchpad_acceptance/release_check.py`,
and `tests/cpu/test_launchpad_acceptance.py`. No host/provider or PR #1407
source changes. Primary Development Hub map_ref: `SYSTEM/AGENT-EXECUTION`;
impact `mapped_detail`. The hub's purpose, placement, status, dependency,
boundary, maturity, and primary links remain accurate; this follow-up repairs
one already-described door's metadata, so no hub source edit is proposed.

## Validation and maturity ceiling

Focused test: `tests/cpu/test_launchpad_acceptance.py`; relevant door regression:
`tests/cpu/test_miner_operations_doors.py`; strict path classifier and canonical
CI scope remain required before merge. Native static inspection earns no
canonical PASS. The exact-head complete-diff review, distinct non-author
approval, successful gates, normal merge, and external receipt remain Root's
delivery responsibility. This repair can earn bounded implementation/testing
only; it does not accept any Launchpad checkout matrix cell or a release.
