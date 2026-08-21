# Symbolic-Numeric Design Simulation — Gate 6: Hybrid Model-Construction Search

**Status:** design-forward simulation; no Strategy v1.0, scoring, miner, validator, or product runtime changes.  
**Objective:** Remove the assumption that every competitor submits a recipe for one neural-operator family and test whether Carbon can compare fundamentally different fast physical-model construction methods under one scientific contract.

## Existing Carbon boundary preserved

Current ratified Strategy v1.0 remains intentionally small: `schema_version`, `challenge_id`, scalar `backbone`, and `parameters`. `Strategy_Schema.md` explicitly says its broader 1.1 knob catalog is a proposal, not the current wire contract. This gate therefore does **not** retrofit hybrid construction into v1.0.

## Simulated Challenge

Assume a future physical system with a known mechanistic scaffold and an expensive/unresolved closure or correction term. Competitors may submit one of three construction families:

```text
A. learned operator
   input state/parameters -> learned fast map

B. mechanistic + learned closure
   known physical scaffold + learned unresolved term

C. reduced physical model + learned correction
   reduced numerical model + learned discrepancy/correction
```

All are intended to serve the **same registered engineering/modeling task** and are examined against the same external physical-system envelope.

## Immediate result

`TrainingStrategy` is too narrow as the long-term scientific abstraction.

The correct future superclass is provisionally:

```text
ModelConstructionStrategy {
  strategy_identity
  challenge_id
  construction_family
  artifact_graph
  trainable_components[]
  fixed_components[]
  training_procedure
  execution_contract
  candidate_output_contract
  resource_request
  provenance
}
```

A neural-operator training strategy becomes one subtype, not the protocol ontology.

**Important:** this is a future schema concept. Strategy v1.0 remains unchanged.

## Artifact graph discovery

Hybrid strategies are not naturally represented by a single `backbone` string. They contain a graph of components and interfaces:

```text
physical scaffold
      ↓
learned closure
      ↓
solver/integrator
      ↓
observable output
```

or:

```text
reduced model ──┐
                ├─> correction/composition -> output
learned model ──┘
```

The strategy therefore needs to identify **what is fixed, what is learned, what is transformed, and how components compose**.

This graph is not the same as `PhysicalSystemSpec`: one describes the physical problem; the other describes the candidate computational construction.

## Fair-comparison simulation

### Case A — same output contract, different internals
All three candidates return the same required observable on the same query interface.

Carbon can compare them on external outcomes using the same qualified MeasurementContracts.

**Finding:** scientific comparability should be anchored primarily in the registered **candidate output / context-of-use contract**, not architecture homogeneity.

### Case B — hybrid model exposes richer internal state
The mechanistic+learned candidate exposes intermediate states that allow a full PDE residual; the pure learned operator returns only final output.

If Carbon gives the hybrid extra score opportunities because it exposes more internals, comparison becomes architecture-dependent.

**Decision:** mandatory score-bearing measurements for a mixed-family Challenge must be observable from the **common required output contract**, unless the Challenge explicitly requires the richer interface from every candidate. Architecture-specific diagnostics may exist as non-comparable evidence but cannot silently advantage one family.

### Case C — one family is slower but more reliable
A hybrid solver is 5x slower than a pure learned operator but has materially better physical robustness.

**Discovery:** one scalar scientific score may be insufficient for downstream engineering selection even if it remains appropriate for subnet emissions. Carbon needs to distinguish:

- scientific performance under the Challenge score;
- resource/cost profile;
- deployment decision utility.

Do not silently add latency/cost into `S_combined` unless Scoring governance deliberately changes it.

### Case D — one family uses much more training compute
A brute-force learned model consumes 20x the training budget and wins slightly.

**Decision:** validator resource ceilings define admissibility/fairness. Carbon should not infer scientific superiority from unrestricted resource expenditure. Resource use belongs in provenance and may support separate efficiency analyses or Challenge classes.

### Case E — mechanistic scaffold contains more prior knowledge
A hybrid strategy uses a domain-specific equation unavailable to a generic learned operator.

Is this 'unfair'?

**Decision:** if the Challenge permits that public scientific prior, using it is a legitimate modeling intervention. Carbon's job is not to equalize prior knowledge; it is to define the allowed construction space prospectively. Hidden/private priors require disclosure/governance analysis.

### Case F — candidate modifies the physical scaffold
A miner changes a supposedly fixed conservation equation to improve score.

**Decision:** fixed scientific components must be content-addressed/immutable under the strategy execution contract. Only declared trainable/replaceable components may vary.

### Case G — learned closure violates admissibility but final error is low
The overall model fits outputs while the closure itself becomes nonphysical.

**Discovery:** whether internal-component behavior matters depends on the engineering claim. If the closure is merely latent and only system-level behavior is claimed, internal plausibility may be diagnostic. If the closure itself is sold/interpreted as a physical relation, it requires its own measurement/qualification claim. Do not infer mechanistic validity from end-to-end accuracy.

### Case H — pure learned model outperforms hybrid model
Carbon must allow this outcome.

**Decision:** symbolic/mechanistic structure is not privileged in scoring merely because it is interpretable. Physics remains external authority; model class receives no ideology bonus.

### Case I — hybrid wins on one regime, learned operator on another
**Discovery:** the product decision may be a portfolio/routing problem rather than a universal winner. Carbon may eventually qualify different FastPhysicalModels for different contexts of use.

This reinforces bounded qualification rather than a single global model champion.

## Earned object: FastPhysicalModel

The output artifact should be generalized beyond neural networks:

```text
FastPhysicalModel {
  artifact_identity
  construction_strategy_ref
  physical_system_spec_ref
  candidate_output_contract
  component_graph_ref
  runtime_requirements
  evidence_refs[]
  qualification_refs[]
}
```

Possible subclasses/realizations:

- learned operator;
- hybrid mechanistic/learned model;
- learned closure coupled to solver;
- reduced-order model;
- learned correction/discrepancy model;
- future symbolic/reduced computational representation.

The superclass is defined by intended role + evidence, not implementation technology.

## Earned object: CandidateOutputContract

Gate 3 discovered observability. Mixed model classes make it essential.

```text
CandidateOutputContract {
  contract_id
  required_inputs
  required_outputs
  query semantics
  resolution/geometry conventions
  optional_outputs[]
  determinism/stochastic semantics?
  allowed state exposure
  runtime interface version
}
```

Score-bearing MeasurementContracts bind to outputs guaranteed by this common contract.

This separates:

- what the physical system is (`PhysicalSystemSpec`);
- how a candidate is constructed (`ModelConstructionStrategy`);
- what a candidate must expose (`CandidateOutputContract`);
- how Carbon measures it (`MeasurementContract`).

## Search-space governance

Hybrid search creates a larger attack and complexity surface. A future Challenge should therefore publish a versioned **ConstructionPolicy** defining allowed families/components/interfaces.

```text
ConstructionPolicy {
  allowed_construction_families
  fixed_component_refs[]
  replaceable_component_slots[]
  allowed_frameworks?
  resource_limits
  candidate_output_contract_ref
  security/execution restrictions
}
```

This is prospective governance, not a learned preference.

## Landscape implications

Intervention identity must become hierarchical. Landscape should be able to ask effects at several levels:

```text
construction family
  -> component placement
  -> architecture
  -> loss/curriculum
  -> optimizer/budget
```

A learned closure strategy is not meaningfully summarized only as `backbone=fno`.

However, hierarchy must not imply causality. Selection provenance and Port C experiments remain necessary.

## Product/qualification implications

A winning strategy still does not directly become a product. For hybrid artifacts, fresh retrain/rebuild may also need to reconstruct fixed + learned components under pinned versions.

Qualification binds the **assembled artifact graph**, not merely learned weights.

A change to:

- solver version;
- fixed mechanistic component;
- learned closure weights;
- composition/interface;
- runtime implementation;

may be qualification-relevant even when the model's public name is unchanged.

## New architecture discoveries

### D-045 — `TrainingStrategy` is a subtype; `ModelConstructionStrategy` is the long-term abstraction
**Class:** EXTEND.

Do not change Strategy v1.0 now. Future mixed-model Challenges need a construction-level strategy object.

### D-046 — Candidate computational structure needs an artifact/component graph distinct from physical-system semantics
**Class:** EXTEND.

Physical model identity and candidate implementation identity must not be conflated.

### D-047 — Cross-family comparability anchors on a common CandidateOutputContract
**Class:** EXTEND/HARDEN.

Mandatory score-bearing measurements must be observable from the common required interface unless richer outputs are required from every candidate.

### D-048 — Architecture-specific observability must not create hidden scoring advantage
**Class:** HARDEN.

Optional internal diagnostics can support research evidence, but mixed-family official scoring must preserve prospective comparability.

### D-049 — Scientific score, resource efficiency, and engineering decision utility are distinct values
**Class:** HARDEN/EXTEND.

Do not casually collapse compute/latency/cost into the physics score. Preserve separate evidence dimensions and let product/Challenge governance define use.

### D-050 — Mechanistic structure receives no automatic score privilege
**Class:** KEEP/HARDEN.

Carbon tests outcomes. Symbolic/hybrid approaches are hypotheses, not favored ideology.

### D-051 — Fixed versus trainable/replaceable component identity must be explicit
**Class:** EXTEND/HARDEN.

Hybrid strategies require content-addressed fixed components and declared modification slots.

### D-052 — End-to-end success does not validate an internal learned physical relation
**Class:** HARDEN.

If an internal closure/constitutive law is itself claimed as physical knowledge, it requires separate evidence/qualification.

### D-053 — The best model may be context-dependent; qualification can produce a portfolio rather than one champion
**Class:** EXTEND/HARDEN.

Different FastPhysicalModels may be qualified for different envelopes/use contexts; routing/escalation can be part of engineering value.

### D-054 — Qualification identity for hybrid models binds the assembled artifact graph
**Class:** HARDEN.

Weights alone are insufficient identity when solver/components/composition affect behavior.

### D-055 — Search-space freedom itself needs a versioned ConstructionPolicy
**Class:** EXTEND.

Allowed model-construction families and replaceable slots are Challenge governance, not implicit validator behavior.

## Scientific implication

Carbon's scientific search object broadens from:

> Which training recipe produces the best neural operator?

into:

> Which permitted model-construction intervention produces the best evidence-bounded fast physical model for this registered task?

That is a materially more durable abstraction.

## Commercial implication

This widens Carbon's potential market position without requiring a broader Summit pitch today. Carbon can eventually evaluate/search across whatever fast-model technology the ecosystem produces rather than betting the company on one architecture family.

It also strengthens the partner proposition: a customer can care about **decision performance and qualification**, while Carbon's competitive system explores multiple admissible implementation families underneath.

## Gate verdict

**PASS — THE LONG-TERM SEARCH ABSTRACTION BROADENS FROM TRAINING TO MODEL CONSTRUCTION.**

Do not modify current Strategy v1.0 or P0. Carry `ModelConstructionStrategy`, `FastPhysicalModel`, `CandidateOutputContract`, component-graph identity, and `ConstructionPolicy` into Gate 7 coupled/multiphysics crash testing.
