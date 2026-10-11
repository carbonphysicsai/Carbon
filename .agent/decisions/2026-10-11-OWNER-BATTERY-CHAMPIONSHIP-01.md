## 2026-10-11 — OWNER-BATTERY-CHAMPIONSHIP-01: battery testnet takeover is a qualify tier plus a daily championship

**Authority.** The owner, 2026-10-11, directly in the Carbon Validator session, deciding VALIDATOR-32 rev 4. Mainnet is set separately.

**The owner's decisions:**

> 1. Format: two tiers. QUALIFY every submission on the r8 rotating bank
>    (exact rebuild + safety checks + screening score). DAILY CHAMPIONSHIP:
>    king + top K qualifiers on one fresh shared batch.
> 2. Battery parameters: K = 10, batch N = 4,000 cases, round 16:00 UTC,
>    entry cut-off 14:00 UTC.
> 3. Takeover rule: pass the safety checks (G-FEAS gate + important-region
>    guard, kept per V3-FINALS-01) AND beat the king by the posted margin of
>    2.25% AND clear the statistical guard (contender's paired improvement
>    exceeds z(1%/K) × its observed paired SE). Ties keep the king.
>    False-takeover target ≤ 1% per round (MARGIN-SIZING-05).
> 4. Publish after every round: every entrant's rounded score, the king's
>    score, and the next posted target.
> 5. King's share keeps its daily decay as today.
> 6. Design-question component: decided after tonight's score-proof pick —
>    keep it (and its cost) only if the picked rule includes it.
> 7. Compute: the daily championship batch is pre-solved on a RunPod Secure
>    Cloud CPU pod (~$3/day), not the AX42, so the AX42 keeps qualification
>    and scoring headroom.
> 9. Motor and other expensive Challenges: weekly rounds, pace set by cost;
>    measure each Challenge's paired noise before posting its margin.
> 10. Write it up as rev 5 with the miner one-pager updated to these
>     numbers; build after battery finishes.

Item 8, the custody, is OWNER-STARTUP-HOST-CUSTODY-04.

**The design:** VALIDATOR-32 rev 5, in the shared operator file `TICKET_DRAFT_PAIRED_FINALS.md`. Its sizing is MARGIN-SIZING-05.

**Readings the executor applies (to be confirmed in the build PR):**
- **The important-region guard "as in v2":** the entrant's important-region error on the batch is not above the king's × (1 + 0.0570), v2's `equivalence_margin_rel`.
- **The guard's z:** z(1 % ÷ 10) = 3.090, one-sided, with K fixed at the registered 10.
- **The margin is relative:**
  - on the accuracy leg's mean error, the entrant's error is below (1 − 0.0225) × the king's;
  - if the picked rule keeps a q leg, it applies on the composite score instead, and that round type stays unposted until the composite's paired noise is measured and the margin re-sized.
- **Rounds are anchored as chain blocks,** so every validator freezes the same entrants.

**What it replaces, prospectively (a new rule version, v4).** Payment is no longer decided by:
- the 5.70 % screening nomination;
- the per-challenger finals and their 5.70 % margin.

Nothing scored under v2 or v3 is rescored (invariant 10).

**Not decided here:**
- the spend for the pods: a grant with its own owner-confirmed figure, via PR Head;
- mainnet values;
- the score-proof pick, which needs its own record (OWNER-BATTERY-SCORE-CANDIDATE-01's procedure).

No LIVE or qualification claim is made.
