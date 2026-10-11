## 2026-10-08 — OWNER-DASHBOARD-01: a public leaders dashboard and a live design showcase

**Authority.** The owner, 2026-10-08, in the Carbon Dashboard session:
"we have to have an awesome dashboard with leaders and their scores. I also
want to have a live design optimizer display of the leaders performance on a
design task against the solver."

**Scope, as directed:**
1. **Leaderboard and miner pages.** A public dashboard per Challenge and
   device class: leaders, standing, incumbent against challengers, each
   miner's per-section scores shown rounded and never case-level, full
   case-level breakdowns only for retired, published batches, and trends.
   Source: the Carbon Validator's signed score feed (VALIDATOR-29), built
   against fixtures until it ships.
2. **The design showcase.** The current leader's model drives Carbon's
   registered design optimizer (`design_search`) on a public design task, on
   retired or published material only, never hidden or live material. It
   shows the search path, predicted objective and safety margins at each step
   against the reference solver's truth, the final pick against the true
   best-in-bank, regret in buyer units, and safety-limit misses. Animated,
   precomputed server-side from public material, and honest about where the
   model is wrong.
3. **Disclosure and claims.** No private hotkey data. No miner recipes (show
   predictions, not architectures) unless the miner opts in. No hidden cases,
   seeds or references. Labelled TESTNET / DEVELOPMENT. No qualification or
   "matches reality" claims.

**Not decided here** (fail closed until the owner decides; see
`docs/development/DASHBOARD_PLAN.md` §7):
- hosting, route and deployment, and any spend;
- live scores on unretired windows (VALIDATOR-29 item 1);
- the recipe opt-in mechanism;
- a dollar conversion for regret.

This record grants no score, rank, frontier, weight, settlement, qualification
or production authority. The plan and ticket are DASHBOARD-01.
