## 2026-10-12 — OWNER-PROVEN-LEADERBOARD-01: the proven leaderboard replaces the king showdown, with top-3 comparison slots at ≤ 1 % false crowns a day

**Authority.** The owner, 2026-10-12, answering the VALIDATOR-32 rev 8
decision page, typed in the Test Lead session and relayed verbatim by the
Test Lead:

> 1 yes, 2 yes, 3 I dont know about this S=10%, 4 this is like 2k a month
> there's no way in hell, 5 maybe

These are scientific and design decisions, not security acceptances.

**Decided:**
1. **The proven leaderboard replaces the king showdown** (VALIDATOR-32
   rev 8, `TICKET_DRAFT_VALIDATOR32_REV8.md`, PROVEN-LEADERBOARD-01 to -08).
   Battery testnet's takeover becomes a comparison with the leader:
   - paired, on cases first exposed after both models froze, each case
     counted once;
   - decided by a time-uniform empirical-Bernstein lower bound with
     asymmetric clipping to [−8, 2];
   - a crossing that has a lower clip is held.
2. **Top-3 comparison slots:**
   - at most 3 new comparisons per rolling 24 h, at α = 3.3e-3 per
     comparison, so **≤ 1 % false crowns a day** whatever the number of
     Sybils;
   - slots are earned only from a model's own after-freeze cases (at least
     400, ranked by estimate − 2 SE, one per coldkey, identical predictions
     collapsed);
   - slots are re-ranked every window.

**Supersedes, prospectively:** the daily championship of
OWNER-BATTERY-CHAMPIONSHIP-01, -02 and -03:
- the rounds;
- the K = 10 entrants and the N = 4,000 batch;
- the 2.25 % posted margin and its guard.

Kept from them:
- one slot per coldkey;
- the safety checks (G-FEAS and the important-region guard);
- the leader's decaying share;
- the public screening ladder, as a display only (it never awards a slot).

Nothing scored earlier is rescored (invariant 10).

**Not decided (open):**
3. **The step slice S.** The owner: "I dont know about this S=10%". S stays
   HUMAN_INPUT, and there is no step pay until it is set.
4. **The per-Challenge case budgets.** §4's RunPod budgets (about $60 a day,
   about $2k a month) are **rejected**. The replacement budget design is
   rev 8 §4b: releases only while a slot is occupied, a dedicated AX42-class
   server with a sealed stock, and RunPod only for bursts. It awaits the
   owner's server, spend and custody decisions.
5. **The daily pre-solved batch feeding the leaderboard (CUSTODY-04's use
   change):** "maybe". Not decided; CUSTODY-04's use is unchanged.

**Build:** after battery finishes, as VALIDATOR-32 rev 8. Mainnet values stay
HUMAN_INPUT.
