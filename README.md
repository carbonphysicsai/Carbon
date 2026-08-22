# Carbon

**Discovery + Evidence for Physics AI**

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

Carbon starts narrowly with neural-operator training strategies, but its durable scientific contract is broader than any one model family. Participants propose reproducible construction methods; independent validators rebuild and test the resulting candidates under registered scientific contracts; Carbon records what survives, what fails, and where the evidence applies.

## The core idea

Fast physical models can make repeated simulation, optimization, control, uncertainty analysis, and agentic engineering dramatically cheaper. The hard problem is credibility: low loss alone does not establish physical admissibility, robustness, reproducibility, or bounded engineering use.

Carbon turns that credibility problem into part of the search objective.

```text
DEFINED PHYSICAL JOB
        ↓
QUALIFY THE EXAM
        ↓
PEOPLE + AGENTS COMPETE
        ↓
VALIDATORS REBUILD + TEST
        ↓
VERIFIED FRONTIER ADVANCE?
        ↓
REWARD THE ADVANCE
```

The producer never owns the official grade.

## Qualified Challenges

A Carbon Challenge is more than a PDE name and a hidden test set. The scientific chain is:

```text
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
Generator Conformance
        ↓
Reference / Truth Policy
        ↓
MeasurementContracts
        ↓
Validation Dossier
        ↓
Score Pack = Evidence Use Contract
        ↓
LIVE qualified Challenge
```

> **Carbon qualifies the exam before the exam qualifies a candidate.**

Target population `P(x)`, finite proposal/sampling distribution `Q(x)`, and score/evidence weighting `w(x)` are separate semantics. A deterministic generator is not automatically a trustworthy scientific judge.

## Physics > loss

Carbon's durable rule is not “physics gets a bigger coefficient.” It is:

> **Admissibility precedes ranking. Mandatory physical/scientific failure cannot be compensated by soft performance elsewhere.**

The current P0 45/30/25 weighted-geometric profile remains one narrow runtime Score Pack profile, not Carbon's universal scientific constitution.

## Frontier rewards

Carbon's owner-recommended future performance market rewards **verified scientific progress**, not permanent leaderboard ownership.

```text
registered baseline / incumbent
        +
eligible challengers
        ↓
common fresh promotion exam where variance matters
        ↓
LeaderReplacementPolicy
        ↓
SUPERIOR | NOT_SUPERIOR | INDETERMINATE
        ↓
FrontierAdvanceEvent
```

A new leader is an evidence state, not simply `new_score > old_score` from unrelated random draws.

## Phase-0 breadth

The roadmap separates proving the judge from proving breadth:

1. **P0 launch slice:** prove one complete qualified Challenge end to end.
2. **Phase-0 expansion:** move under the same constitution toward roughly **4–7 concurrently reward-enabled academic Challenges**, preserving the original **seven-PDE breadth ambition** where operationally feasible.

Each active Challenge in a frozen `ChallengeSetEpoch` has equal notional performance-reward opportunity `1/N`. Raw scores across different Challenges are not treated as a common scientific unit.

## Treasury settlement

Directly encoding Carbon's Challenge accounting into normalized Bittensor validator weights is not the preferred future design. The current research architecture is:

```text
Bittensor / Yuma miner-side emission
        ↓
registered Carbon Treasury neuron
        ↓
separately governed TreasuryVault
        ↓
ChallengeSetEpoch accounting
        ↓
FrontierAdvanceEvent-bound entitlement
        ↓
validator-governed / timelocked settlement
        ↓
winner payout
```

The treasury settles economic value; it does not determine scientific truth. This architecture is **specified for implementation research and still requires localnet/testnet qualification** before production use.

## P0 implementation

Current P0 remains deliberately bounded:

- neural-operator strategy submissions;
- validator-controlled fresh retraining;
- protected evaluation;
- mandatory gates + Challenge-bound score;
- JAX-first qualified execution path;
- no arbitrary miner code in the official evaluator;
- product qualification separate from subnet search.

The first authoritative Burgers design is being repaired/qualified around a fixed-viscosity `u0 → u(T)` task with a qualified periodic Cole–Hopf reference path. Historical `poc/` Burgers code remains implementation evidence, not automatically LIVE-qualified science.

## Product path

A subnet frontier winner is a **candidate**, not a product.

> **Rank nominates. Evidence qualifies.**

Selected artifacts or systems enter a separate job-shaped Product Qualification path with exact artifact identity, context of use, evidence, limitations, answerability/escalation, and lifecycle rules.

## Physics intelligence

Verified experiments create experimental memory. Carbon reserves **physics intelligence** for provenance-bearing knowledge that demonstrably improves future scientific or engineering decisions.

A graph, embedding, ontology, or card lake is not automatically intelligence.

> **Canon informs hypotheses. Carbon experiments adjudicate them.**

## Bittensor's role

> **Bittensor supplies the open market of optimizers and the economic substrate. Carbon supplies the scientific objective, independent judge, frontier rule, and evidence-bound settlement semantics.**

Simple version:

```text
Carbon:    What counts as a real advance?
Bittensor: Who can find it?
```

Bittensor consensus does not determine physical truth.

## Roadmap

> **First prove the judge. Then prove the portfolio. Then deepen the physics. Then widen the search. Bring industry in throughout.**

- **Stage 1A:** one qualified Challenge / full judge.
- **Stage 1B:** Phase-0 4–7 Challenge portfolio, frontier selection, treasury settlement.
- **Stage 2:** deeper physical regimes / systems / geometry.
- **Stage 3:** heterogeneous model families under common task/evidence contracts.
- **Stage 4:** partner-shaped commercial discovery Challenges.
- **Stage 5:** exact-artifact / system qualification for bounded use.
- **Stage 6:** broader reconstruction protocols and later sandboxed construction-algorithm discovery.

## Documentation authority

This branch contains both current runtime documents and newer owner-recommended architecture. **Do not infer authority from filename or recency.**

Start here:

- [`DOCUMENTATION_STATUS.md`](./DOCUMENTATION_STATUS.md) — status / supersession / migration index.
- [`docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`](./docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md) — integrated scientific constitution.
- [`Design_Specs/System_Identity_and_Roadmap_v2.md`](./Design_Specs/System_Identity_and_Roadmap_v2.md) — integrated architecture and roadmap.
- [`SPEC_VNEXT_INTEGRATED.md`](./SPEC_VNEXT_INTEGRATED.md) — consolidated future protocol candidate.
- [`Design_Specs/Build_Out_vNext_Integrated.md`](./Design_Specs/Build_Out_vNext_Integrated.md) — future implementation sequence.

### Current runtime authority remains separate

Until an intentional reviewed migration:

- [`SPEC.md`](./SPEC.md) remains current runtime architecture where implemented;
- [`Design_Specs/Scoring.md`](./Design_Specs/Scoring.md) remains sole current P0 scoring mathematics;
- existing schemas, packs, registry entries, and code remain implementation reality;
- frontier/treasury architecture is not claimed live merely because it is specified.

See [`docs/context/DOCUMENT_RECONCILIATION_AUDIT_2026-08-22.md`](./docs/context/DOCUMENT_RECONCILIATION_AUDIT_2026-08-22.md) for the full migration audit.

## Maturity discipline

Carbon distinguishes:

`MOTIVATED / SPECIFIED / IMPLEMENTED / TESTED / REPLICATED / PRODUCTION-QUALIFIED`

Integrated design gauntlets have already exposed concrete defects in the first Challenge instantiation, including a missing causal input, under-resolved generator regimes, a truth-vs-generator ranking inversion, a mischaracterized residual diagnostic, and material reconstruction variance. Those are useful design-validation results; they are **not** a claim that the production subnet or treasury is already qualified.
