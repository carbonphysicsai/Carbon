## 2026-10-09 — OWNER-GRAPHITE-STAGE-A-01: the Graphite ladder wave's stage A grants (battery, kimi-k3)

**Authority.**
- **The figure.** The owner replied "Approve 2" to the Test Lead's exact line
  "approve Graphite stage A, $128.44". The Test Lead relayed it.
- **The relation to R4.** The owner confirmed it directly in the Test
  Engineer's session on 2026-10-09: a new USD 128.44 for all nine stage A
  runs, with R4's unused runs still spendable on top (not counted inside
  it).
- **The plan.** `docs/development/graphite/GRAPHITE_LADDER_WAVE_PLAN.md`
  section 4 (#889), stage A: Level 0 and Level 1 on battery, kimi-k3 at every
  role.

**Decision.**
1. **GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR** (phase 3):
   - 5 runs at USD 14.91 (R4's per-run worst case), cleanup 0.12, ceiling
     74.67;
   - `max_concurrency` 2, 39,600 s per run.
   - **Binding:** battery, main's blob, `min_level` 0 (Level 0 and above,
     unlike R4), start model kimi-k3 for the Constructor and Planner, and
     R4's token share of 11.93.
2. **GRAPHITE-GRANT-STAGE-A-ATTACKER** (phase 4):
   - 4 runs at USD 13.41 (10.00 model plus PHASE4's 3.41 worst case),
     cleanup 0.13, ceiling 53.77;
   - `max_concurrency` 2, 15,600 s per run (PHASE4's).
   - **Binding:** battery, main's blob, start model kimi-k3 for the Attacker.
   - **Model money:** PHASE4's plus 10.00, at least four full kimi-k3
     reservations, so an Attacker no longer stops before its first kimi-k3
     call (GRAPHITE-D35).
3. **The total** is 74.67 + 53.77 = USD 128.44, the approved stage ceiling.
   The 0.25 cleanup is split between the two grants.
4. **The code that binds them:**
   - `grant_binding.Phase3Grant` gains `start_roles`, `authority` and
     `runner`, so each grant's run conditions are its own; R4's are
     unchanged.
   - A phase-3 run refuses a phase-4 grant (`grant_is_not_a_phase3_grant`).
   - `phase4.PHASE4_STAGE_GRANTS` lets phase 4 accept a stage grant by its id
     for its Challenge only. Battery's default phase-4 grant, the dry run and
     prelive are unchanged.

**Not granted here.**
- **R4** is unchanged (45.00, 3 runs, Level 1 and above) and stays
  spendable.
- **Stages B and C** need their own approval.
- **Concurrency above 2** waits for a host-load check (plan section 4).
- **Running a level is not authorized by this grant.** Each run still needs
  the plan's entry conditions; L1 confirmation waits for VALIDATOR-25.
- **Scope.** No Level 4 run, no pod beyond what each runner already admits,
  and no production authority.

**Tests.**
- `tests/cpu/test_graphite_stage_a_grant.py`: the figures, both bindings,
  the kimi-k3 start rungs, the phase-3 refusal, phase 4 for battery only,
  and the Attacker's model money.
- `test_graphite_phase3_r4_grant.py` now skips stage A's own grants in its
  "no other grant has conditions" loop.
- The grant, R4, cooling-CPU, phase-4 and Attacker suites: 190 passed.
