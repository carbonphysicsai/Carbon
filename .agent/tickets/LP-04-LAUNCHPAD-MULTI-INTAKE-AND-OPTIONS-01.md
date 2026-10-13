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
ceiling from hoped-for Level 4. PLT-16 #1276 landed and was synced from main.
The later queue amendment and construction plan section 6 supersede the
classifier-only timing: retain construction_level/arm until S3 supplies the
composition-derived summary. Its wiring is separate; LP-04's final summary
display and removal stay blocked on S3. Changed constructions remain closed
without their required ceiling/opening/checks/serving facts. No
compiler enters the miner import closure. Historical level-bound
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

Baseline: 130 canonical tests passed. The first multi-validator slice passed
148 tests, including 18 new pair/journal/receiver/failure/projection tests.
The new profile field intake_targets holds closed URL/receiver pairs, bounded
to 32 validators per Challenge as a configuration resource limit. A prospective
multi feedback schema reports execution states and individual outcomes, never
a combined scientific score. The old single-target path remains byte-compatible.
The schema-parity regression retains the original launch fields while S3 is
pending; its parity and historical freeze checks remain.

Final local acceptance: 178 focused construction/setup/transport/history tests
and 812 broader Launchpad/MCP/intake/invariant tests passed without skips.
After live peer-progress/cache/read-poll guards, 81 directly affected tests
passed, including 32 new LP-04 tests. Pinned Black 26.5.1/Ruff 0.16.3 passed.
New fixture failures were repaired to the existing OWNER-prefix and exact
registration-digest format; no contract guard or pin was relaxed. Dynamic
exact-head CI and handoff facts belong in the external/local queue report.

CI found three direct Challenge imports in otherwise neutral doors. REPAIR:
route optional construction-contract, multi-feedback schema/status and refusal
normalization through ChallengeCampaign; share only generic journal pointers.
Multi feedback names its public Challenge identity before registry resolution.
No neutrality assertion changed. Canonical repair acceptance: 533 tests passed
with two intentional AST-fixture skips; final registry/history/unknown-identity
checks passed 159 with those same two skips. Retired history has no new hook.

The amended v3 notice is display only: validate/compile add fixed public text
when composition_graphs accompanies width/depth in a v3-bound campaign. The
same public result reaches page and MCP; no admission or frozen binding changes.
No notice applies without those fields or to v4. V4's typed refusal stays with
its registered compiler. SHADOW remains OFF. Final exact-head evidence belongs
in the untracked report; no completion claim precedes the S3 dependency.

Final bounded failure repair: a target-local journal-directory error is
FAILED_INFRA for that target, so it cannot abort another validator's trip.
The failure/recovery test checks that no send occurs for the blocked directory,
the peer scores independently, private exception text is absent and a retry
attempts only the repaired target while reusing the peer's cached verdict.
