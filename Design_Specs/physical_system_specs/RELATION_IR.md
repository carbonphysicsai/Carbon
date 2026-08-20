# Physical Relation IR — provisional authoring contract

**Status:** DESIGN PROTOTYPE / NON-RUNTIME / NON-SCORING / pending tech-science review.  
**Purpose:** Provide the smallest representation-agnostic structure needed for a `PhysicalSystemSpec` to express governing mathematical relations without binding Carbon to ModelingToolkit, SymPy, Modelica, or another symbolic engine.

This file does **not** ratify a protocol ontology, evaluator, residual implementation, physics gate, or threshold.

---

## 1. Design decision

A physical relation should have two independently useful representations:

1. **human-readable canonical text** for scientific review;
2. **structured relation IR** for machine mapping, comparison, and adapter development.

The structured form is intentionally tiny. It represents mathematical structure, not numerical evaluation semantics.

For the current Burgers prototype, the implemented reference solver supports the relation:

```text
∂u/∂t + u ∂u/∂x = ν ∂²u/∂x²
```

because `poc/generators/burgers1d.py` advances the state according to explicit `-u * u_x` advection plus implicit `ν u_xx` viscosity.

This is a **provisional Carbon semantic representation of implemented P0 behavior**, pending tech/science-lead review. It is not imported merely from textbook convention.

---

## 2. Minimal relation object

```yaml
relation_id: governing_pde
relation_type: pde
relation_ir_version: "prototype-0.1"
canonical_text: "d_t(u) + u*d_x(u) = nu*d_xx(u)"
expression:
  op: eq
  args:
    - op: add
      args:
        - op: partial
          expr: {op: var, name: u}
          wrt: t
          order: 1
        - op: mul
          args:
            - {op: var, name: u}
            - op: partial
              expr: {op: var, name: u}
              wrt: x
              order: 1
    - op: mul
      args:
        - {op: param, name: nu}
        - op: partial
          expr: {op: var, name: u}
          wrt: x
          order: 2
```

The text and expression must describe the same relation. A future validator for authoring artifacts may check structural well-formedness; it must not infer scientific validity from successful parsing.

---

## 3. Prototype grammar

The first grammar should support only what an initial PDE/ODE authoring prototype needs.

### Leaves

```text
var(name)
param(name)
const(value)
```

### Algebra

```text
add(args...)
mul(args...)
pow(base, exponent)
neg(expr)
```

### Relations

```text
eq(lhs, rhs)
```

### Differential structure

```text
partial(expr, wrt=<independent-variable>, order=<positive integer>)
derivative(expr, wrt=<independent-variable>, order=<positive integer>)
```

`partial` is used for PDE structure; `derivative` may be used for ordinary derivatives where scientifically appropriate.

No implicit Einstein summation, tensor-index convention, weak-form semantics, integral operator, stochastic calculus, discontinuity/event semantics, or constitutive-law ontology is ratified in prototype-0.1. Additions require explicit versioning.

---

## 4. Why an AST instead of a framework object

Carbon needs scientific identity that survives changes in authoring tooling.

A ModelingToolkit adapter should eventually be able to map a supported symbolic system into this structure. A SymPy or Modelica adapter may do the same. Carbon should compare the resulting Carbon representation, not serialized framework internals.

The IR therefore deliberately excludes:

- Julia expression serialization;
- Python ASTs;
- ModelingToolkit UUIDs/types;
- solver-specific discretization objects;
- compiler/code-generation state;
- numerical tolerances.

Those belong to adapters, numerical realization provenance, or dossier evidence rather than the physical relation itself.

---

## 5. Equality and equivalence policy

Prototype-0.1 distinguishes **identity** from **mathematical equivalence**.

Two expression trees are identical only if their normalized serialized Carbon representation is identical under explicitly ratified serialization rules.

The following must **not** be assumed automatically in the initial integration:

```text
a + b  == b + a
u_t + u u_x = nu u_xx  == u_t + u u_x - nu u_xx = 0
expanded expression == factored expression
symbolic simplification == numerical equivalence
```

A later adapter/authoring layer may implement reviewed normalization rules, but symbolic equivalence cannot silently rewrite registered historical evidence.

---

## 6. Relationship to evaluation primitives

A governing relation may later be the source for a **candidate** residual primitive, but the relation itself contains no evaluation semantics.

For example, a future authoring tool could propose:

```text
R = d_t(u_hat) + u_hat*d_x(u_hat) - nu*d_xx(u_hat)
```

Carbon still requires separate scientific qualification of:

- how derivatives are estimated;
- grid/mesh assumptions;
- normalization;
- aggregation over space/time/batch;
- reference precision;
- applicable regime;
- tolerance;
- whether the metric is diagnostic, soft-score-bearing, or a hard gate.

Therefore:

```text
relation IR != residual definition != gate != threshold
```

---

## 7. Adapter contract

A future symbolic-numeric adapter may:

- map supported variables and parameters;
- map supported equality relations;
- map supported derivatives;
- report unsupported structure explicitly;
- preserve assumptions and source provenance.

It may not:

- invent missing scientific relations;
- silently simplify into a different registered meaning;
- assign score semantics;
- choose thresholds;
- claim physical validity because conversion succeeded.

A reference ModelingToolkit adapter should be tested by comparing its output to a manually reviewed Carbon relation IR for the same scientific model.

---

## 8. Burgers prototype acceptance test

The first manual representation passes the design test if a scientific reviewer can verify all of the following:

1. state variable `u`, independent variables `x,t`, and parameter `nu` resolve to declared `PhysicalSystemSpec` symbols;
2. the structured relation corresponds to the implemented reference evolution in `poc/generators/burgers1d.py`;
3. periodic boundary semantics remain separate from the PDE expression;
4. IC distribution and stress ranges remain separate from the PDE expression;
5. no seed/draw information is present;
6. no evaluation threshold or score semantics are present;
7. a future ModelingToolkit representation can map into the same Carbon semantic structure without making ModelingToolkit the protocol authority.

---

## 9. Open questions for review

- Should `canonical_text` use Unicode mathematical notation, ASCII-only normalized notation, or remain presentation-only with no identity semantics?
- Should commutative operators eventually receive a deterministic canonical ordering?
- Do tensor/vector systems require indexed expressions or typed vector operators first?
- When coupled systems arrive, should relations reference component scopes/namespaces?
- Should units attach only to variables/parameters, or also be statically checkable across expression nodes?
- What explicit relation types are required beyond `pde`, `ode`, algebraic constraint, constitutive relation, and inequality/admissibility relation?

None of these questions blocks the Burgers prototype.

---

## 10. Constitutional rule

> **Carbon may represent a governing relation without treating that representation as proof, evaluation, or scientific authority.**

The relation IR exists to make scientific structure traceable and portable across authoring ecosystems. The Challenge/dossier/Score-Pack chain remains responsible for deciding what the represented relation is allowed to mean operationally.
