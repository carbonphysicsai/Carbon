# Carbon Physical System Representation

**Status:** DESIGN INTEGRATION DRAFT — non-runtime, non-scoring, pending review/ratification.  
**Purpose:** Add a representation-agnostic physical semantic layer that can support Challenge authoring, reusable evaluation primitives, Landscape transfer reasoning, and later product qualification without changing P0 scoring or execution semantics.  
**Does not override:** `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Landscape_Agent.md`, `Specialist_Bank.md`, or `Build_Out.md` sequencing.

---

## 1. Design objective

Carbon currently binds scientific meaning through a Challenge, generator, Score Pack, Validation Dossier, strategy schema, and protected evaluation contract. This is sufficient for P0. The long-term physics-intelligence architecture, however, benefits from a machine-readable representation of **what physical system a Challenge claims to represent**.

This specification introduces the conceptual object:

```text
PhysicalSystemSpec
```

A `PhysicalSystemSpec` is descriptive scientific metadata. It is **not** a score, a gate, a proof of scientific validity, or a runtime source of protocol truth.

The intended long-term relationship is:

```text
DOMAIN SCIENCE
      ↓
PhysicalSystemSpec
      ↓
Generator / reference realization
      ↓
Validation Dossier
      ↓
registered Challenge + Score Pack
      ↓
authoritative evaluation
```

---

## 2. Constitutional invariants

1. **The symbolic/structured model does not certify the physical model.**
2. **Derived evaluation primitives are candidates until scientifically qualified.**
3. **`PhysicalSystemSpec` cannot silently create or modify a gate, threshold, Score Pack, or `S_combined`.**
4. **Scientific validity remains owned by the qualified Challenge / dossier / governance path.**
5. **Symbolic equivalence does not imply numerical, statistical, or operational equivalence.**
6. **Carbon remains representation-agnostic.** ModelingToolkit, Modelica, SBML, CellML, SymPy, or manual authoring may be adapters; none is the protocol ontology by itself.
7. **Missing structure is preferable to fabricated structure.** Fields may be absent, unknown, assumption-bound, or not applicable.
8. **No new P0 runtime dependency is created by this spec.**
9. **No physical metadata may leak protected official realizations, hidden seed information, or reconstruction-sensitive exam state.**
10. **Historical records bind the exact `PhysicalSystemSpec` identity/version when one is present; later versions do not silently reinterpret old evidence.**

---

## 3. Challenge relationship

A future-compatible Challenge may reference:

```text
Challenge
├── ChallengeSpec
├── GeneratorPack
├── ScorePack
├── ValidationDossier
└── physical_system_spec_id   # optional initially
```

For P0 this identifier may be absent or used only in non-runtime provenance.

When present, it should identify an immutable/versioned `PhysicalSystemSpec` by content-addressable identity or another ratified immutable mechanism.

---

## 4. Minimum conceptual schema

The exact serialization is not ratified by this draft. The semantic fields below define the intended information classes.

```text
PhysicalSystemSpec {
  identity {
    physical_system_spec_id
    version
    content_hash
  }

  system_class
    # pde | ode | dae | algebraic | hybrid | other

  variables {
    independent_variables
    state_variables
    observed_variables
  }

  parameters {
    symbols
    units
    admissible_domains
  }

  governing_relations
  initial_conditions
  boundary_conditions

  constraints {
    algebraic_constraints
    admissibility_constraints
  }

  scientific_features {
    conserved_quantities
    known_invariants
    dimensionless_groups
    regime_features
  }

  assumptions
  provenance
  references
}
```

### 4.1 Field semantics

- **governing relations:** equations or structural relations used to describe the scientific model; they are not automatically authoritative gates.
- **units:** scientific metadata where available; dimensional consistency tooling may use them only under qualified rules.
- **admissible domains:** scientific parameter/state bounds, distinct from hidden official draws.
- **known invariants/conserved quantities:** candidate scientific structure requiring dossier/Challenge qualification before score-bearing use.
- **dimensionless groups/regime features:** human-qualified physical features that may support Challenge description, Landscape transfer analysis, and product-envelope semantics.
- **assumptions:** required because many physical relations and invariants only hold under specific conditions.

---

## 5. Representation adapters

Carbon should own the semantic contract, not a modeling language.

Potential adapters may include:

```text
ModelingToolkit ─┐
Modelica         ├──► PhysicalSystemSpec
SBML / CellML   ┤
SymPy            │
manual authoring ┘
```

An adapter may parse, map, or validate representable structure. It may not invent scientific claims or fill absent scientific metadata as production truth.

### 5.1 ModelingToolkit reference adapter

ModelingToolkit is a strong candidate reference adapter because it exposes structured variables, parameters, equations, hierarchical composition, and symbolic-numeric scientific models. Any adapter is an authoring/integration tool only; Carbon must remain usable without Julia or ModelingToolkit at runtime.

---

## 6. Physics Evaluation Primitive Library

A later Challenge-authoring layer may consume a `PhysicalSystemSpec` to propose reusable **candidate** evaluation primitives.

Potential primitive families:

### 6.1 Governing-relation residual

For a qualified relation:

```text
F(u, derivatives(u), parameters) = 0
```

an evaluator may compute a numerically defined residual. The discretization, normalization, aggregation, tolerance, and gate status remain separately qualified scientific choices.

### 6.2 Conservation / invariant checks

A declared quantity may produce candidate measurements of drift or violation. Whether the quantity is conserved under the registered boundary conditions and regime must be explicitly qualified.

### 6.3 Admissibility checks

Examples may include positivity or bounded-state requirements when scientifically appropriate.

### 6.4 Initial / boundary consistency

Candidate checks may evaluate consistency with registered conditions where meaningful.

### 6.5 Dimensional consistency

Units may support authoring-time or diagnostic checks. Dimensional consistency alone is not evidence of physical validity.

### 6.6 Regime feature extraction

Human-qualified physical features, including appropriate dimensionless groups, may be computed for scientific metadata and Landscape analysis.

**Invariant:** no primitive becomes score-bearing merely because it can be derived or computed.

---

## 7. Validation Dossier linkage

Where `PhysicalSystemSpec` is used, the Validation Dossier should eventually be able to trace:

```text
physical relation / assumption
      ↓
numerical reference implementation
      ↓
convergence / reference evidence
      ↓
candidate evaluation primitive
      ↓
human-qualified metric / threshold / gate
```

This is intended to improve scientific traceability, not automate scientific judgment.

---

## 8. Landscape integration

The long-term intervention-outcome record should be capable of conditioning evidence on structured physical context.

Current conceptual experiment:

```text
E = (H, C, X, Y, P)
```

Future-compatible extension:

```text
E = (H, C, Φ, X, Y, P)
```

where `Φ` references the applicable `PhysicalSystemSpec` or a qualified derived physical feature representation.

This enables Landscape to test whether knowledge transfers across scientifically identifiable regimes rather than relying only on Challenge IDs.

### 8.1 Two linked graphs

Prefer linked structures rather than one unbounded ontology initially:

```text
Experimental graph
strategy → execution → outcome → qualification

Physical graph
system family → relations/components → regime features → constraints/invariants
```

Evidence may link the two:

```text
training intervention
      ↓
scientific outcome
      ↓
under physical regime Φ
```

### 8.2 Epistemic constraint

Physical similarity does not establish intervention transfer. Transfer remains observed/predictive/causal-candidate/experimentally-supported according to the ratified Landscape type system.

---

## 9. Product / qualification integration

A future Qualification Record may bind the exact physical-system identity/version where scientifically useful:

```text
artifact identity
+ context of use
+ physical_system_spec_id
+ Product Battery evidence
+ qualification policy
+ provenance
```

This can improve traceability of the qualified physical regime, especially when raw parameter bounds alone do not fully describe regime membership.

`PhysicalSystemSpec` does not itself expand a qualified envelope or authorize runtime use.

---

## 10. Long-term model-class expansion

Neural operators remain Carbon's initial practical model class. The protocol should not make neural-network architecture a permanent conceptual boundary.

A later generic object may be:

```text
FastPhysicalModel
```

A `FastPhysicalModel` is a computational artifact intended to approximate, accelerate, or augment a more expensive physical model within a registered scientific context.

Potential future subclasses may include:

- learned operator;
- hybrid mechanistic/learned model;
- learned closure;
- reduced-order model;
- differentiable surrogate;
- other human-approved fast physical representations.

Likewise, `TrainingStrategy` may later generalize to `ModelConstructionStrategy` for registered Challenge classes that permit hybrid mechanistic/learned designs.

**Do not implement this generalization in P0 merely because this design anticipates it.**

---

## 11. Explicitly out of scope for initial integration

- equation discovery as core P0 behavior;
- symbolic regression as an official Challenge class;
- automated scientific-gate generation;
- automated threshold selection;
- direct symbolic-expression reasoning as a Landscape truth oracle;
- mandatory ModelingToolkit/Julia runtime dependency;
- changes to P0 Burgers scoring or miner strategy schema;
- changes to Bittensor emissions;
- automatic coupled-system Challenge generation.

---

## 12. First integration test: Burgers semantic prototype

The first test should be an **authoring-only** `PhysicalSystemSpec` for the existing 1D viscous Burgers Challenge.

Success means:

1. a scientist can inspect one structured object and identify the system variables, parameters, governing relation, conditions, assumptions, and registered physical features;
2. the object can be linked to the existing generator, dossier, Challenge, and evidence provenance without changing runtime behavior;
3. no official seed, realized draw, or protected exam state is exposed;
4. no score/gate changes are implied;
5. the representation can be produced manually and, separately, through a reference symbolic-numeric adapter without changing its semantic meaning.

Failure of this prototype should cause schema simplification before broader integration.

---

## 13. Proposed research hypotheses

These are not current score inputs or established results.

### H16 — Structured physical context improves transfer prediction

Landscape conditioned on qualified physical context predicts intervention transfer across Challenges better than Challenge ID and ordinary metadata alone.

### H17 — Structured scientific authoring improves Challenge construction

Reusable physical-system metadata and evaluation primitives reduce Challenge-authoring time/error without weakening scientific validity.

### H18 — Hybrid model-construction search adds value in appropriate regimes

For selected Challenge classes, searching hybrid mechanistic/learned construction strategies improves qualification outcomes or engineering decision economics relative to black-box surrogate search alone.

### H19 — Physical context improves experiment allocation

Information-value experiment selection conditioned on structured physical features produces more transferable decision value than allocation based only on unstructured experiment history.

These hypotheses belong to future empirical work and must not be asserted as implementation facts.

---

## 14. Integration principle

> **Make Carbon scientifically representation-aware now; defer symbolic runtime machinery until the lean experimental system works.**

The intended endpoint is not a symbolic-numeric modeling platform. It is a Carbon evidence system capable of learning how model-construction interventions interact with identifiable physical structure, regime, and engineering context.
