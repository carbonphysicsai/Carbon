# Skill: Carbon Wave A Builder

When the user says to build Carbon, execute Wave A, or continue tickets:

1. If `.agent/ORIENTATION.md` is missing, complete ticket **A-1** first (full repo read + orientation note).
2. Read `HERMES_KICKOFF.md` (repo root or agent_pack/), `.agent/INVARIANTS.md`, `.agent/MODEL_ROUTING.md`, and `.agent/WAVE.md`.
3. Open the next `todo` ticket in `.agent/tickets/` (A-1, then A0→A12).
4. Implement minimum viable DoD; add tests first or with code.
5. Run the ticket’s test command.
6. Update `.agent/WAVE.md` status + evidence.
7. On fail twice: mark `blocked` or one Grok escalate if configured; log in DECISIONS.md.
8. When all Wave A rows are `done`, write `.agent/WAVE_A_REPORT.md`.

Never invent LIVE thresholds. Never mark emission_capable on stubs.
Default model glm-5.2; escalate grok-4.6 only per MODEL_ROUTING.md.
