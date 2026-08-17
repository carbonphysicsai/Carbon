# Skill: Carbon Wave A Builder

When the user says to build Carbon, execute Wave A, or continue tickets:

1. If `.agent/ORIENTATION.md` is missing, complete ticket **A-1** first (full repo read, Build_Out **v1.4** pin, KEEP/WRAP/REPAIR/REPLACE table).
2. Read `HERMES_KICKOFF.md`, `.agent/INVARIANTS.md`, `.agent/MODEL_ROUTING.md`, and `.agent/WAVE.md`.
3. Open the next `todo` ticket in `.agent/tickets/` (A-1, then A0→A12).
4. Create branch `agent/wave-a/<ticket-id>`; do not commit straight to main.
5. Run **baseline** pytest/PoC smoke before edits.
6. Implement minimum viable DoD; prefer WRAP/REPAIR over REPLACE.
7. Run baseline tests again + the ticket’s test command.
8. Update `.agent/WAVE.md` status + evidence; log spend/escalations in DECISIONS.md.
9. On fail twice or soft $ budget exceeded: mark `blocked` or one Grok escalate if configured; stop and report.
10. Leave a clean diff for human/Codex review before the next ticket unless human allows continue.
11. When all Wave A rows are `done`, write `.agent/WAVE_A_REPORT.md`.

Never invent LIVE thresholds. Never mark emission_capable on stubs.
Default model glm-5.2; escalate grok-4.6 only per MODEL_ROUTING.md.
Hermes API keys must use `${VAR}` form.
