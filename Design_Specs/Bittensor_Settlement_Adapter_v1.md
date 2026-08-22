# Carbon Bittensor Settlement Adapter v1

**Status:** OWNER-RECOMMENDED interface + stop-ship requirements; production implementation intentionally unresolved.  
**Purpose:** Define the trust boundary between Carbon's frontier-only Challenge settlement and Bittensor's normalized validator-weight / Yuma emission system.

---

# 1. Core problem

Carbon's scientific/economic layer produces **absolute logical settlement instructions**:

```text
PAY(miner_uid, slot_fraction)
WITHHOLD(slot_fraction)
```

where each reward-enabled Challenge in a frozen ChallengeSetEpoch owns one fixed logical slot:

```text
slot_fraction = 1 / N
```

Bittensor validators submit **relative** weight vectors that are normalized before Yuma Consensus.

Therefore the adapter must not assume that omitted or zero weights preserve unused Challenge capacity.

---

# 2. Input contract

Conceptually:

```text
SettlementInstructionSet {
  settlement_id
  challenge_set_epoch_id
  n_reward_enabled_challenges
  slot_fraction

  instructions[] {
    challenge_id
    challenge_version
    frontier_event_ref | null
    action: PAY | WITHHOLD
    miner_uid | null
    fraction
  }

  total_pay_fraction
  total_withhold_fraction
  scientific_manifest_digest
}
```

Required invariants:

```text
sum(fraction) = 1
one instruction per reward-enabled Challenge
PAY only references verified FrontierAdvanceEvent
WITHHOLD has no miner scientific winner
```

---

# 3. Output contract

The adapter must produce a chain-facing plan plus an auditable predicted effect:

```text
BittensorSettlementPlan {
  settlement_id
  mechanism_id
  target_uids
  raw_weights
  expected_normalized_weights
  expected_paid_miner_fraction
  expected_withheld_or_reserved_fraction
  expected_MinerBurned
  chain_constraints_snapshot
  adapter_version
  safety_status
}
```

The plan must fail closed if it cannot preserve the settlement doctrine within the ratified tolerance.

---

# 4. Required chain-constraint snapshot

Before producing weights, the adapter records at least:

```text
netuid
mechanism_count / mechanism split
min_allowed_weights
max_weights_limit
weights_rate_limit
weights_version
commit_reveal status / timing
tempo / next epoch timing
owner-associated sink UIDs if any
RecycleOrBurn mode
```

No deployment should rely on remembered defaults.

---

# 5. Adapter safety invariants

## A1 — No fictitious scientific winner

A `WITHHOLD` instruction may never be translated into positive miner reward for an unrelated miner merely to satisfy row normalization or minimum-weight rules.

## A2 — No silent redistribution

Unused Challenge slots may not be silently redistributed to active frontier winners.

## A3 — No hidden cross-subnet penalty

An adapter that implements local withholding through `MinerBurned` must quantify the resulting future cross-subnet emission effect. A material unapproved penalty is stop-ship.

## A4 — No stale-incumbent payout

Failure to update weights cannot be treated as withholding if old weights remain economically active.

## A5 — Sparse-vector chain requirements do not redefine science

`min_allowed_weights` and `max_weights_limit` are chain transport constraints. They may change encoding, never Carbon's scientific winner set.

## A6 — Yuma consensus agreement required

Multiple honest validators using the adapter must produce economically compatible weight semantics. Divergent sink/reserve encodings that change clipping/rank are invalid.

## A7 — Settlement cadence must be chain-valid

The Challenge settlement cadence must respect weight rate limits, commit/reveal timing, and tempo boundaries.

## A8 — Exact accounting survives chain normalization

For every settlement, Carbon records:

```text
logical intended fractions
submitted raw vector
stored normalized vector
observed miner incentive
observed withheld/burned/reserved amount
```

and reconciles them.

---

# 6. Rejected v1 adapters

The following are not production-approved:

### Naive zeroing

Fails because row normalization redistributes unused slots.

### Pay current incumbent

Fails Carbon's frontier-only doctrine.

### Redistribute among active frontier winners

Fails fixed equal-Challenge allocation.

### Do not update weights

Fails because stale prior weights can remain active.

### Owner-associated burn/recycle sink as default

Locally expresses withholding, but current Bittensor uses `MinerBurned` in future cross-subnet emission allocation. This can materially penalize Carbon precisely when scientific progress is sparse.

### One mechanism per Challenge

Current Bittensor mechanism count is insufficient for 4–7 simultaneous Carbon Challenges.

---

# 7. Research candidates

## R1 — Trust-minimized protocol reserve

Route unused slots to a non-owner reserve whose assets are governed or made inaccessible under an independently auditable policy.

Must solve:

- custody/control;
- whether emission is economically spendable;
- whether reserve stake changes governance/economic incentives;
- exact disposal policy;
- no conversion into unapproved carry-forward rewards.

## R2 — Explicit settlement treasury/router

All or part of miner incentive is received by a deterministic protocol settlement layer that pays FrontierAdvanceEvents according to the Carbon ledger.

This is expressive but introduces additional trust/custody unless implemented trustlessly.

## R3 — Future native-chain feature

A chain-native mechanism for absolute withholding / unallocated miner incentive would be the cleanest semantic match if Bittensor later supports it.

Carbon should keep the adapter interface independent enough to adopt such a feature without changing scientific settlement semantics.

---

# 8. Localnet/testnet qualification matrix

Before production, qualify at least:

```text
N = 4, 5, 6, 7
k = 0, 1, floor(N/2), N
```

with multiple validators and representative chain hyperparameters.

For every cell record:

- planned PAY/WITHHOLD vector;
- accepted/rejected `set_weights` behavior;
- normalized stored rows;
- Yuma miner incentive;
- validator clipping/trust effects;
- `MinerBurned`;
- next-epoch subnet emission share;
- rate-limit / commit-reveal timing;
- reserve/sink behavior;
- exact deviation from Carbon logical intent.

---

# 9. Stop-ship criterion

Do not call the subnet IM mechanism implementation-complete until one Bittensor adapter demonstrates:

> **A Challenge that produces no frontier event can leave its logical reward slot unpaid without rewarding an unrelated miner, without silently reallocating that slot to another Challenge, and without imposing an unapproved material penalty on Carbon's future subnet emissions.**

This is the decisive remaining deployment criterion.

---

# 10. Final statement

> **The Bittensor Settlement Adapter is transport infrastructure for Carbon's scientific economy. It must faithfully encode frontier settlement; it is not allowed to rewrite the incentive mechanism to fit chain normalization.**
