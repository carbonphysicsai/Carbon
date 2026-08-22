# Carbon Emissions Mapping v2 — Frontier Event Settlement

**Status:** OWNER-RECOMMENDED v2 — supersedes `Emissions_Mapping_v1.md` as the preferred design on this branch.  
**Scope:** downstream economic settlement after Challenge-local scientific scoring and frontier replacement.  
**Does not redefine:** Challenge science, Score Pack semantics, product qualification, or Yuma consensus.

---

# 1. Why v2 replaces v1

`Emissions_Mapping_v1.md` explored proportional allocation among all `VALID_RANKED` candidates inside one Challenge.

The clarified Carbon mechanism is different:

> **Only a new scientifically verified Challenge frontier earns the Challenge's miner reward for that settlement period.**

Therefore proportional participation scoring is not the intended base mechanism.

---

# 2. Separation of responsibilities

```text
qualified Challenge
    ↓
Score Pack / ScoreEngine
    ↓
ScoreResult
    ↓
LeaderReplacementPolicy
    ↓
FrontierAdvanceEvent or no event
    ↓
ChallengeSetEpoch equal-slot settlement
    ↓
SettlementObligation
    ↓
BittensorSettlementAdapter
    ↓
validator weight signal / Yuma consensus
```

Scientific score determines evidence and ordering inside the Challenge. It does not directly determine the size of the Challenge's cross-portfolio reward slot.

---

# 3. Equal reward-enabled Challenge slots

For `N` qualified, LIVE, reward-enabled Challenges frozen for a settlement window:

```text
base_slot = 1/N
```

Every Challenge receives the same base opportunity.

This intentionally spreads search pressure across the active Challenge portfolio and avoids pretending that raw scores from different Score Packs are comparable.

P0 may aim for seven PDE Challenges, but only qualified reward-enabled Challenges count.

---

# 4. Pay condition

For Challenge `c`:

```text
verified FrontierAdvanceEvent -> PAY(new_frontier_uid, 1/N)
otherwise                    -> WITHHOLD(1/N)
```

No payment occurs merely because a miner remains incumbent.

No payment occurs to a scientifically inadmissible, invalid, failed-infrastructure, or indeterminate candidate.

---

# 5. One payment maximum per Challenge window

A Challenge may establish at most one paid frontier event per settlement window.

All eligible contenders are batch-compared under the registered promotion procedure.

This prevents:

- arrival-order reward gaming;
- multiple transient records consuming multiple period rewards;
- evaluator-latency effects;
- first-arrival advantage.

---

# 6. Frontier advancement is qualified evidence

The pay condition is not:

```text
new_score > old_score
```

It is:

```text
LeaderReplacementPolicy(...) == SUPERIOR
```

The policy must respect the Challenge's scientific resolution, uncertainty, reconstruction policy, strata, admissibility, and exact exam identities.

`INDETERMINATE` does not create a paid event.

---

# 7. No carry-forward in v2

A Challenge slot that is not paid in a period does not accumulate into a future jackpot under v2.

Reasons:

- reduces strategic withholding incentives;
- avoids reward explosions on saturated Challenges;
- keeps period economics bounded;
- matches the intended "new winner gets that period's emissions" semantics.

Future sponsor bounties or explicit frontier prizes may accumulate separately under their own policy.

---

# 8. No redistribution at Carbon policy layer

If seven Challenges are reward-enabled and only two advance, Carbon's abstract intent is:

```text
2 × (1/7) payable
5 × (1/7) withheld
```

not:

```text
1/2 + 1/2 to the two event winners
```

Renormalizing active event winners changes the breadth mechanism and makes payout depend on unrelated Challenges' success that period.

---

# 9. Bittensor settlement adapter is mandatory

Current Bittensor normalizes surviving validator weights and normalized rank drives miner incentive. Consequently, ordinary zero weights for no-event Challenges may cause the remaining positive destinations to absorb a larger fraction of miner incentive.

The `BittensorSettlementAdapter` must implement or explicitly approximate:

```text
PAY(fraction)
WITHHOLD(fraction)
```

under current chain constraints.

Potential chain mechanisms must be tested rather than assumed. In particular, current Bittensor documentation says miner incentive directed to subnet-owner-associated hotkeys is withheld/burned or recycled, but such withholding contributes to `MinerBurned`, which affects the subnet's future cross-subnet emission share.

Therefore no sink strategy is ratified until testnet measurements quantify:

- actual miner payout;
- miner burn/recycle result;
- validator dividends/bonds effects;
- Carbon subnet emission-share effects;
- Yuma consensus/clipping behavior;
- minimum-weight-count compliance.

---

# 10. Challenge-set boundaries

`N` and Challenge membership are frozen for the settlement window.

Changes to:

- Challenge activation;
- reward enablement;
- suspension;
- retirement;

apply prospectively at a window boundary.

---

# 11. Multi-Challenge winner

A miner that establishes several independent frontier advances may receive several equal Challenge slots in the same window.

This does not violate breadth: each payment corresponds to a separate scientific frontier advance.

---

# 12. Scientific defect

If a Challenge's exam becomes scientifically invalid or compromised, its reward state is suspended. The Challenge is removed from future reward-enabled sets at the next safe boundary or immediately frozen under emergency policy.

No economic layer may continue paying frontier events using an invalid scientific comparator.

---

# 13. v2 invariants

1. **Reward frontier advance, not participation.**
2. **Reward event, not permanent incumbent status.**
3. **Equal base slot per qualified reward-enabled Challenge.**
4. **At most one paid frontier event per Challenge per settlement window.**
5. **Leader replacement is scientifically qualified, not an epsilon score comparison.**
6. **No-event slot is withheld, not redistributed by Carbon policy.**
7. **No carry-forward jackpot in v2.**
8. **Cross-Challenge raw score comparison is unnecessary and forbidden by default.**
9. **Chain-specific normalization/burn behavior belongs to an explicit adapter.**
10. **The economic record never changes the underlying scientific ScoreResult or FrontierRecord.**

---

# 14. Final statement

> **Carbon allocates equal base opportunity across its qualified Challenge portfolio and pays miners only when independent evidence establishes a new scientific frontier.**
