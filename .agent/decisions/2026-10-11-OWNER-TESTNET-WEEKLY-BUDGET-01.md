## 2026-10-11 — OWNER-TESTNET-WEEKLY-BUDGET-01: a standing testnet testing budget of one hundred fifty US dollars per week

**Authority.** The owner's words, as the Test Lead relayed them from its session:

> approve $150/week testing budget

> 150 a week is good

The Test Lead relayed both to the coordinating session. The owner confirmed to the
Graphite Testing Manager session on 2026-10-11 that he approved it, verbatim as the Test
Lead relayed it. This record is written by the Graphite Testing Manager at the
coordinator's request.

**Amended 2026-10-12 — the standing test grant (OWNER-TEST-GRANT-01).** The
owner found the per-run asks an obstacle: "These individual grants are an
annoyance. We need a test grant." Asked for the figure and the terms in one
question, he answered:

> Yes — 300/week, 50 per run, but fix the ledger first

So, from this amendment:
- **The figure is USD 300 per rolling seven days**, replacing the USD 150
  below. One pot that all testnet testing draws from — the score proof, data
  collection and Graphite alike.
- **Per-run safety cap: USD 50.** A single run above that still needs its own
  owner record.
- **Per-run approval is removed when #1168 is on main, and not before.** The
  condition he attached was "fix the ledger first": individual runs stop
  needing his approval only once the ledger is a sound sole control. He was
  offered the version effective immediately and declined it, on the ground
  that once per-run approval goes the ledger is the only control on spend.
- **How the condition is met, which is not how it was worded.** He asked for
  the ledger to count settled pod charges. It cannot: the provider never
  reports a pod's charge, so there is no settled figure to count, and #1168
  says so plainly — "the ledger holds no settled pod charge of its own".
  Instead #1168 refuses to ever count *less*: an unresolved pod stays counted
  at its **full reservation**, only a provider-reported charge or a zero-cost
  refusal lowers a run's count, an unreadable root refuses the seed, and
  seeded historical spend counts against new launches and rolls off at its own
  start time. Put that way to him, he answered:

  > Yes — that satisfies it, lift per-run approval

- **So the cap binds on worst-case reservations, not on actual spend.** That
  is the deliberate trade. If a reservation overestimates, a launch is refused
  slightly earlier than the real spend required. If a reservation ever
  underestimates a real charge, actual spend can exceed USD 300 without the
  ledger refusing anything — the worst-case basis is the only thing guarding
  that, so a grant's `worst_case_run_cost` being honest is now load-bearing.
- **Still their own record regardless of the cap:** anything carrying sealed
  or hidden material — custody is a security acceptance and stays separate
  from spend — anything on mainnet, anything touching LIVE, and any run above
  the per-run cap.
- **A weekly spend summary goes to the owner.**

Today's four grants (USD 86.71 + 44.85 + 25 + 16 = USD 172.56) fit inside 300
with about USD 127 to spare; they did not fit inside 150, which is what forced
the question.

**Decided (as originally recorded, superseded in part by the amendment above).**
1. **The figure: one hundred fifty US dollars per week** (USD 150), as a rolling seven-day
   cap, for testnet testing: pods plus model charges. **Superseded: the figure
   is now USD 300.**
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
