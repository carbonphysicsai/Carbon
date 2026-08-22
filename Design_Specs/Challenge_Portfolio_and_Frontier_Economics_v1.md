# Carbon Challenge Portfolio and Frontier Economics v1

**Status:** OWNER-RECOMMENDED v1 for tech/economic review.  
**Purpose:** Define the scientific/economic semantics of running multiple independent Challenges while rewarding only verified frontier advances.

---

# 1. Core objective

Carbon should reward **new verified scientific frontier progress**, not continuous possession of the current leaderboard lead.

The portfolio should also preserve breadth across physics rather than allowing one easy/popular Challenge to absorb the subnet's entire search effort.

---

# 2. ChallengeSetEpoch

A settlement epoch freezes the reward-enabled Challenge portfolio:

```text
ChallengeSetEpoch {
  epoch_id
  active_challenge_ids_and_versions
  N
  open_boundary
  close_boundary
  notional_slot = 1/N
  treasury_accounting_version
  frontier_policy_refs
}
```

Adding, retiring, freezing, or materially versioning a Challenge changes the next epoch, not the current one retroactively.

---

# 3. Equal notional opportunity

For `N` active qualified Challenges, each receives equal notional performance-reward opportunity `1/N` for the settlement period.

This is a deliberate breadth policy.

It does not assert equal:

- difficulty;
- scientific importance;
- commercial value;
- score scale;
- information value;
- expected rate of improvement.

---

# 4. FrontierBaseline

Every Challenge must begin from an independently registered frontier baseline before a miner can earn the first frontier reward.

A baseline may be:

- a protocol benchmark method;
- a qualified internal method;
- an existing public method reconstructed under Carbon's rules;
- another explicitly registered baseline.

The first miner must beat the baseline under the same leader-replacement doctrine.

---

# 5. Candidate screen

Only scientifically eligible candidates enter frontier promotion.

Non-eligible states remain distinct:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
```

Only appropriate `VALID_RANKED` contenders can proceed.

---

# 6. Common frontier promotion experiment

Do not compare a challenger's new random-draw score to an incumbent's historical random-draw score when finite-sample or reconstruction variance can matter.

For each Challenge settlement:

```text
incumbent
+ eligible contenders
      ↓
fresh common hidden cases
same Challenge identity
same Score Pack
same qualified reference/measurement path
same registered reconstruction-repeat policy
      ↓
LeaderReplacementPolicy
```

This produces a scientifically comparable promotion decision.

---

# 7. LeaderReplacementPolicy

The policy returns:

```text
SUPERIOR
NOT_SUPERIOR
INDETERMINATE
```

A floating-point inequality alone is insufficient.

Challenge-specific policy may use:

- minimum meaningful improvement;
- reconstruction repeats;
- evaluation repeats;
- conservative bounds;
- equivalence/indeterminate bands;
- other dossier-qualified resolution semantics.

No universal margin is ratified here.

---

# 8. Batched settlement

Default v1 rule:

- collect eligible contenders during the window;
- run the common promotion experiment;
- select the strongest scientifically verified improvement over the opening incumbent/baseline;
- emit at most one paid `FrontierAdvanceEvent` per Challenge/window.

Arrival order does not determine reward.

---

# 9. FrontierAdvanceEvent

```text
FrontierAdvanceEvent {
  event_id
  challenge_set_epoch_id
  challenge_id
  challenge_version
  prior_frontier_id
  new_frontier_strategy_or_method_id
  miner_hotkey
  payout_address
  promotion_exam_digest
  score_pack_digest
  validation_dossier_digest
  result_record_digest
  leader_replacement_policy_version
  entitlement_fraction
  event_timestamp_or_block
}
```

The event is the bridge from science to settlement.

---

# 10. No incumbent rent

If no challenger advances the frontier:

```text
incumbent remains scientific frontier
no new FrontierAdvanceEvent
no new performance entitlement
```

The incumbent's historical achievement remains in the scientific record but does not automatically earn another period's performance reward.

---

# 11. Same-miner improvement

A miner may advance its own incumbent method with a genuinely new strategy/method and earn the new event. Carbon rewards the improvement, not identity turnover.

---

# 12. Unused period opportunity

The base policy does not redistribute an inactive Challenge's period opportunity to other Challenge winners.

With a treasury architecture, untriggered notional allocations remain general treasury capital unless a separately governed bounty policy says otherwise.

No automatic unbounded Challenge-specific carry-forward is assumed in v1 because it can create strategic delay incentives.

---

# 13. Challenge defects

If a material generator, truth, measurement, leakage, or scoring defect is discovered:

```text
Challenge frontier settlement = FROZEN
```

until repair and requalification.

A material new scientific identity establishes a new frontier lineage or an explicit requalification bridge. Raw scores across incompatible versions are not compared.

---

# 14. Known strategic risks

Monitor and mitigate:

- staged disclosure / incremental-release gaming;
- duplicate strategies / sybils;
- collusive challengers;
- strategic submission timing;
- baseline manipulation;
- threshold-edge gaming;
- evaluator leakage;
- low-participation Challenges;
- challenge-owner manipulation;
- treasury proposal censorship.

No design can prove that a miner is not withholding a stronger unreleased method.

---

# 15. v1 laws

1. **Reward frontier advance, not incumbency.**
2. **A new leader is an evidence state.**
3. **Promotion comparisons use common evidence where variance matters.**
4. **One Challenge cannot inherit unused reward opportunity from another by default.**
5. **Raw scores across Challenges are not compared.**
6. **Challenge portfolios are frozen prospectively per settlement epoch.**
7. **Material Challenge defects freeze settlement.**
8. **FrontierAdvanceEvent is the sole normal bridge from scientific promotion to performance payout.**
