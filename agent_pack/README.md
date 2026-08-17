# Carbon agent pack — executor-agnostic Wave work

Bounded tickets + acceptance tests + invariants for building Carbon against **Build_Out v1.4**.

Works with **Codex, Hermes, Claude Code, Cursor, or a human**. The valuable pattern is:

```text
spec → bounded ticket → DoD → tests → review → next ticket
```

Not any single vendor harness.

---

## Start here

| Doc | Role |
|-----|------|
| **`/AGENTS.md`** (repo root) | Constitutional rules for every agent/human |
| **`EXECUTION_PROTOCOL.md`** | Wave ticket loop, orientation, audit-first |
| **`.agent/WAVE.md`** | Checklist / status board |
| **`.agent/INVARIANTS.md`** | Never-violate list |
| **`.agent/tickets/`** | A-1, A0–A12 work units |
| **`PLANS.md`** | Optional plan template for complex tickets |
| **`executors/`** | Optional harness-specific notes (Hermes, etc.) |

---

## Process rules (keep)

- Sync to **Build_Out v1.4**
- Mandatory orientation + **KEEP/WRAP/REPAIR/REPLACE**
- Preserve existing PoC / Grok-shipped code unless REPLACE is justified
- Baseline regression **before and after** each ticket
- One ticket per branch/worktree (harness-native is fine)
- Explicit stop / block on repeated failure or unresolved science decisions
- Stronger observability (logs + metrics + failure tags)
- v1.4 FSM/LIVE semantics (`CANCELLED`, FAILED_INFRA, hash-bound qualification)

---

## What moved out of the core protocol

Model routing (GLM/Kimi/Grok), Engy URLs, and Hermes `${VAR}` config are **not** part of the execution protocol. They live under `executors/` if you still use that harness.

---

## Suggested first gate

1. Orientation (A-1)  
2. A0 → A1 → A2 → A3  
3. Human review of orientation quality + diffs  
4. Continue Wave A  

---

## Out of scope unless human expands

Wave B/C/D full run, LIVE flip, inventing thresholds, Landscape/specialists, multi-agent swarm on core contracts.
