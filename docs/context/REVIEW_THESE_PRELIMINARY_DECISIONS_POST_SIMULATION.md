# Review These Preliminary Decisions — Post-Simulation Architecture

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject.  
**Purpose:** Distill the mature design decisions surfaced across symbolic-numeric / agentic simulation Gates 1–10 into one review queue.  
**Scope:** These are architecture-level decisions for future Carbon evolution. Unless explicitly stated, they do **not** change current P0 wire contracts, A1–A6 scope, current scoring, LIVE Challenge semantics, or product qualification on `main`.

---

# Executive disposition

Proceed on the design branch as though **S1–S18 are accepted provisionally**, while preserving the following master guardrail:

> **Do not broaden P0 because the long-term ontology has broadened.**

The current launch path remains bounded neural-operator strategy search with validator-controlled retraining and protected evaluation. The decisions below define the architecture Carbon should grow into if and when evidence, security, and implementation maturity justify it.

The intended review model is:

```text
S1   ACCEPT / MODIFY / REJECT
...
S18  ACCEPT / MODIFY / REJECT
```

---

# S1 — Ratify `PhysicalSystemSpec` as descriptive scientific semantics

### Preliminary decision: **ACCEPT**

Use a versioned `PhysicalSystemSpec` as a descriptive/provenance artifact for the physical system represented by a Challenge.

It may describe:

- system identity/class;
- variables/fields/parameters;
- governing relations;
- conditions/domains;
- assumptions/exclusions;
- numerical/reference provenance;
- reconciliation issues.

It must **not** define score weights, gates, thresholds, official seeds, hidden draws, or product qualification.

### Why

The Burgers and Poisson simulations showed that Challenge labels and prose alone are insufficient to preserve precise physical identity and source conflicts.

### Current/future scope

- Current: design-only artifact; optional A3 binding path already exists.
- Future: candidate authoring/traceability input for additional Challenges.

### Affected files/specs if accepted

- `Design_Specs/Physical_System_Representation.md`
- `Design_Specs/physical_system_specs/*`
- future Challenge authoring specs

### Confidence

**Very high.**

---

# S2 — Keep physical semantics separate from measurement and scoring authority

### Preliminary decision: **ACCEPT**

Ratify the authority chain:

```text
physical property / relation
        ↓
MeasurementContract
        ↓
Validation Dossier evidence/calibration
        ↓
Score Pack use
        ↓
ScoreEngine
```

A governing equation does not itself define a score-bearing residual, discretization, normalization, aggregation, threshold, or weight.

### Why

Burgers exposed a concrete failure: the current `residual_diagnostic` omits `d_t(u)` and is therefore not the full PDE residual.

### Current/future scope

- Current: principle only; do not add score authority.
- Future: standalone versioned MeasurementContract artifacts where useful.

### Affected files/specs if accepted

- future measurement/evaluation primitive spec
- `Scoring.md` references only when production integration occurs
- Validation Dossier authoring flow

### Confidence

**Very high.**

---

# S3 — Introduce `MeasurementContract` as a first-class future object

### Preliminary decision: **ACCEPT**

A future `MeasurementContract` should bind at least:

- semantic source/reference;
- required observables;
- numerical method;
- discretization/sampling;
- normalization/aggregation;
- precision/reference floor;
- applicability;
- limitations;
- implementation version;
- evidence role.

### Guardrail

The object defines **what is measured**, not whether the measurement is scientifically adequate or score-bearing.

### Why

Gate 3/4 showed that measurement identity changes with numerical implementation and output observability.

### Current/future scope

Post-P0 authoring/evaluation architecture only.

### Affected files/specs if accepted

- future `MeasurementContract` design spec
- Challenge authoring / Validation Dossier integration

### Confidence

**Very high.**

---

# S4 — Ratify `EvidenceRequirement` as pre-evidence, not evidence

### Preliminary decision: **ACCEPT**

Use a typed object for known-but-not-yet-completed scientific evidence work.

Suggested states:

```text
PLANNED
RUNNING
SATISFIED
FAILED
WAIVED_WITH_RATIONALE
```

### Why

Challenge Compiler simulation showed a recurring ambiguity between:

- unresolved scientific definitions;
- known evidence work that has not been run;
- completed evidence.

### Guardrail

Generated dossier scaffolding or an `EvidenceRequirement` must never masquerade as completed evidence.

### Current/future scope

Future authoring workflow only.

### Confidence

**High.**

---

# S5 — Challenge Compiler may author, but never certify

### Preliminary decision: **ACCEPT**

A future Challenge Compiler should output a `ChallengeAuthoringPackage`, not a LIVE Challenge, scientific certificate, or Score Pack.

It may propose:

- semantic imports;
- candidate measurements;
- required outputs;
- stress categories;
- evidence requirements;
- dossier skeleton;
- unresolved decisions;
- disclosure review.

### Guardrail

> **Generated scientific documentation must not bypass scientist review, dossier qualification, registry authority, or scoring governance.**

### Current/future scope

Later authoring/product capability; no P0 change.

### Confidence

**Very high.**

---

# S6 — Ratify prospective-decision lift as the standard for `physics intelligence`

### Preliminary decision: **ACCEPT**

Define physics intelligence as:

> **Provenance-bearing knowledge about how model-construction interventions interact with physical structure, regime, measurement, and engineering context, demonstrated by improved prospective scientific or engineering decisions rather than retrospective narrative alone.**

### Required evidence direction

Landscape should eventually be tested on held-out/prospective tasks such as:

- transfer prediction;
- experiment allocation;
- qualification-failure prediction;
- search efficiency;
- decision economics.

### Guardrail

A knowledge graph, ontology, embedding, or large card corpus is not automatically physics intelligence.

### Current/future scope

Landscape research criterion; no P0 runtime effect.

### Confidence

**Very high.**

---

# S7 — Introduce `ContextFeatureSet` instead of bloating PhysicalSystemSpec

### Preliminary decision: **ACCEPT**

Keep `PhysicalSystemSpec` small and descriptive. Richer Landscape features should be derived into a separate versioned `ContextFeatureSet` with provenance.

Feature provenance should distinguish:

```text
authored
 derived
 learned
```

and support applicability/uncertainty where needed.

### Why

Landscape simulation showed that ontology labels, derived dimensionless groups, and learned representations have different epistemic status.

### Current/future scope

Future Landscape research only.

### Confidence

**High.**

---

# S8 — Preserve selection provenance and censoring in experimental memory

### Preliminary decision: **ACCEPT**

Future experimental records should preserve, where available:

```text
selection provenance:
  performance search
  Port C registered experiment
  reproduction
  sponsored study
  other

result state:
  completed-valid
  scientific failure
  training/construction failure
  censored/no-result
  infrastructure failure
```

### Why

Search history is adaptively selected. Missingness and failures are intervention-dependent and can bias predictive/causal inference.

### Guardrail

Infrastructure failure must never be interpreted as negative scientific evidence.

### Current/future scope

Evidence/Landscape schema evolution; no P0 scoring change.

### Confidence

**Very high.**

---

# S9 — Ratify `ModelConstructionStrategy` as the long-term strategy superclass

### Preliminary decision: **ACCEPT**

Long-term Carbon should generalize from `TrainingStrategy` to `ModelConstructionStrategy`.

A future construction strategy may specify:

- learned operator training;
- hybrid mechanistic/learned construction;
- reduced model;
- learned closure;
- symbolic/numeric approximation;
- classical surrogate;
- component replacement in a composed system.

### Guardrail

**Do not change current Strategy v1.0.** Neural training remains the P0 implementation.

### Why

Gates 6 and 8 showed that the entire Carbon loop remains coherent for non-neural model construction.

### Affected files/specs if accepted later

- future Strategy schema version
- miner execution contract
- ConstructionPolicy

### Confidence

**Very high.**

---

# S10 — Introduce `CandidateOutputContract` for cross-family comparability

### Preliminary decision: **ACCEPT**

Mixed-family Challenges should compare candidates through a common registered observable/query interface.

A future `CandidateOutputContract` may define:

- required inputs;
- required outputs;
- query semantics;
- resolution/geometry conventions;
- optional outputs;
- runtime interface version;
- answerability/coverage semantics where relevant.

### Guardrail

Architecture-specific internal observability must not silently create a scoring advantage. Mandatory score-bearing measurements should be observable from the common required contract unless richer outputs are required from every candidate.

### Current/future scope

Hybrid/mixed-family Challenge work only.

### Confidence

**Very high.**

---

# S11 — Ratify `ReconstructionProtocol`: producer-independent reconstruction is the invariant

### Preliminary decision: **ACCEPT**

Generalize the verification principle:

> **The producer proposes a reproducible construction method; an independent evaluator reconstructs the candidate before the official exam.**

Examples:

- neural model → fresh retraining;
- ROM → rebuild basis/operator;
- symbolic reduction → rerun reduction/transformation;
- adaptive solver → reconstruct/configure executable;
- portfolio → rebuild models + router.

### Guardrail

Fresh retraining remains mandatory for current neural Challenges.

### Current/future scope

Architecture principle now; future execution abstraction later.

### Confidence

**Very high.**

---

# S12 — Separate scientific performance, computational admissibility, and product utility

### Preliminary decision: **ACCEPT**

Do not silently fold latency, memory, training cost, information value, novelty, or commercial value into the physics score.

Future acceleration Challenges may distinguish:

```text
scientific admissibility
computational admissibility
ranking among admissible candidates
product/engineering decision utility
```

### Why

A high-fidelity solver can be scientifically perfect but fail an acceleration task's resource constraint. A slower model may still be the better product for a high-consequence application.

### Guardrail

Any resource criterion that becomes score-bearing must be explicitly registered and governed.

### Current/future scope

Future mixed-family Challenge design and product qualification.

### Confidence

**Very high.**

---

# S13 — Ratify technology neutrality / no model-family ideology

### Preliminary decision: **ACCEPT**

Carbon should not reward a method because it is neural, symbolic, mechanistic, hybrid, interpretable, or fashionable.

> **Model class is a hypothesis. Registered external evidence is the judge.**

If a ROM, classical surrogate, symbolic reduction, or analytical approximation wins under the registered objective and admissibility constraints, Carbon should accept that outcome.

### Guardrail

Interpretability or explicit physics structure does not expand a qualification envelope without evidence.

### Current/future scope

Scientific constitution now; implementation remains P0-neural.

### Confidence

**Very high.**

---

# S14 — Ratify composition architecture for future multiphysics systems

### Preliminary decision: **ACCEPT FOR FUTURE v0.2+; DEFER EXACT SCHEMA**

Future composition-capable physical semantics require:

- scoped symbol identity;
- explicit alias/shared-quantity relationships;
- first-class coupling/interface semantics;
- unit/dimension or explicit nondimensionalization capability;
- multi-source/interface/system measurements;
- assembled composition identity.

### Suggested object

`CouplingContract` for participant/interface physical relations.

### Guardrail

Do not retrofit these concepts into PhysicalSystemSpec v0.1 merely to anticipate future systems.

### Why

The multiphysics crash test showed flattened names and implicit coupling are insufficient.

### Current/future scope

Deferred until actual coupled Challenge implementation.

### Confidence

**Very high on the need; medium/high on final schema.**

---

# S15 — Component qualification does not automatically compose

### Preliminary decision: **ACCEPT**

Ratify:

```text
qualified component A
+
qualified component B
!=
qualified assembled system A∘B
```

Coupled systems require evidence about interfaces, numerical coupling, joint operating envelope, and assembled behavior.

### Future concept

A `CompatibilityEnvelope` may be useful, but its exact artifact shape remains deferred.

### Current/future scope

Product/multiphysics qualification principle only.

### Confidence

**Very high.**

---

# S16 — Answerability, abstention, routing, and escalation are prospective task semantics

### Preliminary decision: **ACCEPT**

A Challenge/product must state whether a candidate is required to answer every in-envelope query or may abstain/escalate.

A future product may legitimately be:

```text
router
  -> fast model A
  -> fast model B
  -> specialist C
  -> high-fidelity escalation
```

### Guardrail

A candidate cannot selectively refuse hard official cases unless the registered task contract permits it.

### Product implication

The strongest product may be a qualified **system/portfolio**, not one universal model.

### Current/future scope

Product qualification / future CandidateOutputContract.

### Confidence

**High.**

---

# S17 — Agentic Exploration Zone belongs on the hypothesis-generation side only

### Preliminary decision: **ACCEPT**

The Scientific Canon may serve as a bounded Agentic Exploration Zone together with Challenge semantics and permitted Landscape evidence.

Agents may use it to propose:

- parameter changes;
- training strategies;
- architectures/compositions;
- data/truth-use policies;
- new construction methods;
- candidate measurements or experiments.

### Constitutional boundary

> **Canon informs hypotheses. Carbon experiments adjudicate them.**

The canon is part of the explorer, never the judge.

### Current/future scope

Scientific/research architecture now; operational agent integration later.

### Confidence

**Very high.**

---

# S18 — Permit future submitted construction algorithms only through a hardened, separate construction domain

### Preliminary decision: **ACCEPT AS LONG-TERM RESEARCH DIRECTION; DO NOT IMPLEMENT NOW**

A future Challenge may permit an agent/miner to submit an executable `ConstructionProgram` that Carbon did not preimplement.

Required architectural invariants:

1. **Construction and official evaluation are separate security domains.**
2. Construction receives only authorized inputs/truth access.
3. Official exam seeds/realizations/private validator state never enter the construction domain.
4. Only sanitized/content-addressed candidate artifacts cross into evaluation.
5. Resource/truth-query access is prospectively governed.
6. Dependencies/toolchains are pinned or tiered by policy.
7. Nondeterminism is governed by a declared randomness contract.
8. Inner candidate-selection/search policy is part of the intervention provenance.
9. The method producer cannot define the official measurement that proves its own success.
10. Novelty is not a primary performance score term.

### Future compounding object

A reproduced novel method may graduate into an evidence-bearing `ConstructionMethodRecord` / Construction Method Library.

### Ship criterion before enabling

Do not implement until Carbon has:

- proven lean subnet operation;
- hardened A4-style secrecy;
- mature isolated execution;
- artifact sanitization;
- dependency/environment provenance;
- resource accounting;
- security/abuse review;
- evidence that expanded search freedom justifies the attack surface.

### Current/future scope

Long-term research only; explicitly out of P0.

### Confidence

**High on architecture; deliberately low commitment on implementation timing/technology.**

---

# Consolidated post-simulation review table

| ID | Decision | Preliminary verdict | Confidence | Scope if accepted |
|---|---|---|---:|---|
| S1 | PhysicalSystemSpec descriptive semantics | ACCEPT | Very high | Post-P0 authoring |
| S2 | Separate semantics / measurement / score authority | ACCEPT | Very high | Constitution |
| S3 | MeasurementContract | ACCEPT | Very high | Post-P0 |
| S4 | EvidenceRequirement | ACCEPT | High | Authoring workflow |
| S5 | Challenge Compiler authors, never certifies | ACCEPT | Very high | Later product/tooling |
| S6 | Prospective decision lift defines physics intelligence | ACCEPT | Very high | Landscape research |
| S7 | ContextFeatureSet separate from PhysicalSystemSpec | ACCEPT | High | Landscape |
| S8 | Selection provenance + censoring | ACCEPT | Very high | Evidence/Landscape |
| S9 | ModelConstructionStrategy superclass | ACCEPT | Very high | Future strategy schema |
| S10 | CandidateOutputContract | ACCEPT | Very high | Mixed-family Challenges |
| S11 | ReconstructionProtocol / producer-independent reconstruction | ACCEPT | Very high | Future execution abstraction |
| S12 | Separate performance / compute / product utility | ACCEPT | Very high | Future Challenge/product |
| S13 | Technology neutrality | ACCEPT | Very high | Constitution |
| S14 | Composition semantics / CouplingContract | ACCEPT FUTURE | Very high | v0.2+ coupled systems |
| S15 | Qualification is non-compositional | ACCEPT | Very high | Product/multiphysics |
| S16 | Answerability / routing / escalation | ACCEPT | High | Product/future Challenge |
| S17 | Agentic Exploration Zone is generative only | ACCEPT | Very high | Research architecture |
| S18 | Sandboxed submitted ConstructionProgram | ACCEPT LONG-TERM | High | Later research capability |

---

# Decisions still intentionally deferred after Gates 1–10

Tech/science lead acceptance of S1–S18 would **not** settle:

- final PhysicalSystemSpec v0.2 grammar;
- final MeasurementContract serialization;
- universal geometry/topology schema;
- universal connector/coupling ontology;
- exact units package or unit system;
- DAE/index/event/stochastic semantics;
- exact CompatibilityEnvelope schema;
- exact portfolio/router qualification artifact;
- production Challenge Compiler UX/API;
- actual Landscape representation/model family;
- exact causal-promotion thresholds;
- exact submitted-code sandbox technology;
- allowable dependency ecosystem;
- arbitrary-code Challenge timing;
- economic pricing for truth-query budgets;
- any change to current P0 score weights or gates;
- any change to current Strategy v1.0 wire contract;
- any claim that H16/H19–H27 have been empirically demonstrated.

---

# Recommended review order

To minimize dependency confusion, review in this sequence:

### Group A — scientific authority and authoring

```text
S1  PhysicalSystemSpec
S2  authority separation
S3  MeasurementContract
S4  EvidenceRequirement
S5  Challenge Compiler boundary
```

### Group B — evidence and intelligence

```text
S6  physics-intelligence definition
S7  ContextFeatureSet
S8  selection/censoring provenance
```

### Group C — long-term search abstraction

```text
S9   ModelConstructionStrategy
S10  CandidateOutputContract
S11  ReconstructionProtocol
S12  performance/compute/product separation
S13  technology neutrality
```

### Group D — composition and product

```text
S14  coupled-system semantics
S15  non-compositional qualification
S16  answerability/routing/escalation
```

### Group E — agentic research ceiling

```text
S17  Agentic Exploration Zone
S18  submitted ConstructionProgram capability
```

---

# Tech/science lead sign-off block

```text
S1   ACCEPT / MODIFY / REJECT   Notes:
S2   ACCEPT / MODIFY / REJECT   Notes:
S3   ACCEPT / MODIFY / REJECT   Notes:
S4   ACCEPT / MODIFY / REJECT   Notes:
S5   ACCEPT / MODIFY / REJECT   Notes:
S6   ACCEPT / MODIFY / REJECT   Notes:
S7   ACCEPT / MODIFY / REJECT   Notes:
S8   ACCEPT / MODIFY / REJECT   Notes:
S9   ACCEPT / MODIFY / REJECT   Notes:
S10  ACCEPT / MODIFY / REJECT   Notes:
S11  ACCEPT / MODIFY / REJECT   Notes:
S12  ACCEPT / MODIFY / REJECT   Notes:
S13  ACCEPT / MODIFY / REJECT   Notes:
S14  ACCEPT / MODIFY / REJECT   Notes:
S15  ACCEPT / MODIFY / REJECT   Notes:
S16  ACCEPT / MODIFY / REJECT   Notes:
S17  ACCEPT / MODIFY / REJECT   Notes:
S18  ACCEPT / MODIFY / REJECT   Notes:
```

---

# Owner preliminary conclusion

The simulation supports a broad long-term architecture without requiring a broad launch implementation.

The recommended posture is:

> **Keep P0 narrow. Ratify the authority boundaries now. Preserve the semantic/evidence hooks that are cheap today. Expand model-construction freedom only after independent reconstruction, measurement discipline, evidence quality, and execution isolation are mature enough to support it.**

If the tech/science lead accepts these decisions, the next step is to convert accepted S-items into targeted normative-spec edits and explicit future build tickets rather than allowing the design branch to become de facto protocol authority.
