# Skill: Carbon Wave A Builder

Executor-agnostic.

1. Read root **AGENTS.md** and **agent_pack/EXECUTION_PROTOCOL.md**.
2. If `.agent/ORIENTATION.md` is missing, complete ticket **A-1 only** first (Build_Out v1.4 pin, KEEP/WRAP/REPAIR/REPLACE).
3. Read `.agent/INVARIANTS.md` and `.agent/WAVE.md`.
4. Open next `todo` ticket under **`.agent/tickets/`** (not agent_pack/.agent).
5. Baseline tests → implement DoD (prefer WRAP/REPAIR) → baseline + ticket tests.
6. Update `.agent/WAVE.md`; stop for review unless human continues.
7. On repeated failure or unresolved science/architecture issue: `blocked` + report.
8. When Wave A is complete, write `.agent/WAVE_A_REPORT.md`.

Never invent LIVE thresholds. Never mark emission_capable on stubs.
Start with **A-1 only** before any implementation tickets.
