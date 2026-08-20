# PhysicalSystemSpec v0.1 — Minimal Candidate

**Status:** DESIGN CANDIDATE / NON-RUNTIME / NON-SCORING  
**Purpose:** Freeze the smallest semantic contract justified by the Burgers traceability test before testing generality on a second physics family.  
**Authority:** This document does not override generator, dossier, envelope, scoring, registry, disclosure, or product specifications.

---

## 1. Design rule

The v0.1 candidate contains only information needed to answer four questions:

1. **What physical model is being described?**
2. **What variables, parameters/fields, conditions, and relations define that model?**
3. **Which Carbon Challenge/generator/reference artifacts does the description apply to?**
4. **What assumptions, provenance, and unresolved conflicts constrain interpretation?**

Everything else is an extension until a real Challenge demonstrates need.

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
    coefficient_fields[]?
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
- coefficient fields / spatially varying material properties;
- initial conditions (not applicable to many elliptic problems);
- boundary conditions;
- observations;
- numerical realization references;
- exclusions;
- reconciliation issues.

**Important:** optional means scientifically optional, not permission to omit known required Challenge semantics.

---

## 4. Variable classes

The Burgers prototype required scalar parameters such as viscosity. Poisson generality testing demonstrates that v0.1 must also distinguish a **coefficient field** from an ordinary scalar parameter.

Use these conceptual classes:

```text
independent_variable   e.g. x, y, t
state_variable         e.g. u(x,t), u(x,y)
parameter              e.g. nu, material scalar
coefficient_field      e.g. k(x,y)
observed_variable      optional output/observable distinct from state
```

A field-valued coefficient is not silently flattened into `parameters` because its dependence on independent variables is scientifically meaningful.

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

They may appear as extensions after a real Challenge requires them.

---

## 10. Generality gate

This candidate is not ratified merely because it fits Burgers. It must survive a structurally different second-system test without requiring a rewrite of the core concepts.

**Chosen second system:** Poisson 2D.

The test specifically checks whether v0.1 can represent:

- no temporal independent variable;
- elliptic rather than evolutionary PDE semantics;
- two spatial dimensions;
- Dirichlet boundaries;
- optional coefficient fields;
- multiple source variants that disagree on the exact governing relation;
- a manufactured analytic field/reference case without confusing that case with the general physical model.

If Poisson requires only bounded extensions/optional fields, the v0.1 abstraction passes its first generality test. If it requires changing the meaning of existing core fields, v0.1 fails and must be revised before ratification.
