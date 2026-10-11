## 2026-10-11 — OWNER-TESTNET-WEEKLY-BUDGET-01: a standing testnet testing budget of one hundred fifty US dollars per week

**Authority.** The owner's words, as the Test Lead relayed them from its session:

> approve $150/week testing budget

> 150 a week is good

The Test Lead relayed both to the coordinating session. The owner confirmed to the
Graphite Testing Manager session on 2026-10-11 that he approved it, verbatim as the Test
Lead relayed it. This record is written by the Graphite Testing Manager at the
coordinator's request.

**Decided.**
1. **The figure: one hundred fifty US dollars per week** (USD 150), as a rolling seven-day
   cap, for testnet testing: pods plus model charges.
2. **Where it is enforced.** The host-level cross-root ledger of PR #1067
   (`carbon/agent_campaign/grant_runs.py`): a launch whose worst-case run cost would take
   the last seven days of recorded spend over the cap is refused (`weekly_budget_reached`).
   A run is reserved at its grant's worst-case run cost and settled at its reported cost.
   It fails closed: an unreadable or corrupt ledger, or a cost that cannot be read,
   refuses the launch. It counts only ids, digests, timestamps and cost totals per run:
   no balance and no account.
3. **Unchanged.** Per-run caps, the 0.65 per hour pod rate ceiling and the grants' run
   counts stay; the weekly cap is an additional bound, not a replacement. Each grant file
   still binds its own spend.
4. **The weekly report.** `python -m carbon.agent_campaign.grant_runs weekly` prints one
   line for the Test Lead: the rolling seven-day total against the cap, the remainder and
   the run count.

**Still the owner's.** These stay with the owner and are not covered by this budget:
- server runs (CCX63);
- mainnet;
- anything over the cap.

**Not decided here.** This is a spend ceiling for development testing on testnet. It
authorizes no mainnet action, no scientific or security acceptance, and no LIVE or
launch authority. The window starts with the ledger: spend before it is not known to it.
