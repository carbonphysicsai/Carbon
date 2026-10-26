# OWNER-SPEED-GATE-500X-01: speed gate at 1/500 of the solver time per design

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25 ~03:00–03:10Z; relayed to the Validator, who specified it in codex-queue/reports/EXAM_ADDITIONS_20261025.md.
- **Owner's words:** "Yes. And let's do 500x."
- **Decided:** a pass/fail speed gate in the launch pool versions, the same rule for every Challenge: time per design ≤ the registered solver seconds per design ÷ 500 (carbon/challenge_registry/speed_gate.py is the single source; ceilings F02 0.38 s, F08 2.08 s, Cooling 2.84 s, Motor 3.3 s). It is never a score input; the closed code is GATE_FAILED (speed).
- **Measurement method (Validator, amended 2026-10-26, VALIDATOR_GRAPH_OPS_V8_RULINGS §10):** the MEDIAN of 20 single-design calls on custody-seeded sealed pool rows, each its own call after one untimed warm-up on a public row, timed by Carbon's fixed program on the grading class. This supersedes the earlier 'all-rows batched wall ÷ rows', which a per-call fixed cost or row recognition can game.
