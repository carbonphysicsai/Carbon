# Mira in internal admission testing: stages 1 and 2

**Ticket:** `.agent/tickets/MIRA-ADMISSION-01_mira_admission_integration.md`.
**Authority:** the owner's handoff "integrate Autoscience Mira into Carbon's
internal admission testing" (2026-10-01), under OWNER-CHALLENGE-ADMISSION-01 as
amended. This is internal development: not mainnet, not a qualification gate,
and not permission to deploy.

**State.** Code built and tested against a fake provider. No integration with
Mira has been demonstrated, no campaign has run, and no evidence has been
accepted. Live Mira execution is **BLOCKED** (see Blockers).

## 1. Repository reconciliation (handoff §2)

| Item | State at this branch's base |
|---|---|
| `main` | `aea352d3`, which includes the admission core (#473) |
| #473 admission core | Merged as `aea352d3`. It carries `carbon/challenge_readiness/admission.py`, `Design_Specs/Challenge_Admission.md`, the pressure test, `DESIGN_OPTIMIZER_SCOPE.md` and the EV1/EV2 audit |
| #458 | GitHub reports it **merged** (20:37:41Z) because its head `0e1e25c9` is an ancestor of main through #473. Its deferred content is **not** on main: the split commit `5fcdc172` reverted it. Main has no `--require-admission`, readiness records stay schema v2, and the held Workbench page is absent (main's page sha256 starts `be64f8b9`; #458's held page was `85a46875`). That deferred work needs a new PR; this branch does not touch it |
| #464 sealed hidden-batch disclosure | Merged (`f1429b60`): `exam.MINER_DISCLOSURE`, rule v2 |
| #468 construction expansion records | Merged (`aadaf233`): `carbon/reconstruction/expansion_record.py`, battery record `0000` |
| #470 divergence detector | Merged (`dc61a6e8`): `carbon/battery/value/divergence.py`, retained `ev2-conditions.json` |
| EV4 optimizer | On `claude/ev4-optimizer` (lead session; EV4 running under a pre-registration frozen 2026-10-01T20:09:26Z). **Not on main and not touched here** |

**Existing implementation reused.** `admission` ledger validators (KEEP; the
controller's ledgers pass through them), `expansion_record` (KEEP; expansions
bind its newest record), `divergence` output (KEEP; consumed as findings),
`agent_connection` (KEEP; tested with a real external client), the battery
contract, rule, disclosure and decision modules (KEEP; pinned and reused),
`research/durable.py`'s supervisor-lease pattern (WRAP into the controller).

**Missing before this work.** No supervisor for an external agent (the
connection module explicitly does not supervise); no spending grant or
reservation; no workspace separation or research-checkout allowlist; no
versioned search request/commitment; no external-process connection test;
no study sheet.

**Affected tests.** The handoff §14 list (all pass, unchanged) plus the new
suites below.

## 2. What is built (handoff §15 stage 2)

| Module | What it does |
|---|---|
| `carbon/agent_campaign/provider.py` | The adapter contract: proposed Carbon-side operations (capabilities, idempotent start, find by key, status, events, artifacts, cancel, usage), not vendor endpoints |
| `carbon/agent_campaign/mira.py` | The Mira adapter: planned artifact-handoff mode, `verified=False`, every operation refuses |
| `carbon/agent_campaign/fake.py` | Deterministic test double with fault injection (timeouts before and after creation, unknown state and usage, cancel leaving workers) |
| `carbon/agent_campaign/grant.py` | The owner's spending grant; every value required; `grant-template` prints it with HUMAN_INPUT |
| `carbon/agent_campaign/boundaries.py` | Four roles; separate workspaces and credentials; allowlisted research checkout (manifest + digests, denylist wins, no symlinks); canaries |
| `carbon/agent_campaign/controller.py` | The durable controller (below) |
| `carbon/agent_campaign/study.py` | Level-0 study sheet and permission inventory; `docs/development/mira/level0/` |
| `carbon/battery/value/search_commitment.py` | Versioned design-search request, budgeted model oracle, commitment before reference access, verified result, comparison harness |
| `carbon/battery/value/ev4_protected_conditions.py` | EV4's conditions, refused by every request and query, and kept out of every research checkout |

**The controller** persists intent and reserves the grant's worst-case run cost
before dispatch; records provider run and worker ids; reconciles ambiguous
timeouts by idempotency key instead of retrying; enforces grant and
per-campaign ceilings, concurrency, run count, runtime and submissions; halts
dispatch on unknown usage, unknown state, unresolved dispatch, incomplete
cleanup or canary exposure; cancels with a recorded request and verifies every
worker stopped, leaving `CLEANUP_INCOMPLETE` as an actionable state; records
findings (consuming the divergence report) and refuses any expansion after one;
binds each expansion to the newest #468 construction record; keeps a
hash-chained attempt ledger of every launch, timeout, reconciliation, event,
artifact, rejection, cancellation and finding. Agent output is stored as data
and never interpreted. A finding's evidence and the ledgers live under the
controller's private root, which no research checkout contains.

**The optimizer layer** is a separate later experiment
(`MIRA-OPTIMIZER-DEV-01`), not EV4. It reproduces `optimizer.mode_d` and
`optimizer.mode_x` exactly on EV4's model grid (conformance test; run as a
diagnostic against the EV4 branch's file, skipped on main where that file is
absent). Development material is EV2's published conditions; any EV4 condition
is refused.

## 3. Level 0, prepared not executed

`level0/study-sheet.json` and `level0/permission-inventory.json`
(`python -m carbon.agent_campaign study --out docs/development/mira/level0`;
`--check` reports pin drift). Eight of ten pins are computed from real sources;
`budget` and `population` are unpinned (human-reserved), so the sheet is
`DRAFT_NOT_FROZEN` and `freezable: false`. Every check is `NOT_RUN`. Each attack
family has a registered diagnostic specimen and valid control, to run in the
diagnostic harness only. The inventory records that today's Level 0 already
admits declarative surfaces the planning ladder places at levels 1, 2 and 5.

## 4. Working engineering decisions (delegated; a lead may change any)

- **MIRA-D1** New package `carbon/agent_campaign` instead of extending
  `carbon/research` (its providers are Carbon-internal B-07 research tasks with
  different semantics). Rejected: putting supervision in `agent_connection`,
  which is documented as not supervising.
- **MIRA-D2** Integration mode: repository/artifact handoff, unverified, so not
  dispatchable. Rejected: guessing an API.
- **MIRA-D3** Research-checkout allowlists of published material per role, with
  a denylist (`.agent/`, evidence, `ev4`, `confirmation`, the controller) that
  wins. To change: edit `boundaries.ALLOWLIST` / `DENY_*`.
- **MIRA-D4** Findings from canary exposure are recorded as `OTHER_SIGNAL`
  (the admission vocabulary has no exposure condition) and also halt dispatch
  until an operator clears the halt with a reason; the finding stays.
- **MIRA-D5** The optimizer comparison uses EV2's published development
  conditions and refuses all EV4 conditions, not only EV4's confirmation set.

## 5. Blockers and the smallest decision each needs

| Blocker | Smallest decision required |
|---|---|
| Live Mira execution | The owner sends the inquiry in `CAPABILITY_REPORT.md` and supplies verified answers (documentation or account evidence) for at least: task supply, cancellation with worker confirmation, usage reporting, workspace separation, red-team scope and output rights |
| Spending grant | The owner completes `grant-template`: account, expiry, grant ceiling, per-campaign ceilings, worst-case run cost, limits (recommendations in `COST_ESTIMATE.md`) |
| Freezing the Level-0 sheet | Science owner: the study population and reconstruction tolerances. Owner: the attack/confirmation budget. Security owner: approve the attacker model and the isolation scope |
| Hostile executable tests | Security owner: the disposable isolated worker and its verified restrictions. Level 0 is declarative only, so executable-code families stay `NOT_RUN` |
| PB-INV/PB-ADV acceptance policies | Science owner (`DESIGN_OPTIMIZER_SCOPE.md` §4); the layer reports and never passes or fails |
| #458's deferred content | Lead: reopen it as a new PR (GitHub shows #458 merged though its content is reverted on main) |
