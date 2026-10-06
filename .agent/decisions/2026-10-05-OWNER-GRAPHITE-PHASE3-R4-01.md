## 2026-10-05 — OWNER-GRAPHITE-PHASE3-R4-01: battery Level 1+ starts on the top rung, GRAPHITE-GRANT-PHASE3-R4

**Authority.** The owner, 2026-10-05. Relayed by the Test Lead and confirmed
by Ryan directly in the Test Engineer session:

> "I agree that it's not necessary until the freedom is there to let it eat.
> Level 0 probably not needed. But 1 and up I want to see creativity. So I
> approve."

> "For 1 and up."

The approval covers USD 10 per run for model calls plus USD 5 per run for
compute, USD 45 in total, over 3 runs.

**Why.** Phase-3 runs 1–5 ran the Constructor on the cheap start rung
(`deepseek-v4-flash-0731`). At Level 1 and above the construction freedom is
wide enough for the strongest model to use. A full-window call on the top rung
reserves more than a Level 0 run's whole token share (below), so it needs a
grant of its own.

**Decision.**

1. **Start rung.** At construction Level 1 and above, the Constructor, and the
   Planner when used, starts on the top Engy ladder rung, `kimi-k3`.
   - Level 0 keeps today's start rungs, so runs 1–5 stay the cheap-model
     baseline.
   - The escalation rule is unchanged. There is simply no rung above the top:
     a stall there is recorded `ladder_top`.
   - The model is recorded per run as a run condition (`run_conditions` in the
     session record, beside `role.model`).
2. **New grant `GRAPHITE-GRANT-PHASE3-R4`.** It is identical to
   GRAPHITE-GRANT-PHASE3-R3 except for:
   - `grant_id`;
   - `monetary_ceiling` USD 45.00;
   - `worst_case_run_cost` USD 14.91, which is R3's compute-inclusive 4.91
     plus 10.00 for the model.

   `permitted_runs` 3 and `max_submissions` 3 are as in R3, and so are the
   expiry, account and `granted_by`.
3. **Token share.** Each R4 run's token share is fixed at USD 11.93 (the Test
   Lead's figure: 14.91 less 2.98 of compute), and its pods get the remaining
   2.98. Today's 12 pods need 2.96. If a later rate ceiling needs more than
   2.98, the budget is refused, typed.
4. **Binding** (`grant_binding.PHASE3_GRANTS`). R4 is bound to battery, to
   main's committed blob, and to Level 1 and above.
   - A Level 0 run under R4 is refused
     `grant_requires_construction_level_1_or_above`.
   - A Level 1+ session that would open below `kimi-k3` is refused
     `start_model_below_the_grants_start_rung`.
   - Every other grant behaves exactly as before.

**Arithmetic.**

    validator:     0.25 + 14.91                          = 15.16    ≤ 45.00
    run 3 gate:    2 × 14.91 + 14.91 + 0.25              = 44.98    ≤ 45.00
    kimi-k3 call:  1,048,576 × 1.95/M + 2,048 × 9.75/M   = 2.0646912 USD reserved
    in 11.93:      ⌊ 11.93 / 2.0646912 ⌋ = 5 full reservations
    in 10.00:      ⌊ 10.00 / 2.0646912 ⌋ = 4 full reservations

Each call settles at Engy's reported charge, so a run can make more calls than
that. Under a Level 0 run's token share (USD 1.95), not one full-window
`kimi-k3` call would be admitted.

**Level 1 timing.** This approval ("For 1 and up", confirmed by Ryan in the
Test Engineer session) clears battery Level 1 runs on R4. It supersedes
OWNER-GRAPHITE-TEST-WAVE-08 §5's wait for battery Level 1.

A run may start only when all of these entry conditions hold:

- the owner has picked a score variant;
- the `hidden_score` variant fix is merged;
- Level 0 run 3 has completed on the same variant;
- the Test Engineer's Level 1 hidden-path check says yes.

These are recorded as conditions only. They are not wired into code, because
none of them maps onto an existing check. Each R4 run also follows the
OWNER-GRAPHITE-TEST-WAVE-05 §3 checklist, in a fresh controller root.

**No execution.** This record dispatches, provisions and spends nothing.
