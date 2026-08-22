# Carbon Emissions and Frontier Settlement v3

**Status:** OWNER-RECOMMENDED v3; supersedes `Emissions_Mapping_v1.md` and `Emissions_Mapping_v2.md` for future architecture on the design branch.  
**Scope:** economic path from Bittensor miner-side subnet emission to Challenge-bound verified frontier payouts.  
**Does not redefine:** scientific Score Pack semantics, Challenge qualification, product qualification, or Bittensor consensus.

---

# 1. Architecture

```text
qualified Challenge evaluation
        ↓
ScoreResult
        ↓
LeaderReplacementPolicy
        ↓
FrontierAdvanceEvent
        ↓
Challenge-period entitlement
        ↓
Carbon Treasury neuron / Vault
        ↓
validator-governed settlement
        ↓
winner payout
```

> **The score measures Challenge-bound scientific evidence. The frontier policy decides whether progress occurred. The treasury settles the entitlement.**

---

# 2. No continuous proportional miner payout

The earlier design-branch recommendation to distribute emissions continuously among all `VALID_RANKED` candidates is superseded.

Base Carbon performance reward is **event-based**:

- being scientifically admissible is necessary but not sufficient for payout;
- being the incumbent leader is not sufficient for payout;
- a verified `FrontierAdvanceEvent` is required.

---

# 3. Challenge portfolio

A `ChallengeSetEpoch` freezes `N` reward-enabled Challenges.

Each Challenge has equal notional opportunity `1/N` for the period.

No raw cross-Challenge score comparison is required.

---

# 4. Event entitlement

If Challenge `c` emits a finalized frontier event during the settlement window, its winning event receives the registered entitlement for that Challenge/window.

If no event occurs, no performance payout is created for that Challenge/window.

Unused opportunity is not redistributed to winners on other Challenges.

---

# 5. Promotion evidence

Where finite-sample/reconstruction variance is material, frontier promotion is based on a common fresh incumbent-vs-challenger experiment rather than comparing unrelated historical scores.

Promotion outcome:

```text
SUPERIOR -> event eligible
NOT_SUPERIOR -> no event
INDETERMINATE -> no frontier payout until resolved under registered policy
```

---

# 6. Treasury transport

Preferred research architecture directs miner-side subnet emission to a separately governed Carbon Treasury neuron, decoupling Bittensor's normalized weight transport from Carbon's Challenge accounting.

The treasury then settles only event-bound entitlements.

This architecture requires localnet/testnet proof before production adoption.

---

# 7. No scientific winner from economic fallback

Operational fallback may be required by the chain/runtime, but it must never create a fictitious scientific frontier event.

Treasury outage, governance delay, or chain failure produces payout-pending state, not scientific defeat.

---

# 8. Information-value rewards

Novelty, replication value, ablation value, uncertainty reduction, and other information-value experiments remain separate from the performance frontier reward.

A future research-bounty treasury may fund them explicitly, but they must not contaminate the meaning of a performance `FrontierAdvanceEvent`.

---

# 9. Product value

A frontier winner is still not a qualified engineering product.

> **Rank nominates. Evidence qualifies.**

Product qualification has separate job-shaped acceptance semantics and may have separate commercial payment economics.

---

# 10. v3 laws

1. **Only a verified frontier advance creates the normal performance payout entitlement.**
2. **Incumbency alone earns no new performance reward.**
3. **Equal Challenge opportunity is frozen prospectively per epoch.**
4. **Unused Challenge opportunity is not redistributed by default.**
5. **Cross-Challenge scalar scores are not used as a common economic unit.**
6. **Promotion evidence and treasury settlement are separate.**
7. **Payout proposals bind exact frontier-event identity.**
8. **Economic/infra failures do not rewrite scientific outcomes.**
