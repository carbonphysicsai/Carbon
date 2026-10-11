## 2026-10-11 — OWNER-GRAPHITE-PHASE3-R4-CEILING-01: R4 at the standing 0.65/h pod ceiling, token share 10.99

**Authority.**
- **The standing ceiling.** The owner replied "approve a standing pod
  ceiling for all stages" to the Test Lead's proposal of USD 0.65/h
  (GRANT-POD-CEILING-01, amendment of 2026-10-10).
- **The cause.** At that ceiling, R4's 11.93 token share of a 14.91 run
  leaves its session's pods too little, so each R4 run is refused, typed.
  That blocks Level 1's further runs. GRANT-POD-CEILING-01 left R4 at 11.93
  on the default ceiling.
- **Confirmed directly.** In the Test Engineer's session the owner answered
  "Yes, 0.65/h + 10.99" to giving GRAPHITE-GRANT-PHASE3-R4 the 0.65/h pod
  ceiling and a 10.99 token share per 14.91 run, with its caps unchanged.
- **When it takes effect.** This record adds to OWNER-GRAPHITE-PHASE3-R4-01
  and leaves that record as merged. It binds when merged to main through PR
  Head, after the owner confirms it in PR Head's session.

**Decision.** As GRANT-POD-CEILING-01 did for stages A, B and C:

| Field | Value |
|---|---|
| `pod_rate_ceiling_usd_per_hr` | **0.65**, added to `GRAPHITE-GRANT-PHASE3-R4.json` |
| Token share (`grant_binding.PHASE3_GRANTS`) | **10.99** (`STAGE_TOKEN_SHARE`), was 11.93: five full kimi-k3 reservations |
| Pods per run | the 3.92 left of the 14.91 run, which is exactly the session's 12 pods at 0.65/h |
| Ceiling, runs, concurrency, per-run cap, submissions, runtime | unchanged: USD 45.00, 3, 1, 14.91, 3, 39600 s |

- **The grant's digest changes.** A store opened under the former R4
  document refuses to continue (`grant_changed_under_existing_store`), so
  further R4 runs start a new root.

**Maturity.** DEVELOPMENT spending authority only.
