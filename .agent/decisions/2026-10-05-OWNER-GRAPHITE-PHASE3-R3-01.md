## 2026-10-05 — OWNER-GRAPHITE-PHASE3-R3-01: a third phase-3 battery grant, GRAPHITE-GRANT-PHASE3-R3

**Authority.** The owner, 2026-10-05, in the Test Lead session. The Test Lead
proposed another three-run battery Constructor grant at the same per-run limit
(worst case USD 4.91 per run, ceiling USD 15.00), noting that actual runs have
cost about USD 3. The owner answered: "approve new grant".

**Why.** Both earlier battery Constructor grants are used up:

| Grant | Runs used |
|---|---|
| GRAPHITE-GRANT-PHASE3 | 3 of 3 |
| GRAPHITE-GRANT-PHASE3-R2 | 2 of 2 |

Phase-3 run 5 produced the wave's first promotable construction, and further
battery Constructor runs are needed, including the coming Level 1 runs on
development variants.

**Decision.**
- **New grant `GRAPHITE-GRANT-PHASE3-R3`.** It is identical to
  GRAPHITE-GRANT-PHASE3-R2 except for:
  - `grant_id`;
  - `permitted_runs` 3;
  - `max_submissions` 3;
  - `monetary_ceiling` USD 15.00.
- **Arithmetic.** The validator check is 0.25 + 4.91 ≤ 15.00. The third run's
  launch gate is at most 2 × 4.91 + 4.91 + 0.25 = 14.98 ≤ 15.00.
- **Where it runs.** In a fresh controller root, because a store binds one
  grant document.
- **Entry gate.** Each run follows the OWNER-GRAPHITE-TEST-WAVE-05 §3
  checklist and requires pod-attribution-v2 (the GPU probe) on main.

**No execution.** This record dispatches, provisions and spends nothing.
