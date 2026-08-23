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

For the present board, Wave A remains active until `.agent/WAVE.md` and the current Build Out acceptance checklist are evidence-backed. A later wave described in the Agentic Master Plan is **not permission to start it**.

Current next-ticket authority comes from `.agent/WAVE.md`.

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
6. stop if a human scientific/economic/security decision is missing.

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
7. Stop for review/merge unless explicitly allowed to continue.
8. On repeated failure or unresolved science/architecture/economic/security decision: mark blocked, report, do not invent.

Complex tickets: use `agent_pack/PLANS.md`; write under `.agent/plans/`.

---

## Constitutional semantics agents must preserve

### Current Wave-A mechanics

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
4. if a material behavior decision remains unresolved, stop and request owner decision.

Do not silently implement the future design into current code and do not preserve stale behavior merely because an old document mentions it.

---

## Success

For the active Wave-A board, success remains:

- current Wave A acceptance criteria green;
- concrete implementation/test/review evidence recorded;
- no constitutional invariant regression;
- `.agent/WAVE_A_REPORT.md` written after all A0–A12 are truly done.

Later waves have their own evidence gates and may separately be `SPECIFIED`, `IMPLEMENTED`, `TESTED`, `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`, `NETWORK_QUALIFIED`, `COMMERCIALLY_VALIDATED`, and `PRODUCTION_QUALIFIED`.

Never infer a later maturity state from an earlier one.

---

## Optional executors

Harness-specific config lives under `agent_pack/executors/` only — never as competing authority in the pack root.
