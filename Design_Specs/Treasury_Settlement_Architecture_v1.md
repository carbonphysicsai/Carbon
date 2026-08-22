# Carbon Treasury Settlement Architecture v1

**Status:** OWNER-RECOMMENDED architecture for implementation research and localnet/testnet qualification.  
**Purpose:** Decouple Bittensor's normalized miner-incentive transport from Carbon's Challenge-specific frontier settlement semantics while preserving validator-governed custody and auditable payouts.  
**Reference implementation studied:** qBittensor Labs Enigma treasury (`qbittensor-labs/enigma/treasury`). Carbon adapts the pattern; it does not inherit Enigma's governance parameters by authority.

---

# 1. Problem

Carbon wants:

```text
N qualified active Challenges
-> equal notional period opportunity 1/N
-> payout only when a Challenge has a verified FrontierAdvanceEvent
-> unused Challenge opportunity must not be redistributed to unrelated winners
```

Direct validator-weight encoding is problematic because Bittensor/Yuma normalizes positive weight signal. Owner-associated burn/sink routes may also affect subnet-level burn/emission economics.

---

# 2. Proposed transport

```text
Bittensor / Yuma
      ↓
registered Carbon Treasury neuron
      ↓
TreasuryVault custody
      ↓
ChallengeSetEpoch accounting
      ↓
FrontierAdvanceEvent entitlements
      ↓
TreasuryController governance
      ↓
timelock
      ↓
Alpha / TAO payout
```

The treasury neuron is an economic transport/custody endpoint, not a scientific authority.

---

# 3. Dual-contract pattern

Recommended starting pattern, informed by Enigma:

## TreasuryController

Owns:

- proposal creation pathways;
- validator voting eligibility;
- quorum and success logic;
- cancellation/expiry;
- spending/rate limits;
- payout-event binding checks;
- governance configuration.

## TreasuryVault

Owns:

- asset custody;
- timelocked execution;
- Bittensor-native transfer/staking integrations as required;
- no scientific decision logic.

---

# 4. Carbon-specific improvement: event-bound payouts

Performance payout proposals must reference an authoritative `FrontierAdvanceEvent`.

Conceptual transfer proposal:

```text
FrontierPayoutProposal {
  frontier_event_id
  frontier_event_digest
  challenge_set_epoch_id
  challenge_id
  recipient
  asset
  amount
  entitlement_fraction
  source_accounting_record_digest
}
```

The controller verifies:

- event exists and is finalized scientifically;
- event has not already been paid/canceled;
- recipient and amount match the registered entitlement;
- event belongs to the stated ChallengeSetEpoch;
- Challenge was reward-enabled and not frozen;
- accounting is not double-spending the same epoch inflow.

Treasury validators then verify settlement legitimacy, not scientific merit.

---

# 5. Governance principles

Starting requirements:

- active-validator eligibility for governance participation;
- dynamic or clearly versioned quorum;
- explicit success threshold;
- timelock between approval and execution;
- cancellation path for discovered defect/compromise;
- proposal expiry;
- asset-specific spending caps/rate limits;
- no single admin unilateral payout;
- auditable event and execution logs;
- emergency freeze with documented authority and sunset/review.

Exact thresholds are implementation parameters to be gauntleted, not scientific constants.

---

# 6. Admin minimization

Enigma uses a Treasury Admin with exclusive proposal-creation authority. Carbon should treat that as a deployable starting precedent, not a terminal design.

Preferred evolution:

```text
confirmed FrontierAdvanceEvent
        ↓
automatically proposal-eligible
        ↓
validator attestation / veto / governance
        ↓
timelock
        ↓
execution
```

The operator should not be able to censor a valid scientific winner indefinitely merely by refusing to create the proposal.

If an admin remains required at launch, censorship must be observable and recoverable through governance/emergency procedures.

---

# 7. Treasury accounting

Treasury inflow is not itself a Challenge reward.

For each `ChallengeSetEpoch`:

```text
period_inflow
N active reward-enabled Challenges
notional fraction per Challenge = 1/N
```

Only a finalized `FrontierAdvanceEvent` creates a performance payout entitlement.

If no event exists for a Challenge, the corresponding notional period opportunity remains treasury capital under the base policy.

Do not automatically reallocate it to other Challenge winners.

---

# 8. Settlement state machine

```text
NO_EVENT
FRONTIER_ADVANCE_CONFIRMED
PAYOUT_PROPOSABLE
PAYOUT_PENDING_GOVERNANCE
PAYOUT_QUEUED
PAYOUT_TIMELOCKED
PAYOUT_EXECUTABLE
PAID
CANCELED_WITH_REASON
EXPIRED
PAYOUT_PENDING_INFRA
```

Scientific event state and payout state remain separate.

---

# 9. Failure isolation

Examples:

- chain RPC outage -> `PAYOUT_PENDING_INFRA`, scientific winner unchanged;
- controller bug -> freeze treasury execution, preserve event ledger;
- discovered Challenge defect before payout -> cancel/freeze proposal under explicit policy and open scientific review;
- duplicate proposal -> reject by paid/event nonce;
- malicious validator coalition -> bounded by quorum, timelock, rate limits, public event binding, and emergency governance;
- malicious admin censorship -> must be detectable; vNext should reduce exclusive proposer power.

---

# 10. Localnet/testnet qualification campaign

Before production use, test:

1. treasury neuron receives intended miner-side emission;
2. no unintended `MinerBurned` semantics from the treasury route;
3. Alpha can be transferred from treasury through the intended Bittensor precompile path;
4. `N=7`, frontier events `k=0,1,2,7` preserve logical Challenge accounting;
5. unused Challenge opportunity is not paid to unrelated miners;
6. one event cannot be paid twice;
7. event amount cannot be modified by proposer;
8. inactive/non-validator voter cannot govern if active-validator gating is intended;
9. quorum changes with validator-set changes as designed;
10. cancellation/expiry/timelock work under adversarial ordering;
11. rate limits prevent drain after governance compromise;
12. chain/RPC/gas-estimation failure preserves payout-pending state rather than scientific failure;
13. Challenge freeze blocks payout;
14. ChallengeSetEpoch changes do not retroactively alter prior entitlement;
15. owner/admin key loss and proposer censorship have documented recovery paths.

---

# 11. Non-claims

This document does not claim:

- Enigma's exact contracts are audited for Carbon;
- its governance thresholds are optimal;
- a treasury removes validator collusion risk;
- EVM/Bittensor precompiles will remain unchanged;
- mainnet behavior equals localnet until tested;
- custody/treasury governance is product qualification or scientific authority.

---

# 12. v1 laws

1. **Treasury receives/settles economic value; it does not define scientific truth.**
2. **Performance payout requires an authoritative FrontierAdvanceEvent.**
3. **No single operator should be able to unilaterally pay itself or redefine entitlement.**
4. **Scientific event state survives treasury outages.**
5. **Unused Challenge opportunity is not silently redistributed.**
6. **Double payout is impossible by event identity.**
7. **Governance parameters are versioned and auditable.**
8. **Production use requires localnet/testnet qualification.**
