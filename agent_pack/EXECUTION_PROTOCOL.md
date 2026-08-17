# Execution Protocol — Carbon Wave work

**Executor-agnostic.** Use with Codex, Hermes, Claude Code, Cursor agents, or a human developer.

Model choice, API keys, and vendor harness config are **out of band** (see optional `agent_pack/executors/`). This file is only: how to take tickets safely against Carbon.

**Build_Out:** v1.4  
**Constitution:** repo root `AGENTS.md`  
**Board / tickets (canonical):** repo root `.agent/`

```text
Carbon/
├── AGENTS.md
├── .agent/           ← WAVE, ORIENTATION, DECISIONS, INVARIANTS, tickets/, plans/
├── agent_pack/       ← this protocol, PLANS template, optional executors/
└── Design_Specs/
```

Do **not** use `agent_pack/.agent/` — that path is retired.

---

## Mission (Wave A default)

Execute **Wave A only** until the Wave A acceptance checklist in `Design_Specs/Build_Out.md` §12 is evidence-backed. Then stop and report unless a human expands scope.

**Recommended start:** ticket **A-1 only**. Review orientation before A0.

---

## Spec pin

- Authoritative sequencing doc: `Design_Specs/Build_Out.md` **version 1.4**
- At orientation, record in `.agent/ORIENTATION.md`:
  - `git` commit SHA
  - Build_Out version string

---

## Mandatory orientation (before A0)

1. Map the repo tree
2. Read Build_Out v1.4 (§0–§8, §12), Miner_MCP, Scoring, README/SPEC, existing PoC/logic
3. Classify major modules: **KEEP / WRAP / REPAIR / REPLACE**
4. Write `.agent/ORIENTATION.md`
5. Only then open ticket **A0**

**Audit-first:** reuse/wrap/repair before create/replace.

---

## Ticket loop

```text
orientation → one ticket → baseline tests → implement → baseline + ticket tests
  → human/reviewer merge → next ticket
```

1. Open next `todo` ticket under **`.agent/tickets/`** (order in `.agent/WAVE.md`)
2. Prefer one branch/worktree per ticket
3. **Before edits:** run existing pytest / PoC smoke; record result
4. Implement minimum DoD; prefer WRAP/REPAIR
5. **After edits:** baseline suite again + ticket tests
6. Update `.agent/WAVE.md` status + evidence
7. Stop for review/merge unless human allows continue
8. On repeated failure or unresolved science/architecture decision: mark `blocked`, report, do not invent

Complex tickets: use `agent_pack/PLANS.md` template; write plan under `.agent/plans/`.

---

## Protocol semantics agents must implement correctly

- Submission FSM includes **`CANCELLED`**; **`FAILED_INFRA`** ≠ physics fail (refund/retry)
- Idempotency key: `strategy_hash + hotkey + challenge version`
- LIVE gate: qualification **hashes bound to exact challenge version**
- TrainEval **stub**: `emission_capable=False`
- Observability: structured logs + metrics/failure tags; no seed leakage

---

## Success

Wave A §12 checklist green with evidence. Hand off with `.agent/WAVE_A_REPORT.md`.

---

## Optional executors

Harness-specific config lives under `agent_pack/executors/` only — never as competing instructions in the pack root.
