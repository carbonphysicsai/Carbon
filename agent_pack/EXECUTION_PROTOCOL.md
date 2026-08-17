# Execution Protocol — Carbon Wave work

**Executor-agnostic.** Use with Codex, Hermes, Claude Code, Cursor agents, or a human developer.

Model choice, API keys, and vendor harness config are **out of band** (see optional `executors/` notes). This file is only: how to take tickets safely against Carbon.

**Build_Out:** v1.4  
**Companion:** root `AGENTS.md` (constitutional rules)

---

## Mission (Wave A default)

Execute **Wave A only** until the Wave A acceptance checklist in `Design_Specs/Build_Out.md` §12 is evidence-backed. Then stop and report unless a human expands scope.

Goal: mature, tested implementation so a developer starts halfway up the mountain—not unsupervised full-subnet ownership.

---

## Spec pin

- Authoritative sequencing doc: `Design_Specs/Build_Out.md` **version 1.4**
- At orientation, record in orientation note:
  - `git` commit SHA
  - Build_Out version string
- Do not let `main` drift redefine the contract mid-run without re-orienting

---

## Mandatory orientation (before A0)

1. Map the repo tree (`Design_Specs/`, `poc/`, `Carbon_Logic/`, `neurons/`, tests, CI, `agent_pack/`, …)
2. Read Build_Out v1.4 (§0–§8, §12), Miner_MCP, Scoring, README/SPEC, existing PoC/logic
3. Classify major modules: **KEEP / WRAP / REPAIR / REPLACE**
4. Write orientation note (path: `.agent/ORIENTATION.md` or `agent_pack/.agent/ORIENTATION.md`):
   - Repo map, commit pin, classification table, doc authority, gaps vs Wave A checklist, non-goals
5. Only then open ticket **A0**

**Audit-first:** reuse/wrap/repair before create/replace. Do not delete working trees for folder cosmetics.

---

## Ticket loop

```text
orientation → one ticket → baseline tests → implement → baseline + ticket tests
  → human/reviewer merge → next ticket
```

1. Open next `todo` ticket under `agent_pack/.agent/tickets/` (order in `WAVE.md`)
2. Prefer one branch/worktree per ticket (harness-native worktrees are fine; no custom branching engine required in-repo)
3. **Before edits:** run existing pytest / PoC smoke; record result
4. Implement minimum DoD; prefer WRAP/REPAIR
5. **After edits:** baseline suite again + ticket tests
6. Update `WAVE.md` status + evidence
7. Stop for review/merge unless human allows continue
8. On repeated failure or unresolved science/architecture decision: mark `blocked`, report, do not invent

Complex Wave B/C tickets: write a short plan first (see `PLANS.md` template). Small A tickets may skip formal plans.

---

## Protocol semantics agents must implement correctly

- Submission FSM includes **`CANCELLED`**; **`FAILED_INFRA`** ≠ physics fail (refund/retry)
- Idempotency key: `strategy_hash + hotkey + challenge version`
- LIVE gate: qualification **hashes bound to exact challenge version**, not merely non-null fields
- TrainEval **stub**: `emission_capable=False`
- Observability: structured logs + metrics/failure tags; no seed leakage

---

## Success

Wave A §12 checklist green with evidence. No invented LIVE thresholds. Existing green PoC/CI remains green or failures are explicit. Hand off with `WAVE_A_REPORT.md`: shipped items, tests, classification outcomes, blocked items, human/SciML next steps.

---

## Optional executors

Harness-specific config (Hermes yaml, Engy models, Codex project settings) belongs in `agent_pack/executors/` or the operator’s local env—not in this protocol.
