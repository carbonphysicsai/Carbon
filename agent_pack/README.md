# Carbon agent pack — executor-agnostic Wave work

Protocol docs and optional harness notes. **Live board and tickets live at repo root `.agent/`.**

```text
spec → bounded ticket → DoD → tests → review → next ticket
```

---

## Canonical paths

| Path | Role |
|------|------|
| **`/AGENTS.md`** | Constitution for every agent/human |
| **`/.agent/`** | WAVE, ORIENTATION, DECISIONS, INVARIANTS, tickets, plans |
| **`agent_pack/EXECUTION_PROTOCOL.md`** | Ticket loop |
| **`agent_pack/PLANS.md`** | Plan template for complex tickets |
| **`agent_pack/executors/`** | Optional Hermes/etc. only |

---

## Process rules

- Build_Out **v1.4**
- Orientation + KEEP/WRAP/REPAIR/REPLACE
- Baseline tests before/after each ticket
- One ticket per branch/worktree
- v1.4 FSM/LIVE hash semantics
- Start agents with **A-1 only**, then checkpoint

---

## First experiment

1. Run **A-1** orientation only  
2. Human reviews ORIENTATION.md  
3. If solid → A0→A3 → checkpoint  
4. Continue Wave A  
