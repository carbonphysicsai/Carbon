# Carbon System Identity and Roadmap v2 — Integrated Architecture

**Status:** OWNER-RECOMMENDED v2 for tech/science/economic review.  
**Purpose:** Canonical system-level identity, Challenge architecture, incentive loop, Phase-0 breadth plan, roadmap, and public explanation after the 2026-08 integrated design campaign.  
**Supersedes for narrative architecture:** `Design_Specs/System_Identity_and_Roadmap.md`.  
**Does not by itself change:** current P0 runtime schemas, LIVE Challenge Registry entries, current ScoreEngine implementation, or chain deployment.

---

## 1. Durable identity

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

Public expression:

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

Partner expression:

> **Give Carbon a defined physical modeling problem, the operating regime that matters, and what the fast model must do. Carbon turns it into a qualified competitive discovery program, independently tests the contenders, and produces evidence about what works, what fails, and what deserves deeper qualification.**

---

## 2. What Carbon standardizes

> **Carbon standardizes the job and the scientific exam, not the model architecture.**

The Challenge owns:

```text
physical semantics
required candidate inputs
required candidate outputs / query semantics
claim / operating envelope
target population
finite SamplingPlan
reference / truth policy
MeasurementContracts
Validation Dossier
Score Pack
frontier promotion policy
```

The participant owns the construction attempt.

The producer never owns the official grade.

---

## 3. Qualified Challenge chain

```text
PHYSICAL SYSTEM / ENGINEERING INTENT
        ↓
scientific authoring
        ↓
PhysicalSystemSpec
+ CandidateOutputContract
+ Claim / Operating Envelope
        ↓
Target Population P(x)
        ↓
InstanceDistributionContract
        ↓
SamplingPlan / Q(x)
        ↓
ChallengeInstanceGenerator
        ↓
generator conformance
        ↓
CanonicalChallengeCase
        ↓
qualified Reference / Truth Realization
        ↓
MeasurementContracts
        ↓
Validation Dossier
        ↓
Score Pack = Evidence Use Contract
        ↓
LIVE qualified Challenge
```

Key rule:

> **Carbon qualifies the exam before the exam qualifies a candidate.**

---

## 4. P/Q/w separation

```text
P(x) = target population the scientific/engineering claim concerns
Q(x) = proposal / finite sampling distribution
w(x) = evidence weighting / scientific or consequence importance
```

Envelope, population, stress sampling, and score weighting are separate semantics.

---

## 5. Construction and reconstruction

Current neural P0:

```text
TrainingStrategy
      ↓
validator-controlled fresh retraining
      ↓
candidate artifact
```

Long-term:

```text
ModelConstructionStrategy
+ ReconstructionProtocolRef
      ↓
validator control plane
      ↓
construction worker / security domain
      ↓
FastPhysicalModel + ConstructionReceipt
      ↓
hard isolation
      ↓
official evaluator
```

> **Producer-independent reconstruction is the invariant; fresh retraining is its learned-model subtype.**

Construction and official evaluation remain separate security domains.

---

## 6. Score semantics

The Score Pack is a **versioned Evidence Use Contract**.

```text
qualified evidence
      ↓
evidence eligibility
      ↓
mandatory admissibility
      ↓
continuous ranking objectives
      ↓
Challenge-bound ScoreResult
```

> **Admissibility precedes ranking.**

> **Mandatory physical/scientific failure cannot be compensated by soft performance.**

P0 45/30/25 is one narrow pack profile, not Carbon's universal constitution.

---

## 7. Frontier promotion

Carbon's base performance market rewards verified progress, not permanent incumbency.

```text
registered baseline / incumbent
        +
eligible challengers
        ↓
COMMON FRESH PROMOTION EXAM
        ↓
LeaderReplacementPolicy
        ↓
SUPERIOR?
 no -> no frontier reward
 yes -> FrontierAdvanceEvent
```

A new leader is an evidence state, not `new_score > old_score` across unrelated draws.

Where variance matters, incumbent and challengers must be compared under the same fresh hidden evidence and registered reconstruction-repeat policy.

At most one frontier winner per Challenge settlement window under the default batched policy.

---

## 8. Phase-0 breadth and Challenge portfolio

### P0 launch slice

Prove one complete qualified Challenge loop end to end.

### Phase-0 expansion

After the judge is proven, expand under the same constitution toward approximately **4-7 simultaneously reward-enabled academic Challenges**, preserving the original ambition of **seven PDE families** where operationally feasible.

The active set is frozen per `ChallengeSetEpoch`.

If there are `N` reward-enabled Challenges, each receives equal **notional period opportunity** `1/N`.

This does not make their raw scores comparable.

```text
Challenge A -> 1/N opportunity
Challenge B -> 1/N opportunity
...
Challenge N -> 1/N opportunity
```

If a Challenge has no verified frontier advance, its period opportunity is not silently reassigned to another Challenge winner.

---

## 9. Treasury settlement

Directly encoding Challenge-period accounting into normalized Bittensor validator weights is not a faithful representation of Carbon's intended economics.

Preferred architecture for implementation research:

```text
BITTENSOR / YUMA
      ↓
miner-side subnet emission
      ↓
CARBON TREASURY NEURON
      ↓
Treasury Vault custody
      ↓
period accounting across frozen ChallengeSetEpoch
      ↓
FrontierAdvanceEvent-bound entitlement
      ↓
validator-governed / timelocked settlement
      ↓
winner payout
```

Scientific authority and settlement authority are separate:

- Score Pack / promotion exam determines scientific frontier state.
- Treasury governance verifies that a proposed transfer corresponds to an authoritative frontier event.
- Treasury voters do not redefine the science.

Unused period allocation remains treasury capital under the base v1 policy; it does **not** automatically compound into the same Challenge's next prize unless a separate bounty policy explicitly says so.

---

## 10. Treasury reference architecture

qBittensor Labs' Enigma implementation demonstrates that a registered treasury neuron can receive subnet miner-side emissions and hold/control Alpha through a Bittensor-connected EVM governance system.

Useful pattern:

```text
TreasuryController
  proposal types
  active-validator governance
  quorum / success rules
  rate limits
  cancellation / expiry

TreasuryVault
  asset custody
  timelock execution
  Bittensor native integrations
```

Carbon should adapt, not copy blindly.

Carbon-specific requirement:

> **Every performance payout proposal should bind an exact FrontierAdvanceEvent digest.**

---

## 11. Result and settlement states

Scientific result states:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
VALID_RANKED
```

Promotion states:

```text
SUPERIOR
NOT_SUPERIOR
INDETERMINATE
```

Settlement states can include:

```text
FRONTIER_ADVANCE_CONFIRMED
PAYOUT_PENDING_GOVERNANCE
PAYOUT_TIMELOCKED
PAYOUT_PENDING_INFRA
PAID
CANCELED_WITH_REASON
```

Settlement failure does not rewrite the scientific record.

---

## 12. Burgers P0 repair

The integrated gauntlets exposed several defects in the old Burgers instantiation:

1. varying viscosity affected the target while `nu` was absent from candidate input;
2. the low-viscosity `nx=128` generator was under-resolved in tested cases;
3. generator error could invert truth preference;
4. the final-time spatial “residual” proxy omitted `u_t` and was not a full PDE residual;
5. reconstruction variance could cross admissibility boundaries.

Owner-recommended first authoritative Burgers slice:

- fixed `nu = 5e-3`;
- candidate map `u0 -> u(T)`;
- primary periodic Cole-Hopf reference, qualified numerical corroboration where useful;
- final-state physical measurements such as finite output, mean/mass conservation, energy non-increase, maximum-principle consistency, field error, and registered stress-stratum error;
- old spatial-balance proxy diagnostic-only unless separately qualified;
- reconstruction-repeat and rank-stability campaign before final leader-promotion thresholds.

Later conditioned Burgers Challenge:

```text
(u0, nu) -> u(T)
```

with `nu` explicitly supplied to the candidate.

---

## 13. Roadmap

> **First prove the judge. Then prove the portfolio. Then deepen the physics. Then widen the search. Bring industry in throughout.**

### Stage 1A — Prove one judge

One qualified Challenge, bounded construction family, end-to-end evidence and settlement dry run.

### Stage 1B — Prove the Phase-0 portfolio

Expand to a small concurrent academic portfolio, target 4-7 Challenges / original seven-PDE breadth where feasible. Demonstrate equal-opportunity accounting, common frontier promotion, treasury settlement, and no cross-Challenge score dependence.

### Stage 2 — Prove physics depth

Keep construction freedom bounded while changing systems/regimes/geometry.

### Stage 3 — Prove model-family neutrality

Freeze well-qualified Challenges and admit heterogeneous construction families through common task/output and evidence contracts.

### Stage 4 — Prove commercial discovery

Partner-shaped Challenge with real workload population, truth hierarchy, evidence requirements, and bounded search.

### Stage 5 — Prove qualification

Exact artifact/system + Product Qualification Pack + context of use + answerability/escalation + lifecycle.

### Stage 6 — Expand discovery freedom

Registered reconstruction protocols -> composable methods -> later sandboxed participant-supplied ConstructionPrograms.

---

## 14. Commercial progression

```text
Discovery     What should we try?
Evidence      Which approaches survive independently?
Qualification Can this exact artifact/system support this job?
Physics intelligence What should we try/test next?
```

The subnet frontier winner remains a candidate, not a product.

> **Rank nominates. Evidence qualifies.**

---

## 15. Bittensor's role

Use:

> **Bittensor supplies the open market of optimizers and the economic substrate. Carbon supplies the scientific objective, independent judge, frontier rule, and evidence-bound settlement semantics.**

Simple:

```text
Carbon:    What counts as a real advance?
Bittensor: Who can find it?
```

Bittensor consensus never determines physical truth.

---

## 16. Communication ladder

### One sentence

> **Carbon pays people and agents to find better ways to build fast physics models, independently proves when the frontier moves, and rewards the verified advance.**

### Stage mechanism

```text
DEFINE THE PHYSICS JOB
        ↓
QUALIFY THE EXAM
        ↓
PEOPLE + AGENTS COMPETE
        ↓
VALIDATORS REBUILD + TEST
        ↓
A VERIFIED FRONTIER ADVANCE WINS
        ↓
TREASURY SETTLES THE REWARD
```

### Thirty seconds

> Engineering simulation is powerful but expensive to repeat thousands of times. Fast models can help, but accuracy alone does not tell you whether they survive the physics. Carbon defines and qualifies a physical modeling exam, then lets people and agents compete over better ways to build the fast model. Validators reconstruct the contenders and test them on fresh protected cases. Mandatory scientific failure cannot be averaged away. A miner gets paid when independent evidence shows it has genuinely moved the frontier on one of Carbon's active Challenges. Multiple Challenges can run in parallel with equal reward opportunity, while a separately governed treasury settles verified frontier events.

---

## 17. Authority boundary

This v2 is an integrated owner recommendation. Until reviewed and migrated intentionally:

- current runtime schemas remain current runtime authority;
- current `Scoring.md` remains current scoring authority;
- current LIVE Challenge artifacts remain binding for any actual LIVE execution;
- generalized reconstruction remains future architecture;
- treasury settlement remains an implementation program requiring localnet/testnet qualification;
- Burgers repairs are not production-qualified until the qualification campaign is completed.
