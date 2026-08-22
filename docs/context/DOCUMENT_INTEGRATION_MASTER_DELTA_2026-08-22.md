# Carbon Document Integration Master Delta — 2026-08-22

**Status:** integration/control memo for owner + tech/science/economic review.  
**Purpose:** preserve the architecture learned since the roadmap reconciliation so the Canon, whitepaper, litepaper, deck, normative specs, and implementation plan do not drift apart.  
**Important:** this memo does not itself make runtime changes. Normative domain owners must be updated intentionally after review.

---

## 1. Executive conclusion

The recent design/gauntlet sequence does not change Carbon's durable identity. It materially strengthens the mechanism beneath it.

Durable identity remains:

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

The new mechanism-level synthesis is:

> **Carbon qualifies the scientific task and exam before it uses that exam to judge producers; rewards only independently verified frontier advances; and separates scientific evidence, frontier promotion, treasury settlement, and product qualification into distinct authorities.**

The post-roadmap additions that must not be lost are:

1. target population / SamplingPlan / generator separation;
2. Validation Dossier as qualification of the exam itself;
3. Score Pack as a versioned Evidence Use Contract;
4. admissibility before ranking (`physics > loss` as doctrine, not merely weights);
5. truth-dominance / generator-conformance stop-ship testing;
6. explicit task-input completeness (Burgers exposed hidden viscosity as a missing causal input);
7. reconstruction variability as method-level evidence;
8. frontier promotion as a separate common head-to-head scientific experiment;
9. reward for **new verified leaders**, not continuous incumbent rent;
10. equal economic opportunity across the active Challenge portfolio;
11. a treasury-neuron settlement layer rather than attempting to encode Carbon's Challenge accounting directly in Yuma weights;
12. treasury payouts cryptographically/evidentially bound to `FrontierAdvanceEvent`s;
13. unused Challenge-period allocation does not automatically flow to other winners;
14. scientific winner state and payout/infrastructure state remain separate;
15. P0 launch slice (one proved Challenge) must be distinguished from Phase-0 breadth (owner target: 4–7 concurrent qualified Challenges; original target seven PDEs).

---

# 2. Canon changes — HIGH PRIORITY

The Scientific Reference Canon should absorb durable epistemic/institutional laws, not implementation-specific Solidity or Burgers constants.

## 2.1 Add premise: the exam population is part of the scientific claim

Add to the premise chain:

> **A scientifically valid evaluator requires a justified target population and a qualified finite evidence design.** An operating envelope does not by itself define prevalence, dependence, strata, query distribution, rare-event importance, or finite sampling adequacy.

Preserve the distinction:

```text
P(x)  target population / claim population
Q(x)  finite proposal or sampling distribution
w(x)  evidence / score importance semantics
```

Canon law:

> **Sampling prevalence, target-population prevalence, and score importance are separate semantics.**

## 2.2 Add premise: the exam must itself earn credibility

Add:

> **A deterministic or numerically sophisticated generator is not automatically a credible scientific judge.** Generator conformance, reference adequacy, representation fidelity, measurement adequacy, and finite-sample sufficiency are separate evidence claims.

Canon formulation:

> **Carbon qualifies the exam before the exam qualifies a candidate.**

## 2.3 Add Score Pack epistemic role

Add:

> **A Score Pack is an Evidence Use Contract.** It states how already-qualified evidence becomes eligibility, scientific admissibility, estimands, aggregation, and deterministic rank. It does not qualify physics, truth sources, generators, or measurements.

Canon law:

> **Admissibility precedes ranking. Mandatory physical failure cannot be compensated by soft performance elsewhere.**

This should replace any interpretation of `physics > loss` as merely a 45/30/25 preference.

## 2.4 Add truth-dominance principle

The executed Burgers pilot exposed a case in which an under-qualified numerical generator could make exact agreement with generator error score better than agreement with independently qualified physical truth.

Canon law:

> **Within the qualified resolution of the exam, disagreement with generator-specific numerical error must not be rewarded over agreement with qualified physical truth.**

Treat this as a stop-ship principle, not a claim that one universal truth solver exists.

## 2.5 Add task-observability / input-completeness principle

Burgers exposed a structural issue: the task varied viscosity while the candidate input omitted viscosity.

Canon law:

> **A candidate cannot be judged for dependence on a physical variable that the registered task withholds from the candidate unless the task intentionally defines that variable as latent uncertainty and the estimand is authored accordingly.**

Public shorthand:

> **The job contract must expose the information needed to define the job.**

## 2.6 Add frontier-reward doctrine

Canon should distinguish scientific score from economic reward.

> **Carbon rewards verified advancement of a registered scientific frontier, not permanent ownership of a leaderboard position.**

A `new leader` is not `score_new > score_old`; it is an evidence state under a registered `LeaderReplacementPolicy`.

## 2.7 Add common promotion-exam doctrine

> **Leader replacement must compare incumbent and challengers on a common fresh promotion experiment when prior scores are not directly comparable because they arose from different hidden realizations.**

This follows the broader principle that numerical ordering is not automatically scientific distinguishability.

## 2.8 Add settlement separation

Canon-level institutional principle:

```text
scientific exam
    -> ScoreResult
    -> frontier-promotion decision
    -> FrontierAdvanceEvent
    -> treasury settlement
```

> **Scientific authority determines whether the frontier moved. Treasury authority determines whether an already-authorized entitlement is correctly settled. Neither should silently perform the other's job.**

## 2.9 Add payout-infrastructure state separation

If a scientifically verified winner cannot be paid because treasury/chain infrastructure is unavailable:

```text
FRONTIER_ADVANCE_CONFIRMED
+
PAYOUT_PENDING_INFRA
```

not `NO_WINNER`.

This generalizes the existing Canon distinction between scientific failure and infrastructure failure.

---

# 3. Whitepaper v2 -> recommended v2.1/v3 changes — MATERIAL

The whitepaper has the correct high-level identity and authority separation, but its current incentive/evaluation sections predate the distribution, dossier, Score Pack, frontier-settlement, and treasury architecture.

## 3.1 Abstract

Keep the durable identity. Update the mechanism sentence so it no longer jumps directly from measured behavior to Bittensor incentives.

Preferred architecture-level wording:

> Participants propose model-construction interventions; validators independently reconstruct them under a qualified Challenge; fresh protected evidence determines scientific admissibility and rank; verified frontier advances create reward entitlements; and Bittensor supplies the persistent economic substrate through a separately governed settlement layer.

Do not over-specify EVM treasury mechanics in the abstract.

## 3.2 New subsection: `The exam is a scientific object`

Add the chain:

```text
PhysicalSystemSpec
+ CandidateOutputContract
+ Claim / Envelope
        ↓
InstanceDistributionContract
        ↓
SamplingPlan
        ↓
ChallengeInstanceGenerator
        ↓
Reference / truth realization
        ↓
MeasurementContracts
        ↓
Validation Dossier
        ↓
Score Pack
```

Explain:
- envelope != population;
- P/Q/w separation;
- query/observation distribution is part of the task;
- censoring changes realized evidence population;
- Challenge-specific truth may be analytic, numerical, experimental, dataset-backed, or partner-controlled;
- no universal generator architecture is required.

## 3.3 Upgrade Validation Dossier treatment

The dossier should be described as qualifying the exam chain, with evidence classes covering:

1. physical-system adequacy;
2. claim/envelope adequacy;
3. target-population adequacy;
4. SamplingPlan adequacy;
5. generator implementation integrity;
6. distribution conformance;
7. reference/truth adequacy;
8. representation fidelity;
9. measurement adequacy/applicability;
10. statistical sufficiency/estimand clarity;
11. secrecy/decontamination/role separation;
12. censoring/limitations/residual uncertainty.

Core line:

> **The distribution architecture defines the exam population. The Validation Dossier earns the right to use that population as an exam.**

## 3.4 Replace fixed-score framing with Score Pack v1 framing

Keep current 45/30/25 only as the P0 compiled example.

Whitepaper should state:

```text
qualified evidence
    ↓
evidence eligibility
    ↓
mandatory admissibility
    ↓
explicit estimands
    ↓
soft aggregation/ranking
```

Key line:

> **Physics > loss is primarily an admissibility doctrine, not a larger physics coefficient.**

Explain distinct evidence states: eligible, not applicable, missing required, reference unavailable/uncertain, infrastructure failure, censored, invalid evidence.

## 3.5 Add `Frontier promotion` section

Scientific score and economic reward are no longer the same operation.

Describe:

```text
ScoreResult
    ↓
LeaderReplacementPolicy
    ↓
common fresh incumbent/challenger promotion exam where required
    ↓
SUPERIOR / NOT_SUPERIOR / INDETERMINATE
    ↓
FrontierAdvanceEvent
```

Rules:
- incumbent receives no automatic rent for remaining leader;
- one paid frontier event at most per Challenge settlement window;
- batch settlement prevents arrival-order gaming;
- first paid leader must beat a registered FrontierBaseline;
- same producer may improve its own frontier if a genuinely new method wins;
- material Challenge version changes establish a new frontier lineage or require explicit requalification.

## 3.6 Rewrite `Why Bittensor? / incentives` section

Current wording says Carbon score -> validator assessment -> Bittensor incentives. This is now incomplete.

Preferred separation:

```text
Carbon scientific objective
        ↓
qualified independent evidence
        ↓
verified frontier advance
        ↓
reward entitlement
        ↓
Treasury settlement
        ↓
Bittensor economic substrate
```

Do not say Bittensor directly pays proportional scientific scores.

## 3.7 Add portfolio breadth rule

Owner direction should be recorded explicitly:

> Phase 0 is intended to progress from one proved launch Challenge to a portfolio of approximately 4–7 concurrently active, scientifically qualified academic Challenges, with the original breadth target of seven PDEs.

Economic policy:

> **Each reward-enabled Challenge receives equal notional opportunity within a frozen ChallengeSetEpoch. Raw scores are never compared across Challenges.**

This is a critical fix to current roadmap language, which otherwise reads as if P0 is terminally one Challenge.

## 3.8 Add treasury settlement architecture

The whitepaper should explain the **pattern**, not copy Enigma implementation details as Carbon facts.

Proposed Carbon pattern:

```text
Bittensor miner-side emission
        ↓
registered Carbon Treasury neuron / vault
        ↓
period inflow ledger
        ↓
ChallengeSetEpoch: N equal notional allocations
        ↓
FrontierAdvanceEvent-backed entitlement
        ↓
validator-governed / timelocked settlement
        ↓
winning miner
```

Important qualifier:

> The Enigma/QBittensor Labs treasury provides a concrete reference architecture showing that a registered treasury neuron, governance controller, timelocked vault, Bittensor voting-power integration, and Alpha transfers are technically plausible. Carbon must still independently review, adapt, test, and secure its own implementation.

Do not imply Carbon has deployed this yet.

## 3.9 Add treasury constitutional requirements

- treasury cannot determine scientific winners;
- payout proposal must bind exact `FrontierAdvanceEvent` digest;
- amount must be mechanically derivable from frozen ChallengeSetEpoch + treasury inflow policy;
- no duplicate payout;
- validator/governance approval verifies settlement correspondence, not subjective scientific merit;
- timelock + cancellation + rate limits;
- payout infra failure does not alter scientific record;
- admin censorship / failure to propose needs an escalation or automated proposal-eligibility path;
- owner cannot unilaterally drain or redirect scientific reward entitlements;
- treasury implementation is separately security-qualified.

## 3.10 Add preliminary Burgers case study

Use as methodological evidence, clearly marked preliminary/non-production:

1. independent Cole–Hopf comparison exposed under-resolution at low viscosity;
2. truth-dominance test showed generator error can reverse intended reward ordering;
3. task audit exposed viscosity varied without being supplied to the one-input FNO;
4. fixed-viscosity repair produced a non-degenerate candidate population;
5. old final-state spatial-balance `residual` was demoted because it omitted `u_t`;
6. reconstruction seed variance can cross admissibility, so one lucky retraining does not establish method quality.

Scientific lesson:

> **Carbon's first end-to-end design exercises did not merely test candidates; they rejected defects in the exam itself.**

Do not present exact provisional thresholds as universal conclusions.

## 3.11 Update falsifiable hypotheses

Add explicit hypotheses/tests:

- qualified task distributions improve validity of frontier selection vs generator-defined sampling alone;
- common promotion exams reduce false frontier replacement;
- method-level reconstruction policy reduces lucky-artifact leader events;
- frontier-only rewards produce greater verified improvement per unit incentive than incumbent-rent or proportional-score alternatives;
- equal Challenge slots preserve physics breadth without requiring cross-Challenge score comparability;
- treasury settlement faithfully transmits verified frontier entitlements without rewriting scientific state.

---

# 4. Litepaper v2 -> recommended v2.1 changes — LIGHT BUT IMPORTANT

Do not import internal schema names heavily.

## 4.1 Change the P0 mechanism explanation

Current litepaper says Bittensor turns protected scores into economic pressure. Refine to:

> Carbon qualifies the exam, independently evaluates submitted methods, and records which candidates are scientifically admissible. A fresh frontier comparison determines whether a submission has actually advanced its Challenge. Only verified advances create reward entitlements.

## 4.2 Add three memorable rules

> **First prove the exam. Then run the exam.**

> **Fail mandatory physics, and soft accuracy cannot rescue you.**

> **Carbon pays for verified frontier advances, not permanent leaderboard ownership.**

## 4.3 Add multi-Challenge breadth paragraph

> After the first narrow Challenge proves the judge, Phase 0 is intended to broaden to a small concurrent portfolio (owner target approximately 4–7 qualified Challenges; original breadth target seven PDEs). Each Challenge keeps its own scientific ruler; Carbon does not pretend a score of 0.85 means the same thing across different PDEs.

## 4.4 Update Bittensor paragraph

Replace language that implies direct score-to-emission mapping.

Preferred:

> Bittensor supplies persistent open economic pressure. Carbon's scientific layer determines whether a Challenge frontier actually moved. A separate settlement layer turns verified frontier events into rewards while preserving the scientific record.

## 4.5 Treasury treatment

One short paragraph only:

> A planned treasury-neuron architecture allows network emissions to accumulate under validator-governed custody and be released as discrete rewards for verified frontier advances, rather than forcing every Challenge-period accounting decision into validator weight normalization. This settlement layer is an implementation/security design, not a source of scientific authority.

Mark as **planned/design**, not implemented, until localnet/testnet and security review.

## 4.6 Update roadmap

Current litepaper says `P0: prove one complete narrow loop`. Keep that as **P0 launch slice**, then explicitly add **Phase-0 portfolio expansion** before the later roadmap stages.

Recommended sequence:

1. prove one complete Challenge + judge;
2. prove frontier selection/reconstruction stability;
3. expand under same constitution toward the 4–7 Challenge Phase-0 portfolio;
4. deepen physics;
5. widen model families;
6. sponsored/partner Challenges + qualification;
7. widen construction freedom only when justified.

---

# 5. Stage deck — MINIMAL CHANGE, HIGH MESSAGE VALUE

Do not teach `InstanceDistributionContract`, `SamplingPlan`, `ScorePack`, treasury Solidity, or quorum parameters from stage.

## 5.1 Mechanism slide should become six beats

```text
1. DEFINE THE PHYSICS JOB
2. QUALIFY THE EXAM
3. PEOPLE + AGENTS COMPETE
4. VALIDATORS REBUILD + TEST
5. A NEW VERIFIED FRONTIER WINS
6. NETWORK REWARDS THE ADVANCE
```

Stage line:

> **First we prove the exam. Then we pay only when someone moves the frontier.**

## 5.2 Replace `score drives weights`

The existing branded deck says `Fail closed. Score drives weights.` This is now misleading.

Replace with:

> **Fail closed. Qualified evidence decides whether the frontier moved. Verified advances earn the reward.**

## 5.3 Add breadth visual

Simple stage graphic:

```text
4–7 PHYSICS CHALLENGES
Burgers | Poisson | ...
        ↓ equal opportunity
new frontier? -> reward
no new frontier? -> no miner payout for that Challenge-period
```

Do not list seven PDEs until the exact Phase-0 portfolio is ratified.

## 5.4 Bittensor explanation

Preferred stage line:

> **Carbon decides what counts as a scientifically verified improvement. Bittensor supplies the open optimizer market and the economic substrate that pays verified advances.**

If asked where unused emissions go, explain the planned treasury architecture in Q&A rather than on the main slide.

## 5.5 Strong Q&A addition

**Who controls the prize money?**

> Carbon is designing a validator-governed treasury settlement layer. Scientific winner determination and custody are separate: a payout has to correspond to a verified frontier event, and the treasury cannot redefine the science.

---

# 6. System Identity & Roadmap — MUST UPDATE

Current roadmap correctly says `First prove the judge`, but it should now distinguish **launch proof** from **Phase-0 breadth**.

Recommended replacement:

### Stage 1A — Prove one judge

One bounded Challenge, complete qualified exam, non-degenerate admissible methods, reconstruction stability, common frontier promotion, treasury-settlement dry run.

### Stage 1B — Prove the Phase-0 research portfolio

Expand under the same architecture to approximately 4–7 concurrently active qualified academic Challenges (owner target; original breadth target seven PDEs).

Goals:
- demonstrate scientific-authoring portability;
- maintain equal Challenge economic opportunity;
- prove frontier settlement under simultaneous heterogeneous Challenges;
- preserve cross-Challenge score non-comparability.

Then continue:

### Stage 2 — Deepen physics
### Stage 3 — Prove model-family neutrality
### Stage 4 — Sponsored / commercial discovery
### Stage 5 — Product qualification
### Stage 6 — Broaden construction freedom

Add roadmap slogan extension:

> **Prove one judge. Prove the portfolio. Then deepen the physics and widen the search.**

---

# 7. SPEC.md — CRITICAL COHERENCY RECONCILIATION

Current SPEC language is now materially stale in several places.

## 7.1 Replace direct score->emissions language

Stale concepts include:

- `Emissions follow that independent score`;
- `Lean scores only -> weights / emissions (winner-heavy decay)`;
- `Full submission ... Official score ... Yes — only path`;
- Landscape Port C `aim emissions at unsaturated high-upside regimes`.

New constitution:

```text
Official scientific evaluation
    -> ScoreResult
    -> LeaderReplacementPolicy
    -> FrontierAdvanceEvent
    -> treasury entitlement
    -> settlement
```

A score alone is not a payout event.

## 7.2 Remove Landscape authority over Challenge reward allocation

Equal Challenge opportunity is owner-level protocol policy under the new design. Landscape may propose Challenge creation/retirement or research priorities, but it must not dynamically reweight LIVE Challenge reward shares on its own.

## 7.3 Rewrite generator claims

Current SPEC says runtime data are challenge-specific, fully auditable, and verified against real physics/simulation tools. This is too strong as an unconditional property.

Replace with maturity-aware language:

> A Challenge may become reward-enabled only after its target population, SamplingPlan, generator, reference policy, measurements, and censoring/statistical limitations have passed its Validation Dossier requirements.

## 7.4 Update `Ground Truth Oracle`

Do not imply Julia/SciML is universally the truth source. It is one possible reference implementation family.

Use:

> Challenge-specific reference/truth realization may be analytic, mesh-/time-converged numerical simulation, experimental measurement, dataset-backed, partner-controlled, or multi-source, subject to qualification.

Burgers example: Cole–Hopf primary; independent numerical witness secondary.

## 7.5 Update P0 Challenge semantics

For the first authoritative Burgers slice, record the owner-recommended fixed-viscosity repair until a conditioned `(u0, nu) -> u(T)` task is explicitly registered.

Do not silently change existing current runtime challenge bytes without the formal migration/versioning path.

## 7.6 Update physics residual claims

Any current claim that the final-time spatial-balance proxy is a full Burgers residual must be removed. It may remain diagnostic-only unless a proper spacetime MeasurementContract is qualified.

---

# 8. Scoring.md — TARGETED FUTURE-ARCHITECTURE RECONCILIATION

Do not silently rewrite current A5 schema-1.0 behavior.

Add a normative/future note:

- current P0 ScoreEngine remains narrow implementation;
- generalized Score Pack = Evidence Use Contract;
- admissibility before soft aggregation;
- exact upstream identities jointly define score meaning;
- score result state matters downstream;
- cross-Challenge scores non-comparable by default;
- `ScoreResult` feeds frontier promotion, not direct emissions.

Explicitly deprecate documentation language that treats 45/30/25 as the economic constitution.

---

# 9. Generator / Data / Validation docs — MUST SYNCHRONIZE

## `Generator_Creation.md`

Add requirement that generator implements an authored `InstanceDistributionContract` + `SamplingPlan`; it does not define population truth by code behavior.

## `Data_Management.md`

Expand train/eval/stress separation into:

- target population vs sampling plan;
- role populations;
- semantic decontamination beyond seed separation;
- intended vs realized evidence after censoring;
- query/observation population.

## `Generator_Validation.md`

Already the strongest new owner. Ensure older references everywhere point to the v2 generalized Validation Dossier role.

## Challenge-specific docs

Burgers should become the worked reference showing:
- task I/O completeness;
- truth qualification;
- generator convergence;
- measurement qualification;
- stress semantics;
- reconstruction repeat policy;
- leader-promotion calibration.

---

# 10. Frontier / treasury normative document stack — NEW

Recommended durable owners:

1. `Score_Pack_Architecture_v1.md` — evidence -> scientific rank;
2. `Frontier_Leader_Settlement_v1.md` — rank evidence -> frontier event;
3. `Treasury_Settlement_Architecture_v1.md` — frontier event -> economic entitlement/custody/payout;
4. `Bittensor_Settlement_Adapter_v1.md` — chain-specific transport/registration/monitoring;
5. `Operations.md` — keys, deploy, pause/freeze, incident response;
6. `Evaluation_Evidence_and_Validator_Audit.md` — independent agreement and audit evidence.

`Emissions_Mapping_v1.md` proportional mapping is superseded conceptually by frontier settlement and should be clearly marked historical/superseded. `Emissions_Mapping_v2.md` should remain aligned with the treasury implementation once designed.

---

# 11. Treasury architecture to preserve from Enigma study — REFERENCE, NOT COPY

QBittensor Labs Enigma demonstrates a concrete dual-contract treasury pattern:

```text
TreasuryController
  proposals / voting / limits / trusted-validator checks

TreasuryVault
  timelocked custody / execution / Bittensor-native operations
```

Relevant demonstrated concepts for Carbon research:

- separately registered treasury neuron;
- treasury hotkey association;
- validator whitelist + active-validator eligibility;
- Bittensor-native stake-weighted voting power;
- dynamic quorum;
- typed proposal paths;
- queue/execute timelock lifecycle;
- cancellation and expiry;
- asset-specific spending/rate limits;
- Alpha transfers using Bittensor staking precompile;
- localnet E2E tests including malicious actors.

Carbon-specific differences recommended:

1. payout proposal must bind `FrontierAdvanceEvent` digest;
2. payout amount should be mechanically checkable against epoch inflow + ChallengeSetEpoch allocation;
3. scientific decision cannot be modified by treasury vote;
4. treasury vote verifies settlement legitimacy, not winner merit;
5. admin proposal censorship should have a bounded fallback/automatic eligibility path;
6. duplicate payout prevention must be keyed by frontier-event identity;
7. settlement state is auditable separately from scientific state;
8. contract upgrade/governance policy must not permit retrospective rewriting of paid scientific history.

---

# 12. Maturity labels — IMPORTANT PUBLIC CLAIM CONTROL

The docs should distinguish at least:

```text
MOTIVATED
SPECIFIED
IMPLEMENTED
TESTED
REPLICATED
PRODUCTION-QUALIFIED
```

Suggested current classification after the design work:

- distribution / Validation Dossier architecture: **SPECIFIED / owner-ratified architecture**;
- Score Pack generalized architecture: **OWNER-RECOMMENDED v1**, current runtime still narrow A5;
- frontier leader settlement: **OWNER-RECOMMENDED / SIMULATED**;
- treasury-neuron Carbon architecture: **REFERENCE-VALIDATED CONCEPT / NOT YET CARBON-IMPLEMENTED**;
- Enigma treasury existence: external implementation evidence, not Carbon implementation;
- Burgers truth/repair findings: **CONTROLLED PILOT**, not production qualification;
- full Carbon miner-incentive hypothesis: still **not empirically validated at scale**.

---

# 13. New constitutional invariants worth adding to the master constitution

1. **The scientific task owns the population; the SamplingPlan defines finite evidence; the generator implements the plan.**
2. **The exam must be qualified before it may qualify candidates.**
3. **Admissibility precedes ranking.**
4. **Within qualified resolution, generator error must not be rewarded over qualified physical truth.**
5. **A registered task must expose the information required to define its candidate mapping, unless latent uncertainty is explicitly part of the task.**
6. **A new leader is an evidence state, not a floating-point inequality.**
7. **Frontier promotion compares scientifically comparable evidence, using a common fresh exam where required.**
8. **Carbon rewards verified frontier advances, not permanent leaderboard incumbency.**
9. **Cross-Challenge scientific scores are not automatically comparable; equal Challenge opportunity does not require them to be.**
10. **Challenge-set membership and equal allocation are frozen prospectively per settlement epoch.**
11. **Scientific winner determination and treasury custody/settlement are separate authorities.**
12. **A treasury cannot create, erase, or alter a `FrontierAdvanceEvent`.**
13. **A settlement failure does not erase a scientific frontier advance.**
14. **Unused Challenge-period allocation cannot silently become another Challenge's scientific reward.**
15. **No payout without an exact evidence/identity chain from qualified Challenge to frontier event to settlement.**

---

# 14. Recommended update order

Do not edit every document independently. Reconcile in authority order:

```text
1. owner/tech/science/economic review of new decisions
2. lock Frontier + Treasury architecture docs
3. update System_Identity_and_Roadmap
4. reconcile SPEC.md
5. reconcile Scoring / Generator / Data / Validation / Operations
6. update Canon constitutional + premise sections
7. update Whitepaper
8. update Litepaper
9. update stage deck / Q&A
10. run a final coherency audit across all public + normative docs
```

Why this order: public papers should summarize the settled architecture, not become accidental normative authorities.

---

# 15. Coherency tests after updates

A final document audit should verify that no live/current document still implies any of the following unless explicitly marked historical:

- raw score directly determines miner payout;
- incumbent leaders continuously earn emissions simply for remaining leaders;
- 45/30/25 is Carbon's universal scientific/economic constitution;
- Challenge scores are comparable across PDEs;
- Landscape dynamically reweights LIVE Challenge rewards;
- generator code defines the task population;
- an operating envelope defines prevalence;
- a deterministic generator is automatically a truth source;
- Julia/SciML is Carbon's universal truth oracle;
- a final-state spatial proxy is the full Burgers PDE residual;
- variable viscosity may be graded when viscosity is absent from the candidate input contract;
- one lucky reconstruction establishes method quality;
- the first admissible miner automatically deserves a frontier prize without beating a registered baseline;
- old incumbent scores from different hidden draws are necessarily comparable to fresh challenger scores;
- a treasury/governance vote is allowed to decide the science;
- treasury/payout failure means no scientific winner;
- unused Challenge allocation automatically flows to other winning Challenges;
- `P0 = one PDE forever` or `P0 = seven simultaneous unqualified PDEs`.

Preferred P0 wording:

> **The P0 launch slice proves one complete Challenge. Phase-0 then expands under the same scientific constitution toward a small concurrent portfolio, with the owner target of roughly 4–7 qualified Challenges and the original breadth target of seven PDEs.**

---

# 16. Final integration statement

The most coherent current Carbon story is now:

> **Carbon turns a defined physical modeling problem into a qualified scientific Challenge. People and agents compete to propose better construction methods. Validators independently rebuild and examine them on fresh protected evidence. Mandatory scientific failures are disqualifying. A separate frontier-promotion experiment determines whether a contender has actually moved the Challenge frontier. Carbon rewards that verified advance—not permanent leaderboard ownership. Multiple qualified Challenges can run in parallel with equal economic opportunity without pretending their scores are comparable. Network emissions can be accumulated through a separately governed treasury-neuron settlement layer, where payouts are bound to exact frontier events. Every authoritative experiment remains evidence; selected artifacts still require a distinct job-shaped qualification path before engineering use.**

This preserves Carbon's original identity while giving the incentive mechanism, scientific judge, multi-Challenge breadth, and economic settlement layer clear and non-overlapping authorities.
