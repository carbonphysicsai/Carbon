## 2026-10-05 — OWNER-GRAPHITE-LITERATURE-GRANT-01: a literature grant for cooling and motor

**Authority.** The owner, 2026-10-05, in the Test Lead session, answering the
Test Lead's request for the cooling and motor literature backfill grant
(VALIDATOR-08, gap 17 of the Graphite cooling readiness review):

> approve

The Test Lead relayed it to the Carbon Validator session the same day with
the grant's exact values.

**Decision.** The grant `GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR`
(`docs/development/graphite/grants/GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR.json`):

| Field | Value |
|---|---|
| Provider | `graphite` |
| Account | `Carbon-Account` |
| Monetary ceiling | USD 4.00 |
| Worst case per run | USD 2.49 (3,000 calls on `deepseek-v4-flash-0731` at the booked USD 0.00082944) |
| Permitted runs | 3 |
| Cleanup allowance | USD 0.10 |
| Maximum runtime | 360,000 s |
| Expires | 2026-12-31 |

It pays only the method-card extraction of a Challenge with a registered
literature profile (`phase2 triage --challenge`). Battery's phase-2 backfill
keeps its own grant, `GRAPHITE-GRANT-PHASE2`. The arithmetic is in
`docs/development/graphite/grants/README.md`.

**No execution.** This record dispatches, provisions and spends nothing. The
backfill runs as an operator step after the tooling (VALIDATOR-08) and this
grant are on main.
