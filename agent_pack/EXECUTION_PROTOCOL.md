# Execution Protocol — Carbon Wave work

**Executor-agnostic.** Use with Codex, Hermes, Claude Code, Cursor agents, or a human developer.

Model choice, API keys, and vendor harness config are **out of band** (see optional `agent_pack/executors/`). This file is only: how to take tickets safely against Carbon.

**Repository constitution:** `CONSTITUTION.md`  
**Scientific canon:** `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`  
**Build sequencing:** `Design_Specs/Build_Out.md` v1.4 + `Design_Specs/Build_Out_Constitutional_Overlay.md`  
**Long-horizon plan:** `Design_Specs/Agentic_Development_Master_Plan.md`  
**Agent constitution:** repo root `AGENTS.md`  
**Board / tickets (canonical):** repo root `.agent/`  
**Delegated decisions:** `.agent/DELEGATED_DECISION_PROTOCOL.md`

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
5. `.agent/DELEGATED_DECISION_PROTOCOL.md`
6. ticket-referenced domain specifications
7. `Design_Specs/Build_Out_Constitutional_Overlay.md` for A8 onward
8. `Design_Specs/Agentic_Development_Master_Plan.md` only for relevant future-compatibility constraints

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
6. identify any unresolved reserved human decision; keep the affected behavior explicit, bounded, and fail closed without blocking unrelated authorized work.

**Audit-first:** reuse/wrap/repair before create/replace.

---

## Ticket loop

```text
orientation/current authority
→ one ticket
→ baseline tests
→ working contract / material decisions where needed
→ notify applicable decision inboxes
→ implement minimum DoD
→ ticket + regression tests
→ independent technical review
→ normal merge
→ board evidence
→ next ticket
```

1. Open next `todo` ticket under `.agent/tickets/` in `.agent/WAVE.md` order unless owner authorizes otherwise.
2. Prefer one branch/worktree per ticket.
3. **Before edits:** run relevant baseline tests / PoC smoke and record result.
4. Implement the minimum coherent change; prefer KEEP/WRAP/REPAIR.
5. Material engineering decisions inside the authorized ticket follow `.agent/DELEGATED_DECISION_PROTOCOL.md`: select the agent-recommended approach, record it, notify the applicable lead, and continue unless an explicit block applies.
6. **After edits:** run baseline + ticket-specific + invariant tests.
7. Update `.agent/WAVE.md` status/evidence only after merge/acceptance rules are satisfied.
8. Stop at the ticket's bounded review/merge boundary, not at every material engineering decision. An explicit `REQUEST_CHANGES` or `BLOCKED` direction pauses the affected change. A reserved human decision blocks only the behavior that cannot proceed correctly with a fail-closed seam; unrelated authorized work continues.
9. On repeated implementation failure, mark the affected ticket or sub-scope blocked and report it without weakening tests or authority boundaries.

Complex tickets: use `agent_pack/PLANS.md`; write under `.agent/plans/`.

---

## Development decisions and asynchronous lead oversight

Development authorization comes from the active Wave and selected ticket, not from prior multi-role approval.

A material development decision must be recorded in `.agent/DECISIONS.md` or the applicable ticket, plan, or specification. Decisions in Carbon's SciML / Technical Lead lane must be surfaced in GitHub issue #42 and mention `@harshaa765`. Owner-reserved decisions and decisions explicitly deferred by a lead route to owner issue #41.

Notification is evidence of delivery and visibility, not approval. No affirmative response, reaction, approval, or waiting period is required for agent-authorized engineering work.

A decision is material when it changes or selects:

- architecture or domain ownership;
- a contract or invariant;
- a public interface or persisted schema;
- scientific assumptions or evidence interpretation;
- security or disclosure boundaries;
- rights or data-use policy;
- operational or resource policy;
- Wave or ticket sequencing; or
- a KEEP / WRAP / REPAIR / REPLACE disposition with cross-ticket impact.

Routine implementation details inside an already selected working contract do not require a separate notification.

Each material-decision record and notification must include:

1. the decision ID and affected ticket;
2. the problem being decided;
3. the agent-recommended approach;
4. implementation location, commit and pull request when available;
5. alternatives rejected and why;
6. invariant, interface, sequencing and downstream effects;
7. reversibility and migration cost;
8. the exact files / decision headings to change or supersede if the lead disagrees;
9. any unresolved human-reserved input; and
10. the agent recommendation if unchanged, normally `KEEP`.

Each material-decision PR must include a `Lead notification` section pointing to the applicable inbox comment.

### Lead actions

The lead may respond:

- `KEEP <decision-id>`;
- `CHANGE <decision-id>: <direction>`;
- `BLOCKED <decision-id>: <reason>`;
- a GitHub `REQUEST_CHANGES` review; or
- `DEFER_TO_OWNER <decision-id>: <question or recommendation>`.

`KEEP` is useful evidence but is not required for development to continue.

`CHANGE`, `BLOCKED`, or `REQUEST_CHANGES` pauses the affected change once observed. Unrelated work remains governed by its own ticket authority.

`DEFER_TO_OWNER` requires Codex to post the complete decision package to issue #41, preserving both the agent recommendation and the lead's recommendation/question. Development continues where the unresolved choice can remain fail-closed. A genuinely owner-reserved value remains unavailable until the owner decides it.

A lead may adjust a decision before merge or after merge through a new bounded superseding repository change. Historical evidence must not be rewritten. Current merged authority controls until a superseding change normally merges.

This delegated process does not authorize agents to decide scientific truth, production thresholds or tolerances, real Challenge populations/SamplingPlans/evidence weights, qualification outcomes, security acceptance, legal/commercial rights, live economics, production deployment, launch readiness, or other decisions explicitly reserved to humans. Missing reserved inputs remain explicit and fail closed. They do not prevent unrelated fixture, schema, interface, test, canonicalization, storage, or infrastructure development.

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
4. if the choice is material but within delegated development authority, select the recommended approach, record it, notify the applicable lead, and continue;
5. if the choice is reserved to humans, route it to the appropriate inbox, keep the affected behavior fail closed, and continue unrelated work; stop the whole ticket only if no correct bounded implementation can proceed without that reserved decision.

Do not silently implement the future design into current code and do not preserve stale behavior merely because an old document mentions it.

---

## Success

For the active board, success remains:

- the selected ticket's exact acceptance criteria and DoD are green;
- concrete implementation, test, CI, review, and normal-merge evidence is recorded;
- material decisions and required lead notifications are durable;
- no constitutional invariant regresses;
- ticket and Wave evidence accurately preserve all unearned maturity states.

Each capability may separately be `SPECIFIED`, `IMPLEMENTED`, `TESTED`, `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`, `NETWORK_QUALIFIED`, `COMMERCIALLY_VALIDATED`, and `PRODUCTION_QUALIFIED`.

Never infer a later state from an earlier one.

---

## Optional executors

Harness-specific config lives under `agent_pack/executors/` only — never as competing authority in the pack root.
