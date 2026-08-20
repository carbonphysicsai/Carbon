# Symbolic-Numeric Integration Design Decisions

**Status:** DESIGN INTEGRATION — owner-directed exploration initiated 2026-08-20. Exact schema/runtime changes remain reviewable; no P0 scoring or execution change is ratified by this file.  
**Primary draft spec:** `Design_Specs/Physical_System_Representation.md`.

---

## Decision summary

The symbolic-numeric SciML review identifies a missing physical semantic layer in Carbon's long-term physics-intelligence architecture. The integration is additive: it does not replace the Challenge, generator, Score Pack, Validation Dossier, Landscape ports, or Specialist Bank.

### SN-D1 — Carbon should be representation-aware, not framework-bound

Carbon should support a canonical `PhysicalSystemSpec` abstraction that may be populated by symbolic-numeric ecosystems or manual scientific authoring. ModelingToolkit is a candidate reference adapter, not a protocol dependency or scientific authority.

### SN-D2 — Physical structure is descriptive, not automatically authoritative

A `PhysicalSystemSpec` may record equations, variables, parameters, constraints, assumptions, invariants, and regime features. It cannot create authoritative gates, thresholds, scores, or qualification claims by itself.

### SN-D3 — Scientific authority remains where it already lives

- Score mathematics remain owned by `Scoring.md`.
- Generator science remains owned by generator/dossier/envelope specifications.
- Landscape remains evidence-learning, not scientific authority.
- Product qualification remains owned by the Specialist Bank/product qualification path.

### SN-D4 — P0 should only receive compatibility hooks

The Burgers vertical slice should not gain a symbolic runtime dependency. P0-compatible work is limited to reserving physical-system identity/provenance hooks and optionally constructing a non-runtime Burgers semantic prototype.

### SN-D5 — Reusable evaluation primitives are a Challenge-authoring capability

Structured physical metadata may later support candidate residual, conservation/invariant, admissibility, boundary/initial consistency, dimensional, and regime-feature primitives. Every score-bearing use still requires explicit scientific qualification.

### SN-D6 — Structured physical context is a Landscape transfer substrate

Long-term Landscape evidence should be able to connect modeling interventions and outcomes to identifiable physical structure/regimes rather than only Challenge IDs. Physical similarity does not itself establish causal transfer.

### SN-D7 — Neural operators are the first model class, not the permanent ontology

Carbon should preserve a path from `TrainingStrategy` toward future Challenge-specific `ModelConstructionStrategy` objects and from learned operators toward a broader `FastPhysicalModel` concept. Hybrid mechanistic/learned models are a later model class, not a P0 requirement.

### SN-D8 — Equation discovery is a separate epistemic regime

Symbolic regression, closure discovery, and governing-equation discovery may become future Challenge classes, but they are not folded into the initial surrogate-discovery architecture because the object being discovered would overlap with the scientific model used to define evaluation.

---

## Ratification boundaries

This integration does **not** ratify:

- a final serialization format;
- a final physical ontology;
- ModelingToolkit as mandatory infrastructure;
- automatic derivation of gates or thresholds;
- H16-H19 as true;
- hybrid strategy classes in P0;
- equation-discovery Challenges;
- any change to `S_combined`, emissions, or current Challenge thresholds.

---

## New invariants

> **The symbolic model does not certify the physical model.**

> **Derived evaluation primitives remain candidates until scientifically qualified.**

> **Physical metadata cannot silently mutate a registered scientific contract.**

> **Symbolic equivalence does not imply numerical or operational equivalence.**

> **Carbon owns the semantic contract, not the modeling language.**

---

## KEEP / WRAP / REPAIR / REPLACE disposition

- **KEEP:** all current P0 scoring, generator, hidden-evaluation, strategy, validator, evidence, Landscape-port, and product-separation invariants.
- **WRAP:** Challenge identity/evidence provenance with optional physical-system identity.
- **REPAIR/EXTEND:** long-term Challenge semantics, reusable scientific authoring primitives, Landscape physical-context features, qualification physical-context provenance.
- **REPLACE:** none.

---

## Strategic consequence

The long-term Carbon research object becomes broader than a neural-network training recipe while remaining narrower than a general-purpose symbolic modeling platform:

> **Carbon is an experimental system for learning which model-construction interventions work for identifiable physical structures, regimes, and engineering contexts.**

For near-term public communication, continue to describe the system through fast learned physics models and independent physics exams. The broader abstraction is architecture future-proofing, not a requirement that stage audiences learn symbolic-numeric modeling.
