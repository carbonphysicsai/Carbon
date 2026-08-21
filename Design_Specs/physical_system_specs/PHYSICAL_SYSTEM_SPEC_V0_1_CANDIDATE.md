# PhysicalSystemSpec v0.1 — Minimal Candidate

**Status:** DESIGN CANDIDATE / NON-RUNTIME / NON-SCORING  
**Purpose:** Freeze the smallest semantic contract justified by the Burgers traceability test and Poisson generality test.  
**Authority:** This document does not override generator, dossier, envelope, scoring, registry, disclosure, or product specifications.

---

## 1. Design rule

The v0.1 candidate contains only information needed to answer four questions:

1. **What physical model is being described?**
2. **What variables, parameters/fields, conditions, and relations define that model?**
3. **Which Carbon Challenge/generator/reference artifacts does the description apply to?**
4. **What assumptions, provenance, and unresolved conflicts constrain interpretation?**

Everything else remains an extension until a real Challenge demonstrates need.

### 1.1 Future-variable policy

**Decision:** do not place anticipated future scientific/model variables in the v0.1 core merely to future-proof the schema.

The core should not yet encode dimensionless-group ontologies, tensor/geometry systems, stochastic-process metadata, DAE index structure, events, learned-component locations, product context-of-use, or other unproven abstractions.

However, v0.1 reserves an optional, namespaced `extensions` container so experimental authoring metadata can be carried without forcing immediate core-schema migration:

```text
extensions {
  <namespace> {
    extension_version
    payload
  }
}
```

Rules:

- extension namespaces must be explicit and collision-resistant (for example `carbon.regime_features` or `adapter.modelingtoolkit` rather than generic `features`);
- extension payloads are **non-core** and must not be required to interpret v0.1 core semantics;
- an extension cannot create score, gate, threshold, LIVE, disclosure, or qualification authority;
- validators may validate the outer extension envelope while treating unknown payloads as opaque;
- a concept is promoted into a later core schema only after multiple real Challenges demonstrate stable semantics and clear ownership;
- historical evidence remains bound to the exact artifact bytes, so later promotion does not reinterpret old artifacts silently.

This gives Carbon extensibility without pretending to know the final ontology of physics.

---

## 2. Minimum semantic contract

```text
PhysicalSystemSpec {
  physical_system_spec_id
  version
  status
  classification

  challenge_binding {
    challenge_id
    generator_version?
    registry_artifact_id?
  }

  system {
    family
    system_class
    spatial_dimension
  }

  variables {
    independent[]
    state[]
    fields[]?
    observed[]?
  }

  parameters[]?

  governing_relations[]

  conditions {
    initial[]?
    boundary[]?
  }

  domains

  numerical_realization_refs[]?

  assumptions[]
  exclusions[]?
  provenance
  reconciliation_issues[]?

  extensions{}?
}
```

This is a semantic shape, not a final YAML/JSON schema.

---

## 3. Required vs optional

### Required in v0.1

- semantic id + version;
- status/classification;
- physical family/class/dimension;
- declared independent variables;
- at least one state variable;
- at least one governing relation, or an explicit typed `UNRESOLVED` state during authoring;
- domain description sufficient to scope the relation;
- assumptions;
- provenance.

### Optional where scientifically applicable

- ordinary scalar/tensor parameters;
- field-valued coefficients, sources, or other declared scientific fields;
- initial conditions (not applicable to many elliptic problems);
- boundary conditions;
- observations;
- numerical realization references;
- exclusions;
- reconciliation issues;
- namespaced extensions.

**Important:** optional means scientifically optional, not permission to omit known required Challenge semantics.

---

## 4. Variable and field classes

The Burgers prototype required scalar parameters such as viscosity. Poisson generality testing demonstrated that v0.1 must also distinguish a **field-valued scientific quantity** from an ordinary scalar parameter.

Use these conceptual classes:

```text
independent_variable   e.g. x, y, t
state_variable         e.g. u(x,t), u(x,y)
parameter              e.g. nu, material scalar
field                   e.g. k(x,y), f(x,y)
observed_variable      optional output/observable distinct from state
```

A field is not silently flattened into `parameters` because its dependence on independent variables is scientifically meaningful. The field should carry an explicit `role` such as `coefficient`, `source`, `forcing`, or another reviewed semantic role; the role does not create evaluation authority.

---

## 5. Governing relation representation

Each relation should carry:

```text
relation_id
kind
machine_semantics   # Carbon relation IR or typed unresolved state
display_text        # presentation/review only
assumptions[]?
provenance[]
```

`display_text` is not identity-bearing. The machine representation is descriptive scientific structure only; neither form creates a residual metric, gate, threshold, or score.

The first IR remains intentionally small. The Poisson test should express divergence-form relations through explicit partial derivatives and algebra rather than adding `grad`, `div`, or `laplacian` merely for notation convenience. New operators are added only when they encode semantics that cannot be represented cleanly and unambiguously by the existing grammar.

---

## 6. Conditions

Conditions are first-class because different physical systems require different condition classes.

```text
condition {
  condition_id
  type              # e.g. dirichlet, neumann, periodic, initial
  target
  region
  value/relation
  provenance
}
```

No condition automatically becomes a Carbon hard gate. A condition may later support a candidate diagnostic that must pass through scientific qualification.

---

## 7. Identity

```text
semantic identity = physical_system_spec_id + version
byte identity     = A3 ArtifactBinding.digest
```

No second canonical content hash exists inside the spec.

---

## 8. Public/private classification

Classification is instance-level:

```text
public_challenge_semantics
controlled_partner_semantics
```

Only the first class is presumed publishable. Neither class may contain official seed material or materialized hidden exam realizations.

---

## 9. Deliberately deferred from v0.1 core

Do not promote these into the core contract yet:

- conserved-quantity ontology;
- dimensionless-group ontology;
- regime taxonomy;
- automatic symmetry representation;
- symbolic equivalence/canonicalization;
- geometry CAD representation;
- events/hybrid automata;
- stochastic-process semantics;
- DAE index metadata;
- integral/operator shorthand;
- learned-component locations;
- product context-of-use fields;
- Score Pack fields;
- evaluation primitive definitions.

They may appear experimentally under a namespaced `extensions` payload, but they remain non-core and non-authoritative until a future schema revision explicitly promotes them.

---

## 10. Generality result

The candidate survived a structurally different second-system test using Poisson 2D.

The test demonstrated that v0.1 can represent:

- no temporal independent variable;
- elliptic rather than evolutionary PDE semantics;
- two spatial dimensions;
- Dirichlet boundaries;
- field-valued coefficient/source quantities;
- multiple source variants that disagree on the exact governing relation;
- a manufactured analytic field/reference case without confusing that case with the general physical model.

Poisson required one bounded semantic extension: explicit field-valued quantities. It did not require changing the meaning of the core identity, relation, condition, domain, provenance, or assumption concepts.

**Generality verdict: PASS WITH ONE BOUNDED CORE EXTENSION.**

The next gate is structural validation: prove that a machine can validate the contract's shape and internal references without claiming to validate the physics.
