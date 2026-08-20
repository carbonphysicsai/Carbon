# Physical Relation IR — provisional authoring contract

**Status:** DESIGN PROTOTYPE / NON-RUNTIME / NON-SCORING / pending tech-science review.  
**Purpose:** Provide the smallest representation-agnostic structure needed for a `PhysicalSystemSpec` to express governing mathematical relations without binding Carbon to ModelingToolkit, SymPy, Modelica, or another symbolic engine.

This file does **not** ratify a protocol ontology, evaluator, residual implementation, physics gate, or threshold.

---

## 1. Design decision

A physical relation should have two independently useful representations:

1. **human-readable display text** for scientific review;
2. **structured relation IR** for machine mapping, comparison, and adapter development.

`display_text` is presentation/review material and is **not identity-bearing machine semantics**. The structured form is intentionally tiny. It represents mathematical structure, not numerical evaluation semantics.

For the current Burgers prototype, the implemented reference solver supports the relation:

```text
∂u/∂t + u ∂u/∂x = ν ∂²u/∂x²
```

because `poc/generators/burgers1d.py` advances the state according to explicit `-u * u_x` advection plus implicit `ν u_xx` viscosity.

This is a provisional Carbon semantic representation of implemented P0 behavior, pending tech/science-lead review. It is not imported merely from textbook convention.

---

## 2. Minimal relation object

```yaml
relation_id: governing_pde
relation_type: pde
relation_ir_version: "prototype-0.2"
display_text: "d_t(u) + u*d_x(u) = nu*d_xx(u)"
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

The display text and expression should describe the same relation. A future validator for authoring artifacts may check structural well-formedness; it must not infer scientific validity from successful parsing.

---

## 3. Prototype grammar

The first grammar should support only what demonstrated Challenge cases require.

### Leaves

```text
var(name)                         # state/dependent variable
param(name)                       # scalar/tensor parameter not varying over declared independent variables
field(name, role)                 # field-valued coefficient/source/etc. over declared independent variables
const(value)
```

`field` was added after the Poisson generality test demonstrated a real need to distinguish spatially varying coefficient/source fields from ordinary scalar parameters. `role` is descriptive (for example `coefficient` or `source`) and is not a scoring or authority label.

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

No implicit Einstein summation, tensor-index convention, weak-form semantics, integral operator, stochastic calculus, discontinuity/event semantics, constitutive-law ontology, or automatic vector-calculus shorthand is ratified in prototype-0.2. Additions require demonstrated need and explicit versioning.

### Why no `grad`, `div`, or `laplacian` yet

The Poisson relation `-∇·(k∇u)=f` can be represented unambiguously in two dimensions as explicit partial derivatives:

```text
-[ d_x(k*d_x(u)) + d_y(k*d_y(u)) ] = f
```

Therefore the second-system test does not yet justify new vector-calculus operators. Carbon should add shorthand only when it carries necessary semantics rather than notation convenience.

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

Prototype-0.2 distinguishes **identity** from **mathematical equivalence**.

Two expression trees are structurally identical only under future explicitly ratified Carbon serialization/normalization rules. No general mathematical equivalence engine is part of the prototype.

The following must **not** be assumed automatically:

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

The Burgers traceability test additionally showed why this distinction matters: the existing PoC `residual_diagnostic()` omits the temporal derivative and is therefore a final-state spatial physics proxy, not the full PDE residual represented here.

---

## 7. Adapter contract

A future symbolic-numeric adapter may:

- map supported state variables, parameters, coefficient/source fields;
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

## 8. Demonstrated-system tests

### Burgers

The manual Burgers representation passes if a reviewer can verify that state `u`, independent variables `x,t`, parameter `nu`, and derivative structure match the implemented reference evolution without importing BC, IC-distribution, seed, or score semantics into the relation.

### Poisson

The second-system test checks that the same IR can represent both reviewed source variants without pretending they are identical:

```text
constant coefficient:      d_xx(u) + d_yy(u) = f
variable coefficient:     -d_x(k*d_x(u)) - d_y(k*d_y(u)) = f
```

Poisson justifies the `field` leaf because `k(x,y)` and `f(x,y)` are field-valued scientific objects. It does not yet justify vector-calculus shorthand or a larger ontology.

---

## 9. Open questions for later review

- Should commutative operators eventually receive a deterministic canonical ordering?
- Do tensor/vector systems require indexed expressions or typed vector operators first?
- When coupled systems arrive, should relations reference component scopes/namespaces?
- Should units attach only to declarations, or also be statically checkable across expression nodes?
- What explicit relation types are required beyond PDE, ODE, algebraic constraint, constitutive relation, and inequality/admissibility relation?

None of these questions blocks Burgers or Poisson authoring prototypes.

---

## 10. Constitutional rule

> **Carbon may represent a governing relation without treating that representation as proof, evaluation, or scientific authority.**

The relation IR exists to make scientific structure traceable and portable across authoring ecosystems. The Challenge/dossier/Score-Pack chain remains responsible for deciding what the represented relation is allowed to mean operationally.
