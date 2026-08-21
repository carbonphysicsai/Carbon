# PhysicalSystemSpec Structural Validator — v0.1 Design

**Status:** DESIGN / AUTHORING TOOL / NON-RUNTIME / NON-SCORING  
**Target:** `PhysicalSystemSpec v0.1` candidate  
**Purpose:** Validate structure, symbol references, classification boundaries, and forbidden content without claiming scientific validity.

---

## 1. Constitutional boundary

The validator answers:

> **Is this artifact structurally well formed under the Carbon authoring contract?**

It does **not** answer:

> **Is this the correct physical model?**

Therefore a successful validation result means only that:

- required fields exist;
- identifiers are well formed and unique where required;
- relation trees use supported operators;
- referenced variables/parameters/fields resolve;
- derivatives are taken with respect to declared independent variables;
- conditions refer to declared targets;
- extension envelopes are well formed;
- known forbidden protected-material keys are absent;
- the document is internally self-consistent enough for scientific review.

Successful structural validation cannot:

- qualify a Challenge;
- create a gate or threshold;
- establish a Validation Dossier result;
- imply symbolic equivalence;
- establish scientific correctness;
- establish numerical adequacy;
- establish product qualification.

---

## 2. Validation levels

### ERROR

The artifact violates the v0.1 structural contract and should not be registered as a `PhysicalSystemSpec` without repair.

Examples:

- duplicate symbol identifiers;
- a relation references undeclared `u`;
- derivative with respect to undeclared `x`;
- unsupported operator in core relation IR;
- public artifact contains a forbidden protected-material field;
- state variable list is empty;
- malformed extension namespace.

### WARNING

The artifact is structurally parseable but contains unresolved or suspicious authoring state requiring scientific review.

Examples:

- governing relation is explicitly `UNRESOLVED`;
- no boundary conditions for a system where the author may have omitted them;
- reconciliation issues remain open;
- controlled/private classification is used without a documented transport policy;
- `display_text` is missing even though machine semantics exist.

### INFO

Non-blocking authoring observations.

---

## 3. Core symbol table

The validator builds a symbol table from:

```text
variables.independent
variables.state
variables.fields
parameters
variables.observed
```

Each symbol must be unique across categories unless a future schema version explicitly allows scoped namespaces.

Core relation leaves resolve as:

```text
var(name)   -> state/observed variable
param(name) -> parameter
field(name) -> declared field
const       -> no symbol lookup
```

Independent variables are referenced through derivative `wrt` fields rather than as ordinary `var` leaves in prototype v0.1.

---

## 4. Relation IR rules

Supported operators in v0.1:

```text
var
param
field
const
add
mul
pow
neg
eq
partial
derivative
```

Rules:

- `eq` has exactly two sides;
- `add`/`mul` have at least two operands;
- `neg` has exactly one expression;
- `pow` has base + exponent;
- `partial`/`derivative` have one expression, a declared independent-variable `wrt`, and positive integer `order`;
- `var`, `param`, and `field` must resolve to the appropriate declared symbol class;
- unknown operators are errors rather than silently accepted core semantics;
- no symbolic simplification or equivalence is performed.

---

## 5. Conditions

For each condition:

- `condition_id` must be unique;
- target must resolve to a declared state/field/observed symbol as appropriate;
- type must be a non-empty identifier;
- region must be explicitly present;
- value/relation may be scalar, structured relation, or typed unresolved state;
- provenance must be present for a ratifiable artifact.

The validator does not infer whether a condition is mathematically sufficient or physically appropriate.

---

## 6. Forbidden protected-material scan

A public or controlled `PhysicalSystemSpec` is descriptive semantics, never a carrier for realized official exam secrets.

The validator should reject any occurrence of explicitly forbidden semantic keys such as:

```text
master_secret
official_seed
official_seeds
live_eval_tensor
live_stress_tensor
materialized_eval
materialized_stress
hidden_exam_tensor
```

The scan is defense-in-depth only. It cannot prove that arbitrary prose or opaque extension payloads contain no sensitive information. Publication review and A4/A6/A9/A10 controls remain authoritative.

Unknown extension payloads must never be assumed public-safe merely because the outer spec validates.

---

## 7. Extension validation

Core validator checks only the outer envelope:

```text
extensions:
  <namespace>:
    extension_version: <non-empty string>
    payload: <any serializable mapping/value>
```

Namespace rules:

- must contain a dot or another explicitly ratified namespace separator;
- must not begin with reserved core namespaces unless owned by Carbon;
- duplicate namespaces are invalid at serialization level;
- unknown extension payloads are opaque to the core validator;
- passing core validation gives no scientific authority to extension contents.

A later extension-specific validator may be registered independently.

---

## 8. Typed unresolved state

Authoring artifacts need an honest way to represent known gaps.

v0.1 validator recognizes strings beginning with:

```text
UNRESOLVED
HUMAN_INPUT
UNKNOWN
```

as explicit authoring missing states where the schema permits them.

They generate warnings rather than fabricated defaults. They are not necessarily acceptable for a LIVE Challenge; registry/dossier policy decides that separately.

---

## 9. Reference implementation

A pure-Python reference validator lives at:

```text
Design_Specs/physical_system_specs/tools/physical_system_spec_validator.py
```

It accepts an already parsed Python mapping and returns a deterministic list of issues. It intentionally has no YAML parser dependency and no access to generator, scoring, validator, or network runtime code.

This keeps the validator an authoring-contract proof rather than a new runtime dependency.

---

## 10. Acceptance tests

Minimum tests should cover:

1. valid minimal evolutionary PDE;
2. valid elliptic PDE with field-valued source/coefficient;
3. undeclared relation variable fails;
4. undeclared derivative axis fails;
5. unsupported relation operator fails;
6. duplicate symbol fails;
7. malformed extension namespace fails;
8. forbidden secret key fails;
9. explicit unresolved governing relation warns rather than fabricating semantics;
10. changing display text alone does not affect structural machine-semantics checks.

---

## 11. Success criterion

The validator succeeds as an integration objective if it can make malformed semantic artifacts fail early **without acquiring any authority over scientific truth**.

> **Structure can be validated mechanically; physics remains qualified scientifically.**
