# Symbolic-Numeric Integration Implementation Map

**Status:** planning/context only — does not override `Design_Specs/Build_Out.md` sequencing.  
**Design draft:** `Design_Specs/Physical_System_Representation.md`.  
**Design decisions:** `docs/context/SYMBOLIC_NUMERIC_INTEGRATION_DECISIONS.md`.

---

## Goal

Integrate structured physical semantics into Carbon without expanding P0 scope or creating a parallel scientific authority. The implementation is split into **P0-compatible provenance hooks** and **post-P0 authoring / Landscape / model-class extensions**.

---

# 1. P0-compatible hooks

These hooks should be folded into existing Wave A/B/C work only when the relevant owner is touched. They do not require a symbolic runtime.

## SN-A1 — Reserve physical-system identity on Challenge provenance

**Natural owner:** A3 Challenge registry / A6 Card store.  
**Semantic owner:** proposed `Physical_System_Representation.md`; Challenge registry remains governed by existing specs.

Reserve optional support for:

```text
physical_system_spec_id
physical_system_spec_version
physical_system_spec_hash
```

Acceptance direction:

- optional / absent is valid in P0;
- identity is immutable/versioned when present;
- no official seed/draw information enters the object;
- no scoring behavior depends on the field;
- old Challenges remain readable without it.

## SN-A2 — Preserve physical-system identity on official evidence

**Natural owner:** A6 Card store / Model Card provenance.

When a Challenge carries a physical-system identity, preserve the same identity on internal scientific evidence so future Landscape ingestion can join experiments to physical context.

Acceptance direction:

- provenance only;
- disclosure remains allow-listed;
- no new miner-visible information is implied;
- no historical backfill is invented without an explicit migration decision.

## SN-A3 — Burgers authoring-only semantic prototype

**Natural owners:** SciML / generator authoring; no validator dependency.

Create a non-runtime `PhysicalSystemSpec` prototype for the existing Burgers P0 Challenge.

Prototype should capture, as scientifically approved inputs:

- state / independent variables;
- viscosity parameter;
- governing relation;
- initial/boundary-condition semantics;
- assumptions;
- current physical-envelope metadata;
- optional derived regime features.

Acceptance direction:

- manually inspectable;
- content-addressable/versionable;
- links to existing Challenge/generator/dossier identities;
- produces no score and changes no runtime behavior;
- does not expose official realized draws.

**Do not:** make P0 depend on ModelingToolkit, Symbolics.jl, Modelica, or any symbolic engine.

---

# 2. Post-P0 scientific-authoring implementation

## SN-S1 — Canonical `PhysicalSystemSpec` schema

Define and ratify a serialization-neutral schema and validation rules.

Required properties:

- representation-agnostic;
- explicit assumptions;
- explicit missing/unknown/not-applicable semantics;
- version/content identity;
- no automatic score/gate semantics;
- extensible scientific feature namespace.

## SN-S2 — Reference ModelingToolkit adapter

Build an authoring adapter that can map supported ModelingToolkit systems into the canonical representation.

Requirements:

- adapter output is reviewable before registration;
- unsupported semantics fail explicitly rather than being fabricated;
- no Julia dependency in miner/validator runtime merely because the adapter exists;
- round-trip semantic equivalence claims are scoped and tested, not assumed.

Possible later adapters: Modelica, SBML, CellML, SymPy, manual/JSON authoring.

## SN-S3 — Physics Evaluation Primitive Library

Create reusable candidate evaluators for authoring / dossier workflows.

Primitive families may include:

- governing-relation residuals;
- conservation/invariant diagnostics;
- admissibility diagnostics;
- boundary/initial-condition diagnostics;
- dimensional checks;
- physical regime feature extraction.

Required controls:

- primitive definition is versioned;
- numerical implementation/discretization is explicit;
- normalization/aggregation is explicit;
- no threshold/gate status is invented by code;
- scientific qualification links the primitive to a Challenge/Score Pack.

## SN-S4 — Dossier traceability integration

Permit dossier artifacts to trace:

```text
PhysicalSystemSpec relation/assumption
  → reference implementation
  → validation evidence
  → evaluation primitive
  → human-qualified metric / gate / threshold
```

This is provenance and scientific traceability, not automatic qualification.

---

# 3. Landscape implementation

## SN-L1 — Physical-context FeatureStore

**Target:** after PI-L0 evidence ingestion is stable.

Add qualified physical context features to Landscape-private evidence.

Potential initial feature classes:

- system family;
- equation/relation family labels;
- nonlinearity class;
- transport/diffusion/stiffness features;
- boundary topology;
- human-qualified dimensionless groups;
- known physical phenomena / regime tags.

Prefer explicit human-qualified features before symbolic-expression embeddings.

## SN-L2 — Physical graph linkage

Represent a physical-context graph separately from the experimental graph initially.

```text
Experimental:
strategy → execution → outcome → qualification

Physical:
system → structure/components → regime features → constraints/invariants
```

Link evidence through immutable physical-system identity/version.

## SN-L3 — H16 transfer-prediction test

Run a prospective comparison:

```text
baseline:
strategy/intervention + Challenge ID + ordinary metadata

vs

physical-context model:
strategy/intervention + qualified physical features + ordinary metadata
```

Primary question: does structured physical context improve prediction of intervention transfer to future/held-out Challenges?

No production Port A/B/C/D dependency should be created before measurable lift exists.

## SN-L4 — Physical-context Port C experiment design

Only after H16-style prospective value is demonstrated, allow physical context to inform information-experiment proposals for:

- transfer tests;
- regime coverage;
- competing-mechanism discrimination;
- underrepresented physical structures.

Port C remains proposal-only until governance registration.

---

# 4. Product / qualification implementation

## SN-P1 — Physical-system identity in qualification evidence

When relevant, allow Product Candidate Model Cards / Product Battery Records / Qualification Records to bind the exact `PhysicalSystemSpec` identity/version.

No physical-system reference expands context of use automatically.

## SN-P2 — Regime-aware answerability inputs

Where human-qualified, derived physical regime features may become inputs to context-of-use / escalation logic.

Examples may include dimensionless groups or coupled-state conditions that describe regime membership more meaningfully than independent raw parameter ranges.

Required controls:

- qualified rule is explicit/versioned;
- no self-certification by model uncertainty;
- no automatically generated regime boundaries;
- lifecycle evidence does not silently mutate old qualification claims.

---

# 5. Later model-class expansion

These items are **not** P0 or immediate post-P0 requirements.

## SN-M1 — `FastPhysicalModel` conceptual superclass

Generalize product/evidence terminology so Carbon can eventually qualify fast physical artifacts beyond neural operators without rewriting the trust model.

## SN-M2 — `ModelConstructionStrategy`

For designated future Challenges, generalize a training recipe to a construction hypothesis that may specify:

- physical scaffold;
- learned component location/type;
- architecture;
- losses;
- curriculum;
- solver coupling;
- optimization;
- resource budget.

## SN-M3 — Hybrid mechanistic/learned Challenge class

Permit controlled comparison of black-box surrogates versus hybrid mechanistic/learned models under the same external scientific contract.

## SN-M4 — Coupled/compositional Challenge authoring

Use structured physical composition to support progressively coupled scientific regimes after simpler Challenge classes are qualified.

## SN-M5 — Equation / closure discovery branch

Treat equation, constitutive-law, or closure discovery as a separate future Challenge family with its own epistemic and validation contract. Do not fold it into ordinary surrogate search by default.

---

# 6. Research hypotheses

- **H16:** qualified structured physical context improves cross-Challenge intervention-transfer prediction.
- **H17:** structured physical authoring and reusable evaluation primitives reduce Challenge-authoring time/error without weakening scientific validity.
- **H18:** hybrid mechanistic/learned search improves qualification outcomes or decision economics in appropriate regimes.
- **H19:** physical-context-aware experiment allocation improves transferable decision value relative to ordinary experiment-history baselines.

These are research hypotheses, not implementation acceptance facts.

---

# 7. Security / scientific invariants

1. No official seed/draw leakage through physical metadata.
2. No automatic gate/threshold creation from symbolic structure.
3. No symbolic model treated as proof of real-world physical validity.
4. No score changes without `Scoring.md` revision / authorized Score Pack semantics.
5. No Challenge state transition from adapter-generated judgments.
6. No Landscape causal upgrade from physical similarity alone.
7. No qualification expansion from symbolic/regime similarity alone.
8. No mandatory symbolic framework dependency in P0 runtime.
9. No silent reinterpretation of historical evidence after `PhysicalSystemSpec` revision.
10. No fabricated scientific metadata when source representations are incomplete.

---

# 8. Suggested sequencing

Current `Build_Out.md` remains authoritative.

P0-compatible integration only:

```text
A3 registry       → SN-A1 optional identity hooks
A6 card store     → SN-A2 evidence provenance hook
SciML authoring   → SN-A3 Burgers semantic prototype (non-runtime)
A12 invariants    → verify identity cannot affect score or leak exam state
```

Post-P0:

```text
SN-S1 → SN-S2 → SN-S3 → SN-S4
             ↓
PI-L0 stable → SN-L1 → SN-L2 → SN-L3
                              ↓ if evidence supports
                              SN-L4

Specialist product work → SN-P1 → SN-P2

Later scientific expansion → SN-M1 → SN-M2 → SN-M3/M4
                                      ↘ optional SN-M5
```

---

# 9. Stop conditions

Pause or simplify this integration if:

- the Burgers prototype duplicates existing metadata without improving traceability;
- a canonical schema requires framework-specific concepts to remain usable;
- authoring tools begin implicitly inventing scientific judgments;
- P0 implementation becomes dependent on post-P0 symbolic machinery;
- physical features do not improve Landscape transfer/decision performance prospectively;
- symbolic abstraction creates more ambiguity than scientific structure.

The design should earn its complexity empirically.
