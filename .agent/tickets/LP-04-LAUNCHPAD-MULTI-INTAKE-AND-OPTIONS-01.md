# LP-04 — Launchpad multi-intake and construction options

Platform queue selection, 2026-10-13. Reviewer Launchpad, with Carbon Validator
for disclosure. One PR to main, starting at
`acecdbbdf452f8dba4b35d7fc3262639360e7fd8`. PLT-15 and LP-03 are merged.
The fresh open-PR scan has no overlap on the intake setup, runner, campaign,
operations, projection, app or level adapter. Do not edit the held endpoint
publication PR #1255's `published_endpoints.json` or PLT-16's library files.

Authority: current constitution/invariants and delivery/delegated-decision
protocols; the owner-selected queue; public PUBLIC_INTAKE_01 sections 9/F1
and UNIFIED_CONSTRUCTION_01_DESIGN sections 1.5 and 4.7; Launchpad test matrix
L5 and U. External opening, the construction ceiling and deployment remain
owner/operator decisions. No chain, signer service, credentials, tunnel,
AX42, compute rental or protected material is operated by this ticket.

## Working decisions and plan

KEEP the current single-intake profile, receiver checks, signing protocol,
commitment gate, idempotent send/poll logic, bounded waits and disclosure
projection. WRAP these for an explicit per-Challenge list of intake/receiver
pairs. Each pair has its own stable private submission journal; reordering a
list cannot send a duplicate or substitute a receiver. Multi-target profiles
require every receiver to be pinned. Published entries may repeat a Challenge
with distinct validators; conflicting/duplicate URL or receiver identities
fail closed. Legacy one-target configuration keeps its existing behavior.

Send the same frozen strategy/contract to each configured validator. One
unreachable, refusing or infrastructure-failed validator does not prevent the
others from being attempted. Report each validator independently. No score
aggregation, best-validator selection, cross-validator scientific acceptance,
ranking or settlement rule is invented. A queued target keeps its journal and
the frozen candidate; subsequent submit/observe reads reuse each target's
existing receiver-bound submission.

Expose one plain construction-options document through the existing options
operation, so the page and agent read the same data. Registered public change
types retain owner ceiling, opening/check status and reasons; an absent public
contract or undecided ceiling is explicit and closed. Do not infer an approved
ceiling from hoped-for Level 4. Remove level picking on the unified path only
when the shared classifier and served public unified contract are available;
the current PLT-16 PR #1276 is a dependency, not permission to stack or copy its
library. No compiler enters the miner import closure. Historical level-bound
campaigns keep their interpretation until their registered migration.

1. Canonical baseline for setup, remote submissions, runner/projection/levels.
2. Implement and test list loading, paired receiver validation, independent
   journals/send/poll, per-validator page and agent projections.
3. Implement shared plain options and fail-closed unified availability; sync
   main only for actual landed dependencies. Preserve all existing checks.
4. Canonical affected and invariant regressions, pinned quality/encoding and
   exact-head delivery hygiene before push, classified CI/Merge gate, Ready
   for PR Head, <=15-line local report and queue DONE or a concrete BLOCKED.

Maturity ceiling: implemented/tested DEVELOPMENT controls, never deployed,
security-qualified, scientifically qualified or LIVE. Primary historical
map_ref WAVE-A/A9; affects NET-2 authenticated ingress and miner disclosure.
Hub maintenance is retired by current delivery authority; no regeneration.
