## 2026-10-04 — OWNER-GRAPHITE-PHASE3-REFUND-01: phase-3 sessions 2 and 3 are refunded through a two-run grant, GRAPHITE-GRANT-PHASE3-R2

**Authority.** The owner, 2026-10-04, in the Test Lead session:

- Asked whether Graphite phase-3 session 2 counts as one of
  GRAPHITE-GRANT-PHASE3's three runs, the owner answered: "no".
- Asked to approve a replacement grant of 2 runs and USD 10.07, which also
  refunds session 3, the owner answered: "approve R2".

**Why.** Neither session was a test of Graphite. Both failed on Carbon harness
defects:

| Session | Run | REF | What failed | Model spend | Pods |
| --- | --- | --- | --- | --- | --- |
| 2 | — | ff796899 | Stopped `context_ceiling` after 2 model calls. Fixed by GRAPHITE-D34 (#560) | USD 0.0063 | none |
| 3 | `graphite-18fc7b1c1eeea8aa` | ac78f661 | `sqlite3.ProgrammingError` at the first pod launch: the operator_compute store was opened on the main thread and used from `asyncio.to_thread`. Fixed separately (the Test Engineer's pod-thread PR) | USD 0.0055 | none created; ledger `pod_launch_refused`, settled USD 0 |

Session 1 (a harness error, GRAPHITE-D33) stays counted, as the owner decided
on 2026-10-03 ("fine either way").

**Why a new grant rather than an edit.** The controller refuses a run once
`len(rows) >= grant.permitted_runs`, whatever each run's outcome
(`carbon/agent_campaign/controller.py:534`). Its store binds the exact grant
document it first opened and refuses any other
(`grant_changed_under_existing_store`, `controller.py:191-196`). So
GRAPHITE-GRANT-PHASE3 stays as it is, at 3 of 3 runs used, and can never launch
again. The refund is a separate grant run in a fresh controller root.

**Decision.**
1. **New grant `GRAPHITE-GRANT-PHASE3-R2`.** It is identical to
   GRAPHITE-GRANT-PHASE3 except for:
   - `grant_id`;
   - `permitted_runs` 2;
   - `max_submissions` 2;
   - `monetary_ceiling` USD 10.07.

   Its arithmetic is in `docs/development/graphite/grants/README.md`.
2. **It runs in a fresh controller root.** Its run count starts at 0, and it
   uses the same per-run worst case (USD 4.91) and cleanup allowance (USD 0.25).
3. **Total phase-3 exposure stays inside the original approval.** About
   USD 0.015 has been spent across sessions 1–3. Adding R2's ceiling of
   USD 10.07 gives a worst case of about USD 10.09, inside the original
   USD 15.00. The old grant's unused headroom can never be spent, because it
   cannot launch.
4. **Entry conditions for each R2 run.** These apply in addition to the
   existing phase-3 handoff:
   - the pod-thread fix has merged;
   - the real-path no-spend pre-live check passes at the run's REF. That check
     drives the real provider client and pod/compute store under live
     threading, with only the network faked;
   - the owner confirms the REF;
   - the operator host is agreed with Data Collection.

**No execution.** This record dispatches, provisions and spends nothing.
