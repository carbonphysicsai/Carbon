# Poisson 2D — PhysicalSystemSpec Generality Test

**Status:** DESIGN TEST / NON-RUNTIME / NON-SCORING  
**System:** Poisson 2D  
**Purpose:** Determine whether the minimal `PhysicalSystemSpec v0.1` candidate survives a structurally different physics family after Burgers.

---

## 1. Test question

Burgers is evolutionary, one-dimensional, nonlinear, time-dependent, periodic, and uses a scalar viscosity parameter.

Poisson is a useful second test because the reviewed repository material is:

- elliptic/static rather than evolutionary;
- two-dimensional;
- Dirichlet-bounded rather than periodic;
- naturally capable of field-valued coefficients and source fields;
- represented by multiple existing source variants that are not scientifically identical.

The schema passes only if it can preserve those differences without changing the meaning of its Burgers-era core concepts.

---

## 2. Reviewed source facts

### Source A — legacy Python Challenge

`carbon/challenges/poisson_2d.py` provides:

- 2D unit-square coordinates;
- a metadata relation `∇²u = f`;
- Dirichlet boundary type metadata;
- manufactured field `u = sin(pi x) sin(pi y)`;
- `f = -2*pi^2*u`, consistent with `∇²u=f`;
- resolution `(128,128)`;
- additive Gaussian noise of scale `0.02` in `u_noisy`;
- fixed train/holdout/stress slicing of repeated generated tensors;
- legacy symbolic metadata including suggested loss weights and labels.

This source is useful for representation testing but is not treated here as a current normative Challenge contract.

### Source B — legacy Julia reference path

`Julia/src/solvers/reference.jl` describes/attempts:

```text
-∇·(k∇u) = f
```

with:

- two-dimensional domain;
- field-valued coefficient `k`;
- field-valued source `f`;
- zero Dirichlet boundary values;
- a discrete divergence-form numerical realization;
- source labels referring to MethodOfLines + KLU.

This is a broader physical model than Source A. Its presence does not itself establish dossier quality or reference rank.

---

## 3. Critical reconciliation finding

The repository does **not** currently support treating “Poisson 2D” as one canonical physical-system object.

The two reviewed relations are different:

```text
A:  ∇²u = f
B: -∇·(k∇u) = f
```

Even with constant `k`, sign convention and model definition must be chosen explicitly. With spatially varying `k`, Source B is plainly a broader variable-coefficient elliptic problem.

### Decision

**Do not choose a canonical Poisson relation during this schema test.**

That would convert legacy implementation material into new scientific authority without a registered Challenge owner, envelope, generator dossier, and versioned Score Pack.

Instead, encode both as provenance-scoped source variants and require a future canonical Poisson Challenge to select/version its intended model deliberately.

This is a successful behavior of `PhysicalSystemSpec`: disagreement remains visible rather than being normalized away.

---

## 4. Schema stress results

### 4.1 No time variable — PASS

The v0.1 candidate already treats independent variables as a list rather than requiring time. Poisson uses only `x,y`.

**No schema redesign required.**

### 4.2 Two spatial dimensions — PASS

The existing independent-variable/domain model extends naturally from Burgers `x` to Poisson `x,y`.

**No schema redesign required.**

### 4.3 Elliptic system class — PASS

`system_class` is descriptive and accommodates `elliptic_pde` without changing relation semantics.

**No schema redesign required.**

### 4.4 Dirichlet boundaries — PASS

The conditions layer can represent a zero Dirichlet condition on the spatial boundary, while Burgers separately used periodic topology.

**No schema redesign required.**

### 4.5 No initial condition — PASS

Initial conditions are scientifically optional. An elliptic problem does not receive a fabricated time/initial condition merely to satisfy a schema.

**No schema redesign required.**

### 4.6 Field-valued coefficient/source — PASS WITH BOUNDED EXTENSION

Burgers only demonstrated a scalar parameter `nu`. The Julia Poisson variant requires `k(x,y)` and both variants require source field `f(x,y)`.

This justifies distinguishing:

```text
parameter
field(name, role)
```

where a field may carry roles such as `coefficient` or `source`.

`RELATION_IR` prototype-0.2 adds this one generic leaf. It does not add framework-specific field types or vector-calculus shorthand.

**This is the first justified extension produced by the second-system test.**

### 4.7 Vector-calculus shorthand — NOT NEEDED YET

The variable-coefficient relation can be expressed using existing algebra + partial derivatives:

```text
-[d_x(k*d_x(u)) + d_y(k*d_y(u))] = f
```

Therefore `grad`, `div`, and `laplacian` are not added merely for notation convenience.

### 4.8 Manufactured solution vs physical model — PASS / IMPORTANT DISTINCTION

The Python source supplies one manufactured solution. `PhysicalSystemSpec` must keep this separate from the general governing relation.

This validates the need to distinguish:

```text
physical model semantics
≠
reference/manufactured case
≠
generator distribution
```

The manufactured case belongs in numerical/reference provenance, not as the definition of the entire physical system.

### 4.9 Legacy symbolic metadata — CORRECTLY EXCLUDED

The Python object includes suggested loss weights, symmetry labels, and `hard_constraints`. None is promoted into v0.1 core semantics because:

- suggested loss weights belong to strategy/scoring design, not physical-system truth;
- a symmetry label requires clear scientific/representation semantics before becoming ontology;
- `elliptic` is already represented by system class and is not a hard Carbon gate by implication.

This confirms the minimization rule is working.

---

## 5. Generality verdict

### **PASS WITH ONE BOUNDED EXTENSION**

Poisson does not require reinterpretation of the core Burgers-era contract. It requires only one justified addition:

> **field-valued scientific objects must be distinct from ordinary parameters.**

Everything else fits existing concepts:

- independent variables;
- state variables;
- domains;
- governing relations;
- conditions;
- assumptions;
- numerical realization references;
- provenance;
- reconciliation issues.

This is strong evidence that the minimal schema is representing physical-system structure rather than Burgers-specific implementation details.

It is **not** evidence that the schema is universal across all physics.

---

## 6. New preliminary decisions

### SN-P1 — Keep `field` as the only Poisson-driven IR extension

**Decision:** add `field(name, role)` to Relation IR prototype-0.2.

Do not add `grad`, `div`, `laplacian`, tensor notation, weak forms, or FEM semantics yet.

### SN-P2 — Do not ratify a canonical Poisson Challenge from legacy sources

**Decision:** preserve both reviewed source variants. A future canonical Challenge must deliberately select its governing relation, sign convention, coefficient model, source distribution, boundary class, generator, reference rank, envelope, and Score Pack.

### SN-P3 — Separate manufactured/reference cases from system semantics

**Decision:** manufactured analytic solutions may be attached as reference/dossier provenance; they do not define the full physical model or Challenge distribution by themselves.

### SN-P4 — Do not promote legacy symbolic-loss metadata

**Decision:** suggested loss weights, baseline errors, loose symmetry labels, and old `hard_constraints` fields are not imported into `PhysicalSystemSpec` core semantics.

---

## 7. What this says about v0.1

The `PhysicalSystemSpec v0.1` candidate is now narrow enough to be useful and broad enough to represent two structurally different PDE classes.

Before calling it ratified, the next step should be **schema minimization and structural-validation design**, not a third physics family immediately.

The recommended next work is:

1. turn the semantic candidate into a precise authoring schema with typed missing states;
2. define a non-scientific `PhysicalSystemSpecValidator` contract;
3. test Burgers and Poisson prototypes against it;
4. only then build a ModelingToolkit adapter against the stable target;
5. keep all of this off miner/validator runtime until explicitly integrated later.

---

## 8. Final conclusion

> **Poisson validates the architecture by forcing Carbon to preserve model variation, field-valued physics, static PDE semantics, and manufactured-reference separation without widening scientific authority.**

The second-system test supports continuing the symbolic-numeric integration.
