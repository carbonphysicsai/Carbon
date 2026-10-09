## 2026-10-10 — OWNER-GRAPHITE-STAGE-B-01: the Graphite ladder wave's stage B grants (battery L2-L3, kimi-k3)

**Authority.**
- **The approval.** The owner replied "approve" to the Test Lead's exact
  line "approve Graphite stage B, $143.35, up to 4 at once". The Test Lead
  relayed it.
- **Direct confirmation.** The owner confirmed it directly in the Test
  Engineer's session.
- **The plan.** `docs/development/graphite/GRAPHITE_LADDER_STAGE_B_PLAN.md`
  section 7 (#938).

**Decision.**
1. **GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR** (phase 3):
   - 6 runs at 14.91, cleanup 0.12, ceiling 89.58;
   - `max_concurrency` 4, 39,600 s per run;
   - **binding:** battery, main's blob, Levels 2 and 3 only (`min_level` 2,
     the new `max_level` 3), kimi-k3 start, and R4's 11.93 token share.
2. **GRAPHITE-GRANT-STAGE-B-ATTACKER** (phase 4):
   - 4 runs at 13.41, cleanup 0.13, ceiling 53.77;
   - `max_concurrency` 4, 15,600 s per run;
   - **binding:** battery, main's blob, kimi-k3 start for the Attacker,
     Levels 2 and 3 only (the new `Phase4Grant.levels`, checked by
     `live_checks` against the run's level).
3. **The total** is 89.58 + 53.77 = USD 143.35.
4. **A run at any other level** is refused
   `grant_level_outside_the_grants_levels`. R4's and stage A's level rules
   are unchanged.

**Not granted here.**
- **Running a level is not authorized by this grant.** The plan's
  prerequisites still apply (stage A's gate, an L1 Q1 report and #902).
- **Scope.** Not stage C or Level 4, and not main deployment.

**Tests.**
- `tests/cpu/test_graphite_stage_b_grant.py`;
- the stage A and R4 tests;
- `test_graphite_phase4.py`.
