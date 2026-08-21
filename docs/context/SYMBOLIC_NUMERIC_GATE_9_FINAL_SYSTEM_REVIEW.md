# Gate 9 — Final System-Level Review: Symbolic-Numeric Design Integration

**Branch:** `design/symbolic-numeric-integration`  
**Status:** final design-discovery reconciliation; no P0 runtime expansion.  
**Scope:** Reconcile Gates 1–8 and discoveries D-001–D-081 into stable Carbon design consequences before canon/paper/deck edits.

---

## 1. Executive judgment

The simulation changed Carbon's **long-term ontology**, but did **not** invalidate its P0 implementation strategy.

### Stable long-term thesis

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

Neural operators remain the correct first model class. Fresh validator retraining remains the correct first producer-independence mechanism. Burgers remains the correct narrow proving ground. None of the symbolic-numeric discoveries justify broadening P0.

The important correction is conceptual: Carbon must not mistake its first implementation for its terminal scientific category.

### Strongest system-level discovery

Carbon's durable value is not a model family, symbolic framework, benchmark, or leaderboard. It is the **controlled experimental loop plus the provenance-bearing evidence system that learns which model-construction interventions work under which physical contexts and engineering constraints.**

---

## 2. What changed versus the earlier design

### 2.1 Search object

Earlier dominant framing:

```text
training strategy -> neural operator
```

Reconciled long-term framing:

```text
ModelConstructionStrategy
        ↓
producer-independent ReconstructionProtocol
        ↓
FastPhysicalModel / qualified decision system
```

A neural training strategy is one subtype.

### 2.2 Physical semantics

Earlier Challenges encoded physical meaning across prose, generator code, dossier and scoring artifacts.

Reconciled architecture adds a descriptive semantic layer:

```text
PhysicalSystemSpec
  + optional composition/coupling semantics
```

It describes the physical object but never certifies it.

### 2.3 Measurement

Earlier design could treat metric names/implementations as sufficiently local to Score Packs.

Reconciled architecture separates:

```text
physical property
    ↓
MeasurementContract
    ↓
Validation Dossier qualification/calibration
    ↓
Score Pack use
```

Measurement definition, qualification and score use are separate authorities.

### 2.4 Experimental evidence

Model Cards remain correct for P0 learned models. Long term, the evidence superclass must support non-trained artifacts and family-specific reconstruction semantics:

```text
ExperimentRecord
```

### 2.5 Physics intelligence

Earlier Landscape graph:

```text
strategy × regime × outcome
```

Reconciled scientific object:

```text
model-construction intervention
× pre-intervention physical context
× selection mechanism
× exact measurement semantics
× execution/reconstruction provenance
→ outcome / censoring
→ reproducibility
→ qualification / lifecycle evidence
```

This is not automatically causal.

---

## 3. Reconciled architecture stack

```text
DOMAIN SCIENCE / ENGINEERING INTENT
                ↓
        PhysicalSystemSpec
     (+ composition/coupling later)
                ↓
     CandidateOutputContract
                ↓
        ConstructionPolicy
                ↓
     ModelConstructionStrategy
                ↓
      ReconstructionProtocol
                ↓
        FastPhysicalModel
                ↓
   protected independent evaluation
                │
       MeasurementContracts
                │
       Validation Dossier
                │
            Score Pack
                ↓
        ExperimentRecord
                ↓
             Landscape
                ↓
 better search / targeted experiments
                ↓
 qualification / portfolio / escalation
```

### Authority invariant

No arrow above implies that the upstream object certifies the downstream one.

- PhysicalSystemSpec does not certify physics.
- Structural validation does not establish scientific validity.
- Symbolic transformation does not establish numerical adequacy.
- Measurement definition does not qualify a threshold.
- Dossier evidence does not choose scoring weights.
- Score does not create product qualification.
- Landscape does not certify causality.
- Component qualification does not certify a composition.

---

## 4. Contradiction review

### Apparent contradiction A — physics > loss vs technology neutrality

**No conflict.**

`physics > loss` is an objective-design principle: low predictive loss cannot compensate for mandatory physical failure under the registered contract. It does not imply that a model must contain explicit physics or symbolic structure.

A classical surrogate, ROM, hybrid model or neural operator may win if it survives the same external evidence standard.

### Apparent contradiction B — independent retraining vs non-neural artifacts

**Resolved by generalization, not replacement.**

Producer-independent reconstruction is the invariant. Fresh retraining is mandatory for neural strategies where the Challenge defines a learned construction. Non-neural families require an equivalent independent rebuild/reduction/configuration protocol.

### Apparent contradiction C — public physical semantics vs protected evaluation

**No conflict if semantics and realizations stay distinct.**

The physical system/envelope can be public while official draws, stress instantiations, seeds and outcome-derived Landscape intelligence remain governed/hidden. Machine-readable physics actually increases Goodhart/leakage pressure, so the Evaluation Information Budget remains necessary.

### Apparent contradiction D — symbolic-numeric structure vs physics authority

**No conflict if symbolic structure is descriptive.**

Symbolic structure proposes/organizes semantics and candidate measurements. Human-qualified scientific contracts, reference evidence and independent exams remain authoritative.

### Apparent contradiction E — one subnet score vs engineering economics

**Resolved by separation.**

Scientific performance, computational admissibility/efficiency and product decision utility are distinct. Do not silently collapse latency, cost, commercial value or information value into `S_combined`.

### Apparent contradiction F — one winner vs portfolio/routing product

**Different layers.**

The performance market may rank submissions under one Challenge. Product qualification may later select several artifacts for different contexts and qualify a router/escalation system. Leaderboard winner remains distinct from product architecture.

### Apparent contradiction G — minimal v0.1 schema vs multiphysics needs

**Resolved by versioning.**

Keep v0.1 minimal for Burgers/Poisson. Composition, scoped identity, units/nondimensionalization, CouplingContract and geometry references belong to future v0.2+ only when implemented.

---

## 5. Stable constitutional additions

The following principles survived every simulation gate and should enter the canon/design constitution.

1. **The physical representation does not certify the physics.**
2. **Measurement definition, measurement qualification and measurement use are separate authorities.**
3. **Producer-independent reconstruction is required; fresh retraining is its learned-model subtype.**
4. **A candidate is compared through a registered task/output contract, not architecture ideology.**
5. **Mechanistic/symbolic structure receives no automatic score privilege.**
6. **Scientific performance, information value, resource efficiency and commercial utility remain distinct values.**
7. **End-to-end success does not validate an internal learned physical relation.**
8. **Component qualification does not automatically compose into system qualification.**
9. **Physical similarity and physics intelligence must earn value prospectively.**
10. **Generated diagnostics and structured intelligence remain subject to Goodhart/leakage governance.**
11. **Answerability, abstention and escalation are prospective task/product semantics.**
12. **The protocol should not require learning when a non-learned physical representation wins.**

These extend, rather than replace, Carbon's existing constitutional separations.

---

## 6. Stable new design objects

### High confidence / architecture-level

- `PhysicalSystemSpec` — descriptive physical semantics.
- `MeasurementContract` — exact numerical measurement identity.
- `CandidateOutputContract` — common observable/query interface.
- `ModelConstructionStrategy` — future superclass for construction interventions.
- `ReconstructionProtocol` — producer-independent rebuild semantics.
- `FastPhysicalModel` — technology-agnostic fast physical artifact.
- `ConstructionPolicy` — prospective allowed search space.
- `ExperimentRecord` — future evidence superclass.
- `ContextFeatureSet` — derived physical/regime features for Landscape experiments.
- `CouplingContract` — future composition/interface physical semantics.

### Useful but pre-evidence/workflow objects

- `AdapterReport` — semantic conversion coverage/loss.
- `EvidenceRequirement` — required-but-not-yet-produced evidence.
- `ChallengeAuthoringPackage` — compiler output, explicitly not a certificate.

### Deferred exact shape

- `CompatibilityEnvelope`;
- geometry/topology schema;
- alias/shared-identity representation details;
- universal unit system;
- DAE/index metadata;
- portfolio/router qualification schema.

---

## 7. What should change now in implementation

### P0 / Wave A

**Do not broaden P0.**

A1–A3 remain closed. A4/A5 should proceed under existing scope. Symbolic-numeric work should not add runtime dependencies or new score authority.

The only near-term future-proofing worth preserving is:

- A3 generic artifact binding can later bind `physical_system_spec` without schema migration;
- A6 internal evidence should preserve exact semantic/measurement identities when those artifacts exist, without miner-facing disclosure by default;
- A12/additive invariant tests should prove semantic artifacts cannot alter score or bypass disclosure;
- repair the Burgers residual/proxy naming/semantics before production authority if that metric persists.

### Post-P0 authoring track

Recommended order:

1. ratify minimal PhysicalSystemSpec v0.1;
2. structural validator;
3. ModelingToolkit adapter + AdapterReport;
4. standalone MeasurementContract candidate;
5. Challenge Authoring Package / EvidenceRequirement tooling;
6. second/third real Challenge validation;
7. only then consider production Challenge Compiler.

### Landscape track

Do not implement a giant ontology first.

Test H16 prospectively using small provenance-bearing ContextFeatureSets. Require decision lift against baselines before claiming structured physical context is a moat.

### Hybrid/composition track

Defer until the lean subnet works. When earned:

- CandidateOutputContract;
- ModelConstructionStrategy;
- ConstructionPolicy;
- ReconstructionProtocol;
- scoped component identity;
- CouplingContract;
- assembled artifact qualification.

---

## 8. Scientific thesis changes

### Keep

- trustworthiness/generalization is the commercial/scientific gap;
- physics > loss;
- producer does not control official grade;
- protected exams are required under adaptive search;
- evidence/failure retention matters;
- Landscape must be epistemically typed;
- qualification is bounded and lifecycle-aware;
- decentralization coordinates search/verification, not scientific truth.

### Deepen

#### Physics intelligence

Recommended definition:

> **Physics intelligence is provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective decisions rather than retrospective narrative alone.**

#### Generalization

Generalization should be discussed at several levels:

1. candidate generalization across hidden draws/regimes;
2. intervention transfer across physical contexts;
3. evidence/measurement portability only when identities and assumptions align;
4. product qualification within bounded context of use.

#### Scientific object

The winning model is not the whole scientific object. The richer object is the intervention + reconstruction + context + measurement + outcome record.

---

## 9. Value accrual / moat review

The simulation strengthens the moat thesis, but also narrows what can honestly be claimed today.

### Potential compounding assets

1. **Challenge-authoring infrastructure** — structured conversion from scientific model to evidence requirements/test plan.
2. **Measurement library + calibration lineage** — reusable but context-bound scientific measurement infrastructure.
3. **Intervention-outcome evidence graph** — successes, failures, censoring, reconstruction and qualification.
4. **Physical-context transfer knowledge** — only a moat if H16/prospective decision lift succeeds.
5. **Qualification/evidence lineage** — difficult-to-copy accumulated credibility across artifacts and contexts.
6. **Partner workflow** — ability to turn scientific models into controlled competitive experimental programs.

### What is not yet a moat

- existence of a symbolic schema;
- ModelingToolkit integration by itself;
- a benchmark suite;
- generic physics residuals;
- an ontology/knowledge graph without prospective value;
- decentralization alone.

### Strongest long-term flywheel

```text
partner/domain model
   ↓
structured Challenge authoring
   ↓
competitive model-construction search
   ↓
independent reconstruction + protected exam
   ↓
provenance-rich evidence including failures
   ↓
Landscape predicts what to try next
   ↓
registered information-value experiments
   ↓
better qualified fast physical models / systems
   ↓
new lifecycle evidence and harder Challenges
```

---

## 10. Product strategy consequences

### Product object

Do not define the long-term SKU as weights/ONNX.

Preferred abstraction:

> **qualified executable FastPhysicalModel or qualified physical-decision system**

Possible packaging includes neural model, compiled library, reduced solver, hybrid system, portfolio/router, API/service, or controlled container.

### Portfolio/routing opportunity

A qualified portfolio may route queries among multiple specialists and escalate outside their evidence envelopes. This can improve engineering decision economics, but it requires system-level qualification; certificates do not compose automatically.

### Partner product candidate

Challenge Compiler should be positioned, if later validated, as:

> **evidence-aware scientific test authoring / model-discovery program design**

not automatic physics verification.

### Proprietary partner boundary

Controlled/private scientific semantics are commercially plausible but require a transparency compatibility test. Some proprietary problems may not be appropriate for an open subnet Challenge.

---

## 11. Canon integration plan

Add a major canon pillar covering:

### Symbolic-numeric and compositional scientific modeling

Topics:

- symbolic-numeric equation-based modeling;
- compositional/acausal systems;
- structural transformation vs physical semantics;
- units/nondimensionalization;
- hybrid mechanistic/learned models;
- reduced-order modeling;
- model discrepancy/learned closures;
- measurement theory / numerical verification;
- model qualification and context of use;
- adaptive data analysis / Goodhart pressure;
- causal inference under adaptive experiment selection.

### Core scientific case to support

> Physical AI is not one model family. Carbon should preserve enough physical and experimental structure to compare modeling interventions, measure them honestly, and learn which approaches transfer without making the representation itself an oracle.

Do not make ModelingToolkit the canon's thesis; use it as one important implementation/ecosystem example.

---

## 12. Whitepaper v1.1 integration plan

The whitepaper deserves meaningful but controlled expansion.

### Add/deepen

1. **Definition of physics intelligence** using prospective decision lift.
2. **Structured physical representations** and why Challenge IDs are insufficient for transfer.
3. **MeasurementContract concept**: physics property != numerical measurement != score.
4. **Model construction as the long-term search space**; neural operators as first class.
5. **Producer-independent reconstruction** as the general scientific principle behind retraining.
6. **Physical similarity as a falsifiable representation hypothesis**, not fixed ontology.
7. **Hybrid/compositional systems** as future search/qualification domain.
8. **Qualification non-compositionality** and portfolio/escalation systems.
9. Add hypotheses for structured context, authoring efficiency, hybrid search and information-value experiment selection.

### Do not overclaim

Use "designed to", "could", "we hypothesize", or future-tense for capabilities not implemented/tested.

Do not claim:

- automatic symbolic-to-exam compilation;
- achieved cross-system transfer intelligence;
- automatic causal discovery;
- automatic physics verification;
- universal hybrid-model superiority;
- deployed multiphysics qualification.

---

## 13. Litepaper integration plan

Keep the litepaper simple.

Recommended changes only:

1. define neural operators as **the starting model class**;
2. broaden one phrase from "training strategies" toward "ways to build fast physics models" while immediately grounding current implementation in neural operators;
3. refine physics intelligence to include learning which interventions work across physical regimes;
4. optionally state that the architecture can later admit hybrid mechanistic/learned approaches;
5. preserve physics > loss, independent exams, evidence, qualification and Bittensor mechanism as the dominant narrative.

Do **not** introduce PhysicalSystemSpec, MeasurementContract, CouplingContract, namespaces, units, or symbolic ASTs in the litepaper.

---

## 14. Summit deck integration plan

Hard simplicity constraint.

### Recommended stage wording

> **Carbon pays people and agents to find better ways to build fast physics models — starting with neural operators — and independently tests what survives.**

### Stack/category

Prefer:

> **Discovery + Evidence layer for Physics AI**

rather than a framework-specific "training + verification" category.

### Potential visual wording

```text
FAST PHYSICS MODELS
starting with neural operators
```

### Keep off stage unless asked
