# LAUNCHPAD-T06-D4-TOOLBOX-01 — toolbox acceptance projection repair

Status: in progress. Initial base: `97106c1b36a19f7750f8e7ac344c4d6536d4b767`.
Current merged-main base: `4124b0080c7e6d30571a75a7307f7f3849f23405`,
reconciled by normal merge `b219b2eb91bd41ec28a4c164d38386884e545d7b`.
Authority: OWNER-LAUNCHPAD-E2E-SUITE-01 D4, T06, and
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md` §3.7. Reviewer: Launchpad
owner Platform2 or Root's independent reviewer.

## Working contract and decision

The `toolbox` operation is offered through the same HTTP and MCP operation
table as `options` and `ladder`, but T06's `_PROJECTED_NAMES` omits it. The
shared door adapters call `release_check.project(payload, name)` already.
The Control Center's toolbox renderer also omits the visible label. REPAIR
the named-operation allowlist and render the existing acceptance text. KEEP
the toolbox body, admission gates, schema, and acceptance reader. Do not infer
a PASS from availability or a successful response. Without a matching public
PASS cell, the toolbox response's closed `acceptance_status` is `UNTESTED`.

Decision T06-D4-TOOLBOX-D1: add `toolbox` to the projector allowlist and the
release capture, show the label in both Control Center toolbox renderings, and
cover both emitted doors plus release-check rejection of a missing/forged label.
This is a reversible, additive metadata repair; no human-reserved science,
security, launch, or economic value is selected. Alternatives of modifying
each door separately or treating the toolbox's presence as acceptance would
duplicate logic or violate D4. A later owner may supersede this by changing
the named projection contract, not by relabeling historical cells.

Expected manifest: this ticket, `scripts/dev/launchpad_acceptance/release_check.py`,
`scripts/dev/miner_launchpad/research_view.js`,
`tests/cpu/test_launchpad_acceptance.py`, and
`tests/cpu/control_center_page_check.cjs`. No host/provider or PR #1407
source changes. PR #1407 merged as `4124b0080c7e6d30571a75a7307f7f3849f23405`;
it also changes `research_view.js` at lines 380-394 and
`control_center_page_check.cjs` after line 1307 for Graphite retention; this
D4 addition is at lines 636 and 143, respectively, distinct hunks. The normal
merge above preserved both changes without a conflict. Primary Development Hub
map_ref: `SYSTEM/AGENT-EXECUTION`;
impact `mapped_detail`. The hub's purpose, placement, status, dependency,
boundary, maturity, and primary links remain accurate; this follow-up repairs
one already-described door's metadata, so no hub source edit is proposed.

## Validation and maturity ceiling

Focused test: `tests/cpu/test_launchpad_acceptance.py`; relevant door/browser
regressions: `tests/cpu/test_miner_operations_doors.py` and
`tests/cpu/test_control_center_live_page.py`; matrix scoreboard regression:
`tests/cpu/test_launchpad_acceptance_matrix.py`. The strict path classifier and canonical
CI scope remain required before merge. Native static inspection earns no
canonical PASS. The exact-head complete-diff review, distinct non-author
approval, successful gates, normal merge, and external receipt remain Root's
delivery responsibility. This repair can earn bounded implementation/testing
only; it does not accept any Launchpad checkout matrix cell or a release.

Static candidate checks on Windows: Python AST parse of the two changed Python
files, `node --check` of the two changed JavaScript files, and `git diff --check`
all exited 0. No canonical test was run under this source-author role while
Root's exclusive TEST lease was active.
