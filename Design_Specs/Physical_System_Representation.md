# Carbon Physical System Representation

**Status:** DESIGN INTEGRATION DRAFT — non-runtime, non-scoring, pending review/ratification.  
**Purpose:** Add a representation-agnostic physical semantic layer for Challenge authoring, scientific traceability, later Landscape transfer reasoning, and later product qualification without changing P0 scoring or execution semantics.  
**Does not override:** `Scoring.md`, `Generator_Creation.md`, `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Landscape_Agent.md`, `Specialist_Bank.md`, or `Build_Out.md` sequencing.

---

## 1. Design objective

Carbon already binds scientific meaning through a Challenge, generator, Score Pack, Validation Dossier, strategy schema, and protected evaluation contract. This is sufficient for P0. Long-term physics intelligence benefits from a machine-readable description of **what physical system a Challenge claims to represent**.

This draft introduces:

```text
PhysicalSystemSpec
```

A `PhysicalSystemSpec` is descriptive scientific metadata. It is **not** a score, gate, proof of scientific validity, runtime truth oracle, or substitute for a Validation Dossier.

The intended authority chain is:

```text
DOMAIN SCIENCE / PARTNER REQUIREMENTS
        ↓
PhysicalSystemSpec
        ↓
Envelope freeze
        ↓
Generator / reference realization
        ↓
Validation Dossier
        ↓
registered Challenge + Score Pack
        ↓
authoritative evaluation
```

Existing semantic owners remain authoritative at each downstream step.

---

## 2. Constitutional invariants

1. **The symbolic/structured model does not certify the physical model.**
2. **Derived evaluation primitives are candidates until scientifically qualified.**
3. **`PhysicalSystemSpec` cannot silently create or modify a gate, threshold, Score Pack, or `S_combined`.**
4. **Scientific validity remains owned by the qualified Challenge / dossier / governance path.**
5. **Symbolic equivalence does not imply numerical, statistical, or operational equivalence.**
6. **Carbon remains representation-agnostic.** ModelingToolkit, Modelica, SBML, CellML, SymPy, or manual authoring may be adapters; none is the protocol ontology by itself.
7. **Missing structure is preferable to fabricated structure.** Fields may be absent, unknown, assumption-bound, not applicable, or `HUMAN_INPUT`.
8. **No new P0 runtime dependency is created by this spec.**
9. **No physical metadata may leak protected official realizations, hidden seed information, master-secret material, or reconstruction-sensitive exam state.**
10. **Historical evidence binds the exact physical-system artifact bytes when one is present; later semantic versions do not silently reinterpret old evidence.**
11. **A3 remains the canonical byte-identity authority for registered physical-system artifacts.** Do not create a competing canonical content-hash field inside the artifact.
12. **A4 seed-domain semantics and A5 ScoreEngine semantics remain independent of this representation.**

---

## 3. Challenge relationship and identity

The completed A3 Challenge Registry already provides a generic content-addressed artifact map. The preferred integration is therefore a conventional optional artifact binding:

```text
ChallengeRecord.artifacts["physical_system_spec"]
    → ArtifactBinding(path, sha256:<digest>)
```

Do **not** migrate the completed A3 top-level schema merely to add separate physical-system id/version/hash fields.

When present:

- A3 binds and verifies the exact artifact bytes through its existing tagged SHA-256 semantics;
- the artifact itself may carry a **semantic** `physical_system_spec_id` and `version` for human/machine interpretation;
- the internal semantic id/version are not a second byte-identity authority;
- absence remains valid unless a future ratified Challenge class explicitly requires the artifact;
- once declared, missing or digest-mismatched bytes fail the ordinary A3 artifact-integrity check for that exact Challenge record;
- no new qualification slot is implied merely by binding the artifact.

### 3.1 Identity rule

Use two distinct concepts:

```text
semantic identity: physical_system_spec_id + version
byte identity:     A3 ArtifactBinding.digest
```

A standalone authoring tool may compute temporary hashes for convenience, but no internal `content_hash` field is canonical unless a future explicit migration changes this rule.

---

## 4. Minimum conceptual schema

The exact serialization is not ratified. The semantic information classes are:

```text
PhysicalSystemSpec {
  physical_system_spec_id
  version
  status

  challenge_binding {
    challenge_id
    generator_version
    optional score_pack / dossier references
  }

  system {
    family
    dimension
    system_class
  }

  operator_problem

  independent_variables
  state_variables
  observed_variables

  parameters {
    symbols
    units
    admissible / role-specific domains
  }

  governing_relations
  initial_condition_family
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

  numerical_realization_refs
  assumptions
  known_reconciliation_issues
  provenance
  references
  publication
}
```

### 4.1 Field semantics

- **governing relations:** equations or structural relations describing the scientific model; never automatic gates.
- **units:** scientific metadata where available; dimensional tooling may use them only under qualified rules.
- **domains/envelopes:** descriptive scientific bounds, distinct from hidden realized draws. The authoritative claim boundary remains owned by `Evidence_and_Envelope_Standards.md` and the registered Challenge evidence.
- **known invariants/conserved quantities:** candidate structure requiring dossier/Challenge qualification before score-bearing use.
- **dimensionless groups/regime features:** human-qualified features that may support Challenge description, Landscape analysis, and later product-envelope semantics.
- **assumptions:** mandatory where a relation or feature only holds conditionally.
- **known reconciliation issues:** explicit place to preserve unresolved source conflicts instead of silently choosing a value.

---

## 5. Public/private boundary

Current generator doctrine makes generator code and parameter ranges public while keeping live eval/stress tensors and protected seed material private. A `PhysicalSystemSpec` should therefore be designed as **public Challenge semantics by default** when it contains only already-public scientific structure.

It must never contain:

- official realized seeds or draw IDs;
- master-secret material;
- hidden eval/stress tensors;
- reconstruction-sensitive protected exam state;
- private partner information not separately authorized for publication.

Whether a particular artifact is actually published remains a Challenge/governance decision; the schema itself must be safe for public use.

---

## 6. Representation adapters

Carbon owns the semantic contract, not a modeling language.

Potential adapters:

```text
ModelingToolkit ─┐
Modelica         ├──► PhysicalSystemSpec
SBML / CellML   ┤
SymPy            │
manual authoring ┘
```

An adapter may parse, map, or validate representable structure. It may not invent scientific claims, gates, thresholds, or missing production metadata.

ModelingToolkit is a candidate reference adapter because it exposes structured variables, parameters, equations, hierarchical composition, and symbolic-numeric models. It is an authoring/integration tool only; no Julia or ModelingToolkit dependency is implied for miner/validator runtime.

---

## 7. Physics Evaluation Primitive Library

A later Challenge-authoring layer may consume a `PhysicalSystemSpec` to propose reusable **candidate** evaluation primitives.

Potential families include:

- governing-relation residuals;
- conservation / invariant diagnostics;
- admissibility diagnostics;
- initial / boundary consistency diagnostics;
- dimensional checks;
- physical regime feature extraction.

For every primitive, the numerical implementation/discretization, normalization, aggregation, tolerance, applicability assumptions, and gate status remain separately qualified scientific choices.

**Invariant:** no primitive becomes score-bearing merely because it can be derived or computed.

---

## 8. Validation Dossier linkage

Where the representation is used, the Validation Dossier should eventually trace:

```text
PhysicalSystemSpec relation / assumption
        ↓
reference realization
        ↓
convergence / reference evidence
        ↓
candidate evaluation primitive
        ↓
human-qualified metric definition
        ↓
Score Pack threshold / gate
```

This is the primary scientific integration point. It improves traceability without automating scientific judgment.

---

## 9. Wave-A boundaries

### A3 — completed; wrap only

Reuse the generic artifact map. Do not reopen the strict top-level schema.

### A4 — seed/leakage boundary

`PhysicalSystemSpec` does not participate in seed derivation or role-domain separation. Its only A4 obligation is to contain no protected seed/draw/reconstruction material.

### A5 — scoring boundary

The ScoreEngine must not parse `PhysicalSystemSpec` to determine gates, thresholds, weights, or score. Official scoring remains metrics + registered Score Pack under `Scoring.md`.

### A6 — first natural evidence propagation point

When A6 is implemented, internal evidence may preserve the physical-system artifact digest plus semantic id/version for future Landscape joins. Trusted-root paths should not be exposed to miners; miner-facing `EvaluationCard` disclosure remains allow-listed.

---

## 10. Landscape integration

The long-term intervention-outcome record should be capable of conditioning evidence on structured physical context.

Current conceptual experiment:

```text
E = (H, C, X, Y, P)
```

Future-compatible extension:

```text
E = (H, C, Φ, X, Y, P)
```

where `Φ` references the applicable physical-system artifact/semantic identity or a separately qualified derived physical-feature representation.

Prefer two linked structures initially:

```text
Experimental graph
strategy → execution → outcome → qualification

Physical graph
system family → relations/components → regime features → constraints/invariants
```

Physical similarity does not establish transfer or causality. Landscape claims remain typed as observed/predictive/causal-candidate/experimentally-supported under the ratified epistemic contract.

---

## 11. Product / qualification integration

A future Product Candidate Model Card / Product Battery Record / Qualification Record may bind the exact physical-system artifact/semantic identity where useful.

This can improve traceability when raw parameter bounds do not fully express a regime. The representation does not expand a context of use, authorize runtime use, or inherit qualification across a changed physical-system version.

---

## 12. Long-term model-class expansion

Neural operators remain Carbon's first practical model class. The trust architecture should not make neural-network architecture a permanent conceptual boundary.

A later generic concept may be `FastPhysicalModel`: a computational artifact intended to approximate, accelerate, or augment a more expensive physical model within a registered scientific context.

Potential later classes include learned operators, hybrid mechanistic/learned models, learned closures, reduced-order models, and differentiable surrogates. Likewise, selected future Challenges may generalize `TrainingStrategy` into `ModelConstructionStrategy`.

Do not implement these abstractions in P0 merely because the design anticipates them.

---

## 13. Explicitly out of scope for initial integration

- equation discovery as core P0 behavior;
- symbolic regression as an official initial Challenge class;
- automated gate generation;
- automated threshold selection;
- direct symbolic-expression reasoning as a Landscape truth oracle;
- mandatory ModelingToolkit/Julia runtime dependency;
- changes to P0 Burgers scoring or miner strategy schema;
- changes to Bittensor emissions;
- automatic coupled-system Challenge generation.

---

## 14. First integration test — Burgers semantic prototype

The first authoring-only prototype lives at:

```text
Design_Specs/physical_system_specs/burgers1d_v0.prototype.yaml
```

It should use only repository-supported scientific facts and explicitly preserve unresolved conflicts. In particular, the current executable config and scientific-justification source disagree on the lower bound of the Burgers stress-viscosity range; the prototype records the mismatch rather than silently choosing a new scientific value.

Success means:

1. a scientist can inspect one object and identify the currently implemented physical/generator semantics;
2. source conflicts and missing scientific authority are visible rather than fabricated away;
3. the object can later be bound through A3 without changing runtime behavior;
4. no protected exam realization is exposed;
5. no score/gate change is implied;
6. the same semantics can later be produced through a symbolic-numeric adapter without changing Carbon's authority model.

---

## 15. Research hypotheses

These remain future empirical hypotheses, not score inputs or established results.

- **H16:** qualified structured physical context improves cross-Challenge intervention-transfer prediction.
- **H17:** structured scientific authoring and reusable primitives reduce Challenge-authoring time/error without weakening scientific validity.
- **H18:** hybrid mechanistic/learned search improves qualification outcomes or engineering decision economics in appropriate regimes.
- **H19:** physical-context-aware experiment allocation improves transferable decision value relative to ordinary experiment-history baselines.

---

## 16. Integration principle

> **Make Carbon scientifically representation-aware now; defer symbolic runtime machinery until the lean experimental system works.**

The intended endpoint is not a symbolic-numeric modeling platform. It is a Carbon evidence system capable of learning how model-construction interventions interact with identifiable physical structure, regime, and engineering context.
