# B-01H — Carbon Iterative Agent Harness Pilot plan

## Authority and start

**Ticket / delivery mode:** B-01H / `SINGLE_TICKET_PR`
**Starting base commit/tree:**
`650b035dae5629ae75b9e3f549b289f28cdbb9ba` /
`6d3664b3b29189cde8c7ffdeaa5a7c851f530955`
**Relevant authority/specifications:** `CONSTITUTION.md`, `AGENTS.md`,
`.agent/INVARIANTS.md`, `.agent/WAVE.md`, `.agent/WAVE_B.md`,
`.agent/DELEGATED_DECISION_PROTOCOL.md`, `.agent/DELIVERY_PROTOCOL.md`,
`agent_pack/EXECUTION_PROTOCOL.md`,
`docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md`, and
the B-05 ticket only for pilot requirement navigation.
**Primary Hub map_ref / impact:** `SYSTEM/AGENT-EXECUTION`; structural update
required for selected-ticket sequencing, new ticket placement, dependency,
boundary, implementation maturity, and primary links.
**Human-reserved inputs:** all B-05 science and every security, production,
rights, economic, qualification, `LIVE`, review, and merge authority remains
unavailable to the harness.

PR #75's normalized external receipt at comment `5513643185` establishes that
B-04's predicate passed and selected B-05 at exact main `650b035d…`, but B-05
was explicitly not started. `OWNER-DX-02` now interposes B-01H and preserves
B-05 as the next scientific ticket and first planned pilot.

## Disposition and decisions

| Existing component | Disposition | Reason |
|---|---|---|
| Root authority, delivery protocol, and final gates | KEEP | HoH hands off to them and cannot replace them. |
| `agent_pack/executors/` optional executor seam | WRAP | Add `hoh/` without moving authority into executor configuration. |
| Canonical wrapper, strict classifier, and Merge gate | KEEP | They remain final acceptance authority. |
| Git worktree model | WRAP | Use exact identity checks and a dedicated writable worktree. |
| Model assertions as completion evidence | REPLACE | Deterministic controller accepts only strict Tester evidence. |
| Per-iteration tracked evidence | REPLACE | Persist dynamic state under the Git common directory. |
| B-05 ticket requirements | KEEP | Map unchanged DoD text; do not implement or reinterpret it. |

Material decisions are `OWNER-DX-02` and `B-01H-D1` through `B-01H-D6` in
`.agent/DECISIONS.md`. They route to issue #42 and use `FOR_AWARENESS`; no
reserved human value is selected.
**Separate-contract exception:** `NOT_APPLICABLE`.

## Vertical slices

1. Record OWNER-DX-02, ticket, plan, stable evidence, board sequencing, and Hub
   impact; preserve historical B-04/B-05 receipt wording.
2. Add standard-library models, strict validation, canonical identities,
   external state storage, disclosure policy/projections, controller-run
   evidence commands, sanitized Developer patch import, adapters, prompts,
   schemas, and B-05 pilot manifest.
3. Add focused role-isolation, malformed-packet, evidence, regression,
   identity-drift, resume, scope, authority-ceiling, hidden-context, and
   synthetic multi-iteration tests.
4. Regenerate and validate the Hub; run focused and full applicable acceptance;
   audit exact manifest and maturity; deliver through the existing protocol.

## Expected manifest / exclusions

Expected paths are limited to `.agent/` B-01H/B-05 sequencing and evidence,
`agent_pack/executors/hoh/`, its executor index, a thin `scripts/dev/hoh.py`,
focused `tests/cpu/test_hoh_*.py`, `.agent/CODE_AUTHORITY.toml`, and semantic plus
generated Development Hub files. No `carbon/` runtime, B-05 scientific
contract/runtime, scoring values, production configuration, CI weakening,
network, rights, economics, or deployment path is owned.

## Tests and commands

- Focused: `./scripts/dev/canonical.sh --focused tests/cpu/test_hoh_models.py
  tests/cpu/test_hoh_controller.py tests/cpu/test_hoh_adapters.py`
- Existing development regressions: change classifier, code authority,
  delivery hygiene, GPT review gate, and Hub validation tests.
- Full: `QUALITY_BASE_SHA=650b035d… ./scripts/dev/canonical.sh --full`
- Hub: renderer, `--check`, validator, route test, browser smoke, and
  `git diff --check` from the maintenance contract.

The start baseline attempted the required canonical wrapper. It returned
`Docker is unavailable; install/start Docker or enter the Carbon Dev Container.`
The host Python 3.13 diagnostic also lacks pytest. This is `PAUSED_INFRA` for
local canonical evidence, not permission to weaken the requirement; exact-head
GitHub canonical gates must pass before merge.

## Risks / stop conditions

- Fail closed on Git identity drift, unsupported Codex CLI flags/version probe,
  malformed packets, protected context, path expansion, missing evidence, or
  non-deterministic resume state.
- Do not claim OS-enforced arbitrary-code security; the bounded Codex adapter
  uses supported sandboxes and isolated projections only.
- Stop B-05 science at every human-reserved value; the manifest is navigation.
- Do not merge without the existing exact-head and post-merge predicates.

## Completion predicate

The exact final head/tree must pass every classified check and `Merge gate`;
receive fresh read-only complete-diff Codex/GPT review with all findings closed;
receive a distinct non-author human approval carrying the exact receipt;
pass `GPT review gate` with zero unresolved threads; normally merge using the
expected-head guard; preserve ordered second-parent and reviewed tree; pass
exact-main `Merge gate`; and post the normalized external receipt. Only then
does B-01H become bounded `SPECIFIED`/`IMPLEMENTED`/`TESTED` and B-05 become
the active first pilot at the exact receipt-recorded main.

## Implementation result

Implemented the optional controller under `agent_pack/executors/hoh/` with a
thin `scripts/dev/hoh.py` entry point. The candidate includes strict versioned
schemas and validators, exact identity checks, atomic external state, isolated
role projections, controller-mediated disclosure, manifest-authorized
evidence-command replay, mandatory protected policy, trusted-shadow regular-file
Developer patch sealing, off-ref exact-parent candidate construction and atomic
compare-and-swap of the manifest-bound local branch with a sanitized Git
boundary and no shared-checkout mutation, durable pending-install recovery,
immutable candidate-tree projection materialization with executable modes
preserved, descriptor-relative no-follow state/projection storage and Developer
sealing, structured
failure/regression carry-forward,
regression-first replanning and handoff blocking, transactional Tester-state
acceptance, identity-checked pause retry, a verified `codex exec` adapter with an
explicit profile-bound absolute executable identity and trusted execution path,
one-shot manual packet and deterministic test
adapters, the exact-ticket B-05 manifest, and focused CPU coverage.

The native Python 3.11.16 diagnostic reports 76 focused tests passing. Ruff
0.16.3 passes on the new Python surface, every JSON schema parses, and diff
hygiene is clean. The real adapter probe identifies `codex-cli
0.151.0-alpha.7.2` but safely rejects it because its actual Developer exec path
reports legacy `workspace-write`, not the required custom permission profile.
The canonical wrapper remains locally `PAUSED_INFRA` because Docker and a
compatible Codex CLI are unavailable; exact-head GitHub checks remain required.
Dynamic final
head/tree, review, approval, merge, and exact-main identities belong only in
the external receipt.
