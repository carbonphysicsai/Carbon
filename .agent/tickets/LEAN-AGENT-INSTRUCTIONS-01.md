# LEAN-AGENT-INSTRUCTIONS-01 — Remove contradictory agent process

Working contract, 17 October 2026. Base:
`54aa139c916ab23681d5a75e48ea2aa34b537424`. Documentation-only change; no runtime,
CI policy, ruleset, deployment, network, economic or qualification change.

## Authority and purpose

Ryan explicitly authorized: "I also authorize you to audit the repos development
instructions for agents that could cause this type of issue". This accompanies
his direction to remove unnecessary machinery and build the lean reproducible
construction and common model-versus-solver scoring path, preserving Bittensor.
Ryan subsequently directed us to engrain this operating vision and give teams
strong guided autonomy, including cleanup authority within owned scope. Keep
that target in one tracked document linked from AGENTS, with concrete ownership
and engineering freedom inside boundaries.
Ryan's subsequent direct engineering-policy amendment says: "No approval
ceremonies. Just regular PR testing." Prefer fewer coherent PRs for meaningful
structural/runtime/behavior work; bundle helper tasks, fixes, tests, docs and
formatting. Small high-risk changes still receive proportionate PR checks.
This supersedes prior engineering approval/receipt ceremonies in AGENTS and task
instructions, while preserving actual enforced protections and science, security
acceptance, legal, LIVE and economic authority.

The audit found current entry points with top-of-file DX03/Hub-retirement
notices but contradictory active body instructions: mandatory human/GPT review
receipts, repeated full-review/exact-main steps, Hub maps/events/regeneration,
fixed multi-field decision packages and automatic multi-inbox notification.
The launcher also demanded a current-main checkout and the root guide repeated
an obsolete Wave-A snapshot. These can create process work, stale blockers and
component-only delivery without completing the product flow.

## Change and limits

Consolidate delivery in `.agent/DELIVERY_PROTOCOL.md`; remove duplicated
lifecycles from the decision protocol and executor entry points. Scope startup
to current authorized work, relevant domain rules, code and tests. Retain real
human-owned decisions, actual protections, meaningful testing, hostile execution
isolation, hidden separation, historical evidence and honest maturity. Ordinary
engineering facts/repairs do not become owner decisions. Obsolete callers must
be removed with their tested replacement; legacy relocation is reported as such.

Owned paths: `AGENTS.md`, `.agent/DELIVERY_PROTOCOL.md`,
`.agent/DELEGATED_DECISION_PROTOCOL.md`, `agent_pack/EXECUTION_PROTOCOL.md`,
`agent_pack/CODEX_TICKET_LAUNCHER.md`, `agent_pack/README.md`,
`agent_pack/PLANS.md`, the stale delivery paragraph in
`agent_pack/executors/hoh/PROTOCOL.md`, `docs/development/CARBON_BUILD_TARGET.md`,
the current-routing/workflow prose in `.agent/WAVE.md`, and this contract.
WAVE points to the lean mission and current scoped assignment without changing
recorded statuses, evidence identities or domain boundaries. It does not select
a successor or renew a runtime campaign.
No frozen Hub/decision history is edited. AGENTS sections 7, 13, 14, 15 and 16
retain their exact domain-boundary text. Core section 6 invariants remain, with
only its stale Wave-A applicability sentence generalized to current work.

The latest amendment is authorized; no further owner adoption question or Root
reapproval is required. Deliver this coherent update through existing PR #1419
and regular applicable CI, with Launchpad as sole publisher/merger. Do not open
another policy PR or bypass a real required check, security rejection or reserved
decision. This source task itself performs no publication or merge.

## Validation and completion

Use existing delivery/diff hygiene, changed-path classification and contract
acceptance. Check local Markdown links and preserved invariant/history bytes.
No new prose-mirroring test framework or runtime/model rerun is needed.
The optional harness keeps its actual packet, evidence and isolation mechanics;
only its duplicated repository delivery lifecycle is removed.

Expected commands: `git diff --check`,
`python scripts/dev/check_delivery_hygiene.py --base 54aa139c916ab23681d5a75e48ea2aa34b537424`,
`python scripts/dev/check_diff_hygiene.py --base 54aa139c916ab23681d5a75e48ea2aa34b537424`,
and classified canonical `./scripts/dev/canonical.sh ./scripts/dev/ci_contract_authority.sh`
before delivery. Product owns that canonical run; native source/link/hygiene
results from this slice are diagnostics, not canonical acceptance.
Report unavailable or failed acceptance honestly. Implementation and local
checks do not imply merge, scientific qualification or security acceptance.

Launchpad is the integration/publication owner. Completion requires coherent
final documentation, relevant validation and delivery under actual applicable
conditions. Do not mark this task delivered because the draft is shorter.
