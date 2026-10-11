## 2026-10-10 — OWNER-GRAPHITE-STAGE-C-01: the Graphite ladder wave's stage C grants (battery Level 4, kimi-k3)

**Authority.**
- **The approval.** The owner replied "Approve stage C" to the Test Lead's
  exact line "approve stage C, $71.80". The Test Lead relayed it.
- **Direct confirmation.** The owner confirmed it directly in the Test
  Engineer's session.
- **The plan.** `docs/development/graphite/GRAPHITE_LADDER_WAVE_PLAN.md`
  section 4 (#889), stage C.

**Decision.**
1. **GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR** (phase 3):
   - 3 runs at 14.91, cleanup 0.12, ceiling 44.85;
   - `max_concurrency` 4, 39,600 s per run;
   - **binding:** battery, main's blob, Level 4 only (`min_level` =
     `max_level` = 4), kimi-k3 start, and R4's 11.93 token share.
2. **GRAPHITE-GRANT-STAGE-C-ATTACKER** (phase 4):
   - 2 runs at 13.41, cleanup 0.13, ceiling 26.95;
   - `max_concurrency` 4, 15,600 s per run;
   - **binding:** battery, main's blob, kimi-k3 start for the Attacker,
     Level 4 only (`Phase4Grant.levels` (4,)).
3. **The total** is 44.85 + 26.95 = USD 71.80.
4. **A run at any other level** is refused
   `grant_level_outside_the_grants_levels`.

**Not granted here.**
- **No Level 4 live run.** Whether one runs stays the owner's and the
  security owner's (the plan's section 1 and the Level 4 isolation
  decisions). The grant authorizes spend only.
- **Running stage C is not authorized by this grant.** Each run still needs
  stage C's entry conditions.

**Tests.** `tests/cpu/test_graphite_stage_c_grant.py`, together with the
stage A, B and R4 grant tests.
