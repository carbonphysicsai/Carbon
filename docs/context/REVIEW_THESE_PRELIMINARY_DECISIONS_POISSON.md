# Review These Preliminary Decisions — Poisson Generality Test

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions; tech/science lead may accept, modify, or reject later.  
**Purpose:** Supplement `REVIEW_THESE_PRELIMINARY_DECISIONS.md` with decisions surfaced by the second-system Poisson test.

---

## Executive disposition

The Poisson test **passes** the `PhysicalSystemSpec v0.1` architecture with one bounded representation extension. It also exposes a source-model conflict that should remain unresolved until Carbon deliberately creates a canonical Poisson Challenge.

Proceed provisionally with P1–P4 below.

---

## P1 — Field-valued scientific objects

### Preliminary decision: **ACCEPT**

Extend Relation IR leaves from:

```text
var, param, const
```

to:

```text
var, param, field, const
```

with:

```text
field(name, role)
```

where role may describe a field as a coefficient, source, or later another scientifically defined role.

### Why

The Julia Poisson source uses a spatial coefficient `k(x,y)` and a source field `f(x,y)`. Treating those as ordinary scalar parameters would erase scientifically meaningful dependence on the independent variables.

### Guardrail

Do not introduce framework-specific leaves such as `ModelingToolkitCoefficientField`. Carbon owns the semantic contract.

### Confidence

**Very high.**

---

## P2 — Canonical Poisson governing relation

### Preliminary decision: **DO NOT RATIFY ONE YET**

Reviewed sources disagree materially:

```text
legacy Python:  ∇²u = f
legacy Julia:  -∇·(k∇u) = f
```

### Why

These are not merely two textual forms of one already registered Carbon Challenge. The Julia form introduces a potentially spatially varying coefficient field and a different sign convention/model definition.

Choosing either now would promote legacy implementation material into scientific authority without a canonical Challenge owner, envelope, generator dossier, reference rank, and Score Pack.

### Required future action

When Carbon intentionally builds a Poisson Challenge, explicitly choose and version:

- constant- vs variable-coefficient model;
- sign convention;
- coefficient/source distributions;
- boundary class;
- operating envelope and exclusions;
- reference backend/rank;
- generator and Score Pack.

Then `PhysicalSystemSpec` follows that registered scientific decision.

### Confidence

**Very high.**

---

## P3 — Manufactured solution separation

### Preliminary decision: **ACCEPT**

The Python source's

```text
u = sin(pi*x) sin(pi*y)
f = -2*pi^2*u
```

is a manufactured/reference case, not the general definition of the Poisson physical model or a complete Challenge distribution.

Keep it under reference/numerical provenance rather than encoding it as the governing system itself.

### Why

This distinction prevents Carbon from confusing:

```text
physical relation
!= one analytic/reference case
!= procedural generator distribution
!= official hidden exam realization
```

### Confidence

**Very high.**

---

## P4 — Do not import legacy symbolic optimization metadata

### Preliminary decision: **ACCEPT**

Do not import the legacy Python Poisson object's:

- suggested loss weights;
- baseline error;
- loose symmetry label;
- `hard_constraints: [elliptic]`;

into `PhysicalSystemSpec v0.1` core semantics.

### Why

- Loss weights are optimization/strategy semantics, not physical-system truth.
- Baseline error is empirical/model evidence, not physical structure.
- Symmetry requires a defined semantic ontology before becoming machine authority.
- `elliptic` is already a descriptive system class and does not imply a Carbon hard gate.

### Confidence

**Very high.**

---

## Generality verdict

```text
PhysicalSystemSpec v0.1 candidate
        +
Poisson second-system test
        =
PASS WITH ONE BOUNDED EXTENSION
```

The only required extension is explicit support for field-valued scientific objects. No change was needed to the meaning of identity, independent/state variables, domains, governing relations, conditions, assumptions, numerical provenance, or reconciliation issues.

---

## Recommended tech-lead action later

```text
P1  ACCEPT / MODIFY / REJECT
P2  ACCEPT / MODIFY / REJECT
P3  ACCEPT / MODIFY / REJECT
P4  ACCEPT / MODIFY / REJECT
```

The most important review question is P2: confirm that no current normative source outside the reviewed material already defines a canonical Poisson Challenge. If one exists, reconcile the prototype to that authority rather than to legacy implementation code.

---

## Owner preliminary conclusion

> **Poisson supports ratifying the shape of the physical semantic layer, but it does not support ratifying a Poisson scientific contract. Carbon should represent source disagreement faithfully and let a future qualified Challenge decide the physics.**
