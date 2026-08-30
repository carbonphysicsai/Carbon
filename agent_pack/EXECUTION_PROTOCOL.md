# Execution Protocol — Carbon Wave work

**Executor-agnostic.** Use with Codex, Hermes, Claude Code, Cursor agents, or a human developer.

Model choice, API keys, and vendor harness config are **out of band** (see optional `agent_pack/executors/`). This file is only: how to take tickets safely against Carbon.

**Repository constitution:** `CONSTITUTION.md`  
**Scientific canon:** `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`  
**Build sequencing:** `Design_Specs/Build_Out.md` v1.4 + `Design_Specs/Build_Out_Constitutional_Overlay.md`  
**Long-horizon plan:** `Design_Specs/Agentic_Development_Master_Plan.md`  
**Agent constitution:** repo root `AGENTS.md`  
**Board / tickets (canonical):** repo root `.agent/`

```text
Carbon/
├── CONSTITUTION.md
├── AGENTS.md
├── .agent/           ← WAVE, ORIENTATION, DECISIONS, INVARIANTS, tickets/, plans/
├── agent_pack/       ← this protocol, PLANS template, optional executors/
├── Design_Specs/
├── docs/context/
└── Business/
```

Do **not** use `agent_pack/.agent/` — that path is retired.

---

## Mission

Execute the **currently authorized wave/ticket only**.

Wave A is closed in bounded engineering scope. Current wave and next-ticket
authority come exclusively from `.agent/WAVE.md`; a plan, future board, or
long-horizon document is not independent permission to start work.

---

## Mandatory authority read before every new ticket

1. `CONSTITUTION.md`
2. `.agent/INVARIANTS.md`
3. `.agent/WAVE.md`
4. ticket under `.agent/tickets/`
5. ticket-referenced domain specifications
6. `Design_Specs/Build_Out_Constitutional_Overlay.md` for A8 onward
7. `Design_Specs/Agentic_Development_Master_Plan.md` only for relevant future-compatibility constraints

If work touches customer/product/business semantics, also read:

- `Business/Business_Canon.md`
- the relevant `Business/` domain document.

If work touches publication/public claims, also read:

- `docs/publications/README.md`.

Do not rely on memory when the repository version exists.

---

## Spec pin

At the start of a new major wave or when orientation becomes materially stale, record/update in `.agent/ORIENTATION.md`:

- repository commit SHA;
- `Build_Out.md` version;
- constitution/canon documents used;
- any known migration overlay relevant to the active ticket.

Completed historical ticket evidence remains historical; do not rewrite it merely because the constitution broadened later.

---

## Orientation rule

Before substantial new implementation, understand the existing repository and the current maturity boundary.

Minimum orientation:

1. map relevant repo tree;
2. read Constitution, Build Out, overlay, current ticket domain specs;
3. inspect existing code/tests;
4. classify touched components **KEEP / WRAP / REPAIR / REPLACE**;
5. identify whether the active work is current-runtime implementation or a future migration seam;
6. identify any unresolved reserved human decision; keep the affected behavior
   explicit, bounded, and fail closed, and stop rather than invent it.

**Audit-first:** reuse/wrap/repair before create/replace.

---

## Ticket loop

```text
orientation/current authority
→ one ticket
→ baseline tests
→ implement minimum DoD
→ ticket + regression tests
→ review/merge
→ board evidence
→ next ticket
```

1. Open next `todo` ticket under `.agent/tickets/` in `.agent/WAVE.md` order unless owner authorizes otherwise.
2. Prefer one branch/worktree per ticket.
3. **Before edits:** run relevant baseline tests / PoC smoke and record result.
4. Implement the minimum coherent change; prefer KEEP/WRAP/REPAIR.
5. **After edits:** run baseline + ticket-specific + invariant tests.
6. Update `.agent/WAVE.md` status/evidence only after merge/acceptance rules are satisfied.
7. Stop for review and normal merge unless explicitly allowed to continue.
8. On repeated failure, mark the affected ticket blocked and report it. If a
   reserved human decision is required for correctness, stop the affected work
   rather than invent it. Material decisions within development authority use
   the notification process below.

Complex tickets: use `agent_pack/PLANS.md`; write under `.agent/plans/`.

---

## Development decisions and lead notification

Development authorization comes from the active Wave and selected ticket, not
from prior multi-role approval.

A material development decision must be recorded in `.agent/DECISIONS.md` or
the applicable ticket, plan, or specification, and Carbon's designated SciML /
Technical Lead, Harshdeep Sharma (`@harshaa765`), must be notified. Notification
is evidence of delivery, not approval: no affirmative response, reaction,
approval, or waiting period is required.

A decision is material when it changes or selects:

- architecture or domain ownership;
- a contract or invariant;
- a public interface or persisted schema;
- scientific assumptions or evidence interpretation;
- security or disclosure boundaries;
- rights or data-use policy;
- operational or resource policy;
- Wave or ticket sequencing;
- a KEEP / WRAP / REPAIR / REPLACE disposition with cross-ticket impact.

Routine implementation details within an already ratified contract do not
require a separate lead notification.

Each material-decision PR must:

1. record the durable decision;
2. include a `Lead notification` section identifying the decision ID or
   heading, affected ticket and files, selected approach, alternatives
   rejected, invariant/interface/sequencing effects, reversibility and
   migration effect, and the notification issue or comment;
3. post or update a notification in GitHub issue #42 and mention
   `@harshaa765`.

The lead may adjust the decision before merge through review or an explicit
direction, or after merge through a new bounded superseding repository change.
An explicit `REQUEST_CHANGES` review or `BLOCKED` direction pauses the affected
change; silence does not. Unrelated work remains governed by its own active
Wave and ticket. Current merged repository authority remains controlling until
a superseding change normally merges, and historical evidence must not be
rewritten.

This non-blocking process does not authorize agents to decide scientific truth,
thresholds, tolerances, Challenge populations or sampling claims,
qualification outcomes, security acceptance, legal or commercial rights, live
economics, production deployment, launch readiness, or other material company
decisions reserved to humans. An unresolved reserved decision remains explicit,
bounded, and fail closed. It does not prevent unrelated fixture, schema,
interface, test, or infrastructure development.

---

## Constitutional semantics agents must preserve

### Durable bounded mechanics inherited from Wave A

- submission FSM includes `CANCELLED`;
- `FAILED_INFRA` is not a physics fail and retains retry/refund semantics;
- LIVE gate binds qualification artifacts/hashes to the exact Challenge version;
- free/mock paths never access protected official material;
- fixture/stub execution cannot create production scientific/economic authority;
- A5 scoring does not own frontier/treasury policy;
- A7 lifecycle does not own frontier/treasury state;
- observability must redact protected exam material.

### Integrated scientific direction

- exam qualification precedes candidate qualification;
- scientific task owns population; `P`, `Q`, and `w` remain separate where applicable;
- admissibility precedes ranking;
- Challenge score is not automatically cross-Challenge comparable;
- rank/leaderboard does not automatically create a frontier event;
- scientific result and treasury settlement are separate;
- construction and official evaluation are separate security domains;
- long-term `TrainingStrategy -> ModelConstructionStrategy -> ConstructionProgram` broadening must not happen inside an earlier bounded ticket without explicit authorization.

### Business/publication boundary

- customer payment never changes the scientific ruler;
- business design is not traction;
- OpCo revenue does not automatically create Alpha value;
- publications explain but do not define protocol truth.

---

## Conflict procedure

If current runtime specs and the integrated constitution appear to conflict:

1. determine the domain owner;
2. check `Build_Out_Constitutional_Overlay.md`;
3. classify the seam as:
   - `NO_CONFLICT`
   - `DOCUMENTATION_LAG`
   - `IMPLEMENTATION_LAG`
   - `MIGRATION_REQUIRED`
   - `NEW_OWNER_DECISION_REQUIRED`;
4. if the choice is material but within development authority, record it and
   notify the designated lead; if it is reserved to humans and required for
   correctness, stop the affected work and request the smallest decision.

Do not silently implement the future design into current code and do not preserve stale behavior merely because an old document mentions it.

---

## Success

For the active board, success remains:

- the selected ticket's exact acceptance criteria and DoD are green;
- concrete implementation, test, CI, review, and normal-merge evidence is
  recorded;
- material decisions and required lead notifications are durable;
- no constitutional invariant regresses;
- ticket and Wave evidence accurately preserve all unearned maturity states.

Each capability may separately be `SPECIFIED`, `IMPLEMENTED`, `TESTED`,
`SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`, `NETWORK_QUALIFIED`,
`COMMERCIALLY_VALIDATED`, and `PRODUCTION_QUALIFIED`.

Never infer a later maturity state from an earlier one.

---

## Optional executors

Harness-specific config lives under `agent_pack/executors/` only — never as competing authority in the pack root.
