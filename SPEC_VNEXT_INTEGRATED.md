# Carbon Protocol Specification — Integrated vNext Candidate

**Status:** OWNER-RECOMMENDED vNext specification candidate for tech/science/economic review.  
**Purpose:** Consolidate the post-gauntlet protocol architecture into one reviewable source without silently changing current P0 runtime behavior.  
**Current runtime authority:** existing `SPEC.md`, `Design_Specs/Scoring.md`, current Challenge Registry entries, and implemented code remain authoritative until intentional migration.

---

# 1. System objective

Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.

The performance market rewards **verified frontier advance on a qualified Challenge**.

---

# 2. Authority chain

```text
Scientific authoring
  PhysicalSystemSpec
  CandidateOutputContract
  Claim / Operating Envelope
  InstanceDistributionContract
  SamplingPlan
  ReferencePolicy
  MeasurementContracts
        ↓
ChallengeInstanceGenerator
        ↓
Validation Dossier
        ↓
registered LIVE Challenge
        ↓
participant ModelConstructionStrategy
        ↓
producer-independent reconstruction
        ↓
FastPhysicalModel candidate
        ↓
protected official evaluation
        ↓
Score Pack / ScoreEngine
        ↓
ScoreResult / ExperimentRecord
        ↓
LeaderReplacementPolicy
        ↓
FrontierAdvanceEvent
        ↓
ChallengeSetEpoch entitlement
        ↓
Treasury settlement
```

No downstream layer repairs missing scientific authority from upstream.

---

# 3. Challenge qualification

A Challenge cannot become reward-authoritative merely because its generator runs.

The Validation Dossier must qualify required evidence for:

- physical-system adequacy;
- claim/envelope adequacy;
- target population `P(x)`;
- finite SamplingPlan / proposal `Q(x)`;
- generator integrity and distribution conformance;
- reference/truth adequacy;
- representation fidelity;
- MeasurementContract adequacy/applicability;
- statistical sufficiency and estimand clarity;
- secrecy/decontamination/role separation;
- censoring and residual uncertainty.

The Score Pack cannot repair missing qualification.

---

# 4. Candidate task contract

All causal inputs required to determine the requested candidate output must be explicit in the CandidateOutputContract.

If a physical parameter changes the target while remaining hidden from the candidate, the task is ill-defined unless the task explicitly defines a conditional/marginal prediction problem that accounts for that hidden variable.

P0 Burgers repair therefore fixes viscosity for the first authoritative `u0 -> u(T)` task. Variable-viscosity Burgers is a separate future `(u0, nu) -> u(T)` Challenge.

---

# 5. Reconstruction

P0 learned-model subtype:

```text
TrainingStrategy -> validator-controlled fresh retraining
```

General invariant:

> Producer-independent reconstruction.

Future registered reconstruction protocols remain separate from arbitrary participant code. Construction and official evaluation remain separate security domains.

---

# 6. Score Pack

The Score Pack is a versioned Evidence Use Contract.

It governs:

- evidence eligibility;
- mandatory admissibility;
- explicit score-bearing estimands;
- measurement-use roles;
- P/Q/w semantics;
- strata;
- uncertainty/repeat policy;
- soft transforms/aggregation;
- deterministic ranking result;
- internal result state and disclosure reference.

`ScoreEngine` executes registered decisions and does not author science.

---

# 7. Scientific result states

At minimum:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
VALID_RANKED
```

A scientific zero is not the same as invalidity or infrastructure failure.

---

# 8. Frontier promotion

A normal performance payout requires a `FrontierAdvanceEvent`.

Default settlement window behavior:

1. freeze opening incumbent/baseline;
2. collect eligible contenders;
3. execute registered common promotion experiment where variance makes historical score comparison unsafe;
4. apply LeaderReplacementPolicy;
5. choose at most one strongest `SUPERIOR` contender per Challenge/window;
6. emit exact frontier event;
7. update frontier only after finalization rules are met.

The LeaderReplacementPolicy may use Challenge-qualified equivalence bands, repeat rules, minimum meaningful separation, conservative bounds, or other explicit uncertainty semantics.

---

# 9. ChallengeSetEpoch

The reward-enabled Challenge portfolio is frozen prospectively per epoch.

```text
ChallengeSetEpoch {
  epoch_id
  Challenge IDs + versions
  N
  notional opportunity = 1/N per Challenge
  settlement boundaries
  frontier policy refs
  treasury accounting version
}
```

P0 launch slice proves one Challenge. Phase-0 expansion targets a small concurrent academic portfolio of roughly 4-7 Challenges, preserving the original seven-PDE breadth objective where feasible.

Raw scores across different Challenges are not used as a common economic unit.

---

# 10. Performance entitlement

Only a finalized FrontierAdvanceEvent creates the normal Challenge performance entitlement.

Incumbency alone does not create new entitlement.

If no event occurs for a Challenge/window, that Challenge's notional opportunity is not silently redistributed to another Challenge winner.

---

# 11. Treasury settlement

Preferred vNext implementation path:

```text
Bittensor/Yuma miner-side emission
        ↓
registered Carbon Treasury neuron
        ↓
TreasuryVault
        ↓
ChallengeSetEpoch accounting
        ↓
FrontierAdvanceEvent-bound payout proposal
        ↓
TreasuryController / validator governance
        ↓
timelock
        ↓
payout
```

Treasury governance verifies that the transfer matches the authoritative event; it does not decide who scientifically won.

Every performance payout must bind an event digest and be protected against duplicate execution.

The treasury architecture is not production-authoritative until localnet/testnet qualification proves chain behavior, custody, voting, timelock, rate limits, Alpha transfer, failure recovery, and no unintended burn/normalization effect.

---

# 12. Settlement states

Examples:

```text
FRONTIER_ADVANCE_CONFIRMED
PAYOUT_PROPOSABLE
PAYOUT_PENDING_GOVERNANCE
PAYOUT_QUEUED
PAYOUT_TIMELOCKED
PAYOUT_PENDING_INFRA
PAID
CANCELED_WITH_REASON
EXPIRED
```

Settlement state does not mutate scientific frontier evidence.

---

# 13. Information-value market

Novelty, reproduction, ablation, uncertainty reduction, causal identification, and targeted evidence acquisition remain distinct from the primary performance frontier reward.

A future research-bounty mechanism may fund them explicitly through separate treasury/governance semantics.

---

# 14. Product qualification

Frontier success nominates candidates. It does not certify product use.

```text
frontier method / candidate
        ↓
fresh product reconstruction
        ↓
Product Qualification Pack / job-shaped evidence
        ↓
Qualification Record
        ↓
answerability / escalation / lifecycle
```

> Rank nominates. Evidence qualifies.

---

# 15. Challenge lifecycle

Material changes to population, SamplingPlan, generator, truth policy, measurement implementation, Score Pack semantics, candidate I/O contract, or frontier policy create a new compatible version or require explicit requalification.

Discovered material scientific defects freeze frontier settlement prospectively until resolved.

Historical evidence remains immutable under its original identity.

---

# 16. Bittensor boundary

Bittensor provides open optimizer participation, validator/economic coordination, and subnet emission substrate.

It does not determine:

- governing physics;
- Challenge population;
- truth/reference validity;
- measurement semantics;
- mandatory scientific thresholds;
- frontier superiority;
- product qualification.

---

# 17. Constitutional invariants

1. The producer never controls the official grade.
2. Carbon qualifies the exam before using it to judge candidates.
3. No individual validator is a trusted scientific authority.
4. Science thresholds are versioned qualified protocol inputs, not runtime opinions.
5. Mandatory scientific failure cannot be compensated by accuracy.
6. Target population, proposal sampling, and score importance are separate.
7. Generator conformance and truth adequacy are separate.
8. Measurement definition, qualification, and use are separate.
9. Score is Challenge-bound evidence, not a universal competence currency.
10. A new leader is an evidence state, not a floating-point inequality.
11. Frontier scientific state and treasury settlement are separate.
12. Incumbency alone earns no new performance reward.
13. Unused Challenge opportunity is not redistributed by default.
14. Cross-Challenge scores are not automatically comparable.
15. Product qualification is distinct from subnet frontier success.
16. Physics remains external authority.
